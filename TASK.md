# Task 44.6 — Bounded folder and mixed-selection discovery through native manual Organize

This Task follows [the development workflow](docs/development-workflow.md) and is subordinate to
current [`SLICE.md`](SLICE.md).

```text
Task ID: 44.6
Parent Slice: 44
Status: IN PROGRESS
Task Base: 001bae34769c718033f147873ab16cc22630e484
Difficulty: High
Test Level: T4
Planner / Reviewer: B
```

## Goal

Complete Slice 44 RO-6 / AC27–32 as one native ResourceLibrary journey: select folders and/or
files, deliberately discover bounded eligible sources under one immutable admitted configuration,
inspect progress/exclusions/errors, safely pause/continue/cancel, then use the existing per-item
choices, exact Preview and separate confirmed execution. Preserve source identity, independent
outcomes/recovery and Files/Operations return context. MediaLibrary remains file management only.

## Why This Task Exists

At Task Base, `RuntimeFilesBrowserService.browse_resource_library` publishes `organizeEligible`
only for regular files; ResourceLibrary folder menus and batch selection cannot admit folders.
`ManualOrganizePreviewService.admit_storage_paths` synchronously stats file selections and
`_source_identity_from_storage` rejects directories with `source_not_file`. Existing whole-library
Preview enumeration lacks this selected-scope, bounded, durable discovery journey. `StorageScanner`
has configured filtering/stability semantics but derives repeated observations from FileIndex and
writes its scan index; calling that workflow cannot establish Files source authority.

The existing Storage `list_page/stat`, manual `create_from_sources`/published historical-pin
support, SQLite Task/Job/claim infrastructure, resident Processing Worker and Operations readback
are the integration boundaries. Reuse these and their pure policy semantics. A new discovery
record/command inside those boundaries may be necessary; a second processing engine, queue,
Scheduler, supervisor or independent Task lifecycle is outside scope. This is the largest remaining
coherent Required Outcome, rather than separate backend, folder-button, stability or test Tasks.

### Preceding review and all-outcome recheck

Task 44.5 is PASS after one correction round. B inspected the real Base..Head diff;
`df0bf7b1a7920b1d70e180a5d7528298c8ceba14` fixes measured tooltip placement and
`001bae34769c718033f147873ab16cc22630e484` changes only the completion report.

```text
Reviewed: c04870ca33f81d393c8a1be3b2e3840ef892b4f8..001bae34769c718033f147873ab16cc22630e484
Decision: PASS
Slice Required Outcomes all satisfied: NO
Next: NEXT TASK
```

AC1–AC6 are COMPLETE. B independently verified the legal 240-byte Local tail-name disclosure
on both routes/list/grid by hover/focus, exact raw paths, keyboard navigation and read recovery,
with zero unintended mutation/activation/executable work. Real-Python proof: 22 cases/50 screenshots;
isolated Docker: 22 cases/48 screenshots, served index/JS/CSS matching the fresh local build.
The inspected df0bf7b image is reused only across the report-only successor, with exact input and
artifact identity verified; it is not claimed freshly built from 001bae3.

Independent final gates: Python 23 PASS; full Web 71 files/1078 PASS; default E2E 239 PASS
(normal 2 workers, 0 failed/skipped); real-Python Operations 21 PASS/DirectFiles 10 PASS;
governance/Ruff/compileall/Web format/lint/typecheck/build/diff checks PASS. First full-unit
4 failures and three Docker health-timeout runs are retained; the unchanged full unit command
and normal Docker proof then passed when run without concurrent gate load. No exclusions,
weaker assertions, timeout/retry/worker changes or pre-existing-failure claims were used.

Evidence and accepted Task snapshot (local ignored artifacts, retained through A review):
`.git/validation-evidence/001bae34769c718033f147873ab16cc22630e484/b44-5-correction-review/`
(`review-index.json`, `task44-5-pass-TASK.md`, `task44-5-pass-review.md`, raw logs and visuals).
Slice Contract/Base and private/user files are preserved. No tracked product changes are made by B.

| Required Outcome | Current result | Rechecked basis |
| --- | --- | --- |
| RO-1 | COMPLETE | Accepted 44.1 direct commands; unchanged backend and full Files/real-Worker regressions retained |
| RO-2 | COMPLETE | Accepted 44.4 native Rules layout/forms; current full Web/default E2E retain affected journeys |
| RO-3 | COMPLETE | Accepted 44.2 canonical/legacy destinations and C identity; no backend/config/schema change in 44.5 |
| RO-4 | COMPLETE | Accepted 44.3 object-scoped tests/separate complete flow; retained by full Web/E2E regressions |
| RO-5 | COMPLETE | 44.5 actual corrected source, real Python/Docker geometry, disclosure and navigation proofs |
| RO-6 | INCOMPLETE | Current folder eligibility/admission reject directories; selected bounded durable discovery is absent |

The next Task Base is the actual committed HEAD above; Slice Base remains unchanged.

## Implementation Scope

Domain/safe-scope and discovery state → additive compatible Persistence → Application/Worker
read-only discovery and manifest handoff → authenticated APIs/Operations projections → native
ResourceLibrary list/grid/manual Organize → integration, restart/migration and browser evidence.

