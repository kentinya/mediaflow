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

Status handed off: **PARTIAL — B46.3-02 and B46.3-03 delivered; B46.3-01 remains
unimplemented. The Task is NOT complete, and no PASS is claimed.**

Checkpoint: `1be609121614e322df8c3abd4c2984c51a00602d` (Task Base
`83144be20c6c7bc787a0fafad7fabb3e177bde6a`, on top of reviewed `d675594f`).

### What this checkpoint changes

**B46.3-02 — independent per-item admission outcomes.** `MediaDiscoveryService.admit`
no longer refuses a whole selection because one selected item is excluded. Each submitted
path resolves to either its real kind or its own `DiscoveryRefusedEntry`; eligible
siblings are admitted as real organizing work and the refused items are persisted with
their bounded `code`/`reason`/`message`/`nextAction`. Structural, RBAC, root-confinement
and budget validation still refuse the entire request, and a selection in which *nothing*
is admissible is refused with the first item's own reason instead of admitting empty work.
A lost-response retry of the same partly-refused selection now reconciles on the union of
admitted scope and refused entries, so it converges instead of claiming a different
selection. The refusal evidence round-trips through SQLite reopen.

**B46.3-03 — no automatic business vetoes on a deliberate folder selection.** The two
manual entrances are now distinct in the single shared predicate module:
`classify_manual_file_selection` keeps its exact-file meaning and the new
`classify_manual_folder_entry` applies only the configured primary-media extension set
(video by default) inside a folder the operator selected by hand, plus the unchanged
temporary/download and extension exclusions. `ManualFolderPolicy` carries the
automatic/deliberate distinction as a value, so the bounded walk asks one question and
`Scanner`/definition-bound filtering is untouched. `_refuse_automatic_directory` /
`_refuse_automatic_file` keep the pre-amendment include/exclude/match gates for
definition-bound Run once and remaining-scope recovery, so this is a per-admission
context and not a global weakening. The mode is stored inside the durable progress
document (`manualSelection`), so no schema column, no migration and no backfill of
existing rows is required: a pre-existing record round-trips as exactly the automatic
admission it was.

Deliberately selected folder and file selections now record only the hard bounds as
refusals: the configured depth (with its `prunedAncestor`) and the explicit
temporary/extension exclusions. Default images, subtitles and NFO never become
independent primaries or fabricated Recognition problems; artwork-off does not promote
them; the existing other-same-stem attachment setting is untouched; a folder of only
non-primary files settles as `empty_excluded` rather than a failure.

Web: refused entries render beside the admitted scope in both the discovery and the
summary workspace views, and the Files page now maps the backend's real bounded reason
(temporary / `excluded_extension_rule` / `configured_depth_exceeded` / `configured_exclude`
/ `not_included`) instead of describing every `source_excluded` as a temporary-file or
extension exclusion. `docs/architecture.md` CURRENT bounded-discovery text states the
deliberate folder rule, the durable admission mode and the per-item refusal contract.

### Files and checkpoints

- `mediaflow/application/scan_filters.py`: `ManualEntryVerdict.EXCLUDED_PRIMARY_EXTENSION`,
  `classify_manual_folder_entry`, `ManualFolderPolicy`.
- `mediaflow/application/media_discovery.py`: per-item `admit` outcomes, the new
  `_directory_refusal`/`_file_refusal` and `_refuse_automatic_*` split (the old
  `_refuse_unselectable_*`/`_refuse_pruned_ancestor` helpers were removed), refusal
  propagation at the definition and recovery entrances, `folder_policy` in `_advance`,
  `_REASON_PRIMARY_EXTENSION`, request-ID reconciliation over refused siblings.
- `mediaflow/domain/media_discovery.py`: `DiscoveryRefusedEntry`, `canonical_refusals`,
  `DiscoveryProgress.refused_entries` / `.manual_selection` (document-level, additive).
- `mediaflow/interfaces/service_api.py`: `selection.refused` / `selection.refusedCount`.
- `web/src/entities/operations/discovery.ts`, `web/src/shared/api/api-client.ts`,
  `web/src/features/library/StorageFilesPage.tsx`,
  `web/src/features/operations/OrganizeCreationPage.tsx`,
  `web/src/features/operations/OrganizeDiscoveryPage.tsx`.
