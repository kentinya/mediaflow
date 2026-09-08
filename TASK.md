# Task 30.2 — Production Docker V2 Artifact Integration and Release Proof

This Task follows [the development workflow](docs/development-workflow.md) and is subordinate to
the current [`SLICE.md`](SLICE.md).

```text
Task ID: 30.2
Parent Slice: 30
Status: READY FOR B REVIEW
Task Base: 177c5c26690864a1186b7632fab1ff579f03ef4e
Difficulty: High
Test Level: T4
Planner / Reviewer: B
```

## Goal

Complete Slice 30 RO-5 by making the Task 30.1 Vite output part of the one production MediaFlow
Docker artifact and proving that the existing Python API service serves the V2 entry, deep route and
built assets safely without Node at runtime, a second HTTP service, or any regression to V1 `/ui`,
API/RBAC, Compose process isolation or release-security boundaries.

## Why This Task Exists

Task 30.1 established the V2 source/build boundary, typed Dashboard journey, Python static-serving
adapter and frontend test foundation, but the current Dockerfile copies only Python project inputs.
The released image therefore contains no V2 build artifact, and `/ui-v2/` cannot work in the actual
Compose deployment. This is the sole remaining substantive Slice Required Outcome gap after Task
30.1 PASS.

This is the largest coherent remaining unit because Docker build integration, runtime asset
placement, Compose behavior, artifact inspection, live HTTP/security smoke coverage and deployment
documentation form one production boundary. Splitting those into file-level or test-only Tasks
would not independently deliver RO-5.

## Implementation Scope

### Deterministic image build and runtime layout

- Convert the Docker build to a bounded multi-stage build (or an equally reviewable one-image
  mechanism) that runs `npm ci` from the committed `web/package-lock.json`, produces the Vite
  artifact, and copies only the required built static files into the final Python runtime image.
- Bind `MEDIAFLOW_UI_V2_ASSET_ROOT` (or the existing static-serving boundary's documented
  equivalent) to the exact immutable artifact directory consumed by the running Python process.
- Keep the final image Python/MediaFlow-only at runtime: no Node executable, npm, frontend source,
  `node_modules`, development server, SSR process, CDN dependency or second HTTP server/service.
- Preserve the existing non-root UID/GID, `/data`, `/config`, media mounts, entrypoint, image
  minimization and four-service shared-image model.

### Production serving and coexistence proof

- Make the built image's API service serve `/ui-v2/`, `/ui-v2/dashboard` and referenced hashed
  assets through the existing Python static boundary, with deterministic bytes/content types and
  the existing CSP, cache, nosniff, referrer and permissions headers.
- Prove non-GET requests and unknown/traversal-like assets fail closed, while V1 `/ui`, `/ui/`,
  `/ui/app.js` and `/ui/style.css` remain available and behaviorally unchanged.
- Preserve `/api/v1/*` routing, Bearer authentication and RBAC outcomes. Static requests must not
  access repositories, Providers, Tasks/Jobs or Storage and must not create work or mutation.
- Ensure missing or failed frontend build input fails the image build or static boundary explicitly;
  do not silently ship stale/partial assets or fall back to a Node service.

### Release/security automation and documentation

- Extend focused Docker/unit policy tests and the release-security smoke so an image built from the
  exact candidate checkout verifies V2 artifact presence, Python serving, V1/V2 coexistence,
  GET-only/static-header behavior, API authentication/RBAC preservation and absence of Node/runtime
  frontend tooling.
- Keep all probes hermetic: use fake tokens, isolated Compose state and generated local fixtures;
  never use production credentials, the operator's media, `config/alist.json`, or an existing
  runtime database.
- Update README/deployment/architecture guidance as needed with the factual production artifact
  flow, build prerequisites, runtime path, no-Node guarantee and V1/V2 migration coexistence.

Frozen for this Task:

- `SLICE.md` Contract fields, Slice Base, Required Outcomes, Required Surfaces, Safety Invariants
  and Explicitly Deferred scope.
