# Task 46.4 — 只管整理的任务中心与真实四类恢复状态

Authority: committed [Slice46](SLICE.md) **RO-4**、AC-5/6/7/8/14/15，以及保持 RO-2/RO-3
已验收入口与确认语义所需的衔接；[Development Workflow](docs/development-workflow.md)。
实施前阅读 [Developer experience](docs/agent-experience/developer-implementation-role.md)。

```text
Task ID: 46.4
Parent Slice: 46
Status: FIX REQUIRED
Task Base: 44cba4f93b94b72d6dee52fcd1199be729ec78c4
Difficulty: High
Test Level: T4
Planner / Reviewer: B
```

## Goal

用户打开任务中心，只看到已受理的整理工作及其合法整理续作；普通复制/移动/删除等仍回原库
文件页。中心保留八个视图：全部、进行中、需要处理、已结束、识别、元数据、分类、冲突。
“需要处理”及所有待处理任务数只表示四类真实业务问题和它们尚需人工完成的恢复步骤。
技术失败保留真实只读历史；完整恢复后的整体显示与实际结果一致，不伪报完成，不改写旧尝试。

完整旅程：进入任务中心 → 查看同一后端整理总体的列表/统计 → 筛选/翻页/选择任务 → 处理
实际四类问题 → 保存决定 → 安全分析 → 查看精确摘要并明确确认 → 查看真实结果。
刷新、重连、前进/后退和服务/数据库重开保留精确上下文。初次手动待确认仍在进行中/全部，
不计人工问题；仅剩技术失败时退出需要处理，仍可在全部/已结束查看事实详情、日志和导出。

Requirements: `V2-OPS-014/016`，必要的 `V2-OPS-015/017`、`V2-FILES-007` 衔接；
`V2-UX-001–003`、`V2-WEB-001`、`V2-AUTH-001–003`、`V2-SAFE-001`；
`UX-001–003/005–007/010`、`REQ-TASK-002/003/006–009`、适用的 `REQ-RECOVERY-004–009`、
`REQ-API-002/003` 和 `REQ-SAFE-*`。按 Slice46 的显式修订收缩 V2 中心，不删除管理 API/CLI 能力。

必须阅读 [Product Experience](docs/product-experience.md) 的完整 TARGET 手动/恢复/中心旅程、
CURRENT Tasks/results/recovery 与普通文件本地查看旅程；[Task Center specification](docs/task-center-page-spec.md)
的 TARGET 八视图/确认规则和仍适用的 CURRENT 详情交互；[Architecture](docs/architecture.md)
的 TARGET work-query ownership、CURRENT Tasks/Results、Operations query/recovery、Files 本地 readback。

### Actual code gap and reuse

以下是 Task Base 的实际代码，不表示本轮已实现或已跑产品探测：

- `mediaflow/domain/operations_run.py::OperationsRunView` / `RECOVERY_PROBLEM_TYPES` 及
  `web/src/entities/operations/run.ts::RUN_VIEWS/RUN_PROBLEM_TYPES` 仍为九视图、五问题类型。
- `sqlite_runtime.py::_run_query_document()` 从既有 Job/Task/transfer 关系生成共享混合总体；
  `_run_query_clauses()`、`operations_runs_window()`、`operations_run_summary()` 及 exact-ID
  detail/items/problem-items/records 读尚未共同限定为整理。summary 仍统计 failure task/file。
  page/count/status/summary 已有同一 SQLite 读快照与有向游标，必须复用，不能退回前端过滤。
- 该 document 的 `item_attention` 仍包含 `actionable_failure` / 通用 `safe_continuation`，
  `run_level_repair` 把有技术修复证据的 pre-Task failed Job 计入 Attention。
  `_problem_item_predicate()` 仍有 failure 分支；不能只删网页标签而保留错误的待处理总体。
- `_verified_recovery_follow_up()`、既有 recovery lineage 和 `automation_linked_handling()` /
  `_automation_handling_coverage_locked()` 已有按原 item 精确关联的恢复证据。复用可证明部分，
  但后者服务 Automation 原始结果/处理状态，不能直接覆盖共享历史或把“最新子任务成功”当全成功。
- `OperationsLanding.tsx` 虽已移除 Task46.3 的创建/手动/发现区块，仍挂载 `WorkerReadinessSection`
  和 `ResidentServiceStatus`，其 readiness query 还参与初始读取、refresh 和 fetching 状态；
  页面仍提供 failure 视图、五类说明与失败文件入口。
- `RunDetailTabs.tsx`、`ProblemFilePanel.tsx`、`TaskItemRecoveryPanel` 和旧 Task/Job V2 页面
  仍可能提供通用技术失败恢复/下一步。保留四类原生表单和精确确认组件，收缩中心呈现。
