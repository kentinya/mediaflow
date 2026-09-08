# Task 29.6 — Release Security and Production Artifact Validation

This Task follows [the development workflow](docs/development-workflow.md) and is subordinate to
the current [`SLICE.md`](SLICE.md).

```text
Task ID: 29.6
Parent Slice: 29
Parent Slice Name: Docker Production Self-hosted Release
Parent Required Outcomes: RO-7 — Release security and validation
Status: READY FOR B REVIEW
Task Base: 1938a3f79089049ab1f24efb766c54b519c519e7
Difficulty: High
Test Level: T4
Planner / Reviewer: B
```

## Goal

Complete the final production-artifact security journey for Slice 29: build and inspect the exact
image and Compose topology, prove deployment secrets and private local state are absent from build
context, layers, filesystem, rendered configuration, logs and authenticated API/Web/export
projections, and verify non-root execution, bounded network exposure, API-token/RBAC enforcement and
unsupported host-access rejection. Close every supported offline quality gate without weakening or
hiding existing tests. This advances Slice 29 Required Outcome RO-7.

## Why This Task Exists

Tasks 29.1–29.5 completed the execution boundary, image/process topology, production WSGI serving,
health/readiness, restart safety and backup/upgrade recovery journeys. The remaining release blocker
is a single coherent security and artifact acceptance pass across repository context, built image,
Compose, runtime output and authenticated management surfaces. Existing validation has partial wheel,
CI, non-root and secret checks, but it does not yet prove the complete Docker release boundary with
canary secrets/private files and network/RBAC assertions. The current baseline also has one failing
Storage Browser regression assertion and one ruff violation; because the Slice requires the supported
offline gates to pass, this Task may make only the smallest behavior-preserving corrections needed to
restore those gates and may not delete, skip or weaken them.

## Operator Journey Contract

- Entry: from a clean checkout, prepare only documented environment-owned secret references and
  isolated media/data paths, then build and inspect the exact candidate image and rendered Compose
  topology before release.
- Visible state: image identity/inventory, four service commands and users, published ports/bind
  address, `/data` and media mount boundaries, authentication/RBAC results, secret/private-state scan
  results, supported quality-gate results and truthful `SKIP`/`UNAVAILABLE` external boundaries.
- Action: run the release-security harness and documented release checklist, authenticate with each
  applicable principal, inspect output/artifacts, and correct the named build, mount, network,
  permission or redaction blocker before release.
- Success: one inspected candidate image serves all four non-root services; only the API port is
  published and loopback-bound by default; authentication and least privilege hold; no canary secret
  or private state appears in any prohibited surface; all supported offline gates pass.
- Failure/recovery: the release is rejected with the affected artifact/surface and bounded next
  action. No failed validation starts media work, grants execution authority, contacts a Provider or
  mutates Storage, and no failure is hidden by deleting tests, weakening assertions or converting an
  available gate to `SKIP`.

## Implementation Scope

```text
Repository/build-context policy
→ exact image and layer/filesystem inspection
→ Compose user/mount/network/process validation
→ authenticated API/Web/export/log redaction and RBAC probes
→ release checklist plus complete supported quality gates
```

Expected ownership/surfaces:

- Add one isolated Docker release-security acceptance harness using temporary `/data`, media mounts,
  configuration and deployment environment files. Seed unique canary values for every applicable
  secret class and harmless private-file canaries, build the exact candidate image, and inspect image
  history/filesystem/build context without printing the canary values on failure.
- Prove `.dockerignore`/build inputs exclude `config/alist.json`, local environment/configuration,
  SQLite/WAL/SHM/journal files, backups, exports, logs, caches, media, Git metadata, tests and other
  private developer state. The installed runtime and declared production dependency must remain
  present and usable.
- Render and inspect Compose with the candidate image. Assert exactly `api`, `worker`, `scheduler`
  and `notification-worker`; the same immutable image identity; one process command per service;
  non-root UID/GID; only local `/data` plus explicit media/config/environment mounts; no host `/`,
  Docker socket, privileged mode, host networking, hidden supervisor or writable source mount.
- Verify only the API service publishes a port and the default bind is loopback. Confirm explicit
  documentation and validation for deliberate LAN/reverse-proxy exposure, proxy-header trust and TLS
  ownership without implementing TLS, certificates or reverse-proxy identity.
- Exercise the production WSGI API/Web using deployment-owned API principals: missing/invalid token
  is rejected, viewer/auditor/operator/executor/admin permissions remain separated, and no read-only
  or denied request creates work, grants authority, sends notification or mutates Storage.
