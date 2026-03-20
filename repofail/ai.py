"""AI explanation layer - deterministic scan results → plain English + fix suggestions.

Uses litellm for provider-agnostic LLM access (OpenAI, Anthropic, Ollama, etc.).
The AI never decides whether there's a problem - it only explains and suggests fixes
for what the deterministic scanner already found.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models import HostProfile, RepoProfile
    from .rules.base import RuleResult

SYSTEM_PROMPT = """\
You are repofail's AI assistant. You explain repository compatibility scan results \
in plain English so any developer - even a beginner - can understand what will break \
and how to fix it.

Rules:
- The deterministic scanner already identified the problems. Trust them completely.
- Never invent problems the scanner didn't find.
- Be specific: mention file paths, version numbers, and commands.
- For each finding, give a concrete fix (a command, a config change, or a code edit).
- Keep explanations concise but thorough. No filler.
- Use markdown formatting for readability.
- If there are no findings, say the repo looks compatible and congratulate them.\
"""

EXPLAIN_TEMPLATE = """\
## Scan Results

**Repo:** {repo_name} ({repo_path})
**Host:** {host_summary}

**Compatibility Score:** {score}%

### Findings ({count} total)

{findings_text}

---

Explain each finding in plain English. For each one:
1. What the problem is (so a beginner understands)
2. What will actually happen if they try to run it (the error they'll see)
3. How to fix it (specific command or code change)

Then give a brief overall summary: "Will this repo work on my machine?" - yes/no/maybe, \
and the most important thing to fix first.\
"""


def _resolve_model() -> str:
    """Resolve model from env, falling back to a sensible default."""
    return os.environ.get("REPOFAIL_MODEL", "gpt-4o-mini")


def _get_api_key() -> str | None:
    return os.environ.get("REPOFAIL_API_KEY")


def _format_finding(r: RuleResult) -> str:
    lines = [f"- **[{r.severity.value}] {r.rule_id}**: {r.message}"]
    lines.append(f"  Reason: {r.reason}")
    if r.evidence:
        ev_str = ", ".join(f"{k}={v}" for k, v in r.evidence.items() if v is not None)
        if ev_str:
            lines.append(f"  Evidence: {ev_str}")
    return "\n".join(lines)


def _build_prompt(
    repo: RepoProfile,
    host: HostProfile,
    results: list[RuleResult],
    score: int,
) -> str:
    host_parts = [f"{host.os} {host.arch}"]
    if host.python_version:
        host_parts.append(f"Python {host.python_version}")
    if host.node_version:
        host_parts.append(f"Node {host.node_version}")
    if host.go_version:
        host_parts.append(f"Go {host.go_version}")
    if host.rust_version:
        host_parts.append(f"Rust {host.rust_version}")
    if host.cuda_available:
        host_parts.append(f"CUDA {host.cuda_version or 'available'}")
    else:
        host_parts.append("no GPU")
    if host.ram_gb:
        host_parts.append(f"{host.ram_gb:.0f} GB RAM")

    findings_text = "\n\n".join(_format_finding(r) for r in results) if results else "(none)"

    return EXPLAIN_TEMPLATE.format(
        repo_name=repo.name or "unknown",
        repo_path=repo.path,
        host_summary=", ".join(host_parts),
        score=score,
        count=len(results),
        findings_text=findings_text,
    )


def explain(
    repo: RepoProfile,
    host: HostProfile,
    results: list[RuleResult],
    score: int,
    model: str | None = None,
) -> str:
    """Generate AI explanation of scan results. Raises ImportError if litellm not installed."""
    try:
        import litellm
    except ImportError:
        raise ImportError(
            "litellm is required for --explain. Install it:\n"
            "  pip install repofail[ai]\n"
            "or:\n"
            "  pip install litellm"
        )

    resolved_model = model or _resolve_model()
    api_key = _get_api_key()

    is_ollama = resolved_model.startswith("ollama")

    env_overrides = {}
    if api_key and not is_ollama:
        if "claude" in resolved_model or "anthropic" in resolved_model:
            env_overrides["ANTHROPIC_API_KEY"] = api_key
        else:
            env_overrides["OPENAI_API_KEY"] = api_key

    old_env = {}
    for k, v in env_overrides.items():
        old_env[k] = os.environ.get(k)
        os.environ[k] = v

    try:
        user_prompt = _build_prompt(repo, host, results, score)

        response = litellm.completion(
            model=resolved_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
            max_tokens=2000,
        )
        return response.choices[0].message.content
    finally:
        for k, v in old_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def check_ai_available() -> tuple[bool, str]:
    """Check if AI explanation is available. Returns (available, reason)."""
    try:
        import litellm  # noqa: F401
    except ImportError:
        return False, "litellm not installed (pip install repofail[ai])"

    model = _resolve_model()
    is_ollama = model.startswith("ollama")

    if not is_ollama and not _get_api_key():
        return False, (
            "No API key found. Set REPOFAIL_API_KEY or use a local model:\n"
            "  export REPOFAIL_API_KEY=sk-...\n"
            "  export REPOFAIL_MODEL=ollama/llama3  # for local"
        )

    return True, f"Using model: {model}"
