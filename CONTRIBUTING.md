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
pytest          # 371 tests should pass
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

## Adding a data connector

Data connectors live in `src/econflow/ingestion/connectors/`. Each connector
is a class that inherits from `AbstractConnector` and implements five methods:

| Method | Contract |
|--------|----------|
| `connect()` | Verify the source is reachable. Raise `ConnectorError` on failure. |
| `download(*, force=False)` | Fetch data. Return the path to the cached CSV. |
| `validate(path)` | Run `DataValidator` checks. Return `DataValidationReport`. |
| `metadata()` | Return the `DatasetMetadata` from the last `download()` call. |
| `cache_key()` | Return a 64-char SHA-256 hex derived from `_make_cache_key()`. |

Register the connector with a single decorator:

```python
from econflow.ingestion.registry import register
from econflow.ingestion.base import AbstractConnector

@register("my_source", label="My Data Source", status="implemented")
class MySourceConnector(AbstractConnector):
    ...
```

Then add the import to `src/econflow/ingestion/connectors/__init__.py`.
No other code changes are required — the connector will appear in
`econflow info` and be available via `get_connector("my_source")`.

See `docs/architecture/DATA_ECOSYSTEM.md` for the full design rationale and
`connectors/world_bank.py` for a complete reference implementation.

**Testing requirements for new connectors:**
- `tests/unit/test_<source>_connector.py` — all five methods, constructor
  validation, `cache_key()` determinism
- `tests/integration/test_<source>_connector.py` — full `fetch()` end-to-end,
  with and without `CacheManager`, marked `@pytest.mark.network` if it needs
  live internet access

---

## Shared CLI utilities

CLI command modules share helpers from `src/econflow/commands/_shared.py`:

| Symbol | Use it for |
|--------|-----------|
| `STATUS_ICONS` | Rich-markup status indicators (pass ✔ / warn ⚠ / fail ✘ / skip – / info ℹ) |
| `deep_get(data, *keys)` | Safe navigation of nested dicts |
| `load_yaml_safe(path)` | YAML loading with structured error return |

Import from `_shared` rather than duplicating these in command modules.

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
