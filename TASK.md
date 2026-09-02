# Task 25.6 — Fail-closed authorized scheduled organization and Automation per-item outcome/recovery

This Task follows [the development workflow](docs/development-workflow.md) and is subordinate to the
current [`SLICE.md`](SLICE.md).

```text
Task ID: 25.6
Parent Slice: 25 — Scheduled Automation and Unattended Organization
Status: IN PROGRESS
Task Base: 1bd8a08eeafa67470e4e39c68e2520e339a0aa2a
Difficulty: High
Test Level: T4
Planner / Reviewer: B
```

## Goal

Make an authorized scheduled occurrence fail closed at every affected boundary with durable,
bounded, secret-free per-item state, and let the operator see and resolve those per-item outcomes
from the Automation journey itself. This Task advances Slice 25 `RO-6` and completes the remaining
part of `RO-7`; `RO-1`…`RO-5` are already accepted by Tasks 25.1–25.5 and are not reopened here.

## Why This Task Exists

Task 25.5 made authorized unattended mutation reachable. What an authorized run actually does at
each failure boundary, and what the operator can see and do about it from Automation, is still
partly unimplemented and entirely unproven. Three gaps exist in code today:

1. Execution-boundary explanations are flattened. With `secret_free_errors=True` — the mode every
   definition-scoped run uses (`mediaflow/application/automation_definition_execution.py:473`) —
   `mediaflow/application/media_organizer.py:379` replaces every `ExecutionResult.errors` entry with
   the single string `"workflow execution failed"`. `OrganizerExecutor` produces distinguishable,
   already secret-free reasons at that boundary (`"destination already exists"`,
   `"attachment destination already exists: …"`, `"cross-storage LINK is not supported"`,
   `"plan destination does not match MediaLibrary root and relative path"`,
   `"operation … is not executable"` — `mediaflow/application/organizer.py:326-470,700-730`), and all
   of them are lost. The generic fallback in `_failure_message`
   (`mediaflow/application/media_organizer.py:568`) additionally labels a scheduled *organize*
   failure `"single-item DryRun analysis failed"`. An operator therefore cannot tell an unsupported
   capability from a collision, a permission denial or a transient Storage error, and gets no next
   action — which is exactly what `RO-6` and product rule 1 (retry is not recovery) forbid.

2. The Automation journey has no per-item outcome view. The shared occurrence projection
   (`mediaflow/application/automation_definition_occurrence.py:104-193`) exposes only last-occurrence
   scalars plus a linked `lastTaskId`; it carries no outcome breakdown and no list of items awaiting
   an operator decision. `RO-7` requires per-item outcomes and recovery to be visible from the
   Automation view after reload. The per-item surface itself already exists and must be reused, not
   rebuilt: `ProcessingCheckpointService.summary()`
   (`mediaflow/application/processing_checkpoint.py:94`), the Task detail route that already returns
   items with checkpoints and recovery batches (`mediaflow/interfaces/service_api.py:3137-3165`), and
   the Web renderer that already shows `stage`, `blocker_kind`, `effect_certainty`, `retry_safety`
   and `recovery_request` (`mediaflow/interfaces/operator_ui.py:2440-2471`).

3. A bounded run can be mistaken for an exhausted scope. `process_library` cancels the scan once the
   configured limit is reached (`mediaflow/application/media_organizer.py:487`), so items beyond the
   bound are never discovered or recorded, and nothing in the occurrence projection says the run
   stopped at its bound. `RO-6` requires unselected siblings not to be concealed.

Beyond those gaps, the Slice requires "real-execution safety evidence" for the authorized matrix and
none exists: operation capability across `MOVE`/`COPY`/`HARD_LINK`/`SOFT_LINK` plus attachments with
no silent substitution, collision handling across `Skip`/`Rename`/`Manual`/`Overwrite`, the boundary
that a grant implies no Overwrite/Delete/MOVE source removal/source-directory cleanup/rollback,
unstable source, Provider and Storage failure, injected partial or uncertain effect, and sibling
independence. `mediaflow/application/conflict_resolution.py:37-47` shows the intended fail-closed
shape today — `apply_configured` auto-resolves only `SKIP` and `RENAME` and returns `None` for
`OVERWRITE`, `MANUAL` and `INVALID_DESTINATION` so the item blocks — but no test proves that holds on
the unattended path, where no conflict decision and no overwrite confirmation is passed
(`mediaflow/application/automation_definition_execution.py:458-484`).