1. **Selection and admission.** Enable explicit folder Organize and folder-only/file-only/multiple-
   folder/mixed batch selections in ResourceLibrary list/grid; retain Operations `新建整理任务`
   handoff and original library/directory return context. Browsing, checking selections, navigation,
   refresh and view changes do no discovery. Backend owns entry types, enabled library/Storage,
   permissions, safe scopes and budgets. Validate the entire request before durable admission;
   reject empty/root, malformed/escape/link or structurally invalid source selections with useful correction.
   Never turn a partly invalid request into a different valid scope. Preserve exact whitespace;
   deduplicate repeated paths and parent/child/explicit-file overlaps on path-component boundaries.
   Selection does not grant execution or directory mutation. Preserve existing public file-only
   intent/Preview/API compatibility; the new native discovery stage must not expand old admissions.

2. **Concrete discovery budgets.** Enforce the following server-side per admitted discovery,
   persisted with its exact scope and never reset by pause/restart/continue:

   | Budget | Bound and counting |
   | --- | --- |
   | Submitted scopes | 1–100 non-root relative paths; validate raw input before deduplication |
   | Primary media | At most 100 unique primary sources in the resulting intent; detect 101 rather than silently admitting the first 100 |
   | Visited entries | At most 10,000 returned entries inspected across all selected scopes/pages, including excluded entries |
   | Visited directories | At most 1,000 distinct directories opened, including selected folders |
   | Paging | `list_page` limit 100; at most 2,000 total page fetches, with bounded provider cursors and repeated/cyclic cursor rejection per directory |
   | Traversal depth | Safety maximum 32 descendant directory levels below a selected folder; the pinned configured `maxDepth` still follows existing library-root semantics |
   | Active work time | At most 600 cumulative seconds of discovery processing/provider work, measured with a monotonic clock; paused/stability waiting time is excluded, work already consumed is retained |
   | Path/cursor shape | Retain existing Files limits: 4096 UTF-8 path bytes, 128 safe segments, 1024 entry-name bytes and 2048 adapter-cursor bytes |
   | Readback | Page item/findings lists at most 100 records; bounded summaries never suppress total errors, incomplete traversal or limit state |

   These bounds retain existing 100-item manual intents and 100-entry Storage paging, while
   bounding media-free traversal and Worker occupancy. Enforce provider timeout/lease boundaries
   through current adapters/Worker conventions; the 600-second budget does not promise immediate
   interruption of an in-flight provider call. Persist counters atomically with progress so replay
   of a safely resumed observation cannot duplicate sources or reset a bound. At a budget/safety
   limit, show incomplete/over-limit scope and a native narrow-selection action; never produce an
   executable first-N prefix or silently split into multiple intents. Configured depth exclusions
   are explained separately from an exhausted safety budget. Exclusions/errors are not organized
   media, and unknown totals remain unknown until established. If a concrete existing platform
   constraint prevents these compatible budgets, return it to B before changing them.

3. **Metadata-only discovery and policies.** Traverse only submitted confined subtrees with paged
   Storage list/stat; validate returned entry paths/types and never follow links. Apply the pinned
   media extensions/include/exclude/depth/stability policy using current Python semantics; a small
   shared pure helper extraction is allowed, not a second rule engine or FileIndex-based scanner.
   Preserve the original ResourceLibrary-relative paths and parent context for Recognition.
   Temporary/non-media/unsupported/extra entries receive bounded explanations. Existing primary/
   extra and subtitle/NFO/image/trailer association remains authoritative; sidecars are not new
   primary execution items. No content read, full-media hash, Provider call or FileIndex lookup
   proves discovery eligibility/stability. Subsequent explicit analysis retains its existing
   bounded NFO/attachment/Metadata behavior.

4. **Real stability and independent findings.** Age/mtime checks never fabricate a required
   stable-size interval. Record bounded durable observations of the actual source in this
   discovery context and use controlled-clock-tested elapsed observation intervals; a changed
   size or relevant observable identity resets the interval. Explain waiting/not-yet-proven
   stability and expose safe observe/continue action without treating actively written files as
   ready. Empty, all-excluded, unstable-only and unreadable scopes remain different outcomes.
   Ordinary item/subtree read failures preserve successful siblings and explicit incomplete
   discovery. Known eligible sources from such partial discovery may proceed only as an
   explicitly reviewed subset with the missing scopes visible, never as complete-folder success.

5. **Durable Worker ownership and recovery.** Admit promptly without recursive enumeration or
   Provider calls in HTTP. Persist actor/exact scope/admission identity and the exact immutable
   Active revision/digest. Use the existing Task/Job/resident Worker/readiness/control boundaries
   for durable discovery, claim/lease/heartbeat/fenced publication and Operations progress.
   Distinguish no/stale/unsupported Worker and unavailable pin from API liveness; readback and
   controls agree across Web/API. Pause/cancel are cooperative requests with acknowledged durable
   state, retained findings and safe continuation. Non-mutating observation may be resumed after
   ownership expiry/restart under a new valid fence; stale owners cannot append/publish/finalize.
   Unknown admission first reconciles durable actor/scope/pin-bound readback, preventing duplicate
   runs or manifests without requiring raw tokens. No new Active can repin admitted discovery,
   stability or its later analysis. Missing/corrupt/unpublished pins fail closed with recovery.

