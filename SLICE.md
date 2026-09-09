# Slice 31 — Operator Shell & Information Architecture

This is the A-owned Slice Contract for the next independently reviewable V2 capability after
Slice 30. Slice 30 remains `PASS / CLOSED` in Git, Roadmap and Progress history and is not reopened.

~~~
Slice ID: 31
Name: Operator Shell & Information Architecture
Owner: A — Slice Owner / Architect / Final Reviewer
Status: READY FOR A REVIEW
Base SHA: 2e7aceb50750fb54689ab26bfd1214b8e36c25f8
Implementation Head: 45cb1d4cdda6cf46a6d6699600bc4a4563efc06b
~~~

The Base is the actual committed `main` checkpoint immediately before Slice 31 activation and
implementation. It must not move when B plans Tasks or Developer work begins. The Contract and its
Roadmap activation commit follow the Base and are governance changes, not Slice implementation.

## V2 program boundary

V2 is a sequence of independently accepted user capabilities:

~~~
Slice 30 — V2 Frontend Platform & Architecture — PASS / CLOSED
Slice 31 — Operator Shell & Information Architecture — ACTIVE
Slice 32 — Library & Files Experience — PLANNED
Slice 33 — Operations Workspace — PLANNED
Slice 34 — Review & Recovery Workspace — PLANNED
Slice 35 — Configuration Administration — PLANNED
Slice 36 — V2 Parity, Accessibility & Legacy UI Retirement — PLANNED
~~~

This Contract owns the shared V2 shell, operator-oriented navigation model and migration-aware route
experience. It does not absorb the business journeys assigned to Slices 32–36.

## User goal and vertical journey

**User goal:** within the current API-principal Bearer authentication architecture, an operator can
enter MediaFlow V2 at the root or a supported deep link, understand where they are and which product
areas are available, navigate the shared information architecture on wide or narrow screens, and
recover from connection, permission, unavailable-route or migration-boundary failures without
learning backend protocols or losing orientation.

**Entry:** open `/ui-v2/` or a documented V2 deep route. An unauthenticated operator is guided through
the existing memory-only API-principal connection interaction and then returned to the intended safe
V2 destination when possible. Direct entry, refresh and Python-served deep-route fallback use the
same route ownership.

**Visible state:** a persistent shell shows MediaFlow identity, the active product area and page
context, connection state, primary operator-oriented destinations, current V2 availability and an
honest handoff to the current V1 Web surface for journeys not yet migrated. Loading, unauthorized,
forbidden, unavailable and not-found states remain inside the shell with bounded, action-oriented
recovery. Raw tokens and implementation-only identifiers are never displayed as navigation concepts.

**Action:** connect or disconnect, open Dashboard, move among the V2 product-area routes, use keyboard
or narrow-screen navigation, recover to a valid parent/home destination, or follow an explicit Web
migration handoff. Merely opening, preloading or navigating the shell creates no Job, Task, Provider
request, execution authority or Storage mutation.

**Success:** the operator reaches the intended available V2 page or a truthful migration handoff,
retains clear location and connection context, and can continue through a coherent responsive and
keyboard-usable shell. The existing Dashboard remains functional through the central typed API/query
boundary, and future feature Slices can attach routes without duplicating shell, auth or navigation
logic.

**Failure:** an absent/invalid principal, 401/403 response, unknown route, unavailable V2 area,
failed read or static/deep-route problem is distinguished without raw exceptions, secrets or false
availability. The shell does not strand the operator on a blank page or imply that a later Slice is
already implemented.

**Recovery:** connect or re-enter the current API-principal token in memory, retry only the failed
read, return to Dashboard or a valid parent route, open the current V1 Web UI for an explicitly
unmigrated journey, or follow the stated deployment correction. Disconnect clears authentication
memory and authenticated query state; recovery never replays unknown work.

## Product Experience / UX constraints

- Navigation is organized around operator goals, not Python modules, endpoints, Task state-machine
  internals or implementation identifiers.
