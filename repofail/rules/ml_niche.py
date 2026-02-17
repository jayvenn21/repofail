"""Niche ML rules: LoRA/MLX scaling, torchao-torch compatibility."""

from ..models import HostProfile, RepoProfile
from .base import RuleResult, Severity


def _get_package_versions(repo: RepoProfile) -> dict[str, str]:
    """Merge version constraints from requirements and pyproject."""
    versions: dict[str, str] = {}
    for source in [repo.raw.get("requirements"), repo.raw.get("pyproject")]:
        if source:
            versions.update(source.get("package_versions", {}))
    return versions


def _torch_max_version(constraint: str) -> float | None:
    """
    Heuristic: extract max torch version allowed by constraint.
    e.g. "==2.1.*" -> 2.1, ">=2.2,<2.4" -> 2.4, "<2.2" -> 2.19 (below 2.2)
    Returns None if unclear.
    """
    import re
    matches = re.findall(r"(\d+)\.(\d+)(?:\.(\d+))?", constraint)
    if not matches:
        return None
    major_minor = []
    for m in matches:
        major, minor, patch = int(m[0]), int(m[1]), int(m[2]) if m[2] else 0
        major_minor.append(major + minor / 100 + patch / 10000)
    # For strict < (e.g. <2.2), max allowed is just below that
    if re.search(r"<\s*[\d.]+", constraint):
        ceiling = min(major_minor)
        return round(ceiling - 0.01, 2)  # e.g. 2.2 -> 2.19
    return max(major_minor) if major_minor else None


def check_lora_mlx_scaling(repo: RepoProfile, host: HostProfile) -> RuleResult | None:
    """
    LoRA scaling behavior differs on MLX backend.
    Fires when: PEFT/LoRA in repo + host has Metal (MLX) + no CUDA.
    """
    if "PEFT" not in repo.frameworks and "LoRA" not in " ".join(repo.frameworks):
        return None
    if host.os != "macos" or not getattr(host, "has_metal", False):
        return None
    if host.cuda_available:
        return None
    return RuleResult(
        rule_id="lora_mlx_scaling",
        severity=Severity.MEDIUM,
        message="LoRA scaling behavior differs on MLX backend.",
        reason="MLX DiT/PEFT path does not use PEFT hooks identically to CUDA path; scaling may differ.",
        host_summary="macOS arm64 (Metal/MLX), no NVIDIA GPU",
        category="hardware_incompatibility",
    )


def check_torchao_incompatible(repo: RepoProfile, host: HostProfile) -> RuleResult | None:
    """
    torchao installed but torch version may be incompatible.
    Known: torchao 0.5.x requires torch 2.2+; repo pins torch 2.1.* → incompat.
    """
    if "torchao" not in repo.frameworks:
        return None
    if not repo.uses_torch:
        return None

    versions = _get_package_versions(repo)
    torch_constraint = versions.get("torch")
    torchao_constraint = versions.get("torchao")

    if not torch_constraint and not torchao_constraint:
        return None  # Can't infer

    # torchao 0.5+ needs torch 2.2+. Check if torch is pinned < 2.2
    torch_max = _torch_max_version(torch_constraint) if torch_constraint else None
    if torch_max is not None and torch_max < 2.2:
        # Check if torchao is 0.5+
        torchao_ver = None
        if torchao_constraint:
            import re
            m = re.search(r"(\d+)\.(\d+)", torchao_constraint)
            if m:
                torchao_ver = int(m.group(1)) + int(m.group(2)) / 10
        if torchao_ver is None or torchao_ver >= 0.5:
            return RuleResult(
                rule_id="torchao_incompatible",
                severity=Severity.LOW,
                message="torchao installed but torch version may be incompatible.",
                reason=f"torchao 0.5.x requires torch 2.2+; repo pins torch {torch_constraint}.",
                host_summary="",
                category="spec_violation",
            )
    return None


