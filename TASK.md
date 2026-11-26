# Task 59.5 — 任务中心按问题文件直达原位恢复

Next Action: DEVELOPER IMPLEMENTS THE TASK CENTER PROBLEM-FILE LIST

```text
Task ID: 59.5
Task Type: SLICE
Parent Slice: 59
Status: PLANNED
Task Base: 5d20ae33c7b5e1d5b84fc908c3d1204084005b72
Difficulty: High
Test Level: T3
Planner / Reviewer: B
```

## 目标

在任务中心选择「需要处理」，直接看到按原任务分组的四类问题文件。按类型筛选或点按一行，
在原任务详情中直接展开对应文件和合法恢复操作。关闭详情回到原列表位置。按提交版
[SLICE.md](SLICE.md) 的 RO-5、AC-07，以及 RO-4、AC-04/05/06 涉及的入口和原位恢复要求，
对齐已批准离线稿的布局、信息层级和操作位置。

当前 `OperationsLanding` 的首层使用八个同级入口，「需要处理」按任务显示，再打开该任务和
指定类型的问题文件面板。现有任务总览提供任务数和分类型文件数，`/runs/{id}/problem-items`
按单个任务和类型读分页。聚合「问题文件」需要覆盖完整授权范围，统一返回列表、去重计数和分页事实。

## 实施步骤

1. 使用现有 admitted-organizing 总体和四类问题谓词。复用可用的读取字段。补充兼容当前客户端的
   有界只读投影，以同一读取快照返回页面、聚合去重数和各类文件数。以持久 Task/TaskItem 标识
   确定分组和文件，来源类型、分类依据、当前阶段及可显示的原因取自持久记录。按完整的授权和
   创建日期范围统计。文件翻页使用稳定顺序及绑定当前主体、范围、日期、类型的有向游标。
2. 首层展示「全部任务」「进行中」「需要处理」「已结束」。按批准稿保留任务统计、创建日期和
   三个普通任务视图。进入「需要处理」默认全部，提供「全部」「识别」「元数据」「分类」「冲突」
   五个轻量筛选和对应文件数。元数据候选及作品搜索修正共用元数据筛选。问题文件按原任务归组，
   组头显示任务、来源类型和「查看任务详情」，整行显示文件名、类型、简短原因、当前状态和进入提示。
   支持键盘、触屏、长文件名、窄屏，以及加载、空结果、读失败、重读和双向分页。
3. 用文件行的准确任务和条目标识打开现有详情，直接展开同一文件。组头动作打开同一任务的普通详情。
   复用已通过的文件行、决定表单和续作动作，按 AC-06 核对四类入口、原位等待和同页新计划摘要的
   层级及位置。将筛选、日期、分页和需要恢复的入口绑定既有返回上下文。关闭回原滚动位置和焦点，
   原行已结算时回最近的可用组头或列表控件。保留八种查询语义和合法深链，包括原类型和精确文件定位。
4. 用同一 Task/TaskItem 的真实读回更新影响到的列表和计数。保持待决定、已保存待分析、分析中和
   待确认的真实归属，换类或结算后按当前证据刷新。保留不受影响的兄弟文件、选择位置及原有详情
   续作资格。普通首轮待确认手动任务保持在当前流程视图，纯技术终结保持原事实详情。

## 验收

- 桌面和 390 px 对照批准稿，从任务中心进入「需要处理」。走通五个筛选、日期范围、统计卡片、
  组头详情、文件整行和空态。检查长文件名、焦点、Enter／空格、触屏、窄窗口和读失败后重读。
- 真实手动和自动任务覆盖多任务、多文件和同一文件跨类。完整范围内单任务只计一次，聚合文件按
  原任务与条目去重，类型按实际成员分别计数。验证跨页、日期筛空、旧游标、权限边界和完整总体。
