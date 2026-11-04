# Slice 48 — Task Flow Status and Automation Success Rate

```text
Slice ID: 48
Name: Task Flow Status and Automation Success Rate
Owner: A — Slice Owner / Architect / Final Reviewer
Status: READY FOR A REVIEW
Base SHA: ba84272721961c970f1eb85d616a0d129523ab92
Implementation Head: a80015e2f7d46e3ad1b8f7b14c453d1030e62104
Implementation Head Acceptance: B PASS — A48-01 corrected; A FINAL REVIEW PENDING, 2026-11-04
Working Branch: main
Development Authorization: CORRECTION COMPLETE; NO ACTIVE IMPLEMENTATION TASK
Risk: High
Final Test Level: T4
Next Action: A REVIEWS THE CORRECTED ORIGINAL BASE..IMPLEMENTATION HEAD; NO SLICE CLOSURE
```

B correction handoff (2026-11-04): Task48.1 correction independently passed; all Slice outcomes/surfaces
reevaluated complete. Refreshed validation and Closure Packet are in [TASK.md](TASK.md). These are factual
readiness fields, not A acceptance. The A48-01 review below retains the original rejected candidate
`2d4f1ae037cc4642b7bcd4231a840cf40d70e7b6`; A must review the corrected original Base..Head anew.

## Authority and accepted baseline

[AGENTS.md](AGENTS.md) and [Development Workflow](docs/development-workflow.md) govern scope,
roles, checkpoints, tests and acceptance. B submitted the full Slice Closure Packet at
`6c39d6ecdf40cad8f06e5e97f58bf47bdc388b49:TASK.md`, with Task48.1/48.2 PASS and final T4 evidence.
A independently reviewed original Base through original Head
`2d4f1ae037cc4642b7bcd4231a840cf40d70e7b6` and returned
**FIX REQUIRED** for A48-01 below. B's PASS/evidence remain historical facts; they do not establish
Slice acceptance. The returned Task48.1 keeps its original Base/goal/scope; B must checkpoint its
correction plan before Developer work. No new capability, scope reduction or independent minor bug
is selected. Outcomes, acceptance, deferrals and immutable Slice Base remain unchanged; the
requirements/journey/architecture amendment remains TARGET until A accepts the corrected range.

