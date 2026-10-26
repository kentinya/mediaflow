# Task 46.3 — Files-first admitted organizing and native item recovery

Authority: committed [Slice46](SLICE.md) RO-2, AC-2/3/16 and the necessary organizing-entry,
confirmation/readback and safety portions of AC-5/7/8/14/15;
[Development Workflow](docs/development-workflow.md). Read the
[Developer experience](docs/agent-experience/developer-implementation-role.md) before implementation.

```text
Task ID: 46.3
Parent Slice: 46
Status: FIX REQUIRED
Task Base: 83144be20c6c7bc787a0fafad7fabb3e177bde6a
Difficulty: High
Test Level: T4
Planner / Reviewer: B
```

## Goal

An operator selects live ResourceLibrary files/folders and explicitly submits 整理. The system
admits durable organizing work before business readiness, performs bounded discovery/stability and
the full planning pipeline inside that task, exposes actual four-type problems through native task
recovery, then requires exact selected execution confirmation before OrganizerExecutor changes media.
The operator can find the same task, preparation or unknown request after close/reload/reconnect/restart.
New manual file-selection work starts only from ResourceLibrary Files.

Journey: Files selection → explicit organizing admission → visible task progress → Recognition /
Metadata / Classification / Conflict decision when required → non-executing decision Save and safe
analysis → exact in-task summary → explicit ready-subset confirmation → independent durable outcomes.
A normal initial confirmation remains reachable in Running/All without becoming Attention. Technical
failures retain factual stages/effects and are never fabricated business decisions. Separate browsing,
analysis-only and supported old preparation remain non-executing preparation.

Requirements: `V2-OPS-015/017` and necessary `V2-OPS-014/016` integration; `V2-UX-001–003`,
`V2-WEB-001`, `V2-AUTH-001–003`, `V2-SAFE-001`; `UX-001–003/005–007/010`,
`REQ-TASK-002/003/005–010`, applicable `REQ-RECOVERY-001–009`, `REQ-API-002/003`,
`REQ-ATT-001–003`, `REQ-SAFE-001–009`. The Slice46 amendments supersede older pre-task filtering,
readiness and preparation-only semantics for explicit organizing, not for analysis-only work.
Read the complete TARGET manual/task recovery and CURRENT Files, Manual organize, bounded folder
and Tasks/results/recovery journeys in [Product Experience](docs/product-experience.md), the affected
TARGET admission/work-query and CURRENT task/recovery/manual/discovery contracts in
[Architecture](docs/architecture.md), and [Task Center specification](docs/task-center-page-spec.md)
TARGET entry/confirmation plus the retained exact summary and four-type recovery interactions.

### Actual code gap and reuse

- `StorageFilesPage.tsx::organizeMutation` calls `submitFilesDiscovery(autoPrepare: true)` and goes
  to `/operations/organize/new?discoveryId=...`. It admits preparation, not an organizing Task.
  Lost responses search a bounded recent discovery list; the unresolved copy relies on the center
  discovery section. Reuse its caller request identity, exact return context and non-replay behavior.
- `MediaDiscoveryService.admit` already bounds/stats selected entries without recursive traversal,
  pins Active and reconciles equivalent open preparation. `_refuse_unselectable_file`, directory
  admission and the shared walk apply automatic include/exclude/depth/extension rules. The shared
  `scan_filters.classify_entry` conflates an unlisted suffix with explicit exclusion. Preserve
  automatic semantics while separating the deliberate manual selection behavior required here.
- `media_discovery.py` already has bounded traversal, observations, stable-size waiting, attachment
  association, material-bound refusals and fenced atomic plan publication. Reuse these facilities;
  do not create another discovery/plan/queue engine or a global source catalog.
- `ManualOrganizeIntentService._snapshot_from_runtime` requires a compatible type policy;
  `_default_choice` can choose the first available type. This path cannot be the early admitted
  task's mandatory readiness gate or fabricate a RecognitionRule result for an unmatched source.
- `media_organizer.py`, `task_runtime.py`, `task_item_recovery.py` and
  `manual_recovery_continuation.py` already provide pipeline checkpoints, four-type decisions and
  exact summary/confirmation. `PersistentTaskCoordinator` acquires a source lock at item start and
  releases it when waiting for recognition/metadata/confirmation: that execution lock alone is not
  durable unfinished-work ownership across queue, pause, decisions and continuation.
- `sqlite_runtime.py::operations_runs_window` and related item/problem reads project durable linked
  runs. Extend necessary admitted-task membership/linkage, rather than disguising preparation as
  execution or doing browser merges. `OperationsLanding.tsx` and `OrganizeNewPage.tsx` still expose
  center creation, an independent library picker and global discovery/manual-action sections.

### All Slice outcomes reevaluated at planning

| Outcome | Assessment at Task Base |
| --- | --- |
| RO-1 readable actions | Complete: Task46.1 PASS retained at `6072f50d5b2e5268c35d6729290512d1ae986104:TASK.md` |
| RO-2 early Files manual organizing | Incomplete; selected by this Task |
| RO-3 local ordinary operations | Complete: Task46.2 PASS at Task Base; preserve its local modal/readback |
| RO-4 organizing-only eight views / four-type truth | Incomplete; this Task adds only the integration its newly admitted manual work needs |
| RO-5 Automation | Incomplete; changed intent/detail/Enabled/Run once/stability semantics remain outside this Task |

Task46.2 reviewed range: `6072f50d5b2e5268c35d6729290512d1ae986104..bb176f2f36c92d5f5298c19e8d1c9eed45c1a9e5`;
implementation `2541d0c89d70a965cfac4d9f45580fb6147a71cb`. Its acceptance/evidence limits and known
pre-existing row-menu native failure remain in `83144be2:TASK.md`; this plan does not rerun or relabel them.

## Implementation Scope

