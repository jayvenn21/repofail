"""Rule: Python ABI / wheel mismatch — arm64 + Python 3.12 + packages that lag wheels."""

import re

from ..models import HostProfile, RepoProfile
from .base import RuleResult, Severity

# Packages that often lack prebuilt wheels for arm64 + Python 3.12
# (source build may fail without LLVM toolchain)
ARM64_PY312_LAGGING = {
    "bitsandbytes",
    "torchvision",
    "opencv-python",
    "opencv-contrib-python",
    "opencv",
    "xformers",
    "pytorch3d",
}


def _parse_python_minor(ver: str | None) -> tuple[int, int] | None:
    """'3.12.1' -> (3, 12). None if unparseable."""
    if not ver:
        return None
    m = re.search(r"(\d+)\.(\d+)", str(ver))
    return (int(m.group(1)), int(m.group(2))) if m else None


def _get_repo_packages(repo: RepoProfile) -> set[str]:
    """Extract package names from repo."""
    packages: set[str] = set()
    raw = repo.raw or {}
    if "requirements" in raw:
        for p in raw["requirements"].get("packages", []):
            packages.add(str(p).lower().replace("_", "-"))
    if "pyproject" in raw:
        for p in raw["pyproject"].get("packages", []):
            packages.add(str(p).lower().replace("_", "-"))
    return packages


def check(repo: RepoProfile, host: HostProfile) -> RuleResult | None:
    """
    Trigger when: macOS arm64 + Python >= 3.12 + deps that lag arm64 3.12 wheels.
    HIGH: deterministic pip install or import failure risk.
    """
    if host.os != "macos" or host.arch != "arm64":
        return None
    py = _parse_python_minor(host.python_version)
    if not py or py < (3, 12):
        return None

    packages = _get_repo_packages(repo)
    found = [p for p in packages if any(lag in p for lag in ARM64_PY312_LAGGING)]
    if not found:
        return None

    return RuleResult(
        rule_id="abi_wheel_mismatch",
        severity=Severity.HIGH,
        message="Likely binary wheel mismatch (arm64 + Python 3.12).",
        reason=(
            f"macOS arm64, Python 3.12+, dependency: {found[0]}. "
            f"{found[0]} often lacks wheels for arm64 3.12. Source build may fail without LLVM toolchain."
        ),
        host_summary=f"macOS arm64, Python {host.python_version}",
        evidence={
            "host_os_arch": "macOS arm64",
            "host_python": host.python_version,
            "problematic_packages": found[:5],
            "expected_failure": "pip install error or runtime import error",
        },
        category="architecture_mismatch",
        confidence="high",
    )