- Scan bounded container output, service logs, error responses, configuration/status projections,
  audit/log APIs, managed configuration export and result export for canary secrets, authorization
  headers, cookies and private host paths. Secret references may remain visible only where the
  existing contract permits; secret values must never appear.
- Restore the complete supported quality gates to green. The known baseline Storage Browser
  assertion and ruff line-length violation may be corrected narrowly, but their test intent must not
  be removed, skipped or weakened and no closed Slice behavior may be redesigned.
- Update only release/deployment documentation, validation automation and narrowly necessary gate
  corrections. No real credential, private endpoint, production path or generated acceptance state
  may enter the checkpoint.

Frozen unless B authorizes a scope correction:

- `SLICE.md`, `docs/roadmap.md`, canonical requirements and all Required Outcome/Surface/Safety
  wording.
- Jobs/Preview/Organize authority, OrganizerExecutor mutation semantics, Storage operations,
  Scheduler/Worker/Notification behavior, migration semantics and Task 29.1–29.5 accepted behavior.
- Built-in users/sessions/OIDC, TLS termination, reverse-proxy implementation/identity, Docker
  Secrets-specific ingestion, full Secret Store, registry publication/signing and CI deployment.
- External SMB/OpenList/S3/TMDB certification, distributed workers, remote databases, Kubernetes,
  automatic rollback and uncertain-mutation replay.

## Acceptance Criteria

- [ ] A clean-checkout build produces one inspectable candidate image used by all four Compose
      services; image history and filesystem contain the installed MediaFlow runtime and production
      WSGI dependency but no canary secret, environment/config private file, database/sidecar,
      backup/export, log/cache, media, Git metadata, test fixture or `config/alist.json`.
- [ ] Rendered Compose contains exactly the four required independent service commands, a single
      immutable image identity, explicit non-root UID/GID, local `/data`, separate confined media
      mounts and read-only config/environment inputs; it contains no secret value, privileged/host
      mode, host `/`, Docker socket, arbitrary host path, supervisor or extra long-lived process.
- [ ] Only the API service publishes a port and it is bound to `127.0.0.1` by default. Deliberate LAN
      or reverse-proxy exposure, trusted proxy-header behavior and deployment-owned TLS remain
      explicit documented boundaries and are not falsely reported as provided by MediaFlow.
- [ ] The running candidate proves non-root identity and required write boundaries for every service;
      `/data` and intended target media writes are available, source/config/environment mounts remain
      read-only, and missing/inaccessible or unsupported host access fails with bounded recovery and
      no fallback.
- [ ] Production API/Web retains Bearer-token authentication and RBAC: missing/invalid credentials
      return bounded denial, viewer/auditor/operator/executor/admin permissions remain least-
      privilege, and denied/read-only requests create no Job/Task/notification/authority or Storage
      mutation.
- [ ] Unique canary values for API, TMDB, Storage/Webhook and authorization/cookie secret classes do
      not appear in image layers/filesystem, rendered Compose, stdout/stderr, service logs, error
      responses, status/configuration/audit/log projections, configuration/result exports or Web
      assets. Failures identify only safe references/categories and never echo the value being sought.
- [ ] The release-security harness is isolated, bounded and fail-closed; absent Docker or external
      services are reported truthfully as `SKIP`/`UNAVAILABLE`, while an available local gate cannot
      be silently skipped. No harness path reads production configuration/media or contacts a remote
      Provider/Storage endpoint.
- [ ] The previously failing Storage Browser assertion and whole-repo ruff gate pass through narrow,
      behavior-preserving corrections if needed; no test is deleted, skipped, relaxed or hidden.
- [ ] Formatting, lint, full unittest discovery, compile, dependency consistency, canonical example
      configuration validation, wheel build/smoke, forbidden FFmpeg/FFprobe audit, Markdown/link
      checks where available and `git diff --check` all pass. External-service skips are enumerated
      and no supported local failure is accepted as pre-existing for Slice-final readiness.
- [ ] The checkpoint contains only RO-7 release security/validation work and narrowly necessary gate
      corrections, with no credentials, private paths, generated databases/logs/media or unrelated
      refactors.

## Required Tests

### Focused and integration tests

- Repository/build-context, Dockerfile/image history/filesystem and private-file/canary-secret
  exclusion tests, including `config/alist.json` ignored/untracked/unstaged evidence.
