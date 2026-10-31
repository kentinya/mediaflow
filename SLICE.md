# Slice 47 — Unified Task Scheduling and Organizing Execution

```text
Slice ID: 47
Name: Unified Task Scheduling and Organizing Execution
Owner: A — Slice Owner / Architect / Final Reviewer
Status: ACTIVE
Base SHA: 5144ab1fc2344b06194969cc2c496835729664c0
Implementation Head: NOT SET
Working Branch: main
Development Authorization: USER-REQUESTED REFACTOR; A SCOPE AUTHORITY — 2026-10-30
Risk: High
Final Test Level: T4
Next Action: B ADJUSTS TASK47.2 TO THE USER-AUTHORIZED ORGANIZING PAUSE RETIREMENT
```

## Authority and accepted baseline

[AGENTS.md](AGENTS.md) and [Development Workflow](docs/development-workflow.md) govern scope,
roles, checkpoints, testing and closure. The user requested Job removal and unified Task execution,
then explicitly authorized A scope authority on 2026-10-30. This checkpoint selects the new Slice;
it is neither implementation nor final acceptance. No self-review or delegation exception is granted.

The immutable Base includes accepted43–46 and subsequent accepted corrections, including original
Automation execution-result presentation. Slice46 remains PASS / CLOSED with original Base
`e9f1a8dc607cfc6d5ea02141b058da8ce849cd70` and accepted implementation
`6469f45811ee59c875cfd10107d3aed129e9d489`; its Contract/A review is retained at
`5144ab1fc2344b06194969cc2c496835729664c0:SLICE.md`. Earlier closure identities and limits remain
in [Progress](docs/progress.md) and Git. This Slice selects the previously deferred queue/Worker
integration only as required below; it does not reopen or rewrite earlier acceptance.

## User goal

- 取消独立 Job 系统：一项整理工作 = 一个 Task + 多个 TaskItem + 对应 Result。
- 手动整理、定时自动整理、运行一次共用整理引擎，以触发来源和执行授权区分入口。
  自动整理根据已配置的规则和有效授权自动执行。
- 将队列、Worker 领取、心跳、控制和状态职责整合进 Task；恢复续作复用现有四类流程。
- 删除冗余 Job 代码、数据库结构和接口，保留现有功能、数据、安全机制及执行记录。
- 先分析依赖，再实施迁移和重构，完成适用测试；不创建第二套执行或恢复系统。

## User-authorized scope amendment — 2026-10-31

The user explicitly removed organizing Pause and resume-from-pause. This scope action uses the
previously granted A scope authority; the same agent also acts as B, which is disclosed here.
This is a Contract amendment, not implementation, Task PASS or A Final Review. Original Slice Base
and accepted history stay unchanged. No A Final Review of this Slice is performed by this agent.

Manual, scheduled, Run once and supported API/CLI organizing expose cancellation, not Pause or
resume-from-pause. Retire their Web/API/CLI actions and dedicated live branches; a hidden button
alone is insufficient. Shared control routes still serve ordinary-file Tasks, but reject organizing
pause/resume with bounded no-effect guidance. Four-type decision → analysis → summary → explicit
continuation remains required and is not resume-from-pause. Human waiting, timed stability waiting,
claim/fence safety stops and uncertain-effect inspection remain intact.

Preserve historical paused rows, IDs, pins, Results and known/uncertain effects. They are not
silently deleted, relabelled Failed/Cancelled or reset to Pending. Show the retired capability and
only offer a backend-proven safe cancellation/inspection action; no automatic resume or new effect
authority. Cancellation stops unperformed work at a safe boundary without undoing completed effects.
Ordinary-file Copy/Move and other existing non-organizing controls remain unchanged.
This amendment supersedes organizing Pause/resume obligations in REQ-TASK-004, V2-OPS-007 and the
CURRENT/TARGET prose; it does not weaken RBAC, source ownership, data preservation or non-replay.

## Requirements and journeys