- 路由仍存在 `/operations/tasks`、`/operations/jobs` 及其 detail；不能留下混合列表或通用
  失败恢复的旁门。`TaskDetailPage.tsx` 已用 `fetchLibraryFileOperationOrigin` 查普通工作的
  持久来源；`LibraryFileOperationsDialog` 和 Files 的精确 operation 选择可复用，不另建本地查看机制。
- `service_api.py` 的 runs collection/detail/problem/items/records/export、游标 scope、
  `api-client.ts` 的类型/normalizer/query keys 和 Dashboard/Shell/Automation 返回链接需一起核对。
  同一 repository 还服务 Automation metrics/records、普通本地操作及管理接口，不能全局裁掉它们。

### All Slice outcomes reevaluated at planning

| Outcome | Task Base 上的结论 |
| --- | --- |
| RO-1 可读操作 | Task46.1 验收保留 |
| RO-2 Files 先接纳整理 | Task46.3 PASS：`44cba4f9:TASK.md`，完整范围/限制/证据保留 |
| RO-3 普通操作留在原库页 | Task46.2 验收保留；既有原生菜单失败限制仍有效 |
| RO-4 整理专用八视图及四类真实状态 | 未完成；本 Task 选定完整交付 |
| RO-5 自动化打开/保存/启用/运行一次 | 未完成；本 Task 不实现其意图与执行改造 |

## Implementation Scope

1. **先统一“哪些记录属于任务中心”。**
   从现有 producers、`_run_query_document()` 和 API consumers 梳理支持的整理命令、持久
   admission/origin、Job→Task 和恢复/续作关系，形成共享、可测试的整理成员判定。
   纳入明确手动整理在发现/分析/确认/执行中的工作、现有定时/definition-bound 整理、合法
   整理续作及尚未产生 Task 的整理排队/失败 Job。独立分析/准备、普通文件操作、通知和未知
   无关命令不属于中心；不能仅凭 `analysis` 阶段排除已明确受理整理的 Task。
   只用支持的命令语义和已保存关联，不按显示名、路径子串、时间邻近或当前 Active 猜归属。
   不删除任何记录，不重建另一套任务或生命周期。
   先按实际写入方完成并测试下列判定表，再改外层过滤：

   | 持久事实 | 中心归属 |
   | --- | --- |
   | Files 明确受理，`media_discoveries.organize_task_id` 指向真实 Task | 纳入，尚在发现/分析/等待初次确认也不隐藏 |
   | 已确认 manual execution 及其 Task；已有实际执行意图的支持整理 Task/Job | 纳入，含尚无 Task 的合法排队/失败 admission |
   | recovery/scope/metadata-correction 等持久链接证明是在继续一份整理工作 | 按原工作与真实尝试关系纳入；分析阶段不凭自身 execute=false 就丢失 |
   | 独立 DryRun/analysis-only/preparation，没有已受理整理或合法恢复来源 | 不纳入，不把分析变成整理提交 |
   | 普通文件/通知/未知无关命令，或只有伪装的名称/前缀 | 不纳入；已知普通工作走其本地持久来源 |

   这是语义表，不是新造命令白名单：逐一核对当前 producers 的字段/链接与支持的旧记录，
   不能只看 command、execute 布尔值或某个链接中的一项就替代完整身份。

2. **把总体限制下推到统计和分页之前，并贯穿精确读取。**
   同一受权整理总体用于八视图、待处理、状态分区、来源选项、搜索、过滤、游标和 selected
   detail/items/problem files/records/log/export。保留 Job→Task 显式去重，游标只限制页，不
   截断统计总体；source options 来自有界的受权整理总体，不来自当前页或未限定混合总体。
   page/count/summary 保持一致读快照。较旧任务必须能按 exact ID 打开，不能只扫描最近 N 条。
   如果需要区分中心与共享管理查询，明确现有调用的 query/context 和兼容语义，再同时接通
   API/client/cache/cursor；不能只在某个网页调用处补 filter，或全局改变其他消费者的总体。
   游标绑定 principal、整理总体和全部实际过滤条件；旧 failure/其他总体游标不能混用。
   保持 bounded SQL、稳定排序、红化后的搜索证据和不可用≠零，读取不调用 Provider/Storage、
   不创建工作或重算当前 Active 的历史业务身份。

3. **统一四类当前问题与真实处理责任。**
   复用既有 typed review/decision/checkpoint 和精确 lineage，给四类任务列表、文件列表和
   pending/Attention 共用同一判定。Metadata 含候选/补正业务决定；网络/429/Provider 传输故障
   不因处于元数据阶段而成为 Metadata 决定。Attention 是四类当前问题的 distinct union；
   同一显示任务跨类型只算一次，各类型保留自己的任务/文件数。
   四类恢复的必要人工决定、分析后的摘要确认保持原类型关联和可达入口；保存决定或分析完成
   不是问题已成功解决。后台排队/分析/执行且无需人工操作时进入进行中，不因“有续作”常驻待办。
   普通手动初次 WaitingConfirm 没有四类 lineage，只在进行中/全部提供原精确摘要。

