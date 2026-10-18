# Task 45.4 — Scan 首次部署移除与共享发现/稳定性连续性

遵循 [Development Workflow](docs/development-workflow.md)，从属于已提交的
[Slice45 Contract](SLICE.md)。规划/审查读取 [B 经验](docs/agent-experience/task-planner-reviewer.md)，
实现读取 [Developer 经验](docs/agent-experience/developer-implementation-role.md)。

```text
Task ID: 45.4
Parent Slice: 45
Status: FIX REQUIRED
Task Base: f02443917bcd5b3ef645a32c432b191dc4f12aa3
Difficulty: High
Test Level: T4
Planner / Reviewer: B
Next Action: DEVELOPER REMOVES SCAN PRODUCTS/MODES/RETIREMENT LAYERS UNDER REVISED CONTRACT; RO-7 AFTER PASS
```

**2026-10-18 main 整合说明：** 用户授权合并 main 与 Slice45 分支，冲突采用 Slice45 内容，
双方非冲突实现保留，后续在 main 继续同 Task。此授权取代下文原先“不导入冻结分支代码”的
隔离要求，仅纳入 main 已有43.1/43.2实现，不继续43.3/其他冻结工作；43.2原B PASS保持，
不等于合并树重新PASS。Scan模式可能已由main删除部分执行路径，Developer须按合并后真实
消费者核对，不重复恢复旧代码。ID/Base/High/T4/FIX REQUIRED与当前首次部署要求均不变。

### main 合并后的范围复核与 Scan 剩余清单 — 2026-10-18

```text
Contract Checkpoint: f1e67582022b565cf1ba2ef6f427081aa94cd901
Decision: TASK45.4 CONTINUES WITH LEGAL SCOPE ADJUSTMENT
Task ID / Base / Difficulty / Test Level: UNCHANGED / UNCHANGED / High / T4
Implementation Decision: FIX REQUIRED; NO PASS OR SLICE CLOSURE
```

用户要求先记录范围并核查剩余代码，本轮不执行产品删除。A 已提交最新 Contract，治理检查
PASS 后按实际 main 复核：当前仍是 Scan 首次部署移除与必要共享连续性的同一完整单元，
沿原 ID/Base 继续。已合并 Slice43 的页面、原生编辑/发布、Run once、分析页面、指标和
引擎设置消费不再是45必须保留、恢复、兼容或逐项验收的前提。RO-5/RO-7 必要删除可直接
调整或清理其专属耦合，无需先适配旧自动化页；自动化页在45完成后另行确认设计和实现。
不主动开展无关页面重做，不自动恢复43.3；43.2原B PASS只保留历史事实。共享受支持基础流程
实际需要的来源/稳定性/规划、Task/Worker、授权、pin/结果/审计和非重放仍须验证。

以下是 `c4aa9b9e217cbcc210b108429f2910631ca96c3b` executable（上述 Contract checkpoint
仅改文档）的实际残留，不是新增 Task 或已完成声明：

| 剩余类别 | 实际位置与现状 | 本 Task 后续处理 |
|---|---|---|
| Web 退役入口/契约 | `web/src/features/operations/ScanRetiredPage.tsx`；`router.tsx`、`destination-model.ts` 仍注册旧 new/detail；`manual-actions.ts` 仍要求 `actions.scan`/Scan modes | 删除页、路由、destination及专用动作字段；旧地址走普通认证/not-found，不留墓碑或跳转 |
| API/专用错误 | `service_api.py` 仍识别 scans/manual-scan/manual-scans/operations/scans，通用 jobs POST 仍单独识别 scan；`application/manual_scan.py` 仅剩 `ManualScanError` | 删除 aliases/识别/410及错误模型；共享支持类型在发现/准入前普通拒绝 |
| CLI 注册与帮助 | `final_cli.py` 仍注册顶层 scan、jobs submit 的 scan choice，包含多处专用报错、恢复与 queued dispatch 分支 | 删除注册/帮助/choices及专用分支；scan/flags/--help/jobs submit scan 均由 argparse 普通错误退出2 |
| 产品类型、配置与调度 | `domain/automation.py` 仍有 `AutomationCommand.SCAN`、ScheduleDefinition 的 scan 支持；`infrastructure/runtime_configuration.py` 接受 scan schedule；`domain/scope_continuation.py` 的支持集合仍含 scan | 收敛为真实支持类型；删除 Scan 配置/调度及专用继续类型，不靠 Scheduler 静默跳过代替删除 |
| Worker/重试/继续退役层 | `automation.py`、`automation_definition_execution.py`、`task_runtime.py`、`task_retry.py`、`recovery_admission.py`、`scope_continuation.py` 及 CLI 仍有 standalone_scan_retired、来源特判或 `require_supported_scan_origin` | 删除专用认识层及无消费者 helper；保留共享来源关联、pin/权限、claim/fence和通用非法类型拒绝 |
| 定义模式历史兼容 | 合并后新定义已只允许 automatic-organization，但 `RECORDED_SCAN_*`/`decode_recorded`、旧值别名及 SQLite 读回仍存在；Web automation entity、Lifecycle/Editor 仍显示旧模式与显式纠正 | 删除旧模式存储解码/别名/展示/纠正及专用拒绝；不为旧43页面兼容，不把未知/省略模式变成执行授权 |
| Readiness/投影与旧证明 | `service_api.py` 的 readiness/action matrix、`operations_lifecycle.py` 类型说明等仍认识 Scan；`test_scan_retirement.py` 和 `scripts/docker_scan_retirement_browser_proof.py` 仍断言410/退役页，其他 fixture仍用SCAN | 删除专用投影/提示，改不存在语义测试；通用安全/包装证明用支持工作，保留其原RBAC/secret/持久化/非重放断言 |

隔离复现：CLI `--help` 仍列出 Scan，`scan` 返回2及 `standalone_scan_retired`；临时 SQLite
上的 POST `/api/v1/scans`、`/api/v1/manual-scan`、`/api/v1/jobs`（command=scan）均返回
410/该专用错误，Task/Job数量均0，runtime绑定未加载。证明当前是“退役拒绝”，尚未满足
普通不存在；不复用旧测试通过来声明新要求完成。本轮未跑完整T4或浏览器验收。

主要独立执行服务、独立domain/manual_scan及SQLite专用CRUD/新表已删除，保留这些有效删除。
StorageScanner/ResourceLibraryScanner、scan_filters、整理内有界发现与真实稳定观察继续保留。
FileIndex完整仓储/schema/同步及CLI实时列表统一仍属RO-7后续完整单元，不塞入45.4或提前关闭Slice。

## Goal

当前服务按首次部署验收：Scan 产品及兼容层视为从未存在。移除独立 Web/API/CLI 入口、
注册/帮助/aliases、专用工作类型/投影/模型/服务/仓储/schema、执行/重试/继续/调度，以及
scan-only/scan-and-plan 定义模式、别名、默认值和专用分支；无退役页/410/指引/专用拒绝防线。
旧地址/命令/类型只走普通 not-found、argparse 参数错误或共享支持集合校验，均不开始发现、
准入或生成许可，不转换成整理。无旧 Scan/V1 parity、迁移/转换/接管或专用历史兼容义务。

操作者仍直接在整理内完成有界发现、真实稳定观察、同页摘要及明确确认。保留其他支持功能
实际需要的 Scanner/Storage、过滤/稳定性/零变更计划、diagnostic Preview/DryRun/Rules 测试和
受支持的 scheduled Preview；不按名称盲删。其他工作所需结果/pin/权限/审计/重启恢复不回归；
首次部署不等于清空现存数据库/媒体/用户文件或 Git 历史，也不是无关 V1 整体下线。

