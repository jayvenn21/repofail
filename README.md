<p align="center">
  <img src="https://raw.githubusercontent.com/jayvenn21/repofail/main/docs/logo.png" width="65%" alt="repofail logo">
</p>

<p align="center">
  Deterministic runtime compatibility analyzer
</p>

<p align="center">
  <a href="https://github.com/jayvenn21/repofail/releases"><img src="https://img.shields.io/github/v/release/jayvenn21/repofail" alt="Release version"></a>
  <a href="https://pypi.org/project/repofail/"><img src="https://img.shields.io/pypi/pyversions/repofail" alt="Python"></a>
  <a href="https://pypi.org/project/repofail/"><img src="https://img.shields.io/pypi/dm/repofail" alt="Downloads"></a>
  <a href="https://github.com/jayvenn21/repofail/actions"><img src="https://img.shields.io/github/actions/workflow/status/jayvenn21/repofail/repofail.yml?branch=main" alt="CI"></a>
  <img src="https://img.shields.io/badge/runtime-validated-brightgreen" alt="Runtime">
  <img src="https://img.shields.io/badge/rules-20%2B-blue" alt="Rules">
  <a href="https://github.com/jayvenn21/repofail/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-MIT-lightgrey" alt="License"></a>
</p>

<p align="center">
  <strong>The static analyzer for runtime compatibility.</strong><br>
  Predict why a repository will fail on your machine before you run it.
</p>

<p align="center">
  <em>repofail answers one question: <strong>Will this repository actually run here?</strong><br>
  It inspects both the repo and your machine - then reports deterministic incompatibilities before you install anything.</em>
</p>

<p align="center">
  <a href="#why-this-exists">Why</a> ·
  <a href="#example-output">Example</a> ·
  <a href="#works-on">Works on</a> ·
  <a href="#install">Install</a> ·
  <a href="#usage">Usage</a> ·
  <a href="#rules">Rules</a> ·
  <a href="#ci-integration">CI</a> ·
  <a href="#contracts">Contracts</a> ·
  <a href="#faq">FAQ</a>
</p>

---

## Quickstart (30 seconds)

```bash
pip install repofail
cd /path/to/any/repo
repofail
```

You get a compatibility score and a list of deterministic blockers (Node version, Python range, CUDA, lock file, spec drift, etc.). No install of the repo’s dependencies. No cloud. No AI.

---

## Why This Exists

Most tools install dependencies.

Few tools tell you:

- Your Node version violates `engines.node`.
- Docker targets the wrong architecture.
- CUDA is hard-coded with no fallback.
- CI and local Python versions drifted.

repofail inspects both the repository and your machine - then reports deterministic incompatibilities before install or runtime.

---

## Works on

- **Python** - requires-python, PyTorch/CUDA, ABI wheels, spec drift
- **Node** - engines.node, native modules, lock files, EOL
- **Go** - go.mod version, CGO dependencies, OS build tags
- **Rust** - rust-version, system lib crates, target-specific deps
- **Docker** - base image, platform mismatch, CUDA
- **ML** - CUDA hard-coding, GPU memory, Apple Silicon wheels
- **Monorepos** - multi-language, subproject detection

Run it against any local clone.

---

## Example output

<p align="center">
  <img src="https://raw.githubusercontent.com/jayvenn21/repofail/main/docs/screenshots/nodefail.gif" width="850" alt="Node engine mismatch demo">
</p>

Deterministic spec violation detected - engines.node requires 22.x, host is 20.x.

---

## Case studies

| Scenario | Without repofail | With repofail |
|----------|------------------|----------------|
| **Node engine mismatch** | Clone → `npm install` → `EBADENGINE` → search, fix, retry | `repofail .` → "Node 22.x required, host is 20.x" + suggested fix in &lt;1s |
| **CUDA on laptop** | Clone → `pip install` → run → `RuntimeError: CUDA unavailable` | `repofail .` → "Hard-coded CUDA path, host has no GPU" before you run |
| **Spec drift (Python)** | CI passes, local fails; pyproject says 3.11, Docker uses 3.9 | `repofail .` → "Spec drift - 3 distinct Python targets" + where they differ |

