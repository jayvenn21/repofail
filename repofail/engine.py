"""Rule engine — runs five rules against repo + host profiles."""

from pathlib import Path

from .models import HostProfile, RepoProfile
from .rules.base import RuleResult, Severity
from .rules import (
    abi_wheel_mismatch,
    torch_cuda,
    python_version,
    python_eol,
    spec_drift,
    apple_silicon,
    native_toolchain,
    gpu_memory,
    node_windows,
    node_engine,
    node_eol,
    lock_file_missing,
    system_libs,
    ml_niche,
    info_signals,
    port_collision,
    docker_only,
)


def run_rules(repo: RepoProfile, host: HostProfile) -> list[RuleResult]:
    """Run all built-in and YAML rules, return any that fire."""
    checks = [
        torch_cuda.check,
        python_version.check,
        python_eol.check,
        spec_drift.check,
        abi_wheel_mismatch.check,
        apple_silicon.check,
        native_toolchain.check,
        gpu_memory.check,
        node_windows.check,
        node_engine.check,
        node_eol.check,
        lock_file_missing.check,
        system_libs.check,
        port_collision.check,
        docker_only.check,
        ml_niche.check_lora_mlx_scaling,
        ml_niche.check_torchao_incompatible,
    ]
    checks.extend(info_signals.CHECKS)
    results: list[RuleResult] = []
    for check_fn in checks:
        try:
            r = check_fn(repo, host)
            if r is not None:
                results.append(r)
        except Exception:
            pass
    # Load and run YAML rules from repo
    try:
        from .rules.yaml_loader import run_yaml_rules
        yaml_results = run_yaml_rules(repo, host, Path(repo.path))
        results.extend(yaml_results)
    except Exception:
        pass
    # Sort by severity: HIGH first, INFO last
    order = {Severity.HIGH: 0, Severity.MEDIUM: 1, Severity.LOW: 2, Severity.INFO: 3}
    results.sort(key=lambda x: order.get(x.severity, 4))
    return results