完成 **RO-5 / S-7**，以及该退役所必需的 **RO-4 / S-5 其他受支持工作的历史/控制连续性**、
**RO-6 / S-6 共享 API/Worker/Persistence 集成**。不改变 RO-1/2/3 已验收旅程或附件修订。
定义绑定 Scan 模式删除由已提交 A 修订授权；已合并 Slice43 的页面/Run once/指标/全局设置
实现不构成保留或验收前提。可清理必要耦合，自动化页重新设计留到45完成后；不把删默认值
解释为隐式自动整理许可，不主动开展无关43开发。
适用要求：V2-OPS-009–012、V2-UX-001–003、V2-AUTH-001–003、V2-SAFE-001、
V2-MIG-001–003、REQ-SCAN-002–006、REQ-TASK-*、REQ-RECOVERY-*、REQ-SAFE-*、UX-001–010。
REQ-SCAN-001 的独立入口按已授权 V2 修订退役，内部发现与稳定性义务不降低。
FileIndex 完全退出及 CLI/两种库页实时列表统一现属同一 Slice 的 RO-7，留给本 Task PASS
后的一个连贯 Task；本 Task 不承担 RO-7 验收，不得在 Scan 退役后将 Slice 记为完成。

## Previous Task Review / Why This Task Exists

以下旧规划复核和原始报告保留各自当时事实；其中薄退役拒绝、旧链接指引、定义模式冻结例外及
旧 Scan/V1 兼容要求均已由最新 Contract 与下方“首次部署”B 复核取代。当前执行以新版 Goal、
Implementation Scope、Acceptance Criteria 和 Required Tests 为准，不要求让过期断言通过。

### Task45.3 B Review 10 — PASS，2026-10-18

- Reviewed Range：`8f5cf4e284766bcc8894817d7640231e85050fb2..f02443917bcd5b3ef645a32c432b191dc4f12aa3`。
  Executable Head：`1bd67c7e5cbf37a4523af89bf73089beedadf61f`；其后仅 TASK.md 报告变化。
- A 的附件修订/策略动作澄清已提交，Task45.3 继续合法，Review7–9 阻塞已解决。
  主文件先执行并验证，附件分别保留失败/未执行/冲突原因、来源/目标、步骤、确定性和固定策略动作。
  主文件完成伴附件警告显示部分成功；未知效果只核查，不新增附件-only 执行或主文件重放。
- B 独立相关 Python **275 tests / 25.770s / OK**；production build PASS；完整真实
  Python/API/SQLite/Worker 浏览器 **37 passed / 1.2m**（workers1/retries0/trace on）。
  五类输入、新阻塞转类、再次失败/成功、少选子集、未知响应、暂停重新授权、重开和 C 身份均覆盖。
- B 另用 fresh fixture 经真实 API/Worker 复现主文件 MOVE 完成、字幕冲突，核对持久结果及重开，
  原项未提供主文件 retry；实际 Task Base schema45→47、合法旧 pin/许可保留及两处 ALTER 故障回滚 PASS。
  实看独立桌面/窄屏新阻塞、摘要和附件告警；主目标和附件目标可换行，操作可达。
- 核对实际 raw logs、匹配源码/依赖/产物后复用最终 T4：Python **2517 / 7 skipped / OK**，
  Vitest **1133**、fake E2E **246**、real Unicode **1**、visual **2**、质量/安全、wheel/安装 consumer、
  Docker 恢复和 release-security。7 skips 是未提供的隔离 endurance/真实外部 Storage 环境，非 PASS。
  独立从实际镜像核对 **163 Python / 4 Web** 文件，wheel163文件与候选逐字节一致。
- B 原始日志、可重跑 probe、截图、迁移、SHA/产物核对及复用限制：
  `.git/validation-evidence/1bd67c7e5cbf37a4523af89bf73089beedadf61f/b-review10-20261018/INDEX.md`。
  Developer 原报告及此前审查保留于本 Task Base 的 TASK.md；没有独立 review commit 或 push。

### 每次 PASS 后的 Slice 全部结果复核

| Required Outcome / Surface | 当前事实 |
|---|---|
| RO-1 / S-1 | Task45.1 PASS：九标签、完整授权总体查询/计数和任务/类型文件定位 |
| RO-2 / S-2 | Task45.2 PASS：创建/Files 同页准备、摘要、精确子集确认和真实 Worker |
| RO-3 / S-3、S-4 | Task45.3 PASS：五类原生输入、安全分析、新阻塞、同页摘要确认、批次独立结果和附件按策略指引 |
| RO-4 / S-5 | 其他受支持工作的详情/记录/导出/协作控制及恢复连续性保留；按 A 修订取消旧独立 Scan 历史/停止兼容 |
| RO-5 / S-7 | **未完成**：仍有独立 Scan Web/API/CLI/Job/恢复分支与“先 Scan”依赖，本 Task 完成 |
| RO-6 / S-6 | 已有统一权威及 Task 证据；仍需退役集成和之后 B 的 Slice-final 验证 |
| RO-7 / S-8、S-9 | **未完成**：后续 A 修订加入同 Slice；FileIndex 仍有完整运行依赖，CLI 仍读索引。45.4 PASS 后规划一个完整退出与列表统一 Task |

**All Required Outcomes satisfied: NO → NEXT TASK。** 不提交 Closure Packet，不宣布 Slice 关闭。
本表已反映随后 A 新增的 RO-7，不将其倒记为 Task45.3 当时已交付的结果。
规划前 `python3 scripts/check_governance.py` PASS；HEAD:SLICE.md 与工作树一致，Slice45/Roadmap ACTIVE。
Task Base 固定为上述规划前 HEAD，不随规划、实现或修正提交移动。

### A 修订后的 B 范围复核 — 2026-10-18

```text
Contract Checkpoint: 90cc8897e6f8e43eb9c215c5bf4a48b7b8f88a71
Decision: TASK45.4 CONTINUES WITH LEGAL SCOPE ADJUSTMENT
Task ID / Base: UNCHANGED
Difficulty / Test Level: High / T4 — UNCHANGED
Implementation Review: NOT PERFORMED; NO PASS CLAIM
```

用户明确授权 A 按未上线现状取消旧 Scan 的生产升级/在途停止与专用历史兼容义务；A 已同步
提交 Slice、稳定 V2 修订、TARGET 设计/旅程与当前范围指针。B 在该已提交 Contract 上复核：
当前 Goal 仍是同一个独立 Scan 退役业务单元，**同 Task 合法调整后继续，不重新规划或移动 Base**。
本文旧 AC-2/AC-3、开发步骤5及 Required Tests 中的旧 Scan 停止/迁移/历史兼容矩阵被下方
新范围取代；不是将对应能力记为已实现，也不是豁免仍适用的安全与 T4 门禁。

Developer 已有未提交的代码和新测试，不能 reset/restore/clean 掉。实际读取的部分改动：