This is the largest coherent unit left inside the Slice: one vertical from the execution boundary to
the operator's Automation view, plus the evidence the Slice demands. It creates no new pipeline, no
new authority and no second recovery lifecycle.

## Implementation Scope

```text
Application → API → Web → Tests
```

- Application — bounded, classified, secret-free execution-boundary failure explanations for
  definition-scoped runs (category, durable state, retry safety, exactly one next action), preserved
  per item in `TaskItem`/`Result`/checkpoint state; the honest label for a scheduled organize failure
  instead of the DryRun fallback.
- Application — extend the shared occurrence projection with a bounded per-occurrence item outcome
  summary, the "stopped at the configured bound" statement, and a hard-capped attention list built
  from `ProcessingCheckpointService`. Read-only, deterministic, no Provider/Storage access.
- API — return that summary from the existing Automation definition detail and occurrences routes
  under unchanged RBAC, validation, cursor and page-bound rules. The existing per-item recovery
  routes stay the only recovery entry point.
- Web — render the summary, the bound statement and the attention list in the Automation detail
  panel with cross-links into the existing Task/per-item recovery surface; reproducible after reload.
- Tests — the T4 authorized-run matrix and falsification evidence below.

Frozen unless a listed Acceptance Criterion cannot be met without touching it, in which case the
change and its reason must be reported:

- grant authority resolution and the grant/revoke lifecycle accepted in Task 25.5
  (`mediaflow/application/unattended_execution.py`) — `authorize()`/`assert_live()` semantics must not
  be weakened;
- `RecognitionTypePolicy` ownership, Naming, Classification, Planner and `OrganizerExecutor` mutation
  authority;
- conflict-strategy semantics in `mediaflow/application/conflict_resolution.py` — no new automatic
  resolution may be added for `OVERWRITE` or `MANUAL`;
- Scheduler admission, Job fencing and due-state advancement (Tasks 25.3–25.4);
- the runtime schema: prefer no `SCHEMA_VERSION` bump. If a bounded read genuinely requires one, it
  must be additive, migrated, rehearsed and reflected in every schema-marker test.

## Acceptance Criteria

- [ ] 1. Every execution-boundary failure in an authorized scheduled run leaves a distinguishable
      bounded category — at minimum unsupported/denied capability, destination or attachment
      collision, invalid destination, Storage failure, Provider failure and uncertain/partial effect
      — together with what is durable, whether repeating is safe, and exactly one safe next action.
      The blanket `"workflow execution failed"` replacement and the `"single-item DryRun analysis
      failed"` label for scheduled organize runs are gone.
- [ ] 2. No explanation, log, audit, API or Web payload contains a credential, token, authorization
      header, cookie, private endpoint or private configuration value; bounded lengths are enforced.
- [ ] 3. No silent operation substitution. `MOVE`, `COPY`, `HARD_LINK` and `SOFT_LINK` each execute
      only the configured operation; an unsupported capability or a cross-storage `LINK` fails
      explicitly with the capability category and never falls back to another operation. A failing
      attachment never silently upgrades the item to success.
- [ ] 4. A live unattended grant alone never produces Overwrite, Delete, MOVE source removal beyond
      the configured operation, source-directory cleanup, rollback or operation fallback. With a
      configured `OVERWRITE` strategy an unattended occurrence blocks only the affected item for
      explicit confirmation and mutates nothing; no automation path sets `overwrite_authorized` or
      supplies a conflict decision on the operator's behalf.
- [ ] 5. Conflict matrix per item: `SKIP` produces a NOOP, `RENAME` a safe alternative destination,
      `MANUAL` and `OVERWRITE` leave that item alone waiting with a resolution path, and an invalid
      destination fails closed. Siblings in the same occurrence keep independent status, effects and
      Results and are never replayed or concealed.
- [ ] 6. Unstable source, Provider failure, Storage failure part-way through a batch and unresolved
      recognition/metadata/classification each leave the affected item durable with known or
      uncertain effect, retry safety and one next action, while completed siblings keep their
      effects. An uncertain mutation is never automatically replayed by the scheduled path or by any
      recovery entry point.
