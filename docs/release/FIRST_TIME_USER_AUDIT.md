# First-Time User Audit — EconFlow v0.1.0

**Auditor role:** External economist, no prior knowledge of EconFlow  
**Machine state:** Clean environment, following documentation exactly  
**Audit date:** 2026-07-07  
**Scope:** Installation → Getting Started → panel estimation → publication tables → reproducibility certificate → replication package

---

## Summary scorecard

| Stage | Outcome | Severity of worst issue |
|---|---|---|
| Install | ✗ FAIL | CRITICAL |
| `econflow doctor` | ✓ PASS | — |
| Getting Started tutorial | ✓ PASS (via correct path) | — |
| README Quick Start | ✗ FAIL | CRITICAL |
| Publication tables (CSV) | ✓ PASS | — |
| Publication tables (LaTeX) | ✗ FAIL | CRITICAL |
| `econflow report` | ✗ FAIL | HIGH |
| Reproducibility certificate | ✓ PASS | LOW |
| Replication package | ✓ PASS (with minor issues) | LOW |
| Python API | ✗ BLOCKED | HIGH |

**Overall verdict: not ready for a public first-time user.** Three critical-severity issues would block a new user before they see a single result.

---

## Issue catalogue

### ISSUE-01 — Package not on PyPI

**Severity: CRITICAL**  
**Location:** README.md, Installation section

**What the README says:**
```bash
pip install econflow
```

**What actually happens:** There is no `econflow` package on the Python Package Index. A clean-machine user running this command will receive a "package not found" error and stop immediately, before seeing any other part of the project.

**Why a new user would struggle:** The README's very first instruction fails. A new user has no way to know whether the package was removed, renamed, or simply never published. There is no GitHub Releases page linked, no wheel file attached, no alternative installation path offered.

**Suggested improvement:** Either publish to PyPI, or replace the install instruction with the editable-install path that actually works:
```bash
git clone https://github.com/abrhamgs3/econflow.git
cd econflow
pip install -e ".[dev]"
```
Add a note explaining that PyPI publication is pending.

---

### ISSUE-02 — README Quick Start command triggers legacy pipeline and fails

**Severity: CRITICAL**  
**Location:** README.md, Quick Start section

**What the README says:**
```bash
econflow run --data-path path/to/panel_clean.csv
```

**What actually happens:**
```
WARNING  Required columns missing: ['country', 'ln_ai', 'ln_tfp', 'ln_hc', 'ln_gdp']
✘ Pipeline error: Data validation failed.
```

The `--data-path` flag invokes a legacy pipeline hard-coded for the AI & Productivity paper. It expects columns named `country`, `ln_ai`, `ln_tfp`, `ln_hc`, `ln_gdp`. A user who brings a CSV with any other column names gets a cryptic failure with no hint that there is a different mode.

**Why a new user would struggle:** This is the first command a user runs after installation. It fails instantly. The error message mentions columns (`ln_ai`, `ln_tfp`) that appear nowhere in the README and that a new user has never heard of. There is no indication in the Quick Start that the correct workflow is `--config/--models/--outputs`. The new user concludes the tool is broken.

**Suggested improvement:** Replace the Quick Start example with the three-flag form that actually works for generic data, and remove or relegate the legacy `--data-path` mode to an "AI & Productivity paper" section. If `--data-path` is kept, the error message must explain that this mode is for a specific dataset and point to the generic mode.

---

### ISSUE-03 — LaTeX output has completely broken significance stars

**Severity: CRITICAL**  
**Location:** `src/econflow/outputs/renderers/latex_renderer.py` → output at `outputs/tables/*.tex`

**What the user sees when opening the .tex file:**
```latex
Coefficient: value & 0.1145$^{$^{$^{*}$$^{*}$}$$^{*}$}$ & ...
```

**What the user expected:** `0.1145$^{***}$`

**What actually compiles:** LaTeX will either throw a "Missing $ inserted" error or render a visually broken superscript depending on the compiler. The main deliverable of the tool — a publication-ready LaTeX table — is unusable.

**Why a new user would struggle:** This is the output they plan to paste directly into their paper. The Getting Started README explicitly promises "LaTeX table at `outputs/tables/table_fe_investment.tex` uses `booktabs` formatting and is ready to paste directly into a manuscript. No reformatting required." That claim is false. A user who trusts the documentation and submits to a journal will get a compilation error at the journal's LaTeX processor.

**Suggested improvement:** Fix the star-rendering logic in the LaTeX renderer. The correct output is `$^{***}$`, produced by escaping the stars before wrapping them in a single math-mode superscript.

---

### ISSUE-04 — `econflow report` always produces 0 tables

**Severity: HIGH**  
**Location:** `econflow report` command, `src/econflow/commands/report.py`

