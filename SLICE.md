# Slice 30 — V2 Frontend Platform & Architecture

This is the A-owned Slice Contract. It follows the V1.0.0 release freeze and V2 activation
checkpoints; Slice 29 remains PASS / CLOSED and is not reopened.

~~~
Slice ID: 30
Name: V2 Frontend Platform & Architecture
Owner: A — Slice Owner / Architect / Final Reviewer
Status: READY FOR A REVIEW
Base SHA: 7c7c602c6531c60ddf2d6678857e2ef76c3860b6
Implementation Head: 6953b87afa09e61ff62ffea5eb2a9a7d96c55492
~~~

The Base is the actual V2 activation commit immediately before Slice 30 implementation begins. It
must not move when B plans Tasks or when Developer implementation starts. The first implementation
Task is not part of this A planning checkpoint.

## V2 program boundary

V2 is an active release/program line on main, not a single mega-Slice. The independently reviewable
program is recorded in docs/roadmap.md:

~~~
Slice 30 — V2 Frontend Platform & Architecture
Slice 31 — Operator Shell & Information Architecture
Slice 32 — Library & Files Experience
Slice 33 — Operations Workspace
Slice 34 — Review & Recovery Workspace
Slice 35 — Configuration Administration
Slice 36 — V2 Parity, Accessibility & Legacy UI Retirement
~~~

This Contract covers only Slice 30. It may establish reusable platform boundaries and one bounded
Dashboard proving path, but it must not absorb the later application work listed above.

## User goal and vertical journey

**User goal:** an authenticated operator can open a V2 Dashboard and receive a trustworthy, typed,
read-only operational summary through the new frontend architecture while the existing Python API,
RBAC and safety authority remain unchanged.

**Entry:** the documented V2 static entry point (prefer /ui-v2/ during migration, or an equivalent
explicitly documented prefix) served by the existing MediaFlow Python application. The operator
supplies the existing API-principal Bearer token through the approved in-memory interaction.

**Visible state:** the route shows authentication/permission state, loading state, a bounded typed
Dashboard response, an honest empty state, a safe categorized error state, and a forbidden/expired
principal state. It never displays a token after the entry interaction or invents unavailable data.

**Action:** the operator may refresh the query and follow bounded Dashboard links into later V2
surfaces. Slice 30 Dashboard actions are read-only; no view, query, route transition or error retry
may create a Job, Task, Provider request, execution authority or Storage mutation.

**Success:** the Dashboard renders data from the existing versioned Python API through the central
typed API client and TanStack Query, with shared UI primitives, a production Vite build, Python
static serving, and automated unit/component/browser evidence.

**Failure:** invalid or expired credentials, 401/403 permission denial, unavailable API, malformed
response, empty data, or build/static-serving failure is identified at the affected boundary with a
bounded safe message. Raw exceptions, headers, tokens, cookies, provider payloads and private paths
are not exposed.

**Recovery:** the operator can re-enter a token in memory, refresh the bounded query, correct the
deployment/static asset boundary, or follow the documented next action. Retry is not presented as a
substitute for an execution or recovery authority, and no backend work is replayed by a read-only
Dashboard attempt.

## Required Outcomes

