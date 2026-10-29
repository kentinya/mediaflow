# Task PATCH-20261029-2 — 任务中心布局与普通文件导航修正

Authority: 用户授权的三项既有界面修正；生命周期、测试与独立审查按
[Development Workflow](docs/development-workflow.md)。相关已验收 Slice38/42/45/46 仅为基础引用，
不是 Parent，不重开或更改其验收、边界、Roadmap 或 Progress。

```text
Task ID: PATCH-20261029-2
Task Type: STANDALONE MINOR BUG
Parent Slice: NONE
Status: READY FOR B REVIEW
Task Base: 8ea5cbbd4914316deadda8297e1bdf38dd9d8eeb
Difficulty: Medium
Test Level: T3
Planner / Reviewer: B
Development Authorization: USER-ACTIVATED TASK — 2026-10-29
Next Action: B REVIEWS THIS TASK AND DECIDES PASS / FIX REQUIRED
```

## Activation

用户于 2026-10-29 明确要求“激活 Task”，本计划成为当前正式独立 Task，状态为 PLANNED，
可由 Developer 按既定边界接手。本次只完成激活，尚未启动产品实现、B Review 或其他代理。

激活前工作区：`main`，HEAD `66fcafba5916c2123cd903ff6ced76f9dd84ae63`；已跟踪文件干净。
已核对原 Task Base 至该 HEAD 仅有两次 `TASK.md` 规划提交，没有产品或测试变更；保留原
Task Base、三项目标、范围、验收及 Medium/T3，不重新定 Base。既存未跟踪文件继续保留。
激活前治理预检：`python3 scripts/check_governance.py` — PASS。

此前独立 `PATCH-20261029-1` 的 PASS 与精确审查记录保留在
`f1463e1d9e16355a6f44fa6fba9c3bbda9efb193:TASK.md`。Slice46 继续 PASS / CLOSED；
本次不修改 SLICE/Roadmap/Progress 或此前验收事实。

## Goal

用户打开任务中心时，主内容区只有一个清晰的页面标题；标题、边距和列表的空间分配与
当前媒体库页协调。用户从任务中心点击共享侧栏“文件”时，进入普通资源库文件页，不出现
“返回任务中心”。显式整理流程和已有任务/准备记录深链仍保留其精确定位与返回能力。