- The primary V2 areas are expressed coherently as Overview, Library, Operations, Review & Recovery,
  and Configuration (or wording proven clearer through user-facing acceptance) while preserving the
  Roadmap ownership of their actual business journeys.
- A destination is never a deceptive dead control. It either opens an implemented V2 surface or
  clearly states that migration is incomplete and offers the appropriate current Web continuation.
- The operator is not sent to CLI to complete an ordinary Web journey and is not asked to transfer a
  raw execution token as part of this shell. The existing API-principal entry remains a stated
  CURRENT identity boundary, not a claim that the final V2 identity experience is complete.
- Route and connection recovery asks only for new human intent. The shell does not repeat prompts or
  expose revision, grant, claim, fence or checkpoint IDs unless a later feature requires one for
  bounded diagnosis/support.
- Responsive and keyboard behavior is part of product completion, not optional polish. Final
  cross-feature parity and comprehensive accessibility/cutover acceptance remain owned by Slice 36.

## Required Outcomes

| ID | Required Outcome | Initial State |
|---|---|---|
| RO-1 | **Operator-oriented information architecture.** One typed, centralized navigation model defines the stable V2 product areas, labels, route ownership, availability/migration state and active-location semantics without mirroring backend modules. | The V2 router owns only entry and Dashboard routes; there is no shared destination model or product-area hierarchy. |
| RO-2 | **Persistent responsive application shell.** Authenticated and recoverable route states render inside a shared shell with brand, primary navigation, active page context and connection controls that remain usable across wide and narrow viewports. | `AppShell` is a header and main wrapper with no navigation, route context or narrow-screen interaction. |
| RO-3 | **Deep-link and authentication continuity.** Root entry, refresh and supported deep links share deterministic routing; an unauthenticated deep link reaches the connection boundary and returns to the intended safe route after connection, while disconnect clears token/query state and leaves an understandable recovery path. | Token entry always opens Dashboard and does not preserve an intended destination; auth handling is repeated at feature level. |
| RO-4 | **Truthful migration coexistence.** Every exposed destination distinguishes implemented V2 content from not-yet-migrated areas and offers a clear current Web continuation where appropriate, without claiming Slice 32–36 capabilities or removing V1 `/ui`. | Only Dashboard exists in V2; future areas have no shared availability or handoff semantics. |
| RO-5 | **Accessible navigation foundation.** The shell provides semantic landmarks, a main-content bypass, visible focus, keyboard-operable navigation, meaningful document/page titles and correct active-state semantics, with usable narrow-screen behavior. | Existing controls have local labels/focus styles, but there is no navigation landmark, skip path, route title model or mobile shell. |
| RO-6 | **Actionable route and permission states.** Not-found, unavailable, unauthenticated, unauthorized and forbidden outcomes preserve shell context and give the smallest valid next action; route retry/navigation does not create work or silently mutate state. | Dashboard owns several local states and the generic not-found route returns only to entry; no shared route-state contract exists. |
| RO-7 | **Reusable shell boundary and proof.** Route metadata, navigation, auth continuation, layout and state primitives remain feature-independent and are covered by focused unit/component tests plus a production-build browser journey. | Slice 30 provides the toolchain and primitives but only a bounded Dashboard proving path. |
| RO-8 | **Authority and coexistence preservation.** The shell keeps `/api/v1/*`, Python domain/application authority, memory-only Bearer handling, RBAC, V1 `/ui`, production static serving and OrganizerExecutor-only mutation unchanged. | These Slice 30/V1 boundaries are established and must not regress during shell work. |

## Required Surfaces

1. **Shell surface.** A feature-independent V2 layout owns brand, primary navigation, current-page
   context, main content, connection controls and narrow-screen navigation behavior.
2. **Information-architecture surface.** One typed destination/route metadata source maps operator
   areas, labels, availability and migration continuation without duplicating backend protocol names
   across components.
