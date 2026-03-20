# repofail GitHub App

A GitHub App that auto-comments on PRs with deterministic runtime compatibility reports. Zero config for end users - install the app, and every PR gets a compatibility check.

## What it does

When a PR is opened or updated:

1. Receives the `pull_request` webhook
2. Shallow-clones the repo at the PR branch
3. Runs `repofail` (deterministic scan - no LLM, no guessing)
4. Posts a Markdown comment on the PR with findings
5. Updates the same comment on subsequent pushes (no spam)

## PR comment example

```
## repofail · compatibility report

**Compatibility score:** 🔴 ███░░░░░░░ **32%**
**Confidence:** high
**Branch:** `feature/add-gpu-training`

### Hard failures

❌ **Hard-coded CUDA path, host has no GPU.**
  - torch.cuda.is_available() at line 45, host has no NVIDIA GPU.
  - Likely error: `RuntimeError: CUDA unavailable`

### Runtime risks

⚠️ Spec drift - 3 distinct Python targets across configs.
  - pyproject.toml requires >=3.11, Dockerfile uses 3.9, CI uses 3.10.

---
**Summary:** 1 hard failure · 1 runtime risk
```

## Self-hosting

### 1. Register a GitHub App

Go to **GitHub → Settings → Developer settings → GitHub Apps → New GitHub App**

- **Name:** `repofail` (or your own name)
- **Homepage URL:** `https://github.com/jayvenn21/repofail`
- **Webhook URL:** `https://your-deploy-url.com/webhook`
- **Webhook secret:** generate one (`openssl rand -hex 32`)
- **Permissions:**
  - Repository contents: **Read**
  - Pull requests: **Read & Write**
  - Metadata: **Read**
- **Subscribe to events:** Pull request
- **Where can this GitHub App be installed?** Any account

After creation:
- Note the **App ID**
- Generate and download a **private key** (.pem file)

### 2. Deploy

#### Docker (recommended)

```bash
cd github-app

docker build -t repofail-app .

docker run -d \
  -p 8000:8000 \
  -e GITHUB_APP_ID=123456 \
  -e GITHUB_PRIVATE_KEY_PATH=/app/private-key.pem \
  -e GITHUB_WEBHOOK_SECRET=your-secret \
  -v /path/to/private-key.pem:/app/private-key.pem:ro \
  repofail-app
```

#### Railway / Fly.io / Render

Set these environment variables:

| Variable | Required | Description |
|----------|----------|-------------|
| `GITHUB_APP_ID` | Yes | Your GitHub App ID |
| `GITHUB_PRIVATE_KEY` | Yes* | PEM key contents (with `\n` for newlines) |
| `GITHUB_PRIVATE_KEY_PATH` | Yes* | Or path to .pem file |
| `GITHUB_WEBHOOK_SECRET` | Recommended | Webhook HMAC secret |

*One of `GITHUB_PRIVATE_KEY` or `GITHUB_PRIVATE_KEY_PATH` is required.

#### Railway one-click

```bash
railway login
railway init
railway up
```

Set env vars in the Railway dashboard.

### 3. Install on repos

Go to your GitHub App's page → **Install** → select repositories.

Every PR on those repos will now get automatic repofail reports.

## Architecture

```
GitHub (PR event)
    │
    ▼ webhook POST
┌──────────┐
│  FastAPI  │ ← verifies HMAC signature
│  server   │ ← exchanges JWT for installation token
└────┬─────┘
     │
     ▼ shallow clone at PR branch
┌──────────┐
│ repofail  │ ← deterministic scan (AST rules, no LLM)
│  scanner  │ ← runs in ~1-2 seconds
└────┬─────┘
     │
     ▼ posts/updates Markdown comment
┌──────────┐
│ GitHub PR │ ← compatibility report with score, findings, fixes
└──────────┘
```

## Development

```bash
cd github-app
pip install -r requirements.txt

# Set env vars (see .env.example)
cp .env.example .env

# Run locally
uvicorn app:app --reload --port 8000

# Expose via ngrok for testing
ngrok http 8000
```

Then set your GitHub App's webhook URL to your ngrok URL + `/webhook`.

## Permissions (minimal)

The app only requests:
- **Contents: Read** - to clone the repo
- **Pull requests: Write** - to post comments
- **Metadata: Read** - required by GitHub

It does not request access to code review, issues, workflows, or anything else.
