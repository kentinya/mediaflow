# Task 44.8 — Complete discovery controls under durable Worker ownership

This Task follows [the development workflow](docs/development-workflow.md), uses
[Task/TEMPLATE.md](Task/TEMPLATE.md), and is subordinate to the unchanged
[Slice 44 Contract](SLICE.md).

```text
Task ID: 44.8
Parent Slice: 44
Status: READY FOR B REVIEW
Task Base: 4bb21dc5bb8b4861478ef07ffecac47143b1ae6c
Difficulty: High
Test Level: T4
Planner / Reviewer: B
```

## Goal

Complete RO-6's durable discovery controls and recovery: accepted cancellation reaches terminal
acknowledgement, pause/continue remains usable, and a Worker that loses ownership cannot change the
current owner's state or observations. Resolve A44-4/A44-5 as one control/ownership correction,
covering Slice acceptance 30/31 and fencing while preserving bounds, pins, findings and separate
Preview/execution authority.

## Why This Task Exists

Slice 44 is checkpointed as FIX REQUIRED; no implementation Task was active. A requires one focused
correction. Task 44.7 remains historically accepted; this Task does not reopen it or change Contract.

B inspected the actual service, SQLite claim/progress transactions, resident Worker and tests, and
independently repeated A's probes on this Task Base. These use authenticated API, activated managed
configuration with supported default policy, temporary real Local/SQLite, actual
MediaDiscoveryWorker.run_next, controlled clocks and event coordination around real list_page.
The delay retains actual responses/capabilities and does not weaken production safety checks.

- Cancel before pickup: accepted request; three pickups after clock advances return no work.
  Readback stays queued/cancelRequested; same selection returns that open record. Claims exclude
  cancellation requests.
- Cancel during listing: control increments version; returning old progress conflicts; subsequent
  pickups exclude cancellation, stranding the accepted request.
- Lease expiry/successor takeover: returning old Worker detects claim loss but publishes paused using
  only version, clears successor claim, and leaves pauseRequested=false with native Resume unavailable.
  This violates ownership even if an additional workaround might eventually allow continuation.

These current reachable defects affect Files → discovery/Operations → Preview and violate RO-6
acceptance 30/31 and fencing. Receipts show zero content reads/mutations and zero execution Tasks.
The helper exit confirms defects, not passing product acceptance. Local retained planning evidence:
`.git/validation-evidence/4bb21dc5bb8b4861478ef07ffecac47143b1ae6c/b-plan44-8/`.
A's original a-final-review2 evidence remains intact.

### Complexity and correction-loop reassessment

Seven Tasks and multiple correction checkpoints already exist. B assessed the whole discovery model
before planning an eighth: full-record version writes mix controls with Worker publication, while
claim replacement does not fence publications. Existing metadata-only discovery, SQLite transactions,
resident Worker and native controls suffice. Correct this one boundary coherently; no new engine,
queue/supervisor, parallel lifecycle or Task per race is needed. Prior manifest/confinement/refusal/
atomic-finalize fixes remain required; no material Contract impossibility is established.
Count repeated corrections at the same capability boundary across Tasks 44.6–44.8; a new Task ID
does not reset the user's three-round complexity threshold. That boundary has already had several
corrections, so reassessment applies now. Keep this Task's ID/Base/Goal/Scope and return necessary
Contract changes to A; do not automatically plan a ninth Task.

### B global reassessment — next correction approach

History contains the initial discovery implementation followed by five functional correction
checkpoints: budget/admission recovery (`71d9aa1`), library/Storage binding (`bf0e00e`), exact manifest/
durable refusal (`62178d3`), atomic Finalize (`f514c15`) and controls/ownership (`3bb4574`). These
are real current-Contract defects, but the recurring publication/control failures indicate that
isolated case fixes have not established one consistent write/transition model. B's earlier local
acceptance and repeated full-gate handoffs also contributed to late discovery and avoidable rework.