3. **Routing and deep-link surface.** TanStack Router owns root, Dashboard, product-area landing or
   migration routes, not-found recovery and intended-route continuation under `/ui-v2/`.
4. **Authentication/permission surface.** Existing memory-only principal state, connect/disconnect,
   401/403 presentation and query-cache clearing are composed once and remain backend-authoritative.
5. **Migration coexistence surface.** Available V2 routes and explicitly unmigrated journeys are
   distinguishable; V1 `/ui` remains reachable as the current Web product without token leakage or a
   false deep-link promise.
6. **Responsive/accessibility surface.** Semantic header/nav/main landmarks, skip-to-content, focus
   visibility/order, active-route indication, page titles and wide/narrow interaction are verified.
7. **Test surface.** Vitest/React Testing Library cover route, nav, auth and shell states; Playwright
   proves direct deep entry, connection continuation, keyboard/narrow navigation and V1/V2
   coexistence against local fakes/built assets.
8. **Documentation surface.** README, Product Experience and Architecture describe the implemented
   shell/IA and CURRENT migration boundary only after implementation evidence exists.

## Safety Invariants

- Python Application/Domain services and `/api/v1/*` remain authoritative. The shell does not
  reimplement permissions, domain decisions, work admission or execution policy.
- The API-principal Bearer token remains runtime-memory-only and is absent from localStorage,
  sessionStorage, IndexedDB, cookies, URLs, route state, rendered output, telemetry, logs and
  screenshots. V1 handoff must not transfer it through a URL or persistent browser mechanism.
- RBAC and backend permission checks remain authoritative. Navigation visibility or frontend route
  access never grants permission, execution authority or mutation admission.
- Rendering, preloading, refreshing or navigating the shell and migration routes performs no
  Storage access, Provider request, Job/Task creation, execution-authorization issuance or media
  mutation unless a later explicitly scoped feature owns such an action.
- Scanner, Parser, Recognition, Metadata, Naming, Classification and Planner remain zero-mutation;
  only OrganizerExecutor may invoke mutating Storage operations. No silent overwrite/delete or
  operation fallback is introduced.
- Active configuration continues to mean the exact immutable snapshot consumed by runtime. The
  shell must not synthesize Active state or expose stale UI state as backend authority.
- Unauthorized, forbidden, unknown and unavailable outcomes are bounded and secret-free. Raw
  headers, tokens, cookies, exception/provider payloads, private paths and credentials never enter
  public UI/test evidence.
- V1 `/ui`, existing API semantics, static headers/CSP/cache behavior and the Python-only production
  runtime remain intact. No Node production server, SSR, CDN runtime dependency or second HTTP
  service is introduced.
- `config/alist.json`, production credentials, private endpoints, operator media and local runtime
  state remain ignored/untracked and absent from checkpoints/tests.

## Explicitly Deferred

- Slice 32 Library & Files business journeys: real Storage browsing, FileIndex list/detail,
  search/filter, Scan/Preview/Organize entry and media actions.
- Slice 33 Operations Workspace: expanded Dashboard, Tasks, Jobs, schedules, Automation,
  Notifications and the complete Web-native interactive execution-authorization journey.
- Slice 34 Review & Recovery Workspace: Recognition/Metadata/Classification review, conflict,
  checkpoint, per-item recovery and bounded batch recovery workflows.
- Slice 35 Configuration Administration: Configuration, Settings, revision/test evidence,
  activation and managed object editing in V2.
- Slice 36 final parity, comprehensive cross-feature accessibility evidence, supported `/ui` cutover
  and V1 UI retirement.
- Any new backend endpoint, repository/schema/domain behavior, API redesign, BFF, frontend-owned
  permission/domain decision or execution-grant implementation.
- Built-in username/password identity, session/cookie authority, OIDC, reverse-proxy identity,
  token persistence/refresh/rotation or redesign of the current API-principal authentication model.
