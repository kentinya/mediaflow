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

### Fix loop for B's FIX REQUIRED (2026-10-11)

B rejected the previous candidate `d9a9af4` with three P1 defects. All three were incomplete
reuse of semantics that already exist in the product, so this loop corrects them inside the same
Task 44.9, with no new Task, no rescope, no Slice-boundary change and no new recovery framework.
Task ID/Base/Goal/Scope and every assigned acceptance criterion are unchanged.

```text
Candidate: 0d9bb218432eb05bab4ae4bb1326628abcb6a6ff
Previous reviewed candidate: d9a9af4b665a5c524a1b5291438e7590ac4b2854
Task Base: ab94ce53189b5a9f16e7614cd011480a42d91e79 (verified ancestor of HEAD)
Branch: slice/44-page-improvements
Evidence: .git/validation-evidence/0d9bb218432eb05bab4ae4bb1326628abcb6a6ff/task44-9/run-1/
```

### Changed Files (this fix loop)

| File | Change |
| --- | --- |
| `mediaflow/application/scan_filters.py` | New pure `PrunedAncestorReason` + `pruned_ancestor(library, relative_path)`: the shallowest ancestor a library-root walk would prune, reusing the one `excluded` / `_directory_may_match` / configured-depth predicate |
| `mediaflow/application/media_discovery.py` | Direct file and folder admission now refuse a policy-pruned ancestor first; the filename-suffix Trailer shortcut is deleted and replaced by the production `AttachmentDiscovery` association applied per completed directory and once at walk end, before the primary bound |
| `web/src/features/library/StorageFilesPage.tsx` | The lost-admission readback now requires the exact original library, `storageId` and immutable `configurationSnapshotId`; otherwise it keeps the honest unresolved state and points at native Operations inspection instead of navigating to another source context |
| `tests/test_media_discovery.py` | Eight new `A44BReviewCorrections` regressions over the real managed-runtime/Local/SQLite journey |
| `web/src/features/library/StorageFilesPage.test.tsx` | Two Web regressions: wrong-binding readback does not navigate; proved original binding still recovers |

### Implemented

1. **P1-A — Root-relative ancestor policy at every direct-selection entrance.**
   `pruned_ancestor()` walks the ancestors of the selected relative path (index `1..len-1`, i.e.
   every directory *above* the selection) and applies exactly the predicate a walk from the
   ResourceLibrary root applies: `excluded()` for an exclude rule, `_directory_may_match()` for an
   include rule, and the configured `max_depth` check using the parent directory's own depth.
   `_refuse_pruned_ancestor()` maps the reason onto the existing bounded refusal vocabulary
   (`source_excluded` / `source_not_included`) with the pruned ancestor path and a native next
   action. Both `_refuse_unselectable_directory` and `_refuse_unselectable_file` call it first, so
   a descendant click can no longer bypass policy that a parent walk honours. B's own
   `production_probes.py` excluded-ancestor case now returns the required `409` refusal with
   `prunedAncestor: "Blocked"` instead of the previous `202` admission.
2. **P1-B — Real attachment association replaces the filename shortcut.**
   The per-entry `if attachment_policies and self._trailer_candidate(raw.name): continue` shortcut
   is deleted. Every file is now `observe()`-ed through the ordinary filtering/stability path
   first, so an orphan trailer, a trailer under a policy that does not enable trailers, and a
   trailer whose main file is not admitted all keep ordinary primary processing and truthful
   findings. Association happens only where the production `AttachmentDiscovery` under the pinned
   policy actually proves it, using `_stem_related()` purely as a cheap *necessary*-condition
   prefilter so the real matcher is not asked about obviously unrelated names — it never decides
   the association. Demotion is applied when a directory's page walk completes and once more at
   walk end, and the primary bound is evaluated on the resulting true primary set, so a 51-main/
   51-associated-Trailer folder stays 51 primaries and the existing 100/101 refusal is unchanged.
   A final walk-end bound check trims any path that an unrelated safety break could have left
   above the bound, so no code path can publish an over-limit manifest.
3. **P1-C — Lost-response recovery only with proof of the original binding.**
   The mutation now captures the rendered `storageId` and `configurationSnapshotId` at both
   submission sites. The reconciliation read recovers a durable record only when it proves the
   same `resourceLibraryId`, the same `storageId`, the same non-null `configurationSnapshotId`
   and the exact scope set, and the record is still open. Otherwise the page keeps the honest
   unresolved state, tells the operator to inspect the pending discovery in the task center, and
   never navigates to a different source context or resubmits. The amended Contract's smaller
   recovery promise is honoured exactly: unresolved native inspection is acceptable, wrong-pin
   guessing is not.

