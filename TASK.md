# Task BUG-AUTO-FORM — Open Automation creation after a Rules save

Authority: user report that 自动化 → 新建自动化任务 cannot open, with
`Automation authority unavailable`; [Development Workflow](docs/development-workflow.md) §3.1.

```text
Task ID: BUG-AUTO-FORM
Task Type: STANDALONE MINOR BUG
Parent Slice: NONE
Status: READY FOR B REVIEW
Task Base: 214eff9ed6ae52078a351a2b6d6d99d88f10b1ce
Difficulty: Low
Test Level: T3
Planner / Reviewer: B / independent B review pending
```

## Goal

Restore the existing creation journey: Automation inventory → 新建自动化任务 →
readable typed form → existing checked Save. Valid published OrganizePolicies must
not make form authority unreadable. Actual denied/unavailable reads retain the existing
bounded error, Back and Refresh recovery; opening the page creates no configuration or work.

Reproduction on the real isolated Python/SQLite/browser harness: save existing
OrganizePolicy A through Rules, then click 新建自动化任务. Rules correctly stores
`move`; Automation's form-authority GET returns 200 with raw operations
`["COPY", "MOVE", "move"]`. The Web decoder accepts uppercase operation spellings only,
rejects the whole document and displays the reported error. Raw spelling duplicates can
also exceed its four-operation bound. The effects projection was introduced in
`8968a06c0765e57e48f00f99561fe3a7fbb13470` (2026-10-28).

Related accepted behavior: REQ-SCHED-004, V2-AUTO-001/002/010 and the complete native
Automation journey in Product Experience. Accepted Slices and their closure records stay unchanged.

## Implementation Scope

1. Derive the form-authority effects from the existing runtime OrganizePolicy parser,
   emitting distinct canonical uppercase operations supported by the existing Web contract.
   Preserve overwrite/cleanup evidence and the exact Active identity.
2. Cover all four operations, accepted aliases/casing, mixed old/managed policy spellings
   and invalid policy rejection in focused API tests.
3. Add a real-Python browser regression: checked Rules save → inventory → click new →
   form opens, remains disabled-first, and opening performs only reads without changing
   Active/definitions/occurrences. Exercise the existing checked creation Save afterwards.

No runtime operation, policy semantics, command authority, persistence, route or schema change.

## Acceptance Criteria

- [x] Developer verified: a legitimate Rules save does not break the new Automation form.
- [x] Developer verified: effects represent at most four distinct canonical operations; aliases/case do not
  duplicate effects, and overwrite/cleanup remain truthful.
- [x] Developer verified: existing checked Save, stale conflict, invalid-input and permission behavior pass
  their directly affected regressions; unknown operations remain rejected.
- [x] Developer verified: opening through the real list entry creates no work or publication.

## Required Tests

### Developer — affected tests

- `.venv/bin/python -m unittest discover -s tests -p test_v2_automation_lifecycle.py`.
- `.venv/bin/ruff check mediaflow/application/automation_workspace_commands.py tests/test_v2_automation_lifecycle.py`
  and matching `ruff format --check`.
- In `web/`: `npm run test -- run src/entities/operations/automation-lifecycle.test.ts src/features/operations/AutomationLifecyclePage.test.tsx src/features/operations/AutomationRouter.test.tsx`.
- In `web/`: `npm run build`, then
  `npm run test:e2e -- --config=playwright.python.automation.config.ts tests/e2e/automation-lifecycle.python.spec.ts --grep 'Rules save|one checked Save|opening the form'`.
- Changed Web test lint/format/typecheck; `python3 scripts/check_governance.py`; `git diff --check`.

### B — acceptance

Independently review the entire Task Base..candidate; reproduce the reported failure and
run the focused Python lifecycle and whole real-Python lifecycle browser spec against
the candidate assets, plus the directly affected Web tests and static checks above.
T3: this is one read projection across API/Web, with no mutation/permission/schema/concurrency
change, so repository-wide T4/release gates are not assigned.

## Workspace and Non-goals

Branch `main`, starting HEAD equals Task Base; governance PASS, Git/worktree writable,
no tracked pre-existing modifications. Preserve all pre-existing untracked files:
`.DS_Store` files, `.mgmt.log`, `.t*.log`, `15`, two Automation reference PNGs under
`docs/pics/`, `output/database-reference-2026-11-01/`,
`output/imagegen/slice45-task-center-v1.zip`, `output/organize-flow-2026-11-01.html`.
No private configuration, production media, deployment, push, Slice/Roadmap/Progress
change, UI redesign or next Task. Developer cannot self-approve; hand off READY FOR B REVIEW.

## Developer Completion Report

- Implementation checkpoint: `b5fcbd446a66a30a39efefa4434d649edf6132d1`;
  review from the immutable Task Base. This handoff changes only TASK.md.
- `form_authority()` now reuses `parse_organize_policy()` and emits the distinct
  uppercase domain operations; the existing strict Web decoder and all command/
  permission/Active/persistence behavior are unchanged. New tests exercise actual
  checked Rules publication, 18 operation spellings, unknown-operation rejection and
  the real inventory-link → disabled-first form → checked Save journey.
- Backend command above: **33 passed**, no skips. Focused Web command above:
  **48 passed** across 3 files. Production build plus assigned Python-harness browser
  grep: **3 passed**, including the previously failing reported journey.
- `ruff check` and `ruff format --check` on the two changed Python files: PASS.
  In `web/`, `npm run typecheck`, `npx eslint tests/e2e/automation-lifecycle.python.spec.ts`,
  `npx prettier --check tests/e2e/automation-lifecycle.python.spec.ts`, `npm run build`:
  PASS. Existing bundle-size and jsdom scrollTo warnings remain non-failing.
  Governance and whitespace checks: PASS.
- Before the fix, both new effects-projection tests failed on raw operation spellings
  and the native browser case displayed the reported error. Its original trace/error
  context remain locally in `.git/validation-evidence/bug-auto-form/pre-fix/`.
  The initial checked-Rules test fixture also correctly refused publication until
  its temporary destination library directories were created; no check was bypassed.
- All original untracked files preserved and unstaged. No deployment/push or production
  configuration/media changes. No known remaining implementation blocker; independent
  B review/assigned acceptance is pending. No Task PASS or Slice closure claimed.

## B Review Result

Pending independent review; no PASS claimed.