| 已有改动 | 同 Task 后续指导 |
|---|---|
| `automation.py` 未绑定 Definition 的 Scan submit 拒绝 | 保留并继续验证；其他提交方式和 Worker 后门仍需逐项检查 |
| `final_cli.py` 的 Scan 提前拒绝、原直接执行/部分继续分支删除 | 保留有效删除/拒绝；退役指引改为实际新建整理，不承诺专用 Scan 历史入口 |
| `service_api.py` 部分 Scan POST/alias 在绑定 runtime 前返回410 | 保留 RBAC/零新工作拒绝；删除仅为 Scan 历史兼容增加的装配/路由/投影 |
| 新 `ManualScanHistoryService` 和 `SQLiteTaskRepository.retire_manual_scan` | 仅服务已取消的旧 Scan 历史/停止目标，应清理它们及专用调用；不另写替代停用/迁移框架 |
| `tests/test_scan_retirement.py` 的 submit/alias/CLI 拒绝反例 | 保留必需退役/RBAC/零工作断言，随最终实现扩展；尚未作为本轮通过证据 |

普通 Task/Result/pin/权限/审计、当前有效工作重连/重启、未知效果非重放继续受保护；不执行
数据库清空或媒体删除。FileIndex 完全退出不属于本 Task，后续同 Slice 的 RO-7 承担。
无其他消费者的 Scan 专用模型/读写/取消代码可删除；仍由共享 Scanner 或冻结定义绑定流程
消费的部分必须保留。
A 的8个文档修改在完整 Task Base..Head 中按上述 SHA 单独归属，Developer 不得将其当自己的
实现或再改范围；冻结文档对照此 A checkpoint，Task/code 仍对照原 Task Base。

### FileIndex 纳入 Slice 后的 B 范围复核 — 2026-10-18

```text
Contract Checkpoint: 0237b7d366bd24e9182797a72cb4939b528602ba
Decision: TASK45.4 CONTINUES; RO-7 REQUIRES ONE NEXT COHERENT TASK AFTER PASS
Task ID / Base / Goal: UNCHANGED
Difficulty / Test Level: High / T4 — UNCHANGED
Implementation Review: NOT PERFORMED; NO PASS CLAIM
```

B 在 A 提交后运行 `python3 scripts/check_governance.py`，结果 PASS；已提交 Slice45/Roadmap
为 ACTIVE，Contract 与工作树一致，原 Slice/Task Base 保持。核对当前未提交代码、现有测试
及三个列表入口：CLI 使用 FileCatalog/SQLiteFileIndex；两种库页已共用 RuntimeFilesBrowserService；
Scanner、整理/恢复、Result 同步和 Automation 基础仍有索引消费者。此前未提交实现均保留。

当前 Scan 退役目标和已开发部分仍合法，继续同 Task；不把新增 RO-7 塞入已在开发的范围，
也不创建第二个活动 Task。45.4 PASS 后 B 必须重新核对全部 Outcome，再按
[退役设计](docs/file-index-retirement-spec.md) 规划一个完整 FileIndex 退出与 CLI 统一 Task，
覆盖所有运行消费者/新库/生产装配及真实无索引整理恢复，不能仅改 list 或按模块拆碎。

给当前 Developer 的边界：

1. 继续下方 Scan 入口/执行路径删除、内部真实稳定性和 T4，不实施 FileIndex 仓储/schema/
   统计/reprocess 的整套退出，也不提前改变 `files list` 接口。
2. 为移除“先 Scan”前置复用现有 live Storage 和工作内观察；不要新增索引补偿、兼容服务、
   no-op 仓储或双写。现有仍被消费的索引暂由后续 RO-7 单元统一移除，不是最终交付例外。
3. 不建设旧 Scan/FileIndex 生产迁移、历史兼容或接管框架，不清空数据库/媒体；现有普通
   Task/Result/pin/权限/未知效果非重放与共享稳定性不回归。
4. A 本次10个文档的变更归属上述 Contract checkpoint；连同先前 A 修订从实际 Base..Head
   中单列，不当作 Developer 实现。冻结文档以本 checkpoint 对照，代码仍对照原 Task Base。
5. 完成报告明确列 RO-7 尚待后续 Task。B 不能因本 Task PASS 提交 Closure Packet 或宣布关闭。

### 首次部署修订后的 B 范围复核 — 2026-10-18

```text
Contract Checkpoint: 0b59846a2f85d2148b8f6de8d8eaa759e1be42cc
Decision: TASK45.4 CONTINUES WITH LEGAL SCOPE ADJUSTMENT
Task ID / Base: UNCHANGED
Difficulty / Test Level: High / T4 — UNCHANGED
Implementation Decision: FIX REQUIRED; NO PASS OR SLICE CLOSURE
```

A 已先 checkpoint 材料性范围修订；B 在已提交 ACTIVE Contract/Roadmap 上运行治理检查 PASS，
再核对当前实际代码。仍是同一 Scan 产品移除与必要共享发现连续性的完整单元，保留有效删除及
工作内真实稳定观察；合法调整同 Task，而不是重开 Task、移动 Base 或免除 T4。

新范围覆盖 standalone 与定义绑定 Scan。已读到的 `ScanRetiredPage`/旧 router、API Scan aliases
与410、CLI 注册/choices/专用报错、application/Worker/retry/continuation Scan guard，
`AutomationTaskRunMode` 两种模式/aliases/默认值、定义执行分支与 Web selector 均不满足新要求。
旧“独立 Scan 不接受但真实 Definition Scan 保留”的来源区分不再是产品例外；删除专用防线，
仍受支持的自动整理/Preview 通过共享校验和既有真实关联/pin/权限保证安全。

此范围重核不是新 executable 候选的完成审查。cb5ebd8/ef1f1f3 及其原 T4/135项聚焦结果只证明
旧候选事实，不满足新增不存在语义。Developer 必须交新候选及匹配 T4；RO-7 仍在本 Task PASS
后规划一个完整 FileIndex 单元，不并行创建第二活动 Task、不提前交 Slice Closure Packet。

A 的10个范围文档修改单列归属上述 checkpoint，Developer 不再改范围。此前 B Review/CLI
修正要求和本轮开始的脏 TASK 副本保存在 Git/耐久证据中；不改写为已完成的新验收。

### 实际代码与复用边界

- Task Base 已有 `ManualScanService`/独立线程、Scan aliases、CLI、Job、Task 继续与 UI 准入。
  当前旧候选已删除主要执行服务、domain/manual_scan 与 SQLite manual scan CRUD/新建表；
  保留这些有效删除，不为本次 rescope 重建旧功能。
- 当前仍有 `ScanRetiredPage`、router/destination、API `standalone_scan_retired`/410，
  `final_cli.py` 的 scan 注册、submit choices 及专用分支；readiness/action matrix 仍有 Scan 项。
  均需删除，不是改文案或把 available 置 false。
- `automation.py`、`task_runtime.py`、`task_retry.py`、`recovery_admission.py`、
  `scope_continuation.py` 的专用 Scan 拒绝与 `require_supported_scan_origin` 保留了退役认识层。
  删除专用层和无消费者 helper，以共享受支持类型/动作集合及正常失败行为封住不支持工作。
- `domain/automation.py` 仍有两种 Scan 模式、scan/preview 等 mode aliases、SCAN_ONLY 默认值；
  `automation_definition_execution.py`、Scheduler/发布/配置和 Web selector/typed model 仍消费它们。
  这些模式专用路径纳入本 Task 删除；相同单词用于独立 diagnostic Preview 时不是同一功能。
- `MediaDiscoveryService/Worker`、`scan_filters`、`StorageScanner/ResourceLibraryScanner` 以及
  已有工作内 observation/waiting_stability/claim/lease/精确 pin 为真实共享能力。优先复用已完成的
  Definition Preview 工作内稳定观察；不可用旧 mtime 或空索引代替真实跨间隔观察。
- `manual_organize_preview.py` 的索引来源前置和结果 reconciliation 的 rescan 指引需按实际
  支持流程修正；完整 FileIndex 仓储/schema/同步及列表接口退出仍由后续 RO-7 统一完成。