The next correction should explain and consolidate the existing ownership boundary: immutable
actor/scope/pin, operator control requests, Worker-owned traversal/progress/observations/refusals,
and the existing one-shot frozen intent link. Trace the current writers and make control reconciliation,
claim validation, progress publication and resulting lifecycle transition agree at the SQLite
transaction boundary. A control-version change is not ownership loss. A live owner must preserve
its bounded work when acknowledging a control; a lost owner must stop without publishing over a
successor; a terminal cancellation must not be reopened. Keep Finalize's existing atomic link.

Prefer consolidation of the current operations over another exception-specific recovery branch.
Checkpoint granularity is an implementation choice inside Scope 1–3: this reassessment requires
no new schema, queue, general workflow framework or per-file persistence mechanism. Verify the
already identified control/publication/ownership cases together before the existing final T4 gates;
do not introduce an open-ended race matrix or another Task for optional proof. This is implementation
guidance, not a new acceptance criterion or a reduction of the assigned tests. Reuse verified matching
candidate evidence across reviewers as the workflow permits; Slice Final's required run remains.

The current P1 reproduction establishes lost progress/refusal and same-discovery Finalize after
the synthetic directory shrinks from 101 to 100 files. It does not establish execution of 101 files,
unauthorized media mutation or data loss. Do not inflate its impact or require an old Worker to
publish private in-memory findings after ownership loss. The fix remains the current live-owner
control/publication boundary, with the same RO-6 outcomes and safety invariants.

Initial governance fails with the recorded FIX REQUIRED + NO ACTIVE IMPLEMENTATION TASK mismatch.
The user/workflow authorize this correction Task. Recheck with the legitimate Task, without changing
Slice status/Base or repairing unrelated tooling.

## Implementation Scope

One boundary: discovery Domain/Persistence → Application/resident Worker → authenticated controls/
readback → existing ResourceLibrary Files/Operations recovery → regression evidence.

1. Reconcile cancellation/pause with actual scheduling. Queued/unclaimed, waiting, paused and
   process/lease-interrupted work need safe durable acknowledgement. In-flight calls are cooperative:
   observe concurrent controls at a safe boundary without overwriting them or losing durable findings.
   Cancellation cannot strand an unclaimable open record blocking deliberate successor selection.
2. Atomically fence all Worker-owned writes by current valid persisted claim, including status,
   progress, findings, counters, manifest and stability observations. Lost owners stop without
   pausing/failing/releasing successor work. A heartbeat before publication alone is insufficient.
   Distinguish operator version changes from ownership loss; controls cannot restore stale claim
   fields. Preserve actor/version/permission checks and fail-closed behavior.
3. Keep pause acknowledgement, waiting and native continuation consistent across API/Web/restart.
   Open states need truthful next actions under Worker/pin readiness. Retain exact actor/scope/
   library/Storage/pin and valid findings; controls/takeover cannot reset consumed budgets/refusals.
4. Adjust existing typed API/projections/Web only as necessary for pending/acknowledged controls,
   conflicts and recovery. Preserve Files list/grid and Operations return context; no CLI/token/DB
   editing or unexplained Pause-before-Continue workaround in the normal journey.
5. Preserve A44-1/2/3 and Task 44.7 fixes: confined/deduplicated manifest, monotonic material refusals,
   read-failure-only reviewed subset and one atomically linked intent. Cancellation grants no intent/
   Preview/execution authority. Do not rewrite frozen work or replay completed/uncertain effects.
6. Prefer existing state/interfaces. Necessary schema evolution requires genuine compatible migration/
   restart proof for schema-45 discoveries and historical file-only intents/Previews/results. No schema
   change is required when existing transaction/claim fields suffice.

Frozen: Slice 43/preservation branch, unrelated RO-1 through RO-5 behavior/visuals, user images,
private configuration and live deployment/media/services. Slice Contract/Roadmap/product CURRENT
closure documents remain A-owned. Only necessary factual implementation notes are in scope.

## Acceptance Criteria

