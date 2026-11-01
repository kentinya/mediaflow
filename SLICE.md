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
Next Action: B PLANS TASK47.5 AGAINST THE 2026-11-02 SOURCE-HISTORY AMENDMENT
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

- Shared per-source TaskItem admission uses backend-proven trigger/context and prior organizing
  history. Definition due work excludes the same observed source version when it has a prior
  `failed` or `partial` organizing outcome. Run once uses the same definition-derived exclusion,
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
  configuration pin, exact source/plan and authority. Old item/Result/pin/effect certainty and original
  Automation outcome/time remain factual. Historical unknown effects do not become verified or
  acquire fresh old authority merely because a new request was confirmed.
- Explicitly queued/processing work and genuine live source ownership still prevent concurrent
  execution. Historical unknown markers are not by themselves proof a Worker is still running,
  nor a permanent veto on explicit manual re-organizing. Necessary application-owner fencing and
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
  analysis and shared four-type decisions/ignore/audit. New manual CLI execution emits the same
  history warning and uses its existing explicit `--execute`; unattended remote discovery cannot
  impersonate selected Files manual intent to bypass history filtering or permissions.

The user's intervening explicit boundaries also remain: no old tasks/cross-version upgrade scope,
and V1 is unsupported. Fresh initialization and same-version reopen/restart, existing new-work
history, permissions, pins, audit and data integrity remain required. This supersedes the obsolete
upgrade/V1 obligations in RO-4/AC-9/10/11/17 only within that stated scope; none are claimed tested.
Accepted43–46 and Task47.4 are not retroactively re-reviewed or relabelled by this amendment.

### Amendment traceability

`V2-TASK-008–010` in [V2 Requirements](docs/v2-requirements.md) owns the durable new rules.
This section and RO-6 supersede affected blanket history-refusal/CLI retry wording in RO-1/2/3/5,
the Safety invariants and AC-6/8/15/16 only for deliberate new manual work. Automatic and same-Task
uncertain replay remain forbidden. The new TARGET journey/architecture sections distinguish this
authorized work from accepted CURRENT delivery.

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

### RO-6 — source-dependent history admission and one new-organizing journey

Apply the 2026-11-02 amendment at each concrete source's shared Task admission, including files
found after a directory Task was created. Automation due/Run once excludes prior failed/partial
versions before Provider work or effects; manual selection reaches a backend-generated exact
summary containing the prior result/effects warning and can execute a newly confirmed legal plan.
Compare real Storage/path/version across library bindings and complete history, not names, the
latest page of Results, or the enclosing Task's aggregate. Recheck history and ownership atomically
at relevant admission/confirmation boundaries. A truly replaced source is new content; missing or
incomparable version evidence cannot silently erase an applicable failed/partial history warning.
Use existing Task/TaskItem/Result/discovery/authorization evidence, no global FileIndex replacement
or new queue/recovery product. Remove CLI retry-failed without dropping shared four-type behavior.

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
Necessary integration in existing ordinary-file/notification consumers preserves their behavior except
for the explicitly authorized ordinary-file Pause/Resume retirement;
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
| AC-19 | Organizing and ordinary-file operations expose no Pause/resume-from-pause in Web/API/CLI or dedicated live dispatch. Old requests are refused without effects; safe cancellation and four-type organizing continuation still work. No paused-organizing migration/restoration system is required; preserve existing readable history and non-replay. |
| AC-20 | Due and definition Run once use shared per-source history admission. Same-version failed/partial items are excluded independently, even zero-effect failures and after restart; free siblings proceed. Historical exclusions are durable/readable and do not fabricate new media success, Attention problems or first-N scope completeness. |
| AC-21 | Manual direct/folder/mixed selection of failed/partial sources, including partial directories/copy remnants and historical unknown effects, reaches the real existing summary with clear per-file history/effects warning before selected confirmation. Current pinned new plans execute through normal conflict/capability/destructive authority, with no new recovery page or mandatory extra operator chore. |
| AC-22 | Query complete organizing history by canonical Storage/path and comparable version across library bindings, before limiting display. Cover older matching history beyond recent pages, mixed results, analysis-only/non-organizing records, genuine replacement and unknown versions. Reads and warnings have zero Provider/media effects. |
| AC-23 | Source-history and ownership checks are backend-authoritative and race-safe. Known active work still blocks; explicit new manual work is not permanently refused by historical partial/unknown markers. Application-owner fencing/exact lock handoff prevents later old steps/writes, retains siblings/old unknown evidence, and never pretends an in-flight remote call was stopped. Confirmation/request loss, stale history/plan, queue full and permission loss retain normal refusal/readback semantics. |
| AC-24 | retry-failed is absent from parser/help/dispatch and exclusive helpers in source, clean wheel and image. Old input stops without Task/Provider/Storage/authority effects. Organize/analysis and same-Task four-type continuation/ignore retain legal behavior; manual CLI prints history warnings and remote unattended input cannot spoof warned manual consent. |
| AC-25 | Real V2 Files/API/SQLite/Worker desktop/narrow journeys prove warning → normal confirmation → actual new organize effects; scheduled and Run once probes prove exclusion/free siblings/no-work truth. Old Results/pins/unknown effects and original Automation time/outcome stay immutable. B supplies applicable T4/native/packaging/restart validation for RO-6 before whole-Slice A review. |

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

2026-11-02 scope/planning workspace: branch `main`, starting HEAD
`980ce42a977b5bc20cf8426dbaf5a232f46cf22b`; no pre-existing tracked edits. Pre-existing untracked
OS/log/reference files, `15` and output artifacts are preserved unstaged. Governance preflight PASS.
The same root agent acts as A for this scope checkpoint and subsequently as B planner, with no
delegation, implementation, final review, push or change to prior acceptance facts.
