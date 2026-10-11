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

The 2026-10-11 review of correction `917baf6` confirms that the original lost-work case is fixed,
but a failed pause acknowledgement is now carried as if its lifecycle were completed traversal
work. A later accepted Continue is overwritten by that stale `paused` status. This is the same
write/transition boundary, counted across capability corrections rather than reset by Task ID.
Simplify that boundary so the latest accepted control determines lifecycle while the live owner's
bounded work remains durable. Reusing a whole failed control projection as traversal work does not
establish that rule. Keep existing SQLite/claims and the coherent Task; no new engine, schema,
race-by-race Task ladder or Contract change is required by this finding.

### User-directed simplification — acknowledge Pause before offering Continue

On 2026-10-11 the user proposed waiting for the Worker to confirm Pause before offering Continue.
B confirms that RO-6/AC3/AC4 require safe, truthful pause/continuation, not withdrawal of a pending
pause request. Use the existing pending request and acknowledged paused state: show "pausing / waiting
for background acknowledgement" while pending; offer and accept Continue after the durable pause
acknowledgement has preserved bounded work and released ownership at the safe boundary.
Backend action availability and application/API validation must enforce the same rule; hiding a
button alone is insufficient. A direct or stale-client Continue during pending Pause must refuse
actionably without claiming success or changing work. Keep missing/stale-Worker information and
existing cancellation/recovery useful; do not leave an unexplained disabled action indefinitely.

This clarifies a permitted implementation within existing Scope 1–4 and AC3/AC4, not a Contract
change or a new Task. B's prior direction was too narrow in requiring reconciliation of an accepted
pending-stage Continue; the backend may instead decline it until acknowledgement. Preserve the
actual historical B44-8-2 evidence: the reviewed candidate advertised and accepted that action,
then stranded it. Update affected tests to prove pending-stage refusal with unchanged durable work,
followed by successful Continue after acknowledgement; retain assertions for counters/refusals,
ownership, cancellation and eventual native recovery. Do not merely delete the racing test or its
assertions. The Task ID/Base/Goal/Scope/Acceptance Criteria and assigned T4 plan remain unchanged.

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

Nine files, one coherent control-boundary correction; no schema change and no Task/Base/Scope
change. This round follows the authoritative direction committed mid-task as
`4729e25 plan(task44.8): offer Continue after pause acknowledgement`
("User-directed simplification — acknowledge Pause before offering Continue").

- `mediaflow/application/media_discovery.py` — `resume` now refuses a *pending* pause with the
  bounded `discovery_pause_pending` (409) before clearing it, so a Continue can no longer race the
  Worker's acknowledgement; `_merge_attempted_work` keeps a settlement projection (paused/cancelled/
  failed) from ever being replayed as this pass's traversal status, so the latest accepted control
  always decides the lifecycle.
- `mediaflow/domain/media_discovery.py` — `SETTLEMENT_DISCOVERY_STATUSES` / `is_settlement_status`
  name the statuses a settlement writes rather than a bounded traversal.
- `mediaflow/interfaces/service_api.py` — the `resume` action is advertised only when
  `pauseRequested` and the durable status is `paused`, and publishes a bounded `pendingReason`
  (`discovery_pause_pending`) while the pause is unacknowledged; the next-action copy states the real
  transient stage instead of promising a Continue the backend will refuse.
- `web/src/entities/operations/discovery.ts` — the action projection carries `pendingReason`.
- `web/src/features/operations/OrganizeDiscoveryPage.tsx` — the discovery page explains the pending
  pause stage; the Continue button keeps rendering strictly from `actions.resume.available`.
- `web/src/features/operations/OrganizeDiscoveryPage.test.tsx` — two new cases: pending pause hides
  Continue and shows the waiting state; acknowledged pause offers Continue.
- `tests/test_media_discovery.py` — the two control regressions reworked to the
  acknowledge-before-Continue semantics (below).
- `scripts/files_organize_discovery_browser_proof.py` — the native control-preservation step now
  proves pending-Continue refusal and the bounded pending reason before the acknowledged Continue.
- `scripts/docker_files_organize_discovery_browser_proof.py` — the production-image proof does the
  same: pending refusal, bounded reason, then acknowledged Continue and finalize.

### Implemented

B44-8-2 (AC3/AC4, Implementation Scope 3, RO-6 acceptance 30). The reviewed defect was that an
accepted Continue raced the Worker's pause acknowledgement: the acknowledgement's version CAS
failed, and `_settle_after_conflict` replayed the failed *paused* projection as the traversal
outcome, leaving the record durably `paused` with `pauseRequested=false`, no advertised Resume and
no claimable work — the supported continuation journey stalled behind an unexplained
Pause-before-Continue workaround.

