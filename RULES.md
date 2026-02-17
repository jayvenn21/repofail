# repofail Rules

High-confidence incompatibility rules. Deterministic, no AI. Extensible via YAML.

## List rules

```bash
repofail --explain list
repofail --explain torch_cuda_mismatch
```

## The rules

### 1. torch_cuda_mismatch (HIGH)

**When:** Repo imports `torch.cuda` or uses `device="cuda"` but host has no NVIDIA GPU.

**Fix:** Run on a machine with CUDA, or use CPU-only PyTorch.

---

### 2. apple_silicon_wheels (MEDIUM/HIGH)

**When:** Host is macOS arm64 and repo depends on packages with x86-only wheels: `nvidia-cuda-*`, `cuda-python`, `horovod`, etc.

**Fix:** Use Rosetta, conda-forge, or verify ARM wheels exist.

---

### 3. python_version_mismatch (HIGH)

**When:** Repo's `requires-python` (pyproject.toml/setup.py) doesn't include host's Python version.

**Fix:** Install the required Python (pyenv, conda, asdf).

---

### 4. native_toolchain_missing (MEDIUM)

**When:** Repo has Node native modules (node-gyp) or Rust/Cargo, but host has no gcc/clang.

**Fix:** Install Xcode CLI tools (macOS) or `build-essential` (Linux).

---

### 5. gpu_memory_risk (LOW/MEDIUM)

**When:** Repo uses torch + diffusers/transformers and host RAM < 16 GB.

**Fix:** Use smaller models, add swap, or run on a machine with more RAM.

---

### 6. node_native_windows (MEDIUM)

**When:** Host is Windows and repo has Node native modules (node-gyp).

**Fix:** Use WSL, or install Visual Studio Build Tools.

---

### 7. missing_system_libs (MEDIUM)

**When:** Repo requires libGL (opencv) or ffmpeg but host doesn't have them.

**Fix:** Install libgl1-mesa-glx (Linux) or ffmpeg.

---

## YAML Rules (Step 3 — Extensible)

Add `.repofail/rules.yaml` or `repofail-rules.yaml` in your repo:

```yaml
- id: custom_cuda_check
  when:
    repo.uses_torch: true
    host.cuda_available: false
  severity: HIGH
  explanation: "Custom CUDA check for this project"
```

---

## Contributing rules

Rules are in `repofail/rules/`. Each rule is a module with:

1. `check(repo: RepoProfile, host: HostProfile) -> RuleResult | None`
2. Returns `None` if the rule doesn't apply
3. Returns `RuleResult` with `rule_id`, `severity`, `message`, `reason`, `host_summary`

Add metadata to `repofail/rules/registry.py` for `--explain`. Add the check to `repofail/engine.py`.

Keep rules deterministic. No network. No guessing.
