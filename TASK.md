# Task 44.9 — Complete ordinary folder Organize with safe discovery restart

This Task follows [the development workflow](docs/development-workflow.md) and
[Task/TEMPLATE.md](Task/TEMPLATE.md), within the checkpointed amended [Slice 44](SLICE.md).

```text
Task ID: 44.9
Parent Slice: 44
Status: READY FOR B REVIEW
Task Base: ab94ce53189b5a9f16e7614cd011480a42d91e79
Difficulty: High
Test Level: T4
Planner: A substituting for B under explicit user authorization on 2026-10-11
Reviewer: B — independent Task Reviewer
Contract Checkpoint: 7e96ebf314e4eab22a72d98028a775f248118138
Plan Revision: 2026-10-11 — legal adjustment after A's user-approved Material Contract Change
```

## Goal

Make ordinary folder/file/mixed-selection organizing correct from native ResourceLibrary Files/
Operations entry through bounded background discovery, truthful findings, exact Preview and
separately confirmed execution. Correct the remaining ordinary defects and offer explicit safe
new discovery when interrupted unfrozen work cannot continue. Discovery has zero media mutation.
This Task implements the amended RO-6 and Slice acceptance 27–32; RO-1 through RO-5 stay intact.

## Why This Task Exists

A's [complete folder audit](docs/reviews/slice-44-folder-organize-audit.md) found eight defect groups
in executable candidate `12fd1b3a75cf76743912b57d1f51d184acb10901`, submitted under Implementation
Head `7e2ab801eaef25b083640813375a49f536ae202f`. No implementation has changed since that review.
The user then authorized reducing exceptional recovery promises and updating both Slice and Task.

### Planning reassessment

Decision: legally adjust the existing PLANNED Task 44.9, rather than continue its superseded plan
or create a new per-defect Task. It has no implementation checkpoint/report or B implementation
review. Preserve its ID and immutable Task Base; the earlier plan remains at
`ef2695af04f8e5165a8606342ef7ba285104af6e:TASK.md`. The committed ACTIVE rescope above was verified
with governance before this plan. It changes Goal/Scope/recovery acceptance with A's explicit
Contract authority; this is not a Developer change or a test-only relaxation.

Guaranteed cross-activation lost-response recovery, precise cursor/unpublished-work continuity
through every race/crash and automatic repair/resumption of all old duplicate/interrupted discovery
are no longer this Task's obligations. They may safely stop or remain unresolved with the native
resolution actions below. Ordinary defects and every safety invariant still require correction.
Useful existing recovery code can stay; do not rewrite it solely to fit a smaller preferred design.

This is one complete Domain → Persistence → Application/Worker → API → Web → Tests unit. Retain
historical Task 44.8 review and repeated-correction evidence. A's substitution covers planning only;
B reviews implementation independently, and A later reviews the full Slice Base..new Head.

## Implementation Scope

1. **Exact ordinary admission and bounded discovery.** Canonicalize exact selected scopes, deduplicate
   parent/child/files and atomically reconcile open actor/library/Storage/pin-bound work beyond recent
   list windows. Keep distinct pins/bindings and deliberate terminal successors distinct. Correct
   directory/page accounting, source confinement and primary limits; do not add a general checkpoint
   framework. Storage calls occur outside SQLite write transactions.
2. **Real policy and attachment behavior.** Existing native managed Web/API Save must validate,
   publish and production-load supported include/exclude/depth/stability settings. Preserve legacy
   defaults, focused edits and exact admitted pins. Direct-selected folders/files and descendants
   share root-relative rules. Use existing attachment association across order/pages so matching
   Trailer videos are not independent primaries; no FileIndex admission or new Extras engine.
3. **Truthful names, failures and waiting.** Align exact supported names/paths through manual identity,
   API and Web, including the legal 179-character filename and 1222-character Local path. Isolate
   item/Storage errors; never leave a failed batch indefinitely queued with failure=null. Read errors
   preserve good findings, mark incomplete scope and require explicit known-subset review. Genuine
   nonzero stability needs actual separated observations; waiting cannot spin, exhaust idle budgets
   or starve other resident commands. Missing evidence waits again or stops truthfully.