### Tests and Results

Every row is a real command run against candidate `0d9bb21`; the original logs and the candidate
hashes are in the evidence directory.

| Gate | Result |
| --- | --- |
| `python scripts/check_governance.py` | PASS |
| `python -m unittest discover -s tests` | **2411 run, 7 skipped, 0 failures** |
| `unittest` skips | **SKIP / UNAVAILABLE (pre-existing, environment-only):** 2 real SMB/S3 acceptance, 4 isolated SMB/OpenList/S3/Local endurance profiles, 1 OpenList real acceptance — no dedicated external service/profile is present. Unchanged from the previous candidate; no product assertion was skipped |
| `cd web && npm run test -- --run` | **1093 passed** (73 files) |
| `cd web && npm run build` | PASS (built before the real-Python and Docker browser proofs) |
| `ruff format --check .` / `ruff check .` | PASS (361 files) |
| `python -m compileall -q mediaflow tests scripts` | PASS |
| `python -m pip check` | PASS |
| Both `config validate` examples | PASS |
| `pip wheel . --no-deps` + `scripts/wheel_smoke_test.py` | PASS (schema 45) |
| `scripts/files_organize_discovery_browser_proof.py` | PASS — `{"ok":true,"passes":11}` |
| `scripts/docker_release_security_smoke_test.py` | PASS |
| `scripts/docker_upgrade_recovery_smoke_test.py` | PASS |
| `scripts/docker_files_organize_discovery_browser_proof.py` | PASS — `{"ok":true,"passes":7}` |
| `cd web && npm run format:check` / `lint` / `typecheck` | PASS |
| `cd web && npm run test:e2e` | **246 passed** |
| Real-Python e2e `operations-inventory.python.spec.ts` | **21 passed** |
| Real-Python e2e `direct-files.python.spec.ts` | **10 passed** |
| `git diff --check` | clean |

**B's own rejection probes, re-run against this candidate:**
`production_probes.py` now passes the orphan-trailer and disabled-trailer cases. The
excluded-ancestor case *fails its own assertion* because the probe still asserts the old `202`
admission while the corrected product now returns the required `409` refusal; that divergence is
the correction, not a regression, and the probe is retained unmodified as the rejection reference.
A new real built-Web probe,
`.git/validation-evidence/<candidate>/b-review44-9-fix/wrong_pin_probe.py`, reproduces B's exact
wrong-pin scenario against the real subprocess API, real managed activations and real SQLite: the
admission response is dropped, a successor pin re-admits the same relative folder, and the page
recovers the **original** binding's record (`6f8d16e9…`) and never the successor (`7af1d91f…`),
with exactly one admission and zero execution Tasks.

### Decisions

- **Reuse the existing policy predicate, not a second filter language.** `pruned_ancestor` calls
  the same `excluded`/`_directory_may_match` helpers the Scanner and walk already use, and returns a
  reason the caller maps to its own bounded vocabulary. No new policy meaning was introduced.
- **Reuse the production attachment matcher, not a filename rule.** `_stem_related` is deliberately
  only a necessary-condition prefilter; association itself is decided solely by
  `AttachmentDiscovery` under the pinned policy, so there is still exactly one definition of
  "this sidecar belongs to that main file".
- **Evaluate the primary bound on the true demoted set.** Association is applied per completed
  directory and at walk end before the bound check, so candidate entries that are about to be
  demoted can never trip `primary_limit` and a final trim makes an over-limit publication
  impossible.
- **Prove the binding or stay unresolved.** Recovery matches `storageId` and the immutable
  `configurationSnapshotId` in addition to the library and scope; the amended Contract explicitly
  allows unresolved native inspection, so no guessed navigation and no general recovery framework
  was added.

### Remaining In-Slice Work

The three B P1 defects are corrected. The user-approved deferrals remain deferred and are **not**
claimed as delivered: guaranteed cross-activation lost-response recovery, precise cursor/
unpublished-work continuation through every race or crash, and automatic repair/resumption of every
legacy duplicate or interrupted discovery. Interrupted unfrozen work that cannot be continued still
resolves through the native explicit new-discovery action. B must reevaluate all Slice Required
Outcomes; this report claims no Task PASS and no Slice state.