- 四类分别从实际问题文件进入对应详情和文件证据。验证决定、分析、必要的新方案摘要、一次明确确认
  及同任务结果。包含元数据候选和搜索修正。核对打开和确认前零媒体变更，确认后只有明示效果，
  其他文件的原结果和合法操作可独立读取。
- 核对关闭、刷新和浏览器返回能恢复对应类型、日期、页、滚动与焦点。原行换类、结算或读取失败
  时验证邻近入口及可采取的下一步。验证既有合法深链、任务详情两页签和「继续整理」仍可达。

## 测试

Developer 在仓库根运行治理、Git 空白及受影响的仓库检查。修改只读投影时，在既有任务中心测试中
覆盖总体、权限、重叠归属、快照、分页及合法／无效输入。Web 覆盖选择、筛选、聚合结果、回落和原位恢复。

```sh
python3 scripts/check_governance.py
git diff --check
.venv/bin/python -m unittest discover -s tests -p test_operations_task_center.py
.venv/bin/ruff check mediaflow/interfaces/service_api.py mediaflow/infrastructure/sqlite_runtime.py tests/test_operations_task_center.py
cd web
npm run typecheck
npm run test -- run src/features/operations/OperationsInventory.test.tsx src/features/operations/RunDetailTabs.test.tsx src/features/operations/TaskItemRecoveryPanel.test.tsx
npm run build
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts --grep 'Task59.5|native recognition recovery|native Metadata|native Classification|native conflict recovery|dated views and 21-file'
```

B 独立运行上述适用组、Web Lint/格式和
`npm run test:e2e -- tests/e2e/operations.spec.ts tests/e2e/task-center-layout.spec.ts`。
以真实 API、SQLite、Worker 和临时媒体根从原入口复验手动、定时或运行一次的四类恢复。
保存 1440、390 px 和适用矮窗口的对照证据，核对确切消费的 Task/条目、审计、允许的文件效果、
未知效果与兄弟结果。若任务满足剩余结果，按 Slice 最终验证收集全部已审范围的证据，再交独立 A 终验。

## 范围边界

范围限于批准的任务中心列表、问题文件读取及与既有详情的衔接。沿用当前页壳、Files 整理流程、
详情布局、全部任务/运行中/已结束的任务语义、已有路由和写入合约。续作采用既有 Task、决定、
方案、执行权限和 Result，遵循 Slice 的固定配置、作用域、审计与不重放约束。

## B 复核与 Slice 59 交接

- **Task 59.4 · PASS。** 独立复核 `bccfb2c4c014eb181d33ebc5b99140c1c722b446..5d20ae33c7b5e1d5b84fc908c3d1204084005b72`
  和完整 Slice 区间。首份摘要交接前新读原准备，核对当前可继续状态与原摘要关联。后台先持久取消后，
  两种响应顺序都进入同一取消终态。保留受理范围、进度、原摘要的只读入口与返回焦点。零分析和执行请求。
  正常方案进入概览，状态核对失败可原位重读，任务中心已就绪续作和准备中重开通过。
- 治理、两段区间空白检查、Web 类型、全量 Lint/格式、构建及测试夹具 Ruff 通过。组件 152 项、
  真实 Python/API/SQLite/Worker 浏览器 13 项通过。审阅了桌面、390 px 和矮窗截图。
  日志与候选截图在
  `.git/validation-evidence/5d20ae33c7b5e1d5b84fc908c3d1204084005b72/b-task59.4-review/`。
- Task 59.1 的通过记录见 `ae98701c:TASK.md`，59.2 见 `171b3de6:TASK.md`，59.3 见
  `0eca27e3:TASK.md`。Task 59.4 前序复核和验收范围见 `ab5eca3e:TASK.md`。
  对照当前代码与批准稿，RO-5 的问题文件导航、分组、统计和直达仍待交付，由本 Task 覆盖。
  Slice 59 仍为 `FIX REQUIRED`，全部合同结果与最终证据将交独立 A 终验。
