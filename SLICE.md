# Slice 30 — V2 Frontend Platform & Architecture

This is the A-owned Slice Contract. It follows the V1.0.0 release freeze and V2 activation
checkpoints; Slice 29 remains PASS / CLOSED and is not reopened.

~~~
Slice ID: 30
Name: V2 Frontend Platform & Architecture
Owner: A — Slice Owner / Architect / Final Reviewer
Status: ACTIVE
Base SHA: 7c7c602c6531c60ddf2d6678857e2ef76c3860b6
Implementation Head: NOT SET
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
Head SHA: NOT SET

Required Outcomes:
- RO-1 through RO-8 — NOT STARTED; B must report each outcome independently.

Implemented:
- No implementation. This is the committed A-owned Contract and architecture boundary.

Tasks completed:
- None. B may plan Task 30.1 after this Contract checkpoint.

Final Tests:
- Governance/release validation belongs to the V2 activation and Slice implementation checkpoints.

Safety Evidence:
- V1.0.0 release baseline and existing Python authority remain unchanged by the Contract.

Known Non-blocking Issues:
- None recorded at Slice activation.

Explicitly Deferred:
- All items in the Explicitly deferred section above.

Documentation Reconciliation Needed:
- A will reconcile factual CURRENT/TARGET statements at Slice closure without extending the
  reviewed Base..Implementation Head range.

Decision: NOT READY FOR A REVIEW
~~~

## Review state

~~~
Slice Status: ACTIVE
Implementation Head: NOT SET
P0/P1 Defects: None known at activation; no implementation has started
Next Action: B PLANS TASK 30.1 FROM THIS COMMITTED CONTRACT
~~~
