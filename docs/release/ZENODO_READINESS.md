# Zenodo Readiness — v1.0.0

**Status: READY.**

## What Zenodo needs

Zenodo's GitHub integration archives a repository at release time and mints
a DOI from repository metadata. It reads metadata from, in order of
precedence: a `.zenodo.json` file if present (in which case `CITATION.cff`
is ignored entirely for Zenodo's own metadata), otherwise `CITATION.cff` if
present, otherwise minimal metadata inferred from the GitHub repository
itself. (Source: Zenodo's own documentation, "CITATION.cff file" —
https://help.zenodo.org/docs/github/describe-software/citation-file/,
verified live during this release-execution session.)

## Decision: CITATION.cff only, no `.zenodo.json`

EconFlow ships a complete, schema-valid `CITATION.cff` (validated this
session against the CFF 1.2.0 schema via `cffconvert --validate`, which
Zenodo's own documentation names as its recommended validator). No
`.zenodo.json` is added, for two reasons:

1. **Not needed.** `CITATION.cff` alone is fully sufficient for Zenodo to
   archive the repository and mint a correctly-attributed DOI-bearing
   record — title, version, authors, license, URL, and abstract are all
   present and valid.
2. **Adding one would be redundant and Zenodo's own stated direction is
   away from it.** Zenodo's documentation explicitly states its long-term
   preference is for `CITATION.cff` to make `.zenodo.json` unnecessary, and
   recommends against maintaining both (if both exist, `.zenodo.json` wins
   and `CITATION.cff` is silently ignored for Zenodo's purposes, which
   would make future edits to `CITATION.cff` alone incorrectly appear to
   update the Zenodo record). A `.zenodo.json` would only be justified if
   EconFlow needed Zenodo-specific fields `CITATION.cff` doesn't support
   (`grants`/funding, `communities`, `related_identifiers`) — it does not
   have any of these today.

## Remaining manual steps (cannot be performed from this sandbox)

These require the maintainer's Zenodo account and GitHub repository
settings access, neither of which is available here:

1. Log into Zenodo with the GitHub account that owns `abrhamgs3/econflow`
   and enable the repository under Zenodo's GitHub integration
   (https://zenodo.org/account/settings/github/).
2. Publish the `v1.0.0` GitHub release (see `GITHUB_RELEASE_v1.0.0.md`).
   Zenodo archives the release automatically on publish and mints a DOI.
3. Once the DOI is minted, uncomment and fill in the `doi:` line already
   present (commented out) at the bottom of `CITATION.cff`'s
   `preferred-citation` block, and commit that as a small follow-up change.

## Verdict

**READY** for the Zenodo-GitHub integration path via `CITATION.cff`. No
code or metadata gap blocks this — only the maintainer-account steps above,
which are outside what this session can perform.
