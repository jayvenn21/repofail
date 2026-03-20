"""Tests for PR comment formatting."""

from comment import format_pr_comment


def test_clean_scan():
    scan = {"estimated_success_probability": 100, "results": [], "confidence": "high"}
    body = format_pr_comment(scan, "owner", "repo", 1, "main")
    assert "No compatibility issues" in body
    assert "repofail" in body
    assert "Quality Gate" in body
    assert "Passed" in body


def test_high_findings():
    scan = {
        "estimated_success_probability": 32,
        "confidence": "high",
        "results": [
            {
                "rule_id": "torch_cuda_mismatch",
                "severity": "HIGH",
                "message": "Hard-coded CUDA path, host has no GPU.",
                "reason": "torch.cuda.is_available() at line 45.",
                "evidence": {"likely_error": "RuntimeError: CUDA unavailable"},
            },
            {
                "rule_id": "spec_drift",
                "severity": "MEDIUM",
                "message": "Spec drift detected.",
                "reason": "3 distinct Python targets.",
            },
        ],
    }
    body = format_pr_comment(scan, "owner", "repo", 2, "feature")
    assert "Critical Issues" in body
    assert "CUDA" in body
    assert "Warnings" in body
    assert "32%" in body
    assert "Failed" in body


def test_info_only():
    scan = {
        "estimated_success_probability": 95,
        "confidence": "high",
        "results": [
            {
                "severity": "INFO",
                "message": "Mixed Python + Node monorepo.",
                "reason": "Both detected.",
            }
        ],
    }
    body = format_pr_comment(scan, "owner", "repo", 3, "dev")
    assert "Structural notes" in body
    assert "1 info" in body


def test_error_scan():
    scan = {"error": "repofail produced no output"}
    body = format_pr_comment(scan, "owner", "repo", 4, "fix")
    assert "Scan error" in body


if __name__ == "__main__":
    test_clean_scan()
    test_high_findings()
    test_info_only()
    test_error_scan()
    print("All tests passed.")
