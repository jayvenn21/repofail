"""repofail GitHub App - auto-comment on PRs with compatibility reports.

Receives pull_request webhooks, clones the repo, runs repofail, and posts
a Markdown comment with the findings. Zero config for the end user - just
install the app on the repo.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, Request

from auth import get_installation_token
from comment import format_pr_comment

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("repofail-app")

app = FastAPI(title="repofail GitHub App")

WEBHOOK_SECRET = os.environ.get("GITHUB_WEBHOOK_SECRET", "")


def _verify_signature(payload: bytes, signature: str | None) -> bool:
    """Verify GitHub webhook HMAC-SHA256 signature."""
    if not WEBHOOK_SECRET:
        log.warning("GITHUB_WEBHOOK_SECRET not set - skipping signature verification")
        return True
    if not signature or not signature.startswith("sha256="):
        return False
    expected = "sha256=" + hmac.new(
        WEBHOOK_SECRET.encode(), payload, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


def _clone_repo(clone_url: str, ref: str, token: str) -> Path:
    """Shallow-clone repo at ref into a temp directory. Returns the path."""
    tmpdir = Path(tempfile.mkdtemp(prefix="repofail-"))
    auth_url = clone_url.replace("https://", f"https://x-access-token:{token}@")
    subprocess.run(
        ["git", "clone", "--depth=1", "--branch", ref, auth_url, str(tmpdir / "repo")],
        capture_output=True,
        timeout=120,
        check=True,
    )
    return tmpdir / "repo"


def _run_repofail(repo_path: Path) -> dict:
    """Run repofail on the cloned repo and return JSON results."""
    result = subprocess.run(
        ["repofail", "-p", str(repo_path), "-j"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    log.info(f"repofail exit={result.returncode} stdout_len={len(result.stdout)} stderr_len={len(result.stderr)}")
    if result.stderr:
        log.info(f"repofail stderr: {result.stderr[:500]}")
    import json
    try:
        return json.loads(result.stdout)
    except Exception:
        log.error(f"Failed to parse repofail output: {result.stdout[:500]}")
        return {"error": result.stderr or "repofail produced no output", "raw": result.stdout[:2000]}


def _post_comment(token: str, owner: str, repo: str, pr_number: int, body: str) -> None:
    """Post or update a comment on a PR via the GitHub API."""
    import httpx

    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json",
    }
    marker = "<!-- repofail-bot -->"
    body_with_marker = f"{marker}\n{body}"

    comments_url = f"https://api.github.com/repos/{owner}/{repo}/issues/{pr_number}/comments"
    resp = httpx.get(comments_url, headers=headers, params={"per_page": 100})
    log.info(f"List comments: {resp.status_code}")
    existing = None
    if resp.status_code == 200:
        for c in resp.json():
            if marker in (c.get("body") or ""):
                existing = c["id"]
                break

    if existing:
        update_url = f"https://api.github.com/repos/{owner}/{repo}/issues/comments/{existing}"
        r = httpx.patch(update_url, headers=headers, json={"body": body_with_marker})
        log.info(f"Update comment: {r.status_code} {r.text[:500]}")
    else:
        r = httpx.post(comments_url, headers=headers, json={"body": body_with_marker})
        log.info(f"Post comment: {r.status_code} {r.text[:500]}")
        if r.status_code >= 400:
            log.error(f"Failed to post comment: {r.status_code} {r.text}")


@app.get("/")
def root():
    return {"app": "repofail", "status": "running"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/webhook")
async def webhook(
    request: Request,
    x_github_event: str = Header(None, alias="X-GitHub-Event"),
    x_hub_signature_256: str = Header(None, alias="X-Hub-Signature-256"),
):
    payload = await request.body()

    if not _verify_signature(payload, x_hub_signature_256):
        raise HTTPException(status_code=401, detail="Invalid signature")

    if x_github_event != "pull_request":
        return {"status": "ignored", "event": x_github_event}

    import json
    data = json.loads(payload)
    action = data.get("action")

    if action not in ("opened", "synchronize", "reopened"):
        return {"status": "ignored", "action": action}

    pr = data["pull_request"]
    repo_data = data["repository"]
    installation_id = data.get("installation", {}).get("id")

    owner = repo_data["owner"]["login"]
    repo_name = repo_data["name"]
    pr_number = pr["number"]
    head_ref = pr["head"]["ref"]
    clone_url = repo_data["clone_url"]

    log.info(f"PR #{pr_number} {action} on {owner}/{repo_name} (branch: {head_ref})")

    if not installation_id:
        log.error("No installation_id in webhook payload")
        raise HTTPException(status_code=400, detail="Missing installation_id")

    try:
        log.info(f"Getting installation token for {installation_id}")
        token = get_installation_token(installation_id)
        log.info("Token acquired, cloning repo")
    except Exception as e:
        log.exception(f"Auth failed for installation {installation_id}")
        return {"status": "error", "detail": f"Auth failed: {e}"}

    repo_path = None
    try:
        repo_path = _clone_repo(clone_url, head_ref, token)
        log.info(f"Cloned to {repo_path}, running repofail")
        scan_results = _run_repofail(repo_path)
        log.info(f"Scan complete, posting comment")
        comment_body = format_pr_comment(scan_results, owner, repo_name, pr_number, head_ref)
        _post_comment(token, owner, repo_name, pr_number, comment_body)
        return {"status": "commented", "pr": pr_number}
    except subprocess.TimeoutExpired:
        log.error(f"Timeout scanning {owner}/{repo_name}#{pr_number}")
        return {"status": "timeout"}
    except Exception as e:
        log.exception(f"Error processing {owner}/{repo_name}#{pr_number}")
        return {"status": "error", "detail": str(e)}
    finally:
        if repo_path and repo_path.parent.exists():
            shutil.rmtree(repo_path.parent, ignore_errors=True)
