# Phase 19.11 — Reproducible Release Validation and CI Baseline

## Goal

Turn the existing local acceptance procedure into a deterministic GitHub Actions quality gate and
validate the installable wheel in an isolated environment. This phase changes no media behavior and
does not publish a release.

## 1. Continuous integration

- Add a least-privilege GitHub Actions workflow for pushes and pull requests.
- Test every supported Python version declared by the project.
- Install only declared development dependencies; use dependency caching without caching credentials.
- Run formatter check, lint, full offline unit suite, compile check, dependency check, both canonical
  configuration validations, and the FFprobe/FFmpeg runtime audit.
- Unit CI must not require TMDB, SMB, OpenList, S3/R2, API tokens, or other production secrets.
- Set explicit job timeouts and read-only repository permissions.

## 2. Isolated wheel smoke test

- Build the wheel with the declared build backend and no undeclared build dependency assumptions.
- Install that wheel into a fresh isolated virtual environment, not editable source.
- Verify the installed `mediaflow` entry point, help output, both example configurations, and a local
  runtime database backup/verify round trip.
- Ensure the smoke test imports the installed artifact rather than the repository checkout.

## 3. Release metadata and operator documentation

- Audit `pyproject.toml` supported Python metadata, package discovery, console entry point, and wheel
  contents; make only corrections required for a valid distributable artifact.
- Document the exact local release-validation commands and CI boundary.
- Add a release checklist covering clean worktree, tests, wheel smoke test, configuration validation,
  changelog/version review, database backup, and explicit no-automatic-publish behavior.

## 4. Safety and scope

- CI and wheel smoke tests use temporary local paths and perform zero production media Storage access.
- Never inject, print, or require secrets; optional live integration tests remain skipped.
- Do not add release publishing, GitHub tokens beyond the automatic read-only token, container images,
  signing, attestations, deployment, database restore, policy/engine changes, or dependency upgrades.
- Preserve RecognitionType C, DryRun defaults, no-overwrite behavior, and the OrganizerExecutor boundary.

## Required tests

- Workflow syntax and command coverage are asserted without network-backed production integrations.
- Wheel contains required Python modules and excludes runtime databases, user configuration, caches,
  tests, local secrets, and media files.
- Fresh-environment console entry point and example configuration validation pass.
- Installed-artifact database backup/verify round trip passes using temporary local files.
- Existing Parser, Recognition, Metadata, Naming, Classification, Planner, Executor, Storage, Task,
  API/UI, operational log, and database backup regressions pass.
- Formatter, lint, compile, dependency, wheel, FFprobe/FFmpeg, config, and diff checks pass.

## Documentation

Update README, requirements, architecture, progress, and roadmap. Add a concise release checklist.

## Out of scope

Artifact publishing, semantic-release automation, Docker/container publication, signing/SBOM,
deployment, OIDC/Secret Store, TLS termination, database restore, and live provider/storage CI.

## Final report

## Phase 19.11 Result

PASS / FAIL

## CI

## Wheel Validation

## Safety

## Regression

## Changed Files

## Decisions

## Remaining Work

## Risks

## Final Recommendation
