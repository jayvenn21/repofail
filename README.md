# repofail

**Pre-flight environment check for repos.** Scans the repo (and host) and reports version mismatches, structure risks, and resource hints so you know what might break before you run the app.

- **Offline** — no calls home
- **Structured** — JSON for CI and scripts
- **Scored** — single readiness score (e.g. 85%) plus a short list of "be aware" items
- **Extensible** — rules and contracts so you can add checks without changing core logic

**When to run it**

- After clone, before `make install` / `docker compose up`
- In CI, to fail or warn when the repo's expected environment doesn't match the runner
- When debugging "works on my machine" — see Python/Node/Docker/RAM notes in one place

## Install

```bash
pip install -e .
```

## Quick start

```bash
repofail                    # From repo root
repofail --json             # Machine-readable
repofail --ci               # CI (exit code from score / severity)
```

## Example output

When issues are found, output is grouped by severity:

```
┌──────────────────────────────────────────────────────────────────────┐
 repofail · environment risk
────────────────────────────────────────────────────────────────────────
 Score    39%  (1 high)
 1 deterministic incompatibility(ies) detected.
────────────────────────────────────────────────────────────────────────
 HARD FAILURES
  ● Node engine constraint violated.
  package.json requires: node 22.x
  Host: node v20.12.2
  This may cause install or runtime breakage.
────────────────────────────────────────────────────────────────────────
 Run with --json for machine output  ·  --ci for exit codes
└──────────────────────────────────────────────────────────────────────┘
```

Clean repos get high scores with restraint — no invented problems:

```
 Score    96%  (confidence: low)
 No high-confidence incompatibilities detected.
```

**Real examples:**
- **AutoGPT** → Node 22.x required, host has v20 → 39%, HIGH
- **browser-use** → Docker targets amd64 on Apple Silicon → 48%, HIGH
- **chopchop** → No strong risks → 96%, low confidence

**Not:** a linter, a security scanner, or a replacement for your runtime. **Is:** a deterministic runtime compatibility analyzer that shows evidence, not guesses.

## Rule categories

Rules are tagged for scalability and filtering:

| Category | Examples |
|----------|----------|
| `spec_violation` | Python version outside range, torchao/torch mismatch |
| `hardware_incompatibility` | CUDA required, low RAM, MLX scaling |
| `toolchain_missing` | No compiler, Rust, node-gyp on Windows |
| `runtime_environment` | Port collision, Docker-only, multi-service RAM |
| `architecture_mismatch` | Apple Silicon x86-only wheels |

Output in `--json` includes `category` per result.

## Scoring model

**Success probability** (0–100%) is deterministic:

- Start at 100
- Subtract: **45** per HIGH, **20** per MEDIUM, **7** per LOW, **5** per INFO
- Confidence multiplier: high 1.0, medium 0.75, low 0.5
- Clamp to 0–100

Example: 1 HIGH → 55%. 2 HIGH → 10%. 5 INFO → 75%.

**Confidence** (rule-driven, defensible):

| Level    | Meaning                                      | Example                                  |
|----------|----------------------------------------------|------------------------------------------|
| **High**   | Deterministic spec violation, hardcoded mismatch | `engines.node` violates, CUDA hardcoded  |
| **Medium** | Structural inference                         | Monorepo, multiple subprojects           |
| **Low**    | Heuristic, incomplete signals                | Structural guess from layout             |

Output in `--json` includes `confidence` and `low_confidence_rules` when relevant.

## Repo name resolution

`repo.name` is derived in order of preference:

1. Root `pyproject.toml` `[project]` name
2. Root `Cargo.toml` `[package]` name
3. Directory name (folder)
4. Root `package.json` name, unless generic (`my-*`, `template`, etc.)

Generic names like `my-t3-app` are skipped so the folder name (e.g. `AutoGPT`) is used instead.

## Commands

| Command | What it does |
|---------|--------------|
| `repofail` | Scan current dir for incompatibilities |
| `repofail .` or `repofail -p /path` | Scan a specific repo |
| `repofail -j` | JSON output (for piping or saving host profile) |
| `repofail -m` | Markdown output |
| `repofail --ci` | CI mode: exit 1 if HIGH rules fire |
| `repofail gen [path]` | Generate env contract from repo |
| `repofail gen . -o contract.json` | Write contract to file |
| `repofail check <file>` | Validate current host against a contract |
| `repofail a [path]` | Audit: scan all repos in a directory |
| `repofail sim [path] -H <file>` | Simulate: would this repo work on target host? |
| `repofail s` | Stats: local failure counts from opt-in reports |
| `repofail -e list` | List all rules |
| `repofail -e <rule_id>` | Explain a specific rule |
| `repofail -v` / `--verbose` | Include rule IDs and confidence hints |
| `repofail -r` | Save failure report when rules fire (opt-in telemetry) |

**Sim** needs a host JSON: run `repofail -j`, save the `host` section to a file, then `repofail sim . -H that-file.json`.

## Usage

```bash
repofail                    # Scan current dir
repofail .                  # Same
repofail -p /path/to/repo   # Scan specific repo
repofail -j                 # JSON output
repofail --ci               # CI mode
repofail gen .              # Generate env contract
repofail gen . -o contract.json
repofail check contract.json
repofail a .                # Audit current dir (or repofail a /path/to/repos)
repofail sim . -H host.json # Simulate on target (create host.json from repofail -j)
repofail -e list            # List rules
repofail -e torch_cuda_mismatch
repofail -r                 # Save report when rules fire
repofail s                  # Stats
```