**What happens:**
```
$ econflow report --config examples/getting_started/config/config.yaml \
    examples/getting_started/outputs/report/

  ⚠  No saved results found in /path/to/project/outputs/results.
       Run econflow run first, then re-run econflow report.

  ✔  Bundle written — 0 table(s), 0 figure(s)
```

The command runs, reports success, and writes an empty bundle — even after a successful `econflow run`. The two commands do not share state: `run` never writes to `outputs/results/`, so `report` never finds anything. The source code confirms this is a known stub: `# TODO (Reproducibility sprint): deserialise EstimationResult objects`.

**Why a new user would struggle:** The `report` command is listed in `econflow --help` alongside `run`, implying it is a working feature. The warning tells the user to "run `econflow run` first" — but the user already did. After re-running, the output is still "0 table(s)". The user has no way to know this command is an unfinished stub; nothing in the help text or the documentation says so.

**Suggested improvement:** Either complete the `run`→`report` integration, or mark the command as `[beta]` in the help text, and add a clear note that `econflow run` already writes tables to the config-specified output directory and that `econflow report` is for a future publication-bundle workflow.

---

### ISSUE-05 — `econflow validate .` fails immediately after `econflow init`

**Severity: HIGH**  
**Location:** `econflow validate` command

**What happens:**
```
$ econflow init my_study
$ cd my_study
$ econflow validate .
  ✗ YAML syntax -- 3 error(s)
    config.yaml  ✗ File not found: config.yaml
    models.yaml  ✗ File not found: models.yaml
    outputs.yaml ✗ File not found: outputs.yaml
```

`econflow init` places config files in `config/`, not in `.`. But `econflow validate .` looks for yaml files directly in the directory passed to it, not in a `config/` subdirectory. The correct call is `econflow validate config/` — but the `init` output says only "Run `econflow validate` to check configuration", with no path argument shown.

**Why a new user would struggle:** The next-steps message from `econflow init` instructs the user to run `econflow validate`. There is no indication of what argument to pass. The natural guess — `econflow validate .` — fails with three errors that look like the project scaffold is broken, not that the path is wrong.

**Suggested improvement:** The `init` next-steps message should show the exact command: `econflow validate config/`. Alternatively, `validate` could auto-detect a `config/` subdirectory when the passed path contains one.

---

### ISSUE-06 — New project → `econflow run` fails with confusing absolute path error

**Severity: HIGH**  
**Location:** `econflow run` after `econflow init`

**What happens:**
```
✘ Configuration validation failed (1 error(s)).
  · data file /sessions/trusting-amazing-keller/.../my_test_study/config/data/processed/panel.csv
    Data file not found: /sessions/.../my_test_study/config/data/processed/panel.csv
    Fix: Run your data preparation script to generate the file...
```

The path resolution is relative to the config file's location (`config/`), not to the project root. So `data/processed/panel.csv` in `config.yaml` resolves to `config/data/processed/panel.csv`, not `data/processed/panel.csv`. The scaffolded config is self-inconsistent on a fresh project.

**Why a new user would struggle:** The user followed the init instructions, edited nothing, and got an absolute-path error pointing to a path that is obviously wrong (inside `config/`). They do not know whether the error is in the config file, the data location, or the framework itself. The suggested fix ("Run your data preparation script") is unhelpful because the user has not written one yet.

**Suggested improvement:** Either make path resolution relative to the project root rather than the config file, or use an absolute path placeholder in the scaffolded `config.yaml` so the error is immediately clear. The `init` README should show a working one-liner for the first run (e.g., pointing `data.path` at the Grunfeld CSV to verify the setup).

---

### ISSUE-07 — No Python API documentation; `fit()` has no docstring

**Severity: HIGH**  
**Location:** `src/econflow/estimation/` — all estimators; `docs/` (no API reference)

**What happens:**
```python
from econflow.estimation import get_estimator
est = get_estimator('fe')
result = est.fit(df)   # KeyError: 'dependent'
```

The user has no docstring to read — `est.fit.__doc__` is `None`. The only way to discover what params are required is to read the source code. Once the user finds `required_parameters = ['dependent', 'regressors']`, they must also discover that `params` is passed to the constructor, not to `fit()`:

```python
est = get_estimator('fe')(params={
    'dependent': 'invest',
    'regressors': ['value', 'capital'],
    'entity_col': 'firm',
    'time_col': 'year',
})
```

There is no Sphinx documentation, no `help(est)` output, no notebook showing Python API usage, and no tutorial section covering direct programmatic use.

**Why a new user would struggle:** Many economists want to use a framework programmatically — in a notebook, in a script, or embedded in a pipeline. The CLI workflow is the only documented path. Anyone who tries the Python API hits a `KeyError` with no guidance, concludes the API is not intended for direct use, and looks elsewhere.

