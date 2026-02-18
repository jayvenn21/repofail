"""Rule: CUDA required but host has no GPU — deterministic, HIGH when hardcoded."""

from ..models import HostProfile, RepoProfile
from .base import RuleResult, Severity


def check(repo: RepoProfile, host: HostProfile) -> RuleResult | None:
    """
    Trigger when repo requires CUDA and host has none.
    HIGH if hardcoded (device='cuda', bitsandbytes, nvidia/cuda Dockerfile).
    MEDIUM if conditional (torch.cuda.is_available() guards).
    """
    if not repo.requires_cuda:
        return None
    if host.cuda_available:
        return None

    # Strong evidence = hardcoded CUDA, CUDA-only deps, or Dockerfile nvidia/cuda
    cuda_mandatory_pkgs = bool(repo.cuda_mandatory_packages)
    dockerfile_cuda = repo.dockerfile_has_cuda
    hardcoded_cuda = bool(repo.cuda_files) and not repo.cuda_optional

    is_mandatory = cuda_mandatory_pkgs or dockerfile_cuda or hardcoded_cuda
    severity = Severity.HIGH if is_mandatory else Severity.MEDIUM

    repo_cuda_usage = []
    if repo.cuda_usages:
        for u in repo.cuda_usages[:8]:
            f, ln, kind = u.get("file", "?"), u.get("line", 0), u.get("kind", "cuda")
            repo_cuda_usage.append(f"Found {kind} in {f}:{ln}" if ln else f"{f}: {kind}")
    elif repo.cuda_files:
        for f in repo.cuda_files[:5]:
            repo_cuda_usage.append(f"{f}: torch.cuda or device='cuda'")
    if repo.dockerfile_has_cuda:
        repo_cuda_usage.append("Dockerfile: FROM nvidia/cuda or cuda installed")
    if repo.cuda_mandatory_packages:
        repo_cuda_usage.append(f"deps: {', '.join(repo.cuda_mandatory_packages[:5])}")

    reason = (
        f"Detected {'hard-coded ' if is_mandatory else ''}CUDA usage. "
        "Host reports no CUDA-capable GPU."
    )
    if is_mandatory:
        if not repo.cuda_optional and repo.cuda_usages:
            reason += " No torch.cuda.is_available() guard detected."
        reason += " This will raise RuntimeError: CUDA unavailable."
    else:
        reason += " Code may have CPU fallback (conditional cuda check)."

    evidence = {
        "repo_cuda_usage": repo_cuda_usage,
        "host_cuda": False,
        "cuda_mandatory": is_mandatory,
        "has_is_available_guard": repo.cuda_optional,
        "determinism": 1.0,
        "breakage_likelihood": "~100%",
        "likely_error": "RuntimeError: CUDA error: no CUDA-capable device is detected",
    }

    host_summary = f"{host.os} {host.arch}, no NVIDIA GPU"
    if host.os == "macos" and host.arch == "arm64":
        host_summary += " (Apple Silicon)"

    return RuleResult(
        rule_id="torch_cuda_mismatch",
        severity=severity,
        message="Hard-coded CUDA execution path detected." if is_mandatory else "Repository uses CUDA; host has no GPU.",
        reason=reason,
        host_summary=host_summary,
        evidence=evidence,
        category="hardware_incompatibility",
        confidence="high",
    )
