# Task 31.2 — Deep-link authentication continuity and actionable recovery

This Task follows [the development workflow](docs/development-workflow.md) and is subordinate to
the current [`SLICE.md`](SLICE.md).

```text
Task ID: 31.2
Parent Slice: 31
Status: READY FOR B REVIEW
Task Base: eee3bca458e9d049c78fa17e626721fa5b507bfe
Difficulty: High
Test Level: T4
Planner / Reviewer: B
```

## Goal

Complete Slice 31's route/authentication lifecycle so an operator entering a supported V2 deep
link can connect through the existing memory-only principal boundary, continue to the intended safe
route, and recover from absent/rejected authority, forbidden access, unavailable data or an unknown
route without losing shell context. This Task targets RO-3 and RO-6 and completes the remaining
RO-7/RO-8 integration and documentation evidence.

## Why This Task Exists

Task 31.1 (accepted through implementation Head
`19c389421ed9db4f12e194e75cdb49e9582267ed`) established the centralized IA, responsive shell,
migration routes and browser proof. The remaining user-journey gap is visible in the current code:
direct product routes do not share an authentication boundary, token entry always opens Dashboard,
and Dashboard locally duplicates unauthenticated, 401, 403 and unavailable recovery. These concerns
form one security-sensitive route lifecycle; implementing them together avoids competing intent or
permission state and makes the shell independently usable before later product areas are migrated.

## Implementation Scope

- Add one feature-independent authentication/route-continuation boundary for supported V2 product
  routes. An unauthenticated direct route must keep a safe, allowlisted intended destination,
  present the existing memory-only connection interaction in shell context, and continue to that
  route after connection. Root entry remains deterministic and connects to Overview/Dashboard.
- Keep continuation derived from the router's known route model or bounded runtime state. Never put
  Bearer material in a URL, route/search state, DOM, browser persistence, log or test artifact, and
  never accept an arbitrary external return target.
- Compose reusable, bounded operator states/actions for not connected, rejected/expired authority
  (401), forbidden permission (403), unavailable/rejected/malformed read results and unknown routes.
  Dashboard must consume the shared lifecycle rather than retain a competing authentication flow.
- On 401, invalidate the rejected in-memory authority and authenticated query state, preserve the
  intended safe route, explain that new credentials are required and wait for explicit reconnection;
  do not automatically replay a rejected request. A 403 must retain the authenticated identity,
  distinguish missing permission from authentication failure and offer only valid navigation or
  reconnection actions.
- Disconnect from any supported route must clear the memory-only token and TanStack Query cache,
  leave an understandable in-shell connection path, and perform no hidden retry or redirect to an
  unrelated destination.
- Preserve explicit retry for safe read-only unavailable states, shell context for not-found and
  migration-unavailable routes, meaningful page titles, and the existing truthful V1 handoff.
- Extend unit/component tests and production-build Playwright journeys for root/direct-deep entry,
  connect-to-intended-route, refresh/no-persist behavior, disconnect/cache clearing, 401 re-entry,
  403 distinction, unavailable retry, not-found recovery and token secrecy/no hidden work.
- Reconcile only factual CURRENT shell/IA/auth-continuation and migration-boundary descriptions in
  `README.md`, `docs/product-experience.md` and `docs/architecture.md` after implementation evidence
  exists. Do not change stable requirements, Roadmap scope/order or the Slice Contract.

## Acceptance Criteria

- [ ] Opening a supported `/ui-v2/` deep route without a token presents one in-shell connection
      boundary and, after valid connection, continues to that exact allowlisted route; connecting
      from root opens Overview/Dashboard, and unknown/external return targets are never accepted.
- [ ] Refresh demonstrates the token's memory-only semantics: no credential survives, the current
      supported path remains understandable, and reconnection continues safely without raw-token
      copy beyond the existing principal-entry interaction or a CLI fallback.
- [ ] Disconnect on every supported route clears the token and authenticated TanStack Query cache,
      exposes an actionable reconnect state at a safe location and neither automatically retries
      work nor leaks authority into URL, route state, storage, cookies or rendered output.
- [ ] A backend 401 clears rejected authority/query state and presents bounded credential re-entry
      for the intended route without automatic replay. A 403 remains visibly distinct, does not
      grant access or discard a still-authenticated principal silently, and offers the smallest
      valid recovery/navigation action.
- [ ] Unavailable, rejected or malformed read results provide an explicit safe retry; not-found and
      migration-unavailable routes retain shell orientation, meaningful titles and valid return or
      V1-Web continuation actions. No state exposes raw exceptions, headers, tokens, private paths
      or implementation-only identifiers.
