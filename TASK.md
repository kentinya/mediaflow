# Task 46.1 — Readable V2 actions and login

Authority: committed [Slice46](SLICE.md) RO-1 / AC-1 and
[Development Workflow](docs/development-workflow.md). Read the
[Developer experience](docs/agent-experience/developer-implementation-role.md) before implementation.

```text
Task ID: 46.1
Parent Slice: 46
Status: PLANNED
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

Not started. At handoff record checkpoint SHA, READY FOR B REVIEW, actual affected checks, visual/
contrast evidence, known risks and remaining Slice outcomes. Full acceptance stays with B.

## B Review Result

Not started. Review the actual Task Base..candidate, record PASS or actionable FIX REQUIRED in this
same Task, then reevaluate all Slice outcomes. RO-2–5 are not satisfied by this readability Task.
