# NO ACTIVE IMPLEMENTATION TASK

B independently reviewed standalone `PATCH-20261029-1` on 2026-10-29: **PASS**.
Authorized bug acceptance is complete; no Task blocker or additional Task remains.

- Task Type / Parent: `STANDALONE MINOR BUG` / `NONE`.
- Reviewed Base: `a9d5c5f1914f5590f0ebe1f60e58d7f91ca56381`.
- Reviewed Head: `608aeea61fc00b5dcf1dacc07e37b6bb4c39b644` (complete 14-file range).
- Product/test checkpoint: `36e4634ea3a6b6ccb339aaa62f265f464e5f70b3`; the reviewed
  successor changes only the Developer report. Task/Developer handoff remains at
  `608aeea61fc00b5dcf1dacc07e37b6bb4c39b644:TASK.md`.
- B completion checkpoint: `f1463e1d9e16355a6f44fa6fba9c3bbda9efb193`; its `TASK.md`
  retains the review summary, actual validation results and limitations. Detailed history stays in Git.
- Local raw logs, exact commands/timing, artifact hashes and acceptance mapping (local only):
  `.git/validation-evidence/608aeea61fc00b5dcf1dacc07e37b6bb4c39b644/b-patch-20261029-1/README.md`.

Slice46 remains **PASS / CLOSED** with its original Base, accepted Implementation Head,
five outcomes and AC-1–18 unchanged. [SLICE.md](SLICE.md), [Roadmap](docs/roadmap.md) and
[Progress](docs/progress.md) are not modified by this independent bug completion.

Next: **NO ACTIVE IMPLEMENTATION TASK**. The user requested the planning-only draft below;
implementation is not authorized. Any future large Slice still requires A's separate scope selection.

## Planning-only draft — PATCH-20261029-2

本轮授权：用户在只读调查后选择一个独立小修 Task，并要求“规划 Task”。本草案只规划，
不启动实现、不启动其他角色或代理。得到实现授权后，再用本计划替换顶部无活动实现通知并
复核 Base 与工作区；如已有其他产品变更，先评估影响，不静默改写本草案的 Base。

### Task — 任务中心布局与普通文件导航修正

Authority: 用户授权的三项既有界面修正；生命周期、测试与独立审查按
[Development Workflow](docs/development-workflow.md)。相关已验收 Slice38/42/45/46 仅为基础引用，
不是 Parent，不重开或更改其验收、边界、Roadmap 或 Progress。

```text
Task ID: PATCH-20261029-2
Task Type: STANDALONE MINOR BUG
Parent Slice: NONE
Status: PLANNED
Task Base: 8ea5cbbd4914316deadda8297e1bdf38dd9d8eeb
Difficulty: Medium
Test Level: T3
Planner / Reviewer: B
Development Authorization: PLANNING ONLY
```

### Goal

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

### Observed gap and root cause

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

### Implementation Scope

主要修改面：`web/src/shared/ui/AppShell.tsx`、`styles.css`、
`web/src/features/operations/OperationsLanding.tsx`，以及必要的 Files 路由上下文消费和相关测试。
导航 helper 只在消除确实失去消费者的 Shell 逻辑时做最小调整，保留显式深链消费者。

1. 先固定回归场景：默认/筛选/选中任务 → 侧栏 Files、带合法来源的 Files → 侧栏 Files，
   以及显式来源深链 → 整理流程 → 原任务。把普通切页和显式流程的预期分开断言。
2. 对任务中心采用单一标题层级与页面边距，参考当前媒体库标题尺度和内容起点；消除双重
   外层留白与列表重复缩进。保留四张统计卡、八个标签、筛选、列表和现有详情布局。
   说明文字可收紧间距、压缩表达或放入可访问的说明位置，保留必要的计数含义与错误解释。
3. 约束业务名称/范围的列宽与长文本展示，给阶段、进度、状态和时间稳定的阅读空间。
   允许省略展示、受控换行或详情揭示，但鼠标和键盘均能取得完整原文；任务选择仍使用
   原 run ID，不能裁改真实路径、名称或后端投影来迁就布局。窄屏只在表格/标签内部滚动。
