# Slice 47 — Unified Task Scheduling and Organizing Execution

```text
Slice ID: 47
Name: Unified Task Scheduling and Organizing Execution
Owner: A — Slice Owner / Architect / Final Reviewer
Status: FIX REQUIRED
Base SHA: 5144ab1fc2344b06194969cc2c496835729664c0
Implementation Head: 5c808d4a67bedfbafb71d88a1ffa8d3480ef5316
Implementation Head Acceptance: REVIEWED CANDIDATE — NOT ACCEPTED
Working Branch: main
Development Authorization: USER-REQUESTED REFACTOR; A SCOPE AUTHORITY — 2026-10-30
Risk: High
Final Test Level: T4
Next Action: TASK47.6 PLANNED FOR THREE SYSTEM SETTINGS AND STALE-AGE REMOVAL; DEVELOPER STOPPED; FRESH ACCEPTANCE PENDING
```

## Authority and accepted baseline

[AGENTS.md](AGENTS.md) and [Development Workflow](docs/development-workflow.md) govern scope,
roles, checkpoints, testing and closure. The user requested Job removal and unified Task execution,
then explicitly authorized A scope authority on 2026-10-30. This checkpoint selects the new Slice;
it is neither implementation nor final acceptance. On 2026-11-03 the user explicitly authorizes
the agent acting as B to exercise A authority for the Contract and related documents, including
settings and the confirmed exclusion of old-task and cross-version upgrade support.
This role exception covers scope/document checkpoints only, not independent A Final Review,
implementation, acceptance or delegation.

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
- 删除“失效判定时间”参数，其余三项放到现有系统设置页，按实际消费者说明作用范围。
  所有整理入口共享系统整理额度；Worker 轮询覆盖共享后台工作，Scheduler 只检查自动化到期。
  保留现有心跳、租约/续约和外部调用超时判断，不新增无进展提示或总运行超时。

## User-authorized settings-scope amendment — 2026-11-03

The user chooses **全部放到系统设置**, then **把失效判定时间这个参数删掉，保留现在的判断逻辑**,
and authorizes this A document action. This replaces the 2026-11-02 Automation-only scope and the
intermediate four-setting/no-progress-observer plan. The earlier CLI/Web Save 1025 failures remain
factual. Range correction alone does not complete the new settings journey.

- **System entry and publication:** use the existing System Settings page as the ordinary editor
  for three runtime settings. Remove Automation's settings tab/form and duplicate ordinary editors;
  old settings links navigate safely to System Settings. Reuse managed checked publication and the
  existing focused API; no second store or new settings page. A three-field Save preserves unrelated
  Drafts/configuration, distinguishes published/adopted/pending/override, and starts no media work.
- **Shared organizing capacity:** `automation.maximumActiveJobs` remains an integer **1–10000**,
  labelled as the system organizing queue limit, not thread/file parallelism. Files, ordinary
  direct CLI/API/remote-source organizing, due/Run once and same-Task machine-work re-entry share
  one atomic allowance. Fullness refuses either origin with truthful recovery, not a source-label
  bypass. Ordinary asynchronous copy/move/delete keep their existing admission/queue rules; they
  do not newly consume organizing capacity.
- **Actual polling consumers:** `automation.workerPollSeconds` controls the shared Worker's idle
  work checks, including organizing and both library kinds' ordinary asynchronous copy/move/delete.
  `automation.schedulerPollSeconds` controls only checks for due Automation definitions. It does not
  gate manual/Run once submission, replace definition Cron/timezone/interval, or control notifications.
  Keep safe-boundary adoption, truthful per-instance evidence, explicit overrides and independent
  heartbeat/configuration rechecks. No promise of fixed task completion time or new parallelism.
- **Remove the unused parameter:** retire `automation.staleJobAgeSeconds` from editable contracts,
  effective runtime models/arguments/readback and new defaults. Existing immutable documents may
  retain the old key and remain readable with it ignored; do not rewrite their digest or admitted
  pins, or require operators to clean historical JSON before using the remaining settings.
  Field-edit commands reject the retired parameter without publication. Preserve current Worker
  heartbeat staleness, per-runner claim expiry/renewal and Provider/Storage call timeouts. Add no
  no-progress observer, whole-Task timeout, automatic failure/cancellation/requeue/uncertain replay.
- **One engine and preserved safety:** keep one Task lifecycle/repository/scheduling authority,
  claim/fence protocol, organizing engine and Executor. Origin remains backend-proven provenance
  for intent/audit/definition semantics, not separate capacity/cadence policy. Preserve atomic
  capacity/authority/source checks, due uniqueness, waiting/cancellation settlement, exact manual
  confirmation, immutable execution pins, independent results and non-replay. Notification policy,
  synchronous browsing/rename/mkdir and ordinary queues are not redesigned.

`V2-TASK-011` and AC-12/26 record this TARGET, not delivered or accepted behavior. Slice Base and
reviewed Implementation Head remain unchanged. Task47.6 keeps ID and true Base
`c8657032dae768d93b12387a5e58db502e23a7ee`; B must align its existing three-setting plan with this
committed Contract and recheck all outcomes. Developer remains stopped by the user; this document
checkpoint does not start implementation or accept the stopped work. Final T4 and an independent
A Final Review remain required.

## User-authorized scope amendment — 2026-10-31