- [ ] AC1 — Accepted cancellation of queued/unclaimed, paused/waiting and in-flight discovery reaches
      durable cancelled at a safe boundary, including SQLite reopen/process restart/lease expiry.
      Exercise authenticated controls plus actual Worker pickup where needed; preclaiming then manually
      calling run_claimed alone is insufficient. Readback explains preserved findings/no execution;
      Finalize refuses cancellation. Deliberate same-scope submission can create successor work;
      unknown admission/control responses reconcile existing work without duplication.
- [ ] AC2 — Returning old Worker after takeover cannot alter successor claim/state/controls/manifest/
      counters/observations. Cover takeover between successful heartbeat and publication, and lost
      ownership on normal/pause/cancel/failure paths. Valid successor advances safely. Use actual
      SQLite transactions, including separate connections to the same DB.
- [ ] AC3 — Concurrent controls/progress neither lose accepted pause/cancel nor strand work on version
      conflict. Pause is acknowledged; native Continue resumes the same permitted scope. Resume/progress/
      renewal cannot undo cancellation. Stale/denied/terminal controls refuse actionably. Restart and
      repeats preserve binding/recovery. Calls need not interrupt immediately; a control losing a race
      to already terminal work may refuse rather than rewrite frozen/completed work.
- [ ] AC4 — Files list/grid and Operations agree with backend pending/acknowledged controls/action
      availability. Refresh/reconnect/unknown response do not duplicate admission/finalize/execution.
      Native continuation and explicit cancellation successor preserve directory/return context without
      CLI/token handling. Normal discovery reaches exact Preview/separately confirmed execution;
      MediaLibrary retains no Organize entry.
- [ ] AC5 — Controls/restart/takeover preserve exact immutable pins, bounded deduplicated/confined
      sources, valid observations and consumed budgets/material refusals. Prior mixed observations,
      provider confinement, cursor/read-failure ordering, 100/101 bounds and concurrent one-intent
      Finalize remain correct. No silent truncated prefix, expanded scope or repinning to current Active.
- [ ] AC6 — Discovery is metadata-only, zero content/Provider/mutation calls, no FileIndex authority.
      Reads/controls/discovery grant no execution/overwrite/delete/fallback permission. Preview/analysis
      stays zero mutation; C remains C with A policies; only OrganizerExecutor mutates explicitly
      authorized reviewed items. Historical completed/partial/uncertain effects stay readable/unreplayed.
- [ ] AC7 — T4 gates have truthful verifiable PASS/FAIL/SKIP/UNAVAILABLE evidence; retain assertions,
      skips and first failures. Exclusions require actual Base proof. Checkpoint only this correction,
      preserving four pre-existing untracked PNGs and excluding config/alist.json/secrets/frozen work.

## Required Tests

### Development and correction feedback

Start with deterministic A44-4/A44-5 regressions, then affected control/claim transitions. Use managed
activation/loading, real Local/SQLite and actual Worker scheduling. Delay/clock coordination preserves
adapter responses/capabilities. Label injected policy/port cases separately from production reachability;
these tests do not add managed stability controls.

Repository root:

```bash
.venv/bin/python scripts/check_governance.py
.venv/bin/python -m unittest tests.test_media_discovery tests.test_media_discovery_provider_manifest
.venv/bin/python -m unittest tests.test_manual_organize_intent tests.test_manual_organize_preview tests.test_manual_organize_execution tests.test_operations_run_inventory tests.test_operations_run_detail tests.test_migration_rehearsal
```

Run new/changed ownership modules too and name them in the report. Cover actual run_next, blocked
list/stat, concurrent controls, lease expiry, heartbeat-to-write takeover, separate SQLite connections,
restart, stale/repeated/lost responses, old/new pins and zero-side-effect spies.

From web/:

```bash
npm run test -- --run src/features/operations/OrganizeDiscoveryPage.test.tsx src/entities/operations/discovery.test.ts src/features/operations/OperationsInventory.test.tsx
```

Add directly affected cases if other boundaries change. Before expensive gates run the real-Python
native proof below; extend bounded fixtures as needed to race controls with actual pickup. An accepted
API/UI control remaining permanently pending is not acceptance.

### Final checkpoint gates