- Authorized TARGET amendment `V2-TASK-001–007` in [V2 Requirements](docs/v2-requirements.md).
  It supersedes the V2 Job-object requirement in `REQ-TASK-008`, Job-emitting `REQ-SCHED-003`,
  Job-specific queue/readiness wording and Job/Task merging in the affected V2 Operations/Automation
  contracts. Frozen V1 meaning and accepted historical facts remain in Git/current baseline sections.
- Preserve `UX-001–007/010`, `REQ-TASK-002–010`, `REQ-SCHED-001/004/005`, applicable
  `REQ-RECOVERY-*`, `REQ-RESULT-*`, `REQ-API-*`, `REQ-DEPLOY-*` and `REQ-SAFE-001–009`,
  interpreted through accepted V2 amendments including `V2-OPS-014–017`, `V2-FILES-007`,
  `V2-AUTO-006/010/011`.
- [Product Experience](docs/product-experience.md) owns complete manual, scheduled, Run once,
  result and four-type recovery journeys; its Slice47 TARGET changes work identity/dispatch only.
- [Architecture](docs/architecture.md) owns CURRENT versus TARGET contracts;
  [Task Center specification](docs/task-center-page-spec.md) retains its eight-view/page semantics.

## Actual-code baseline and dependencies

Investigation at the immutable Base found:

- `AutomationJob` carries admission capacity, claims/heartbeats, cancellation, worker identity,
  immutable configuration/definition pins, trigger/principal/request evidence and pre-Task failures.
  `PersistentTask` owns processing/items/results but has no equivalent complete queue ownership.
- Scheduled work emits a Job and creates its Task later; real Run once atomically creates both.
  Files manual work already admits a Task early and can adopt it for confirmed execution.
- The resident Worker consumes Job, discovery, manual execution and ordinary transfer runners.
  Strategies/planners/OrganizerExecutor are shared; outer orchestration and claims are still split.
  Legacy queued organizing also re-enters CLI orchestration and extracts the Task ID from output.
- Four-type recovery already owns decisions/checkpoints/summaries. Existing recovery, metadata and
  scope continuation relations still queue Jobs and may reference later Task attempts.
- Runtime schema53 has Job identity columns in 12 tables, including due/occurrence state,
  continuation/batch relations, authorization consumption/audit, schedule audit and operational logs.
  Run queries, original-record outcomes, metrics, Dashboard, API/CLI/Web and release proofs depend on them.
- Configuration contains Job-named capacity/staleness keys. Published snapshots, digests and supported
  admitted pins must stay reproducible; deleting their parser support by search-and-replace is unsafe.

B must turn this dependency analysis into coherent Tasks and inspect any additional serialized,
notification, export or packaging references. This list is evidence, not a closed allowlist of files.

## Required outcomes

### RO-1 — one organizing Task owns scheduling and execution

One newly admitted organizing work has one stable Task identity from admission through discovery,
analysis, human waiting, execution, cooperative controls and permitted recovery. Each concrete source
has its own TaskItem, plans/checkpoint/effect evidence and corresponding Results. Recovering or
continuing that work must not mint a Job or a new top-level organizing Task. A deliberate distinct
new organizing request remains new work, with existing source-ownership and non-replay checks.

Task owns bounded queue eligibility/admission, Worker claim ownership, heartbeat/staleness,
cooperative cancellation, four-type continuation and fenced publication. Keep lifecycle, processing stage and
per-item outcome explicit and consistent; do not introduce a separately managed queue object with
its own competing lifecycle. Internal per-attempt/decision/plan evidence may remain within the Task;
it is not another operator work or scheduler. Existing safe evidence/authority records are not
redundant merely because Job is removed.

The shared scheduling capacity counts distinct organizing Tasks with admitted pending machine work
or a running Worker stage, including discovery, analysis and execution. Each Task uses at most one
slot across manual/due/Run once and permitted continuation, regardless of its item/attempt count.
Machine-timed stability waiting remains queued work. The counting boundary is:

| Situation | Capacity use |
|---|---|
| Pending machine work or an active Worker stage, including a Task with other human-blocked items | One slot for the Task |
| Entire Task waiting for a human decision/initial confirmation, with no remaining queued/claimed machine work | Zero slots; retain Task/source ownership and all evidence |
| Cancellation requested while work or an in-flight call is still active | Keep its slot until the safe boundary is acknowledged and no admitted machine work remains |
| Terminal work with no active/queued machine work | Zero slots; retain results and any uncertainty/non-replay protection |

New admission and every transition from non-queued waiting work back to machine work check
capacity atomically with queue eligibility and applicable authority consumption. Full capacity refuses
new manual/Run once work without an orphan Task or consumed authority; a due occurrence remains due,
without occurrence creation/due advance, for a normal later Scheduler tick. A refused confirmation,
analysis continuation of an existing Task preserves its waiting state, saved choices,
summary and results, publishes a bounded queue-full answer and consumes no execution authority.
The operator can explicitly retry that command when capacity is available, with normal freshness/
authority checks; refusal does not register an automatic continuation. Decision Save alone needs no
queue slot and grants no effects. An exact duplicate of already admitted work reconciles to it even
when full, without another slot. Slot release never releases durable source ownership or makes
uncertain effects replayable. Capacity remains admission control, not new worker/thread parallelism.
Move current capacity/staleness settings and actual resident adoption to the Task meaning, preserving
supported configurations, explicit overrides and immutable historical pins. Staleness is evidence,
never automatic permission to replay an effect. Ordinary operations retain their existing scope,
controls and safe runners; adapt shared integration without redesigning their queues.

### RO-2 — all triggers use one organizing application engine

Files manual submission, Scheduler due emission, saved-definition Run once and supported API/CLI
organizing enter the same application scheduling/execution engine. Scheduler directly admits a
pinned Task and commits occurrence/due-state idempotency atomically; it still does not choose media
policies or mutate Storage. Definitions and occurrence/audit evidence remain, without an independent
Job queue/state machine. Worker consumes the admitted Task and pin directly, without parsing CLI
output or invoking a parallel processing engine.

Preserve existing source-selection intent, configured filtering, attachments, stability handling,
complete-scope requirements and each entrance's limits. Sharing the engine does not erase the
manual direct-file/folder distinction or raise Run once's `min(definition itemLimit,100)` ceiling.
Ready/unstable siblings and complete traversal remain truthful; no silently executable first-N
prefix. Existing one conditional wait/re-scan in `(0,60]` seconds remains where applicable.

Manual work is admitted before business readiness and still requires exact summary/selected
confirmation before effects. Checked Enabled publication authorizes normal scheduled execution;
Run once's explicit command authorizes one saved-scope execution, including while disabled, without
schedule advancement or a second initial confirmation. Preserve current permissions, scoped intent,
live disable/removal checks and explicit overwrite/Delete/cleanup authority. No initial independent
grant/pre-analysis gate returns. Configured rule/policy selection stays in the existing pipeline.

### RO-3 — reuse four-type recovery inside the same work

Reuse Recognition, Metadata candidate/correction, Classification and Conflict decisions, checkpoints,
source validation, exact analysis/summary and explicit continuation. Decision Save/analysis grants no
mutation. Schedule/claim only the exact permitted TaskItems/remaining scope; retain successful,
ignored, skipped, failed, partial and uncertain siblings independently. Completed or uncertain
mutations never replay, consumed authority never refreshes itself, and legitimate old pins remain.

Preserve attempt/result history when a Task continues or its current aggregate changes. Original
execution outcomes/times/effects stay distinguishable from later handling; a successful follow-up
cannot rewrite the original Automation record. The Task identity stays fixed. Each file's decisions,
checkpoints, attempts and Results remain durably traceable to that Task and the exact source/version
and pin. Internal TaskItem IDs may be reused or versioned; unchanged IDs are not an acceptance
requirement. If an implementation creates a successor item ID, it must preserve the prior ID/history
and an explicit durable relation, keep affected-file counts and supported links truthful, and prevent
duplicate source ownership/effects. An ID change cannot widen scope, substitute source content or
grant authority. No new mapping/recovery subsystem is required. Pre-upgrade child Task identities
remain traceable historical evidence rather than being destroyed or silently merged.