The user explicitly removed Pause and resume-from-pause from organizing AND ordinary-file
operations, and confirmed there are no currently paused organizing Tasks. This scope action uses
the previously granted A scope authority; the same agent acts as B, disclosed here. It is a Contract
amendment, not implementation, Task PASS or A Final Review. Original Slice Base/history stay intact.
No A Final Review of this Slice is performed by this agent.

Manual/due/Run once/API/CLI organizing and ordinary-file operations (including Copy/Move) expose
cancellation, not Pause or resume-from-pause. Remove their Web/API/CLI actions, availability projections
and dedicated live dispatch; hiding buttons alone is insufficient. Shared routes reject retired
commands without effects; do not leave a callable back door. Cancellation stops unperformed work
at a safe boundary without interrupting in-flight calls or undoing completed effects.

Four-type decision → analysis → summary → explicit continuation remains; it is not resume-from-pause.
Human waiting, timed stability waiting, claim/fence safety stops, independent effects/results and
uncertain-effect inspection/non-replay remain. No new pause migration, restoration or compatibility
executor is required given the user's confirmed absence of paused organizing work. Existing historical
data remains readable and is never deleted, falsely relabelled or automatically replayed by retirement.
This narrowly authorizes removal of ordinary-file Pause/Resume, not a redesign of those operations.
It supersedes Pause/resume obligations in REQ-TASK-004, V2-OPS-007 and affected CURRENT/TARGET prose;
all other permissions, cancellation, authority, confinement and evidence guarantees remain.

## User-authorized scope amendment — 2026-11-02

The user explicitly adds source-dependent handling of prior `failed` / `partial` organizing
items and retirement of the independent CLI `tasks retry-failed` entrance to this Slice, and
requests Task planning only. This is A's scope checkpoint; the same agent then acts as B planner,
disclosed here. It is no implementation, independent Task review or A Final Review. The original
Slice Base and Tasks47.1–47.4 acceptance remain unchanged. Task47.4 passed B at
`383d8834787674675183f4b251d9dfd26a5dc511..dd3f1c25126cd574d8df293d0163131bc6cb9ad6`;
its packet is preserved in `980ce42a977b5bc20cf8426dbaf5a232f46cf22b:TASK.md`. The new outcome
must be delivered before the enlarged Slice can become READY FOR A REVIEW.

- Shared per-source TaskItem admission uses backend-proven trigger/context and the latest formal
  organizing outcome for the same observed source version. Definition due work excludes that
  source only when this outcome is `failed` or `partial`. A later manual organizing success means
  an earlier failure no longer causes this exclusion; normal filtering/conflicts still apply.
  Run once uses the same definition-derived exclusion,
  preserving its existing one-click initial execution. Report the exclusion honestly; a scope
  containing only historical exclusions is not a newly organized-media success or a scan failure.
- A deliberate new manual organizing request does not exclude a file merely for prior `failed` /
  `partial` history, including completed steps or historical unknown effects. Files direct, folder
  and mixed selections reach the existing exact plan summary with a conspicuous per-file history
  warning before its ordinary selected execution confirmation. The user checks source, target and
  Storage effects and explicitly starts new work; no extra verification page, routine checkbox,
  CLI recovery command or automatic operation-completion detector is selected.
- This is a narrow explicit-intent amendment to the old blanket manual uncertain-history refusal,
  not automatic replay or resumed execution of an old item. New work receives its own current
  configuration pin, exact source/plan and authority. Old recorded outcomes, completed steps,
  Results/pins/effect certainty and original Automation outcome/time remain factual. Necessary
  lock/claim/fence and current handling-state changes are permitted, without rewriting that history.
  Historical unknown effects do not become verified or
  acquire fresh old authority merely because a new request was confirmed.
- A concrete file still queued/processing without its own terminal outcome retains normal source
  ownership. A file item already recorded as `failed` or `partial` is history for this manual rule:
  neither its parent Task's running status nor a historical unknown marker alone reclassifies it
  as an active file or permanently vetoes new manual organizing. No proof of remote completion is
  required from this Task or the user. Necessary application-owner fencing and
  exact per-file lock handoff preserve siblings and prevent a superseded Worker starting later
  steps or rewriting old results. Already dispatched remote calls cannot be stopped or proved
  finished by a Web warning; disclose that limitation and leave their factual evidence intact.
- Existing directories, targets and copy remnants use the normal plan/capability/Hash/conflict
  and explicit destructive-effect rules. Do not add special residual deletion, attachment-only
  replay, historical-step restoration or universal rollback. Other old statuses are not newly
  auto-excluded under this amendment. Four-type continuation inside its original Task is not a
  new automatic discovery and retains its existing decision/analysis/summary/confirmation path.
- Remove `tasks retry-failed` parser/help/dispatch and exclusive execution/analysis helpers;
  unsupported old input fails normally with zero work/effects. Keep ordinary `organize`, scoped
  analysis and shared four-type decisions/ignore/audit. Apart from retiring retry-failed and the
  shared normal manual-organizing adjustment, ordinary CLI/remote keep their existing source and
  authorization semantics; add no CLI warning requirement, new remote category, consent field or
  history-refusal rule. The conspicuous new warning is required in Web Files only.