6. **Freeze and existing manual handoff.** Finalize one immutable deduplicated source list with
   Storage-built identities and idempotent linkage to the existing manual intent. Historical-pin
   `create_from_sources` handoff must prove this durable admission and its published revision;
   browser-supplied pins/manifests/fingerprints are never authority. Later folder additions cannot
   enlarge the list. Existing choices/Recognition/TypePolicy/Metadata/Naming/Classification/
   Organize/Planner remain the production pipeline, including RO-3 destinations and C reusing A
   policies without changing C. Missing/changed sources yield affected-item refusal/re-analysis,
   preserving unaffected items. Preview is zero mutation, with exact sources/targets/attachments,
   conflicts and permissions. Execute only explicitly selected exact Preview items under current
   permission/capability/source/ownership/one-shot authority gates. No whole-directory Move,
   cleanup permission, silent fallback/overwrite/delete or automatic uncertain replay is granted
   by discovery. New-source recovery is explicit successor work, never mutation of a frozen list,
   old pin, consumed authority or completed/partial/uncertain result. Post-result index-sync errors
   remain separate and cannot trigger another media mutation.

7. **Compatibility and evidence.** Use additive persistence only where required for discovery
   scope/checkpoints/admission/linkage; preserve existing file-only intents, snapshots, previews,
   results, Tasks/Jobs, direct-file commands and authority on restart/upgrade. Rehearse migration
   against actual prior committed SQLite/application artifacts and include historical admitted,
   completed, partial and uncertain work. Existing work gains no folder scope or new permission.
   Extend current production-shaped Python/SQLite/Storage/Worker browser seams and committed
   coverage. Preserve RO-1 through RO-5, Rules, MediaLibrary isolation and direct commands.

Frozen: Slice User Goal/Required Outcomes/Required Surfaces/Safety Invariants/Base and deferrals;
A-owned Roadmap/closure/CURRENT reconciliation; frozen Slice 43; original user images and all
pre-existing unrelated files. `config/alist.json` remains ignored/untracked/unstaged. Do not use
production credentials/media or alter a live Docker deployment. Bring a genuine Contract conflict
to B immediately; do not silently rewrite the Contract or substitute a weaker execution identity.

## Acceptance Criteria

- [ ] AC1 — ResourceLibrary list/grid folder-only, file-only, multiple-folder and mixed actions
      complete native discovery → reviewed choices → exact Preview → separately confirmed
      execution, preserving Operations creation/return and original-directory context. No CLI,
      raw-token handling or MediaLibrary Organize entry; selection alone starts no work.
- [ ] AC2 — Entire scope validation, exact whitespace and component-aware overlap deduplication
      hold under backend authority. Paging and Scope 2 bounds are durable and enforced; 100
      primary items work, while 101/entry/directory/depth/page/time/cursor exhaustion cannot
      silently authorize a prefix or claim complete traversal. Links/escapes/unsafe entries fail
      closed. Configured policy exclusions remain distinguishable from safety limits.
- [ ] AC3 — Pinned filters/depth and genuine durable size-stability observations exclude actively
      written/temporary/unsupported sources. Empty/all-excluded/unstable/unreadable/partial states
      and independent findings are truthful, with explicit subset review or safe correction/
      observe/continue/narrow recovery. FileIndex is neither admission nor stability authority.
- [ ] AC4 — Admission is prompt and reconciles unknown outcomes; Worker/readiness, progress,
      pause/continue/cancel/restart and lease fencing are native and durable. Actor/scope/pin and
      counters survive without duplicate items/intents. Changed Active cannot repin old work;
      unavailable/corrupt/unpublished context refuses work and arbitrary historical pins.
- [ ] AC5 — Frozen lists and Storage identities feed the existing pipeline with original paths,
      applicable RO-3 target semantics, C identity and attachment rules intact. Later new sources
      are excluded; missing/changed sources stop their own item. Execution retains current
      permission/capability/conflict/source/ownership/explicit destructive-intent gates and
      independent completed/partial/uncertain effects. Successor recovery and index-sync failure
      never replay media mutations or rewrite historical plans/results/pins.
- [ ] AC6 — Discovery is metadata-only/no Provider/no FileIndex calls; discovery, reads and
      analysis/Preview perform zero media mutation or execution-authority issuance. Only the
      existing OrganizerExecutor mutates explicitly reviewed items. Web/API agree; no new
      processing engine, queue, Scheduler, supervisor or parallel lifecycle is introduced.
- [ ] AC7 — Actual prior file-only/pinned/historical work remains compatible through restart
      and any additive schema migration. T4 focused/integration/full regression and all assigned
      safety/quality/packaging/migration/native-browser gates pass with retained raw evidence,
      skips/unavailable reported honestly and no weakened assertions/test removal/hidden retry.
      Checkpoint contains only the complete RO-6 boundary and preserves frozen/private/user files.

## Required Tests

### Development and correction feedback

Start with new discovery/scope/paging/stability/persistence/Worker/API tests and directly affected
existing modules. Extend appropriate committed modules or add `tests.test_files_organize_discovery`
(and split by coherent layer if needed); record the actual names in the checkpoint. Use controlled
clocks and temporary Local/SQLite plus supported SMB/OpenList/S3-prefix fakes/local servers.
Required case families are Scope 1–7 and AC1–7, including two legal simultaneous workers, claim
loss/restart, old/new Active pins, stable-size resets, 100/101 limits, independent read failures,
malicious paths/cursors, frozen-list changes, unchanged historical effects and mutation/Provider/
FileIndex spies. Fakes retain all current production capabilities; do not invent reachability by
removing an adapter capability or mixing unsupported runtime versions.

