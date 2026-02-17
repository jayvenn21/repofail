"""Rule: Docker-only dev environment — native run may not be documented."""

from pathlib import Path

from ..models import HostProfile, RepoProfile
from .base import RuleResult, Severity


def _has_clear_native_install(repo: RepoProfile) -> bool:
    """True if repo has obvious native install path (make, pip -e)."""
    repo_path = Path(repo.path)
    if (repo_path / "Makefile").exists() or (repo_path / "makefile").exists():
        return True
    if (repo_path / "pyproject.toml").exists() or (repo_path / "requirements.txt").exists():
        return True
    return False


def check(repo: RepoProfile, host: HostProfile) -> RuleResult | None:
    """If Dockerfile + devcontainer but no clear native install, flag HIGH."""
    if not repo.has_dockerfile or not repo.has_devcontainer:
        return None
    if _has_clear_native_install(repo):
        return None

    return RuleResult(
        rule_id="docker_only_dev",
        severity=Severity.HIGH,
        message="Repo appears container-first. Running natively may fail.",
        reason=(
            "Dockerfile and devcontainer present, but no obvious native install path "
            "(e.g. Makefile, root pyproject.toml). Documentation may assume Docker/Dev Container."
        ),
        host_summary=f"{host.os} {host.arch}",
        evidence={"has_dockerfile": True, "has_devcontainer": True},
        category="runtime_environment",
    )
