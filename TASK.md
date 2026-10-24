# Task 46.1 — Readable V2 actions and login

Authority: committed [Slice46](SLICE.md) RO-1 / AC-1 and
[Development Workflow](docs/development-workflow.md). Read the
[Developer experience](docs/agent-experience/developer-implementation-role.md) before implementation.

```text
Task ID: 46.1
Parent Slice: 46
Status: READY FOR B REVIEW
Task Base: 725458f83862d12362fe4d9da57d0ceb9437398e
Difficulty: Medium
Test Level: T3
Planner / Reviewer: B
```

## Goal

An operator can read and distinguish actions when connecting to V2, navigating business pages,
opening dialogs and following success or error states. Cover Entry, Files/MediaLibrary, Task Center,
Rules, Storage, Automation and Settings, including shared Shell/error-state actions.

Journey: open Entry → read the token field and Connect action → connect or correct invalid input →
continue to the intended page → use readable permitted actions → inspect the result/error and the
existing legal next action. Reconnect/disconnect retains current authentication and non-replay rules.

Requirements: `V2-UX-004`, applicable `V2-UX-001–003`, `V2-SHELL-001`, `V2-AUTH-001–003`,
`V2-SAFE-001` and `UX-001/002/007`. Read the TARGET readable-action journey and CURRENT V2 Operator
Web migration journey in [Product Experience](docs/product-experience.md), and the V2 program/API
and Operator Web contracts in [Architecture](docs/architecture.md).

### Actual gap and reusable implementation

- `web/src/shared/ui/styles.css`: `.mf-button` and `.mf-field input` use `#202b24` backgrounds
  with dark `--ink: #18243b`. Entry uses the shared `Button` and `TextField` without a local repair.
- Files, Rules, Task Center and Automation settings have separate overrides; their selector order,
  specificity, disabled opacity and dialog context must be checked together. A base-only change
  cannot establish readability of every consumer or preserve danger/secondary distinctions.
- Reuse existing shared UI components, native buttons/links and the light Shell. Existing Entry,
  auth, file-dialog and browser tests protect semantics, but CSS-string guards/jsdom do not prove
  rendered contrast. Source inspection is complete; browser reproduction/verification is work below.

## Implementation Scope

1. Reproduce Entry's unreadable Connect/field in the built app. Inventory the actual shared and
   scoped primary/secondary/danger, button-styled link, icon, dialog and selected actions on the
   listed surfaces. Include dialogs rendered outside a page's styling ancestor. Record the winning
   computed colors/states so the repair addresses the cascade rather than adding another page patch.
2. Repair the shared light action palette and directly related Entry field colors. Adjust only
   conflicting consumer overrides needed for RO-1; preserve each page's layout and intended action
   hierarchy. Prefer `styles.css`; touch `Button.tsx`, `TextField.tsx` or direct consumers only when
   their markup/class composition is a demonstrated cause. No component API redesign is required.
3. Verify normal/hover/keyboard-focus/selected/submitting/disabled states. Keep visible focus,
   accessible names, button/link semantics, `disabled`/`aria-busy`, existing validation, permission
   guards and duplicate-submit protection. Opening, hovering, focusing or dismissing a view must
   not submit work; busy controls must not gain a second command path.
4. Add focused real-browser regression coverage in
   `web/tests/e2e/action-readability.python.spec.ts`, using the existing temporary Python/SQLite/
   Local fixture and production build through `playwright.python.config.ts`. Keep the new Python
   spec excluded from the default fake-server suite in `playwright.config.ts`. Reuse existing fixture
   setup; any necessary fixture additions stay isolated in the existing harness, never product APIs.
   Test real route/dialog components, computed contrast and interaction, not synthetic DOM or CSS
   literals. Capture desktop/narrow evidence using test output paths, without tracked binary artifacts.
5. Run the affected checks below and hand off a coherent READY FOR B REVIEW checkpoint. Report the
   measured states, screenshots and any inaccessible context truthfully. Automation inventory/edit/
   settings can supply its current action contexts; its known detail/Enabled defects belong to RO-5
   and must not be hidden with fabricated successful payloads or fixed in this Task.

## Acceptance Criteria

- [ ] Entry's field, value/placeholder, Connect, connected/disconnect and validation/error actions
  are readable. Empty input is rejected; a valid temporary token follows the recorded intended route.
  Refresh/reconnect and disconnect preserve memory-only credentials and current cache/intent handling.
