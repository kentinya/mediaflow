# NO ACTIVE IMPLEMENTATION TASK

Task46.4 **PASS**，被审候选 `3b101d55fd52fed511ed8a262f636085edb0b32f`。
Slice46仍ACTIVE，RO-5待下一Task规划；以下保留本Task计划和验收记录，不授权新实施。
终态采用现有governance guard支持的无活动Task通知格式，未为状态表示改造过程工具。

## Task 46.4 — 只管整理的任务中心与真实四类恢复状态

Authority: committed [Slice46](SLICE.md) **RO-4**、AC-5/6/7/8/14/15，以及保持 RO-2/RO-3
已验收入口与确认语义所需的衔接；[Development Workflow](docs/development-workflow.md)。
实施前阅读 [Developer experience](docs/agent-experience/developer-implementation-role.md)。

```text
Task ID: 46.4
Parent Slice: 46
Status: PASS
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

## Developer Completion Report (fix round for B46.4-02)

```text
Task: 46.4 / High / T4
Task Base: 44cba4f93b94b72d6dee52fcd1199be729ec78c4
Fix base (B review checkpoint): d63dd7105177f492c287c99412b90e22f19380cf
Implementation Head: 7655377204772aaba6fbec1ad4040005bbe28140
Status: READY FOR B REVIEW
Slice: ACTIVE (this is not A Final Review, PASS or closure)
Push: none performed
```

本轮只修 B46.4-02 的 P1，保留 Task ID/Base/Goal/Scope；不新建 Task、不改 RO-5 意图/执行
引擎、不改 RO-1/2/3 已验收入口，也不自行 PASS。此前报告与 B 复核结论保留在 Git 历史。

### 根因与本轮更正

`sqlite_runtime.py::_run_query_document()` 的 `recovered_success` 只在
`failed/partial/pending/processing/paused` 项上取证，`ignored`（以及 `skipped`、`cancelled`）
因不在检查集合里被直接跳过；只要存在 confirmed preparation，别的项的真实成功即可把整个 run
投影成 `completed` + `recovered_completion=true`。原 Task/Result 未被改写，但列表/统计/详情/
“已完成（恢复成功）”文案因此与逐项事实相反。

- 新增共享 `SQLiteTaskRepository._verified_own_effect_sql(item_alias)`：该项自身 Task 的
  **最新** Result 必须是 `success`、`effect_certainty` 非 `attempted_unverified/unknown`、
  `uncertain_effects='[]'`；较早的成功被后来的失败/不确定结果取代即不算成功，无 Result 也不算。
- `recovered_success` 不再按 status 白名单排除项，而是枚举原整理范围的**全部必要主项**
  （既有附件扩展名过滤保持不变），要求每一项都有“自身最新真实成功”或“exact source/pin/
  lineage 的已核实成功 follow-up”。忽略/跳过/取消/待处理/失败/部分/不确定都是“无成功证据”，
  会阻止整体完成投影；同一结果同时驱动 `derived_status`、状态分区、统计、详情与文案（同一
  read snapshot）。既有“任务本身 failed/partial_success + 无 pending 四类 review + 存在
  confirmed preparation”门槛不变。
- 只读投影；无 schema、Worker、Scheduler、OrganizerExecutor、admission/authority 变更，
  不授予执行/重放权，不重跑成功或不确定项，不改写原 Task/Result/决定/audit。
- `docs/architecture.md` CURRENT 事实补充该逐项证据规则（Task46.4 合同内的事实澄清）。

### 新增真实链路回归（`tests/test_task_center_recovery_lineage.py`，12 用例）

- **mixed ignored + 实际恢复成功**（B 原负例同形）：真实双项 Manual admission + 产品
  `MetadataReviewService` 决定 + ignore admission + 真实 Worker 分析/整理。重开前后 API 都是
  `status=failed`、`recovered_completion=false`，列表/状态分区/`view=ended` 一致，统计无
  attention/问题计数，`dispositions.ignored=1` 且 `success=0`，被忽略文件仍在源处、成功兄弟
  已移动到目标，旧 Results 不变，确认后无第二次执行被受理（不重放）。
- **skip**：真实 destination 冲突由产品 `ConfirmationService` 写入、`skip` 由产品决定 API 应用；
  同 run 的另一项真实恢复成功后仍 `failed`/`false`，skip 项与既有目标字节都不变，且逐项证据
  为“一项有 verified follow-up、skip 项没有”。
- **只恢复部分 → 全项恢复 → 证据失效**：两项分别真实恢复，之前 `false`、之后 `completed`+
  `true`（重开后同）；随后把其中一项原 source_path 改成不匹配值，逐项 follow-up 证据与整体
  投影同时回落到 `failed`/`false`，恢复后再次成立。
- **单项全成功正例**：干净单项任务（Metadata）恢复后详情/列表/分区为 `completed`+`true`。
- **技术/未知效果负例**：既有 mixed technical fixture（未知效果 sibling、无 Result 的成功
  sibling）与 follow-up 预变更失败都保持 `partial_success`+`false`，源文件未被改动。
- `OperationsInventory.test.tsx` 新增投影契约用例：`recovered_completion=false`+`failed` 的行
  显示“失败”、无“已完成（恢复成功）”与“每个必要条目…”文案；`true`+`completed` 的行与详情
  显示该文案与说明。

### 实际命令与结果

| 命令 | 结果 |
| --- | --- |
| `python3 scripts/check_governance.py` | PASS（开始与提交前） |
| `git diff --check` | clean |
| `.venv/bin/python .git/validation-evidence/d63dd710/b-review-20261028/mixed-reproduction.py` | **exit 0**；B 原三项 contractChecks 全 true（ignored 仍在源处、兄弟真实整理、`mixedIgnoreIsNotAllSuccess=true`），旧 Results unchanged |
| `.venv/bin/python -m unittest tests.test_operations_run_inventory tests.test_operations_task_center tests.test_operations_run_detail tests.test_operations_run_detail_plan_evidence tests.test_operations_run_detail_log_isolation tests.test_task_center_recovery_lineage tests.test_recovery_continuation tests.test_recovery_batch tests.test_processing_recovery_admission tests.test_library_file_operation_history tests.test_operations_workspace tests.test_v2_automation_operations tests.test_api_security tests.test_manual_ignore tests.test_manual_ignore_batch tests.test_manual_operations_contract` | **374 tests OK / 54.2s** |
| 同上单跑 `tests.test_task_center_recovery_lineage` | **12 tests OK / 4.1s**（SQLite ResourceWarning 与既有套件一致，属既有噪声） |
| `.venv/bin/ruff check mediaflow tests scripts` / `ruff format --check` | PASS / 358 files formatted |
| `web`: `npm run test -- run`（12 个受影响文件，含 `OperationsInventory`、`run`、`RunDetailTabs`、`TaskItemRecoveryPanel`） | **191 tests OK / 10.7s** |
| `web`: `npm run typecheck` / `npm run lint` / `npm run format:check` | PASS / PASS / PASS |
| `web`: `npm run build` | PASS（当前生产资产 `index-DwbDDOhM.js`） |
| `web`: `npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts` | **40 passed / 1.3m**（各自干净 harness） |
| 同上独立干净 harness：`operations-task-center-visual.python.spec.ts` | **2 passed / 9.2s** |

所有浏览器/后端探测只用 harness 临时 SQLite/媒体根与合成 Provider；故障注入只作用于既有
adapter/fixture seam。未用用户配置/数据库/媒体，未手填成功/伪造 claim/改 DOM；既有产品或测试
断言、timeout、retry、skip 未放宽。

### 已知风险与剩余工作

- 投影是严格“逐项已验证成功”：仅 status=success 但没有 Result 行（或最新 Result 不是已验证
  成功）的项不再算成功证据，因此这类旧/异常记录所在 run 不会显示恢复完成。这与产品既有
  `confirmed_success`（要求 Result 证据）一致，属保守方向；未回填/改写任何历史行。
- ignored/skipped 项会让该 run 永久停在 `failed`/`partial_success`（忽略/跳过按合同不算整理
  成功），逐项处置仍完整可读；这是本轮要求的行为而不是缺陷。
- 无 schema/Worker/执行语义变更；`recovered_completion` 仍是只读投影，不新增执行权。
- 未跑全量 Python `discover`、默认 E2E、wheel/installed-consumer、Docker/发布安全矩阵与 B 的
  完整 T4；按分工属 B。RO-5 与 Slice 最终关闭/文档对账仍未开始。

### 交付身份

- Implementation Head: `76553772`（4 files：`sqlite_runtime.py` 查询投影、lineage/Web 回归、
  architecture CURRENT 事实）
- Fix range: `d63dd7105177f492c287c99412b90e22f19380cf..76553772`
- 本报告在独立 docs checkpoint 提交；Working tree 无 tracked dirty，既有 untracked 日志/
  参考图/OS/private 文件保持未暂存。


## User-authorized test reconciliation — 2026-10-28

用户在前轮 B 的两处测试阻塞后明确要求“你自己处理一下吧”。据此由 B 亲自完成本次 **test-only**
适配；这是已披露的角色例外。产品实现仍为 `7655377204772aaba6fbec1ad4040005bbe28140`，
不把 B 自己修改的测试称为另一位 Developer 的独立交付，不改授权或生产执行逻辑。

Test checkpoint: `3b101d55fd52fed511ed8a262f636085edb0b32f`。

- 第一项保留 analysis-only 的两跳真实 Worker、相对范围、快照、预算、结果和媒体零变更检查；
  断言两份分析续作不进入整理中心，数据库重开后仍保留各自管理记录和结果。
- 第二项复用已有原生 harness 的已受理 definition occurrence / live scoped grant / Active；
  用现有 resume API 和真实 Worker 消费，验证只有剩余文件进入子任务、原任务不变、原预算/
  快照保持；原任务的完成续作投影和子任务均在数据库重开前后可查，保留有界脱敏检查。
- 两份完整 suite 及 inventory/task-center/recovery-lineage 直接回归：**212 tests / OK / 20.144s**。
  changed-file ruff/format、governance 和完整范围 diff whitespace 均通过。未新增 skip/retry、
  未放宽 timeout、未修改 harness/产品或删除范围/安全断言。
- 本人适配时两次错误断言（把继承的原预算误写为 1、把既有 snake_case API 字段误写为
  camelCase）已按实际合同修正；初次失败日志保留，不归因于产品回归。

本轮原始日志：`.git/validation-evidence/b40f58c6/test-reconciliation-20261028/`。
`execution-inputs.json` 证明相对前轮 B 候选只改上述两份测试及 TASK；四份构建资产 SHA256
逐项相同。原有 untracked/private/参考图完整保留，无 push。

## B Review Result

```text
Reviewed: 44cba4f93b94b72d6dee52fcd1199be729ec78c4..3b101d55fd52fed511ed8a262f636085edb0b32f
Product implementation: 7655377204772aaba6fbec1ad4040005bbe28140 (unchanged)
Test reconciliation: 3b101d55fd52fed511ed8a262f636085edb0b32f
Decision: PASS — 2026-10-28 / B
Slice Required Outcomes / Surfaces all satisfied: NO — RO-5 remains
Next: NEXT TASK — RO-5 remains; no active implementation or Slice closure
```

本轮完整范围是原 Task Base..精确候选，共48个文件。上一轮B对全部产品变更的独立审查、
5项原始复现、mixed ignored负例及原生结果保留于 `b40f58c6:TASK.md`；从其被审候选到
本轮候选，实际只变 TASK 和两份测试。B补审两份测试完整diff，未把真实整理续作遗漏改成
合理排除：analysis-only 的负向归属和 live-authorized organize 的正向归属现均有真实
Worker、持久记录及重开证明。B亲自改测试的用户授权例外见上节；无另一人独立审查的虚称。

### Acceptance and user behavior

- 原五个产品问题复现通过。保存决定、排队分析、摘要或受理都不冒充恢复成功；必要人工
  决定/确认保留四类责任。真实逐项成功才完成，失败尝试/Results不改写。
- mixed ignored+verified-success仍保持failed及非recovered_completion；skip/technical/
  unknown、source/pin失配、最新Result及partial→all-success由直接回归和全量Python覆盖。
- 整理总体先统一再统计/分页/精确读取；合法整理及其续作可见，普通文件操作和纯分析不混入。
  本轮正向测试实际通过 resume API 和生产Worker处理唯一剩余文件，原任务/预算/快照保留，
  原运行及其子任务在重开前后均可查；负向测试保留两跳Worker/媒体零变更与管理历史。
- 既有native40场景覆盖四类决定→分析→精确确认→真实结果、unknown/non-replay、技术只读、
  Files旧链接回原库及Worker/SQLite/API重开。visual2场景的desktop/narrow截图已人工检查。
- 安装包在源码目录外运行CLI/fresh DB/backup/restore/lease/消费者，installed-query确证安装的
  SQLite总体排除standalone analysis。没有仅凭标签、手填成功或前端mock替代真实结果。

### Actual evidence and matching reuse

新日志：`.git/validation-evidence/b40f58c6/test-reconciliation-20261028/`。
匹配的上一轮B日志：`.git/validation-evidence/c6d568a2/b-review-20261028/`。
均为稳定本地ignored证据，不声称已远程交付。

`execution-inputs.json` 记录精确候选、diff和两份测试哈希，并逐项核对现有四份生产资产
SHA256。相对前轮被审候选，产品、harness、Web源码/测试、依赖、配置和包装输入未变；
测试不进入wheel的 `mediaflow*` package。故仅复用输入相同的Web/native/packaging及未改的
安全证明；变动的Python测试已执行两份完整suite/直接回归，并对最终候选重跑全量Python。

| 本轮fresh命令（repo root） | 实际结果 / evidence |
| --- | --- |
| `.venv/bin/python -m unittest tests.test_automation_definition_execution tests.test_scope_continuation tests.test_operations_run_inventory tests.test_operations_task_center tests.test_task_center_recovery_lineage` | **212 / OK / 20.144s**；`affected.log` |
| `.venv/bin/python -m unittest discover -s tests` | **2903 / OK / 7 skipped / 315.592s**（real315.91s）；`python-full.log` |
| `.venv/bin/ruff check .` / `.venv/bin/ruff format --check .` | PASS / 386 files；`ruff-check.log`、`ruff-format.log` |
| `.venv/bin/python -m compileall -q mediaflow tests scripts` | PASS |
| `python3 scripts/check_governance.py` / `git diff --check` | PASS；收尾再次核对 |

上轮 **2903 / 2 failures / 7 skips** 的失败全量、Task Base单跑及本候选初次适配错误均保留，
没有隐去失败、增加skip/retry或放宽timeout。最终fresh结果见上表。

复用的原始命令/结果详见 `b40f58c6:TASK.md` 的 B actual acceptance evidence：Web单测
**87 files / 1266 passed**，默认Node E2E **240 passed**，真实Python原生inventory
**40 passed**，visual **2 passed**，Web typecheck/lint/format/build、pip check、examples、
禁用依赖检查均通过。wheel smoke和installed-query通过；wheel SHA256
`a1d5304edf227a7ca2db862e229fcf1e80d0a048262decb4a034951eed8fe553`。
上轮Playwright共用产物目录/installed-query实路径比较的纠正日志仍保留。

未提供真实SMB/S3/OpenList及endurance环境的既有7项skip仍是限制；SQLite ResourceWarning
和jsdom提示没有隐藏。Docker发布安全矩阵未重跑：本Task不改schema/运行命令/Worker执行
及消费/镜像部署或发布边界，已有wheel/installed消费者、本地安全全量及原生Worker重开，
不声称未跑的环境/发布证明通过。所有测试只用临时根和fake/local Provider，不触及用户媒体。

### All Slice outcomes reevaluated

| Outcome | 当前结论 |
| --- | --- |
| RO-1 | Task46.1已验收动作样式保留；本Task未改palette/Entry认证，默认Web回归无新增失败 |
| RO-2 | Task46.3早期受理/占用/初次确认保留；原生40场景含Files→Task→确认/Worker/重开 |
| RO-3 | Task46.2原库持久查看保留；普通Task旧链接回准确原库，既有菜单/non-localhost限制未宣称修复 |
| RO-4 | **本Task PASS**：产品五项阻塞及两处过时测试契约已解决，最终全量Python无失败 |
| RO-5 | **未完成**：Automation仍有独立grant门控/eligibility、旧Save publication状态及Run once分析后确认流程；本轮核对真实现有代码，未改变这些路径 |

本轮只收尾46.4；不扩大为RO-5实施，不更新Slice/Roadmap/Progress或提交Slice Closure Packet，
不由B关闭Slice、不push。后续需要的产品工作是合同内完整RO-5，由下一 coherent Task规划。
A-owned旧“首个Task”指针与最终文档对账仍留给A，不作为功能交付或关闭证据。

本轮时间从 UTC 01:06:59 起计；测试/构建/探测实际并集约338s，保守按346s计。
UTC 01:18:38时已用699s，比例<49.5%；后续仅文档核对和本地提交，无测试等待填充分母。
原始时间与测试日志保留在本轮证据目录；符合本轮测试时间低于50%的限制。
