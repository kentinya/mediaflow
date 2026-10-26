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

## Developer Completion Report (this round — physical source ownership across stages)

Status handed off: **READY FOR B REVIEW — candidate for the whole Task; no PASS claimed.**

Implementation Head for this fix round: **`eb11c241`** (`test(organize): cover cross-binding and
folder-walk source ownership`, on top of the fix `b7513ce4`), on top of B's reviewed `6d79858a`.
`ed066b61`..this checkpoint changes TASK.md only.  B's contract correction and review at
`6d79858a:TASK.md`, the earlier reviewed ranges and their ignored evidence directories are
unchanged.

### B46.3-04 / P1 (1) — `source_fingerprint` 是库绑定的，不是物理来源

**B 的真实顺序（原样复现，未改动任何探测）：** 同一 Storage 上两个合法 ResourceLibrary 绑定
（`whole` 根为空、`nested` 根为 `Movies`）。先通过 whole 提交 `Movies/One.2001.mkv`，真实 Worker
完成分析产出 `previewed` 摘要且原 Task 仍 `running`；再通过 nested 提交 `One.2001.mkv`。
B 的 `alias_after_analysis_identity_probe.py` 在 `6d79858a` 上：

```json
{"first_status":"completed","first_preview_status":"previewed","first_task_status":"running",
 "observed_file_unchanged":true,"same_entry_fingerprints_differ_by_library":true,
 "first_storage_scope":[["Movies/One.2001.mkv","Movies/One.2001.mkv"]],
 "second_storage_scope":[["One.2001.mkv","Movies/One.2001.mkv"]],
 "second_status":202,"second_task":"…","works":2,"mutations":0}
```

同一探测在本候选上：

```json
{"first_status":"completed","first_preview_status":"previewed","first_task_status":"running",
 "observed_file_unchanged":true,"same_entry_fingerprints_differ_by_library":true,
 "second_status":409,"second_task":null,"works":1,"mutations":0,
 "second_error":{"code":"source_already_organizing",
   "details":{"existingWorkId":"…","reason":"source_already_organizing"}}}
```

**根因：** `source_fingerprint()` 的摘要刻意包含 `resourceLibraryId`（它是“是否仍是我审阅的那次
occurrence”的库绑定证据）。`_discovery_source_owners_locked` 与 `find_owned_source_work` 的
TaskItem 分支却把它当成“物理来源是否被替换”的证据：一次来源完成分析、指纹持久化之后，两个绑定
的摘要天然不同，于是被判为“来源已替换”，有效 owner 被排除，第二份未完成任务被建出来。队列初期旧
来源尚无指纹，所以此前“刚提交就从别名再提交”的用例没覆盖到该阶段。

**修复（区分事实，不统一改写历史）：**

* `mediaflow/domain/source_evidence.py` 新增 `SourceVersionEvidence`（观测 size、modifiedAt、
  存在的 provider validator 名称）与 `source_version_evidence(entry)`、
  `stored_source_version_evidence(persisted_evidence)`：**物理来源 + 可比较内容版本**，不含库、
  主体、配置 pin 或计划上下文。
* `source_version_is_known_different(observed, stored)` 是唯一的“是否真的被替换”判定：只有两侧
  都有可比较证据且不相等才算替换；**任一侧未知一律不是不同**，因此不可比的观测绝不会释放仍然
  有效的占用。
* `find_owned_source_work` 增加 `source_version` 参数。TaskItem 分支：同一绑定内持久指纹仍可直接
  比较（替换即释放，旧记录证据不完整也不被永久锁死）；跨绑定时改用该 Task 自己 admission
  记录的持久证据（`_linked_task_source_version_locked`），只有它证明替换才排除 owner。
  discovery 分支同样用 `fingerprintEvidence` 里持久化的 size/modifiedAt/validator 名称比较，
  不再比较两个不可比的摘要。
* 归属判断路径的 primary 路径统一用已 admitted/pinned root 的 canonical Storage 路径；反向
  `storage_scope` 映射只用于 TaskItem 的 legacy 回退，没有重新引入 `startswith` 根猜测。
* **没有**新增字段/表：可比较证据从记录里已有的 `fingerprintEvidence` 与 TaskItem 指纹重建，
  没有迁移、没有旧行回填、没有重绑历史 pin。

### B46.3-04 / P1 (2) — 文件夹来源的查重与接纳不是同一个原子决定

**B 的真实顺序（原样复现）：** 同一 ResourceLibrary 通过现有 Files API 分别提交文件夹 `Movies`
与 `Movies/Sub`（实际只有 `Movies/Sub/One.2001.mkv`）。两个真实 Worker 先后领取这两条实际排队
记录，两次都读到来源空闲，随后两条 discovering 各自持久 `sources` 都含该 primary。
B 的 `folder_ownership_sequential_claims_probe.py` 在 `6d79858a` 上：

```json
{"ownership_reads":[{"path":"Movies/Sub/One.2001.mkv","free":true},
                    {"path":"Movies/Sub/One.2001.mkv","free":true}],
 "durable_sources":[["Movies/Sub/One.2001.mkv"],["Movies/Sub/One.2001.mkv"]],
 "phases":["analyzing","analyzing"],"mutations":0}
```

同一探测在本候选上：

```json
{"ownership_reads":[{"path":"Movies/Sub/One.2001.mkv","free":true},
                    {"path":"Movies/Sub/One.2001.mkv","free":true}],
 "durable_sources":[[],["Movies/Sub/One.2001.mkv"]],
 "phases":["empty_excluded","analyzing"],"mutations":0}
```

**根因：** `_walk::refusal_for_owned_source` 只在应用层先读 owner 再写入内存集合；
`record_media_discovery_progress` 在自己的事务内只按本 discovery 的 claim/version 写 sources，
**没有**在同一事务里对其他未完成工作重新检查同一 concrete source。两条 discovery 的 CAS 都能
成功，各自持有合法 Worker fence 并不等于同一来源只有一个 owner。

**修复：**

* `record_media_discovery_progress` 在写入 manifest 的同一个 `BEGIN IMMEDIATE` 内调用新的
  `_reserve_discovered_sources_locked`：对本次要拥有的每个来源重新做 `find_owned_source_work`
  （排除自身 discovery、自身 organize Task 与合法 lineage）。`SQLite` 的 reserved lock 使同一数据库
  两个连接上的两个 Worker 串行化，第二个一定看到第一个已提交的 manifest。
* 命中即**整体回滚**并抛 `DiscoveryConflict(..., refused_sources=…)`；`DiscoveryConflict` 新增
  `refused_sources` 属性，只携带相对路径与可公开的 owner 引用/主体事实（**不含**指纹、claim、pin
  或物理 Storage 路径，`reserved_refusals()` 是唯一构造点）。