T4 is necessary for persistence/concurrency, immutable admitted work and core recovery. Full Python
covers focused/integration cases normally; record coverage instead of duplicating identical final runs.

Repository root:

```bash
.venv/bin/python scripts/check_governance.py
.venv/bin/python -m unittest discover -s tests
.venv/bin/ruff format --check .
.venv/bin/ruff check .
.venv/bin/python -m compileall -q mediaflow tests scripts
.venv/bin/python -m pip check
.venv/bin/mediaflow --config config/strategy.example.json config validate
.venv/bin/mediaflow --config config/mediaflow.phase13.2.example.json config validate
.venv/bin/python -m pip wheel . --no-deps -w dist/task44-8
.venv/bin/python scripts/wheel_smoke_test.py dist/task44-8/mediaflow-*.whl
.venv/bin/python scripts/docker_release_security_smoke_test.py
.venv/bin/python scripts/docker_upgrade_recovery_smoke_test.py
.venv/bin/python scripts/files_organize_discovery_browser_proof.py
.venv/bin/python scripts/docker_files_organize_discovery_browser_proof.py
git diff --check
```

Smoke-test exactly one current wheel and hash it. Audit source/dependencies for FFmpeg/FFprobe and
staged/tracked files for secrets/private config/unrelated/frozen changes. Docker uses isolated
projects/ports/volumes and daemon-visible temporary binds (TMPDIR=/run/mf-docker-tmp where needed),
never live deployment. Preserve original security/upgrade artifacts. Reopen actual schema-45
interrupted/controlled discoveries and historical file-only work. If schema evolves, extend genuine
upgrade proof without weakening coverage; fabricated newer documents alone cannot prove compatibility.

From web/:

```bash
npm run test -- --run
npm run format:check
npm run lint
npm run typecheck
npm run build
npm run test:e2e
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts
npm run test:e2e -- --config=playwright.direct-files.python.config.ts tests/e2e/direct-files.python.spec.ts
```

Build before native/Docker browser proofs; identify served JS/CSS/runtime/image inputs. Native proof
covers cancellation before pickup/during controlled in-flight work, pause/Continue, preserved findings,
explicit successor and normal intent/Preview/confirmed execution on synthetic media. Deterministic
actual-Worker/repository tests cover takeover; avoid fragile browser timing solely to repeat a race.
Inspect saved visible states/receipts. Existing folder/file/multiple/mixed selections, Operations return,
direct-file parity and RO-1 through RO-5 regressions remain covered. No unrelated Rules/toolbar redesign
or optional additional visual matrix is required.

Unavailable isolated service/Docker evidence is explicit SKIP/UNAVAILABLE with reason; available
failed gates stay FAIL. Report missing material required evidence to B rather than claiming PASS.

### B independent verification

Inspect Base..submitted Head, criteria and original candidate identity/logs. Independently reproduce
queued/in-flight cancellation with actual pickup and stale-owner/successor takeover on real SQLite.
Require terminal cancellation/safe successor, unchanged successor ownership/observations and native
pause/Continue. Inspect Files/Operations images/receipts, served identity, prior manifest/atomic-Finalize
regressions and original migration/security evidence.

For every suspect: current production reachability → user impact → Contract violation → repeatable
actual evidence → severity. Unsupported assembly/injected policy/weakened capabilities, optional proof
and P2/P3 wording cannot justify FIX REQUIRED. Other gates may reuse verified matching evidence;
missing/incompatible/contradicted evidence needs fresh affected runs.

After correction Task PASS reconcile factual Closure Packet/evidence, return Slice to READY FOR A REVIEW
and hand to A. This correction-loop handoff is not another B Slice acceptance/PASS/CLOSED decision.
Preserve A's reviews and Slice Base; do not create another Task for optional proof/cleanup.

### Evidence and rerun rules

