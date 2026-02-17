"""Tests for niche ML rules: LoRA/MLX scaling, torchao incompatible."""

import tempfile
from pathlib import Path

import pytest

from repofail.models import HostProfile, RepoProfile
from repofail.rules.ml_niche import check_lora_mlx_scaling, check_torchao_incompatible
from repofail.risk import estimate_success_probability
from repofail.rules.base import RuleResult, Severity


def _make_repo(**kwargs) -> RepoProfile:
    defaults = {
        "path": "/tmp/test",
        "name": "test",
        "uses_torch": False,
        "frameworks": [],
        "raw": {},
    }
    return RepoProfile(**{**defaults, **kwargs})


def _make_host(**kwargs) -> HostProfile:
    defaults = {
        "os": "macos",
        "arch": "arm64",
        "cuda_available": False,
        "has_metal": True,
    }
    return HostProfile(**{**defaults, **kwargs})


def test_lora_mlx_scaling_fires_on_macos_metal_no_cuda():
    """LoRA/MLX rule fires when PEFT + macOS Metal, no CUDA."""
    repo = _make_repo(frameworks=["PEFT", "Transformers"])
    host = _make_host(os="macos", has_metal=True, cuda_available=False)
    r = check_lora_mlx_scaling(repo, host)
    assert r is not None
    assert r.rule_id == "lora_mlx_scaling"
    assert r.severity == Severity.MEDIUM


def test_lora_mlx_scaling_does_not_fire_without_peft():
    """LoRA/MLX rule does not fire when repo lacks PEFT."""
    repo = _make_repo(frameworks=["Transformers"])
    host = _make_host(os="macos", has_metal=True)
    r = check_lora_mlx_scaling(repo, host)
    assert r is None


def test_lora_mlx_scaling_does_not_fire_with_cuda():
    """LoRA/MLX rule does not fire when host has CUDA."""
    repo = _make_repo(frameworks=["PEFT"])
    host = _make_host(os="macos", has_metal=True, cuda_available=True)
    r = check_lora_mlx_scaling(repo, host)
    assert r is None


def test_torchao_incompatible_fires_when_torch_pinned_low():
    """torchao rule fires when torch < 2.2 and torchao present."""
    repo = _make_repo(
        uses_torch=True,
        frameworks=["torchao"],
        raw={"requirements": {"package_versions": {"torch": "==2.1.*"}, "packages": []}, "pyproject": {}},
    )
    host = _make_host()
    r = check_torchao_incompatible(repo, host)
    assert r is not None
    assert r.rule_id == "torchao_incompatible"
    assert r.severity == Severity.LOW


def test_torchao_incompatible_does_not_fire_without_torchao():
    """torchao rule does not fire when torchao not in repo."""
    repo = _make_repo(uses_torch=True, frameworks=["Transformers"], raw={"requirements": {"package_versions": {"torch": "==2.1.*"}}})
    host = _make_host()
    r = check_torchao_incompatible(repo, host)
    assert r is None


def test_estimate_success_probability_confidence_multiplier():
    """Medium confidence reduces penalty (0.75x)."""
    r = RuleResult("t", Severity.INFO, "m", "r", confidence="medium")
    assert estimate_success_probability([r]) == 96  # 5 * 0.75 = 3.75, 100-4=96


def test_estimate_success_probability():
    """Probability decreases with severity-weighted results (confidence multiplier = 1.0 for high)."""
    def make_result(severity):
        return RuleResult("test", severity, "msg", "reason")

    assert estimate_success_probability([]) == 100
    assert estimate_success_probability([make_result(Severity.LOW)]) == 93   # 7 penalty
    assert estimate_success_probability([make_result(Severity.MEDIUM)]) == 80  # 20 penalty
    assert estimate_success_probability([make_result(Severity.HIGH)]) == 55   # 45 penalty
    assert estimate_success_probability([make_result(Severity.INFO)]) == 95   # 5 penalty
    assert estimate_success_probability([make_result(Severity.HIGH), make_result(Severity.MEDIUM)]) == 35  # 45+20