- [ ] 7. The occurrence projection exposes, from the same application service used by API and Web, a
      bounded per-item outcome summary (counts per durable item status including waiting kinds,
      skipped, ignored, partial, failed, cancelled and unchanged), an explicit statement of whether
      the run stopped at its configured item bound, and a hard-capped attention list of items needing
      an operator decision with stage, blocker kind, effect certainty, retry safety and one next
      action. It reuses `ProcessingCheckpointService`, adds no second checkpoint/recovery projection,
      and performs no Job, Task, grant, Provider or Storage work.
- [ ] 8. The Automation definition detail and occurrences API routes return that summary under the
      existing permissions, validation, cursor and page bounds, with no unbounded scan and no N+1
      read for a rendered page; existing payload fields and pagination shape stay compatible.
- [ ] 9. The Operator Web Automation detail panel renders the outcome summary, the bound statement
      and the attention list, cross-links each attention item into the existing Task/per-item
      recovery surface, survives reload, and introduces no new mutation action on the Automation
      surface.
- [ ] 10. API and Web report the same state, outcome, failure explanation and next action for the
      same occurrence and the same item.
- [ ] 11. Zero-mutation invariants hold: `scan-only` and `scan-and-plan` occurrences mutate nothing,
      and opening or refreshing the Automation list, detail, occurrence or history creates no Job,
      Task, grant, Provider request or Storage probe.
- [ ] 12. `RecognitionType C` remains `C` through scheduled plan, execution and Result while its
      configured downstream `A` Naming/Classification ownership stays visible.
- [ ] 13. Test Level T4 passes with actual reported results, including the falsification evidence
      below; no test is deleted, no assertion relaxed and no skip hidden.
- [ ] 14. The checkpoint contains only this Task and no private configuration, credential or
      unrelated file.

## Required Tests

Test Level T4. Every command below must be run and its actual result reported. New focused modules
are expected (for example `tests/test_automation_authorized_execution_matrix.py` and coverage added to
`tests/test_automation_definition_occurrence.py`); module names are the Developer's choice, the
coverage is not.

Focused:

- `./.venv/bin/python -m unittest tests.test_automation_definition_execution` — extended for the
  authorized matrix over temporary Local roots: `MOVE`, `COPY`, `HARD_LINK` and `SOFT_LINK` each
  executing only their configured operation with attachments; an unsupported capability and a
  cross-storage `LINK` failing explicitly with no substitution; `SKIP`, `RENAME`, `MANUAL` and
  configured `OVERWRITE` producing the per-item outcomes in Acceptance Criteria 4 and 5; an unstable
  source, a Provider failure, a Storage failure after the first successful item, and an injected
  partial/uncertain effect each leaving durable per-item state with one next action and no automatic
  replay; sibling independence; mixed RecognitionTypes with `C` remaining `C`; sub-scope and item
  bound still enforced under execution.
- A focused module for the bounded execution-boundary failure classification — every category in
  Acceptance Criterion 1 maps to its own bounded secret-free explanation, durable state, retry safety
  and single next action; length bounds enforced; no raw adapter message, credential, token, header,
  cookie or private endpoint reaches `TaskItem`, `Result`, checkpoint, occurrence, log or API payload.
- `./.venv/bin/python -m unittest tests.test_automation_definition_occurrence
  tests.test_processing_checkpoint` — the per-item outcome summary, the bound-reached statement and
  the capped attention list: correct counts across success, partial, failed, skipped, ignored,
  cancelled, unchanged and every waiting status; the cap honored with an honest "more items" signal;
  a bounded run reported as bound-reached and never as an exhausted scope; identical results from the
  bulk and single-definition projection paths; no Provider, Storage, Job, Task or grant side effect.
- `./.venv/bin/python -m unittest tests.test_automation_api tests.test_operator_ui
  tests.test_api_security` — the summary on the definition detail and occurrences routes under
  `READ`; RBAC refusal for an unauthorized principal; bounded pages and cursors unchanged; the Web
  panel rendering summary, bound statement and attention list with working cross-links into the
  existing per-item recovery surface; state reproduced after reload; no new Automation mutation
  action; the bounded secret-free error contract preserved.