Run `python -m repofail.cli` if you haven't installed.

## What It Does

**Rules (extensible via `.repofail/rules.yaml`):**

| Rule | Severity | When |
|------|----------|------|
| **Torch CUDA mismatch** | HIGH | Hard-coded CUDA, host has no GPU |
| **Python version violation** | HIGH | Host outside `requires-python` range |
| **Python EOL** | HIGH | requires-python pins to 3.7 or 3.8 (EOL) |
| **ABI wheel mismatch** | HIGH | arm64 + Python 3.12 + bitsandbytes/torchvision/etc |
| **Apple Silicon wheel mismatch** | MEDIUM/HIGH | arm64 macOS + x86-only packages, Docker amd64 |
| **Node engine mismatch** | HIGH | package.json engines.node vs host |
| **Node EOL** | HIGH | engines.node requires Node 14 or 16 (EOL) |
| **Lock file missing** | HIGH | package.json has deps, no package-lock.json or yarn.lock |
| **Native toolchain missing** | HIGH (Cargo) / MEDIUM (Node) | Native build, no compiler |
| **Port collision** | HIGH | docker-compose port already in use |
| **Docker-only dev** | HIGH | Dockerfile + devcontainer, no native install path |
| **GPU memory risk** | LOW/MEDIUM | Large-model frameworks, low RAM |
| **Node native on Windows** | MEDIUM | node-gyp on Windows |
| **Missing system libs** | MEDIUM | libGL, ffmpeg not detected |
| **Python minor mismatch** | INFO | Minor version drift (3.11 vs 3.12) |
| **Multiple Python subprojects** | INFO | Monorepo with 2+ Python packages |
| **Mixed Python + Node** | INFO | Backend + frontend in same repo |
| **Docker vs host Python** | INFO | Dockerfile Python ≠ host |
| **Low RAM multi-service** | INFO | Multi-service repo, &lt;16 GB RAM |

Each result includes **evidence** (file:line, host version, etc.) for auditability. JSON output: `results[].evidence`.

## Architecture

```
repofail/
  cli.py
  engine.py
  contract.py
  telemetry.py
  models.py
  scanner/
    repo.py      # Repo scanning
    host.py      # Host inspection (OS, arch, CUDA, Python, Node, Rust, compiler, RAM)
    parsers.py
    ast_scan.py
  rules/
    torch_cuda.py
    python_version.py
    python_eol.py
    abi_wheel_mismatch.py
    node_engine.py
    node_eol.py
    lock_file_missing.py
    apple_silicon.py
    native_toolchain.py
    gpu_memory.py
    node_windows.py
    system_libs.py
    yaml_loader.py   # .repofail/rules.yaml
  fleet.py           # audit, simulate
```

Extensible: add `.repofail/rules.yaml` or `repofail-rules.yaml` for custom rules.

## Stage 5 — Fleet / Enterprise

```bash
repofail a /path/to/monorepo         # Scan all repos
repofail sim . -H prod-host.json     # Pre-deploy: would this work on prod?
```

Fleet-wide validation. Pre-deployment simulation against a target host profile. Export `repofail --json` and use the host section as `prod-host.json`.

## Stage 4 — Failure Telemetry (opt-in, local)

```bash
repofail --report        # Save failure report when rules fire
repofail s               # View local failure stats
```

Reports saved to `~/.repofail/reports/`. No cloud. No API. Your data stays local. Aggregates: by rule, by host (os + arch + cuda).

## Stage 3 — Environment Contracts

```bash
repofail gen .           # Print contract to stdout
repofail gen . -o repofail-contract.json
repofail check repofail-contract.json
```

Versioned runtime expectations. Teams share contracts. CI checks drift.

## Stage 2 — CI Guardrail

```yaml
# .github/workflows/repofail.yml
- run: repofail --ci
```

Exits 1 if HIGH rules fire. Use `--fail-on MEDIUM` to be stricter.

```
repofail --ci
 Score    39%  (1 high)
 1 deterministic incompatibility(ies) detected.
 HARD FAILURES
  ● Node engine constraint violated.
 Exit code: 1
```

## Runs anywhere

repofail is designed to run on **any machine, any repo, any scale**:

| Aspect | How |
|--------|-----|
| **OS** | macOS, Linux, Windows — uses `pathlib`, `platform`, no hardcoded paths |
| **Python** | 3.10+ — standard library + typer, pyyaml, tomli |
| **Scale** | AST scan capped at 100 Python files per repo; audit iterates dirs; no full-tree parse |
| **Network** | Zero — runs fully offline, no API keys |
| **Install** | `pip install -e .` or `pip install repofail` (when on PyPI) |
| **CI** | GitHub Actions, GitLab, etc. — tested on ubuntu, macos, windows |

**Graceful degradation:** On Windows, RAM detection returns `None` (GPU memory rule may skip). CUDA, compiler, Node, Rust detection use `shutil.which` and subprocess — missing tools are handled safely.

**Large repos:** Scanning skips `.git`, `venv`, `node_modules`, etc. and limits Python file count. For huge monorepos, use `repofail a /path` to audit subdirs.

## Testing

```bash
pip install pytest
pytest tests/ -v
```
