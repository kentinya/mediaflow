# Task 44.7 — Preserve the exact bounded discovery manifest through continuation and refusal

This Task follows [the development workflow](docs/development-workflow.md), uses
[Task/TEMPLATE.md](Task/TEMPLATE.md), and is subordinate to the unchanged
[Slice 44 Contract](SLICE.md).

```text
Task ID: 44.7
Parent Slice: 44
Status: READY FOR B REVIEW
Task Base: fd11b62bca219e4424511d4a679c2f3f6f115c77
Difficulty: High
Test Level: T4
Planner / Reviewer: B
```

## Goal

Complete RO-6's exact selected-source discovery-to-intent journey: each eligible source occurs
once, observations stay inside the admitted selection, and material traversal/safety refusals
survive continuation and prevent freezing a truncated manifest. Address A44-1/A44-2/A44-3 as
one discovery-integrity correction, preserving native Files/Operations, immutable pins, Worker
ownership and separate Preview/execution authority.

## Why This Task Exists

Slice 44 is committed as `FIX REQUIRED`; Task 44.6 remains historically accepted. This is the
workflow's new focused correction Task. Six accepted Tasks plus this correction form seven Tasks;
do not split these manifest-integrity failures into assertion-sized Tasks.

B inspected current discovery, managed loading, source identity validation, the four current
Storage pagination adapters, A's receipts and prior Task evidence. B independently reproduced two
current failures using validated/activated managed configuration, SQLite, production runtime/Storage
construction, the production OpenList HTTP client/adapter, a bounded loopback HTTP server and
authenticated discovery/finalize APIs, without runtime policy injection or replaced `list_page`:

- Non-atomic OpenList pages returning the same ordinary filename twice produce a completed
  discovery with two copies of `Movies/A.2001.mkv`. Finalize fails with `duplicate_source` and
  creates no intent. This violates RO-6 / acceptance 27/29/30/31 in the current user journey.
- The OpenList HTTP parser/adapter accepts a basename `../Outside/B.2002.mkv`. Discovery raises
  an unhandled `ValueError` at the existing traversal-free source identity validator. Durable API
  readback remains queued without a published actionable failure. This violates RO-6 / acceptance
  29/30/32. The existing validator prevents this path becoming an intent; retain that protection.

Evidence distinctions matter. A44-1's stable-size receipt injects a policy into the normalized
runtime; current managed loading exposes extensions/maxDepth, not configurable include/exclude/
stability fields. A44-2's sibling and A44-3's cyclic-cursor receipts replace Storage-port responses.
These are Contract regression cases, not independently established current provider reachability
proofs. Do not claim otherwise, add configuration controls, remove current adapter checks, invent
future providers or weaken capabilities to manufacture production reachability. A's decision is
unchanged; this Task completes the existing RO-6 manifest/confinement/refusal behavior.

Local planning evidence is retained at
`.git/validation-evidence/fd11b62bca219e4424511d4a679c2f3f6f115c77/b-plan44-7/`:
`production-probes.py`, `production-receipts.json`, original failed harness runs and the confirmed
run log. A's original probes remain in the prior Head's `a-final-review/` directory.

Initial governance preflight rejects `FIX REQUIRED` plus `NO ACTIVE IMPLEMENTATION TASK`. The
user/workflow explicitly require B to create this correction Task in that handoff. Recheck with
the legitimate planned Task; do not change Slice status/Base or repair unrelated tooling here.

## Implementation Scope

One existing boundary: discovery Domain/Persistence → Application/Worker → authenticated API
→ existing ResourceLibrary Files/Operations → manual intent handoff → regression evidence.

1. Keep a bounded manifest keyed by exact Storage/ResourceLibrary/source path. Deduplicate provider
   pages and repeated observations through durable pause/restart. A previously eligible file that
   changes, disappears or becomes unstable must not survive merely because its path was seen.
   Count unique eligible primaries for the 100-source bound; actual traversal/page/time work remains
   bounded. Preserve valid source identity and genuine stability evidence.
