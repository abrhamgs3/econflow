# Next Session Work Plan

**Date:** 2026-06-26  
**Objective:** Ship EconFlow v0.1.0 and begin paper migration. No new features.  
**Estimated total:** 4.5 hours

---

## Pre-session state

- HEAD: `f061af0` (docs: rewrite getting_started tutorial)
- 1 commit unpushed: `f061af0`
- Git index: corrupted — files appear simultaneously as staged-for-deletion
  and untracked. Working tree is intact. HEAD is correct.
- CI: was failing (ruff) — fix committed but not yet verified against latest push
- `dist/` wheel: rebuilt with correct author, not yet committed
- CITATION.cff: ORCID and affiliation are placeholders

---

## Task 0 — Fix git index [10 min]

**Must be done first. Everything else is blocked until git is clean.**

The index is in a split state: the staging area has deleted all tracked files,
but the working tree still has them all. `git reset --hard HEAD` restores both
the index and working tree to match HEAD (`f061af0`).

```
cd "C:\Users\Lenovo\Desktop\Courses\EconWithAi\AI and Productivity\econflow"
git reset --hard HEAD
git status
```

Expected result: `nothing to commit, working tree clean`

If `git reset` fails due to `objects/maintenance.lock`: open Task Manager,
end any `git.exe` or `vscode` processes, then retry.

**Verification:** `git log --oneline -3` should show `f061af0` at top and
`git status` should be clean.

---

## Task 1 — Push pending commit [10 min]

One commit is not yet on GitHub: `f061af0 docs: rewrite getting_started tutorial`.

```
git push origin main
```

Then add the journal and work plan (written at end of 2026-06-25 session):

```
git add docs/development/2026-06-25.md docs/development/NEXT_SESSION.md docs/development/README.md
git commit -m "docs: add development journal 2026-06-25 and next session plan"
git push origin main
```

**Verification:** `https://github.com/abrhamgs3/econflow/commits/main` shows
`f061af0` and the journal commit at the top.

---

## Task 2 — Verify GitHub Actions [20 min]

Open `https://github.com/abrhamgs3/econflow/actions` and confirm:

- `CI / pytest — Python 3.10` ✅
- `CI / pytest — Python 3.11` ✅
- `CI / pytest — Python 3.12` ✅
- `CI / ruff lint` ✅

If any check is red, read the log and fix immediately before proceeding.
Previous failures were: null bytes, ruff version drift, missing pyarrow.
All three are fixed in committed code. A new failure indicates a regression.

**Do not proceed to Task 3 until all four checks are green.**

---

## Task 3 — Finish repository cleanup [45 min]

### 3a — Resolve dist/ tracking [15 min]

`dist/econflow-0.1.0-py3-none-any.whl` and `dist/econflow-0.1.0.tar.gz` are
currently tracked in git and were rebuilt last session. Decision required:

**Option A (recommended):** Add `dist/` to `.gitignore`, remove from git tracking.
Artifacts are built at release time, not committed.

```
echo "dist/" >> .gitignore
git rm -r --cached dist/
git add .gitignore
git commit -m "chore: stop tracking dist/ artifacts in git"
```

**Option B:** Keep tracking dist/. Simpler now, creates binary diff noise on
every version bump.

### 3b — Resolve cli_scaffold/ [15 min]

`src/econflow/cli_scaffold/` is excluded from the wheel and from ruff but
still present in the repository. Decision required:

**Option A (recommended):** Delete it. It is not imported by production code.
Its commands are placeholders that duplicate functionality in `cli.py`.

```
git rm -r src/econflow/cli_scaffold/
git commit -m "chore: remove cli_scaffold placeholder (not part of public API)"
```

**Option B:** Keep it as a development scaffold, document its status in a
comment in `__init__.py`.

### 3c — Fill CITATION.cff [15 min]

Replace the two placeholder fields:

```yaml
orcid: "https://orcid.org/0000-0000-0000-0000"  # replace with your ORCID
affiliation: ""  # replace with your institution
```

Register at `https://orcid.org` if not already registered (takes 5 minutes).
Add institution name. Repeat in both `authors` and `preferred-citation` blocks.

```
git add CITATION.cff
git commit -m "docs: add ORCID and affiliation to CITATION.cff"
```

---

## Task 4 — Final release verification [20 min]

With git clean and CI green, run the full health check:

```
git status                          # must be clean
pytest tests/ -q                    # must be 100 passed
python3 -m ruff check src/ tests/   # must be 0 errors
python3 -c "import econflow; print(econflow.__version__)"  # must be 0.1.0
```

Then create and push the v0.1.0 release tag:

```
git tag -a v0.1.0 -m "EconFlow v0.1.0 — first public release"
git push origin v0.1.0
```

