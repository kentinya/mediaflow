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

Second correction loop for `FIX REQUIRED` on
`eee3bca..bb8f732`. This checkpoint follows `905cc3a`; the B Review Result
below remains the review record for the `bb8f732` checkpoint.

### Changed Files

- `web/src/shared/navigation/destination-model.ts` — canonical
  `DestinationPath` union; `destinationPaths` and `isDestinationPath` derived
  from the one `destinations` contract, so the continuation allowlist and its
  runtime validator share the single typed navigation source.
- `web/src/shared/api/auth-store.ts` — removed the separately hard-coded
  `ALLOWED_INTENDED_PATHS`; `setIntendedPath` is now typed as
  `DestinationPath` and runtime-guarded by the model's `isDestinationPath`.
- `web/src/shared/api/auth-context.ts` — `useIntendedPath()` now returns
  `DestinationPath | null`.
- `web/src/shared/auth/AuthBoundary.tsx` — always replaces the recorded
  intention with the operator's latest explicit supported-route choice before
  redirecting to the connection boundary (no stale-intention short-circuit).
- `web/src/shared/auth/AuthStateBanner.tsx` / `.test.tsx` — moved from
  `web/src/features/auth` into `shared/auth` beside the lifecycle it serves.
- `web/src/shared/auth/AuthorizedReadBoundary.tsx` (new) — feature-independent
  boundary owning the whole connection/permission/cache-clearing contract for
  one authenticated read-only query: not-connected, 401 rejection, 403
  distinction, bounded unavailable retry, and delegation of data states.
- `web/src/shared/auth/AuthorizedReadBoundary.test.tsx` (new) — directly
  proves rejected-token + authenticated-cache clearing without replay,
  forbidden identity retention, bounded retry wiring and ready-data handoff.
- `web/src/features/dashboard/DashboardPage.tsx` — consumes
  `AuthorizedReadBoundary` and renders only its own loading/empty/success
  content; no local 401/403 categorization, cache clearing or banner choice.
- `README.md` — source-ownership bullet updated for the shared/auth move and
  the typed navigation model.
- Tests: `destination-model.test.ts` (derived unique allowlist), `auth-store.test.ts`
  (model-derived allowlist + typed guard), `AuthBoundary.test.tsx` (changed
  intent + cache-cleared-after-401), `DashboardPage.test.tsx`,
  `AuthStateBanner.test.tsx`, `web/tests/utils.tsx`, and Playwright
  `deep-link.spec.ts` / `dashboard.spec.ts` (generic forbidden copy plus a new
  changed-intent journey).

### Implemented

1. **One typed navigation source for continuation.** The path type and the
   runtime validator both come from the centralized destination model; the
   auth store holds no second route list. `destinations` is statically checked
   against the canonical `DestinationPath` union and `destinationPaths` is the
   derived runtime projection, so route-model drift is impossible without a
   compile error and the guard coverage locks it down.
2. **Latest explicit route intent always wins.** `AuthBoundary` overwrites any
   earlier intention whenever an unauthenticated operator reaches a supported
   product route, so a new shell choice made at the connection boundary is what
   reconnection continues to — never a stale destination. Proven in an
   AuthBoundary component test and a Playwright journey (deep `/library` →
   choose Operations → connect lands on Operations).
3. **Shared authorized-read lifecycle replaces feature-local rules.**
   `AuthorizedReadBoundary` owns the 401 rejection transition (clear the
   rejected authority first so the read query is disabled, then remove the
   authenticated cache — this ordering prevents a synchronous replay of the
   rejected request), the 403 identity-retention distinction, the bounded
   unavailable/malformed retry and the not-connected presentation. Dashboard
   no longer categorizes 401/403, calls `clearRejectedAuthority()`,
   `queryClient.clear()` or selects auth banners itself.
4. **Direct evidence.** Boundary unit tests prove rejected token + cache
   clearing with zero automatic `refetch`; route-level tests assert the
   dashboard query cache is empty after a 401; browser journeys keep proving
   the full success/failure/recovery matrix.