The user confirms that old tasks and cross-version upgrades remain excluded; V1 is unsupported.
The supported persistence journey is fresh initialization → submit new work → same-version
reopen/restart → inspect or safely continue that work. Preserve its history, permissions, pins,
audit and data integrity, including failed/partial source history used by RO-6. No old-Job/old-task
migration, import, takeover, cross-version upgrade/rollback or mixed-version writer interoperability
is required. Existing immutable configuration containing retired fields remains readable as specified
above; this does not select old-task upgrade support. The outcomes, surfaces and acceptance below
apply this exclusion directly; no product validation is claimed by this scope clarification.
Accepted43–46 and Task47.4 are not retroactively re-reviewed or relabelled by this amendment.

The user's planning correction confirms latest formal outcome, not any-ever failure, as the
criterion. Task47.5 stays PLANNED with the same immutable Task Base; A checkpoints these narrower
terms before B updates its draft. This correction adds no implementation or review acceptance.

### Amendment traceability

`V2-TASK-008–010` in [V2 Requirements](docs/v2-requirements.md) owns the durable new rules.
This section and RO-6 supersede affected blanket history-refusal/CLI retry wording in RO-1/2/3/5,
the Safety invariants and AC-6/8/15/16 only for deliberate new manual work. Automatic replay of an
unresolved old attempt and same-Task uncertain replay remain forbidden; new automatic admission
uses the latest-formal-outcome rule above. The new TARGET journey/architecture sections distinguish this
authorized work from accepted CURRENT delivery.

## Requirements and journeys

- Authorized TARGET amendments `V2-TASK-001–011` in [V2 Requirements](docs/v2-requirements.md).
  It supersedes the V2 Job-object requirement in `REQ-TASK-008`, Job-emitting `REQ-SCHED-003`,
  Job-specific queue/readiness wording and Job/Task merging in the affected V2 Operations/Automation
  contracts. Frozen V1 meaning and accepted historical facts remain in Git/current baseline sections.
- Preserve `UX-001–007/010`, `REQ-TASK-002–010`, `REQ-SCHED-001/004/005`, applicable
  `REQ-RECOVERY-*`, `REQ-RESULT-*`, `REQ-API-*`, `REQ-DEPLOY-*` and `REQ-SAFE-001–009`,
  interpreted through accepted V2 amendments including `V2-OPS-014–017`, `V2-FILES-007`,
  `V2-AUTO-006/010/011`.
- [Product Experience](docs/product-experience.md) owns complete manual, scheduled, Run once,
  result and four-type recovery journeys; its Slice47 TARGET includes the explicit settings-scope,
  history and control amendments above.
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

Within its applicable scheduling policy, capacity counts distinct organizing Tasks with admitted
pending machine work or a running Worker stage, including discovery, analysis and execution.
Each Task uses at most one applicable slot across its stages and permitted continuation,
regardless of its item/attempt count. The system organizing allowance is shared by manual,
due and Run once work and same-Task machine-work re-entry, as defined in the settings amendment.
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
Move the remaining three settings into System Settings with the consumer scopes above, preserving
explicit overrides and immutable pins. Retire the unused stale-age parameter; preserve existing
heartbeat/lease/call-timeout judgments and uncertain-effect protection. Ordinary operations share
the Worker's idle cadence but retain their existing admission rules, controls and safe runners;
do not redesign their queues or count them against organizing capacity.

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
grant authority. No new mapping/recovery subsystem is required. Earlier attempts inside supported
same-version work retain their identities, relations and original outcomes.

Continuation after restart/claim loss is conditional on the existing supported control/recovery
boundary and durable proof that the remaining stage/step is safe to run, plus the normal pin/source/
authority/fence rechecks. If a Storage mutation was dispatched but its outcome was not durably proved,
retain the affected step as uncertain, prevent replay and preserve factual inspection evidence.
Timeout, lease expiry, process restart or a missing Result alone is not proof that nothing happened.
Safe unaffected siblings retain only their existing permitted actions. No seamless automatic
continuation at every possible crash point is promised; this Slice adds no new technical recovery
or attachment-only replay path. No fifth business recovery type, generic technical-failure Web recovery,
cross-Task bulk mutation, arbitrary historical Reprocess or universal rollback is introduced.

### RO-4 — preserve same-version work and remove the live Job schema

Fresh initialization creates the Task-owned runtime schema without an independent Job table/index
or redundant Job-only identity column/foreign key. Same-version reopen/restart preserves newly
admitted Task/TaskItem/Result, plan/attachment/effect/checkpoint, definition/occurrence,
control/decision, request identity, pin, authorization consumption, audit/log and relevant relation.
Queued/pre-start, human-waiting, active/interrupted and terminal work retain their actual state
and evidence. Retired Scan/Preview/FileIndex products receive no execution/compatibility layer.

Readback and permitted continuation use exact durable Task/item/attempt relationships, not guessed
names/timestamps/current Active. Pending work retains its original intent/pin under existing safe
restart rules; entered, completed, partial or uncertain work is never blindly reset to Pending.
Keep existing schema-readiness and claim/fence checks. Initialization/reopen failure must not
present an incomplete database as ready, change existing durable work or grant execution authority.
Use isolated fresh/same-version databases, never user databases/media, for these checks.

Remove live Job repositories/models/services/dispatch, APIs/CLI commands and frontend models as
well as the redundant schema. No Job compatibility executor, dual queue/write or renamed Job store
may remain. Read existing immutable configuration without rewriting revisions/digests/pins; this
does not require converting old Job rows, restoring old tasks or proving an old-schema upgrade.
The exclusion does not authorize clearing user data or rewriting prior accepted implementation facts.

### RO-5 — complete operator and administrative journeys without loss