- Provider switching, new Metadata/Storage providers, processing/recovery policy changes, uncertain-
  mutation replay, rollback, overwrite/delete defaults or any V1 product expansion.
- SSR, React Server Components, Node production serving, micro-frontends, CDN runtime dependencies,
  native mobile clients, global search/command palette, localization and complete visual-theme work.

## Slice Acceptance Criteria

1. An operator entering `/ui-v2/` or a supported deep route can connect through the current
   memory-only principal boundary, reach the intended valid destination and remain oriented within a
   persistent responsive shell.
2. The operator can identify the active page and navigate the stable goal-oriented product areas;
   each exposed destination is either functional in V2 or truthfully offers the current V1 Web
   continuation without a dead end or CLI fallback.
3. Dashboard remains a working typed read-only route. Library, Operations, Review & Recovery and
   Configuration business capabilities are not falsely implemented or pulled forward from later
   Slices.
4. Connect, disconnect, 401/403, unavailable and not-found flows preserve useful route context and
   provide an actionable next step; disconnect removes token and authenticated query state.
5. Shell/navigation behavior is usable by keyboard and at narrow and wide viewports, with semantic
   landmarks, skip-to-content, visible focus, page title and active-route evidence. Slice 36 remains
   responsible for final cross-feature accessibility/parity/cutover acceptance.
6. Route navigation, migration placeholders/handoffs and shell rendering are zero-side-effect and
   leak no token, secret, raw exception, private path or implementation-only authority identifier.
7. The architecture remains feature-first with centralized typed route/navigation/auth ownership;
   feature pages do not duplicate the shell or bypass TanStack Router, Query or the central API
   client.
8. Automated unit/component/browser evidence covers entry, deep-link continuation, active
   navigation, responsive/keyboard use, 401/403, unavailable/not-found recovery, disconnect/cache
   clearing and unchanged V1/V2 coexistence.
9. Python API/RBAC/static/deployment behavior, the V1 `/ui`, memory-only Bearer model, CSP/cache
   policy and OrganizerExecutor-only mutation boundary remain unchanged and regression-covered.

## Final Validation Expectations

- `python3 scripts/check_governance.py` passes against the committed Slice 31 Contract and ACTIVE
  Roadmap row, with no active Task before B planning and Base SHA `2e7aceb5…` unchanged.
- Frontend lockfile/tooling gates pass: `npm --prefix web ci`, format check, TypeScript typecheck,
  ESLint, Vitest/React Testing Library, production Vite build and Playwright browser tests.
- Focused shell evidence covers root and direct deep entry, return-to-intended-route after connect,
  active navigation, keyboard and narrow viewport operation, page titles/landmarks, disconnect/query
  clearing, 401/403, not-found/unavailable recovery and truthful V1 migration handoff.
- Browser/network evidence proves token absence from DOM, URLs, persistent stores and logs, and
  proves shell navigation/handoff performs no hidden work-admission or mutation request.
- Existing Python V2 static-serving, API security/RBAC, CSP/header, V1 UI coexistence and release-
  security tests pass. The Docker release-security smoke test is run at Slice Final when Docker is
  available and reported `UNAVAILABLE` rather than inferred when it is not.
- Normal Python quality gates pass: Ruff format/check, full unittest discovery, compileall and
  `git diff --check`. Existing root-CWD private runtime state must not be deleted to make tests pass;
  use an isolated clean checkout when required and report both results truthfully.
- Tests use local fakes and temporary state only; no production credentials, user media, remote
  Storage or Metadata Provider is required.

## Closure Packet

~~~
Slice: 31 — Operator Shell & Information Architecture
Base SHA: 2e7aceb50750fb54689ab26bfd1214b8e36c25f8
Head SHA: 45cb1d4cdda6cf46a6d6699600bc4a4563efc06b

Required Outcomes:
- RO-1 — COMPLETE: one typed `destinationData` literal owns product-area labels, paths,
  availability, migration state, active-location semantics, the `DestinationPath` union and the
  runtime intended-route allowlist.