Root affected regressions:

```bash
.venv/bin/python scripts/check_governance.py
.venv/bin/python -m unittest tests.test_scanner tests.test_storage_browser tests.test_v2_manual_organize tests.test_manual_organize_intent tests.test_manual_organize_preview tests.test_manual_organize_execution tests.test_processing_worker_readiness tests.test_operations_run_inventory tests.test_operations_workspace tests.test_operations_run_detail tests.test_migration_rehearsal tests.test_direct_file_operations
```

Web: run changed/new discovery model/component/Operations tests first, then affected Files/manual
Organize/Operations tests and their focused browser specs. Use current built assets. Resolve known
blockers before full gates; the full checkpoint selections below include these existing cases.

### Final checkpoint gates

T4 is required because this Task changes source admission, immutable pins, Worker concurrency,
persistence and the execution handoff. Final candidate runs include new discovery tests through
full discovery below; no older development run on different source can substitute.

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
git diff --check
```

Audit production source/dependencies for forbidden FFmpeg/FFprobe runtime dependencies and the
exact staged manifest for private configuration/secrets/user/frozen files. Use one current wheel
for the wheel smoke command, identifying its hash; don't pass stale additional wheels.

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

Add one coherent committed real-Python native folder/mixed-selection acceptance and its isolated
production-Docker invocation, for example:

```bash
.venv/bin/python scripts/files_organize_discovery_browser_proof.py
.venv/bin/python scripts/docker_files_organize_discovery_browser_proof.py
.venv/bin/python scripts/files_toolbar_browser_proof.py
.venv/bin/python scripts/docker_files_toolbar_browser_proof.py
```

Record justified equivalent names/configurations before submission. The new proofs must use real
Python APIs, SQLite, current Worker and current built Chromium assets for folder/file/multiple/
mixed selections in list/grid and Operations return, success/partial/readiness/limit/stability/
unknown-admission recovery, old-pin isolation, frozen lists, cooperative control/restart and exact
confirmed per-item execution. Use temporary synthetic media and fake/local Metadata services with
actual production capabilities. Docker uses isolated project/ports/volumes and daemon-visible temp
binds (here `TMPDIR=/run/mf-docker-tmp`), proves served artifact/source identity and actual Worker
pickup; preserve the live deployment. Extend upgrade/restart rehearsal as needed to cover real
prior manual intents/previews/results/pins and new discovery persistence, rather than treating a
generic schema smoke or a fabricated newer-format document as compatibility proof. RO-5 proofs
retain both-route/four-viewport geometry and the corrected complete-name disclosure.

### B independent verification

B inspects Task Base..Head and reproduces a real Python/SQLite/Worker/Web folder plus explicit
child/file mixed selection through deduplicated discovery, preserved path-context choices, exact
Preview and separately confirmed execution. Independently exercise a stable-size wait/changed
observation, partial subtree failure with explicit reviewed subset, 101/budget refusal, pause/
restart/continue and unknown-admission readback. Check pinned context across activation, manifest
immutability after adding/changing sources, stale-owner rejection and completed/uncertain effect
non-replay using legal current assembly. Inspect Docker/migration served identities, raw logs and
screenshots; gates may use matching verifiable evidence under the workflow, while missing or
contradicted evidence requires fresh affected execution. No future/degraded-adapter hypothesis
alone blocks this Task.

### Evidence and rerun rules

Keep a secret-free index, raw original logs, receipts, screenshots/measurements and migration/
restart fixtures under `.git/validation-evidence/<tested-full-sha>/task44-6/<run-id>/` or accessible
CI artifacts through A Final Review. Record source/dirty/submitted identity, exact commands/cwd/
environment/dependency/configuration/fixtures, normal selection/workers/retries/timeouts, built
JS/CSS/image/wheel digests, exits/counts/durations, first failures and every repeat. Save visual
state and raw-path/no-side-effect/authority evidence outside `docs/pics`; `/tmp` alone and prose
PASS labels are insufficient. Do not run suites sharing `web/test-results` concurrently. Changed
runtime/tests/harness/dependency/config/artifacts require fresh affected gates; the T4 final
candidate still requires every assigned checkpoint gate. A report-only successor requires proven
unchanged inputs and fresh checks consuming the report (governance/release policy).

## Non-goals

- Work outside RO-6 or additions to the Slice Contract; A-owned closure/reconciliation/RESCOPE.
- MediaLibrary Organize, whole-library/root Organize, automatic intent splitting or raising 100
  primary items; new queues/Schedulers/supervisors or a second processing/rule/attachment engine.
- Replacing exact media Preview/execution identity with RO-1 optional-fingerprint direct-command
  rules; automatic directory Move, cleanup, overwrite/delete permission or uncertain-effect replay.
- FileIndex-driven source membership/stability, full-media hashing during discovery, new provider
  operations, browser Upload/Download, metadata-score redesign or unrelated Rules/shell styling.
- Frozen Slice 43 resumption, production services/media/credentials, live deployment or Git push.
- A separate Task for a field/test/wording/optional proof, or the next Slice.

## Developer Completion Report

### Changed Files

Backend (Python) — correction round 1
- `mediaflow/domain/media_discovery.py` — `DiscoveryIncompleteReason.SAFETY_DEPTH_LIMIT`, the
  `BUDGET_LIMITED_REASONS` boundary (budget/safety/cursor exhaustion vs. ordinary read
  failure) with `discovery_budget_limited()`, and the canonical `discovery_scope_signature()`
  used by actor/scope/pin-bound admission reconciliation.
- `mediaflow/application/media_discovery.py` — the safety-depth cutoff below each selected
  folder is now a truthful incomplete outcome (truncated finding + `safety_depth_limit`)
  instead of a silent `configured_depth_excluded` continue; `finalize` refuses every
  budget-limited walk with `discovery_budget_limited`; `admit` reconciles an identical open
  actor/scope/pin submission to its durable record (terminal records are never reopened —
  the same scope afterwards is deliberate successor work in a new record).
- `mediaflow/interfaces/service_api.py` — the finalize action is not advertised (and carries
  a bounded `refusal`) for budget-limited walks; the native next action names the narrowing
  recovery; discovery runs carry the `整理发现` label in the unified run inventory and its
  overview documents.
- `mediaflow/infrastructure/sqlite_runtime.py` — the run-inventory population unions the
  `media_discoveries` rows (one `discovery` run kind, honest status derivation, bounded
  library-identity scope evidence, no fabricated Task-item counts) so an admitted discovery
  is visible and recoverable through existing Operations readback.
- `mediaflow/domain/operations_run.py` — `DISCOVERY_COMMAND_LABEL` next to the command-label
  map (a discovery is not a Task command family).

Web (TypeScript/React) — correction round 1
- `web/src/entities/operations/discovery.ts` (+ test) — bounded `refusal` on advertised
  actions; the list projection's omitted `sources` no longer fails normalization.
- `web/src/entities/operations/run.ts` — a run kind whose bounded label comes from its own
  durable record (the discovery stage) may carry `recognizedCommand` with a null `command`.
- `web/src/features/operations/OrganizeDiscoveryPage.tsx` — the budget/safety refusal is
  explained natively (banner + finalize error path), with the reason label map covering the
  new/incomplete reasons.
- `web/src/features/library/StorageFilesPage.tsx` — a lost/failed discovery admission is an
  honest unknown state; the page reconciles the same scope through the bounded readback
  before any resubmission and never promises "no work was created".
- `web/src/features/operations/discoveries-query.ts` (new) + `OperationsLanding.tsx` — the
  principal-scoped discovery readback section with native entry links, so recovery locates
  the original admission without raw identifiers.
- `web/src/shared/navigation/destination-model.ts` (+ test) — the discovery destination and
  its bounded Files/Operations return context join the shared route/auth continuation model.
- `web/src/shared/api/api-client.ts` — `fetchOrganizeDiscoveries` (bounded list read) and the
  refusal field in the discovery action model.
- `web/src/shared/ui/styles.css` — the readback list layout.
- `web/tests/fake-server.mjs` — reconciliation, the refusal field, the discovery list route
  and a `discoveryLimit` fixture that mirrors the real budget-limited contract.
- `web/tests/e2e/library-files.spec.ts` — three new browser cases: budget-limited finalize
  refusal with narrowing recovery, reload/reconnect to the same durable discovery with its
  return context, and open-scope reconciliation to one durable record.

Tests / proofs — correction round 1
- `tests/test_media_discovery.py` — the vacuous 101-limit assertion replaced with the real
  unavailable-action + refused-finalize checks (retaining the 100-item success); a new
  default-budget safety-depth case (direct source found, deep subtree truncated and
  explained, finalize refused); the reconciliation/successor-work case replacing the
  duplicate-record expectation.
- `scripts/files_organize_discovery_browser_proof.py` — four selections plus the 101 budget
  refusal, the safety-depth truthful outcome, actor/scope/pin reconciliation (open reuse +
  terminal successor) and the unified Operations readback (list + run rows + overview).
- `scripts/docker_files_organize_discovery_browser_proof.py` — the same corrected journeys
  against the production image, plus fresh-image identity verification.

### Implemented

Correction round 1 addresses exactly the four B blockers and their direct root causes:

1. **A budget-limited walk can never become executable work.** The domain now separates
   budget/safety/cursor exhaustion (`BUDGET_LIMITED_REASONS`) from an ordinary read-failure
   subset. `finalize` refuses a budget-limited discovery durably (`discovery_budget_limited`,
   HTTP 409), the API does not advertise the action and publishes the bounded refusal, the
   native next action is the narrowing recovery, and the page explains that the recorded
   findings are a truncated prefix — never an executable subset. An ordinary read-failure
   subset keeps its explicit-review path unchanged.
2. **The safety depth is truthful.** The Task's own 32-level bound is measured below each
   selected folder and produces an honest `partial_success` with
   `incompleteReason=safety_depth_limit` and a bounded truncated finding, separate from the
   configured library-root depth exclusion. A truncated scope cannot finalize.
3. **A lost admission response reconciles instead of duplicating.** Admission matches an
   identical open submission by actor + canonical deduplicated scope signature + the exact
   admitted configuration pin and returns the original durable record. The Files page treats
   a lost/5xx/malformed response as an honest unknown state, reconciles through the bounded
   readback, and only admits a new discovery when no durable record for that exact scope
   exists. The Operations task center publishes every admitted discovery through the unified
   run inventory (new `discovery` run kind, honest derived status, `整理发现` label) and a
   principal-scoped readback section with native entry links — recovery without raw tokens
   or duplicate work. A terminal record is never reopened; the same scope afterwards is
   deliberate successor work in a new record.
4. **Refresh/reconnect keeps the admitted discovery.** The discovery page is a registered
   child destination with `dynamicPrefix`, and its bounded Files/Operations return contexts
   join the authentication-continuation allowlist. A fresh deep entry, a browser refresh and
   a reconnect continue the same durable discovery — never the Dashboard — and admission of
   new work is never replayed by the continuation.

### Tests and Results

All commands from `/root/mediaflow` (Web commands from `web/`); the tested candidate is the
committed correction checkpoint `71d9aa1a08655fccda247e2f99594737daa19e30`; raw evidence
index, proof matrices and screenshots under
`.git/validation-evidence/71d9aa1a08655fccda247e2f99594737daa19e30/task44-6-correction/`.

Python (repository root)
- `python scripts/check_governance.py` — **PASS**.
- `python -m unittest discover -s tests` — **PASS**, 2350 tests, 7 skipped (the pre-existing
  external-service skips; no test deleted, skipped or weakened).
- `ruff format --check .` / `ruff check .` — **PASS** (357 files).
- `python -m compileall -q mediaflow tests scripts` — **PASS**.
- `python -m pip check` — **PASS**.
- `mediaflow --config config/strategy.example.json config validate` and the phase-13.2
  example — **PASS**.
- `python -m pip wheel . --no-deps -w dist` — **PASS**; wheel sha256 `c9b280de…`; then
  `scripts/wheel_smoke_test.py dist/mediaflow-2.0.0.dev0-py3-none-any.whl` — **PASS**.
- `git diff --check` — **PASS**.

Web (`web/`)
- `npm run typecheck` — **PASS**; `npm run lint` / `format:check` — **PASS**; `npm run build`
  — **PASS** (index `ce9351ee…`, JS `25f90668…`, CSS `abd3206d…`).
- `npm run test -- --run` — **PASS**, 72 files / 1083 tests.
- `npm run test:e2e` (default suite) — **PASS**, 246 tests (the three new discovery cases
  included).
- `npm run test:e2e -- --config=playwright.python.config.ts
  tests/e2e/operations-inventory.python.spec.ts` — **PASS**, 21 tests.
- `npm run test:e2e -- --config=playwright.direct-files.python.config.ts
  tests/e2e/direct-files.python.spec.ts` — **PASS**, 10 tests.

Real-Python acceptance (real API + real SQLite + real Chromium on the built artifact)
- `python scripts/files_organize_discovery_browser_proof.py` — **PASS**. The four selections
  reproduce their earlier results; the 101-source scope stops at `primary_limit` with 100
  sources, finalize is neither advertised nor accepted (`discovery_budget_limited`) and no
  intent item is created; the safety-depth scope returns the direct source plus an honest
  `safety_depth_limit` truncation and refuses finalize; an identical open scope reconciles
  to its durable record and a terminal record admits fresh successor work; the discovery
  list and the unified run inventory (rows + overview with `整理发现`) publish every admitted
  discovery. 8 browser passes; the only non-read requests are the bounded discovery
  admissions; Active revision/digest/activation count and executable Organize Task count
  unchanged.
- `python scripts/files_toolbar_browser_proof.py` — **PASS**, 22 passes / 48 screenshots;
  served index `ce9351ee…` identical to the local candidate.

Isolated Docker acceptance (production image `mediaflow:task44-6-d71`, built by
`git archive HEAD` of the committed checkpoint, isolated project/ports/volumes,
`TMPDIR=/run/mf-docker-tmp`)
- `python scripts/docker_files_organize_discovery_browser_proof.py --image
  mediaflow:task44-6-d71` — **PASS**. The four selections against the assets the production
  image serves, plus the budget refusal, the safety-depth truthful outcome, open-scope
  reconciliation and the unified run-inventory readback.
- `python scripts/docker_files_toolbar_browser_proof.py --image mediaflow:task44-6-d71` —
  **PASS**, 22 passes; the served index equals the local candidate.
- `python scripts/docker_health_smoke_test.py --image mediaflow:task44-6-d71` — **PASS**.
- `python scripts/docker_release_security_smoke_test.py --image mediaflow:task44-6-d71` —
  **PASS**.
- `python scripts/docker_upgrade_recovery_smoke_test.py` — **PASS** (per-run fresh images;
  genuine schema 38 → 45 upgrade with `CURRENT_SCHEMA = 45` verified).

First failures and repeats (retained, not hidden)
- The first full suite after the domain change failed the old duplicate-record expectation;
  it was updated to the reconciled semantics (open scope reused, terminal scope = successor
  work) and the suite passed.
- The real-Python proof first compared reconciliation against an already-terminal record; the
  proof's own ordering was corrected and the rerun passed.
- The proof's Operations readback first failed because the served `dist` bundle predated the
  `run.ts` normalizer change; the artifact was rebuilt and every browser gate rerun against
  the fresh build.
- A session shell exported `NODE_ENV=production`, which made direct `npx vitest` runs resolve
  the production React build (no `act`) and fail 23 *unchanged* feature test files. The same
  failure reproduces on a stashed clean tree at HEAD, so it is an environment property, not a
  product regression; every recorded gate uses the package script's own `NODE_ENV=test`.
- The Docker toolbar proof first reused a stale cached image (served index differed); the
  cache was deleted and the image rebuilt from the committed HEAD, then PASS.
- The first Docker runs under `/tmp` failed with `bind source path does not exist`; per the
  Task's Docker isolation plan they were rerun with `TMPDIR=/run/mf-docker-tmp` and passed.

### Decisions

- **Budget exhaustion is a distinct durable boundary, not a read failure.** A frozen set of
  incomplete reasons is the single source of truth for backend refusal, action advertisement
  and Web copy, so an exhausted walk can never drift back into an executable prefix.
- **The safety bound is per selected folder and honest.** Measuring the Task's own depth
  below each selected folder keeps configured library-root semantics separate; the cutoff is
  a truncated finding with its own reason, never a `configured_*` exclusion.
- **Reconciliation is bound to actor + scope signature + pin.** Only an *open* record with
  the exact same actor, canonical deduplicated scope and immutable Active pin is reused; a
  terminal record is never reopened, so deliberate successor work stays explicit.
- **Operations readback through the existing inventory.** The discovery joins the unified
  run population as its own run kind with honest derived status and a kind label, rather
  than a second inventory or queue.
- **The discovery route joins the continuation model.** Deep-link recovery is the same
  bounded allowlist mechanism every other journey page already uses; no new auth surface.

### Remaining In-Slice Work

- B still owns the all-Required-Outcome recheck and any further Task inside Slice 44.
- The discovery list read remains principal-scoped and bounded to 50; a dedicated paged
  history surface was not part of this Task.
- Only the Local Storage adapter was exercised end-to-end; the shared pure filters and the
  Storage-port-only walk are provider-neutral, but SMB/OpenList/S3 folder discovery was not
  run against a real remote provider.

### Risks / Deviations

- **`NODE_ENV` environment note.** A production `NODE_ENV` in the operator shell makes
  `vitest` resolve the production React build and fail unchanged component tests; the
  package script pins `NODE_ENV=test` and every recorded gate used it. Disclosed as an
  environment property; no assertion was changed and no test was excluded.
- **Docker images are built from committed trees only.** The candidate gates ran after the
  correction commit so `git archive HEAD` includes the fix; a stale cached image was deleted
  and rebuilt rather than reused.
- **`CURRENT_SCHEMA` was already stale at the Task Base** (39 vs. runtime 44); it is now 45
  with the schema-44 → 45 upgrade test, as recorded in the first submission.
- **Version-pinned test assertions** were updated to 45 because schema 45 is an intentional
  additive change; no assertion was weakened or removed.
- **ResourceLibrary stability/include/exclude policy is not configurable through the managed
  document** (pre-existing configuration-surface gap, disclosed in the first submission;
  unchanged by this correction).
- **Unrelated untracked files preserved.** Four untracked screenshots under `docs/pics/`
  predate this Task and were left untouched; no stash, reset, restore, checkout or clean was
  used against them.

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: 71d9aa1a08655fccda247e2f99594737daa19e30
```
## B Independent Review Evidence — 2026-10-09