4. 共享侧栏 Files 使用普通页面导航，不从任务中心生成或转带 `returnOps`，包括当前页面
   已有该参数时再次点击侧栏。Files 可见来源随路由已提交状态同步清除，避免挂载缓存残留。
   显式任务/准备/整理链接携带的合法上下文继续解析、传递和返回；不要全局删除 helper、
   现有返回按钮或 URL 验证，也不新增返回开关、会话标记或业务状态。
5. 更新受到本次普通导航预期影响的测试，补足真实布局、长路径与同路由重新进入用例。
   采用现有本地 fake/临时 Python harness；样本来自隔离 fixture，不使用用户媒体或运行库。

### Acceptance Criteria

- [ ] 主内容区仅显示一个可见“任务中心”页面标题；侧栏入口与浏览器页签仍正常。
      八个视图以及加载、空列表、读取失败状态都没有重复标题或多余标题空档。
- [ ] 在 `1536×1024`、100% 缩放、scale 1 下，任务中心标题的字体尺度、顶部起点、
      内容左右边界与当前媒体库页一致；移除页面宽度限制和多层留白造成的无意义缩进。
      使用至少 5 条代表性短/长路径 fixture，默认无详情时首屏至少显示 3 条完整任务行。
- [ ] 桌面默认列表中长路径不会把阶段、进度、状态和时间挤出可视列表宽度；业务名称与
      范围两列仍可辨认，完整原文可通过 hover/focus 或现有详情读取，选中的仍是原任务。
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
      计数、八视图成员关系、四类恢复、已有持久结果和权限不变。Files/媒体库及其他共享
      Shell 页面不因新增样式出现标题、边距、控件可读性回退。

### Required Tests

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
```

`task-center-layout.spec.ts` 为本 Task 新增的聚焦浏览器用例，使用既有 fake server 与
必要的只读响应 fixture，验证标题/边距/首屏行、长路径列宽、桌面/窄屏和普通/显式来源导航。
不新增与实现镜像的 CSS 字符串测试。若改动共享路径组件，额外运行其现有直接受影响测试。

**B — acceptance and regression**

在精确候选上检查 scope、diff、预检及 Developer 结果；独立复现原三项问题的消失、同路由
来源清除与显式流程保留。在 `web/` 执行正常质量门禁和有界受影响浏览器回归：

```sh
npm run typecheck
npm run lint
npm run format:check
npm run build
npm run test:e2e -- tests/e2e/task-center-layout.spec.ts tests/e2e/operations.spec.ts tests/e2e/manual-organize.spec.ts tests/e2e/deep-link.spec.ts
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-task-center-visual.python.spec.ts
```

最后一项使用既有临时 SQLite/本地媒体/Python API harness，核对八视图、问题文件、显式
整理摘要、重新连接与读取失败的真实集成；不是生产环境验证。B 打开并审阅实际截图：
桌面任务中心与媒体库并排比较、长路径列表、选中详情、空/读取失败和窄屏/键盘状态。
现有视觉脚本还需补上本轮媒体库对照及长路径证据；可复用聚焦用例的相同候选截图。
保留截图/原始日志于 workflow 规定的稳定忽略位置，不能仅凭脚本退出码宣布视觉通过。

本 Task 不触及 Python 业务、Storage、配置激活、schema、权限或并发执行；不要求全量
Python/Web 单元/E2E、Docker 或 wheel 发布矩阵。发现实际跨边界风险时由 B 重评，不能
扩张实现范围或把全量验收交给 Developer。

### Non-goals

- 不新增/重开 Slice，不改 SLICE/Roadmap/Progress、既有验收事实或全站视觉系统。
- 不改业务接口、投影语义、任务计数/状态、执行/恢复/授权、库配置、媒体或数据库。
- 不删除显式整理流程的上下文/返回功能，不恢复任务中心新建入口或全局普通操作中心。
- 不改媒体库业务功能；媒体库只作为当前标题、边距和共享 Shell 的对照。
- 不在本轮规划中实现产品、运行实现验收、自动调用其他角色、推送或部署。

### Developer Completion Report

未开始；实现授权与 Developer 受影响测试结果待后续填写。

### B Review Result

未提交实现候选；尚未开展 B Review，不作 PASS/FIX REQUIRED 决定。