- Compose topology tests for exact services/image identity/commands, non-root user, mounts,
  read-only flags, network publishing/default bind, health checks and absence of supervisor,
  privileged mode, host root/network and Docker socket.
- Production-container authentication/RBAC matrix and zero-side-effect denial/read tests across
  representative API/Web, configuration/export, audit/log and execution-authority surfaces.
- Runtime secret-redaction scans using unique canaries across image, Compose, logs, responses,
  exports and Web assets without exposing the canaries in test failure output.
- Existing deployment, health/readiness, restart/fencing, upgrade/recovery, authentication,
  configuration/export, redaction, release-validation and closed-Slice safety regressions.

### Required commands

```bash
python3 scripts/check_governance.py
.venv/bin/python -m unittest <focused release/container/auth/redaction tests>
.venv/bin/python scripts/docker_release_security_smoke_test.py
.venv/bin/python scripts/docker_smoke_test.py
.venv/bin/python scripts/docker_health_smoke_test.py
.venv/bin/python scripts/docker_restart_fault_smoke_test.py
.venv/bin/python scripts/docker_upgrade_recovery_smoke_test.py
.venv/bin/ruff format --check .
.venv/bin/ruff check .
.venv/bin/python -m unittest discover -s tests
.venv/bin/python -m compileall -q mediaflow tests scripts
.venv/bin/python -m pip check
.venv/bin/python -m mediaflow.cli --config config/strategy.example.json config validate
.venv/bin/python -m mediaflow.cli --config config/mediaflow.phase13.2.example.json config validate
.venv/bin/python -m pip wheel . --no-deps -w /tmp/mediaflow-wheel-check
.venv/bin/python scripts/wheel_smoke_test.py /tmp/mediaflow-wheel-check/mediaflow-*.whl
test -z "$(rg -n -i 'ffprobe|ffmpeg' mediaflow pyproject.toml Dockerfile compose.yaml scripts || true)"
git diff --check
```

Run repository Markdown/link validation when an existing supported command is available and record
the exact command/result. Environment-unavailable external SMB/OpenList/S3/TMDB/reverse-proxy tests
may remain explicit `SKIP`/`UNAVAILABLE`; all available local/Docker gates and the full offline suite
must pass with zero failures.

## Non-goals

- Built-in username/password users, sessions, OIDC, reverse-proxy identity or a full permissions
  administration product.
- TLS termination, certificates, public-Internet policy enforcement, registry publication, release
  signing, automated deployment or CI access to production secrets.
- Docker Secrets-specific ingestion, full Secret Store, secret rotation automation or persistence of
  secret values in managed configuration.
- External-service certification, remote SQLite/database support, distributed/HA orchestration,
  Kubernetes/Swarm packaging, automatic rollback or uncertain-mutation replay.
- New media-processing, Scheduler, Worker, Notification, Storage, migration or execution-authority
  behavior; optional UI polish and unrelated refactors.

## Developer Completion Report

### Changed Files

- `.dockerignore` — explicit exclusion of SQLite/WAL/SHM/journal, database,
  backup/export, log/cache, media and other private artifacts from build input.
- `mediaflow/interfaces/operator_ui.py` — restored the served Storage-browser
  “Storage-relative breadcrumb” guidance text without changing behavior.
- `tests/test_system_settings_management.py` — narrow formatter correction for
  the known whole-repo ruff gate; test intent unchanged.
- `tests/test_release_security.py` — focused offline release-policy tests for
  `.dockerignore`, `config/alist.json` ignore/untracked evidence, Compose
  secret/boundary text and required gate commands.
- `scripts/docker_release_security_smoke_test.py` — isolated RO-7 Docker
  release-security acceptance harness.
- `docs/deployment.md`, `docs/release.md` — documented the release-security
  validation journey and its required commands.

### Implemented

- Repaired the two known baseline gates narrowly: the served Operator Web
  guidance again includes the “Storage-relative breadcrumb” wording, and
  `tests/test_system_settings_management.py` is ruff-clean/formatted without
  removing or weakening assertions.
- Extended `.dockerignore` to cover private SQLite/WAL/SHM/journal, database,
  backup/export, log/cache, media and archive artifacts explicitly.
- Added an isolated Docker release-security harness that builds the exact
  candidate image from a clean `git archive` checkout with harmless
  private-file/secret canaries, scans image history/configuration/filesystem,
  validates the rendered Compose topology (four services, one image, one
  command each, non-root UID/GID, `/data` volume, read-only config/env/source,
  read-write target, loopback-only API publication), proves non-root mount
  boundaries and per-service process commands, exercises missing/invalid
  Bearer denial plus viewer/auditor/operator/executor/admin RBAC with
  zero-side-effect assertions, scans Web/API/configuration/result/audit/log
  projections and durable SQLite evidence for every canary class, and verifies
  host-root rejection fails closed.