4. **Normal controls and simple recovery.** Keep acknowledged Pause/Continue, safe cancellation,
   ownership fencing, durable material refusals and atomic one-intent Finalize. Interrupted unfrozen
   work may stop with preserved state/reason and a native explicit new-discovery action, after the
   old attempt is settled/fenced. Never finalize unsafe/incomplete work as complete. Lost-response
   handling recovers only proved original context; otherwise retain selection, show unresolved state
   and offer native Operations inspection/resolution, without another pin/root or automatic submit.
   Derive readiness from the actual discovery command, liveness and schema compatibility.
5. **Preserved history and exact execution handoff.** Preserve old discoveries and historical
   file-only intents/Previews/results/pins. Unsupported unfinished legacy work may stop with a useful
   native explanation/new-discovery action; do not delete/guess-merge or silently repin it. Necessary
   schema evolution is additive and needs actual migration/reopen proof. Freeze the exact source list
   into the existing manual intent/Preview, retain original recognition path/C identity and execute
   only separately authorized reviewed items under all existing permission/source/conflict gates.

Retain current concrete backend bounds: 100 submitted scopes, 100 true primaries, 10,000 visited
entries, 1,000 distinct directories, 2,000 page fetches, 100 entries per page, safety depth 32 and
600 seconds active work per attempt; preserve existing path/evidence bounds and real configured
policy depth. Waiting time is not active traversal. A new deliberate attempt has visible new state;
controls/restart within the old attempt cannot reset durable budgets or material refusals. No silent
first-N execution, automatic splitting or scope growth is permitted.

Likely affected areas are existing discovery/SQLite/Worker, managed configuration/runtime mapping,
pure filters/attachment association, typed API and ResourceLibrary Files/Operations controls/tests.
Specific fields/helpers/checkpoint granularity remain Developer choices. Preserve frozen Slice 43,
user PNGs, config/alist.json, live deployment/media/services and unrelated pages. Contract/Roadmap/
closure remain A-owned; factual implementation architecture notes must not redefine this target.

## Acceptance Criteria

| Criterion | Required observable result / original audit evidence |
|---|---|
| AC1 — Correct admission | A44-6: concurrent, reordered and overlapping equivalent scopes, including an existing admission beyond the recent-list window, converge on one open actor/library/Storage/pin-bound record. Distinct bindings/pins and deliberate successors remain distinct. Lost response plus later root/pin change recovers the proved original or stays truthfully unresolved with native inspection; no wrong association or automatic duplicate submission. |
| AC2 — Actual configured filters | A44-7: native managed Save validates/publishes and the real loader/Worker consumes exact include/exclude/depth/stability policy. Invalid Save preserves Active/input. Direct selection cannot bypass root-relative exclusions/depth; new activation cannot change old admission. |
| AC3 — Genuine non-busy stability | A44-8: required nonzero age/mtime/size intervals use real source observations. Before eligibility, waiting neither spins/exhausts idle budgets nor prevents other resident work. Eligible sources are re-observed; missing/invalid evidence waits again or stops with a safe next action. Exact cursor/observation continuity across every restart is not required. |
| AC4 — Exact names and partial errors | A44-9/A44-10: legal long/whitespace names/paths survive native detail/list/manual handoff. An isolated failed item is durable and actionable. Gone/denied selected files and subtrees preserve good findings, report incomplete scope and allow only explicit known-subset review; never false complete or an indefinitely queued whole batch with failure=null. |
| AC5 — Bounds and attachments | A44-11/A44-12: pages do not count as new directories; correct units govern the existing traversal budgets. 51 main videos plus 51 matching enabled Trailer attachments yield 51 primaries. Exactly 100 true primaries works; 101/material truncation refuses an executable prefix. Existing attachment suffix/conflict semantics remain. |
| AC6 — Native controls and safe restart | A44-13 and revised acceptance 30: readiness reflects actual discovery command support. Files list/grid and Operations support ordinary folder/file/multiple/mixed journeys and return context, acknowledged Pause/Continue and cancel. A representative unresumable interruption keeps history/findings/reason, fences/settles old work and supports explicit new discovery without media effects. Lost admission has actionable native unresolved-state inspection; API/Web agree. |
| AC7 — Safety and compatibility | Earlier required safety remains: confined deduplicated frozen manifest, monotonic durable material refusal, stale-owner fencing and atomic one-intent Finalize. Actual old-schema history/frozen/file-only work survives reopen; unsupported unfinished discovery may stop truthfully. Source changes stop their item; no repin/new authority/replay of completed, partial or uncertain mutation. C remains C with A policies; discovery calls no content/Provider/mutation ports; only OrganizerExecutor mutates separately confirmed items. |
| AC8 — Validated coherent checkpoint | Current Contract obligations have meaningful regressions/production-path proof and fresh assigned T4 evidence. Retain useful code; no mandatory new request-correlation protocol, per-page continuation framework, universal legacy repair or arbitrary-race no-work-loss guarantee. Report actual PASS/FAIL/SKIP/UNAVAILABLE and preserve private/user/frozen files. No Slice closure is implied. |