1. Trace the existing Files command → API discovery → resident Worker → pipeline → summary →
   confirmation → execution/recovery path. Make explicit organizing admission distinct from
   analysis-only preparation using existing durable Task/Job/intent/discovery infrastructure.
   Persist the source selection, actor, exact request identity, pin and real links atomically enough
   to avoid orphan/duplicate admission. Direct files may be stat-verified at admission; folders
   become durable outer work before traversal. No metadata lookup, full folder walk or ready plan
   may be required to create that organizing work. Preserve bounded validation, RBAC, enabled source
   library, root confinement, immutable pins and read-only browse semantics.
2. Separate manual entry rules from automatic scan filtering. A directly selected regular file is
   not rejected merely for an unlisted suffix, include miss or rule miss. Apply explicit extension
   exclusions and truthful unfinished-source checks per item; eligible siblings remain admissible.
   For folder/mixed-folder expansion retain configured primary-media extensions, default video, and
   existing attachment association. Other automatic include/exclude/match conditions cannot veto
   deliberate manual work. Preserve technical safety/traversal budgets and real stability inside
   the admitted task; do not globally weaken Scanner or Automation filtering. Distinguish explicit
   extension rules from a missing allowlist entry, including temporary suffix exclusions. Default
   images/subtitles/NFO are not independent folder primaries or fabricated recognition problems.
   Artwork-off does not promote images; enabled other-same-stem association still works. Custom
   primary extensions retain their deliberate configured meaning; unmatched files remain at source.
3. Add/reuse durable verified source ownership, separate in meaning from a short-lived execution
   lease. Atomically check/reserve each concrete source with its TaskItem admission; no database
   transaction spans Storage I/O. Ownership covers queued/running/paused/unresolved business work
   across manual, existing scheduled/Run once and legal continuation entrances. Use verified
   Storage-relative source identity and admitted context, never filename, UI labels or today's
   Active. Overlapping folder/direct requests and distinct library bindings to the same concrete
   source cannot execute it twice. Return the exact authorized existing-work reference/reason,
   without exposing a foreign principal's private context. A continuation inherits/transfers its
   legitimate lineage without self-conflict. Define release/settlement for success, permitted
   skip/ignore/cancel and terminal failure; neither a lease timeout nor decision Save drops an
   unresolved reservation. Finished history alone is not a perpetual lock; completed/uncertain
   effects remain protected against replay through both old and newly submitted requests.
   Supported pre-change unfinished organizing work must participate in the check; an empty new
   ownership index cannot make an existing queued/paused/recovery source appear available.
   Integrate this safety boundary into existing Automation entrances without changing RO-5 intent.
4. Run the actual shared Parse → Recognition → type-policy → Metadata → Naming → Classification →
   plan pipeline inside admitted work. Persist genuine per-item problems/checkpoints and expose
   existing four-type forms and counts; never force a default type/identity/target or turn transport,
   unreadable sources or invalid configuration into a business decision. Preserve independent
   siblings, explanations, C identity under A naming/classification, provider abstraction and pins.
   Reuse native decision → analysis → exact summary → confirmation → outcome. A new business
   blocker changes the relevant type; Save/analysis is not success. Necessary human recovery steps
   retain lineage; queued/running analysis alone is not Attention. Technical follow-up failure
   removes obsolete four-type problems without claiming success or erasing historical evidence.
5. Keep the exact normal summary/selected confirmation reachable from the admitted run in Running
   and All after refresh/service restart. Normal initial WaitingConfirm without four-type lineage
   is unfinished but outside Attention/pending counts. Preserve full completeness/bounds checks:
   material traversal/primary/depth/time refusal cannot authorize a silently truncated first-N run.
   Show partial read evidence and require the existing explicit known-subset acknowledgement where
   permitted. Summary binds source, pin, plans, attachments, operations/destinations and selected
   subset; overwrite/Delete/cleanup keep separate applicable authority. Revalidate on confirmation
   and at execution with current permissions, capabilities, source evidence and claim/fence checks.
   Repeated/concurrent/unknown confirmation converges on exact durable work; completed or uncertain
   effects and successful siblings never replay. Retain old prepared-work and supported recovery links.
6. Make ResourceLibrary Files the only normal new manual file-selection entry. Remove center
   creation CTAs and independent source-selection/manual-action flow; remove the center discovery
   section once exact task/preparation readback is available from Files, including its exclusive
   reads/polling/refresh dependencies. Give Files bounded durable access to its admitted work,
   separate/pre-existing preparation and exact unresolved request, independent of component memory,
   one overwritable slot or a recent-N-only lookup. Use principal-bound backend readback/paging;
   hints carry no credentials or authority. Generic new-organize URLs guide to Files without work
   or another library picker. Preserve exact valid Files/prepared/recovery context in shared routes;
   foreign/stale/malformed context never guesses a library/request or auto-starts discovery. Update
   necessary Shell/Dashboard/return links. Close/reload/reconnect is read-only and never resubmits.
7. Extend the existing Python/API/SQLite/Worker and browser fixtures through real supported commands.
   Add only necessary additive durable fields/indexes/links; justify any schema change with old-row
   preservation, fresh/upgrade/reopen and failure-atomicity tests. Update affected architecture
   contract facts for the newly delivered path, clearly retaining unimplemented Slice46 TARGET.
   Keep broader center population/eight-view/failure-removal and Automation redesign deferred.

## 本轮开发执行指南（B46.3-01 / B46.3-02）

本节把原 Scope 和 B 的修正要求具体化，不增加 Task、不缩小原验收，也不改变 Base、High/T4
或 FIX REQUIRED。保留已有文件/文件夹筛选修复，按以下顺序完成整个用户流程。
本轮交付目标是 Files → 真正的整理任务 → 处理问题 → 摘要确认 → 实际结果 → 重启后可找回，
不能再次仅交付筛选或单个内部步骤就申请整个 Task PASS。

1. **先把“整理”提交接到真实的耐久任务。**
   从 `StorageFilesPage.tsx::organizeMutation`、`submitFilesDiscovery` 和当前 Files API 入手，
   调整 `MediaDiscoveryService.admit` 及必要的 Task/仓储关联。明确整理请求通过权限、来源范围
   和请求级硬边界校验后，先持久保存整理任务、提交身份、所选库/范围、实际配置 pin 及真实关联，
   返回可读取的任务上下文。文件夹遍历和规则/元数据/目标计算交给现有 Worker 在任务内完成。
   不要先跑完整发现或等计划就绪，也不要只给准备记录换名称、添加一个不参与生命周期的假 Task。
   已有独立分析/旧准备记录仍按原身份读取；浏览或分析请求不能自动变成整理提交。