## User Journey

| 环节 | 本 Task 验收结果 |
|---|---|
| 目标 | 不存在 Scan 产品；直接整理安全稳定的所选媒体，其他支持功能保持完整 |
| 入口 | 任务中心/Files 新建整理；支持的自动整理与诊断入口不变；旧 Scan 路由/命令不存在 |
| 可见状态 | 原整理的发现/真实稳定等待/未就绪原因和摘要；旧输入只有正常认证下的普通404/参数/不支持错误，无退役页或指引 |
| 动作 | 在原工作内等待/重新检查，查看同页新摘要后明确确认；不先 Scan、不转换旧命令、不隐式取得执行权 |
| 成功 | 无预扫描即能完成真实观察与精确摘要；确认前零 mutation/零许可，确认后只执行所选范围 |
| 失败 | 写入中、边界不足、缺 pin、权限不足等按当前支持工作解释；不支持输入不产生发现/工作/许可 |
| 恢复 | 保留当前工作 pin/范围/观察/逐项结果，同版本重启/重开/合法继续；不自动 repin 或重放完成/未知效果 |

## Implementation Scope / 逐步开发指导

同一 Task 内按下列连贯阶段修正，不拆成删按钮/删命令/补测试等单点 Task。先建立受影响反例，
修正已知问题后冻结新 executable 候选做完整 T4。不继续导入冻结43工作或修改 A-owned 范围；
按最新 Contract 清理必要43耦合，无需恢复/适配其旧页面实现。

### 1. 核对真实消费者并建立不存在语义反例

- 列 Web(V1/V2)/API aliases/CLI/配置发布/Job/调度/Worker/retry/resume/continuation/投影的
  Scan 专用清单；区分共享发现/过滤/稳定性/计划与产品模式，不按名称全局删除或替换。
- 在现有临时 Local/SQLite/fake Provider fixture 记录配置/runtime、list/stat/read、准入、
  观察、执行权和 mutation 调用。覆盖普通不支持类型，不为旧 Scan 建状态迁移/接管/历史矩阵。
- 复用 `tests/test_scan_retirement.py` 等现有测试位置，但把专用退役断言改成正常不存在/
  不支持错误和零新工作断言。保留 RBAC/来源/权限/非重放含义，后续用受支持 fixture 证明。

### 2. 删除全部产品入口与退役兼容层

- 删除 `ScanRetiredPage` 及旧 new/detail router/destination、导航、按钮、typed API/query/model，
  V1 `operator_ui.py` 和 action matrix/readiness 里也不保留“不可用 Scan”专用项。旧深链自然
  走现有 not-found 和普通认证语义；不加墓碑页、redirect、410、提示新建整理或自动 POST。
- 删除 Scan API/aliases 的注册/识别、专用错误/handler/service 装配；通用 API 共享支持集合
  在 runtime/发现/准入前校验不支持类型，正常未知路由不构造发现/Provider/业务执行器。
  不用 `if command == scan` 改报错文案伪装删除；不降低公共认证/RBAC或暴露原始异常。
- 删除顶层 `scan` 注册/帮助/参数及专用提前退役分支；`jobs submit` choices 只剩受支持
  `preview`。`scan`、旧 flags、`scan --help`、`jobs submit scan` 都由 argparse 普通错误
  退出2，在 `_configuration`/数据库/runtime/Storage/Provider 前停止。无隐藏 alias、argv
  预检、自定义 Action/特殊拒绝、捕获通用异常或给 bootstrap 补字段绕过。

### 3. 删除定义绑定 Scan 模式及专用执行/防线

- 删除 scan-only/scan-and-plan enum 值、scan/preview 等该 mode 的 aliases、默认值、
  selector/help、配置/DTO解码/序列化以及专用发布/准入/Scheduler/dispatch/继续路径。
  移除 AutomationCommand.SCAN、专用任务类型等无真实共享消费者的产品值；共有分析阶段可保留。
- 只允许实际支持意图的普通类型校验；未知配置/模式/工作先拒绝再发现/准入。删除
  `require_supported_scan_origin` 等“真 Definition Scan 可继续、其他 Scan 已退役”的专用
  helper/guards。共享真实来源关联、pin/权限、claim/fence、原子准入和通用不支持错误仍保留。
- 自动整理继续依赖正常 Preview/精确 scope、单独授予的权限、当前 grant/capability/conflict
  验证；删除 Scan 默认不自动取得许可，不把旧模式/未知数据重解释成 organize。唯一模式表单
  不必增加多余确认，但后端支持集合和授权必须明确。
- 保留实际支持的 scheduled/diagnostic Preview、DryRun/Rules 测试及其他消费者所需的零变更
  Planner/discovery；mode alias `preview` 删除不等于删除独立 Preview 工作。两者均须回归。
- 更新受影响 example config、harness、typed fixtures、帮助与当前命令参考；不读改私有 config
  或运行库，不实现 Slice43 Run once/新指标/全局设置消费，也不宣称交付其完整工作区。

### 4. 保留有效删除并清理真正专用数据/无消费者代码

- 当前已删的 ManualScanService/domain/manual_scan/SQLite CRUD 和 fresh Scan 专用 CREATE
  不恢复；残留 ManualScanError、Scan 专用 models/schema/仓储/历史/导出/取消及专用兼容测试
  在无支持消费者时删除，不保留 no-op、新历史服务、startup drain 或“防御用”退役认识层。
- 第一次部署不创建 Scan 专用表/数据/默认配置；无需旧版本/Task Base Scan 库或 V1 parity。
  不执行清库、DROP现存用户库、删除媒体或 Git 历史；同版本支持工作 reopen/restart、事务失败
  原子性和逐项持久结果仍验证。共享 schema 改动只限本 Task 真正必要部分并说明实际 diff。
- 通用历史/包装/安全 fixture 改用受支持工作，不再借旧 SCAN 播种/驱动 Worker。保留其原来
  的 secret/RBAC/未知效果/精确来源/持久化断言；不能删测试含义、skip/retry 造绿。

### 5. 让共享整理/恢复独立完成真实稳定观察

- 保留现有工作内 observation 与同 definition/config pin 的可复用证据；工作内发现零变更。
  stable-size 第一次 stat 不等于稳定，须真实配置间隔内未变观察；大小/mtime/有效指纹变化
  重置区间。minimum age、modified threshold、临时/包含/排除、depth/item/entry/time bounds 不降级。
- 新建/Files 单项、多项、目录和恢复共用当前准备链；必要观察由原工作内完成，不要求 Scan
  Task/READY 记录，不把 FileIndex/旧mtime当新证明。无关兄弟项互不污染，未稳定/不完整项无许可。
- 原生状态解释实际等待、重新检查/安全继续；长等待走既有持久 Worker，不在 HTTP/浏览器
  循环/长写事务内等待。原 pin A 不随 Active B 改绑；重开/接替只用合法证据，旧 owner 不发布。
- 修复可达的“先 Scan”前置/指引，不只改文字留下死前置；缺 pin/身份不足明确补正/新准备或
  只读核查。FileIndex RO-7 后续整体移除，本 Task 不新增索引兼容/补偿/双写/no-op 仓储。

### 6. 验证原生支持旅程与生产产物后交新候选

- 真 Python/SQLite/Worker + production build 验证旧路由普通404、旧命令普通错误、无 Scan
  模式/aliases；fresh 新整理→真实等待→同页摘要→精确确认→真实结果→重启/恢复。
  分析/未确认零 mutation/许可，来源变化重置，成功/未知兄弟不重放。
