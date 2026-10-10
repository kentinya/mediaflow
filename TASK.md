# Task 44.8 — Complete discovery controls under durable Worker ownership

This Task follows [the development workflow](docs/development-workflow.md), uses
[Task/TEMPLATE.md](Task/TEMPLATE.md), and is subordinate to the unchanged
[Slice 44 Contract](SLICE.md).

```text
Task ID: 44.8
Parent Slice: 44
Status: PLANNED
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
If this Task exceeds three correction rounds, reassess the whole control/ownership model before
another patch, keeping ID/Base/Goal/Scope. Return necessary Contract changes to A; do not automatically
plan a ninth Task.

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

Six files, one coherent correction boundary; no schema change and no Task/Base/Scope change.

- `mediaflow/domain/media_discovery.py` — new `DiscoveryOwnershipLost` (code
  `discovery_ownership_lost`, status 409) distinguishing lost claim from `DiscoveryConflict`.
- `mediaflow/infrastructure/sqlite_runtime.py` — claim-fenced `record_media_discovery_progress`
  (required `claim_token`, `AND claim_token=?` in the same statement as the version CAS), new
  atomic `settle_media_discovery_control` (status + progress + control flags + claim release in one
  transaction), operator-only `update_media_discovery` and `create_manual_intent_for_discovery`
  (never write claim columns), precise `_raise_discovery_write_conflict`, and claim selection that
  still admits an unacknowledged `cancel_requested` row.
- `mediaflow/application/media_discovery.py` — `run_claimed`/`_advance` raise ownership loss instead
  of publishing a pause; `_settle_after_conflict` reacts to the fresh record at a safe boundary;
  `_cancel`/`_publish_paused`/`_fail` settle atomically under the live claim; `request_cancel`
  settles terminal cancellation immediately; `resume`/pause stay operator-owned.
- `mediaflow/interfaces/service_api.py` — truthful `nextAction` for a pending cancellation.
- `scripts/files_organize_discovery_browser_proof.py` — bounded native cancellation step
  (durable terminal acknowledgement, no stranded claim, explicit successor work).
- `tests/test_media_discovery.py` — A44-4/A44-5 regressions (below).

### Implemented

A44-5 (ownership fencing). Every Worker-owned write — status, progress, findings, counters,
manifest and stability observations — is fenced by the *exact current persisted claim* in the same
statement as the version CAS, so a takeover between a successful heartbeat and the publication can
no longer rewrite a successor. A lost claim raises `DiscoveryOwnershipLost` and the old owner stops
without pausing, failing, releasing or otherwise touching successor work; a version conflict stays
`DiscoveryConflict` so the live owner can settle an operator control. Operator-owned writes (pause
request, resume, freeze/intent link) never write claim columns, so a control cannot restore a stale
claim. `claim_and_run`/`run_claimed` keep actor/version/permission checks and fail closed.

A44-4 (cancellation settlement). An accepted cancellation is settled atomically as one terminal
outcome: record, request flag and claim release are a single transaction, so a cancellation can
never be left as an open record no Worker may claim. Claim selection no longer excludes
`cancel_requested` rows, so a request left open by an earlier build is still picked up and
acknowledged through a real Worker pass. Concurrent controls reconcile at a safe boundary: an
accepted pause is acknowledged under the live claim, a resume or lapsed lease yields the claim for
the next pass, and resume/progress/renewal can never undo a cancellation. Readback explains a
pending cancellation truthfully and Finalize refuses cancellation.

Preserved from prior accepted work: confined/deduplicated manifest, monotonic material refusals,
read-failure-only reviewed subset, one atomically linked intent, exact pins, consumed budgets and
separate Preview/execution authority. Cancellation grants no intent/Preview/execution authority.

### Tests and Results

Test Level T4. All commands run from the repository root with `.venv/bin/python` on the final tree
(commit `3bb4574`); Docker gates used the documented daemon-visible `TMPDIR=/run/mf-docker-tmp`.

- `scripts/check_governance.py` — **PASS** (exit 0).
- `python -m unittest discover -s tests` — **PASS**: 2380 tests, OK (skipped=7).
- `tests.test_media_discovery tests.test_media_discovery_provider_manifest` — **PASS**: 65 tests.
- `tests.test_manual_organize_intent|preview|execution`, `tests.test_operations_run_inventory`,
  `tests.test_operations_run_detail`, `tests.test_migration_rehearsal`, `tests.test_task_persistence`
  — **PASS**: 153 tests.
- `ruff format --check .` / `ruff check .` — **PASS** (358 files formatted, all checks passed).
- `python -m compileall -q mediaflow tests scripts` — **PASS**.
- `python -m pip check` — **PASS** (no broken requirements).
- `mediaflow --config config/strategy.example.json config validate` and
  `... config/mediaflow.phase13.2.example.json config validate` — **PASS**.
- `python -m pip wheel . --no-deps -w dist/task44-8` + `scripts/wheel_smoke_test.py` — **PASS**
  (one wheel, `sha256=79541860b688a4da10071f99db58dae10df9264638b555d782e8c0c007ff26ca`, schema 45,
  database SHA-256 `260ed838a4feaa6278534bc678243b0e8f3f09f5f9df177275e8c702407503e9`).
- `scripts/docker_release_security_smoke_test.py` — **PASS**.
- `scripts/docker_upgrade_recovery_smoke_test.py` — **PASS** (genuine schema-38 base image → schema-45
  candidate, interrupted migration, restore and durability).
- `scripts/files_organize_discovery_browser_proof.py` — **PASS** (`{"ok":true,"passes":11}`, including
  the new cancellation step).
- `scripts/docker_files_organize_discovery_browser_proof.py` — **PASS**
  (`{"ok":true,"passes":7}`).
- From `web/`: `npm run test -- --run` — **PASS** (73 files, 1086 tests).
- From `web/`: `npm run format:check`, `npm run lint`, `npm run typecheck`, `npm run build` — **PASS**.
- From `web/`: `npm run test:e2e` — **PASS** (246 tests). One earlier run reported two
  `library-files.spec.ts` failures caused by two Playwright suites sharing `web/test-results/`
  concurrently; both pass in isolation and the clean serial suite is green. One earlier
  `operations-inventory.python.spec.ts` failure had the same artifact collision cause and passes in
  isolation. No product defect.
- `npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts`
  — **PASS**.
- `npm run test:e2e -- --config=playwright.direct-files.python.config.ts tests/e2e/direct-files.python.spec.ts`
  — **PASS** (10 tests).
- `git diff --check` — **PASS**.

Added deterministic regressions in `tests/test_media_discovery.py` (all **PASS**):

- queued cancellation reaches durable terminal acknowledgement; three real Worker pickups find no
  work, readback never regresses, Finalize refuses, a same-scope submission creates successor work,
  zero mutation and zero Tasks;
- cancellation during a blocked in-flight listing reaches terminal through the returning Worker
  instead of stranding behind the stale CAS;
- a stale owner cannot clear a successor claim: takeover between successful heartbeat and
  publication leaves claim/status/controls/version untouched, and the valid successor still advances;
- cancellation and takeover stay durable across separate connections and a repository reopen;
- an accepted pause concurrent with an in-flight walk is acknowledged (not lost) and Continue
  resumes the same scope with no duplicate/lost finding;
- resume/pause/re-cancel cannot undo an accepted cancellation; a late claim finds no work;
- a queued record already carrying `cancel_requested` from an earlier build is still claimed and
  settled to `cancelled`;
- the existing stale-owner expectation was corrected from `discovery_conflict` to
  `discovery_ownership_lost` (the old assertion encoded the A44-5 defect).

### Decisions

- One new domain error type instead of overloading `DiscoveryConflict`: a version conflict is an
  operator change the live owner may settle, while a lost claim must stop without writing. The API
  publishes both as 409 with distinct codes, so no Web change was needed.
- Cancellation is settled synchronously by the control request rather than deferred to a Worker pass.
  This is the smallest change that makes "cannot strand an unclaimable open record" true by
  construction, and it keeps the request's version CAS semantics.
- Pause stays cooperative (the Worker acknowledges at its safe boundary) because it is a
  continuable state; only cancellation is terminal at request time.
- Claim selection now admits `cancel_requested` rows instead of excluding them: exclusion was the
  stranding mechanism, and the claimant settles the accepted cancellation through the normal fenced
  path.
- No schema change: existing version/claim columns and `BEGIN IMMEDIATE` transactions suffice, as
  the Task allowed.

### Remaining In-Slice Work

A44-4/A44-5 are resolved and the corrected Slice handoff returns to A. No new Task is defined here.
The recorded P2/P3 wording/assertion notes were left untouched as non-blocking.

### Risks / Deviations

- The in-flight cancellation path is cooperative: the returning Worker acknowledges cancellation at
  its next safe boundary, so an accepted cancel is durable immediately but its Worker-side
  acknowledgement depends on that pass. This is the intended semantics and is covered by tests; no
  work is stranded because the record is already terminal and the claim released.
- The three Docker scripts fail in this environment unless run with the documented
  `TMPDIR=/run/mf-docker-tmp`, because the Docker daemon cannot see this container's `/tmp`. This is
  a pre-existing environment property, not a change from this Task; all three pass with the
  documented setting.
- No material Contract problem found; no Slice/Contract change was required or made.

### Checkpoint

```text
Status: SUBMITTED FOR REVIEW
Head SHA: 3bb45747b6e50f6bc44fb57e7b6384f429e247bb
```

## B Review Result

```text
Reviewed: NOT YET REVIEWED
Decision: PENDING
Slice Required Outcomes all satisfied: PENDING
Next: PENDING
```

NEXT ACTION: DEVELOPER IMPLEMENTS CURRENT TASK
