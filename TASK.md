# Task 30.1 - V2 Frontend Foundation and Read-Only Dashboard Proof

This Task follows [the development workflow](docs/development-workflow.md) and is subordinate to
the current [`SLICE.md`](SLICE.md).

```text
Task ID: 30.1
Parent Slice: 30
Status: READY FOR B REVIEW
Task Base: 9858c5ebbedf9fd98879f35383da44cd2228ce9f
Difficulty: High
Test Level: T4
Planner / Reviewer: B
```

## Goal

Deliver the first independently verifiable V2 proving unit: a project-owned React + TypeScript +
Vite frontend with explicit ownership boundaries, a central typed Dashboard API/auth/query boundary,
and a read-only Dashboard route served by the existing Python application at a separate documented
`/ui-v2/` migration prefix. This advances Slice 30 RO-1 through RO-4 and establishes the
frontend/test evidence needed for RO-6, while preserving the existing Python API, RBAC and V1
`/ui` authority.

## Why This Task Exists

The repository is at the V2 activation baseline but has no frontend source tree, package/toolchain,
client-side router, query cache, typed API boundary or component-level Dashboard proof. The existing
Dashboard API and dependency-free `/ui` are useful V1 authorities, but they cannot prove the adopted
V2 architecture or its memory-only authentication and honest state behavior.

This is the largest reasonable first unit because it creates the reusable runtime boundary and
proves one complete read-only user path without migrating later V2 application surfaces or moving
domain/execution authority into the browser. Production Docker packaging and final Slice-level
deployment/security hardening remain separate follow-up work.

## Implementation Scope

### Frontend source and runtime boundaries

- Add a first-class `web/` (or repository-justified equivalent) React + TypeScript + Vite project
  with a committed lockfile and deterministic scripts for format/type/lint/test/build.
- Make ownership explicit in source layout, at minimum for:
  - application bootstrap/providers;
  - route definitions;
  - Dashboard feature;
  - Dashboard entity/types;
  - shared API and auth state;
  - shared UI primitives/styles.
- Use TanStack Router for client-side route ownership and TanStack Query for the single Dashboard
  server-state/query-cache boundary. Node is build/development tooling only.
- Keep frontend production code out of `mediaflow.domain` and `mediaflow.application`; do not add a
  frontend-owned domain or a second backend service.

### Typed API and authentication boundary

- Add one central typed API client for the existing `GET /api/v1/dashboard` contract, including the
  bounded `recentLimit` query used by the proving route. The client must validate/normalize the
  response into frontend-owned types without leaking provider payloads or raw exceptions.
- Represent at least these safe error categories explicitly: missing/invalid or expired principal
  (`401`), forbidden permission (`403`), unavailable/network failure, and malformed successful
  response. Messages must be bounded and secret-free.
- Accept the existing API-principal Bearer token through the V2 entry interaction only in runtime
  memory. Clear the input after connect and on disconnect; do not use `localStorage`,
  `sessionStorage`, IndexedDB, cookies, URL/query/hash parameters or token-bearing telemetry/logging.
- Preserve the existing API/RBAC outcomes. Do not add a login/session system, token refresh service,
  permission bypass or new backend authentication endpoint.

### Read-only Dashboard proving path

- Add a documented V2 entry route and Dashboard route, with the route flow:
  `router -> Dashboard route -> TanStack Query -> central typed API client -> existing Python API ->
  typed model -> shared UI primitives`.
- Render user-visible loading, empty, success, categorized transport/shape error, unauthorized
  and forbidden states. State must be derived from the bounded API result and must not fabricate
  unavailable counts or details.
- Provide a bounded refresh action that re-fetches the same read-only query. It must not submit a
  Job/Task, invoke a Provider, inspect arbitrary Storage, issue execution authority or mutate media.
- Use shared primitives for the Dashboard shell, status presentation, counts and refresh control;
  do not duplicate API/auth/query logic inside the feature component.

### Python static coexistence boundary

- Serve the built V2 static artifact from the existing Python/MediaFlow application at `/ui-v2/` (or
  an explicitly documented equivalent), including the entry document and required assets, while
  preserving the V1 `/ui`, `/ui/`, `/ui/app.js` and `/ui/style.css` behavior.
- Keep static serving GET-only and preserve the existing safe response headers/CSP/cache and
  `/api/v1/*` routing/authentication semantics. Do not make the V2 static route access repositories,
  Storage, Providers, Tasks, Jobs or execution services.
- Ensure the source checkout can produce the same deterministic static artifact that the Python
  application serves. The final Docker image/Compose packaging mechanism is a follow-up Task, but
  this Task must not require a Node process to serve the V2 page.

### Tests and documentation

- Add Vitest and React Testing Library coverage for typed normalization, auth/permission outcomes,
  memory-only token behavior, query refresh and every required Dashboard state.