- Existing `/api/v1/*` semantics, domain/application authority, RBAC, Task/Job behavior,
  OrganizerExecutor mutation boundary and all media-operation safety policies.
- The Task 30.1 Dashboard feature scope and later Slice 31-36 application surfaces.
- `config/alist.json`, real/private configuration, credentials, tokens, endpoints, media paths,
  `.mediaflow/` runtime state and other operator data.

## Acceptance Criteria

- [ ] A clean Docker build uses the committed frontend lockfile to build Vite assets and places the
      resulting immutable artifact at the exact path consumed by Python in the final image.
- [ ] The final runtime image contains the required V2 static artifact but contains/requires no Node
      executable, npm, `node_modules`, frontend source tree, Vite server, second HTTP service, SSR or
      CDN runtime dependency.
- [ ] The existing Compose API service serves the V2 entry, Dashboard deep route and hashed assets
      from the built image with correct content types and existing security/cache headers; no host
      `web/dist` bind mount or Node process is required.
- [ ] V1 `/ui` coexistence, the four existing service roles, non-root runtime, persistence/media
      mounts, health/readiness and `/api/v1/*` 401/403/RBAC behavior remain intact.
- [ ] V2 static reads and error probes remain GET-only, bounded and zero-side-effect; unknown,
      traversal-like or missing assets fail closed without exposing paths, credentials or raw
      exceptions.
- [ ] Release-security automation builds the exact candidate checkout and proves artifact/runtime
      composition plus live V1/V2/API behavior using isolated local fixtures and fake credentials.
- [ ] Documentation truthfully describes the production build-to-runtime flow, prerequisites,
      artifact location, Python-only runtime and migration boundary without claiming later V2
      surfaces or `/ui` cutover complete.
- [ ] T4 validation passes with actual totals/skips/unavailable gates recorded; pre-existing failures
      are accepted only with reproducible unrelatedness evidence, and no validation touches the
      operator's `.mediaflow/` database or private configuration.
- [ ] The checkpoint contains only this coherent Task, excludes private/generated artifacts and
      `config/alist.json`, introduces no hidden skips or weakened assertions, and passes
      `git diff --check`.

## Required Tests

Run from the repository root unless the isolation note below applies:

```text
python3 scripts/check_governance.py
npm --prefix web ci
npm --prefix web run format:check
npm --prefix web run typecheck
npm --prefix web run lint
npm --prefix web run test -- --run
npm --prefix web run build
npm --prefix web run test:e2e
.venv/bin/ruff format --check .
.venv/bin/ruff check .
.venv/bin/python -m unittest tests.test_container_deployment tests.test_container_probe tests.test_release_security tests.test_v2_ui
.venv/bin/python -m unittest discover -s tests
.venv/bin/python -m compileall -q mediaflow tests scripts
python3 scripts/docker_release_security_smoke_test.py
git diff --check
```

The full unittest discovery must run from an isolated clean Git clone/checkpoint checkout when the
repository root contains `.mediaflow/mediaflow.sqlite3`; use the same project interpreter and record
the exact isolated path/command. Do not rename, move, edit or run the suite against the operator's
runtime database merely to obtain a green result. Environment-only cache/browser/temp redirections
are allowed when disclosed and when they do not change build inputs or gate assertions. Docker or
browser unavailability must be reported as `SKIP/UNAVAILABLE`, never inferred as success.

## Non-goals

- Work outside Slice 30 or implementation of Slice 31-36 shell/navigation, Files/FileIndex,
  Operations, Review/Recovery, Configuration or parity/cutover behavior.
- Replacing V1 `/ui`, moving `/ui-v2` to `/ui`, deleting legacy assets, or claiming V2 feature
  parity/accessibility completion.
- Adding a Node production server, BFF, SSR, CDN runtime, second container/service, new backend
  endpoint, API redesign, login/session/OIDC system or token persistence.
- Changing Recognition, Metadata, Naming, Classification, planning, execution, Storage adapters,
  conflict/recovery semantics, overwrite/delete authority or OrganizerExecutor behavior.
