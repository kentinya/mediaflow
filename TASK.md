# Task 46.4 — 只管整理的任务中心与真实四类恢复状态

Authority: committed [Slice46](SLICE.md) **RO-4**、AC-5/6/7/8/14/15，以及保持 RO-2/RO-3
已验收入口与确认语义所需的衔接；[Development Workflow](docs/development-workflow.md)。
实施前阅读 [Developer experience](docs/agent-experience/developer-implementation-role.md)。

```text
Task ID: 46.4
Parent Slice: 46
Status: READY FOR B REVIEW
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

## Developer Completion Report (fix round for B46.4-03/05)

```text
Task: 46.4 / High / T4
Task Base: 44cba4f93b94b72d6dee52fcd1199be729ec78c4
Fix base (B review checkpoint): e3dec038a76ec391ef302d1da4effcce1e895218
Implementation Head: 4ea21d2bdec889818cb2255d653b8f16dd17acb4
Status: READY FOR B REVIEW
Slice: ACTIVE (this is not A Final Review, PASS or closure)
Push: none performed
```

本轮只修 B46.4-03/05 两个 P1，保留 Task ID/Base/Goal/Scope；不新建 Task、不改 RO-5 意图/
执行引擎、不改 RO-1/2/3 已验收入口，也不自行 PASS。上一轮报告与 B 的复核结论保留在 Git 历史。

### B46.4-03 — 逐项四类责任约束中心恢复入口

- `task_item_recovery.py` 新增共享 `item_recovery_kind()` / `TASK_ITEM_RECOVERY_KINDS`：只有
  当前四类问题（含 live blocker、已保存决定待续作）或已受理的四类恢复链才是
  `business_problem` / `recovery_lineage`；其余全部是 `technical_history`。run-item 页、
  条目证据页、batch 文档和单条目面板都读这一个后端判定。
- `recovery_admission.py` 在 admission 时把真实四类决定身份写入既有
  `recovery_requests.review_kind/review_id`（保存决定后的 `*_resolved`、live blocker），
  因此管理 API 对纯技术失败发起的分析续作仍保留 `review_kind=NULL` 并保持
  `technical_history`；既有列无 schema 变化。
- `service_api.py` 为 run items、item evidence、saved batch child 发布同一 `recoveryKind`；
  `RunDetailTabs` 只给 `business_problem`/`recovery_lineage` 条目显示批量选择，已保存批次
  的技术历史 child 只显示持久行/证据和“技术历史，仅只读”，不提供摘要/确认/重试；batch
  级 nextAction 在没有任何可操作 child 时也不渲染。
- 技术历史仍保留真实原因/阶段/效果/结果/日志/导出：条目表的失败证据改为
  `failure.category: failure.message`（不再拼接 `nextAction`），证据页不渲染其
  `checkpoint.nextAction`，`TaskItemRecoveryPanel` 显示“无（技术历史，仅只读）”并省略
  generic next action。管理 API/CLI 的单条/批次恢复能力未删除。

### B46.4-05 — Job 归属必须证明已受理整理来源

- `operations_run.py` 新增 `ORGANIZING_JOB_SEED_COMMAND_FAMILIES=("organize",)` 与
  `ORGANIZING_JOB_LINEAGE_RELATIONS`（recovery/scope/metadata-correction 的持久 relation 表）。
- `sqlite_runtime.py` 的 Job 分支不再只按命令白名单：`organize` admission（含 pre-Task
  排队/失败）直接纳入；其余 continuation Job 必须通过自身 `job_id` 对应的持久 relation
  指向 `organizing_tasks` 递归总体中的源 Task。纯分析 continuation 的 Job/子 Task 因此在
  排队、claim、绑定、完成/失败和重开各阶段都留在管理历史而不进入中心。
- `resolve_operations_run_link()` 的 Job→Task 回退也改用同一共享总体，而不是只比对命令；
  普通/分析身份的旧深链仍得到有界 404。
- 新增真实链路：CLI `organize` DryRun → 管理 API continue（202，Job queued）→ 中心列表/
  统计/来源/游标/详情/导出全部为空 → 真实 Worker → 子 Task → 重开后仍为空；同一链路在
  已受理整理 Task 上 continue 时，Job 在 claim 前后和重开后都保留在中心，并正确绑定子 Task。
  scope/metadata-correction continuation Job 的真实 relation 正反例也覆盖。

### 实际命令与结果

| 命令 | 结果 |
| --- | --- |
| `python3 scripts/check_governance.py` | PASS（开始与交付前） |
| `git diff --check` | clean |
| `.venv/bin/python .git/validation-evidence/cb1327a/b-review-20261027/reproduce.py` | **exit 0**，`contractChecks` 5/5 true |
| `.venv/bin/python .git/validation-evidence/e3dec038/b-review-20261027/cli-continuation.py` | **exit 0**；continue 202，中心 total=0、beforeStatus=404 |
| `.venv/bin/python -m unittest tests.test_operations_run_inventory tests.test_operations_task_center tests.test_operations_run_detail tests.test_operations_run_detail_plan_evidence tests.test_operations_run_detail_log_isolation tests.test_task_center_recovery_lineage tests.test_recovery_continuation tests.test_recovery_batch tests.test_processing_recovery_admission tests.test_library_file_operation_history tests.test_operations_workspace tests.test_v2_automation_operations tests.test_api_security tests.test_manual_ignore tests.test_manual_ignore_batch tests.test_manual_operations_contract` | **370 OK** |
| `.venv/bin/ruff check mediaflow tests scripts` / `ruff format --check` | PASS / 358 files formatted |
| `web`: 13 个受影响 vitest 文件（含 `RunDetailTabs`、`TaskItemRecoveryPanel`、`task-item-recovery`） | **192 tests OK** |
| `web`: `npm run typecheck` / `npm run lint` / `npm run format:check` | PASS / PASS / PASS |
| `web`: `npm run build` | PASS（当前生产资产） |
| `web`: `npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts` | **40 passed**（含 mixed 技术项不可批量选择、纯技术无 guidance、saved batch 技术 child 只读） |
| 同上独立干净 harness：`tests/e2e/operations-task-center-visual.python.spec.ts` | **2 passed** |

所有浏览器/后端探测只用 harness 临时 SQLite/媒体根与合成 Provider；故障注入只作用于实际
Provider/Executor adapter。未用用户配置/数据库/媒体，未伪造成功/claim 或手改 DOM。既有
产品测试/断言/timeout/retry/skip 未放宽。

### 已知风险与剩余工作

- 管理 API/CLI 仍可按显式请求继续一个纯技术条目（这是保留的管理恢复能力）；中心是否展示
  动作由服务端 `recoveryKind` 决定，网页不再提供旁门。若未来其他 Web 消费者忽略该字段，
  仍需在消费端保持同一门控。
- `has_persisted_recovery_lineage` 新增要求 continuation request 带四类 `review_kind`。
  升级前已存在的 in-flight 四类 request 若 `review_kind` 为空，在其排队/运行期间会暂时按
  technical_history 只读展示；完成后由当前四类问题判定恢复原类型与摘要入口。未回填历史行，
  未改写任何原 Task/Result/claim。
- 无 schema 变更、无 Worker/Scheduler/OrganizerExecutor 执行语义变更；`recoveryKind` 是只读
  投影，不授予执行/重放权。
- 未跑全量 Python `discover`、wheel/Docker/发布安全矩阵与 B 的完整 T4；按分工属 B。
- RO-5 与 Slice 最终关闭/文档对账仍未开始。

### 交付身份

- Implementation Head: `4ea21d2bdec889818cb2255d653b8f16dd17acb4`
- Fix range: `e3dec038a76ec391ef302d1da4effcce1e895218..4ea21d2bdec889818cb2255d653b8f16dd17acb4`
  （17 个文件：后端查询/恢复判定、Web entities/中心 UI、affected tests 与 architecture CURRENT）。
- 本报告在独立 docs checkpoint 提交；Working tree 无 tracked dirty，既有 untracked 日志/
  参考图/OS 文件保持未暂存。

## B Review Result

```text
Reviewed: 44cba4f93b94b72d6dee52fcd1199be729ec78c4..d63dd7105177f492c287c99412b90e22f19380cf
Implementation candidate: 4ea21d2bdec889818cb2255d653b8f16dd17acb4
Decision: FIX REQUIRED — 2026-10-28 / B re-review
Acceptance runs: original reproduction, mixed-result counterexample, focused lineage and native checks
Task blocker: B46.4-02 (P1) — ignore plus actual recovery success is falsely projected as all-success
Slice Required Outcomes / Surfaces all satisfied: NO
Next: SAME TASK FIX LOOP — preserve Task ID/Base/Goal/Scope
```

此前完整判定在 `542be061:TASK.md`、`a456b9d0:TASK.md` 保留。本轮核对整个 Task Base..Head
manifest、当前生产调用链及新增18文件修复，不把 Developer 结果转写为 B 验收。

### Verified fixes

- **B46.4-01 原始恢复停点通过。** 保存决定、完成分析、等待摘要确认仍保留原四类责任；
  原复现的 Recognition/Conflict 单项真实成功、重开及旧 Results 保留也通过。
- **B46.4-03 本轮实际验证通过。** real-Python 的 technical-only 无 generic guidance/继续，
  mixed Task 的技术/unknown/success 项不可批量选择，重开 saved mixed batch 的技术 child
  只读；三条现有原生用例均通过。未删除管理单项/批次 API 能力。
- **B46.4-04 原生入口验证通过。** 真实 direct-file Task 的旧深链返回正确原库与所选操作，
  旧集合关闭、未知身份有界只读、无混合读取/命令；本轮再次执行现有用例通过。
- **B46.4-05 本轮实际验证通过。** 原 CLI/API continuation 复现中，continue仍202、中心
  total=0；新增真实 CLI → 管理 continue → queued Job → Worker/子 Task → reopen 的现有
  regression 通过，合法整理来源的续作正例仍可见。未把纯分析记录删除。

### B46.4-02 — Remaining P1 and required correction

**实际场景与事实：**复用现有 native `seed_batch_summary_recovery` 的两主文件 Manual
admission及真实 pre-mutation 失败fixture；用现有 MetadataReviewService（与 native Metadata
fixture相同）建立合法候选决定。通过已有恢复 API 明确忽略 B，对 A 保存候选 → continue →
真实 Worker分析 → 精确摘要 → 仅确认 A → 真实 Worker整理。没有手填任何成功状态/Result。

最终 A 已真正整理，B 的 TaskItem 为 `ignored`、文件仍在 source；原 Results 未改。
但中心在 SQLite/API 重开前后都发布：

```text
status=completed
recovered_completion=true
attention=false
problem_types=[]
```

界面据此显示“已完成（恢复成功）”，并声明“每个必要条目都有精确关联的真实成功证据”。
这没有满足 RO-4 / AC-15、Task Implementation Scope §4 / Acceptance 中“忽略不等于整理成功、
真实全成功才投影恢复完成”的既定结果。B46.4-02 的原始单项正例虽通过，混合结果仍未交付。

**根因：**`sqlite_runtime.py::_run_query_document()` 的 `recovered_success` 只检查
`failed/partial/pending/processing/paused` 的未成功项；`ignored` 项直接被排除，随后只要
有 confirmed preparation，就可由其他项成功把整个 run 判成恢复全成功。原 Task/Result
未改并不能纠正这一错误的列表/统计/详情投影。

**修复步骤：**

1. 对原整理范围的必要主项统一计算实际处置与证据。只有每个必要项的本次真实成功，或其
   exact source/pin/合法 lineage 的已核实成功 follow-up，才能形成全成功恢复完成投影。
   忽略/跳过/取消/无成功证据不能通过从检查集合排除而算成成功；未知/部分效果仍保持真实。
   保留既有主文件成功/附件告警语义，不扩大执行范围或引入附件自动重放。
2. 同一结果用于列表、状态筛选、统计、详情和 recovered_completion 文案。已结束、已处理
   问题与整理全成功保持区别；两项中一项忽略、一项成功的实际处置可完整查看，不能宣称
   “每个必要条目成功”。原失败尝试、忽略决定、Results/audit保持原样，成功或未知项不重跑。
3. 在当前 lineage/Task Center tests 增加上述真实双项 API/Worker 负例，并覆盖单项/多项全
   成功正例、只恢复部分、ignored/skip、技术/未知效果、source/pin不匹配。断言最终 API 的
   status/recovered_completion、列表/统计和页面文案，及忽略文件仍在源处、成功兄弟不重放。
   初始 review fixture 应与配置实际识别结果匹配，不用“已自动识别却再强行创建识别选择”
   的不合法 fixture 冒充产品失败。可复用本轮已完成 Metadata 负例；无需新增过程框架。

这仍是原 B46.4-02 和原 Task 的修复，不新建 Task、不扩展合同或 RO-5。Developer跑新增失败
用例与直接受影响测试后交新 checkpoint；B 在修正候选上完成原定 T4，包含已验证01/03/04/05
的回归。不能把本轮四个修复点通过写成整个 Task PASS。

### B evidence and testing boundary

启动为 `main` / `d63dd710`，无 tracked dirty；既有 untracked日志、参考图、OS/private文件
保留且未暂存。证据在 `.git/validation-evidence/d63dd710/b-review-20261028/`，未提交、非远程
可达；JSON保存实际 API/Worker/逐项源存在性/重开和旧Results事实，脚本副本及资产SHA256保留。

| B 本轮实际命令 / cwd | 结果 / 证据 |
| --- | --- |
| `python3 scripts/check_governance.py` | 开始与文档完成后 PASS |
| `.venv/bin/python .git/validation-evidence/cb1327a/b-review-20261027/reproduce.py` | exit0，原5项contractChecks true；`original-reproduction.json`，约0.65秒 |
| `.venv/bin/python .git/validation-evidence/e3dec038/b-review-20261027/cli-continuation.py` | exit0，纯分析续作202但中心total=0；`cli-continuation.json`，约0.17秒 |
| `.venv/bin/python .git/validation-evidence/d63dd710/b-review-20261028/mixed-reproduction.py` | **exit1**，A真实成功、B ignored且仍在源处；`mixedIgnoreIsNotAllSuccess=false`；`mixed-reproduction.json`，约0.24秒，旧Results unchanged |
| `.venv/bin/python -m unittest tests.test_task_center_recovery_lineage` | **8 OK / 2.323s**；SQLite ResourceWarning原样保留在`lineage-tests.log` |
| `web/`: `npm run build` | PASS，约1.1秒；`build.log` / `production-assets.json` |
| `web/`: `npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts --grep 'a technical failure keeps its exact read-only|a mixed run never offers|a reopened mixed saved batch|retired Task collections stay closed'` | **4 passed / 3.7s**；`native-critical.log`，各原生入口独立验证 |
| `git diff --check` | clean |

仅使用既有产品 API/CLI、production review producer、现有临时库/native fixture及真实 Worker；
无用户配置/数据库/媒体、无伪造成功/claim或DOM修改。诊断中一版 review fixture与实际C目录
自动识别不匹配，未作为缺陷；最终负例用合法Metadata选择，成功均由Worker实际执行。
诊断/最终原始证据保留；未修改产品/既有测试、断言、timeout/retry/skip。

已证明原 Task P1，按workflow §6在昂贵门禁前 FIX REQUIRED。本轮未启动全量 Python/Web/
默认E2E、wheel/Docker/发布安全矩阵；Developer的结果未冒充B验收，必要T4在修正候选上执行。
所有测试/构建/探测含诊断尝试累计保守上界小于60秒；已记录23:05:01–23:09:48 UTC工作区间
下界287秒，占比小于21%，满足本轮严格小于50%，未故意等待扩大分母。

### All Slice outcomes reevaluated

| Outcome | 当前结论 |
| --- | --- |
| RO-1 | Task46.1已验收基础保留；本候选未改动作样式，不宣称完整视觉重验 |
| RO-2 | Task46.3先受理/占用/初次确认基础保留；四类原始恢复停点通过，整体仍待修正后T4 |
| RO-3 | 原库持久查看基础保留；普通工作旧入口回库原生验证通过，既有菜单限制不重开 |
| RO-4 | **未完成**：原 B46.4-02 的 mixed ignored/all-success 投影仍为P1；01/03/04/05局部验证通过 |
| RO-5 | **未完成**：Automation detail/Save/Enabled/Run once/稳定性改造仍属后续，当前Task不提前实现 |

继续同一Task修复；不规划下一Task，不交Closure Packet、不关闭Slice，不改Roadmap/Progress。
仅checkpoint本TASK复核；不改产品或A-owned文档，不push。

## Developer Completion Report (fix round for B46.4-02)

```text
Task: 46.4 / High / T4
Task Base: 44cba4f93b94b72d6dee52fcd1199be729ec78c4
Fix base (B review checkpoint): d63dd7105177f492c287c99412b90e22f19380cf
Implementation Head: 76553772
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
