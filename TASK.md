# Task 29.2 — Production Image, Compose Topology and Serving Boundary

This Task follows [the development workflow](docs/development-workflow.md) and is subordinate to
the current [`SLICE.md`](SLICE.md).

```text
Task ID: 29.2
Parent Slice: 29
Parent Slice Name: Docker Production Self-hosted Release
Parent Required Outcomes: RO-1, RO-2 and the deployable portion of RO-3
Status: PLANNED
Task Base: a81e960f09ad3f2b430d7935467bbaa5203562a4
Difficulty: High
Test Level: T4
Planner / Reviewer: B
```

## Goal

Deliver the first deployable Docker vertical journey: a deployment owner can build one clean,
installable MediaFlow image, start the API, Processing Worker, Scheduler and Notification Worker as
independent Compose services, reach the existing authenticated Web/API through an explicitly
selected production WSGI server, and keep runtime state on a local persistent `/data` volume while
media roots remain explicit container-visible mounts.

This advances Slice 29 Required Outcomes RO-1 (image and service topology), RO-2 (production HTTP
boundary), and the packaging/runtime contract needed for RO-3 (durable `/data` and explicit media
mounts). It does not claim the Slice's complete health, restart-fault, upgrade or release-security
outcomes until their dedicated Tasks are reviewed.

## Why This Task Exists

Task 29.1 completed the pre-release Jobs/Preview execution-boundary correction. The remaining Slice
currently has no Dockerfile, Compose topology or production HTTP serving artifact, so an operator
cannot install the already-existing application as the promised self-hosted product. The largest
reasonable next unit is the complete packaging and process boundary: splitting this into a Dockerfile,
four independent service entries, a WSGI choice and volume snippets would leave no runnable vertical
deployment to verify.

## Operator Journey Contract

- Entry: a clean checkout with deployment-owned environment references and explicit media mount
  directories.
- Visible state: rendered Compose services, image identity, non-root UID/GID, container-visible
  `/data` and media paths, service/process state, and the existing authenticated API/Web surface.
- Action: build the image, render Compose, start the isolated stack, connect with the existing API
  bearer token, and restart an individual service without replacing the data volume.
- Success: exactly one image runs four independent processes; API requests are served by the
  production WSGI boundary; SQLite/configuration/task state is under `/data`; media access is only
  through explicitly mapped paths.
- Failure: invalid build context, missing required mount, inaccessible `/data`, unsupported host
  path, missing deployment-owned secret reference, or failed service process is reported as a
  bounded startup/Compose error rather than a false healthy deployment.
- Recovery: correct the environment, mount, ownership or image configuration and rerun the bounded
  build/start action; never copy private host state into the image or fall back to a development
  server, root container, host root or Docker socket.

## Implementation Scope

```text
Build context / image
→ production WSGI entrypoint
→ Compose api / worker / scheduler / notification-worker processes
→ local /data volume and explicit media bind mounts
→ authenticated API/Web smoke journey
→ packaging, mount and process-boundary tests
```

Expected ownership/surfaces:

- Add a reproducible, bounded Docker build definition and ignore rules. The build must install the
  package and only declared runtime dependencies; it must not copy `config/alist.json`, `.mediaflow`,
  databases, logs, caches, media, credentials or arbitrary files from the checkout.
- Add a production WSGI serving entrypoint/adapter and its declared dependency. `wsgiref.simple_server`
  remains development/trusted-loopback only. Preserve the existing bearer-token authentication,
  RBAC, management-only bootstrap and runtime configuration binding.
- Add a Compose file (and deployment documentation where needed) with exactly four independent
  services: `api`, `worker`, `scheduler` and `notification-worker`. Each service invokes one
  MediaFlow process, has explicit environment/reference inputs, uses the shared local `/data`
  volume, and does not embed a long-lived supervisor or silently start another service.
