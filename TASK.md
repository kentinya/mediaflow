# Task 42.3 — Native live-file organize admission and selected-run return

This Task follows [the development workflow](docs/development-workflow.md) and is subordinate to
the current [`SLICE.md`](SLICE.md).

```text
Task ID: 42.3
Parent Slice: 42
Status: FIX REQUIRED
Task Base: c55bb3cef6efa8b51158831f4136d7bc3d5fd490
Difficulty: High
Test Level: T4
Planner / Reviewer: B
```

## Goal

Complete Slice RO-4 and its RO-1/RO-7 navigation, admission-reconciliation and privacy integration:
an authenticated operator starts `新建整理任务` in the task center, selects a single or bounded
multiple eligible live ResourceLibrary files, reviews the existing exact Preview, explicitly
authorizes execution and returns to the same task center with the admitted run selected. Preserve
the ordinary Files-originated journey and its return context.

## Why This Task Exists

At Task Base, `OperationsLanding.tsx` links to `OrganizeNewPage.tsx`, which presents an English
explanation and generic Files link without passing the chosen ResourceLibrary or operations
context. The live bounded Files selection, server-held intent, choice, Preview and queued execution
already exist. `StorageFilesPage.tsx` carries only Files return context through intent/Preview;
`OrganizePreviewPage.tsx` navigates known admission to the separate execution page rather than the
selected unified run. Its network-error copy claims nothing was submitted without proving that.

The next coherent unit is the complete new-task → live files → exact Preview → admitted run journey,
including its safe failure/return behavior. Reuse these existing surfaces and application services;
do not build another file browser, task engine, generalized workflow or execution authority.
High/T4 reflects exact admission, unknown command outcomes, immutable pins and permission isolation.

Previous Task 42.2 B review (completed before replacing TASK.md):

```text
Reviewed: cf7099a478a203f3f29ac57ef5b8acc295aadaa9..faabf20dc034c4c8da310928b3f39b0512616da6; completion report at c55bb3cef6efa8b51158831f4136d7bc3d5fd490
Decision: PASS
Slice Required Outcomes all satisfied: NO
Next: NEXT TASK
```

B audited the actual full range and both correction checkpoints against AC-T1–AC-T8. The former
Manual explanation and cross-run log blockers are resolved through exact durable links; the final
standalone correction reuses existing checkpoint/Result/PipelineEvidence, preserving honest Manual
plan unavailability. B reran the unchanged legal production Local Storage processing-chain repro:
CREATE_DIRECTORY/MOVE, created directories, C identity/A downstream policies and cleanup are visible
in the native browser; all inspection requests are GET. No execution authority or second persistence
was added by this correction. Original dirty Task review is preserved at
`/tmp/mediaflow-b-task42-2-before-pass.md`; final Task/review copy is
`/tmp/mediaflow-b-task42-2-pass.md`. Developer's complete report remains in Git at the report SHA.

Independent B evidence (logs `/tmp/mediaflow-b42-2-r3-*`): Python full Ran 2113, OK (7 skipped;
2106 passed); all 13 exact focused commands passed, 432 total; detail/plan/log suites 53 passed;
release/security/migration/preflight 19 passed. Web full 61 files / 939 passed; original focused command serial rerun 33 files / 521 passed.
Real Python browser 12/12 passed, covering producer/Worker linkage, Manual and standalone durable
explanations/export/refresh/restart. Docker release-security passed using an isolated daemon-visible
TMPDIR and cleaned its resources; wheel smoke passed, schema 42. Python/Web quality/build, two
example config validations, governance, whitespace/manifest/private/dependency checks and unchanged
reference checksum passed. The 7 pre-existing isolated Storage real-service/endurance skips remain
explicit; no required local gate was unavailable. Existing chunk/SQLite ResourceWarnings remain.

