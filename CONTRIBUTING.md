# Contributing

repofail is opinionated and deterministic.

We welcome:

- New deterministic rules
- Improvements to host inspection
- Clearer error evidence
- Performance improvements

We do NOT accept:

- Heuristic guesses
- AI-based predictions
- Cloud integrations
- Non-deterministic scoring

---

## Release pipeline (maintainers)

Version is the source of truth in `pyproject.toml`. GitHub Releases and PyPI must stay aligned.

1. **Bump version** in `pyproject.toml` (e.g. `0.2.7`).
2. **Commit and push**: `git add pyproject.toml && git commit -m "Release 0.2.7" && git push`
3. **Create and push tag**: `git tag v0.2.7 && git push origin v0.2.7`
4. **Create GitHub Release**: GitHub → Releases → Create new release → choose tag `v0.2.7` → Publish.  
   The **Publish to PyPI** workflow runs only when a release is *published* (not on tag push), and uploads the built package to PyPI.

README uses `docs/logo.png` (relative) so the logo renders on PyPI when the sdist is built from the same tree.