* 应用层 `_publish_without_reserved_sources` 把这些来源从 manifest、findings、counters 中移除，
  逐个写入真实拒绝（共用 domain 的 `owned_source_refusal`），并在同一 claim 下重发其余兄弟；
  一个来源都没留下时 phase 是 `empty_excluded`（不是伪造的 `empty` 或成功），随后照常释放 claim，
  若仍是完整的可准备清单则照常进入分析。
* 只对**明确 Files 选择**（`progress.manual_selection`）生效，与“只有它创建外层整理任务”的边界
  一致；definition Run once 与 remaining-scope recovery 的既有准入/lineage 规则不变。
* Storage `stat`/`list` 全部在事务外，事务内只比较已验证证据并保持 claim/version fence。

### 新增/扩展的永久回归

`tests/test_media_discovery.py`（`AdmissionAndScopeTests`，146 → 151）：

| 测试 | `6d79858a` 上 | 本候选 |
| --- | --- | --- |
| `test_a_cross_binding_alias_after_analysis_owns_one_physical_source` | 失败（202 + 第二 Task） | 通过 |
| `test_the_reverse_cross_binding_alias_order_also_owns_one_source` | 失败 | 通过 |
| `test_a_replaced_cross_binding_source_is_a_new_content_version` | 通过 | 通过 |
| `test_two_folder_walks_never_admit_one_source_twice` | 失败（两份都持有） | 通过 |
| `test_a_loser_republishes_its_free_siblings_after_a_reservation` | 失败 | 通过 |

第一/第三条覆盖 B 指定的真实顺序（whole → 实际分析到等待确认 → nested），并断言同一实际文件
不归两份未完成工作、准确拒绝/已有工作结论、`reopen` 后状态；第二条覆盖反向绑定；第三条覆盖
真实文件替换；第四/第五条用两个真实 `claim_and_run`/`MediaDiscoveryWorker` 入口、两个 SQLite
连接和一次刻意的 owner-read 延迟，让两次真的都读到空闲，再断言最终持久 `sources`/`TaskItem`
归属最多一个、失败竞争者的结论真实、独立兄弟保留，并覆盖 `reopen`。

`tests/test_task_persistence.py` 新增 `SourceOwnershipEvidenceTests`（21 → 24 tests，3 个新用例）：
两个绑定的摘要确实不同而可比较版本相同、TaskItem 跨绑定仍占用/同绑定替换释放/不可比不释放、
已结算项不再占用、legacy 无证据行保持占用。该模块在 `6d79858a` 上因缺少新 API 而 error（即
新 API 确为本次新增）。

### 实际命令与结果（本轮）

仓库根目录：

* `python3 scripts/check_governance.py` — PASS；`git diff --check` — clean。
* `.venv/bin/ruff check mediaflow tests scripts` — clean；
  `ruff format --check mediaflow tests scripts` — 358 files formatted。
* `.venv/bin/python -m compileall -q mediaflow tests scripts` — clean；`pip check` — 无冲突依赖。
* Required Tests 的十个套件 — **396 OK**（45.7 s；此前 391 + 5 个新回归）。
* `.venv/bin/python -m unittest tests.test_media_discovery.AdmissionAndScopeTests` — **25 OK**（原 20）。
* `.venv/bin/python -m unittest tests.test_task_persistence.SourceOwnershipEvidenceTests` — **3 OK**。
* 直接受影响的 Automation/持久化/续作十二套件（含 `tests.test_scope_continuation`、
  `tests.test_task_persistence`）— **359 OK**（27.9 s）。
* 直接受影响的 Files/普通操作/配置十二套件 — **232 OK**（11.7 s）。

`web/`（当前生产 build：`index-Cw7c73S-.js` sha256 `7e315a9c…`、`index-9CMd6NZ6.css`
sha256 `6431101f…`，均由本候选源码 `npm run build` 生成，与 `fe0aa281` 审阅时同一身份）：

* `npm run typecheck` / `npm run lint` / `npm run format:check` — clean；`npm run build` — built。
* `npm run test -- run`（九份 Required Tests spec）— **9 files / 166 tests passed**。
* `npm run test -- run`（全量）— **87 files / 1265 tests passed**。
* `npx playwright test --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts`
  — **41 passed**（1.5 m），包含 B 记录的原首错旅程与四个原生恢复类型、并列兄弟独立性、未知准入、
  C→A 身份与真实 Worker 结果/重启断言。
* `npx playwright test --config=playwright.python.config.ts
  tests/e2e/operations-task-center-visual.python.spec.ts` — **2 passed**。

B 的两个探测未改动重跑（见上面的 JSON）：`alias_after_analysis_identity_probe.py` 与
`folder_ownership_sequential_claims_probe.py`。

证据目录（本地 ignored）：`.git/validation-evidence/dev-46.3-fix5/`（`required-tests.log`、
`automation-and-persistence.log`、`files-and-configuration.log`、`native-inventory.log`、
`native-visual.log`、`asset-digests.log`、`alias-after-analysis.log`、
`folder-sequential-claims.log`、两个未更改的 B 探测脚本及 `*-artifacts/`）。

### Known risks / limits

* 本轮两项修复在真实 Files API、真实 Worker 入口、两连接 SQLite 与真实 `reopen` 上取证；文件夹
  竞争用例的两个 Worker 是**先后**进入竞争边界（第二个在第一已完成来源观察之后启动），并对
  owner-read 加了有限延迟让两者都读到空闲——这与 B 记录的真实 Worker 轮询形状一致，但不是
  同一瞬间的双线程 barrier 竞争（B 的首次 barrier 尝试本身是 inconclusive）。
* 未新增 schema，故无迁移/旧行回填/reopen 迁移旅程；沿用 schema 52。
* 跨绑定“替换”判定依赖旧记录自身持久化的 `fingerprintEvidence`；一个既无该证据、又跨绑定提供
  新观测来源的情况按“未知”保留占用（保守、避免重放），此时需要人工取消旧工作才能复用该路径。
* RO-4 的 organizing-only population/八视图/failure 移除与 RO-5 的 Automation 意图变更仍按
  Non-goals 保持 TARGET；完整 T4 门禁仍由 B 执行。

### Remaining Slice outcomes

RO-1 complete（Task46.1）。RO-2：B 指定的两项同一物理来源全阶段唯一归属已交付并在真实边界
取证；真实原生 E2E 文件在单一 spec 默认配置下 **41 passed**（与 B 的验收一致），但完整 T4 门禁仍由
B 执行，因此 RO-2 仍**不**声明完成。RO-3 complete（Task46.2，证据限制照旧保留）。RO-4/RO-5
仍 TARGET。

