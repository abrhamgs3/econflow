# Contributing to EconFlow

Thank you for considering a contribution. EconFlow is an open-source project and
all contributions — bug reports, documentation improvements, and code patches —
are welcome.

---

## Code of Conduct

This project follows the [Contributor Covenant Code of Conduct](CODE_OF_CONDUCT.md).
By participating you agree to uphold it. Report unacceptable behaviour to
abrhamgs3@gmail.com.

---

## Ways to contribute

- **Report a bug** — open a [Bug Report](https://github.com/abrhamgs3/econflow/issues/new?template=bug_report.yml)
- **Request a feature** — open a [Feature Request](https://github.com/abrhamgs3/econflow/issues/new?template=feature_request.yml)
- **Fix a bug or add a feature** — fork, branch, and open a pull request
- **Improve documentation** — typos, examples, and clarifications are always welcome

---

## Development setup

```bash
git clone https://github.com/abrhamgs3/econflow.git
cd econflow
pip install -e ".[dev]"
```

Verify everything works:

```bash
pytest          # 100 tests should pass
ruff check src/ tests/
econflow doctor
```

---

## Branching model

| Branch | Purpose |
|---|---|
| `main` | Always releasable; protected |
| `dev` | Integration branch for next release |
| `feature/<name>` | Individual features or fixes |

Work against `dev` unless the change is a critical hotfix to `main`.

---

## Making a change

1. Open an issue describing the problem or proposal before starting.
2. Fork the repository and create a branch: `git checkout -b feature/my-change`.
3. Make your changes. Keep commits small and focused.
4. Add or update tests. The test suite must pass before review.
5. Run the linter: `ruff check src/ tests/` — fix all warnings.
6. Update `CHANGELOG.md` under `## [Unreleased]`.
7. Open a pull request against `dev` (or `main` for hotfixes).

---

## Tests

EconFlow uses `pytest`. All new code must be accompanied by tests.

```bash
pytest                  # run everything
pytest -x               # stop on first failure
pytest tests/unit/      # unit tests only (once populated)
pytest --tb=short -q    # compact output
```

Test files live in `tests/`. See `tests/conftest.py` for shared fixtures.

The `sample_panel` fixture provides a generic 10 × 10 balanced panel — use it
rather than creating paper-specific test data.

---

## Code style

EconFlow uses [ruff](https://docs.astral.sh/ruff/) for linting and formatting.
Configuration is in `pyproject.toml`. CI will reject PRs that fail the lint check.

```bash
ruff check src/ tests/      # lint
ruff check --fix src/ tests/ # auto-fix safe issues
```

Key conventions:
- Line length: 100 characters
- Python 3.10+ syntax
- Type hints on all public functions
- Google-style docstrings

---

## Scientific code

EconFlow separates **framework code** (infrastructure, CLI, provenance) from
**scientific code** (estimators, data processing). Contributions to the
scientific code are welcome but are held to a higher standard — changes must
not alter numerical output without explicit discussion and updated reference
outputs.

---

## Pull request checklist

Before submitting, confirm:

- [ ] Tests pass (`pytest`)
- [ ] Linter passes (`ruff check src/ tests/`)
- [ ] New behaviour is covered by tests
- [ ] `CHANGELOG.md` updated under `[Unreleased]`
- [ ] Docstrings added or updated for public API changes
- [ ] PR description explains *what* and *why*

---

## Release process (maintainers)

1. Move `[Unreleased]` entries to a new version block in `CHANGELOG.md`
2. Bump `version` in `pyproject.toml` and `src/econflow/__init__.py`
3. Commit: `git commit -m "release: vX.Y.Z"`
4. Tag: `git tag -a vX.Y.Z -m "EconFlow vX.Y.Z"`
5. Push: `git push origin main --tags`
6. Build: `python -m build`
7. Publish: `twine upload dist/*`
8. Create a GitHub release using the tag with the release notes from `docs/release_notes/`