The correction implements the user/B direction directly: a cooperative pause is acknowledged at the
Worker's safe boundary (preserving the interrupted pass's counters, findings, manifest, stability
observations and monotonic material refusals and releasing the claim atomically), and Continue is
offered and accepted only *after* that acknowledgement.

- Backend availability and validation agree: while the pause is pending, `actions.resume.available`
  is false, `actions.resume.pendingReason` is `discovery_pause_pending`, and a direct or
  stale-client `POST .../resume` is refused with the same bounded 409 code and a native next action,
  changing no durable field (version, flags, counters, sources, claim all unchanged).
- The readback states the transient stage truthfully rather than advertising an action that cannot
  succeed, so the operator is never left with an unexplained dead end; cancellation keeps its own
  terminal path and the missing/stale-Worker guidance is untouched.
- After acknowledgement the pause is `paused` + `pauseRequested=true`, Continue is offered, and the
  accepted Continue genuinely continues the same admitted scope to completion.
- The reconciliation guard is retained as defence in depth: a settlement projection contributes its
  bounded work but never its superseded lifecycle, so the latest accepted control keeps deciding the
  lifecycle even if such a race were reintroduced. Cancellation settlement, exact-claim fencing,
  takeover behaviour, pins, budgets and separate Preview/execution authority are unchanged.

No new schema, queue, supervisor, engine or per-file persistence; the existing SQLite transactions
and claim columns suffice.

### Tests and Results

Test Level T4. All commands run from the repository root with `.venv/bin/python` on the committed
tree `12fd1b3a75cf76743912b57d1f51d184acb10901`; Docker gates used the documented daemon-visible
`TMPDIR=/run/mf-docker-tmp`.

- B's original probe (retained unmodified as `original-b44-8-2-probe.py`) — now **FAILS BY
  CONSTRUCTION**: it asserted the reviewed defect itself (`resume.available is True` during a pending
  pause, then a stranded `paused` record). It is kept as the first-failure record.
- Corrected companion probe (`corrected-resume-during-pause-settlement.py`, same real
  managed/Local/SQLite/API/Worker sequence with the corrected expectation) — **PASS**, 3/3
  iterations: pending Continue refused (`discovery_pause_pending`, version unchanged), acknowledged
  pause preserves the bounded work and releases the claim, acknowledged Continue completes the same
  scope; zero Storage mutations and zero execution Tasks in every iteration.
- `tests.test_media_discovery tests.test_media_discovery_provider_manifest` — **PASS**: 71 tests.
- `tests.test_manual_organize_intent|preview|execution`, `tests.test_operations_run_inventory`,
  `tests.test_operations_run_detail`, `tests.test_migration_rehearsal` — **PASS**: 137 tests.
- `python -m unittest discover -s tests` — **PASS**: 2384 tests, OK (skipped=7).
- `scripts/check_governance.py` — **PASS**.
- `ruff format --check .` / `ruff check .` — **PASS** (358 files formatted, all checks passed).
- `python -m compileall -q mediaflow tests scripts` — **PASS**.
- `python -m pip check` — **PASS** (no broken requirements).
- Both example config validations — **PASS**.
- Wheel build + `scripts/wheel_smoke_test.py` — **PASS** (one wheel,
  `sha256=40b848715bac1bf392c3467d3dfd817d5c45da9330ae5898a01cee490d4707f7`, schema 45, database
  SHA-256 `260ed838a4feaa6278534bc678243b0e8f3f09f5f9df177275e8c702407503e9`).
- `scripts/docker_release_security_smoke_test.py` — **PASS**.
- `scripts/docker_upgrade_recovery_smoke_test.py` — **PASS** (genuine schema-38 base image →
  schema-45 candidate, injected failure, restore, durability).
- `scripts/files_organize_discovery_browser_proof.py` — **PASS** (`{"ok":true,"passes":11}`), with
  the control-preservation step reporting "pending pause refused Continue; acknowledged pause
  continued to 101 visited / 100 sources / primary_limit; finalize refused".
- `scripts/docker_files_organize_discovery_browser_proof.py` — **PASS** (`{"ok":true,"passes":7}`).
- From `web/`: `npm run test -- --run` — **PASS** (73 files, 1088 tests).
- From `web/`: `npm run format:check`, `npm run lint`, `npm run typecheck`, `npm run build` —
  **PASS**.
- From `web/`: `npm run test:e2e` — **PASS** (246 tests).
- From `web/`: `npm run test:e2e -- --config=playwright.python.config.ts
  tests/e2e/operations-inventory.python.spec.ts` — **PASS** (21 tests).
