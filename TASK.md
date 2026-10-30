# Task PATCH-20261030-2 — 任务中心紧凑日期筛选栏

Authority：用户于 2026-10-30 提供任务中心筛选区截图，接受“去掉重复视图标题、共用创建日期
标签、合并时区提示、对齐并紧凑排版”的调查建议，要求规划并收敛验收断言，随后明确要求
“激活Task”。现将已修订草案提升为正式 `PLANNED` Task，供 Developer 按下述范围实施。
此次激活仅更新本 `TASK.md`，不开始产品实现或自动启动其他角色。

生命周期遵循 [Development Workflow](docs/development-workflow.md#31-independent-minor-bugs)。
Slice46 维持 A 已接受的 **PASS / CLOSED**；SLICE/Roadmap/Progress、原 Base、已接受 Head
及延期边界不变。前一独立修正 PATCH-20261030-1 的 B PASS 和证据保留在
`7d9699863b98116d636b41f08b7d1e2707b4409a:TASK.md`，不是本 Task 的待办。

```text
Task ID: PATCH-20261030-2
Task Type: STANDALONE MINOR BUG
Parent Slice: NONE
Status: READY FOR B REVIEW
Task Base: b50e4834b48a1f1fd3347a36ce5cdbb16aad51ce
Difficulty: Low
Test Level: T2
Planner / Reviewer: B
Implementation Authorization: USER-ACTIVATED — 2026-10-30
```

## Goal

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

## Implementation Scope

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
   说明默认收起，展开后完整可读且不被容器裁切；不限定文档流或浮层实现。
   说明控件保持键盘可操作，日期仍关联有效说明；开关本身不发起 API 请求，不改变筛选、
   URL 或选择，也不干扰既有轮询和正常读取。
4. 在 `web/src/shared/ui/styles.css` 的任务中心范围内消除嵌套水平留白叠加，统一筛选栏
   和表格内容边界。正常缩放且可用宽度充足时以紧凑单行为目标，控件高度约 34–36px、
   组间距约 8–12px，辅助文字视觉降级但清晰可读；这些数值是设计目标，验收以实际对齐、
   层级、可读性为准。
   空间不足时按组换行；覆盖详情打开后的列表收窄和手机宽度，不为单行布局压缩日期文字。
5. 调整直接引用旧控件名称的组件/浏览器测试，保留原筛选、恢复和刷新断言，增加必要的
   可见层级、说明开关和响应式验证。仅同步实际受影响的选择器，不借此删减旧行为覆盖。

预期改动为上述两个产品文件及直接受影响的测试：
`OperationsInventory.test.tsx`、`AppShell.test.tsx`、`tests/e2e/task-center-layout.spec.ts`、
`tests/e2e/operations-inventory.python.spec.ts`；可复用现有
`operations-task-center-visual.python.spec.ts` 作视觉验证。新增局部组件仅在确有必要时使用。

## Acceptance Criteria

- [ ] AC-1：八个视图保留原选中标签和单个页面标题；标签与筛选栏之间没有重复的当前视图
  标题/通用说明，四类问题处理、阶段/失败证据和必要下一步说明仍可见。
- [ ] AC-2：筛选栏只显示一次“创建日期”和一次“本地时区”；两端日期名称可由读屏和
  键盘独立识别，日历选择仍可用，日期范围及清除在视觉上属于同一组。
- [ ] AC-3：时区说明默认收起；鼠标、触摸和键盘均可开关、状态可辨且内容不被裁切。
  开关本身不发起 API 请求，不改变日期、标签、分页、详情与 URL，也不干扰既有轮询和
  正常读取；日期说明关联不悬空。不以操作前后总请求数相等作为断言。
- [ ] AC-4：以 1536×1024、1280×800 的正常缩放默认列表检查紧凑单行的设计目标；
  390×844、320px 宽度及字体、缩放、原生日期控件差异导致空间不足时允许按组换行。
  硬性要求为控件文字/图标可读、操作可达、筛选与表格内容边界对齐，无重叠或页面横向
  溢出；说明展开和详情收窄也须满足。保留表格内部必要的有界滚动。
- [ ] AC-5：无日期显示当前标签完整获准总体；起始单侧、结束单侧、同日/跨日双侧均即时
  生效；结束日完整包含，起止顺序和非法日期仍受原有校验约束。“清除”在有条件时可用，
  清除后恢复当前标签总体并重置分页，不能引入搜索提交步骤。
- [ ] AC-6：切标签保留日期并回该标签第一页，详情返回/浏览器前后退/重连恢复合法上下文；
  迟到响应不覆盖当前条件。中文手动刷新、静默轮询和正常刷新保留内容的行为不回退。
- [ ] AC-7：无匹配结果提供可用清除入口；网络/格式错误保留日期并使用原读取恢复，
  401/403 沿用原权限边界，不把失败渲染为零条成功结果。浏览、筛选和时区说明只读，
  不创建整理任务或获得执行权限。
- [ ] AC-8：新增或调整的样式限定任务中心；页头、统计卡、表格列可读性、详情与问题文件
  入口保持可用。审查实际选择器影响范围；如改动涉及共享选择器或控件，针对实际受影响的
  相邻入口做检查，不要求全站逐页视觉回归。

## Required Tests

测试分工遵循 [workflow §6](docs/development-workflow.md#6-test-levels)。T2：本轮仅局部
Web 呈现和说明开关，不修改后端查询、时间转换、持久化、权限或执行契约；若实际需要
跨越该边界，先由 B 重新评估范围与 Test Level。

### Developer — affected tests

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

扩展现有布局 spec，覆盖 AC-1–4 的真实可见结果、说明开关不自行发起请求、清除按钮出现后
的换行及 320px 布局。请求断言区分说明操作与既有轮询/读取，不冻结轮询来满足总请求数断言。
对已改名的真实 Python 测试同步定位方式，保留原时间/总数断言。
检查桌面、窄屏、详情打开和说明展开的实际截图；不以 DOM 形状或 CSS 字面量替代视觉验收。
交接实际结果与剩余风险即可，不要求 Developer 跑整个 Python/Web/E2E 套件。

### B — acceptance and regression

审查完整 `Task Base..candidate`，确认产品改动和测试同步均在授权范围。B 独立验收新增/
修改的布局、信息层级、说明开关、可访问性及实际选择器影响范围（AC-1–4、AC-8）。
AC-5–7 是既有筛选、上下文、读取恢复与只读边界的保留要求；运行受影响回归并保留原断言，
不重新建立整套日期/认证/刷新验收矩阵。匹配候选的已有回归结果按 workflow 的证据复用
规则核对使用；缺失或执行输入变化的部分补跑，不机械重复有效覆盖。

`web/` 下运行适用静态/产物检查：

```sh
npm run typecheck
npm run lint
npm run format:check
npm run build
npm run test:e2e -- tests/e2e/task-center-layout.spec.ts
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts tests/e2e/operations-task-center-visual.python.spec.ts --grep 'time filter:|capture the eight task-center views'
```

使用既有隔离 Python/API/SQLite harness 和临时合成数据，不读取用户运行库/媒体或真实
Provider。真实 API 日期用例作为控件名称变更直接影响的回归，保留本地日边界、单侧/双侧、
分页、八视图及重连断言；既有刷新/读取失败回归沿用上方组件和布局 spec 的覆盖。
视觉 spec 验证真实八视图、问题文件入口和窄屏。人工检查同视口实际渲染的对齐、信息层级、
日期文字、焦点、触摸可达性和说明裁切，保留候选身份/结果/截图到 ignored evidence。
这是 T2 局部修正，不要求全仓 Python/Web/E2E、容器/打包或执行安全矩阵。

## Non-goals

- 不增加快捷日期、搜索、来源/状态等筛选，不引入新日期库或重写日历弹层。
- 不承诺原生日期占位、日期格式和图标跨浏览器逐像素一致。
- 不修改 API、URL 结构、`run-time.ts`、查询/刷新算法或整理/恢复/执行权限。
- 不重设计任务详情、统计卡、其他页面/共享组件；不清理整份历史 CSS。
- 不修改 SLICE/Roadmap/Progress、需求/架构/页面规范或参考图片；不选择下一 Slice。
- 不自动启动其他角色或子代理、不 push、不部署。

## Developer Completion Report

### Candidate — 2026-10-30

- Implementation checkpoint：`390e0db50cfc2e05013e0ca70bb0d9d568c04667`；
  Task Base 保持 `b50e4834b48a1f1fd3347a36ce5cdbb16aad51ce`。
  真实 Web 源码树：`34aac81e522e9421554d3150408d6e3ef4952869`。
  本报告为仅 `TASK.md` 的后继 checkpoint，产品/测试/harness/构建输入不再变化；
  B 审查完整 Base..交接 Head。状态为 **READY FOR B REVIEW**，不是独立 PASS。
- 产品只改 `OperationsLanding.tsx` / 任务中心局部 CSS：删除标签下重复标题/通用描述；
  合并创建日期组及低强调清除；独立开始/结束日期名称；默认收起、鼠标/键盘/触摸可开的
  时区说明，带展开状态/关联和有效日期描述；移除嵌套水平留白，日期保留原生宽度并换行。
  四类问题/失败证据、页头/统计/详情保留；后端、`run-time.ts`、URL、查询/轮询和权限未改。
- 测试仅同步四个直接受影响文件，保留既有日期/总数/失败/上下文断言；新增本地说明、
  四视口实测、说明展开/详情收窄、原生控件可访问描述及触摸验证。
  请求验证在现有列表正常轮询之间记录路由/方法/时间，等待下一次正常轮询成功；不禁用
  轮询、不使用前后总请求数相等断言。所有场景从现有路由、标签、日期和详情入口发生；
  使用既有 Node fake 或隔离 Python/API/SQLite harness，无新增测试入口或用户库/媒体。

### Actual affected verification

下表命令 cwd 为 `web/`（根目录检查单列）；原始日志/截图/输入与产物 SHA256 保存于本机
ignored `.git/validation-evidence/developer-patch-20261030-2/`，索引见其中 `README.md`。

| Command | Actual result |
|---|---|
| `npm run test -- run src/features/operations/OperationsInventory.test.tsx src/shared/ui/AppShell.test.tsx src/features/operations/TaskRefreshControl.test.tsx` | 3 files / **61 passed**，6.01s，0 skips；`components-final.log` |
| `npm run typecheck` | 通过；`typecheck-final.log` |
| `npx eslint src/features/operations/OperationsLanding.tsx src/features/operations/OperationsInventory.test.tsx src/shared/ui/AppShell.test.tsx tests/e2e/task-center-layout.spec.ts tests/e2e/operations-inventory.python.spec.ts` | 通过；`eslint-final.log` |
| `npx prettier --check src/features/operations/OperationsLanding.tsx src/shared/ui/styles.css src/features/operations/OperationsInventory.test.tsx src/shared/ui/AppShell.test.tsx tests/e2e/task-center-layout.spec.ts tests/e2e/operations-inventory.python.spec.ts` | 通过；`prettier.log` |
| `npm run build` | 通过；`build.log`；产物 `index-DW6J-cHO.js` / `index-IPyNb6dh.css`，用于两种浏览器 harness |
| `npm run test:e2e -- tests/e2e/task-center-layout.spec.ts --output=../.git/validation-evidence/developer-patch-20261030-2/layout-verified-results` | Chromium **13 passed**，18.0s，0 skips；`layout-verified.log` |
| `npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts tests/e2e/operations-task-center-visual.python.spec.ts --grep 'time filter:|capture the eight task-center views' --output=../.git/validation-evidence/developer-patch-20261030-2/python-results` | 真实 Python **5 passed**，6.6s，0 skips；含本地日两端/单侧/清除、分页/详情返回/重连、八视图及实际问题文件入口；`python-browser.log` |
| 根目录 `python3 scripts/check_governance.py`、`git diff --check` / staged diff check | 通过；preflight/交接检查均执行 |

视觉实际检查：1536×1024、1280×800 默认及筛选/展开均紧凑单行；390×844、320px 日期按组
换行，日期文字/日历图标/清除/说明按钮可读可达，无页面横向溢出；说明在文档流内完整显示。
1280 桌面加载完成的详情使列表收窄后仍可读；手机保留原全屏详情、关闭后说明/日期不丢失。
另检查真实 Python 的 All、元数据恢复及问题文件入口截图，必要问题说明仍存在。

### Failures and remaining limits

- 初轮 typecheck 报新增 Testing Library `getByRole` 选项不支持 `exact`；已使用区域限定的
  精确字符串名称修复，随后静态/组件检查通过。保留初轮失败 `typecheck.log`，没有弱化断言。
  两次 formatter 命令因误用根目录 cwd 未找到文件，随后均在 `web/` 正确执行；不算通过。
- 验证浏览器为 Chromium；触摸是 Playwright 的真实触摸事件模拟，不声称实机 iOS/Safari/
  Firefox、读屏软件或所有字体/缩放组合已验收。原生日历跨浏览器差异不承诺像素一致。
- 已有 jsdom `scrollTo` 未实现、Node NO_COLOR/FORCE_COLOR 和 Vite 大 chunk 警告；无新增
  产品失败。未跑全仓 Python/Web/E2E 或容器矩阵，按本 T2 Developer 分工交 B 独立验收。
- 未改 SLICE/Roadmap/Progress/需求/架构；没有子代理、自签 PASS、推送或发布。
  原有 untracked/private 文件未加入 checkpoint；无本 Task 外产品改动。

## B Review Result

待 B 对交接候选独立审查；Developer 验证不构成 PASS。B 记录精确 `Task Base..Head`、
实际验收结果及 `PASS / FIX REQUIRED`；独立修正 PASS 后回到无活跃实施 Task，不声明 Slice 关闭。

## Workspace record

### Planning

- Repository：`/Users/songzhidong/mediaflow`；branch：`main`；规划 HEAD/Task Base：
  `b50e4834b48a1f1fd3347a36ce5cdbb16aad51ce`；工作区和 Git index 可写。
- 开始时没有 tracked 改动；原有 untracked 保留：根/`docs`/`docs/pics`/`testdata`/`web`
  的 `.DS_Store`，`.mgmt.log`、`.t.log`、`.t_test_*.log`，根目录 `15`，
  `docs/pics/自动化页-全局设置.png`、`docs/pics/自动化页.png`，
  `output/imagegen/slice45-task-center-v1.zip`。均不加入本次规划 checkpoint。
- 规划前 `python3 scripts/check_governance.py`：PASS。本轮只做规划文档/治理检查，
  未运行产品测试，不声称实现或验收完成。

### Activation — 2026-10-30

- Branch：`main`；激活前 HEAD：`da53640f093c2d4809ecf360b1c9d4a9b01c5153`。
  工作区和 Git index 可写，无 tracked 或 staged 改动；上列原有 untracked 文件保持原样。
- `Task Base..HEAD` 仅含本 `TASK.md` 的规划/断言修订，产品实现输入未变；保留原
  Task Base `b50e4834b48a1f1fd3347a36ce5cdbb16aad51ce`、Goal、范围、AC 和 Low/T2 分级。
- 激活前治理检查 PASS；本次只提升 Task 状态及授权说明，尚未实施或运行产品测试。


### Developer workspace — 2026-10-30

- Branch：`main`；实施前 HEAD：`39e493cd0f52e94d9de1bf3c0bfe69f4d6929eb4`。
  工作区/Git index 可写，无 pre-existing tracked/staged 改动；上列原有 untracked 全部保留。
- 治理检查通过后仅本 Task 由 IN PROGRESS 转 READY FOR B REVIEW；只 stage 六个源码/测试
  文件与本报告，没有改动或收录已有日志、OS 文件、参考图片、私有配置或用户运行数据。