- [ ] All applicable action variants on the listed real surfaces, including both library kinds'
  Rename/Delete/text/transfer dialogs, remain readable in normal/hover/focus and selected states.
  Enabled text has computed contrast at least 4.5:1, or 3:1 for qualifying large text. Account for
  transparent backgrounds, ancestor colors and effective opacity; do not infer success from hex literals.
- [ ] Submitting/disabled labels remain legible and visibly unavailable; primary, secondary and danger
  retain clear distinctions. Actual UI state drives their availability. Icon actions retain accessible
  names and visible glyphs, and keyboard focus remains visible on buttons and button-styled links.
- [ ] Desktop `1536 × 1024` and narrow `390 × 844` evidence shows Entry and representative business/
  dialog variants without clipped action labels or inaccessible controls. Measure every distinct
  palette/context combination; screenshots and assertions identify the actual elements/states covered.
- [ ] Existing invalid-input, permission-denied, in-flight and failure states keep their current
  behavior. A held temporary-fixture command stays disabled/busy and cannot submit twice. No action
  handler, permission, auth storage or mutation authority is broadened by the visual repair.
- [ ] Existing authentication continuation/privacy tests and the focused browser matrix pass.
  No cosmetic test substitutes for actual rendered-state checks; no assertion is removed merely
  to make the palette change pass.

## Required Tests