Retain index/original logs/receipts/images under
`.git/validation-evidence/<tested-full-sha>/task44-8/<run-id>/` or accessible CI through A's decision.
Record tested/dirty/submitted identity, commands/cwd/versions/dependencies/config/selection/Worker/
clock settings, artifact hashes, exit/count/skip/unavailable/duration, first failures and exact repeats.
Planning negative probes are separate from passing gates. Copy fixed/default proof outputs, especially
/tmp and web/test-results, to retained candidate evidence before overwrite; shared-output runs are
sequential. Source/test/harness/dependency/config/artifact changes require fresh affected evidence;
corrected executable T4 candidates need all assigned final gates. Report-only successors require
verified unchanged runtime inputs plus fresh document-consuming checks. Never change assertions,
skips, timeouts, selection or retries to manufacture green results.

## Non-goals

- Change Slice Goal/RO/Surfaces/Safety/Deferred/Base, rescope or declare closure.
- New queue/supervisor/engine/lifecycle/provider or managed stability controls.
- Expand bounds/scope, follow links, auto-split manifests or freeze truncated prefixes.
- New execution/overwrite/delete/fallback authority, FileIndex admission, media hashing/FFprobe.
- P2/P3 wording/Rules assertions, optional proof, unrelated refactors or governance handoff repair.
- Live deployment/media changes, reopen accepted Tasks, move Task Base or split fixes by race.

## Developer Completion Report

### Changed Files

Five files, one coherent correction boundary; no schema change and no Task/Base/Scope change.

- `mediaflow/domain/media_discovery.py` — `DiscoveryConflict` now carries the refused
  `attempted` projection and its `attempted_observations` (never in `details`, so no claim
  token/fingerprint/physical path is published).
- `mediaflow/infrastructure/sqlite_runtime.py` — `_raise_discovery_write_conflict` attaches that
  projection on a version conflict and attaches nothing on a claim mismatch;
  `settle_media_discovery_control` now accepts `observations` and persists status/progress/
  sources/control flags/claim release *and* the stability observations in one `BEGIN IMMEDIATE`
  transaction.
- `mediaflow/application/media_discovery.py` — `run_claimed` hands the refused projection to
  `_settle_after_conflict`, which reconciles a same-owner control with the bounded work of the
  losing publication under the exact persisted claim (`_merge_attempted_work` verifies discovery/
  pin/Storage/library/scope identity first); a cleared-pause publication settles through the same
  atomic claim-releasing path; a bounded retry re-reads when a concurrent control moves again; a
  lost claim still carries nothing and stops.
- `scripts/files_organize_discovery_browser_proof.py` — bounded native control-preservation step
  (truthful pre-pickup pause, Continue to the real 100/101 bound, refused Finalize), plus a
  deterministic wait for the resolved scope section that removes a pre-existing harness race.
- `tests/test_media_discovery.py` — two new A44-8-1 regressions (below).

### Implemented

B44-8-1 (AC3/AC5, RO-6 acceptance 29/30). A publication that loses the version CAS to a
*same-owner* operator control is no longer discarded. `record_media_discovery_progress` and
`settle_media_discovery_control` raise `DiscoveryConflict` with the exact projection that lost the
CAS (and, on the progress path, the stability observations written with it). The returning owner
re-reads the fresh record and reconciles: the operator's control flags and lifecycle transition
win, while the same owner's counters, findings, manifest, pending traversal, stability
observations and monotonic material refusals are preserved — and only when the attempt belongs to
the same discovery, pin, Storage, ResourceLibrary and admitted scope. An accepted pause is
therefore acknowledged *with* the completed walk (101 visited entries, 2 page fetches, 100
retained sources, `refusalReasons=[primary_limit]`) instead of a reset record; Continue publishes
the same work through the atomic claim-releasing settlement, so it never re-walks with reset
accounting; Finalize keeps refusing the truncated prefix with `discovery_budget_limited`. A
cleared pause, a lapsed lease or a still-pending control yields the claim for the next pass. A
claim mismatch still carries nothing: a lost owner stops without touching successor state.

Preserved unchanged: A44-4/A44-5 cancellation settlement, fencing and takeover behavior; the
confined/deduplicated manifest; monotonic material refusals; the read-failure-only reviewed
subset; one atomically linked intent; exact pins, consumed budgets and separate
Preview/execution authority. No new schema, queue, supervisor or per-file persistence.

