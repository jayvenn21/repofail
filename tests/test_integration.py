"""Integration tests — full pipeline on real temp repos."""

import tempfile
from pathlib import Path

import pytest

from repofail.scanner import scan_repo, inspect_host
from repofail.engine import run_rules


def test_full_pipeline_torch_cuda_repo():
    """Create repo with torch.cuda, run pipeline — should get torch_cuda rule on Mac."""
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "model.py").write_text("import torch.cuda\ndevice = 'cuda'")
        (Path(d) / "requirements.txt").write_text("torch>=2.0\n")

        repo = scan_repo(d)
        host = inspect_host()
        results = run_rules(repo, host)

        assert repo.uses_torch
        assert repo.requires_cuda
        assert "model.py" in repo.cuda_files

        # On Mac without CUDA, torch_cuda rule should fire
        if host.os == "macos" and not host.cuda_available:
            rule_ids = [r.rule_id for r in results]
            assert "torch_cuda_mismatch" in rule_ids


def test_full_pipeline_repofail_on_itself():
    """Run repofail on the repofail repo — should complete without error."""
    from pathlib import Path
    repo_path = Path(__file__).resolve().parent.parent
    repo = scan_repo(repo_path)
    host = inspect_host()
    results = run_rules(repo, host)

    assert repo.name == "repofail"
    assert repo.has_pyproject
    assert repo.python_version is not None
    # repofail doesn't use torch/cuda, so likely no rules fire
    assert isinstance(results, list)
