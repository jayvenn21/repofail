"""Rule: Spec drift — Python version inconsistent across pyproject, Dockerfile, CI."""

import re

from ..models import HostProfile, RepoProfile
from .base import RuleResult, Severity


def _extract_minor(ver: str | None) -> str | None:
    """Extract 3.XX from version string. '3.11.2' -> '3.11', '>=3.10' -> '3.10'."""
    if not ver:
        return None
    m = re.search(r"(\d+)\.(\d+)", str(ver))
    return f"{m.group(1)}.{m.group(2)}" if m else None


def check(repo: RepoProfile, host: HostProfile) -> RuleResult | None:
    """
    If pyproject, Dockerfile, and CI matrix specify different Python versions
    across source types, flag as spec drift — runtime expectations inconsistent.
    """
    by_source: dict[str, set[str]] = {}
    sources: list[str] = []

    if repo.python_version:
        v = _extract_minor(repo.python_version)
        if v:
            by_source.setdefault("pyproject", set()).add(v)
            sources.append(f"pyproject: {repo.python_version}")

    raw = repo.raw or {}
    docker = raw.get("dockerfile") or {}
    if isinstance(docker, dict):
        dp = docker.get("python_version")
        if dp:
            v = _extract_minor(dp)
            if v:
                by_source.setdefault("docker", set()).add(v)
                sources.append(f"Dockerfile: {dp}")

    ci_versions: set[str] = set()
    for wf_name, wf_data in (raw.get("workflows") or {}).items():
        if isinstance(wf_data, dict):
            for pv in wf_data.get("python_versions") or []:
                v = _extract_minor(str(pv))
                if v:
                    ci_versions.add(v)
                    sources.append(f"CI ({wf_name}): {pv}")
    if ci_versions:
        by_source["ci"] = ci_versions

    # Drift = Docker version conflicts with pyproject (or CI)
    # Skip when no Docker — CI matrix testing multiple versions is intentional
    has_docker = "docker" in by_source
    if not has_docker:
        return None
    all_versions = set()
    for vs in by_source.values():
        all_versions.update(vs)
    if len(all_versions) < 2:
        return None

    return RuleResult(
        rule_id="spec_drift",
        severity=Severity.HIGH,
        message="Spec drift detected — Python versions inconsistent across project definitions.",
        reason=(
            f"Found: {', '.join(sorted(all_versions))}. "
            "Runtime expectations are inconsistent (pyproject vs Docker vs CI)."
        ),
        host_summary="",
        evidence={
            "versions": sorted(all_versions),
            "drift_entropy": len(all_versions),
            "sources": sources[:6],
            "determinism": 0.6,
            "breakage_likelihood": "~70%",
            "likely_error": "CI and local runtime definitions diverge; subtle version-dependent bugs",
        },
        category="spec_violation",
        confidence="high",
    )