2. Validate provider entry path/name/type, exact requested directory and admitted selection before
   source construction or traversal scheduling. Reject sibling/ancestor/absolute/traversal and
   inconsistent entries without normalization into authority, out-of-scope observations, link
   following, content reads or uncaught source-construction errors. Preserve valid exact whitespace
   names and legitimate adapter/root conventions. Publish an actionable bounded refusal outcome.
3. Make material incomplete/safety facts durable and monotonic. Ordinary read failure cannot erase
   unsafe-entry, cursor or exhausted-budget refusal. Worker continuation/restart, API projection and
   backend Finalize agree even when findings are truncated. Preserve the separately legal explicitly
   reviewed read-failure-only subset of unaffected sources.
4. Freeze one exact deduplicated manifest through existing manual intent authority. Maintain pin,
   version/claim fencing and unknown-response reconciliation. Adjust API/Web only as needed for
   corrected completeness/counts/recovery; no alternate workflow or execution permission.
5. Prefer existing bounded state/interfaces. Persistence changes require compatible migration and
   historical discovery/file-only intent/Preview/result readback. Do not redesign configuration,
   queue, Worker or discovery engine to solve these cases.

Frozen: Slice 43/preservation branch, unrelated RO-1 through RO-5 behavior/visual contracts, user
images, private configuration and live deployments/media. Slice Contract/Roadmap/product CURRENT
closure documents remain A-owned. Only directly necessary factual implementation notes are in scope.

## Acceptance Criteria

- [ ] AC1 — Current managed/OpenList repeated pages yield one source and one valid intent, without
      duplicate_source or false primary limits. Mixed stable/unstable policy-level cases over three
      observations and SQLite restart also deduplicate. Changed/missing/unstable prior sources keep
      truthful identity/stability semantics. Exactly 100 unique primaries work; 101 cannot freeze.
- [ ] AC2 — The current OpenList unsafe-name journey publishes an actionable durable refusal,
      without an uncaught exception or misleading queued/completed success. Unsafe entries never
      enlarge the manifest or cause out-of-selection stat/traversal. Cover sibling/ancestor/absolute/
      traversal/path-name mismatch at the Storage port; retain current adapter defenses, legitimate
      root prefixes and exact whitespace names. API/Web expose the same result and recovery.
- [ ] AC3 — Material safety/budget/cursor refusal survives ordinary subtree read failure in both
      orders and across SQLite restart/continuation. Readback disables Finalize; backend Finalize
      rejects it without intent/authority. Read-failure-only explicitly reviewed subsets still work.
      Label cursor port cases separately; hypothetical adapters alone cannot establish current P0/P1.
- [ ] AC4 — Native ResourceLibrary Files list/grid and Operations expose unique counts, failures and
      safe continuation; valid discoveries reach exact intent/Preview and separate confirmation
      without CLI/token ceremony. Unknown responses reconcile durable work rather than duplicate it.
      MediaLibrary retains no Organize entry; ordinary file commands and unrelated pages retain parity.
- [ ] AC5 — Preserve exact old/new Active pins, frozen-source immutability, stale-owner fencing and
      completed/partial/uncertain effect non-replay. Discovery has metadata-only Storage observations,
      zero Provider/content-read/mutation calls and no FileIndex admission/stability authority.
      Analysis stays zero mutation; only OrganizerExecutor mutates authorized exact Preview items;
      C remains C under A downstream policies. No overwrite/delete/fallback permission is gained.
- [ ] AC6 — Assigned T4 gates pass with truthful PASS/FAIL/SKIP/UNAVAILABLE evidence. Keep tests,
      assertions and first failures; prove unrelated failures at Task Base. Checkpoint only this
      correction, preserve the four pre-existing user PNGs, and exclude private config/real secrets.

## Required Tests

### Development and correction feedback