- Tests: `tests/test_media_discovery.py` (`ManualEntrySemanticsTests` rewritten to the
  independent-outcome contract, new `ManualFolderExpansionTests`),
  `tests/test_v2_automation_run_once.py` (unchanged automatic veto),
  `web/src/features/library/StorageFilesPage.test.tsx` (reason-specific copy).

### Actual affected commands and results

From repository root:

- `python3 scripts/check_governance.py` — PASS; `git diff --check` — clean.
- `.venv/bin/python -m unittest tests.test_media_discovery tests.test_media_discovery_provider_manifest tests.test_organize_preparation tests.test_scanner tests.test_attachments tests.test_v2_automation_run_once` — **208 tests OK**.
- `.venv/bin/python -m unittest tests.test_manual_organize_intent tests.test_manual_organize_preview tests.test_manual_organize_execution tests.test_operations_task_center tests.test_task_center_recovery_lineage tests.test_recovery_continuation tests.test_recovery_batch tests.test_automation_run_once tests.test_automation_definition_execution tests.test_automation_admission` — **298 tests OK**.
- `.venv/bin/python -m unittest tests.test_v2_manual_organize tests.test_operations_workspace tests.test_manual_operations tests.test_operations_run_inventory` — **121 tests OK**.
- `.venv/bin/python -m unittest tests.test_v2_automation_run_once tests.test_v2_automation_operations tests.test_configuration_snapshot` — **83 tests OK**.
- `.venv/bin/python -m unittest tests.test_runtime_files_browser tests.test_direct_file_operations tests.test_media_library_direct_commands tests.test_operations_run_detail` — **129 tests OK**.
- `.venv/bin/ruff check` / `ruff format --check` on all six changed Python files — clean.

From `web/`:

- `npm run test -- run` on the 10 named Files/Operations/entities/API/router suites —
  **176 tests passed**.
- `npm run typecheck` — clean; `npm run lint` — clean; `npm run build` — built;
  Prettier clean on every changed Web file.
- `npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts`
  — **41 passed** (real Python API/SQLite/Worker/built assets).
- `npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-task-center-visual.python.spec.ts`
  — **2 passed**.

Testing/build/probe wall time was ≈5.5 minutes of an ≈69-minute round (≈8%), counting
overlapping runs once. No full Python discovery, no full Web suite, no packaging/release
matrix and no direct-files release matrix was run; those stay B-owned. No assertion was
weakened and no retry was added.

### Tests that had to change, and why

Five pre-existing expectations encoded the contract B46.3-03 explicitly overrules. Each was
rewritten to assert the *new* contract plus the retained automatic behaviour, never a
weakening:

1. `test_directly_selected_file_ignores_include_and_match_rules` — a deliberate folder now
   keeps its `mkv` files despite an exclude/include rule.
2. `test_a_directly_selected_file_ignores_an_excluded_ancestor` — the deliberately selected
   folder below the excluded ancestor is now admitted.
3. `test_a_directly_selected_nested_folder_cannot_bypass_a_pruned_ancestor` →
   `test_a_directly_selected_nested_folder_below_an_excluded_ancestor_is_admitted`.
4. `test_published_exclude_and_stability_policy_reach_the_worker` — the deliberate
   `Movies/Excluded` selection is admitted; the published stability policy is still proven.
5. `test_a_trailer_of_an_unadmitted_main_file_keeps_ordinary_processing` — swapped the
   non-extension `filename` exclusion for a genuine `extension` exclusion, so the case
   still proves attachment association only against admitted primaries.
6. `test_a_partly_refused_selection_is_never_a_different_scope` (B46.3-02's named
   violation) → `test_a_partly_refused_selection_keeps_eligible_siblings` plus
   `test_a_wholly_refused_selection_creates_no_work`.

`test_a_directly_selected_file_below_a_depth_pruned_ancestor_is_refused` was kept and still
passes: depth is a hard reachability bound, not a business rule, and its `prunedAncestor`
detail is preserved through the new per-item refusal (`DiscoveryRefusedEntry.pruned_ancestor`).

### Remaining work — B46.3-01 (not implemented)