Preserved failures: the first overlapping Web focused run was 520 passed / 1 failed (Automation
heading timeout), followed by unchanged complete serial passes above. Required fake browser run
remains 63 passed / 2 failed, deep-link.spec.ts:209 and :479. B's prior accepted-code run at ac5a43e
(which differs from this Task Base only in TASK.md) was 58 passed / these same 2 failed
(`/tmp/mediaflow-b-r4-e2e.log`); the clean earlier Base export reproduced them independently
(`/tmp/mediaflow-b-r3-base-deeplink.log`, 12 passed / 2 failed). These are proven pre-existing,
unrelated failures, never labelled PASS. Their spec/package/lockfile remain unchanged. No assertions,
skips or timeouts were relaxed. All Developer intermediate failures remain in its Git report. An intermediate B governance call
after setting the completed Task header to PASS refused that unsupported active-Task status;
archive/replacement with PLANNED resolves the transition without changing the guard or product.
Final governance below is evaluated against the new actual active Task.

After PASS B reevaluated all RO-1–RO-7: native inventory/detail/navigation, unified query/history and
RO-3 explanation/export are delivered; RO-4 still has the new-entry/return gap, RO-5 lacks safe queued
native Continue and RO-6 lacks native task-linked decisions/failed-analysis recovery. RO-7's read/
privacy integration is delivered; later admission/control/recovery integration is still open.
No Contract issue awaits A. Slice remains ACTIVE, so Slice Final is not applicable. The two
correction rounds retained the bounded read boundary and existing execution authority; the next
Task likewise reuses complete existing behaviors. No production implementation file or unrelated
user image was edited by B.

## Implementation Scope

```text
Existing live-source/intent/Preview/admission contracts → bounded durable linkage/reconciliation
→ shared Application/API behavior → Files and Operations routing/forms → Tests
```

### Operator journey

- **Entry:** `新建整理任务` from `操作与任务`, with optional existing ResourceLibrary scope;
  direct new-task URLs and ordinary Files organize remain supported.
- **Visible state:** actual enabled ResourceLibrary and live bounded directory/file selection,
  eligibility and limits, pinned intent/choices, exact Preview targets/operations/attachments/
  conflicts and destructive implications; admission/Worker waiting and eventual item outcomes.
- **Action:** select eligible live files, supply only necessary human choices, review Preview,
  explicitly execute the exact selected candidates, or cancel/back to preserved bounded context.
- **Success:** known durable admission resolves its exact unified run, selected in the task center
  before or after Worker linkage; its independent items/results are inspectable without raw tokens.
- **Failure:** missing setup/policy/permission, Storage read failure, invalid selection, stale source/
  intent/Preview, conflict and failed or unknown submission remain distinct; no empty-success claim.
- **Recovery:** retain safe selection/input or the known durable intent/Preview/execution; refresh
  prerequisites or exact durable evidence, explicitly revise/re-Preview when needed, and reconcile
  unknown admission before allowing another command. No automatic submission or mutation replay.

### Required behavior and boundaries

1. Replace the explanation-only entry with a working native bounded selection journey. Reusing
   the existing ResourceLibrary Files route is preferred and explicitly allowed by RO-4. Preserve
   the task-center filters/selected run/detail state through validated bounded return context.
   The selected ResourceLibrary is meaningful; unavailable/deleted scope offers a safe choice.
   MediaLibrary remains a destination/browser, never an organize source.
2. Reuse live Storage/ResourceLibrary admission and eligibility for single/bounded multi-file
   selection. Server resolves SourceIdentity and RecognitionType-bound policies; a FileIndex row,
   client path or frontend eligibility flag never authorizes physical selection or execution.
   Preserve independent choices and explain refusals without losing unaffected input.
3. Integrate the existing intent/choice/Preview/confirm surfaces into the Chinese native journey.
   Show exact target, operation, attachments, conflicts and applicable overwrite/source-cleanup
   implications. Preview and choice-only actions remain zero-mutation. No unnecessary repeated
   confirmation, raw authority-token entry, CLI or V1 fallback for this ordinary journey.
4. Explicit execute submits only the reviewed selection and server-held exact authority. Resolve
   known admission to the durable run through existing execution/Job/Task links; queue waiting is
   visible and does not require Task creation first. Preserve list context while selecting the
   admitted run. Files-originated users retain a meaningful return to their library/directory.
