"""Format repofail scan results into a polished GitHub PR comment.

Design principles:
- No emoji anywhere
- Shields.io badges for status indicators
- Inline logo in header
- Collapsible sections for non-critical content
- Clean, minimal footer
"""

from __future__ import annotations

import urllib.parse

LOGO_URL = "https://raw.githubusercontent.com/jayvenn21/repofail/main/docs/logo.png"
REPO_URL = "https://github.com/jayvenn21/repofail"


def _badge(label: str, value: str, color: str) -> str:
    """Generate a shields.io badge image tag."""
    label_enc = urllib.parse.quote(label)
    value_enc = urllib.parse.quote(value)
    url = f"https://img.shields.io/badge/{label_enc}-{value_enc}-{color}?style=flat-square"
    return f'<img src="{url}" alt="{label}: {value}">'


def _gate_badge(score: int, has_high: bool) -> str:
    if has_high:
        return _badge("quality gate", "failed", "critical")
    if score >= 90:
        return _badge("quality gate", "passed", "brightgreen")
    if score >= 70:
        return _badge("quality gate", "warning", "yellow")
    return _badge("quality gate", "failed", "critical")


def _score_badge(score: int) -> str:
    if score >= 90:
        color = "brightgreen"
    elif score >= 70:
        color = "yellow"
    elif score >= 50:
        color = "orange"
    else:
        color = "critical"
    return _badge("score", f"{score}%", color)


def _findings_badge(high: int, medium: int, info: int) -> str:
    parts = []
    if high:
        parts.append(f"{high} critical")
    if medium:
        parts.append(f"{medium} warning{'s' if medium != 1 else ''}")
    if info:
        parts.append(f"{info} note{'s' if info != 1 else ''}")
    if not parts:
        return _badge("findings", "none", "brightgreen")
    text = ", ".join(parts)
    color = "critical" if high else ("orange" if medium else "blue")
    return _badge("findings", text, color)


def _format_evidence(ev: dict) -> str:
    """Format evidence block as a clean markdown snippet."""
    parts = []
    sources = ev.get("sources", [])
    if sources:
        formatted = " | ".join(f"`{s}`" for s in sources[:6])
        parts.append(f"**Sources:** {formatted}")
    if ev.get("likely_error"):
        parts.append(f"**Impact:** {ev['likely_error']}")
    fix = ev.get("suggested_fix") or ev.get("fix")
    if fix:
        parts.append(f"**Fix:** {fix}")
    return "<br>".join(parts)


def format_pr_comment(
    scan: dict,
    owner: str,
    repo: str,
    pr_number: int,
    branch: str,
) -> str:
    """Build a Markdown PR comment from repofail JSON output."""
    L: list[str] = []

    # Header with logo
    header = (
        f'<h3><img src="{LOGO_URL}" width="22" align="top">'
        f"&nbsp;repofail</h3>"
    )

    if "error" in scan:
        L.append(header)
        L.append("")
        L.append(_badge("status", "scan error", "critical"))
        L.append("")
        L.append(f"```\n{scan['error'][:500]}\n```")
        L.append("")
        L.append("---")
        L.append(
            f'<sub><a href="{REPO_URL}">repofail</a>'
            f" scanned <code>{branch}</code></sub>"
        )
        return "\n".join(L)

    score = scan.get("estimated_success_probability", 100)
    results = scan.get("results", [])
    confidence = scan.get("confidence", "high")

    high = [r for r in results if r.get("severity") == "HIGH"]
    medium = [r for r in results if r.get("severity") in ("MEDIUM", "LOW")]
    info = [r for r in results if r.get("severity") == "INFO"]

    # Header
    L.append(header)
    L.append("")

    # Badge row
    badges = [
        _gate_badge(score, bool(high)),
        _score_badge(score),
        _findings_badge(len(high), len(medium), len(info)),
    ]
    L.append("&nbsp;".join(badges))
    L.append("")

    # Metadata
    L.append(f"**Branch:** `{branch}` | **Confidence:** {confidence}")
    L.append("")

    # Clean result
    if not results:
        L.append(
            "> **No compatibility issues detected.** "
            "This branch is clear for the target environment."
        )
        L.append("")
        L.append("---")
        L.append(
            f'<sub><a href="{REPO_URL}">repofail</a>'
            f" scanned <code>{branch}</code></sub>"
        )
        return "\n".join(L)

    # Critical findings
    if high:
        L.append("#### Critical Issues")
        L.append("")
        for r in high:
            msg = r.get("message", "")
            reason = r.get("reason", "")
            ev = r.get("evidence", {})

            L.append(f"**{msg}**")
            L.append("")
            L.append(f"{reason}")
            L.append("")

            ev_text = _format_evidence(ev)
            if ev_text:
                L.append(ev_text)
                L.append("")

    # Warnings
    if medium:
        L.append("<details>")
        L.append(f"<summary><b>Warnings ({len(medium)})</b></summary>")
        L.append("")
        L.append("| Severity | Finding | Detail |")
        L.append("|:---------|:--------|:-------|")
        for r in medium:
            sev = r.get("severity", "MEDIUM")
            L.append(
                f"| {sev} | {r.get('message', '')} | {r.get('reason', '')} |"
            )
        L.append("")
        L.append("</details>")
        L.append("")

    # Info
    if info:
        L.append("<details>")
        L.append(f"<summary>Structural notes ({len(info)})</summary>")
        L.append("")
        L.append("| Finding | Detail |")
        L.append("|:--------|:-------|")
        for r in info:
            L.append(
                f"| {r.get('message', '')} | {r.get('reason', '')} |"
            )
        L.append("")
        L.append("</details>")
        L.append("")

    # Footer
    L.append("---")
    L.append(
        f'<sub><a href="{REPO_URL}">repofail</a>'
        f" scanned <code>{branch}</code>"
        " · deterministic runtime compatibility analysis</sub>"
    )

    return "\n".join(L)