Reviewed actual Task Base `001bae34769c718033f147873ab16cc22630e484` through
`4f70ba49dd170ee32a462ee8bc38aa871fe65bb2`, including Developer's executable checkpoint
`c1c2340d3d6584994f4ec426230bce363fadd96c`. The successor changes only TASK.md.
The header remained PLANNED, but the latest Developer Checkpoint requested READY FOR B REVIEW;
this review resolves that checkpoint and leaves the same Task in its correction loop.

Independent evidence, reproducible probe and original receipts/logs/screenshots:
`.git/validation-evidence/4f70ba49dd170ee32a462ee8bc38aa871fe65bb2/b44-6-review/`.
Run `.venv/bin/python
.git/validation-evidence/4f70ba49dd170ee32a462ee8bc38aa871fe65bb2/b44-6-review/production-boundary-probe-v7.py`
from the repository root after the current Web build. The completed probe exits 0 as a diagnostic;
it records product refusals/missing refusals and is not an acceptance PASS. Its `repeat-v7/`
contains actual API responses, durable actor/scope/pin-bound rows and inspected screenshots.
The fixture uses the actual managed configuration, real Local Storage/SQLite, production CLI API
and resident Worker pickup, current built Chromium assets and synthetic temporary media. The
response-loss case forwards the real admission, then drops only its browser response; it does
not remove a production Storage capability, invent an adapter or use mixed runtime versions.

