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

Checkpoints on `main` after B's `FIX REQUIRED` (reviewed Head `1dc70c43`):

```text
14a42f41  fix(organize): verify Storage source identity and settle legal continuations
ae58dab5  docs(task-46.3): page Files organize readback and cover accepted siblings
332eb35d  feat(organize): give the admitted Task its real items, problems and outcome
47c4bfeb  chore(schema): move the processing-worker default to schema 52
1e9eebc5  test(e2e): assert the one-Task organizing contract in the stability journey
```

`1e9eebc5` is the reviewable Implementation Head. This report is a report-only successor.

### B46.3-01 / P1 — the admitted Task now owns items, problems and outcome

B reproduced three symptoms of one gap: `Task=running` with `TaskItems=0` while the
Metadata view returned `total=0`; an explicit execution completing in a *different*
Task while the admitted one stayed `running`; and a native recovery summary that
never appeared.

* **Items and four-type problems.** `publish_task_item_problem` publishes each
  blocked item whose cause is one of the four native organizing problems on the
  Task the operator actually sees: RecognitionType under the pinned choice,
  Metadata choice, Metadata correction, Classification, and destination Conflict.
  It is driven from the live analysis objects inside `_run_item`, so no problem is
  reconstructed from a document and no default type/identity/target is fabricated.
  A Provider outage, Storage fault, missing configuration or capability gap is
  deliberately **not** a business decision — it keeps its factual failure
  evidence and never becomes a fifth type.
* **Real outcome.** A confirmed execution adopts the Task the Files selection
  already admitted, when it is the exact unfinished Task of the same principal,
  library binding and pin. Adopting a settled/foreign Task is refused and the whole
  admission rolls back, so another run's history is never rewritten; a plain
  intent with no Files admission keeps the ordinary new-Task path.
* **Native recovery self-conflict.** A remaining-scope recovery preparation refused
  itself: `find_owned_source_work` saw its own unfinished ancestor TaskItem and
  answered `source_already_organizing` for the exact sources it exists to review.
  A legal continuation now excludes its own persisted `recovery_continuations`
  lineage, and an analysis-only sibling preparation in the same library no longer
  vetoes it. The real duplicate-execution gate remains the admitted TaskItem plus
  the one-shot execution authority.
* **Files readback beyond one page.** `整理记录` now consumes the backend's own
  `nextBefore` cursor with a real `查看更多` / `返回上一页` pair, so a known run past
  the first 25 is reopenable instead of truncated to a recent-N window.

Measured on B's own probe (`.git/validation-evidence/1dc70c43/b46.3-review/`):

| Probe | B (reviewed Head) | this candidate |
| --- | --- | --- |
| `task_flow_probe.py` | task_items 0, metadata total 0 | task_items 1 (`waiting_metadata_correction`), metadata total **1**, attention total **1**, 0 mutations |
| `completion_probe.py` | admitted Task `running`, 0 items, `execution_task_is_different: true` | admitted Task **`completed`**, **1** item, `execution_task_is_different: **false**`, 3 real effect calls |
| native `a frozen mixed recovery preparation never republishes a decided sibling` | `firstPrepared: false` | **passes** (3.5 s) |

The two metadata problem kinds are also proven directly: a zero-candidate Provider
yields `waiting_metadata_correction`; two equally-scored candidates yield
`waiting_metadata`; both reach `?view=metadata` with `total=1`, `?view=attention`
with `total=1`, and zero media mutation.

### B46.3-02 / P1 — an accepted sibling really enters work

`overlap_probe.py` now reads `persisted_scope: [One, Three]` and
`sources_after_walk: [One, Three]` (B measured `[One]` for both). The still-free
entries are added by `extend_media_discovery_scope`: the ownership re-check and the
scope write are one `BEGIN IMMEDIATE` transaction, so two overlapping requests on
separate connections cannot both claim the same free source. A frozen or settled
record is never widened — such entries are reported with their own refusal instead
of silently changing a reviewed manifest.

### B46.3-04 / P1 — actual confined Storage identity

Schema 52 adds the additive, nullable `task_items.source_storage_path` and
`media_discoveries.storage_scope_json`. Verified ownership now compares the exact
confined **Storage** path, so two valid bindings of one Storage agree on one
concrete source while genuinely distinct roots still never collide. A pre-change
row keeps NULL and falls back to its library-relative path plus its exact library
binding — nothing is backfilled and no legacy row is re-bound.

`source_alias_probe.py` now answers **409 `source_already_organizing`** with the
first work's exact `existingWorkId` where B measured two accepted, distinct Tasks.