- Fixing the pre-existing CWD-relative test/runtime-database isolation defect; this Task must avoid
  the operator database during validation but must not absorb unrelated test-infrastructure work.
- Production credentials, real external services, real media, private paths, generated runtime
  databases, unrelated refactors, optional proof, copy polish or P2/P3 cleanup.

## Developer Completion Report

### Changed Files

Implementation checkpoint `6953b87afa09e61ff62ffea5eb2a9a7d96c55492` (7 files, +289/−19):

- `Dockerfile` — bounded multi-stage build: `node:22-bookworm-slim AS web-build` stage runs
  `npm ci --no-audit --no-fund` from the committed `web/package-lock.json` plus `npm run build`
  with an explicit artifact-integrity gate; the final `python:3.13-slim` stage copies only the
  built static files to `/opt/mediaflow/web/dist` and binds
  `MEDIAFLOW_UI_V2_ASSET_ROOT=/opt/mediaflow/web/dist` in the image environment. Existing
  UID/GID 10001, `/data`, `/config`, entrypoint, minimization and `VOLUME`/`USER` lines unchanged.
- `scripts/docker_release_security_smoke_test.py` — image-scan additions (V2 artifact presence/
  completeness, web root contains only `dist`, no `node_modules`, no `.ts`/`.tsx` frontend source,
  no `node`/`npm`/`npx`/`vite` executable, asset-root env binding, non-empty real
  `v2_ui_assets()` serving map), image-config assertion for the `MEDIAFLOW_UI_V2_ASSET_ROOT`
  binding, and the new live `assert_v2_static_serving` V1/V2 coexistence probe.
- `tests/test_container_deployment.py` — multi-stage Dockerfile policy test (stage list, lockfile
  `npm ci`, artifact copy, env binding, final stage free of Node/npm/frontend source) and Compose
  policy test (no `web/dist` host mount, no asset-root override drift, no Node in Compose).
- `tests/test_release_security.py` — `.dockerignore` must also exclude `web/node_modules`,
  `web/dist`, `web/coverage`, `web/playwright-report`, `web/test-results`.
- `README.md`, `docs/deployment.md`, `docs/architecture.md` — factual production artifact flow,
  build prerequisites (multi-stage, no host Node), artifact location, Python-only runtime,
  V1/V2 coexistence and updated release-security coverage; no claim of later V2 surfaces or
  `/ui` cutover.
- This recording commit adds the Developer Completion Report to `TASK.md` (carrying B's planned
  Task into the checkpoint).

### Implemented

- **Deterministic image build and runtime layout (RO-5):** the image build runs `npm ci` against
  exactly the committed `web/package-lock.json` (npm `ci` fails on any lockfile/manifest mismatch),
  builds the Vite artifact in the Node stage, and only `/build/web/dist` crosses into the final
  Python stage. A failed frontend build, a missing `dist/index.html`, or a dist without built
  JS/CSS fails the image build explicitly; stale or partial assets are never shipped. The final
  image binds `MEDIAFLOW_UI_V2_ASSET_ROOT=/opt/mediaflow/web/dist` — the exact directory consumed
  by the running Python process. Verified in the built image: `/opt/mediaflow/web` contains only
  `dist` (index.html, favicon.svg, hashed JS/CSS); the installed `mediaflow.interfaces.v2_ui`
  boundary loads a 6-path serving map from it.
- **No-Node runtime guarantee:** the runtime image contains/requires no Node executable, npm,
  `node_modules`, frontend source tree, Vite/dev server, SSR process, CDN dependency or second
  HTTP service; Compose is unchanged and needs no host `web/dist` bind mount. Non-root UID/GID
  10001:10001, `/data`, `/config`, media mounts, entrypoint, healthchecks and the four-service
  shared-image model are untouched.