- 改动共享观察/claim/并发时用双 connection/event/barrier 证明；保留首败和精确复跑，
  不建设旧 Scan 停止/接管/迟到发布矩阵。桌面/380px/键盘/深链/返回/重连按实际旅程验收。
- 按下方完整 T4 冻结 executable、验证源码/served-assets/wheel/image 身份，提交连贯 checkpoint
  和真实报告/耐久证据。不复用旧候选 T4 覆盖新源码，不做 Slice-final/下一 Task/A Final Review。

## Acceptance Criteria

- [ ] **AC-1 产品不存在：** 独立 Scan 的 Web/API/CLI/aliases/注册/帮助/导航/readiness/action 项
  与专用创建/调度/执行/重试/继续/数据结构/退役层删除。旧 URL 为普通认证下404，无专用页/
  410/指引；顶层 `scan`（含旧flags/`--help`）和 `jobs submit scan` 为标准 argparse 错误退出2，
  help 无该输入，配置/数据库/runtime/Storage/Provider 未调用。通用不支持类型发现/准入前拒绝。
- [ ] **AC-2 定义模式删除：** scan-only/scan-and-plan 值/aliases/defaults/selector及专用发布/
  Scheduler/admission/dispatch/continuation不存在，无 Scan-origin 特判或旧模式兼容执行器。
  旧意图不转 organize；自动整理仍需完整明确权限，支持 Preview 等能力不因名称误删。
- [ ] **AC-3 首次部署/支持工作完整：** fresh schema/config 不含 Scan专用产品，无旧 Scan/V1
  parity/迁移/转换/接管/历史兼容；不清库/删媒体。其他工作 Task/Result/历史/导出/pin/权限/
  审计、同版本重开/重启/逐项恢复及事务失败原子性正常，未知输入零新工作/观察/许可/变更。
- [ ] **AC-4 真实稳定性：** 无预扫描的新来源在原整理内完成有界跨真实间隔观察与同页摘要；
  年龄/变化重置/临时排除/限制/精确pin保留，未稳定或不完整项不可执行，确认前零变更/许可。
  不再依赖/建议 Scan；shared discovery/planning、diagnostic/scheduled Preview、DryRun/Rules正常。
- [ ] **AC-5 共享权威/自动化延期边界：** 不增加队列/配置/发现/恢复/执行引擎；真来源/pin、RBAC、
  claim/fence/原子准入、OrganizerExecutor-only、C→A身份与已完成/未知非重放不回归。模式删除
  和必要耦合清理采用最新A授权；43专属实现不作为保留/验收前提，页面重新设计留到45完成后，
  不主动扩展43功能，也不削弱其他受支持基础流程。
- [ ] **AC-6 原生体验：** 新整理及其他支持工作桌面/380px/键盘/深链/返回/重连可用；普通404
  不伪装退役页，Worker/稳定性/权限/缺pin/未知请求有当前合法下一步，无CLI回退或内部材料负担。
- [ ] **AC-7 T4/真实性：** 全量/真实Python/持久化/wheel/Docker证据匹配新候选及实际产物；
  A-owned文档/预存脏文件保持，不改历史完成事实；报告RO-7仍待下一Task，不宣称Slice完成。

## Required Tests

High/T4 来自删除跨 Web/API/CLI/发布/调度/Worker 的产品类型、共享来源/观察/持久化与权限边界；
不是旧 Scan 生产迁移风险。先修受影响反例，再对新精确 executable 完成全部门禁；full 包含 focused
时记录覆盖，不机械重复。同版本 reopen/restart 不等于旧版兼容。ignored 运行库属用户环境，
全量用精确候选干净隔离 checkout、临时 Local/SQLite/fake Provider，禁读改用户库/私密 config。

最新自动化延期边界不降低 High/T4 或下列完整门禁。若为完成本 Task 合法调整/移除43专属
实现，相关用例须按新支持表面同步，不要求旧页面/Run once逐项兼容；共享权限、pin、结果、
未知效果非重放和其他受支持流程的原断言必须保留映射，不能以延期为由删安全证明或加skip造绿。

### Development and correction feedback

1. **不存在与零副作用：** 先改现有 `tests.test_scan_retirement` 和受影响 Web/API/CLI 用例，
   覆盖旧new/detail/API aliases及方法、顶层scan/flags/--help、jobs submit scan、通用工作/
   定义模式/别名的普通错误。help/typed/routes/readiness/action无Scan项，无墓碑/410/退役指引。
   CLI以 `_configuration`、数据库/runtime/Storage/Provider 调用即失败证明参数前置拒绝；
   Web/API按正常认证校验，所有不支持输入零发现/观察/准入/执行许可/媒体变更。
   `.venv/bin/python -m unittest tests.test_scan_retirement tests.test_manual_operations_contract
   tests.test_manual_operations tests.test_automation_api tests.test_automation_admission
   tests.test_operator_job_submission tests.test_batch_cli tests.test_task_retry
   tests.test_task_pause_resume tests.test_scope_continuation`。
2. **共享发现/稳定性/准入：**
   `.venv/bin/python -m unittest tests.test_scan_retirement_stability tests.test_scanner
   tests.test_media_discovery tests.test_media_discovery_provider_manifest tests.test_organize_preparation
   tests.test_manual_organize_preview tests.test_manual_organize_execution
   tests.test_recovery_continuation tests.test_task_persistence tests.test_organizer_mutation_authority`。
   控制时钟证明首次观察不稳定、真实间隔就绪、大小/mtime/指纹改变重置、临时/排除/限制、
   单项/多项/目录、pinA→ActiveB、缺pin、工作重开/旧owner和兄弟项独立。精确子集/附件警告、
   确认前零mutation/许可不回归。原生生产Worker还须真实跨短配置间隔，不能只靠fake clock。
3. **定义模式删除与支持能力：**
   `.venv/bin/python -m unittest tests.test_automation_definition_execution
   tests.test_automation_definition_occurrence tests.test_automation_task_definition_preview
   tests.test_operations_task_center tests.test_operations_run_inventory
   tests.test_operations_run_detail tests.test_processing_checkpoint`。
   删除旧Scan模式成功/兼容断言，新增enum/parser/config/API/Scheduler/Worker普通非法值与
   零准入反例；省略/非法mode不转成有权限organize。支持的自动整理显式grant、撤销/消费/
   pin与diagnostic/scheduled Preview正常；不是借删Scan模式取消所有Preview。
   通用历史/计数/恢复fixture用受支持工作，保留读取无副作用和非重放证明。
4. `web/`：`npm run test -- run src/features/operations src/entities/operations
   src/shared/api src/shared/navigation src/routes`。核对route/typed/selector/default/aliases消失，
   旧链接普通not-found、正常auth/返回/错误，其他详情/任务中心/Files/Dashboard及受影响Settings。
   禁用 `any`/假available/隐藏元素代替产品删除。按实际diff加入相关测试。
5. 扩展真实Python harness/spec 与wheel/Docker proof，旧Scan fixture替换为支持工作，不重建
   V1/Task Base旧Scan数据库、全状态历史、迁移/接管/专用退役矩阵；所有仍适用的RBAC/secret/
   来源/持久化/零mutation断言逐项映射，不能删含义/加skip/retry/放宽timeout造绿。

### Final checkpoint gates

最终新 executable candidate 完整满足以下门禁。cb5ebd8 等旧 executable 结果不可覆盖本次改动；
后续仅 report/document successor 可在明确diff证明运行输入不变后按workflow复用，并重跑文档消费检查。