时间分布：本轮约 95 分钟，其中 build/测试/浏览器运行合计约 20–21 分钟（含 2 次原生 E2E、
2 次全量 Web 单测与若干聚焦重跑，重叠只计一次），远低于 50%；未故意等待、未重复全量套件、
未放宽断言或超时。

## Developer Completion Report (previous round — Files return context)

Status handed off: **READY FOR B REVIEW — candidate for the whole Task; no PASS claimed.**

Implementation Head for this fix round: **`e3393a9d`** (`fix(operations): carry the router-committed
list context into the Files link`), on top of B's reviewed `a60bab03`.  This report is a report-only
successor.  B's contract correction at `a60bab03:TASK.md`, its review at
`aaef53e9:TASK.md`, the earlier reviewed ranges and their ignored evidence directories are unchanged.

### 原 Task 的返回上下文丢失 — root cause and fix

**触发器（B 的真实入口，未改动）：** 任务中心输入 `操作类型 = manual_organize` → 点侧栏 Files →
选择文件整理 → 摘要 → 确认 → 模拟执行响应丢失 → 核对提交结果 → 落在
`/ui-v2/operations?run=…`，`command=manual_organize` 丢失。

**根因（本机复现后才修）：** `AppShell.tsx::filesJourneyReturnContext` 的 memo 依赖 Router 已提交的
`pathname/searchStr`，却从 `window.location.search` 取值。TanStack Router 在渲染目标路由时就发布新
`searchStr`，而浏览器地址栏要等该 history action flush 才更新；`filter` 提交正是这个窗口。因此
memo 用旧（空的）`window.location.search` 计算，Files href 只剩 `?returnOps=`（空上下文）。
**已用真实浏览器证实：** 在 4199 端口真实的 Python/API/SQLite/Worker 服务与当前生产 build 上，
`任务中心 → 填 操作类型 → 读侧栏 Files href` 打印 `returnOps=` 且 `window.location.search` 已变成
`?command=manual_organize`，证明是可复现的时序缺陷而不是计数下游；把该 memo 临时插桩后确认
`search` 为空对象而 `searchStr` 已含过滤值。

**修复：** memo 只使用同一个已提交来源 `searchStr`（现有路由订阅），删除 `window.location`
读取；保留 `operations-return.ts` 的全部键/值白名单与长度边界，因此"无上下文"（`returnOps`
缺失）与"默认列表的合法空上下文"（`returnOps=`）仍然区分，token/不受支持参数仍被丢弃。
未改导航体系、主流程权限、精确确认或未知结果不重发规则；未删除或放宽任何断言/超时/重试。

### 新增回归（`web/src/shared/ui/AppShell.test.tsx`）

| 测试 | 在 `a60bab03` | 在本候选 |
| --- | --- | --- |
| `carries a submitted task-center filter into the sidebar Files link` | 失败（href `?returnOps=`） | 通过 |
| `keeps a journey's existing bounded context instead of re-deriving it` | 失败（已有上下文被重算为空） | 通过 |

两条都用真实路由树 + 真实侧栏 Link：第一条先在任务中心**提交筛选**再点真实侧栏，断言 href 含
`returnOps=command%3Dmanual_organize`、跟随该链接落到 Files 且 `returnOps` 回读为同一序列化上下文、
并且没有掺入 `resourceLibraryId` 等额外权威；没有用"测试开始就预置 returnOps"的方式来掩盖该缺陷。
第二半是"已有合法上下文原样携带"（不是重新推导）。两者在 HEAD 树上被实际验证为失败，非推理。

`docs/architecture.md` 的 Task46.3 CURRENT 段补充了该单一来源事实（仍保留未实现的 TARGET 声明）。

### 第一个真实首错已消失（B 的目标）

`npx playwright test --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts`
（当前生产 build，真实 Python/API/SQLite/Worker）：

* 本候选：**41 passed / 0 failed**（整文件顺序执行，1.4 m）。B 记录的首错 spec:1239 已通过。
* 同一 tree 只把 `AppShell.tsx` 换回 `a60bab03` 并重新 build：**22 passed / 19 failed**，失败行号
  与 B 记录完全一致（`1108, 1330, 1431, 1715, 2087, 2390, 2546, 2664, 2873, 3090, 3110, 3148, 3168,
  3207, 3291, 3509, 4330, 4917, 4981`）。这不是"顺手修好一切"的声明：该文件此前 19 个失败由
  返回上下文丢失引发的连锁假设造成，本候选整文件绿色即为实测结果，未改期望计数、未加重试。
* `operations-task-center-visual.python.spec.ts`：**2 passed**（截图旅程同样从 Files 开始并确认）。

### 实际命令与结果（本轮）

仓库根：

* `python3 scripts/check_governance.py` — PASS；`git diff --check` — clean。
* `.venv/bin/ruff check web` — PASS（Python 侧本轮无改动）。
* `.venv/bin/python -m unittest tests.test_media_discovery tests.test_media_discovery_provider_manifest
  tests.test_organize_preparation` — **168 OK**；`… tests.test_manual_organize_intent
  tests.test_manual_organize_preview tests.test_manual_organize_execution tests.test_operations_task_center
  tests.test_task_center_recovery_lineage tests.test_recovery_continuation tests.test_recovery_batch`
  — **223 OK**；`.AdmissionAndScopeTests/.NativeRecognitionJourneyTests/.ZeroMutationTests` — **27 OK**。
  共享 shell 改动对 Python 边界不可达，这三组是"直接受影响"回归，未跑 B 的全量。

`web/`：

* `npm run test -- run` 九个 Required-Tests spec 加 `AppShell.test.tsx` — **10 files / 175 tests passed**。
* `npm run typecheck`、`npm run lint`、`npm run format:check` — clean；`npm run build` — built。
* `npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts
  tests/e2e/operations-task-center-visual.python.spec.ts` — 两个 spec **并行**执行时 33 passed / 10 failed：
  inventory 文件前 10 个旅程（spec 412/485/532/561/647/770/872/917/1108/1537）的
  `第 1 页起共 N 条` 计数断言在**共享同一 harness 数据库的两个 worker**下失败。同命令把
  `--workers=1` 后 **42 passed / 1 failed**，剩下的 1 个是 visual spec 的
  `check('选择 Three.2003.mkv')` 超时（该文件在 inventory 的 19 个旅程之后已被真实 Worker 处理掉）。
  这两种结果在 `a60bab03` 上**逐条一致**（并行 33/10，共同一 10 个行号；serial 23/20）。
  单独运行 `operations-task-center-visual.python.spec.ts`：**2 passed**（修复前后都通过）。
  因此并行/顺序下的这些失败是共享 harness 测试顺序问题，不是本改动引入；我没有改计数、加
  重试或放宽超时，也不声称该并行/顺序组合已经全绿——完整文件在单一 spec、默认配置下为 41 passed。