Integration and affected regression:

- `./.venv/bin/python -m unittest tests.test_automation_definition_execution
  tests.test_automation_unattended_grant tests.test_automation_definition_occurrence
  tests.test_automation_task_definition tests.test_automation_task_definition_preview
  tests.test_automation_api tests.test_automation_admission tests.test_automation_job_fencing
  tests.test_cron_scheduler tests.test_execution_authorization tests.test_manual_organize_execution
  tests.test_conflict_resolution tests.test_task_persistence tests.test_task_pause_resume
  tests.test_task_retry tests.test_processing_checkpoint tests.test_processing_recovery_admission
  tests.test_recovery_continuation tests.test_recovery_batch tests.test_organizer
  tests.test_organizer_rollback tests.test_attachments tests.test_resource_library_pipeline
  tests.test_scanner tests.test_recognition tests.test_configuration_snapshot
  tests.test_api_credentials tests.test_api_security tests.test_operator_ui
  tests.test_migration_rehearsal tests.test_final_integration` — adjust only if a module name does not
  exist, and report the substitution.

Full regression:

- `./.venv/bin/python -m unittest discover -s tests -p 'test_*.py'` with actual run/skip totals. Any
  failure claimed pre-existing must be reproduced at Task Base
  `1bd8a08eeafa67470e4e39c68e2520e339a0aa2a` or on a clean `git archive` tree, with the reproduction
  command and cause recorded. The six known environment failures caused by the ignored local runtime
  database and `config/strategy.json` (`test_api_credentials` x2, `test_final_integration`,
  `test_resource_library_pipeline`, `test_runtime_storage_configuration` x2) count as pre-existing
  only with that evidence.

Falsification evidence (record the command and the observed result, not a claim):

- Byte-level before/after comparison of source and destination trees for each matrix case: exactly
  the configured operation happened, nothing else was created, moved, overwritten or deleted, and the
  source is still present for `COPY`/`HARD_LINK`/`SOFT_LINK`.
- A counting or refusing Storage double observes zero mutation calls for `scan-only`,
  `scan-and-plan`, an unauthorized or revoked occurrence, an `OVERWRITE`-configured collision and an
  unsupported-capability item.
- A configured `OVERWRITE` collision in an unattended run leaves the existing destination file
  byte-identical and the item waiting for confirmation.
- Deliberate regressions on a throwaway `git archive HEAD` copy (workspace untouched) make the new
  tests fail — for example letting an unsupported `LINK` fall back to `COPY`, auto-resolving
  `OVERWRITE` or `MANUAL` in `apply_configured`, restoring the blanket `"workflow execution failed"`
  string, automatically retrying an uncertain partial effect, dropping the bound-reached statement, or
  counting a waiting item as success in the outcome summary.
- Opening and refreshing the Automation list, detail, occurrence and history views creates no Job,
  Task, grant, Provider request or Storage probe.
- No credential, token, authorization header, cookie, private endpoint or private configuration value
  appears in any new explanation, summary, attention list, log, audit or API/Web payload.

Quality and safety gates:

- `./.venv/bin/ruff check .`
- `./.venv/bin/ruff format --check .`
- `./.venv/bin/python -m compileall -q mediaflow tests scripts`
- `./.venv/bin/pip check`
- `./.venv/bin/mediaflow --config config/strategy.example.json config validate`
- `./.venv/bin/mediaflow --config config/mediaflow.phase13.2.example.json config validate`
- forbidden `ffprobe`/`ffmpeg` runtime scan (no matches)
- wheel build plus isolated installed-wheel smoke (`scripts/wheel_smoke_test.py`); `python -m build`
  is unavailable in this virtualenv, so `pip wheel . --no-deps --no-build-isolation` plus the smoke
  script is the accepted substitute and must be reported as such, including the reported supported and
  runtime schema versions and whether migration is required
- if and only if the schema changes: a real upgrade of a database built by Task Base code, migration
  rehearsal tests, and every schema-marker test updated with nothing else changed in those files
- Markdown relative-link existence check for changed documents
- private-config/secret scan: `config/alist.json` and `config/strategy.json` remain ignored, untracked
  and unstaged; no credential-like value in `Task Base..Head`
