"""Informational rules — add nuance, never false alarm. Quality > quantity."""

import re

from ..models import HostProfile, RepoProfile
from .base import RuleResult, Severity


def _parse_version(s: str | None) -> tuple[int, int] | None:
    """Extract (major, minor) from version string. Returns None if unclear."""
    if not s:
        return None
    # Match 3.11, 3.12, >=3.10, ^3.11, etc.
    m = re.search(r"(\d+)\.(\d+)", s)
    if m:
        return int(m.group(1)), int(m.group(2))
    return None


def _host_minor(host: HostProfile) -> tuple[int, int] | None:
    """Host Python version as (major, minor)."""
    return _parse_version(host.python_version)


def check_python_minor_mismatch(repo: RepoProfile, host: HostProfile) -> RuleResult | None:
    """Repo targets different Python minor than host — may cause subtle issues."""
    if not repo.python_version or not host.python_version:
        return None
    # Skip open-ended constraints (>=3.10, ^3.10) — host likely satisfies
    cv = repo.python_version
    if (">=" in cv or "^" in cv) and "<" not in cv:
        repo_ver = _parse_version(cv)
        host_ver = _host_minor(host)
        if repo_ver and host_ver and repo_ver[0] == host_ver[0] and repo_ver[1] <= host_ver[1]:
            return None  # host is within range
    repo_ver = _parse_version(repo.python_version)
    host_ver = _host_minor(host)
    if not repo_ver or not host_ver:
        return None
    if repo_ver == host_ver:
        return None
    # Same major, different minor
    if repo_ver[0] == host_ver[0] and repo_ver[1] != host_ver[1]:
        return RuleResult(
            rule_id="python_minor_mismatch",
            severity=Severity.INFO,
            message="Repo targets different Python minor than host.",
            reason=f"Repo: {repo.python_version}, host: {host.python_version}. Minor differences may cause subtle dependency issues.",
            host_summary=f"Python {host.python_version}",
            confidence="high",
            evidence={"repo_python": repo.python_version, "host_python": host.python_version},
        )
    return None


def check_multiple_python_subprojects(repo: RepoProfile, host: HostProfile) -> RuleResult | None:
    """Multiple Python subprojects — ensure consistent virtualenvs."""
    python_sps = [s for s in repo.subprojects if s.get("type") == "python"]
    if len(python_sps) < 2:
        return None
    paths = [s.get("path", "?") for s in python_sps]
    return RuleResult(
        rule_id="multiple_python_subprojects",
        severity=Severity.INFO,
        message="Multiple Python subprojects detected.",
        reason=f"Paths: {', '.join(paths[:5])}{'...' if len(paths) > 5 else ''}. Ensure consistent virtualenvs or use per-subproject envs.",
        host_summary="",
        confidence="medium",
        evidence={"pyprojects_found": len(python_sps), "paths": paths[:8]},
        category="runtime_environment",
    )


def check_mixed_python_node(repo: RepoProfile, host: HostProfile) -> RuleResult | None:
    """Mixed Python + Node monorepo."""
    types = {s.get("type") for s in repo.subprojects}
    if "python" in types and "node" in types:
        return RuleResult(
            rule_id="mixed_python_node",
            severity=Severity.INFO,
            message="Mixed Python + Node monorepo.",
            reason="Backend and frontend in same repo. Verify Node version and Python venv are compatible with docs.",
            host_summary="",
            confidence="medium",
            evidence={"types": list(types)},
            category="runtime_environment",
        )
    return None


def check_docker_python_mismatch(repo: RepoProfile, host: HostProfile) -> RuleResult | None:
    """Docker present but repo Python constraint may differ from host."""
    if not repo.has_dockerfile:
        return None
    docker_py = None
    if repo.raw.get("dockerfile"):
        docker_py = repo.raw["dockerfile"].get("python_version")
    repo_py = repo.python_version
    host_ver = _host_minor(host)
    if not host_ver:
        return None
    # If Docker pins a different Python than host
    if docker_py:
        docker_ver = _parse_version(docker_py)
        if docker_ver and docker_ver != host_ver:
            return RuleResult(
                rule_id="docker_python_mismatch",
                severity=Severity.INFO,
                message="Dockerfile uses different Python than host.",
                reason=f"Dockerfile: Python {docker_py}, host: {host.python_version}. Local dev may differ from container.",
                host_summary="",
                confidence="high",
                evidence={"docker_python": docker_py, "host_python": host.python_version},
            )
    return None


def check_low_ram_multi_service(repo: RepoProfile, host: HostProfile) -> RuleResult | None:
    """Host RAM < 16GB with multi-service / complex repo."""
    if host.ram_gb is None or host.ram_gb >= 16:
        return None
    if len(repo.subprojects) < 2 and not repo.has_dockerfile:
        return None
    return RuleResult(
        rule_id="low_ram_multi_service",
        severity=Severity.INFO,
        message="Multi-service repo with limited RAM.",
        reason=f"Host has {host.ram_gb:.0f} GB RAM. Multiple subprojects or Docker may need more. Consider increasing swap or using remote dev.",
        host_summary=f"{host.ram_gb:.0f} GB RAM",
        confidence="medium",
        evidence={"ram_gb": host.ram_gb, "subproject_count": len(repo.subprojects), "has_dockerfile": repo.has_dockerfile},
        category="runtime_environment",
    )


CHECKS = [
    check_python_minor_mismatch,
    check_multiple_python_subprojects,
    check_mixed_python_node,
    check_docker_python_mismatch,
    check_low_ram_multi_service,
]
