"""CLI entry point — scan repo, run rules, output clearly."""

import sys
from pathlib import Path

import click
import typer


def _err(msg: str) -> None:
    """Raise a styled error (red box) — used for all CLI errors."""
    raise click.BadParameter(msg)

# Subcommands (short names so "repofail gen" works)
_SUBCOMMANDS = {"gen", "s", "a", "sim", "check"}


def _preprocess_argv():
    """Fix argv so: (1) repofail . /path works via -p, (2) repofail . --json works."""
    argv = sys.argv[1:]
    if not argv:
        return
    first = argv[0]
    if first in _SUBCOMMANDS or first.startswith("-"):
        return
    # First token is path-like (not a subcommand). Convert to -p and optionally reorder options.
    path_tokens = [first]
    opt_tokens = ["-p", first]
    i = 1
    while i < len(argv):
        t = argv[i]
        if t.startswith("-"):
            opt_tokens.append(t)
            i += 1
            if "=" not in t and i < len(argv) and not argv[i].startswith("-") and t in ("--explain", "-e", "--path", "-p", "--fail-on"):
                opt_tokens.append(argv[i])
                i += 1
        else:
            path_tokens.append(t)
            opt_tokens.extend(["-p", t])
            i += 1
    sys.argv[1:] = opt_tokens

from .scanner import scan_repo, inspect_host
from .engine import run_rules
from .contract import generate_contract, validate_contract, EnvironmentContract
from .telemetry import save_report, get_stats
from .rules.base import Severity
from .rules.registry import RULE_INFO
from .risk import estimate_success_probability
from .format import format_human

app = typer.Typer(help="Predict why a repository will fail on your machine.")


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    json_out: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
    markdown_out: bool = typer.Option(False, "--markdown", "-m", help="Output as Markdown"),
    ci: bool = typer.Option(False, "--ci", help="CI mode: exit 1 if HIGH rules fire"),
    fail_on: str = typer.Option("HIGH", "--fail-on", help="In CI mode: fail on this severity or higher (HIGH/MEDIUM/LOW)"),
    explain: str = typer.Option(None, "--explain", "-e", help="Explain a rule by ID and exit"),
    report: bool = typer.Option(False, "--report", "-r", help="Save failure report locally (opt-in telemetry)"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Include rule IDs and low-confidence hints"),
    path: Path = typer.Option(Path("."), "--path", "-p", exists=True, file_okay=False, dir_okay=True, resolve_path=True, help="Repo path (default: .)"),
) -> None:
    """Scan a repository and report detected incompatibilities."""
    if ctx.invoked_subcommand is not None:
        return
    if explain:
        _print_explain(explain)
        return

    scan_path = path
    try:
        repo_profile = scan_repo(scan_path)
        host_profile = inspect_host()
        results = run_rules(repo_profile, host_profile)
    except NotADirectoryError as e:
        _err(str(e))

    if json_out:
        _print_json(repo_profile, host_profile, results, verbose)
    elif markdown_out:
        _print_markdown(repo_profile, host_profile, results)
    else:
        _print_human(repo_profile, host_profile, results, verbose)

    if report and results:
        saved = save_report(repo_profile.name or repo_profile.path, results, host_profile)
        if saved:
            typer.echo(f"Report saved: {saved}", err=True)

    if ci:
        _ci_exit(results, fail_on)


def _host_summary(host) -> str:
    """Build host summary string."""
    parts = [f"{host.os} {host.arch}"]
    if host.cuda_available:
        parts.append(f"CUDA {host.cuda_version or 'available'}")
    else:
        parts.append("no NVIDIA GPU")
    if getattr(host, "has_metal", False) and host.os == "macos":
        parts.append("Metal (MLX) available")
    if host.ram_gb is not None:
        parts.append(f"{host.ram_gb:.0f} GB RAM")
    return ", ".join(parts)


def _stack_items(repo_profile) -> list[str]:
    """Build detected stack items; never return empty."""
    items = []
    if repo_profile.python_version:
        items.append(f"Python {repo_profile.python_version}")
    elif repo_profile.has_pyproject or repo_profile.has_requirements_txt:
        items.append("Python project")
    if repo_profile.uses_torch:
        items.append("PyTorch")
    if repo_profile.uses_tensorflow:
        items.append("TensorFlow")
    if repo_profile.frameworks:
        items.extend(repo_profile.frameworks)
    cuda_note = "required" if repo_profile.requires_cuda else "optional"
    if repo_profile.uses_torch or repo_profile.uses_tensorflow:
        items.append(f"CUDA {cuda_note} backend")
    if repo_profile.has_package_json and "Node project" not in items:
        items.append("Node project")
    if repo_profile.has_cargo_toml and "Rust project" not in items:
        items.append("Rust project")
    if repo_profile.has_dockerfile:
        items.append("Dockerized")
    # Only show subprojects when they add info (nested paths or multiple)
    show_subprojects = any(sp.get("path", ".") != "." for sp in repo_profile.subprojects) or len(repo_profile.subprojects) > 1
    if show_subprojects:
        for sp in repo_profile.subprojects[:8]:
            path, ptype = sp.get("path", "."), sp.get("type", "?")
            prefix = "./" if path != "." else ""
            extra = f" ({sp.get('python_version', '')})" if sp.get("python_version") else ""
            items.append(f"{ptype} at {prefix}{path}{extra}".rstrip())
    if not items:
        items.append("(no config files detected)")
    return items


