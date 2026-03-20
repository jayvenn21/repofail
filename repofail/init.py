"""Interactive init - generate .repofail.yaml config for a repo."""

from pathlib import Path

import typer
import yaml


TEMPLATE = {
    "version": 1,
    "rules": {
        "fail_on": "HIGH",
    },
}


def detect_stack(repo_path: Path) -> dict:
    """Auto-detect project stack from files present."""
    stack = {"languages": [], "has_docker": False, "has_ci": False}
    if (repo_path / "pyproject.toml").exists() or (repo_path / "requirements.txt").exists():
        stack["languages"].append("python")
    if (repo_path / "package.json").exists():
        stack["languages"].append("node")
    if (repo_path / "Cargo.toml").exists():
        stack["languages"].append("rust")
    if (repo_path / "go.mod").exists():
        stack["languages"].append("go")
    if (repo_path / "Dockerfile").exists():
        stack["has_docker"] = True
    if (repo_path / ".github" / "workflows").is_dir():
        stack["has_ci"] = True
    return stack


def run_init(repo_path: Path, non_interactive: bool = False) -> Path:
    """Run interactive init and write .repofail.yaml. Returns path to written file."""
    config = dict(TEMPLATE)
    config["rules"] = dict(TEMPLATE["rules"])

    stack = detect_stack(repo_path)

    if not non_interactive:
        typer.echo(f"Detected stack: {', '.join(stack['languages']) or 'unknown'}")
        if stack["has_docker"]:
            typer.echo("  Docker: yes")
        if stack["has_ci"]:
            typer.echo("  CI: yes")
        typer.echo()

        # Severity threshold
        fail_on = typer.prompt(
            "Fail CI on severity (HIGH / MEDIUM / LOW)",
            default="HIGH",
        ).upper()
        if fail_on not in ("HIGH", "MEDIUM", "LOW"):
            fail_on = "HIGH"
        config["rules"]["fail_on"] = fail_on

        # Enforce lock
        if typer.confirm("Enforce runtime lock? (repofail lock/verify)", default=False):
            config["lock"] = True

        # Custom rule overrides
        if typer.confirm("Disable any built-in rules?", default=False):
            disabled = typer.prompt("Rule IDs to disable (comma-separated)").strip()
            if disabled:
                config["rules"]["disable"] = [r.strip() for r in disabled.split(",") if r.strip()]

        # Languages to scan (if multi-language)
        if len(stack["languages"]) > 1:
            typer.echo(f"Languages detected: {', '.join(stack['languages'])}")
            skip = typer.prompt("Skip any? (comma-separated, or enter to keep all)", default="").strip()
            if skip:
                config["rules"]["skip_languages"] = [s.strip() for s in skip.split(",") if s.strip()]
    else:
        config["rules"]["fail_on"] = "HIGH"

    out_path = repo_path / ".repofail.yaml"
    out_path.write_text(yaml.dump(config, default_flow_style=False, sort_keys=False))
    return out_path