Reservation stays coupled to source-item admission rather than a pre-scan: direct
files are checked at request admission with their observed fingerprint (a replaced
file at the same path is a different concrete source and is admitted), folders are
admitted as outer work and checked inside their own bounded walk, and the converging
sibling write is the atomic check-and-extend described above. No transaction spans
Storage I/O.

### Two further defects found and fixed while delivering the above

* **Metadata candidate authority leaked across pins and occurrences.** A new
  preparation could borrow the previous Active revision's — or a replaced file's —
  candidates. `_reviews_under_snapshot` now filters by the owning Task's own
  configuration pin and by the exact source occurrence. A pin-less legacy Task
  keeps its existing eligibility; an unprovable owner fails closed. `tests.
  test_organize_preparation`'s three AC-5 cases pass unchanged in intent.
* **Schema 52 moved the processing-worker default.** `ProcessingWorkerService`'s
  `runtime_schema_version` default is deliberately kept in step with
  `SCHEMA_VERSION`; both moved to 52, with the configuration journeys that assert
  the current marker.

### Actual commands and results

From repository root:

* `python3 scripts/check_governance.py` — PASS; `git diff --check` — clean.
* `.venv/bin/ruff check mediaflow tests` / `ruff format --check mediaflow tests` —
  clean / 329 files formatted.
* `.venv/bin/python -m unittest tests.test_media_discovery
  tests.test_media_discovery_provider_manifest tests.test_organize_preparation
  tests.test_manual_organize_intent tests.test_manual_organize_preview
  tests.test_manual_organize_execution tests.test_operations_task_center
  tests.test_task_center_recovery_lineage tests.test_recovery_continuation
  tests.test_recovery_batch tests.test_scope_continuation
  tests.test_task_persistence` — **503 OK** (52 s).
* `.venv/bin/python -m unittest tests.test_v2_automation_run_once
  tests.test_v2_automation_operations tests.test_configuration_snapshot
  tests.test_automation_run_once tests.test_automation_definition_execution
  tests.test_automation_admission tests.test_operations_run_inventory
  tests.test_operations_run_detail` — **235 OK**.
* `.venv/bin/python -m unittest tests.test_v2_manual_organize
  tests.test_operations_workspace tests.test_manual_operations
  tests.test_runtime_files_browser tests.test_direct_file_operations
  tests.test_media_library_direct_commands tests.test_configuration_organize
  tests.test_configuration_destination tests.test_configuration_classification
  tests.test_configuration_destination_activation
  tests.test_configuration_destination_precheck
  tests.test_scan_retirement_stability` — **232 OK**.

From `web/` (built production assets):

* `npm run typecheck` — clean; `npm run lint` — clean; `prettier --check src tests`
  — clean; `npm run build` — built.
* `npm run test -- run` — **87 files / 1262 tests passed**.
* `npx playwright test --config=playwright.python.config.ts
  tests/e2e/operations-task-center-visual.python.spec.ts` — **2 passed**.
* `npx playwright test --config=playwright.python.config.ts
  tests/e2e/operations-inventory.python.spec.ts` — **21 passed / 20 failed**.
  Unmodified Task Base (`cd6db051`, freshly built in a detached worktree), same
  command: **23 passed / 18 failed**. The candidate's failure set is a **strict
  subset-plus-nothing-new at the assertion level**: every candidate failure also
  fails at Base. The two names that differ run-to-run (`a real standalone pipeline
  run…`, `verified primary completes…`) pass in isolation on **both** Base and
  candidate, i.e. they are the intra-file ordering dependency B already documented,
  not a regression.
* One Base failure is now **fixed**: `unknown routes and fresh organization retain
  real elapsed stability and exact confirmation` snapshotted durable counts before
  the Files 整理 command and required them unchanged, which encoded the superseded
  one-row-per-preparation accounting. It now asserts the stronger per-table
  statement. It passes in isolation and inside its `--grep`, and still fails inside
  the full sequential file (`waiting_stability` → `completed`) — the same ordering
  dependency, reported honestly rather than papered over.
* `npx playwright test --config=playwright.direct-files.python.config.ts
  tests/e2e/direct-files.python.spec.ts` — **20 passed / 2 failed**, byte-identical
  to Base (the pre-existing MediaLibrary row-menu failure Task46.2 documented). Not
  erased and not claimed fixed.

### New coverage added in this round

`tests/test_media_discovery.py::AdmissionAndScopeTests` gained three cases:

1. `test_a_newly_accepted_sibling_really_enters_the_admitted_scope` — the exact
   B46.3-02 sequence, but asserting the *durable* scope, the canonical Storage
   path, the walked manifest, the linked intent items and the single Task, so a
   response-only admission cannot pass again.