### Risks / Deviations

- High: managed configuration publication, admission/ownership fencing, shared source identity and
  the discovery manifest are all in scope. Mitigated by the full T4 gate set above, the real
  Docker upgrade/recovery harness and the corrected real built-Web wrong-pin probe.
- **Environment, not a product failure:** this Docker daemon cannot see the private `/tmp` tmpfs
  that `tempfile` uses, so the three Docker gates fail at `up -d` with
  `bind source path does not exist` under the default `TMPDIR`. They all pass with a
  daemon-visible `TMPDIR=/dev/shm` (and a matching artifact root for the discovery proof). No
  harness or product code was modified. The default-`TMPDIR` run is reported as
  `UNAVAILABLE / ENVIRONMENT`, not as PASS.
- The previous candidate's one pre-existing intermittent Python failure
  (`test_v2_rules_workspace_commands`) did **not** reproduce in this loop's full 2411-test run; it
  is unrelated to the changed files and is not claimed as fixed.

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: 0d9bb218432eb05bab4ae4bb1326628abcb6a6ff
Task Base: ab94ce53189b5a9f16e7614cd011480a42d91e79
Commit: fix(slice44): correct B-review P1 defects A44-6/7/12 in Task 44.9
Evidence: .git/validation-evidence/0d9bb218432eb05bab4ae4bb1326628abcb6a6ff/task44-9/run-1/
Local commit only; not pushed.
```

## B Review Result

Review date: 2026-10-11. Reviewed the actual immutable Task Base..candidate range below;
workspace Head `aa623a3fb792a92b281aa27ac9686234dc80dd54` adds only `TASK.md` and Developer-role
experience changes after the executable candidate. Runtime/test/build inputs are unchanged.
Independent local evidence:
`.git/validation-evidence/aa623a3fb792a92b281aa27ac9686234dc80dd54/b-review44-9/review-index.json`.

Governance passed. Independent focused discovery/configuration/persistence regression: **51 run,
0 failures, 0 skips**. Additional actual managed-runtime/Local/SQLite/API probes: **3 run,
3 semantic failures, 0 skips**. A fresh Web build passed and reproduced index digest
`fc2e9476292e8b9b7812590f404bf60beadace371051aa04c15b4a1d61f1e2be`; an actual Chromium/Python
API/SQLite probe reproduced wrong-pin recovery. Its script exits 0 when it reproduces the defect;
that is not product acceptance. Raw logs, scripts, receipts and the inspected screenshot are indexed.

The Developer's supplied `run-1/` contains six summary/manifest/hash files, without original gate
logs or browser artifacts. No full-gate evidence is accepted by reuse in this rejecting review;
the claimed pre-existing Python failure/Base reproduction remains unverified. The remaining T4
gates and Slice Final were not rerun after proving current-Contract blockers, as permitted by the
workflow's early-rejection rule. Corrected executable work still requires the unchanged assigned
T4 gates and readable matching evidence, including first failures and any actual Base proof.

**Global complexity reassessment:** folder discovery has already exceeded three correction rounds
across Tasks 44.6–44.9 and their fix loops. A's smaller recovery Contract remains feasible; the
remaining defects are incomplete reuse of existing semantics: filename shortcuts replace actual
attachment association, leaf-only checks omit root-relative ancestor filtering, and scope-only
readback guesses replace original-admission proof. Complete these same journey rules within Task
44.9. Use the already-authorized unresolved/native-inspection outcome when proof is unavailable;
no general recovery framework, mandatory cross-activation correlation protocol, new per-defect Task
or further rescope is required. Task ID/Base/Goal/Scope and all assigned acceptance remain unchanged.

```text
Reviewed: ab94ce53189b5a9f16e7614cd011480a42d91e79..d9a9af4b665a5c524a1b5291438e7590ac4b2854
Decision: FIX REQUIRED
Slice Required Outcomes all satisfied: NO
Next: SAME TASK FIX LOOP
```

- **P1 — Unknown-response recovery still selects another root/pin (AC1/AC6/AC7;
  RO-6 recovery and Slice acceptance 30/31).** Current production reachability: two valid managed
  activations retain the same library ID and relative `Recover` folder while changing its root;
  both admissions are legal. User impact: Files' batch Organize loses the original POST response
  and automatically navigates to the other admission, presenting another source context as the
  recovered request. Contract violation: only a proved original admission may be recovered;
  unresolved native inspection is allowed, wrong association remains forbidden. Actual evidence:
  `.venv/bin/python .git/validation-evidence/aa623a3fb792a92b281aa27ac9686234dc80dd54/b-review44-9/wrong_pin_probe.py`
  serves the freshly built Web through the real Python API, performs actual managed import/
  validation/activation and records two SQLite pins. Original discovery
  `f5df9d48-7fd8-4345-8703-806d9b7f1df4` has pin
  `fb63071f-319a-4117-afeb-0fb128a05a87`; the actual recovered URL selects
  `dc7e16fa-1c84-4335-8fe5-ee267fa753f9`, pin
  `88678e70-856d-4c19-b3af-4149f55e991a`. Receipts and inspected screenshot are retained.
  `StorageFilesPage.tsx:2139` still compares only library ID, open state and path set, despite its
  new comment claiming Storage/pin comparison. Severity is P1 because required recovery associates
  the wrong live source context. **Correction:** recover only with original binding/pin proof;
  otherwise retain the request/selection, expose unresolved state with native Operations inspection/
  resolution, and block guessed navigation/automatic submission. Guaranteed recovery across
  activation is not required; add a real built-Web regression for this exact scenario.
- **P1 — Direct selection bypasses an excluded ancestor (AC2/AC7; RO-6 pinned
  root-relative filtering and Slice acceptance 28).** Current production reachability: the real
  loader accepts a published `excludeRules=[{"kind":"directory","pattern":"Blocked"}]`;
  Local contains `Blocked/Sub/Film.2001.mkv`. User impact: browsing into that folder and selecting
  its file permits organizing media that the active directory policy excludes. Contract violation:
  direct-selected files/folders must share the root-relative policy of a parent walk. Actual
  evidence: `production_probes.py`, run with `PYTHONPATH=. .venv/bin/python` from the repository
  root, uses exact managed publication/loading, real Local/SQLite and authenticated API with no
  injected/removed runtime policy. Selecting `Blocked` returns 409, but selecting its descendant
  file returns 202, then `completed` with that file as a primary and `excludedEntries=0`.
  `production_probes.log` records the failed assertion. `_refuse_unselectable_file` at
  `mediaflow/application/media_discovery.py:1912` checks the leaf only; directory admission likewise
  checks only the selected directory. Severity is P1 because the required configured policy is
  bypassed through an ordinary Files entry. **Correction:** evaluate the admitted root-relative
  ancestor exclusions/reachability at each direct-selection entrance using existing filter
  semantics; preserve exact paths/pins and actionable refusal. Cover direct files and nested
  folders against the same parent traversal, without changing policy meaning or scope.
- **P1 — Trailer-name shortcut silently drops unassociated/non-enabled attachments
  (AC4/AC5/AC7; RO-6 existing main/attachment semantics and Slice acceptance 27–29).** Current
  production reachability: valid published configuration enables attachments; a supported mp4
  has a `-trailer` suffix but no associated main file, or actual published policy has
  `trailers=false` and `otherSameStem=false`. These are supported policy settings, not weakened
  Storage substitutes. User impact: folder Organize reports `completed` while silently omitting
  media, with no exclusion/error finding; later Preview cannot recover the omitted primary.
  Contract violation: reuse actual attachment association/policy and report truthful findings,
  rather than introducing filename-only primary suppression. Actual evidence: the same
  `production_probes.py`/log records an orphan-only folder as `completed`, `sources=[]`,
  `excludedEntries=0`, `findings=[]`; the disabled-Trailer case returns only the main mkv instead
  of both eligible videos. Both expected-source assertions fail against real managed-runtime/
  Local/SQLite/API. `mediaflow/application/media_discovery.py:1241` skips every matching suffix
  whenever any enabled attachment policy exists, before `_attachment_owner` can prove association;
  skipped entries never return to ordinary observation. Severity is P1 because required folder
  discovery loses eligible items and falsely reports completion. **Correction:** suppress a
  primary only when the existing matcher under the applicable pinned policy proves its association;
  unassociated/inapplicable files must retain ordinary filtering/stability/primary processing and
  truthful findings. Cover orphan, disabled Trailer, applicable-policy and page/order cases while
  retaining 51-main/51-associated-Trailer behavior and the existing 100/101 primary refusal.

NEXT ACTION: B REVIEWS CORRECTED CANDIDATE 0d9bb21 — SAME TASK
