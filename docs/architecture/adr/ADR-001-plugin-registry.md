# ADR-001: Plugin Registry as the Primary Extension Mechanism

**Status:** Accepted  
**Date:** 2026-06-28  
**Deciders:** Technical Steering Committee  
**Supersedes:** —  
**Superseded by:** —

---

## Context

EconFlow began as a bespoke replication package for a single study. Its extraction into
a general-purpose platform required resolving a fundamental design question: how should
third-party authors — researchers who want to add a new estimator, diagnostic, connector,
or output format — extend the platform without modifying its source code?

Three extension scenarios drove the design:

1. A researcher needs an estimator not included in the distribution (e.g., Driscoll-Kraay
   standard errors, Arellano-Bond GMM). They should not need to fork EconFlow.
2. A research institution maintains a proprietary database connector. They need to
   distribute it separately from EconFlow's public release.
3. A journal requires output in a format not included in the standard distribution.
   A contributor should be able to add a renderer as a standalone package.

The platform needed an extension mechanism that was: predictable (the same pattern for
every plugin type), safe (registration failure is visible at import time, not silently
at runtime), and minimal (adding a plugin requires no changes to EconFlow core).

The project also needed to choose between a static and a dynamic plugin model.
In a static model, all plugins are enumerated at build time. In a dynamic model, plugins
register themselves at import time. Given the research context — where users frequently
work in environments without network access or package management — dynamic registration
was necessary to support local, non-distributed plugins.

---

## Decision

We adopt the **import-time decorator registry pattern** as the universal extension
mechanism for all five plugin types in EconFlow: estimators, diagnostics, renderers,
connectors, and integrity checks.

The pattern is defined as follows:

1. Each plugin type has a module-level `dict` named `_REGISTRY` that maps string
   identifiers to class objects.

2. A `@register(id)` class decorator (one per plugin type, with distinct names:
   `@register`, `@register_diagnostic`, `@register_renderer`, `@register_integrity_check`,
   and for connectors `@register`) writes the decorated class into `_REGISTRY` at the
   time the module is imported. The decorator returns the class unmodified.

3. Registration raises `RegistryError` immediately if the `id` is already present in
   `_REGISTRY`, unless `overwrite=True` is explicitly passed. Duplicate IDs are treated
   as programming errors, not runtime conditions.

4. Each registry exposes four functions with consistent naming:
   - `get_<type>(id: str) -> Type[Base]` — raises `RegistryError` on unknown ID
   - `list_<type>s() -> list[str]` — returns sorted list of registered IDs
   - `register_<type>(id, cls)` — programmatic alternative to the decorator
   - `unregister_<type>(id)` — for use in tests only

5. Built-in plugins are registered in the `plugins/__init__.py` or
   `connectors/__init__.py` of their respective sub-package via explicit imports of each
   plugin module. Imports happen in alphabetical order to make registration order
   deterministic.

6. No plugin may register itself conditionally (e.g., only if a dependency is
   available). If a plugin has optional dependencies, it must import unconditionally
   and raise `ImportError` with installation instructions at instantiation time, not at
   registration time.

The five plugin base classes are:
- `estimation.base.BaseEstimator` — for econometric estimators
- `diagnostics.base.BaseDiagnostic` — for post-estimation tests
- `outputs.base.BaseRenderer` — for output format renderers
- `ingestion.base.AbstractConnector` — for data source connectors
- `integrity.base.BaseIntegrityCheck` — for result integrity checks

---

## Alternatives Considered

### Alternative 1: Python Entry Points (`importlib.metadata`)

The standard Python mechanism for cross-package plugin distribution. A third-party
package declares `[project.entry-points."econflow.plugins"]` in `pyproject.toml`.
EconFlow discovers and loads plugins by iterating entry points at startup.

**Why not chosen:** Entry points require the third-party package to be installed. A
researcher working locally with a plugin module in their project directory (without
packaging it) would need to run `pip install -e .` before the plugin was recognized.
This is a meaningful friction for researchers who are not experienced Python packagers.
The import-time pattern allows plugins to be loaded by simply `import`-ing a file,
with no packaging step required. Entry point discovery is planned as an optional
addition (see Future Implications) but cannot be the primary mechanism.

### Alternative 2: Directory Scanning

EconFlow scans a configured plugins directory at startup and imports all `.py` files
it finds.

**Why not chosen:** Directory scanning is non-deterministic (file system ordering),
slow (reads the filesystem on every startup), and provides no mechanism for a plugin
to declare its type or capabilities before being fully imported. It also requires
plugin authors to place their code in a specific directory rather than any importable
location.

### Alternative 3: Class Inheritance Scanning

EconFlow scans all subclasses of `BaseEstimator` at startup using
`BaseEstimator.__subclasses__()`.

**Why not chosen:** Subclass scanning discovers everything that has been imported,
regardless of whether it was intended as a plugin. It provides no way to assign a
stable string identifier to a plugin (the class name is a poor substitute — it is
not stable across rename refactors). It also discovers all intermediate abstract
subclasses, requiring special-casing to exclude them.

