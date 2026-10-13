# Task 43.2 — Automatic Organization Only, Durable Exact Preview and Run once

This Task follows [the development workflow](docs/development-workflow.md) and the committed
[`SLICE.md`](SLICE.md). Read [B's experience](docs/agent-experience/task-planner-reviewer.md) for
planning/review and [Developer's experience](docs/agent-experience/developer-implementation-role.md)
for implementation. A retains the Slice boundary and final-review authority.

```text
Task ID: 43.2
Parent Slice: 43
Status: PLANNED
Task Base: 0f17234a046801d6abce7280e469bec2471bf0e8
Difficulty: High
Test Level: T4
Planner / Reviewer: B
```

## Goal

An operator manages automatic organization as the sole Automation mode, analyzes an exact definition
through durable Preview, and deliberately
runs its published bounded organizing intent once. Durable outcomes and native recovery remain
reachable without changing the schedule or borrowing scheduled execution authority.

Complete **RO-4**, the revised fixed-mode/removal portion of **RO-2**, and the remaining
durable-analysis journey in **RO-3**; deliver the manual-origin
links and definition-local outcome/recovery needed by **RO-5/RO-7**. Cross-definition inventory,
calendar metrics/records and global settings remain separate coherent in-Slice work.
Traceability: UX-001–010, V2-AUTO-002/003/004/006/009, REQ-TASK-001/005/007/008/009,
REQ-SCHED-001/002/003/005/006/007, REQ-SAFE-008 and the existing manual execution/recovery invariants.
The explicit REQ-SCHED-001/002 and V2-AUTO-009 amendment removes the two unwanted Automation modes.

## Why This Task Exists

B passed Task 43.1's implementation `7b9bc83fd2f14271f594924895b976ca3a02af0e` and inspected its
report-only successor `6da94ad8627b27363c210b224ae175d3cf1d8c33`. Native checked publication and
retained history are accepted at Task level, while its old mode selector requires the now-authorized
transition. The Slice is not complete. Review/evidence and the Required-Outcome
reassessment are retained locally in
`.git/validation-evidence/7b9bc83fd2f14271f594924895b976ca3a02af0e/b-review43.1-20261013/INDEX.md`;
the prior Task 43.1 plan/report is recoverable at that report successor's `TASK.md`.

**B Contract reassessment: REPLANNED, same unstarted Task ID.** A checkpointed the user's clarified
instruction at this Task's Base. Governance passed before this replan. Previous three-mode and
conversion/compatible-processing plans were NOT STARTED and are superseded. This plan retains
durable exact Preview/Run once, removes the unwanted Automation modes entirely and preserves High/T4.
The preceding plan remains at `10b5710a43589b6fcbe07aa962f61bd441678c67:TASK.md` and locally at
`.git/validation-evidence/automation-only-20261013/task43.2-before-clarification.md`.
Task 43.1's existing publication/history acceptance remains valid; no Slice final acceptance is implied.

Actual gaps at Base:

- Domain parsing, definition publication/editor and Scheduler still support all three historical
  modes. Removing only the selector would leave direct API/CLI admission and old scheduled emission
  available. Complete removal must safely reject old configuration/work while retaining recorded
  pins/history; it does not require conversion or compatible execution of old modes.
- Automation list/detail have no definition-bound Run once action or durable manual-origin admission.
  `AutomationJobService.submit` rejects definition IDs; legacy generic Job submission is not a scoped
  substitute. `DefinitionScopedExecutionService` requires an enabled scheduled definition.
- `AutomationTaskDefinitionPreviewService.create` discovers/analyzes inline before returning its
  persisted Preview. Large analysis is not durable running/cancellable work.
- Existing MediaDiscovery, manual intents/Preview/execution, Worker claims, request reconciliation,
  Operations controls and task-linked recovery already provide most of the necessary behavior.
  Discovery currently obtains the current Active itself and rejects an empty selected path; merely
  linking a definition to Files does not enforce its exact pin, sub-scope or item ceiling.
- Operations currently infers scheduled trigger from any Job definition ID. There is no durable
  definition origin on manual execution, so adding a display label cannot establish correct links.

These are one coherent definition-bound analysis/admission journey across the existing authorities,
not separate field, table, test or UI Tasks. Reuse those services and their execution models.

## Implementation Scope

```text
Existing definition/pin and bounded request validation
→ additive durable analysis/admission/origin associations and atomic reconciliation
→ automatic-organization-only lifecycle and removal of unwanted definition modes/branches
→ existing Preview / discovery / manual execution services and resident Workers
→ shared authenticated API projections/commands
→ native Automation entry, exact review, durable progress and contextual Operations recovery
→ application/persistence/API/Web/browser and upgrade tests
```

### Operator journey

- **Goal/entry:** from a published definition's list/detail, explicitly choose Preview or `运行一次`.
  Reads, navigation and opening the action create no work. Draft-only/removed definitions explain
  why Run once is unavailable and offer their existing publication/history recovery. Removed-mode
  input/work explains unsupported state through existing configuration correction/cancel/history.
- **Visible state:** the exact published name, source ResourceLibrary/sub-scope and item bound with
  fixed `自动整理` intent; old records retain their original historical intent;
  enabled schedule separately from command readiness/permissions; analysis/admission/processing
  separately from outcome. Show exact candidate versus Active Preview, freshness, effects,
  independent ineligible items and a concrete next action.
- **Action:** new/copy/edit uses an automatic-organization-only form with one checked Save.
  Run once enters live bounded source discovery/selection, exact manual Preview,
  then the existing separate one-shot confirmation/execution. A scheduled grant is not that intent.
- **Success:** promptly expose a durable analysis/run and its status/link; execution uses exactly
  the reviewed selection. Return to the originating definition and preserve safe Files/Operations
  context across refresh/reconnect. Disabled schedules can run once without becoming enabled.
- **Failure/recovery:** explain invalid/stale pin, source/dependency, denied permission, capacity,
  unsupported legacy mode, unavailable Worker, analysis/cancellation, conflict, changed Preview/source
  and unknown submission. There is no conversion or compatible old-mode run action.
  Preserve input and durable per-item state; reconcile an unknown request before any deliberate
  resubmission. Repair readiness or use existing task decision/analysis/continuation; completed or
  uncertain effects are never replay candidates.

### Automatic organization only and complete mode removal

1. Remove `AutomationTaskRunMode.SCAN_ONLY` / `SCAN_AND_PLAN`, their parsing aliases, Web choices
   and definition-bound scan/plan publication, scheduling/admission/execution branches. Domain and
   shared application validation, managed activation/import, API and CLI accept automatic organization
   only. Hiding the selector or retaining a compatible old-mode executor does not satisfy the Task.
2. Removed-mode configuration is unsupported and fails validation/activation with existing
   correction/removal guidance; reads never automatically convert/default it. No grandfathering,
   dedicated legacy inventory or conversion endpoint/form is added. Preserve focused Save, normal
   management/activation/revoke checks, disabled/no-authority create/copy and zero-work publication.
3. Old queued/running definition-bound scan/plan work stops safely at existing supported boundaries,
   remains diagnosable/cancellable where safe and cannot invoke retained old-mode processing, resume
   as automatic organization or gain mutation authority. A proved historical request lookup reads
   its original record only. Preserve completed outcomes, original intent/pins, grants/audits and
   Task 43.1's integrity-aware history; do not erase records/media or replay completed/uncertain work.
4. Preserve Scanner/Planner modules, automatic organization's internal Scan → Plan/Preview stages
   and unrelated standalone Scan/Preview/DryRun commands. Historical read decoding can retain old
   recorded values as data, but cannot expose them as valid runnable definition modes. Valid
   automatic-organization work retains its existing exact-pin and safe-boundary semantics.

This is removal within the current definition journey. It does not authorize a general V1 retirement,
another queue/recovery engine, a legacy-mode migration framework or changes to unrelated commands.

### Exact context and shared application authority

1. Resolve the exact observed published revision and definition on the backend, with current command
   permissions and readiness. Pin definition identity/fingerprint, mode, ResourceLibrary, safe
   relative sub-scope and item ceiling with the immutable configuration. Stale new admission refuses
   instead of silently resolving today's Active. A proved existing request reads back its original
   admitted pin rather than creating a replacement after publication changes.
2. Automatic-organization Run once permits a disabled published schedule only with current manual
   command permissions and explicit one-shot intent. Distinguish durable manual origin from a
   scheduled occurrence before applying gates that require enabled schedules or update due state.
   Reuse manual admission/Worker execution; do not mutate its pinned document, synthesize an enabled
   copy or weaken Scheduler/unattended gates. Removed modes cannot execute definition-bound work.
3. Run once reuses live Storage discovery/selection and existing exact manual
   Preview/one-shot execution. Enforce the definition's ResourceLibrary/sub-scope/pin and ceiling at
   every handoff, including a definition scoped to the library root. URL/context hints, browser
   Storage IDs, FileIndex, raw fingerprints and a scheduled grant cannot authorize that selection.
   Keep the existing 100-primary manual/discovery bound; allow an explicitly selected narrower
   bounded subset when the definition ceiling is larger. Label both bounds. Never silently execute
   a first-N prefix, enlarge manifests, or execute a changing whole-library scope.
4. Expensive definition Preview and manual discovery/analysis are durable, observable and
   cancellable at supported safe boundaries; HTTP returns their durable identity promptly rather
   than waiting for a full source walk or Provider batch. Extend the existing Preview/application
   chain and Task/Worker machinery. Preserve exact Preview evidence, candidate versus Active
   labels, per-item explanation and grant validation. Existing supported non-Active Preview routes
   remain compatible but cannot admit Run once or scheduled authority as if published.
5. Preview/grant/revoke remain distinct. Initial unattended grant requires completed exact valid
   Preview plus explicit scoped authority; saving/enabling/copying/Run once does not grant, revive,
   consume or expand scheduled authority. Valid automatic-organization scheduled runs retain
   idempotent occurrence emission and live revocation at every not-yet-performed mutation boundary.
6. Atomic reconciliation binds the exact request, principal (including legal Unicode identities),
   definition context and operation/selection to the corresponding existing admission. Duplicate,
   concurrent and commit-then-response-loss submissions converge without duplicate work or double
   authority consumption. A changed binding with the same request ID refuses. Reads and unknown
   reconciliation do not recreate work; no POST retry or credential persistence in the browser.
7. Persist a manual definition-origin link atomically with its actual admission and retain immutable
   historical name/source/mode/version. Use the real Job/Task or manual execution as the run anchor;
   create no dummy Job, second queue or parallel recovery engine. Scheduled/manual origin stays
   explicit in Automation definition history and Operations after rename/remove/restart. Linked
   Job/Task/execution is one admitted run. Diagnostic/grant-preflight Preview, discovery alone and
   rejected admission are not admitted media runs. Previously admitted scan/plan runs preserve their
   original mode/outcome and count once, never as organized media. Preserve pre-Task failures and
   linked item/recovery outcomes; Job completion is not media success.
8. Manual request admission, completion, pause/continue/cancel and failure never initialize,
   advance/reset or consume definition due state/occurrences. Scope/source/selection changes cannot
   reuse previous one-shot authority; current RBAC, capacity, source stability, capabilities,
   conflicts, locks/leases/fences and OrganizerExecutor-only mutation remain authoritative.

### Surfaces, compatibility and frozen scope

Use the current shared shell, typed client/query/navigation/authentication and existing definition,
Files, Preview, Operations detail/records/export/decision/recovery routes. Backend availability
controls Web actions and direct POST identically. Show durable work immediately and restore its
proved request context across reload; isolate principal changes and reconnect. Include empty/no/
corrupt Active, loading, narrow/keyboard and 401/403/unavailable/malformed response recovery.

Necessary additive persistence/API/Worker and lifecycle-transition extensions belong here. Existing
V1/API/CLI callers remain compatible except the Contract's explicit removal of the two Automation
modes; old input/work is unsupported with existing correction/removal/cancel guidance. Preserve schema45/older
rows, published pins, grants/audits, historical occurrences and accepted Slice 44 Files/discovery
behavior. Explain any necessary factual
architecture adjustment without converting TARGET or other Required Outcomes into delivered claims.

During Developer implementation, freeze `SLICE.md`, Roadmap, Progress, stable requirements,
permanent contracts and all Slice Bases.
Preserve the four pre-existing untracked PNGs unchanged/unstaged; both Automation checksums are in
the Contract. Keep `config/alist.json` ignored/untracked/unstaged and use only temporary/fake/local
fixtures, never production media or private credentials.

## Acceptance Criteria

- [ ] **AC-T1 — Native exact journey:** Preview/Run once are explicit Web actions over the shared
  application authority. Automatic organization finishes the promised success/failure/recovery path;
  disabled published schedules work manually, while Draft-only/removed definitions cannot masquerade as Active.
- [ ] **AC-T2 — Pin and bounds:** exact definition/configuration and source scope/item ceiling survive
  every durable handoff and restart; stale new requests refuse without repinning. Automatic mode
  selects live bounded sources, reviews exact Preview and separately admits exactly that selection
  with existing one-shot/destructive-intent gates. No scheduled-grant or FileIndex shortcut exists.
- [ ] **AC-T3 — Durable analysis/authority:** long analysis returns durable observable work promptly,
  supports existing safe controls and yields exact independent Preview evidence. Reads/Preview have
  zero media mutation; valid explicit grant and future scheduled execution remain separate and work.
- [ ] **AC-T4 — Atomic request recovery:** concurrent/duplicate/response-loss/reload requests reconcile
  once with unchanged binding, current permissions and principal isolation, including Unicode IDs.
  Unknown state remains unknown until proved; no automatic replay or double authority consumption.
- [ ] **AC-T5 — Schedule independence:** every manual run and terminal/control/failure path preserves
  enabled state, due time and scheduled occurrence uniqueness; no grant creation/revival/revoke occurs
  merely through Run once. Already admitted scheduled work retains its original authority semantics.
- [ ] **AC-T6 — Durable history/outcomes:** actual manual/scheduled origins and immutable historical
  context survive rename/remove/reopen; Automation definition history and Operations reach the same
  durable run/results and native per-item recovery with return context. No dummy Job/double count,
  false Job-success projection or replay of successful/uncertain effects.
- [ ] **AC-T7 — Compatibility/safety:** current RBAC, source stability/confinement, old/new pins,
  capacity, locks/leases/fences, live revocation, C-with-A/A identity and accepted Files/Settings/Rules/
  Operations/V1 journeys hold. Passive reads call no Provider and create no Draft/grant/work.
- [ ] **AC-T8 — T4 checkpoint:** assigned gates and actual additive upgrade evidence pass with honest
  counts/skips/limitations; exact candidate/evidence match and only Task-owned files enter the checkpoint.
- [ ] **AC-T9 — Complete mode removal:** only automatic organization remains a valid Automation mode;
  no scan-only/scan-and-plan values/aliases, choices or compatible definition-bound executor remain.
  Validation/publication/import and Web/API/CLI refuse removed-mode input; old work stops safely,
  with recorded intent/results/pins/history intact across upgrade/reopen. No conversion, grandfathered
  publication or legacy-mode inventory is added. Standalone Scan/Preview and internal analysis remain.

## Required Tests

Run from repository root under [the workflow's stages/evidence rules](docs/development-workflow.md#6-test-levels).
High/T4 reflects Active/admission/execution/persistence/concurrency/core-Worker boundaries, not UI size.

### Development and correction feedback

Add focused application/API/persistence coverage for this journey (planned modules
`tests.test_automation_run_once`, `tests.test_v2_automation_run_once`) and changed durable Preview
tests. First run new/changed cases and directly affected existing modules:

```bash
.venv/bin/python scripts/check_governance.py
.venv/bin/python -m unittest tests.test_automation_run_once tests.test_v2_automation_run_once tests.test_automation_definition_publication tests.test_v2_automation_lifecycle tests.test_automation_task_definition_preview tests.test_automation_preview_grant_gate tests.test_automation_definition_execution tests.test_automation_definition_occurrence
npm --prefix web run test -- run src/entities/operations src/features/operations
npm --prefix web run test:e2e -- --config=playwright.python.automation.config.ts tests/e2e/automation-run-once.python.spec.ts
```

Use real SQLite/application/API and production Worker assemblies; fake/local external ports only.
Cover automatic-organization Run once with enabled and disabled schedules; fixed-mode create/edit/
copy, rejected removed-mode/alias configuration/publication/import/admission, safe-stop of old queued/
running work and retained historical evidence. Include root/sub-scope,
invalid/traversal/over-limit/changed selection; stale definition/Active and intact old pins;
missing secrets/pins/dependencies/Worker; principal and
permission changes; concurrent/duplicate/unknown admission and reopen; cancellation/partial/no-work/
uncertain outcomes; source stability/conflicts/capability/refused effects; safe decisions/recovery;
schedule state and grant independence; manual origin and no duplicate count; corrupt historical
evidence versus genuine absence. Assert zero side effects separately on read, analysis and denial.

Update tests whose mode-support/execution expectation the explicit amendment supersedes; preserve
historical-read and safe-stop/safety coverage with actual old fixtures, and retain all standalone
Scan/Preview and organizing analysis regressions. Do not relabel old pins as automatic, hide skips
or relax mutation/authority/history assertions to manufacture a green suite.

### Final checkpoint gates

Full Python includes focused and existing affected application/integration cases; no mechanical
second focused run is required after that succeeds on the same candidate/configuration.

```bash
.venv/bin/python -m unittest discover -s tests
.venv/bin/ruff format --check .
.venv/bin/ruff check .
.venv/bin/python -m compileall -q mediaflow tests scripts
.venv/bin/python -m pip check
.venv/bin/mediaflow --config config/strategy.example.json config validate
.venv/bin/mediaflow --config config/mediaflow.phase13.2.example.json config validate
npm --prefix web run test -- run
npm --prefix web run typecheck
npm --prefix web run lint
npm --prefix web run format:check
npm --prefix web run build
npm --prefix web run test:e2e
npm --prefix web run test:e2e -- --config=playwright.python.automation.config.ts tests/e2e/automation-lifecycle.python.spec.ts tests/e2e/automation-run-once.python.spec.ts
npm --prefix web run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts
npm --prefix web run test:e2e -- --config=playwright.python.unicode-principal.config.ts tests/e2e/operations-principal-identity.python.spec.ts
.venv/bin/python scripts/wheel_smoke_test.py
.venv/bin/python scripts/docker_release_security_smoke_test.py
.venv/bin/python scripts/docker_upgrade_recovery_smoke_test.py
.venv/bin/python scripts/check_governance.py
git diff --check
sha256sum docs/pics/自动化.png docs/pics/自动化-全局设置.png
rg -n -i 'ffprobe|ffmpeg' mediaflow pyproject.toml
```

The final search expects exit 1/no matches. Wheel/static-serving checks cover installed Worker/API
paths; Docker security covers packaged auth/manual execution; Compose upgrade/restart covers durable
origin/analysis/admission and preserved ownership. Create a workspace-local ignored `TMPDIR` before
Docker invocation on this host and record the exact command. Run Playwright suites sequentially or
with explicitly separate output directories and harnesses; preserve failed first runs and exact repeats.

Native real-Python/SQLite/temporary Local/synthetic-or-local Provider browser journeys must prove
automatic-organization Run once through actual Worker outcomes, independent due/grant state and immediate
Operations links. Include duplicate/unknown and Unicode-principal reload/reconnect isolation, stale
pin/source and denied recovery, durable analysis safe controls, and one affected item's native
decision/recovery without replaying its successful sibling. Also drive completed exact Preview →
explicit scoped grant → actual Scheduler emission → Worker outcome with current revocation. Node
fixtures or HTTP readback alone cannot replace these paths. Inspect actual wide/narrow screenshots
and traces for the new interactions; retain the reference originals unchanged.

Drive fixed-mode native create/edit/copy → disabled publication → exact Preview/authority → manual
and scheduled outcome. Verify no mode selector/conversion action exists, removed-mode/alias imports
and direct commands fail, Scheduler emits no removed-mode occurrence and old queued/running work
stops safely instead of executing a compatible branch. Preserve original historical evidence across
configuration correction/removal, upgrade and reopen without automatic conversion or media mutation.

For schema changes, also run `.venv/bin/python -m unittest tests.test_migration_rehearsal
tests.test_upgrade_preflight` and an actual isolated **Slice Base schema44 → candidate** and
**Task Base schema45 → candidate** seed/upgrade/reopen rehearsal. Seed using those real Git sources,
record exact commands/SHAs and compare retained Task/Job/manual/discovery/occurrence/review/Result,
configuration pins, grants/audits, original recorded intent and due state; don't substitute a current schema
with its version number edited. Old unfinished work stays safely diagnosable and never acquires guessed origin or
new execution authority. If no schema changes, prove that from the diff and still cover durable
origin/restart compatibility and unsupported old-work stopping. No safety-test weakening/hidden
skip/retry manufactures PASS.

### B independent verification

B independently drives a disabled published automatic-organization definition through Run once using
real API/SQLite/browser/Workers, verifies its exact scope/pins/limits and unchanged due/grant state,
and reproduces concurrent or response-lost admission before/after publication and reopen. Inspect the persisted
actual run/origin link, Operations/definition history and one mixed-item recovery. Check long Preview
admission is prompt/durable and its safe cancellation, fresh grant and scheduled execution still work.
Reproduce stale/denied cases and principal isolation. Inspect matching original gate logs and actual
visual artifacts; rerun missing/incompatible/contradicted gates. A proven P1 permits early rejection;
PASS requires the complete candidate plan.

Independently inspect the absence of mode selection/conversion, rejected removed-mode/alias input
and Scheduler/Worker safe-stop of genuine old queued/running work. Verify original history/pins/
results survive correction/removal and reopen; no compatible execution branch or automatic mode
conversion remains. Standalone Scan/Preview and valid automatic organization still work.

### Evidence and rerun rules

Retain one index/raw logs/browser images/traces/build hashes per candidate under
`.git/validation-evidence/<full-source-sha>/<run-id>/` or CI through A's final decision. Record exact
source/reviewed SHA, dirty input identity, commands/cwd/runtime/dependencies/fixtures/worker/retry
settings, artifact digests, exits/counts/skips/durations and first failures/repeats. The previous
Task's runtime evidence is baseline information, not acceptance of this changed executable candidate.
Document-only successors may reuse proved identical runtime inputs; rerun document-consuming gates.
Executable/test/harness/dependency/configuration/artifact changes require fresh affected evidence
and this T4 candidate's complete final gates. Disclose unavailable gates and local-only artifacts.

## Non-goals

- Changing the Slice Contract/Base, Roadmap, Progress or stable requirements; A final review/closure.
- Reference inventory/search/paging/monthly metric cards, consolidated cross-definition record tabs,
  or the global-settings form and actual resident polling adoption. These remain in-Slice outcomes,
  not permanent deferrals; a definition-local history link does not complete RO-1/RO-5.
- Another queue/processing/recovery engine, synthetic Jobs, larger/split manual manifests, unbounded
  whole-library execution, MediaLibrary organizing sources or per-definition downstream policy overrides.
- New schedule modes/overlap/backfill, generic historical Reprocess, universal rollback, seamless
  exceptional discovery recovery beyond accepted Slice 44, or automatic uncertain-mutation replay.
- Legacy Automation-mode conversion, a dedicated legacy-mode inventory, grandfathered publication
  or compatible execution of either removed mode; deletion of historical evidence/media or changes
  to unrelated standalone Scan/Preview commands.
- Identity/Secret Store/deployment redesign, new Providers/Storage/FFmpeg/FFprobe, image edits,
  unrelated refactors and optional P2 cleanup.

## Developer Completion Report

### Changed Files

### Implemented

### Tests and Results

Record the exact tested/submitted candidate, commands/counts/durations and retained evidence index;
include upgrade, native production/browser/Worker outcomes, first failures/repeats and any limitations.

### Decisions

### Remaining In-Slice Work

### Risks / Deviations

### Checkpoint

```text
Status: NOT STARTED
Head SHA: none
```

## B Review Result

```text
Reviewed: none
Decision: PENDING
Slice Required Outcomes all satisfied: NO
Next: PENDING
```