适用：`UX-001/002/007`、`V2-UX-001–004`、`V2-SHELL-001`、`V2-AUTH-001–003`、
`V2-OPS-006/008/009/014–016`；完整旅程参见
[Product Experience](docs/product-experience.md#tasks-results-and-per-item-recovery) 的任务与恢复、
Real Storage Files 和 V2 Operator Web 章节，以及
[任务中心页面规格](docs/task-center-page-spec.md#2-页面结构与共有行为)、
[媒体库视觉规格](docs/media-library-page-visual-spec.md)。现有八视图的组成与交互继续适用；
本次只校正重复层级、空间利用和普通侧栏导航，不另造页面或业务流程。

- 入口：任务中心默认/筛选/选中任务页面，以及这些页面的共享侧栏“文件”。
- 可见状态与动作：保留统计、八个标签、筛选、分页、详情/问题文件和刷新；普通切页直接
  到文件浏览，显式任务深链继续其原有流程。
- 成功：桌面可直接阅读任务、状态和进度，窄屏控制可达；普通文件页没有多余返回入口。
- 失败与恢复：保留加载、空列表、读取失败、401/403、失效任务/上下文的既有解释与合法
  恢复动作。刷新/重新连接恢复合法 URL 状态，不自动创建、取消、重提或执行工作。

## Observed gap and root cause

已在当前运行页面复现，并与本 Base 源码交叉确认：

1. `AppShell.tsx` 输出 `.mf-page-context` 的“任务中心”，`OperationsLanding.tsx` 再输出
   页面标题；现有 CSS 只对 Files/Rules 等已有专用布局隐藏这层提示。
2. `styles.css` 给非 Files 主容器 `28px 4vw` 留白，任务中心又叠加
   `28px 32px` 内边距与 `1360px` 最大宽度；列表 layout/main 各再缩进 `20px`。
   媒体库页采用约 `23px/18px` 左右边距、`30px/36px` 标题字号/行高。任务中心的重复
   标题、统计说明、视图说明和换行筛选把列表向下挤压；业务名称与范围重复长路径，表格
   自动列宽又挤走状态、进度与时间。
3. `AppShell.tsx` 把任务中心列表状态自动放入侧栏 Files 链接的 `returnOps`；默认筛选也
   产生 `?returnOps=`。`StorageFilesPage.tsx` 对非 null 值显示返回入口，空串也算来源。
   `AppShell.test.tsx` 和 `tests/e2e/operations.spec.ts` 当前明确断言此普通导航行为，需按
   本轮授权修正；显式上下文的解析与整理续作契约继续保留。
4. Files 的来源上下文目前用 `useMemo(..., [])` 在挂载时读取。实现时须覆盖同一 Files
   路由内点击侧栏清除来源的情况，避免地址已清除而页面仍显示旧返回入口。

规划前工作区：`main`，HEAD 为上述 Task Base；已跟踪文件干净。已有未跟踪的本地日志、
`.DS_Store`、`15`、自动化参考图与 imagegen 压缩包均保留，不纳入 Task checkpoint。
治理预检已运行 `python3 scripts/check_governance.py`：PASS。

## Implementation Scope

主要修改面：`web/src/shared/ui/AppShell.tsx`、`styles.css`、
`web/src/features/operations/OperationsLanding.tsx`，以及必要的 Files 路由上下文消费和相关测试。
导航 helper 只在消除确实失去消费者的 Shell 逻辑时做最小调整，保留显式深链消费者。

1. 先固定回归场景：默认/筛选/选中任务 → 侧栏 Files、带合法来源的 Files → 侧栏 Files，
   以及显式来源深链 → 整理流程 → 原任务。把普通切页和显式流程的预期分开断言。
2. 对任务中心采用单一标题层级，参考当前媒体库的标题尺度、内容起点与空间分配，减少
   多层留白造成的无意义缩进。具体内边距、最大宽度和详情比例由实现按实际效果调整，
   不要求删除某条 CSS 或逐像素复制媒体库。保留四张统计卡、八个标签、筛选、列表和
   详情查看/关闭/返回能力；说明文字可收紧间距、压缩表达或放入可访问的说明位置，
   保留必要的计数含义与错误解释。
3. 约束业务名称/范围的列宽与长文本展示，给阶段、进度、状态和时间稳定的阅读空间。
   允许省略展示、受控换行或详情揭示，但鼠标和键盘均能取得完整原文；任务选择仍使用
   原 run ID，不能裁改真实路径、名称或后端投影来迁就布局。窄屏只在表格/标签内部滚动。
4. 共享侧栏 Files 使用普通页面导航，不从任务中心生成或转带 `returnOps`，包括当前页面
   已有该参数时再次点击侧栏。Files 可见来源随路由已提交状态同步清除，避免挂载缓存残留。
   显式任务/准备/整理链接携带的合法上下文继续解析、传递和返回；不要全局删除 helper、
   现有返回按钮或 URL 验证，也不新增返回开关、会话标记或业务状态。
5. 更新受到本次普通导航预期影响的测试，补足真实布局、长路径与同路由重新进入用例。
   采用现有本地 fake/临时 Python harness；样本来自隔离 fixture，不使用用户媒体或运行库。

## Acceptance Criteria

- [ ] 主内容区的页面标题与位置提示合计只有一处可见的“任务中心”标题文字，且保留语义标题；
      侧栏入口与浏览器页签仍正常。八个视图以及加载、空列表、读取失败状态没有重复
      位置提示或其空档。断言必须能检出当前 Base 中额外的 `<p>` 小字，不能只数 heading；
      允许隐藏该提示，不要求从 DOM 删除，也不把侧栏的同名入口计入重复。
- [ ] 在 `1536×1024`、100% 缩放、scale 1 下，与同环境的媒体库截图对照，标题层级、
      内容边界和留白尺度协调，允许合理差异。相同代表性数据下，与 Base 对比可见列表
      起始位置上移、首屏内容利用改善；默认无详情时首屏能读到完整任务行及其状态、进度，
      不靠缩小到难读的字体或隐藏必要信息满足。样本覆盖短范围、较长的连续无空格路径、
      同前缀不同结尾的路径，数量足以检查列表与滚动，不规定固定样本数或首屏行数。
- [ ] 在上述参考桌面视口、默认无详情的列表中，长路径不会把阶段、进度、状态和时间
      挤出可视列表宽度；业务名称与范围两列仍可辨认，完整原文可通过 hover/focus 或
      现有详情读取，选中的仍是原任务。
- [ ] `1280×800` 及 `390×844` 下可用；八标签、筛选、分页、详情关闭/返回和问题处理
      入口均可通过键盘操作，焦点可见且不遮挡。允许表格/标签区域内部有界横向滚动，
      页面本身不因长路径或筛选控件横向溢出；不要求窄屏满足桌面首屏行数。
- [ ] 默认、带筛选/分页、选中详情的任务中心点击侧栏 Files 后，URL 无 `returnOps`，
      文件页无“返回任务中心”；已有合法来源的 Files 页面再点侧栏 Files 也同步清除。
      普通从媒体库等页面进入 Files 的行为继续成立，不携带任务筛选或猜测任务/库。
- [ ] 显式合法来源深链仍提供其原有返回动作；整理/准备/确认及已受理任务可回到准确的
      任务和合法列表上下文。刷新后重新连接不丢失此类显式状态；无效/超长/越界来源继续
      按既有规则降级，不能据此跳到其他页面或获得权限。
- [ ] 浏览、切页、刷新只进行必要读取；不提交业务命令，不启动发现/元数据查询或 Storage 变更。
      计数和八视图成员关系的语义、四类恢复、已有持久结果和权限保持原有契约。
      固定对照资源库 Files 与媒体库的标题、内容边界和控件可读性；若修改通用主容器或
      全局标题规则，再对 Rules 与 Automation 做同类布局冒烟检查。记录实际受影响选择器
      与检查页面，不把“所有 Shell 页面不回退”扩成全站业务验收。

## Required Tests

按 [workflow §6](docs/development-workflow.md#6-test-levels) 分工。以下为实现后的计划，
不是本次规划已运行的结果。Developer 完成受影响验证后交候选，B 独立审查完整 Base..Head。

**Developer — affected tests**

仓库根：`python3 scripts/check_governance.py`、`git diff --check`。
在 `web/` 执行：

```sh
npm run test -- run src/shared/ui/AppShell.test.tsx src/shared/navigation/operations-return.test.ts src/routes/router.test.tsx src/features/operations/OperationsInventory.test.tsx src/features/library/StorageFilesPage.test.tsx src/features/operations/OrganizeRouter.test.tsx
npm run typecheck
```

覆盖普通导航去除来源、同路由上下文清除、显式整理来源保持、URL 验证、标题与列表交互。
对主要受影响文件执行以下检查；其他实际修改的 Web 文件补入对应命令并记录：

```sh
npx eslint src/shared/ui/AppShell.tsx src/features/operations/OperationsLanding.tsx src/features/library/StorageFilesPage.tsx src/shared/ui/AppShell.test.tsx src/features/operations/OperationsInventory.test.tsx src/features/library/StorageFilesPage.test.tsx tests/e2e/task-center-layout.spec.ts tests/e2e/operations.spec.ts
npx prettier --check src/shared/ui/AppShell.tsx src/shared/ui/styles.css src/features/operations/OperationsLanding.tsx src/features/library/StorageFilesPage.tsx src/shared/ui/AppShell.test.tsx src/features/operations/OperationsInventory.test.tsx src/features/library/StorageFilesPage.test.tsx tests/e2e/task-center-layout.spec.ts tests/e2e/operations.spec.ts
```

CSS 在 jsdom 不生效，不能把组件断言当作布局证明；使用构建产物运行聚焦浏览器用例：

```sh
npm run build
npm run test:e2e -- tests/e2e/task-center-layout.spec.ts
npm run test:e2e -- tests/e2e/operations.spec.ts --grep 'inventory shows the run list'
```

`task-center-layout.spec.ts` 为本 Task 新增的聚焦浏览器用例，使用既有 fake server 与
必要的只读响应 fixture，验证可见重复提示消失、布局改善、长路径列宽、桌面/窄屏和普通/
显式来源导航。布局以实际几何、溢出、可见性及截图为依据，不锁死像素、样本/行数或
CSS 实现；标题检查不能只统计 heading。若改动共享路径组件，额外运行其直接受影响测试。

**B — acceptance and regression**

在精确候选上检查 scope、diff、预检及 Developer 结果；独立复现原三项问题的消失、同路由
来源清除与显式流程保留。在 `web/` 执行正常质量门禁和有界受影响浏览器回归：

```sh
npm run typecheck
npm run lint
npm run format:check
npm run build
npm run test:e2e -- tests/e2e/task-center-layout.spec.ts
npm run test:e2e -- tests/e2e/operations.spec.ts --grep 'inventory shows the run list|task-center views stay keyboard operable|the selected run detail is|Operations failures stay inside'
npm run test:e2e -- tests/e2e/manual-organize.spec.ts --grep 'reconciles a lost admitted response and selects its durable Operations run'
npm run test:e2e -- tests/e2e/deep-link.spec.ts --grep 'refresh keeps memory-only semantics and reconnects to the same supported path'
```

以上使用构建产物和既有本地 fake API，分别覆盖本轮布局/导航、列表与详情的可达性、
显式来源链路的准确任务回读，以及重新连接。相关旧测试若锁定了本轮明确允许调整的
详情比例等实现细节，应改为检查查看/关闭/返回、可读性与焦点可达，不保留过时的几何断言。
不要求完整运行 manual-organize/deep-link 文件或 Python 视觉脚本中的问题分页、Worker
分析/执行全链。需要新增实际影响范围之外的回归时，B 先说明候选引入的具体风险。

B 打开并审阅实际截图：相同数据/视口下 Base 与候选的任务中心布局、当前媒体库对照、
长路径列表、选中详情、空/读取失败和窄屏/键盘状态；八个标签的可达性及共享标题层级
仍需覆盖，不扩成四类业务恢复全链。按上述受影响规则安排 Files/Rules/Automation 对照，
不重新验证其文件操作或配置发布。可复用聚焦用例的相同候选截图；保留截图/原始日志于
workflow 规定的稳定忽略位置。脚本退出码或孤立的行数指标不能代替视觉验收。

本 Task 不触及 Python 业务、Storage、配置激活、schema、权限或并发执行；不要求全量
Python/Web 单元/E2E、Docker 或 wheel 发布矩阵。发现实际跨边界风险时由 B 重评，不能
扩张实现范围或把全量验收交给 Developer。

## Non-goals

- 不新增/重开 Slice，不改 SLICE/Roadmap/Progress、既有验收事实或全站视觉系统。
- 不改业务接口、投影语义、任务计数/状态、执行/恢复/授权、库配置、媒体或数据库。
- 不删除显式整理流程的上下文/返回功能，不恢复任务中心新建入口或全局普通操作中心。
- 不改媒体库业务功能；媒体库只作为当前标题、边距和共享 Shell 的对照。
- 激活不自动启动其他角色或代理；推送、部署和范围外工作不在本 Task 授权内。

## Developer Completion Report

**READY FOR B REVIEW — 实施完成，未自行声明 Task PASS 或 Slice CLOSED。**

- Task Base：`8ea5cbbd4914316deadda8297e1bdf38dd9d8eeb`。
- 产品/测试 checkpoint：`19ef96e7e2c77ec7e5507ad41a5b9bb7db75a90b`（7 文件）。
- 本报告提交为 report-only successor；B 审查完整 Base..本报告 Head，产品/测试源码身份以上一
  checkpoint 为准。
- 未 push、未部署；未修改 SLICE/Roadmap/Progress 或既有验收事实。既存 untracked
  OS/log/参考图/测试产物保持原状且未纳入 checkpoint。
- 未改 Python 业务、Storage、配置激活、schema、权限或并发执行。

### 已实施修复

1. `AppShell.tsx`：`/operations` 不再渲染共享 shell 的 `.mf-page-context` 位置提示，页面保留
   唯一语义 `<h2>任务中心</h2>`；浏览器页签与侧栏入口不变。共享侧栏 Files 一律使用普通页面
   导航（`search={{}}`），删除由任务中心列表状态生成/转带 `returnOps` 的 Shell 逻辑。
   任务/准备/整理深链自身携带的合法来源上下文、返回按钮与 URL 验证均保留。
2. `StorageFilesPage.tsx`：来源上下文改为读取 router 已提交 search（`useSearch`）并继续经
   `readOperationsReturnContext` 校验，不再用挂载时 `window.location` 快照；同一 Files 路由
   再点侧栏 Files 会同步清除来源与可见返回入口。显式合法深链仍显示准确的任务中心返回。
   为通过 React Compiler lint，补充既有 setState 的稳定依赖，不改变清理语义。
3. `OperationsLanding.tsx` + `styles.css`：任务中心使用与媒体库 Files 一致的内容边界（无外层
   二次 inset）、30/36 标题、紧凑统计/视图说明/筛选；表格改为固定列布局，业务名称/范围可省略
   但仍保留完整 `title`、可访问名称与现有详情全文，阶段/进度/状态/时间有独立稳定空间。
   选中详情时列表列允许换行，不把列表/详情挤出既有布局。删除/调整了重复的九视图过期注释，
   视图说明仅收紧表达，保留原计数和失败解释。
4. 测试：更新 `AppShell.test.tsx` 与 `operations.spec.ts` 的旧普通导航预期；新增
   `task-center-layout.spec.ts`，用既有 Node fake API 的只读 `/operations/runs` 响应补充代表性
   short/long/same-prefix scope，覆盖 1536/390 布局、长路径、八视图键盘、详情关闭/返回、
   普通/筛选/选中导航及显式来源清除。未新增产品入口或后端接口。

### 实际验证

| 命令（cwd） | 实际结果 |
| --- | --- |
| `python3 scripts/check_governance.py`（repo root） | PASS |
| `git diff --check`（repo root） | PASS |
| `npm run typecheck`（web/） | PASS |
| `npm run test -- run src/shared/ui/AppShell.test.tsx src/shared/navigation/operations-return.test.ts src/shared/navigation/destination-model.test.ts src/routes/router.test.tsx src/features/operations/OperationsInventory.test.tsx src/features/library/StorageFilesPage.test.tsx src/features/operations/OrganizeRouter.test.tsx` | 7 files / 154 tests passed |
| `npx eslint` 上述源码/测试及 `tests/e2e/task-center-layout.spec.ts`、`tests/e2e/operations.spec.ts` | PASS |
| `npx prettier --check` 上述源码/CSS/测试 | All matched files use Prettier code style |
| `npm run build`（web/） | PASS；仅既有 Vite chunk-size warning |
| `npm run test:e2e -- tests/e2e/task-center-layout.spec.ts` | 5/5 passed |
| `npm run test:e2e -- tests/e2e/operations.spec.ts` | 25/25 passed |
| `npm run test:e2e -- tests/e2e/manual-organize.spec.ts --grep 'reconciles a lost admitted response and selects its durable Operations run'` | 1/1 passed |
| `npm run test:e2e -- tests/e2e/deep-link.spec.ts --grep 'refresh keeps memory-only semantics and reconnects to the same supported path'` | 1/1 passed |

候选截图和原始日志保存在本地稳定忽略位置
`.git/validation-evidence/19ef96e7e2c77ec7e5507ad41a5b9bb7db75a90b/developer-patch-20261029-2/`
（1536 任务中心、390 列表/详情、长路径详情）。实际截图使用构建产物与本地 fake API。

### 剩余风险与 B 交接

- Developer 只执行 Task 指定的受影响验证；完整 Web/Python/E2E、真实视觉矩阵、Docker/wheel
  发布验收仍由 B 在精确候选上执行。未把全量门禁交回 Developer。
- jsdom 仍输出既有 `window.scrollTo not implemented` 提示；Vite 仍有既有 chunk-size warning；
  未删除、隐藏失败或放宽断言。
- 新聚焦用例只改写既有 operations/runs 响应中的 `source_scope` 与合法阶段/进度字段，不构造
  产品不存在的入口；解析器仍按真实严格契约校验。
- B 应重新评估独立 minor bug 的完整范围，决定 PASS / FIX REQUIRED；Developer 不规划下一
  Task、不关闭 Slice、不自动 push/发布。

## B Review Result

```text
Reviewed: PENDING
Decision: PENDING
Candidate: 19ef96e7e2c77ec7e5507ad41a5b9bb7db75a90b
Acceptance runs: not yet run by B
Task blockers: none recorded by Developer
Next: B reviews Task Base..candidate plus this report-only successor and runs assigned acceptance
```