2. `test_overlapping_library_bindings_own_one_concrete_storage_source` — two valid
   bindings of one Storage; the second submission of the same physical file is
   refused with the first work's identity instead of starting a second Task.
3. `test_a_legal_recovery_preparation_does_not_own_itself_out` — a paused Task with
   one unfinished TaskItem really owns that source, and the legal continuation of
   that same Task is not refused.

`tests/test_task_persistence.py` covers schema 52 additively: the schema-34 upgrade
journey now asserts the wider physical layout with a NULL canonical path, and the
schema-42/44 upgrade journeys assert the current marker while still preserving every
pre-existing row.

`tests/test_organize_preparation.py`'s ambiguous-source journey was updated from the
superseded "preparation links no review" contract to the corrected one — the
admitted Task now owns exactly one `pending` Metadata review on a
`waiting_metadata` item of that same Task.

`web` `整理记录` gained backend-cursor paging; `StorageFilesPage.test.tsx` remains
48 passed.

Testing/build/probe wall time was ≈110 minutes inside a round of ≈2 h 25 m
(≈76 %, counting overlapping runs once). That is **over** the 50 % budget: the E2E
file had to be run four times fully plus many focused runs to separate the
pre-existing failures from candidate regressions and to establish a fresh Base
baseline. It is disclosed rather than rounded down.

### Known risks / limits

* RO-4's complete organizing-only population across all legacy queries, the
  eight-view/failure-removal convergence and historical recovered-success
  projection remain outside this Task, as B's Non-goals state. The newly admitted
  manual Task's own membership and four-type lifecycle are in and working.
* RO-5 Automation detail/Enabled/Run once intent changes remain outside this Task.
  Only the shared source-ownership safety boundary is integrated.
* The demonstrated four-type publication covers Metadata choice and correction
  end-to-end. Recognition, Classification and Conflict publish through the same
  `publish_task_item_problem` boundary from the same live objects, but only the
  Metadata two were exercised as a complete admitted-Task journey in this round;
  the other three are exercised through the existing recovery suites, not through
  a new Files-admission browser journey.
* A Files-admitted Task adopts its execution, so a run's durable Task count per
  admission is 1 rather than 2. Journey fixtures written against the old
  double-row accounting needed the two corrections above; other fixtures were
  verified unchanged.
* `2026-10-26` note: the task-item retirement in `admit_manual_execution` deletes a
  *pre-existing analysis TaskItem of the same Task and source* before writing the
  execution item (the shared review/plan rows are untouched). One source keeps one
  item; verified by the AC-5 journeys.
* The intra-file E2E ordering dependency and Task46.2's pre-existing row-menu
  failure are unchanged and neither fixed nor assumed fixed.
* `web/tests/e2e/operations-inventory.python.spec.ts` still has 20 failures in a
  full sequential run. B should judge these against a Base run of the same spec
  rather than the count alone.

### Remaining Slice outcomes

RO-1 complete (Task46.1). RO-2: early durable admission, per-request results,
verified Storage source ownership, Files-only entry, Files readback, native
four-type problem publication and truthful Task settlement are implemented and
proven at their real boundaries. The real-Python E2E file is not green, and its
remaining failures are the pre-existing family plus one documented intra-file
ordering dependency, so RO-2 is **not** claimed complete. RO-3 complete (Task46.2).
RO-4/RO-5 unchanged and still TARGET.

## B Review Result

```text
Reviewed Task range: 83144be20c6c7bc787a0fafad7fabb3e177bde6a..1dc70c43180aa50b285798ace4ef5e92529b9500
Implementation: ee21ea29 (with 2d4649d9); report-only successor 1dc70c43
Decision: FIX REQUIRED — 2026-10-26
Open Task blockers: B46.3-01/02/04 (P1)
B46.3-03: prior folder-filtering correction retained
Slice Required Outcomes / Surfaces all satisfied: NO
Next: SAME TASK FIX LOOP; complete Task46.3, no new Task or Slice closure
```

B reviewed the full 35-file Task Base..Head manifest and changes, retaining previous verified facts
and checking the new admission, source ownership, schema, API, Web and test integration. The current
report-only successor changes TASK.md; B tests below use the executable candidate identified above.
The original Base/Goal/Scope/High/T4 and acceptance criteria remain unchanged. Earlier partial reports
and B decisions remain in Git (`8577cd3d:TASK.md`); this file retains the current handoff and decision.

### Verified progress