- `git diff --check` and `git diff --cached --check`

External gates: report PASS/FAIL/SKIP/UNAVAILABLE honestly. Real production Storage, Provider
credentials and user media are not required and must not be used; use temporary Local roots plus
fake/in-memory Provider and adapter doubles.

## Non-goals

- Automatic replay of uncertain mutation, cross-run compensation, historical or crash rollback, and
  forced interruption of in-flight external calls — Slice-deferred.
- New recovery actions, a second recovery or checkpoint lifecycle, or a redesign of batch recovery,
  `ExecutionAuthorization`, `ManualExecutionAuthorization`, Task/TaskItem/Result or
  `OrganizerExecutor`.
- Any new unattended Overwrite or Delete authority, automatic conflict resolution, source-directory
  cleanup or operation fallback.
- Reopening `RO-1`…`RO-5`: definition management, Preview, Scheduler admission and the grant
  lifecycle stay as accepted, except where an Acceptance Criterion above cannot be met otherwise.
- Provider switching or credential lifecycle, notification Provider management and media-server
  refresh.
- The recorded P2 residual from the Task 25.5 review (the global `LIMIT` in
  `list_unattended_execution_grants`, production-unreachable): optional, not required by any
  Acceptance Criterion here, and not a blocker for this Task.
- Slice closure documents, Roadmap updates and the Closure Packet — B's work after this Task.

## Developer Completion Report

### Changed Files

- `mediaflow/application/processing_checkpoint.py`
- `mediaflow/application/recovery_admission.py`
- `mediaflow/application/organizer.py` and `mediaflow/application/media_organizer.py`
- `tests/test_processing_checkpoint.py` and `tests/test_processing_recovery_admission.py`
- `tests/test_automation_definition_execution.py`
- `tests/test_automation_authorized_execution_matrix.py`
- `tests/test_operator_ui.py`
- `TASK.md` (this Developer Completion Report, in the report-only follow-up commit)

### Implemented

- Ordered checkpoint guards so a retry-safe failure explanation cannot grant retry over a pending
  blocker, interrupted admission, unverified/unknown effect, or unavailable configuration snapshot.
  Recovery admission now re-checks those retry safety facts before accepting a retry request,
  including against a forged/stale action projection.
- Completed authorized scheduled E2E coverage for `SKIP`, `RENAME`, and `MANUAL` conflicts and an
  invalid destination, preserving independent sibling `TaskItem`/`Result` state and byte-level
  destination/source expectations. Configured `SKIP` now persists as `SKIPPED` with a warning rather
  than being misclassified as a failed execution-boundary error.
- Added authorized occurrence coverage for an unstable source, a Provider failure, and a Storage
  failure after a successful sibling. Each affected item remains durable with its category, effect
  certainty, retry safety and one next action; no automatic recovery request/replay is created and
  completed siblings retain their effects.
- Added Automation API read-only coverage for list/detail/occurrence plus Task and TaskItem
  checkpoint-history first-open and refresh paths, including SQL write detection, durable Job/Task/
  grant identity checks, and RBAC refusal without summary leakage. Added Operator Web assertions for
  bounded cards, bound statement, capped attention links, failure fields, reload path and no new
  Automation mutation action.

### Tests and Results

- `./.venv/bin/python -m unittest tests.test_automation_definition_execution` — PASS (21 tests).
- `./.venv/bin/python -m unittest tests.test_automation_authorized_execution_matrix` — PASS (8 tests).
- `./.venv/bin/python -m unittest tests.test_automation_definition_occurrence tests.test_processing_checkpoint`
  — PASS (26 tests).
- `./.venv/bin/python -m unittest tests.test_automation_api tests.test_operator_ui tests.test_api_security`
  — PASS (65 tests).
