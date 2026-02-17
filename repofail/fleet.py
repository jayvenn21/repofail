"""Stage 5 — Fleet/enterprise: audit, simulate."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from .models import HostProfile, RepoProfile
from .scanner import scan_repo, inspect_host
from .engine import run_rules


def _is_repo(p: Path) -> bool:
    """Check if path looks like a repo (has deps file)."""
    return (
        (p / "pyproject.toml").exists()
        or (p / "requirements.txt").exists()
        or (p / "package.json").exists()
        or (p / "Cargo.toml").exists()
    )


def audit(base_path: Path) -> list[dict]:
    """Scan all repo-like subdirs, return aggregated report."""
    base_path = Path(base_path).resolve()
    if not base_path.is_dir():
        return []
    results = []
    host = inspect_host()
    for d in sorted(base_path.iterdir()):
        if not d.is_dir() or d.name.startswith("."):
            continue
        if not _is_repo(d):
            continue
        try:
            repo = scan_repo(d)
            rule_results = run_rules(repo, host)
            results.append({
                "path": str(d),
                "name": repo.name or d.name,
                "rule_count": len(rule_results),
                "rules": [r.rule_id for r in rule_results],
                "has_high": any(r.severity.value == "HIGH" for r in rule_results),
            })
        except Exception:
            pass
    return results


def host_from_dict(data: dict) -> HostProfile:
    """Build HostProfile from dict (e.g. from JSON file)."""
    return HostProfile(
        os=data.get("os", "linux"),
        arch=data.get("arch", "x86_64"),
        cuda_available=data.get("cuda_available", False),
        cuda_version=data.get("cuda_version"),
        python_version=data.get("python_version"),
        node_version=data.get("node_version"),
        rust_version=data.get("rust_version"),
        has_compiler=data.get("has_compiler", True),
        has_metal=data.get("has_metal", False),
        has_libgl=data.get("has_libgl", False),
        has_ffmpeg=data.get("has_ffmpeg", False),
        ram_gb=data.get("ram_gb"),
    )


def simulate(repo_path: Path, host_path: Path) -> tuple[RepoProfile, HostProfile, list]:
    """Run rules against repo with a target host profile from file."""
    repo = scan_repo(repo_path)
    data = json.loads(host_path.read_text())
    if "host" in data:
        data = data["host"]
    host = host_from_dict(data)
    results = run_rules(repo, host)
    return repo, host, results