Task Center keeps its eight organizing views, consistent authorized filtering/counts/paging and
four-type Attention union. Admission/pre-start failures are now Task evidence; one organizing work
counts once. Current work state, stage, each item's results and original execution outcomes remain
truthful. Files keeps exact request reconciliation/return, initial confirmation and ordinary-file
local progress on both library kinds; no extra work picker/global monitoring block is added.

Automation keeps definitions, due/calendar/latest metrics, enablement/Run once and read-only original
execution records. System Settings owns the three runtime settings; Automation's former settings
links navigate there without publication. Records preserve original outcome filtering, actual times,
concise failure/next-step presentation and no later-handling controls. Dashboard, task-scoped logs,
JSON exports, health/readiness, CLI and API use Task identities/behavior. Retained links or
identifiers resolve read-only to proved same-version Task/history or bounded unavailable/denied
evidence; no old-Job mapping layer is required. They never execute, infer a new identity or require
the removed Job collections. Remove Job collection,
submission, cancellation and stale-requeue APIs/commands; retained capabilities use Task equivalents
with unchanged permissions and safe-repeatability limits.

### RO-6 — source-dependent history admission and one new-organizing journey

Apply the 2026-11-02 amendment at each concrete source's shared Task admission, including files
found after a directory Task was created. Automation due/Run once excludes versions whose latest
formal organizing outcome is failed/partial before Provider work or effects; a later manual success
removes this failure-based exclusion without deleting the earlier result. Manual selection reaches
a backend-generated exact summary containing the applicable result/effects warning and can execute
a newly confirmed legal plan.
Compare real Storage/path/version across library bindings, finding the latest applicable formal
outcome from the full matching population, not names, the latest arbitrary page of Results, or the
enclosing Task's aggregate. Recheck relevant summary evidence and ownership atomically
at relevant admission/confirmation boundaries. A truly replaced source is new content; missing or
incomparable version evidence cannot silently erase an applicable failed/partial history warning.
Use existing Task/TaskItem/Result/discovery/authorization evidence, no global FileIndex replacement
or new queue/recovery product. Remove CLI retry-failed without dropping shared four-type behavior.

## Required surfaces and boundaries

Domain Task/TaskItem/Result/queue ports; application admission/engine/Worker/Scheduler and four-type
recovery; runtime SQLite fresh initialization/same-version persistence, source locks and claims;
authorization/audit/log/outbox relations; managed setting parsing/publication/adoption;
API/CLI/Web projections and consumers;
Task Center/Files/Automation/System Settings/Dashboard/health/export; source-external wheel and Docker
fresh startup/same-version restart/security proofs and applicable startup/restart operator guidance.