Old seamless-recovery assertions may be explicitly revised to current safe-stop/unresolved/native
restart acceptance. Identify their original test IDs, changed expectations and A Contract reason;
retain meaningful no-false-success, no-Finalize, pin/ownership and no-replay assertions. Do not weaken
or remove tests of still-required safety/outcomes. P2/P3 copy, optional proof and cleanup cannot
produce a blocker or another Task by themselves.

## Required Tests

### Development and correction feedback

Convert still-applicable audit scenarios into meaningful regressions before expensive full gates.
Use actual managed publication/loading, authenticated API, temporary Local/SQLite and real Worker
pickup; injected domain policies alone do not establish configured behavior. Separate connections
prove admission/Finalize races; controlled clocks prove stability and waiting. A reduced-directory-
budget multi-page fake/local OpenList case can prove correct accounting without replaying all 1001
historical HTTP pages. Deferred recovery expectations do not need an exhaustive combination matrix.

Repository root:

```bash
.venv/bin/python scripts/check_governance.py
.venv/bin/python -m unittest tests.test_media_discovery tests.test_media_discovery_provider_manifest
.venv/bin/python -m unittest tests.test_runtime_strategy_configuration tests.test_configuration_objects tests.test_configuration_management tests.test_configuration_snapshot tests.test_configuration_package_exchange tests.test_scanner tests.test_attachments
.venv/bin/python -m unittest tests.test_manual_organize_intent tests.test_manual_organize_preview tests.test_manual_organize_execution tests.test_operations_run_inventory tests.test_operations_run_detail tests.test_migration_rehearsal
```

These cover admission/bounds/names/errors/controls/fencing, actual policy/attachment semantics and
existing exact handoff/history. Run changed/new modules too. From web/:

```bash
npm run test -- --run src/entities/operations/discovery.test.ts src/features/operations/OrganizeDiscoveryPage.test.tsx src/features/library/StorageFilesPage.test.tsx src/features/operations/OperationsInventory.test.tsx
```

Add affected native configuration tests. Build/run the existing real-Python native proof for ordinary
selection/return, exact Preview/confirmed temporary execution, long paths, partial read failure,
readiness and simple interrupted/unresolved recovery. Include one genuine elapsed nonzero stability
interval through published policy, alongside deterministic changed-source/negative checks. Domain
race tests may stay deterministic; do not require fragile browser timing or production services.

```bash
npm --prefix web run build
.venv/bin/python scripts/files_organize_discovery_browser_proof.py
```

### Final checkpoint gates

