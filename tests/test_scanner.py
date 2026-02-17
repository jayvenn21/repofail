"""Tests for repo scanner and host inspector."""

import tempfile
from pathlib import Path

import pytest

from repofail.scanner import scan_repo, inspect_host


def test_scan_repo_empty_dir():
    """Empty dir should return minimal profile."""
    with tempfile.TemporaryDirectory() as d:
        profile = scan_repo(d)
        assert profile.path == str(Path(d).resolve())
        assert profile.name == Path(d).name
        assert not profile.uses_torch
        assert not profile.requires_cuda


def test_scan_repo_requirements_txt():
    """requirements.txt with torch should be detected."""
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "requirements.txt").write_text("torch>=2.0\ntransformers\n")
        profile = scan_repo(d)
        assert profile.uses_torch
        assert "Transformers" in profile.frameworks


def test_scan_repo_torch_cuda_in_code():
    """Python file importing torch.cuda should set requires_cuda and cuda_files."""
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "trainer.py").write_text("import torch.cuda\nx = torch.cuda.is_available()")
        profile = scan_repo(d)
        assert profile.uses_torch
        assert profile.requires_cuda
        assert "trainer.py" in profile.cuda_files


def test_scan_repo_pyproject():
    """pyproject.toml should be parsed."""
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "pyproject.toml").write_text("""
[project]
name = "test-repo"
requires-python = ">=3.10,<3.12"
dependencies = ["torch", "diffusers"]
""")
        profile = scan_repo(d)
        assert profile.name == "test-repo"
        assert profile.python_version == ">=3.10,<3.12"
        assert profile.uses_torch
        assert "Diffusers" in profile.frameworks


def test_scan_repo_node_native():
    """package.json with node-gyp should be detected."""
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "package.json").write_text('{"dependencies": {"node-gyp": "^10.0.0"}}')
        profile = scan_repo(d)
        assert profile.has_package_json
        assert "node-gyp" in profile.node_native_modules


def test_scan_repo_lock_file_missing():
    """package.json with deps but no lock file should set node_lock_file_missing."""
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "package.json").write_text('{"dependencies": {"lodash": "^4.0.0"}}')
        profile = scan_repo(d)
        assert profile.has_package_json
        assert profile.node_lock_file_missing
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "package.json").write_text('{"dependencies": {"lodash": "^4.0.0"}}')
        (Path(d) / "package-lock.json").write_text("{}")
        profile = scan_repo(d)
        assert not profile.node_lock_file_missing


def test_scan_repo_name_prefers_folder_over_generic_package_json():
    """Generic package.json names (my-t3-app, etc.) are skipped; folder name wins."""
    with tempfile.TemporaryDirectory() as d:
        folder_name = Path(d).name
        (Path(d) / "package.json").write_text('{"name": "my-t3-app"}')
        profile = scan_repo(d)
        assert profile.name == folder_name


def test_inspect_host_returns_profile():
    """Host inspector should return HostProfile with required fields."""
    host = inspect_host()
    assert host.os in ("macos", "linux", "windows")
    assert host.arch in ("arm64", "x86_64")
    assert isinstance(host.cuda_available, bool)
    assert isinstance(host.has_compiler, bool)
    assert host.python_version is not None
    # node_version, rust_version may be None if not installed
    assert host.node_version is None or host.node_version.startswith(("v", "0", "1", "2"))