* `npm run test:e2e -- --config=playwright.direct-files.python.config.ts tests/e2e/direct-files.python.spec.ts`
  — **19 passed / 3 failed**；失败均为行菜单 `role=menuitem` 点击时 "element is not stable / detached"
  （spec 549/556/579），即 Task46.2 已记录的既有 row-menu native failure，与本轮 shell 改动无关，
  且逐条在 `a60bab03` 上复现（同样 3 条，同样报错）。单独跑这 3 条在基线上仍失败 3 条，构成
  既有失败、未被本轮修改。

证据目录（本地 ignored）：`.git/validation-evidence/dev-46.3-fix4/`（`native-full.log`、
`native-baseline.log`、`native-required*.log`、`native-serial*.log`、`native-visual*.log`、
`direct-files*.log`、`py-*.log`、`asset-digests.log` 及对应 `*-artifacts/` trace）。
生产资源身份：`web/dist/assets/index-Cw7c73S-.js`（sha256 `7e315a9c…`）、`index-9CMd6NZ6.css`
（`6431101f…`），由本候选源码 `npm run build` 生成。

### Known risks / limits

* 修复只在真实浏览器（真实 Python 服务 + 当前生产 build）与真实路由树单测两个层面取证；
  不含两 operator 的浏览器旅程（与 B 的说明一致）。
* 并行执行两个原生 spec 时因共享 harness 数据库出现顺序相关计数失败（本候选与基线条数一致）。
  这是 B 拥有的 harness/顺序/计数收敛范围；我没有修改期望值或加重试来"修好"它。
* Task46.2 的既有 row-menu native failure 仍存在（本轮未改相关行为）。
* RO-4 的 organizing-only population/八视图/failure 移除与 RO-5 的 Automation 意图变更仍按
  Non-goals 保持 TARGET；未新增 schema，故无迁移/旧行回填。

### Remaining Slice outcomes

RO-1 complete（Task46.1）。RO-2：本轮修掉了 B 指定的原 Task 返回上下文首错，`operations-inventory`
整文件在单一 spec 默认配置下 41 passed，但并行共享队列的组合仍非全绿，且完整 T4 门禁仍由 B 执行，
因此 RO-2 仍**不**声明完成。RO-3 complete（Task46.2，证据限制照旧保留）。RO-4/RO-5 仍 TARGET。

时间分布：本轮约 50 分钟，其中 build/测试/浏览器运行合计约 12–13 分钟（含失败重跑与基线对照，
重叠只计一次），远低于 50%；未故意等待、未重复全量套件、未放宽断言或超时。

## Developer Completion Report (previous round — same-library ownership)

Status handed off: **READY FOR B REVIEW — candidate for the whole Task; no PASS claimed.**

Implementation Head for this fix round: **`0ad89131`** (`fix(organize): own one source once across
same-library admissions`), on top of B's reviewed `4678a2a2`.  This report is a report-only
successor.  B's contract correction at `4678a2a2:TASK.md`, its review at `8b4f8819:TASK.md`, the
earlier reviewed ranges and their ignored evidence directories are unchanged.

### B46.3-04 / P1 — one source, one owner, in the same library too

B's own probe (`same_library_concurrent_probe.py`, unmodified) on `4678a2a2`:

```json
{"distinct_task_count":2,"canonical_scopes":[[["Movies/One.2001.mkv","Movies/One.2001.mkv"]],
 [["Movies/One.2001.mkv","Movies/One.2001.mkv"],["Movies/Three.2003.mkv","Movies/Three.2003.mkv"]]],
 "mutations":0}
```

Same probe on this candidate:

```json
{"distinct_task_count":1,
 "durable_scopes":[[["Movies/One.2001.mkv","Movies/One.2001.mkv"],["Movies/Three.2003.mkv","Movies/Three.2003.mkv"]],
                   [["Movies/One.2001.mkv","Movies/One.2001.mkv"],["Movies/Three.2003.mkv","Movies/Three.2003.mkv"]]],
 "mutations":0}
```

Root cause and fix:

* `_discovery_source_owners_locked` granted a same-library owner only once its record was
  frozen/intent-linked/completed, and `_reserve_admitted_sources_locked` skipped a same-library
  *discovery* outright — while the service layer assumed the other request would merge.  Two
  concurrent submissions could therefore each observe every source free and each commit a Task.
* The library-identity exemption is **removed**, not replaced by a wider query: ownership is decided
  only by the verified concrete-source evidence (Storage plus its ResourceLibrary-root-relative path
  and observed fingerprint, with cancelled/failed and already-executed work excluded as before).
* The service layer now converges on the winning open work *before* that boundary — the pre-commit
  `_reconcile_library_work` path, additionally reached from `_admit_remaining_sources` through the new
  `_converge_owned_sources`.  The loser's still-free siblings join the winner's committed scope via
  the existing atomic `extend_media_discovery_scope`, and the sources it already holds are reported as
  `existing`.  A frozen or settled manifest is never widened, so a genuinely competing source keeps
  its `source_already_organizing` refusal.  Storage I/O stays outside every transaction; no schema
  column, queue, catalog or global idempotency layer was added.
* `_reserve_admitted_sources_locked` now refuses **any** owner the boundary finds, so the transaction
  can no longer accept a source the durable state already proves is held.

The new `AdmissionAndScopeTests.test_two_concurrent_selections_of_one_library_own_each_source_once`
reproduces B's race over two SQLite connections in both submission orders.  It asserts: one durable
Task/scope, at most one owner per concrete source, and that `Three` is never silently dropped (it is
conclusive as either admitted-to-the-same-work or an explicit per-item reason).  On `4678a2a2` this
test fails with two works and two Tasks for one source; on this candidate it passes.

### B46.3-02 / P1 — a lost extension keeps this request's own refusals

B's `mixed_scope_race_probe.py` on `4678a2a2` reported `second_refused` holding only `Three`:
`Movies/Excluded.part`'s `source_excluded / temporary_file` was gone from both the response and its
request readback.  On this candidate:

```json
{"second_refused":[
  {"path":"Movies/Excluded.part","reason":"temporary_file","code":"source_excluded"},
  {"path":"Movies/Three.2003.mkv","reason":"admission_not_committed","code":"admission_not_committed"}],
 "replay_selection":{"existing":[{"path":"Movies/One.2001.mkv"}],
                     "refused":["Movies/Excluded.part","Movies/Three.2003.mkv"],"scopes":[]},
 "persisted_scope_after_actual_worker_wins":["Movies/One.2001.mkv"],
 "actual_work_count":1,"mutations":0}
```