- Add a minimal Playwright browser path against a local fake or existing local test API that loads the
  built/static V2 route and proves the authenticated Dashboard request and a safe failure/recovery
  state. Never use production credentials, media, Storage or external providers.
- Add Python coverage for V2 static routes, V1/V2 coexistence, GET-only behavior, headers and the
  no-side-effect boundary; retain existing legacy UI/API/security tests.
- Document the V2 entry prefix, token model, build-only Node role, local verification commands and
  migration coexistence in the repository's appropriate README/architecture/development guidance.

Frozen for this Task:

- `config/alist.json` and all real/private configuration, credentials, tokens, cookies, endpoints,
  media paths and generated runtime data.
- Existing V1 `/ui` assets and their public route contract.
- Existing `/api/v1/*` endpoint semantics, Python domain/application authority, RBAC, Storage
  adapters, Metadata providers, Task/Job behavior, execution authorization and OrganizerExecutor
  mutation boundary.

## Acceptance Criteria

- [ ] `web/` (or the documented equivalent) is a first-class typed React/Vite source boundary with
      explicit app, route, feature, entity and shared ownership; no monolithic `app.js` replacement
      or frontend production code is added to Python domain/application modules.
- [ ] The documented V2 entry and Dashboard route build and execute the complete Router -> Query ->
      central typed client -> existing Dashboard API -> typed model -> shared UI path.
- [ ] Bearer authentication is sent only from an in-memory token, the entry input is cleared after
      use, disconnect clears auth/query state, and repository inspection/tests show no persistent
      browser token storage, URL token, cookie token or token-bearing telemetry.
- [ ] The central client preserves existing `401`/`403` semantics and exposes bounded unauthorized,
      forbidden, network/unavailable and malformed-response outcomes without raw headers, tokens,
      exceptions, provider payloads or private paths.
- [ ] Loading, honest empty, success, categorized error, unauthorized and forbidden states are
      visibly rendered and recoverable through token re-entry or bounded refresh; refresh repeats
      only the read-only Dashboard query.
- [ ] Dashboard code uses shared UI primitives and TanStack Query; no Dashboard view/query/retry
      action creates work, calls Providers, grants authority or mutates Storage.
- [ ] Python serves the built V2 artifact at the documented prefix with GET-only handling and the
      existing security/header/API boundaries intact, while all existing V1 `/ui` routes remain
      available and behaviorally unchanged.
- [ ] Vitest, React Testing Library, the minimal Playwright path and the required Python static/auth/
      safety regressions pass, or any unavailable external browser gate is explicitly reported as
      `SKIP/UNAVAILABLE` rather than inferred successful.
- [ ] The checkpoint contains only this Task, excludes `config/alist.json` and private artifacts,
      passes `git diff --check`, and records the actual build/test commands and results.

## Required Tests