Out of scope: new providers or Storage/media commands, distributed scheduling/database, process
supervision redesign, new parallelism/overlap/backfill policies, unbounded discovery, MediaLibrary
organizing, new auth/Secret Store, wholesale UI redesign/V1 cutover, retired product restoration,
history deletion/retention, new recovery types, automatic uncertain replay and universal rollback;
old-task/Job migration or takeover, cross-version upgrade/rollback and mixed-version interoperability.
Necessary integration in existing ordinary-file/notification consumers preserves their behavior except
for the explicitly authorized ordinary-file Pause/Resume retirement and shared Worker idle cadence;
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
| AC-2 | One Task scheduling authority enforces the shared system organizing bound atomically across manual, due/definition Run once and same-Task machine-work re-entry; either origin's occupancy can fill it. Ordinary asynchronous file work keeps its existing admission rules. Simultaneous Scheduler ticks admit one Task per occurrence with atomic due advance. Prove one slot across multiple items/attempts, zero for wholly human-waiting work, one while other machine work or an unacknowledged active call remains, and atomic re-entry. Full capacity preserves waiting work/choices/results without authority consumption or automatic continuation; no orphan, duplicate still reconciles, refused due remains due. |
| AC-3 | Concurrent Workers claim at most one effective owner; stale-owner heartbeats/item/result/aggregate writes and controls cannot defeat current ownership. Capacity release follows the documented safe boundary; human waiting is not busy-loop claimed or used to release source ownership. Readiness is Task-based and read-only. |
| AC-4 | All organizing entrances use the shared application engine and production pipeline/Executor; no Job queue, CLI-output Task extraction or second engine remains. |
| AC-5 | Files manual exact summary/selected confirmation, scheduled enable intent and disabled Run once follow existing distinct authority semantics; denied/stale/unknown requests, disable/remove/permission-loss races fail safely. |
| AC-6 | Filtering, primary/attachment identity, configured limits, complete bounds and real stability are preserved; ready/unstable/empty/unreadable/overflow outcomes remain distinct, with no first-N execution or fabricated success. |
| AC-7 | Four business decision → analysis → exact summary → selected continuation journeys finish inside the same newly admitted Task after refresh/restart. Assert exact per-file source/version/pin and durable item/attempt/result lineage, accurate counts and supported links, rather than mandatory equality of internal TaskItem IDs. Mixed batches keep independent accepted/refused results and no fifth recovery type. |
| AC-8 | At supported cancel/restart/claim-loss and four-type continuation boundaries, prove safe remaining stages can continue only with durable safety evidence and normal authority/fence checks. Inject interruption before mutation dispatch and after dispatch before durable outcome proof: the latter remains uncertain and cannot replay, even after timeout/lease expiry/restart. Preserve completed/ignored siblings, pins and consumed authority; technical history stays read-only in V2. Do not require seamless automatic continuation at every crash point or add a new recovery path. |
| AC-9 | Fresh initialization → new-work admission/processing → same-version reopen/restart preserves Task/item/attempt identity and relations, pre-start failures, four-type waiting/continuation, request/due uniqueness, consumed/revoked authority and exact pins/audit/log/attachment/results. Failed/partial history remains usable by RO-6. No old-task or Base schema53 Job migration proof is required. |
| AC-10 | Applicable initialization/reopen failure checks preserve existing durable state and do not authorize work from an unavailable or incomplete database. Existing schema/claim fences remain effective; restart never automatically replays an entered uncertain effect. No cross-version upgrade/rollback or mixed-version interoperability proof is required. |
| AC-11 | Fresh and same-version reopened databases have no live Job table/index/FK/queue; source/wheel/container expose no redundant Job domain/repository/dispatch/API/CLI/Web path. Immutable configuration readability does not retain a Job executor or require old-task conversion. |
| AC-12 | Supported configuration and immutable pins remain readable without changing stored revisions/digests. Under V2-TASK-011, System Settings owns the three runtime fields: shared organizing capacity 1–10000, shared Worker idle poll and Automation-due Scheduler poll. Remove staleJobAgeSeconds from editable/effective/default contracts; existing immutable documents containing it remain readable with the value ignored. Keep invalid-input refusal, explicit overrides, truthful actual consumption, current heartbeat/lease/call-timeout logic and uncertain-effect protection. |
| AC-13 | Eight-view Task Center counts, filters, cursors, detail, four-type union and recovery-complete projection remain consistent across all pages/restart; ordinary work/analysis-only preparation remains outside its organizing population. |
| AC-14 | Automation definitions/Run once/metrics/latest and original records retain independent truth; old failures/times/known effects survive later recovery, filtering and paging. Original execution counts once and recovered work creates no second original run. |
| AC-15 | Files exact task/preparation/unknown readback, ordinary local operations on both library kinds, Dashboard, scoped logs/audit/JSON, API/CLI/health and supported links work without Job collections or new authority. Retained links use proved same-version Task/history or bounded unavailable/denied evidence, without an old-Job mapping requirement. |
| AC-16 | RBAC, source ownership/confinement, zero-mutation reads/analysis, C→A identity, explicit destructive permission, immutable pins, attachments and completed/uncertain non-replay pass automated coverage. |
| AC-17 | Real Python/API/SQLite/Worker/Scheduler browser journeys using built assets, desktop/narrow inspection, installed wheel and Docker fresh/same-version restart/security gates establish the same Task lifecycle and preserved new-work records. Old-task migration and cross-version upgrade gates are excluded. |
| AC-18 | B supplies applicable full T4 results and exact Base..Head evidence; unavailable gates remain pending/disclosed. A independently reviews the whole Slice before PASS / CLOSED and CURRENT reconciliation. |
| AC-19 | Organizing and ordinary-file operations expose no Pause/resume-from-pause in Web/API/CLI or dedicated live dispatch. Old requests are refused without effects; safe cancellation and four-type organizing continuation still work. No paused-organizing migration/restoration system is required; preserve existing readable history and non-replay. |
| AC-20 | Due and definition Run once use shared per-source admission: exclude only when the same version's latest formal organizing outcome is failed/partial, including zero-effect failure and after restart. Later manual success removes this failure-based exclusion; earlier results remain. Free siblings proceed. Exclusions are durable/readable and do not fabricate new media success, Attention problems or first-N scope completeness. |
| AC-21 | Manual direct/folder/mixed selection of failed/partial sources, including partial directories/copy remnants and historical unknown effects, reaches the real existing summary with clear per-file history/effects warning before selected confirmation. Current pinned new plans execute through normal conflict/capability/destructive authority, with no new recovery page or mandatory extra operator chore. |
| AC-22 | Find the latest applicable formal organizing outcome by canonical Storage/path and comparable version across library bindings, before limiting display. Cover matching history beyond recent pages, failed→manual success, mixed results, analysis-only/non-organizing records, genuine replacement and unknown versions. A late predecessor publication cannot masquerade as a newer organizing attempt. Reads and warnings have zero Provider/media effects. |
| AC-23 | Backend source checks distinguish file items with no terminal outcome from items already failed/partial; parent Task running or historical unknown markers alone cannot block the latter's new manual request. Necessary atomic application fencing/lock/current-state changes preserve old outcomes/Results/pins/steps/unknown evidence and siblings, and do not claim a remote call stopped. Normal source/plan/permission/queue/request checks remain; an unrelated history append alone adds no re-confirmation chore. |
| AC-24 | No live retry-failed parser/help/dispatch/exclusive helpers remain in source, clean wheel or image; documentation and negative-test literals may remain. Old input stops without Task/Provider/Storage/authority effects. Normal CLI/remote source/authority semantics, organize/analysis and same-Task four-type continuation/ignore remain; no new CLI warning or remote history gate is required. |
| AC-25 | Real V2 Files/API/SQLite/Worker desktop/narrow journeys prove warning → normal confirmation → actual new organize effects; scheduled and Run once probes prove exclusion/free siblings/no-work truth. Old Results/pins/unknown effects and original Automation time/outcome stay immutable. B supplies applicable T4/native/packaging/restart validation for RO-6 before whole-Slice A review. |
| AC-26 | System Settings three-field Save/readback at capacity 1/1025/10000 reaches actual consumers; Automation no longer has a settings tab/form and old links safely navigate to System Settings. Prove shared organizing allowance in both directions between manual and due/Run once, with atomic full/refusal/release/explicit retry and same-Task re-entry preserving choices/results/pins/authority. Prove the shared Worker poll also advances both library kinds' ordinary asynchronous copy/move/delete without moving them into organizing capacity; Scheduler poll only checks Automation due definitions. Prove retired-parameter absence from editable/effective/default settings, zero-publication refusal of its field edits, readable unchanged existing snapshots and preserved heartbeat/lease/call-timeout/non-replay behavior. Use real System Settings Save → Files → exact summary/normal confirmation → Storage effects, actual resident adoption/override and same-version restart; B supplies affected/T4/package evidence. No 10000-task load test, fixed timing/DOM/internal layout assertion, no-progress observer, second queue or new settings page. |

