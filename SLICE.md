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

The user's 2026-10-24 scope amendments integrate the diagnosed Automation defects and narrow
Task Center attention/recovery to four business problem types. These are required TARGET changes;
prior closure records remain historical facts. Base and Implementation Head remain unchanged.

## User decision and goal

用户实际使用发现多个按钮呈深色且文字不可辨，登录时尤其明显。用户随后明确：

- 重命名、删除等普通文件操作不进入操作中心；该中心只保留整理任务。
- 页面中的 Worker 状态显示、整理发现和手动操作板块全部移除。
- 手动整理统一从文件页进入，任务中心的整理创建入口删除。
- 自动化策略的“打开”和名称点击恢复可用；保存后继续修改 Enabled/启停不再误报旧版本冲突。
- 修复仅启用却未获无人值守授权时反复产生 `unattended_execution_authority_missing` 失败记录：
  清楚显示待授权、打通分析与明确授权，并在新定时任务受理前检查授权。
- “需要处理”及待处理任务统计只包含识别、元数据、分类、冲突四类当前问题；删除“失败恢复”。
  其他失败只在“全部任务 / 已结束”查看任务与失败原因，不单独统计失败或提供恢复指引。

本 Slice 交付按钮可读、文件操作归属清楚的 V2 体验：普通文件管理在原库页完成反馈与恢复，
文件选择式手动整理从资源库文件页发起，任务中心专注已受理整理的进度、结果与恢复。
“不进入任务中心”约束用户入口、列表、统计和处理归属，不取消后台耐久任务、结果或审计。
同时修复已复现的自动化详情读取、保存后表单版本残留及未授权调度问题，保留真实并发保护、
独立明确授权与运行时授权复核。