- 根目录：`.venv/bin/python scripts/check_governance.py`、`.venv/bin/ruff format --check .`、
  `.venv/bin/ruff check .`、`.venv/bin/python -m unittest discover -s tests`、
  `.venv/bin/python -m compileall -q mediaflow tests scripts`、`.venv/bin/python -m pip check`。
- `.venv/bin/mediaflow --config config/strategy.example.json config validate` 和
  `.venv/bin/mediaflow --config config/mediaflow.phase13.2.example.json config validate`；
  `rg -n -i 'ffprobe|ffmpeg' mediaflow pyproject.toml` 无匹配（预期exit1）。
  逐项审查产品类型/aliases/registration/defaults/retirement层删除清单和剩余scan/preview真实
  消费者，不要求全仓零字符串。Type C→NamingA/ClassA仍为C的计划/真实结果回归在full/native。
- `web/`：`npm run typecheck`、`npm run lint`、`npm run format:check`、`npm run test -- run`、
  `npm run build`、`npm run test:e2e`。共享路由/导航/typed/readiness涉及所有普通入口。
- `web/`：`npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts`；
  `npm run test:e2e -- --config=playwright.python.unicode-principal.config.ts tests/e2e/operations-principal-identity.python.spec.ts`；
  `npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-task-center-visual.python.spec.ts`。
  完整顺序spec；新增probe自包含，新spec写明并执行精确命令。实际production assets看1536×1024
  与380×720：九标签/正常404/无模式selector、真实稳定等待/变化重置、同页摘要/精确确认、
  Files返回、键盘/遮挡/深链/重连，保留实际截图/trace而非脚本“aligned”标签。
- `.venv/bin/python -m pip wheel . --no-deps -w dist`；
  `.venv/bin/python scripts/wheel_smoke_test.py <本候选确切wheel路径>`。
  安装wheel后从源码目录外运行真实site-packages消费者：旧CLI普通参数错误、帮助无Scan、
  旧API普通404/非法类型、无Scan模式/专用schema，同时共享发现/摘要/确认/Preview仍工作。
  不只import/“missing item”拒绝，记录wheel digest及模块实际导入路径。
- 扩展既有Docker task-center proof或增加小型首次部署proof，报告可直接复跑的精确命令：
  同候选production API/常驻Worker普通拒绝不支持输入，无Scan路由/模式/退役层；fresh新来源
  不预Scan，真实观察→摘要→明确确认→实际结果→同版本重启/恢复。临时Local/fakeProvider；
  未确认零许可/变更、变化重置、成功/未知不重放，核对实际served assets。
- `.venv/bin/python scripts/docker_release_security_smoke_test.py --image mediaflow:task45.4-security`。
  可复用经内容证明的同一image；记录完整imageID、源码/served-assets manifest，不用标签/
  打印SHA代替身份。Docker不可用如实报告，不削弱原RBAC/secret/非重放断言。
- **持久化门禁：** fresh schema/config 无Scan专用表/模式/默认值；支持工作创建→持久观察→
  确认→执行→close/reopen/重启/逐项恢复正常，事务失败回滚、原pin/权限/结果/审计保全。
  提供共享schema实际diff，无改动也明确证明。本次不要求Task Base旧库升级/V1 parity，
  不能为首部署清用户库或恢复Scan兼容代码；若确需改共享schema，验证本版本fresh/reopen和
  失败原子性，不删/改受支持历史含义。完整FileIndex schema退出留RO-7，不在本Task冒充完成。
- `git diff --check`；完整Task Base..Head manifest/name-status/stat/diff、A文档与私密文件检查。
  A-owned范围文件对照最新授权 `f1e67582022b565cf1ba2ef6f427081aa94cd901`（早期授权仍在Git），
  Task/代码仍对照原Task Base。
  新source/tests/harness/dependencies/config/assets必须匹配最终T4，不能复用旧退役语义报告。

### B independent verification

B 读实际Base..Head、剩余消费者及匹配候选原始证据，独立核对API/CLI/Job/模式/continue/
Worker普通不存在/不支持错误、无产品/退役认识层、零发现/准入/许可。真实Python/SQLite/Worker
和production build完成无预扫描来源的真实稳定观察→同页精确确认→执行→重启恢复；核对
pin/权限/成功与未知兄弟不回归，实看桌面/窄屏/键盘/旧深链普通404。缺失/不匹配才重跑相关
门禁，不因换审查者无理由重复全量；确定P0/P1可提前拒绝，PASS前仍须满足全部新候选门禁。

### Evidence and preservation

按workflow将source/checkpoint SHA、cwd/命令/runtime/依赖/fixture、时钟/真实等待、Worker/selection/
retry配置、exit/counts/skips/duration、首败/复跑、日志/截图/trace和wheel/image/served-assets digest
保存在 `.git/validation-evidence/<full-source-sha>/<run-id>/INDEX.md` 或CI；/tmp不能是唯一交接。
本次范围修订前dirty TASK副本与状态留在
`.git/validation-evidence/scan-first-deployment-scope-20261018/`，不作为产品实现证据。

保留开始已有的 `docs/pics/操作与任务.png` 删除意图、两张未跟踪自动化页图、各处`.DS_Store`、
`output/imagegen/slice45-task-center-v1.zip`、`web/test-results-batch-check/`、
`web/test-results-real-python-final/`。不纳入checkpoint，不用reset/restore/clean/stash隐藏。
`config/alist.json` ignored/untracked/unstaged；不打开用户运行DB或生产媒体。证据不进普通源码提交。

## Non-goals

- Developer修改SLICE/Roadmap/Progress/稳定需求/CURRENT声明、移动Base/关闭Slice或规划下一Task。
- Slice43自动化页/Run once/指标/全局设置的重新设计实现留到45完成后；本Task仅清理必要耦合，
  不导入后续冻结开发，不要求保留/恢复/兼容旧43专属实现。Scan模式和专用路径仍完整删除。
- 整体Preview/DryRun/Rules或支持scheduled Preview退役、V1整体cutover、新Provider/MediaLibrary Organize。
- 旧Scan/V1 parity、历史/停止/接管/迁移/转换兼容层、删除现有数据库/媒体/用户文件/Git历史。
- FileIndex完整退出与CLI列表统一属RO-7，待本Task PASS后一个连贯Task完成；不提前验收。
- 新队列/Scanner/观察/恢复/执行引擎、扩大限制、任意历史Reprocess、自动repin、附件-only执行/
  补偿回滚、主文件/已完成/不确定effects重放，或已验收创建恢复界面整体重做。

以上按最新已提交 A 修订实施，Task ID/Base 和安全/T4不变；未满足项继续在同一修正循环完成，
不将延期的自动化页工作或RO-7后续单元当作本Task已交付。

**历史候选报告，非当前完成声明。** 以下原文对应 cb5ebd8/ef1f1f3；本轮范围调整未改产品代码。
其专用退役拒绝、旧链接指引和保留定义模式不满足新Contract；原测试总数不能作为新候选通过证据。
Developer完成同Task修正并验证新候选后再追加真实报告，不将本段历史文字改成新验收事实。

### Checkpoint / Scope

- **Status: READY FOR B REVIEW**；Developer 不自判 PASS、不关闭 Slice、不规划下一 Task，未 push。
- Task Base：`f02443917bcd5b3ef645a32c432b191dc4f12aa3`。
- 最终 executable checkpoint：`cb5ebd834d6532bdc2b6354073d32d3dc6dd0ddd`。
  本报告为其 TASK.md-only successor；完整报告提交 SHA 写入下方证据的
  `report-checkpoint.log`，`report-only.diff`证明无源码/测试/harness/依赖/配置变化。