Start with committed regressions for the two current production reproductions, then related
multi-observation/dedup/confinement/refusal cases. Use real managed activation/loading, SQLite,
temporary Local roots and real adapter methods for current reachability proofs. Controlled clocks
and bounded Storage-port fakes cover explicitly labelled Contract cases without weakening adapters.

```bash
.venv/bin/python scripts/check_governance.py
.venv/bin/python -m unittest tests.test_media_discovery
.venv/bin/python -m unittest tests.test_openlist_storage tests.test_smb_storage tests.test_s3_storage tests.test_local_storage tests.test_scanner tests.test_manual_organize_intent tests.test_manual_organize_preview tests.test_manual_organize_execution tests.test_operations_run_inventory tests.test_operations_run_detail tests.test_migration_rehearsal
```

Run changed Web discovery/Files/Operations tests and the affected native browser case before full
gates. Record actual names of added test modules. Cover repeated pages, changed observations,
overlap, unique 100/101, unsafe entries, both refusal/read-error orders, restart, stale claims,
historical pins, unknown responses and no-side-effect spies.

### Final checkpoint gates

T4 covers source confinement/admission, durable ownership and execution handoff. Full Python
discovery includes focused/integration cases; do not duplicate them solely for reviewer identity.

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
.venv/bin/python -m pip wheel . --no-deps -w dist
.venv/bin/python scripts/wheel_smoke_test.py dist/mediaflow-*.whl
.venv/bin/python scripts/docker_release_security_smoke_test.py
.venv/bin/python scripts/docker_upgrade_recovery_smoke_test.py
.venv/bin/python scripts/files_organize_discovery_browser_proof.py
.venv/bin/python scripts/docker_files_organize_discovery_browser_proof.py
git diff --check
```

Smoke-test exactly one current wheel and record its hash. Audit production source/dependencies for
forbidden FFmpeg/FFprobe and staged/tracked private config, secrets, unrelated/frozen files. Docker
runs use isolated projects/ports/volumes and daemon-visible temp binds (`TMPDIR=/run/mf-docker-tmp`
where required), preserving live services. Upgrade/restart proof preserves existing schema-45
discoveries and historical file-only work; extend real migration evidence if persistence changes.

From `web/`:

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

Real-Python/native production-Docker proofs use current built assets, real SQLite/Worker, synthetic
media and bounded fake/local Providers. Cover folder/file/multiple/mixed selections, unique-source
handoff, unsafe/refused discovery, explicit read-failure-only subset, Operations return and normal
exact separately confirmed Preview execution. Inspect actual saved browser states and served
artifact identity. Distinguish policy/port cases from native managed journeys. Full Web/direct-file
regressions cover unchanged RO-1 through RO-5; run their affected native proofs if those surfaces
change. No new Rules/toolbar redesign or optional visual proof is required for this correction.

### B independent verification

B inspects actual Task Base..submitted Head and candidate/evidence identity. Independently repeat
managed/real-OpenList duplicate-page and unsafe-name journeys, durable readback/finalization,
restart and refusal/read-failure ordering. Inspect one native Files → Operations → exact intent/
Preview journey and original Docker/migration artifacts. For every suspected blocker, check current
production reachability, concrete user effect, Contract clause, repeatable actual evidence and
severity in that order. Optional injected policies, unsupported future assembly or weakened
adapters alone cannot justify FIX REQUIRED.

Other gates may use verified matching evidence; missing/contradicted/incompatible evidence needs a
fresh affected run. Upon correction Task PASS, B updates the factual handoff/evidence and returns
Slice status to `READY FOR A REVIEW`, without declaring Slice acceptance/PASS/CLOSED. Preserve A's
prior review history and immutable Slice Base.

### Evidence and rerun rules

Retain a secret-free index and original logs/receipts/screenshots under
`.git/validation-evidence/<tested-full-sha>/task44-7/<run-id>/` or accessible CI through A's decision.
Record source/dirty/submitted identity, exact commands/cwd/versions/dependencies/safe config/
selection/Worker settings, built JS/CSS/image/wheel digests, exit/count/skip/unavailable/duration,
first failures and repeats. `/tmp` alone or prose PASS is insufficient. Do not run suites sharing
`web/test-results` concurrently. Changed executable/test/harness/dependency/config/artifact inputs
need fresh affected evidence; the corrected T4 candidate needs every assigned final gate.
Report-only successors require proven unchanged runtime inputs and fresh document-consuming checks.
Negative baseline reproductions are not passing product gates.

## Non-goals

- Change Slice Goal/Required Outcomes/Surfaces/Safety/Deferred/Base, rescope or declare closure.
- New managed include/exclude/stability controls, providers, queue or second organizing engine.
- Expand selection/budgets, auto-split manifests, follow links or silently freeze truncated prefixes.
- Add execution/overwrite/delete/fallback authority, FileIndex admission or content hashing/FFprobe.
- Fix non-blocking Rules Save assertions, progress wording, optional proof or unrelated cleanup.
- Repair governance tooling solely for the transient no-Task handoff or change live deployment.
- Reopen accepted Tasks or split fixes by assertion. If this Task exceeds three B correction rounds,
  reassess the whole approach for unnecessary state/complexity before continuing; keep ID/Base/Goal
  fixed and return any material Contract problem to A.

## Developer Completion Report

This is the correction-round report for B's `FIX REQUIRED` review round 1. The round-1 report
that B reviewed is preserved in Git at `0c989769f702d409bee8082991574771f257680c`.

### Changed Files

Correction (this round):

- `mediaflow/application/media_discovery.py` — `_finalize()` now *builds* the intent through the
  intent service and persists the discovery link plus that exact intent as one repository outcome
  via `_persist_frozen()`; a repository that cannot link atomically fails closed with
  `DiscoveryUnavailable` instead of committing an orphan intent or a dangling link.
- `mediaflow/application/manual_organize.py` — `create_from_sources()` is split into
  `prepare_from_sources()` (validation + projection, no persistence) and a thin persisting
  wrapper. The ordinary Files/Preview paths keep calling `create_from_sources`; its signature,
  return value and validation are unchanged.
- `mediaflow/infrastructure/sqlite_runtime.py` — new
  `create_manual_intent_for_discovery(discovery, expected_version, intent, items, audit)`: one
  `BEGIN IMMEDIATE` transaction that applies the discovery version CAS together with a one-shot
  `intent_id IS NULL` guard and only then inserts the intent, its items and its creation audit.
  `create_manual_intent_with_audit` now shares the extracted `_insert_manual_intent_locked()`
  helper; no schema change (still 45).
- `tests/test_media_discovery.py` — new `FinalizeHandoffFencingTests` with 7 regressions
  (concurrent authenticated finalize, direct two-linker race, lost-response repeat, idempotent
  re-finalize, SQLite reopen/restart, fail-closed without atomic linkage, one-shot repository
  transition).
- `web/src/features/operations/OrganizeDiscoveryPage.tsx` — the fenced concurrent-finalize 409 is
  explained as recovery (refresh and open the one linked list) instead of leaking the raw code.
- `web/src/features/operations/OrganizeDiscoveryPage.test.tsx` — one new page journey test.

### Implemented

- **B P1 (AC4 / Implementation Scope 4 / RO-6 durable handoff and duplicate-intent fencing)** —
  the previous `_finalize()` called `create_from_sources()`, which committed the intent first, and
  only then published the discovery link by version CAS. Two legitimate concurrent Finalize
  requests therefore both created a durable intent; the CAS loser returned 409 while its orphan
  intent stayed visible in `GET /api/v1/manual-intents`.
- Now the intent is only *prepared* (validated, not persisted) before the transition. The
  production repository commits the discovery link and the intent in one transaction, gated by the
  existing version CAS **and** a one-shot `intent_id IS NULL` guard. Only the request that wins the
  discovery transition inserts an intent; every concurrent, repeated, lost-response or
  restart-then-retry request converges on that one linked intent, and a losing request has no side
  effect.
- Actor / pin / source / version binding is retained: the intent is still built by the same
  `ManualOrganizeIntentService` validation with the discovery's own actor and immutable snapshot,
  and `create_from_sources` remains the ordinary Files/Preview authority. A genuinely new successor
  discovery is still a separate admission and a separate intent.
- Discovery still grants no execution authority: finalize only freezes the source list and links an
  ordinary open manual intent; a separate exact Preview and an explicitly confirmed execution are
  still required. Zero Storage mutation and no Task were created by any run.
- B's P1 reproduction was re-run unchanged after the fix: 10/10 attempts now return exactly one
  durable intent, and the linked discovery intent is that same intent.

### Tests and Results

Reproduction of B's P1 (unchanged probe, `.git/validation-evidence/.../b-review44-7/concurrent-finalize.py`):

```text
before fix: 2 durable intents per raced attempt (201 + 409), linked discovery pointed at only one
after fix:  10/10 attempts -> exactly 1 durable intent, linked == the created intent, 0 tasks,
            media source still present, statuses [201, 409]
