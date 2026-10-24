# Slice 46 — V2 Organizing Task Center and Readable Actions

```text
Slice ID: 46
Name: V2 Organizing Task Center and Readable Actions
Owner: A — Slice Owner / Architect / Final Reviewer
Status: ACTIVE
Base SHA: e9f1a8dc607cfc6d5ea02141b058da8ce849cd70
Implementation Head: NOT SET
Working Branch: main
Development Authorization: USER-REQUESTED NEXT SLICE — 2026-10-24
Risk: High
Final Test Level: T4
Next Action: B PLANS THE FIRST TASK
```

## Authority and accepted baseline

[AGENTS.md](AGENTS.md) and [Development Workflow](docs/development-workflow.md) govern roles,
implementation, testing and closure. This newly selected Slice does not reopen or reinterpret
Slices43–45 acceptance. Base is the checkpoint before this Contract, not a later planning commit.
No product implementation or B Task is delivered by this selection.

The complete previous Slice43 Contract, A review, validation limits and attribution mapping remain
at `e9f1a8dc607cfc6d5ea02141b058da8ce849cd70:SLICE.md`. Its current-lineage accepted implementation
is `acc5c567788410cde68ed24b4fee12a84ee47ef2` (original review ID
`97316131946bdecc483b684f6e6f6ecb98c5594d`). Accepted45 closure remains at current-lineage
`3947fbe00963a17744570a2f7a95ac0146991d53:SLICE.md` (original
`13ecfc0e75fc34ff0ae489e655124a178943cba4`). Original review identities, deferrals and preservation
refs remain historical facts. This Slice does not rewrite history.

The user's 2026-10-24 scope amendments integrate the diagnosed Automation defects, narrow
Task Center attention/recovery to four business problem types, admit Files manual organizing
before business-rule resolution and make Automation enablement/Run once explicit execution intent.
These are required TARGET changes;
prior closure records remain historical facts. Base and Implementation Head remain unchanged.

## User decision and goal

用户实际使用发现多个按钮呈深色且文字不可辨，登录时尤其明显。用户随后明确：

- 重命名、删除等普通文件操作不进入操作中心；该中心只保留整理任务。
- 页面中的 Worker 状态显示、整理发现和手动操作板块全部移除。
- 手动整理统一从文件页进入，任务中心的整理创建入口删除。
- 自动化策略的“打开”和名称点击恢复可用；保存后继续修改 Enabled/启停不再误报旧版本冲突。
- 自动化移除独立无人值守授权步骤；明确启用即允许按已保存策略定时执行，解决
  `unattended_execution_authority_missing` 的重复失败，不再要求先分析、再单独授权。
- “需要处理”及待处理任务统计只包含识别、元数据、分类、冲突四类当前问题；删除“失败恢复”。
  其他失败只在“全部任务 / 已结束”查看任务与失败原因，不单独统计失败或提供恢复指引。
- 手动整理保留同源未结束工作去重及明确后缀排除；选文件夹时沿用资源库的媒体类型筛选，
  默认视频作为主文件，图片等按已有附件配置处理，不因未明确排除而自动成为独立整理项。
  不再要求规则全部匹配或先生成可执行摘要。明确提交后先受理整理任务，四类问题在任务内恢复。
- 自动化“运行一次”直接受理并执行该已保存整理策略一次，四类问题同样在任务内处理；
  正常文件无需先出摘要再确认一次。文件页手动整理仍保留任务内摘要与执行确认。
- 自动化定时运行和“运行一次”维持现有稳定性判断及有界等待/复查逻辑，撤回此前
  “首次发现不稳定就直接失败、完全不等待”的调整；仍未稳定的文件记失败，其他文件继续。
  下次自动化照常运行，不增加按上次失败结果筛选/重试的机制。

本 Slice 交付按钮可读、文件操作归属清楚的 V2 体验：普通文件管理在原库页完成反馈与恢复，
文件选择式手动整理从资源库文件页发起，任务中心专注已受理整理的进度、结果与恢复。
“不进入任务中心”约束用户入口、列表、统计和处理归属，不取消后台耐久任务、结果或审计。
同时修复已复现的自动化详情读取、保存后表单版本残留及未授权调度问题，保留真实并发保护、
明确执行意图、范围限制与运行时权限/安全复核。

