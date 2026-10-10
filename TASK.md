# Task 44.7 — Preserve the exact bounded discovery manifest through continuation and refusal

This Task follows [the development workflow](docs/development-workflow.md), uses
[Task/TEMPLATE.md](Task/TEMPLATE.md), and is subordinate to the unchanged
[Slice 44 Contract](SLICE.md).

```text
Task ID: 44.7
Parent Slice: 44
Status: PLANNED
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

### Changed Files

Implementation:

- `mediaflow/domain/media_discovery.py` — durable `DiscoveryProgress.refusal_reasons`,
  `discovery_material_refusal()`, `deduplicate_sources()`, `MAX_DISCOVERY_REFUSALS`.
- `mediaflow/application/media_discovery.py` — manifest keyed by exact ResourceLibrary-relative
  source path; provider-entry/stat confinement admission; monotonic material refusals; truthful
  removal of changed/missing/unstable prior sources.
- `mediaflow/interfaces/service_api.py` — the durable material refusal drives the Finalize gate,
  next action and the new bounded `progress.refusalReasons` / `progress.materialRefusal` readback.

Tests and Web:

- `tests/test_media_discovery.py` — 13 new regressions (repeated observations, duplicate provider
  pages, 100-unique bound, disappeared/changed sources, sibling/ancestor/absolute/traversal/deep
  entries, exact whitespace names, both refusal/read-failure orders, SQLite restart, read-failure-only
  subset). Also removed a stray mid-file `unittest.main()` block that had silently stopped discovery
  of the last class.
- `tests/test_media_discovery_provider_manifest.py` — new production-reachability module: managed
  activation + real OpenList HTTP client/adapter over a bounded loopback server for the repeated-page
  and unsafe-basename journeys.
- `web/src/entities/operations/discovery.ts`, `web/src/entities/operations/discovery.test.ts`,
  `web/src/features/operations/OrganizeDiscoveryPage.tsx`,
  `web/src/features/operations/OrganizeDiscoveryPage.test.tsx` — publish and explain the durable
  refusal; one new page journey test.

### Implemented

- **A44-1** — the manifest is now one entry per exact Storage/ResourceLibrary/source path, so a
  repeated provider page or repeated stability observation never appends a second copy and never
  falsely exhausts the 100-primary bound. A fully completed later pass drops a previously eligible
  source that changed, disappeared or is no longer proven stable. Finalize freezes the exact unique
  list into the existing manual intent.
- **A44-2** — every provider listing entry and explicit-file `stat` answer is validated for exact
  requested-directory membership, safe relative components, no absolute/traversal path and a
  consistent name/type before counting, queueing, observing or freezing. Unsafe/out-of-scope entries
  are excluded without normalization into authority, out-of-selection stat/traversal or an uncaught
  exception, and the walk becomes an actionable durable refusal. Legitimate root prefixes and exact
  whitespace names are preserved.
- **A44-3** — material refusals (budget, entry/directory/page/time, safety depth, cyclic cursor,
  unsafe entry) are recorded in a separate durable, monotonic `refusal_reasons` list. An ordinary
  read failure in another subtree updates the current `incomplete_reason` but can no longer erase
  the refusal, in either event order or across a SQLite restart. That list is the single authority
  that disables Finalize in both the API projection and the backend. The explicitly reviewed
  read-failure-only subset still freezes.

### Tests and Results

Baseline: A's probe
`.git/validation-evidence/9637e7b766fdba5287a68b1f708a7fc1f76f4a68/a-final-review/discovery-probes.py`
reproduced all three defects on Task Base (`mixedStability` duplicated A and finalized 201
`duplicate_source`; `escapedSelection` froze `Outside/B.2002.mkv`; `maskedCursorLimit` froze
`Loop/A.2001.mkv`). After the correction it no longer reproduces them (the probe asserts the defect,
so its negative assertion now fails as expected); the corrected behaviour is asserted by the
committed regressions and retained at `task44-7/run-1/three-defect-verification.py`.

Development and correction feedback:

```text
.venv/bin/python scripts/check_governance.py — PASS
.venv/bin/python -m unittest tests.test_media_discovery — PASS (52 tests)
.venv/bin/python -m unittest tests.test_media_discovery_provider_manifest — PASS (2 tests)
.venv/bin/python -m unittest tests.test_openlist_storage tests.test_smb_storage tests.test_s3_storage tests.test_local_storage tests.test_scanner tests.test_manual_organize_intent tests.test_manual_organize_preview tests.test_manual_organize_execution tests.test_operations_run_inventory tests.test_operations_run_detail tests.test_migration_rehearsal — PASS (255 tests)
```

Final checkpoint gates (T4), repository root:

```text
.venv/bin/python scripts/check_governance.py — PASS
.venv/bin/python -m unittest discover -s tests — PASS: 2367 tests, 7 skipped, 0 failures/errors, 456.921 s
.venv/bin/ruff format --check . — PASS (358 files)
.venv/bin/ruff check . — PASS
.venv/bin/python -m compileall -q mediaflow tests scripts — PASS
.venv/bin/python -m pip check — PASS
.venv/bin/mediaflow --config config/strategy.example.json config validate — PASS
.venv/bin/mediaflow --config config/mediaflow.phase13.2.example.json config validate — PASS
.venv/bin/python -m pip wheel . --no-deps -w <tmp> — PASS; one wheel mediaflow-2.0.0.dev0-py3-none-any.whl, SHA-256 5f7656278c0063f97ed2ca61d4a683e069f15c8dcbf0b7778cfe226e6dca133f
.venv/bin/python scripts/wheel_smoke_test.py <wheel> — PASS (schema 45 backup verified)
.venv/bin/python scripts/docker_release_security_smoke_test.py — PASS
TMPDIR=/run/mf-docker-tmp .venv/bin/python scripts/docker_upgrade_recovery_smoke_test.py — PASS (genuine schema-38 → 45 upgrade, injected failure, restore, old/new work durable)
.venv/bin/python scripts/files_organize_discovery_browser_proof.py — PASS: 11 browser passes, 4 selections, limit refusals, reconciliation, one exact confirmed completed effect and successor isolation
TMPDIR=/run/mf-docker-tmp .venv/bin/python scripts/docker_files_organize_discovery_browser_proof.py — PASS: 7 browser passes, production Worker exact Move and no replay
git diff --check — PASS
```

From `web/`:

```text
npm run test -- --run — PASS: 72 files / 1084 tests
npm run format:check — PASS
npm run lint — PASS
npm run typecheck — PASS
npm run build — PASS (index a1fbbe97…, JS 4182fabb…, CSS abd3206d…)
npm run test:e2e — PASS: 246 tests
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts — PASS: 21 tests
npm run test:e2e -- --config=playwright.direct-files.python.config.ts tests/e2e/direct-files.python.spec.ts — PASS: 10 tests
```

SKIP/UNAVAILABLE: the same 7 pre-existing external-service/endurance profiles remain skipped;
no production service, credential, user media or live deployment was used.

### Decisions

- Kept the durable refusal in the existing `progress_json` document (`refusalReasons`) rather than a
  new table/column: no schema change (still 45), historical records read back with an empty list, and
  `discovery_material_refusal()` still honours an older record's own material `incomplete_reason`.
- Keyed the manifest by the ResourceLibrary-relative source path inside one already
  Storage/library/pin-bound discovery, which is the exact identity `ManualSourceIdentity` consumes.
- Made an unsafe/out-of-scope provider entry a material refusal rather than a silent skip, because a
  walk that received an unconfined entry is not a complete, freezable scope.
- Admission compares the exact path the adapter published for the requested directory, so Local/SMB/
  S3/OpenList root prefixes and exact boundary whitespace names keep working.
- Reported the material refusal before the empty-source case at Finalize, so an unsafe/budget walk
  explains its root cause instead of a misleading `selection_empty`.
- Removed the stray mid-file `unittest.main()` in `tests/test_media_discovery.py`; it had silently
  prevented the last test class from running. No test or assertion was deleted or weakened.

### Remaining In-Slice Work

Correction of A44-1/A44-2/A44-3 within unchanged RO-6 and A's final review. B owns the review and the
factual handoff; no further discovery scope is claimed here.

### Risks / Deviations

- Reachability distinctions preserved: A44-1/A44-2 now have real managed/OpenList production
  reproductions in `tests/test_media_discovery_provider_manifest.py`; the port-level confinement and
  refusal-ordering cases are explicitly labelled Contract/port cases. A44-3's cursor/read-failure
  ordering remains a bounded Storage-port case; no adapter was weakened and no future provider was
  invented.
- A's original probe asserts the defect, so it now fails its own negative assertion on the corrected
  code. That is expected and is recorded, not hidden.
- Two operational first failures were resolved and retained: the discovery browser proof needs the
  Web artifact rebuilt after a source edit, and Playwright suites must not share `web/test-results`.
- No persistence/migration change: schema stays 45 and the genuine upgrade rehearsal passes.
- Pre-existing P2 (concurrent Rules Save allowed-code assertion; queued/paused discovery wording) is
  untouched and remains B's to judge.

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: 62178d37927c861fd1275d84cba9fd6f2488a643
```


## B Review Result

```text
Reviewed: —
Decision: PENDING
Slice Required Outcomes all satisfied: PENDING
Next: PENDING
```

NEXT ACTION: DEVELOPER IMPLEMENTS CURRENT TASK