### Tests and Results

Test Level T4. Commands run from the repository root with `.venv/bin/python` on the final tree
(commit below); Docker gates used the documented daemon-visible `TMPDIR=/run/mf-docker-tmp`.

- B's original probe `.git/validation-evidence/fe1e355.../b-review44-8/control-probes.py` — its
  `pauseDropsRefusal` case now **FAILS by construction**: it asserts
  `after['progress']['refusalReasons'] == []`, i.e. that an accepted pause *must* discard the same
  owner's completed work. That assertion encoded the defect B reported, so it is retained
  unmodified as the first-failure record and replaced by the corrected companion below.
- Corrected companion probe (`control-probes-corrected.py`, same four cases, corrected
  expectation) — **PASS** (4/4: queuedCancel, inFlightCancel, takeoverBeforeWrite, pauseKeepsWork;
  zero Storage mutations and zero execution Tasks in every case).
- `tests.test_media_discovery tests.test_media_discovery_provider_manifest` — **PASS**: 70 tests.
- `tests.test_manual_organize_intent|preview|execution`, `tests.test_operations_run_inventory`,
  `tests.test_operations_run_detail`, `tests.test_migration_rehearsal` — **PASS**: 137 tests.
- `python -m unittest discover -s tests` — **PASS**: 2383 tests, OK (skipped=7).
- `scripts/check_governance.py` — **PASS**.
- `ruff format --check .` / `ruff check .` — **PASS** (358 files formatted, all checks passed).
- `python -m compileall -q mediaflow tests scripts` — **PASS**.
- `python -m pip check` — **PASS** (no broken requirements).
- Both example config validations — **PASS**.
- Wheel build + `scripts/wheel_smoke_test.py` — **PASS** (one wheel,
  `sha256=d137dd8289f194777e961d3f5adf7141509dbf40d93059fa735973dd0a728cae`, schema 45, database
  SHA-256 `260ed838a4feaa6278534bc678243b0e8f3f09f5f9df177275e8c702407503e9`).
- `scripts/docker_release_security_smoke_test.py` — **PASS**.
- `scripts/docker_upgrade_recovery_smoke_test.py` — **PASS** (genuine schema-38 base image →
  schema-45 candidate, injected failure, restore, durability).
- `scripts/files_organize_discovery_browser_proof.py` — **PASS** (`{"ok":true,"passes":11}`, 3/3
  consecutive runs on the final tree, including the new control-preservation step).
- `scripts/docker_files_organize_discovery_browser_proof.py` — **PASS**
  (`{"ok":true,"passes":7}`).
- From `web/`: `npm run test -- --run` — **PASS** (73 files, 1086 tests).
- From `web/`: `npm run format:check`, `npm run lint`, `npm run typecheck`, `npm run build` —
  **PASS**.
- From `web/`: `npm run test:e2e` — **PASS** (246 tests).
- From `web/`: `npm run test:e2e -- --config=playwright.python.config.ts
  tests/e2e/operations-inventory.python.spec.ts` — **PASS** (21 tests).
- From `web/`: `npm run test:e2e -- --config=playwright.direct-files.python.config.ts
  tests/e2e/direct-files.python.spec.ts` — **PASS** (10 tests).
- `git diff --check` — **PASS**.

Added deterministic regressions in `tests/test_media_discovery.py` (both **PASS** on the final
tree, both **FAIL** on the unmodified Base tree — verified in an isolated `git worktree` at
`8d24958` with only the test file copied):

- `test_a_pause_racing_the_publication_keeps_the_bounded_work` — a real 101-source Local walk
  completes, its publication is held immediately before the real repository write, an accepted
  pause wins the version CAS, and the acknowledgement keeps 101 visited entries, 2 page fetches,
  100 sources and `primary_limit`; Continue keeps the refusal and Finalize refuses with
  `discovery_budget_limited`. Zero mutation, zero Tasks.