`_accept_onto_existing` replaced `outcome.refused` with only the extension's `not_admitted` set.  The
complete per-request outcome is now `canonical_refusals(outcome.refused + not_admitted)`, so each exact
`(path, kind)` keeps one truthful conclusion: the refusal this request already resolved (explicit
temporary suffix / extension exclusion) *and* the extension result.  No other request's evidence is
read or rewritten.  The control run (extension commits normally) retains the same `.part` conclusion.

The new `test_a_lost_extension_keeps_this_requests_own_exclusion` drives the same real API/Worker race
and additionally reopens the SQLite repository to prove both request identities read back their own
stable outcomes after a restart.  On `4678a2a2` it fails (`.part` missing); on this candidate it passes.

### Actual commands and results (this round)

From the repository root:

* `python3 scripts/check_governance.py` — PASS; `git diff --check` — clean.
* `.venv/bin/ruff check` and `ruff format --check` on the three changed Python files — clean/formatted
  (one over-long test line fixed, then `ruff format` applied).
* `.venv/bin/python -m unittest tests.test_media_discovery
  tests.test_media_discovery_provider_manifest tests.test_organize_preparation
  tests.test_manual_organize_intent tests.test_manual_organize_preview
  tests.test_manual_organize_execution tests.test_operations_task_center
  tests.test_task_center_recovery_lineage tests.test_recovery_continuation
  tests.test_recovery_batch` — **388 OK** (44.8 s), i.e. the previously reported 386 plus the two new
  regressions.
* `.venv/bin/python -m unittest tests.test_media_discovery.AdmissionAndScopeTests` — **17 OK**
  (was 15).
* `.venv/bin/python -m unittest tests.test_v2_automation_run_once tests.test_v2_automation_operations
  tests.test_configuration_snapshot tests.test_automation_run_once
  tests.test_automation_definition_execution tests.test_automation_admission
  tests.test_operations_run_inventory tests.test_operations_run_detail tests.test_scope_continuation
  tests.test_task_persistence` — **356 OK** (27.8 s); the shared source-ownership boundary still
  preserves every existing Automation entrance.
* `.venv/bin/python -m unittest tests.test_v2_manual_organize tests.test_operations_workspace
  tests.test_manual_operations tests.test_runtime_files_browser tests.test_direct_file_operations
  tests.test_media_library_direct_commands tests.test_configuration_organize
  tests.test_configuration_destination tests.test_configuration_classification
  tests.test_configuration_destination_activation tests.test_configuration_destination_precheck
  tests.test_scan_retirement_stability` — **232 OK** (11.5 s).

B's probes re-run unmodified against this candidate: `same_library_concurrent_probe.py` (one Task,
zero mutations), `mixed_scope_race_probe.py` and `mixed_scope_control_probe.py` (complete per-item
refusals, zero mutations), a repeated-root/overlapping-binding check (409 with the winner's exact
`existingWorkId`, one work, one Task, zero mutations).

### The real-Python E2E file is still not green — unchanged, and not caused here

`npx playwright test --config=playwright.python.config.ts
 tests/e2e/operations-inventory.python.spec.ts` (built production assets): **22 passed / 19 failed** on
this candidate.  I ran the same command on the same tree with my four files stashed: **22 passed /
19 failed, the identical 19 journeys**.  The failing set is therefore unchanged by this round, and I am
not claiming it is harmless or base-only.

Reproduced failure shapes, all order-dependent and each passing in isolation:

* `new task selection reconciles a lost admission …` — the pre-journey `expectRunTotal(SEEDED_RUN_TOTAL +
  2)` assertion sees 4 instead of 6 because an earlier journey's analysis run was not published in this
  sequence; the later steps then fail on `command=manual_organize` in the URL.  It passes standalone.
* `unknown routes and fresh organization retain real elapsed stability …` — fails as `waiting_stability`
  in the full sequence and passes standalone in 11.6 s.
* The remaining four business-blocker native-recovery journeys, the batch-summary, technical-recovery,
  attachment-collision and stability journeys show the same pattern.

These journeys encode per-journey `SEEDED_RUN_TOTAL + N` counts and an "the summary came from the
analysis run" sequence that the Task46.3 one-Task accounting (correctly) shifted.  Reconciling that
shared counting sequence across the whole sequential file is the remaining work; I did not guess at
assertion values and did not weaken any assertion to make them pass.

### Known risks / limits

* The real-Python `operations-inventory` E2E file is not green (19 order-dependent failures, identical
  with and without this round's change).  This remains the largest open risk for RO-2/AC-16 and is the
  reason RO-2 is still not claimed complete.
* The two fixed blockers are proven at the real API/application, real Worker and two-connection SQLite
  boundaries, and by new permanent regressions; they are *not* proven through a browser journey.
* `docs/architecture.md`'s Task46.3 CURRENT section now states the delivered same-library ownership and
  complete-outcome facts.  No schema change was needed, so no migration or old-row backfill applies.
* RO-4's organizing-only population/eight-view/failure-removal and RO-5's Automation intent changes
  remain outside this Task, per B's Non-goals.

### Remaining Slice outcomes

RO-1 complete (Task46.1).  RO-2: same-library atomic source ownership and complete per-request
admission outcomes are now delivered and covered; the real-Python E2E file is still not green, so RO-2
is **not** claimed complete.  RO-3 complete (Task46.2).  RO-4/RO-5 unchanged and still TARGET.

## Developer Completion Report

Status handed off: **READY FOR B REVIEW — candidate for the whole Task; no PASS claimed.**

Implementation Head for this fix round: **`36882ccf`** (`fix(organize): bind Files-source
convergence to the submitting principal`), on top of B's reviewed `c4379196`.  This report is a
report-only successor.  B's contract correction at `c4379196:TASK.md`, its review at
`885214c7:TASK.md`, the earlier reviewed ranges and their ignored evidence directories are unchanged.

### B46.3-04 / P1 — 合并是主体（principal）绑定，不是库绑定

B's authoritative proof (`published_principal_convergence_probe.py`, unmodified — two enabled
`operator` principals actually published and resolved by the production loader) on `0ad89131`:

```json
{"first_status":202,"second_status":202,"same_discovery":true,
 "second_selection":{"existing":[{"path":"Movies/One.2001.mkv"}],"refused":[],"scopeCount":2,
                     "scopes":[{"path":"Movies/Three.2003.mkv"}]},
 "stored_actor":"operator","stored_scope":["Movies/One.2001.mkv","Movies/Three.2003.mkv"],
 "second_request_owner_result":{"items":[],"total":0},
 "request_binding_under_original_actor":true,"request_binding_under_submitting_actor":false,
 "mutations":0}
```

The same probe on this candidate:

```json
{"first_status":202,"second_status":202,"same_discovery":false,
 "second_selection":{"existing":[],"refused":[{"path":"Movies/One.2001.mkv",
   "code":"source_owned_by_another_operator","reason":"source_owned_by_another_operator"}],
   "scopeCount":2,"scopes":[{"path":"Movies/Three.2003.mkv"}]},
 "stored_actor":"operator","stored_scope":["Movies/One.2001.mkv"],
 "second_request_owner_result":{"items":[{"discoveryId":"…","scopes":[{"path":"Movies/Three.2003.mkv"}],
   "admissionRequestId":"22222222-2222-4222-8222-222222222222"}],"total":1},
 "request_binding_under_original_actor":false,"request_binding_under_submitting_actor":true,
 "mutations":0}
```

Root cause and fix:

* `_converge_owned_sources` received the actor but never compared it with `record.actor`, and
  `_refuse_owned_sources` granted the same-library merge exemption to *any* principal's open
  discovery.  A second operator's submission therefore extended the first operator's scope and had
  its own request identity bound under the first operator's record, so its Files readback
  (`organize-work?requestId=…`) returned `total: 0` for work it had really submitted.
* Convergence now requires **principal + library/Storage binding + immutable pin + admission kind**.
  The same-library exemption is narrowed to the *same principal*.
* A source held by another principal's unfinished work is a new bounded reason,
  `source_owned_by_another_operator` (`_REASON_OWNED_BY_ANOTHER_PRINCIPAL`), whose refusal publishes
  the fact and its own next action but **not** the holder's Task/discovery identity — that is the
  other operator's private context.  `_scope_owned_error` accepts the already-resolved refusal so a
  boundary conflict answers with the same bounded conclusion instead of a generic duplicate.