Try the demos: [node engine](https://github.com/jayvenn21/repofail-demo-node-engine), [spec drift](https://github.com/jayvenn21/repofail-demo-spec-drift), [CUDA hardcoded](https://github.com/jayvenn21/repofail-demo-cuda-hardcoded).

---

## Install

**From PyPI (recommended)**

```bash
pip install repofail
```

**One-liner (curl)**

```bash
curl -sSL https://raw.githubusercontent.com/jayvenn21/repofail/main/install.sh | bash
```

**pipx (isolated CLI)**

```bash
pipx install repofail
```

**Homebrew** (formula: [jayvenn21/homebrew-tap](https://github.com/jayvenn21/homebrew-tap))

```bash
brew tap jayvenn21/tap
brew install jayvenn21/tap/repofail
```

**From source (development)**

```bash
git clone https://github.com/jayvenn21/repofail.git
cd repofail
pip install -e .
```

## Usage

```bash
# Scan
repofail                    # Scan current dir
repofail -p /path/to/repo   # Scan specific repo
repofail -j                 # JSON output (machine-readable)
repofail -m                 # Markdown output
repofail -v                 # Verbose: rule IDs and low-confidence hints
repofail --ci               # CI mode: exit 1 if HIGH rules fire
repofail --fail-on MEDIUM   # CI: fail on MEDIUM or higher (default: HIGH)
repofail -r                 # Save failure report when rules fire (opt-in telemetry)

# AI-powered explanations (requires REPOFAIL_API_KEY or Ollama)
repofail . --ai             # Plain English explanation + fix suggestions
repofail . --ai --model ollama/llama3   # Use local model (no data leaves your machine)
repofail . --ai --model claude-sonnet-4-20250514  # Use Anthropic

# Init
repofail init               # Interactive config generator
repofail init --yes         # Non-interactive (defaults)

# Rules
repofail -e list            # List all rules
repofail -e spec_drift      # Explain a rule

# Contracts
repofail gen .              # Generate env contract to stdout
repofail gen . -o contract.json
repofail check contract.json

# Fleet
repofail a /path            # Audit: scan all repos in directory
repofail a /path -j         # Audit with JSON output
repofail sim . -H host.json # Simulate: would this work on target host?
repofail s                  # Stats: local failure counts (from -r reports)
repofail s -j               # Stats with JSON output
```

## Exit codes

- **0** - No deterministic violations (or scan completed successfully)
- **1** - Violations detected (with `--ci`) or target host has issues (with `sim`)
- **2** - Invalid usage / bad input (e.g. not a directory, contract violation)

---

## CI integration

**Option A - Reusable action (comment on PR + fail CI)**

```yaml
name: repofail
on:
  pull_request:
    branches: [main, master]
jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: jayvenn21/repofail/.github/actions/repofail@main
        with:
          path: .
          fail_on: HIGH
          comment: 'true'
          upload_artifact: 'true'
          pr_number: ${{ github.event.pull_request.number }}
```

The action installs repofail, runs a compatibility check, comments the Markdown report on the PR, uploads the JSON artifact, and fails the job if violations meet the threshold.

**Option B - Inline (no comment)**

```yaml
- uses: actions/checkout@v4
- uses: actions/setup-python@v5
  with:
    python-version: "3.12"
- run: pip install repofail
- run: repofail --ci
```

Exits 1 if HIGH rules fire. Use `--fail-on MEDIUM` to be stricter.

**Option C - Lock + verify (enforcement)**

Pin the runtime once, then fail CI on drift:

```bash
repofail lock          # generates repofail.lock.json (python, node, arch, os, cuda, docker_base)
repofail verify        # exit 1 if host doesn't match lock
```

Commit `repofail.lock.json`. In CI, run `repofail verify` so builds only pass on the locked environment.

**Fleet compliance**

Scan many repos and get violations, most common drift, and risk clusters:

```bash
repofail fleet ~/org --policy org.policy.yaml
```

Policy YAML (optional): `fail_on: HIGH`, `max_repos: 500`, `max_depth: 4`. With `fail_on: HIGH`, exit code is 1 if any repo has a HIGH finding.

**Option D - GitHub App (zero config)**

Install the [repofail GitHub App](github-app/) on your repos and every PR gets an automatic compatibility comment - no workflow file needed.

```
## repofail · compatibility report

Compatibility score: 🔴 ███░░░░░░░ 32%

### Hard failures
❌ Hard-coded CUDA path, host has no GPU.
   Likely error: RuntimeError: CUDA unavailable

### Runtime risks
⚠️ Spec drift - 3 distinct Python targets across configs.
```

Self-host with Docker or Railway. See [`github-app/README.md`](github-app/README.md) for setup.

## Contracts

```bash
repofail gen . -o contract.json
repofail check contract.json
```

Versioned runtime expectations. Teams share contracts. CI checks drift. Generated contracts report the installed repofail version (from PyPI/Homebrew) so tooling stays traceable.

---

## AI-powered explanations

repofail is deterministic by default - fast AST rules, no hallucination. The `--ai` flag layers plain English explanations on top of the scan results using your own API key or a local model.

```bash
pip install repofail[ai]  # installs litellm

# Set your key (OpenAI, Anthropic, or skip for Ollama)
export REPOFAIL_API_KEY=sk-...

# Scan with AI explanation
repofail . --ai
```

**What the AI does:**
- Translates each finding into plain English a beginner can understand
- Explains what error you'll actually see if you try to run the repo
- Suggests specific fixes (commands, config changes, code edits)
- Gives an overall "will this work on my machine?" verdict

**What the AI does NOT do:**
- It never decides whether there's a problem - that's the deterministic scanner
- It never sees your source code - only the structured scan results (a few KB of JSON)
- Zero false positives from detection - the rules are the source of truth

**Supported providers:**

| Provider | Model example | Cost per scan | Setup |
|----------|--------------|---------------|-------|
| OpenAI | `gpt-4o-mini` (default) | ~$0.001 | `REPOFAIL_API_KEY=sk-...` |
| Anthropic | `claude-sonnet-4-20250514` | ~$0.001 | `REPOFAIL_API_KEY=sk-ant-...` |
| Ollama | `ollama/llama3` | $0.00 | No key needed, runs locally |

```bash
# Use a specific model
repofail . --ai --model claude-sonnet-4-20250514

# Fully local - no data leaves your machine
repofail . --ai --model ollama/llama3
```

> repofail works fully offline by default. The `--ai` flag adds AI-powered explanations using your own API key (OpenAI, Anthropic) or a local model via Ollama. No data is sent anywhere unless you opt in.

---

## Rules

| Tool | Reads Repo | Inspects Host | Predicts Failure | CI Enforceable |
|------|------------|---------------|------------------|----------------|
| pip | ✅ | ❌ | ❌ | ❌ |
| Docker | ✅ | ❌ | ❌ | ❌ |
| **repofail** | ✅ | ✅ | ✅ | ✅ |

**Deterministic rule coverage** - repofail includes checks across:

- **Spec violations** - Python requires-python, Node engines.node, Go go.mod, Rust rust-version
- **Architecture mismatches** - Apple Silicon vs amd64 Docker, Go/Rust OS build tags
- **Hardware constraints** - CUDA requirements, GPU memory
- **Toolchain gaps** - missing compilers, CGO, Rust system crates, node-gyp
- **Runtime drift** - CI vs Docker vs local inconsistencies
- **Environment shape** - multi-service RAM pressure, port collisions

See all rules: `repofail -e list` · Explain one: `repofail -e <rule_id>`

<details>
<summary>Rule reference</summary>

| Rule | Severity | When |
|------|----------|------|
| Torch CUDA mismatch | HIGH | Hard-coded CUDA, host has no GPU |
| Python version violation | HIGH | Host outside `requires-python` range |
| Go version mismatch | HIGH | go.mod go directive > host Go |
| Rust version mismatch | HIGH | Cargo.toml rust-version > host rustc |
| Spec drift | HIGH | pyproject vs Docker vs CI - inconsistent Python |
| Node engine mismatch | HIGH | package.json engines.node vs host |
| Lock file missing | HIGH | package.json has deps, no lock file |
| Go CGO no compiler | MEDIUM | CGO deps but no gcc/clang |
| Go OS build tags | MEDIUM | Build tags exclude current host OS |
| Rust target platform | MEDIUM | Target-specific deps for a different OS |
| Apple Silicon wheel mismatch | MEDIUM/HIGH | arm64 + x86-only packages or Docker amd64 |
| … | | `repofail -e list` |

</details>

<details>
<summary>Scoring model</summary>

**Compatibility Score** = `100 − Σ(weight × confidence × determinism)`

| Severity | Weight | Determinism |
|----------|--------|-------------|
| HIGH | 45 | 1.0 for spec violations |
| MEDIUM | 20 | 0.8–1.0 |
| LOW | 7 | 0.5–1.0 |
| INFO | 5 | structural only |

**Determinism scale:** `1.0` = guaranteed failure · `0.75` = high likelihood · `0.6` = probabilistic (spec drift) · `0.5` = structural risk

Score floors at 10%. When score ≤15% with HIGH rules: "- fatal deterministic violations present".

</details>

---

## Architecture

```
repofail/
  cli.py           # Typer CLI (scan, init, lock, verify, fleet, gen, check, sim)
  engine.py        # Rule runner
  init.py          # Interactive config generator
  scanner/         # Repo + host inspection (Python, Node, Go, Rust, Docker)
  rules/           # Deterministic rule implementations
  lock.py          # Runtime lock / verify
  fleet.py         # Audit, simulate, fleet scan
```

Extensible via `.repofail/rules.yaml` or `.repofail.yaml` (generated by `repofail init`).

---

## FAQ

**Does repofail install or run my project?**  
No. It only reads configs and (optionally) inspects Python/JS for patterns. No `pip install`, no `npm install`, no execution.

**Does it need the internet?**  
No. It runs fully offline. Host inspection uses local subprocesses (e.g. `node --version`).

**Why “deterministic”?**  
Same repo + same host → same result. No ML, no heuristics that change between runs. Rules are based on config and code.

**Can I add my own rules?**  
Yes. Put a `.repofail/rules.yaml` (or `repofail-rules.yaml`) in the repo and define conditions on `repo.*` and `host.*`. See `repofail -e list` for built-in rule IDs.

**What if my repo is clean?**  
You get a high score (e.g. 96–100%) and “No deterministic blockers detected.” repofail does not invent problems.

---

## How repofail is different

| Tool | What it answers | Overlap |
|------|----------------|---------|
| **CodeRabbit / Greptile** | "Is this PR good code?" (LLM review) | None - code quality, not runtime |
| **CodeQL / Snyk** | "Does this code have vulnerabilities?" | None - security, not compatibility |
| **pip / npm / Docker** | "Install these deps" | Finds problems *after* you hit the error |
| **go-runtime-compat** | "Will this Go code fail in a container?" | Go only |
| **repofail** | "Will this repo fail on **this machine** before you run it?" | **Cross-language, pre-execution, deterministic** |

repofail is the only tool that combines **repo scanning + host inspection + failure prediction** across Python, Node, Go, Rust, Docker, and CUDA - before you run anything.

---

## Roadmap

- [x] Python / Node / Docker / CUDA scanning
- [x] Go scanner (go.mod, CGO, build tags)
- [x] Rust scanner (rust-version, target platforms, system crates)
- [x] `repofail init` - interactive config generator
- [x] Runtime lock enforcement (`repofail lock` / `verify`)
- [x] Fleet compliance mode (`repofail fleet`)
- [x] AI-powered explanations (`--ai` flag, BYOK, Ollama support)
- [x] GitHub App - auto-comment on PRs with environment-specific warnings
- [ ] Java scanner (JNI, JVM version, native bindings)
- [ ] Web dashboard - paste a GitHub URL, get a report
- [ ] Community rule marketplace (`repofail-community-rules`)

---

## When not to use it

- **You need dependency resolution** - use pip, npm, poetry, etc. repofail does not install or resolve.
- **You need security scanning** - use Dependabot, Snyk, or similar. repofail is compatibility-only.
- **You want “AI suggested fixes”** - repofail gives deterministic, rule-based suggestions only.
- **You run only in one environment** - if every dev and CI use the same OS/runtime, the value is smaller (still useful for drift and contracts).

---

## Testing

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

**Quick checks:** `bash -n install.sh` (syntax). The GitHub Action runs on every PR in this repo (see [.github/workflows/repofail.yml](.github/workflows/repofail.yml)); to test the reusable action, use it in another repo’s workflow on a PR.

---

## License

MIT - see [LICENSE](LICENSE).