| ID | Required Outcome | Initial State |
|---|---|---|
| RO-1 | **First-class frontend boundary.** A project-owned React + TypeScript + Vite SPA source tree has explicit app, route, feature, entity and shared ownership boundaries, with no return to a monolithic app.js pattern. | The released V1 UI is an embedded dependency-free static surface and no V2 frontend source tree exists. |
| RO-2 | **Authoritative typed client and auth boundary.** V2 uses one central typed API boundary for existing /api/v1/* semantics, preserves API-principal Bearer authentication, keeps the token memory-only, and represents 401/403 and permission decisions explicitly. | The V1 UI and API are authoritative; no V2 client boundary exists. |
| RO-3 | **Vertical Dashboard proof.** Router → Dashboard route → TanStack Query → central API client → existing Python API → typed model → shared UI primitives is exercised by a coherent read-only user path. | No V2 route or query path exists. |
| RO-4 | **Honest state and safety presentation.** The Dashboard proves loading, empty, success, error, unauthorized/forbidden and bounded refresh behavior without fabricating data or creating side effects. | V1 UI behavior is covered by legacy tests; no component-level V2 state proof exists. |
| RO-5 | **Production deployment boundary.** Vite output is buildable and served by the existing Python/MediaFlow application and Docker artifact without a Node production runtime, a second HTTP service, SSR, or CDN dependency. | V1 serves its embedded static assets from Python and has no V2 build artifact. |
| RO-6 | **Modern frontend test foundation.** Vitest covers utility/state/permission logic, React Testing Library covers Dashboard behavior, and a minimal Playwright browser path proves the built/static V2 route. Existing Python API, security, CSP and deployment tests remain intact. | New frontend behavior would otherwise be asserted through exact legacy JavaScript source strings. |
| RO-7 | **Migration coexistence.** The V1 Operator UI remains available and documented while V2 is introduced behind a clear boundary; no /ui cutover or legacy deletion is hidden in this Slice. | V1 /ui/ is the supported management surface. |
| RO-8 | **Authority and security preservation.** The proving path does not duplicate domain/execution authority, alter API semantics, weaken RBAC, introduce token persistence, or bypass explicit execution and OrganizerExecutor gates. | V1 authority and safety boundaries are complete and released. |

## Required surfaces

1. **Frontend source surface.** A first-class web/ (or repository-justified equivalent) with
   package/build/type configuration and explicit app, routes, features, entities and shared boundaries.
2. **Routing surface.** A client-side router with a documented V2 entry and Dashboard route; route
   ownership is explicit and does not require a Node server or server-side rendering.
3. **API/query surface.** One typed API client and one query/cache boundary consume the existing
   authenticated Dashboard endpoint and normalize safe 401/403/network/shape failures.
4. **Authentication/permission surface.** Bearer token input and request headers exist only in
   runtime memory; permission-driven presentation is visible and uses existing API/RBAC outcomes.
5. **Shared UI surface.** Project-owned primitives and styles cover the Dashboard shell, loading,
   empty, error, forbidden and bounded refresh states without feature-specific API duplication.
6. **Build/serving surface.** The production build emits deterministic static assets and the Python
   application serves them with existing headers, CSP, cache and /api/v1/* boundaries intact.
7. **Test surface.** Vitest, React Testing Library and a minimal Playwright path are wired for the
   proving behavior; Python tests continue to cover API/static/security/deployment contracts.
8. **Migration/documentation surface.** The V1 /ui and V2 entry coexist, with architecture,
   developer and deployment documentation stating the boundary and Node-only build role.

## Adopted target architecture

Repository evidence shows no blocker to the requested target, so Slice 30 adopts it as its
architecture contract:

- React and TypeScript with Vite for a client-side SPA;
- TanStack Router for route ownership and TanStack Query for server-state fetching/caching;
- feature-first modular structure with explicit app, routes, features, entities and shared boundaries;
- a central typed API client, auth/permission boundary and project-owned design-system foundation;
- Vitest, React Testing Library and a Playwright foundation for new V2 coverage;
- Python remains the only production server runtime; Node is build/development tooling only;
- Vite output is served by the existing MediaFlow Python application and Docker runtime.

The implementation may choose equivalent package versions or a better repository-local directory
layout only when it preserves these properties and records the reason in the Task checkpoint. It
must not introduce Next.js, SSR, React Server Components, a Node production server, micro-frontends,
Redux by default, or CDN runtime dependencies without a concrete repository blocker and an explicit
A-reviewed architecture change.

## Safety and authority invariants

- Python application/domain services remain authoritative. The frontend does not reimplement
  Recognition, Metadata, Naming, Classification, OrganizePlan, Task, Result or execution decisions.
- Existing /api/v1/* semantics, validation, state, RBAC, audit and error categories remain the
  authority shared by API and Web. Slice 30 does not redesign API contracts to fit a component.
- The API-principal Bearer token is accepted through the existing boundary and remains memory-only.
  No localStorage, sessionStorage, IndexedDB token persistence, frontend-managed auth cookies,
  URL/query-string token, or token-bearing telemetry is permitted.
- Read-only Dashboard queries do not create work, call Providers, inspect arbitrary Storage, issue
  execution authority or mutate media. Loading/error/retry behavior is side-effect bounded.
- Explicit confirmation, one-shot execution authority, DryRun versus mutation distinction, RBAC,
  recovery/continuation fencing and OrganizerExecutor-only Storage mutation remain unchanged.
- Automated decisions and API errors shown by V2 are bounded and secret-free. Tokens, cookies,
  authorization headers, credentials, private host paths and raw provider/exception payloads never
  enter UI state, logs, tests, exports or screenshots.
- Production deployment remains Python/MediaFlow/Waitress plus static assets. Node dependencies are
  build-time inputs and are not copied into or required by the runtime image.
- The V1 /ui remains usable throughout Slice 30. No route replacement, deletion or final cutover
  is accepted until the later parity/retirement Slice.

## Explicitly deferred

- Slice 31 operator shell and complete information architecture beyond the bounded Dashboard route.
- Slice 32 Files/FileIndex migration, Storage browsing, file detail and media actions.
- Slice 33 complete Operations workspace, including Tasks, Jobs, schedules and Notifications.
- Slice 34 review, conflict, checkpoint and per-item recovery workspace.
- Slice 35 Configuration/Settings/forms, revision evidence, activation and administration migration.
- Slice 36 parity, accessibility completion, /ui cutover and legacy UI retirement.
- Any new backend endpoint or domain behavior not required to consume an existing Dashboard contract;
  API redesign, BFF/server-for-frontend and frontend-owned domain authority.
- Built-in username/password identity, Cookie Sessions, OIDC, reverse-proxy identity integration,
  token persistence, token refresh service or a new authentication system.
- Next.js, SSR, React Server Components, Node production serving, micro-frontends, Redux by default,
  CDN runtime dependencies and direct public Internet exposure.
- Provider switching, additional Metadata Providers, Storage adapters, execution policy changes,
  uncertain-mutation replay, rollback, overwrite/delete defaults and any V1 product expansion.

## Slice acceptance criteria

1. The V2 frontend source boundary is first-class, typed, feature-owned and documented; no frontend
   production code is placed in the Python domain/application modules.
2. An authenticated operator can open the documented V2 Dashboard route and trace a real request
   through the router, TanStack Query, central API client, existing Python API and typed model.
3. Loading, empty, successful, categorized error, unauthorized and forbidden states are user-visible,
   bounded, tested and recoverable without creating Jobs, Tasks, Provider calls or Storage mutation.
4. The token is held only in browser memory, absent from URLs and persistent browser stores, and the
   V2 permission presentation matches existing API-principal/RBAC responses.
5. Shared UI primitives and styles are used by the proving path; state/query/auth behavior is not
   hidden in one monolithic component or duplicated across feature routes.
6. A production Vite build is served by the existing Python application and Docker artifact with
   static headers/CSP/cache policy and /api/v1/* behavior preserved, without Node at runtime.
7. Vitest, React Testing Library and a minimal Playwright browser path pass for the Dashboard proof;
   legacy UI tests are retained, and Python security/API/deployment tests remain green.
8. The V1 /ui remains available, the V2 migration boundary is documented, and no later Slice
   behavior is claimed complete.

## Final validation expectations

- python3 scripts/check_governance.py passes with this committed Contract, Slice 30 Roadmap row
  ACTIVE, no active Task before B planning, and Base SHA 7c7c602c… unchanged.
- Frontend quality gates defined by the committed Task pass using the repository's lockfile/tooling:
  format/type/lint, Vitest, React Testing Library, production Vite build and minimal Playwright
  browser smoke. Tests must run against local fakes or the existing local API, never production
  credentials, media or Storage.
- The existing Python gates remain green: ruff format --check ., ruff check ., full unittest
  discovery, compileall, API/static header/CSP tests, release-security checks and git diff --check.
- Static serving verifies cache/CSP/response boundaries, API authentication and permission outcomes,
  and absence of token persistence or secret-bearing browser/network evidence.
- Slice final validation must exercise the complete Dashboard journey and report unavailable Docker,
  browser or external-service gates as SKIP/UNAVAILABLE, never as inferred success.

## Closure packet

~~~
Slice: 30 — V2 Frontend Platform & Architecture
Base SHA: 7c7c602c6531c60ddf2d6678857e2ef76c3860b6
Head SHA: 6953b87afa09e61ff62ffea5eb2a9a7d96c55492

Required Outcomes:
- RO-1 — COMPLETE: project-owned typed React/Vite feature-first frontend boundary.
- RO-2 — COMPLETE: central typed API client, explicit 401/403 outcomes and memory-only Bearer auth.
- RO-3 — COMPLETE: Router → Query → client → existing Python API → typed model → shared UI path.
- RO-4 — COMPLETE: loading, empty, success, categorized failure, auth denial and bounded refresh proof.
- RO-5 — COMPLETE: locked Vite build is baked into and served from the Python Docker artifact with
  no Node production runtime or second service.
- RO-6 — COMPLETE: Vitest/RTL and Playwright foundations plus retained Python security/API tests.
- RO-7 — COMPLETE: V1 `/ui` and separate `/ui-v2/` coexist in source and production image.
- RO-8 — COMPLETE: Python/RBAC/execution authority and OrganizerExecutor-only mutation are preserved.

Required Surfaces:
- Frontend source surface — COMPLETE.
- Routing surface — COMPLETE.
- API/query surface — COMPLETE.
- Authentication/permission surface — COMPLETE.
- Shared UI surface — COMPLETE.
- Build/serving surface — COMPLETE in source checkout and production Docker artifact.
- Test surface — COMPLETE.
- Migration/documentation surface — COMPLETE for Slice 30; A reconciliation items are listed below.

Implemented:
- A typed React/TypeScript/Vite SPA with TanStack Router/Query, central bounded Dashboard client,
  memory-only API-principal auth, shared UI primitives and the complete read-only Dashboard journey.
- Python GET-only `/ui-v2/` static serving with safe headers, deep-route fallback, fail-closed asset
  handling and unchanged V1 `/ui` plus `/api/v1/*` authority.
- A locked multi-stage Docker build that copies only Vite output into the final non-root Python image,
  with image/live release-security proof of V1/V2 coexistence and no Node runtime.

Tasks completed:
- Task 30.1 — V2 Frontend Foundation and Read-Only Dashboard Proof — PASS at `1630c55404770f2657f6f4d99bfa1b08d46cf876`.
- Task 30.2 — Production Docker V2 Artifact Integration and Release Proof — PASS at `6953b87afa09e61ff62ffea5eb2a9a7d96c55492`.

Final Tests:
- `python3 scripts/check_governance.py` — PASS.
- `npm --prefix web ci --include=dev` — PASS; 254 packages, 0 vulnerabilities.
- Frontend format/type/lint — PASS; Vitest/RTL 45/45; production Vite build PASS; Playwright 3/3.
- Ruff format/check and compileall — PASS; focused container/static/security tests 33/33.
- Full unittest discovery in an isolated clean clone — PASS, 1406 tests, 7 skipped environment-gated
  SMB/S3/OpenList/symlink/POSIX suites; no unavailable required local gate.
- `python3 scripts/docker_release_security_smoke_test.py` — PASS with Docker available: exact clean
  candidate image, four-service stack, baked V2 artifact, no Node runtime, static headers/coexistence,
  RBAC, redaction, non-root/mount and zero-side-effect evidence all passed.
- `git diff --check` — PASS.

Safety Evidence:
- Dashboard entry/query/refresh uses only bounded GET requests and creates no Job, Task, Provider call,
  execution authority or Storage mutation.
- Bearer token remains runtime-memory-only and is absent from persistent browser stores, URLs,
  rendered output, image, logs and exported evidence.
- Static serving is GET-only, allowlisted/fail-closed and repository/Storage/Provider independent.
- The production image remains non-root and Python-only; V1 API/RBAC, DryRun, confirmation,
  recovery fencing and OrganizerExecutor-only mutation boundaries are unchanged.
- Release tests used fake tokens, temporary Compose state and an isolated clean clone; private
  configuration, `config/alist.json`, operator media and the existing `.mediaflow` database were not used.

Known Non-blocking Issues:
- P2: The pre-existing CWD-relative test/runtime-database isolation hazard can make root-worktree CLI tests
  observe or write `.mediaflow/mediaflow.sqlite3`; Slice-final full regression was therefore run in an
  isolated clean clone. This Slice does not change that unrelated test-infrastructure behavior.
- P2: `node:22-bookworm-slim` floats within the Node 22 line; frontend packages remain lockfile-pinned.
- P3: Existing unittest ResourceWarnings and 7 environment-gated skips remain unchanged.

Explicitly Deferred:
- Slice 31 operator shell and complete information architecture beyond the bounded Dashboard route.
- Slice 32 Files/FileIndex migration, Storage browsing, file detail and media actions.
- Slice 33 complete Operations workspace, including Tasks, Jobs, schedules and Notifications.
- Slice 34 review, conflict, checkpoint and per-item recovery workspace.
- Slice 35 Configuration/Settings/forms, revision evidence, activation and administration migration.
- Slice 36 parity, accessibility completion, `/ui` cutover and legacy UI retirement.
- New backend/domain behavior, API redesign/BFF and frontend-owned domain authority.
- New identity/session/OIDC systems, token persistence/refresh, SSR/Node production serving,
  micro-frontends, Redux-by-default and CDN runtime dependencies.
- Provider/Storage expansion, execution-policy changes, uncertain-mutation replay, rollback and any
  V1 product expansion listed in the Contract remain deferred.

Documentation Reconciliation Needed:
- A should reconcile stale activation-era statements in the Chinese canonical specification,
  `docs/product-experience.md`, `docs/v2-requirements.md` and `docs/roadmap.md` that still say Slice 30
  has no implementation/Task and record the final Roadmap/Progress closure facts if A returns PASS.
- README, deployment and architecture guidance already describe the implemented V2 build/runtime
  boundary; A should verify those facts without extending Base..Implementation Head.

Decision: SLICE READY FOR A REVIEW
~~~

## Review state

~~~
Slice Status: READY FOR A REVIEW
Implementation Head: 6953b87afa09e61ff62ffea5eb2a9a7d96c55492
P0/P1 Defects: None found by B in Base..Implementation Head or Slice-final validation
Next Action: A FINAL REVIEW
~~~