Create a GitHub Release at `https://github.com/abrhamgs3/econflow/releases/new`:
- Tag: `v0.1.0`
- Title: `EconFlow v0.1.0`
- Body: paste contents of `docs/release_notes/v0.1.0.md`
- Attach: `dist/econflow-0.1.0-py3-none-any.whl` and `dist/econflow-0.1.0.tar.gz`
  (if dist/ was not removed in Task 3a; otherwise build first with `python -m build`)

**EconFlow is done when this task is complete.**

---

## Task 5 — Return to the AI & Productivity paper [30 min]

Switch context to the AI & Productivity repository.

### 5a — Review current paper state [15 min]

```
cd "C:\Users\Lenovo\Desktop\Courses\EconWithAi\AI and Productivity"
git log --oneline -5
git status
pytest tests/ -q
```

Read `FORENSIC_REPORT_ai_index_levels_fe.md` and the latest referee reports
(`Referee_Reports_v13.md`) to re-establish which scientific questions remain
open.

### 5b — Identify migration entry point [15 min]

The paper currently runs via `run_pipeline.py` using the `ai_productivity`
package. The migration plan (in `docs/development/MIGRATION_PLAN.md` of the
EconFlow repo) specifies a phased approach. Identify the lowest-risk first step:

- Confirm which pipeline stages are already equivalent between `ai_productivity`
  and `econflow` (ingestion, validation, basic FE estimation)
- Confirm which stages are NOT yet in EconFlow (AI index construction,
  TFP computation, Driscoll-Kraay SE, falsification suite)
- Choose the first stage to migrate based on: lowest risk, most value, least
  paper-specific logic

---

## Task 6 — Begin migration: make pipeline config-driven [1.5 hours]

This is the highest-value technical task and the prerequisite for the
`getting_started` tutorial being end-to-end runnable (T1 in the journal).

**Current state:** `src/econflow/pipeline.py` hardcodes column names
(`country`, `year`, specific variable names) inherited from the AI & Productivity
research config.

**Target state:** Pipeline reads `entity_col`, `time_col`, `dependent`, and
`regressors` from `config.yaml`. Any CSV with any column names works.

### 6a — Audit hardcoded column references [20 min]

```
grep -rn "country\|\"year\"\|ai_index\|tfp_growth" src/econflow/ \
  --include="*.py" | grep -v "docstring\|#\|test"
```

List every hardcoded column assumption in production code.

### 6b — Add config fields and update pipeline [40 min]

In `src/econflow/core/config.py`: add `entity_col: str`, `time_col: str`,
`dependent: str`, `regressors: list[str]` to the config model.

In `src/econflow/pipeline.py`: replace all hardcoded column names with
`config.entity_col`, `config.time_col`, etc.

In `src/econflow/data/validators.py`: replace `REQUIRED_COLUMNS` hardcoded
list with the config-driven column set.

### 6c — Verify getting_started works end-to-end [30 min]

```
econflow run \
  --config  examples/getting_started/config/config.yaml \
  --models  examples/getting_started/config/models.yaml \
  --outputs examples/getting_started/config/outputs.yaml
```

Output table must match `examples/getting_started/expected_outputs/table_fe_investment.csv`
within the tolerance specified in `expected_outputs/README.md`.

Then verify the AI & Productivity config still works (no regression):

```
econflow run \
  --config  examples/ai_productivity_paper/config/config.yaml \
  --models  examples/ai_productivity_paper/config/models.yaml \
  --outputs examples/ai_productivity_paper/config/outputs.yaml
```

### 6d — Add regression test [20 min]

Create `tests/integration/test_getting_started.py`. Gate behind
`ECONFLOW_RUN_LIVE_REGRESSION=1`. Assert coefficient values match expected
within tolerance bounds from `expected_outputs/README.md`.

---

## Definition of Done

The session is complete when:

- [ ] `git status` is clean
- [ ] All 4 GitHub Actions checks are green
- [ ] `v0.1.0` tag exists on GitHub
- [ ] GitHub Release created with release notes attached
- [ ] `econflow run` works against `examples/getting_started/`
- [ ] 100 tests pass + integration test added
- [ ] Paper migration entry point identified and documented

---

## If Time Runs Short

Cut in this order:

1. Skip Task 6d (integration test) — document as T6 in the journal
2. Skip Task 6c verification against AI & Productivity config — test manually
3. Defer Task 6b to next session — stop after audit (6a) and document findings
4. Do not skip Tasks 0–4 — the release must ship

---

## Notes

- Close VS Code or GitHub Desktop before starting to prevent `maintenance.lock`
  recurrence. The lock is created by VS Code's background git operations.
  Alternatively: `File → Preferences → Settings → git.enabled → false` in
  VS Code before running git commands from the terminal.
- Do not create new features. If a scientific requirement surfaces during
  migration (6b), log it as a task for the following session.
- The AI & Productivity paper is the primary deliverable. EconFlow is
  infrastructure. Prioritise accordingly.
