# Task 43.2 — Single-mode Automation, Durable Exact Preview and Run once

This Task follows [the development workflow](docs/development-workflow.md) and the committed
[`SLICE.md`](SLICE.md). Read [B's experience](docs/agent-experience/task-planner-reviewer.md) for
planning/review and [Developer's experience](docs/agent-experience/developer-implementation-role.md)
for implementation. A retains the Slice boundary and final-review authority.

```text
Task ID: 43.2
Parent Slice: 43
Status: PLANNED
Task Base: dfd64505fd4344d4d99d1b0ad0a3e07d92fbca33
Difficulty: High
Test Level: T4
Planner / Reviewer: B
```

## Goal

An operator manages automatic organization as the sole Automation mode, safely converts a legacy
scan/plan definition when needed, analyzes an exact definition through durable Preview, and deliberately
runs its published bounded organizing intent once. Durable outcomes and native recovery remain
reachable without changing the schedule or borrowing scheduled execution authority.

Complete **RO-4**, the revised fixed-mode/legacy-transition portion of **RO-2**, and the remaining
durable-analysis journey in **RO-3**; deliver the manual-origin
links and definition-local outcome/recovery needed by **RO-5/RO-7**. Cross-definition inventory,
calendar metrics/records and global settings remain separate coherent in-Slice work.
Traceability: UX-001–010, V2-AUTO-002/003/004/006/009, REQ-TASK-001/005/007/008/009,
REQ-SCHED-003/005/006/007, REQ-SAFE-008 and the existing manual execution/recovery invariants.
The explicit V2-AUTO-009 amendment supersedes REQ-SCHED-001's three-mode selection for this journey.

## Why This Task Exists

B passed Task 43.1's implementation `7b9bc83fd2f14271f594924895b976ca3a02af0e` and inspected its
report-only successor `6da94ad8627b27363c210b224ae175d3cf1d8c33`. Native checked publication and
retained history are accepted at Task level, while its old mode selector requires the now-authorized
transition. The Slice is not complete. Review/evidence and the Required-Outcome
reassessment are retained locally in
`.git/validation-evidence/7b9bc83fd2f14271f594924895b976ca3a02af0e/b-review43.1-20261013/INDEX.md`;
the prior Task 43.1 plan/report is recoverable at that report successor's `TASK.md`.

**B Contract reassessment: REPLANNED, same unstarted Task ID.** A checkpointed the user's
single-mode amendment at this Task's Base. Governance passed before this replan. The earlier
Task 43.2 plan at proposed Base `6da94ad8627b27363c210b224ae175d3cf1d8c33` was never implemented;
its three-mode branches are superseded. This plan retains the coherent definition-bound Preview/
Run-once goal, includes necessary fixed-mode lifecycle/legacy recovery and preserves High/T4.
Its original working copy is retained locally at
`.git/validation-evidence/single-mode-automation-20261013/task43.2-before-rescope.md`.
Task 43.1's existing publication/history acceptance remains valid; no Slice final acceptance is implied.

Actual gaps at Base:

- Domain parsing, definition publication/editor and Scheduler still support all three historical
  modes. Removing only the selector would leave direct API/CLI admission and old scheduled emission
  available. Legacy data needs explicit bounded conversion and intact original admitted pins/history.
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
→ fixed-mode lifecycle and safe legacy conversion/new-admission gates
→ existing Preview / discovery / manual execution services and resident Workers
→ shared authenticated API projections/commands
→ native Automation entry, exact review, durable progress and contextual Operations recovery
→ application/persistence/API/Web/browser and upgrade tests
```

### Operator journey

- **Goal/entry:** from a published definition's list/detail, explicitly choose Preview or `运行一次`.
  Reads, navigation and opening the action create no work. Draft-only/removed definitions explain
  why Run once is unavailable and offer their existing publication/history recovery. Old scan/plan
  definitions show legacy status and an explicit conversion/history entry.
- **Visible state:** the exact published name, source ResourceLibrary/sub-scope and item bound with
  fixed `自动整理` intent, or the truthful historical mode for legacy objects;
  enabled schedule separately from command readiness/permissions; analysis/admission/processing
  separately from outcome. Show exact candidate versus Active Preview, freshness, effects,
  independent ineligible items and a concrete next action.
- **Action:** new/copy/edit uses a fixed automatic-organization form with one checked Save; explicit
  legacy conversion reviews changed effects and publishes disabled without inherited authority.
  Run once enters live bounded source discovery/selection, exact manual Preview,
  then the existing separate one-shot confirmation/execution. A scheduled grant is not that intent.
- **Success:** promptly expose a durable analysis/run and its status/link; execution uses exactly
  the reviewed selection. Return to the originating definition and preserve safe Files/Operations
  context across refresh/reconnect. Disabled schedules can run once without becoming enabled.
- **Failure/recovery:** explain invalid/stale pin, source/dependency, denied permission, capacity,
  unsupported legacy mode, unavailable Worker, analysis/cancellation, conflict, changed Preview/source
  and unknown submission. Legacy objects offer conversion, not a hidden new-run branch.
  Preserve input and durable per-item state; reconcile an unknown request before any deliberate
  resubmission. Repair readiness or use existing task decision/analysis/continuation; completed or
  uncertain effects are never replay candidates.

### Single-mode lifecycle and legacy transition

1. Native definition create/edit/copy exposes only automatic organization and removes the mode
   selector. Shared backend commands reject new scan-only/scan-and-plan definitions, re-enabling or
   new manual/scheduled admissions, including direct API/CLI aliases and managed publication paths.
   Keep legacy parsing/read/export support and standalone Scan/Preview/DryRun; deleting enum values
   or all old processing branches is not necessary and must not break admitted historical work.
2. A legacy definition remains inspectable with its original mode, source, schedule and history.
   Scheduler and command readiness refuse new legacy work with actionable conversion guidance;
   passive reads do not change configuration, grants, due state or create failed Jobs as a substitute.
   Whole-document validation permits unchanged legacy objects in an unrelated focused successor,
   rather than dropping/converting siblings or making all configuration unpublishable. Import may
   preserve such data for recovery but cannot authorize legacy emission or silently convert it.
3. Conversion, or copying a legacy object into a new automatic one, is explicit about changed
   effects. Reuse checked successor publication and normal management/activation/revoke permissions.
   Keep conversion identity/history, publish disabled, invalidate/revoke prior future authority,
   and require fresh exact Preview and explicit applicable grant/one-shot intent. Stale/concurrent/
   failed/unknown conversion has the same preserved-Active/input/reconciliation behavior as Save.
   No new occurrence, media work or grant is emitted by conversion/publication itself.
4. Old admitted scan/plan Jobs/Tasks, occurrences, exact pins and results retain their original
   non-mutating intent and existing controls/recovery across conversion, new Active and reopen.
   A historical request lookup may return its proved original admission; it cannot create a new
   legacy run or broaden it into organizing work. Preserve Task 43.1 integrity-aware retained history.

This is the necessary complete transition of the current definition journey, not a second queue,
general V1 retirement, separate migration Slice or cleanup of unrelated modes in other features.

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
   copy or weaken Scheduler/unattended gates. Legacy modes cannot admit new definition-bound work.
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
V1/API/CLI callers remain compatible except the Contract's explicit restriction on new removed-mode
definition publication/admission; failed commands offer conversion recovery. Preserve schema45/older
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
- [ ] **AC-T9 — Single mode and legacy recovery:** native create/edit/copy has no mode selector;
  backend new-publication/admission gates cannot be bypassed by old clients, aliases or imports.
  Legacy objects remain reachable, new legacy emission refuses, and explicit conversion/copy publishes
  disabled with fresh-evidence/authority requirements. Old admitted scan/plan work keeps its original
  non-mutating pin; unrelated publication and history/export survive conversion/upgrade/reopen.

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
copy, explicit legacy conversion, direct/alias/import new legacy-mode refusals, retained real legacy
admitted pins and unrelated successor preservation. Include root/sub-scope,
invalid/traversal/over-limit/changed selection; stale definition/Active and intact old pins;
missing secrets/pins/dependencies/Worker; principal and
permission changes; concurrent/duplicate/unknown admission and reopen; cancellation/partial/no-work/
uncertain outcomes; source stability/conflicts/capability/refused effects; safe decisions/recovery;
schedule state and grant independence; manual origin and no duplicate count; corrupt historical
evidence versus genuine absence. Assert zero side effects separately on read, analysis and denial.

Update only tests whose new-mode selection/admission expectation the explicit amendment supersedes;
retain old-mode historical/admitted-work regressions with genuine legacy fixtures. Do not relabel
legacy pins as automatic or remove legacy safety assertions to manufacture a green suite.

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

Drive fixed-mode native create/edit/copy and legacy conversion → disabled publication → fresh
Preview/authority → manual and scheduled outcome. Verify direct new scan/plan admissions fail,
Scheduler emits no new legacy occurrence, old admitted non-mutating work still completes under its
original pin, and conversion/import/unrelated Save/reopen retain historical evidence and safe recovery.

For schema changes, also run `.venv/bin/python -m unittest tests.test_migration_rehearsal
tests.test_upgrade_preflight` and an actual isolated **Slice Base schema44 → candidate** and
**Task Base schema45 → candidate** seed/upgrade/reopen rehearsal. Seed using those real Git sources,
record exact commands/SHAs and compare retained Task/Job/manual/discovery/occurrence/review/Result,
configuration pins, grants/audits, legacy-mode intent and due state; don't substitute a current schema
with its version number edited. Old unfinished work stays safely diagnosable and never acquires guessed origin or
new execution authority. If no schema changes, prove that from the diff and still cover durable
origin/restart compatibility. No safety-test weakening/hidden skip/retry manufactures PASS.

### B independent verification

B independently drives a disabled published automatic-organization definition through Run once using
real API/SQLite/browser/Workers, verifies its exact scope/pins/limits and unchanged due/grant state,
and reproduces concurrent or response-lost admission before/after publication and reopen. Inspect the persisted
actual run/origin link, Operations/definition history and one mixed-item recovery. Check long Preview
admission is prompt/durable and its safe cancellation, fresh grant and scheduled execution still work.
Reproduce stale/denied cases and principal isolation. Inspect matching original gate logs and actual
visual artifacts; rerun missing/incompatible/contradicted gates. A proven P1 permits early rejection;
PASS requires the complete candidate plan.

Independently inspect the absence of a native mode selector, perform explicit legacy conversion and
verify disabled/fresh-authority state. Prove rejected direct/Scheduler new legacy admission alongside
retained original legacy processing/history, including unrelated publication and reopen.

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