2. **让每个实际来源在整个未结束期间只归一个有效整理流程。**
   复用现有 TaskItem、来源身份、仓储事务和执行锁机制，补齐排队、暂停、等待决定期间的耐久
   来源占用。直接文件在已验证后检查；文件夹先建外层任务，再在遍历发现每个来源时，把
   查重/占用与对应条目准入原子提交。Storage 调用放在数据库事务外，提交时校验所依赖的版本。
   手动、现有 Automation 和合法续作共用这一安全边界；续作继承自己的关联，不能与自己冲突。
   重复项显示后端允许读取的已有任务；同批其他可用文件继续。成功、明确忽略/取消和失败按
   原 Scope 的规则结算，不能因为 Worker 租约到期或保存了决定就释放仍未解决的来源。
   保留旧未完成工作参与检查，避免新占用机制把旧任务的文件误判为空闲。

3. **区分“复用同一来源的处理”与“记录本次提交结果”。**
   修改 `admit` / `_reconcile_admission` 及必要的持久读回：每次提交必须能耐久读到自己的完整
   所选范围、逐项受理/已有任务/排除结论、具体原因和真实任务关联；不只保存筛过的可用来源。
   同一个处理任务可以被多次提交引用，但不能拿第一次提交的结果冒充第二次的结果。
   可以沿现有持久请求关联保存有界逐项结果，或用能区分完整选择的准入身份实现；具体结构由
   Developer 在现有架构内选择，不要求新队列、全局目录或通用幂等框架。

   下表是必须覆盖的具体结果，内部字段和状态命名沿用/扩展现有类型即可：

   | 用户动作 | 必须可读取的结果 |
   | --- | --- |
   | 提交视频 A，得到任务 123 | A 已受理，关联真实任务 123 |
   | 123 尚未结束，再提交 A 和带 `.part` 后缀的 B | A 已在任务 123；B 被排除并保留临时后缀原因 |
   | 第二次提交断线后，按第二次请求身份查询 | 返回第二次的两项结论；不会漏掉 B、改写第一次结果或再次执行 A |
   | 同批另有未被占用的正常视频 C | C 独立受理；A 的已有工作或 B 的排除不阻断 C |

   同一请求重复读回必须稳定；换了被排除项、并发提交、重新打开 API/SQLite 后也不能串用
   别次的结果。未知结果先读回，不能猜最近任务或自动重发；来源防重复执行仍由第 2 步保证。

4. **把现有分析、四类处理、摘要确认接入这个任务。**
   复用 `media_organizer.py` / `task_runtime.py` / `task_item_recovery.py` /
   `manual_recovery_continuation.py` 的实际流水线、决定、检查点和确认能力。
   缺少识别、元数据待选、分类未命中或冲突时，保存本任务的真实逐项问题并提供原生处理入口；
   不用首个类型或默认目标填平问题。网络/存储/配置故障保留实际故障原因。
   保存决定后只分析允许范围，展示精确来源、目标、操作、附件、可执行子集和高风险影响，
   由用户明确确认后才执行。普通初始 WaitingConfirm 在 Running/All 可找回，不计四类待处理；
   四类恢复过程保留必要人工步骤的关联。真正成功才算成功，已成功/效果未知项不能被续作重放。
   完整发现、真实稳定性和硬预算必须在任何媒体变更前校验，不能执行超限范围的前 N 项。

5. **先让 Files 能找回原工作，再移除旧入口并完成界面衔接。**
   给 Files 有界、主体隔离的耐久任务/准备/精确未知请求读回，覆盖多个提交，关闭、刷新、
   重新登录和服务重启后都能打开原上下文。普通文件操作仍留在现有本页状态弹窗。
   当这些读回接通后，在同一个 Task 中移除任务中心的新建整理、独立选库、手动操作和整理
   发现板块及其专属查询；保留合法旧准备/任务恢复深链，通用创建 URL 只引导 Files。
   更新必要的 Shell/Dashboard/返回链接。删除入口不能丢掉已知工作，也不能通过访问页面启动
   新工作。全局 Worker 区块、完整八视图查询范围收敛和 RO-5 意图变更仍按本 Task 原 Non-goals。

**受影响验证和交付要求：** 在 Required Tests 已指定的真实入口/现有测试模块中，加入以上
提交 A → 提交 A+B → 精确读回/重启 → 独立 C、两个连接并发占用、文件夹先建任务再遍历、
四类决定到实际结果、正常待确认返回的覆盖。沿用现有 Python/API/SQLite/Worker 和浏览器
harness；新增测试必须在交接中给出实际运行命令和结果。测试分工、T4 门禁和低于 50% 的
测试时间约束保持原要求，不能把 B 全量回归转给 Developer。
最后交付一个完成原全部验收的候选及 READY FOR B REVIEW 报告；列明剩余问题和实际失败。
中间可以有必要的实现提交，但不能把未完成的核心链路拆到新 Task，或把局部测试通过写成完成。

## Acceptance Criteria

- [ ] Single/multiple/direct/folder/mixed Files commands create observable durable organizing work
  before full business readiness. Folder admission precedes recursion. Browsing/refresh/analysis-only
  preparation creates no organizing work or execution authority; MediaLibrary remains destination-only.
- [ ] Direct unlisted suffix and automatic include/rule misses are admitted; explicit excluded
  extensions and unfinished-source duplicates have accurate per-item reasons/existing-work access.
  Eligible siblings survive refusals. Default folder images/subtitles/NFO do not become primaries;
  video/custom extensions and artwork/other-same-stem attachment settings behave as specified.
- [ ] Overlapping concurrent manual/direct/folder/scheduled/Run once/continuation requests across
  separate SQLite connections admit at most one effective owner per verified concrete source.
  Queue, pause, unresolved decisions and restart preserve ownership; legal continuation works.
  Equal names on different sources do not collide; overlapping bindings cannot bypass ownership.