Follow [test levels and ownership](docs/development-workflow.md#6-test-levels). T3 covers a shared
presentation change across routes with auth/dialog integration; it does not alter backend authority,
persistence or media processing. Slice46's final T4 obligations remain unchanged.

### Developer — affected tests

From repository root:

```bash
python3 scripts/check_governance.py
git diff --check
```

From `web/`, after implementing the new spec:

```bash
npm run test -- run src/features/entry/EntryPage.test.tsx src/shared/auth/AuthBoundary.test.tsx src/shared/ui/AppShell.test.tsx
npx prettier --check src/shared/ui/styles.css tests/e2e/action-readability.python.spec.ts playwright.config.ts
npm run build
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/action-readability.python.spec.ts
npm run test:e2e -- tests/e2e/deep-link.spec.ts
```

The browser matrix must cover rendered color/opacity/focus and existing busy/permission/error behavior
on the real components. The Entry/auth/Shell and deep-link checks cover invalid input, continuation,
401/403, reconnect/disconnect and token privacy. Run additional new/changed/directly affected tests
and changed-file formatting/lint/type checks if component or fixture code changes; list exact commands
in the handoff. No full Python/Web/E2E or packaging matrix is assigned to Developer.

### B — acceptance and full regression

On the submitted candidate, independently run the two focused Playwright commands above and inspect
the desktop/narrow screenshots and measured normal/hover/focus/selected/busy/disabled states.
Confirm the regression fails against the old palette and passes with the repair. Reject text-only
CSS checks as sole evidence. All services/data are isolated; use no user media or private configuration.

From `web/`, B also runs:

```bash
npm run typecheck
npm run lint
npm run format:check
npm run test -- run
npm run build
```

Full Web unit/static coverage is justified by the globally consumed stylesheet; this Task requires
no full Python suite, all-E2E run, Docker or wheel gate. The Slice-final
[shared full gates](docs/development-workflow.md#shared-full-regression-commands) remain B-owned.
Record candidate SHA, artifact identity, commands/results, screenshots, failures and unavailable checks.

## Non-goals

- RO-2–5: early organize admission, local ordinary-work status, center population/navigation/recovery,
  Automation detail/Save/Enabled/authorization/Run once and stability semantics remain separate work.
- No new identity/theme system, dark mode, general form/page redesign or unrelated CSS cleanup.
- No backend/domain/API/schema/permissions/execution changes or extra retry/undo capability.
- No Slice/Roadmap boundary change, Slice acceptance, or next-Task plan.

## Workspace and handoff

Planning started on `main` at Task Base; governance passed and repository/Git/TASK.md were writable.
Preserve the pre-existing `docs/pics/操作与任务.png` deletion and all untracked reference images, logs,
OS files and test/artifact directories. Keep private runtime state ignored/untracked/unstaged.

## Developer Completion Report

Status: READY FOR B REVIEW. Implemented only Task 46.1 (RO-1/AC-1). The shared light action
palette, Entry field colors and the conflicting consumer overrides were repaired; a real-browser
readability matrix was added. RO-2–RO-5 are untouched.

### Source identity

- Task Base: `725458f83862d12362fe4d9da57d0ceb9437398e`
- Checkpoint: this report's commit (`docs(task-46.1): hand off readable V2 actions`); see
  `git log -1` for the exact SHA and the parent chain to the Task Base.
- Branch: `main`. No push, no tag, no release.
- Files changed: `web/src/shared/ui/styles.css`, `web/playwright.config.ts`,
  `web/tests/e2e/action-readability.python.spec.ts` (new), `TASK.md`.
- Preserved untouched: the pre-existing `docs/pics/操作与任务.png` deletion and all untracked
  images/logs/OS files/test-output directories listed at planning time. No private runtime state
  was staged.

### What actually changed, and why

The measured cause was the cascade, not one missing declaration. Inventory of the real bundle
before the repair (`1536×1024`, isolated real-Python harness):

| Element | Rendered text | Rendered backdrop | Contrast |
|---|---|---|---|
| Entry `#api-token` | `rgb(24,36,59)` | `rgb(32,43,36)` | **1.06:1** |
| Entry Connect | `rgb(24,36,59)` | `rgb(32,43,36)` | **1.06:1** |
| Automation `a.mf-button-primary` (新建自动化任务) | `rgb(24,36,59)` | `rgb(32,43,36)` | **1.06:1** |
| Review / Notifications primary links | `rgb(24,36,59)` | `rgb(32,43,36)` | **1.06:1** |
| Shell skip link | `rgb(16,21,18)` | `rgb(18,104,245)` | **3.80:1** |
| Files active view toggle | `rgb(18,104,245)` | `rgb(237,244,255)` | **4.39:1** |
| Files selected library card | `rgb(18,104,245)` | `rgb(239,245,255)` | **4.43:1** |
| Active shell nav link / hover | `rgb(18,104,245)` | `rgb(228,239,255)` | **4.18:1** |
| Task Center tab labels, `Refresh`, dialog close | `rgb(102,120,149)` | `rgb(255,255,255)` | **4.48:1** |
| Disabled batch action (55% opacity) | blended `#94bbfa` | blended `#7dacfa` | **1.17:1** |
| Disabled danger action (55% opacity) | blended `#eea09b` | blended `#ea8c84` | **1.18:1** |
| Rules disabled action | `rgb(148,160,178)` | `rgb(243,245,248)` | **2.42:1** |

The dark `#202b24` base `.mf-button`/`.mf-field input` fill was the root defect: it was inherited by
Entry, Review, Notifications and every primary button-styled `<Link>`, while Files/Rules/Automation
each patched over it locally. Disabled relied on `opacity: 0.55`, which composites both label and
fill so no palette can stay legible.

Repair (single shared palette + only the overrides that were demonstrably wrong):

- `:root` gained `--accent-strong` (accent-coloured text/hover), `--accent-soft`, and one explicit
  `--disabled-surface/-ink/-line` unavailable palette. `--muted` `#667895`→`#57678a`.
- `.mf-button` is a real primary (accent fill, white label, hover/focus darkening) instead of the
  dark base; `.mf-button-secondary` is the light surface variant with its own hover/focus.
  `.mf-button:disabled` no longer uses opacity, so a disabled label stays at 6.68:1 and visibly grey.
- `.mf-button-danger` uses `#c2413b` (5.11:1 white label) with a legible disabled state.
- `.mf-field input` / `.mf-filter-field` no longer use the dark fill; Entry is readable with the
  shared `Button`/`TextField` markup unchanged.
- Shell: skip link to white-on-accent (4.86:1), nav hover/active to `--accent-strong` on its pale
  tint, and selected nav stays distinguishable.
- Files: `--files-accent` `#2f6bff`→`#1f56d8` (white label 6.21:1, dark-on-soft 5.39:1),
  `--files-muted`→`#5a6b85`, and the later geometry block's white-everything override was restated
  so disabled and primary stay correct at that specificity (this was the actual cascade bug).
- Task Center, Rules, Automation and pagination/selection states restated on the same tokens.
  Task-local primary/secondary/danger distinctions, focus rings, `disabled`/`aria-busy`, action
  handlers, permission guards and auth storage are unchanged — only colors and the disabled
  mechanism moved.

### Evidence

New real-browser matrix: `web/tests/e2e/action-readability.python.spec.ts` (5 tests, excluded from
the fake-server suite via `playwright.config.ts`). Every assertion composites the full ancestor
background chain and the effective ancestor opacity, then compares the **visible** foreground with
the **painted** backdrop against 4.5:1 (3:1 for qualifying large text). Coverage:

1. Entry field/label/Connect/validation alert/connected+Disconnect; empty input rejected; valid
   token continues to the recorded route; token absent from localStorage/sessionStorage/cookies/URL.
2. All visible actions measured on Dashboard, both Files kinds, Storage, Rules, Automation, Task
   Center, Settings; both library kinds' create-folder dialog (primary/secondary/close/field); a
   real MediaLibrary delete-confirmation danger action; a real row action menu; narrow `390×844`
   Files plus its dialog with no clipped labels.
3. Primary vs secondary vs danger backdrops stay distinct; keyboard-modality focus ring measured on
   a primary button, a secondary button and a button-styled nav link.
4. Real disabled batch/pagination actions readable and distinguishable from enabled; a held Files
   command proves `aria-busy="true"`, `disabled`, `提交中…` label, and that a second activation
   (dispatched click + Enter) never reaches the backend; read-only principal exposes no token text.
5. A real 503 Task Center read failure stays readable, and re-entry re-reads the surface.

Measured after the repair (all ≥5.6:1 except the deliberately 4.86:1 white-on-accent primary):
Entry field 15.51, Entry Connect 4.86, nav active 6.40, skip link 4.86, view toggle active 5.62,
selected library card 6.78, dialog primary 6.21, dialog cancel 15.86, dialog close 5.66, dialog
field 15.51, Task Center tabs 7.43, disabled batch/page 6.68, Automation primary link 4.86,
Automation secondary 17.27.

Screenshots (ignored test output, not tracked): `web/test-results/action-readability/*.png` —
`entry-desktop`, `entry-invalid`, `entry-connected`, `entry-connected`, `*-desktop` for all eight
surfaces, `resource-dialog-desktop`, `media-dialog-desktop`, `medialibrary-delete-danger`,
`files-disabled`, `files-submitting`, `files-narrow`, `files-dialog-narrow`,
`task-center-read-failure`. Visually reviewed: `entry-desktop` (light field, dark label, blue
Connect), `medialibrary-delete-danger` (light dialog, readable toggle/table, distinct danger action),
`files-narrow` (no clipped labels at 390px).

Regression proof: with the old `styles.css` restored and rebuilt, all 5 new tests fail; with the
repair they pass. The spec is not a CSS-literal guard.

### Commands actually run

From repository root: `python3 scripts/check_governance.py` → PASS; `git diff --check` → clean.

From `web/`:

```
npm run test -- run src/features/entry/EntryPage.test.tsx src/shared/auth/AuthBoundary.test.tsx src/shared/ui/AppShell.test.tsx   → 3 files / 21 tests passed
npm run test -- run src/shared/ui                                                                                              → 4 files / 31 tests passed
npx prettier --check src/shared/ui/styles.css tests/e2e/action-readability.python.spec.ts playwright.config.ts                  → all formatted
npm run typecheck                                                                                                              → clean
npm run lint                                                                                                                   → clean
npm run build                                                                                                                  → built
timeout 400 npx playwright test --config=playwright.python.config.ts tests/e2e/action-readability.python.spec.ts                → 5 passed
npm run test:e2e -- tests/e2e/deep-link.spec.ts                                                                                → 14 passed
npm run test:e2e -- tests/e2e/manual-organize.spec.ts                                                                          → 14 passed
npm run test:e2e -- tests/e2e/library-files.spec.ts                                                                            → 48 passed
npm run test:e2e                                                                                                               → 242 passed (16 files)
npx playwright test --config=playwright.config.ts --list                                                                       → 242 tests, 0 action-readability
```

### Known risks and limits

- The measured matrix covers every palette/context combination that a V2 surface renders from the
  visited fixtures (admin principal, seeded real data). Some data-dependent variants — an error
  banner's own inline color, a provider-specific Storage card accent, the Automation
  detail/Enabled defect states — were not separately measured here because those states are the
  known RO-5 defects and must not be faked into a passing payload. Their shared palette inherits
  the repaired tokens.
- `--warn` `#d69b1b` (draft-state badge) is 2.45:1 on white. It is a pre-existing non-action
  annotation outside RO-1's action/Entry scope and was deliberately left alone; flagging it rather
  than silently widening the Task.
- Entry has no in-page submitting state: `connect()` sets the token synchronously and navigates, so
  the busy/disabled proof uses the real held Files command instead of inventing an Entry spinner.
- Contrast is asserted for the visible text/backdrop pair only; it does not model subpixel
  antialiasing, so borderline 4.5:1 pairs were deliberately avoided in favor of ≥5:1 except the
  white-on-`--accent` primary (4.86:1).
- B must independently re-run the two focused Playwright commands, inspect the screenshots and
  confirm the old-palette failure. Slice-final T4 gates and RO-2–RO-5 remain outstanding.

## B Review Result

Not started. Review the actual Task Base..candidate, record PASS or actionable FIX REQUIRED in this
same Task, then reevaluate all Slice outcomes. RO-2–5 are not satisfied by this readability Task.