Independent checks: focused discovery/Scanner/persistence/release-policy modules 82 PASS;
Web production build, governance and Base..Head diff check PASS, with raw `review-receipts.json`
and logs. No pre-existing failure exclusion is claimed. B stops on the reproducible P1 blockers
below, before complete native Preview/execution, remaining full Python/Web/E2E, real-Python
Operations/DirectFiles, toolbar, Docker/security/wheel/migration gates. Developer's reported totals
are not certified by this rejecting review; the corrected T4 candidate still needs every assigned
gate and verifiable raw evidence. The submitted proof currently demonstrates discovery/admission,
control and intent linkage, rather than the required complete confirmed-execution/recovery journey.

All earlier diagnostic scripts/logs remain: the first helper used wrong SQLite column names;
intermediate helpers incorrectly expected a connection field or loaded data on the newly discovered
unsupported reconnection route, and one used a fetch Response status as a function. The final
probe observes the actual Not connected state, follows its native entry link and records the
wrong Dashboard return instead. These helper failures are not counted as failed project gates.

No existing test was deleted. Exact schema assertions and the pre-RO-6 directory eligibility
expectation were updated for the selected behavior; the new 101-item test contains a vacuous
assertion documented in blocker 1. Slice/AGENTS/Roadmap/configuration/dependency files are unchanged
in this Task diff. No real credential/private configuration or unrelated user asset is included;
config/alist.json remains ignored/untracked/unstaged, and four untracked user images are untouched.
This is B correction round 1; Task ID/Base/Goal/Scope/acceptance/test plan remain unchanged.