- [ ] Genuine Recognition, Metadata candidate/correction, Classification and Conflict cases are
  admitted, enter their native task lists/counts and complete through decision/analysis/summary/
  explicit execution to real results. No default choice fabricates readiness. New blockers and
  technical failures keep independent state without stale four-type membership or false completion.
- [ ] Normal WaitingConfirm is reachable from Running/All after close/reload/reconnect/real API and
  repository reopening, with its exact summary, and creates no Attention/pending count. Four-type
  recovery retains its human confirmation lineage; decision Save/analysis grants no execution.
- [ ] Real stability, full bounds and completeness gates precede mutation. Over-limit discovery
  cannot execute the first 100 of 101 primaries; empty/no-eligible-primary differs from unavailable
  or incomplete scope. Partial read evidence never silently becomes a complete-scope success.
- [ ] Confirmation executes only the exact selected ready scope through OrganizerExecutor. Stale
  source/plan/permission, duplicate confirmation, uncertain effects, faults after mutation and
  restart retain fences/results; successful and uncertain siblings never replay or gain authority.
  RecognitionType C remains C with NamingPolicy A and ClassificationPolicy A.
- [ ] Center creation/manual/discovery entries and their exclusive reads are gone. Files can reopen
  multiple known tasks/preparations and reconcile a lost admission by exact identity without the
  removed discovery block, recent-N guesses or automatic resubmission. Valid old preparation links
  work; generic/invalid/foreign/stale creation context guides/refuses without new work or scope leaks.
- [ ] New Files/task/recovery states work at 1536×1024 and 390×844 with keyboard, readable actions,
  loading/read error/401/403/not-found recovery, focus and exact return context. Existing ordinary
  local operations, administrative APIs/CLI and Automation records/intents remain intact.

## Required Tests

Follow workflow §6. Developer runs new/changed/directly affected checks; B owns T4 acceptance/full
regression. Exercise success, invalid input, conflict, failure and important edges above through
existing supported entries. Fault injection may delay/fail actual adapters/persistence; do not prove
behavior with unreachable database inventions, guessed routes, fabricated success payloads or DOM state.

### Developer — affected tests

From repository root:

```bash
python3 scripts/check_governance.py
git diff --check
.venv/bin/python -m unittest tests.test_media_discovery tests.test_media_discovery_provider_manifest tests.test_organize_preparation
.venv/bin/python -m unittest tests.test_manual_organize_intent tests.test_manual_organize_preview tests.test_manual_organize_execution
.venv/bin/python -m unittest tests.test_operations_task_center tests.test_task_center_recovery_lineage tests.test_recovery_continuation tests.test_recovery_batch
```

Extend these suites with early admission, direct-vs-folder filtering/attachments, exact request
readback beyond recent pages, source ownership races/settlement, real stability/bounds, four-type
recovery and normal confirmation membership. Any new dedicated source-ownership test module must
also be run explicitly and named in the handoff. Run the directly changed Automation admission/
execution suites when integrating source ownership; do not run all Automation tests by default.
Apply `.venv/bin/ruff check <changed-python-files>` and `.venv/bin/ruff format --check <changed-python-files>`.

From `web/`:

```bash
npm run test -- run src/features/library/StorageFilesPage.test.tsx src/features/operations/OrganizeCreationPage.test.tsx src/features/operations/OrganizeDiscoveryPage.test.tsx src/features/operations/OrganizeRouter.test.tsx src/features/operations/OperationsRouter.test.tsx src/features/operations/OperationsInventory.test.tsx src/features/operations/TaskItemRecoveryPanel.test.tsx src/shared/api/operations-api.test.ts src/routes/router.test.tsx
npm run typecheck
npm run lint
npm run build
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts tests/e2e/operations-task-center-visual.python.spec.ts
```

Include any other new/changed component/entity/API tests explicitly. Apply Prettier to changed Web
files. Update the real-Python creation journey to begin from Files, not the removed center link.
Extend the existing harness/specs for real early admission, four business blockers, normal summary
return, exact lost response, backend reopen and actual selected execution. No new orchestration
framework or broad process-tool work. Run directly affected local ordinary-operation checks if
shared Files, task-link or query behavior changes; full direct-files/browser release matrix remains B-owned.

### B — acceptance and full regression

Review the entire immutable Task Base..candidate and reproduce the critical Files → admitted task →
four-type decision → analysis → confirmation → actual mutation path, plus direct/folder filtering,
parallel source reservation and normal WaitingConfirm readback. Verify backend service/repository
reconstruction over the same temporary database, not just page reload. Inspect real desktop/narrow
screenshots, read-error/permission states and no-write reads against built production assets.

Run the real-Python commands above and, from `web/`, the affected ordinary Files regression:

```bash
npm run test:e2e -- --config=playwright.direct-files.python.config.ts tests/e2e/direct-files.python.spec.ts
```

