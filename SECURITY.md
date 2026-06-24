# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.1.x   | ✅ Active  |

Only the latest release receives security fixes. We follow
[Semantic Versioning](https://semver.org/), so patch releases (0.1.x)
are reserved for bug and security fixes with no breaking changes.

## Reporting a Vulnerability

**Please do not open a public GitHub issue for security vulnerabilities.**

Report security issues by email to **abrhamgs3@gmail.com** with the subject
line `[SECURITY] EconFlow — <brief description>`.

Include:

- A description of the vulnerability and its potential impact
- Steps to reproduce (proof-of-concept code or commands if possible)
- The EconFlow version(s) affected
- Any suggested fix, if you have one

### Response timeline

| Step | Target |
|------|--------|
| Acknowledgement | Within 48 hours |
| Initial assessment | Within 5 business days |
| Fix or workaround | Within 30 days for critical issues |
| Public disclosure | After fix is released and users have had time to update |

We follow [coordinated disclosure](https://en.wikipedia.org/wiki/Coordinated_vulnerability_disclosure).
You will be credited in the security advisory unless you request otherwise.

## Scope

EconFlow is a data-processing and econometrics framework. The primary security
concerns are:

- **Dependency vulnerabilities** — EconFlow depends on pandas, numpy,
  linearmodels, statsmodels, and scipy. Vulnerabilities in these libraries
  should be reported to the respective projects, but please also notify us so
  we can update our pinned bounds.
- **Arbitrary code execution via config files** — EconFlow loads YAML
  configuration using `PyYAML`. If you discover a path where a maliciously
  crafted config file can execute arbitrary code, that is in scope.
- **Path traversal in output directories** — anything that allows writing
  files outside the configured output directory is in scope.

## Out of Scope

- Vulnerabilities in the operating system, Python interpreter, or unrelated
  third-party software
- Denial-of-service attacks against a local CLI tool
- Issues that require physical access to the machine
