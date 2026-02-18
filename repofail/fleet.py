"""Stage 5 — Fleet/enterprise: audit, simulate."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from .models import HostProfile, RepoProfile
from .scanner import scan_repo, inspect_host
from .engine import run_rules


SKIP_AUDIT_DIRS = {".git", "__pycache__", ".venv", "venv", "node_modules", ".tox", "build", "dist", "eggs"}


def _is_repo(p: Path) -> bool:
    """Check if path looks like a repo (has .git or deps file)."""
    return (
        (p / ".git").exists()
        or (p / "pyproject.toml").exists()
        or (p / "requirements.txt").exists()
        or (p / "package.json").exists()
        or (p / "Cargo.toml").exists()
    )


def _find_repos(base_path: Path, max_depth: int = 4, max_repos: int = 50) -> list[Path]:
    """Find repo roots recursively (nested repos)."""
    found: list[Path] = []
    base = Path(base_path).resolve()

    def walk(d: Path, depth: int) -> None:
        if depth > max_depth or len(found) >= max_repos:
            return
        if not d.is_dir():
            return
        if d.name.startswith(".") or d.name in SKIP_AUDIT_DIRS:
            return
        try:
            rel = d.relative_to(base) if d != base else Path(".")
            if any(part in SKIP_AUDIT_DIRS for part in rel.parts):
                return
        except ValueError:
            return
        if _is_repo(d):
            found.append(d)
            return  # Don't descend — this dir is the repo root
        for child in sorted(d.iterdir()):
            if child.is_dir():
                walk(child, depth + 1)

    for child in sorted(base.iterdir()):
        if child.is_dir():
            walk(child, 1)
    if _is_repo(base):
        found.insert(0, base)
    return list(dict.fromkeys(found))  # dedupe


def audit(base_path: Path) -> list[dict]:
    """Scan all repo-like subdirs (including nested), return aggregated report."""
    base_path = Path(base_path).resolve()
    if not base_path.is_dir():
        return []
    dirs = _find_repos(base_path)
    results = []
    host = inspect_host()
    for d in dirs:
        try:
            repo = scan_repo(d)
            rule_results = run_rules(repo, host)
            high_count = sum(1 for r in rule_results if r.severity.value == "HIGH")
            med_count = sum(1 for r in rule_results if r.severity.value in ("MEDIUM", "LOW"))
            results.append({
                "path": str(d),
                "name": repo.name or d.name,
                "rule_count": len(rule_results),
                "rules": [r.rule_id for r in rule_results],
                "has_high": high_count > 0,
                "high_count": high_count,
                "medium_count": med_count,
                "score": __import__("repofail.risk", fromlist=["estimate_success_probability"]).estimate_success_probability(rule_results),
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