## B Review Result

```text
Reviewed: 001bae34769c718033f147873ab16cc22630e484..4f70ba49dd170ee32a462ee8bc38aa871fe65bb2
Decision: FIX REQUIRED
Slice Required Outcomes all satisfied: NO
Next: SAME TASK FIX LOOP
```

- **P1 — Exceeded discovery budgets still admit a first-N ordinary Organize intent
  (AC2; Scope 2; Slice RO-6 / AC29).** With the default legal production budgets and 101 ordinary
  Local MKV files under `mass`, the actual Worker produces `partial_success`, 100 sources and
  `incompleteReason=primary_limit`. Its API advertises finalize as available; POST finalize with
  the actual version returns 201 and creates an open 100-item manual intent whose next action
  is `continue to an exact zero-mutation Preview`. `MediaDiscoveryService.finalize/_finalize`
  accepts any PARTIAL_SUCCESS without checking budget exhaustion, while `_over_primary_limit`
  drops the overflow source. This admits the truncated prefix rather than requiring the operator
  to narrow the oversized scope; no execution is claimed by this reproduction. Evidence:
  `repeat-v7/production-boundary-results.json` (`primary-limit`, including intent readback) and
  `production-boundary-probe-v7.log`. Refuse budget/safety/cursor-limited finalization in backend
  and Web, preserve the narrowing action, and distinguish ordinary read-failure subsets from
  exceeded budgets. Replace the always-passing assertion at `tests/test_media_discovery.py:753`
  (`assertFalse(available is False and False)`) with actual unavailable-action and rejected-finalize
  checks, retaining the existing 100-item success and other assertions.

