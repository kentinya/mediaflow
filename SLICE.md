# Slice 48 — Task Flow Status and Automation Success Rate

```text
Slice ID: 48
Name: Task Flow Status and Automation Success Rate
Owner: A — Slice Owner / Architect / Final Reviewer
Status: PLANNED
Base SHA: ba84272721961c970f1eb85d616a0d129523ab92
Implementation Head: NOT SET
Implementation Head Acceptance: NOT REVIEWED
Working Branch: main
Development Authorization: SLICE PLANNING ONLY — USER REQUEST, 2026-11-03
Risk: High
Final Test Level: T4
Next Action: USER AUTHORIZES IMPLEMENTATION; A ACTIVATES SLICE; B PLANS FIRST TASK
```

## Authority and accepted baseline

[AGENTS.md](AGENTS.md) and [Development Workflow](docs/development-workflow.md) govern scope,
roles, checkpoints, tests and acceptance. The user requested investigation without edits, then
selected separation of Task flow status from file outcomes, extended that meaning to Automation's
success rate, and explicitly requested Slice planning. This checkpoint records the selected TARGET;
it does not authorize product implementation, create an implementation Task or claim acceptance.
A must checkpoint an ACTIVE Contract before B plans implementation under the workflow.

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
- Automation's success rate counts Task flow completion only, without inspecting file outcomes.
- Keep stage/waiting explanations, per-file results and safe four-type continuation usable.

The planned amendments are `V2-TASK-012–014` and `V2-AUTO-012` in
[V2 Requirements](docs/v2-requirements.md). They amend the V2 realization of `REQ-TASK-002/003`,
affected aggregate/recovered-success wording in `V2-OPS-016`, and the success-rate realization of
`V2-AUTO-005`. They do not alter the frozen V1 baseline or declare the new behavior CURRENT.
Preserve `UX-001–007/010`, applicable `REQ-TASK-005–010`, `REQ-RESULT-*`, `REQ-RECOVERY-*`,
`REQ-SAFE-*`, `V2-TASK-001–011`, entry/authority boundaries in `V2-OPS-014/015/017`,
`V2-FILES-007` and `V2-AUTO-010/011`, except for the explicit aggregate/metric amendments above.
Original records-only file-result semantics under `V2-AUTO-006` remain separate.

Baseline investigation found file-derived settlement in
[task_persistence.py](mediaflow/domain/task_persistence.py) (`task_work_status`),
[task_runtime.py](mediaflow/application/task_runtime.py) and
[manual_task_engine.py](mediaflow/application/manual_task_engine.py). The current Task/run models
retain partial-success/paused values. Automation's metric query in
[sqlite_runtime.py](mediaflow/infrastructure/sqlite_runtime.py) additionally requires successful
primary-file evidence and no uncertain success item; its separate records-only projection is
intentionally file-sensitive. These are implementation gaps for the selected TARGET, not proof of
delivered new behavior; B must trace all affected producers and consumers before Task planning.