```

Development and correction feedback:

```text
.venv/bin/python scripts/check_governance.py — PASS
.venv/bin/python -m unittest tests.test_media_discovery — PASS (59 tests, incl. 7 new
  FinalizeHandoffFencingTests)
.venv/bin/python -m unittest tests.test_media_discovery_provider_manifest — PASS (2 tests)
.venv/bin/python -m unittest tests.test_manual_organize_intent tests.test_manual_organize_preview
  tests.test_manual_organize_execution tests.test_scope_continuation tests.test_task_persistence
  tests.test_operations_run_inventory tests.test_operations_run_detail — PASS (205 tests)
.venv/bin/python -m unittest tests.test_openlist_storage tests.test_smb_storage tests.test_s3_storage
  tests.test_local_storage tests.test_scanner tests.test_migration_rehearsal — PASS (255 tests)
```

Final checkpoint gates (T4), repository root:

```text
.venv/bin/python scripts/check_governance.py — PASS
.venv/bin/python -m unittest discover -s tests — PASS: 2374 tests, 7 skipped, 0 failures/errors,
  428.147 s
.venv/bin/ruff format --check . — PASS (358 files)
.venv/bin/ruff check . — PASS
.venv/bin/python -m compileall -q mediaflow tests scripts — PASS
.venv/bin/python -m pip check — PASS
.venv/bin/mediaflow --config config/strategy.example.json config validate — PASS
.venv/bin/mediaflow --config config/mediaflow.phase13.2.example.json config validate — PASS
.venv/bin/python -m pip wheel . --no-deps -w <tmp> — PASS; one wheel
  mediaflow-2.0.0.dev0-py3-none-any.whl, SHA-256
  2ebc36a88f2fc73a593c291a824b01e37845e1bf78243332c23967f24139cf15