4. **按逐项实际结果投影结束与恢复成功。**
   当前问题转移给合法子尝试时，按持久关系更新当前处理责任，保留每次尝试的独立历史。
   新四类问题转到对应类型；恢复只剩技术失败时移出四类待办，保留真实 failed/partial/unknown
   事实，不能靠旧 `_resolved`/retry/continuation 标记继续占 Attention。
   只有原整理范围的每个必要 item 都有精确 source/pin/合法关联的真实成功证据，才显示整体
   “已完成（恢复成功）”；保留已接受的主文件成功/附件告警语义和告警事实。不能从一个兄弟、
   最新子任务总数、单次 analysis 或 consumed 标记推断全部完成。
   忽略/跳过可按允许的真实处置结束问题，但不等于整理成功；混合技术失败/未知效果不能被
   恢复成功掩盖。显示层投影不改写原 Task/Result，不重复计算同一显式关联工作，不按同名
   来源把独立 run 自由合并，更不能重跑成功项或给不确定效果新增执行权。

5. **一次接通 API 契约与八视图界面。**
   更新中心的 typed DTO/normalizer/view/problem/summary/query state，保持 malformed/401/403/
   not-found/read-error 的真实处理。明确区分“中心四类问题”与仍支持的管理恢复类型，不能
   为删中心 failure 就删除共享 API/CLI recovery engine、普通操作允许的恢复或历史 failure 字段。
   中心不再有 Failure Recovery 导航、筛选、专属统计/问题数、失败文件恢复面板和通用
   修复/重试/核查指导。All/Ended 可按失败状态找记录，详情保留原因、阶段、已完成/不确定
   效果、结果、日志和导出；每项事实数量仍保留，不改成成功或从历史消失。
   移除全局 Worker/resident 区块及仅服务它们的 query/poll/refetch/loading/error 依赖；
   不删除其他页面仍用的组件。任务本身固定上下文、就绪和失败事实继续可读，中心可在
   Worker 缺失时查看排队/历史；没有替代监控页，也不恢复创建/手动/发现区块。

6. **封住旧 V2 入口，保留已授权消费者。**
   核对现有 Task/Job 列表、detail、旧 failure URL/search、Dashboard/Shell、Automation 与
   返回上下文。旧列表不能显示混合总体；整理深链到精确整理上下文，普通操作用持久 origin
   回原 kind/library/source 的本地查看。原库已停用/删除、来源上下文缺失或权限不足时，给出
   有界不可用/权限状态，不猜当前库、不降级到通用失败恢复，也不提交任何命令。
   旧 failure 深链只能到精确只读历史或普通不可用，不能恢复第五页或映射成假 Metadata。
   仅在合法范围内保留筛选/页/选中项，拒绝不匹配游标；401 重连不重放操作，跨 principal
   不复用私有缓存/返回线索。共享管理 API/CLI、Automation 记录/统计、Files 本地查看仍按其
   合法范围工作；不因中心收缩删除数据、禁用后端恢复或改变自动化执行意图。

7. **用真实入口验证并更新实现事实。**
   扩展现有 mixed-history、typed recovery、Files 与 real-Python browser fixtures，不另造
   过程框架。新增状态由已有支持的命令/API/Worker/允许的决定产生；故障注入只延迟/失败实际
   adapter/persistence。仓储单测可构造合法持久形状，但不能用手填成功、伪造 claim 或 DOM
   修改代替用户旅程证明。新增字段/schema 必须解释必要性并证明 fresh/upgrade/reopen/
   failure atomicity；优先复用现有证据。更新受影响 CURRENT 架构/查询/界面实现事实，RO-5
   继续标 TARGET；不改 A-owned Slice/Roadmap/Progress 边界或自行关闭 Slice。

## Acceptance Criteria

- [ ] 混合历史超过多页、普通/通知/未知记录较新或夹在中间时，八视图、统计、来源选项、
  搜索、双向分页及 exact-ID 各读取均只包含受权整理总体。pre-Task 整理 Job 排队/失败仍可见，
  Job 绑定 Task 前后 identity/count 不漂移；独立分析不混入，已受理整理的分析阶段不被隐藏。
- [ ] 普通操作不从 `all`、filter/cursor、selected run 或旧 Task/Job 列表/深链泄入中心。
  精确来源可证明时回到正确 kind/library 的本地查看；失效/拒绝上下文只读且不猜库、不执行。
  共享 API/CLI、Automation records/metrics 与本地普通操作未被全局裁剪或删除。
- [ ] 页面恰好八个兄弟视图，移除失败恢复及全局 Worker/resident/已移除的手动与发现区块。
  初始进入、刷新、轮询和重连不请求这些区块的独占读取；任务级诊断和空/加载/读错状态可用。