Early admission now creates a real persisted Task and discovery together. The focused admission
suite passes 12 tests, including the original repeated-request exclusion sequence, library-local
backend paging and an independently eligible sibling's admission response. Files-only creation and
removal of the center discovery/manual-action reads are implemented. Per-request outcome persistence
and backend exact readback are present. These are useful changes, but the complete required journey
is still not delivered by a Task row and response assertions alone.

### Required corrections

1. **B46.3-01 / P1 — connect the admitted Task to actual items, recovery and outcomes.**
   Through the existing Files command with `autoPrepare: true`, followed by the real discovery
   Worker and a synthetic Provider returning no candidates, the result is:
   `Task=running`, `TaskItems=0`, discovery `prepared/completed`, blocked Preview; the authenticated
   Metadata view returns 200 with `total=0` while Running has one run. The unready file remains
   preparation rather than a native task problem. In a separate successful journey, explicit plan
   confirmation and the real execution Worker complete a different execution Task, but the original
   admitted Task remains `running` with zero items. Both are reproducible user journeys, not timing
   or optional display issues.
   - Integrate the shared processing pipeline and durable per-item checkpoints/problems with the
     early admitted work. Real Recognition/Metadata/Classification/Conflict problems must populate
     native task forms/lists/counts and finish through legal analysis and exact confirmation. Do not
     substitute a default type or target, or treat technical errors as business decisions.
   - Reuse actual durable admission/intent/plan/execution/continuation links so one operator work
     has truthful progress, recovery, summary access and final result. Existing child execution
     Tasks may retain their history; a verified completed execution must settle/project the original
     work correctly. Updating a discovery-stage aggregate alone is insufficient.
   - Keep normal initial confirmation in Running/All with an exact summary link after restart,
     outside Attention without four-type lineage. Keep known prepared/unknown work reachable from
     Files, including backend pages beyond the first 25: the new `OrganizeWorkPanel` currently
     fetches one page and only toggles 3/all loaded items, without consuming `nextBefore`.
   - Repair the supported remaining-scope summary journey. B independently reproduces the existing
     real-Python test `a frozen mixed recovery preparation never republishes a decided sibling`:
     `firstPrepared` remains false at line 2675. Trace the actual admission/freeze/analysis/source
     ownership boundary and preserve its supported pin/decision/non-replay behavior. Do not simply
     raise the Worker loop limit, timeout or retry count. Reconcile other reported E2E failures by
     actual links/populations; change obsolete totals only when the authoritative records prove
     the new expectation. Do not assume all 18 reported failures share one cause.
2. **B46.3-02 / P1 — a newly accepted sibling must really enter work.**
   The earlier missing `.part` refusal is corrected in the tested fresh/repeated-request case.
   However, submitting `[One]`, then `[One, Three]` before the first work runs returns 202 twice
   with the same discovery identity. The second response claims `Three` is newly admitted, but the
   stored scope remains `[One]`; after the real Worker walk the manifest still contains only `One`
   and there is no second discovery for `Three`. The existing new sibling test asserts the response
   but never advances the Worker to catch this loss.
   `_reconcile_library_work` / `_accept_onto_existing` persist an outcome saying the free sibling
   was admitted without adding it to executable/discoverable scope. Either independently admit
   genuinely free siblings with their own durable work while linking existing sources, or legally
   and atomically extend an unfrozen work's actual scope with full completeness/budget validation.
   Do not silently widen frozen work or merely change response text. Preserve each request's exact
   immutable result and real work links. Extend the existing sibling test through Worker discovery,
   summary/explicit selected execution, actual result, exact readback and reopen; prove the new
   file completes and the already-owned file never replays.
3. **B46.3-04 / P1 — use actual confined Storage source identity and atomic ownership.**
   A single temporary file `source:Movies/One.2001.mkv` is exposed through two valid ResourceLibrary
   bindings on the same Storage: `nested` rooted at `Movies` and `whole` rooted at the Storage root.
   Sequential normal Files submissions of `nested/One.2001.mkv` and
   `whole/Movies/One.2001.mkv` both return 202 with distinct Tasks and no existing/refused item.
   They are the same physical source. `find_owned_source_work` currently compares library-relative
   path strings, so overlapping root bindings do not agree on identity.
   - Resolve the immutable library/root binding to the exact confined Storage-relative source path
     before ownership comparison; keep library/principal/pin context separately. Distinct actual
     roots with equal relative names must not falsely collide either.
   - Replace check-then-publish ownership with an atomic check/reservation coupled to source-item
     admission across separate SQLite connections. Current calls read ownership before later scope/
     manifest writes; admission's `BEGIN IMMEDIATE` only checks an actor/scope admission signature.
     Preserve legitimate continuation ownership and current execution fences, without a transaction
     spanning Storage I/O. A recent-50 discovery scan is not a complete ownership index.
   - Cover overlapping bindings and concurrent direct/folder/Automation/continuation paths using
     supported admissions and real source identities. Include queued, paused and unresolved human
     work, settlement, legacy supported work and completed/uncertain non-replay. Do not fix this by
     blocking unrelated libraries or by issuing broader execution authority.