- From `web/`: `npm run test:e2e -- --config=playwright.direct-files.python.config.ts
  tests/e2e/direct-files.python.spec.ts` — **PASS** (10 tests).
- `git diff --check` — **PASS**.

Added/updated deterministic regressions in `tests/test_media_discovery.py` (both **PASS** on the
submitted tree, both **FAIL** on the unmodified pre-correction tree `7b90907` verified in an isolated
`git worktree` with only the test file copied):

- `test_a_continue_racing_the_publication_is_refused_until_acknowledged` — a real 101-source Local
  walk completes and its publication is held; the accepted pause is pending, so Continue is not
  advertised and a direct Continue is refused with `discovery_pause_pending`; the acknowledgement
  then keeps 101 visited entries, 2 page fetches, 100 sources and `primary_limit`, and the
  acknowledged Continue keeps the refusal with Finalize refused.
- `test_a_premature_continue_never_strands_the_pause_acknowledgement` — the deterministic form of
  B's reviewed sequence: a Continue arrives while the real pause settlement is held immediately
  before its own repository write; it is refused actionably, the acknowledgement then lands with the
  bounded work preserved and the claim released, and the acknowledged Continue really continues the
  same scope.

Evidence retained at
`.git/validation-evidence/12fd1b3a75cf76743912b57d1f51d184acb10901/task44-8/` (identity, changed-file
hashes, wheel hash, focused/related/full/static logs, original and corrected probes plus receipts,
native and Docker proof output, Web/E2E logs).

### Decisions

- The user/B direction is implemented as a *state* rule, not a UI rule: the pending stage is refused
  in the application (`resume`) and reflected in the API projection, and the Web only renders the
  backend's `available`/`pendingReason`. Hiding a button alone would not have satisfied the Task.
- A refused premature Continue changes nothing durably — no version bump, no flag change, no claim
  touch — so a repeated or stale-client Continue is idempotent and safe, and the subsequent
  acknowledged Continue is the single accepted transition.
- The pause acknowledgement keeps its existing atomic settlement (status + progress + sources +
  control flags + observations + claim release in one `BEGIN IMMEDIATE` transaction); the new rule
  only orders Continue after it, so no new transaction or schema was needed.
- `SETTLEMENT_DISCOVERY_STATUSES` is a domain-level fact about which statuses a settlement writes,
  which keeps the reconciliation guard meaningful without re-encoding lifecycle knowledge in the
  application layer.
- The two control regressions were reworked rather than deleted: the assertions that prove the
  bounded work (101/100/`primary_limit`), the released claim and zero mutation are retained, and the
  pending-stage refusal assertions were added, exactly as the Task requires.

### Remaining In-Slice Work

B44-8-2 is corrected and the candidate returns to B. No new Task is defined here. The recorded
P2/P3 wording/assertion notes were left untouched as non-blocking.

### Risks / Deviations

- An authoritative user/B commit (`4729e25`) landed on this branch while the correction was in
  progress and changed the required correction direction for the *same* Task ID/Base/Goal/Scope:
  from reconciling a pending-stage Continue to refusing it until acknowledgement. The implementation
  was adapted to the committed direction; the earlier reconciliation approach is not submitted as
  the fix, though its guard is retained as defence in depth.
- The full Web suite is timing-sensitive under concurrent heavy load: while the Python/Docker gates
  ran in parallel, one unrelated `RulesWorkspacePage` deep-link case timed out in three separate
  full runs (1 failure each, different cases). That file passes 49/49 in isolation (repeated 3x) and
  the final full run with no concurrent load passed 1088/1088. Discovery-only Web tests pass 4/4 in
  isolation. Retained logs record both the flaky and the clean runs; the affected file is untouched
  by this correction.
- Three Docker scripts need the documented `TMPDIR=/run/mf-docker-tmp` because the Docker daemon
  cannot see this container's `/tmp`. Pre-existing environment property; all pass with it.
- The Docker browser proof builds its image from `git archive HEAD`, so it was run against the
  committed candidate `12fd1b3` (an earlier uncommitted run legitimately failed against the
  pre-correction image and was discarded).