Run from the repository root after implementation; use the repository lockfile/tooling selected by
the Developer:

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
.venv/bin/python -m unittest discover -s tests
.venv/bin/python -m compileall -q mediaflow tests scripts
scripts/docker_release_security_smoke_test.py
git diff --check
```

If the selected package manager or script names differ, the Developer must record the exact
repository-equivalent commands and why. Docker/browser availability must be recorded explicitly;
no production service or credential may be substituted for an unavailable local gate.

## Non-goals

- Work outside the Slice 30 Contract or implementation of Slice 31-36 behavior.
- Complete V2 operator shell/navigation, Files/FileIndex, Tasks/Jobs, Reviews/Recovery,
  Configuration/Settings or any other later application surface.
- Final Docker multi-stage image/Compose packaging, production release smoke expansion or `/ui`
  cutover/legacy UI retirement; these require a follow-up Task while Slice 30 remains ACTIVE.
- Any new backend endpoint, API redesign, BFF/server-for-frontend, frontend-owned domain authority,
  Provider/Storage adapter, execution policy, Task/Job mutation, schedule or notification behavior.
- Built-in username/password identity, Cookie Sessions, OIDC, reverse-proxy identity integration,
  token persistence, token refresh, CDN runtime dependency, SSR, Next.js, React Server Components,
  micro-frontends, Redux-by-default or a Node production server.
- Production credentials, real external services, `config/alist.json`, private paths, generated
  runtime databases, unrelated refactors, optional proof or P2/P3 cleanup.
- Treating retry as execution/recovery authority or changing any OrganizerExecutor, DryRun,
  overwrite/delete, conflict, recovery-fencing or Storage-mutation safety rule.

## Developer Completion Report

### Changed Files

Implementation checkpoint `46859e846d44a964e1cbcf8ef4acde37328c7660` (51 files, +6726/-5):

- New frontend boundary `web/` (45 files): `package.json` + `package-lock.json`, Vite/Vitest/
  Playwright/ESLint/Prettier/TS configs, `index.html`, `public/favicon.svg`, and `src/` with
  `app/` (App, providers, query-client), `routes/router.tsx`, `features/dashboard/` (page, view,
  query) + `features/entry/EntryPage.tsx` (+ RTL tests), `entities/dashboard/dashboard.ts` (+ tests),
  `shared/api/` (api-client, api-errors, auth-store, auth-context, tests), `shared/auth/AuthControls.tsx`,
  `shared/ui/` (AppShell, StatusBanner, CountGrid, RefreshControl, Button, TextField, styles.css),
  `tests/` (setup, utils, fixtures, e2e/dashboard.spec.ts, e2e fake-server.mjs), and `web/.gitignore`.
- `mediaflow/interfaces/v2_ui.py` (new): read-only built-artifact static boundary for `/ui-v2/`.
- `mediaflow/interfaces/service_api.py`: dispatch `/ui-v2` prefix to the V2 static boundary before
  the `/api/v1` routing; V1 `/ui` assets and `/api/v1/*` handling untouched.
- `tests/test_v2_ui.py` (new): 11 Python static/coexistence/safety tests.
- `README.md`, `docs/architecture.md`: V2 entry prefix, token model, build-only Node role,
  local verification commands, migration coexistence, factual Slice 30 implementation status.
- `.dockerignore`: exclude `web/node_modules`, `web/dist`, coverage and Playwright artifacts from
  the build context (the Docker image itself is unchanged; packaging is a follow-up Task).
- This recording commit adds the Developer Completion Report to `TASK.md` (carrying B's planned
  Task into the checkpoint).

### Implemented

- **Frontend source/runtime boundary (RO-1):** first-class `web/` React 19 + TypeScript (strict) +
  Vite 8 project with committed lockfile and deterministic `format:check`/`typecheck`/`lint`/
  `test`/`build`/`test:e2e` scripts; explicit app/route/feature/entity/shared ownership; TanStack
  Router (code-based route tree, basepath `/ui-v2`) and TanStack Query as the single query/cache
  boundary. No frontend code in Python domain/application modules; no second backend service.
- **Central typed API + auth boundary (RO-2):** one `fetchDashboard` client for the existing
  `GET /api/v1/dashboard` contract with the bounded `recentLimit=10` query; strict normalization
  into frontend-owned types (unknown fields ignored, any missing/wrong field = malformed);
  explicit `unauthorized`/`forbidden`/`unavailable`/`rejected`/`malformed` categories with fixed
  bounded secret-free messages (no server message, header, exception or payload passthrough);
  Bearer token accepted only through the V2 entry into a memory-only store (no localStorage,
  sessionStorage, IndexedDB, cookies, URL/query/hash, telemetry); input cleared after connect;
  Disconnect clears token + query cache. No login/session/refresh/bypass added.
- **Read-only Dashboard proving path (RO-3, RO-4):** route flow Router → Dashboard route →
  TanStack Query → central client → existing Python API → typed model → shared primitives.
  Visible loading, honest empty (files/tasks/jobs all zero), success (counts + redacted recent
  failures), categorized error, unauthorized and forbidden states, all derived from the bounded
  API result; recovery via token re-entry (explicit disconnect) or bounded Refresh that repeats
  only the same read-only GET (no auto-retry, no window-focus refetch, no other request).
- **Python static coexistence boundary (RO-5, RO-7):** `/ui-v2`, `/ui-v2/` and deep client routes
  serve the built entry document; known built assets serve with allowlisted content types; dotted
  paths, traversal (`..`) and non-allowlisted file types fail closed 404; missing artifact fails
  closed; GET-only (405 otherwise); responses reuse the existing `_static_response` header policy
  (no-store, CSP, nosniff, referrer/permissions policy). V1 `/ui` bytes/headers/method behavior
  unchanged and `/api/v1/*` auth semantics preserved. Asset root resolves from
  `MEDIAFLOW_UI_V2_ASSET_ROOT` (deployment) or the checkout's `web/dist`; source checkout produces
  the deterministic served artifact via `npm --prefix web run build`; no Node process is needed to
  serve.
- **Tests and docs (RO-6, RO-8):** Vitest + RTL cover normalization, client categories, memory-only
  token behavior, every Dashboard state, bounded refresh, entry connect/disconnect and cache
  clearing; a minimal Playwright path proves the built/static route, the authenticated GET with
  Bearer header, no token display/persistence, unauthorized→re-entry recovery and the distinct
  forbidden state; Python tests cover V2 static routes, V1/V2 coexistence, GET-only, headers and
  the no-repository/Storage side-effect boundary. README/architecture document the boundary; the
  existing legacy UI/API/security tests are retained and green.

### Tests and Results

All commands from repository root; Test Level T4 battery, all PASS:

- `python3 scripts/check_governance.py` — PASS
- `npm --prefix web ci` — PASS (lockfile install, 0 vulnerabilities)
- `npm --prefix web run format:check` — PASS (Prettier)
- `npm --prefix web run typecheck` — PASS (tsc, strict, both project configs)
- `npm --prefix web run lint` — PASS (ESLint flat config)
- `npm --prefix web run test -- --run` — PASS (5 files, 44 tests: Vitest + RTL)
- `npm --prefix web run build` — PASS (`web/dist/index.html` + 2 hashed assets, base `/ui-v2/`,
  no inline script/style → CSP-compatible)
- `npm --prefix web run test:e2e` — PASS (3 Playwright tests, Chromium headless shell v1243,
  against built artifact + local fake API only)
- `.venv/bin/ruff format --check .` — PASS (406 files)
- `.venv/bin/ruff check .` — PASS
- `.venv/bin/python -m unittest discover -s tests` — PASS (1404 tests, 7 skipped)
- `.venv/bin/python -m compileall -q mediaflow tests scripts` — PASS
- `scripts/docker_release_security_smoke_test.py` — PASS ("Release-security smoke acceptance
  passed.") against implementation checkpoint 46859e8… (clean `git archive HEAD` checkout, image
  build, four-service stack, non-root/mount/RBAC/redaction/canary evidence). Docker was available;
  no gate was skipped. Note: the image does not yet contain the V2 artifact — Docker/Compose
  packaging of `/ui-v2/` is the explicitly deferred follow-up Task, so the smoke exercised the
  unchanged V1 surface.
- `git diff --check` — PASS

The 7 unittest skips are pre-existing environment-gated suites unrelated to this Task (real
SMB/S3/OpenList acceptance matrices, storage endurance profiles, symlink availability). They were
not skipped or weakened by this Task.

### Decisions

- **Code-based TanStack Router tree** instead of the file-based router plugin: one proving route
  pair needs no codegen; route ownership stays explicit in `src/routes/router.tsx` with basepath
  `/ui-v2` and a `createAppRouter` factory so tests can inject memory history.
- **Static serving = built-artifact map + allowlist** loaded once per process (thread-safe, reset
  hook for tests), with `MEDIAFLOW_UI_V2_ASSET_ROOT` for deployment layouts. Chosen over importing
  artifact bytes into Python source so the committed tree stays source-only and the served bytes
  are exactly the deterministic build output. Trade-off: rebuilds need a process restart
  (documented in `v2_ui.py`).
- **SPA fallback policy:** entry document serves non-dotted unknown paths; any dotted final
  segment, `..` part or non-allowlisted type is 404, so only built bytes ever leave the process.
- **Fixed category messages** instead of forwarding server error text: bounded by construction,
  immune to provider/exception/path leakage; the client still preserves the 401/403 semantics.
- **Empty state = files+tasks+jobs all zero** (the honest live state; zeros are never replaced by
  estimates). `recentLimit=10` is an explicit named constant matching the API default.
- **Playwright path uses one Node fake server** (static `/ui-v2/` from `web/dist` + fake
  `/api/v1/dashboard`) rather than the real Python stack — the Task allows a local fake, and it
  keeps the browser gate hermetic; the Python static/auth boundary is covered by
  `tests/test_v2_ui.py` against the real WSGI app.
- **Recovery flow through explicit disconnect:** after a rejected 401, the entry shows the
  connected state until the operator disconnects; e2e proves that honest path rather than
  auto-clearing auth on 401.

### Remaining In-Slice Work

- Docker image/Compose packaging of the V2 artifact and release smoke expansion for `/ui-v2/`
  (explicit follow-up Task in this Task's non-goals; the current image serves V1 `/ui` only).
- Slice 30 Required Outcome reconciliation (RO-5 Docker artifact evidence) and any further Tasks
  B plans from the Contract — not defined here.

### Risks / Deviations

- Playwright required `npx playwright install chromium` plus `playwright install-deps` (apt) in
  this environment; browsers/system deps are not committed. On a machine without them, `test:e2e`
  must be reported SKIP/UNAVAILABLE rather than inferred.
- The static artifact is process-cached after first V2 request; serving a fresh `npm run build`
  requires an application restart until the packaging Task changes the mechanism.
- Default asset root assumes a repository checkout layout; installed-wheel/container deployments
  must set `MEDIAFLOW_UI_V2_ASSET_ROOT` until Docker packaging lands (documented in README).
- No unavailable external gate in this run: Docker and Chromium were both available and used; no
  production credential, media, Storage or external service was touched.
- The B-planned Task 30.1 content of `TASK.md` enters Git history with this recording commit
  (no standalone planning commit existed in the working tree when this Task started).

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: 46859e846d44a964e1cbcf8ef4acde37328c7660
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