- Added focused offline release-policy regression tests covering
  `config/alist.json` ignore/untracked/unstaged evidence, private-artifact
  exclusion patterns, Compose literal-secret/unsupported-boundary text and the
  required T4 gate commands.
- Updated deployment/release documentation with the RO-7 release-security
  runbook and harness.

### Tests and Results

- `python3 scripts/check_governance.py` — PASS.
- `.venv/bin/python -m unittest tests.test_release_security
  tests.test_storage_browser tests.test_container_deployment
  tests.test_api_security tests.test_configuration_package_exchange
  tests.test_release_validation` — PASS (54 tests).
- `.venv/bin/python -m unittest discover -s tests` — PASS (1,393 tests,
  7 SKIP: real SMB/S3/OpenList and isolated endurance profiles are
  UNAVAILABLE because those external/profiled environments are not configured).
- `python3 scripts/docker_release_security_smoke_test.py` — PASS on the
  committed image, including unsupported-host-root failure.
- `python3 scripts/docker_smoke_test.py` — PASS.
- `python3 scripts/docker_health_smoke_test.py` — PASS.
- `python3 scripts/docker_restart_fault_smoke_test.py` — PASS.
- `python3 scripts/docker_upgrade_recovery_smoke_test.py` — PASS.
- `.venv/bin/ruff format --check .` — PASS.
- `.venv/bin/ruff check .` — PASS.
- `.venv/bin/python -m compileall -q mediaflow tests scripts` — PASS.
- `.venv/bin/python -m pip check` — PASS.
- `.venv/bin/python -m mediaflow.cli --config config/strategy.example.json
  config validate` — PASS.
- `.venv/bin/python -m mediaflow.cli --config
  config/mediaflow.phase13.2.example.json config validate` — PASS.
- `.venv/bin/python -m pip wheel . --no-deps -w
  /tmp/mediaflow-wheel-check.NCLBVL` then
  `.venv/bin/python scripts/wheel_smoke_test.py
  /tmp/mediaflow-wheel-check.NCLBVL/mediaflow-0.1.0-py3-none-any.whl` — PASS.
- Forbidden FFmpeg/FFprobe audit
  (`rg -n -i 'ffprobe|ffmpeg' mediaflow pyproject.toml Dockerfile compose.yaml
  scripts`) — PASS (no matches).
- `git diff --check` — PASS.
- Markdown/link validation — UNAVAILABLE (no repository-supported command
  exists to run).

### Decisions

- The smoke harness builds from a temporary clean `git archive HEAD` context
  with canaries injected only into that disposable context, so no production
  or repository-private file is read or altered.
- Canary failures identify only the affected secret class/surface and never
  echo the canary value; image/DB scans pass canaries through container
  environment variables rather than source code or failure text.
- The isolated harness publishes the API on a free loopback port, so the
  Compose assertion checks loopback host binding and container target 8080
  rather than a hard-coded host port; the committed Compose default remains
  `127.0.0.1:8080:8080`.
- The two baseline gate repairs are intentionally behavior-preserving: a
  guidance sentence in the served Operator Web and formatter-only changes in
  one test module.

### Remaining In-Slice Work

- No remaining Task 29.6 implementation work is known. Slice-level final
  review/closure remains owned by B/A and is not claimed here.

### Risks / Deviations

- No supported local/Docker gate failed. Seven full-suite tests remain SKIP
  for real SMB/S3/OpenList/endurance environments because those dedicated
  services/profiles are unavailable; no local gate was converted to SKIP.
- No repository Markdown/link validation command is supported, so that optional
  external-quality gate is recorded as UNAVAILABLE rather than claimed.
- The release docs describe the implementation-head artifact validation and do
  not claim publication, registry signing, CI deployment or final Slice
  acceptance.

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: 657f1a3697eec8e1537bee1335d45a06bec35c6f
```

## B Review Result

```text
Reviewed: [Head SHA or Task Base..Head]
Decision: PENDING
Slice Required Outcomes all satisfied: PENDING
Next: PENDING
```

If `FIX REQUIRED`, list only blockers for this Task. Fixes remain in this Task unless B explicitly
finds a genuinely independent business goal. This result does not close the Slice or update
Roadmap.