High/T4 remains appropriate for managed Active configuration, concurrent admission, SQLite changes
and core execution handoff. The smaller recovery promise does not lower those risks. Full suites
can cover focused cases without a redundant final rerun; identify matching coverage. Fresh complete
gates are required for the submitted implementation, not for this A Contract/planning checkpoint.

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
.venv/bin/python -m pip wheel . --no-deps -w dist/task44-9
.venv/bin/python scripts/wheel_smoke_test.py dist/task44-9/mediaflow-*.whl
.venv/bin/python scripts/docker_release_security_smoke_test.py
.venv/bin/python scripts/docker_upgrade_recovery_smoke_test.py
.venv/bin/python scripts/files_organize_discovery_browser_proof.py
.venv/bin/python scripts/docker_files_organize_discovery_browser_proof.py
git diff --check
```

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

Build before real-Python/Docker browser checks. Git-archive Docker proofs must test the actual
committed candidate, with source/served-asset/image hashes. Smoke-test one exact wheel and retain
its digest. Use isolated projects/ports/volumes and daemon-visible binds where required; no live
deployment or production media/services. Audit dependencies for FFmpeg/FFprobe and staged files
for secrets/private/frozen/unrelated content.

If persistence evolves, use an actual prior schema-45 database seeded by the old implementation:
a representative interrupted discovery, duplicate-history fixture and frozen/file-only intents/
Previews/results/pins. Verify preserved history and authority after upgrade/reopen; unfinished
unsupported discoveries may stop with native new-discovery recovery. No automatic resumption of
every old combination is required, and no deletion/guess-merge/repinning is allowed. Extend affected
migration tests; retain still-required assertions. Preserve RO-1/MediaLibrary isolation, RO-3 targets
and RO-5 layout. Report actual failures and external SKIP/UNAVAILABLE with reasons.

### B independent verification

Inspect Task Base..submitted Head against this amended Contract and the original audit. Independently
reproduce atomic equivalent-scope admission; real configured filtering/nonzero stability without
busy pickup; legal long names and isolated missing/denied-file partial review; multi-page directory
accounting; 51 main/Trailer association; discovery-command readiness. Inspect real built-Web simple
interruption/new-discovery and response-loss/changed-root handling: proved original or truthful
unresolved inspection is acceptable; wrong-pin guessing and automatic submit are not.

Recheck normal controls, stale-owner refusal, material-limit persistence, atomic Finalize and normal
separately confirmed temporary execution. Other gates may use verified matching Developer/CI
provenance under workflow reuse rules; missing/incompatible/contradicted evidence needs affected
fresh runs. A does not issue B PASS. After B PASS reevaluate all Slice outcomes, run the current
Slice-final gate and submit a fresh Closure Packet/READY FOR A REVIEW; preserve rejection/rescope
history and immutable Base. Stop creating Tasks when current outcomes are satisfied.

### Evidence and rerun rules

Retain one indexed candidate/run under
`.git/validation-evidence/<tested-full-sha>/task44-9/<run-id>/` or accessible CI through A's decision.
Record source/dirty-input manifest, commands/cwd/runtime/locks/configuration/Worker/selection/clock,
artifact hashes, real results/durations/skips/unavailable, readable logs/images and first failures.
Changed executable/test/harness/configuration/served inputs need fresh affected evidence and final
T4 gates. Report-only successors need input matching/document checks. Old audit PASS/negative
receipts are historical evidence, not acceptance of new implementation or deferred recovery.

## Non-goals

- Guaranteed seamless lost-response recovery through activation changes, precise cursor/unpublished-
  work continuation through arbitrary races/crashes, or automatic repair/resumption of every legacy
  duplicate/interrupted discovery. Do not add a framework to obtain these deferred guarantees.
- New queue/Scheduler/supervisor/Provider/Extras engine, FileIndex-based admission, content hashing,
  alternate execution pipeline, unbounded work, automatic splitting or MediaLibrary Organize.
- Unrelated configuration/Rules/direct-file/layout redesign, optional P2/P3 cleanup, Contract/Base/
  Deferred changes, historical review rewriting, Slice closure, deployment or push.

## Developer Completion Report

### Fix loop 2 for B's FIX REQUIRED (2026-10-12)

B rejected candidate `0d9bb21` with two P1 defects. Both were incomplete reuse of semantics that
already exist in the product, so this loop corrects them inside the same Task 44.9: no new Task, no
rescope, no Slice-boundary change, no new recovery framework. Task ID/Base/Goal/Scope and every
assigned acceptance criterion are unchanged.

```text
Candidate: 74126160d7f8a6b08bac293e9262dbf04ef5e790
Previous reviewed candidate: 0d9bb218432eb05bab4ae4bb1326628abcb6a6ff
Task Base: ab94ce53189b5a9f16e7614cd011480a42d91e79 (verified ancestor of HEAD)
Branch: slice/44-page-improvements
Evidence: .git/validation-evidence/74126160d7f8a6b08bac293e9262dbf04ef5e790/task44-9/run-1/
```

### Changed Files (this fix loop)

| File | Change |
| --- | --- |
| `mediaflow/domain/media_discovery.py` | New optional `admission_request_id` on `MediaDiscovery`, validated as a canonical UUID, published in `document()` and restored by `from_document()` |
| `mediaflow/infrastructure/sqlite_runtime.py` | Additive `admission_request_id` column plus `media_discoveries_request` index (no schema-version bump), wired through the column list, insert, loader and a new actor-bound `find_media_discovery_by_request_id` |
| `mediaflow/application/media_discovery.py` | `admit()` accepts and validates the optional client request identity and reconciles an exact retry to the record that identity created; `_demote_attachments` is now a fixpoint over the currently admitted set, with the production association computed once per directory by the new `_attachment_owners` |
| `mediaflow/interfaces/service_api.py` | The admission handler accepts the optional `requestId` and echoes `admissionRequestId` in the operator projection |
| `tests/test_media_discovery.py` | Eleven new `A44BReviewCorrections` regressions: mutual/three-member/mixed/Trailer/page-order/stem-chain demotion and the request-identity admission contract |
| `tests/test_task_persistence.py` | The schema-45 upgrade test drops and re-adds the new column/index; the round-trip proves the identity survives and is actor-bound |
| `web/src/shared/api/request-id.ts` (+ `.test.ts`) | New `newRequestId()`/`isRequestId()` helper mirroring the existing Delete request-identity precedent; `null` when the runtime has no random source |
| `web/src/shared/api/api-client.ts` | `submitFilesDiscovery` sends the optional `requestId` and returns the echoed `admissionRequestId` |
| `web/src/entities/operations/discovery.ts` (+ `.test.ts`) | The discovery model publishes a strictly-validated `admissionRequestId` |
| `web/src/features/library/StorageFilesPage.tsx` (+ `.test.tsx`) | The lost-admission readback now recovers only the record carrying this request's own echoed identity; otherwise the honest unresolved state stands |

### Implemented

1. **P1-A — Genuine original-admission proof replaces the rendered pin.**
   The backend resolves the immutable Active pin at admission time, so a pin the page rendered
   earlier cannot prove which admission its POST became: a successor activation legally admits the
   same relative scope under a new pin, and an equivalent older open admission can exist under the
   rendered pin. `StorageFilesPage` now generates its own identity for this exact request *before*
   submitting (`newRequestId()`, mirroring the existing Delete `requestId` precedent), the API
   validates it as a canonical UUID and stores it durably, and the operator projection echoes it.
   The readback recovers a record only when its echoed identity equals this request's own value.
   When that proof is absent the page keeps the honest unresolved state, explains it and points at
   native Operations inspection; it never replays the admission and never navigates to another
   source context. No guaranteed cross-activation recovery protocol was added, exactly as the
   amended Contract allows.
2. **P1-B — Retained-primary-aware attachment demotion.**
   `_demote_attachments` no longer computes owners against the pre-demotion source set. The real
   production `AttachmentDiscovery` association is computed once per directory (the new
   `_attachment_owners`, using `_stem_related` only as a cheap necessary-condition prefilter), then
   resolved to a fixpoint over the currently admitted set: a source is demoted only while an
   admitted primary it attaches to stays admitted. A mutual same-stem group therefore keeps exactly
   one deterministic, page-order-independent primary, while a sidecar of a demoted member (a
   Trailer beside a mutual group, or a longer stem chain) is still demoted instead of being promoted
   to an independent primary. Orphan-Trailer, disabled-Trailer, 51-main/51-associated-Trailer and
   the existing 100/101-primary refusal behavior are unchanged.

### Tests and Results

Every row is a real command run against candidate `7412616`; the original logs are in the evidence
directory. The full Python and Web suites are reported from an isolated run: an earlier attempt ran
them concurrently with the three Docker gates, and two timing-sensitive Python concurrency tests
plus eleven Web tests flaked under that load. Both suites pass cleanly when serialized, and the two
Python failures were independently re-run alone (2 passed) to confirm they are load flakes rather
than product failures.

| Gate | Result |
| --- | --- |
| `python scripts/check_governance.py` | PASS |
| `python -m pytest tests/ -q` | **2415 passed, 7 skipped, 1739 subtests passed** |
| pytest skips | **SKIP / UNAVAILABLE (pre-existing, environment-only):** 2 real SMB/S3 acceptance, 4 isolated SMB/OpenList/S3/Local endurance profiles, 1 OpenList real acceptance — no dedicated external service/profile is present. Unchanged; no product assertion was skipped |
| `cd web && npm run test -- --run` | **1102 passed** (74 files) |
| `ruff format --check .` / `ruff check .` | PASS (361 files) |
| `python -m compileall -q mediaflow tests scripts` | PASS |
| `python -m pip check` | PASS |
| Both `config validate` examples | PASS |
| `pip wheel . --no-deps` + `scripts/wheel_smoke_test.py` | PASS (schema 45) |
| `scripts/files_organize_discovery_browser_proof.py` | PASS — `{"ok":true,"passes":11}` |
| `scripts/docker_release_security_smoke_test.py` | PASS |
| `scripts/docker_upgrade_recovery_smoke_test.py` | PASS |
| `scripts/docker_files_organize_discovery_browser_proof.py` | PASS — `{"ok":true,"passes":7}` |
| `cd web && npm run format:check` / `lint` / `typecheck` / `build` | PASS |
| `cd web && npm run test:e2e` | **246 passed** |
| Real-Python e2e `operations-inventory.python.spec.ts` | **21 passed** |
| Real-Python e2e `direct-files.python.spec.ts` | **10 passed** |
| `git diff --check` | clean |

**B's own rejection probes, re-run against this candidate:**

- `production_probes.py` (B's P1-B evidence) now reports **4 run, 0 failures**: the fourth probe's
  `Film.2001.mkv` + `Film.2001.mp4` case returns `sources=["Movies/Film.2001.mkv"]` with one
  admitted primary instead of the previous empty completed manifest. The orphan-Trailer and
  disabled-Trailer cases still pass and zero mutations are recorded.
- A developer probe reproducing B's exact P1-A precondition — an equivalent older open admission
  already under the rendered pin, plus a successor activation before the page reconciles — drives
  the real built Web, Chromium, subprocess API, actual managed import/validate/activate and SQLite.
  It records one browser POST and proves the page selects neither the stale prior admission nor the
  successor: it keeps the explained unresolved state, replays nothing and creates zero execution
  Tasks (`p1a-fix-receipts.json`, `p1a-fix-durable-receipt.json`, inspected `p1a-fix.png`).

### Decisions

- **Reuse the existing request-identity precedent.** The client-generated UUID, its canonical
  validation and the actor-bound durable lookup mirror the already-shipped Delete `requestId`
  idempotency instead of inventing a second correlation protocol.
- **Durable proof, additive storage.** The identity is an additive nullable column with its own
  index and no schema-version bump, so a prior-schema row stays readable and finishable and simply
  is not reconcilable by request identity — the honest unresolved state, never a guess.
- **One definition of attachment association.** `_attachment_owners` calls the same
  `AttachmentDiscovery` with the same pinned policy the exact Preview consumes; `_stem_related`
  remains only a necessary-condition prefilter and never decides the association.
- **Resolve to a fixpoint, not a single greedy pass.** Owners are recomputed against the surviving
  set until stable, so a sidecar of a demoted member cannot be promoted to an independent primary.
  The association itself is computed once, keeping the resolution bounded.

### Remaining In-Slice Work

Both B P1 defects are corrected. The user-approved deferrals remain deferred and are **not** claimed
as delivered: guaranteed cross-activation lost-response recovery, precise cursor/unpublished-work
continuation through every race or crash, and automatic repair/resumption of every legacy duplicate
or interrupted discovery. Interrupted unfrozen work that cannot be continued still resolves through
the native explicit new-discovery action. B must reevaluate all Slice Required Outcomes; this report
claims no Task PASS and no Slice state.

### Risks / Deviations

- High: managed configuration publication, admission/ownership fencing, shared source identity and
  the discovery manifest are all in scope. Mitigated by the full T4 gate set above, the real Docker
  upgrade/recovery harness and the real built-Web stale-pin probe.
- **Environment, not a product failure:** this Docker daemon cannot see the private `/tmp` tmpfs
  that `tempfile` uses, so the Docker gates fail at `up -d` with `bind source path does not exist`
  under the default `TMPDIR`. They pass with a daemon-visible
  `TMPDIR=/root/mediaflow/.dsh-docker-tmp`; no harness or product code was modified. The
  default-`TMPDIR` failure is reported as `UNAVAILABLE / ENVIRONMENT`, not as PASS.
- **Load-induced flakes, disclosed:** running the two full suites concurrently with the three
  Docker gates produced 2 Python and 11 Web failures in timing-sensitive concurrency tests. Both
  suites pass in an isolated serial run, and the two Python tests pass when re-run alone. No test
  was weakened, skipped or retried to manufacture a green gate.
- The client request identity is generated with the Web Crypto random source. Where a runtime offers
  no such source, no identity is sent and the page keeps the honest unresolved state instead of
  inventing a collision-prone value.

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: 74126160d7f8a6b08bac293e9262dbf04ef5e790
Task Base: ab94ce53189b5a9f16e7614cd011480a42d91e79
Commit: fix(slice44): correct B-review P1 defects in Task 44.9 discovery
Evidence: .git/validation-evidence/74126160d7f8a6b08bac293e9262dbf04ef5e790/task44-9/run-1/
Local commit only; not pushed.
```