def _print_human(repo_profile, host_profile, results, verbose: bool = False) -> None:
    """Human-readable output — box layout, score, findings, footer."""
    from .risk import run_confidence

    prob = estimate_success_probability(results)
    run_conf, low_conf_rules = run_confidence(results)
    repo_name = repo_profile.name or str(repo_profile.path)
    text = format_human(
        repo_name, prob, results,
        verbose=verbose,
        confidence=run_conf,
        low_confidence_rules=low_conf_rules if verbose else None,
    )
    typer.echo(text)


def _print_explain(rule_id: str) -> None:
    """Print rule description and exit."""
    if rule_id == "list" or rule_id == "rules":
        typer.echo("Available rules:")
        for rid in RULE_INFO:
            typer.echo(f"  {rid}")
        typer.echo("\nUse: repofail --explain <rule_id>")
        return
    info = RULE_INFO.get(rule_id)
    if not info:
        _err(f"Unknown rule: {rule_id}\nAvailable: {', '.join(RULE_INFO.keys())}")
    typer.echo(f"Rule: {rule_id}")
    typer.echo(f"Severity: {info['severity']}")
    typer.echo(f"Description: {info['description']}")
    typer.echo(f"When: {info['when']}")
    typer.echo(f"Fix: {info['fix']}")


def _ci_exit(results, fail_on: str) -> None:
    """Exit 1 if any result meets or exceeds fail_on severity. INFO never fails."""
    order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2, "INFO": 4}  # INFO never triggers
    threshold = order.get(fail_on.upper(), 0)
    for r in results:
        if order.get(r.severity.value, 3) <= threshold:
            raise typer.Exit(1)


def _print_markdown(repo_profile, host_profile, results) -> None:
    """Markdown output for docs/PRs."""
    prob = estimate_success_probability(results)
    typer.echo(f"# repofail: {repo_profile.name or repo_profile.path}")
    typer.echo()
    typer.echo(f"**Estimated run success probability: {prob}%**")
    typer.echo()
    typer.echo("## Detected stack")
    for item in _stack_items(repo_profile):
        typer.echo(f"- {item}")
    typer.echo()
    typer.echo("## Host")
    typer.echo(f"- {_host_summary(host_profile)}")
    typer.echo()
    if not results:
        typer.echo("## Result")
        typer.echo("No high-confidence incompatibilities detected.")
        return
    typer.echo("## Risk analysis")
    for r in results:
        typer.echo(f"\n### [{r.severity.value}] {r.message}")
        typer.echo(f"- **Reason:** {r.reason}")
        if r.host_summary:
            typer.echo(f"- **Host:** {r.host_summary}")
    typer.echo(f"\n---\n{len(results)} potential runtime mismatch(es) detected.")


def _print_json(repo_profile, host_profile, results, verbose: bool = False) -> None:
    """JSON output for piping/CI."""
    import json
    from dataclasses import asdict

    from .risk import run_confidence

    prob = estimate_success_probability(results)
    run_conf, low_conf_rules = run_confidence(results)

    output = {
        "estimated_success_probability": prob,
        "confidence": run_conf,
        "repo": {
            "name": repo_profile.name,
            "path": repo_profile.path,
            "python_version": repo_profile.python_version,
            "uses_torch": repo_profile.uses_torch,
            "requires_cuda": repo_profile.requires_cuda,
            "has_pyproject": repo_profile.has_pyproject,
            "has_requirements_txt": repo_profile.has_requirements_txt,
            "has_dockerfile": repo_profile.has_dockerfile,
            "has_package_json": repo_profile.has_package_json,
            "subprojects": repo_profile.subprojects,
        },
        "host": asdict(host_profile),
        "results": [
            {
                "rule_id": r.rule_id,
                "severity": r.severity.value,
                "message": r.message,
                "reason": r.reason,
                "host_summary": r.host_summary,
                "confidence": getattr(r, "confidence", "high"),
                **({"category": r.category} if getattr(r, "category", "") else {}),
                **({"evidence": r.evidence} if getattr(r, "evidence", None) else {}),
            }
            for r in results
        ],
    }
    if low_conf_rules:
        output["low_confidence_rules"] = low_conf_rules
    typer.echo(json.dumps(output, indent=2))


