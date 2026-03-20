"""Format repofail scan results into a polished GitHub PR comment."""

from __future__ import annotations


def _status_icon(sev: str) -> str:
    return {
        "HIGH": ":red_circle:",
        "MEDIUM": ":orange_circle:",
        "LOW": ":yellow_circle:",
        "INFO": ":large_blue_circle:",
    }.get(sev, ":white_circle:")


def _gate_status(score: int, has_high: bool) -> tuple[str, str]:
    """Return (icon, label) for the quality gate."""
    if has_high:
        return ":x:", "Failed"
    if score >= 90:
        return ":white_check_mark:", "Passed"
    if score >= 70:
        return ":warning:", "Warning"
    return ":x:", "Failed"


def _format_evidence(ev: dict) -> list[str]:
    """Extract useful evidence fields as formatted lines."""
    lines = []
    sources = ev.get("sources", [])
    if sources:
        lines.append("Sources: " + " | ".join(f"`{s}`" for s in sources[:6]))
    if ev.get("likely_error"):
        lines.append(f"Impact: {ev['likely_error']}")
    fix = ev.get("suggested_fix") or ev.get("fix")
    if fix:
        lines.append(f"Fix: {fix}")
    return lines


def format_pr_comment(
    scan: dict,
    owner: str,
    repo: str,
    pr_number: int,
    branch: str,
) -> str:
    """Build a Markdown PR comment from repofail JSON output."""
    if "error" in scan:
        return (
            "## repofail\n\n"
            "| Status | Branch |\n"
            "|--------|--------|\n"
            f"| :warning: Scan error | `{branch}` |\n\n"
            f"```\n{scan['error'][:500]}\n```\n\n"
            "---\n"
            "<sub>Powered by <a href=\"https://github.com/jayvenn21/repofail\">repofail</a></sub>"
        )

    score = scan.get("estimated_success_probability", 100)
    results = scan.get("results", [])
    confidence = scan.get("confidence", "high")

    high = [r for r in results if r.get("severity") == "HIGH"]
    medium = [r for r in results if r.get("severity") in ("MEDIUM", "LOW")]
    info = [r for r in results if r.get("severity") == "INFO"]

    gate_icon, gate_label = _gate_status(score, bool(high))
    finding_counts = []
    if high:
        finding_counts.append(f"{len(high)} critical")
    if medium:
        finding_counts.append(f"{len(medium)} warning{'s' if len(medium) != 1 else ''}")
    if info:
        finding_counts.append(f"{len(info)} info")
    findings_str = ", ".join(finding_counts) if finding_counts else "none"

    lines: list[str] = []

    # Header
    lines.append("## repofail")
    lines.append("")

    # Summary table
    lines.append("| Quality Gate | Score | Findings | Confidence |")
    lines.append("|:------------|:------|:---------|:-----------|")
    lines.append(f"| {gate_icon} {gate_label} | **{score}%** | {findings_str} | {confidence} |")
    lines.append("")

    if not results:
        lines.append("> :white_check_mark: **No compatibility issues detected.** This branch is clear for the target environment.")
        lines.append("")
        lines.append("---")
        lines.append(f"<sub>Scanned `{branch}` | <a href=\"https://github.com/jayvenn21/repofail\">repofail</a> - deterministic runtime compatibility analysis</sub>")
        return "\n".join(lines)

    # Critical findings
    if high:
        lines.append("### Critical Issues")
        lines.append("")
        for r in high:
            rule_id = r.get("rule_id", "")
            msg = r.get("message", "")
            reason = r.get("reason", "")
            ev = r.get("evidence", {})

            lines.append(f"> {_status_icon('HIGH')} **{msg}**")
            lines.append(f"> ")
            lines.append(f"> {reason}")

            ev_lines = _format_evidence(ev)
            for el in ev_lines:
                lines.append(f"> {el}")
            lines.append("")

    # Warnings
    if medium:
        lines.append("<details>")
        lines.append(f"<summary><b>Warnings ({len(medium)})</b></summary>")
        lines.append("")
        lines.append("| Severity | Finding | Detail |")
        lines.append("|:---------|:--------|:-------|")
        for r in medium:
            sev = r.get("severity", "MEDIUM")
            lines.append(f"| {_status_icon(sev)} {sev} | {r.get('message', '')} | {r.get('reason', '')} |")
        lines.append("")
        lines.append("</details>")
        lines.append("")

    # Info notes
    if info:
        lines.append("<details>")
        lines.append(f"<summary>Structural notes ({len(info)})</summary>")
        lines.append("")
        lines.append("| Finding | Detail |")
        lines.append("|:--------|:-------|")
        for r in info:
            lines.append(f"| {r.get('message', '')} | {r.get('reason', '')} |")
        lines.append("")
        lines.append("</details>")
        lines.append("")

    # Footer
    lines.append("---")
    lines.append(f"<sub>Scanned `{branch}` | <a href=\"https://github.com/jayvenn21/repofail\">repofail</a> - deterministic runtime compatibility analysis</sub>")

    return "\n".join(lines)