## B Review Result

Review date: 2026-10-11. Reviewed the immutable Task Base..corrected executable candidate below.
Workspace Head `b9d38f9e477906595abafe8a137bd4ccc2a48755` differs from executable candidate
`0d9bb218432eb05bab4ae4bb1326628abcb6a6ff` only in `TASK.md`. Production/test/build inputs match.
Independent evidence index:
`.git/validation-evidence/b9d38f9e477906595abafe8a137bd4ccc2a48755/b-review44-9/review-index.json`.

Governance passed. Independent Python discovery/configuration/persistence regression: **59 run,
0 failures, 0 skips**. The two added lost-response Web tests passed; **43 other tests were deselected
by the explicit `-t` filter**, not accepted as full-module coverage. Independent managed-runtime/
Local/SQLite/API probes: **4 run, 3 passed, 1 semantic failure, 0 skips**. Fresh Web build passed.
Real built-Web/Chromium/Python API proofs confirmed the original after-admission activation case
is corrected, but reproduced wrong-record navigation when activation precedes admission. The
negative browser probe exits 0 to confirm reproduction, not product acceptance. Its actual image
was inspected; raw scripts/logs/receipts and asset identities are retained.

The preceding ancestor-exclusion, orphan-Trailer and disabled-Trailer cases now pass. Developer
evidence for `0d9bb21/task44-9/run-1/` now includes original artifacts; inspected full-suite logs
report Python **2411 run / 7 skipped / OK** and Web **1093 passed / 73 files**. These reports do not
prove the two missing behaviors below. The remaining assigned T4 gates were not independently
rerun after proving blockers, under the workflow's early-rejection rule. No Slice Final was run;
the unchanged complete checkpoint plan and matching raw evidence remain required before PASS.