## Validation and handoff

B plans coherent architecture/user-behavior units from actual code; this Contract is not a Task
breakdown. Developer runs new/changed/directly affected tests and hands off coherent checkpoints;
B owns full regression/acceptance and the final Closure Packet under workflow §6. Required T4
coverage includes its shared Python/Web/static/examples/package/security gates plus AC-specific
fresh initialization, concurrency, authority, same-version restart and native proofs. Reuse existing
test infrastructure and temporary roots/fakes/local servers; meaningful persistence/reopen/effect
assertions cannot be replaced by string searches or mock-only UI tests. Do not weaken tests to
permit Job removal.

Use the explicit capacity-state/queue-full cases and supported interruption boundaries above as
acceptance scenarios. File lineage/history/counts and non-replay are the result obligations; keeping
all internal item IDs equal or enumerating every theoretical crash point is not a separate gate.

The preceding investigation ran 138 core Task/Automation/authority/recovery tests and 45
original-record/log-isolation tests on the Base: 183 passed, with database ResourceWarnings in the
first run. These are pre-refactor observations, not final acceptance; no full/Web/container result
is claimed. A scope checkpoint runs relevant document/link/governance checks only. Implementation
Head and Closure Packet were subsequently supplied by B; the A Final Review below supersedes
this original planning-stage availability statement.

## Workspace and role record

Repository `/Users/songzhidong/mediaflow`, branch `main`, starting HEAD equals the immutable Base.
No pre-existing tracked edits; pre-existing untracked OS/log/reference/image/archive artifacts remain
unrelated and unstaged. Workspace/Git are writable. Private runtime/configuration/media are not read
or used for validation. No push/history rewrite is authorized or performed.

The user grants A scope authority; earlier B investigation is disclosed. No implementation,
Task review or A Final Review is conducted by this scope action. Roles remain separate under the
workflow; no sub-agents are requested or spawned. `TASK.md` remains NO ACTIVE IMPLEMENTATION TASK
until B plans against the committed Contract. No original closed Slice fact is changed.

2026-11-02 scope/planning workspace: branch `main`, starting HEAD
`980ce42a977b5bc20cf8426dbaf5a232f46cf22b`; no pre-existing tracked edits. Pre-existing untracked
OS/log/reference files, `15` and output artifacts are preserved unstaged. Governance preflight PASS.
The same root agent acts as A for this scope checkpoint and subsequently as B planner, with no
delegation, implementation, final review, push or change to prior acceptance facts.

2026-11-03 settings document checkpoint: branch `main`, starting HEAD
`d2669f237e3576704da071354e428983c2b28793`; governance preflight PASS. The same B agent uses
the user's explicit A document authority, then returns to B for Task alignment. Twenty-one
pre-existing tracked implementation/test/harness edits and all untracked/private artifacts are
preserved unstaged; no product changes, push, candidate acceptance or independent final review.
Document checks pass: whitespace, 126 local links across nine affected documents, unchanged
Slice identity/acceptance IDs and accepted closure ledger. Product/T4 acceptance remains pending.

## A Final Review — FIX REQUIRED — 2026-11-02

```text
Slice Base: 5144ab1fc2344b06194969cc2c496835729664c0
Reviewed Implementation Head: 3cf1b6b4b59dbea0bbd2159c404e760f7bcd9417
Review starting HEAD: 62a566f9c7395fae14b5ee5df9dae987bb4bb201
Decision: FIX REQUIRED
Blocking finding: A-P1-1 — direct CLI terminal unknown-effect work retains shared capacity
Next action: B reopens/reassesses Task47.5 with its original Base and correction/test plan
```

This independent A review uses the entire original Slice range (225 changed files), not only
Task47.5: Task scheduling/claims/source ownership, manual and automatic entry/completion paths,
four-type continuation, Job removal/fresh persistence, API/CLI/Web consumers and B's actual
validation evidence. `3cf1b6b4..62a566f9` changes only B's `TASK.md` report. The review applies the
user's scope amendments: no old-task/cross-version upgrade or V1 acceptance is claimed. Original
Slice Base, accepted43–46 and previous B Task review checkpoints remain unchanged. This A instance
has not implemented or B-reviewed this Slice and has spawned no agents.

