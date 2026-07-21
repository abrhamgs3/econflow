# GitHub Release — Prepared, Not Published

This file records the exact title and description to use when publishing the
`v1.0.0` GitHub release. It is prepared for the maintainer to paste into the
GitHub "Create a new release" form; nothing has been published automatically.

## Tag

`v1.0.0` (to be created against commit `fd9c8dd`, or later if additional
commits land before publishing)

## Release title

```
EconFlow v1.0.0
```

## Release description

The full body is `RELEASE_NOTES_v1.0.0.md` at the repository root — copy its
contents (from "EconFlow v1.0.0" through "Acknowledgements") directly into
the GitHub release description field. It already covers Overview, Highlights,
Major Features, Installation, Quick Start, Documentation links, Scientific
Reproducibility, Known Limitations, Citation, License, and Acknowledgements.

## Publishing steps (for the maintainer to perform manually)

1. Confirm `main` is in the desired state and push it to `origin`.
2. `git tag -a v1.0.0 -m "EconFlow v1.0.0"` and `git push origin v1.0.0`.
3. On GitHub, draft a new release from the `v1.0.0` tag, using the title and
   description above.
4. If the Zenodo-GitHub integration is enabled for this repository (see
   `ZENODO_READINESS.md`), publishing this release will trigger Zenodo to
   archive it and mint a DOI automatically. Once minted, update the
   commented-out `doi:` line in `CITATION.cff` with the real DOI and commit
   that as a small follow-up.

Nothing in this document performs a git push, tag, or GitHub API call — it
is a prepared reference only, per the instruction not to publish
automatically.
