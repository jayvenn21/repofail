"""Tests for Stage 4 — local failure telemetry."""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from repofail.telemetry import (
    FailureReport,
    save_report,
    load_reports,
    get_stats,
    REPORTS_DIR,
)


def test_save_report(tmp_path):
    """Saving report creates file in reports dir."""
    with patch("repofail.telemetry.REPORTS_DIR", tmp_path):
            from repofail.telemetry import save_report, load_reports, get_stats
            from repofail.models import HostProfile

            host = HostProfile(os="linux", arch="x86_64", cuda_available=True, python_version="3.11")
            results = [
                type("R", (), {"rule_id": "torch_cuda_mismatch", "severity": type("S", (), {"value": "HIGH"})()})(),
            ]
            p = save_report("test-repo", results, host)
            assert p is not None
            assert p.exists()
            data = json.loads(p.read_text())
            assert data["repo_name"] == "test-repo"
            assert "torch_cuda_mismatch" in data["rule_ids"]


def test_save_report_no_results():
    """No save when no results."""
    from repofail.telemetry import save_report
    from repofail.models import HostProfile

    host = HostProfile(os="macos", arch="arm64", cuda_available=False)
    p = save_report("x", [], host)
    assert p is None


def test_get_stats_empty():
    """Stats when no reports."""
    with patch("repofail.telemetry.REPORTS_DIR", Path("/nonexistent/repofail/stats")):
        from repofail.telemetry import get_stats
        s = get_stats()
        assert s["total_runs"] == 0