- `test_a_continue_racing_the_publication_publishes_the_work_once` — the same race with pause then
  Continue: the completed bounded work is published once under the live claim (no reset, no
  re-walk), the claim is released and no duplicate finding/source appears.

### Decisions

- Reconciliation is driven by the *refused projection* carried on `DiscoveryConflict`, not by a
  re-walk or a snapshot stored before the walk. The losing owner is the only party that still
  holds the completed bounded work, and it is still the valid claim holder, so it is the correct
  party to settle the operator's control with that work.
- The refused projection is validated field-by-field against the fresh record (discovery id, pin
  id and digest, Storage, ResourceLibrary, scope signature) before any of it is carried. A control
  can never be reconciled with work that was never admitted for this discovery.
- Observations now travel through the control-settlement transaction as well as the progress
  transaction, so an acknowledged pause cannot lose the stability evidence that belongs to the
  same pass.
- A cleared pause publishes the completed work through the same atomic claim-releasing settlement
  used for pause/cancel, rather than a plain progress write plus a separate release, so a
  successful Continue can never leave a stale claim behind.
- The reconciliation loop is bounded (`_CONTROL_RECONCILE_ATTEMPTS = 4`) and always ends safely:
  it either settles the operator's control with the same work or yields the claim so the next pass
  continues. It never spins on a live lock.
- Cancellation keeps its A44-4 semantics unchanged: the request settles terminal and releases the
  claim atomically, so the returning owner is no longer the claim holder and correctly writes
  nothing.
- The native browser proof's control-preservation step is deliberately about truthful pre-pickup
  pause plus Continue-to-the-bound; the narrow in-flight race is proven deterministically in
  Python instead of by fragile browser timing, exactly as the Task's test plan allows.

### Remaining In-Slice Work

B44-8-1 is resolved and the corrected handoff returns to B. No new Task is defined here. The
recorded P2/P3 wording/assertion notes were left untouched as non-blocking.

### Risks / Deviations

- A same-owner pause that is *acknowledged* now reports the completed walk's truthful status when
  the operator later clears the pause (the settlement for the pause itself still reports
  `paused`). This is the intended "preserve bounded work" semantics and is covered by the new
  regressions.
- The native browser proof's browser step reads the discovery page after a heading that renders
  before the authenticated read resolves. A deterministic wait for the same assertion's own
  content was added; no assertion, timeout or selection was weakened. The flake was reproduced on
  the unmodified Base harness (2/3 failures) and the fixed harness passes 4/4 under 6-way CPU
  load and 3/3 on the final tree. It is a pre-existing harness race, not a product defect.
- Three Docker scripts need the documented `TMPDIR=/run/mf-docker-tmp` because the Docker daemon
  cannot see this container's `/tmp`. Pre-existing environment property; all pass with it.