.venv/bin/python scripts/wheel_smoke_test.py <wheel> — PASS (schema 45 backup verified)
TMPDIR=/run/mf-docker-tmp .venv/bin/python scripts/docker_release_security_smoke_test.py — PASS
TMPDIR=/run/mf-docker-tmp .venv/bin/python scripts/docker_upgrade_recovery_smoke_test.py — PASS
  (genuine schema upgrade, injected failure, restore, old/new work durable)
.venv/bin/python scripts/files_organize_discovery_browser_proof.py — PASS: 11 browser passes,
  4 discovery cases, limit refusals, reconciliation and one exact confirmed execution
TMPDIR=/run/mf-docker-tmp .venv/bin/python scripts/docker_files_organize_discovery_browser_proof.py
  — PASS: 7 browser passes, production Worker exact Move and no replay
git diff --check — PASS
```

From `web/` (after rebuilding the served assets for the changed page):

```text
npm run test -- --run — PASS: 73 files / 1086 tests
npm run format:check — PASS
npm run lint — PASS
npm run typecheck — PASS
npm run build — PASS (index 1ec542ff…, JS ea91f2ef…, CSS abd3206d…)
npm run test:e2e — PASS: 246 tests
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts
  — PASS: 21 tests
npm run test:e2e -- --config=playwright.direct-files.python.config.ts tests/e2e/direct-files.python.spec.ts
  — PASS: 10 tests