* To make that distinction possible, `find_owned_source_work` now publishes the admitting principal of
  an owning Task through the durable link that created it (a Files admission's `organize_task_id`, or
  an admitted manual execution's `actor`); a scheduled/Run-once Task honestly reports `None` and keeps
  its publishable reference.  No schema column, queue, catalog or idempotency layer was added, and
  Storage I/O stays outside every transaction.
* The still-free siblings of the second operator's selection are admitted into **its own** new durable
  work under its own request identity.  The first operator's Task, scope and request binding are
  untouched.

New permanent regressions in `tests/test_media_discovery.py`:

| Test | On `0ad89131` | On this candidate |
| --- | --- | --- |
| `test_another_operator_submission_never_merges_into_the_first_operators_work` | fails (`first["discoveryId"] == second["discoveryId"]`) | passes |
| `test_concurrent_operator_selections_still_own_each_source_once` | fails (One lands inside the other operator's work) | passes |
| `test_each_operator_reads_only_its_own_files_organizing_work` | passes (readback was already principal-scoped) | passes |

The first two were verified failing on the exact prior `HEAD` tree (`git show HEAD:` sources with the
new tests), not asserted from reasoning.  Both drive the real Files API, the real durable boundary and
(exact) two SQLite connections; the first also reopens the repository and asserts both request
identities still read back their own results.

### B's other observations in this round

* The native return-context failure B named first (`operations-inventory.python.spec.ts:1239` /
  spec line 1108) is unchanged and still not green.  It is a *count* failure in the full sequential
  file (the `expectRunTotal(SEEDED_RUN_TOTAL + 2)` assertion at spec line 1121 sees 4, not 6, because
  an earlier journey's analysis run is not published in this sequence); the later
  `command=manual_organize` URL assertion is downstream of that.  It passes in isolation.  I did not
  change assertion values or add retries.
* B46.3-02 (complete per-request refusals) and B46.3-04's same-actor unique ownership are retained:
  B's unmodified `mixed_scope_race_probe.py` still returns the `.part` temporary-file exclusion beside
  `admission_not_committed` with the frozen scope at `[One]`; `same_library_concurrent_probe.py` still
  yields one effective Task with zero mutations; `repeated_root_probe.py` still yields the canonical
  `Movies/Movies/One.2001.mkv` scope and a 409.

### Actual commands and results (this round)

From the repository root:

* `python3 scripts/check_governance.py` — PASS; `git diff --check` — clean.
* `.venv/bin/ruff check mediaflow tests scripts` — clean;
  `ruff format --check mediaflow tests scripts` — 358 files formatted.
* `.venv/bin/python -m compileall -q mediaflow tests scripts` — clean; `pip check` — no broken
  requirements.
* `.venv/bin/python -m unittest tests.test_media_discovery … tests.test_recovery_batch` (the ten
  suites named in Required Tests) — **391 OK** (45.1 s), i.e. the previously reported 388 plus the
  three new principal-boundary tests.
* `.venv/bin/python -m unittest tests.test_media_discovery.AdmissionAndScopeTests` — **20 OK**
  (was 17).
* `.venv/bin/python -m unittest tests.test_v2_automation_run_once tests.test_v2_automation_operations
  tests.test_configuration_snapshot tests.test_automation_run_once
  tests.test_automation_definition_execution tests.test_automation_admission
  tests.test_operations_run_inventory tests.test_operations_run_detail tests.test_scope_continuation
  tests.test_task_persistence` — **356 OK** (27.8 s).
* `.venv/bin/python -m unittest tests.test_v2_manual_organize tests.test_operations_workspace
  tests.test_manual_operations tests.test_runtime_files_browser tests.test_direct_file_operations
  tests.test_media_library_direct_commands tests.test_configuration_organize
  tests.test_configuration_destination tests.test_configuration_classification
  tests.test_configuration_destination_activation tests.test_configuration_destination_precheck
  tests.test_scan_retirement_stability` — **232 OK** (11.6 s).

From `web/` (built production assets):

* `npm run test -- run` on the nine Required-Tests spec files — **9 files / 166 tests passed**
  (was 165; the new Files copy test is added).
* `npm run typecheck` — clean; `npm run lint` — clean; `npm run format:check` — clean;
  `npm run build` — built.

B's probes re-run unmodified against this candidate: `principal_convergence_probe.py`,
`published_principal_convergence_probe.py` (both now show two distinct works, each request bound under
its own principal, zero mutations), `same_library_concurrent_probe.py`, `mixed_scope_race_probe.py`,
`repeated_root_probe.py`.

Durable local ignored evidence for this round: `.git/validation-evidence/dev-46.3-fix3/`
(`focused-tests.log`, `ruff.log`, `concurrent-two-principal.log`, `full-overlap.log`,
`published-principal-convergence.log` and the three probe scripts).

### The real-Python E2E file is still not green — unchanged, and not caused here

`npx playwright test --config=playwright.python.config.ts
tests/e2e/operations-inventory.python.spec.ts` (built production assets): **22 passed / 19 failed**,
and the failing 19 spec line numbers are **exactly** B's recorded set
(`1108, 1330, 1431, 1715, 2087, 2390, 2546, 2664, 2873, 3090, 3110, 3148, 3168, 3207, 3291, 3509,
4330, 4917, 4981`).  `operations-task-center-visual.python.spec.ts` — **2 passed**.

I am not claiming this failure is harmless, base-only, or fixed.  Reproduced first-failure shape on
this candidate: `expectRunTotal` at spec line 1121 waits for `第 1 页起共 6 条` and the page renders the
earlier journeys' unfixed count; the trace and `error-context.md` retain the actual route.  The
subsequent `command=manual_organize` URL assertion follows from that.  It passes standalone.  This
remains B-owned harness/order/counter reconciliation, and remains the largest open risk for RO-2.

Testing/build/probe wall time this round: ~45 s + 28 s + 12 s focused Python, ~14 s + 3 s web unit,
~10 s visual E2E, and 2 × ~170 s full native E2E (one run plus one baseline comparison), plus
~30 s builds and a handful of sub-second probes — roughly 8–9 minutes of subprocess wall time inside a
round of about 70 minutes (≈13 %, overlapping runs counted once).  No repeated full suite, deliberate
waiting or relaxed assertion/timeout.

### Known risks / limits

* The real-Python `operations-inventory` E2E file is not green (the same 19 journeys as B's report).
  RO-2 is therefore still **not** claimed complete.
* The principal-boundary fix is proven at the real API/application, real durable-boundary and
  two-connection SQLite levels plus a real repository reopen, and by a Files-page copy test; it is
  *not* proven through a two-operator browser journey (the browser harness publishes a single admin
  principal).
* The native return-context failure B names first is a counting/sequencing effect in that sequential
  file, not a product return-context defect: the journey passes standalone and the route it lands on
  carries the selected run.  I did not "fix" it by changing expected counts.
* `docs/architecture.md`'s Task46.3 CURRENT section now states the delivered principal-bound
  convergence fact.  No schema change was needed, so no migration or old-row backfill applies.
* RO-4's organizing-only population/eight-view/failure-removal and RO-5's Automation intent changes
  remain outside this Task, per B's Non-goals.

### Remaining Slice outcomes

RO-1 complete (Task46.1).  RO-2: early durable admission, per-request results, verified Storage source
identity, atomic per-source reservation, truthful admission outcomes, same-library unique ownership,
principal-bound convergence, Files-only entry/readback and truthful Task settlement are implemented
and proven at their real boundaries — but the real-Python E2E file is not green, so RO-2 is **not**
claimed complete.  RO-3 complete (Task46.2).  RO-4/RO-5 unchanged and still TARGET.

## Developer Completion Report (earlier round — rule-miss and atomic reservation)

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
Reviewed Task range: 83144be20c6c7bc787a0fafad7fabb3e177bde6a..1ae2f5c1b34ffeb0531be471fb0c090436a71e17
Executable candidate: eb11c241 (implementation b7513ce4)
Report-only successors: eb11c241..1ae2f5c1 changes TASK.md only
Decision: FIX REQUIRED — 2026-10-26
Prior cross-binding-after-analysis trigger: corrected in the verified case
Prior empty-root folder competition trigger: corrected in the verified case
Remaining B46.3-04 / P1: nonempty library-root loser path and conflict-settlement bypass
Full T4 acceptance: pending; no Task PASS or Slice closure
Next: SAME TASK FIX LOOP
```

B reassessed the entire 45-file immutable Task Base..Head change set against original Scope §3 and
RO-2/AC-16, retaining previously verified unchanged facts and inspecting this round's version evidence,
source publication transaction, conflict handling and tests. The report-only range is verified by its
exact diff. Task Base/Goal/Scope/High/T4 and the committed Slice boundaries remain unchanged. This is
not A Final Review. The prior exact review and evidence remain at `6d79858a:TASK.md`.

### Verified progress

- B's unmodified cross-binding-after-analysis probe now returns **409**, no second Task, one work;
  the original Task remains unfinished with its previewed summary and unchanged actual file.
- B's unmodified two-folder/two-connection Worker probe with an empty ResourceLibrary root now
  persists the primary in exactly one work; the competitor has no sources and phase `empty_excluded`.
- The 25 AdmissionAndScope tests and 3 SourceOwnershipEvidence tests independently pass: **28 OK**.
- Shared ownership refusal construction and the transaction's first reservation check are present;
  no Storage I/O is introduced inside that transaction and no schema/old-pin rewrite is delivered.
- Web/Shell source, tests, harness and dependencies are unchanged from `fe0aa281`. Prior B full Web
  unit/static and return-context code facts remain applicable to those matching inputs. The backend
  has changed, so prior native/Python acceptance is not treated as a fresh complete current gate.

These successes narrow the existing source-ownership blocker. Do not redo the accepted return-context,
principal isolation or original alias correction to address the remaining publication failure below.

### Required correction — B46.3-04 / P1: 非空库根下仍可把被拒绝的来源写回两份工作

**真实使用与实际表现：** 一个合法资源库的 root 为 `Movies`，操作者从它的 Files 页分别提交
`Sub` 与 `Sub/Deep` 两个文件夹，实际主文件为 Storage 中的
`Movies/Sub/Deep/One.2001.mkv`。两个现有 Worker 分别领取真实外层任务并交错来源检查，
均读到空闲。最后两条记录的 `sources` **都持久保留同一个主文件**；一份进入 `analyzing`，
另一份已写“source_already_organizing”拒绝却仍保留该文件。实际 Task 分别仍 `running` /
`pending`，不是两个已结束历史记录；该观察不把 discovery 的 `completed` 当成整理 Task 已完成。
两份外层 Task 允许先存在，违反要求的是同一个 primary 被保留到两份未结束工作。
零媒体效果；不声称实际重复执行、删除或数据损坏。

本场景只把已验证的原文件夹触发器换成**正常非空资源库根目录**，没有新增入口或权限、
篡改数据库、改 DOM/响应或制造不可能状态。源文件和两个文件夹都确实存在，配置通过生产
验证/发布，Worker 通过 `claim_and_run` 真实领取任务。根为空时两种路径恰好相同，先前回归
没有暴露下面的路径空间混用。

**已确认的两段根因：**

1. `_reserve_discovered_sources_locked` 用 Storage-relative path 判断物理来源，返回的是供操作者
   使用的 library-relative 拒绝路径；`reserved_refusals` 又主动不携带 Storage path。
   `_publish_without_reserved_sources` 却直接用 `refused_paths` 过滤 `updated.sources[*].path`。
   本例拿 `Sub/Deep/One...` 去删除 `Movies/Sub/Deep/One...`，删不掉；拒绝原因和计数已更新，
   来源却仍在清单里。findings/refusals 与 source manifest 需要各自正确的路径语义。
2. 第二次进 `_persist` 时仓储再次检测到 owner，抛出 reservation `DiscoveryConflict`。
   它随后被通用 `run_claimed → _settle_after_conflict → _merge_attempted_work` 当作普通版本/
   控制冲突保留 attempted sources，再经 `_settle_control → settle_media_discovery_control`
   写回；后者会更新 `sources_json`，却不执行同一个来源占用检查。因此前面的原子拒绝被实际
   后备写入绕过。只修首次 reservation SELECT，或只加另一个局部判重，不能完成原保证。

**本轮开发步骤（现有组件内完成）：**

1. 在拒绝后重发分支中明确区分库内相对路径和 Storage-relative 来源键。按准确 admitted/pinned
   root 或已有可靠映射找到并删除被拒绝的 source，保持 findings、primary counter、refusals
   与剩余 manifest 一致。空根与非空根必须同语义，不使用猜测前缀/重复拼接，也不把物理路径
   暴露到操作者错误详情。若内部需要两种坐标，通过现有内部值传递，公开投影仍保持边界。
2. 将来源竞争与普通 version/control 冲突区别处理：来源已被他人持有时，不能把原 attempted
   manifest 当成可恢复进度直接写回。所有会让未完成工作继续持有/分析/执行来源的持久发布
   路径，包括当前 settle/reconcile 回退，必须维持同一个占用决定，不能绕开 reservation。
3. 竞争失败项保留准确 existing-work/权限受限理由；可用兄弟仍处理，无 primary 时明确归结
   排除原因。保留独立结果、真实预算/稳定性、合法 lineage 和主体隔离；不因新增检查破坏
   已接受的 pause/cancel/lease 交接或丢弃已完成/效果未知记录。Storage I/O 留在事务外。
4. 在现有 `tests/test_media_discovery.py` 的两个连接/真实 Worker 回归中加入此非空根用例，
   同时保留空根对照。断言最终持久 primary 最多归一份未完成工作，拒绝项已从 loser 的 sources
   真正移除，findings/counters/逐项拒绝一致，独立兄弟不丢失；SQLite/API reopen 后仍成立。
   让真实 reservation 冲突经过上述 reconcile/settle 路径，不能只测首次抛错或异常字符串。
   直接相关控制/租约回归沿用已有入口；不靠修改期望值、禁用非空根或禁止正常重叠配置通过。

以上是原 Scope §3 和 AC-16 的文件夹原子来源接纳及“有效兄弟独立”要求的剩余部分，不是新
产品功能。继续同一个 Task46.3，不新增治理 Task/来源目录/队列或通用过程框架。必要架构事实
随实际实现更正，不用 CURRENT 文档声明替代行为；原 Base 和 Slice 边界不变。

### Independent checks and evidence

Local durable ignored evidence: `.git/validation-evidence/1ae2f5c1/b46.3-review/`.

| Check / command | B actual result |
| --- | --- |
| `python3 scripts/check_governance.py`; full Task Base..1ae2f5c1 `git diff --check` | PASS / clean |
| Prior unmodified `alias_after_analysis_identity_probe.py` | second409, no second Task, one unchanged physical source; `alias-after-analysis.log` |
| Prior unmodified `folder_ownership_sequential_claims_probe.py` | empty root: one manifest holds the source, competitor empty_excluded; `folder-ownership.log` |
| `nested_root_folder_probe.py` | same real Worker scenario with root Movies: both manifests retain Movies/Sub/Deep/One; zero effects; `nested-root-folder.log` |
| `nested_root_folder_diagnostic_probe.py` | ordinary read/transaction rechecks see the actual owner, yet loser persists source plus refusal through settlement; original Task running / pending; `nested-root-folder-diagnostic.log` |
| `.venv/bin/python -m unittest tests.test_media_discovery.AdmissionAndScopeTests tests.test_task_persistence.SourceOwnershipEvidenceTests` | **28 OK**, 4.452 s process wall; `focused-tests.log`; ResourceWarning retained |
| `.venv/bin/ruff check mediaflow/application/media_discovery.py mediaflow/domain/media_discovery.py mediaflow/domain/source_evidence.py mediaflow/infrastructure/sqlite_runtime.py tests/test_media_discovery.py tests/test_task_persistence.py` | PASS; `ruff.log` |

The authoritative probes enter through the existing Files API/application and real Worker claim
entry over isolated temporary Local Storage and real SQLite. A bounded delay after the normal
ownership read schedules the second real claim; no fabricated claim/success payload, direct DB
mutation, guessed route or DOM manipulation establishes a finding. The diagnostic records returned
ownership facts and durable results; it does not change the application decision. Both probes prove
conflicting admitted manifests, not actual double media mutation or data loss.

Full current Python/native/default/visual/packaging/installed-consumer/resident-restart/schema/
failure-atomicity/RBAC/pins/non-replay acceptance is pending and B-owned. The Developer's 41 native
passes on this candidate are reported evidence, not independent B acceptance. Prior B 41 inventory /
2 visual passes were at `fe0aa281`; changed backend inputs require current coverage before PASS.
Workflow §6 permits early FIX REQUIRED on the concrete remaining P1, so B did not repeat expensive
full gates here; none is waived or relabelled green. Developer runs the failing/new/directly affected
cases and changed-file checks; B completes full T4 on the corrected complete candidate.

B review started at 13:03:57 UTC on 2026-10-26. All product tests/probes consumed less than 8 seconds
subprocess wall time inside more than five minutes of code/contract/real-entry evidence review,
strictly below 50%. No deliberate waiting, repeated full suite or relaxed assertion/timeout.

### All Slice outcomes reevaluated

| Outcome | Assessment at reviewed Head |
| --- | --- |
| RO-1 readable shared actions | Task46.1 acceptance retained; no new full visual claim |
| RO-2 Files-first organizing | Incomplete: original two triggers improve, but nonempty-root source pruning and settlement still permit duplicate ownership |
| RO-3 local ordinary operations | Task46.2 acceptance/evidence limits retained, including existing row-menu native limitation |
| RO-4 organizing-only center/four-type truth | Incomplete; broader population/eight-view/failure-removal stays outside this Task; new manual-work integration still requires complete acceptance |
| RO-5 Automation detail/Enabled/Run once | Incomplete; intent semantics remain TARGET; shared source-safety promises not waived |

Slice remains ACTIVE. This checkpoint changes only B-owned TASK.md; pre-existing untracked/private/
reference files and A-owned boundaries remain preserved. No product implementation, next Task,
push/publication or Slice closure by B.
