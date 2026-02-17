"""Terminal output formatting — box layout, colors, width control."""

import shutil
from typing import List

import click

from .rules.base import RuleResult, Severity


def _get_width() -> int:
    try:
        return min(72, shutil.get_terminal_size((72, 24)).columns)
    except OSError:
        return 72


def _wrap(text: str, indent: int = 0, width: int = 72) -> List[str]:
    """Wrap text to width, first line has indent, following lines +2."""
    prefix = " " * indent
    extra = "  "
    lines = []
    rest = text
    first = True
    while rest:
        max_len = width - (indent if first else indent + len(extra))
        if len(rest) <= max_len:
            lines.append(prefix + rest)
            break
        break_at = rest.rfind(" ", 0, max_len + 1)
        if break_at <= 0:
            break_at = max_len
        chunk = rest[:break_at].strip()
        rest = rest[break_at:].strip()
        lines.append(prefix + chunk)
        prefix = " " * indent + extra
        first = False
    return lines


def _score_color(score: int) -> str:
    if score >= 90:
        return "green"
    if score >= 70:
        return "yellow"
    return "red"


def _group_by_severity(results: List[RuleResult]) -> tuple[List[RuleResult], List[RuleResult], List[RuleResult]]:
    """Split into: hard_failures (HIGH), runtime_risks (MEDIUM/LOW), observations (INFO)."""
    hard = [r for r in results if r.severity == Severity.HIGH]
    risks = [r for r in results if r.severity in (Severity.MEDIUM, Severity.LOW)]
    obs = [r for r in results if r.severity == Severity.INFO]
    return hard, risks, obs


def _bullet_text(r: RuleResult, verbose: bool, bullet: str = "○") -> str:
    """One-line bullet for a result. ● = hard failure, ○ = risk/observation."""
    base = r.message.rstrip(".")
    if verbose and r.rule_id:
        base = f"{base} [{r.rule_id}]"
    return f"{bullet} {base}"


def _evidence_to_lines(r: RuleResult) -> List[str]:
    """Convert evidence dict to human-readable lines for HARD FAILURES."""
    ev = r.evidence or {}
    lines: List[str] = []

    if r.rule_id == "torch_cuda_mismatch":
        for s in ev.get("repo_cuda_usage", [])[:5]:
            lines.append(f"  {s}")
        if not ev.get("has_is_available_guard") and ev.get("cuda_mandatory"):
            lines.append("  No torch.cuda.is_available() guard detected")
        if ev.get("host_cuda") is False:
            lines.append("  Host has no CUDA device")
        if ev.get("cuda_mandatory") and lines:
            lines.append("  This will raise RuntimeError: CUDA unavailable.")
        return lines

    if r.rule_id == "node_engine_mismatch":
        eng = ev.get("engines_node")
        host = ev.get("host_node")
        if eng:
            lines.append(f"  package.json requires: node {eng}")
        if host:
            lines.append(f"  Host: node {host}")
        if lines:
            lines.append("  This may cause install or runtime breakage.")
        return lines

    if r.rule_id == "abi_wheel_mismatch":
        lines.append(f"  Detected: {ev.get('host_os_arch', 'macOS arm64')}, Python {ev.get('host_python', '?')}")
        for p in ev.get("problematic_packages", [])[:3]:
            lines.append(f"  Dependency: {p}")
        fail = ev.get("expected_failure")
        if fail:
            lines.append(f"  Expected failure: {fail}")
        return lines

    if r.rule_id == "lock_file_missing":
        lines.append("  package.json has dependencies")
        lines.append("  No package-lock.json or yarn.lock found")
        fail = ev.get("expected_failure")
        if fail:
            lines.append(f"  {fail}")
        return lines

    if r.rule_id == "node_eol":
        lines.append(f"  engines.node: {ev.get('engines_node', '?')}")
        lines.append(f"  Node {ev.get('eol_major', '?')} is end-of-life")
        return lines

    if r.rule_id == "python_eol":
        lines.append(f"  requires-python: {ev.get('requires_python', '?')}")
        lines.append(f"  Python {ev.get('eol_version', '?')} is end-of-life")
        return lines

    # Generic: requires_python, host_python, etc.
    labels = {
        "requires_python": "requires-python",
        "host_python": "Host Python",
        "engines_node": "engines.node",
        "host_node": "Host Node",
        "problematic_packages": "Packages",
        "port": "Port",
    }
    for k, v in ev.items():
        if v is None or k in ("host_cuda", "cuda_mandatory", "has_is_available_guard", "repo_cuda_usage"):
            continue
        if isinstance(v, list):
            v = ", ".join(str(x) for x in v[:5])
        label = labels.get(k, k.replace("_", " ").title())
        lines.append(f"  {label}: {v}")
    return lines[:6]  # Cap generic evidence