The Task's primary blocker is untouched by this checkpoint: the Files command
(`POST /api/v1/resource-libraries/{id}/files/discoveries`, `autoPrepare: true`) still admits
a *preparation*, and no durable organizing Task exists at submission. Still required:
Scopes 1/3/4/5/6 and the necessary Scope 7 integration — early durable organizing
admission before discovery/business readiness, verified atomic concrete-source ownership
across manual/Automation/continuation entrances with settlement, native four-type recovery
inside the admitted work, exact normal summary/confirmation membership in Running/All after
restart, durable Files task/preparation/unknown-request readback, and removal of the center
creation/manual-action/discovery entries and their exclusive reads. All acceptance bullets
except the direct-file/folder filtering ones remain unmet.

### Known risks / limits

- `selection.refused` is additive. The export/CLI/legacy consumers were not audited for a
  refused-entry projection; only the Web discovery/summary views and the API document
  consume it here.
- The primary-extension refusal inside a deliberate folder reuses the existing
  `unsupported_extension` reason string. That is deliberate (it is the same "not a primary
  media extension" fact an automatic walk reports), but a reader cannot tell from the
  reason alone whether the suffix came from a folder expansion or a direct selection; the
  per-item refused list is the only place a *direct* file refusal carries a distinct code.
- A deliberate folder selection no longer honours a configured `directory`/`glob` exclude
  rule. This is the intended RO-2/B46.3-03 semantics, but it is a real behaviour change for
  a library that used a directory rule as a manual veto; the automatic Scanner/definition
  path is unchanged and asserted.
- The `operations-inventory.python.spec.ts` intra-file ordering dependency reported in the
  previous handoff still exists; the whole file in order passes.
- Task46.2's known pre-existing row-menu native failure is untouched and neither fixed nor
  assumed fixed.

### Remaining Slice outcomes

RO-1 complete (Task46.1). RO-2 partially: direct-file *and* folder eligibility/filtering
plus independent per-item admission now match RO-2; early durable organizing admission,
source ownership, four-type recovery membership and the Files-only center removal are not
delivered. RO-3 complete (Task46.2). RO-4/RO-5 unchanged and still outside this checkpoint.

## B Review Result

```text
Reviewed Task range: 83144be20c6c7bc787a0fafad7fabb3e177bde6a..62df5ca402b007f364b6a53df1a85c154d278526
Implementation: 1be609121614e322df8c3abd4c2984c51a00602d
Report-only successor: 62df5ca402b007f364b6a53df1a85c154d278526
Decision: FIX REQUIRED — 2026-10-25
Open Task blockers: B46.3-01 and B46.3-02 (P1)
B46.3-03: original folder-rule veto corrected in the checked path
Slice Required Outcomes / Surfaces all satisfied: NO
Next: SAME TASK FIX LOOP; complete Task46.3, no new Task or Slice closure
```

B inspected the full fourteen-file Task Base..Head manifest/diff, retaining the previously reviewed
unchanged facts and checking the incremental application/domain/API/Web/test/architecture changes.
`1be60912..62df5ca4` changes only TASK.md; executable inputs are the implementation above.
Developer explicitly hands off PARTIAL with B46.3-01 unimplemented. No scope reduction, Task PASS
or acceptance of the whole organizing journey follows from the filtering repairs. Earlier review
and evidence remain at `bccdbc3a:TASK.md`; Task Base/Goal/Scope/High/T4 are unchanged.

### Required corrections

1. **B46.3-01 / P1 remains open — complete early durable organizing and its Web journey.**
   A normal Files request to `POST /api/v1/resource-libraries/library/files/discoveries` with
   `autoPrepare: true` still returns 202 with one preparation and zero Tasks immediately after
   submission. Implement the still-missing original Scopes 1/3/4/5/6 and necessary Scope 7:
   organizing admission before folder traversal/business readiness; atomic verified source
   ownership across queued/paused/decision/Automation/continuation work; native four-type decisions
   and recovery; exact in-task summary/selected confirmation reachable in Running/All after restart;
   durable Files task/preparation/unknown-request readback; removal of center creation/manual/
   discovery entries and their exclusive reads. Preserve analysis-only preparation, full bounds,
   real stability, pins, current permissions/effect confirmation and completed/uncertain non-replay.
   These are already Task46.3 obligations, not a later Task or optional RO-4 cleanup. Do not describe
   eligible siblings as admitted organizing Tasks while only preparation exists.
2. **B46.3-02 / P1 remains open for repeated selection — retain this request's refused items.**
   Fresh mixed admission now correctly keeps an eligible video and records its excluded sibling.
   However, the existing-open-admission path still loses that evidence:
   - Submit `[Movies/One.2001.mkv]` with request ID A and `autoPrepare: true`.
   - Before that preparation runs, submit `[Movies/One.2001.mkv, Movies/downloading.mkv.part]`
     with distinct request ID B and the same mode through the same Files API.
   - Both return 202 with the same discovery identity; B returns `selection.refused: []` instead
     of the excluded item's `temporary_file` reason. Exact repetition of B also returns 202 and
     the same empty refusal list. No media mutation occurs, but the selected item's result vanishes.
   Reconcile the complete submitted selection and refusal evidence, not only its eligible scope.
   `admit` currently calls `_reconcile_admission` with `deduplicated` admitted entries before
   storing new refusals; the durable lookup's scope signature omits those refused entries.
   Return/persist bounded per-request admission outcomes or distinguish genuinely different
   selections while preserving exact request identity and original immutable evidence. Do not
   overwrite A's history, silently reuse its different outcomes, or create duplicate effective
   source execution merely to preserve refusal text. Cover changed excluded siblings, same-request
   readback, reopen and the overlapping/concurrent path; keep structural/RBAC/root/bounds checks.
   Keep the original duplicate-plus-eligible-sibling coverage when source ownership is implemented.

**Verified progress:** the original B46.3-03 automatic-directory veto is corrected. A deliberately
selected folder under a real published `directory: Movies` exclusion now admits; its walk keeps the
video while filtering unrelated image/subtitle/NFO suffixes. Focused tests verify artwork-off,
custom primary extensions, empty non-primary folders, per-item refusal/reopen/request identity and
unchanged definition-bound automatic filtering. Web source now renders refused entries and uses
reason-specific copy. This does not establish final visual/native/full-T4 acceptance, nor complete
all manual/mixed-selection/attachment/recovery outcomes of the Task.

### Independent checks and evidence

Durable local ignored evidence: `.git/validation-evidence/62df5ca4/b46.3-review/`.

| Check | Actual result |
| --- | --- |
| Governance; `git diff 83144be2..62df5ca4 --check` | PASS / clean |
| `.venv/bin/python -m unittest tests.test_media_discovery.ManualEntrySemanticsTests tests.test_media_discovery.ManualFolderExpansionTests tests.test_v2_automation_run_once.RunOnceApiTests.test_definition_run_once_keeps_the_unchanged_automatic_folder_filtering` | 15 OK, 1.27 s process wall; `focused-python.log`; SQLite ResourceWarnings retained |
| `npm run test -- run src/features/library/StorageFilesPage.test.tsx src/entities/operations/discovery.test.ts` in `web/` | 2 files / 59 tests passed, 6.22 s process wall; `focused-web.log`; existing scrollTo warnings retained |
| `entry_probe.py` in the evidence directory | Actual Files body with `autoPrepare: true`: zero Tasks remains; fresh mixed selection has its refused item; excluded manual folder admits and retains video-only primary; `entry-probe.log` |
| `repeated_selection_probe.py` in the evidence directory | B46.3-02 missing refusal reproduced, including exact B request readback; `repeated-selection.log`; zero mutation |
| `.venv/bin/ruff check` on the six changed Python files | All checks passed |

Probes use the existing authenticated Files API fixture, real temporary Local Storage/SQLite and
production-validated/published configuration. No guessed route, invented database state, user media
or secret is used. The initial repeated-selection helper additionally assumed that B's readback
would return 409; actual status was 202, so that helper assertion failed. Its raw output is retained
in `repeated-selection-initial.log`. The corrected probe asserts the observed missing evidence;
no request conflict or execution replay is claimed. All probe attempts count in testing time.

Workflow §6 permits early FIX REQUIRED on proven blockers. Full T4 Python/Web/native/packaging/
resident-restart acceptance remains pending on a corrected complete candidate. No gate is waived,
no Developer-reported full result becomes B evidence, and no browser/visual pass is claimed here.
Developer runs failing/new/changed/affected checks; B retains full acceptance ownership.
Review started at 13:33:52 UTC. Tests/probes/static/governance used less than 15 seconds subprocess
wall time inside more than two minutes of code/contract/evidence review before reconciliation,
strictly below 50%; no deliberate waiting, repeated full suites or weakened assertions/timeouts.

### All Slice outcomes reevaluated

| Outcome | Assessment at reviewed Head |
| --- | --- |
| RO-1 readable shared actions | Prior Task46.1 acceptance retained; shared palette unchanged |
| RO-2 Files-first organizing | Incomplete: folder/filtering repairs progress, B46.3-01/02 still block |
| RO-3 local ordinary operations | Prior Task46.2 acceptance/evidence limits retained; local status implementation unchanged |
| RO-4 organizing-only center/four-type truth | Incomplete; complete population/view/recovery delivery remains outstanding |
| RO-5 Automation detail/Enabled/Run once | Incomplete; unchanged semantics apart from filtering-preservation safety work |

Slice stays ACTIVE. Continue this same Task through all original acceptance criteria. This review
changes only B-owned TASK.md; A-owned Slice/Roadmap/Progress and all pre-existing dirty/untracked/
private/reference files remain preserved. No product implementation, new Task, push or closure by B.

## Developer Completion Report

Status handed off: **READY FOR B REVIEW — candidate for the whole Task; no PASS claimed.**

Checkpoints on `main` (Task Base `83144be20c6c7bc787a0fafad7fabb3e177bde6a`):

```text
8577cd3d  prior B planning text (unchanged)
2d4649d9  feat(organize): admit durable organizing work from Files and keep per-request results
ee21ea29  fix(operations): count one admitted organizing work once
```

`ee21ea29` is the reviewable Implementation Head. It carries the E2E spec updates for the removed
center sections; no other executable input changed after `2d4649d9` except the run-population fix.

### What this checkpoint delivers

**B46.3-01 — Files-admitted organizing Task (Scopes 1/3/4/5/6 + necessary 7).**
`POST /api/v1/resource-libraries/{id}/files/discoveries` no longer admits only a preparation. The
admission transaction (`SQLiteTaskRepository.create_files_organize_work`) commits the discovery
record *and* a real `manual_organize` Task in one durable outcome: queued status, execute authority,
the immutable configuration snapshot, the admitted primary bound, the library root scope and
bounded display evidence. Folder traversal, Provider calls, target calculation and plan readiness
all still happen afterwards inside the resident Worker. `MediaDiscovery.organize_task_id` is the
durable link; `_sync_organize_task` projects the real discovery stage onto the Task and never
reopens a Task that already reached a terminal execution outcome. A completed or partial *walk*
keeps the Task running because decisions or confirmation are outstanding. Admission creates no
media effect and no execution authority.

**Source ownership (Scope 3).** `find_owned_source_work` is separate from the short-lived execution
lease. A concrete source is `(storage_id, library-relative path)` plus, when both sides know it, the
observed fingerprint — never a filename, a UI label or today's Active. A TaskItem owns its source
while its status is not in the new `SETTLED_ITEM_STATUSES`, so queued/running/paused/decision-pending
work keeps its claim and a finished history row is not a perpetual lock. Direct files are checked at
request admission; a folder is admitted as outer work before traversal and its discovered sources are
checked inside that task's own bounded walk, so there is no pre-task traversal and no database
transaction spanning Storage I/O. A refusal carries `existingWorkId`/`existingWorkKind`, and eligible
siblings stay independently admissible. A manual execution of a linked intent takes ownership over
through its own TaskItems, so confirmed work is not blocked by its own admission.

**B46.3-02 — per-request admission results.** New additive table
`media_discovery_admission_outcomes` (one row per `(actor, requestId)`) stores each converging
request's complete submitted selection, newly admitted items, already-held items and its own
refusals. It is deliberately separate from `media_discoveries`, so a Worker progress publication, a
control or a freeze never rewrites another request's answer. The projection publishes
`selection.existing`/`existingCount` beside `selection.refused`, echoes the *publishing* request's
identity in `admissionRequestId`, and `GET …/discoveries/{id}?requestId=…` reads one exact request's
result. The reported sequence now behaves as B required: A admits `[One]`; B submits
`[One, downloading.mkv.part]` and receives the same durable work with `One` as shared admitted scope
and `.part` refused as `temporary_file`; repeating B is stable; A still reads its own original result;
exactly one Task exists; zero media mutation.

**Files-only entry (Scope 6).** `OperationsLanding` no longer renders the new-organize CTA, the
independent library radio picker, the manual-action section or the discovery section, and their
exclusive queries are gone (`discoveries-query.ts` deleted). `GET
/api/v1/resource-libraries/{id}/files/organize-work` is library-scoped, principal-scoped and
cursor-paged over durable rows, with a `requestId` form for exact lost-admission reconciliation.
Files renders its own `整理记录` panel from that read and uses it for the lost-response lookup instead
of the removed center list. `operations/organize/new` without valid prepared context renders
`从资源库文件页开始整理` and navigates back to Files — no picker, no work started. Valid
`discoveryId` deep links keep working.

**Schema 51 is additive** (`SCHEMA_VERSION` 50→51): one table, three indexes, one nullable
`media_discoveries.organize_task_id` column. Fresh create, in-place upgrade and reopen are covered by
`tests.test_task_persistence` (2 upgraded/legacy rows, both passing).

**Run accounting fix.** `ee21ea29`: the unified run population joined the discovery branch for every
discovery row, so one admission appeared as **two** runs (discovery + new Task) and inflated the
center's totals. The discovery branch now covers only rows without their own organizing Task — the
definition Run once, the remaining-scope recovery preparation and pre-change records. Verified
directly: one Files admission now yields exactly one run row.

### Actual commands and results

From repository root:

* `python3 scripts/check_governance.py` — PASS; `git diff --check` — clean.
* `.venv/bin/python -m unittest discover -s tests` — **2846 tests OK, 7 skipped** (full Python suite,
  304 s wall).
* `.venv/bin/python -m unittest tests.test_media_discovery tests.test_media_discovery_provider_manifest
  tests.test_organize_preparation tests.test_manual_organize_intent tests.test_manual_organize_preview
  tests.test_manual_organize_execution tests.test_operations_task_center
  tests.test_task_center_recovery_lineage tests.test_recovery_continuation tests.test_recovery_batch`
  — **379 OK**.
* `.venv/bin/python -m unittest tests.test_v2_automation_run_once tests.test_v2_automation_operations
  tests.test_configuration_snapshot tests.test_automation_run_once
  tests.test_automation_definition_execution tests.test_automation_admission
  tests.test_operations_run_inventory tests.test_operations_run_detail tests.test_scope_continuation`
  — **335 OK**.
* `.venv/bin/python -m unittest tests.test_v2_manual_organize tests.test_operations_workspace
  tests.test_manual_operations tests.test_runtime_files_browser tests.test_direct_file_operations
  tests.test_media_library_direct_commands tests.test_configuration_organize
  tests.test_configuration_destination` — **187 OK**.
* `.venv/bin/python -m unittest tests.test_scan_retirement_stability` — 2 OK.
* `.venv/bin/ruff check mediaflow tests` / `ruff format --check mediaflow tests` — clean / formatted.

From `web/`:

* `npm run test -- run` — **87 files / 1262 tests passed**.
* `npm run typecheck` — clean; `npm run lint` — clean; `prettier --check src` — clean;
  `npm run build` — built.
* `npm run test:e2e -- --config=playwright.python.config.ts
  tests/e2e/operations-task-center-visual.python.spec.ts` — **2 passed**.
* `npm run test:e2e -- --config=playwright.python.config.ts
  tests/e2e/operations-inventory.python.spec.ts` — **23 passed / 18 failed**. Baseline comparison on
  the unmodified Task Base: **35 passed / 6 failed**. See the open failure below.

Testing/build/probe wall time was ≈57 minutes inside a round of ≈9 h 10 m (≈10 %, counting
overlapping runs once). Full Python and full Web suites were run because this Task touches the core
pipeline, schema and persistence; the E2E file was run repeatedly to separate real regressions from
baseline flakiness.

### New coverage added in this checkpoint

`tests/test_media_discovery.py` (`AdmissionAndScopeTests`) gained five cases, all passing:

1. `test_files_admission_commits_a_real_pending_organizing_task` — the Task exists before readiness,
   is `pending`/execute-authorized/pinned with no item, is linked from the record, and survives the
   walk as the *same* Task.
2. `test_a_second_request_keeps_its_own_refused_item` — the exact B46.3-02 sequence above, including
   B's repeat, B's `?requestId=` readback and A's unchanged original result.
3. `test_a_refused_sibling_does_not_block_an_independent_third_file` — a third free video is admitted
   while an owned item and an excluded one each keep their own outcome.
4. `test_files_work_readback_reopens_multiple_runs_by_request_identity` — cursor paging beyond one
   page, the exact `requestId` readback and a proved absence returning `[]`.
5. `test_a_folder_walk_does_not_admit_an_already_owned_source_again` — folder admitted as outer work,
   owned file kept out of its manifest with the existing-work reference, free sibling admitted.

`tests/test_media_discovery_provider_manifest.py`, `tests/test_organize_preparation.py` and
`tests/test_scan_retirement_stability.py` had `list_tasks() == ()` assertions that encoded the
superseded "discovery creates no Task" contract. Each was replaced by a *stronger* assertion
(`assert_no_executable_work` / `assert_waiting_work_only` / item-table check): the durable organizing
Task exists and no item, plan, Preview or execution authority does.

Three `test_media_discovery.py` cases reused one concrete source across two admissions in one journey
(`test_a_directly_selected_file_ignores_an_excluded_ancestor`,
`test_mixed_explicit_selection_preserves_trailer_association_through_preview`, the concurrent-finalize
loop). RO-2 source ownership correctly refuses that, so each now uses its own fixture source; the
behaviour each case studies (ancestor veto removal, trailer association, finalize fencing) is
unchanged and still asserted.

Web: `OperationsInventory.test.tsx` and `router.test.tsx` asserted the removed center CTA and its
library picker. They now assert the sections are absent, that the generic creation URL renders the
Files guidance and that no admission POST leaves that page. `StorageFilesPage.test.tsx` reads its
reconciliation from the new `organize-work` endpoint.

### Open failure — one real E2E regression, not yet fixed

`web/tests/e2e/operations-inventory.python.spec.ts` is **18 failed / 23 passed** on this candidate
versus **6 failed / 35 passed** on the unmodified Task Base. So this candidate introduces **12**
additional real-Python E2E failures. Confirmed on the candidate and *reproducibly* investigated for
the first two:

1. `new task selection reconciles a lost admission…` — the center shows `第 1 页起共 4 条` where the
   journey expects `… 6 条`. The count is now consistent (one admission = one run), but the journey's
   expected totals were written against the old double-row accounting, so every `expectRunTotal` in
   the organizing journeys is off by the newly-merged rows.
2. `a frozen mixed recovery preparation never republishes a decided sibling` — `firstPrepared` is
   `false`: the prepared summary the journey drives does not appear within its bounded Worker loop.

The remaining ten share the same shape (center totals, prepared-summary appearance, and the journeys
that follow them). They are *not* claimed fixed, and the counts above are the honest numbers.

**This is an unfinished Task item, not a passing gate.** The most likely single cause of the
total-mismatch family is that the E2E fixtures seed their populations and expected totals against the
old one-row-per-preparation accounting; that needs to be reconciled with the merged run identity
(B-owned full-population work is `RO-4`, but the *totals of these journey fixtures* must agree with
the new identity, which is this Task's integration duty). The prepared-summary family needs a root
cause in the frozen/analysis boundary under the new Task-linked admission before it can be called
done. I ran out of this round's budget with both under investigation and did not weaken any assertion,
add retries or relax a timeout to make them pass.

### Known risks / limits

* `organize_task_id` is nullable and additive. A pre-change record keeps its original
  preparation-only lineage and is never retroactively given a Task; the discovery branch of the run
  population keeps covering it, so its history stays visible.
* `_sync_organize_task` tolerates a failed Task update (it is an aggregate projection, not a media
  fault), so a Task row could momentarily lag its discovery stage. The discovery record remains the
  authority.
* Source ownership compares fingerprints only when both sides recorded one. A pre-change record without
  a frozen manifest falls back to path identity, which is the conservative behaviour for legacy rows.
* `selection.existing` is additive; export/CLI consumers were not audited for it.
* Task46.2's known pre-existing row-menu native failure is untouched and neither fixed nor assumed
  fixed. `operations-inventory.python.spec.ts`'s intra-file ordering dependency reported earlier also
  still exists.
* RO-4's complete organizing-only populations/eight-view set and RO-5's Automation intent changes
  remain outside this Task.

### Remaining Slice outcomes

RO-1 complete (Task46.1). RO-2: the early durable admission, per-request results, verified source
ownership, Files-only entry and Files readback are implemented, but the real-Python E2E gate above is
not yet green, so the outcome is **not** claimed complete. RO-3 complete (Task46.2). RO-4/RO-5
unchanged and still TARGET.
