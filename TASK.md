# Task 31.1 — Operator shell, information architecture, and migration routes

This Task follows [the development workflow](docs/development-workflow.md) and is subordinate to
the current [`SLICE.md`](SLICE.md).

```text
Task ID: 31.1
Parent Slice: 31
Status: READY FOR B REVIEW
Task Base: 2de6551a40808b2781701a57d4a6d09b6831dc12
Difficulty: Medium
Test Level: T3
Planner / Reviewer: B
```

## Goal

Deliver the feature-independent V2 operator shell and its centralized, typed information
architecture: operators can identify their current location, navigate the stable product areas on
wide or narrow screens, and reach truthful V2 or current-V1-Web destinations. This is the first
coherent platform boundary for Slice 31 and directly advances RO-1, RO-2, RO-4, RO-5, RO-7 and
preservation outcome RO-8.

## Why This Task Exists

The current V2 `AppShell` is only a header/main wrapper, the router exposes only entry and
Dashboard, and route labels and availability are not represented by a shared model. There is no
primary navigation, active-page context, semantic bypass, narrow-screen navigation, or truthful
landing/handoff for areas intentionally owned by later Slices. Building these pieces together is
the largest independently testable architecture unit: the route metadata defines what the shell
renders, while component and browser evidence can verify navigation, migration truthfulness,
keyboard use and responsive behavior without inventing the deferred business journeys.

## Implementation Scope

- Define one typed, centralized destination/route metadata model for the goal-oriented product
  areas: Overview, Library, Operations, Review & Recovery, and Configuration (or equally clear
  operator wording). It must own labels, V2 route ownership, availability/migration state,
  current-V1-Web continuation and active-location/page-title metadata.
- Extend TanStack Router beneath `/ui-v2/` with the product-area landing or migration routes needed
  by that model. Dashboard remains the implemented V2 destination; later-Slice areas must render an
  honest unavailable/not-yet-migrated state with a useful next action rather than a dead control or
  simulated business capability.
- Turn `AppShell` into a persistent feature-independent layout with MediaFlow identity, primary
  navigation, active page context, the existing connection controls and a stable main-content
  region. Do not duplicate shell/navigation definitions in feature pages.
- Provide wide and narrow viewport navigation with semantic header/nav/main landmarks, a working
  skip-to-content path, visible focus, keyboard-operable controls, correct active-route semantics
  and meaningful document/page titles.
- Keep the V1 `/ui` continuation truthful and explicit. Handoff must not put the Bearer token in a
  URL, persistent browser storage or another transfer mechanism, and it must not promise a V1 deep
  link that the current product does not support.
- Add focused Vitest/React Testing Library coverage for the IA model, shell rendering, active route,
  migration state/handoff, accessible navigation and narrow-menu state; extend Playwright coverage
  for production-build wide/narrow and keyboard navigation plus V1/V2 coexistence.
- Preserve the current entry, memory-only connect/disconnect and typed read-only Dashboard
  behavior. Changes to Python APIs, domain/application behavior, RBAC, static-serving architecture
  or V1 UI implementation are outside this Task.

## Acceptance Criteria

- [ ] One typed route/destination source drives product-area labels, route ownership,
      availability/migration state, V1 continuation, active-location semantics and page titles;
      shell components and feature pages do not maintain competing navigation maps.
- [ ] On authenticated/recoverable V2 routes, the persistent shell exposes brand, primary
      goal-oriented destinations, active page context, connection controls and main content at both
      wide and narrow viewports.
- [ ] Overview opens the working V2 Dashboard. Every destination whose business journey belongs to
      Slices 32–35 is visibly identified as not yet available in V2 and provides a truthful current
      Web continuation or an in-shell return action; no control claims deferred behavior or requires
      CLI completion.
- [ ] Navigation has semantic landmarks, a working skip link, logical keyboard operation, visible
      focus, correct active-state semantics and meaningful route-specific document/page titles;
      narrow navigation can be opened, used and dismissed without trapping focus or hiding the
      active context.
- [ ] Shell navigation, migration pages and V1 handoff issue no API work-admission, execution-
      authorization, provider, Storage or mutation request. No token, secret, raw exception,
      private path or implementation-only authority identifier is rendered, persisted or placed in
      a URL.
- [ ] The current memory-only Bearer boundary, backend-authoritative RBAC, Dashboard behavior,
      `/api/v1/*`, V1 `/ui`, CSP/cache/static serving and OrganizerExecutor-only mutation boundary
      remain unchanged and regression-covered.
- [ ] Focused component tests and a production-build browser journey prove route-driven active
      navigation, migration truthfulness, keyboard navigation, narrow behavior, page titles and
      V1/V2 coexistence using only local fakes and non-production state.
- [ ] The assigned T3 gates pass with actual evidence, and the checkpoint contains only this Task's
      coherent frontend platform/test changes plus its completion report.

## Required Tests