- **P1 — Safety-depth truncation claims complete discovery and offers normal finalization
  (AC2–3; Scope 2–3; Slice RO-6 / AC29).** With pinned configured `maxDepth=null`, select legal
  Local folder `deep`, containing one direct MKV and another below 33 descendant directories.
  The safety cutoff in `mediaflow/application/media_discovery.py:705–709` silently omits the
  deep subtree, labels it `configured_depth_exceeded`, then returns `completed`,
  `incomplete=false`, one source, finalize available and POST finalize 201. The operator is told
  the selected scope was fully traversed although eligible media was never reached. Evidence:
  `repeat-v7/production-boundary-results.json` (`safety-depth`) and the completed probe log.
  Measure the Task's safety depth below each selected folder, keep configured library-root depth
  semantics separate, and publish a truthful safety-limit/incomplete outcome that requires native
  scope narrowing and cannot finalize a truncated prefix. Add real Local/default-budget coverage.

- **P1 — Lost admission response causes duplicate discoveries and leaves no native Operations
  recovery (AC1/AC4; Scope 5/7; Slice RO-6 / AC30 and Required Surfaces).** In the current Files
  page, select `电影` and click batch Organize. Forward its real POST to completion (202), then
  drop only the response. Web says `存储或服务暂时不可用，请稍后重试；不会创建任何任务。` despite
  durable admission. Following that instruction and clicking again returns another 202 and a
  distinct discovery ID; SQLite contains both queued records with the identical actor, scope
  and admitted pin. No reconciliation read occurs before resubmission. Both discoveries are
  absent from the real Operations run inventory (`GET /api/v1/operations/runs`: 200, total 0,
  items []); the native center displays no admitted runs, so the lost first discovery cannot be
  found/continued there. Evidence: `repeat-v7/browser-evidence.json`, durable rows/inventory in
  `production-boundary-results.json`, `unknown-admission-error.png`, `operations-center.png` and
  API log. Add actor/scope/pin-bound admission identity and unknown-outcome reconciliation, retain
  an honest unknown state instead of promising no work, and expose durable discoveries through
  existing Operations readback/control so recovery locates the original admission without raw
  identifiers or duplicate work. Keep deliberate successor work distinct.

- **P1 — Refresh/reconnect loses the admitted discovery and Files return context
  (AC1/AC4; Scope 1/5; Slice RO-6 / AC27/30).** Refresh the successfully admitted native discovery
  URL carrying `returnTo=files&returnResourceLibraryId=source`. Memory-only auth correctly clears,
  but the new discovery route is absent from `shared/navigation/destination-model.ts` and its
  return-search allowlist. The page stays Not connected; following its actual `Go to the V2 entry`
  link and reconnecting returns to `/ui-v2/dashboard` rather than that durable discovery.
  The same discovery remains readable through its authenticated API (200). Evidence:
  `repeat-v7/browser-evidence.json.refreshRecovery`, `discovery-reload.png` and
  `discovery-reconnect-dashboard.png`. Register the discovery destination and safe Files/Operations
  return context in the shared route/auth continuation model; verify fresh deep entry, browser
  refresh and rejected-token reconnection return to the same discovery without admitting work.
