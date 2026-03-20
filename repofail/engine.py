"""Rule engine - runs all rules against repo + host profiles."""

from pathlib import Path

import yaml as _yaml

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
    go_version,
    rust_compat,
)

_RULE_ID_MAP: dict[str, str] = {
    "torch_cuda.check": "torch_cuda_mismatch",
    "python_version.check": "python_version_mismatch",
    "python_eol.check": "python_eol",
    "spec_drift.check": "spec_drift",
    "abi_wheel_mismatch.check": "abi_wheel_mismatch",
    "apple_silicon.check": "apple_silicon_x86",
    "native_toolchain.check": "native_toolchain_missing",
    "gpu_memory.check": "gpu_memory_insufficient",
    "node_windows.check": "node_windows",
    "node_engine.check": "node_engine_mismatch",
    "node_eol.check": "node_eol",
    "lock_file_missing.check": "lock_file_missing",
    "system_libs.check": "system_libs_missing",
    "port_collision.check": "port_collision",
    "docker_only.check": "docker_only",
    "rust_compat.check_rust_version": "rust_version_mismatch",
    "rust_compat.check_rust_target_platform": "rust_target_platform",
    "go_version.check": "go_version_mismatch",
    "go_version.check_cgo": "go_cgo_missing",
    "go_version.check_os_build_tags": "go_os_build_tags",
    "ml_niche.check_lora_mlx_scaling": "lora_mlx_scaling",
    "ml_niche.check_torchao_incompatible": "torchao_incompatible",
}


def _load_config(repo_path: Path) -> dict:
    """Load .repofail.yaml from repo root, if present."""
    cfg_path = repo_path / ".repofail.yaml"
    if cfg_path.exists():
        try:
            return _yaml.safe_load(cfg_path.read_text()) or {}
        except Exception:
            pass
    return {}


def _get_disabled_rules(config: dict) -> set[str]:
    """Extract disabled rule IDs from config."""
    rules = config.get("rules", {})
    disabled = rules.get("disable", [])
    if isinstance(disabled, list):
        return set(disabled)
    return set()


def run_rules(repo: RepoProfile, host: HostProfile) -> list[RuleResult]:
    """Run all built-in and YAML rules, return any that fire."""
    config = _load_config(Path(repo.path))
    disabled = _get_disabled_rules(config)

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
        rust_compat.check_rust_version,
        rust_compat.check_rust_target_platform,
        go_version.check,
        go_version.check_cgo,
        go_version.check_os_build_tags,
        ml_niche.check_lora_mlx_scaling,
        ml_niche.check_torchao_incompatible,
    ]
    checks.extend(info_signals.CHECKS)
    results: list[RuleResult] = []
    for check_fn in checks:
        fn_key = f"{check_fn.__module__.rsplit('.', 1)[-1]}.{check_fn.__name__}"
        rule_id = _RULE_ID_MAP.get(fn_key)
        if rule_id and rule_id in disabled:
            continue
        try:
            r = check_fn(repo, host)
            if r is not None:
                if r.rule_id in disabled:
                    continue
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