The explicit TARGET amendment is `V2-UX-004`, `V2-OPS-014–016` and `V2-FILES-007` in
[V2 Requirements](docs/v2-requirements.md#slice46-authorized-target--not-yet-delivered).
It supersedes the earlier all-command population, center-created manual entry, nine-view navigation
and general-failure attention/recovery. Eight views retain shared analysis, four-type native recovery
and all execution safety. CURRENT descriptions are the accepted Base until implementation and
acceptance; TARGET is not a delivery claim.
The Automation corrections fulfill existing `V2-AUTO-001–006`; they add no execution authority or
new Automation capability.

## Applicable requirements and journeys

- `UX-001–003/005–007/010`, `REQ-TASK-002/003/005–010`, applicable `REQ-RECOVERY-*`,
  `REQ-API-002/003` and `REQ-SAFE-001–009`: [Requirements](docs/requirements.md).
- `V2-UX-001–004`, `V2-WEB-001`, `V2-SHELL-001`, `V2-AUTH-001–003`, `V2-SAFE-001`,
  `V2-FILES-002/003/007`, `V2-AUTO-001–006`, applicable amended `V2-OPS-001–016`:
  [V2 Requirements](docs/v2-requirements.md).
- [Product Experience](docs/product-experience.md): V2 authentication/continuation; Real Storage
  Files/Common file maintenance; separate MediaLibrary journey; Manual organize/bounded discovery;
  Tasks/results/per-item recovery; complete native Automation workspace; Slice46 TARGET journey.
- [Task Center specification](docs/task-center-page-spec.md): accepted nine-view baseline amended
  by Slice46's eight views/four-type attention, same-interface summary/confirmation and results.
- [Architecture](docs/architecture.md): V2/authentication; Operations read projection and typed
  recovery; direct commands/durable Delete; admitted-transfer Worker lifetime; Automation focused
  publication/shared analysis and eligibility; Slice46 TARGET.

### Complete user journeys

**Readable actions:** open V2 Entry or a business page/dialog → distinguish action text, availability,
submission and keyboard focus → connect or use the permitted command → read success or stage-specific
validation/permission/transport failure and safe next action. Reconnect restores the supported read;
credentials stay memory-only and no command replays.

**Ordinary file management:** enter ResourceLibrary/MediaLibrary Files → inspect exact selection,
capabilities and bounded impact → submit an ordinary command or confirm Delete → follow local progress,
independent durable results and live-directory reconciliation. Failure shows completed steps, known
or uncertain effects and allowed repair/controls locally. Closing a dialog, reload, reconnect or service
restart retains access from the original library to relevant unfinished/attention work and bounded
recent results. Unknown admission is reconciled by exact durable identity, never guessed/replayed.

**Manual organizing and follow-up:** select live ResourceLibrary files/folders → explicitly prepare,
observe real discovery/stability progress → inspect same-interface exact summary → select eligible
items and separately confirm execution → follow the admitted organizing run in Task Center.
Preparation findings/unknown requests remain reachable from Files. Pre-execution problems stay in
preparation; admitted Recognition/Metadata/Classification/conflict problems use native task/type
recovery. Save a decision → analyze → review/confirm the eligible summary → inspect actual results;
completed/ignored outcomes clear only their exact current problem. Other terminal failures are
read-only history in All/Ended. Center views never offer arbitrary new manual-organize requests.

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
“打开” → read the exact saved definition and truthful grant eligibility, including ineligible
reasons → enter Edit → save a checked change → continue changing Enabled or use the existing
explicit enable/disable action on the same page → read the confirmed published state without
leaving/reopening. Genuine concurrent publication, validation/permission/read failure or unknown
submission preserves known durable state/input, explains the next action and never auto-replays.

**Scheduled authority:** a saved/enabled definition without unattended authority shows “待授权”
and a working native analysis/explicit-grant entry → review exact scope/effects → explicitly grant
→ observe current authorization/readiness → a normal eligible due occurrence executes through the
existing Worker. Known missing authority blocks new scheduled admission without repeated failed
Jobs/Tasks. Grant-action failures/unknown outcomes retain the safe next action on Automation.
Historical missing-grant failures remain read-only in Task Center All/Ended, outside attention and
without repair guidance; native Automation authorization remains available independently. With valid
authority and a complete healthy read, an empty scope reports no work; permission/Storage failure
is not emptiness.

## Base audit and reuse

- Shared `styles.css` gives `.mf-button` background `#202b24` with dark `--ink: #18243b`.
  Some pages override this locally; Entry uses the shared Button. Shared fields have the same color
  combination. This source-level cause still needs browser reproduction; no product fix is claimed.
- `OperationsLanding.tsx` renders global Worker/resident status, organizing-discovery readback and
  a manual-action section; landing/refresh also read those dependencies.
- `StorageFilesPage.tsx` already submits exact selected discovery and passes its durable identity to
  shared preparation. Unknown-admission guidance currently relies on center discovery records.
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

### RO-2 — Files-only manual organization and retained preparation recovery

Remove center new-organize CTAs, manual-action section and its independent source-selection entry.
ResourceLibrary Files is the sole normal entry for new file-selection-based manual organization.
Keep exact selections, pins, bounded preparation, same-interface summary/confirmation and return
context. MediaLibrary stays a destination, never an organizing source.

Shared preparation components/routes may remain for exact Files-originated work and legal
continuations. A generic new-organize URL without that context guides to Files without starting
work or offering another independent library picker. Preserve valid prepared-work deep links;
a route containing `operations` is not by itself an independent creation entry. Invalid/foreign/
stale context cannot choose a guessed library/request or start work.

Provide Files-local access to its bounded preparation progress, findings and exact unknown-request
readback after removing the discovery block. Close/refresh/reconnect never silently cancels,
resubmits or starts discovery. Analysis-only findings do not become execution tasks/authority.
The four business types' task recovery remains in the center and is not new-task creation.
Automation's published-definition-bound `运行一次`/scheduled journeys retain their authority and records;
this entry change does not add a generic manual file picker to Automation.

### RO-3 — ordinary-file progress, results and recovery stay local

Create-folder/text, Rename, bounded text Edit, Copy, Move and Delete belong to their originating
ResourceLibrary/MediaLibrary file surface. Replace normal center links/guidance with local inspection
and existing permitted controls/recovery. Reuse result dialogs/projections and only add bounded local
access needed to reopen relevant work/results. Multiple operations stay independent; equal IDs in
two library kinds never exchange scope, cache or authority.

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
admitted organizing runs and legitimate organizing continuations: standalone manual executions,
scheduled/definition-bound runs and actual linked Job/Task records. Preserve pre-Task organizing
queue/failures and explicit durable deduplication. Terminal failures outside the four types appear
only in All/Ended and their selected read-only detail/results/export. Discovery/analysis alone remains
preparation; admitted recovery links retain their supported context.

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

### RO-5 — usable Automation detail, continued editing and scheduled authority

Make both the definition name and “打开” entry render the saved definition before and after
enablement. Align the real eligibility projection and frontend contract with the supported shared
analysis model. Eligible, ineligible and permission/evidence-unavailable states show truthful bounded
reasons/next actions instead of making a valid definition unreadable. Do not fabricate eligibility,
freshness or zero-mutation evidence, relax unrelated malformed-response validation, or restore
retired Preview products to satisfy an obsolete contract. Reads create no work or authority.

After a confirmed own Save, update the form's saved values and observed publication identity
consistently so the next same-page edit/Enabled change or explicit enable/disable command can
complete without a false stale-state refusal. Submit the intended enabled state and display the
confirmed durable state; preserve disabled-first create/copy and the separation of enablement from
unattended grants/execution. A genuine peer publication still refuses stale commands and preserves
input for deliberate review; never silently overwrite or rebind a peer's change. Rejected/unknown
commands retain bounded failure/reconciliation guidance and never replay automatically.

Complete the native saved definition → shared zero-mutation analysis → exact explicit unattended
grant → scheduled execution journey. Show published, enabled, granted and ready as distinct states;
an enabled definition with no grant has an actionable “待授权” state, not only a raw error code or
an unusable Task Center repair control. Known missing authority must block new scheduled Job/Task
admission at the backend and expose bounded current readiness/next action on Automation, rather
than repeatedly manufacturing failed execution records. Preserve due-state idempotency/coalescing;
authorization recovery resumes normal eligible scheduling without replaying blocked ticks.

This is a narrow pre-admission readiness correction, not removal of Worker authorization. Recheck
live authority for already-admitted work and at mutation boundaries; revocation, changed scope,
permission loss and races still fail closed with truthful evidence. Keep prior failed Jobs/Tasks,
occurrences/results/audit and genuine post-admission failures visible. Native authorization remains
on Automation independently of Task Center history. All/Ended shows those failed records without
attention, separate failure counts or repair prompts. No automatic retry, relabelling or data cleanup.
Grant reads/errors cannot invent eligibility or authority. Healthy authorized empty scopes remain no-work;
unreadable/missing scopes or missing authority cannot be reclassified as empty/success.

## Required surfaces and architecture boundary

- Shared V2 actions/styles and actual Entry/business/dialog consumers.
- Both library kinds' command results and bounded local work/readback/controls; ResourceLibrary
  manual organizing preparation, exact summary and confirmation.
- Eight center lists/counts/options/cursors, four-type pending-task statistics and recovery, selected
  factual detail/results, affected Task/Job/former Failure Recovery deep links and necessary
  shell/Dashboard/return integration.
- Typed authenticated API/application queries and bounded repository projections over existing
  Job/Task/items/results, preparation, transfer/Delete and audit state.
- Automation inventory name/“打开”, definition detail/eligibility, focused Edit/Save/Enabled controls,
  shared analysis/explicit grant/readiness and native pre-start authorization.
- Existing Scheduler admission/readiness and Worker grant rechecks, with truthful Automation/Task
  Center history/counts over existing managed definitions, grants, due state and occurrences.

No second execution/recovery engine, catalog, lifecycle or mutation authority. Frontend cannot load
mixed pages and filter them locally. Storage stays behind ports; only OrganizerExecutor mutates.
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
only shared readability, integration corrections and the Automation corrections in RO-5 are included.
The limited Scheduler readiness check in RO-5 is in scope; no scheduler/queue redesign is authorized.

## Acceptance

| ID | Acceptance |
|---|---|
| AC-1 | Applicable V2 actions and Entry are readable with computed contrast and desktop/narrow visual evidence; focus/busy/disabled and existing auth continuation/token privacy work. |
| AC-2 | New file-selection-based manual organizing starts from ResourceLibrary Files and completes preparation → same-interface summary → selected confirmation → admitted task; center creation actions/independent source selection are absent. |
| AC-3 | Files can recover exact preparation/progress/unknown requests after close/reload/reconnect without the center discovery list, guessed identity, automatic submission or fabricated execution tasks. |
| AC-4 | Both library kinds complete ordinary work locally, including multiple operations, per-item results and existing safe controls/recovery after close/reload/restart; no normal center handoff remains. |
| AC-5 | Mixed histories spanning multiple pages produce organizing-only eight views/counts/options/cursors/details; pre-Task failures remain in All/Ended, explicit Job→Task deduplication and permitted continuations remain truthful. |
| AC-6 | The three removed blocks and exclusive landing reads are absent; task-specific Worker/pin/readiness and factual failure evidence remain readable, with recovery limited by RO-4. |
| AC-7 | Existing file/preparation links preserve exact principal/kind/source/pin or explain refusal; tampered/deleted/stale/foreign contexts and 401/403 create no work or cross-scope exposure. |
| AC-8 | Delete/Move/partial/unknown effects, lost responses, duplicates/concurrent controls and restart retain durable per-item evidence/fences; completed or uncertain mutations never replay. |
| AC-9 | Definition-bound Run once, scheduled records/statistics and native organizing recovery still work; no retired Scan/Preview/FileIndex product or new authority returns. |
| AC-10 | Required evidence passes or unavailable gates stay explicit; A reviews immutable Base..Implementation Head, then CURRENT documentation is reconciled at accepted closure. |
| AC-11 | Automation name/“打开” and direct detail links render valid saved definitions before/after enabling; real eligible/ineligible/unavailable eligibility evidence is readable, bounded and truthful. Malformed/401/403/not-found/read failures have safe recovery; reads create no work/grant/media effects and no retired product returns. |
| AC-12 | On the same Edit page, successful Save → another Enabled change/Save and Save → explicit enable/disable complete with correct durable readback, without a false conflict or forced reopen. Genuine concurrent changes still refuse stale commands and preserve input; failed/unknown commands never silently overwrite or auto-replay, and enablement alone grants/executes nothing. |
| AC-13 | Enabled/no-grant definitions show actionable pending authorization on Automation and complete native analysis → explicit grant → normal due execution. Repeated due ticks with known missing authority admit no new execution Job/Task; current readiness remains visible. Historical failures remain intact in Task Center All/Ended without attention, separate failure statistics or repair guidance. Worker/revocation/concurrency guards remain, old work never replays, and healthy authorized empty scope reports no work without masking permission/Storage failures. |
| AC-14 | Only current Recognition/Metadata/Classification/Conflict problems and their required human recovery steps enter Attention and pending-task statistics. Tasks deduplicate across types; type/file counts remain accurate across pages, filters, refresh and restart. Failure Recovery and separate Task Center failure statistics/guidance are absent, including former deep links; other terminal failures and factual reasons/effects remain accessible in All/Ended without success relabelling. |
| AC-15 | Four-type decision → analysis → exact summary/confirmation → real outcome remains Web-completable. Save/admission alone does not imply success; after actual resolution no stale review/continuation keeps a task in Attention. If all organizing work succeeds through exact linked recovery, overall display becomes Completed/recovered while prior failed attempts remain history. A new four-type blocker changes type; a purely technical follow-up failure becomes read-only All/Ended history. Mixed successful/ignored/four-type/technical/uncertain items retain independent truth without false success or completed/uncertain replay. |

## Validation and handoff

Final level is **T4**: moving Delete/transfer recovery and changing shared task-query visibility
crosses application/API/Web/persistence/authority boundaries. B sizes coherent Tasks from these
outcomes and actual code. Developer runs new/changed/directly affected checks and hands off each
coherent checkpoint. B owns full regression/acceptance under workflow §6; A does not implement or
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
- Real backend eligibility payloads must pass the frontend contract; extend Automation API/Web
  coverage for eligible/ineligible/unavailable reads and same-page repeated Save/Enabled commands,
  genuine concurrent publication and failed/unknown outcomes. After building, run the applicable
  `tests/e2e/automation-lifecycle.python.spec.ts` and `tests/e2e/automation-workspace.python.spec.ts`
  through the same real-Python Playwright configuration, without reopening between every command.
- Cover enabled/no-grant repeated due ticks, the full native analysis/grant/scheduled journey,
  read/permission/unknown-grant failures, revoke/queued-work races and restart. Verify no new failed
  execution records before admission, truthful Automation/Task Center counts and retained historical
  failures in All/Ended and native Automation readiness. Extend existing occurrence/execution/grant
  tests; compare healthy authorized empty scope, missing scope and missing authority without weakening
  Worker checks or auto-replay.
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
The current four-type attention amendment starts from checkpoint `b5ee45669a07f0c0058d971b9b6fe579e83177cc`
on the same branch with the same unrelated dirty files preserved; it does not repin the Slice Base.