- The exact required integration command from this Task:
  `./.venv/bin/python -m unittest tests.test_automation_definition_execution tests.test_automation_unattended_grant tests.test_automation_definition_occurrence tests.test_automation_task_definition tests.test_automation_task_definition_preview tests.test_automation_api tests.test_automation_admission tests.test_automation_job_fencing tests.test_cron_scheduler tests.test_execution_authorization tests.test_manual_organize_execution tests.test_conflict_resolution tests.test_task_persistence tests.test_task_pause_resume tests.test_task_retry tests.test_processing_checkpoint tests.test_processing_recovery_admission tests.test_recovery_continuation tests.test_recovery_batch tests.test_organizer tests.test_organizer_rollback tests.test_attachments tests.test_resource_library_pipeline tests.test_scanner tests.test_recognition tests.test_configuration_snapshot tests.test_api_credentials tests.test_api_security tests.test_operator_ui tests.test_migration_rehearsal tests.test_final_integration` — FAIL / PRE-EXISTING / UNRELATED: 452 tests ran; four failures were the documented ignored local runtime/configuration cases: `test_api_credentials` x2, `test_final_integration`, and `test_resource_library_pipeline`.
- `./.venv/bin/python -m unittest discover -s tests -p 'test_*.py'` — FAIL / PRE-EXISTING /
  UNRELATED: 1096 tests ran, 6 failures, 7 skips. The six failures were exactly
  `test_api_credentials` x2, `test_final_integration`, `test_resource_library_pipeline`, and
  `test_runtime_storage_configuration` x2.
- The full regression failures were reproduced from a clean Task Base archive using
  `git archive 1bd8a08eeafa67470e4e39c68e2520e339a0aa2a`, with only ignored `config/strategy.json`
  and the temporary-tree runtime SQLite/history files copied in. That archive ran 1079 tests,
  skipped 7, and reproduced the same six failures.
- `./.venv/bin/ruff check .` — PASS; `./.venv/bin/ruff format --check .` — PASS (354 files);
  `./.venv/bin/python -m compileall -q mediaflow tests scripts` — PASS; `./.venv/bin/pip check`
  — PASS.
- `./.venv/bin/mediaflow --config config/strategy.example.json config validate` — PASS;
  `./.venv/bin/mediaflow --config config/mediaflow.phase13.2.example.json config validate` — PASS.
  Runtime `ffprobe|ffmpeg` scan — PASS, with no forbidden runtime matches.
- `./.venv/bin/pip wheel . --no-deps --no-build-isolation` and
  `./.venv/bin/python scripts/wheel_smoke_test.py dist/mediaflow-0.1.0-py3-none-any.whl` — PASS.
  `./.venv/bin/python -m build` — UNAVAILABLE: this virtualenv cannot execute `build.__main__`.
  The installed-wheel smoke reported supported schema 27, runtime schema 27, and migration
  required `NO`.
- Markdown relative-link existence check, private-config tracking/staging scan,
  `git diff --check` and staged diff check — PASS. `config/alist.json` and `config/strategy.json`
  remain ignored, untracked and unstaged.
- Falsification on throwaway `git archive HEAD` copies — expected FAIL: restoring an early
  retry-safe failure branch made the five-case checkpoint guard test fail, and restoring the old
  SKIP-as-error path made the authorized conflict test fail for the SKIP case. The workspace was
  untouched by both experiments.
- Production Storage/Provider services and credentials — SKIP by design; all new evidence uses
  temporary Local roots and fake/in-memory Provider and Storage doubles.

### Decisions

- Kept the existing immutable failure envelope and schema unchanged; the correction only restores
  the precedence of safety facts and strengthens retry admission validation.
- Kept conflict resolution and execution authority unchanged: only configured SKIP/RENAME resolve
  automatically; OVERWRITE/MANUAL remain waiting, and OrganizerExecutor remains the sole mutation
  boundary.
- Preserved Provider failure context when the configured retry policy is disabled so the scheduled
  path records `provider_failure` instead of converting it into an unrelated Storage failure.
- Represented intentional configured `SKIP` as a warning-backed `SKIPPED` execution result, keeping
  the existing `NOOP`/skip semantics and avoiding a false failure category.

### Remaining In-Slice Work

- No additional implementation work is known inside this Task. Task and Slice review status remain
  with B/A.

### Risks / Deviations

- The required integration/full regression commands retain the six documented pre-existing,
  environment-state failures; the clean Task Base archive evidence above is the cause evidence.
  Pre-existing unclosed SQLite test connections emitted `ResourceWarning` messages but did not alter
  test outcomes.