```

SKIP/UNAVAILABLE: the same 7 pre-existing external-service/endurance profiles remain skipped; no
production service, credential, user media or live deployment was used. Docker gates ran with
`TMPDIR=/run/mf-docker-tmp` because the daemon cannot see a `/tmp` bind source; the first
release-security attempt without it failed on that mount and is retained.

FAIL / PRE-EXISTING / UNRELATED: the earlier full-suite run recorded
`tests.test_v2_rules_workspace_commands.RulesWorkspaceCommandTests.test_simultaneous_saves_never_publish_a_mixed_or_lost_successor`
failing on `['rules_destination_check_failed']`. It is intermittent and reproduces on the unchanged
Task Base worktree `fd11b62` (21 failures in 400 isolated executions, retained as
`base-rules-repro-long.py`); B already recorded it at Task Base and excluded it from the fix list.
The final full-suite run passed without it. This judgement remains B's.

### Decisions

- Made the discovery link and the intent one durable transaction rather than adding a
  retry/compensation step, because "converge on one linked intent" is only guaranteed if the loser
  cannot commit first. The one-shot `intent_id IS NULL` guard is what makes the transition
  idempotent even when two writers hold the same version.
- Reused the existing intent validation by extracting `prepare_from_sources()` instead of
  duplicating admission rules, so the discovery path and the ordinary Files path cannot drift.
- Kept `create_from_sources()` as the public ordinary admission API with an unchanged signature and
  behaviour; the discovery path is the only new caller of the prepare/link split.
- Made a repository without atomic linkage fail closed (`DiscoveryUnavailable`, 503) rather than
  fall back to a two-step commit that could leave orphan work. This is a safety invariant, not a
  capability regression: the production repository always provides the atomic method.
- No schema or migration change; the finalize transaction only writes columns that already exist.
- Explained the fenced 409 in the Web page instead of showing the raw `discovery_conflict` code,
  matching the existing durable-refusal copy pattern.

### Remaining In-Slice Work

Correction of B's P1 within unchanged RO-6, and B's re-review plus the remaining factual handoff.
No further discovery scope is claimed here; B owns the review boundary and any Slice-level decision.

### Risks / Deviations

- Evidence location: this run's index and raw logs are staged at
  `.git/validation-evidence/<submitted-sha>/task44-7/run-1/` in the submitted commit. The wheel
  rebuilt at the final candidate has a different file SHA than the pre-test-edit build, but every
  wheel member's content hash is byte-identical (tests are not packaged), so the earlier
  release-security/upgrade results remain valid for the production artifact.
- The B P1 probe is a local independent script under `.git/validation-evidence/`; the committed
  regression is `FinalizeHandoffFencingTests`, which drives the real WSGI API, real managed
  activation, real Local Storage and real SQLite without replacing a production method.
- The Rules concurrency failure above is pre-existing/unrelated by Base proof but is not declared
  non-blocking here; B decides.
- Pre-existing P2 (Rules Save allowed-code assertion; queued/paused discovery wording) is untouched.

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: f514c157e098bdf753356a8ec2c9517494df2fbf
```

## B Verification Evidence

B reviewed the full `fd11b62bca219e4424511d4a679c2f3f6f115c77..0c989769f702d409bee8082991574771f257680c`
range. `62178d37927c861fd1275d84cba9fd6f2488a643..0c989769f702d409bee8082991574771f257680c`
changes only TASK.md; executable inputs are identical. This is correction review round 1.

