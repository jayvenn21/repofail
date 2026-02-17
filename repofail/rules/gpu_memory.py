"""Rule 5: GPU memory risk heuristic."""

from ..models import HostProfile, RepoProfile
from .base import RuleResult, Severity

RAM_THRESHOLD_GB = 16


def check(repo: RepoProfile, host: HostProfile) -> RuleResult | None:
    """If repo references large models and host RAM < threshold, flag LOW/MEDIUM."""
    if not repo.uses_torch:
        return None
    # Heuristic: diffusers/transformers often use large models
    large_model_frameworks = {"Diffusers", "Transformers", "PEFT"}
    if not (repo.frameworks and large_model_frameworks & set(repo.frameworks)):
        return None

    if host.ram_gb is None:
        return None
    if host.ram_gb >= RAM_THRESHOLD_GB:
        return None

    severity = Severity.MEDIUM if host.ram_gb < 8 else Severity.LOW
    return RuleResult(
        rule_id="gpu_memory_risk",
        severity=severity,
        message=f"Repo uses large-model frameworks; host has {host.ram_gb:.0f} GB RAM.",
        reason=f"Detected {', '.join(large_model_frameworks & set(repo.frameworks))}; recommend >= {RAM_THRESHOLD_GB} GB",
        host_summary=f"{host.os} {host.arch}, {host.ram_gb:.0f} GB RAM",
        category="hardware_incompatibility",
    )