Continuation after restart/claim loss is conditional on the existing supported control/recovery
boundary and durable proof that the remaining stage/step is safe to run, plus the normal pin/source/
authority/fence rechecks. If a Storage mutation was dispatched but its outcome was not durably proved,
retain the affected step as uncertain, prevent replay and preserve factual inspection evidence.
Timeout, lease expiry, process restart or a missing Result alone is not proof that nothing happened.
Safe unaffected siblings retain only their existing permitted actions. No seamless automatic
continuation at every possible crash point is promised; this Slice adds no new technical recovery
or attachment-only replay path. No fifth business recovery type, generic technical-failure Web recovery,
cross-Task bulk mutation, arbitrary historical Reprocess or universal rollback is introduced.

### RO-4 — preserve data and safely remove the Job schema

Provide a versioned, repeatable, failure-atomic migration from the actual schema53 Base, covering
fresh initialization, reopen and the supported upgrade path. Preserve every supported historical
Task/TaskItem/Result, plan/attachment/effect/checkpoint, definition/occurrence, control/decision,
request identity, pin, authorization consumption, audit/log and relevant relation. Retired
Scan/Preview/FileIndex products receive no restored execution/compatibility layer.

No existing persisted Job row is discarded merely because its command is unknown or retired.
Preserve such residual rows as non-executable historical evidence with original kind/state and
provenance; never relabel them as organizing or recreate a retired product to display them.

Use exact durable relationships: an explicitly linked Job migrates into its existing work; an
unlinked queued or pre-start historical Job must remain represented by a Task with its actual
admission/failure evidence and no invented per-item effects. Preserve old identifiers as bounded
migration provenance/references where needed. Multiple historical Tasks/attempts retain their own
identities and original outcomes. Missing, conflicting or unprovable links cannot be guessed from
names/timestamps/current Active, silently dropped or converted into execute authority.

Supported provably unstarted work remains runnable with its original intent/pin after migration.
Previously entered, completed, partial or uncertain work retains safe controls/inspection and is
never blindly reset to Pending. Upgrade must use the deployment's safe service-quiescence/fencing
boundary; mixed incompatible old/new writers cannot claim, publish or start new effects against
the migrated authority. Do not interrupt an in-flight Storage call or pretend migration undoes it.
Failure leaves the previous durable authority usable/intact, without a half migration or premature
schema marker. Prove backup/upgrade/reopen behavior on isolated copies, never user databases/media.

After verified migration, remove the independent Job table/indexes, redundant Job-only identity
columns/foreign keys, repositories/models/services/dispatch, APIs/CLI commands and frontend models.
No live Job compatibility executor, dual queue/write or renamed Job store may remain. Necessary
legacy configuration parsing and bounded read-only identifier resolution are allowed solely to
preserve supported pins/history; they cannot create Jobs, introduce work or widen authority.

### RO-5 — complete operator and administrative journeys without loss

Task Center keeps its eight organizing views, consistent authorized filtering/counts/paging and
four-type Attention union. Admission/pre-start failures are now Task evidence; one organizing work
counts once. Current work state, stage, each item's results and original execution outcomes remain
truthful. Files keeps exact request reconciliation/return, initial confirmation and ordinary-file
local progress on both library kinds; no extra work picker/global monitoring block is added.

Automation keeps definitions, due/calendar/latest metrics, enablement/Run once, read-only original
execution records and consumed settings. Records preserve original outcome filtering, actual times,
concise failure/next-step presentation and no later-handling controls. Dashboard, task-scoped logs,
JSON exports, health/readiness, CLI and API use Task identities/behavior. Retained old deep links or
identifiers resolve read-only to proved Task/history or bounded unavailable/denied evidence; they
never execute, infer a new identity or require the removed Job collections. Remove Job collection,
submission, cancellation and stale-requeue APIs/commands; retained capabilities use Task equivalents
with unchanged permissions and safe-repeatability limits.

## Required surfaces and boundaries