- Define explicit container-visible media mounts and the Local Storage root-path contract. `/data`
  must remain local application persistence; media mounts are separate and carry their intended
  read-only/read-write authority. Use a documented non-root UID/GID and fail closed when required
  paths are absent or inaccessible.
- Provide an isolated Compose smoke harness using temporary data/media paths that builds the exact
  image, starts the four services, reaches the authenticated Web/API and proves state survives an
  individual service restart. The harness must not use production paths, credentials or external
  Storage/TMDB services.
- Update only deployment/release documentation needed to make this journey executable. Do not
  redesign health/readiness semantics, Scheduler/Worker fencing, backup/upgrade migration, or the
  already-complete Jobs execution boundary in this Task.

Frozen unless B authorizes a scope correction:

- `SLICE.md`, `docs/roadmap.md`, `docs/requirements.md`, `docs/product-experience.md`,
  `docs/architecture.md` and the canonical Chinese requirements specification.
- Jobs/Preview/Organize execution-boundary behavior delivered by Task 29.1, including authority,
  Preview conflict semantics and OrganizerExecutor-only mutation.
- New identity systems, TLS termination, reverse-proxy identity/trust, Docker Secrets-specific
  ingestion, remote databases, distributed workers, Kubernetes/Swarm and automatic registry or CI
  publication.

## Acceptance Criteria

- [ ] A clean checkout produces one installable MediaFlow image from a bounded, reproducible build
      context; `config/alist.json`, credentials, private paths, databases, logs, caches and media
      are absent from the image and build context evidence.
- [ ] `docker compose config` renders exactly four independently addressable services named `api`,
      `worker`, `scheduler` and `notification-worker`; each service has one process command,
      explicit restart/dependency behavior and no hidden supervisor or second service.
- [ ] The API service uses the selected production WSGI server and deliberate host/port binding;
      the development `wsgiref.simple_server` path is not used by the production Compose command.
- [ ] An isolated fresh `/data` volume and explicit temporary media mounts start the stack under the
      documented non-root UID/GID. Missing/inaccessible `/data` or required media mount fails with
      actionable state and never falls back to host root, an arbitrary host path or Docker socket.
- [ ] The existing authenticated Operator Web/API is reachable through the Compose API service;
      bearer-token authentication, RBAC and management/runtime configuration binding remain the
      same application behavior as the non-container deployment.
- [ ] Representative durable state written under `/data` remains present after restarting an
      individual service; no service startup creates media work, calls a Provider, sends a
      notification or mutates Storage merely to boot.
- [ ] Image, Compose and startup output contain only secret references/identities, never secret
      values, authorization headers, cookies, execution tokens or provider credentials.
- [ ] The checkpoint contains only this packaging/serving/mount journey and its tests; no health
      model redesign, upgrade/migration implementation, unrelated cleanup or real deployment data
      is included.

## Required Tests

### Focused and integration tests

- Dockerfile/build-context tests proving bounded context, package installation, non-root user and
  absence of ignored/private files and secret literals.
- Production WSGI construction/entrypoint tests proving the Compose API command does not import or
  invoke `wsgiref.simple_server`, preserves deliberate host binding and forwards the existing WSGI
  application/authentication behavior.
- Compose schema tests for exactly four service names, one process per service, shared local `/data`,
  explicit media mounts, non-root UID/GID and no Docker socket/host-root mapping.
- Isolated Docker smoke acceptance: build the exact image, render Compose, start from temporary
  `/data` and media directories, authenticate to the API/Web, write representative durable state,
  restart one service, and verify state remains. Record `SKIP`/`UNAVAILABLE` with the exact boundary
  if a Docker engine is absent; do not infer a production pass from static YAML tests.
- Existing application authentication, configuration, Worker, Scheduler and Notification Worker
  tests, plus the Task 29.1 execution-boundary regression suite.

### Required commands

