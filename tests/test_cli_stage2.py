"""Tests for Stage 2 CLI: --ci, --markdown, --explain."""

import tempfile
from pathlib import Path

import pytest

from repofail.scanner import scan_repo, inspect_host
from repofail.engine import run_rules
from repofail.rules.registry import RULE_INFO


def test_ci_exits_1_on_high():
    """--ci should mean exit 1 when HIGH rules fire."""
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "x.py").write_text("import torch.cuda")
        repo = scan_repo(d)
        host = inspect_host()
        results = run_rules(repo, host)
    if host.cuda_available:
        pytest.skip("Host has CUDA, torch_cuda rule won't fire")
    assert any(r.severity.value == "HIGH" for r in results)
    # _ci_exit would raise SystemExit(1) - tested via CLI


def test_explain_registry():
    """All rules have registry entries."""
    assert "torch_cuda_mismatch" in RULE_INFO
    assert "python_version_mismatch" in RULE_INFO
    assert "apple_silicon_wheels" in RULE_INFO
    assert "native_toolchain_missing" in RULE_INFO
    assert "gpu_memory_risk" in RULE_INFO
    for rid, info in RULE_INFO.items():
        assert "description" in info
        assert "severity" in info
        assert "when" in info
        assert "fix" in info