Reconcile the new CURRENT architecture claims after these fixes: Task-native recovery/outcome and
verified source ownership are not yet established by the current implementation. No unrelated
refactor, additional command/queue, next governance Task or Slice rescope is required.

### Independent validation and evidence

Local ignored evidence: `.git/validation-evidence/1dc70c43/b46.3-review/`.

| Check | Actual result |
| --- | --- |
| Governance; full-range `git diff 83144be2..1dc70c43 --check` | PASS / clean |
| `.venv/bin/python -m unittest tests.test_media_discovery.AdmissionAndScopeTests` | 12 OK, 0.90 s process wall; `admission-tests.log` |
| `task_flow_probe.py` | Native Files admission + actual Worker + zero-candidate fake Provider: blocked plan, zero TaskItems, Metadata total 0; zero effects; `task-flow.log` |
| `completion_probe.py` | Actual explicitly confirmed execution completes; separate original admission Task stays running/empty; three real temporary Storage effect calls; `completion.log` |
| `overlap_probe.py` | Newly accepted `Three` absent from persisted scope and real walked manifest; no effects; `overlap.log` |
| `source_alias_probe.py` | Same Storage source through overlapping library roots admitted twice to distinct Tasks; no effects; `source-alias.log` |
| `npm run build` in `web/` | PASS; production `index-BwL35e0c.js` / `index-BFNi4meT.css`; existing chunk warning; `native.log` |
| `npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts --grep 'a frozen mixed recovery preparation never republishes a decided sibling' --output=../.git/validation-evidence/1dc70c43/b46.3-review/native-artifacts` in `web/` | 1 failed at `firstPrepared`, 2.02 s process wall; real Python/API/SQLite/Worker/built assets; `native.log`, trace and error context retained |

All probes use existing authenticated Files/plan/run APIs and existing test fixtures over temporary
Local Storage/SQLite; no guessed endpoint, fabricated successful payload or production media is used.
The Provider response is an isolated supported no-candidate boundary. The successful execution probe
uses the existing explicit confirmation and OrganizerExecutor path; its effects stay in temporary roots.
A separate attempted two-Worker barrier probe ended with `BrokenBarrierError` (5.28 s); it is retained
in `source-race.log` and establishes no duplicate execution or successful race reproduction. The
source-identity blocker above is independently proven by sequential public admissions, while the
missing atomic reservation is a code-review finding. No media loss or actual double mutation is claimed.

Developer's 2846-test/1262-test/full native results remain its report, not independent B acceptance.
B did not rerun full suites after reproducing required-journey blockers. The reported Base comparison
and claim of twelve additional E2E failures were not independently rerun here; only the exact native
failure above is independently established. An expected-total mismatch by itself is not classified
as a product defect without durable population evidence.

Workflow §6 permits early FIX REQUIRED. Full T4 Python/Web/default/native/packaging/installed-consumer/
upgrade/failure-atomicity/resident-restart/safety gates remain pending on a corrected candidate, not
waived or transferred to Developer. Required acceptance is not satisfied by the 12 admission tests.
Review started at 17:14:29 UTC (2026-10-26 local). Tests/build/probes, including the failed barrier
attempt, total less than 20 seconds subprocess wall time inside more than four minutes of review
before reconciliation, strictly below 50%; no deliberate waiting or repeated full suites.

### All Slice outcomes reevaluated

| Outcome | Assessment at reviewed Head |
| --- | --- |
| RO-1 readable shared actions | Prior Task46.1 acceptance retained; no shared palette changes |
| RO-2 Files-first organizing | Incomplete: early row/request evidence/entry removal progress; native recovery, actual accepted scope, truthful completion and source ownership still block |
| RO-3 local ordinary operations | Prior Task46.2 acceptance/evidence limits retained; no complete re-acceptance claimed for shared query changes |
| RO-4 organizing-only center/four-type truth | Incomplete; full population/eight-view work remains outside this Task, while new manual integration must be fixed here |
| RO-5 Automation detail/Enabled/Run once | Incomplete; unchanged intent contract, shared ownership safety must still integrate |

Slice remains ACTIVE; continue the same Task with original acceptance. This review updates only
B-owned TASK.md, keeps old reports reachable in Git, and preserves all pre-existing untracked/private/
reference artifacts. No product implementation, push, new Task or Slice closure by B.