- No material Contract problem found; no Slice/Contract change was required or made.

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: 917baf6377c332b0a0cbd15e529d841016e64f69
```

## B Review Result

Review date: 2026-10-10. Reviewed the actual submitted implementation
`3bb45747b6e50f6bc44fb57e7b6384f429e247bb` and its report-only successors through
`fe1e355e108520bd4fc169e131290050fe509e3f`. The latter range changes only TASK.md;
runtime, tests, harnesses, dependencies and configuration are unchanged. The stale PLANNED header
and SUBMITTED FOR REVIEW report do not establish acceptance; this is Task 44.8's first B review.

Independent verification: focused discovery/provider tests PASS (68 tests, 13.986 seconds);
manual intent/Preview/execution, Operations inventory/detail and migration regression PASS
(137 tests, 17.257 seconds); governance, changed-file Ruff and diff checks PASS. Real authenticated
API/managed-default Local/SQLite probes independently confirm terminal queued/in-flight cancellation,
safe deliberate successor admission, and takeover immediately before the actual SQL publication:
the old owner changes neither successor ownership nor state, and the successor completes.

The pause/control probe below proves an in-scope P1. Under the workflow's early-blocker rule,
B did not rerun the remaining expensive T4 gates or accept their completion-report labels.
No candidate-bound Task 44.8 evidence index/raw archive was found at the prescribed retained
location or linked in the report. The discovered temporary t4-gates/t4-gates2 Python logs contain
2352 tests, not the reported 2381, and have no verified matching candidate identity; they are not
reused. The corrected executable candidate still needs all assigned final gates with retained
source/environment/artifact identity, original logs and required browser receipts/images.

Global complexity reassessment: prior Slice corrections already span several rounds. This new
failure comes from combining a whole Worker publication with the operator version CAS, then
settling that conflict from the pre-publication durable snapshot. The existing discovery model,
claim fence and SQLite transaction boundary are sufficient to reconcile controls and progress.
Keep one coherent correction in this Task; no new queue, lifecycle, engine or Task per race is
needed. No Contract impossibility is established; ID/Base/Goal/Scope and assigned tests are retained.

Evidence (local, retained through A review):
`.git/validation-evidence/fe1e355e108520bd4fc169e131290050fe509e3f/b-review44-8/`
contains the index, original probe scripts/logs/receipts, first harness errors and corrected runs,
focused/affected regression logs and scope/input identities. The first control-probe harness
expected 200 instead of Finalize's successful 201; the first no-control harness used the wrong
error-code spelling. Both original failures are retained, not counted as product failures.

```text
Reviewed: 4bb21dc5bb8b4861478ef07ffecac47143b1ae6c..fe1e355e108520bd4fc169e131290050fe509e3f
Decision: FIX REQUIRED
Slice Required Outcomes all satisfied: NO
Next: SAME TASK FIX LOOP
```

- P1 / B44-8-1 — AC3/AC5 and RO-6 acceptance 29/30: an accepted pause concurrent with
  Worker publication discards the same owner's completed observations, consumed counters and
  material refusal. **Current production reachability:** managed activation/loading, default
  policy/budgets, real Local directory with 101 media files, real SQLite and actual
  MediaDiscoveryWorker.run_next. Event coordination delays the real repository call immediately
  before publication; adapter responses/capabilities, configuration and limits are unchanged.
  **User impact:** Files/Operations Pause acknowledges a record with zero findings/progress and
  hides the already encountered 101-item limit; Continue can bypass its required narrowing/successor
  recovery. **Contract violation:** AC3 requires safe continuation without losing findings;
  AC5 and Implementation Scope 2/3 require preserved observations, consumed budgets and material
  refusals; A44-4/A44-5 explicitly require control reconciliation without resetting them.
  **Repeatable evidence:** run `.venv/bin/python
  .git/validation-evidence/fe1e355e108520bd4fc169e131290050fe509e3f/b-review44-8/control-probes.py`.
  In `pauseDropsRefusal`, the attempted publication has status partial_success, 101 visited entries,
  two page fetches, 100 retained sources and refusalReasons=[primary_limit]. Pause wins the version
  CAS; application/media_discovery.py:549-556 calls _settle_after_conflict without that publication,
  and :571-593 settles the fresh old progress through _publish_paused. Readback becomes paused
  with zero visited entries/page fetches/sources/active time and no refusal. After a legal external
  removal of the 101st synthetic file, Resume and actual Worker pickup on the same discovery ID/pin
  report completed/100; Finalize returns 201 and creates the linked intent. The no-control companion
  probe retains primary_limit and refuses Finalize with 409/discovery_budget_limited after the same
  removal. Receipts record zero discovery mutation and zero execution Tasks. **Severity:** current
  reachable P1, breaking the bounded-discovery/control/recovery Contract. **Required correction:**
  reconcile a same-owner control/version change with the bounded in-flight progress, counters,
  observations and monotonic refusal under the exact persisted claim, while preserving accepted
  controls and refusing all stale-owner writes. Do not discard work and silently re-walk with reset
  accounting. Retain the existing new cancellation/takeover behavior. Add deterministic regressions
  for this pause/publication race and safe Continue/Finalize refusal; satisfy the unchanged T4 final
  gates on the corrected candidate and retain its verifiable index/raw logs/receipts/images.

NEXT ACTION: DEVELOPER FIXES CURRENT TASK