The explicit TARGET amendment is `V2-UX-004`, `V2-OPS-014–017`, `V2-FILES-007` and
`V2-AUTO-010/011` in
[V2 Requirements](docs/v2-requirements.md#slice46-authorized-target--not-yet-delivered).
It supersedes the earlier all-command population, center-created manual entry, nine-view navigation,
general-failure attention/recovery and Files' ready-plan prerequisite for task admission. Eight views
retain shared analysis, four-type native recovery and all execution safety. CURRENT descriptions
are the accepted Base until implementation and acceptance; TARGET is not a delivery claim.
Automation's user-authorized `V2-AUTO-010/011` supersede independent grant/pre-analysis requirements
and Run once's analysis-then-confirm sequence in `V2-AUTO-002–006`. Enablement supplies bounded
scheduled intent; Run once supplies one deliberate execution intent. Broader file/destructive
authority is not implied. The previous grant journey is superseded TARGET, not unfinished delivery.

## Applicable requirements and journeys

- `UX-001–003/005–007/010`, `REQ-TASK-002/003/005–010`, applicable `REQ-RECOVERY-*`,
  `REQ-API-002/003` and `REQ-SAFE-001–009`: [Requirements](docs/requirements.md).
- `V2-UX-001–004`, `V2-WEB-001`, `V2-SHELL-001`, `V2-AUTH-001–003`, `V2-SAFE-001`,
  `V2-FILES-002/003/007`, `V2-AUTO-001–006/010/011`, applicable amended `V2-OPS-001–017`:
  [V2 Requirements](docs/v2-requirements.md).
- [Product Experience](docs/product-experience.md): V2 authentication/continuation; Real Storage
  Files/Common file maintenance; separate MediaLibrary journey; Manual organize/bounded discovery;
  Tasks/results/per-item recovery; complete native Automation workspace; Slice46 TARGET journey.
- [Task Center specification](docs/task-center-page-spec.md): accepted nine-view baseline amended
  by Slice46's eight views/four-type attention, same-interface summary/confirmation and results.
- [Architecture](docs/architecture.md): V2/authentication; Operations read projection and typed
  recovery; direct commands/durable Delete; admitted-transfer Worker lifetime; Automation focused
  publication, current grant/pre-analysis boundaries and their Slice46 replacements.

### Complete user journeys

**Readable actions:** open V2 Entry or a business page/dialog → distinguish action text, availability,
submission and keyboard focus → connect or use the permitted command → read success or stage-specific
validation/permission/transport failure and safe next action. Reconnect restores the supported read;
credentials stay memory-only and no command replays.

**Ordinary file management:** enter ResourceLibrary/MediaLibrary Files → inspect exact selection,
capabilities and bounded impact → submit an ordinary command or confirm Delete → follow local progress,
independent durable results and live-directory reconciliation. The header's 当前页面操作状态 button,
immediately left of 添加资源库 (添加媒体库 on MediaLibrary), uses the same button style and opens a
centered modal for this file page's ordinary-operation status, results and existing permitted controls.
Failure shows completed steps, known
or uncertain effects and allowed repair/controls locally. Closing a dialog, reload, reconnect or service
restart retains access from the original library to relevant unfinished/attention work and bounded
recent results. Unknown admission is reconciled by exact durable identity, never guessed/replayed.

**Manual organizing and follow-up:** select live ResourceLibrary files/folders → explicitly submit
整理 → check same-source unfinished organizing work and explicit extension exclusions → admit durable
organizing work without requiring all business rules to match. Folder expansion retains the library's
configured primary-media extension filter, defaulting to video, plus existing attachment semantics.
Follow discovery/stability/pipeline
progress and per-item findings in Task Center. Recognition/Metadata/Classification/Conflict problems
enter their native task/type recovery; ready items reach the exact in-task summary and selected
execution confirmation. Save a decision → analyze → review/confirm the eligible summary → inspect
actual results; successful siblings are not replayed and one blocked item does not erase others.
Files retains exact request readback/return context. Other terminal failures are read-only history
in All/Ended. Browsing or analysis-only preparation never implicitly submits an organizing task.
Center views never offer arbitrary new manual-organize requests.

**Four-type attention:** open “需要处理” or one of the four type lists → inspect the task's current
business problems → complete the corresponding native decision/analysis/confirmation → refresh
the authoritative result. A task counts once even when it has several types/items. Pending human
steps in that four-type journey stay reachable; queued/running recovery alone is not a human to-do.
When no such current problem remains, the task leaves attention even if historical technical failures
remain. A new four-type blocker moves to that type; a new technical failure is visible only through
All/Ended with its factual reason/effects, no generic recovery prompt or dedicated failure count.
If linked four-type recovery completes all organizing work successfully, the overall task display
becomes “已完成（恢复成功）”; original failed attempts remain independently visible in its history.

**Automation detail and continued editing:** open a published definition through its name or
“打开” → read the exact saved definition and truthful enabled/execution readiness, including unavailable
reasons → enter Edit → save a checked change → continue changing Enabled or use the existing
explicit enable/disable action on the same page → read the confirmed published state without
leaving/reopening. Genuine concurrent publication, validation/permission/read failure or unknown
submission preserves known durable state/input, explains the next action and never auto-replays.

**Scheduled execution:** save a definition → explicitly enable it → at a normal due occurrence,
admit and execute the saved bounded organizing policy through the existing pipeline. Enablement is
the scoped scheduled execution intent, with no independent grant, pre-analysis or pending-grant step.
It does not run immediately. Disabling/removing stops future due admission and unperformed scheduled
effects at safe boundaries; completed/in-flight effects are not rolled back. Configuration edits,
permissions, pins and readiness remain truthful and backend-authoritative.

**Automation Run once:** click 运行一次 on the published definition → admit a real organizing task
before rule/metadata/classification/conflict readiness → perform discovery/stability/full planning
inside the task → execute ready items within the saved policy, without a separate initial summary/
execution-confirmation gate. The click is this run's explicit execution intent. Disabled definitions
may run once with execution permission; this neither enables nor advances the schedule. Four-type
problems enter Task Center decisions/re-analysis/explicit continuation; successful siblings are not
replayed. A healthy empty scope is a labelled no-work outcome; unreadable scope is a factual failure.
Unknown admission reconciles the exact request. Historical grant failures stay unchanged in All/Ended.

**Automation stability:** scheduled execution and Run once reuse the existing shared organizing
pipeline's stability checks and bounded wait/re-observation. If there are unstable candidates but no
ready files, wait once and re-scan only when the shortest remaining interval is greater than zero
and at most 60 seconds. If ready files exist, do not wait for unstable siblings. Files still unstable
after this handling fail without media effects; ready files proceed. A later normal run applies its
ordinary saved scope/filtering and stability checks without a previous-failure retry/selection flow.
Instability failures remain factual All/Ended history outside four-type Attention. This supersedes
the earlier46 no-wait target; configured policy/real elapsed proof and Files manual handling remain.

## Base audit and reuse

- Shared `styles.css` gives `.mf-button` background `#202b24` with dark `--ink: #18243b`.
  Some pages override this locally; Entry uses the shared Button. Shared fields have the same color
  combination. This source-level cause still needs browser reproduction; no product fix is claimed.
- `OperationsLanding.tsx` renders global Worker/resident status, organizing-discovery readback and
  a manual-action section; landing/refresh also read those dependencies.
- `StorageFilesPage.tsx` already submits exact selected discovery and passes its durable identity to
  shared preparation. Unknown-admission guidance currently relies on center discovery records.
- The Files command currently requests `autoPrepare` discovery, then opens shared preparation;
  `media_discovery.py` rejects selected sources using extension/include/exclude/depth filters, and
  manual planning/execution requires ready intent/plan items before task admission. This explains
  why pre-task business problems cannot use task recovery; the TARGET moves that boundary, not just
  the button's disabled state. This is source inspection, not a new runtime reproduction.
- `FileCommandDialogs.tsx` sends Delete inspection/recovery to `/operations/tasks/$taskId`.
  `TransferDialog.tsx` already polls kind-scoped progress/controls. Both kinds reuse durable direct-
  command/Delete/transfer families. Local reopen/readback must replace the removed center handoff.
- `operations_run.py`, `sqlite_runtime.py` and `service_api.py` already provide explicit Job/Task
  linkage, bounded consistent pages/counts and durable results. Mixed ordinary/organizing work and
  other consumers, including Automation, share this projection; reuse it with explicit query scope.
- Isolated real-Python/temporary-SQLite/browser diagnosis reproduced both Automation defects:
  name/“打开” uses the detail route; its HTTP 200 grant-eligibility response lacks `current` and
  `zeroMutation` required by the frontend normalizer. The focused Edit route reads successfully.
- `AutomationLifecyclePage.tsx` retains its pre-Save candidate authority after a successful edit.
  Its own publication triggers the stale-input banner/disabled Save; a following enable/disable
  request uses the old identity and returns `409 configuration_version_conflict`. Durable saved
  values remain readable after re-entry. This is diagnosis, not a delivered correction.
- The user's actual error is `unattended_execution_authority_missing`. Scheduler currently admits
  an enabled definition before grant checking; Worker checks authority before Storage/Task creation
  and persists the Job as failed. The grant control is on the broken detail route, absent from Edit.
  Isolated runs confirmed healthy authorized empty directories complete with zero items, while a
  missing grant or missing scope produces distinct failures; emptiness is not this error's cause.

## Required outcomes

### RO-1 — readable shared buttons throughout V2

Repair the shared light-theme action palette and conflicting consumer overrides. Cover primary,
secondary, danger, button-styled links, dialog actions and accessible icon actions across Entry,
Files/MediaLibrary, Task Center, Rules, Storage, Automation and Settings. Normal/hover/focus,
selected, submitting and disabled states remain distinguishable; preserve focus visibility, action
semantics and busy/disabled duplicate-submit guards.

Enabled text meets WCAG AA contrast: 4.5:1 for ordinary text or 3:1 for qualifying large text.
Disabled labels remain legible and visibly unavailable. Verify computed browser colors and actual
rendered states, not only CSS literals/selectors. Fix the directly related Entry field colors where
needed for the same readable login journey; no form/authentication redesign or dark-mode product.

### RO-2 — Files-only manual organization before business-rule resolution

Remove center new-organize CTAs, manual-action section and its independent source-selection entry.
ResourceLibrary Files is the sole normal entry for new file-selection-based manual organization.
An explicit Files 整理 command admits durable bounded organizing work before complete rule matching,
metadata/target/conflict resolution or an executable summary exists. Directly selected files retain
the two business entry checks: unfinished same-source organizing work and explicitly excluded
extensions; a merely unlisted suffix is not an explicit exclusion for that deliberate file selection.
Folder expansion (including the folder part of mixed selections) retains the ResourceLibrary's
configured primary-media extension filter, whose default is video. This restores the existing
folder file-type behavior and supersedes the earlier46 all-non-excluded-folder-files target.
It does not hardcode video against explicit library configuration or restore rule-ready gating.
Other automatic scan include/exclude/rule-match readiness must not become additional manual vetoes.

Under the default media extensions, pictures/subtitles/NFO are not independent primary candidates
merely because they were found in a selected folder or their suffix was not explicitly excluded.
Existing policy-controlled attachment association remains: matched sidecars may follow an admitted
primary; unassociated files stay at source and create no Recognition/Attention problem. Disabling
artwork does not promote pictures to primaries. Preserve the existing other-same-stem option, which
can still associate matching pictures when enabled; no image-content/ad detection or automatic
deletion is added. Apply these folder semantics inside the admitted task's bounded discovery,
without changing explicit single/multiple-file intent or MediaLibrary's destination-only role.
A folder with no eligible primary explains that no eligible media was found; filtered sidecars
do not become fabricated Recognition failures.

Backend duplicate detection uses verified Storage/source identity, not just filename; include queued,
running, paused and unresolved four-type/recovery work, across manual/Automation/continuations.
Check/reserve each concrete source atomically with admission so overlapping/concurrent requests
cannot execute it twice. Show the exact existing run or explicit extension-exclusion reason per item;
eligible siblings remain independently admissible. A finished history record alone is not a perpetual
entry lock; completed/uncertain effects still cannot be replayed through a new request.

Keep authentication/RBAC, valid bounded source selection, library/root confinement and immutable
admission pins. Real stability waiting and downstream business analysis now belong inside the task;
neither rule misses nor instability force an analysis-ready prerequisite before task creation.
Folder traversal retains hard safety budgets and cannot execute a silently truncated first-N prefix.
Unreadable sources/configuration or technical errors never become fabricated business decisions.

Reuse the full pipeline and native four-type decisions within the admitted task. Missing/ambiguous
recognition, metadata decisions, classification misses and conflicts produce actual per-item problems
in Attention and its four lists/statistics. Do not force a default type, identity or destination to
make an item ready. Exact summary and explicit selected execution confirmation remain inside the
task before mutation, including separate permission for overwrite/Delete/cleanup where applicable.
Its normal summary/confirmation remains reachable in the exact task context without inventing a
fifth Attention type when none of the four business problems exists.
Task admission, analysis and decision Save confer no unreviewed media effects. Only OrganizerExecutor
mutates after source/capability/authority/fence checks; successful or uncertain siblings never replay.

Shared preparation components/routes may remain for exact Files-originated work and legal
continuations. A generic new-organize URL without that context guides to Files without starting
work or offering another independent library picker. Preserve valid prepared-work deep links;
a route containing `operations` is not by itself an independent creation entry. Invalid/foreign/
stale context cannot choose a guessed library/request or start work.

Files retains bounded access to the exact submitted work, unknown-request reconciliation and any
separate analysis-only/pre-existing preparation after removing the discovery block. Close/refresh/
reconnect never silently cancels, resubmits or starts discovery. Merely browsing or requesting analysis
does not create an organizing task or execution authority. Existing prepared-work remains supported;
it cannot force new explicit Files organizing back through the old pre-task readiness gate.
The four business types' task recovery remains in the center and is not new-task creation.
Automation uses its saved definition scope and retains its records; its changed execution intent
and Run once flow are defined in RO-5. No generic manual file picker is added to Automation.

### RO-3 — ordinary-file progress, results and recovery stay local

Create-folder/text, Rename, bounded text Edit, Copy, Move and Delete belong to their originating
ResourceLibrary/MediaLibrary file surface. Replace normal center links/guidance with local inspection
and existing permitted controls/recovery. Reuse result dialogs/projections and only add bounded local
access needed to reopen relevant work/results. Multiple operations stay independent; equal IDs in
two library kinds never exchange scope, cache or authority.

Use the user-selected header entry 当前页面操作状态, immediately left of 添加资源库, styled the same
as that Add button; apply the corresponding placement/style beside 添加媒体库 on MediaLibrary Files.
Clicking opens a centered modal with bounded ordinary-operation progress, independent item results
and existing permitted controls/recovery. Each entry retains its originating library/source context;
ResourceLibrary and MediaLibrary work never mix. Empty/loading/read-error states and modal dismissal/
keyboard behavior follow existing accessible conventions. Closing the modal neither cancels nor
replays work; this same entry reopens relevant durable work after close/reload/reconnect/restart.
Do not add a global operation center or new retry/undo authority through this presentation choice.

Retain durable Tasks/results/audit, claims and immutable admitted context, including supported
ordinary work admitted before46. Close/reload/restart must not strand known work. An in-memory ID or
single overwritable browser slot cannot be the only recovery index. Browser hints remain non-
authoritative and principal-isolated; backend readback validates exact kind/library/source. Missing
historical/library/pin context explains its restriction instead of silently rebinding.

Show per-item stage, effects, conflicts/refusals, uncertainty and safe next action. Reuse only
backend-permitted cooperative controls/safe continuation; add no retry/rollback authority. Delete
retains explicit intent; cross-Storage Move retains Copy→verify→Delete-source. Unknown effects are
inspection-only. Display/read failure never replays mutation. Successful work refreshes live Storage
without discarding unaffected selections or sibling results.

### RO-4 — organizing-only Task Center with truthful queries

Keep the shell, eight sibling views, detail/results/export and four-type native recovery. The views
are All, Running, Attention, Ended, Recognition, Metadata, Classification and Conflict; remove Failure
Recovery from navigation, filters, summaries and normal/deep-link recovery entry. Include supported
admitted organizing runs and legitimate organizing continuations: explicitly submitted manual tasks
through discovery/analysis/confirmation/execution, scheduled/definition-bound runs and actual linked
Job/Task records. Preserve pre-Task organizing
queue/failures and explicit durable deduplication. Terminal failures outside the four types appear
only in All/Ended and their selected read-only detail/results/export. Separate analysis-only requests
remain preparation; analysis stages inside an explicitly admitted manual task do not hide that task
from the center. Admitted recovery links retain their supported context.

Apply the organizing population on the backend before grouping, filtering, paging, counts and
problem membership. Cards/totals/options and all recovery views use the same authorized consistent
population. Ordinary-file, notification and unknown unrelated commands cannot leak through `all`,
filters/cursors, selected runs or legacy Task/Job lists. Classify from supported command semantics
and durable admitted context/links, never display labels, substrings or today's mutable Active.

Attention and every Task Center pending-task badge/card/count are the distinct union of current
Recognition, Metadata (candidate/correction), Classification and Conflict problems. Type lists keep
their own task/file counts; never sum overlapping type counts as the task total. Preserve explicit
four-type lineage through required human decision/analysis/summary-confirmation steps; decision
Save or analysis completion alone cannot strand that unfinished journey. Queued/running follow-ups
without a required human action belong in Running. Genuine completion or an explicit permitted
skip/ignore clears the relevant problem without inventing organizing success.

Other technical failures—including network/Provider transport, Storage, permissions/grants, missing
configuration/source, partial or uncertain effects—are not a fifth type or a fallback attention
reason. A Provider outage is not a Metadata decision solely because it occurred during lookup.
Remove Task Center's separate failure totals/cards/problem counts and generic retry/repair/inspection
guidance for these failures. All/Ended retain real failed/partial status and bounded factual reasons,
stages, per-item completed/uncertain effects, logs and export; their inclusive totals still count the
records. Status filtering within All/Ended may locate failed records without a separate failure
statistic or recovery page. Existing administrative API/CLI recovery remains outside this V2 UX.

Mixed tasks enter attention only for their current four-type problems. Resolving all of those removes
the task even if another item has a technical failure; do not relabel that run Completed or discard
its failed result. If recovery itself ends in only a technical failure, retain that outcome in
All/Ended and remove obsolete four-type attention; never keep stale review/continuation flags alive.
Where all work instead reaches verified success through exact linked four-type recovery, project
the task's overall display as Completed/recovered without rewriting prior attempt outcomes or
counting the recovery twice. Decision Save, analysis, skip/ignore or missing evidence is not proof
of organizing success; detail/results preserve their distinct dispositions.
An unresolved four-type decision alongside an uncertain effect can remain visible, but uncertainty
never gains execution authority. Refresh/restart preserve the same membership and truthful counts.

Remove global Worker/resident status, organizing-discovery and manual-operation blocks plus their
exclusive landing reads/polling/refresh dependencies. Task-local readiness and factual failure
evidence remain; recovery guidance/actions are limited to the four types. Empty states explain scope;
no replacement monitoring page is required.

Ordinary-file deep links resolve to their local inspection context or bounded permission/unavailable
recovery without executing. Necessary shell/Dashboard/return-link corrections prevent alternate
creation entries or stranded file work. Shared administrative API/CLI evidence and Automation records
remain functional; center-specific scope never deletes data or silently changes another consumer.

### RO-5 — usable Automation detail, enable-to-execute and real Run once

Make both the definition name and “打开” render the saved definition before/after enablement.
Replace mandatory independent-grant eligibility reads/normalization with the supported enabled/
execution-readiness contract; remove grant/revoke/pending-authorization controls and their exclusive
preflight dependencies. Valid disabled/unavailable states remain readable. Do not fabricate old
analysis evidence or weaken malformed/denied/not-found/read-error handling. Reads create no work.

After a confirmed own Save, reconcile saved form values and publication identity so further Enabled
edits or explicit enable/disable succeed on the same page. Preserve disabled-first create/copy,
optimistic concurrency, peer-change refusal/input retention and exact unknown-outcome reconciliation.
A successful checked enable (including Saved Enabled=true), or deliberate Save of an already-enabled
successor, records bounded scheduled execution intent for that exact published definition. Show the
source/scope/limits and applicable organizing-policy effects being enabled; enforce backend execution
permission as well as applicable configuration permissions, and audit the actual actor/publication.
All supported enable/publication entry points enforce the same intent and permission boundary.
Browsing, unrelated publication, failed/stale commands or insufficient privileges cannot create or
expand execution intent.

Remove the independent unattended grant requirement and mandatory pre-analysis for scheduled work.
An enabled saved definition can execute at a normal due occurrence without a separate grant or a
per-run confirmation. New/copy remains disabled; enablement alone does not immediately create a run.
Enabled successors use the deliberate saved scope; legitimate admitted work retains immutable pins.
Known disabled/removed/permission-unavailable conditions are checked before due admission and again
at unperformed mutation boundaries. Disabling/removing withdraws future scheduled execution intent
and stops remaining scheduled effects cooperatively; no rollback or interruption of an in-flight
Storage call. Re-enabling does not replay old failed runs or accumulate blocked ticks.

Run once is a real execution command for the current saved definition, independent of its schedule.
Its explicit click supplies this run's bounded execution intent; no prior analysis/grant, external
file selection, executable-summary prerequisite or second initial execution confirmation is required.
Admit the durable organizing task before business-rule readiness. Reuse the scheduled organizing
pipeline, configured source scope/filtering, immutable pins, real stability and full backend
plan/source/capability/conflict/authority validation. Ready items execute; Recognition/Metadata/
Classification/Conflict problems wait independently in Task Center's four native recovery flows and
pending counts. Recovery decisions remain non-executing until their explicit safe continuation;
exact linked results govern removal/completion under RO-4. No forced default match or replay of
successful/uncertain siblings. Files manual summary/confirmation in RO-2 remains required.
Retain Run once's effective primary-source limit of `min(definition itemLimit, 100)` and existing
traversal/evidence budgets; sharing the pipeline does not silently raise its bound to the scheduled
ceiling.

A disabled definition can run once with current execution permission without enabling, changing next
due state or consuming scheduled intent. Source ownership is atomic across manual/Run once/due/
recovery work; repeats, lost responses, concurrent triggers and refresh reconcile exact request/run
identities without duplicate work. One accepted real execution counts once across its Job/Task and
Automation/Task Center records; separate analysis is not retroactively converted into execution.
Healthy empty scopes are labelled no-work; partial bounds cannot execute a first-N prefix, and
permission/Storage failures cannot masquerade as emptiness or success.

For both scheduled execution and Run once, preserve the existing shared organizing pipeline's real
stability checks and bounded wait/re-observation; the user withdrew the earlier46 immediate-failure/
no-wait target. The age check uses time since last modification against the larger configured
minimum-age/modified threshold; a nonzero stable-size interval requires unchanged observations
separated by that real duration. No prior observation is fabricated from old modification time.
When unstable candidates exist and no files are ready, retain one wait/re-scan if the shortest
remaining interval is greater than zero and at most 60 seconds; longer intervals do not synchronously
wait. If any files are ready, process them without waiting for unstable siblings. Preserve the
existing work-scoped evidence and continuation behavior; do not add cross-run observation sharing
or a new waiting lifecycle. Files still unstable after this handling fail without media effects;
ready siblings proceed. Retain factual reasons and truthful aggregates: only instability-failure
outcomes mean Failed, never empty/no-work success; stable success plus instability failure is
PartialSuccess. These failures appear in All/Ended without four-type Attention, pending-task counts
or a recovery entry. A later ordinary occurrence/Run once uses normal saved scope/filtering/stability
checks; add no previous-failure selection, automatic retry or old-result rewriting. Files manual
stability handling in RO-2 remains unchanged.

Existing published enabled definitions adopt the new Enabled semantics without requiring an old
grant, re-analysis or a forced off/on cycle. Old grants/revocations are historical evidence, neither
an extra gate nor a way to execute a disabled definition. Preserve supported already-admitted pins,
results, due-state idempotency/coalescing, fences, audit and old failed records; infer no new execute
intent from old analysis-only preparations or unknown requests. Reconcile these states explicitly
without relabelling failures or replaying historical work. Backend live permission/scope/effect
checks remain. Overwrite/Delete/cleanup require explicit policy and effect intent; enabling or Run
once cannot silently add those effects. This changes the intent boundary, not the execution engine.

## Required surfaces and architecture boundary

- Shared V2 actions/styles and actual Entry/business/dialog consumers.
- Both library kinds' command results and bounded local work/readback/controls; ResourceLibrary
  manual entry, atomic same-source/exclusion checks and task-before-rule-resolution admission,
  in-task discovery/analysis/four-type recovery, exact summary and confirmation.
- Eight center lists/counts/options/cursors, four-type pending-task statistics and recovery, selected
  factual detail/results, affected Task/Job/former Failure Recovery deep links and necessary
  shell/Dashboard/return integration.
- Typed authenticated API/application queries and bounded repository projections over existing
  Job/Task/items/results, preparation, transfer/Delete and audit state.
- Automation inventory name/“打开”, definition detail/execution readiness, focused Edit/Save/Enabled
  and real Run once; remove independent grant controls and mandatory grant-analysis dependencies.
- Existing Scheduler/Worker admission and live scoped-intent/permission checks, with truthful
  Automation/Task Center history/counts over definitions, pinned runs, due state and occurrences.

Reuse the existing execution/recovery engine and lifecycle; no second catalog or broader file
authority. Frontend cannot load mixed pages and filter them locally. Storage stays behind ports;
only OrganizerExecutor mutates.
Reuse durable evidence; justify/test any necessary additive schema change in its B Task and preserve data.

## Invariants and deferrals

Preserve RBAC/memory-only credentials, exact kind/root confinement, zero-mutation reads/discovery/
analysis, bounds/real stability, C identity under NamingPolicy A and ClassificationPolicy A, immutable
pins, explicit destructive/overwrite authority, atomic admission, capabilities, claims/leases/fences,
independent results/audit/redaction and completed/ignored/uncertain non-replay without silent fallback.

Deferred: new providers/commands; queue/Scheduler/Worker supervision redesign; MediaLibrary organizing;
cross-kind transfer; unbounded work; Upload/Download; new auth/Secret Store; dark-mode customization;
general redesign/localization; a global file-operation center; history cleanup/retention; cross-Task
bulk recovery; arbitrary historical Reprocess; automatic uncertain replay/rollback; V1 cutover;
Scan/Preview/FileIndex restoration/migration. Automation/Notifications/Dashboard are not redesigned;
only shared readability, integration corrections and the Automation intent/Run once changes in RO-5
are included. These Scheduler/Worker/authorization adaptations are in scope; no scheduler/queue or
supervision redesign, new file commands or unrestricted authority is authorized.

## Acceptance

| ID | Acceptance |
|---|---|
| AC-1 | Applicable V2 actions and Entry are readable with computed contrast and desktop/narrow visual evidence; focus/busy/disabled and existing auth continuation/token privacy work. |
| AC-2 | Explicit ResourceLibrary Files 整理 admits durable organizing work before rule/metadata/classification/conflict readiness or an executable summary; single/multiple/folder/mixed selections follow task-contained discovery/analysis → exact summary → selected execution confirmation. Center creation actions/independent source selection are absent; browsing/analysis-only preparation creates no organizing task. |
| AC-3 | Files can recover the exact submitted task and separate/pre-existing preparation/unknown requests after close/reload/reconnect without the center discovery list, guessed identity or automatic submission. Task progress and four-type findings stay reachable in Task Center. |
| AC-4 | Both library kinds complete ordinary work locally, including multiple operations, per-item results and existing safe controls/recovery after close/reload/reconnect/restart. 当前页面操作状态 sits immediately left of 添加资源库 / 添加媒体库 with the corresponding Add button's style and opens a centered modal; entries retain originating library/source context and never mix library kinds. Empty/loading/read-error/dismissal states remain usable; closing/reopening creates no cancellation or replay. No normal center handoff remains. |
| AC-5 | Mixed histories spanning multiple pages produce organizing-only eight views/counts/options/cursors/details; pre-Task failures remain in All/Ended, explicit Job→Task deduplication and permitted continuations remain truthful. |
| AC-6 | The three removed blocks and exclusive landing reads are absent; task-specific Worker/pin/readiness and factual failure evidence remain readable, with recovery limited by RO-4. |
| AC-7 | Existing file/preparation links preserve exact principal/kind/source/pin or explain refusal; tampered/deleted/stale/foreign contexts and 401/403 create no work or cross-scope exposure. |
| AC-8 | Delete/Move/partial/unknown effects, lost responses, duplicates/concurrent controls and restart retain durable per-item evidence/fences; completed or uncertain mutations never replay. |
| AC-9 | Definition-bound real Run once, scheduled records/statistics and native organizing recovery follow RO-5; no retired Scan/Preview/FileIndex product or broader file authority returns. |
| AC-10 | Required evidence passes or unavailable gates stay explicit; A reviews immutable Base..Implementation Head, then CURRENT documentation is reconciled at accepted closure. |
| AC-11 | Automation name/“打开” and direct detail links render saved definitions before/after enabling with truthful enabled/execution-readiness states. Independent grant eligibility dependencies/actions are absent. Malformed relevant responses/401/403/not-found/read failures remain bounded; reads create no work or media effects and no retired product returns. |
| AC-12 | On the same Edit page, successful Save → another Enabled change/Save and Save → explicit enable/disable complete with correct durable readback, without a false conflict or forced reopen. Genuine peer changes refuse stale commands and preserve input; failed/unknown commands do not overwrite/replay. Checked enable/enabled-successor Save records scoped scheduled intent with execution permission and audit, without immediately creating work. |
| AC-13 | Enabled definitions execute normal due runs without independent grants, grant pre-analysis or per-run confirmation; existing enabled/no-grant definitions need no off/on cycle and produce no missing-grant failures. Disabled/removed definitions cannot start future scheduled work or unperformed scheduled effects; live permission loss/disable/removal races fail closed without rollback. Changed enabled successors require deliberate checked publication and execution permission. Old grants/revocations/failed history do not override Enabled or replay/relabel work. Healthy empty scope reports no work; unavailable scope remains factual failure. |
| AC-14 | Only current Recognition/Metadata/Classification/Conflict problems and their required human recovery steps enter Attention and pending-task statistics. Tasks deduplicate across types; type/file counts remain accurate across pages, filters, refresh and restart. Failure Recovery and separate Task Center failure statistics/guidance are absent, including former deep links; other terminal failures and factual reasons/effects remain accessible in All/Ended without success relabelling. |
| AC-15 | Four-type decision → analysis → exact summary/confirmation → real outcome remains Web-completable. Save/admission alone does not imply success; after actual resolution no stale review/continuation keeps a task in Attention. If all organizing work succeeds through exact linked recovery, overall display becomes Completed/recovered while prior failed attempts remain history. A new four-type blocker changes type; a purely technical follow-up failure becomes read-only All/Ended history. Mixed successful/ignored/four-type/technical/uncertain items retain independent truth without false success or completed/uncertain replay. |
| AC-16 | Direct-file business checks remain same-source unfinished organizing work and explicit extension exclusion; a merely unlisted suffix does not veto explicit file selection. Folder/mixed-folder discovery retains the configured primary-media extension filter, defaulting to video, and existing attachment semantics. Default images/subtitles/NFO do not become independent primaries or generate Attention through primary admission; artwork-off does not promote images, and other-same-stem settings remain effective. Unassociated files stay at source; no ad-content classifier/deletion is added. Rule/include misses cannot demand a ready plan first. Duplicates/exclusions have truthful per-item reasons and independent siblings; source ownership is atomic across overlapping manual/Automation/continuation requests, including queued/paused/recovery work, and is not inferred from filename or any past task. Rule-miss/ambiguous-recognition, metadata-decision, classification-miss and conflict cases are admitted and reachable in their four task recovery lists/counts through real completion. Stability, bounds, RBAC/confinement/pins, exact confirmation and completed/uncertain non-replay remain enforced. |
| AC-17 | One explicit Run once on an enabled or disabled saved definition admits a real organizing task before rule readiness and executes ready items through the same bounded pipeline, without preliminary analysis/grant or a second initial summary/execute gate. Four business blockers enter native recovery/Attention/counts and complete without successful-sibling replay; Files manual summary/confirmation remains. Saved scope/filtering/limits/pins, schedule independence, source ownership, exact unknown-request reconciliation, empty/no-work, partial/incomplete bounds, permissions and uncertain effects remain truthful across refresh/restart and simultaneous triggers. |
| AC-18 | Scheduled execution and Run once preserve the shared organizing pipeline's existing age/stable-size checks and bounded wait/re-observation. With unstable candidates and no ready files, one wait/re-scan occurs only when the shortest remaining interval is greater than zero and at most 60 seconds; ready siblings avoid that wait, and longer intervals do not synchronously wait. Proven-stable files proceed, including those proven by the re-scan; remaining unstable files fail without mutation. A settled stable-success/unstable-failure mix is PartialSuccess, and solely instability-failure outcomes are Failed rather than empty/no-work success. Instability alone adds no four-type Attention/pending count or recovery entry. Later ordinary runs retain normal saved scope/filtering/checks, without previous-failure retry/selection, cross-run observation sharing or old-result rewriting. Configured real elapsed proof, work-scoped evidence and Files manual handling remain intact. |

## Validation and handoff

Final level is **T4**: local Delete/transfer recovery, shared task-query ownership and Automation
execution-intent/admission changes cross application/API/Web/persistence/authority boundaries.
B sizes coherent Tasks from these outcomes and actual code. Developer runs new/changed/directly
affected checks and hands off each coherent checkpoint. B owns full regression/acceptance under
workflow §6; A does not implement or
self-approve those Tasks. This Contract does not prescribe per-field/per-selector Tasks.

B's final evidence includes:

- Applicable shared full Python/Web/static/package and safety gates; isolated temporary media roots
  and fake/local services only. Cover RBAC, pins/fences, C→A identity and completed/uncertain non-replay.
- Mixed-population/paging/count/cursor/selection tests and both kinds' local ordinary-work unknown,
  partial/uncertain, reopen/restart/control journeys, including already supported admitted work.
  Existing anchors include `tests/test_operations_run_inventory.py`, `tests/test_operations_task_center.py`,
  `tests/test_media_library_direct_commands.py` and directly affected direct-file/transfer tests.
- Cover the eight-view/four-type contract on the full backend population: overlapping task counts,
  Metadata decision vs Provider outage, pre-Task authority failures, partial/unknown effects, mixed
  tasks, saved-decision/pending-summary steps, verified full recovery and overall completion display
  vs retained mixed failure, new blocker/technical failure,
  refresh/restart and removed Failure Recovery links. No generic failure may inflate attention or
  dedicated failure statistics; All/Ended/detail/export must retain its exact failed evidence. Reuse
  `tests/test_task_center_recovery_lineage.py` and current typed-recovery browser journeys, adapting
  obsolete fifth-type expectations without weakening authority or execution safety assertions.
- Real Python/API/SQLite/Worker browser journeys against built production assets. After building,
  from `web/`, run and meaningfully extend applicable specs with
  `npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/direct-files.python.spec.ts tests/e2e/operations-inventory.python.spec.ts tests/e2e/operations-task-center-visual.python.spec.ts`.
  Also cover Files-originated organizing, retained Automation links and native recovery. Node-fake
  E2E alone does not establish backend population, persistence or Worker behavior.
- Cover manual submission with recognition misses/ambiguity, metadata decisions, classification
  misses and conflicts: a real durable task exists before readiness, each native recovery/count
  works through verified outcome and restart. Exercise explicit excluded vs merely unlisted suffixes
  for direct file selection, automatic include-rule misses, mixed/folder selections, stability waiting
  and real bounds. Folder discovery must retain configured primary extensions and default video
  filtering: cover video with poster/fanart/same-stem images, unrelated ad images, subtitles and NFO,
  attachments/artwork on/off and other-same-stem settings. Unassociated non-primary files stay at source,
  create no independent Recognition/Attention item and are not promoted when artwork is off;
  explicit library extension customization remains honored. Cover folders containing only non-primary
  files with truthful no-eligible-media readback instead of Recognition failures. Shared
  Automation filtering stays unchanged. Overlapping/concurrent manual/Automation/recovery requests
  reserve one source once, while same-named distinct sources and terminal history are not falsely
  blocked. Preserve analysis-only zero mutation/no task authority, exact request readback, partial/
  unknown non-replay and in-task exact summary/confirmation. Extend existing preparation/direct-file/
  task-recovery tests rather than merely changing frontend eligibility fixtures.
- Real backend detail/readiness payloads must pass the frontend contract after obsolete grant
  dependencies are removed. Cover same-page repeated Save/Enabled commands, peer publication,
  denied execute/configuration permissions and failed/unknown publication; no command can fabricate
  execution intent. After building, meaningfully extend `tests/e2e/automation-lifecycle.python.spec.ts`
  and `tests/e2e/automation-workspace.python.spec.ts` through the real-Python Playwright configuration.
- Cover enable/enabled-successor intent, current enabled/no-old-grant definitions, disable/remove/
  permission-loss races with queued/in-flight work, unrelated publication, restart and old-grant/
  revoked/analysis-only history. No re-analysis/regrant or missing-grant failure may gate new
  supported runs; execution still fails closed for actual permission/scope/effect violations.
- Cover real Run once on disabled and enabled definitions from click to durable Task/Worker/results,
  with no normal second confirmation. Exercise four business blockers/recovery, concurrent due/manual/
  recovery source ownership, same-named distinct sources, lost responses/restart, empty/read-error/
  stability/overflow (including `min(definition itemLimit, 100)`) and correct execution statistics.
  No schedule change, first-N execution, historical/uncertain replay or destructive-intent escalation.
  Reuse current Automation Run once,
  definition publication/execution/occurrence and execution-safety matrix tests; adapt obsolete grant
  assumptions while retaining their actual permissions/fences/pin/effect safety assertions.
- Cover both Automation entry paths with ready/unstable siblings and initially all-unstable scopes:
  preserve the existing conditional single wait/re-scan and 60-second remaining-interval bound,
  including zero-duration, positive-size-duration, changed-source and over-bound cases. Only proven
  stable files execute; remaining unstable outcomes retain truthful failure/PartialSuccess without
  four-type Attention inflation or false no-work. Cover later normal scope/filtering/checks and old
  failure history; add no failed-item retry/selection or cross-run observation mechanism.
- Actual desktop/narrow Entry, local progress/results/recovery and simplified-center inspection;
  computed contrast and keyboard evidence for shared variants/overrides. Record candidate/artifact
  identity, actual commands/results, failures and skips; do not test only CSS implementation literals.

Planning validation is governance/document consistency and `git diff --check` only. No product test
or visual pass is claimed. Closure Packet and A Final Review: **NOT STARTED**. Implementation Head:
**NOT SET** until a reviewed implementation exists.

## Workspace record

Planning started on `main` at Base above; repository/Git/governance files were writable and the
preflight passed. Pre-existing deletion of `docs/pics/操作与任务.png` and untracked reference images,
logs, OS files and test/artifact directories remain unrelated, untouched and unstaged. Private
runtime configuration/databases/user media are not planning fixtures. No push is authorized/performed.
The current folder-media-filter amendment starts from checkpoint `fccf0ea4ac18c2683ed2095d2cb3e943bb3b0800`
on the same branch with the same unrelated dirty files preserved; it does not repin the Slice Base.
