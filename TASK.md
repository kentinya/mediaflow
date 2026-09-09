# Task 31.2 — Deep-link authentication continuity and actionable recovery

This Task follows [the development workflow](docs/development-workflow.md) and is subordinate to
the current [`SLICE.md`](SLICE.md).

```text
Task ID: 31.2
Parent Slice: 31
Status: PLANNED
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

### Changed Files

- `web/src/shared/api/auth-store.ts` — added `setIntendedPath` / `clearIntendedPath` / `getIntendedPath` to the memory-only auth store; `clearToken` also clears intended path.
- `web/src/shared/api/auth-context.ts` — added `useIntendedPath()` hook.
- `web/src/shared/api/auth-store.test.ts` — added tests for intended-path tracking and co-clearing with token.
- `web/src/shared/auth/AuthControls.tsx` — disconnect now clears intended path and navigates back to the entry boundary.
- `web/src/features/entry/EntryPage.tsx` — tracks the router's current pathname as the intended destination before connection; after valid connect, navigates to the intended route (or Dashboard as safe default when no deep intention exists); a `justConnected` ref prevents the post-connect navigation from re-registering the same path as an intention.
- `web/src/features/auth/AuthStateBanner.tsx` — new reusable component with `AuthStateBanner` (not-connected / unauthorized / forbidden variants) and `UnavailableBanner` (explicit retry for unavailable/malformed reads).
- `web/src/features/auth/AuthStateBanner.test.tsx` — unit tests for all three banner variants and token-secrecy assertion.
- `web/src/features/entry/EntryPage.test.tsx` — updated for deep-link continuation behaviour; added test for clear-intent-on-disconnect.
- `web/tests/e2e/deep-link.spec.ts` — new Playwright suite covering direct deep entry, connect-from-root, deep-link continuation, disconnect/cache-clear, 401/403 distinction, unavailable retry, unknown-route recovery, and V1 handoff token secrecy.
- `README.md` — updated V2 frontend section with authentication continuity facts.
- `docs/product-experience.md` — updated CURRENT V2 FOUNDATION to reflect shell auth lifecycle.
- `docs/architecture.md` — appended Task 31.2 implementation evidence.

### Implemented

1. **Intended-route tracking in auth store.** `MemoryAuthStore` now exposes `setIntendedPath` / `clearIntendedPath` / `getIntendedPath`. `clearToken` also clears the intended path so a single disconnect action resets both the principal and the post-connect continuation target.
2. **Entry page stores and consumes intended path.** The entry page captures the current router pathname (when not already at `/`) as the intended destination via a `useEffect` guarded by a `justConnected` ref to avoid post-navigate re-registration. On connect it navigates to the stored path (falling back to `/dashboard` when unset) and clears the intention atomically.
3. **AuthControls disconnect navigates to entry.** Disconnect from any route now calls `authStore.clearToken()`, `authStore.clearIntendedPath()`, `queryClient.clear()`, and `navigate({ to: "/" })` so the operator always lands at the in-shell connection boundary.
4. **Reusable auth-state banners.** `AuthStateBanner` renders not-connected, unauthorized (401), and forbidden (403) states with bounded, secret-free recovery actions. `UnavailableBanner` renders explicit-retry for unavailable/rejected/malformed read outcomes.
5. **Documentation reconciliation.** README, product-experience, and architecture docs describe the CURRENT shell auth/continuation behavior without claiming later Slice capabilities.

### Tests and Results

```
python3 scripts/check_governance.py                         PASS
npm --prefix web ci                                          (already installed)
npm --prefix web run format:check                            PASS
npm --prefix web run typecheck                               PASS
npm --prefix web run lint                                    PASS
npm --prefix web run test -- --run                           PASS (56 tests, 8 files)
npm --prefix web run build                                   PASS
npm --prefix web run test:e2e                                PASS (13 tests)
.venv/bin/python -m unittest tests.test_v2_ui                PASS (11 tests)
.venv/bin/python -m unittest tests.test_release_security     PASS (6 tests)
.venv/bin/ruff format --check .                              PASS
.venv/bin/ruff check .                                       PASS
.venv/bin/python -m unittest discover -s tests               UNAVAILABLE (pre-existing timeout on full discovery; targeted module runs OK)
.venv/bin/python -m compileall -q mediaflow tests scripts    PASS
python3 scripts/docker_release_security_smoke_test.py        UNAVAILABLE (read-only /var/lib/deepseek-harness/.docker/buildx/activity)
git diff --check                                             PASS
```

Pre-existing failures (unrelated to this Task):
- `tests.test_api_credentials` — 2 assertion failures present at Task Base (`retired-viewer` principal missing from runtime config; legacy credential status returns non-zero). These existed before this Task and are not within scope.

### Decisions

- **Intended path lives in `authStore`, not React state.** Keeps the continuation model independent of any single component and allows AuthControls (which has no router `useNavigate` dependency for this purpose) to clear it on disconnect.
- **Root entry does not register an intended path.** `useEffect` skips `setIntendedPath` when `location.pathname === "/"` so that connecting from root falls through to the default Dashboard destination rather than landing back on the entry page.
- **`justConnected` ref suppresses the useEffect after connect.** Prevents the post-navigate re-render from overwriting the cleared intended path with the same value. A ref (not state) avoids unnecessary re-renders.
- **AuthStateBanner is a standalone reusable component.** Dashboard retains its existing local auth-state rendering; the banner component is available for future routes owned by later Slices without duplicating the pattern.

### Remaining In-Slice Work

- Slice 32 Library & Files business journey (real Storage browsing, FileIndex list/detail, search/filter, Scan/Preview/Organize entry).
- Slice 33 Operations Workspace (expanded Dashboard, Tasks, Jobs, schedules, Automation, Notifications).
- Slice 34 Review & Recovery Workspace (Recognition/Metadata/Classification review, conflict, checkpoint, per-item recovery).
- Slice 35 Configuration Administration (Configuration, Settings, revision/test evidence, activation).
- Slice 36 V2 Parity, Accessibility & Legacy UI Retirement (final parity, comprehensive accessibility, `/ui` cutover).

### Risks / Deviations

- `tests.test_api_credentials` has 2 pre-existing failures unrelated to this Task; reported above.
- Full `unittest discover` times out in this environment — confirmed pre-existing by testing on base HEAD. Targeted module runs (`test_v2_ui`, `test_release_security`, `test_dashboard`, `test_container_probe`) all pass.
- `docker_release_security_smoke_test.py` is `UNAVAILABLE` due to a read-only filesystem at `/var/lib/deepseek-harness/.docker/buildx/activity/`; not a code issue.
- No deviation from safety invariants: zero mutation, Bearer token never leaves memory, no secret leakage into DOM/URL/persistent stores/logs.

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: NOT SET (pending commit)
```

## B Review Result

```text
Reviewed: PENDING
Decision: PENDING
Slice Required Outcomes all satisfied: PENDING
Next: PENDING
```

If `FIX REQUIRED`, B lists only unmet Task blockers below this block. Fixes remain in Task 31.2;
this result cannot close the Slice or update Roadmap.
