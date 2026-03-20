"""Format repofail scan results into a polished GitHub PR comment."""

from __future__ import annotations


def _severity_emoji(sev: str) -> str:
    return {"HIGH": "\u274c", "MEDIUM": "\u26a0\ufe0f", "LOW": "\u2139\ufe0f", "INFO": "\U0001f4cb"}.get(sev, "\u2022")


def _score_bar(score: int) -> str:
    filled = score // 10
    empty = 10 - filled
    if score >= 90:
        color = "\U0001f7e2"
    elif score >= 70:
        color = "\U0001f7e1"
    else:
        color = "\U0001f534"
    return f"{color} {'█' * filled}{'░' * empty} **{score}%**"


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
            "## repofail · compatibility report\n\n"
            f"> Scan failed: `{scan['error']}`\n\n"
            f"Branch: `{branch}`"
        )

    score = scan.get("estimated_success_probability", 100)
    results = scan.get("results", [])
    confidence = scan.get("confidence", "high")

    lines = [
        "## repofail · compatibility report",
        "",
        f"**Compatibility score:** {_score_bar(score)}",
        f"**Confidence:** {confidence}",
        f"**Branch:** `{branch}`",
        "",
    ]

    if not results:
        lines.append("> **No compatibility issues detected.** This repo looks good for the CI environment.")
        lines.append("")
        lines.append("---")
        lines.append(
            "*Powered by [repofail](https://github.com/jayvenn21/repofail) - "
            "deterministic runtime compatibility analysis*"
        )
        return "\n".join(lines)

    high = [r for r in results if r.get("severity") == "HIGH"]
    medium = [r for r in results if r.get("severity") in ("MEDIUM", "LOW")]
    info = [r for r in results if r.get("severity") == "INFO"]

    if high:
        lines.append("### Hard failures")
        lines.append("")
        for r in high:
            lines.append(f"{_severity_emoji('HIGH')} **{r.get('message', '')}**")
            lines.append(f"  - {r.get('reason', '')}")
            ev = r.get("evidence", {})
            if ev.get("likely_error"):
                lines.append(f"  - Likely error: `{ev['likely_error']}`")
            lines.append("")

    if medium:
        lines.append("### Runtime risks")
        lines.append("")
        for r in medium:
            sev = r.get("severity", "MEDIUM")
            lines.append(f"{_severity_emoji(sev)} {r.get('message', '')}")
            lines.append(f"  - {r.get('reason', '')}")
            lines.append("")

    if info:
        lines.append("<details>")
        lines.append(f"<summary>Structural notes ({len(info)})</summary>")
        lines.append("")
        for r in info:
            lines.append(f"- {_severity_emoji('INFO')} {r.get('message', '')} - {r.get('reason', '')}")
        lines.append("")
        lines.append("</details>")
        lines.append("")

    lines.append("---")

    summary_parts = []
    if high:
        summary_parts.append(f"{len(high)} hard failure{'s' if len(high) != 1 else ''}")
    if medium:
        summary_parts.append(f"{len(medium)} runtime risk{'s' if len(medium) != 1 else ''}")
    if info:
        summary_parts.append(f"{len(info)} note{'s' if len(info) != 1 else ''}")
    lines.append(f"**Summary:** {' · '.join(summary_parts)}")
    lines.append("")

    if high:
        lines.append(
            "> **Action required:** This PR has deterministic compatibility issues "
            "that will cause failures in the target environment."
        )
        lines.append("")

    lines.append(
        "*Powered by [repofail](https://github.com/jayvenn21/repofail) - "
        "deterministic runtime compatibility analysis*"
    )

    return "\n".join(lines)