```bash
python3 scripts/check_governance.py
<repository Docker/Compose validation and isolated smoke harness>
python3 -m unittest <focused packaging/WSGI/Compose tests>
python3 -m unittest discover -s tests
python3 -m compileall -q mediaflow tests scripts
python3 -m pip check
python3 -m pip wheel . --no-deps -w dist
python3 scripts/wheel_smoke_test.py dist/mediaflow-*.whl
test -z "$(rg -n -i 'ffprobe|ffmpeg' mediaflow pyproject.toml || true)"
git diff --check
```

The full regression may retain the known pre-existing Storage Browser failure and environment
unavailable external-service skips only when reproduced at this Task Base with exact evidence.

## Non-goals

- Distinct liveness, management-readiness and business/Worker-readiness health model or probe
  semantics; these belong to the next health/recovery Task.
- Restart duplicate-occurrence, stale-owner fencing, uncertain-mutation recovery, backup/restore,
  upgrade preflight, migration rehearsal and release-candidate validation.
- New authentication/identity/session systems, TLS/certificate/reverse-proxy implementation,
  remote/managed databases, Docker Secrets-specific ingestion or registry publication.
- Changes to Jobs/Preview/Organize authority, Automation definitions, Files/FileIndex Manual Preview,
  OrganizerExecutor or any closed Slice 26–28 behavior.
- Production credentials, private host paths, databases, media, logs or generated caches.

## Developer Completion Report

### Changed Files

```text
.dockerignore
.gitignore
Dockerfile
compose.yaml
deploy/mediaflow.env.example
docs/deployment.md
docs/release.md
mediaflow/container_entrypoint.py
mediaflow/final_cli.py
mediaflow/production_wsgi.py
pyproject.toml
scripts/docker_smoke_test.py
scripts/make_deployment_config.py
tests/test_container_deployment.py
TASK.md
```

### Implemented

```text
Docker artifact:
- Bounded, non-root Dockerfile/image build: Python 3.13-slim, UID/GID
  10001:10001, declared Waitress dependency, no config/private/database/log/
  cache/media files or build residue in the image.
- .dockerignore keeps the build context to the package and build metadata only.

Production serving:
- mediaflow/production_wsgi.py selects Waitress as the production WSGI adapter.
- final_cli.py adds `mediaflow api serve-production --host --port --threads`;
  it builds the exact existing authenticated MediaFlowApi application and never
  imports/invokes wsgiref.simple_server. `api serve` remains the documented
  development/trusted-loopback listener.

Compose/runtime boundary:
- compose.yaml defines exactly api/worker/scheduler/notification-worker with one
  MediaFlow command each, unless-stopped restart, non-root user, shared local
  /data volume, and explicit /media/incoming (ro) and /media/organized (rw)
  bind mounts with create_host_path=false.
- Deployment-owned secret values live in a host-mounted environment file loaded
  by the container entrypoint, so Compose source and rendered output carry only
  references/paths, never secret values.
- mediaflow/container_entrypoint.py performs bounded preflight (config, /data,
  Local Storage media mounts, forbidden host-root/Docker-socket paths, API token
  reference) and then execs one MediaFlow command.

Journey support:
- scripts/make_deployment_config.py renders the canonical example with Docker
  container paths; docs/deployment.md documents build/start/verify/failure/
  recovery and secret hygiene; docs/release.md reflects the current packaging
  artifact without claiming full Slice release completion.
- scripts/docker_smoke_test.py builds the exact image, starts the isolated
  four-service stack, reaches authenticated API/Web through Waitress, writes a
  durable Job, restarts the API service, verifies persistence, non-root UID,
  secret-free logs/Compose output, four running services, and a missing media
  mount failure.
```

### Tests and Results