### Tests and Results

```
python3 scripts/check_governance.py                         PASS
npm --prefix web ci                                         PASS (fresh install, 0 vulnerabilities)
npm --prefix web run format:check                           PASS
npm --prefix web run typecheck                              PASS
npm --prefix web run lint                                   PASS
npm --prefix web run test -- --run                          PASS (76 tests, 10 files)
npm --prefix web run build                                  PASS
npm --prefix web run test:e2e                               PASS (16 tests, chromium)
.venv/bin/python -m unittest tests.test_v2_ui               PASS (11 tests)
.venv/bin/python -m unittest tests.test_release_security    PASS (6 tests)
.venv/bin/ruff format --check .                             PASS
.venv/bin/ruff check .                                      PASS
.venv/bin/python -m unittest discover -s tests              PASS (1408 tests, 7 skipped, isolated clean checkout)
.venv/bin/python -m compileall -q mediaflow tests scripts   PASS
python3 scripts/docker_release_security_smoke_test.py       PASS
git diff --check                                            PASS
```

### Decisions

- **The typed path union lives in the destination model, and the model's array
  is checked against it.** Keeping the union as the canonical declared set and
  deriving `destinationPaths`/`isDestinationPath` from `destinations` makes a
  new route opt into the allowlist by construction instead of by a second
  manual list.
- **401 clearing is deliberately two-phase.** Clearing only the rejected
  authority first disables the mounted read query; only then is the
  authenticated cache removed. Clearing the cache while the observer was still
  enabled caused TanStack Query to synchronously replay the rejected request,
  which the tests caught and this ordering eliminates.
- **The read lifecycle is a boundary component, not a hook plus per-feature
  switches.** The boundary renders the auth/read states itself and hands
  feature content a typed data/refresh view, so a later API-backed feature
  cannot silently reintroduce feature-local permission or cache rules.
- **`AuthStateBanner`/`UnavailableBanner` moved into `shared/auth`** with the
  boundary so no `shared` module imports from a feature directory.

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
- The only non-web file beyond `TASK.md` is `README.md`, updated solely to keep
  the source-ownership bullet factual after the `shared/auth` move.

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: 4e0d0039aaf5bd72c01c379c5585680f0055d424
```

## B Review Result

```text
Reviewed: eee3bca458e9d049c78fa17e626721fa5b507bfe..bb8f732526cab2221d0edebdcad2953c9743e586
Decision: FIX REQUIRED
Slice Required Outcomes all satisfied: NO
Next: SAME TASK FIX LOOP
```

- Intended-route authority is still duplicated instead of coming from the one typed navigation
  source required by RO-1 and this Task. `web/src/shared/api/auth-store.ts` hard-codes
  `ALLOWED_INTENDED_PATHS` separately from `destinations` in
  `web/src/shared/navigation/destination-model.ts`; `setIntendedPath(path: string)` therefore relies
  on a second manually synchronized route map. `AuthBoundary` also refuses to replace an existing
  intention, so a new explicit supported-route choice made at the connection boundary can leave the
  operator reconnecting to the stale earlier route. Derive the runtime validator and path type from
  the centralized destination model, update continuation on the operator's latest explicit safe
  route intent, and cover route-model drift plus changed-intent continuation in component/browser
  tests.
- The rejected-authority/cache/permission lifecycle remains feature-local rather than owned once by
  the reusable route/auth boundary. `DashboardPage.tsx` directly categorizes 401/403, calls
  `authStore.clearRejectedAuthority()` and `queryClient.clear()`, and selects the auth banners; a
  later API-backed feature would have to duplicate that transition despite the Acceptance Criterion
  explicitly prohibiting feature-level connection, permission and cache-clearing rules. Move this
  transition/presentation contract into a feature-independent shared hook/boundary consumed by
  Dashboard, retain 403 identity and explicit read-only retry semantics, and directly prove rejected
  token plus authenticated cache clearing and no replay before fresh human intent.