**Global complexity reassessment:** this functionality has exceeded three correction rounds across
Tasks 44.6–44.9 and their fix loops. The reduced Contract remains feasible. The remaining problems
are a proof boundary and loss of attachment ownership, not a need for a larger framework. Rendered
Active state cannot prove a later request's admitted pin; retain the authorized unresolved/native
inspection outcome when proof is absent. Reuse existing attachment semantics while ensuring a
demoted source still has an admitted owner. Keep these corrections in Task 44.9; no separate
per-test/per-defect Task, guaranteed cross-activation correlation framework or B rescope is needed.
Task ID/Base/Goal/Scope/acceptance and the Slice Contract remain unchanged.

```text
Reviewed: ab94ce53189b5a9f16e7614cd011480a42d91e79..0d9bb218432eb05bab4ae4bb1326628abcb6a6ff
Decision: FIX REQUIRED
Slice Required Outcomes all satisfied: NO
Next: SAME TASK FIX LOOP
```

- **P1 — Rendered Active pin is still mistaken for proof of the actual admission
  (Task AC1/AC6/AC7; RO-6 and Slice acceptance 30/31).** Current production reachability: the
  native Files page renders an old valid Active root/pin; an equivalent open admission from an
  earlier click/other tab exists under that pin. Another valid activation changes the root before
  the current POST reaches the API. The API legally admits that POST under the new Active pin.
  No illegal configuration, mixed versions or reduced production port is involved.
  Current user impact: after the response is lost, Files' batch Organize navigates to the prior
  old-root discovery as if it were the current request; the actual new-root request remains separate.
  Contract violation: unknown admission may recover only a proved original actor/binding/pin;
  guessed association is forbidden, and unresolved native inspection is explicitly allowed.
  Actual evidence:
  `.venv/bin/python .git/validation-evidence/b9d38f9e477906595abafe8a137bd4ccc2a48755/b-review44-9/stale_pin_probe.py`
  uses the fresh built Web, Chromium, subprocess API, actual managed import/validate/activate and
  SQLite. It records one browser POST. Actual submitted admission
  `3f491073-210d-4b7d-b518-72ac583fecf6` has pin
  `87610bb1-2c16-4e7c-917e-e021c36935a3`; recovered URL instead selects prior
  `50c47271-2346-402a-90fc-aa4e95efe53f`, pin
  `2c25f40f-e0c7-49c1-ac65-8f2f9503ac8b`. Receipts, durable rows and inspected screenshot
  agree; execution-task count is zero. `StorageFilesPage.tsx:2129` submits only library/paths,
  without making the rendered pin authoritative at admission, while readback at line 2155 uses
  that rendered pin to choose an old record. Severity: P1, because current required recovery
  associates another live source context. **Correction:** require genuine original-admission
  proof before automatic navigation; if unavailable, preserve selection and honest unresolved
  state with native Operations inspection/resolution and no automatic replay. A guaranteed
  cross-activation recovery protocol is not required. Retain the now-passing after-admission
  activation case and cover this before-admission scenario through actual production paths.