5. Treat transport/malformed/lost responses as unknown until exact durable evidence proves the
   outcome. Reuse existing exact admission-equivalence checks and bounded persisted relations;
   any necessary read projection/correlation must bind principal, Preview, item set, versions,
   pin and destructive permissions, and cannot admit work or mint/reissue authority. Do not match
   by filenames, time, current Active or merely overlapping selections. If exact reconciliation
   is unavailable, explain the uncertainty and retain investigation actions without resubmission.
6. Preserve selection/input on known refusal and keep accepted intent/Preview/execution after
   refresh, auth continuation and process restart. Permission/principal changes clear owned forms,
   selections and caches; return URLs contain no secrets, host roots or authority material. Stale
   configuration/source requires the existing safe refresh/re-Preview path, not silent repinning.
7. Keep keyboard/focus/back and narrow-screen behavior usable. Failed reads cannot authorize
   commands. Preserve Scan/Preview, inventory/detail/export, both library kinds' Files/direct
   commands/transfers, existing control paths, Rules/Settings return, Automation and Notifications.

Frozen: Slice Contract/Base, Roadmap, canonical requirements, Product Experience and reference
images; pipeline/rule semantics, physical source authority, policy/type mapping, authorization
consumption/destructive permissions, Worker ownership/leases/fences, Storage adapters and
OrganizerExecutor mutation behavior. Use existing persistence. A minimal compatible additive
link/correlation is permitted only if required for this exact admission/reconciliation journey;
it is never a second lifecycle or execution authority.

## Acceptance Criteria

- [ ] **AC-T1 — Complete new-task entry:** task-center new organize starts actual bounded live
      ResourceLibrary selection, carries valid current scope/return context, and works from direct
      URLs. Single/multiple eligible files reach existing intent/Preview without a generic link gap.
- [ ] **AC-T2 — Exact explained Preview:** server-derived identity, C identity under A downstream
      policies, choices, targets, operations, attachments and conflicts remain correct. Destructive
      permission is explicit only where applicable. Read/choice/Preview performs zero media mutation.
- [ ] **AC-T3 — Selected durable run:** one explicit exact execution admits at most one equivalent
      execution; known admission returns to its exact selected unified run, including pre-Task/Worker
      waiting and later linkage/results. Narrower/overlapping/differently bound submissions cannot
      resolve to unrelated work. No raw execution tokens or avoidable CLI/V1 handoff.
- [ ] **AC-T4 — Safe actionable failure:** missing setup/policy/permission, read failure, invalid/
      stale selection or Preview and conflicts preserve safe input/durable evidence and identify
      a meaningful next action. Unknown/lost/malformed admission responses never claim no submission,
      auto-repeat, silently broaden scope or authorize another execution before exact reconciliation.
- [ ] **AC-T5 — Context and privacy:** cancel/back, browser history, refresh/auth continuation and
      restart preserve the appropriate bounded Operations/Files context and durable work. Forms,
      selection and caches clear across principals; malformed return context fails safely; no
      secret, physical root or authority appears in URLs, errors, DOM or exports.
- [ ] **AC-T6 — Compatibility and safety:** existing Files-originated organize, Scan/Preview,
      inventory/detail/records/export and direct commands/transfers remain usable. Backend RBAC,
      source revalidation, immutable pins, exact authority, duplicate/fencing/Worker gates and
      OrganizerExecutor-only mutation remain unchanged. No uncertain replay or operation fallback.
- [ ] **AC-T7 — Production journey proof:** real Python-backed browser starts from the new task
      entry, selects temporary live files, creates/reviews Preview, explicitly admits execution,
      inspects the selected run and completes through the real Worker. Verify return/auth/restart
      and unknown-admission reconciliation using actual production admission/services and legal
      configuration; fixture-only successful navigation is insufficient.
- [ ] **AC-T8 — Reviewable T4 checkpoint:** required focused/full, quality/security/package and
      affected migration gates have honest commands/totals/skips/failures/unavailable results.
      No private config/credentials, reference edits, unrelated changes or weakened coverage.