def _explanation_summary(results: List[RuleResult]) -> str | None:
    """Multi-line summary: deterministic vs structural. Feels analytical."""
    if not results:
        return None
    hard, risks, obs = _group_by_severity(results)
    parts = []
    if hard:
        parts.append(f"{len(hard)} deterministic incompatibility(ies) detected.")
    if risks:
        parts.append(f"{len(risks)} runtime risk(s) detected.")
    if obs:
        parts.append(f"{len(obs)} structural observation(s).")
    return " ".join(parts) if parts else None


def _score_context(results: List[RuleResult], prob: int) -> str:
    """Short context for score line, e.g. '(5 informational)'."""
    if not results:
        return ""
    by_sev = {}
    for r in results:
        by_sev[r.severity] = by_sev.get(r.severity, 0) + 1
    parts = []
    for sev in [Severity.INFO, Severity.LOW, Severity.MEDIUM, Severity.HIGH]:
        n = by_sev.get(sev, 0)
        if n:
            label = "informational" if sev == Severity.INFO else sev.value.lower()
            parts.append(f"{n} {label}")
    return " (" + ", ".join(parts) + ")" if parts else ""


def format_human(
    repo_name: str,
    prob: int,
    results: List[RuleResult],
    verbose: bool = False,
    confidence: str = "high",
    low_confidence_rules: List[str] | None = None,
) -> str:
    """Build the human terminal output as a single string."""
    width = _get_width()
    lines = []

    lines.append("┌" + "─" * (width - 2) + "┐")
    lines.append(" repofail · environment risk")
    lines.append("─" * width)

    ctx = _score_context(results, prob)
    if verbose and confidence != "high":
        ctx = f"{ctx} (confidence: {confidence})".strip() or f"(confidence: {confidence})"
    if verbose and low_confidence_rules:
        ctx = f"{ctx} — low-confidence: {', '.join(low_confidence_rules[:3])}".strip()
    score_str = f" Score    {prob}%{ctx}"
    score_color = _score_color(prob)
    lines.append(click.style(score_str, fg=score_color))
    summary = _explanation_summary(results)
    if summary:
        lines.append(click.style(f" {summary}", dim=True))
    lines.append("─" * width)

    if results:
        hard, risks, obs = _group_by_severity(results)
        if hard:
            lines.append(" HARD FAILURES")
            for r in hard:
                bullet = _bullet_text(r, verbose, bullet="●")
                for ln in _wrap(bullet, indent=2, width=width):
                    lines.append(click.style(ln, fg="red"))
                ev_lines = _evidence_to_lines(r)
                for el in ev_lines:
                    lines.append(click.style(el, fg="red", dim=True))
        if risks:
            lines.append(" RUNTIME RISKS")
            for r in risks:
                bullet = _bullet_text(r, verbose, bullet="○")
                for ln in _wrap(bullet, indent=2, width=width):
                    lines.append(click.style(ln, dim=True))
        if obs:
            lines.append(" ENVIRONMENT OBSERVATIONS")
            for r in obs:
                bullet = _bullet_text(r, verbose, bullet="○")
                for ln in _wrap(bullet, indent=2, width=width):
                    lines.append(click.style(ln, dim=True))
    else:
        lines.append(" No high-confidence incompatibilities detected.")

    lines.append("─" * width)
    footer = " Run with --json for machine output  ·  --ci for exit codes"
    if len(footer) > width:
        footer = " --json  ·  --ci  ·  --help"
    lines.append(click.style(footer, dim=True))
    lines.append("└" + "─" * (width - 2) + "┘")

    return "\n".join(lines)