Run all applicable [shared full T4 gates](docs/development-workflow.md#shared-full-regression-commands):
full Python/Web/static/default E2E, wheel/installed-consumer smoke, C→A identity, RBAC, migration if
changed, source ownership/pins/fences and completed/uncertain non-replay. Since Worker/persistence
admission is affected, assess and run applicable packaged resident restart/deployment/security proof;
record exact candidate/artifact, commands/counts/skips and durable ignored evidence. Unavailable gates
remain pending, not PASS. Task46.2's known pre-existing row-menu native failure is not erased or
assumed fixed; retain its evidence and reassess only if this Task changes the relevant behavior.

Testing/build/probe wall time must be strictly below **50%** of this round's elapsed work time,
counting overlapping runs once, including failed probes. No deliberate waiting, repeated full suites,
weakened assertions/timeouts or transferred B full gates. A proven blocker permits early FIX REQUIRED
in this same Task. Planning requires only governance/document/whitespace checks, not product suites.

## Non-goals

- RO-4's complete organizing-only population across all legacy queries/details, eight-view/failure
  removal, all-history pending union and historical recovered-success projection. Necessary newly
  admitted manual-task membership and four-type lifecycle above are in this Task and cannot be deferred.
- Global Worker/resident block removal remains RO-4. No monitoring product, queue/Worker supervision
  redesign, general idempotency framework, source catalog or governance tooling.
- RO-5 Automation detail/Save/Enabled/grant removal/Run once intent or stability redesign. Only shared
  source-ownership safety integration is included; preserve existing saved filtering and authority.
- New commands/providers, MediaLibrary organizing, cross-kind transfer, global ordinary-operation
  center, cross-Task bulk recovery, arbitrary historical Reprocess, uncertain replay/rollback,
  Upload/Download, retired Scan/Preview/FileIndex restoration, auth redesign or unrelated row-menu fixes.
- Slice/Roadmap boundaries, A final review/closure or a second Task plan.

## Workspace and handoff

Planning starts on `main` at Task Base above. Governance passed; workspace/Git/TASK.md are writable.
Pre-existing deletion `docs/pics/操作与任务.png` and all untracked OS/log/reference/test artifacts,
including `15`, the Automation screenshots and `output/imagegen/slice45-task-center-v1.zip`, are
preserved and excluded. Private runtime configuration/databases/media are not fixtures. This planning
checkpoint changes only TASK.md; no push/publication. A-owned stale first-Task/Implementation Head
pointers in Slice/Roadmap/Progress are not changed by B or used to negate accepted Task46.1/46.2.

Planning validation: `python3 scripts/check_governance.py` PASS; `git diff --check` clean. No product
suite, runtime probe, build or media operation was run for planning; checking time is below 50%.

## Developer Completion Report

Status handed off: **READY FOR B REVIEW — candidate for the whole Task; no PASS claimed.**

Checkpoints on `main` after B's `FIX REQUIRED` (reviewed Head `2998b7e3`):

```text
b04f36e5  fix(organize): reserve each admitted source atomically and report real outcomes
79aa4941  fix(organize): let the pinned RecognitionRule decide a Files item's type
ba9d18a3  test(organize): cover the undecided-type journey and the real one-Task counts
```

`ba9d18a3` is the reviewable Implementation Head.  This report is a report-only
successor.  B's prior report at `2998b7e3:TASK.md`, the earlier reviewed range and
its ignored evidence directory are unchanged.

### B46.3-01 / P1 — the pinned rule decides the type; a miss is a real problem

`recognition_probe.py` (B's own probe, unmodified) at `2998b7e3`:

```json
{"recognition_rules":0,"admission":true,"stage":"prepared","preview_status":"previewed",
 "preview_item_statuses":["previewed"],"automatically_assigned_types":["A"],
 "recognition_view_total":0,"task_item_count":0,"mutations":0}
```

Same probe on this candidate:

```json
{"recognition_rules":0,"admission":true,"stage":"prepared","preview_status":"blocked",
 "preview_item_statuses":["blocked"],"automatically_assigned_types":[null],
 "recognition_view_total":1,"task_item_count":1,"mutations":0}
```

* `ManualChoice.recognition_type_id` is optional.  An undecided choice carries
  no downstream policy identity, because those policies *are* the pinned mapping
  of a type nobody has chosen; `ManualChoice` refuses a partial downstream set.
* A Storage-scoped Files admission now resolves each source by running the
  production `RecognitionRuleEngine` over the parsed local path/filename/
  extension.  A real match selects that type and its exact policy mapping; a
  miss or an equal-priority tie stays undecided.  `_default_choice` no longer
  reaches the Files path at all, and no catch-all rule was added.
* The analysis publishes an undecided source as its own native Recognition
  problem (choices = the pinned enabled types) with no destination, operation or
  policy identity, so no confirmable plan can exist before the decision.  A
  Provider/Storage/configuration fault is still a factual technical outcome.
* A saved native Recognition decision is applied to the linked intent item
  through the ordinary optimistic `update_choice`, which persists the pinned
  mapping and its audit.  A rule-resolved or operator-saved type is never
  overwritten; a decision that cannot be applied leaves the item a real problem.
* The pre-RO-2 analysis-only `/files/organize` entry keeps its historic
  initialized editor default (`files_admission=False`), so existing prepared
  work, definition Run once and the recovery DryRun continuation are unchanged.
  That is why B's four native-recovery E2E journeys still pass.

`recognition_journey_probe.py` (new, this round) shows the delivered journey
through real entries with an empty published rule set:

```json
{"admit_status":202,"stage":"prepared","task_items":["waiting_recognition"],
 "recognition_view_total":1,"checkpoint_actions":["resolve_recognition","ignore"],
 "decision_kind":"recognition","mutations":0}
```

### B46.3-02 / P1 — no acknowledgement without a committed scope

`scope_race_probe.py` (B's probe, unmodified) at `2998b7e3` returned
`second_claimed_admitted: [{Three}]` with the durable scope still `[One]`.  On
this candidate the same probe returns:

```json
{"second_status":202,"second_claimed_admitted":[],
 "second_refused":[{"code":"admission_not_committed","path":"Movies/Three.2003.mkv"}],
 "persisted_scope_after_actual_worker_wins":["Movies/One.2001.mkv"],
 "actual_work_count":1,"mutations":0}
```

`_extend_scope` now returns a third truthful outcome (`unpublished`), and
`_split_admitted` proves every proposed entry against the *committed durable
scope*.  An entry is `admitted` only when the committed scope really holds it; a
source another unfinished work owns keeps that work's exact reference; an
extension that never committed is reported as `admission_not_committed` with a
resubmit next action.  A technical failure is never called a duplicate source and
a frozen manifest is never widened.

### B46.3-04 / P1 — exact path identity and atomic initial ownership

`repeated_root_probe.py` at `2998b7e3`: canonical scope `Movies/One.2001.mkv`
(wrong), second submission 202, two distinct Tasks for one physical file.  On
this candidate: canonical scope **`Movies/Movies/One.2001.mkv`**, second
submission **409 `source_already_organizing`**, **no** second Task, zero
mutations.

`canonical_source_path` no longer infers "already Storage-relative" from a
textual prefix; it joins the known pinned root exactly as the adapters do, so a
root of `Movies` and a library-relative `Movies/One.mkv` can never disagree with
the real `Movies/Movies/One.mkv`.

`create_files_organize_work` now re-checks each already-observed direct source
inside its own `BEGIN IMMEDIATE` transaction.  The check and the Task/discovery
insert are one decision, the observed fingerprint travels from admission as the
verified identity (a replaced file at the same path is a different source), and
no Storage call happens inside the transaction.  `concurrent_source_probe.py`
(both requests observe the source free, then both try to commit) now returns
**one** admitted Task and a truthful 409 with the winner's `existingWorkId`
(`2998b7e3`: two accepted, distinct Tasks).

### Actual commands and results

From repository root:

* `python3 scripts/check_governance.py` — PASS; `git diff --check` — clean.
* `.venv/bin/ruff check mediaflow tests scripts` — clean;
  `ruff format --check mediaflow tests scripts` — 358 files formatted.
* `.venv/bin/python -m unittest tests.test_media_discovery
  tests.test_media_discovery_provider_manifest tests.test_organize_preparation
  tests.test_manual_organize_intent tests.test_manual_organize_preview
  tests.test_manual_organize_execution tests.test_operations_task_center
  tests.test_task_center_recovery_lineage tests.test_recovery_continuation
  tests.test_recovery_batch` — **386 OK** (44 s).
* `.venv/bin/python -m unittest tests.test_v2_automation_run_once
  tests.test_v2_automation_operations tests.test_configuration_snapshot
  tests.test_automation_run_once tests.test_automation_definition_execution
  tests.test_automation_admission tests.test_operations_run_inventory
  tests.test_operations_run_detail tests.test_scope_continuation
  tests.test_task_persistence` — **356 OK**.
* `.venv/bin/python -m unittest tests.test_v2_manual_organize
  tests.test_operations_workspace tests.test_manual_operations
  tests.test_runtime_files_browser tests.test_direct_file_operations
  tests.test_media_library_direct_commands tests.test_configuration_organize
  tests.test_configuration_destination tests.test_configuration_classification
  tests.test_configuration_destination_activation
  tests.test_configuration_destination_precheck
  tests.test_scan_retirement_stability` — **232 OK**.

From `web/` (built production assets):

* `npm run typecheck` — clean; `npm run lint` — clean;
  `npx prettier --check src tests` — clean; `npm run build` — built.
* `npm run test -- run` — **87 files / 1262 tests passed**.
* `npx playwright test --config=playwright.python.config.ts
  tests/e2e/operations-task-center-visual.python.spec.ts` — **2 passed**.

### The E2E gate is NOT green — read this before judging it

`npx playwright test --config=playwright.python.config.ts
tests/e2e/operations-inventory.python.spec.ts` on this candidate:
**22 of 41 passed**, and the failing set is order-dependent rather than stable.
I established a fresh baseline for comparison instead of guessing:

| Tree | Same command | Result |
| --- | --- | --- |
| immutable Task Base `83144be2`, freshly built in a worktree | 41/41 | **all passed** |
| this round's starting Head `2998b7e3`, freshly built | 20 failed / 21 passed | failed |
| this candidate | 16–20 failed / 21–25 passed (varies) | failed |

So these are **real regressions introduced by Task46.3 work**, not a
pre-existing family, and my round reduced but did not eliminate them.  What I
fixed and can point at concretely:

* the `retirement` stability journey asserted the superseded one-row-per-
  preparation accounting; it needed a published rule for its own library and the
  corrected counts — it now passes in isolation and in-file.
* the shell lost the task-center journey's return context when RO-2 removed the
  creation CTA.  The Files link now carries the grammar-validated context, which
  is the RO-2-authorized return-link correction; `new task selection…`,
  `a selected execution never blocks…`, `a brand-new ambiguous source…`,
  `a real standalone pipeline run…` and `the default unfiltered origin…` all
  pass in isolation after it.
* the ambiguous-source and sibling-independence journeys were being broken by a
  *harness* rule I added; narrowing it restored them.

What is still failing, honestly: the four business-blocker native-recovery
journeys, the batch-summary journey, the technical-recovery journeys, the
attachment-collision journey and the stability journey fail **only when run
after the earlier journeys in the full sequential file**, and pass in isolation.
Their assertions encode per-journey run counts
(`SEEDED_RUN_TOTAL + N`) and a "the summary was produced by the analysis run"
sequence that the corrected one-Task accounting shifted.  I did not finish
reconciling that sequence, so I am not claiming the file is green, not claiming
the remaining failures are harmless, and not claiming a base-only cause.

Testing/build/probe wall time was roughly 3 h 10 m inside a round of about
4 h 20 m (≈73 %, counting overlapping runs once).  That is **over** the 50 %
budget: establishing an honest Base baseline needed two extra worktree builds
and full E2E runs, and the order-dependent failures needed repeated focused runs
to separate candidate regressions from harness regressions.  It is disclosed
rather than rounded down.

### Known risks / limits

* The real-Python E2E file is not green (see above).  This is the single largest
  remaining risk for RO-2 and the reason RO-2 is not claimed complete.
* In this round the four-type publication is exercised end-to-end for
  **Recognition** (a new real Files journey, including decision → analysis →
  exact summary → confirmed execution → real cross-Storage move).  Metadata,
  Classification and Conflict still publish through the same
  `publish_task_item_problem` boundary and are covered by the existing recovery
  suites, but I did not add a new Files-admission browser journey for them.
* RO-4's complete organizing-only population/eight-view/failure-removal and
  RO-5's Automation intent changes remain outside this Task, as B's Non-goals
  state.  Only the shared source-ownership safety boundary is integrated, and I
  re-ran the affected Automation admission/execution suites (356 OK) after
  restricting the rule resolution to explicit Files admissions.
* The delivered schema is unchanged from `2998b7e3` (52); no additive column was
  needed for these three corrections, so no new migration journey applies.
* `scripts/operations_inventory_harness.py` publishes two new fixture rules.
  They are test-harness configuration for the isolated real-Python journey, not
  product behaviour, and B should judge them as harness changes.

### Remaining Slice outcomes

RO-1 complete (Task46.1).  RO-2: early durable admission, per-request results,
verified Storage source identity, atomic per-source reservation, truthful
admission outcomes, Files-only entry, Files readback, an undecided-type native
Recognition journey and truthful Task settlement are implemented and proven at
their real boundaries — but the real-Python E2E file is not green, so RO-2 is
**not** claimed complete.  RO-3 complete (Task46.2).  RO-4/RO-5 unchanged and
still TARGET.

## B Review Result

```text
Reviewed Task range: 83144be20c6c7bc787a0fafad7fabb3e177bde6a..2998b7e3bbc4b7afb46060f5755c261cdcf970b1
Executable candidate: 1e9eebc5; 2998b7e3 adds TASK.md and Python comments only
Decision: FIX REQUIRED — 2026-10-26
Open Task blockers: B46.3-01/02/04 (P1); narrower remaining causes below
B46.3-03: prior folder-filtering correction retained
Slice Required Outcomes / Surfaces all satisfied: NO
Next: SAME TASK FIX LOOP; complete Task46.3, no new Task or Slice closure
```

B reviewed the full 41-file Base..Head manifest/change set, retaining prior verified unchanged facts
and independently checking the new Task/problem/execution, source/transaction/schema and Web paging
changes. `1e9eebc5..2998b7e3` also changes comments in sqlite_runtime.py; inspection confirms no
executable successor difference. Original Task Base/Goal/Scope/High/T4/acceptance remain unchanged.
The previous review and probes remain at `cd6db051:TASK.md` and its ignored evidence directory.

### Verified progress

The previous simple cases are corrected on this candidate:

- A no-candidate Metadata outcome now creates one TaskItem and Metadata total 1, with zero effects.
- A ready file's explicitly confirmed execution completes the same originally admitted Task with
  one item; the old empty-running Task symptom is fixed in that successful single-file journey.
- Sequential `[One]` then `[One, Three]` really persists and discovers both files.
- The original real-Python remaining-scope test `a frozen mixed recovery preparation never
  republishes a decided sibling` independently passes after building the current production assets.
- Files now consumes backend cursors for its organizing history rather than only toggling the
  first loaded page. The new source-path columns and explicit library bindings are present.

These successes narrow the open blockers; they do not establish all four native recovery journeys,
all interleavings or full T4 acceptance. The three remaining findings below are the same original
no-forced-type, truthful admission and atomic concrete-source requirements, not new scope.

### Required corrections

1. **B46.3-01 / P1 — rule misses must remain Recognition problems, not forced default types.**
   In a real validated/published configuration with `recognitionRules: []` and enabled compatible
   policies, submit `Movies/One.2001.mkv` through the existing Files API, then run the real discovery
   Worker with the fixture's local synthetic Provider. Without an operator choosing any type,
   the intent assigns type A, the plan is `previewed`, Recognition total is 0 and the Task has no
   problem item. This violates RO-2/AC-16's explicit prohibition on default types making work ready.
   `_default_choice` still selects `snapshot.recognition_types[0]`, and `_run_item` passes that
   value as `forced_recognition_type_id`, so the new Recognition publication branch is bypassed.
   - Separate an actual explicit human type decision from an automatically initialized editor
     value. For new Files work, run RecognitionRule against the pinned source before selecting its
     type policy; persist a genuine unresolved/ambiguous Recognition item when no type is known.
   - Only force a type when a legal source-bound explicit decision already authorizes that choice.
     Preserve existing explicit manual edits and old prepared work without treating their defaults
     as a new Files user's choice. Do not repair this by disabling valid empty-rule publication,
     rejecting the Files request before creating its Task, or inventing a catch-all rule.
   - Add a real Files-admission journey for rule miss/ambiguity → native Recognition selection →
     analysis → exact selected confirmation → actual result. Also exercise Classification and
     Conflict through their required native paths and keep C→A identity, immutable pins and
     independent completed/uncertain siblings. Metadata list membership alone is not proof that
     all four business journeys are complete.
2. **B46.3-02 / P1 — do not acknowledge a scope extension that lost its write.**
   The simple sequential accepted-sibling case now works. However, use the same public sequence
   `[One]` then `[One, Three]` and let the real Worker finish/freeze One between the second
   request's open-work lookup and `extend_media_discovery_scope`. The second request returns 202
   saying Three is admitted, but the frozen durable scope is still only One and no second work
   holds Three. `_extend_scope` catches `DiscoveryConflict` and returns `(current, ())`, which
   falsely tells `_accept_onto_existing` that every proposed admission succeeded. Runtime-resolution
   failure and an unavailable extender similarly return apparent success.
   - Preserve an explicit accepted/refused/conflicted result from the actual transaction; derive
     the response/outcome row from committed scope, never from the proposed list after a failed
     write. No successful admission may refer to a file no durable work actually holds.
   - On a legal version change, re-read and perform only a bounded valid re-evaluation, or return
     the accurate outcome. If old work froze/settled, independently admit the still-free sibling
     through the existing boundary or report its real non-admission and explicit next action;
     never widen the frozen manifest or call a technical failure a duplicate source.
   - Extend the existing accepted-sibling test by scheduling a real Worker at the check/write
     boundary, and cover simultaneous extensions, exact request readback/reopen, bounds and stale
     pins. Assert the final scope and actual result, not just a 202 or JSON selection.
3. **B46.3-04 / P1 — complete exact path identity and atomic initial ownership.**
   The simple `nested/One` versus `whole/Movies/One` check is improved, but two supported cases
   still admit the same physical source to distinct Tasks:
   - Root `Movies`, relative selection `Movies/One.2001.mkv`, actual file
     `source:Movies/Movies/One.2001.mkv`: `canonical_source_path` guesses the relative value is
     already Storage-relative because it starts with `Movies/`, and stores the wrong canonical
     value `Movies/One.2001.mkv`. Submitting the same file through the whole-root library as
     `Movies/Movies/One.2001.mkv` then also returns 202 with a different Task and no existing-work
     refusal. Remove this ambiguous prefix inference. A library-relative input always joins its
     known pinned root; already-Storage-relative callers must have an explicit separate contract.
   - With the ordinary `source:Movies/One.2001.mkv`, two normal admission calls on separate SQLite
     connections and overlapping library bindings both observe that exact canonical path free.
     Synchronizing the real ownership reads before their writes yields two distinct admitted Tasks
     with identical canonical source identity. `extend_media_discovery_scope` has an atomic recheck,
     but `create_files_organize_work` still only checks an actor/scope admission signature inside
     its transaction. An atomic Task+discovery insert is not an atomic source check/reservation.
   Recheck/reserve each verified direct source with initial admission in the same transaction, and
   use the equivalent source-item boundary for discovered files and other existing entrances.
   Keep pin/principal/library context distinct from physical source identity, preserve safe legal
   continuation, and make competing requests return truthful per-item existing-work references.
   Cover initial direct admissions, folder item admission and extension, not only the extension
   path; test concurrent aliases, repeated directory names, distinct actual roots and reopen.
   Never span Storage I/O with the reservation transaction, silently rebind legacy evidence or
   permit successful/uncertain effects to replay.

Keep these corrections in Task46.3 and its existing components. Do not create additional governance
Tasks, a second queue, a source catalog or a generic process framework. Update architecture claims
only to reflect behavior actually delivered and verified; the existing Source/Task guarantees are
not weakened by documenting the current defects.

### Independent checks and evidence

Local durable ignored evidence: `.git/validation-evidence/2998b7e3/b46.3-review/`.

| Check | Actual result |
| --- | --- |
| Governance; `git diff 83144be2..2998b7e3 --check` | PASS / clean |
| `.venv/bin/python -m unittest tests.test_media_discovery.AdmissionAndScopeTests` | 15 OK, 1.04 s process wall; `admission-tests.log`; SQLite ResourceWarning retained |
| `recognition_probe.py` | Published no-rule configuration → automatic type A, `previewed` plan, Recognition total 0 / TaskItems 0; zero effects; `recognition.log` |
| Prior `task_flow_probe.py` against current source | Metadata total 1 / TaskItems 1; zero effects; `task-flow.log` |
| Prior `completion_probe.py` against current source | Same admitted Task completed, one item, three actual temporary Storage effect calls; `completion.log` |
| Prior `overlap_probe.py` against current source | Sequential One+Three persists and walks both; zero effects; `overlap.log` |
| `scope_race_probe.py` | Actual Worker freezes old work before extension; Three falsely reported admitted with frozen scope still One; zero effects; `scope-race.log` |
| `repeated_root_probe.py` | Incorrect canonical path for repeated root name; same physical source accepted twice to distinct Tasks; zero effects; `repeated-root.log` |
| `concurrent_source_probe.py` | Two separate SQLite connections both see canonical `Movies/One.2001.mkv` free, both admit distinct Tasks for it; zero effects; `concurrent-source.log` |
| `npm run build` (`web/`) | PASS, existing chunk warning; `native.log` |
| `npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts --grep 'a frozen mixed recovery preparation never republishes a decided sibling' --output=../.git/validation-evidence/2998b7e3/b46.3-review/native-artifacts` (`web/`) | 1 passed, 7.49 s process wall; real Python/API/SQLite/Worker/current production build; `native.log` |

All scenarios start at existing Files application/API/Worker entries over temporary Local Storage
and SQLite. Empty Recognition rules pass the production configuration validation/publication path;
no impossible state or invented route is used. Race probes delay an actual ownership read or scope
write while the other real admission/Worker proceeds; no fabricated success payload, direct state
insertion or DOM manipulation proves their result. The successful completion probe explicitly
confirms the existing exact plan and confines real effects to temporary roots. Duplicate admissions
are proven; actual double mutation, data loss or exploitation is not claimed.

The developer-reported full E2E failures remain visible. Its comparison baseline `cd6db051` is a
prior rejected review checkpoint, not immutable Task Base `83144be2` or an accepted waiver. No claim
that the remaining 20 failures are harmless or baseline-only is independently accepted here. Native
results/counts from different full-file runs do not by themselves establish causation; analyze exact
failure behavior and required outcomes. B independently establishes only the focused success above.
The report also discloses testing/build/probe time about 76% of its round, exceeding the user's
50% ceiling. This is recorded as a process deviation, not a fabricated product failure or a new
Task; future fixes use the affected-test plan, with full T4 acceptance still B-owned.

Workflow §6 permits early FIX REQUIRED after proven blockers. Full T4 regression/static/default/native/
packaging/installed-consumer/schema/failure-atomicity/resident-restart/safety gates remain pending on
a corrected complete candidate; no gate is waived, no Developer full results become independent B
acceptance, and no full visual/native success is claimed. B's review started at 23:07:03 UTC on
2026-10-25 (2026-10-26 local); tests/build/probes took less than 20 seconds subprocess wall time
inside more than three minutes of code/contract/evidence review before reconciliation, strictly
below 50%. No deliberate waiting, repeated full suite, retries or weakened assertions/timeouts.

### All Slice outcomes reevaluated

| Outcome | Assessment at reviewed Head |
| --- | --- |
| RO-1 readable shared actions | Prior Task46.1 acceptance retained; small paging CSS change has no final visual claim |
| RO-2 Files-first organizing | Incomplete: tested Metadata/basic completion/sequential sibling paths improve; no-forced-type, truthful concurrent admission and source ownership still block |
| RO-3 local ordinary operations | Prior Task46.2 acceptance/evidence limits retained; shared persistence changes still await full acceptance |
| RO-4 organizing-only center/four-type truth | Incomplete; broad eight-view/population/failure-removal remains outside this Task, new manual-task integration is still this Task's duty |
| RO-5 Automation detail/Enabled/Run once | Incomplete; unchanged intent semantics, shared ownership must remain safe across entrances |

Slice stays ACTIVE. Only B-owned TASK.md changes in this checkpoint; all pre-existing dirty/untracked/
private/reference artifacts and A-owned boundaries remain preserved. No product implementation,
new Task, push, publication or Slice closure by B.