- RO-2 — COMPLETE: the authenticated and recoverable route experience uses one persistent,
  responsive shell with brand, navigation, page context and connection controls.
- RO-3 — COMPLETE: root entry, refresh and allowlisted deep links share deterministic routing;
  unauthenticated entry preserves the intended safe route in memory and disconnect clears token,
  continuation and authenticated query state.
- RO-4 — COMPLETE: Dashboard is identified as available V2 content, later product areas are
  truthful migration surfaces with a V1 Web continuation, and V1 `/ui` remains available.
- RO-5 — COMPLETE: semantic landmarks, skip-to-content, active-state semantics, page titles,
  visible focus and keyboard-usable wide/narrow navigation are implemented and browser-proven.
- RO-6 — COMPLETE: unauthenticated, rejected-authority, forbidden, unavailable and not-found
  states remain in shell context and expose bounded connection, retry or navigation actions.
- RO-7 — COMPLETE: route metadata, shell, auth continuation and authorized-read lifecycle are
  feature-independent and covered by unit/component plus production-build browser evidence.
- RO-8 — COMPLETE: existing Python API/domain authority, memory-only Bearer handling, RBAC, V1
  coexistence, static serving and OrganizerExecutor-only mutation boundaries are preserved.

Required Surfaces:
- Shell surface — COMPLETE.
- Information-architecture surface — COMPLETE.
- Routing and deep-link surface — COMPLETE.
- Authentication/permission surface — COMPLETE.
- Migration coexistence surface — COMPLETE.
- Responsive/accessibility surface — COMPLETE.
- Test surface — COMPLETE.
- Documentation surface — COMPLETE for implemented CURRENT shell/IA/auth-continuation facts; A
  reconciliation items are listed below.

Implemented:
- A centralized operator-oriented destination model and TanStack Router route tree for Overview,
  Library, Operations, Review & Recovery and Configuration, with honest implemented/migration
  availability and active-route semantics.
- A responsive application shell with semantic navigation, current-page context, narrow-screen
  disclosure, skip/focus/title support, connection controls, not-found recovery and V1 handoff.
- Feature-independent memory-only authentication continuation and authorized-read boundaries with
  deterministic deep-link recovery, explicit disconnect/cache clearing, 401 re-entry, 403
  distinction and bounded unavailable retry.
- Focused Vitest/RTL and Playwright evidence for routing, navigation, responsive/keyboard use,
  authentication/recovery, token secrecy, zero hidden work and V1/V2 coexistence.

Tasks completed:
- Task 31.1 — Operator shell, information architecture, and migration routes — PASS at
  `19c389421ed9db4f12e194e75cdb49e9582267ed`.
- Task 31.2 — Deep-link authentication continuity and actionable recovery — PASS at
  `45cb1d4cdda6cf46a6d6699600bc4a4563efc06b`.

Final Tests:
- `python3 scripts/check_governance.py` — PASS.
- `npm --prefix web ci` — PASS; 254 packages installed, 255 audited, 0 vulnerabilities.
- Frontend format/type/lint — PASS; Vitest/RTL 79/79 in 10 files; production Vite build PASS;
  Playwright Chromium 16/16.
- `.venv/bin/python -m unittest tests.test_v2_ui tests.test_release_security` — PASS, 17/17.
- Ruff format/check — PASS; 301 files already formatted; compileall — PASS.
- Root-CWD full unittest discovery — 1408 run, 6 failures and 7 skips. All 6 failures loaded the
  ignored local `config/alist.json` instead of isolated test configuration; no private values are
  reproduced in this packet.
- Full unittest discovery from an isolated clean detached worktree at the exact Implementation
  Head — PASS, 1408 tests, 7 environment-gated skips. This proves the root-CWD failures are
  pre-existing/private-runtime-state effects unrelated to Slice 31.