## Required Tests

Use temporary SQLite/storage and synthetic/local Provider dependencies. Never use real credentials
or user media. Record every attempt and its actual result; unchanged serial reruns are allowed,
but do not hide failures, weaken assertions/timeouts or label unavailable gates PASS.

### Focused and integration

Extend existing suites, adding a coherent new-entry/admission suite only when needed. Cover legal
live selection with/without FileIndex, bounded/mixed eligibility, policies/C identity, exact choice/
Preview and execution, stale source/Active/pins, RBAC, concurrent/duplicate/lost-response admission,
exact principal/selection/permission reconciliation, pending Job→Task linkage, Worker wait/restart,
zero mutation before explicit execution, unknown effects and preserved independent results.

```sh
.venv/bin/python -m unittest tests.test_v2_manual_organize tests.test_manual_organize_intent tests.test_manual_organize_preview tests.test_manual_organize_execution tests.test_manual_operations_contract
.venv/bin/python -m unittest tests.test_operations_workspace tests.test_operations_run_inventory tests.test_operations_run_detail tests.test_processing_worker_readiness
.venv/bin/python -m unittest tests.test_direct_file_operations tests.test_direct_file_transfers tests.test_file_catalog_api tests.test_api_security
```

Web models/API/router/forms cover new entry through admission/selected run, bounded validated return
context, multi-file choices, independent refusal, malformed/401/403 responses, unknown admission,
no automatic repeat, permission/principal change, keyboard/narrow/history and compatibility.

From `web/`:

```sh
npm run test -- --run src/entities/operations src/features/operations src/features/library src/shared/api src/shared/navigation src/routes
npm run test:e2e -- tests/e2e/operations.spec.ts tests/e2e/manual-organize.spec.ts tests/e2e/manual-operations.spec.ts tests/e2e/deep-link.spec.ts
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts
```

Extend the real Python harness/spec above to drive the new-task Files journey, not only create work
through a harness control route. A separate real spec is allowed under the same isolated boundary;
report its exact command. Run all Playwright invocations sequentially to preserve shared artifacts.
The two Base-proven deep-link failures remain reportable pre-existing failures unless this Task's
changes actually affect them; no automatic waiver for any new failure.

### Full, quality, safety and packaging

```sh
python3 scripts/check_governance.py
.venv/bin/python -m unittest discover -s tests
.venv/bin/ruff format --check .
.venv/bin/ruff check .
.venv/bin/python -m compileall -q mediaflow tests scripts
.venv/bin/python -m pip check
.venv/bin/python -m mediaflow.cli --config config/strategy.example.json config validate
.venv/bin/python -m mediaflow.cli --config config/mediaflow.phase13.2.example.json config validate
.venv/bin/python -m unittest tests.test_release_security tests.test_release_validation tests.test_migration_rehearsal tests.test_upgrade_preflight
.venv/bin/python scripts/docker_release_security_smoke_test.py
git diff --check
git diff --check c55bb3cef6efa8b51158831f4136d7bc3d5fd490
sha256sum docs/pics/操作与任务.png
git check-ignore config/alist.json
git ls-files config/alist.json
rg -n -i 'ffprobe|ffmpeg' mediaflow pyproject.toml
```

Docker may use an isolated daemon-visible TMPDIR; report the actual invocation and clean only
gate-owned resources. Build a wheel with `.venv/bin/python -m pip wheel . --no-deps
--no-build-isolation -w <temporary-output>` and run `.venv/bin/python scripts/wheel_smoke_test.py
<built-wheel>`. Any additive persistence requires a real Task-Base schema fixture preserving pins,
existing admissions/results/ownership/authority and fail-closed incompatible/failed upgrades.

From `web/`:

```sh
npm run test -- --run
npm run typecheck
npm run lint
npm run format:check
npm run build
```