**Suggested improvement:** Add docstrings to all `fit()` methods with a working example. Add one notebook (`examples/getting_started/notebook.ipynb`) showing the Python API alongside the CLI. A single "Python API Quick Start" section in the README would dramatically lower the barrier.

---

### ISSUE-08 — `AIProdError` exposed in public `__all__` and `dir(econflow)`

**Severity: MEDIUM**  
**Location:** `src/econflow/__init__.py`, `__all__`

**What the user sees:**
```python
import econflow
print(econflow.__all__)
# [..., 'AIProdError', ...]
```

`AIProdError` is a remnant of the "AI & Productivity" paper-specific codebase. It was renamed to `EconFlowError` as part of the generalisation work, but the old name was kept as an alias and accidentally included in `__all__`.

**Why a new user would struggle:** The name `AIProdError` is confusing — it implies the package is for one specific paper. An economist adopting EconFlow for a growth study, a labour study, or a health study sees an exception class named after an AI productivity paper and reasonably wonders if they are using the right tool. It is also a footgun for anyone who catches `AIProdError` in their code — if the alias is removed in a future version, their code breaks silently.

**Suggested improvement:** Remove `AIProdError` from `__all__` and emit a `DeprecationWarning` if it is imported directly. Keep the alias internally for one version cycle to avoid breaking any existing users.

---

### ISSUE-09 — README test count is wrong (says 100, actual count is 1,341)

**Severity: MEDIUM**  
**Location:** README.md, Testing section

**What the README says:**
```
pytest   # full suite (100 tests)
```

**What actually runs:** 1,341 tests. The stale count is a minor issue in isolation, but it reads as evidence that the README has not been kept up-to-date — which raises legitimate questions about what else is stale.

**Suggested improvement:** Remove the parenthetical count entirely, or use a badge that reflects the live count. Hardcoded numbers always lag.

---

### ISSUE-10 — `econflow run` log output shows absolute internal paths

**Severity: MEDIUM**  
**Location:** `src/econflow/pipeline_generic.py` — INFO log messages

**What the user sees:**
```
INFO  CSV table written: /sessions/trusting-amazing-keller/mnt/AI and Productivity/econflow/examples/getting_started/outputs/tables/table_fe_investment.csv
```

The full absolute path contains platform-internal directory names. On a typical development machine it would contain the user's home directory, which is fine; but in shared or CI environments (the exact place where EconFlow is most useful for reproducibility), these paths can expose internal structure or become unwieldy.

**Why a new user would struggle:** The bigger issue is psychological — the path is so long that the filename itself is hard to read at a glance. The user has to scan to the end of a 120-character line to confirm the file was written where expected.

**Suggested improvement:** Log relative paths (relative to the project root or the working directory) in INFO messages, reserving absolute paths for DEBUG mode.

---

### ISSUE-11 — Replication package README has a broken step sequence

**Severity: LOW**  
**Location:** `replication_package/README.md` (generated by `econflow package`)

**What the README shows:**
```
1. Install the pinned environment:
   pip install -r environment.txt

3. Verify against the certificate:
   econflow verify --baseline certificate.json
```

Step 2 is missing. The sequence jumps from 1 to 3.

**Why a new user would struggle:** A replication package is given to journal reviewers and future researchers who are unfamiliar with the tool. A reviewer who sees a numbered list jump from 1 to 3 will wonder what they missed and may contact the author to ask.

**Suggested improvement:** Add a step 2 — most naturally "Run the analysis: `econflow run --config config/config.yaml ...`" — or fix the numbering.

---

### ISSUE-12 — Reproducibility certificate flags `dirty: true` with no explanation

**Severity: LOW**  
**Location:** `econflow certify` output — `certificate.json`, `environment.git.dirty`

**What the user sees in `certificate.json`:**
```json
"git": {
    "commit": "ef52ea7...",
    "branch": "main",
    "dirty": true,
    "tags": []
}
```

The certificate silently records `dirty: true` when there are uncommitted changes. A new user who does not think of themselves as a software developer will not know what "dirty" means in a git context, will not know whether this invalidates their certificate, and cannot find an explanation in the command output or the help text.

**Why a new user would struggle:** The whole point of the certificate is to prove reproducibility. A flag that says something is "dirty" feels alarming. Does this mean the results can't be trusted? Is the certificate invalid? The tool provides no answer.

**Suggested improvement:** The `econflow certify` command output should emit a warning when `dirty: true`, with a plain-English explanation: "Your working directory has uncommitted changes. To ensure full reproducibility, commit or stash all changes before certifying." A link to documentation on what this means would help.

---

### ISSUE-13 — CLI has 16 commands with no conceptual grouping

**Severity: LOW**  
**Location:** `econflow --help`