- `python3 scripts/docker_release_security_smoke_test.py` — PASS with Docker available: clean
  candidate image, four-service stack, V1/V2 static coexistence, headers, non-root execution,
  RBAC, redaction, exact Active snapshot and zero-side-effect denial checks passed.
- `git diff --check` — PASS for Base..Implementation Head and the B closure edits.

Safety Evidence:
- Shell rendering, routing, handoff and recovery issue no Storage/Provider request, Job/Task
  creation, execution authority or media mutation; browser network assertions allow only the
  operator-selected read-only Dashboard request/retry.
- Bearer material remains runtime-memory-only and absent from URLs, route state, rendered output,
  localStorage, sessionStorage, IndexedDB, cookies, logs, screenshots and V1 handoff.
- A 401 clears rejected authority and authenticated query cache without automatic replay; a 403
  retains the authenticated principal and never grants frontend authority.
- Python `/api/v1/*`, RBAC, CSP/cache/static serving, V1 `/ui`, immutable Active-snapshot authority
  and OrganizerExecutor-only mutation remain regression-covered and unchanged.
- Tests use local fakes and temporary/isolated state. `config/alist.json`, credentials, private
  endpoints and operator media are absent from Base..Implementation Head.

Known Non-blocking Issues:
- P2: the pre-existing root-CWD configuration-isolation hazard lets six Python tests read ignored
  local `config/alist.json`; the exact Implementation Head passes all 1408 tests in a clean
  worktree. Slice 31 neither changes nor conceals that unrelated test-infrastructure behavior.
- P3: existing sqlite `ResourceWarning` output and 7 environment-gated skips remain unchanged.

Explicitly Deferred:
- Slice 32 Library & Files business journeys: real Storage browsing, FileIndex list/detail,
  search/filter, Scan/Preview/Organize entry and media actions.
- Slice 33 Operations Workspace: expanded Dashboard, Tasks, Jobs, schedules, Automation,
  Notifications and the complete Web-native interactive execution-authorization journey.
- Slice 34 Review & Recovery Workspace: Recognition/Metadata/Classification review, conflict,
  checkpoint, per-item recovery and bounded batch recovery workflows.
- Slice 35 Configuration Administration: Configuration, Settings, revision/test evidence,
  activation and managed object editing in V2.
- Slice 36 final parity, comprehensive cross-feature accessibility evidence, supported `/ui` cutover
  and V1 UI retirement.
- Any new backend endpoint, repository/schema/domain behavior, API redesign, BFF, frontend-owned
  permission/domain decision or execution-grant implementation.
- Built-in username/password identity, session/cookie authority, OIDC, reverse-proxy identity,
  token persistence/refresh/rotation or redesign of the current API-principal authentication model.
- Provider switching, new Metadata/Storage providers, processing/recovery policy changes, uncertain-
  mutation replay, rollback, overwrite/delete defaults or any V1 product expansion.
- SSR, React Server Components, Node production serving, micro-frontends, CDN runtime dependencies,
  native mobile clients, global search/command palette, localization and complete visual-theme work.

Documentation Reconciliation Needed:
- A should reconcile activation-era current-state metadata in the canonical Chinese specification,
  `README.md`, `docs/v2-requirements.md`, `docs/progress.md` and `docs/roadmap.md` if final review
  returns PASS; several still identify Slice 30 as most recently closed and no large Slice as active,
  while Roadmap correctly remains ACTIVE until A closes Slice 31.
- Product Experience and Architecture already describe the implemented shell, information
  architecture, memory-only continuation and migration boundary; A should verify those facts without
  extending Base..Implementation Head.

Decision: SLICE READY FOR A REVIEW
~~~

## Review State

~~~
Slice Status: READY FOR A REVIEW
Implementation Head: 45cb1d4cdda6cf46a6d6699600bc4a4563efc06b
P0/P1 Defects: None found by B in Base..Implementation Head or Slice-final validation
Next Action: A FINAL REVIEW
~~~

## A Final Review

Pending B Closure Packet and A review of Base..Implementation Head.