- `python -m build` is unavailable in this virtualenv; the Task-approved pip-wheel plus isolated
  smoke substitute passed. No schema marker or migration changed.
- No production credentials, external account authorization or user media were used.

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: 9980357c6ae270a5d9b09fb6abaf9225ebe86df7
```

## B Review Result

```text
Reviewed: 1bd8a08eeafa67470e4e39c68e2520e339a0aa2a..20a54263b0e0f4ac374573e710fc02ab122fd093
Decision: FIX REQUIRED
Slice Required Outcomes all satisfied: NO
Next: SAME TASK FIX LOOP
```

Reviewed diff range covers reported code Head `450ffc9` plus the report-only commit `20a5426`.
Only the unmet points are listed. Everything not listed here is accepted and must not be changed.

1. Acceptance Criterion 6 and the Slice safety invariant on uncertain effects are broken by
   `_actions()` in `mediaflow/application/processing_checkpoint.py:824`. The new
   `if failure is not None:` branch is placed before the blocker, `admission_interrupted`, effect
   certainty and snapshot guards, so a `retry_safe` explanation now overrides all four refusals, and
   `RecoveryAdmissionService.request()` (`mediaflow/application/recovery_admission.py:107-129`)
   re-validates only the snapshot — it never re-checks effect certainty or interrupted admission.
   Evidence — direct calls to `_actions()` with `failure_explanation("storage_failure",
   retry_safe=True)` versus `failure=None`, identical in every other argument:
   - `certainty=ATTEMPTED_UNVERIFIED`: `unknown / investigate(admissible=False) /
     "automatic_replay_refused: effect certainty is not verified"` becomes
     `safe / retry(admissible=True) / reason=None`.
   - `certainty=UNKNOWN`: same refusal becomes `safe / retry(admissible=True)`.
   - `raw_stage="admission_interrupted"`: `unsafe / investigate(admissible=False) /
     "manual_execution_reconciliation_required: exact authority was consumed before the execution
     state was published"` becomes `safe / retry(admissible=True) / reason=None`.
   - `status=WAITING_CONFIRM` with a confirmation blocker: `resolve_confirmation` with its
     `resolution_path` becomes `retry(admissible=True)`, so a waiting item loses the explicit
     resolution action Acceptance Criterion 5 requires.
   - `snapshot_resolvable=False`: `unsafe / investigate / "automatic_replay_refused: pinned
     configuration is unavailable"` becomes an advertised `safe / retry(admissible=True)`; admission
     still refuses, but the checkpoint, API and Web now offer a retry that cannot run.
   Correction direction: the failure explanation must not be able to grant an action. Subordinate it
   to the existing guards (evaluate it only after blocker, `admission_interrupted`, effect certainty
   and snapshot resolution have declined to refuse), or gate the `retry_safe` path on
   `certainty is EffectCertainty.NONE`, no blocker, `raw_stage != "admission_interrupted"` and
   `snapshot_resolvable is True`, and keep the explanation as the action description only. Add tests
   pinning each of the five combinations above.

2. Acceptance Criterion 5 is unproven for three of its four configured strategies and for the
   invalid-destination case. Evidence — `grep -n "ConflictStrategy\."
   tests/test_automation_definition_execution.py tests/test_automation_authorized_execution_matrix.py`
   returns only two hits, both `ConflictStrategy.OVERWRITE` in the single new test
   `test_unattended_overwrite_collision_waits_without_mutation`; `grep -n
   "invalid_destination\|INVALID_DESTINATION" tests/test_automation_authorized_execution_matrix.py`
   returns only line 102, a hand-written string passed to `classify_failure()` in
   `test_execution_boundary_categories_are_distinguishable_and_bounded`. The new
   `PlanStatus.INVALID` / `INVALID_DESTINATION` and UNKNOWN-conflict `_failed(..., stage="storage")`
   branches added in `mediaflow/application/media_organizer.py` therefore have no test at all.
   Correction direction: on the authorized definition-scoped path over temporary Local roots, prove
   per item that `SKIP` produces a NOOP with the destination byte-identical, `RENAME` writes only the
   safe alternative destination and leaves the existing file untouched, `MANUAL` leaves that item
   waiting with its resolution path, and an invalid destination fails closed with zero mutation and
   the `invalid_destination` category, with siblings keeping independent status and Results.