**A-P1-1 — ordinary CLI does not settle a finished unknown-effect attempt.** Existing entry:
`mediaflow --config <isolated-bootstrap> organize <source> --execute --limit 1`, under a legal
COPY policy. The real LocalStorage adapter encounters `ENOSPC` opening its target staging file;
the pipeline records a terminal `partial` TaskItem and Result (`CREATE_DIRECTORY` completed,
`attempted_unverified`, `mutation_outcome`). All calls have returned and the CLI exits, but
`final_cli.py::_settle_direct_organize` calls `scheduling.settle` without the finished-pass boundary
used by `ManualTaskEngineWorker`. Settlement refuses the recorded unknown marker; the Task stays
`running`, queue `claimed`, capacity **1**, including after same-version reopen. With capacity 1,
a second distinct ordinary CLI request is rejected as queue-full after the disk fault is removed.
CLI exits 2 with the settlement exception and omits the normal Task/result summary.

The direct settlement call was introduced in `1e46e5baa` (2026-11-01 00:25:11 +08:00).
Task47.5's finished-pass capacity correction covers the resident path but leaves this existing CLI
caller unchanged. This is an unmet RO-1/RO-2 and AC-2/4/15/24 invariant in the unclosed Slice,
not a standalone minor bug or a new scope request. Unknown Result evidence must remain unknown;
retaining it does not mean the finished process still has machine work or needs a queue slot.

**Correction boundary for B:** keep Task47.5 ID/Base/goal and the shared kernel; make ordinary
CLI completion and applicable control/human-wait settlement use the same supported finished-pass
rules as the resident path. Release capacity only when the pass's calls returned and durable
items/results prove no remaining machine work; preserve the original Result, effects, source
protection, siblings and fences. Return the honest Task/result summary. Add real CLI-entry
regression for this failure, subsequent distinct admission and reopen, plus directly affected
control/mixed-item cases. Do not clear uncertainty, auto-replay, add recovery/remote detection or
broaden the Contract. B owns the correction plan and fresh assigned acceptance before another
Closure Packet; A does not implement or self-approve it.

**Actual evidence:** local ignored root
`.git/validation-evidence/3cf1b6b4b59dbea0bbd2159c404e760f7bcd9417/a-final-review/`.
`cli_capacity_probe.py` invokes the existing production CLI with the existing isolated managed
fixture, fake Provider and real SQLite/LocalStorage/Executor. Only target `Path.open('wb')` receives
the OS disk-full error; no synthetic endpoint, repository mutation or fabricated Task state is used.
`cli-capacity.log` records the terminal item/Result, retained slot, next admission refusal and reopen.
`focused.log`: A independently ran six Task scheduling/fencing/source race/manual engine/history/
entrance-recovery modules: **134 tests OK**, 11.343s. That passing set misses this CLI disk-failure
settlement. The reproduced blocker is not waived by passing suites.

B's retained packet at `62a566f9:TASK.md` includes 2530 Python tests (7 optional remote/endurance
skips), 1267 Web unit tests and 253 fake E2E, native journeys, clean wheel/source proof and Docker
fresh/security/same-version restart. A inspected raw logs and the report-only/Web reuse diffs;
these remain valid evidence for their covered cases, not proof of the missing CLI outcome. A did
not mechanically rerun full suites or claim new wheel/container acceptance. No CURRENT/closure
reconciliation is performed on FIX REQUIRED. Roadmap stays ACTIVE; Progress's closure ledger is
unchanged. Pre-existing untracked files remain unstaged; no product/test edits or push occurred.

## A Final Review — FIX REQUIRED — capacity compatibility — 2026-11-02

The 2026-11-03 settings amendment above supersedes this review's original numeric-only direction
and the later Automation-only correction. Reproduced failures and evidence remain factual;
acceptance now requires the three-setting System Settings journey and parameter removal under
V2-TASK-011 and AC-26.

```text
Slice Base: 5144ab1fc2344b06194969cc2c496835729664c0
Reviewed Implementation Head: 5c808d4a67bedfbafb71d88a1ffa8d3480ef5316
Review starting HEAD: 7ac253dd11ab3453f36cd40500c79c72b4f888de
Decision: FIX REQUIRED
Resolved: A-P1-1 — direct CLI finished-pass capacity settlement; B-P1-1 — batch parsing
Blocking finding: A-P1-2 — published legal capacity exceeds the new Task kernel's accepted range
Next action: B plans one bounded in-Slice compatibility correction and fresh acceptance
```

A independently reviewed the original Slice Base..candidate (225 changed files): Task scheduling,
claims/source ownership and fences, all organizing entrances, same-Task four-type continuation,
Job removal/fresh persistence, history admission/warnings, API/CLI/Web consumers and actual B evidence.
`5c808d4a..7ac253dd` changes only B's Task report; executable inputs are the reviewed candidate's.
The six outcomes and user amendments remain authoritative; old-task/cross-version upgrade and V1
support remain excluded. This A instance neither implemented nor B-reviewed the Slice, and used no
sub-agents. The preceding rejected candidate/review stays historical; this review supersedes its
current blocker assessment without rewriting the original Base or any prior acceptance.

**A-P1-2 — legal global capacity publication breaks organizing admission.** From the existing
Automation global-settings API, GET advertises `automation.maximumActiveJobs` as an integer in
**1–10000**. An authenticated ordinary PUT changing 100 to **1025** returns **201** and publishes
that value as Active. In the same isolated managed deployment/SQLite database, the existing command
`mediaflow --config <bootstrap> organize <source> --execute --limit 1` then returns **2**:
`Task scheduling capacity must be between 1 and 1024 Tasks`. It creates no Task or media effect;
the queue is empty. GET still truthfully shows Active 1025. Saving **1024** through the same settings
entry returns 201, after which the same CLI command succeeds with one actual COPY target.