- [ ] Attention 和每一个待处理任务 badge/card/count 是当前四类问题的 distinct union。
  同一任务有多个问题不重复算任务；任务数/文件数不同，多页/过滤/刷新/重开后与文件列表一致。
  pre-Task 技术失败、Provider outage、权限/Storage/配置错误、partial/uncertain 不形成第五类。
- [ ] 四类决定 → 分析 → 精确摘要 → 明确确认 → 真实结果仍 Web 可完成；必要人工步骤可达，
  后台自动处理不虚增人工待办。普通初次确认留在进行中/全部，不进入 Attention 或已结束。
- [ ] 决定保存/analysis/skip/ignore 不被当作恢复成功；新业务阻塞正确换类型；纯技术 follow-up
  失败清掉过时四类责任，但不显示 Completed。混合成功/忽略/业务问题/技术失败/未知效果保留
  独立真相。所有必要项精确关联的真实成功才显示整体恢复完成，旧失败尝试仍在，恢复不双算。
- [ ] 无失败恢复专属统计、通用技术修复/重试/核查入口或旧链接旁门；All/Ended 的真实失败/
  部分/不确定历史、阶段、效果、日志、结果和导出仍完整可读。四类问题旁有不确定效果时，
  仍可查看合法决定但绝不新增执行/重放权；成功兄弟不重跑。
- [ ] 查询/统计一致读快照、principal/population/filter-bound cursor、bounded evidence、历史
  pins/来源隔离和红化不退化；读页面、翻页、刷新、返回、下载读取和401重连无新工作/媒体效果。
  两条 SQLite 连接更新问题/恢复关系时，页与计数不相互矛盾；API/仓库重开保留同一事实。
- [ ] 实际 1536×1024 与390×844下八视图、键盘焦点、详情返回、四类表单/确认及只读技术历史
  可用；401/403/not-found/malformed/read-error 不成为空或成功，也不恢复旧创建/失败页。

## Required Tests

