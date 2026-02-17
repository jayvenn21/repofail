"""Tests for Stage 5 — audit, simulate."""

import json
import tempfile
from pathlib import Path

import pytest

from repofail.fleet import audit, simulate, host_from_dict


def test_audit_empty_dir():
    """Audit on dir with no repos returns empty."""
    with tempfile.TemporaryDirectory() as d:
        r = audit(Path(d))
        assert r == []


def test_audit_finds_repos():
    """Audit finds repo-like subdirs."""
    with tempfile.TemporaryDirectory() as base:
        base_p = Path(base)
        (base_p / "repo1").mkdir()
        (base_p / "repo1" / "pyproject.toml").write_text('[project]\nname="x"')
        (base_p / "repo2").mkdir()
        (base_p / "repo2" / "requirements.txt").write_text("torch")
        (base_p / "empty").mkdir()
        r = audit(base_p)
        assert len(r) == 2
        names = {x["name"] for x in r}
        assert "x" in names or "repo1" in names


def test_host_from_dict():
    """Host profile from dict."""
    h = host_from_dict({"os": "linux", "arch": "x86_64", "cuda_available": True})
    assert h.os == "linux"
    assert h.arch == "x86_64"
    assert h.cuda_available is True


def test_simulate():
    """Simulate runs rules against target host."""
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "x.py").write_text("import torch.cuda")
        (Path(d) / "requirements.txt").write_text("torch")
        host_file = Path(d) / "host.json"
        host_file.write_text(json.dumps({
            "os": "linux",
            "arch": "x86_64",
            "cuda_available": False,
            "python_version": "3.11",
            "has_compiler": True,
        }))
        repo, host, results = simulate(Path(d), host_file)
        assert repo.uses_torch
        assert host.os == "linux"
        assert any(r.rule_id == "torch_cuda_mismatch" for r in results)