@app.command("gen")
def gen_cmd(
    path: Path = typer.Argument(Path("."), exists=True, file_okay=False, dir_okay=True, resolve_path=True, help="Repo path"),
    output: Path | None = typer.Option(None, "-o", help="Output file"),
) -> None:
    """Generate an environment contract from the repository."""
    try:
        repo_profile = scan_repo(path)
    except NotADirectoryError as e:
        _err(str(e))
    contract = generate_contract(repo_profile)
    text = contract.to_json()
    if output:
        output.write_text(text)
        typer.echo(f"Wrote {output}", err=True)
    else:
        typer.echo(text)


@app.command("s")
def stats_cmd(
    json_out: bool = typer.Option(False, "-j", help="JSON output"),
) -> None:
    """Show local failure stats from opt-in reports."""
    stats = get_stats()
    if json_out:
        import json
        typer.echo(json.dumps(stats, indent=2))
        return
    if stats["total_runs"] == 0:
        typer.echo("No reports yet. Run with --report when rules fire to contribute.")
        return
    typer.echo(f"Total runs with failures: {stats['total_runs']}")
    typer.echo()
    typer.echo("By rule:")
    for rule_id, count in sorted(stats["by_rule"].items(), key=lambda x: -x[1]):
        typer.echo(f"  {rule_id}: {count}")
    typer.echo()
    typer.echo("By host:")
    for host, count in sorted(stats["by_host"].items(), key=lambda x: -x[1]):
        typer.echo(f"  {host}: {count}")


@app.command("a")
def audit_cmd(
    path: Path = typer.Argument(Path("."), file_okay=False, dir_okay=True, help="Dir of repos"),
    json_out: bool = typer.Option(False, "-j", help="JSON output"),
) -> None:
    """Scan all repos in directory — fleet-wide compatibility check."""
    from .fleet import audit
    if not path.exists() or not path.is_dir():
        _err(f"Directory not found: {path}\nUse a path that exists, e.g. repofail a .")
    results = audit(path)
    if json_out:
        import json
        typer.echo(json.dumps(results, indent=2))
        return
    if not results:
        typer.echo("No repos found.")
        return
    high = sum(1 for r in results if r["has_high"])
    medium = sum(1 for r in results if r.get("rule_count", 0) > 0 and not r["has_high"])
    clean = len(results) - high - medium
    typer.echo(f"Found {len(results)} repos. {high} high-risk. {medium} medium. {clean} clean.")
    typer.echo()
    for r in results:
        status = "HIGH" if r["has_high"] else ("MEDIUM" if r.get("rule_count", 0) > 0 else "OK")
        rules_preview = ", ".join(r["rules"][:5]) or "none"
        if len(r.get("rules", [])) > 5:
            rules_preview += " ..."
        typer.echo(f"  [{status}] {r['name']}: {r['rule_count']} issue(s) — {rules_preview}")


@app.command("sim")
def sim_cmd(
    repo_path: Path = typer.Argument(Path("."), file_okay=False, help="Repo to check"),
    host_file: Path = typer.Option(..., "-H", help="Host JSON (from repofail -j)"),
) -> None:
    """Simulate: would this repo work on target host? (pre-deployment check)."""
    from .fleet import simulate
    if not host_file.exists():
        _err(f"Host file not found: {host_file}\nCreate one with: repofail -j > host.json")
    if not repo_path.exists() or not repo_path.is_dir():
        _err(f"Repo path not found: {repo_path}")
    try:
        repo, host, results = simulate(repo_path, host_file)
    except Exception as e:
        _err(str(e))
    typer.echo(f"Repo: {repo.name or repo_path}")
    typer.echo(f"Target host: {host.os} {host.arch}" + (" CUDA" if host.cuda_available else " no-CUDA"))
    typer.echo()
    if not results:
        typer.echo("OK: No incompatibilities for target host.")
        return
    typer.echo(f"{len(results)} issue(s) on target host:")
    for r in results:
        typer.echo(f"  [{r.severity.value}] {r.rule_id}: {r.message}")
    raise typer.Exit(1)


@app.command("check")
def check_cmd(
    contract_path: Path = typer.Argument(..., exists=True, path_type=Path, help="Contract JSON path"),
) -> None:
    """Validate current host against an environment contract."""
    import json
    data = json.loads(contract_path.read_text())
    requires = data.get("requires", {})
    contract = EnvironmentContract(
        repo=data.get("repo", ""),
        version=str(data.get("repofail_contract", "1")),
        requires=requires,
        optional=data.get("optional", {}),
    )
    host = inspect_host()
    host_data = {
        "python_version": host.python_version,
        "cuda_available": host.cuda_available,
        "has_compiler": host.has_compiler,
        "ram_gb": host.ram_gb,
        "node_version": host.node_version,
        "rust_version": host.rust_version,
    }
    failures = validate_contract(contract, host_data)
    if not failures:
        typer.echo("OK: Host satisfies contract.")
        return
    lines = ["Contract violations:"] + [f"  {req}: {reason}" for req, reason in failures]
    _err("\n".join(lines))


def _main() -> None:
    """Entry point: preprocess argv (repofail . -> repofail -p .), then run app."""
    _preprocess_argv()
    app()


if __name__ == "__main__":
    _main()