Domain Task/TaskItem/Result/queue ports; application admission/engine/Worker/Scheduler and four-type
recovery; runtime SQLite/schema migration, source locks and claims; authorization/audit/log/outbox
relations; managed setting parsing/publication/adoption; API/CLI/Web projections and consumers;
Task Center/Files/Automation/Dashboard/health/export; source-external wheel and Docker
startup/restart/upgrade/security proofs and operator upgrade documentation.

Out of scope: new providers or Storage/media commands, distributed scheduling/database, process
supervision redesign, new parallelism/overlap/backfill policies, unbounded discovery, MediaLibrary
organizing, new auth/Secret Store, wholesale UI redesign/V1 cutover, retired product restoration,
history deletion/retention, new recovery types, automatic uncertain replay and universal rollback.
Necessary integration in existing ordinary-file/notification consumers preserves their behavior;
it does not authorize a new global operation/recovery center or unrelated refactors.

## Safety invariants

Preserve backend RBAC, exact explicit scoped intent, bounds and Storage confinement, immutable
admitted snapshots, atomic source ownership, capability/conflict validation, claim/lease/fences,
current authority before each unperformed effect, only-OrganizerExecutor mutation, zero-mutation
reads/analysis, independent results/attachments/audit/redaction and completed/uncertain non-replay.
RecognitionType C remains C with NamingPolicy A and ClassificationPolicy A. No FFmpeg/FFprobe.

## Acceptance

| ID | Required proof |
|---|---|
| AC-1 | Manual file/folder/mixed submission, due occurrence and Run once each admit exactly one stable organizing Task before business readiness and preserve source scope/limits/pins and exact request readback. |
| AC-2 | Manual/due/Run once and permitted continuation share one distinct-Task bound under concurrency; simultaneous Scheduler ticks admit one Task per occurrence with atomic due advance. Prove one slot across multiple items/attempts, zero for wholly human-waiting work, one while other machine work or an unacknowledged active call remains, and atomic re-entry. Full capacity preserves existing waiting work and saved choices/results without authority consumption or automatic continuation; new admission has no orphan, an existing duplicate still reconciles, and a refused due tick leaves its occurrence/due state unchanged. |
| AC-3 | Concurrent Workers claim at most one effective owner; stale-owner heartbeats/item/result/aggregate writes and controls cannot defeat current ownership. Capacity release follows the documented safe boundary; human waiting is not busy-loop claimed or used to release source ownership. Readiness is Task-based and read-only. |
| AC-4 | All organizing entrances use the shared application engine and production pipeline/Executor; no Job queue, CLI-output Task extraction or second engine remains. |
| AC-5 | Files manual exact summary/selected confirmation, scheduled enable intent and disabled Run once follow existing distinct authority semantics; denied/stale/unknown requests, disable/remove/permission-loss races fail safely. |
| AC-6 | Filtering, primary/attachment identity, configured limits, complete bounds and real stability are preserved; ready/unstable/empty/unreadable/overflow outcomes remain distinct, with no first-N execution or fabricated success. |
| AC-7 | Four business decision → analysis → exact summary → selected continuation journeys finish inside the same newly admitted Task after refresh/restart. Assert exact per-file source/version/pin and durable item/attempt/result lineage, accurate counts and supported links, rather than mandatory equality of internal TaskItem IDs. Mixed batches keep independent accepted/refused results and no fifth recovery type. |
| AC-8 | At supported cancel/restart/claim-loss and four-type continuation boundaries, prove safe remaining stages can continue only with durable safety evidence and normal authority/fence checks. Inject interruption before mutation dispatch and after dispatch before durable outcome proof: the latter remains uncertain and cannot replay, even after timeout/lease expiry/restart. Preserve completed/ignored siblings, pins and consumed authority; technical history stays read-only in V2. Do not require seamless automatic continuation at every crash point or add a new recovery path. |
| AC-9 | Genuine Base schema53 fixtures migrate/reopen with linked/unlinked Jobs, every supported status, pre-start failures, old continuation chains, request/due uniqueness, consumed/revoked authority and exact audit/log/attachment/result identity intact. Residual unknown/retired Job rows survive as non-executable history with their original meaning. |
| AC-10 | Failure injection proves migration rollback, unchanged prior authority/schema marker and safe repeat/reopen; quiescence/schema/fence checks reject incompatible writers and never restart entered uncertain work automatically. |
| AC-11 | Fresh and upgraded databases have no live Job table/index/FK/queue; source/wheel/container expose no redundant Job domain/repository/dispatch/API/CLI/Web path. Provenance/parser exceptions are bounded/read-only, not a compatibility executor. |
| AC-12 | Existing supported configuration and immutable pins remain readable with unchanged meaning/digests; Task capacity/staleness and Worker/Scheduler cadence/override/adoption semantics are truthful. |
| AC-13 | Eight-view Task Center counts, filters, cursors, detail, four-type union and recovery-complete projection remain consistent across all pages/restart; ordinary work/analysis-only preparation remains outside its organizing population. |
| AC-14 | Automation definitions/Run once/metrics/latest and original records retain independent truth; old failures/times/known effects survive later recovery, filtering and paging. Original execution counts once and recovered work creates no second original run. |
| AC-15 | Files exact task/preparation/unknown readback, ordinary local operations on both library kinds, Dashboard, scoped logs/audit/JSON, API/CLI/health and proved old-link resolution work without Job collections or new authority. |
| AC-16 | RBAC, source ownership/confinement, zero-mutation reads/analysis, C→A identity, explicit destructive permission, immutable pins, attachments and completed/uncertain non-replay pass automated coverage. |
| AC-17 | Real Python/API/SQLite/Worker/Scheduler browser journeys using built assets, desktop/narrow inspection, installed wheel and Docker fresh/restart/upgrade/security gates establish the same Task lifecycle and preserved records. |
| AC-18 | B supplies applicable full T4 results and exact Base..Head evidence; unavailable gates remain pending/disclosed. A independently reviews the whole Slice before PASS / CLOSED and CURRENT reconciliation. |
| AC-19 | Organizing exposes no Pause/resume-from-pause in Web/API/CLI or live dedicated dispatch. Old requests are refused without effects; historical paused work retains exact evidence and safe cancellation/inspection. Ordinary-file Pause/Resume and four-type organizing continuation still work. |

