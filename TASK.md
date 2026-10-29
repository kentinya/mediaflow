# Task PATCH-20261030-1 — 任务中心统一时间筛选与刷新反馈

Authority：用户在发现仅“全部任务”完成简化后，明确要求“其他标签页也改”。本 Task 将同一
创建时间范围交互补齐到其余七页，明确替换上一修正中“其他七视图保留原筛选”的限制；
不改各标签的业务收录范围、任务详情和四类恢复权限。遵循
[AGENTS.md](AGENTS.md)、[Development Workflow §3.1](docs/development-workflow.md#31-independent-minor-bugs)
及 [B 角色指南](docs/agent-experience/task-planner-reviewer.md)。
本轮由 B 完成规划并建立 PLANNED checkpoint，交 Developer 实施；不自动启动其他角色/agent。
用户随后要求修复任务中心刷新闪烁和英文文案、参考整理规则页，补入同一只读查询体验修正；
Task ID、Base、Medium/T3 和此前八标签结果不变，状态仍为 PLANNED。

```text
Task ID: PATCH-20261030-1
Task Type: STANDALONE MINOR BUG
Parent Slice: NONE
Status: READY FOR B REVIEW
Authorization: USER-REQUESTED CORRECTION — 2026-10-30
Task Base: e40093aa2400794f4423987658fba3095c7adda5
Difficulty: Medium
Test Level: T3
Planner / Reviewer: B
```

上一独立修正 PATCH-20261029-4 已 PASS；完整 B 记录在 `3e0e7d62:TASK.md`，治理后指针在
`e40093aa:TASK.md`。Slice46 仍为 PASS / CLOSED，其原 Base、Implementation Head、SLICE、
Roadmap、Progress 和延期边界不变。本次不是重新评审或关闭原 Slice。

## Goal and complete journey

用户从侧栏进入任务中心，切换全部任务、进行中、需要处理、已结束、识别恢复、元数据恢复、
分类恢复、冲突处理，八页的列表筛选均只提供“创建时间从（本地）／至（本地）＋清除时间”。
默认或清除后读取**当前标签完整获准总体**，选定日期后读取其中创建时间在范围内的任务，
仍采用有界服务端分页。切换标签保留合法时间范围并从新标签第一页读取；清除日期不切回 All，
也不把“需要处理／识别恢复”等标签变成全状态任务列表。
任务中心刷新使用“刷新／刷新中…”等中文文案；手动刷新有明确反馈且防重复点击，后台轮询
安静更新真实状态，不周期性切换页头按钮或挤动布局。正常刷新保留现有列表/详情和当前上下文。

- Entry/state：八标签及统计卡片沿用现有入口和布局，默认不打开详情；时间、数量、任务行及
  当前标签一致，区分加载、空总体、范围内无匹配和读取失败。
- Action：选单侧/双侧日期即应用，无搜索提交；可清除时间、刷新、翻页、打开/关闭详情，
  以及按当前任务/类型查看问题文件和合法后续动作。
- Success：列表、总数/统计、分页使用相同服务端条件；浏览器刷新、前进后退、重连和现有
  合法回程保留标签/时间、仍有效的分页及精确任务、问题文件定位，不留下不可见列表限制。
  游标失效沿用既有明确提示/重新读取，不要求复用失效页。
- Failure/recovery：读取失败保留可见日期和明确的只读重读动作；401/403 沿用共享边界。
  空结果可清除时间回到当前标签；筛选/刷新/返回不提交工作、调用 Provider 或重放命令。

适用要求：UX-001/002/007、REQ-API-003、V2-OPS-001/003/005/009/012/014/016、
V2-AUTH-001–003、V2-SAFE-001；完整旅程见
[Tasks, results and per-item recovery](docs/product-experience.md#tasks-results-and-per-item-recovery)、
[任务中心页面约定](docs/task-center-page-spec.md) 与
[CURRENT query contract](docs/architecture.md#current--task-center-query-summary-confirmation-and-typed-recovery-slice45)。
现行文档中“其他七视图保留原筛选”是待本 Task 替换的旧界面定义；用户本轮明确授权统一，
不扩大整理总体、恢复能力或管理 API 的权限/查询能力。

## Actual code gap and implementation anchors

- `OperationsLanding.tsx` 的筛选展示、`readFilters`、`filtersToSearch`、旧条件规范化和查询组装
  均以 `view === "all"` 特判；其他七页仍渲染搜索、来源、状态、操作类型和搜索提交。
  仅删除控件会使原 URL 中条件继续影响总体。
- 同文件已有 `RunTimeRangeFields`、本地日界限转换、清除、查询 key、服务端游标与标签切换，
  可以复用。`view` 是后端标签总体谓词；不能与附加列表条件一并删除。
- `operations-return.ts` 的 `operationsLandingSearch` 只对 All 清除旧列表条件/游标，
  非 All 回程仍会恢复旧搜索等条件。实际详情、四类处理和现有 Files/Automation 链路还携带
  `run`、`problemRun`、`problemType`、问题文件/详情游标，需区分列表限制与精确定位。
- `OperationsInventory.test.tsx`、`operations-return.test.ts` 及现有 real-Python
  `time filter:` 用例明确断言其他页保留旧控件；这些断言需要替换，保留原权限、范围、
  结果和返回安全检查。不是新建筛选系统或退役管理 API。
- 页头 `RefreshControl` 默认显示 `Refresh/Refreshing…`；`anyFetching` 直接取清单/选中详情的
  `isFetching`，而清单每 5 秒后台读取一次，导致未点刷新也周期性改文字和 disabled 样式。
  B 经现有侧栏→任务中心和页头刷新入口、隔离 fake API 的受控读取延迟复现：按钮宽度约
  76.7→107.8px，右对齐时左边缘跳约 31.1px；同条件刷新期间表格节点保持连接，未观察到
  整张表卸载。因此修复已证明的按钮跳变，并验证正常刷新不清空列表，不能先假定整页重建。
  本地诊断在 `.git/validation-evidence/patch-20261030-1/planning-refresh/`，首次短采样未捕获
  轮询状态，后续完整窗口记录自动及手动切换；这不是候选验收或产品通过记录。
- 整理规则页已有中文 secondary 按钮、忙碌反馈和防重复；它没有同样的列表周期轮询。
  复用其可见交互/样式，不把任务中心后台轮询直接当作用户手动刷新，也不全站改默认文案。

## Implementation Scope and ordered steps

1. **复用八页统一筛选条。** 其余七页采用现有 All 创建日期交互；删除旧搜索/提交、来源、
   状态、操作类型及其独占草稿/处理器，范围仅为页面级任务列表筛选条，不删除详情/问题处理
   内部必要的搜索、候选输入、文件处置筛选或命令。适当消除已失效的 All/非 All 展示分支。
   请求中/清除/空结果文案统一表达时间条件与当前标签；无日期时可沿用不显示清除按钮。
   既有标题、统计、八标签、表格列、行操作和详情/问题文件布局不重做。

2. **统一提交条件，保留标签语义。** 所有列表请求只提交当前 `view`、可见日期及正常分页；
   不再从旧 URL/组件状态/返回上下文发送 q、source、status、command、attention 或 problem
   等额外列表限制。`view=attention` 及四类恢复 view 本身仍由后端限定真实四类总体；
   不以删除可见状态筛选为由删除它们。保持管理 API 和其余消费者的搜索/筛选契约。
   复用当前本机时区日界限，结束日含完整小数秒；日期 min/max、单侧范围及自动应用保持。
   切换标签保留日期、清空旧标签分页；改变/清除日期重新从当前标签第一页读取。

3. **完成真实入口的 URL/回程恢复。** 将 All 已有的规范化覆盖到全部八页，避免首次请求或
   回程中隐形条件/旧游标短暂生效。不携带旧条件铸造的列表游标；合法时间/view 的正常游标
   则继续用于刷新/详情关闭/重连。
   精确 `run`、详情 tab/item、`problemRun`/`problemType` 和问题文件分页不是普通列表筛选，
   不得机械按名称全删。需要处理页多类型任务必须继续允许明确选择类型；四类恢复页仍按其
   本身类型展示。基于实际可达的查看问题文件→详情→返回、已有 Files/Automation 链接及
   旧页面能够产生的书签/回程核对，必要时同步已有 URL 生成者/allowlist，不新造入口。
   仅在列表条件改变时清理与旧条件绑定的分页；不扩展为通用 URL/认证重构。

4. **保持服务端总体与恢复独立。** 复用现有查询、计数、去重和分页，不在浏览器当前页过滤
   或伪造日期统计。统计卡片保留各自原有总体/分区含义，仅同步当前日期范围，不将当前
   标签的行数套到所有卡片。多类型重叠、四类任务/文件数、普通初次待确认和技术失败归属保持。
   快速改日期/标签时旧响应不覆盖当前状态；失败/401/403 不显示旧总体为新条件成功。
   本轮不改后端业务、任务状态、存储、schema、执行、恢复决定或权限。

5. **修复刷新反馈与跳动。** 页头参照整理规则页使用中文“刷新／刷新中…”，保持 secondary
   样式、键盘名称/焦点和忙碌防重复。任务中心本页现有列表、详情、问题文件里的只读刷新
   入口同样采用中文，保持各自原有读取范围；不是全站翻译或翻译后台数据。
   正常静默轮询继续及时发现新任务/进度，不反复改页头按钮的文字/宽度/disabled 外观；
   手动刷新单独呈现必要反馈，同一手动刷新未完成时重复点击不触发重复刷新组。
   与已在途的同条件后台读取安全合并/协调，不以关闭轮询、延长轮询周期或人为延时止闪。
   手动刷新继续覆盖清单、已选 overview 及既有活动详情读回；局部 busy 的完成/失败应与
   本次操作实际负责的读取相符，不能刚发请求就显示完成；不等待未挂载面板、之后的定时
   轮询或全局所有查询空闲。允许现有查询机制合并或取消后重读，不规定全页 GET 固定次数，
   但重复点击不能重复受理同一手动刷新。按钮文案切换不造成可见的页头/周边内容跳动，
   窄屏正常换行允许。正常同条件刷新不临时清空现有内容或用整块加载占位替换，保持当前
   日期、标签、详情选择和可继续操作的位置；不要求特定 DOM 节点/组件实例保持同一对象，
   也不要求实际数据变化后滚动坐标逐像素不变。数据更新引起的行增删、排序、任务状态变化
   和已删除/不再可读对象的真实结果仍应显示，不能为保持旧画面隐藏变化。
   日期/标签真正改变时沿用真实加载状态，不将别的查询或身份缓存当作当前结果。
   请求失败明确展示现有读失败边界，401/403 保留权限/缓存清理规则；不得为“不闪”继续展示
   受限/失效内容。只调整任务中心消费方或必要可选展示参数，不全局修改 RefreshControl、
   AuthorizedReadBoundary 的权限/重读行为和其他页面默认语言。

6. **同步直接相关 CURRENT 文档与测试。** 在同一实现 checkpoint 更新 README、
   Requirements 的修订说明、V2-OPS-001/003、Product Experience、Architecture 和
   task-center-page-spec，统一改为八标签时间范围；说明清除后仍为当前标签总体，
   管理 API 能力保留。历史参考图不改，原 Slice/旧 Task 的验收事实不重写。
   页面约定及旅程同步中文手动刷新、静默轮询和正常刷新保留内容的语义。
   测试替换“其他七页保留原筛选”断言，保留既有 All、安全/身份/回程检查。

优先文件：`web/src/features/operations/OperationsLanding.tsx`、
`web/src/shared/navigation/operations-return.ts`、本页消费的 `RunDetailTabs.tsx`/
`ProblemFilePanel.tsx` 及直接测试；允许必要的查询/导航/刷新展示 helper、
现有隔离 harness/fixture 和局部样式调整。生产修改限 Web 查询呈现，不改 Python 业务/API。

## Acceptance Criteria

- [ ] AC-1：八个真实标签逐一检查，页面级任务列表筛选条只有两个创建日期控件及按需清除时间，
  无旧搜索、来源、状态、操作类型或搜索提交；All 时间筛选语义保持。任务详情、问题处理
  内部必要输入/筛选/命令，以及其他页面共享搜索保留，不对整个页面机械断言“零搜索框”。
- [ ] AC-2：每个标签无日期/清除后都是该标签完整获准总体，日期限制与标签谓词组合正确。
  Running、Attention、Ended 和四类恢复不串总体；四类问题/任务身份、待处理去重、问题文件
  数量及合法操作沿用原计算/授权规则。选/清除日期和切标签允许相应行数/统计正常变化，
  断言其符合当前日期与各卡片原有总体含义，不断言切换前后数字相等。
- [ ] AC-3：单侧/双侧日期直接应用；本地显示/筛选时区一致，含结束日最后小数秒。
  切标签保留日期并重开第一页，日期变更/清除弃用旧列表游标。跨页行、总数/统计一致，
  没有当前页内筛选、无界全量加载或旧响应覆盖新条件。
- [ ] AC-4：旧页面真实可产生的非 All 书签、刷新、详情关闭、认证重连及原有合法回程均
  不复活已删除条件，也不重用旧条件游标。精确任务详情、必要问题类型/文件定位及合法
  详情/问题文件页状态保留；已失效游标或已删除/不再可读对象沿用既有明确失败/重新读取，
  不要求强行保留旧页或旧对象。管理 API 的其他消费者仍支持原搜索/筛选。
- [ ] AC-5：四类页“查看问题文件”、需要处理页的明确类型选择、单项证据/详情及返回可用，
  不因删除 `problem` 列表条件误删 `problemType` 定位。保留已有 Files/Automation 精确链接；
  不要求本轮重跑恢复执行全链路或新增恢复动作。
- [ ] AC-6：加载、空总体、日期无匹配、请求失败、401/403 分支正确，日期按既有合法 URL
  保留，身份/缓存清理仍生效。清除回到当前标签总体。未显式执行 Provider 搜索、恢复决定
  或控制命令的纯筛选/标签/刷新/分页/证据打开与返回旅程，业务 API 只有有界只读请求，
  不创建工作、访问 Provider 或写媒体，不重放成功/不确定效果；此断言不套到原有显式命令。
- [ ] AC-7：1536×1024 和 390×844 下实看八标签入口、日期/清除、代表性列表/详情/问题文件；
  键盘可达，焦点可见，无本次引入的整页横向溢出/控件遮挡；既有标签/表格容器滚动允许。
- [ ] AC-8：CURRENT 文档不再把其他七页写成保留旧筛选；原 Slice 和已接受 Task 的历史结论
  不变。实际结果/失败/限制、精确 checkpoint 和测试用时清楚记录，交 READY FOR B REVIEW。
- [ ] AC-9：任务中心页头及本页现有只读刷新按钮使用中文，正常/手动忙碌状态清楚，重复点击
  不重复受理手动刷新；busy 对应本次负责的读取，完成或失败后可继续合法操作。桌面/390px
  正常与忙碌文案切换无可见布局跳动，正常响应式换行允许。各刷新入口原读取范围保持；
  正常同条件手动刷新不临时清空列表/详情或替换成整块加载，不无故重置日期/标签/有效分页/
  选择及操作位置。不以节点对象身份、固定像素、GET 固定条数或保留已经失效的旧结果验收。
- [ ] AC-10：观察至少一个真实轮询周期及新工作/进度读回，页头不周期性切换手动 busy 文案
  或闪变外观，列表仍实时更新。覆盖手动刷新与在途轮询交叠、失败及401/403；不关闭/放慢
  轮询止闪、不伪装成功、不展示受限旧数据、不重发命令。共享组件必要可选展示参数不能
  改掉其余页面的默认语义/文案；用实际受影响消费者的聚焦检查验收，不扩成全站逐页扫查。

## Required Tests

T3：跨 Web 列表/URL/回程、手动/后台刷新反馈与既有 API 时间/分页边界的只读集成修正。无新领域状态、权限或
执行协议。按 [workflow §6](docs/development-workflow.md#6-test-levels) 分工；不要求全仓
Python/Web/E2E、wheel/Docker/外部服务矩阵。若确需改 schema、权限、执行或后端业务，先交 B
重评边界/等级。测试用时须小于本轮工作用时 50%；优先已知问题/直接影响，不以扩跑无关测试
填充验收，不通过删除安全断言、重试或放宽超时解决失败。

### Developer — affected tests

根目录：`python3 scripts/check_governance.py`，结束前 `git diff --check`。
`web/`：

```sh
npm run test -- run src/shared/ui/AppShell.test.tsx src/features/operations/OperationsInventory.test.tsx src/features/operations/OperationsRouter.test.tsx src/features/operations/RunDetailTabs.test.tsx src/features/operations/run-query.test.ts src/shared/navigation/operations-return.test.ts
npm run typecheck
npm run lint
npm run build
npm run test:e2e -- tests/e2e/task-center-layout.spec.ts
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts --grep "time filter:|refresh feedback:|a visible terminal inventory discovers new work and shows live progress"
```

对实际改动的 TS/TSX/CSS/测试文件运行 `npx prettier --check <实际文件清单>`；新增 helper/test
加入受影响清单。如修改 `scripts/operations_inventory_harness.py`，根目录运行：

```sh
.venv/bin/ruff check scripts/operations_inventory_harness.py
.venv/bin/ruff format --check scripts/operations_inventory_harness.py
```

- 单元用例按八 view 参数化覆盖控件、无日期/选日期/清除、请求参数及旧条件移除；覆盖
  快速切换、读取失败与必要回程分支。独立问题文件/详情筛选不是本次删除对象。
- 用延迟读取/现有轮询计时能力覆盖中文、手动 busy/防重、静默轮询、交叠读取、失败与
  正常同条件内容保留。更新任务中心页头对应的英文定位断言，按实际容器定位；不把其他
  页面/恢复命令的同名按钮全局替换。必要共享展示参数须有现有默认行为不变的覆盖。
  内容保留检查可见状态、选择、位置与可操作性；测量跳动用于解释可见问题，不把本地
  76.7/107.8px 诊断数值、DOM 身份或请求固定计数变成硬门禁。同时覆盖正常任务状态/行数
  更新，防止以冻结旧内容“修复”闪烁。列表无搜索断言限定页面筛选条，保留问题处理输入。
- 扩展现有 `time filter:` real-Python 旅程，使用 `operations_inventory_harness.py` 现有时间、
  轮询/恢复隔离 fixture，必要时有限扩展已有 seed。覆盖 Running/Ended 时间总体与至少一个
  有实际四类问题的 Attention/恢复视图，断言范围内/外记录、计数/分页、旧非 All 链接及精确
  问题文件/详情回程。仅打开已有处理/证据，不把恢复执行全链路加入本布局/查询修正门禁。
  在同一 spec 中以 `refresh feedback:` 命名聚焦真实手动刷新/轮询旅程；复用既有 live
  inventory 用例证明新工作/进度仍会出现，同步移除其已废弃列表筛选动作，保留实时性断言。
  从现有任务中心刷新入口验证延迟读取期间内容/上下文和中文反馈，不新建探测入口。
- 默认浏览器用例从现有标签入口逐一验证八页一致，桌面/390px 实看并保存截图；复杂回程
  选代表案例，不要求八页 × 所有错误 × 全部视口的笛卡尔积。
- 临时 SQLite/Local 和一次性身份；不访问用户配置、运行库、媒体或外部 Provider。
  不新增产品路由/探测端点，不构造实际使用中不可能触发的问题。

### B — independent acceptance

独立审查完整 Task Base..candidate，先核对八页一致与标签总体不串，再核对旧条件清理、
问题文件定位及回程；不把旧 Task 限定 All 的 PASS 当作本 Task 验收。
执行上述受影响命令（完整包含的用例不重复执行），额外在 `web/` 运行 `npm run format:check`；
根目录核对后端既有时间/游标契约：

```sh
.venv/bin/python -m unittest tests.test_operations_run_inventory.RunInventoryTestCase.test_time_filters_compose_with_status tests.test_operations_run_inventory.RunInventoryTestCase.test_cursors_bind_the_submitted_filter_scope
python3 scripts/check_governance.py
git diff --check e40093aa2400794f4423987658fba3095c7adda5..HEAD
```

B 独立实看八标签筛选，桌面/390px 截图与一个真实四类问题文件→证据→返回路径，保留
实际命令、精确候选、计数/失败/skips 与用时；证据保存在 CI 或 ignored 稳定本地目录。
独立核对 AC-9/10 的手动与静默轮询反馈及实际数据更新，并保留前后帧/布局/请求证据；
只复用输入/产物完全一致的 B 自有证据。规划只做治理、代码/文档核对及上述有界诊断，未跑候选验收。

## Non-goals and workspace

不重开/关闭 Slice、不改 Roadmap/Progress、不重做页面/统计/详情或 Rules/Automation 产品；
不新增搜索、任务归并、Provider/API/schema/索引，不改变管理 API 的其他消费者；
不删问题文件/详情自身必要筛选，不修改四类恢复/初次确认/控制/执行/权限或效果真值；
不创建新流程工具、远端/生产测试或新 agent，不自动推送/部署本轮新 Task。

规划预检 PASS；`main` / Task Base 如上，初始无 tracked 改动，工作区及 Git 可写。
原有未跟踪各级 `.DS_Store`、`.mgmt.log`、`.t.log`、`.t_test_*.log`、`15`、
`docs/pics/自动化页.png`、`docs/pics/自动化页-全局设置.png`、
`output/imagegen/slice45-task-center-v1.zip` 均保留，不移动/清理/暂存；私有配置不读取或纳入。
实施前重新记录实际分支/HEAD/status；本 Base 不随规划、实施、返工或报告提交移动。

## Developer Completion Report

Decision：READY FOR B REVIEW（Developer 交接，不是独立 Task PASS）。

- 实施起点：`main / f30f521529ab6c68209b961c34bdc2b4dc90cdb2`；Task Base 保持
  `e40093aa2400794f4423987658fba3095c7adda5`。
- 实现 checkpoint：`87630b5898bcfa6ec3c341f7b11d73f9f5e1f06a`；源码树
  `04de4690855a10c3762690965b06d49f642f368b`。本报告为随后仅修改 TASK.md 的管理提交；
  B 审查完整 Task Base..候选 HEAD，产品/测试/构建输入与实现 checkpoint 相同。
- 八页共用日期控件与有界 view+时间查询；旧列表条件及关联游标不再生效，精确任务、
  详情和问题类型/文件分页保留。中文局部刷新控件以实际手动读取 Promise 控制 busy、防重，
  预留忙碌文字宽度；轮询维持 5 秒，同条件在途读取可合并，页头等待清单/overview/活动详情读取。
  恢复面板和计划摘要也使用相同局部反馈，共享 RefreshControl/权限边界默认行为未改。
- 已同步六处 CURRENT 文档；无 Python 业务/API、schema、权限、命令或媒体操作修改，
  SLICE/Roadmap/Progress 未改。初始未跟踪文件全部保留且未暂存，未读取私有运行库/配置或用户媒体。

验证均在本地隔离 fixture 上实际执行；浏览器从现有侧栏/窄屏菜单、八标签、日期、刷新、
查看问题文件及证据/关闭详情入口进入。旧书签使用旧页面可产生的字段，延迟/503/401/403
拦截现有 GET，不新增产品路由/探测入口，不通过禁用按钮合成不可发生的重复动作。
双击防重由真实 userEvent 双击验证；不是固定全页 GET 次数门禁。

| cwd / 命令 | 实际结果 | 本地原始日志（下述 evidence/logs/ 内） |
|---|---|---|
| 根：`python3 scripts/check_governance.py`、`git diff --check` | 通过 | `governance-handoff.log` / `diff-check-handoff.log` |
| web：Required Tests 六文件命令，附加 `TaskRefreshControl.test.tsx`、`TaskItemRecoveryPanel.test.tsx` | 8 文件、99 测试通过；无 skips；10.15s | `task-units-complete.log` |
| web：`npm run typecheck`、`npm run lint`、`npm run build` | 均 exit 0 | `task-typecheck-reviewed.log`、`task-lint-handoff.log`、`task-build-complete.log` |
| web：实际变更 TS/TSX/E2E 文件 `npx prettier --check` | 全部通过 | `task-format-reviewed.log` |
| web：`npm run test:e2e -- tests/e2e/task-center-layout.spec.ts` | 7 通过；无 skips；5.1s | `task-layout-complete.log` |
| web：Required real-Python grep，附加 `server-side filtered selection\|a mixed run never\|a reopened mixed saved batch\|the eight views and the exact\|dated views and 21-file` | 14 通过；无 skips；20.5s | `task-python-complete.log` |

最后一组包含 Required 的全部 time filter / refresh feedback / live inventory 用例；增加的五项是
本次删除旧控件后直接受影响的列表、混合类型、保存批次只读和 21 文件证据回程。最终三组测试
共 35.75s；包含先前失败和静态检查的验证累计约 3–4 分钟，本轮读码实施/交接超过 12 分钟，
验证占比低于 50%。没有运行全仓 Python/Web/E2E、发布矩阵或恢复执行全链路。

证据目录：`.git/validation-evidence/patch-20261030-1/`（本机 ignored，不声称远端可访问）。
`layout-final/` 留存桌面/390px 列表、详情及手动 busy 截图，已实看；`python-final/` 为最终
隔离 Python 运行产物，`logs/` 保留最终和前轮原始结果；`identity.json` 记录身份。
构建 JS `web/dist/assets/index-BLEu7AnR.js` SHA256：
`b59d7e5149bf1f78a956a6db10c92066318658a66479e073d32bdfeda8d10864`；
lockfile SHA256：`76349eb03577cf68e9aa9715f1eda5ec066f4e09eb92eb3bb471fc71d77ec58f`。

前轮实际失败保留：新增测试用了 Testing Library 不支持的 exact 参数；旧 Files 回程断言还期待
status、窄屏用例漏走菜单、空列表误期待不存在的分页文字、503 误期待共享异常标题而非现有
Operations unavailable。均按实际界面/类型修正后执行相关检查；没有删除权限/副作用断言或加重试。
曾并行运行两个 Playwright 命令导致共用 test-results 的 ENOENT 证据冲突，之后全部串行运行；
该冲突轮不作为通过依据。

剩余限制：B 尚未独立复核 AC/执行其额外后端时间游标及 format:check 门禁；无全站/外部服务、
长时耐久或发布验证。构建仍报告大于 500kB chunk 提示，单元环境有 scrollTo 未实现诊断；
对应命令均正常完成。本轮没有证明其为父版本问题，也未扩范围处理。Task 不自签 PASS，
不推送、不发布，不启动其他角色/agent。

## B Review Result

尚未复核；规划及预检不是 PASS。B 在收到精确 checkpoint 后审查完整 Base..Head，
给出 PASS 或 FIX REQUIRED；独立修正完成后恢复 compact NO ACTIVE IMPLEMENTATION TASK。
