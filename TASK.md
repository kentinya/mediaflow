# NO ACTIVE IMPLEMENTATION TASK

独立修复 **PATCH-20261111-4 — 任务详情文件证据就地展开** 已由 B 于 2026-11-11
独立验收 **PASS**，授权目标全部满足，无剩余 Task 阻塞。

- Task Type: STANDALONE MINOR BUG；Parent Slice: NONE；Medium / T3。
- 完整审查范围：`42e666ca6c600cbaf93625dd5b389763c28ddade..ff8f3a699d2d6a1a27a2a221299cec9c616207ed`。
- [固定 B 最终审查、完整 Task 与开发／返工记录](https://github.com/kentinya/mediaflow/blob/5ad944f079f617036393440e8e6802d7ee6c7414/TASK.md#b-final-review--patch-20261111-4-pass)。
- [原规划与开发指导](https://github.com/kentinya/mediaflow/blob/4ec6cbf55fd936824790585d2280325b2cca36a6/TASK.md)。

现行呈现与输入保留规则见[任务正文与文件证据](docs/task-center-page-spec.md#current--任务正文与文件证据)，
完整用户旅程见[Product Experience](docs/product-experience.md#current--v2-dialog-readability-and-navigation-experience-slice50-pass--closed)。

验收计数、原失败及修正、截图／本地证据与验证限制保留在固定 B 审查中。
后续收尾与文档治理只改变文档，产品源码、测试和构建输入保持受验候选。

Slice54 继续 PASS / CLOSED；其 Base／接受 Head、SLICE／Roadmap／Progress 不变。
当前无活动实施 Task。

---

## 规划草案 — PATCH-20261111-5：任务详情整理入口收敛与提示留白

本次用户授权“规划一个单独修复Task”，仅授权规划。下列草案不激活实施，不授权产品
修改、其他代理、推送或部署。后续明确授权激活时，保留本 ID／Base／目标／范围，
再移除顶部无活动实施通知并进入正式 Task 生命周期。

Authority: 用户本轮独立修复范围；遵循
[Development Workflow](docs/development-workflow.md#31-independent-minor-bugs)。
上一独立修复 PATCH-20261111-4 的接受身份与固定 B 审查保留，不重开 Slice54。

```text
Task ID: PATCH-20261111-5
Task Type: STANDALONE MINOR BUG
Parent Slice: NONE
Status: PLANNED
Task Base: 436117e0588d30794dc3ee17d4fc1d0988a79442
Difficulty: Medium
Test Level: T3
Planner / Reviewer: B
Development Authorization: PLANNING ONLY — NOT AUTHORIZED FOR IMPLEMENTATION
```

### Goal and actual gap

任务中心 → 打开已整理成功任务详情 → 直接阅读流程、独立文件／附件结果与就地证据，
无需再进入另一个准备摘要或看到重新发起整理的重复入口。只有仍需确认／处理的工作
保留相应的现有合法摘要与继续动作。查看失败／取消／混合结果时，真实原因、阶段、
已完成／不确定效果及证据继续可读，不因删入口误报成功。

源码调查确认：

- `OperationsLanding.tsx` 的 `RunDetailFacts` 对所有非空 `filesPreparation` 展示
  “文件整理准备”。`continuable: false` 时固定显示结束说明、“查看只读摘要”和
  “从文件页重新发起”，未区分正常完成与异常结果，成功任务因此也带有重复操作区。
- “查看只读摘要”导航至 `/operations/organize/new`，`OrganizeCreationPage.tsx`
  将任务中心背景换成“整理所选文件／逐文件整理准备”接收页，再打开
  `ManualOrganizeDialog`，所以这不是保留原列表背景的就地查看。
- `StatusBanner` 以 `section.mf-status` 输出，公共样式原有 `padding: 16px 20px`；
  `styles.css` 的 `.mf-organize-dialog-body section` 优先级更高，将其覆盖为
  `padding: 10px 0`，使警告框文字紧靠棕色左边框；该规则也影响其他整理提示。
- 已有测试明确要求已结束任务保留这两个入口；其中真实 Python 浏览器旅程
  `initial manual preparation remains reachable from Task Center` 在执行完成后点击
  “查看只读摘要”。修复时要更新入口预期，同时保留其只读历史／零重放的实质覆盖。

以上是源码及测试静态调查，尚未作当前构建的浏览器视觉复现，未声明产品测试通过。
适用 `V2-OPS-005/007/008/018/019`、`V2-UX-005/006`、`V2-TASK-012–014`，以及
[任务／逐项恢复完整旅程](docs/product-experience.md#tasks-results-and-per-item-recovery)、
[整理弹窗完整旅程](docs/product-experience.md#current--manual-organize-dialog-slice53-pass--closed)、
[任务中心页面约定](docs/task-center-page-spec.md#手动受理与确认)、
[整理弹窗架构边界](docs/architecture.md#current--manual-organize-dialog-slice53-pass--closed)。
用户本次授权收敛上述现有呈现；不改变历史记录、继续资格或执行安全语义。

### Implementation scope and ordered guidance

1. 在 `RunDetailFacts` 删除“查看只读摘要”和“从文件页重新发起”两个入口；
   `filesPreparation` 不存在或后端 `continuable` 不为 true 时，不渲染整个
   “文件整理准备”区域，包含标题、结束提示和空按钮容器。正常完成、失败和取消
   一致处理该重复区域；这些状态的真实结果与失败事实仍由原任务详情／文件证据呈现。
   不新增一条替代性“已结束／去文件页”提示或折叠版重复入口。
2. 明确“需要时显示”的边界：已有准确关联且后端允许继续时保留现有“继续整理”及
   其原 discovery／library／returnOps；等待确认可继续到准确摘要。四类处理中的
   决定→分析→摘要→确认及未知提交核对保留原入口。不能依据 Task completed 推定
   文件全成功，不能仅因 failed／cancelled 再挂一个只读摘要按钮，也不另造前端
   继续资格／通用恢复判断。排队／执行中的既有继续资格不在本 Task 重新设计。
3. 收窄整理弹窗的通用 `section` 样式，避免覆盖 `StatusBanner` 的水平内边距与
   提示框边界。原只读深链接、加载／读取失败、未就绪和明确确认中的 info／warning／
   error 提示均有协调留白，长路径与多段文字可读；正常业务分区的布局仍清晰。
   优先排除 `.mf-status` 或明确限定业务分区，不通过全站增加特异性或 `!important`
   叠补，不删除警告来隐藏间距问题。
4. 保留准确历史准备深链接及其只读能力，包括没有计划、计划读取失败与页内重新读取；
   已结束工作不得重新选择、修正、分析或确认。普通文件页的整理入口保留。
   本 Task 用移除正常任务详情的多余跳转消除用户报告的背景切换路径，不重构
   `OrganizeCreationPage` 路由背景，也不承诺旧深链接或保留的“继续整理”改为同页弹窗。
5. 更新旧入口预期并补充直接受影响测试。只读历史用已有准确 preparation URL
   验证，不为测试增加隐藏产品入口；确认后的正常旅程在原 Task 查看结果，不能
   通过删掉末尾只读断言同时丢失零写／零重放覆盖。视觉检查包括已结束任务详情
   原列表背景、普通 Files 整理弹窗及旧只读链接的警告留白。

允许产品文件限于 `OperationsLanding.tsx`、`shared/ui/styles.css` 及确有必要的
`ManualOrganizeDialog.tsx` 呈现调整；测试限于直接受影响的 operations／organize 单元、
浏览器用例及最小本地 fixture。无需改后端、API 类型、继续资格、路由或共享 modal 行为。
若发现必须改变这些契约，先交 B 重评，不借本 Task 扩展实现。

### Acceptance criteria

- [ ] 已结束任务详情无两个旧入口、无“文件整理准备”标题／结束说明／空区；正常成功、
  completed 但文件失败或未知、failed、cancelled、无准备关联均有覆盖。
- [ ] 流程与文件／附件结果、失败／取消事实、效果未知／结果缺失保持真实；逐文件就地
  证据、记录／导出及历史计划说明可达，不重放成功兄弟项或不确定效果。
- [ ] 未结束且后端允许继续的准确准备入口保留；待确认与四类原生恢复仍能检查摘要并
  明确确认一次，完成后回到原 Task；轮询转终态后旧操作区消失，不自动跳转或提交。
- [ ] 任务详情的打开／关闭／刷新保持原视图、日期／页／滚动与合理焦点。删除入口后的
  正常完成查看全程留在任务中心，不切换到整理准备背景；不引入新的背景路由。
- [ ] 原只读深链接、刷新／认证恢复仍读取准确准备；有计划／无计划／读取失败可辨，
  仅允许安全重读，不重新分析、确认或执行，未知请求仍核对原提交身份。
- [ ] 1536px 桌面、390px 窄屏及矮窗口中，提示标题／正文与棕色条有清楚水平留白，
  多段文字、长路径、错误和关闭动作可读可达；提示框与正常业务分区均无整页溢出。
- [ ] 移除入口及改变提示样式不增加业务写请求、Provider／媒体 Storage I/O；普通 Files
  整理仍可新发起，既有草稿、精确确认、危险授权和未知提交非重放保护不变。

### Required tests

激活后先运行根目录 `python3 scripts/check_governance.py`。下列 Web 命令 cwd 为 `web/`。

#### Developer — affected tests

```sh
npm run test -- run src/features/operations/OperationsInventory.test.tsx src/features/operations/OrganizeCreationPage.test.tsx src/features/operations/ManualOrganizeDialog.test.tsx src/features/operations/RunDetailTabs.test.tsx src/features/operations/TaskItemRecoveryPanel.test.tsx
npm run typecheck
npx eslint src/features/operations/OperationsLanding.tsx src/features/operations/OperationsInventory.test.tsx src/features/operations/OrganizeCreationPage.test.tsx tests/e2e/operations.spec.ts tests/e2e/task-center-layout.spec.ts tests/e2e/operations-inventory.python.spec.ts
npx prettier --check src/features/operations/OperationsLanding.tsx src/features/operations/OperationsInventory.test.tsx src/features/operations/OrganizeCreationPage.test.tsx src/shared/ui/styles.css tests/e2e/operations.spec.ts tests/e2e/task-center-layout.spec.ts tests/e2e/operations-inventory.python.spec.ts
npm run build
npm run test:e2e -- tests/e2e/operations.spec.ts tests/e2e/task-center-layout.spec.ts
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts --grep 'initial manual preparation remains reachable from Task Center|PATCH-20261111-5'
```

静态检查追加实际修改文件。根目录运行 `git diff --check`。新增浏览器回归可放在上列
文件并以本 Task ID 命名，覆盖提示框真实留白／长文与终态区域消失；不能只断言
按钮隐藏或 CSS 数值。查看桌面／390px／矮窗口截图并记录实际结果。测试只用隔离
假服务或真实 Python／临时 SQLite／临时 Local 根，不使用运行数据库或用户媒体。

单元覆盖终态矩阵、可继续／无关联、轮询变化、历史计划读取失败及不重复命令。
直接受影响的原生手动旅程必须保留 Files 准入→离开→Task 继续→明确确认→原 Task
真实结果；结束后再用准确旧链接验证只读无重放，不依赖已删除按钮。

#### B — independent acceptance

审查固定 Task Base..候选全部差异，独立复核上述旅程、零写请求和截图；执行上述
受影响单元／Node E2E，以及 `npm run typecheck`、`npm run lint`、
`npm run format:check`、`npm run build`。在当前构建上执行：

```sh
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts --grep 'initial manual preparation remains reachable from Task Center|PATCH-20261111-2|PATCH-20261111-5'
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/manual-organize-dialog.python.spec.ts
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/task-flow.python.spec.ts
```

核对五类 Task 流程与独立文件效果、四类同 Task 恢复、原计划只读、精确确认和原请求
核对；对无计划／读失败的旧深链接保留明确下一步。视觉验收涵盖成功详情与混合结果、
Files 弹窗及旧只读卡的提示留白／滚动／键盘关闭，不能将旧深链接自身已有接收页背景
误判为本 Task 要求改成任务中心背景。证据留于
`.git/validation-evidence/<candidate>/patch-20261111-5/`，保留原失败与实际限制。

T3 依据为已有入口、异步状态和共享整理弹窗呈现的消费者集成；不改变权限、schema、
Storage、后端确认／调度／执行协议。不要求全 Python／全 Web／全 E2E、wheel 或 Docker
矩阵；发现实际安全契约变更须重评，不能以当前等级跳过新增风险。

### Non-goals and documentation boundary

不删除资源库文件页、不删除真实历史计划／证据或后台 API，不退役准确历史深链接；
不新增“仅异常时查看只读摘要”的第二套判断、不改 Task 状态／统计／执行资格、不做
整个任务中心／整理路由／全站提示框重设计。PATCH-20261111-4 的就地证据位置和
同文件输入保留保持；SLICE／Roadmap／Progress 与已接受 Slice 身份不变。

本规划仅更新 TASK.md，不提前把 CURRENT 产品文档写为已实现。B PASS 后，按实际
结果最小协调 task-center-page-spec、Product Experience 以及 V2 Requirements／
Architecture 中直接提及已删除入口的现行措辞；保留原接受身份与安全契约，不把本次
独立呈现修复写成重开或关闭 Slice。

### Workspace and handoff

规划基线：`main`，HEAD／Task Base 如上；治理预检 PASS，暂存区原为空。预存
`mediaflow/.DS_Store` 修改及未跟踪 `.DS_Store`、`.explore_adapter_block.py`、日志、
`15`、各目录系统元数据和 `output/` 调查材料原样保留，不纳入规划提交；不读取
私有配置／运行数据库／用户媒体，不推送或部署。

尚未实施、未运行产品验收。激活并实施后由 Developer 提交完整 checkpoint、实际
受影响检查与限制，交 READY FOR B REVIEW；B 独立验收 PASS／FIX REQUIRED。
修正保持同一 Task；PASS 后恢复简短无活动实施通知及固定审查指针，不规划授权外工作。