- No material Contract problem found; no Slice/Contract change was required or made.

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: 12fd1b3a75cf76743912b57d1f51d184acb10901
Report SHA: 883f11ebe69fe23d99ac94406422b14137748144 (TASK.md only)
```

## B Independent Verification — correction round 2

Review date: 2026-10-11. Inspected immutable Task Base through submitted/report Head
`fe5e4d14f07d5465bd9e0e2a5355959fd5e5bea7`, including correction implementation
`917baf6377c332b0a0cbd15e529d841016e64f69`. Implementation-to-Head changes only TASK.md;
all five Developer-indexed executable hashes match the current files. No Task Base/Goal/Scope/
acceptance/test-plan or Slice Contract change is authorized by this review.

B independently ran the focused discovery/provider regression: PASS, 70 tests, 14.637 seconds.
The original four production-path control probes now PASS: queued/in-flight cancellation,
heartbeat-to-write successor takeover, and preserved 101-item refusal after concurrent Pause,
Continue and legal external directory shrink. B44-8-1 is resolved on this candidate. The prior
review remains in committed `fe5e4d14:TASK.md` and the retained submitted-task snapshot.

The additional current supported Pause/Continue publication sequence below reproduces one P1.
Developer's retained index and original final logs were opened; Python records 2383 tests/7 skips,
Web E2E records 246/21/10, and the five changed-file hashes match. B has not fully accepted those
remaining gate/artifact identities or rerun expensive full/Web/browser/Docker/wheel/migration
checks after the proven blocker. They are not substituted for acceptance. No Slice Final or
handoff is performed; the corrected executable candidate still needs the unchanged T4 gates.

Evidence (local/not pushed, retained through A review):
`.git/validation-evidence/fe5e4d14f07d5465bd9e0e2a5355959fd5e5bea7/b-review44-8-round2/`.
It retains input/image hashes, submitted Task snapshot, original/corrected control probe,
focused log, and the new probe/receipts. Initial and extended user-impact probe runs are retained;
both reproduce 3/3, with no harness error or changed production source. Required governance,
changed-file Ruff and complete reviewed-range/working-tree diff checks are recorded in its index.

## B Review Result

```text
Reviewed: 4bb21dc5bb8b4861478ef07ffecac47143b1ae6c..fe5e4d14f07d5465bd9e0e2a5355959fd5e5bea7
Decision: FIX REQUIRED
Slice Required Outcomes all satisfied: NO
Next: SAME TASK FIX LOOP
```

- P1 / B44-8-2 — AC3/AC4, Implementation Scope 3 and RO-6 acceptance 30: a later accepted
  Continue is overwritten by the returning Worker's stale pause acknowledgement.
  **Current production reachability:** authenticated API, managed default Local configuration,
  one real media file, actual MediaDiscoveryWorker.run_next and actual SQLite transactions.
  Coordination delays the real progress publication, then the real pause settlement; both call
  their original implementations with unchanged arguments. No weakened adapter, unsupported
  configuration, injected error or manual SQL edit is used. **Current user impact:** ResourceLibrary
  Files → discovery/Operations advertises Continue after Pause; Continue returns 200 and clears
  pauseRequested, but readback subsequently says paused with Continue and Finalize unavailable.
  Worker pickup cannot advance it, and repeating the Files selection returns the same open work.
  Users need an extra Pause-before-Continue workaround or cancellation/recreation to proceed.
  **Contract violation:** AC3 requires concurrent controls not to strand work and native Continue
  to resume the same scope; AC4/Scope 3 require consistent usable native recovery without that
  unexplained workaround; RO-6 acceptance 30 requires truthful cooperative pause/continue.
  **Repeatable evidence:** run `.venv/bin/python
  .git/validation-evidence/fe5e4d14f07d5465bd9e0e2a5355959fd5e5bea7/b-review44-8-round2/resume-during-pause-settlement.py`.
  All three runs: Pause accepts version 2; Continue accepts queued/version 3/pauseRequested=false
  while pause acknowledgement is pending. Its real version CAS fails; application/media_discovery.py
  lines 644–650 replace attempted traversal work with the failed paused projection, lines 694–698
  copy its status into the freshly resumed record, and lines 632–643 settle paused/version 4 with
  pauseRequested=false and no claim. Three actual pickups after successive 600-second clock advances
  return None; repeated Resume is a 200 no-op; Finalize returns 409/discovery_not_complete; the same
  selection reconciles the same ID. Receipts retain one discovered source, zero content-read/mutation
  calls and zero execution Tasks. **Severity:** P1, the current supported continuation journey
  stalls; this evidence does not establish media loss or mutation. **Required correction:** use the
  user's acknowledge-before-Continue direction: while Pause is pending, show the waiting state and
  refuse premature Continue consistently in backend availability/application/API; offer and accept
  it after durable safe-boundary pause acknowledgement. Preserve bounded work/refusals and exact
  claim fencing, and ensure accepted Continue actually continues the same scope. Prove premature
  refusal does not alter work, then acknowledged native Continue succeeds; retain the original
  negative probe and update affected regressions to assert these semantics. Keep the same Task
  ID/Base/Goal/Scope and satisfy the unchanged candidate T4 plan with retained evidence.

NEXT ACTION: DEVELOPER FIXES CURRENT TASK