Reference SHA-256 remains `a8a5dc329891207b0feb487fa60690e97072d11b73da1136324459bf79915f86`.
Private config stays ignored/untracked/unstaged; forbidden dependency search has no matches. Audit
the complete Base..Head/staged manifest without printing private configuration.

## Non-goals

- Work outside Slice 42; changing Contract/Base, Roadmap, canonical requirements/reference or closing
  the Slice; implementing the next Slice.
- RO-5's new async Continue/control authority and RO-6's task-linked decisions/failed-analysis
  recovery commands. Existing choices necessary for a new organize intent stay in this Task.
- New file browser/task engine/providers/operations, unbounded or MediaLibrary source organization,
  scheduling, history deletion, bulk cross-task recovery, universal rollback, SSE/WebSocket or V1 retirement.
- Recreating consumed execution authority, changed-plan autoexecution, uncertain mutation replay,
  silent fallback, unrelated refactors, wording-only or optional-proof cleanup.

## Developer Completion Report

This report covers Task 42.3 cumulatively: the original implementation checkpoint
`eda07568000b036c1dbcd84f8f875c96ecdb722e` plus this B-requested correction checkpoint. Task ID,
Task Base, Goal and Scope are unchanged; only the B P1 blocker and its direct root cause were fixed.

### Changed Files

This correction checkpoint (`TASK.md` plus the P1 fix):

- `web/src/features/operations/OperationsLanding.tsx` — the `新建整理任务` entry spreads the
  existing `operationsReturnSearch(returnContext)` helper instead of `returnContext || undefined`,
  so the valid empty default-list origin is carried as a present `returnOps=` marker.
- `web/src/shared/navigation/destination-model.ts` — `setJourneyOperationsContext` replays an
  empty-but-present `returnOps` unchanged through authentication continuation on every journey
  surface (new/intent/Preview/execution, ResourceLibrary Files, landing reconnect). An *absent*
  key still means "not Operations-originated"; nonempty contexts keep the existing canonical
  re-validation and tampered values are still dropped.
- `web/src/shared/navigation/destination-model.test.ts` — new empty-origin replay case across all
  five journey surfaces plus the absence-vs-present contrast, and the landing reconnect case.
- `web/src/features/operations/OperationsInventory.test.tsx` — new default-list entry test: the
  entry link carries the exact empty `returnOps=` marker, and marker + admitted run resolves to the
  same bounded landing search the real router accepts.
- `scripts/operations_inventory_harness.py` — one additional synthetic fixture file
  (`Four.2004.mkv`) with its synthetic metadata candidate (`tmdb` 104 "Four" 2004); the
  `manual-file-state` read accepts a bounded `file=` query over the four harness-created files
  (default still `Three.2003.mkv`). Harness-only: no product code, no persistence, no new endpoint.
- `web/tests/e2e/operations-inventory.python.spec.ts` — one new real-browser test starting from the
  default unfiltered, unselected task center and covering the empty-origin journey, the selected
  durable run, auth continuation, real Worker completion and real runtime restart.
- This Developer Completion Report in `TASK.md`.

Delivered earlier in this Task at `eda07568000b036c1dbcd84f8f875c96ecdb722e` (unchanged by this
correction): `mediaflow/application/manual_organize_execution.py`,
`mediaflow/interfaces/service_api.py`, `web/src/entities/operations/organize.ts`,
`web/src/shared/api/api-client.ts`, `web/src/features/library/StorageFilesPage.tsx`,
`web/src/features/operations/OrganizeExecutionPage.tsx`,
`web/src/features/operations/OrganizeIntentPage.tsx`,
`web/src/features/operations/OrganizeNewPage.tsx`,
`web/src/features/operations/OrganizePreviewPage.tsx`,
`web/src/shared/navigation/operations-return.ts`,
`web/src/shared/navigation/operations-return.test.ts`,
`web/src/features/operations/OrganizeRouter.test.tsx`, `web/src/routes/router.test.tsx`,
`web/tests/fake-server.mjs`, `web/tests/e2e/deep-link.spec.ts`,
`web/tests/e2e/library-files.spec.ts`, `web/tests/e2e/manual-operations.spec.ts`,
`web/tests/e2e/manual-organize.spec.ts`, `tests/test_v2_manual_organize.py`.