- 耐久证据：`.git/validation-evidence/cb5ebd834d6532bdc2b6354073d32d3dc6dd0ddd/final-20261018/INDEX.md`。
  精确 cwd/command/exit/count/duration、runtime、manifest、首次失败、trace/截图、wheel/image摘要
  均留存；本地路径不声称远程可达。开发反馈及起始脏文件快照保留于
  `.git/validation-evidence/task45.4-development-20261018/`。

### Changed Files / Implemented

- 完整 Task Base..Head name-status/stat/diff 见证据；A 已提交的范围文档单列归属，不算 Developer
  实现。本轮未修改 SLICE/Roadmap/Progress/稳定需求/CURRENT；原有用户图像删除、未跟踪图像、
  .DS_Store/zip/旧浏览器输出均保留且未纳入提交；私密 alist 仍 ignored/untracked/unstaged。
- Application/API/CLI/Worker：独立 Scan submit、所有 aliases、旧详情/取消入口、通用 Job(scan)、
  forged-definition dispatch、retry/resume/continue 明确退役拒绝；拒绝在配置/Provider/Storage发现
  前完成，不创建新 Task/观察/许可，不暗转 Organize，保留 RBAC。CLI 旧 flags 仅返回薄拒绝。
- 删除独立 ManualScan runner/domain/repository/history/cancel/UI 装配；只留有界错误类型与退役
  说明。V1/V2 创建/执行动作删除，旧new/detail链接认证后指向新建整理与任务中心，不回放旧scope。
  readiness/action matrix 不再广告可执行Scan；其他任务历史/结果/导出与控制保持。
- 复用未改动的 MediaDiscovery Worker/过滤/真实稳定性观察：fresh目录/单项/多项无预扫描即可
  等待真实区间、源变化重置、同页摘要并精确子集确认后才由真实 Worker 执行。旧mtime不是观察。
  修正可达恢复指引，不要求不可能的独立Scan；不新增队列/观察/恢复引擎或索引补偿服务。
- 定义Preview复用同pin/同definition内的持久来源观察；变化重置、新pin不能借旧区间，Provider
  DTO/秘密/指纹不泄露。冻结定义绑定Automation模式/发布/调度保留；C→NamingA/ClassA仍是C。
- 通用历史/取消/pin等原Scan fixtures迁为受支持Preview，保留原安全断言；更新真实Python/
  Docker/release-security夹具。新增退役反例、fresh观察/变更/pin和原生完整链测试。

### Tests And Results — Final T4

以下全部来自上述最终 executable SHA 的完整历史隔离clone，不读用户ignored运行库。
修正后的全部门禁重新执行，没有用旧候选最终全量结果代替。

| 门禁 | 实际结果 |
|---|---|
| Python full unittest discover | **PASS 2500 tests /249.410s /7 skipped** |
| governance、ruff format/check、compileall、pip check | **PASS** |
| 两个批准example config validate、禁止FFprobe/FFmpeg搜索 | **PASS**；搜索无匹配预期exit1 |
| Web typecheck/lint/format/build | **PASS** |
| Vitest full | **PASS 76 files /1112 tests** |
| Fake浏览器全量 | **PASS 240**，workers1/retries0/trace on |
| 完整真实Python inventory spec | **PASS 38**，精确剩余scope/稳定性/确认/真实Worker/重连非重放 |
| Unicode principal / 九视图及创建visual spec | **PASS 1 /2**；实际查看桌面1536×1024/380×720截图 |
| wheel build / wheel_smoke_test | **PASS**；清除PYTHONPATH，真正安装而非源码误导入 |
| 安装wheel消费者 | **PASS 29**；site-packages实际CLI退役、内部观察/摘要/确认/Worker |
| production Docker退役/真实稳定性/同页确认/Worker/restart | **PASS**；无确认零许可/零变更，变化重置 |
| Docker release-security完整门禁 | **PASS**；secret/RBAC/权限/非重放等原断言保留 |
| 完整manifest、冻结文档、私密文件、git diff --check | **PASS** |

- 7个 **SKIP而非PASS**：独立真实OpenList/SMB/S3验收环境3项、Local/SMB/OpenList/S3 endurance
  隔离profile4项未提供；精确名称/原因见 `skip-reasons.log`。未新增skip/重试或削弱断言。
  raw日志中的 ResourceWarning 保留，未掩盖或自行认定既有豁免。
- wheel SHA256：`2dd97025ce001ddf0bd300ad62e925c3ad4221840ebebd6ef3289d19d0e65beb`；
  162 Python模块逐字节匹配候选。最终release-security重建的实际imageID：
  `sha256:6a0a857e83fd41d514b5ec32b7449a637814bd78b3610570cec974bf883327f5`。
  重建后再次完整运行production proof，核对162 Python/4 Web文件与实际served assets字节摘要。
- shared schema条件门禁：60个共享CREATE TABLE语句不变，schema47不变；仅移除两个Scan专用
  fresh CREATE，不新增DROP/delete/ALTER/迁移。实际diff与shared-schema-comparison.json留证；
  fresh/reopen共享pin、全量既有迁移与wheel backup/rehearsal通过，不建设旧Scan迁移矩阵。
- 开发期首败均保留：无.git归档环境、Preview夹具scope/Provider/识别、fake旧Scan预期、Colima
  临时挂载、wheel PYTHONPATH污染、release夹具构造无关OpenList、退役链接视觉对比度；逐项定位
  修正后先跑受影响用例，最终候选完整T4。未把产品失败标为既有或自行豁免。

### Decisions / Risks / Remaining Work

- 完整FileIndex退出和CLI/两种库页实时列表统一是 **RO-7待后续B规划**；本Task不交付它，
  不因此宣称Slice全部Outcome完成。共享Scanner/enum/定义绑定Scan与有限历史标签保留原因见索引。
- 无数据库清空/媒体删除；只在隔离Local fixtures执行显式确认操作，生产路径仍仅OrganizerExecutor
  变更媒体。定义/普通pin、未知效果非重放、权限及源范围不降级。
- 已实际审阅九视图、旧new/detail、稳定等待、同页摘要与确认、键盘/窄屏/返回证据；长摘要需要
  纵向滚动但没有页面横向溢出。现存部分共享英文指引保持，不进行范围外整页重做。
- 可复用经验：容器exec不继承entrypoint加载的秘密环境；测试fixture仅构造所需Local适配器，
  不因无关Provider/Storage造成假失败。wheel消费者清除PYTHONPATH并断言site-packages真实来源。


## B Review Result

```text
Contract Recheck: 0b59846a2f85d2148b8f6de8d8eaa759e1be42cc
Scope Decision: TASK45.4 LEGALLY ADJUSTED; ID/BASE/HIGH/T4 UNCHANGED; RO-7 AFTER PASS
Previous Reviewed Range: f02443917bcd5b3ef645a32c432b191dc4f12aa3..ef1f1f3129f3424c41db59e28d185b7467032737
Previous Executable Head: cb5ebd834d6532bdc2b6354073d32d3dc6dd0ddd
Implementation Decision: FIX REQUIRED
New Executable Candidate Review: NOT PERFORMED; NO PRODUCT CODE CHANGED BY RESCOPE
Slice Required Outcomes all satisfied: NO
Next: SAME TASK FIX LOOP; B PLANS RO-7 ONLY AFTER PASS
```

### 当前修正决定 — 2026-10-18，首次部署范围