- [ ] The router, auth store/context, query client and reusable route-state primitives own this
      lifecycle once; Dashboard and later feature routes do not duplicate connection, continuation,
      permission or cache-clearing rules.
- [ ] Navigation, connection presentation, disconnect and recovery perform no Storage/Provider
      access, Job/Task creation, execution-authorization issuance or media mutation. Only the
      already-authorized Dashboard read and an operator-selected safe read retry may call the API.
- [ ] `/api/v1/*`, backend RBAC, V1 `/ui`, Python static serving/CSP/cache behavior, memory-only
      Bearer handling and OrganizerExecutor-only mutation remain unchanged and full-regression
      covered; `config/alist.json` and private runtime state remain absent from the checkpoint.
- [ ] Component and production-browser evidence covers the complete success/failure/recovery
      matrix, checks token absence from DOM/URL/persistent stores, and proves no mutation/work-
      admission request occurs during routing or recovery.
- [ ] README, Product Experience and Architecture describe only the implemented CURRENT shell,
      authentication continuation and migration coexistence facts while preserving all V2 TARGET
      boundaries and Explicitly Deferred work.
- [ ] All T4 gates pass with truthful PASS/FAIL/SKIP/UNAVAILABLE reporting, and the checkpoint is a
      coherent Task 31.2 change without assertion weakening, hidden skip or unrelated files.

## Required Tests

Task 31.2 T4 gates:

```bash
python3 scripts/check_governance.py
npm --prefix web ci
npm --prefix web run format:check
npm --prefix web run typecheck
npm --prefix web run lint
npm --prefix web run test -- --run
npm --prefix web run build
npm --prefix web run test:e2e
.venv/bin/python -m unittest tests.test_v2_ui tests.test_release_security
.venv/bin/ruff format --check .
.venv/bin/ruff check .
.venv/bin/python -m unittest discover -s tests
.venv/bin/python -m compileall -q mediaflow tests scripts
python3 scripts/docker_release_security_smoke_test.py
git diff --check
```

Add focused frontend test commands only if tests are split into a narrower project. The full
Vitest, Playwright and Python discovery commands above remain required. Docker/browser gates that
are genuinely unavailable must be reported with exact environmental evidence rather than inferred;
do not install a skip, weaken an assertion or use production services/data to manufacture a pass.

## Non-goals

- Changing principal identity, backend RBAC or API permissions; persisting/refreshing/rotating the
  Bearer token; adding username/password, cookie/session, OIDC or proxy identity.
- Adding an execution grant/unlock, mutation-admission flow, new backend endpoint, schema,
  repository or application/domain behavior.
- Implementing Library/Files, Operations, Review & Recovery or Configuration business journeys
  owned by Slices 32–35, or comprehensive cross-feature parity/cutover owned by Slice 36.
- Replacing or retiring V1 `/ui`, changing V1/API/static contracts, or transferring a V2 token to
  the V1 UI.
- Altering `SLICE.md` Required Outcomes, Required Surfaces, Safety Invariants, Explicitly Deferred,
  Slice Base or Roadmap ordering/status.
- Optional visual redesign, copy polish, dependency/framework changes or unrelated refactoring.
- Planning the next Slice or declaring Slice 31 `PASS / CLOSED`.

## Developer Completion Report

Correction loop for `FIX REQUIRED` on `eee3bca..ea0f573`. New checkpoint follows
`e4c7deb`; the B Review Result below remains the review record for the first
Task 31.2 checkpoint.

### Changed Files

- `web/src/shared/auth/AuthBoundary.tsx` (new) — shell-level route/connection
  boundary. An unauthenticated operator opening a supported product deep route
  gets its allowlisted destination recorded and is redirected to the in-shell
  entry; connecting then continues to that exact route. Root entry records
  nothing and defaults to Dashboard; unknown routes are left to not-found.
- `web/src/shared/auth/AuthBoundary.test.tsx` (new) — route-level integration
  proof for deep-entry redirects, root/unknown behaviour, authenticated deep
  routes, and the in-place 401 authority-clearing lifecycle.
- `web/src/shared/api/auth-store.ts` — continuation targets are restricted to
  the router-known allowlist; a 401 clears only the rejected credential via
  `clearRejectedAuthority()` while preserving the intended path; the new
  `isRejected()` state keeps a rejected principal distinct from a plain
  disconnect until a fresh credential is entered.
- `web/src/shared/api/auth-context.ts` — added the `useRejected()` hook.
- `web/src/features/dashboard/DashboardPage.tsx` — consumes the shared
  `AuthStateBanner` / `UnavailableBanner` states; on a backend 401 it clears
  the rejected authority and the authenticated TanStack Query cache in place
  behind the bounded unauthorized state (no local duplicate auth flow).