遵循 [workflow §6](docs/development-workflow.md#6-test-levels)：Developer 跑新增/修改/直接受影响
测试；B 负责完整回归和验收。所有测试使用临时库/测试根、fake/local provider，不用用户媒体/
私有配置。先复现当前任务要改的真实结果；本轮测试/构建/探测的重叠墙钟时间须严格少于工作
时间的50%，不故意等待、不扩大 full 矩阵、不放宽断言/超时、不靠 skip/retry 变绿。

### Developer — affected tests

从仓库根目录，按本 Task 实际修改扩展这些现有直接受影响套件：

```bash
python3 scripts/check_governance.py
git diff --check
.venv/bin/python -m unittest tests.test_operations_run_inventory tests.test_operations_task_center tests.test_operations_run_detail tests.test_operations_run_detail_plan_evidence tests.test_operations_run_detail_log_isolation
.venv/bin/python -m unittest tests.test_task_center_recovery_lineage tests.test_recovery_continuation tests.test_recovery_batch
.venv/bin/python -m unittest tests.test_library_file_operation_history tests.test_operations_workspace tests.test_v2_automation_operations tests.test_api_security
```

覆盖重点：混合总体与所有读取旁门、Job→Task 去重、跨页计数/来源/游标/事务快照、四类 union、
初次确认与恢复确认区别、逐项精确恢复成功/新阻塞/纯技术失败、只读历史和共享消费者不退化。
普通操作实际 producers 或 scope/recovery engine 若改动，补跑对应直接套件；没有改动时不
机械扩展全部 Automation/Files/配置测试。新专用测试模块必须明确列出实际命令并跑到用例。
Python changed-file 检查只针对实际修改文件：`ruff check`、`ruff format --check`。

从 `web/`，扩展并运行当前相关 unit/contract tests（新增文件需一并列出）：

```bash
npm run test -- run src/entities/operations/run.test.ts src/entities/operations/run-detail.test.ts src/features/operations/OperationsInventory.test.tsx src/features/operations/OperationsRouter.test.tsx src/features/operations/RunDetailTabs.test.tsx src/features/operations/TaskItemRecoveryPanel.test.tsx src/features/operations/RunLifecycleControls.test.tsx src/features/operations/run-query.test.ts src/features/operations/run-detail-query.test.ts src/shared/navigation/operations-return.test.ts src/features/dashboard/DashboardPage.test.tsx src/features/library/LibraryFileOperationsDialog.test.tsx
npm run typecheck
```

保留 malformed/denied、权限、无重放和精确确认断言，把旧九视图/混合总体/第五类“应当存在”
改为新合同的正反断言；不能只删掉失败用例。对 changed Web files 跑 ESLint/Prettier 检查。
构建当前生产资产后，两个直接相关 real-Python spec **各自启动一个干净 harness**：

```bash
npm run build
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-task-center-visual.python.spec.ts
```

扩展现有 fixture 的真实整理/普通/通知历史及四类链，覆盖八视图、移除的入口/请求、技术历史、
来源/返回、刷新/restart、实际1536×1024/390×844。保留已存在380×720覆盖。Node-fake 不能替代
真实 Python population/recovery/persistence 证明。Developer 不跑全量 Python/Web/default E2E、
包装或 Docker 矩阵；受影响测试完成即可提交 READY FOR B REVIEW。

### B — acceptance and full regression

B 独立审查整个 Task Base..候选，核对所有原始 RO-4 结果及全部 Slice outcomes。先沿上述
真实入口完成 critical reproduction，再跑适用 [shared full T4 gates](docs/development-workflow.md#shared-full-regression-commands)：
全量 Python/Web/static/default E2E、当前生产资产的原生八视图/四类恢复/只读技术历史、
wheel/installed-consumer、RBAC/redaction/pins/non-replay 与必要的发布安全证明。

B 特别验证：大于一页且全局当前页主要是普通工作的历史；后端统计/列表快照竞争；保存决定、
排队分析、摘要确认、全成功恢复、只恢复部分、忽略、技术失败与未知效果的完整变化；source/pin
或 lineage 不匹配的成功记录不得关闭另一个问题。通过真正 Worker 结果和 SQLite/API 重开证明，
不能只查前端标签。实际读取计数证明移除区块不再产生独占请求，且无 Storage/Provider/命令效果。

若实现只调整 read model/呈现，常驻 Worker 行为不作新改造；B 根据实际 diff 执行适用 packaged/
restart/security 门禁。schema、runtime pin、Worker 消费或授权发生变化时，补当前升级/失败
原子性、已安装消费者和常驻重启证明；不得用旧候选的 native 结果冒充新 backend。严格满足
输入/资产身份相同的 B 既有结果可按 workflow 复用，并记录原始证据与已证实的相同范围。

### Known baseline limits to preserve

Task46.3 在 `44cba4f9:TASK.md` PASS（reviewed Head `9fe6038`，production `8280219e`）。
其源身份/占用、早期 admission、Files readback 和确认/执行不在本 Task 重写。
Task46.2 普通文件原生回归的三项既有菜单/non-localhost失败仍保留，不得顺手修、删证据或
标成已解决；若本 Task 的本地深链衔接引入真实回归，必须在本 Task 修复。
两个 native spec 合并一次调用的既有共享 fixture 顺序限制已记录，以上采用各自干净启动，
不改断言、不隐藏用例。全量/环境/必要验收问题继续由 B 负责，不转交 Developer。

## Non-goals

- RO-5 的 Automation detail/Save/Enabled/grant移除/Run once执行意图、稳定性或调度行为改造；
  本轮仅保持既有记录/链接/授权消费者可用，不能提前把 enabled 当新执行授权。
- 重做已验收 Task46.1–46.3、来源占用/扫描/执行/恢复引擎、全局来源目录、队列/Worker监督、
  无关普通文件菜单问题、历史清理或更大的重构。必要只读证据投影不产生新生命周期/执行权。
- 新命令/providers、MediaLibrary整理、跨Task批量修改、任意历史重处理、自动不确定重放/
  回滚、Upload/Download、Scan/独立Preview/FileIndex恢复、身份系统/主题/全局页面重设计。
- A-owned Slice/Roadmap/Progress边界及最终关闭、下一Task计划。Task PASS后由B重评全部结果；
  不把本Task PASS写成整个Slice完成。

## Workspace and planning validation

规划基于 `main` / Task Base above，已提交 Slice46 为 ACTIVE。启动时没有 tracked dirty files；
既有 `.DS_Store`、日志/测试日志、`15`、docs/pics 的 Automation 参考图片及
`output/imagegen/slice45-task-center-v1.zip` 等 untracked/private/reference 文件完整保留并排除。
本规划只改 `TASK.md`，不修改产品、治理脚本或 A-owned 文档，不 push。

规划检查：`python3 scripts/check_governance.py` PASS；`git diff --check` clean。仅阅读实际代码与
合同并执行文档/治理检查，没有产品测试、构建、浏览器探测或媒体操作；检查时间低于本轮50%。
Task46.3 的完整计划/交付/复核在 Git 保留，其终结 PASS 不被本 Task 的 PLANNED 状态覆盖。

## Developer Completion Report

```text
Task: 46.4 / High / T4
Task Base: 44cba4f93b94b72d6dee52fcd1199be729ec78c4
Status: READY FOR B REVIEW
Slice: ACTIVE (this is not A Final Review, PASS or closure)
Push: none performed
```

本轮实现 RO-4 的整理专用总体、八视图、四类真实问题与只读技术历史。RO-1/2/3/5 未改动。

### 实际变化

- `mediaflow/domain/operations_run.py`：`OperationsRunView` 由九视图改为八视图、删除 `failure`
  视图与问题类型；新增共享、可测试的总体归属规则
  （`ORGANIZING_TASK_COMMAND_FAMILIES`/`ORGANIZING_JOB_COMMAND_FAMILIES`/
  `ORGANIZING_TASK_LINEAGE_RELATIONS` 与 `is_organizing_*_command`）。`attention_reason`
  只剩 `task_problem`。
- `mediaflow/infrastructure/sqlite_runtime.py`：总体归属下推到 `_RUN_QUERY_SELECT` 的三个
  分支（Job 命令家族、Task 命令家族 + `media_discoveries.organize_task_id` + 持久续作关系、
  仅有 definition origin 的 Run once 准备行），因此列表、过滤总数、状态分区、attention、
  summary、source options、游标窗口、exact-ID detail/items/records/export 全部共用同一总体。
  删除 `failure` 问题谓词与失败统计列；`_problem_item_predicate` 只保留四类业务问题，并让
  “已保存决定待显式继续”仍属原类型（不新增第五类、不误判为技术失败）。attention 即四类
  distinct union；`run_level_repair` 只保留为只读事实字段，不进入 attention/统计。
- `mediaflow/interfaces/service_api.py`：拒绝退役的 `view=failure`/`problem=failure`；
  exact-ID 中心读经 `is_task_center_run` 限定；Automation 记录 handoff 继续使用冻结的
  pre-start 失败事实（不与中心失败统计混淆）。
- `web/src/entities/operations/run.ts`、`OperationsLanding.tsx`、`ProblemFilePanel.tsx`：
  八视图、四问题类型；`attention` 与 `problem_types` 双向一致才接受；移除全局 Worker/
  常驻服务区块及其独占 readiness 读取、失败视图标签、“运行级修复”链接与通用失败文件入口。
- 既有普通文件工作（复制/移动/删除/维护）现在只在其原库的 file-operations/operations
  读取上呈现；中心精确 ID 读取对它们是 404（RO-3 已验收的本地入口不变）。

### 受影响命令与结果（本轮实际执行）

| 命令 | 结果 |
| --- | --- |
| `python3 scripts/check_governance.py` | PASS |
| `git diff --check` | clean |
| `.venv/bin/python -m unittest tests.test_operations_run_inventory tests.test_operations_task_center tests.test_operations_run_detail tests.test_operations_run_detail_plan_evidence tests.test_operations_run_detail_log_isolation tests.test_task_center_recovery_lineage tests.test_recovery_continuation tests.test_recovery_batch tests.test_library_file_operation_history tests.test_operations_workspace tests.test_v2_automation_operations tests.test_api_security tests.test_automation_workspace_read_model tests.test_direct_file_operations tests.test_direct_file_transfers` | **534 OK** |
| `.venv/bin/python -m unittest discover -s tests` | **2890 OK, 7 skipped** |
| `.venv/bin/ruff check mediaflow tests scripts` / `ruff format --check` | PASS / 358 files formatted |
| `.venv/bin/python -m compileall -q mediaflow tests scripts`, `pip check` | PASS / no broken requirements |
| 两个 example 配置 `config validate`；FFprobe/FFmpeg 依赖扫描 | PASS；无匹配（exit 1） |
| `web`: `npm run typecheck` / `lint` / `format:check` | PASS / PASS / PASS |
| `web`: `npm run test -- run` | **87 files / 1265 tests OK** |
| `web`: `npm run test:e2e -- --config=playwright.config.ts`（Node fake） | **242 passed** |
| `web`: `npm run build` 后 `npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-task-center-visual.python.spec.ts`（独立干净 harness） | **2 passed**；截图 1536×1024、380×720、390×844 |
| 同上独立干净 harness：`tests/e2e/operations-inventory.python.spec.ts` | **41 passed**（含八视图/四类原生恢复/技术只读历史/刷新与真实 restart） |
| `.venv/bin/python -m pip wheel` + `scripts/wheel_smoke_test.py <wheel>` | PASS（安装消费者加载 recovery 模块） |

浏览器探测均使用 harness 临时 SQLite/媒体根与本地合成 Provider，不使用用户媒体或私有配置。
截图人工检查：桌面 1536×1024 八标签同排、无 Worker/失败恢复、问题文件清单与统计一致；窄屏
380×720 与 390×844 标签可横向滚动、聚焦可滚动到末项。E2E 与构建/探测占本轮工作墙钟时间
明显低于 50%。

### 已知失败与风险

- 本 Task 未改变 Storage/Worker/Scheduler 执行引擎；manifest 只读，新增无 schema 变更。
- `media_discoveries` 中**仅有** `organize_task_id` 的 Files 受理由其 Task 行代表；analysis-only
  准备（无 definition origin、无组织 Task）不再计入中心——这是 RO-4 的既定收缩，非回归。
- 原库本地 readback（`/resource-libraries/{id}/file-operations`）保留既有契约，仍回显其原始
  scope；本轮未改动它，也不在该路径上声称新增 redaction 行为。
- 一处 E2E 计数从“分析+执行 2 行”改为“1 行”是 RO-4 的直接结果（此前分析准备被计入中心）。
- 既有 Task46.2 三项 direct-files 菜单/非 localhost 失败不在本 Task 范围，未修、未跳过、未标绿。
- 未做全量 Docker/发布安全门禁（按分工属 B）。

### 剩余 in-Slice 工作

RO-5（Automation detail/Save/Enabled/grant 移除与真实 Run once 执行意图）仍未实现；中心
八视图/四类恢复的最终 A 关闭与文档对账同样未开始。

### 交付身份

- Implementation Head: `9241bd5158e5e1576dc4e403520ede1fdc49e0a5`
- Range: `44cba4f93b94b72d6dee52fcd1199be729ec78c4..9241bd5158e5e1576dc4e403520ede1fdc49e0a5`
  （23 files：4 production modules、1 harness、10 Python suites、4 Web modules、4 Web
  tests，外加本 `TASK.md`）。
- Working tree 无 tracked dirty；既有 untracked 日志/参考图/OS 文件保持未暂存。

## B Review Result

```text
Reviewed: 44cba4f93b94b72d6dee52fcd1199be729ec78c4..cb1327a934b7edbcec5b5fb07f26fc7f1a198e74
Implementation candidate: 9241bd5158e5e1576dc4e403520ede1fdc49e0a5
Decision: FIX REQUIRED — 2026-10-27 / B
Acceptance runs: critical API/SQLite/Worker/CLI and real-Python browser reproduction; see below
Task blockers: B46.4-01–05 (P1, required RO-4 outcomes)
Slice Required Outcomes / Surfaces all satisfied: NO
Next: SAME TASK FIX LOOP — preserve Task ID/Base/Goal/Scope
```

### Required corrections

1. **B46.4-01 — 四类恢复在必要人工步骤结束前不能消失。**
   真实 Recognition 决定 → continue → Worker 分析完成后，原任务和分析子任务都发布
   `attention=false, problem_types=[]`；生成仍需人工确认的摘要后仍如此。Conflict 决定
   刚保存就消失：`_saved_decision_continuation_sql()` 的 stage 集合遗漏 `conflict_resolved`。
   在共享当前问题投影中沿精确 item/continuation/preparation 保留原四类责任：保存后待分析、
   分析完成待生成摘要、摘要待确认都可从对应类型恢复；自动排队/执行无需人工时不虚增待办。
   新业务阻塞转类型，纯技术失败退出四类，实际完成/合法忽略才结束相应责任。不要只补一个
   stage 或前端 badge。用当前原生四类链验证各停点、刷新和重开，类型文件列表/计数一致。

2. **B46.4-02 — 全部真实成功后必须有整体恢复完成投影。**
   单项 Recognition 和 Conflict 经原生决定、分析、精确确认、真实 Worker 移动成功，来源
   已不存在、执行 completed、旧 Results 未改，但原任务在 SQLite/API 重开后仍为 `failed`。
   `_run_query_document()` 的 `derived_status` 仅回显旧 attempt 状态，没有所需的整体恢复状态。
   复用逐项 exact source/pin/lineage/effect 证据，统一列表/状态筛选/统计/详情的整体
   Completed/recovered 显示；原失败尝试和 Results 保持原样。覆盖全部成功及只恢复部分、
   忽略/跳过、技术失败、未知效果和不匹配 source/pin 的反例，禁止最新子任务成功替代全覆盖。

3. **B46.4-03 — 技术失败详情仍能启动通用恢复。**
   从中心“全部任务”搜索真实 technical 失败 → 详情 → 查看证据，仍看到且可用
   “继续此条目的安全分析”。`RunDetailTabs` 无条件挂载 `TaskItemRecoveryPanel`，其 generic
   retry、批量失败分析及 checkpoint 下一步指导没有按本 Contract 收缩。将中心的技术失败
   展示限定为原因/阶段/已完成和不确定效果/结果/日志/导出；关闭通用修复/重试/核查指导及
   操作旁门，包含旧 Task/Job/detail 深链。四类合法恢复及其必要后续仍可完成，管理 API/CLI
   和普通文件本地允许的恢复仍保留。修正现有 technical E2E 中“只读”却继续点击分析的断言，
   不把迁移入口当成移除行为的证明。

4. **B46.4-04 — 旧 V2 Tasks/Jobs 仍绕过中心总体。**
   用现有 `POST /api/v1/resource-libraries/source/files/commands` 创建目录，再打开已存在的
   `/ui-v2/operations/tasks`，真实 `files_direct_command` Task 仍在混合列表。旧 Task/Job 页面
   继续读原管理 collection，不能用 runs exact-ID 返回404代替封闭这些入口。旧 V2 列表接入
   整理总体或转到中心；整理 detail 到精确上下文，普通操作用持久 origin 回原 kind/library
   的本地查看；缺失/停用/删除/权限拒绝时有界不可用，不猜库、不执行。保留管理 API/CLI
   的合法混合查询；覆盖 Tasks、Jobs 和 detail 的实际路由、分页、401/403、重连和返回。

5. **B46.4-05 — 普通独立 organize DryRun 仍被当整理任务。**
   调用已有 CLI `organize <临时库内文件>`，不带 `--execute`，实际得到 DRY_RUN、零移动和
   `execute_authorized=false`，但中心 exact-ID 返回200并计为 completed 整理。生产 CLI
   `final_cli.py` 明确将此形状作为 analysis-only；当前 `_organizing_population_sql()` 只按
   `organize` family 或任一 continuation link 纳入，未判真实意图及来源。补齐所有现有
   producers 的执行意图/已受理 Files Task/合法整理 lineage 判定，独立分析及其分析续作
   排除于所有中心读取/统计/游标；Task/Result 本身仍保留。不可简单全局要求 execute=true：
   已受理 Files 的分析阶段和合法四类恢复分析仍应纳入。用真实 CLI 分析与对应 execute、
   Files admission、独立与整理来源的 continuation 证明正反边界。

按以上修复整个既定 RO-4，不新建 Task，不改 RO-5 意图/执行引擎或 A-owned 边界。
同步受影响的架构/查询/界面实现事实，保留其余 TARGET 和已接受历史。Developer 运行新增失败
用例与直接受影响测试后提交新的 READY FOR B REVIEW checkpoint；B 在修正候选上完成原 T4
验收，不能复用本轮 Developer 的全量 PASS 标签代替 B 验收。

### B evidence and test boundary

复核入口为既有 CLI、产品 API、现有 harness/原生页面；仅使用临时 SQLite/媒体根与现有
synthetic Provider。审查范围覆盖上述完整 Base..Head 的23文件 manifest及其现有调用链。
本地原始证据：`.git/validation-evidence/cb1327a/b-review-20261027/`（未提交、不可声称远程可达）。

| B 本轮命令 / 证据 | 实际结果 |
| --- | --- |
| `python3 scripts/check_governance.py` | PASS（开始及复核文档完成后） |
| `.venv/bin/python .git/validation-evidence/cb1327a/b-review-20261027/reproduce.py` | exit 1；5项合同断言均失败：识别摘要待确认、Conflict Save待办、两条全成功恢复状态、CLI独立分析总体；`reproduce.json` 保存 API/Worker/重开事实，最后运行约0.5秒 |
| `web/`: `npm run build` | PASS；`build.log`，`production-assets.json` 保存当前资产SHA256 |
| `web/`: `npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/b46-4-review.tmp.spec.ts` | **2 failed**：technical history generic continuation、legacy V2 mixed population；浏览器用时分别956ms/422ms，`browser.log`及trace/截图保留 |
| `git diff --check` | clean |

上述临时 browser spec 仅用于独立复现，已移至证据目录 `browser.spec.ts`，从工作树移除；没有
改动产品/既有测试、断言、timeout、retry或skip。Python证据脚本用真实 API/Worker 执行，
不手填成功或伪造 claim；CLI仅将 Provider 工厂替换为同一fixture的 synthetic registry。
不支持的 remote `execute=false` 已返回400，是拒绝证据，不作为任何缺陷依据。

已确认 P1，按 workflow §6 在昂贵门禁前给出 FIX REQUIRED。本轮未跑完整 Python/Web/default
E2E、wheel/Docker/发布安全矩阵；Developer报告的全量结果仍属其交付事实，没有转换为B验收。
测试/构建/探测累计保守上界小于30秒；仅已记录的08:50:05–08:54:50 UTC工作区间即285秒，
占比小于11%（完整本轮更长），满足本轮严格小于50%，未靠等待扩大分母。

### All Slice outcomes reevaluated after review

| Outcome | 当前结论 |
| --- | --- |
| RO-1 | Task46.1既有验收保留；本候选未改样式实现，不宣称重跑全视觉验收 |
| RO-2 | Task46.3已验收的Files先受理/来源占用/初次确认基础保留；四类恢复呈现受B46.4-01影响，仍由本Task修复 |
| RO-3 | 原库本地持久查看基础保留；旧中心列表旁门由B46.4-04修复，不重开普通菜单问题 |
| RO-4 | **未完成**：B46.4-01–05；八标签和移除全局区块不等于完整交付 |
| RO-5 | **未完成**：Automation detail/Save/Enabled/Run once意图和稳定性结果仍待后续；本Task不提前实现 |

不规划下一Task，不提交Closure Packet，不更改Slice/Roadmap/Progress，不关闭Slice。
分支仍为`main`；所有启动时untracked日志、参考图、OS文件和私有文件保留且未暂存；不push。