此前Review1的CLI复现仍成立，但“唯一阻塞”只描述当时的较窄验收。最新Contract下已确认仍有
旧routes/退役页/API410/CLI注册及choices/专用guards/定义Scan模式与默认值，均须按上方
六阶段 Scope 和AC-1/2删除；共享稳定观察的有效实现保留并回归。新候选执行完整T4后再交B。
本轮只checkpoint范围并调整Task，未修代码、未跑新runtime候选、未授予Task PASS或Slice closure。

本轮文档验证：治理检查 PASS；`tests.test_governance tests.test_release_security` 共15项、
2.364s、OK；`git diff --check` PASS，11份相关文档的本地链接无缺失，开始已有12项无关脏文件
状态均保留。A checkpoint仅含10份范围文档；本轮无源码/测试/harness/config/依赖/产物改动。
证据：`.git/validation-evidence/scan-first-deployment-scope-20261018/INDEX.md`。
这些只是材料性范围调整后的文档/治理检查，不是Task新候选T4或B PASS。

以下Review1及其修正步骤是历史记录，涉及保留退役防线、旧模式或旧入口说明的要求全部被
当前Goal/Scope/AC/Required Tests取代；不得依据旧步骤恢复兼容层，也不要求过期断言通过。

### B Review 1 — 2026-10-18

**唯一阻塞（P1；AC-1/AC-7、开发步骤3）：CLI 仍将 `jobs submit scan` 识别为正常工作流。**

- `mediaflow/final_cli.py:467` 的提前拒绝仅覆盖顶层 `scan`；`jobs submit scan` 继续进入
  `_configuration`，随后在 `:1171–1187` 构造 repository/service 才可能到达应用层退役拒绝。
- B 独立隔离复现：无 config 返回 `--config or MEDIAFLOW_CONFIG is required`；不存在的 config
  返回读取错误，均已越过参数阶段。仅有 management bootstrap、
  尚无 Active 时抛出未处理的 `AttributeError: ManagementBootstrapConfiguration ...
  automation_maximum_active_jobs`。用户最新指令要求该输入作为普通非法参数在配置前停止。
- 完整复现脚本、原始首败/复跑、Task Base 对照和审查边界：
  `.git/validation-evidence/cb5ebd834d6532bdc2b6354073d32d3dc6dd0ddd/b-review1-20261018/INDEX.md`。
  `probe_cli_retirement.py` 在候选 exit1 为原验收下的反证；不作为通过的测试计数。
  该原脚本要求所有入口给专用退役提示的断言已被用户对 `jobs submit scan` 的新指令取代，
  只作历史诊断保留，不要求 Developer 让旧断言通过。

### 历史同 Task CLI 修正步骤（已被当前完整修正计划取代）

用户补充指令（2026-10-18）将本轮 CLI 删除要求扩展到顶层 `scan`。上方 B Review 1 保留
当时的复现事实；“顶层现有拒绝测试保持自身规则”的旧修正要求已被下列要求取代。
原 Developer 报告/证据中的 CLI 薄拒绝是旧候选事实，不满足现在的验收，也不要求通过旧的专用文案断言。
本轮只修改 Task 要求，不表示产品代码已修复或 B 已验收。

1. **先加失败回归。** 在 `tests/test_scan_retirement.py` 覆盖顶层 `scan`、带旧
   `--limit`/`--path` 的调用、`scan --help`，以及 `jobs submit scan` 和其带 `--limit` 的调用。
   对无 config、不存在/非法 config、临时最小 bootstrap 无 Active，
   以及运行时不可用/损坏的输入，均断言标准参数错误（退出码2；直接调用 argparse 时捕获
   `SystemExit(2)`）、普通未知命令/非法参数类别和无后续调用；断言没有专用退役文案/类别或
   新建整理指引。把现有顶层专用退役测试改为上述不存在语义，不保留旧断言。
2. **删除命令注册和专用退役分支。** 删除顶层 `scan` 的 `add_parser` 注册、对应帮助项及
   `arguments.command == "scan"` 的提前拒绝分支；将 `jobs submit` 的 workflow choices
   改为只接受 `preview`。顶层和 submit 帮助/用法只展示实际支持的输入；让 argparse 自身
   拒绝旧 `scan` 调用。不添加 argv 预检查、
   特殊 argparse Action、隐藏选项、别名、旧输入重定向或专用退役分支。删除只为该旧CLI
   输入保留的无消费者代码，相关帮助/校验说明同步为真实支持范围。
   不通过捕获通用 AttributeError、给 bootstrap 补工作配置字段或建立新服务来绕过此问题。
3. **证明无前置副作用。** 对上述两种旧CLI输入 patch `_configuration`、运行库/配置库、runtime
   lease、Storage/Provider factory 为调用即失败，断言全部未调用。临时目录中无新数据库、
   Task/Job/观察/许可和媒体变更。正常 `jobs submit preview`、list/show/cancel 等保持原分流。
   保留应用 `AutomationJobService.submit` 和 Worker 的退役防线、真实 Definition 来源校验。
4. **先跑受影响反馈。** 执行 `.venv/bin/python -m unittest tests.test_scan_retirement
   tests.test_operator_job_submission tests.test_batch_cli tests.test_automation_admission
   tests.test_scope_continuation tests.test_task_retry`。独立复现核对新指定的普通参数错误语义；
   不为满足原证据脚本中过期的专用退役提示断言重新保留旧命令。
   按实际测试文件更新命令，不删已有 RBAC/零工作/稳定性/非重放断言。
5. **冻结修正候选，再完成现有 Final checkpoint gates。** Difficulty/范围/Base/Goal/AC 与
   **T4 不变**；此修正改变 executable source，不能沿用 cb5ebd8 的最终全量作为新候选门禁。
   安装 wheel 的实际 CLI 消费者必须覆盖顶层 `scan`（含旧 flags/`--help`）与
   `jobs submit scan` 在无 Active/配置不可用时直接以普通 argparse 未知命令/非法参数错误
   停止、无专用退役提示、顶层和 submit help 中无该命令/可选工作流，
   并核对从 site-packages 导入。其余原生/生产门禁遵循上方既定计划；提交新 checkpoint，
   更新真实报告与耐久证据后再交 B。不得 amend 已审历史。

### Review1 当轮实际验证与未执行边界（历史）

- 治理检查 PASS；已提交 Contract 与工作树一致，report successor 只改 TASK.md；A-owned
  文档从 `0237b7d...` 至待审 Head 无变化，Task Base..Head whitespace 检查 PASS。
- 在精确 executable SHA 的隔离 checkout 独立运行 retirement、fresh stability、Definition
  Preview、scope continuation、Task retry 与 recovery continuation：**135 tests /11.822s /OK**。
  首次命令误填不存在的 `test_recovery_admission` 模块（91个真实用例运行且一个导入错误）；
  原始日志保留，改用实际存在的模块后得到上述结果。ResourceWarning 原样保留。
- 已核对实际源码差异和 Developer 证据索引；本轮遇到确定 P1 后按 workflow 提前拒绝，
  **未独立复跑 full Python/Web、真实浏览器、wheel 或 Docker，未完成本候选全部验收或证据复用批准**。
  Developer 的已有全量结果仍是该旧候选的证据，不覆盖漏测入口，也不是本轮 B PASS。
- 保留所有会话开始已有脏文件和私密 ignored 配置；不修改产品代码、Slice/Roadmap/稳定需求，
  不创建45.5、Closure Packet，不宣布 Slice 完成。Task45.3 PASS仍保持其历史结论。
