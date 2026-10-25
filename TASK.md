# Task 46.1 — Readable V2 actions and login

Authority: committed [Slice46](SLICE.md) RO-1 / AC-1 and
[Development Workflow](docs/development-workflow.md). Read the
[Developer experience](docs/agent-experience/developer-implementation-role.md) before implementation.

```text
Task ID: 46.1
Parent Slice: 46
Status: FIX REQUIRED
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

Status: READY FOR B REVIEW; no Developer acceptance or Slice closure. Task Base remains
`725458f83862d12362fe4d9da57d0ceb9437398e`. Review that Base through source candidate
**`f99a5856c0941b4c847de83d5395ad2245b45657`** on `main`. The subsequent report-only checkpoint
changes this section only. Original implementation/report: `f820a8db2f68c38348caf8579eb1965964606f98`.
No push, tag, release or publication was performed.

### Changes and actual defect

The original checkpoint repaired shared light primary/secondary/disabled palettes, Entry inputs,
selected states and conflicting Files/Rules/Task Center/Automation overrides. This follow-up found
one remaining real cascade defect: `.mf-files-page .mf-button` painted Delete white with dark text,
identical to Cancel. Its label was readable, so the previous contrast-only check did not catch the
lost danger distinction. The small scoped danger selector now preserves white-on-red Delete on
both library kinds, with the existing disabled and hover/focus states intact. No handler, permission,
API, Storage behavior, component API, layout or RO-2–5 behavior changed.

The browser spec now measures actual normal/hover/keyboard-focus and selected controls, both library
kinds' Rename/text/Delete/Copy/Move dialogs, actual disabled Delete during a held impact read, and
Automation's native create/edit/settings contexts. It uses existing `Live/Beta.txt` and
`harness-scheduled` fixtures; no new harness route or fabricated successful business payload exists.
Opening, hovering, focusing and dismissing these dialogs is checked for zero non-GET product calls.
The viewer test submits through the visible Create Folder dialog and observes the real backend
403 and retained error, instead of merely checking token text is absent.

Contrast measurement now composites text and adjacent background through each ancestor's alpha/
opacity in paint order. A modal measurement covers the reachable dialog, not the page behind its
sibling overlay. Each reading includes element/state, computed text/backdrop, opacity and focus.
A malformed backdrop diagnostic string and an obsolete source-color literal guard were replaced
by actual computed contrast evidence. Existing semantic/behavior assertions remain.

### Real-browser evidence

All six focused tests pass against the production build served by the temporary Python/SQLite/
Local harness. Final output has **458 readings**, minimum **4.69:1**, over the visited controls;
this is a measured fixture matrix, not a claim about every possible data-dependent screen.

| Actual context/state | Contrast |
|---|---|
| Entry Connect normal / hover / focus | 4.86 / 7.43 / 7.43 |
| Both libraries' Delete normal / hover / focus | 5.11 / 8.22 / 8.22 |
| Both libraries' disabled Delete during held impact read | 6.68 |
| Selected view toggle normal / hover / focus | 5.62 / 6.67 / 5.62 |
| Selected library card / current navigation | 6.78 / 6.40 |
| Real held Create Folder busy label | 6.68 |

The held command retains `disabled`, `aria-busy`, its real submitting label and one submission after
another attempted activation. The original Entry/validation/connected/disconnect/privacy and
read-failure checks remain. Entry has neither a placeholder nor an asynchronous submitting state;
no nonexistent Entry state was introduced to test it. Transport 503 is injected only on the actual
Task Center read route; no successful business state is invented.

Before rebuilding the repair, the new distinction assertion ran against the actual pre-repair
production CSS (`f820a8db` product source) and **failed**: ResourceLibrary Delete and Cancel both
painted `rgb(255,255,255)`. After rebuilding, both kinds pass. The earlier original-dark-palette
reproduction in `f820a8db:TASK.md` was not rerun this round; B still owns its independent check.

Desktop **1536×1024** and narrow **390×844** screenshots include Entry and Files/dialog contexts.
Visually inspected final Entry desktop/narrow, Files narrow create dialog, ResourceLibrary text
editor and MediaLibrary Delete: labels are readable, and the red Delete differs from Cancel.
The focused spec also captures all visited business surfaces and both kinds' five dialog contexts.

Local durable evidence (not tracked or remotely published):
`.git/validation-evidence/task-46.1-followup/`. `final-readability-artifacts/` contains PNGs and
per-test JSON readings; `danger-before-artifacts/` retains the failed reproduction/trace.
`runs.jsonl` records exact commands, exits and wall times; matching `*.log` retain raw output.
`source-artifact-sha256.json` binds source/spec/harness/config/lockfile and built asset identities;
`candidate-sha.txt` records the source candidate. These are local handoff files, not CI links.

Built artifact: CSS `index-Bg1MEjGx.css`, SHA-256
`63afadfc239fa84e8af9eb4c81bd43136730d6ac809434c642d01e090e50da57`;
JS `index-CVVvyMuv.js`, SHA-256
`6e8ae999f577bb23f7e61df4568f359806211d3fa5e68e5c41ce888d10d3d376`.

### Actual checks this round

Commands below run from `web/`, except governance/whitespace from repository root. Final browser,
static/build and 21 unit results use the source candidate's executable inputs. A report-only
successor does not change those inputs.

| Command | Actual result |
|---|---|
| `python3 scripts/check_governance.py`; `git diff --check` | clean |
| `npx prettier --check src/shared/ui/styles.css tests/e2e/action-readability.python.spec.ts playwright.config.ts` | clean |
| `npm run typecheck` | clean |
| `npx eslint tests/e2e/action-readability.python.spec.ts` | clean |
| `npm run test -- run src/features/entry/EntryPage.test.tsx src/shared/auth/AuthBoundary.test.tsx src/shared/ui/AppShell.test.tsx` | 3 files, 21 passed |
| `npm run build` | built; existing >500 kB chunk warning |
| `npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/action-readability.python.spec.ts` | 6 passed, 22.5 s Playwright total |
| `npm run test:e2e -- tests/e2e/deep-link.spec.ts` | 14 passed on final build, 3.9 s Playwright total |

Failures retained: first lint caught an empty fixture destructuring pattern in the new report hook;
it was corrected, and lint/type/format checks subsequently passed. The deliberate pre-repair
Delete-distinction reproduction failed as described above. No failures, skips or timeouts were
suppressed. No full Python/Web/E2E/packaging matrix was run this round; B owns acceptance.

Timed verification commands total **85.890 s**, including failed checks, static checks, builds and
browser/unit reruns. The recorded elapsed lower bound was already **493.8 s** at evidence review
(started after initial document reading), giving an upper bound of **17.4%** for timed verification
versus this round. Raw monotonic command times and the wall-clock lower-bound marker are retained.
No deliberate waiting was added to increase the denominator.

### Workspace, remaining risk and B handoff

Started on `main` at `f820a8db2f68c38348caf8579eb1965964606f98`; governance passed. Only the two
source/test files above and this report changed. The pre-existing `docs/pics/操作与任务.png` deletion,
all untracked images/logs/OS files/test-output directories and private runtime state remain unstaged.
No Slice/Roadmap/Progress boundary or B decision changed. Acceptance checkboxes remain B-owned.

B should independently review Base..candidate, inspect retained desktop/narrow screenshots and
readings, rerun the assigned browser/static/unit acceptance, and reproduce the original palette
failure. Automation detail/Enabled defects remain RO-5, not repaired or hidden here. The pre-existing
low-contrast non-action warning badge remains out of scope. The solid-background color measurement
does not model glyph antialiasing, gradients or arbitrary sibling overlays; no such effect is claimed
as validated. Arbitrary data-dependent/provider states and Slice-final T4 remain outstanding.

## B Review Result

**FIX REQUIRED — B, 2026-10-25.** Independently reviewed the complete Task range
`725458f83862d12362fe4d9da57d0ceb9437398e..379ad3e0521012c42928d488eb14b06a5ec7079a`,
including both implementation checkpoints, the browser spec, test configuration and all Task/report
changes. Executable candidate is `f99a5856c0941b4c847de83d5395ad2245b45657`; its successor changes
only the Developer report. Task ID/Base/Goal, Medium/T3 and parent Contract remain unchanged.

### B46.1-01 — disabled shared secondary actions look enabled (P1)

RO-1 / AC-1 and the Task's third acceptance criterion require disabled actions to remain visibly
unavailable. Through the real Settings page, click **查看 Active JSON → 导出脱敏配置包**. Hold the
existing configuration-package export GET while it is in flight. The actual export button becomes
disabled, but retains the exact enabled text, text color `rgb(24,36,59)`, white background,
`rgb(226,232,240)` border and opacity `1`. Only the pointer cursor changes to default; there is no
visible unavailable/busy treatment on the button. Backend refusal/duplicate-submit protection still
works; this finding does not claim an authority bypass.

In `web/src/shared/ui/styles.css:753–764`, `.mf-button:disabled` and
`.mf-button.mf-button-secondary` have equal specificity; the later secondary rule wins all three
palette properties after disabled opacity was changed to 1. The existing Files and Automation
settings scoped disabled rules mask this defect in the current disabled-state tests. A successful
contrast reading alone cannot establish availability distinction.

Correct within **this same Task**:

1. Make the shared secondary disabled palette win the cascade while retaining readable text and
   enabled normal/hover/focus distinctions. Keep the existing scoped Files/Automation variants and
   danger distinction correct; do not redesign component APIs, alter handlers or add export logic.
2. Extend the existing real-Python readability spec through the Settings entry above. Hold and then
   continue the real export response; assert actual disabled state, readable computed contrast,
   visible distinction from the unfocused enabled state, no second request on attempted activation,
   and restored availability after readback. Do not fabricate successful responses, toggle DOM
   disabled attributes, or create a new test-only product endpoint.
3. Run the new/failing focused browser case, changed-file checks and directly affected regressions,
   then hand off another coherent checkpoint for B. Full Web acceptance remains B-owned; no new
   Task or Slice-boundary changes are needed.

### Independent acceptance evidence

All commands ran on the submitted candidate's executable inputs, from `web/` unless stated.
Local raw logs, scripts, computed readings, screenshots and source/build hashes are retained at
`.git/validation-evidence/task-46.1-b-review/`; these are local evidence, not published CI links.

| Check | Actual result |
|---|---|
| `npm run typecheck`; `npm run lint`; `npm run format:check` | All passed |
| `npm run test -- run` | 84 files / 1,221 tests passed; no skips |
| `npm run build` | Passed; existing >500 kB chunk warning |
| `npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/action-readability.python.spec.ts` | 6 passed; 458 readings, minimum 4.69:1 |
| `npm run test:e2e -- tests/e2e/deep-link.spec.ts` | 14 passed |
| Independent Entry baseline reproduction | Actual Entry with Task-Base stylesheet: Connect 1.06:1; candidate stylesheet: 4.86:1 |
| Independent Settings export reproduction | B46.1-01 reproduced through native controls and existing GET; enabled/disabled paint values identical |

Playwright used explicit output directories under the evidence folder. The Entry baseline comparison
served the complete committed Task-Base stylesheet in place of the observed CSS asset, with the
same production JS and real Entry; no source checkout or business response was changed. B visually
inspected desktop/narrow Entry, narrow Files create dialog, MediaLibrary Delete and the Settings
disabled export screenshot. Text and danger distinction improve; disabled export remains the blocker.
Rebuilt CSS/JS hashes match the Developer's recorded final artifact. Static/1,221-unit/20-browser
passes do not override the independently reproduced failure.

No full Python, all-E2E, wheel or Docker gate is assigned or claimed for this T3 review. Slice-final
T4 remains pending. A convenience contact-sheet attempt lacked Pillow; individual PNGs were inspected
directly instead, without changing dependencies or skipping the visual review.

Timed verification commands total 150.2 s; overlapping command intervals occupy 97.8 s of wall
time. The recorded review lower bound, starting after initial document/source inspection, is
281.9 s: verification occupies at most 34.7% of that wall interval, below the user's 50% limit.
Exact command timings and the interval calculation are retained in `timing-summary.json`;
no deliberate waiting was added. Final governance and whitespace checks passed as well.

### All Slice outcomes reassessed

RO-1 is substantially delivered but **incomplete** until B46.1-01 is corrected. RO-2 (early manual
admission), RO-3 (durable library-local ordinary work), RO-4 (eight organizing-only views/four-type
Attention) and RO-5 (Automation detail/Enabled/real Run once) remain incomplete. The Task range has
no business/API/persistence changes; current `OperationsLanding.tsx` still reads discovery/manual
actions and renders global Worker state, while `AutomationDetailPage.tsx` and
`automation_definition_execution.py` still depend on separate grant eligibility/authority. Existing
accepted foundations are reuse, not delivery of those TARGET outcomes.

Next action: **Developer corrects B46.1-01 in Task 46.1**. Do not plan a successor or submit Slice46
to A yet. B has not closed the Slice or changed A-owned Slice/Roadmap/Progress fields. Review started
on `main` at `379ad3e0`; governance passed. All pre-existing deleted/untracked files remain untouched
and unstaged; only this B Task record is checkpointed. No push or publication is authorized/performed.