**A Web follow-up — 2026-11-02:** the existing `自动化 → 全局设置` form also saves
**1025** with HTTP 201 and shows the new published Active value. From Files, selecting one real
fixture file and clicking `批量整理` then sends the existing `/files/discoveries` command, which
returns HTTP 400 `invalid_request` with the same 1–1024 kernel error. The page shows only
`无法开始整理发现，请刷新后重试。`; refreshing cannot correct the published capacity mismatch.
The source remains present and no target is created. Through the same Web form, saving **1024**
restores admission; the same file reaches its normal plan summary and explicit confirmation, then
the real Worker/OrganizerExecutor performs its configured MOVE. This confirms A-P1-2 affects the
ordinary Web journey as well; B's correction/acceptance must cover that existing journey.

The new `domain/task_scheduling.py::MAX_TASK_CAPACITY = 1024` / `require_capacity` conflicts with
the retained settings/configuration/Scheduler range of 1–10000. `TaskSchedulingService` and
repository admission enforce the smaller limit. The bound entered in `e53e38999459f81da65f625ee3b73d39e9ff793e`
(2026-10-30 19:27:53 +08:00); ordinary CLI consumption of the kernel entered in
`1e46e5baa0ea1dc1d3400ef42bf80d80b8a954cb` (2026-11-01 00:25:11 +08:00).
This violates RO-1/RO-5 and AC-4/12/15: supported settings must retain their operational meaning.
It is an in-Slice P1 compatibility gap, not an independent minor bug, a capacity-load test or a new
user feature. Reproduction needs one file and an ordinary legal Save, with no fabricated endpoint,
repository state, exhausted queue, Provider fault or thousands of admitted Tasks.

**Current correction boundary for B:** follow the user-authorized settings-scope amendment,
V2-TASK-011 and AC-26. Preserve legal capacity 1–10000 for all shared organizing consumers,
move the remaining three fields into System Settings and remove the unused stale-age parameter.
Align Task47.6 before implementation; numeric range alignment alone is insufficient. Keep atomic capacity,
source/authority/fence/waiting semantics, immutable pins and a single Task engine. No need to admit
10000 tasks to prove a legal ceiling. B owns affected/T4 acceptance, whole-Slice reassessment and a
fresh Closure Packet. Preserve Task47.5's passed fixes/history; A implements no product fix and does
not close or reconcile CURRENT on this rejection.

**Independent evidence:** local ignored root
`.git/validation-evidence/5c808d4a/a-final-review/` (local only).
`capacity_settings_journey.py` / `capacity-settings-journey.log` drive the existing production WSGI
settings GET/PUT and real CLI against one managed temporary SQLite/LocalStorage deployment. Only
MetadataProvider is synthetic; all configuration activation, Task admission and actual COPY use
production behavior. The 1024 recovery is verified, not proposed. No user database, media or private
configuration is accessed.

- `web-capacity/capacity-web.spec.mjs` and `web-capacity/test-output-final/` (`proof.json`/PNGs):
  **1 real-Python Chromium journey passed**, 4.0s, using the existing repository harness and built
  V2 artifact. Settings Save, navigation, Files selection/admission, summary and confirmation are
  actual page actions; existing harness controls only step the real background workers and read
  fixture Storage state. A inspected the failure screenshot. This adds one focused journey;
  it does not claim a new full-suite run.
- `focused.log`: six scheduling/fencing/source-race/manual-engine/history/entrance modules,
  **141 tests OK**, 13.948s. This set does not cover the published-capacity mismatch.
- `cli-capacity.log`: independent rerun of the prior A real CLI ENOSPC probe with corrected success
  expectations; terminal partial/unknown evidence stays, exit 1/normal summary, capacity 0, next
  distinct file succeeds and same-version reopen stays settled. `active-cancel.log` proves the slot
  remains while a real write is blocked, then releases after cancellation and returned ENOSPC.
  `batch-root.log` and `multi-storage.log` independently prove actual root batch/cross-Storage COPY.
- `native.log`: **3 real Python/API/SQLite/Worker Chromium journeys passed** (history warning →
  ordinary confirmation → actual new organize, eight center views and in-context summary), 10.4s.
  A also inspected B's desktop and 390px summary/confirmation screenshots; the warning and original
  confirmation remain visible with readable wrapping and no new acknowledgement checkbox.
- `artifact-proof.json`: A independently compared all **169** wheel Python modules byte-for-byte
  with candidate source; no extra/missing modules. SHA-256 matches B's clean wheel:
  `7f75e4ed89ee0fd492228a302cb0d3f12644df04344473049e307fa54afee05d`.

B's packet at `7ac253dd:TASK.md` and raw logs at
`.git/validation-evidence/5c808d4a/b-review/` were checked: 2537 Python tests with 7 optional remote/
endurance skips (the one Task-document heading failure was corrected and its 8-test module rerun),
22 current native journeys, quality/examples, clean installed consumers and Docker fresh/security/
same-version restart passed. The explicit unchanged-input diff supports reuse of 1267 Web unit and
253 fake E2E results; A independently verified that diff. The synchronized Automation native copy
waits for the actual new definition readback; its initial stale-fingerprint refusal remains disclosed
as P2. These results establish their covered behavior but do not waive A-P1-2. A did not rerun or
claim new full Python/Web/container acceptance. Pre-existing untracked files remain unstaged;
this review changes only A-owned review/status documents, with no product/test edits or push.
