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

Third correction loop for `FIX REQUIRED` on the second-correction checkpoint
`4e0d0039`. This checkpoint addresses only the two blockers B listed against
that Head; the B Review Result below remains the review record for `4e0d0039`.

### Changed Files

- `web/src/shared/navigation/destination-model.ts` — one `destinationData`
  `as const` literal is now the sole source of the route contract.
  `DestinationPath`, `DestinationAvailability`, the exported `destinations`
  projection, the `destinationPaths` allowlist and the `isDestinationPath`
  validator are all derived from that literal, so no manually enumerated union
  exists beside the data to drift from it.
- `web/src/shared/api/api-errors.ts` — added the feature-neutral
  `ApiReadError` / `ApiReadErrorCategory` authorized-read contract.
  `DashboardApiError` now extends it and keeps only the Dashboard-specific
  bounded response copy.
- `web/src/shared/auth/AuthorizedReadBoundary.tsx` — detects read-error category
  through the base `ApiReadError` only; the `DashboardApiError` import is gone,
  so the shared boundary no longer references any feature type.
- `web/src/shared/auth/AuthorizedReadBoundary.test.tsx` — three new specs prove
  the lifecycle for a plain non-Dashboard `ApiReadError` consumer: 401 clears
  the rejected authority plus authenticated cache with zero replay, 403 retains
  the principal, unavailable offers one bounded retry.

### Implemented

1. **Single-source navigation path contract (B blocker 1).** The union is
   `(typeof destinationData)[number]["path"]`. Adding a destination to the
   literal adds it to the type, the allowlist and the guard simultaneously;
   deleting one removes it from all four. An unknown or external target is
   still rejected by the existing tests, and destination-path uniqueness is
   still asserted.
2. **Feature-neutral read lifecycle (B blocker 2).** The boundary owns the
   401-clearing / 403-retention / bounded-retry rules against the shared error
   contract alone. A Dashboard consumer keeps its own copy because
   `DashboardApiError` narrows the message map; a later feature either throws
   `ApiReadError` or subclasses it and inherits the identical lifecycle with no
   duplicated rules and no change to `api-client.ts`.

### Tests and Results

```
python3 scripts/check_governance.py                         PASS
npm --prefix web ci                                         PASS (fresh install, 0 vulnerabilities)
npm --prefix web run format:check                           PASS
npm --prefix web run typecheck                              PASS
npm --prefix web run lint                                   PASS
npm --prefix web run test -- --run                          PASS (79 tests, 10 files)
npm --prefix web run build                                  PASS
npm --prefix web run test:e2e                               PASS (16 tests, chromium)
.venv/bin/python -m unittest tests.test_v2_ui tests.test_release_security PASS (17 tests)
.venv/bin/ruff format --check .                             PASS (305 files)
.venv/bin/ruff check .                                      PASS
.venv/bin/python -m unittest discover -s tests              PASS (1408 tests, 7 skipped, isolated clean worktree)
.venv/bin/python -m compileall -q mediaflow tests scripts   PASS
python3 scripts/docker_release_security_smoke_test.py       PASS
git diff --check                                            PASS
```

### Decisions

- **Derived union instead of `satisfies`.** Annotating the array
  `satisfies readonly Destination[]` is circular here because `Destination.path`
  is typed `DestinationPath`; the `as const` literal plus a derived alias and a
  widened `readonly Destination[]` export keeps one data source and compiles.
- **Inheritance instead of a parallel classifier.** `DashboardApiError extends
  ApiReadError` lets one `instanceof` test carry the shared category while the
  Dashboard edge retains its own copy, so the boundary needed no second
  conversion step and existing Dashboard tests are untouched.
- **No `isApiReadError` helper.** A pure `instanceof` alias would be a
  zero-content function under the repository TypeScript rules; the boundary uses
  `instanceof ApiReadError` directly.
- **Separate renders, not `rerender`,** for the three non-Dashboard proofs:
  `rerender` drops the `QueryClientProvider` wrapper in this test harness.

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

- No failures remain on the required T4 gate list. The full Python discovery run
  is executed in an isolated clean `git worktree` of this Head: six
  configuration tests read protected local runtime state (`/mnt/HDD_2`) through
  the root working directory, so a dirty-checkout run is not authoritative.
- No safety-invariant deviation: routing/recovery performs zero mutation, no
  Storage/Provider/Job access, no execution-authority issuance; Bearer material
  stays out of DOM, URL, persistent stores, logs and test artifacts;
  `config/alist.json` remains ignored/untracked and untouched here.
- Scope is exactly the two B blockers plus their proof tests. `README.md`,
  `auth-store.ts`, `auth-context.ts`, `AuthBoundary.tsx`, `DashboardPage.tsx`
  and the Playwright specs are unchanged from `4e0d0039`.

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: 45cb1d4cdda6cf46a6d6699600bc4a4563efc06b
```

## B Review Result

```text
Reviewed: eee3bca458e9d049c78fa17e626721fa5b507bfe..4e0d0039aaf5bd72c01c379c5585680f0055d424
Decision: FIX REQUIRED
Slice Required Outcomes all satisfied: NO
Next: SAME TASK FIX LOOP
```

- The intended-path type is still a second manually synchronized route list, so the Task's required
  single typed navigation authority is not complete. In
  `web/src/shared/navigation/destination-model.ts`, `DestinationPath` enumerates all five paths
  separately from `destinations`, while `destinations: readonly Destination[]` only checks that each
  array value belongs to the union; adding a union-only path compiles even though
  `destinationPaths`/`isDestinationPath` reject it at runtime. Derive `DestinationPath`, the runtime
  allowlist and its guard from the literal `destinations` data itself (with an appropriate
  `satisfies` shape), then retain the invalid/external-target and uniqueness tests without another
  path enumeration.
- `AuthorizedReadBoundary` is still coupled to Dashboard and therefore does not meet the
  feature-independent lifecycle criterion. Repository inspection shows the shared boundary imports
  `DashboardApiError` and recognizes 401/403 only through `instanceof DashboardApiError`; any later
  feature query returning its own typed API error would be treated as a generic unavailable read or
  would have to reuse a Dashboard-specific error, rather than inheriting the shared authority/cache
  transition. Define a feature-neutral shared authorized-read error/category contract (or an
  explicit typed classifier supplied to the boundary), keep Dashboard-specific response copy at the
  feature/client edge, and prove a non-Dashboard-shaped consumer receives the same 401 clearing,
  403 retention and bounded retry behavior without duplicating those rules.