- `web/src/features/auth/AuthStateBanner.tsx` — reusable bounded
  not-connected / unauthorized / forbidden states and `UnavailableBanner`
  with an explicit read-only retry; custom titles/descriptions stay secret-free.
- `web/src/routes/router.tsx` — mounts `AuthBoundary` inside the shell root so
  every supported route shares the lifecycle once.
- `web/src/features/entry/EntryPage.tsx` — consumes the boundary-recorded
  intended path on connect (Dashboard default from root); disconnect clears
  token, intended path and query cache and returns to the entry boundary.
- `web/src/shared/api/auth-store.test.ts`, `web/src/features/auth/AuthStateBanner.test.tsx`,
  `web/src/features/dashboard/DashboardPage.test.tsx`,
  `web/src/features/entry/EntryPage.test.tsx`, `web/tests/utils.tsx` — unit and
  component coverage for the allowlist, rejected-authority model, shared
  banner states and an isolated-router test helper without the app route tree.
- `web/tests/e2e/deep-link.spec.ts`, `web/tests/e2e/dashboard.spec.ts` —
  Playwright journeys reworked to the real boundary flow: direct deep entry,
  connect-to-exact-route, refresh memory-only semantics, disconnect/cache
  clearing, 401 in-place rejection + explicit continuation, 403 distinction,
  real unavailable and malformed reads with bounded retry, unknown-route shell
  context, and V1-handoff token secrecy.

`README.md`, `docs/product-experience.md` and `docs/architecture.md` already
described exactly the CURRENT behaviour this correction implements, so they
needed no further change once the code and tests matched them.

### Implemented

1. **Shared route/connection boundary with allowlisted continuation.** The
   shell-level `AuthBoundary` records the router-known destination before an
   unauthenticated deep route redirects to the entry interaction. The store
   only accepts allowlisted paths, so arbitrary or external return targets are
   never stored or followed. Connecting from the entry continues to the exact
   recorded route; connecting from root still defaults to Overview/Dashboard.
2. **Distinct 401 lifecycle modelled in the store.** A rejected principal is
   cleared from memory and its authenticated query cache is cleared in place
   while the safe intended route survives. `isRejected()` keeps the bounded
   unauthorized state visible on the route until a fresh credential is
   explicitly entered (which resets the boundary); a plain disconnect returns
   to the neutral not-connected state.
3. **Dashboard consumes the shared lifecycle.** Dashboard renders through the
   reusable `AuthStateBanner`/`UnavailableBanner` components for
   not-connected, unauthorized, forbidden and unavailable/malformed outcomes,
   with no competing bespoke auth markup; `AuthBoundary` owns route-level
   interception.
4. **Truthful browser proof.** Playwright journeys now exercise the real
   flows: direct deep entry, refresh (memory-only), disconnect/cache clearing,
   401 rejection with no replay and explicit continuation to the same route,
   403 distinction with the principal retained, real unavailable and malformed
   reads with explicit retry, unknown-route recovery and V1-handoff token
   secrecy.

### Tests and Results

```
python3 scripts/check_governance.py                         PASS
npm --prefix web ci                                         PASS (fresh install, 0 vulnerabilities)
npm --prefix web run format:check                           PASS
npm --prefix web run typecheck                              PASS
npm --prefix web run lint                                   PASS
npm --prefix web run test -- --run                          PASS (68 tests, 9 files)
npm --prefix web run build                                  PASS
npm --prefix web run test:e2e                               PASS (15 tests, chromium)
.venv/bin/python -m unittest tests.test_v2_ui               PASS (11 tests)
.venv/bin/python -m unittest tests.test_release_security    PASS (6 tests)
.venv/bin/ruff format --check .                             PASS
.venv/bin/ruff check .                                      PASS
.venv/bin/python -m unittest discover -s tests              PASS (full discovery in isolated clean checkout)
.venv/bin/python -m compileall -q mediaflow tests scripts   PASS
python3 scripts/docker_release_security_smoke_test.py       PASS
git diff --check                                            PASS
```

### Decisions

- **The boundary, not the entry page, records the intended destination.**
  `EntryPage` is only ever mounted at `/`, so it cannot observe a deep route
  before the operator connects; a shell-level boundary mounted for every route
  is the only place that can record the router-known destination and redirect
  unauthenticated deep entries to the connection boundary.
- **Rejection is modelled as store state, not component state.** Dashboard's
  401 handler only mutates external systems (auth store, query cache), which
  satisfies the react-hooks rules and keeps the rejected state observable by
  the route boundary and the shell without duplicated local state.
