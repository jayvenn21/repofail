"""Tests for the five rules."""

import platform
import tempfile
from pathlib import Path

import pytest

from repofail.models import HostProfile, RepoProfile
from repofail.rules.torch_cuda import check as check_torch_cuda
from repofail.rules.python_version import check as check_python_version
from repofail.rules.apple_silicon import check as check_apple_silicon
from repofail.rules.native_toolchain import check as check_native_toolchain
from repofail.rules.gpu_memory import check as check_gpu_memory


def _make_repo(**kwargs) -> RepoProfile:
    defaults = {
        "path": "/tmp/test",
        "name": "test",
        "uses_torch": False,
        "requires_cuda": False,
        "cuda_files": [],
        "python_version": None,
        "frameworks": [],
        "node_native_modules": [],
        "has_cargo_toml": False,
        "rust_system_libs": [],
        "requires_libgl": False,
        "requires_ffmpeg": False,
        "raw": {},
    }
    return RepoProfile(**{**defaults, **kwargs})


def _make_host(**kwargs) -> HostProfile:
    defaults = {
        "os": "macos",
        "arch": "arm64",
        "cuda_available": False,
        "python_version": platform.python_version(),
        "node_version": None,
        "rust_version": None,
        "has_compiler": True,
        "has_metal": False,
        "has_libgl": True,
        "has_ffmpeg": True,
        "ram_gb": 16.0,
    }
    return HostProfile(**{**defaults, **kwargs})


def test_torch_cuda_fires_when_no_cuda():
    """Rule 1: Fires HIGH when repo hardcodes CUDA and host has none."""
    repo = _make_repo(uses_torch=True, requires_cuda=True, cuda_files=["trainer.py"], cuda_optional=False)
    host = _make_host(cuda_available=False)
    r = check_torch_cuda(repo, host)
    assert r is not None
    assert r.rule_id == "torch_cuda_mismatch"
    assert r.severity.value == "HIGH"
    assert r.evidence and "trainer.py" in str(r.evidence.get("repo_cuda_usage", []))


def test_torch_cuda_does_not_fire_with_cuda():
    """Rule 1: Does not fire when host has CUDA."""
    repo = _make_repo(uses_torch=True, requires_cuda=True)
    host = _make_host(cuda_available=True)
    r = check_torch_cuda(repo, host)
    assert r is None


def test_torch_cuda_does_not_fire_without_torch():
    """Rule 1: Does not fire when repo doesn't use torch."""
    repo = _make_repo(uses_torch=False)
    host = _make_host(cuda_available=False)
    r = check_torch_cuda(repo, host)
    assert r is None


def test_python_version_fires_when_mismatch():
    """Rule 3: Fires when host Python outside requires-python range."""
    repo = _make_repo(python_version=">=3.12")
    host = _make_host(python_version="3.11.0")
    r = check_python_version(repo, host)
    assert r is not None
    assert r.rule_id == "python_version_mismatch"
    assert r.severity.value == "HIGH"


def test_python_version_does_not_fire_when_match():
    """Rule 3: Does not fire when version in range."""
    repo = _make_repo(python_version=">=3.10,<3.12")
    host = _make_host(python_version="3.11.5")
    r = check_python_version(repo, host)
    assert r is None


def test_apple_silicon_fires_on_macos_arm_with_x86_packages():
    """Rule 2: Fires when arm64 macOS + x86-only packages."""
    repo = _make_repo(raw={"requirements": {"packages": ["nvidia-cuda-runtime-cu11", "torch"]}})
    host = _make_host(os="macos", arch="arm64")
    r = check_apple_silicon(repo, host)
    assert r is not None
    assert r.rule_id == "apple_silicon_wheels"


def test_apple_silicon_does_not_fire_on_linux():
    """Rule 2: Does not fire on Linux."""
    repo = _make_repo(raw={"requirements": {"packages": ["nvidia-cuda-runtime-cu11"]}})
    host = _make_host(os="linux", arch="x86_64")
    r = check_apple_silicon(repo, host)
    assert r is None


def test_native_toolchain_fires_when_no_compiler():
    """Rule 4: Fires when native modules but no compiler."""
    repo = _make_repo(node_native_modules=["node-gyp"], has_cargo_toml=False)
    host = _make_host(has_compiler=False)
    r = check_native_toolchain(repo, host)
    assert r is not None
    assert r.rule_id == "native_toolchain_missing"


def test_native_toolchain_does_not_fire_with_compiler():
    """Rule 4: Does not fire when compiler present."""
    repo = _make_repo(node_native_modules=["node-gyp"])
    host = _make_host(has_compiler=True)
    r = check_native_toolchain(repo, host)
    assert r is None


