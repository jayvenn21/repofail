# repofail - 30-second quickstart

## What it does

Answers one question: **Will this repository run on this machine?**

It does **not** install your project. It reads configs and your environment, then reports compatibility issues (Node version, Python range, CUDA, lock file, spec drift, etc.) with a single score and clear evidence.

## Install

```bash
pip install repofail
```

Or: `pipx install repofail` | [install.sh](https://raw.githubusercontent.com/jayvenn21/repofail/main/install.sh) | Homebrew (see README).

## Run

```bash
cd /path/to/any/repo
repofail
```

You get:

- A **compatibility score** (0–100%)
- **HARD FAILURES** (deterministic blockers) with evidence and suggested fixes
- Optional: **RUNTIME RISKS**, **STRUCTURAL PROFILE**

## CI

```bash
repofail --ci
```

Exits 1 if HIGH (or configured) severity violations are found. Use in GitHub Actions or any CI.

## Next

- `repofail -e list` - list all rules  
- `repofail -e spec_drift` - explain a rule  
- [README](https://github.com/jayvenn21/repofail#readme) - full docs, FAQ, when not to use