Task 31.1 T3 pass gates:

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
.venv/bin/python -m compileall -q mediaflow tests scripts
git diff --check
```

The following Slice-final/release commands remain documented for active-Task governance but are
not Task 31.1 PASS gates unless implementation impact or discovered risk expands beyond this T3
frontend boundary:

```bash
.venv/bin/python -m unittest discover -s tests
python3 scripts/docker_release_security_smoke_test.py
```

If a browser or another required local tool is unavailable, report `UNAVAILABLE` with the exact
reason; do not infer a pass. Tests must not use production credentials, remote providers, operator
media or private runtime state.

## Non-goals

- Completing RO-3 intended-route authentication continuation or consolidating all feature-level
  401/403 handling; this Task preserves current connect/disconnect and Dashboard recovery behavior
  while establishing the shell/route foundation for the next in-Slice unit.
- Implementing real Library/Files, Operations, Review & Recovery, Configuration or Settings
  business behavior owned by Slices 32–35.
- Adding or changing a backend endpoint, schema, domain/application service, API contract, identity
  model, permission rule, token persistence or Web-native execution authority.
- Retiring or redesigning V1 `/ui`, transferring its token, or claiming unsupported V1 deep links.
- Comprehensive cross-feature accessibility/parity/cutover acceptance owned by Slice 36.
- Slice-final factual documentation reconciliation, the next Task, or the next Slice.

## Developer Completion Report

### Changed Files
- `web/tests/e2e/dashboard.spec.ts`
- `TASK.md`

### Implemented
- Corrected the migration browser journey to follow the actual narrow interaction: the narrow menu starts closed (CSS `display:none`), so destination links are absent from the accessibility tree until the menu is opened; the test now opens the menu before asserting active-route state.
- Fixed the navigation link selector to the real accessible name `Library Migration` (the link renders the label and the `Migration` status badge, concatenated without a space); removed the failing exact `Library` match.
- Added a real keyboard-navigation proof: focuses the `Operations Migration` link and activates it with `Enter`, then asserts the route changed to `/ui-v2/operations`, the page title updated to `Operations | MediaFlow`, and the active `aria-current="page"` marker moved to the Operations link after reopening the menu.
- Preserved the existing zero-API-work migration assertions (`apiRequests` empty), the keyboard open/close behavior, and the truthful V1/V2 handoff + return journey.

### Tests and Results
- `python3 scripts/check_governance.py` — PASS
- `npm --prefix web run format:check` — PASS
- `npm --prefix web run typecheck` — PASS
- `npm --prefix web run lint` — PASS
- `npm --prefix web run test -- --run` — PASS (49 tests)
- `npm --prefix web run build` — PASS
- `npm --prefix web run test:e2e` — PASS: all 4 Playwright cases pass, including the corrected migration/narrow/keyboard journey. Ran with `PLAYWRIGHT_BROWSERS_PATH=/root/.cache/ms-playwright` against the built artifact and local fake server.
- `.venv/bin/python -m unittest tests.test_v2_ui tests.test_release_security` — PASS (17 tests)
- `.venv/bin/ruff format --check .` — PASS
- `.venv/bin/ruff check .` — PASS
- `.venv/bin/python -m compileall -q mediaflow tests scripts` — PASS
- `git diff --check` — PASS
- `npm --prefix web ci` — UNAVAILABLE: this sandbox sets `npm config omit=dev`, causing `npm ci` to silently skip dev-dependencies (only 16 of 278 packages installed); dev toolchain requires `--include=dev`. No gate assertion was weakened or skipped — the full install runs correctly with `npm ci --include=dev`.

### Decisions
- Kept the correction limited to B's blockers: the narrow-menu open-before-assert ordering, the real `Library Migration` accessible name, and an exercised destination link by keyboard; no production shell, API, auth, or Slice contract changes.
- Used native keyboard `Enter` against the menu toggle and the focused nav link so the evidence proves keyboard-operable navigation without adding test-only accessibility hooks.
- Discovered that this sandbox's npm config has `omit=dev`, causing the raw `npm ci` gate to silently skip dev-dependencies; the full install runs correctly with `npm ci --include=dev`.

### Remaining In-Slice Work
- Intended-route authentication continuation and broader shared 401/403 handling remain outside this Task as documented in the Task non-goals.
- Other Slice 31 Required Outcomes and later product-area migrations remain for B/A sequencing and their owning Slices.

### Risks / Deviations
- The E2E gate now executes to a passing result because the Playwright Chromium binary is present in `/root/.cache/ms-playwright`; it remains environment-dependent and would be `UNAVAILABLE` where the browser is not installed.
- The sandbox's npm config sets `omit=dev`, so the raw `npm ci` gate silently skips dev-dependencies; dev toolchain is only fully installed with `--include=dev`. No gate assertion was weakened.
- No production credentials, private paths, operator media, or ignored runtime files were added.
- `web/dist` and Playwright test artifacts remain ignored and are absent from the checkpoint.

### Checkpoint
```text
Status: READY FOR B REVIEW
Head SHA: 19c389421ed9db4f12e194e75cdb49e9582267ed
```

## B Review Result

```text
Reviewed: 2de6551a40808b2781701a57d4a6d09b6831dc12..3929954f31bed52d4d5d88cc98ffbcee6e8e1a60
Decision: FIX REQUIRED
Slice Required Outcomes all satisfied: NO
Next: SAME TASK FIX LOOP
```

- The production-browser acceptance gate still fails. B ran
  `npm --prefix web run test:e2e`: 3 tests passed and the migration/narrow journey failed while
  looking for an exact accessible-name `Library` link before the CSS-hidden narrow menu was opened;
  the rendered link also includes the `Migration` status in its accessible name. The correction
  uses the keyboard only to open and close the menu button and never activates a navigation link by
  keyboard, so it still does not prove keyboard navigation. Make the assertions follow the actual
  narrow interaction and accessible names, exercise a destination link by keyboard while retaining
  active/page context, and rerun the complete Playwright gate to a passing result without weakening
  assertions or adding a skip.
- The Completion Report names Head
  `39299541c3d43bfdc24df2a9ea6a3c41dbfbbd59`, which `git` reports as a nonexistent object. The
  actual correction commit is `3929954f31bed52d4d5d88cc98ffbcee6e8e1a60`. Update the report to a
  real full checkpoint SHA after committing the next correction so B can review the declared
  Task Base..Head range.