3. Acceptance Criterion 6 unstable source has new code and zero tests. Evidence —
   `grep -rn "UNSTABLE\|unstable" tests/test_automation_definition_execution.py
   tests/test_automation_authorized_execution_matrix.py` returns no matches, and
   `grep -rln "unstable_source" tests/` returns no files. Untested code: the new `FileScanStatus`
   UNSTABLE branch inside `discovered()` in `mediaflow/application/media_organizer.py`, and the
   `retry_category='unstable_source'` / `__unstable_source` path in
   `list_task_item_status_counts()` in `mediaflow/infrastructure/sqlite_runtime.py`, which excludes
   unstable items from `selected` and therefore changes the Acceptance Criterion 7 bound statement.
   Correction direction: run an authorized occurrence containing one unstable source and assert the
   durable TaskItem plus Result, the `unstable_source` explanation with its retry safety and single
   next action, zero mutation, that completed siblings keep their effects, and that the unstable item
   is excluded from the selected count so the bound statement stays honest.

4. Acceptance Criterion 6 Provider failure and mid-batch Storage failure are unproven on the
   scheduled path. Evidence — `provider_failure` appears in the new tests only at
   `tests/test_automation_authorized_execution_matrix.py:106`, inside the same unit-level
   `classify_failure()` case list; no test drives a Provider failure or a Storage failure occurring
   after the first successful item through a definition-scoped authorized run. Correction direction:
   add both cases end to end and assert the failed item's durable state, effect certainty, retry
   safety and one next action, that the already-successful sibling keeps its effects and Result, and
   that no automatic replay of the failed item occurs.

5. Acceptance Criterion 9 has no test. Evidence — `git diff --stat
   1bd8a08..20a5426 -- tests/` shows `tests/test_operator_ui.py` untouched, and
   `grep -n "outcomeSummary\|itemOutcomeSummary\|attentionItems\|boundReached\|stoppedAtBound"
   tests/test_operator_ui.py tests/test_automation_api.py tests/test_api_security.py` returns no
   match, while the module already pins Web behavior with exact `assertIn` checks on `APP_JS`
   (for example `tests/test_operator_ui.py:772-783`). The new Automation panel block in
   `mediaflow/interfaces/operator_ui.py` — count cards, bound statement, attention table, the
   `showTaskItem(taskId, itemId)` cross-links, the cap warning and the five failure fields in the
   task-item detail — is unverified. Correction direction: extend `tests/test_operator_ui.py` in the
   existing style to pin the rendered summary, the bound statement, the attention list with its
   cross-link into the existing per-item recovery surface, the truncation signal, the failure fields,
   and that the panel adds no Automation mutation action; include the reload path required by the
   criterion.

6. The Required Test "RBAC refusal for an unauthorized principal" on the summary routes was not
   added. Evidence — `test_api_definition_detail_and_occurrence_routes_share_summary` in
   `tests/test_automation_authorized_execution_matrix.py` builds `MediaFlowApi` with a single
   `ApiPermission.READ` principal and asserts `status == 200` for the list, detail and occurrences
   routes only; `tests/test_api_security.py` is untouched by this checkpoint. Correction direction:
   assert that a principal without `READ` is refused on the definition detail and occurrences routes
   carrying the new summary, and that the refusal body exposes no summary content.

7. Acceptance Criteria 7 and 11 read-only claims are not actually asserted. Evidence — the trace
   assertion in `tests/test_automation_authorized_execution_matrix.py:489-491` counts only
   statements matching `statement.lstrip().upper().startswith("SELECT")`, so any INSERT, UPDATE or
   DELETE executed inside `project_occurrences()` cannot fail that test; and the falsification item
   "Opening and refreshing the Automation list, detail, occurrence and history views creates no Job,
   Task, grant, Provider request or Storage probe" is absent from the Developer Completion Report and
   from the new tests. Correction direction: assert on the already-captured trace that the projection
   issues no write statement, and add the read-only proof across the Automation list, detail,
   occurrence and history views — no Job, Task, grant, Provider request or Storage probe created on
   first open and on refresh — then record that command and its observed result in the report.
