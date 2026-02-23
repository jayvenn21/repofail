"""Stage 5 — Fleet/enterprise: audit, simulate, fleet scan."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from .models import HostProfile, RepoProfile
from .scanner import scan_repo, inspect_host
from .engine import run_rules

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore[assignment]

SKIP_AUDIT_DIRS = {".git", "__pycache__", ".venv", "venv", "node_modules", ".tox", "build", "dist", "eggs"}

# Rule ID -> short category for risk clusters
RULE_CATEGORIES: dict[str, str] = {
    "torch_cuda_mismatch": "ML/CUDA",
    "python_version_mismatch": "Python",
    "python_eol": "Python",
    "spec_drift": "Spec drift",
    "abi_wheel_mismatch": "ML/ARM",
    "apple_silicon_wheels": "ML/ARM",
    "node_engine_mismatch": "Node",
    "node_eol": "Node",
    "node_lock_file_missing": "Node",
    "native_toolchain_missing": "Native build",
    "gpu_memory_risk": "ML/RAM",
    "node_native_windows": "Node/Windows",
    "missing_system_libs": "System libs",
    "docker_only": "Docker",
    "lock_file_missing": "Lock file",
}
DEFAULT_CATEGORY = "Other"


def _is_repo(p: Path) -> bool:
    """Check if path looks like a repo (has .git or deps file)."""
    return (
        (p / ".git").exists()
        or (p / "pyproject.toml").exists()
        or (p / "requirements.txt").exists()
        or (p / "package.json").exists()
        or (p / "Cargo.toml").exists()
    )


def _load_policy(policy_path: Path | None) -> dict[str, Any]:
    """Load optional policy YAML: fail_on (HIGH/MEDIUM/LOW), max_repos, max_depth."""
    if not policy_path or not policy_path.exists() or not yaml:
        return {}
    try:
        data = yaml.safe_load(policy_path.read_text()) or {}
        return {
            "fail_on": data.get("fail_on", "HIGH"),
            "max_repos": data.get("max_repos", 500),
            "max_depth": data.get("max_depth", 4),
        }
    except Exception:
        return {}


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


def fleet_scan(
    base_path: Path,
    policy_path: Path | None = None,
) -> dict[str, Any]:
    """
    Scan all repos under base_path; optionally apply policy.
    Returns: total_repos, violations (count), repos (list), by_rule (most common drift), risk_clusters.
    """
    base_path = Path(base_path).resolve()
    policy = _load_policy(policy_path)
    max_repos = int(policy.get("max_repos", 500))
    max_depth = int(policy.get("max_depth", 4))

    dirs = _find_repos(base_path, max_depth=max_depth, max_repos=max_repos)
    host = inspect_host()
    repos: list[dict[str, Any]] = []
    rule_counter: Counter[str] = Counter()
    category_counter: Counter[str] = Counter()

    for d in dirs:
        try:
            repo = scan_repo(d)
            rule_results = run_rules(repo, host)
            rule_ids = [r.rule_id for r in rule_results]
            for rid in rule_ids:
                rule_counter[rid] += 1
                category_counter[RULE_CATEGORIES.get(rid, DEFAULT_CATEGORY)] += 1
            high_count = sum(1 for r in rule_results if r.severity.value == "HIGH")
            med_count = sum(1 for r in rule_results if r.severity.value in ("MEDIUM", "LOW"))
            score = __import__("repofail.risk", fromlist=["estimate_success_probability"]).estimate_success_probability(rule_results)
            repos.append({
                "path": str(d),
                "name": repo.name or d.name,
                "rule_count": len(rule_results),
                "rules": rule_ids,
                "has_high": high_count > 0,
                "high_count": high_count,
                "medium_count": med_count,
                "score": score,
            })
        except Exception:
            pass

    violations = sum(1 for r in repos if r["rule_count"] > 0)
    by_rule = dict(rule_counter.most_common(15))
    risk_clusters = [{"category": k, "count": v} for k, v in category_counter.most_common(10)]

    return {
        "total_repos_scanned": len(repos),
        "violations": violations,
        "repos": repos,
        "most_common_drift": by_rule,
        "risk_clusters": risk_clusters,
        "policy": policy,
    }


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