- **Production serving and coexistence proof:** the Compose API service serves `/ui-v2/`,
  `/ui-v2/dashboard` (unknown client routes fall back to the entry document) and referenced hashed
  assets through the existing Python static boundary with deterministic bytes/content types and the
  existing no-store/CSP/nosniff/referrer/permissions headers; POST is 405; unknown/missing/encoded-
  traversal assets fail closed 404; V1 `/ui`, `/ui/app.js`, `/ui/style.css` behave unchanged;
  unauthenticated `/api/v1/dashboard` stays 401 beside V2 serving.
- **Release/security automation:** the smoke now proves V2 artifact/runtime composition (including
  executing the real static-serving loader inside the image) and live V1/V2 behavior from the exact
  candidate checkout, alongside all previous canary/redaction/RBAC/mount evidence.
- **Documentation:** README, deployment and architecture guidance state the factual
  build-to-runtime flow, prerequisites, artifact path, no-Node guarantee and migration
  coexistence without claiming later V2 surfaces.

### Tests and Results

Test Level T4 battery, all PASS. Commands from the repository root unless noted:

- `python3 scripts/check_governance.py` — PASS
- `npm --prefix web ci` — PASS (run as `npm --prefix web ci --include=dev`; see Deviations)
- `npm --prefix web run format:check` — PASS
- `npm --prefix web run typecheck` — PASS
- `npm --prefix web run lint` — PASS
- `npm --prefix web run test -- --run` — PASS (5 files, 45 tests: Vitest + RTL)
- `npm --prefix web run build` — PASS (deterministic artifact, hashed assets)
- `npm --prefix web run test:e2e` — PASS (3 Playwright tests against built artifact + local fake API)
- `.venv/bin/ruff format --check .` — PASS (406 files)
- `.venv/bin/ruff check .` — PASS
- `.venv/bin/python -m unittest tests.test_container_deployment tests.test_container_probe tests.test_release_security tests.test_v2_ui` — PASS (33 tests)
- `.venv/bin/python -m unittest discover -s tests` — PASS: 1406 tests, OK (skipped=7), run from an
  isolated clean clone of the implementation checkpoint: exact path/command
  `git clone /root/mediaflow /tmp/task302-clone && cd /tmp/task302-clone && /root/mediaflow/.venv/bin/python -m unittest discover -s tests`.
  The repository root contains `.mediaflow/mediaflow.sqlite3`, so the operator runtime database was
  never used, renamed, moved or edited.