## Validation and handoff

B plans coherent architecture/user-behavior units from actual code; this Contract is not a Task
breakdown. Developer runs new/changed/directly affected tests and hands off coherent checkpoints;
B owns full regression/acceptance and the final Closure Packet under workflow §6. Required T4
coverage includes its shared Python/Web/static/examples/package/security gates plus AC-specific
migration/concurrency/authority/restart/native proofs. Reuse existing test infrastructure and temporary
roots/fakes/local servers; meaningful migration/reopen/effect assertions cannot be replaced by string
searches or mock-only UI tests. Do not weaken tests to permit Job removal.

Use the explicit capacity-state/queue-full cases and supported interruption boundaries above as
acceptance scenarios. File lineage/history/counts and non-replay are the result obligations; keeping
all internal item IDs equal or enumerating every theoretical crash point is not a separate gate.

The preceding investigation ran 138 core Task/Automation/authority/recovery tests and 45
original-record/log-isolation tests on the Base: 183 passed, with database ResourceWarnings in the
first run. These are pre-refactor observations, not final acceptance; no full/Web/container result
is claimed. A scope checkpoint runs relevant document/link/governance checks only. Implementation
Head, Closure Packet and A Final Review are not yet available.

## Workspace and role record

Repository `/Users/songzhidong/mediaflow`, branch `main`, starting HEAD equals the immutable Base.
No pre-existing tracked edits; pre-existing untracked OS/log/reference/image/archive artifacts remain
unrelated and unstaged. Workspace/Git are writable. Private runtime/configuration/media are not read
or used for validation. No push/history rewrite is authorized or performed.

The user grants A scope authority; earlier B investigation is disclosed. No implementation,
Task review or A Final Review is conducted by this scope action. Roles remain separate under the
workflow; no sub-agents are requested or spawned. `TASK.md` remains NO ACTIVE IMPLEMENTATION TASK
until B plans against the committed Contract. No original closed Slice fact is changed.
