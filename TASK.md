# Task 44.9 — Complete ordinary folder Organize with safe discovery restart

This Task follows [the development workflow](docs/development-workflow.md) and
[Task/TEMPLATE.md](Task/TEMPLATE.md), within the checkpointed amended [Slice 44](SLICE.md).

```text
Task ID: 44.9
Parent Slice: 44
Status: PLANNED
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

Pending implementation. This planning revision fixes no product defect and claims no runtime PASS.

### Changed Files

Pending.

### Implemented

Pending.

### Tests and Results

Pending actual candidate results/provenance, including PASS/FAIL/SKIP/UNAVAILABLE.

### Decisions

Pending implementation choices inside the smaller Contract and this Task.

### Remaining In-Slice Work

Current-contract audit corrections remain pending; exceptional recovery promises are explicitly
deferred, not delivered or counted as fixed. B must reevaluate all RO after implementation.

### Risks / Deviations

High: managed publication, admission/ownership, shared source identity and necessary migration.
User-authorized A substitutes for planning; B retains independent implementation review.

### Checkpoint

No implementation checkpoint yet; Developer reports actual candidate and assigned gates.

## B Review Result

```text
Reviewed: NOT SET
Decision: PENDING
Slice Required Outcomes all satisfied: PENDING
Next: DEVELOPER IMPLEMENTS CURRENT TASK
```

NEXT ACTION: DEVELOPER IMPLEMENTS CURRENT TASK
