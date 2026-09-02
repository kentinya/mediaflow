# Task 25.6 — Fail-closed authorized scheduled organization and Automation per-item outcome/recovery

This Task follows [the development workflow](docs/development-workflow.md) and is subordinate to the
current [`SLICE.md`](SLICE.md).

```text
Task ID: 25.6
Parent Slice: 25 — Scheduled Automation and Unattended Organization
Status: PLANNED
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

### Implemented

### Tests and Results

### Decisions

### Remaining In-Slice Work

### Risks / Deviations

### Checkpoint

```text
Status: PENDING
Head SHA: [full SHA]
```

## B Review Result

```text
Reviewed: PENDING
Decision: PENDING
Slice Required Outcomes all satisfied: PENDING
Next: PENDING
```