### Implemented

Correction (the B P1 blocker):

- The entry and auth-continuation paths now separate three states exactly: absent marker → not
  Operations-originated (Files-originated journey behavior preserved); present-but-empty marker →
  default-list Operations origin (returns to the task center with the admitted run selected);
  nonempty marker → existing validated filter context. Known admission from the default list now
  selects its exact unified run instead of opening the separate execution page.
- Reused the existing `operationsReturnSearch` helper for the entry rather than inventing a new
  marker or a third state; journey pages already branch on `!== null`, so no page needed a change.
- Reused, unchanged: existing admission authority (still exactly one Execute POST, no replay),
  existing Preview/execution links, bounded Files returns, exact admission-equivalence checks,
  Worker claim/restart ownership, and all authorization/destructive-permission gates.
- The empty-origin write is confined to the harness fixture (one more synthetic temporary file) and
  a bounded harness-only query parameter; no product behavior, schema or authority changed.

Task as a whole (unchanged by this correction):

- A bounded read-only admission reconciliation endpoint whose `known` result requires the exact
  principal, Preview, selected item set, intent version, immutable configuration pin, per-item
  versions/fingerprints and destructive permissions from the consumed persisted authority. The read
  does not admit work, mint authority or mutate Storage.
- The Chinese native `新建整理任务` journey: enabled ResourceLibrary choice → live Files selection →
  existing intent → exact Preview → explicit execution → exact selected unified run, with validated
  bounded Operations and Files return context through navigation and authentication continuation.
- Unknown/lost/malformed/5xx Execute responses stay locked until the exact durable read resolves
  them; a Preview reads its bounded durable execution history before exposing Execute.
- Localized manual organize intent/Preview/execution surfaces including operation and
  destructive-effect labels and action-oriented recovery copy.

### Tests and Results

Correction-focused and required Task gates, all run on the final tree unless noted:

- `python3 scripts/check_governance.py` — **PASS**.
- `.venv/bin/python -m unittest tests.test_v2_manual_organize tests.test_manual_organize_intent tests.test_manual_organize_preview tests.test_manual_organize_execution tests.test_manual_operations_contract` — **PASS**, 103 tests.
- `.venv/bin/python -m unittest tests.test_operations_workspace tests.test_operations_run_inventory tests.test_operations_run_detail tests.test_processing_worker_readiness` — **PASS**, 114 tests.
- `.venv/bin/python -m unittest tests.test_direct_file_operations tests.test_direct_file_transfers tests.test_file_catalog_api tests.test_api_security` — **PASS**, 176 tests.
- `.venv/bin/python -m unittest discover -s tests` — **PASS**, 2119 tests, 7 skips. The 7 skips are the explicitly `BLOCKED` real OpenList/S3/SMB service and endurance profiles (external-environment gates), recorded as unavailable, never as PASS.
- `.venv/bin/ruff format --check .` — **PASS**, 335 files. `.venv/bin/ruff check .` — **PASS**. `.venv/bin/python -m compileall -q mediaflow tests scripts` — **PASS**. `.venv/bin/python -m pip check` — **PASS** (only a pip cache-directory ownership warning).
- `.venv/bin/python -m mediaflow.cli --config config/strategy.example.json config validate` and `.venv/bin/python -m mediaflow.cli --config config/mediaflow.phase13.2.example.json config validate` — **PASS**.
- `.venv/bin/python -m unittest tests.test_release_security tests.test_release_validation tests.test_migration_rehearsal tests.test_upgrade_preflight` — **PASS**, 19 tests.
- From `web/`, `npm run test -- --run src/entities/operations src/features/operations src/features/library src/shared/api src/shared/navigation src/routes` — **PASS**, 659 tests; `npm run test -- --run` — **PASS**, 62 files / 952 tests; `npm run typecheck`, `npm run lint`, `npm run format:check`, `npm run build` — **PASS** (known >500 kB chunk-size warning only).
- From `web/`, `npm run test:e2e -- tests/e2e/operations.spec.ts tests/e2e/manual-organize.spec.ts tests/e2e/manual-operations.spec.ts tests/e2e/deep-link.spec.ts` — **FAIL / PRE-EXISTING / UNRELATED**, 66 passed / 2 failed (`deep-link.spec.ts:211` and `:481`; B proved both at Task Base, spec/package/lockfile untouched).
- From `web/`, `npm run test:e2e -- tests/e2e/library-files.spec.ts` — **PASS**, 40 tests.
- From `web/`, `npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts` — **PASS**, 14 tests (the 13 previously reviewed plus the new default-unfiltered-origin/empty-auth test), verified three consecutive times on the final tree.
- `.venv/bin/python -m pip wheel . --no-deps --no-build-isolation -w <temporary-output>` and `.venv/bin/python scripts/wheel_smoke_test.py <built-wheel>` — **PASS**, schema 42; temporary wheel output removed after the smoke test.
- `.venv/bin/python scripts/docker_release_security_smoke_test.py` — **FAIL / ENVIRONMENT**: both attempts were rejected by the Docker daemon with `invalid mount config for type "bind": bind source path does not exist` for the smoke script's own generated temporary `deployment.env`/`mediaflow.json`, so the gate never reached build/inspect. No gate-owned containers, networks or volumes remained; the unique test image and both TMPDIRs were removed. The prior checkpoint's Docker PASS is the last valid Docker evidence; this correction touches no container/packaging code. Recorded as unavailable, never as PASS.
- `git diff --check` and `git diff --check c55bb3cef6efa8b51158831f4136d7bc3d5fd490` — **PASS**.
- Reference image SHA-256 — **PASS**, `a8a5dc329891207b0feb487fa60690e97072d11b73da1136324459bf79915f86`. `config/alist.json` is ignored and neither tracked nor staged. The required FFmpeg/FFprobe search returned no matches (`rg` was unavailable in this shell; the equivalent `grep -rni` search over `mediaflow/` and `pyproject.toml` returned no matches).

Before-and-after evidence for the exact B repro shapes (scratch specs removed after proof, so they
are not part of this checkpoint):

- Default unfiltered/unselected entry, pre-fix: the journey reached HTTP 202 and the browser landed
  on `/ui-v2/operations/organize/execution/{executionId}` with `运行详情` absent — the reported
  AC-T3/RO-4 gap. Post-fix: the same journey lands on `/ui-v2/operations?run={taskId}` with
  `运行详情` visible.
- Direct entry with valid empty `returnOps=`, pre-fix: after Connect the URL was
  `/ui-v2/operations/organize/new` with the origin lost. Post-fix:
  `/ui-v2/operations/organize/new?returnOps=` — the AC-T5 gap is closed.

### Decisions

- Reused the existing `operationsReturnSearch` helper (whose contract already states that a
  present-but-empty context marks the default-list Operations origin) instead of introducing a new
  marker or widening `readOperationsReturnContext`'s return type.
- Replayed the empty marker verbatim through authentication continuation rather than
  re-canonicalizing it: an empty context carries nothing to validate, and verbatim replay keeps
  tampered nonempty contexts dropping to absent exactly as before (proved by the unchanged hostile
  value tests).
- Added the second harness fixture file plus a bounded `file=` query rather than reusing
  `Three.2003.mkv`, because the serial spec shares one harness database and the earlier journey
  moves that file away; the default argument keeps all existing assertions untouched.
- Kept the Task's execution authority and persistence exactly as reviewed: no new admission path,
  no replay, no second lifecycle, payload still exactly one Execute POST.

### Remaining In-Slice Work

- Only what B plans next. The Task's stated non-goals remain: RO-5 native queued Continue/control
  recovery and RO-6 task-linked decisions and failed-analysis recovery. This correction added no
  scope beyond the B P1.

### Risks / Deviations