**What the user sees:** 16 commands in a single flat list: `init`, `doctor`, `validate`, `info`, `run`, `report`, `certify`, `verify`, `package`, `fetch`, `datasets`, `inspect`, `reproduce`, `compare`, `release-check`, `docs`.

**Why a new user would struggle:** A new user does not know which commands belong to which workflow. `release-check` and `docs` are developer-facing commands that should not be in a first-time user's mental model. `fetch`, `datasets`, `cache`, `inspect`, `reproduce`, and `compare` are advanced features. Presenting all 16 equally suggests they are all relevant from day one.

**Suggested improvement:** Group commands in the help output (Typer supports group panels): a "Getting started" group (`init`, `doctor`, `validate`, `run`), a "Results" group (`report`, `certify`, `verify`, `package`), a "Data" group (`fetch`, `datasets`, `cache`), and a "Replication" group (`inspect`, `reproduce`, `compare`). Move `release-check` and `docs` to a "Developer" group or suppress them from the default help.

---

### ISSUE-14 — No diagnostic (Hausman test, etc.) tutorial or example

**Severity: LOW**  
**Location:** Getting Started tutorial, `docs/`

**What the documentation promises:**  
The README package structure lists `diagnostics/` with "Hausman, Sargan-Hansen, Pesaran CD, Arellano-Bond AR". The tool has six diagnostic plugins implemented. The Getting Started tutorial runs three models and says nothing about which one to prefer — but the whole reason to run OLS vs. entity FE vs. two-way FE is to justify specification choices, which requires diagnostic tests.

**Why a new user would struggle:** An economist's first question after seeing three models is: "Which should I use? Did I pass the Hausman test?" There is no documented path from the CLI to a diagnostic result. `list_diagnostics()` exists in the Python API but with no example and no docstring on `run()`.

**Suggested improvement:** Add a Step 4 to the Getting Started tutorial: "Run a Hausman test" with a working CLI or Python API example. A single concrete example with interpretation would unlock the entire diagnostics subsystem for new users.

---

## Observed strengths

These worked well on first contact and should be preserved:

**`econflow doctor` is excellent.** Clear categorisation (System / Core packages / External tools / Optional), helpful `→ pip install ...` hints for missing packages, and the right exit code. This is the model for how all commands should present themselves.

**The Getting Started tutorial content is high quality.** The economic explanation of fixed effects (within-firm demeaning, between-vs-within variation) is genuinely useful and accurate. A new user who reaches this content and follows the correct `--config/--models/--outputs` invocation gets a working result in under a minute.

**`econflow init` scaffold is sensible.** Directory structure, starter scripts, and the scaffolded config are all reasonable starting points. The config file comments are clear and guide the user toward the right edits.

**`econflow certify` and `econflow package` work end-to-end.** Once a successful run exists, the certificate captures all the right information (git commit, package versions, SHA-256 fingerprints) and the package bundles it cleanly. The replication package README, despite the step-numbering bug, conveys the right workflow.

**The YAML config system is well-designed.** Three-file separation (`config.yaml`, `models.yaml`, `outputs.yaml`), strict validation with fix hints, and the `econflow validate config/` command together give a new user a reliable pre-flight check before any computation.

---

## Would you continue using EconFlow?

**Tentatively yes — but only after fixing ISSUE-01, ISSUE-02, and ISSUE-03.**

The core idea is genuinely useful. For an applied economist who regularly runs panel regressions, a YAML-driven config system that separates data, models, and outputs — and automatically generates a reproducibility certificate — would meaningfully reduce the friction of building a replication package. The Getting Started tutorial shows that when the tool works, it works quickly and cleanly.

But I cannot recommend it to a colleague in its current state, for these reasons:

First, it cannot be installed from PyPI. Any colleague who types `pip install econflow` following the README will stop before they see a single feature.

Second, the first command in the README Quick Start breaks visibly. The damage this does to trust is disproportionate to the ease of fixing it.

Third, the LaTeX output — the primary deliverable for academic economists — is broken. I would not paste `0.1145$^{$^{$^{*}$$^{*}$}$$^{*}$}$` into a journal manuscript. The CSV output is usable, but economists expect LaTeX tables.

If those three issues were fixed, I would run the Getting Started tutorial, adapt the Grunfeld config for my own panel data, and evaluate the tool seriously. The architecture is sound. The reproducibility infrastructure (`certify`, `package`, `verify`) is more thoughtful than anything else in the open-source panel econometrics space. The configuration validation with fix hints is better than most tools I have used.

The gap between the tool's potential and its current first-time user experience is real but narrow. Fixing the three critical issues and the four high-severity issues would make EconFlow a compelling choice for reproducible panel econometrics.

---

*Audit conducted 2026-07-07. No source code was modified during this audit.*
