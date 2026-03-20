"""GitHub App authentication - JWT signing and installation token exchange.

Flow:
1. Sign a JWT with the App's private key
2. Exchange it for a short-lived installation access token
3. Use that token for API calls (clone, comment)
"""

from __future__ import annotations

import base64
import logging
import os
import re
import time

import httpx
import jwt

log = logging.getLogger("repofail-app")

APP_ID = os.environ.get("GITHUB_APP_ID", "")
PRIVATE_KEY = os.environ.get("GITHUB_PRIVATE_KEY", "")
PRIVATE_KEY_PATH = os.environ.get("GITHUB_PRIVATE_KEY_PATH", "")


def _normalize_pem(raw: str) -> str:
    """Reconstruct a valid PEM from a potentially mangled env var value."""
    key = raw.strip()
    key = key.replace("\\n", "\n").replace("\\r", "")

    # If it already looks like valid multi-line PEM, return as-is
    lines = key.split("\n")
    if len(lines) > 3 and lines[0].startswith("-----BEGIN"):
        return key if key.endswith("\n") else key + "\n"

    # Strip all PEM headers/footers and whitespace, then reconstruct
    body = re.sub(r"-----[A-Z ]+-----", "", key)
    body = re.sub(r"\s+", "", body)

    # Validate it's valid base64
    try:
        base64.b64decode(body)
    except Exception:
        log.error(f"PEM body is not valid base64 (len={len(body)}, first 20 chars: {body[:20]})")
        raise ValueError("Invalid PEM key - base64 decode failed")

    pem_lines = [body[i:i+64] for i in range(0, len(body), 64)]
    return (
        "-----BEGIN RSA PRIVATE KEY-----\n"
        + "\n".join(pem_lines)
        + "\n-----END RSA PRIVATE KEY-----\n"
    )


def _get_private_key() -> str:
    if PRIVATE_KEY:
        key = _normalize_pem(PRIVATE_KEY)
        log.info(f"PEM key loaded from env var (len={len(key)}, lines={key.count(chr(10))})")
        return key
    if PRIVATE_KEY_PATH and os.path.isfile(PRIVATE_KEY_PATH):
        key = open(PRIVATE_KEY_PATH).read()
        log.info(f"PEM key loaded from file {PRIVATE_KEY_PATH}")
        return key
    raise RuntimeError(
        "GitHub App private key not configured. "
        "Set GITHUB_PRIVATE_KEY or GITHUB_PRIVATE_KEY_PATH."
    )


def _create_jwt() -> str:
    """Create a JWT signed with the App's private key (valid 10 minutes)."""
    if not APP_ID:
        raise RuntimeError("GITHUB_APP_ID not set.")
    now = int(time.time())
    payload = {
        "iat": now - 60,
        "exp": now + (10 * 60),
        "iss": APP_ID,
    }
    return jwt.encode(payload, _get_private_key(), algorithm="RS256")


def get_installation_token(installation_id: int) -> str:
    """Exchange JWT for an installation access token."""
    app_jwt = _create_jwt()
    resp = httpx.post(
        f"https://api.github.com/app/installations/{installation_id}/access_tokens",
        headers={
            "Authorization": f"Bearer {app_jwt}",
            "Accept": "application/vnd.github+json",
        },
    )
    resp.raise_for_status()
    return resp.json()["token"]