Evidence is local and retained at
`.git/validation-evidence/0c989769f702d409bee8082991574771f257680c/b-review44-7/`.
Independent current managed/OpenList probes confirm corrected duplicate-page and unsafe-entry
behaviour; the focused suite passes 54 tests. A separate current managed/real Local/SQLite API
concurrency probe, without replaced repository/adapter/runtime methods, twice reproduces duplicate
durable intents when two legitimate Finalize requests start together. Raw request responses,
discovery readback and authenticated manual-intent listing are retained. No media effect or Task
execution was requested; the source remains present and the Task table remains empty.

Fresh full regression ran 2367 tests in 472.412 seconds: FAILED, 2 failures, 7 skipped. Both failures
are the known Rules simultaneous-Save allowed-code assertion (`rules_destination_check_failed`),
under the two import names. Original pre-existing Base failures remain in the prior B evidence
(`base-concurrency-diagnostic.log`, `slice-base-concurrency-diagnostic.log`); B's new archived exact
Task-Base isolated runs passed 12 attempts and do not claim to reproduce that intermittent failure.
These assertions are not the reason for this rejecting review and remain outside the fix list.

Fresh Web unit regression passes 73 files / 1085 tests; format/lint/typecheck/build and root
governance/Ruff/compile/dependency/example-config checks pass. Developer's reported 72 files / 1084
tests do not describe this fresh run. The supplied wheel differs from submitted source in
media_discovery.py, and the supplied discovery Docker image differs in all three changed Python
modules; their earlier results are not reused as final-candidate gates. B rebuilt the current wheel
and its isolated smoke passes. The first smoke attempt used a non-executable temporary mount;
the retained repeat uses /tmp. Fresh Docker release-security validation failed while waiting for
isolated Compose health; it is not treated as a separately proven production P0/P1. Upgrade,
fresh Docker/native discovery and E2E gate repeats are NOT RUN after the proven current P1.
All assigned T4 gates remain required on the corrected candidate before PASS; no gate is waived.

No source/tests/Contract/Roadmap changes were made by B, no assertions/skips were weakened,
and the four pre-existing user images/private configuration remain excluded and preserved.

## B Review Result

```text
Reviewed: fd11b62bca219e4424511d4a679c2f3f6f115c77..0c989769f702d409bee8082991574771f257680c
Decision: FIX REQUIRED
Slice Required Outcomes all satisfied: NO
Next: SAME TASK FIX LOOP
```

- P1 — AC4 / Implementation Scope 4 / RO-6 durable handoff and duplicate-intent fencing:
  two concurrent authenticated Finalize requests for the same discovery and expectedVersion
  return HTTP 201 and 409, but create two durable intents for the same actor/pin/source. Discovery
  links only one; authenticated `GET /api/v1/manual-intents` exposes both. Two independent runs
  reproduced this on the current legal managed configuration, real Local Storage and SQLite,
  without weakening or replacing a production method. Evidence: `concurrent-finalize.py`,
  `concurrent-finalize.log`, `concurrent-finalize-repeat.log`,
  `concurrent-finalize-receipts.json` in the B evidence directory above. The current
  `mediaflow/application/media_discovery.py` `_finalize()` commits `create_from_sources()` before
  publishing the discovery link by version CAS; the losing request has already committed its
  extra intent. Make creation/linkage for one discovery atomic or equivalently durably fenced
  and idempotent: concurrent, repeated, lost-response and restart paths must converge on one
  linked intent without orphan work. Retain actor/pin/source/version binding and legitimate
  explicitly new successor intents. Fix inside Task 44.7 with its unchanged ID/Base/Goal/Scope;
  include a current real-SQLite authenticated concurrency/recovery regression, then complete the
  existing assigned T4 candidate gates.

NEXT ACTION: DEVELOPER FIXES CURRENT TASK — SAME TASK FIX LOOP