### Alternative 4: Explicit Registration in Configuration Files

Plugin classes are declared in `config.yaml` and instantiated by the pipeline by name.

**Why not chosen:** This would require every configuration file to contain `import`-style
references to plugin modules. It couples the runtime extension mechanism to the static
configuration format, making it impossible to register a plugin in code without
modifying YAML. It also provides no discoverability — `list_estimators()` could not
be implemented without parsing all known configuration files.

---

## Trade-offs

**Accepted costs:**

- Plugins must be imported before they are available. A user who forgets to import a
  third-party plugin module will receive a `RegistryError` on `get_estimator()` with
  no indication that the plugin exists. This is addressed by the entry point discovery
  planned for a future sprint (ADR-001-F1).

- Import-time registration means that importing a plugin module has a side effect
  (writing to `_REGISTRY`). This is a deliberate exception to the general Python
  principle that imports should be side-effect-free. The side effect is intentional,
  bounded, and documented.

- Duplicate ID detection at import time means that accidentally importing the same
  module twice (which Python's import system prevents under normal circumstances) or
  defining two plugins with the same ID in the same codebase produces an immediate
  error. This is a cost worth paying: silent overwrites would produce incorrect behavior
  that is extremely difficult to debug.

**Realized benefits:**

- The pattern is identical across all five plugin types. A contributor who has written
  one type of plugin understands the pattern for all others.
- `list_estimators()` and its equivalents work at any time after the built-in plugins
  are loaded, enabling the `econflow info` and `econflow datasets` commands.
- Testing a plugin in isolation requires only importing the plugin module and calling
  the base class's abstract methods; no framework setup is needed.

---

## Consequences

**Immediate consequences:**

1. Every new estimator, diagnostic, renderer, connector, and integrity check must be
   a class that inherits from the corresponding base class and is decorated with the
   corresponding `@register()` decorator.

2. Any code that adds a new plugin type (i.e., a new category of extension point) must
   follow the same pattern: define a base class, create a `_REGISTRY` dict, implement
   the four access functions, and document the stable interface in the Plugin SDK.

3. The five base classes — `BaseEstimator`, `BaseDiagnostic`, `BaseRenderer`,
   `AbstractConnector`, `BaseIntegrityCheck` — become the most important stable
   contracts in the codebase. Their abstract method signatures must not change without
   a deprecation cycle.

4. The built-in plugin lists in `plugins/__init__.py` and `connectors/__init__.py`
   are the canonical list of what EconFlow ships. Adding a built-in plugin means adding
   an import to one of these files.

**Architectural constraints imposed:**

- No sub-package may access a plugin from another sub-package directly (e.g., the
  pipeline must not import `OLSEstimator` from `estimation.plugins.ols`). All
  cross-subsystem access goes through the registry: `get_estimator("ols")`.

- No plugin ID may be a Python keyword, contain whitespace, or start with an underscore.
  IDs must be valid Python identifiers for forward-compatibility with entry point naming.

---

## Future Implications

**ADR-001-F1 (Planned):** Entry point discovery. In a future release, EconFlow will
discover plugins registered under the `econflow.plugins` entry point group at startup.
This will be additive — the import-time mechanism will continue to work. Entry points
are planned as the distribution mechanism for third-party packages; import-time
registration remains the mechanism for local plugins.

**ADR-001-F2 (Under consideration):** Plugin metadata. A future extension to the
registry may allow plugins to declare metadata beyond their ID: a human-readable label,
a version string, a set of capabilities, and a documentation URL. This would enable
`econflow info` to display richer information about available plugins. The decorator
signature would be extended: `@register("ols", label="Pooled OLS", version="1.0")`.
This must be done in a backward-compatible way — the current single-argument form must
continue to work.

**ADR-001-F3 (Contingent on community growth):** Plugin validation. If the plugin
ecosystem grows to the point where quality control becomes necessary, the registry may
gain an optional validation hook: a class method that the registry calls after
registration to verify that the plugin meets a minimum capability standard. This is not
planned for v1.0.

---

## Cross References

- `src/econflow/estimation/registry.py` — estimator registry implementation
- `src/econflow/diagnostics/registry.py` — diagnostic registry implementation
- `src/econflow/outputs/registry.py` — renderer registry implementation
- `src/econflow/ingestion/registry.py` — connector registry implementation
- `src/econflow/integrity/registry.py` — integrity check registry implementation
- `docs/plugin_sdk/PLUGIN_SDK.md` — Plugin SDK (the external contract for plugin authors)
- `docs/architecture/MILESTONE_v0.7.md` §1.10 — Plugin Architecture capability assessment
- `docs/roadmap/V1_RELEASE_CRITERIA.md` §3 — Plugin SDK release criteria
- ADR-004 — Connector Framework (applies this pattern to data connectors)
- ADR-005 — Reporting Engine (applies this pattern to renderers)
- ADR-006 — Research Integrity Framework (applies this pattern to integrity checks)