def test_gpu_memory_fires_when_low_ram():
    """Rule 5: Fires when large-model frameworks and low RAM."""
    repo = _make_repo(uses_torch=True, frameworks=["Diffusers", "Transformers"])
    host = _make_host(ram_gb=8.0)
    r = check_gpu_memory(repo, host)
    assert r is not None
    assert r.rule_id == "gpu_memory_risk"


def test_gpu_memory_does_not_fire_with_enough_ram():
    """Rule 5: Does not fire when RAM sufficient."""
    repo = _make_repo(uses_torch=True, frameworks=["Diffusers"])
    host = _make_host(ram_gb=32.0)
    r = check_gpu_memory(repo, host)
    assert r is None


def test_node_windows_fires():
    """Rule 6: Fires when Windows + node native modules."""
    from repofail.rules.node_windows import check as check_node_windows
    repo = _make_repo(node_native_modules=["node-gyp"])
    host = _make_host(os="windows")
    r = check_node_windows(repo, host)
    assert r is not None
    assert r.rule_id == "node_native_windows"


def test_node_engine_mismatch():
    """Node engine rule fires when host Node outside engines.node range."""
    from repofail.rules.node_engine import check as check_node_engine
    repo = _make_repo(has_package_json=True, node_engine_spec=">=18")
    host = _make_host(node_version="v16.20.0")
    r = check_node_engine(repo, host)
    assert r is not None
    assert r.rule_id == "node_engine_mismatch"
    assert r.severity.value == "HIGH"


def test_node_engine_no_fire_when_in_range():
    """Node engine rule does not fire when host satisfies engines.node."""
    from repofail.rules.node_engine import check as check_node_engine
    repo = _make_repo(has_package_json=True, node_engine_spec=">=18")
    host = _make_host(node_version="v20.12.2")
    r = check_node_engine(repo, host)
    assert r is None


def test_system_libs_fires():
    """Rule 7: Fires when repo needs libGL/ffmpeg but host doesn't have."""
    from repofail.rules.system_libs import check as check_system_libs
    repo = _make_repo(requires_libgl=True)
    host = _make_host(has_libgl=False)
    r = check_system_libs(repo, host)
    assert r is not None


def test_abi_wheel_mismatch_fires_on_arm64_py312():
    """ABI wheel rule fires when macOS arm64 + Python 3.12 + lagging packages."""
    from repofail.rules.abi_wheel_mismatch import check as check_abi
    repo = _make_repo(raw={"requirements": {"packages": ["bitsandbytes", "torch"]}})
    host = _make_host(os="macos", arch="arm64", python_version="3.12.1")
    r = check_abi(repo, host)
    assert r is not None
    assert r.rule_id == "abi_wheel_mismatch"
    assert r.severity.value == "HIGH"
    assert "bitsandbytes" in str(r.evidence.get("problematic_packages", []))


def test_abi_wheel_mismatch_does_not_fire_on_py311():
    """ABI wheel rule does not fire when Python < 3.12."""
    from repofail.rules.abi_wheel_mismatch import check as check_abi
    repo = _make_repo(raw={"requirements": {"packages": ["bitsandbytes"]}})
    host = _make_host(os="macos", arch="arm64", python_version="3.11.5")
    r = check_abi(repo, host)
    assert r is None


def test_abi_wheel_mismatch_does_not_fire_on_linux():
    """ABI wheel rule does not fire when host is not macOS arm64."""
    from repofail.rules.abi_wheel_mismatch import check as check_abi
    repo = _make_repo(raw={"requirements": {"packages": ["bitsandbytes"]}})
    host = _make_host(os="linux", arch="x86_64", python_version="3.12.1")
    r = check_abi(repo, host)
    assert r is None


def test_lock_file_missing_fires():
    """Lock file rule fires when package.json has deps but no lock file."""
    from repofail.rules.lock_file_missing import check as check_lock
    repo = _make_repo(has_package_json=True, node_lock_file_missing=True)
    host = _make_host()
    r = check_lock(repo, host)
    assert r is not None
    assert r.rule_id == "lock_file_missing"
    assert r.severity.value == "HIGH"


def test_node_eol_fires():
    """Node EOL rule fires when engines.node requires 14 or 16."""
    from repofail.rules.node_eol import check as check_node_eol
    repo = _make_repo(has_package_json=True, node_engine_spec="16.x")
    host = _make_host()
    r = check_node_eol(repo, host)
    assert r is not None
    assert r.rule_id == "node_eol"
    assert r.severity.value == "HIGH"
    assert r.evidence.get("eol_major") == 16


def test_python_eol_fires():
    """Python EOL rule fires when requires-python pins to 3.7 or 3.8."""
    from repofail.rules.python_eol import check as check_python_eol
    repo = _make_repo(python_version="==3.8")
    host = _make_host()
    r = check_python_eol(repo, host)
    assert r is not None
    assert r.rule_id == "python_eol"
    assert r.severity.value == "HIGH"
