# NO ACTIVE IMPLEMENTATION TASK

最近独立修正：**PATCH-20261030-1 — 任务中心统一时间筛选与刷新反馈，B PASS（2026-10-30）**。
AC-1–10 已满足，该修正没有待实施或返工项。下方新增规划草案仅供后续实施使用，
本轮只授权规划，不启动实施。

- Task Type：STANDALONE MINOR BUG；Parent Slice：NONE；Difficulty：Medium；Test Level：T3。
- Reviewed Base：`e40093aa2400794f4423987658fba3095c7adda5`。
- Reviewed Head：`0cfbb3b785a101e4625c0c1bdd9e2a11e25e8c51`；Implementation checkpoint：
  `87630b5898bcfa6ec3c341f7b11d73f9f5e1f06a`。
- 完整授权/AC/Developer 交接：`0cfbb3b7:TASK.md`；B 完整范围审查、实际结果及证据限制：
  `7d9699863b98116d636b41f08b7d1e2707b4409a:TASK.md`。

现行八标签时间筛选、中文手动刷新、静默轮询与读取恢复以
[V2 Requirements](docs/v2-requirements.md)、
[Task Center specification](docs/task-center-page-spec.md)、
[Product Experience](docs/product-experience.md#tasks-results-and-per-item-recovery) 和
[Architecture](docs/architecture.md#current--task-center-query-summary-confirmation-and-typed-recovery-slice45)
为准。完整测试流水保留在 Git 与本地 ignored evidence，本通知仅保留验收结论/checkpoint 指针。

Slice46 维持 A 已接受的 **PASS / CLOSED**；原 Base、Implementation Head、SLICE、Roadmap、
Progress 和延期边界不变。下一大 Slice 由 A 单独选择，其他实施须有相应授权。
生命周期遵循 [Development Workflow](docs/development-workflow.md#31-independent-minor-bugs)。

---

## 规划草案：PATCH-20261030-2 — 任务中心紧凑日期筛选栏

**仅规划，未授权实施。** 保留本文件顶部 `NO ACTIVE IMPLEMENTATION TASK`；下面的
`PLANNED` 是草案元数据。用户明确授权实施后，才将本草案提升为正式 Task；复核期间的
源代码变化，保留真实实现起点，不把规划提交冒充实现或验收。

Authority：用户于 2026-10-30 提供任务中心筛选区截图，接受“去掉重复视图标题、共用创建日期
标签、合并时区提示、对齐并紧凑排版”的调查建议，并要求规划一版 Task。
本轮仅修改本 `TASK.md`；产品代码、其他文档、SLICE/Roadmap/Progress 和历史验收保持原样。

```text
Task ID: PATCH-20261030-2
Task Type: STANDALONE MINOR BUG
Parent Slice: NONE
Status: PLANNED
Task Base: b50e4834b48a1f1fd3347a36ce5cdbb16aad51ce
Difficulty: Low
Test Level: T2
Planner / Reviewer: B
Implementation Authorization: NOT GRANTED — PLANNING ONLY
```

### Goal

修正现有 `/ui-v2/operations` 八个视图共用筛选区的重复说明、层级和缩进问题，让用户在选中
标签下直接使用紧凑的创建日期范围，减少筛选区对列表首屏的占用。
这是现有 Web 呈现的有界修正，关联已接受的 `V2-UX-001/003`、`V2-OPS-001/003`，不增加
业务能力或改变已接受 Slice 的结果、架构和安全边界。

依据：[Requirements](docs/requirements.md) 的现行任务中心界面修正、
[V2 Requirements](docs/v2-requirements.md) 的上述稳定 ID、
[完整任务与恢复旅程](docs/product-experience.md#tasks-results-and-per-item-recovery)、
[Task Center integration](docs/product-experience.md#task-center-integration)、
[页面规范 §2](docs/task-center-page-spec.md#2-页面结构与共有行为) 和
[CURRENT query contract](docs/architecture.md#current--task-center-query-summary-confirmation-and-typed-recovery-slice45)。

已核实的缺口：

- `OperationsLanding.tsx` 的 `ViewNavigation` 在选中标签下又输出同名 `h3` 及
  `RUN_VIEW_DESCRIPTIONS`，重复当前位置，并在 All 暴露“任务与 Job / 受理时记录”说明。
- `RunTimeRangeFields` 分别显示“创建时间从（本地）”“至（本地）”，外层再常驻完整时区
  说明；该说明沿用正文大小，占据独立段落，层级重于视图说明。
- `styles.css` 的 `.mf-run-layout` 与其子 `.mf-run-main` 同时被赋予左右 padding，
  桌面叠加为 32px，标题为 18px；窄屏两层也叠加，导致缩进不一致和可用宽度损失。

完整旅程：进入任一任务标签 → 看见当前标签、创建日期范围与简短时区提示 → 选择任意一端
或两端日期即时筛选，必要时展开时区说明 → 查看真实范围内结果并进入详情 → 无匹配时可
清除条件，读取失败时保留日期并沿用原读取恢复。说明展开/收起仅影响本地展示。

### Implementation Scope

预期呈现（示意文字不要求替换原生日期框的浏览器占位）：

```text
[原八个横向标签；当前标签保持选中]
创建日期  [ 开始日期 / 日历 ] — [ 结束日期 / 日历 ]  清除  本地时区 ⓘ
[原任务表格 / 空态 / 读取状态]
```

1. 在 `web/src/features/operations/OperationsLanding.tsx` 移除八个标签下重复的视图标题及
   通用描述；保留页面“任务中心”标题、全部八标签、选中语义和实际问题处理中的必要说明。
   只清理直接失去消费者的描述常量，不扩展到其他业务文案。
2. 将两端日期归为“创建日期”组，独立可访问名称使用“开始日期”“结束日期”；保留原生
   `type=date`、双向 `min/max` 约束、现有事件处理、URL 字段及本地日边界转换。
   工具栏有日期时显示低强调的“清除”，调用原 `resetFilters`；空态/错误态的“清除时间”
   恢复入口可保留，测试应按所在区域区分，不能把所有同类按钮误当作一个。
3. 常驻简短“本地时区”和带名称“时区说明”的说明按钮；通过点击或 Enter/Space 展开/
   收起本地说明，提供准确的展开状态和关联。说明表达“按本机时区的创建日期筛选，结束日
   包含整天；列表/详情沿用同一时区并显示偏移”，不用硬编码城市/偏移。
   说明放在正常文档流，避免面板 `overflow:hidden` 截断；默认不占独立段落。
   说明控件保持键盘焦点，日期仍关联有效说明；操作不改变筛选、URL、选择或请求。
4. 在 `web/src/shared/ui/styles.css` 的任务中心范围内消除嵌套水平留白叠加，统一筛选栏
   和表格内容边界。桌面常规宽度呈一条紧凑工具栏，控件高度约 34–36px、组间距约 8–12px，
   辅助文字视觉降级但清晰可读；这些数值是设计目标，验收以实际对齐、层级、可读性为准。
   空间不足时按组换行；覆盖详情打开后的列表收窄和手机宽度，不为单行布局压缩日期文字。
5. 调整直接引用旧控件名称的组件/浏览器测试，保留原筛选、恢复和刷新断言，增加必要的
   可见层级、说明开关和响应式验证。仅同步实际受影响的选择器，不借此删减旧行为覆盖。

预期改动为上述两个产品文件及直接受影响的测试：
`OperationsInventory.test.tsx`、`AppShell.test.tsx`、`tests/e2e/task-center-layout.spec.ts`、
`tests/e2e/operations-inventory.python.spec.ts`；可复用现有
`operations-task-center-visual.python.spec.ts` 作视觉验证。新增局部组件仅在确有必要时使用。

### Acceptance Criteria

- [ ] AC-1：八个视图保留原选中标签和单个页面标题；标签与筛选栏之间没有重复的当前视图
  标题/通用说明，四类问题处理、阶段/失败证据和必要下一步说明仍可见。
- [ ] AC-2：筛选栏只显示一次“创建日期”和一次“本地时区”；两端日期名称可由读屏和
  键盘独立识别，日历选择仍可用，日期范围及清除在视觉上属于同一组。
- [ ] AC-3：时区说明默认收起；鼠标、触摸和键盘均可开关、状态可辨且内容不被裁切。
  开关不触发额外 API 请求或改变日期、标签、分页、详情与 URL；日期说明关联不悬空。
- [ ] AC-4：1536×1024 和 1280×800 默认列表的工具栏为紧凑单行；390×844 和 320px
  宽度自然换行，控件文字/图标可读、操作可达、无重叠或页面横向溢出。展开说明或详情使
  列表收窄时仍保持对齐、可读且无溢出，允许换行；保留表格内部必要的有界滚动。
- [ ] AC-5：无日期显示当前标签完整获准总体；起始单侧、结束单侧、同日/跨日双侧均即时
  生效；结束日完整包含，起止顺序和非法日期仍受原有校验约束。“清除”在有条件时可用，
  清除后恢复当前标签总体并重置分页，不能引入搜索提交步骤。
- [ ] AC-6：切标签保留日期并回该标签第一页，详情返回/浏览器前后退/重连恢复合法上下文；
  迟到响应不覆盖当前条件。中文手动刷新、静默轮询和正常刷新保留内容的行为不回退。
- [ ] AC-7：无匹配结果提供可用清除入口；网络/格式错误保留日期并使用原读取恢复，
  401/403 沿用原权限边界，不把失败渲染为零条成功结果。浏览、筛选和时区说明只读，
  不创建整理任务或获得执行权限。
- [ ] AC-8：样式改动限定任务中心；页头、统计卡、表格列可读性、详情与问题文件入口
  保持可用；无关页面和共享控件不因通用选择器变化而改变。

### Required Tests

测试分工遵循 [workflow §6](docs/development-workflow.md#6-test-levels)。T2：本轮仅局部
Web 呈现和说明开关，不修改后端查询、时间转换、持久化、权限或执行契约；若实际需要
跨越该边界，先由 B 重新评估范围与 Test Level。

#### Developer — affected tests

根目录：`python3 scripts/check_governance.py`、`git diff --check`。

`web/` 下：

```sh
npm run test -- run src/features/operations/OperationsInventory.test.tsx src/shared/ui/AppShell.test.tsx src/features/operations/TaskRefreshControl.test.tsx
npm run typecheck
npm run build
npm run test:e2e -- tests/e2e/task-center-layout.spec.ts
```

对实际变更的 TS/TSX/CSS 文件运行 `npx prettier --check <实际文件列表>`，对变更 TS/TSX
运行 `npx eslint <实际文件列表>`。上述组件覆盖当前筛选、异步读取/失败/旧响应、详情返回
与刷新行为；浏览器覆盖真实日期控件、布局、八标签和键盘操作。

扩展现有布局 spec，覆盖 AC-1–4 的真实可见结果、说明开关不触发额外请求、清除按钮出现后
的换行及 320px 布局。对已改名的真实 Python 测试同步定位方式，保留原时间/总数断言。
检查桌面、窄屏、详情打开和说明展开的实际截图；不以 DOM 形状或 CSS 字面量替代视觉验收。
交接实际结果与剩余风险即可，不要求 Developer 跑整个 Python/Web/E2E 套件。

#### B — acceptance and regression

审查完整 `Task Base..candidate`，确认产品改动和测试同步均在授权范围；独立复现
AC-1–8。复用匹配候选的 Developer 受影响测试结果，核对执行输入，不机械重复。

`web/` 下运行适用静态/产物检查：

```sh
npm run typecheck
npm run lint
npm run format:check
npm run build
npm run test:e2e -- tests/e2e/task-center-layout.spec.ts tests/e2e/operations.spec.ts
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts tests/e2e/operations-task-center-visual.python.spec.ts --grep 'time filter:|refresh feedback:|capture the eight task-center views'
```

使用既有隔离 Python/API/SQLite harness 和临时合成数据，不读取用户运行库/媒体或真实
Provider。真实 API 日期用例验证本地日边界、单侧/双侧、分页、八视图及重连未回退；
视觉 spec 验证真实八视图、问题文件入口和窄屏。人工检查同视口实际渲染的对齐、信息层级、
日期文字、焦点、触摸可达性和说明裁切，保留候选身份/结果/截图到 ignored evidence。
这是 T2 局部修正，不要求全仓 Python/Web/E2E、容器/打包或执行安全矩阵。

### Non-goals

- 不增加快捷日期、搜索、来源/状态等筛选，不引入新日期库或重写日历弹层。
- 不承诺原生日期占位、日期格式和图标跨浏览器逐像素一致。
- 不修改 API、URL 结构、`run-time.ts`、查询/刷新算法或整理/恢复/执行权限。
- 不重设计任务详情、统计卡、其他页面/共享组件；不清理整份历史 CSS。
- 不修改 SLICE/Roadmap/Progress、需求/架构/页面规范或参考图片；不选择下一 Slice。
- 本轮不实施、不启动其他角色或子代理、不 push、不部署。

### Developer Completion Report

未开始；后续仅在用户明确授权实施后填写 checkpoint、实际变更、受影响测试结果和风险，
状态交至 `READY FOR B REVIEW`。验收仍由 B 独立完成。

### B Review Result

待实施候选。本草案不构成实施或 PASS；后续记录精确 `Task Base..Head`、实际验收结果及
`PASS / FIX REQUIRED`。独立修正 PASS 后回到无活跃实施 Task，不声明 Slice 关闭。

### Workspace record — planning

- Repository：`/Users/songzhidong/mediaflow`；branch：`main`；规划 HEAD/Task Base：
  `b50e4834b48a1f1fd3347a36ce5cdbb16aad51ce`；工作区和 Git index 可写。
- 开始时没有 tracked 改动；原有 untracked 保留：根/`docs`/`docs/pics`/`testdata`/`web`
  的 `.DS_Store`，`.mgmt.log`、`.t.log`、`.t_test_*.log`，根目录 `15`，
  `docs/pics/自动化页-全局设置.png`、`docs/pics/自动化页.png`，
  `output/imagegen/slice45-task-center-v1.zip`。均不加入本次规划 checkpoint。
- 规划前 `python3 scripts/check_governance.py`：PASS。本轮只做规划文档/治理检查，
  未运行产品测试，不声称实现或验收完成。