- **P1 — Reciprocal attachment demotion silently removes every same-stem video
  (Task AC4/AC5/AC7; RO-6 and Slice acceptance 27–29).** Current production reachability:
  a valid managed, published attachment policy enables the existing `otherSameStem` setting,
  and a Local folder contains `Film.2001.mkv` and `Film.2001.mp4`. The real loader and matcher
  support both files/settings; production capabilities are preserved.
  Current user impact: folder Organize reports completed with no discovered sources, so neither
  video reaches Preview, although its findings call both eligible primaries.
  Contract violation: folder discovery must preserve existing primary/attachment association and
  truthful empty/excluded/partial outcomes; an attachment must not silently remove its only owner.
  Actual evidence:
  `PYTHONPATH=. .venv/bin/python .git/validation-evidence/b9d38f9e477906595abafe8a137bd4ccc2a48755/b-review44-9/production_probes.py`
  publishes/loads the exact managed document and uses authenticated API, SQLite and delegating
  real Local Storage. The fourth probe fails: `status=completed`, `sources=[]`,
  `excludedEntries=0`, two `kind=primary` findings and zero mutation calls.
  `MediaDiscoveryService._demote_attachments` computes owners against the pre-demotion source
  set, then removes both mutual owners; it never checks whether either owner remains admitted.
  Severity: P1, because eligible current-user media disappears from the required journey with
  false completion. **Correction:** demote only with an applicable association to a retained
  admitted primary, or report an ambiguous association truthfully with safe actionable resolution;
  never publish an empty completed manifest by mutually removing valid sources. Reuse the existing
  policy/matcher rather than adding an unrelated attachment engine. Cover same-stem groups and
  page/order behavior while retaining corrected orphan/disabled-Trailer behavior, 51-main/
  51-associated-Trailer coverage and the existing 100/101-primary refusal.

NEXT ACTION: DEVELOPER FIXES CURRENT TASK — SAME TASK FIX LOOP