Slice47 remains PASS / CLOSED, with original Base
`5144ab1fc2344b06194969cc2c496835729664c0` and accepted implementation
`5134c78b22057781d472e6ebf61a1799d9e40324`. Its complete Contract/A review is preserved at
[the Slice47 checkpoint](https://github.com/kentinya/mediaflow/blob/ba84272721961c970f1eb85d616a0d129523ab92/SLICE.md);
B's final packet remains at `749507ca9000329484bdc9fb7ad5c44e0efc0cd0:TASK.md`.
Earlier accepted identities, safety and deferrals in [Progress](docs/progress.md) remain unchanged.

## User goal and requirement traceability

- Task reports whether its own processing flow completed, failed or was cancelled.
- File success, partial success, failure, skip, ignore and effect uncertainty remain independent
  TaskItem/Result facts; they do not turn a normally completed Task into failed/partial success.
- File-processing technical failures, including unknown effects and missing file results, can close
  as completed; Task completion does not wait for actual Storage results to be established.
- Automation's success rate counts scheduled and definition Run once Task flow completion;
  Files/CLI manual organizing and ordinary file operations do not enter its numerator or denominator.
- Keep stage/waiting explanations, per-file results and safe four-type continuation usable.

The planned amendments are `V2-TASK-012–014` and `V2-AUTO-012` in
[V2 Requirements](docs/v2-requirements.md). They amend the V2 realization of `REQ-TASK-002/003`,
affected aggregate/recovered-success wording in `V2-OPS-016`, and the success-rate realization of
`V2-AUTO-005`. They also amend `V2-AUTO-006` so execution records show the same Task flow result
as Task Center, with independent file results. They do not alter the frozen V1 baseline or declare
the new behavior CURRENT.
Preserve `UX-001–007/010`, applicable `REQ-TASK-005–010`, `REQ-RESULT-*`, `REQ-RECOVERY-*`,
`REQ-SAFE-*`, `V2-TASK-001–011`, entry/authority boundaries in `V2-OPS-014/015/017`,
`V2-FILES-007` and `V2-AUTO-010/011`, except for the explicit aggregate/metric/record amendments above.
Original execution times, attempts and file/effect history remain factual; their preservation does
not require retaining a file-derived failure label as the Task's execution result.

Baseline investigation found file-derived settlement in
[task_persistence.py](mediaflow/domain/task_persistence.py) (`task_work_status`),
[task_runtime.py](mediaflow/application/task_runtime.py) and
[manual_task_engine.py](mediaflow/application/manual_task_engine.py). The current Task/run models
retain partial-success/paused values. Automation's metric query in
[sqlite_runtime.py](mediaflow/infrastructure/sqlite_runtime.py) additionally requires successful
primary-file evidence and no uncertain success item; its separate records-only projection also
classifies execution results by file outcomes. Both must adopt Task flow meaning for the selected
TARGET. These describe the original Base gaps, not current acceptance. The submitted implementation changes
these boundaries; A48-01 records a remaining competing recovery projection in its consumers.

Complete TARGET journeys and technical contracts are in
[Product Experience](docs/product-experience.md#target--task-flow-status-and-automation-success-rate-slice48-active)
and [Architecture](docs/architecture.md#target--task-flow-status-and-automation-success-rate-slice48-active).

## RO-1 — one five-state Task lifecycle, independent of file outcomes

The current durable Task aggregate and its ordinary Web/API/CLI projections use exactly these five
flow states. Stages, queue eligibility, controls, file results and read availability are distinct facts.

| State | Meaning |
|---|---|
| `pending` | Work is admitted and waiting to start or legally re-enter machine processing. |
| `running` | The flow is unfinished, including processing, stability waiting and required human decision/confirmation. |
| `completed` | The Task closed its admitted work, including file-processing technical failure; actual file results may be absent or effects unknown. This says nothing about file success. |
| `failed` | A Task-level flow failure prevented normal completion and can be truthfully persisted. |
| `cancelled` | An explicit Task cancellation was acknowledged at the safe boundary. |

Do not publish `partial_success` or `paused` as a current Task aggregate status. Pause remains
retired; waiting and unknown/unavailable read evidence are not additional Task lifecycle states.
Do not collapse processing stages or TaskItem/Result/attachment/transfer-operation vocabulary into
these five values. Audit the older twelve-value `mediaflow/domain/tasks.py` vocabulary and its actual consumers
so it cannot remain a competing durable Task lifecycle; shared scanning/pipeline stages may remain
as stages without a broad scanner rewrite.

Normal closure yields completed for all-success/failed/partial/mixed, skipped/ignored, individually
cancelled files, healthy empty and complete history-excluded scope. File-processing technical failure
also closes as completed when the current attempt ends, even when a file Result was never produced
or the actual Storage effect remains unknown. Do not require a successful file, a formal per-file
Result, effect verification or remote-stop proof before that technical closure. Preserve known
failure/step evidence and explicitly show missing results/unknown effects without inventing success.

Required human decisions, genuine remaining machine work and a call still executing in the current
application attempt stay unfinished. A stale processing marker left by an ended technical failure is
not, by itself, proof of live work. Scope incompleteness or a failure of the Task's own orchestration
still yields failed; an all-terminal file population alone cannot prove Task closure. Task closure
must itself be durably saved under the existing owner fence. Only acknowledged explicit Task
cancellation yields cancelled, never cancelled-file counts. A technical failure of a file operation
must not be reclassified as a Task orchestration failure merely because its Result is missing.

## RO-2 — explicit flow-failure boundaries and preserved execution safety

Apply the same lifecycle to manual Files/file/folder/mixed work, supported direct API/CLI/remote
organizing, scheduled due work, definition Run once and existing same-Task continuation. Ordinary-file
Task producers on both library kinds adopt this meaning where they write/read the shared Task
aggregate, without redesigning their per-operation results, admission, queues or controls.

| Situation | Required Task interpretation |
|---|---|
| File parsing/recognition/metadata/target/conflict/Storage/attachment technical failure, including timeout or interrupted file work with no formal Result | Close the ended file attempt as a technical failure and allow Task completed without requiring actual file results. Preserve known outcomes and show absent results/unknown effects; unaffected work and required human decisions retain their own state. |
| Discovery root/list failure or an incomplete/overflowed scope prevents proving the admitted scope was processed | Task flow failure; never pretend this is healthy empty completion or execute a first-N subset. A bounded file-local discovery error may remain item-local when scope completeness is still proved. |
| A missing/corrupt required pinned context, broken work relation or orchestration error prevents the Task flow from finishing | Task flow failure with bounded stage/reason, known effects and existing permitted next action. |
| No/stale Worker, temporary readiness waiting, claim expiry/loss or a cooperative cancellation request | Not by itself a terminal failure. Preserve real waiting/ownership and existing safe settlement rules. |
| A file operation ended technically, but its actual Storage result or formal Result is absent | Missing file results do not block Task completed. Fence/retire the ended application attempt and preserve known steps, missing-result/unknown-effect evidence and non-replay; do not demand a result lookup or remote-stop proof. |
| The current application attempt still has a genuinely live Storage call | Keep it unfinished with existing ownership/capacity protection; a timeout or ended technical attempt must not be confused with a call that is still executing locally. Completion never grants replay or silently clears a live mutation. |
| Database/publication failure prevents recording a terminal outcome | Preserve last durable truth and unavailable/interruption evidence; do not claim the failure or completion was saved. |

Keep one authoritative application settlement policy for flow outcome and use it across producers
and claim-fenced repositories. Do not rebuild a parallel flow engine or infer completion by relabelling
an existing file aggregate. Cancellation acknowledgement wins races with normal finalizers;
stale-owner writes cannot publish a later terminal outcome. Preserve current queue capacity,
human-waiting slot release, current authority, immutable pins and atomic source ownership.
Do not keep an ended technical attempt running or holding its ordinary Task slot solely for a missing
file Result. Any still-required protection against a live/uncertain effect remains authoritative;
Task completed does not itself grant another execution, release a live call or erase uncertainty.

TaskItem/Result/attempt/checkpoint/attachment results, effect certainty, completed steps, audit/logs
and source-history gates retain their real meaning. Due/Run once still excludes a source version
whose latest formal file outcome is failed/partial even when its enclosing Task is completed.
New manual warning/confirmation remains. No successful/uncertain replay, implicit new authority,
repinning, new retry product, pause restoration, fifth recovery type or universal rollback.
Missing formal file results remain missing; Task completion must not manufacture formal history
or overwrite an existing Result merely to satisfy source-history or file-count predicates.
Normal paths still persist per-file Results and all available evidence; tolerating a Result lost to
technical failure does not authorize intentionally omitting ordinary result persistence.

## RO-3 — readable flow state and independent file results on all affected surfaces

Task Center keeps the same eight organizing views and four-type Attention union. Its state badges,
ended/running membership, counts, detail, management filters, paging and links use the same five-state
flow facts. Waiting stage/reason remains visible; waiting work is not labelled finished. Missing or
unreadable Task-state evidence is unavailable, not a fabricated Task failure, success or zero total.

A normally completed mixed-result Task reads, for example, “流程已完成；成功 7、部分成功 2、失败 1”.
An all-failed file population can show completed flow and truthful file failures together. File details
keep actual cause, effects and existing actions; a completed badge must not hide warnings or mean
“全部整理成功”. Progress counts settled/processed files independently from success counts; finishing
all admitted file attempts can reach 100% processing progress without claiming successful effects.
Task-level error/recovery presentation distinguishes orchestration failure from item errors.
Technical closure without file results shows “流程已完成；文件处理发生技术失败，实际结果未记录/效果未知”.
Known file counts remain readable; absent results are not fabricated as successful, empty or verified.

Four-type human decision → analysis → exact summary → explicit continuation keeps its same Task,
legitimate pin, independent outcomes and original attempt evidence. Human-required work remains
unfinished. Where existing legal continuation re-enters a terminal Task, only explicit admitted
continuation may move it back to pending/running; status alone grants no recovery or execution.
“恢复成功” still requires actual resolution/proven file effects; flow completion alone cannot trigger
that claim or clear an unresolved business problem. Technical/uncertain file history remains factual,
without adding a generic failure-recovery center.

Affected Files local ordinary-operation modals/readback, Automation task-state readback, Dashboard,
API/CLI, JSON export and existing Task-status notification/log consumers distinguish flow from file
results. Ordinary operation result vocabularies and notification policy remain intact. No global
ordinary-operation center, extra control or replacement UI is selected.

## RO-4 — Automation success rate and execution records use Task flow results

Select original Automation admissions: Scheduler due and the Automation definition's Run once.
Files/CLI manual organizing, ordinary file operations, rejected admission and analysis/preparation
are excluded from both numerator and denominator. Retain the local-month/timezone window and count
each Task identity once before page limits. Explicit continuation retains the original Task/trigger
and does not add a run. Do not infer Automation origin from today's definition or a later continuation.
In this Contract, “运行一次” means the Automation definition command; “手动整理” means the separate
Files/CLI organizing entrance, not Run once merely because an operator clicked its button.

```text
automation = authorized original due or definition Run once Tasks, in the local-month window
successful = count(automation where Task.status == completed)
evaluated = count(automation where Task.status in {completed, failed})
ended = count(automation where Task.status in {completed, failed, cancelled})
successRate = successful / evaluated, or unavailable/no-evaluated-data when evaluated == 0
```

Cancelled Tasks are excluded from both rate numerator and denominator, as are pending/running Tasks,
including required human waiting. Only completed/failed Automation Tasks participate in the rate.
If none exist, show no percentage, including when the cohort contains only cancelled/unfinished Tasks
or unrelated Files/manual/ordinary Tasks completed. Cancelled Tasks remain in execution records,
monthly admitted totals and all-ended counts; they do not become active or disappear from history.
The all-ended count includes cancellation and must not be reused as the success-rate denominator.
Server/API/Web rate explanations and validation use the completed-plus-failed denominator.

Execution records and existing monthly execution/active counts retain the due-plus-Run-once basis.
Execution-record Task results/filters use the same current durable Task flow state as Task Center;
file outcomes are separate detail/counts. A completed Run once record counts as Task success in the rate.

Remove requirements for a successful primary, all-file/attachment success, verified effect certainty
or a nonempty organized-file count from rate computation. All-file failure/partial/skip/ignore,
unknown effects, missing file results, healthy empty and complete history-excluded flows count as
Task success in the Automation cohort when Task status is completed. They do not acquire successful
file effects. Rates/Task status follow the current durable Task if permitted continuation changes
its lifecycle; continuation never increases the admitted Task count. Original attempt results/times
remain immutable and independently readable.

For the same Task and consistent read basis, Task Center and Automation execution records show the
same flow result. If a normally completed Task has ten failed files, both show “流程已完成” and
records independently show “文件失败 10 个”; that Automation Task counts as successful in the rate. Do not
retain a file-derived “执行失败” label for a completed Task. Record status filtering/counts/paging
use Task flow state over the authorized population, while bounded file counts/causes/effects remain
independent. Required human waiting remains unfinished in both surfaces.

Keep actual file counts, unknown effects and no-work/exclusion reasons honest: zero successful files
is not proof of zero work, and an all-failed Task is not a healthy empty/no-work record. Original
execution times, append-only attempts and file/effect history remain factual and are not overwritten
by a current Task status or later continuation. Records remain read-only and compact without new
execution/recovery controls. This explicitly amends the file-derived result/filter realization of
`V2-AUTO-006`, retaining scoped zero-write reads. No file-derived original-stage outcome may substitute
for Task.status in records or the success-rate query. Unavailable Task/metric evidence remains
unavailable; it is not reconstructed from file success/failure.

## 场景与统计口径 — Slice48 TARGET

普通复制、移动、删除本来就使用 Task；单项同步命令也可能在一次请求内完成其 Task。
普通操作仍在原库的“当前页面操作状态”查看，整理 Task 仍由任务中心承载。
下表中的技术失败指文件处理/文件操作失败，不包含 Task 自身范围、必要上下文或调度关系失效。
任务完成后保留文件事实；技术失败不要求补齐正式 Result 或查明实际文件效果。
同一 Task 同时符合多行时，自身流程失败和已确认取消沿用各自结果；其余场景仍有人工待办或
真正执行中的工作就保持未结束，没有这些待办才显示 completed。技术失败本身不新增等待结果的步骤。

| 场景 | Task 和后续流程 | 文件/操作结果 | 自动化成功率（定时 + 运行一次） |
|---|---|---|---|
| 全部文件成功 | completed，流程结束 | 成功照实显示 | 成功数、计算分母各加 1 |
| 有识别、元数据、分类或冲突人工待办 | running；在同一 Task 决定、分析、确认并继续；没有机器工作时释放普通队列名额 | 已完成文件保留，待办独立处理 | 等待期间不进入分母，正常收尾后计成功 |
| 文件技术失败，实际效果明确 | 当前尝试结束后 completed；其他独立文件按既有规则处理 | 保留失败、部分完成和已完成步骤 | 正常收尾后计成功 |
| 文件技术失败，实际效果未知 | 当前尝试技术终止后 completed，不等待查明文件实际效果 | 保留未知警告，不自动重放 | 计成功 |
| 文件技术失败，没有正式文件结果 | 当前尝试技术终止后 completed，不等待补齐 Result | 显示结果未记录/效果未知，保留已有证据，不编造成功 | 计成功 |
| 文件部分成功，或文件全部失败/跳过/忽略 | 没有其他待办且正常收尾后 completed | 各文件按真实结果独立显示 | 计成功 |
| 仍在正常处理、排队、稳定性等待或等待首次执行确认 | pending/running，不提前完成 | 显示当前阶段；普通首次确认不计四类人工待办 | 暂不进入分母 |
| Task 自身无法完成范围发现、必要上下文/关系或流程调度 | failed；若终态保存失败，保留最后可读状态并提示未保存 | 不改写已有文件结果 | 仅成功保存的 failed 进入分母，不进入成功数 |
| 用户明确取消且已经确认取消 | cancelled，保留已完成和未知效果 | 不回滚、不重放 | 不参与成功率，仍保留执行记录及已结束数量 |

这些 Task 结算规则同样适用于普通复制/移动/删除，但普通操作和 Files/CLI 手动整理均不进入
上表的自动化成功率；自动化页“运行一次”计入。普通操作不能因 Task completed 显示
“复制/移动/删除成功”；仍显示实际操作失败、部分完成、效果未知或结果未记录。
没有发生技术终止的真实在途调用不套用技术失败行。
同一 Task 有多个四类问题时，待处理任务总数去重；每类任务/文件数独立保留。

统计示例：5 个自动化 Task（定时或运行一次）中，全部成功、未知效果技术失败、缺失结果技术失败、
文件部分成功各 1 个均已收尾，另 1 个等待人工处理，则成功率为 4/4 = 100%，已结束 4 个、进行中 1 个。
新增 Files/CLI 手动整理或普通操作不改变该成功率；新增自动化“运行一次”按它自己的 Task 状态参与统计。
另一个独立例子：8 个 completed、1 个 failed、1 个 cancelled 的自动化 Task，成功率为 8/9 ≈ 88.9%，
已结束数量仍是 10。若自动化 Task 全部取消，成功率显示暂无统计，不能显示 0% 或 100%。

## Required surfaces, exclusions and persistence boundary

Required: Task domain/settlement, actual producers/runners and claim-fenced SQLite writes/reads;
API/CLI/Web Task and run models; Task Center, Files ordinary-operation status and existing Task
consumers; Automation metric service/API/cards, execution-record Task results/filters and independent
file detail; applicable installed artifacts.
Fresh initialization → new work → same-version reopen/restart preserves five-state Tasks, file
outcomes, waiting/continuation, errors, results, pins, request/occurrence identities and fences.

No old-task/status migration, bulk historical relabelling, cross-version upgrade/rollback or
mixed-version writer support is selected. Retained historical evidence must not be falsified, erased
or used to restore paused execution; no task/data clearing. Read-only historical handling, if retained,
must not infer a new flow success from an old partial/file-result aggregate without proof.
Other exclusions: new Providers/Storage commands, queue/parallelism/settings/supervision redesign,
unbounded discovery, MediaLibrary organizing, new recovery types, cross-Task bulk mutation,
attachment-only retry, automatic uncertain replay and universal rollback. No unrelated refactors.

## Acceptance

| ID | Required proof |
|---|---|
| AC-1 | Supported Task producers/readers expose pending/running/completed/failed/cancelled only as current flow statuses; retired paused/partial-success aggregate branches are removed or confined to honest read-only historical evidence. Stages and per-file/operation results retain distinct meanings. |
| AC-2 | The scenario table yields completed for normal closure and ended file-processing technical failure, including all-success/mixed/all-failed/all-partial/skipped/ignored/individual cancellations, unknown effects and no formal file Result. Missing actual results, result verification and remote-stop proof are not completion gates. Known file evidence and absent-result truth remain; healthy empty/history exclusions remain distinct. |
| AC-3 | Required decision/analysis/summary/confirmation, genuine remaining machine work and a genuinely executing local call do not complete early. An ended technical attempt with a stale processing marker or missing Result does not stay running solely for that reason. Human/stability waiting and queue-capacity behavior remain correct without a sixth Task status. |
| AC-4 | Task-level scope/pin/relation/orchestration failures preventing normal completion remain failed with all-success, mixed or all-failed file populations; file-local failures alone never make Task failed. An unfinished flow cannot become completed merely because all known files have terminal results. Incomplete traversal/overflow is not empty success or first-N execution. Persistence refusal preserves last durable truth. |
| AC-5 | Files direct/folder/mixed, direct supported API/CLI/remote, due, Run once and same-Task four-type continuation use the same flow settlement behavior. Both library kinds' ordinary-file Task producers adopt it without changing operation-result semantics or queue rules. |
| AC-6 | Concurrent cancel/finalize, stale claim/result publication and restart before/after mutation dispatch preserve pins, authority and completed/uncertain non-replay. An ended file technical attempt can close without a formal Result; retire/fence its application owner and preserve missing-result/unknown-effect evidence. Task completed cannot clear a genuinely live call or grant replay; a missing file Result alone cannot retain an ended Task's ordinary queue slot. Cancellation remains acknowledged Task intent. |
| AC-7 | Real Task Center All/Running/Attention/Ended and four problem lists have consistent authorized counts/membership/paging; mixed/all-failed completed flows retain truthful file counts, causes, effects and readable progress. Waiting remains unfinished. Flow completion never falsely displays file recovery success. |
| AC-8 | Existing four-type decision → analysis → summary → explicit continuation works in the same Task through refresh/restart, preserving independent siblings and original attempts. No new technical/attachment replay or generic failure-recovery flow appears. |
| AC-9 | Automation success rate uses original Scheduler-due and definition Run once admissions: completed/(completed+failed), with no file-result/Result-presence/effect predicates. Cancelled and pending/running Tasks, Files/CLI manual organizing and ordinary operations are excluded from numerator and denominator. No completed/failed Automation Tasks yields no percentage. Cancelled Tasks remain in records/admitted/all-ended counts, never active; server/API/Web denominator explanations and validation distinguish all-ended counts from the rate denominator. |
| AC-10 | Due/Run once completed Tasks with failed/partial/skipped/ignored/unknown/missing-result or zero-work files count as success. Automation 8 completed, 1 failed and 1 cancelled yields 8/9 (about 88.9%) with 10 ended, unchanged by extra cancelled, Files/CLI manual or ordinary Tasks; Run once contributes by its own status. All-cancelled, cancelled-plus-unfinished and only unfinished Automation plus completed unrelated manual Tasks yield no percentage. Verify original admission/continuation deduplication, pagination-independent counts, local-month bounds and unavailable reads; records/monthly execution/active counts retain due-plus-Run-once populations. |
| AC-11 | For the same Task and consistent read basis, Task Center and Automation records agree on the current flow result. Each surface applies that flow-state meaning to server-side status filters/counts/paging within its own authorized population. A normally completed Task with ten failed files shows completed flow and ten independent file failures on both surfaces and counts as Task success; Task-level failure remains failed regardless of file mix. Required waiting remains unfinished. Legal continuation updates current status/statistics without another run or rewriting original execution times/attempts/file effects. All-failed is neither empty/no-work nor successful media organization; records retain read-only/compact boundaries. |
| AC-12 | Source-history admission still uses latest formal file outcome: a failed/partial item in a completed Task is excluded by due/Run once and warned for new Files manual confirmation, with old effects/history preserved. |
| AC-13 | Files local modals/readback on both library kinds, Dashboard, API/CLI, scoped logs/export and applicable notification consumers distinguish Task flow status, per-file result and effect certainty. Missing file results do not block technical completion or invent file success; unavailable Task-state truth is not coerced to a valid Task outcome. |
| AC-14 | Fresh/same-version persistence and affected source-external wheel/container startup/restart consumers prove the five-state lifecycle, waiting, file evidence and original records survive; old-task/cross-version conversion is not required. |
| AC-15 | RBAC, bounds/confinement, exact manual/Automation/continuation intent, immutable pins, zero-mutation reads/analysis, C using Naming A/Classification A remaining C, cancellation/fences and successful/uncertain non-replay retain automated coverage. |
| AC-16 | B supplies applicable full T4/native/artifact results with actual failures/skips/limits; A independently reviews the complete original Base..Implementation Head before PASS / CLOSED and CURRENT document reconciliation. |

## Implementation planning and validation allocation

B plans coherent full-stack Tasks only after implementation authorization and an ACTIVE committed
Contract. Lifecycle/settlement and its real consumers form one outcome; Automation metrics and its
native readback form another. B chooses actual Task boundaries from the code, keeping necessary
integration/tests with each behavior rather than splitting by enum, file, layer or test gate.
Task48.1 and Task48.2 have B PASS at `469ecc076c6efc660055f47277d7917a0b64a9aa:TASK.md`
and `d448ce5d392865daadccb085af61e39d98f786c8:TASK.md`. B stopped planning and submitted final
validation at the Closure Packet above. A returns Task48.1's flow/readback boundary for A48-01;
B owns the detailed correction plan, independent acceptance and refreshed Slice-final evidence.
The original Task48.1 Base is `4f11762d617d50555f3b106357e8f41988f7c2f9`; do not repin it or the
Slice Base, add unrelated improvements, or treat B's prior PASS as corrected-candidate acceptance.

Final risk is T4 because shared durable settlement affects the core pipeline, ownership/cancellation,
source-history gates and persistent/API/Web interpretation. Developer runs new/changed/directly
affected tests and relevant checks; B owns full regression and acceptance under workflow §6.
Affected areas include task persistence/scheduling/fencing, manual engine/continuations, direct
ordinary operations and history, Operations inventory/center, Automation operations/records/metrics,
source-history ownership and shared Web entity/API/UI tests. Use mocks/local servers/temporary
Storage roots and real Python/API/SQLite/Worker native desktop/narrow journeys for AC-5–13.
Applicable full/static/build/installed-wheel/container fresh/same-version restart/security gates follow
workflow §6; scope-specific tests cover the matrix/rate/fault/race boundaries above. No live user
media, production database, real external-service credentials or cross-version upgrade proof.

## Final validation, Closure Packet and A Final Review

**A decision: FIX REQUIRED — 2026-11-04.** Reviewed original Slice range
`ba84272721961c970f1eb85d616a0d129523ab92..2d4f1ae037cc4642b7bcd4231a840cf40d70e7b6`.
Review source HEAD `6c39d6ecdf40cad8f06e5e97f58bf47bdc388b49` differs from the implementation
only in TASK.md reports. The full production diff, affected journeys, settlement/SQLite fences,
ordinary-operation projections, CLI/API/Web consumers, Automation cohort/rate and actual B evidence
were inspected. No product implementation was changed by A. One concrete P1 blocks acceptance;
no CURRENT/closure reconciliation or new Slice selection is performed.

### A48-01 — P1: recovered-file proof overrides a durably failed Task flow

**Unmet:** RO-1/3/4, AC-4/7/11/13; `V2-TASK-013/014`, `V2-AUTO-012`.
The shared run SQL still evaluates `recovered_success` before current durable Task status
(`mediaflow/infrastructure/sqlite_runtime.py`, `_run_query_document`, predicate near line 5612,
`derived_status` near line 5864). A confirmed recovery summary plus verified file effects can
therefore turn a Task's real `failed` flow into `completed` / `recovered_completion=true`.
Automation's records-only outcome reads the durable failed status while its enclosing run uses that
competing projection. Task Center, record fields and the Task-based metric disagree.

**Existing-entry reproduction:** reuse
`test_v2_automation_run_once.RunOnceApiTests.test_recognition_decision_continues_analysis_summary_and_execution_on_one_task`:
real definition Run once admission → Worker Recognition wait → existing recovery decision/continue
APIs → real analysis → exact summary confirmation → resident manual execution and successful Storage
move. At its existing SQLite `release_scheduled_claim` terminal-completed write boundary, inject
one `sqlite3.OperationalError("database is locked")`. The Worker then uses the unmodified repository
to durably publish its orchestration failure. No Task/status/Result row is fabricated, no nonexistent
route is called, and the mutation occurs exactly through the production journey. This is a fault
injection at an actual SQLite write, not a claim that a spontaneous lock was observed in production.

Actual readback after that journey:

| Evidence / existing GET | Observed |
|---|---|
| Durable Task / file Result | `failed` / `SUCCESS` |
| `/api/v1/operations/runs/{taskId}` | `status=completed`, `recovered_completion=true` |
| `/api/v1/operations/automation/records?limit=20` | Top-level `completed` / recovered; nested `recordOutcome.status=failed`, with obsolete waiting-file explanation |
| Existing metrics GET at the fixture clock | completed 0, failed 1, evaluated 1, rate 0% |

This is an unmet selected Slice48 outcome, not reopening an accepted Slice or an independent bug.
The recovery projection predates this Slice (predicate `ea4e5346f6eb8e55b79cff43df398efc377caed8`,
2026-10-27; verified-own-effect extension `7655377204772aaba6fbec1ad4040005bbe28140`, 2026-10-28).
Slice48 retained it while changing records/metrics to durable flow meaning. No reproduced Base failure
or newly introduced regression is claimed; the current ordinary continuation reaches the conflict.

**Required correction:** current supported Task flow must remain backend-authoritative across run
status, recovery display, status filters/counts/paging, Automation record envelopes and metrics.
Verified file/recovery effects may remain independent facts but cannot override a Task-level flow
failure or imply saved flow completion. Reconcile the record's explanation with current Task/file
facts while preserving original times/attempts/effects and legitimate historical evidence. Add the
existing-entry regression above, including reopen and no replay; preserve successful recovery,
waiting, cancellation and missing-Result technical closure. B plans/reviews this bounded correction
inside returned Task48.1 and refreshes affected/final evidence under workflow §6. Do not add another
recovery product, repin work or invent successful effects.

### Evidence checked and independent validation

B's full packet remains at the immutable checkpoint above. Its raw local evidence is under
`.git/validation-evidence/2d4f1ae037cc4642b7bcd4231a840cf40d70e7b6/slice-final/`.
Actual logs support 2581 Python tests (7 disclosed optional skips), 253 default browser tests,
70 newly run native tests plus 14 matching reused Automation tests, matching reused Web quality/
build/1273 unit results, clean-source wheel and installed/container 10-case proofs, and Docker
security/restart/transfer gates. Artifact identities, the initial stale-module wheel rejection,
rebuilds and distinct image IDs remain disclosed; A does not recast them as one immutable image or
claim remote/production verification. Those passes do not cover A48-01 or accept a future fix.

A's independent local evidence:
`.git/validation-evidence/2d4f1ae037cc4642b7bcd4231a840cf40d70e7b6/a-review/`.

- `PYTHONPATH=tests:. .venv/bin/python -m unittest -v test_task_flow_status test_manual_task_engine test_v2_automation_run_once test_direct_file_operations test_direct_file_transfers test_automation_entrance_recovery test_notifications test_organize_source_history`: **313 passed**, 81.824s; `independent-python.log` and summary.
- `web/ npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/task-flow.python.spec.ts --workers=1 --output=<a-review>/native-flow`: **2 passed**, real Python/API/SQLite/Worker browser path; `native-flow.log` and summary.
- `PYTHONPATH=tests:. .venv/bin/python <a-review>/recovery-sqlite-publication-probe.py`: reproduces
  A48-01 through the journey above; exact script, full JSON and `blocker-summary.json` are retained.
  Script SHA256: `5cc04f467400c124c7466be28fe9f24fd12c012c5332599f24bd932817504458`.
  The reused success-only test's expected `settled is not None` assertion stops after the injected
  publication failure; this is reported in the JSON, not counted as a passing test. The authoritative
  evidence is the subsequent durable/API readback shown above.

A did not mechanically rerun B's full suites. The seven optional real-service/endurance skips and
all original deferrals remain. Acceptance stops at this P1; B supplies the corrected candidate and
updated packet before another whole-range A decision.

## Review workspace

Repository `/Users/songzhidong/mediaflow`, branch `main`, starting HEAD
`6c39d6ecdf40cad8f06e5e97f58bf47bdc388b49`; tracked files initially clean, workspace/Git writable,
governance preflight PASS. All pre-existing untracked OS/log/reference/output files and `15` remain
untouched/unstaged. Isolated fixture databases/media were used; no user runtime DB, private config,
production media, push, deployment, reset/clean/stash or history rewrite. This checkpoint changes
only the A decision, factual current pointers and returned-Task notice; B's packet is preserved in
Git and below that notice. The original activation facts follow.

## Activation workspace

Repository `/Users/songzhidong/mediaflow`, branch `main`, activation starting HEAD
`7824c2de71378ab5f69ed8e988c59689850437c1` for Task48.2 activation; immutable Slice Base remains as above. Governance
preflight passed; tracked files were clean and workspace/Git are writable. Pre-existing untracked
OS/log/reference/output files and `15` remain unstaged and untouched. This activation changes only
Contract authorization, Task status and current pointers; it does not execute product code,
touch private configuration or user database/media, push, deploy or rewrite history.