- **A 401 keeps the operator on the route behind the unauthorized banner.**
  The boundary redirects fresh unauthenticated deep entries, but a 401-rejected
  principal stays in place so the distinct "new credentials required" state
  remains visible and the rejected request is never replayed before explicit
  human intent; the retained intended path makes re-entry continue to the same
  route.
- **Documentation required no second reconciliation pass.** The CURRENT
  statements in `README.md`, `docs/product-experience.md` and
  `docs/architecture.md` matched the corrected implementation exactly, so the
  fix loop closed the documentation gap by making the code true to them.

### Remaining In-Slice Work

- Slice 32 Library & Files business journey (real Storage browsing, FileIndex
  list/detail, search/filter, Scan/Preview/Organize entry).
- Slice 33 Operations Workspace (expanded Dashboard, Tasks, Jobs, schedules,
  Automation, Notifications).
- Slice 34 Review & Recovery Workspace (Recognition/Metadata/Classification
  review, conflict, checkpoint, per-item recovery).
- Slice 35 Configuration Administration (Configuration, Settings, revision/test
  evidence, activation).
- Slice 36 V2 Parity, Accessibility & Legacy UI Retirement (final parity,
  comprehensive accessibility, `/ui` cutover).

### Risks / Deviations

- No known failures remain on the required T4 gate list.
- The full Python discovery run is executed in an isolated clean checkout of
  this checkpoint (per the review note) so protected local runtime state in the
  working checkout does not affect the result.
- No deviation from safety invariants: routing/recovery performs zero
  mutation, no Storage/Provider/Job access, no execution-authority issuance;
  Bearer material never leaves runtime memory and never appears in DOM, URL,
  persistent stores, logs or test artifacts; `config/alist.json` remains
  ignored/untracked and is not part of this checkpoint.

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: bb8f732526cab2221d0edebdcad2953c9743e586
```

## B Review Result

```text
Reviewed: eee3bca458e9d049c78fa17e626721fa5b507bfe..ea0f57330ca5267fdab9e1a791b68e3f95c9231f
Decision: FIX REQUIRED
Slice Required Outcomes all satisfied: NO
Next: SAME TASK FIX LOOP
```

- Deep-link authentication continuity is not implemented. `EntryPage` is mounted only at `/`, so
  its pathname effect cannot capture an unauthenticated product route before the operator follows
  the existing entry link; the new Playwright case loads `/library`, performs a full-page
  `goto("/ui-v2/")` that clears the memory store, and then asserts Dashboard instead of the intended
  Library route. `setIntendedPath` also accepts any string rather than enforcing the router's known
  destinations. Add the shared route/connection boundary with allowlisted continuation, and prove
  in component and browser tests that a real unauthenticated deep entry connects back to that exact
  supported route while root still defaults to Dashboard and arbitrary targets are rejected.
- The required 401 authority lifecycle is absent. `DashboardPage` was not changed: after a 401 it
  retains the rejected token and authenticated query state and links to root without preserving the
  intended route; the E2E test checks only that one request occurred and never proves authority/
  cache clearing or successful explicit reconnection. Implement the shared 401 transition so the
  rejected credential and authenticated cache are cleared, the safe intended route is retained,
  no replay occurs before new human intent, and a new credential continues to that route; verify
  token, cache, request count and recovery outcome directly.
- The shared recovery boundary is not wired into product behavior. Repository search shows
  `AuthStateBanner` and `UnavailableBanner` are imported only by their own test file, while
  `DashboardPage` still duplicates all not-connected/401/403/unavailable rendering. The browser
  test named `unavailable state provides explicit safe retry` exercises only the Operations
  migration placeholder and no failed read or retry. Compose the reusable lifecycle into Dashboard
  and the route boundary, and add a real unavailable/rejected/malformed read test with an explicit
  bounded retry; retain the distinct 403 behavior and authenticated principal.
- The CURRENT documentation is materially ahead of implementation. `README.md`,
  `docs/product-experience.md` and `docs/architecture.md` state that deep links return to their exact
  route, 401 clears rejected authority/query state, and Dashboard consumes a shared lifecycle, but
  the reviewed code does none of those things. Reconcile these statements only after the corrected
  implementation and tests make them true.
- Required-test reporting is not truthful/complete. The report records raw `npm ci` as merely
  “already installed”, full discovery as a timeout and Docker smoke as unavailable. B actually ran
  raw `npm --prefix web ci` successfully, ran Docker release-security smoke to PASS, and ran full
  discovery in an isolated clean checkout at the implementation Head to `1408 tests` PASS with
  `7 skipped`; the dirty root run completed with 6 private-runtime-state failures rather than a
  timeout. Rerun/report the next checkpoint's gates accurately, using an isolated clean checkout
  for full Python regression without deleting or changing protected local configuration.