- `.venv/bin/python -m compileall -q mediaflow tests scripts` — PASS
- `python3 scripts/docker_release_security_smoke_test.py` — PASS ("Release-security smoke
  acceptance passed.") against implementation checkpoint 6953b87…: clean `git archive HEAD`
  checkout, `--no-cache` multi-stage image build, image history/config/filesystem scans (V2
  artifact + no-Node + binding evidence), rendered Compose topology, four-service healthy stack on
  temporary paths, non-root/mount boundaries, live V1/V2 static coexistence with safe headers,
  GET-only/fail-closed V2 probes, RBAC/zero-side-effect denial, managed-runtime activation, Worker
  restart, projection/export/log/SQLite canary scans, and the unsupported-host-root fail-closed
  probe. Docker was available; no gate was skipped or inferred.
- `git diff --check` — PASS

The 7 unittest skips are pre-existing environment-gated suites unrelated to this Task (real
SMB/S3/OpenList acceptance environments absent, symlink/POSIX-lease conditions). They were not
introduced, hidden or weakened by this Task.

### Decisions

- **Image-owned asset-root binding:** `MEDIAFLOW_UI_V2_ASSET_ROOT=/opt/mediaflow/web/dist` is set
  in the final image stage rather than in `compose.yaml`, so the binding is part of the immutable
  image configuration consumed by the process, with a single source of truth and no Compose/image
  drift. The deployment-owned override via the mounted environment file still works (documented),
  and unit tests assert Compose contains no host `web/dist` mount and no asset-root override.
- **Artifact at `/opt/mediaflow/web/dist`:** keeps the frontend artifact inside the existing
  `WORKDIR`/home of the runtime user already covered by the image `chown` and by the smoke's
  `/opt/mediaflow` canary-scan root, without new volumes or paths.
- **`node:22-bookworm-slim` build stage:** pinned to the Node major line required by the frontend
  toolchain (`vite` ^8, Playwright). JS dependencies are pinned by the committed lockfile via
  `npm ci`; the Node minor drift inside the major line remains a disclosed build-tooling risk.
- **Build-stage integrity gate:** `test -f dist/index.html` plus a built JS/CSS presence check fail
  the image build explicitly on missing/incomplete frontend build input, complementing `npm ci`'s
  lockfile strictness; the static boundary still fails closed (404) if a runtime artifact root is
  missing.
- **Smoke scan runs the real serving loader inside the image:** asserting a non-empty
  `v2_ui_assets()` map from the installed `mediaflow` package proves the exact Python boundary
  consumes the exact baked artifact, stronger than file-existence checks alone.
- **Live traversal probe uses `%2f` encoding** so the server-side rejection (not client URL
  normalization) is exercised over real HTTP.
- **No change to `mediaflow/` runtime code was needed:** the existing
  `MEDIAFLOW_UI_V2_ASSET_ROOT` static-serving boundary already satisfied the serving contract; this
  Task binds it to the built artifact and proves it in production composition.

### Remaining In-Slice Work

- B review of this checkpoint; B's re-evaluation of the Slice 30 Required Outcomes after this Task
  (RO-5 production deployment boundary is delivered for review; whether all Required Outcomes are
  satisfied is B's determination). Slice closure, the Closure Packet and any next Task remain
  B/A-owned and are not planned here.

### Risks / Deviations

- **Environment-only redirects (disclosed; none change build inputs or gate assertions):**
  - `npm ci --include=dev`: the ambient harness environment sets `NODE_ENV=production`, which makes
    npm default to `omit=["dev"]`; the flag restores the lockfile's full dependency install.
  - `NODE_ENV=test` for the Vitest/RTL and Playwright gates: with `NODE_ENV=production`, React
    Testing Library loads the production react-dom build where `act` is absent (13 spurious
    failures); `test` is the standard test environment value.
  - `PLAYWRIGHT_BROWSERS_PATH=/root/.cache/ms-playwright` for the e2e gate: the sandbox `HOME` is
    read-only, so the pre-installed Chromium at `/root/.cache/ms-playwright` is named explicitly.
  - `DOCKER_CONFIG=/tmp/task302-docker-config` and `TMPDIR=/root/mediaflow/build/tmp-smoke` for the
    Docker smoke: the sandbox `HOME` is read-only (buildx state) and the Docker daemon cannot see
    sandboxed `/tmp` bind sources, so the deployment fixtures were created in the Git-ignored
    workspace `build/` tree (removed afterwards; no repo pollution).
- Docker image builds require registry/network access for the Node/Python base images and the
  locked npm dependencies; the release smoke builds `--no-cache` from a clean checkout each run.
- `node:22-bookworm-slim` is a floating tag within the major line; JS dependencies are pinned by
  the lockfile, but Node minor updates can change build behavior between builds.
- An operator who overrides `MEDIAFLOW_UI_V2_ASSET_ROOT` through the deployment environment file
  points the V2 static root elsewhere; an empty/missing artifact then fails closed with 404 on
  `/ui-v2/*` while the API and V1 `/ui` keep serving (documented deployment-owned behavior).
- The 7 pre-existing environment-gated unittest skips and unavailable real SMB/S3/OpenList
  environments remain unavailable exactly as before this Task.

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: 6953b87afa09e61ff62ffea5eb2a9a7d96c55492
```

## B Review Result

```text
Reviewed: [Head SHA or Task Base..Head]
Decision: PENDING
Slice Required Outcomes all satisfied: PENDING
Next: PENDING
```

If `FIX REQUIRED`, list only blockers for this Task. Fixes remain in this Task unless B explicitly
finds a genuinely independent business goal. This result does not close the Slice or update Roadmap.
