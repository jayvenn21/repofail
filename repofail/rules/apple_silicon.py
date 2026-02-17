"""Rule 2: Apple Silicon wheel mismatch."""

import re

from ..models import HostProfile, RepoProfile
from .base import RuleResult, Severity

# Packages with known x86-only or problematic wheels on Apple Silicon
X86_ONLY_PACKAGES = {
    "cuda-python",
    "nvidia-cuda-runtime-cu",
    "nvidia-cudnn-cu",
    "nvidia-cublas-cu",
    "nvidia-cufft-cu",
    "nvidia-curand-cu",
    "nvidia-cusolver-cu",
    "nvidia-cusparse-cu",
    "nvidia-nccl-cu",
    "nvidia-nvtx-cu",
    "nvidia-nvjitlink-cu",
    "horovod",
    "faiss-gpu",
    "faiss-cpu",
    "faiss",  # Many builds x86-only
}


def _tensorflow_version_old(raw: dict) -> bool:
    """True if tensorflow constraint implies < 2.11 (no native arm64 wheels)."""
    for src in ["pyproject", "requirements"]:
        data = raw.get(src) or {}
        tv = str(data.get("tensorflow_version") or "")
        if not tv:
            continue
        # Match <2.11, <=2.10, ==2.10.*, ~=2.10, etc.
        if "<2.11" in tv or "<=2.10" in tv or "==2.10" in tv or "~=2.10" in tv:
            return True
        m = re.search(r"<\s*(\d+)\.(\d+)", tv)
        if m and (int(m.group(1)) < 2 or (int(m.group(1)) == 2 and int(m.group(2)) < 11)):
            return True
    return False


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
    """If host is arm64 macOS and repo has x86-only/problematic packages or Docker amd64, flag MEDIUM/HIGH."""
    if host.os != "macos" or host.arch != "arm64":
        return None

    reasons = []
    evidence = {"host": "macOS arm64"}

    packages = _get_repo_packages(repo)
    found = [p for p in packages if any(x in p for x in X86_ONLY_PACKAGES)]
    if found:
        reasons.append(f"Packages: {', '.join(found[:5])}")
        evidence["problematic_packages"] = found[:5]

    if repo.uses_tensorflow and _tensorflow_version_old(repo.raw):
        reasons.append("tensorflow < 2.11 (no native arm64 wheels)")
        evidence["tensorflow_old"] = True

    if repo.docker_platform_amd64:
        reasons.append("Dockerfile uses --platform=linux/amd64")
        evidence["docker_platform"] = "amd64"

    if not reasons:
        return None

    severity = Severity.HIGH if ("cuda" in " ".join(found).lower() or "faiss" in " ".join(found).lower() or repo.docker_platform_amd64) else Severity.MEDIUM
    return RuleResult(
        rule_id="apple_silicon_wheels",
        severity=severity,
        message="Apple Silicon wheel likely unavailable or Docker targets amd64.",
        reason="; ".join(reasons) + ". Installation may require emulation or fail.",
        host_summary="macOS arm64 (Apple Silicon)",
        evidence=evidence,
        category="architecture_mismatch",
    )