Complete TARGET journeys and technical contracts are in
[Product Experience](docs/product-experience.md#target--task-flow-status-and-automation-success-rate-slice48-planned)
and [Architecture](docs/architecture.md#target--task-flow-status-and-automation-success-rate-slice48-planned).

## RO-1 — one five-state Task lifecycle, independent of file outcomes

The current durable Task aggregate and its ordinary Web/API/CLI projections use exactly these five
flow states. Stages, queue eligibility, controls, file results and read availability are distinct facts.

| State | Meaning |
|---|---|
| `pending` | Work is admitted and waiting to start or legally re-enter machine processing. |
| `running` | The flow is unfinished, including processing, stability waiting and required human decision/confirmation. |
| `completed` | The flow normally finished its admitted scope and durably accounted for every item; this says nothing about file success. |
| `failed` | A Task-level flow failure prevented normal completion and can be truthfully persisted. |
| `cancelled` | An explicit Task cancellation was acknowledged at the safe boundary. |

Do not publish `partial_success` or `paused` as a current Task aggregate status. Pause remains
retired; waiting and unknown/unavailable read evidence are not additional Task lifecycle states.
Do not collapse processing stages or TaskItem/Result/attachment/transfer-operation vocabulary into
these five values. Audit the older twelve-value `mediaflow/domain/tasks.py` vocabulary and its actual consumers
so it cannot remain a competing durable Task lifecycle; shared scanning/pipeline stages may remain
as stages without a broad scanner rewrite.

Normal completion includes all files failed/partial, mixed results, all skipped/ignored, individually
cancelled items, recorded uncertain outcomes, healthy empty scope and complete history-excluded
scope. None is proof of successful media organization. Only actual Task cancellation yields
`cancelled`; counting cancelled file items must not infer that intent. No failed-item threshold,
success ratio, attachment failure or absence of successful files determines Task flow failure.

Scope completeness and durable/safe finalization still matter. An unfinished item, required human
step, queued machine stage or unacknowledged in-flight call keeps the Task unfinished. Preserve a
recorded Task-level failure even if some or all files succeeded; later item-derived aggregation cannot
turn it into completed. No flow completion before durable outcome/safe-boundary publication.

## RO-2 — explicit flow-failure boundaries and preserved execution safety

Apply the same lifecycle to manual Files/file/folder/mixed work, supported direct API/CLI/remote
organizing, scheduled due work, definition Run once and existing same-Task continuation. Ordinary-file
Task producers on both library kinds adopt this meaning where they write/read the shared Task
aggregate, without redesigning their per-operation results, admission, queues or controls.

| Situation | Required Task interpretation |
|---|---|
| File parsing/recognition/metadata/target/conflict/Storage/attachment failure is durably isolated and the flow can finish | Keep the file's real outcome; normal Task completion remains possible, even if every file fails. |
| Discovery root/list failure or an incomplete/overflowed scope prevents proving the admitted scope was processed | Task flow failure; never pretend this is healthy empty completion or execute a first-N subset. A bounded file-local discovery error may remain item-local when scope completeness is still proved. |
| A missing/corrupt required pinned context, broken work relation or orchestration error prevents the Task flow from finishing | Task flow failure with bounded stage/reason, known effects and existing permitted next action. |
| No/stale Worker, temporary readiness waiting, claim expiry/loss or a cooperative cancellation request | Not by itself a terminal failure. Preserve real waiting/ownership and existing safe settlement rules. |
| A dispatched Storage effect lacks durable outcome proof | Preserve uncertainty and fences; no guessed completion/failure, replay, automatic requeue or capacity/source release before the existing safe boundary. A safely recorded uncertain file outcome does not itself fail an otherwise completed flow. |
| Database/publication failure prevents recording a terminal outcome | Preserve last durable truth and unavailable/interruption evidence; do not claim the failure or completion was saved. |

Keep one authoritative application settlement policy for flow outcome and use it across producers
and claim-fenced repositories. Do not rebuild a parallel flow engine or infer completion by relabelling
an existing file aggregate. Cancellation acknowledgement wins races with normal finalizers;
stale-owner writes cannot publish a later terminal outcome. Preserve current queue capacity,
human-waiting slot release, current authority, immutable pins and atomic source ownership.

TaskItem/Result/attempt/checkpoint/attachment results, effect certainty, completed steps, audit/logs
and source-history gates retain their real meaning. Due/Run once still excludes a source version
whose latest formal file outcome is failed/partial even when its enclosing Task is completed.
New manual warning/confirmation remains. No successful/uncertain replay, implicit new authority,
repinning, new retry product, pause restoration, fifth recovery type or universal rollback.

## RO-3 — readable flow state and independent file results on all affected surfaces

Task Center keeps the same eight organizing views and four-type Attention union. Its state badges,
ended/running membership, counts, detail, management filters, paging and links use the same five-state
flow facts. Waiting stage/reason remains visible; waiting work is not labelled finished. Missing or
unreadable evidence is unavailable, not a fabricated Task failure, success or zero total.

A normally completed mixed-result Task reads, for example, “流程已完成；成功 7、部分成功 2、失败 1”.
An all-failed file population can show completed flow and truthful file failures together. File details
keep actual cause, effects and existing actions; a completed badge must not hide warnings or mean
“全部整理成功”. Progress counts settled/processed files independently from success counts; finishing
all admitted file attempts can reach 100% processing progress without claiming successful effects.
Task-level error/recovery presentation distinguishes orchestration failure from item errors.

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

## RO-4 — Automation success rate is calculated from Task flow alone

Keep the current authorized Automation-only population, local-month/timezone boundaries and admitted
cohort selection: due and definition Run once Tasks count once by durable Task identity. Ordinary
manual work, rejected admission, analysis-only/preparation work and later continuation are not extra
Automation runs. Compute the numerator/denominator server-side over the complete same read basis,
before page limits, independently of the file-sensitive records-only outcome projection.

```text
successful = count(Task.status == completed)
ended = count(Task.status in {completed, failed, cancelled})
successRate = successful / ended, or unavailable/no-ended-data when ended == 0
```

Cancellation remains in the existing ended denominator and is not successful. Pending/running,
including required human waiting, are outside that denominator. This carries forward the denominator
explained in the planning conversation; it adds no cancellation policy/configuration.

Remove requirements for a successful primary, all-file/attachment success, verified effect certainty
or a nonempty organized-file count from rate computation. All-file failure/partial/skip/ignore,
recorded uncertainty, healthy empty and complete history-excluded flows count as Task success when
Task status is completed. They do not acquire successful file effects. Rates/Task status follow the
current durable Task if permitted continuation changes its lifecycle; continuation never increases
the admitted Task count. Original attempt results/times remain immutable and independently readable.

Keep actual file counts, unknown effects, no-work/exclusion reasons and original Automation execution
records honest. In particular, zero successful files is not proof of zero work: an all-failed Task
must not become a healthy empty/no-work record. Original records-only file-result classification,
filtering, paging and times keep `V2-AUTO-006` semantics; clearly distinguish those original file
results from current Task flow success where needed. Do not use a file-sensitive record outcome as
a hidden replacement for Task.status in the success-rate query. Unavailable metrics remain unavailable.

## Required surfaces, exclusions and persistence boundary

Required: Task domain/settlement, actual producers/runners and claim-fenced SQLite writes/reads;
API/CLI/Web Task and run models; Task Center, Files ordinary-operation status and existing Task
consumers; Automation metric service/API/cards and records separation; applicable installed artifacts.
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
| AC-2 | Automated settlement matrix proves normal completion for all-success, mixed success/partial/failure, all-failed, all-partial, all-skipped/ignored, individual file cancellations, recorded uncertainty, healthy empty and complete history exclusions. File effects/results are unchanged. |
| AC-3 | Waiting decision/analysis/summary/confirmation, pending machine work and active/unacknowledged calls do not complete early. Existing human/stability waiting and queue-capacity behavior remain correct without introducing a sixth Task status. |
| AC-4 | Task-level scope/pin/relation/orchestration failures remain failed even with successful files; file-local failures alone never make Task failed. Incomplete traversal/overflow is not empty success or first-N execution. Persistence refusal preserves last durable truth. |
| AC-5 | Files direct/folder/mixed, direct supported API/CLI/remote, due, Run once and same-Task four-type continuation use the same flow settlement behavior. Both library kinds' ordinary-file Task producers adopt it without changing operation-result semantics or queue rules. |
| AC-6 | Concurrent cancel/finalize, stale claim/result publication, restart before/after mutation dispatch and recorded uncertain-file settlement preserve source ownership, capacity, pins, results, authority and completed/uncertain non-replay. Cancellation is explicit acknowledged Task intent, never inferred from file counts. |
| AC-7 | Real Task Center All/Running/Attention/Ended and four problem lists have consistent authorized counts/membership/paging; mixed/all-failed completed flows retain truthful file counts, causes, effects and readable progress. Waiting remains unfinished. Flow completion never falsely displays file recovery success. |
| AC-8 | Existing four-type decision → analysis → summary → explicit continuation works in the same Task through refresh/restart, preserving independent siblings and original attempts. No new technical/attachment replay or generic failure-recovery flow appears. |
| AC-9 | Automation population/rate uses completed/(completed+failed+cancelled), never file/attachment/record-outcome predicates. Pending/running are excluded, cancellation is counted once and zero ended Tasks produce no percentage, not fabricated 0%/100%. |
| AC-10 | With completed Tasks containing only failed/partial/skipped/ignored/uncertain or zero-work files, rates remain Task-based. A cohort of 8 completed, 1 failed and 1 cancelled is 80% regardless of file mix. Verify due/Run once deduplication, full-population counts beyond pages, local-month boundaries and denied/unavailable reads. |
| AC-11 | Legal current-Task continuation updates its lifecycle-based statistics without adding a run. Original records-only result/times/filter/paging remain independent and immutable; all-failed completed flow is not mislabelled empty/no-work or successful media organization. |
| AC-12 | Source-history admission still uses latest formal file outcome: a failed/partial item in a completed Task is excluded by due/Run once and warned for new Files manual confirmation, with old effects/history preserved. |
| AC-13 | Files local modals/readback on both library kinds, Dashboard, API/CLI, scoped logs/export and applicable notification consumers consistently distinguish Task flow status, per-file result and effect certainty. No unavailable truth is coerced to a valid Task outcome. |
| AC-14 | Fresh/same-version persistence and affected source-external wheel/container startup/restart consumers prove the five-state lifecycle, waiting, file evidence and original records survive; old-task/cross-version conversion is not required. |
| AC-15 | RBAC, bounds/confinement, exact manual/Automation/continuation intent, immutable pins, zero-mutation reads/analysis, C using Naming A/Classification A remaining C, cancellation/fences and successful/uncertain non-replay retain automated coverage. |
| AC-16 | B supplies applicable full T4/native/artifact results with actual failures/skips/limits; A independently reviews the complete original Base..Implementation Head before PASS / CLOSED and CURRENT document reconciliation. |

## Implementation planning and validation allocation

B plans coherent full-stack Tasks only after implementation authorization and an ACTIVE committed
Contract. Lifecycle/settlement and its real consumers form one outcome; Automation metrics and its
native readback form another. B chooses actual Task boundaries from the code, keeping necessary
integration/tests with each behavior rather than splitting by enum, file, layer or test gate.
No implementation Task is planned or approved by this A planning checkpoint.

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

This planning checkpoint verifies governance, document links/anchors, unchanged accepted closure
ledger, source-only planning manifest and whitespace. It does not claim product tests or completed
implementation. Unavailable required future gates remain pending, not waived or marked PASS.

Pre-checkpoint document validation passed: nine Markdown-only changed paths; 131 local links/anchors
and three immutable historical Git targets; unchanged prior closure-ledger/Roadmap/REQ-UX rows;
four RO, sixteen AC and four unique TARGET requirement IDs; no active implementation Task;
`git diff --check`. The committed-Contract governance check is run after the planning checkpoint.

## Final validation, Closure Packet and A Final Review

NOT STARTED. Implementation Head is NOT SET. All RO/AC delivery proofs, B acceptance and
independent whole-Slice A review remain pending. Slice47's review and actual limits are historical,
not validation of Slice48. Do not declare implementation PASS from this planning checkpoint.

## Planning workspace

Repository `/Users/songzhidong/mediaflow`, branch `main`, starting HEAD/Base above. Governance
preflight passed; tracked files were clean and workspace/Git are writable. Pre-existing untracked
OS/log/reference/output files and `15` remain unstaged and untouched. Only planning/requirement/
TARGET journey/architecture/pointer documents are selected for this checkpoint; no code, tests,
private configuration, user database/media, push, deployment or history rewrite is authorized here.