```text
python3 scripts/check_governance.py                                    -> PASS
.venv/bin/python -m unittest tests.test_container_deployment          -> PASS (9 tests)
.venv/bin/python -m unittest tests.test_api_security tests.test_api_credentials \
    tests.test_management_setup tests.test_configuration_status \
    tests.test_automation_api tests.test_release_validation            -> PASS (60 tests)
.venv/bin/python scripts/docker_smoke_test.py                          -> PASS (Docker engine
                                                                          available; build + four
                                                                          services + API restart
                                                                          persistence + missing
                                                                          mount failure)
.venv/bin/python -m unittest discover -s tests                         -> 1375 tests,
    failures=1 (pre-existing, see Risks), skipped=7 (external real-service gates)
.venv/bin/python -m unittest tests.test_storage_browser.StorageBrowserWebTests.\
    test_setup_picker_and_execution_environment_guidance_are_present  -> FAIL / PRE-EXISTING /
                                                                       UNRELATED (identical at
                                                                       Task Base a81e960)
.venv/bin/ruff format --check <all files changed by this Task>        -> PASS
.venv/bin/ruff check <all files changed by this Task>                 -> PASS
.venv/bin/ruff format --check .                                       -> FAIL / PRE-EXISTING /
                                                                        UNRELATED
.venv/bin/ruff check .                                                -> FAIL / PRE-EXISTING /
                                                                        UNRELATED
.venv/bin/python -m compileall -q mediaflow tests scripts             -> PASS
.venv/bin/python -m pip check                                         -> PASS
.venv/bin/mediaflow --config config/strategy.example.json config validate \
                                                                      -> PASS
.venv/bin/mediaflow --config config/mediaflow.phase13.2.example.json config validate \
                                                                      -> PASS
.venv/bin/python -m pip wheel . --no-deps -w dist/check               -> PASS
.venv/bin/python scripts/wheel_smoke_test.py dist/check/mediaflow-0.1.0-py3-none-any.whl \
                                                                      -> PASS
test -z "$(rg -n -i 'ffprobe|ffmpeg' mediaflow pyproject.toml Dockerfile \
    compose.yaml scripts docs/deployment.md || true)"                  -> PASS
git diff --check                                                       -> PASS
```

### Decisions

```text
- Waitress is the explicitly selected production WSGI server and is declared as
  the first runtime dependency. The Compose API command is a separate
  `serve-production` subcommand, leaving the standard-library development
  listener and its existing tests unchanged.
- Deployment secret values are supplied through a host-mounted environment file
  that the container entrypoint loads into the process environment. This keeps
  values out of `docker compose config` output without introducing in-product
  Docker Secrets ingestion (which remains deferred).
- Startup safety is enforced by a bounded entrypoint preflight and by
  `create_host_path: false` bind mounts; missing mounts are Docker/Compose
  errors and inaccessible paths are reported before a MediaFlow process starts.
  Preflight performs no Storage mutation, Provider call, Job/Task creation or
  notification.
- /data is a Compose named volume. SQLite/history are configured as absolute
  paths under /data by the deployment config helper and rejected by preflight
  if they escape that boundary.
```

### Remaining In-Slice Work

```text
Slice 29 RO-4 (health/readiness model), RO-5 (restart fault/ownership matrix),
RO-6 (backup/upgrade/migration recovery), the remaining release-security and
final RO-3/RO-7 evidence are not implemented by this Task and remain ahead. The
deployment runbook explicitly does not claim them.
```

### Risks / Deviations

```text
- Full regression retains the known pre-existing Storage Browser failure:
  `test_setup_picker_and_execution_environment_guidance_are_present` fails
  identically at Task Base a81e960 ("Storage-relative breadcrumb" absent from
  served APP_JS). It is unrelated to this packaging/serving Task.
- Whole-repo ruff format/check each report the same pre-existing
  `tests/test_system_settings_management.py` issue; it reproduces at Task Base.
  Every file changed by this Task is format- and lint-clean.
- 7 skipped full-suite tests are real external SMB/S3/OpenList/endurance gates:
  SKIP / UNAVAILABLE, no inferred pass.
- This Task intentionally does not implement graceful shutdown semantics beyond
  the Waitress process boundary; RO-2/RO-4 lifecycle/health treatment is a later
  Slice 29 Task.
```

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: a14bf85b361a1909507d9ab54dcb224e2a280a1a
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
