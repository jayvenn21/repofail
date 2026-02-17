"""Tests for Stage 3 — environment contracts."""

import json
import tempfile
from pathlib import Path

import pytest

from repofail.scanner import scan_repo
from repofail.contract import generate_contract, validate_contract, EnvironmentContract


def test_generate_contract_python_only():
    """Contract from Python-only repo."""
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "pyproject.toml").write_text('[project]\nname = "x"\nrequires-python = ">=3.10"')
        repo = scan_repo(d)
        c = generate_contract(repo)
        assert c.requires.get("python") == ">=3.10"
        assert "cuda" not in c.requires


def test_generate_contract_torch_cuda():
    """Contract from torch.cuda repo requires cuda."""
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "x.py").write_text("import torch.cuda")
        (Path(d) / "requirements.txt").write_text("torch")
        repo = scan_repo(d)
        c = generate_contract(repo)
        assert c.requires.get("cuda") is True


def test_generate_contract_to_json():
    """Contract serializes to valid JSON."""
    c = EnvironmentContract(repo="test", requires={"python": ">=3.10"}, optional={})
    data = json.loads(c.to_json())
    assert data["repo"] == "test"
    assert data["requires"]["python"] == ">=3.10"
    assert "repofail_contract" in data


def test_validate_contract_python_pass():
    """Host with matching Python satisfies contract."""
    c = EnvironmentContract(requires={"python": ">=3.10,<3.13"}, optional={})
    host = {"python_version": "3.11.0", "cuda_available": False, "has_compiler": True}
    failures = validate_contract(c, host)
    assert len(failures) == 0


def test_validate_contract_python_fail():
    """Host with wrong Python fails contract."""
    c = EnvironmentContract(requires={"python": ">=3.12"}, optional={})
    host = {"python_version": "3.11.0", "cuda_available": False, "has_compiler": True}
    failures = validate_contract(c, host)
    assert any("python" in f[0] for f in failures)


def test_validate_contract_cuda_required():
    """Host without CUDA fails when contract requires it."""
    c = EnvironmentContract(requires={"cuda": True}, optional={})
    host = {"cuda_available": False}
    failures = validate_contract(c, host)
    assert any("cuda" in f[0] for f in failures)


def test_validate_contract_node_required():
    """Host without Node fails when contract requires it."""
    c = EnvironmentContract(requires={"node": True}, optional={})
    host = {"node_version": None}
    failures = validate_contract(c, host)
    assert any("node" in f[0] for f in failures)
