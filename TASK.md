# Task PATCH-20261029-1 — Readable Automation pre-start execution records

Authority: the user's explicit small-version bug instruction and “开始干活” after the proposed
B planning → Developer implementation → B acceptance sequence. The existing
[CURRENT Automation journey](docs/product-experience.md#current--complete-native-automation-workspace-accepted43-amended46),
[CURRENT read-model contract](docs/architecture.md#current--v2-automation-workspace-and-consumed-engine-settings-slice43-pass--closed)
and normal safety/test/Git rules in [Development Workflow](docs/development-workflow.md) apply.

```text
Task ID: PATCH-20261029-1
Parent Slice: 46
Status: PLANNED
Task Base: a9d5c5f1914f5590f0ebe1f60e58d7f91ca56381
Difficulty: Low
Test Level: T3
Planner / Reviewer: B
Development Authorization: USER-REQUESTED STANDALONE MINOR BUG — 2026-10-29
```

## Small-version lifecycle exception

The user explicitly limits A to large-version Slice work and says small-version bugs do not need
A's intervention. This is a standalone correction to already accepted behavior; `Parent Slice: 46`
is a provenance association, not reactivation, scope expansion or a new Slice. Slice46's original
Base, accepted implementation/review/closure and Roadmap/Progress remain unchanged. B reviews this
patch only and does not declare a Slice closed.

The preflight before planning passed with the previous no-active-Task notice. The unchanged guard
supports only Tasks under ACTIVE/FIX REQUIRED Slices; with this explicitly authorized standalone
Task it reports `active Task requires committed HEAD Slice 46 to be ACTIVE or FIX REQUIRED`
(exit 1). Record that actual exception separately from code/test results at each required preflight;
do not weaken the guard or report it as PASS. After B acceptance restore the no-active-Task notice
with the exact patch candidate/result and exception pointer, and verify the guard returns PASS.
This is a one-Task exception, not a general lifecycle policy change.

## Goal and existing defect

Automation → 执行记录 must display settled pre-start failures, their genuine category/next action,
and healthy siblings without adding execution controls. A valid HTTP200 records page currently
fails frontend normalization when one pre-start `failureStage` lacks required booleans.

`_automation_record_failure_stage` returns only stage/category/nextAction/statement before formal
Task creation. The strict frontend also requires `itemsTruncated` and `unavailable`; page-wide
`items.map` throws and AuthorizedReadBoundary renders “执行记录不可用”. Formal-Task failure
branches already publish the complete envelope. This implements existing `V2-AUTO-001/005/006`,
`UX-002/003/005/007` and `REQ-API-002/003`; execution semantics are unchanged.

## Implementation scope and steps

1. Add the existing complete envelope fields to the proven pre-start backend branch:
   `items=[]`, `effects={none:0, known:0, uncertain:0, partial:0}`,
   `itemsTruncated=False`, `unavailable=False`. Retain the original stage/category/statement/
   nextAction and all ownership/read-only/retry decisions. No new abstraction is needed for this
   small branch correction; keep the frontend decoder strict.
2. Add regression coverage using existing isolated managed-definition/Storage fixtures. Let a
   normal Scheduler occurrence reach the real Worker with an unavailable saved source directory,
   then read the real records API. Assert the complete zero-item envelope, no formal Task/media
   effect, and unchanged work/authority counts across refresh/read. Extend the existing mixed
   scheduled/manual/pre-start read-model test to pin the full pre-start shape, including the
   historical `unattended_execution_authority_missing` record without replaying it.
3. Feed an actual Python API response from that fresh isolated journey through the real Web
   fetch/decoder and Automation records page, alongside a genuine completed/no-work sibling.
   Use a small test-only fixture exporter if needed; do not handcraft a corrected response to
   stand in for this cross-layer check. Assert the failure explanation and sibling both render,
   no unavailable banner or execution control appears, and refresh repeats only the read.
   Reuse existing empty/formal-failure/unreadable/denied/malformed cases instead of duplicating
   broad suites. Test fixtures stay temporary/local and invoke supported product entries.
4. Run affected checks, inspect the complete diff and private/unrelated files, and checkpoint only
   this Task. Hand the immutable candidate and actual results to B. Keep all corrections in this
   same Task.

## Acceptance criteria

- [ ] Actual scheduled source-preflight failure with no Task yields a complete frontend-decodable
  `failureStage`, preserving the exact failure category and next action.
- [ ] Existing historical pre-start failures become readable through projection alone; no database
  migration, history rewrite, authorization grant or old-work replay is required.
- [ ] A mixed actual API page renders both the pre-start failure and completed/no-work sibling;
  filtering/refresh retain truthful counts/context and do not create work or authority.
- [ ] Healthy empty history, formal-Task failure/partial evidence, evidence-unavailable state and
  genuine denied/malformed reads retain their current distinctions and behavior.
- [ ] Records remain read-only and bounded; no Task Center ownership/retry safety/RBAC/pin or
  secret-redaction change. New tests fail on Task Base and pass on the corrected candidate.

## Required tests

### Developer — affected tests

Run from repository root unless the command specifies `web/`:

- `python3 scripts/check_governance.py` — disclose the one-Task lifecycle exception above.
- `.venv/bin/python -m unittest tests.test_automation_workspace_read_model` — complete envelope,
  mixed records, exact ownership, historical outcome and passive-read/denial behavior.
- Run the new real Scheduler/Worker pre-start regression by its exact unittest name; record the
  name/result in the handoff (reuse `tests.test_v2_automation_run_once` fixtures where practical).
- In `web/`: `npm run test -- run src/features/operations/AutomationWorkspaceReadModel.test.tsx`
  — actual backend response through fetch/strict decoder/page, mixed rows and read-only refresh.
- `.venv/bin/ruff check <changed Python files>` and
  `.venv/bin/ruff format --check <changed Python files>`; in `web/`,
  `npx prettier --check <changed Web test files>` and `npx eslint <changed Web test files>`.
- `git diff --check`. Run no whole-repository Python/Web/E2E/release matrix as Developer.

### B — acceptance

Review Task Base..candidate and independently reproduce the original source-preflight journey
through the actual API and strict frontend. Retain exact SHAs/commands/results and red-before-fix
evidence in stable ignored storage.

- Repeat/reuse matching affected results only with explicit input identity; run any missing cases.
- `.venv/bin/python -m unittest tests.test_automation_workspace_read_model tests.test_v2_automation_run_once`
  plus any new dedicated fixture/regression module: directly affected read/Worker integration.
- In `web/`: `npm run test -- run src/features/operations/AutomationWorkspaceReadModel.test.tsx src/entities/operations/automation.test.ts src/shared/api/api-client.test.ts`.
- In `web/`: `npm run typecheck` and `npm run build`.
- In `web/`: `npm run test:e2e -- --config=playwright.python.automation.config.ts tests/e2e/automation-workspace.python.spec.ts --grep 'records tab|records page traverses|healthy empty history'`
  — built production assets, real API records navigation/paging/empty state. The new actual-response
  component regression supplies the missing pre-start branch coverage.
- Check changed-file quality/whitespace, exact records-read no-work evidence and guard result.
  No full-repository/T4 regression is assigned: production changes only add read-projection fields,
  without mutation, schema, permission, concurrency or execution changes.

## Non-goals and handoff

No ResourceLibrary deployment-identity fix, deployment configuration change, new authorization,
history clearing, schema migration, execution change, second recovery surface, unrelated refactor,
Slice/Roadmap/Progress change or Git push. The user's latest boundary is local code, tests and
independent B review only: no deployment, remote operations or push in this round. The patch must
require no data cleanup or media replay.

Developer reports READY FOR B REVIEW with full checkpoint SHA, changes, affected commands/results
and remaining risks. B reports PASS/FIX REQUIRED for this patch alone, then restores the compact
no-active-Task notice after PASS. Preserve unrelated/untracked work and private configuration.