- The new real-browser test was initially flaky, and the flake was in the test, not the product: it
  clicked `生成精确预览` immediately after `保存选择`, so the Preview sometimes submitted a
  not-yet-refetched intent version and the real backend correctly refused it with
  `manual_preview_conflict` (409). The test now waits for the save's own durable intent refetch
  before requesting the Preview; the assertion after the runtime restart was likewise scoped to the
  bounded `主条目` region instead of the whole detail region (Playwright strict mode). Three
  consecutive full-spec runs pass 14/14 on the final tree. No product behavior, assertion strength
  or timeout was weakened to obtain that.
- One intermediate full-suite run reported `FAILED (failures=1)` during a verbose rerun with
  unchanged source; the immediate unchanged rerun was fully green (**PASS**, 2119 tests, 7 skips).
  Both results are recorded; no assertion, skip or timeout was changed to obtain the green run. B
  may want to note the flake.
- Docker gate is **FAIL / ENVIRONMENT** as documented above — environment-limited, not a product
  regression.
- The two fake deep-link E2E failures remain **FAIL / PRE-EXISTING / UNRELATED**, exactly as B
  accepted; their spec, package and lockfile are unchanged.
- Pre-existing untracked reference images under `docs/pics/` and existing SQLite
  `ResourceWarning`s remain and are excluded from this checkpoint. No real credentials or
  `config/alist.json` were staged.

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: <filled by the report update after this commit>
```

## B Review Result

```text
Reviewed: c55bb3cef6efa8b51158831f4136d7bc3d5fd490..eda07568000b036c1dbcd84f8f875c96ecdb722e
Decision: FIX REQUIRED
Slice Required Outcomes all satisfied: NO
Next: SAME TASK FIX LOOP
```

- **P1 — Preserve the default task-center origin and its authentication continuation.**
  **Current production reachability:** an authenticated operator opens the supported default
  `/ui-v2/operations` list without filters or a selected run, clicks `新建整理任务`, chooses the
  enabled ResourceLibrary, selects a live file, saves its choice, generates the exact Preview and
  explicitly executes. B reproduced this with the current real Python API, checked Active
  configuration, production Local Storage and real Worker; no production capability was removed.
  **User impact:** the API returns 202 and the same admitted Task completes its actual MOVE, but
  the browser opens `/ui-v2/operations/organize/execution/{executionId}` instead of the task center
  with that run selected. The native `运行详情` region count is 0; `返回操作与任务` also points to
  `/ui-v2/operations` without a run. A separate supported direct entry with valid empty
  `returnOps=` loses that origin during Connect authentication, producing the same routing gap.
  **Contract:** AC-T3 and AC-T5, Scope behavior 1/4/6, and Slice RO-4's selected-run return and
  RO-7's authentication/return-context integration are unmet.
  **Evidence:** `OperationsLanding.tsx:1140` uses `returnContext || undefined`, dropping the valid
  empty origin; `destination-model.ts`'s `setJourneyOperationsContext` drops an empty canonical
  context too. Against `.venv/bin/python scripts/operations_inventory_harness.py --port 4184`,
  `node /tmp/mediaflow-b42-3-default-origin-proof-r2.mjs` records one Execute POST, HTTP 202,
  completed exact Worker linkage and the wrong URL, then fails the AC-T3/RO-4 assertion.
  `node /tmp/mediaflow-b42-3-empty-auth-origin-proof.mjs` records `hasOrigin: false` after Connect
  and fails the AC-T5 assertion. Their adjacent `.json` and `.log` files retain the results;
  `/tmp/mediaflow-b42-3-review-evidence.md` records the independent validation attempts honestly.
  **Required correction:** preserve the distinction between absent Files origin and valid empty
  Operations origin at entry and through the existing Files/intent/Preview/execution/auth journey.
  Known admission must select its exact unified run even from the default list and after auth.
  Retain bounded validation, nonempty filter context and ordinary Files returns; reuse existing
  admission authority without replay. Extend the real browser coverage to the default unfiltered,
  unselected entry and empty-context authentication, rather than proving only a filtered entry.
  Fix within Task 42.3; Task Base, Goal and Scope remain unchanged.
