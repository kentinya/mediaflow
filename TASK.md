# Task 50.3 — 两种库的完整浏览布局、配置弹卡与加载体验

用户于 2026-11-06 明确授权激活本 Task。未命名 Storage 的编辑阻塞已由 B 复核消除；
保存结果未知/并发冲突的核对与继续阻塞已由 Developer 在同一 Task 修正并交回
READY FOR B REVIEW；本轮不推送或部署。

Authority：已提交 [Slice50](SLICE.md) 的 RO-3 全部、RO-4 两种库加载部分；对应
`V2-UX-009–011`、`V2-UX-012` 的加载部分及 AC-5/6/7/9、适用 AC-10/11。
生命周期、测试和 Git 按 [Development Workflow](docs/development-workflow.md)，角色按
[B 指南](docs/agent-experience/task-planner-reviewer.md)。本 Task 把同一库页的加载与
布局一并交付；合同允许 B 按真实依赖调整建议分组，侧栏主页面切换仍待后续任务。

```text
Task ID: 50.3
Task Type: SLICE
Parent Slice: 50
Status: READY FOR B REVIEW
Task Base: 073e75a97d08f5ad02d4cbe9e2d9cc1efc89564d
Candidate: fd4df8ea36fefb59f003f494f06724b35ccc9d2e
Difficulty: High
Test Level: T4
Planner / Reviewer: B
Working Branch: main
Development Authorization: TASK 50.3 ONLY; SAME TASK FIX LOOP COMPLETED
```

### Goal 与完整用户旅程

用户从侧栏进入“文件”或“媒体库”，在去掉目录树后的完整宽度内浏览文件；实际等待读取时
显示对应区域的加载反馈，数据已就绪时直接显示内容。点击文件夹进入、用面包屑/上一级/
根目录返回，继续搜索、选择、切换列表/网格和分页。通过“添加资源库/添加媒体库”或
选中库的菜单打开居中配置卡片，
填写/编辑并保存，读回真实 Active 后返回正确库/目录；通过库菜单移除配置时，能看懂对象、
引用限制和文件保留结果。失败保留输入或真实读取状态，使用现有刷新/纠正/核对入口继续。

完整目标旅程见 [Product Experience TARGET](docs/product-experience.md#target--v2-dialog-readability-and-navigation-experience-slice50-active)，
及 CURRENT 的 Real Storage Files、Common file maintenance、Library Add/Edit/removal、
MediaLibrary files；业务/技术边界见 [Architecture TARGET](docs/architecture.md#target--v2-dialog-readability-and-navigation-experience-slice50-active)。
视觉按两份 [文件页](docs/file-page-visual-spec.md) /
[媒体库页](docs/media-library-page-visual-spec.md)
TARGET，替换对应旧树/抽屉几何，既有业务约束继续适用。

### 实际代码依据

- `StorageFilesPage.tsx` 的 `FileBrowseView` / `DirectoryTree`、`MediaLibraryFilesPage.tsx`
  的 `MediaBrowseView` / `MediaDirectoryTree` 均消费 `buildDirectoryTree` 和本页已知/访问
  目录记忆；已有 `openPath`、面包屑、根目录、分页和 URL 上下文可承接去树浏览。
- 两文件导出的 `AddResourceLibraryDrawer` / `AddMediaLibraryDrawer` 仍渲染
  `mf-files-drawer` 三步侧抽屉；添加及编辑共用。资源库除基础字段外，还有包含/排除规则和
  三项稳定性设置，不能按媒体库较短表单删减。`open*LibraryEdit` 先读精确编辑投影，
  保存沿用现有 `editExpected` 与 checked API，不能用缓存状态替代。
- `LibraryCardStrip.tsx` 已共享库菜单，消费方传入两种库的编辑/移除标签；媒体库菜单
  accessible name 仍固定“资源库操作”。配置确认由 `DeleteResourceLibraryDialog.tsx`
  和 `DeleteMediaLibraryDialog` 承担，已有引用、精确 Active、取消及文件保留说明。
- 资源库从 `systemStatusQueryOptions` 取得库信息，初始等待是文字块。媒体库从
  `mediaLibraryListQueryOptions` 读取，`data?.items ?? []` 在列表尚未返回时进入“尚未添加
  媒体库”分支；`AuthorizedReadBoundary` 把 pending 交给页面，并不替它拦截该空态。
  两页目录等待也分别是文字块。目录查询 key 已含各自库种类、库 ID、路径与 cursor，
  复用这个边界即可，不因动画重建缓存/命令系统。
- `shared/ui/modal-card.tsx` 已有 `ModalCardShell`、`useModalLayer`、滚动锁定及进出呈现；
  `StorageEditDrawer.tsx` 是已接受的配置弹卡消费者。优先复用这些无业务外壳。

以上是现有入口的源码缺口分析，本轮没有运行浏览器，不把它写成新候选的交互实测。

### Implementation Scope / Developer 开发指导

1. **先处理两个现有浏览页面。** 去掉两页树组件、传参和占位布局，让卡片条下的浏览区域
   使用释放宽度。顺着消费链删除仅供树使用的目录构建/记忆/发现逻辑；保留普通操作刷新、
   精确路径、选择、游标、整理返回仍使用的状态。无效/消失目录的指引改用现存面包屑、
   根目录或刷新。共享 CSS 中抽屉类也被 Rules 消费，修改前查清消费者，只移除本页失效规则。
2. **替换四个配置入口的呈现。** 在两页原 Add/Edit 状态和表单模型上使用共享居中卡片；
   按内容组织字段/步骤、固定可达的标题/关闭/底部操作和有界正文。保留全部输入、编辑只读
   ID、精确投影与 Storage 选项、隐藏配置、验证及现有保存语义和后端权威边界；允许卡片
   所需的前端接线调整，不搬入自动化业务模型。
   显式编辑的读取过程有可见反馈，成功才允许用该投影保存；读失败给原合法刷新/重开路径。
3. **收好进出与提交状态。** 复用共享焦点/背景锁定/进出能力，关闭、取消、Escape、页面
   离开和回焦遵循现有未保存输入/在途规则。保存失败保留输入，冲突刷新真实 Active 后由
   用户明确决定；未知结果沿用既有核对，不通过动画或重挂载自动重发。成功名称编辑保留
   合法目录，绑定/根变化回正确根；禁用保留现有重新启用入口。
4. **完成库菜单和配置移除确认。** 改善现有选中库菜单的对象名称、图标文字、间距、普通/
   危险动作与 hover/focus/disabled/busy；菜单靠边和窄屏不裁切，操作仍指向该库。确认清楚
   展示库、Storage/根、引用限制和“只移除配置、保留物理文件”；沿用原确认/并发与引用
   检查，取消不发布配置。不要把条目文件 Delete 的业务重做一遍。
5. **两种库采用同一套实际等待反馈。** 先区分库信息未返回、真实空、无 Active、拒绝与
   失败，再分别处理目录读取。对未就绪区域用协调的占位/动效，内容就绪后平顺接入；
   快速响应/有效缓存直接呈现，不加延时或为动画串行读取。同条件刷新保持已有内容及
   刷新状态；切库/路径的反馈属于新上下文，不将迟到旧响应展示成新内容。沿用各自查询 key
   和认证边界，reduced-motion 提供静态反馈。
6. **从真实入口补验证。** 更新受布局替换直接影响的断言，保留其业务结果断言；在既有
   fake server、现有两种库组件及原生 harness 上补最少必要场景。测试名称和文件组织按
   实际职责安排，交接记录实际运行命令；由正常库菜单/添加按钮、文件夹与真实 API 完成旅程。
   慢读/迟到响应仅控制真实读取的返回时机，不捏造产品路由、命令或不可达状态。
7. **提交一个完整候选。** 更新直接受影响的文档事实，不改 Slice 边界/大版本状态；报告
   实现 SHA、改动、受影响测试实际结果和剩余问题，交 READY FOR B REVIEW。不要自验收。

### Acceptance Criteria

- [ ] 两页没有页内目录树及空白占位，文件区使用释放宽度，全局侧栏保留。文件夹、精确
  路径/边界空格、面包屑/上一级/根、搜索、刷新、视图、选择和有界分页可完成原浏览。
  例如进入子目录后名称编辑仍留该目录，根绑定变更则读正确新根。
- [ ] 添加/编辑资源库、添加/编辑媒体库四入口全部是与已接受自动化/存储协调的居中卡片。
  已有可编辑字段继续可编辑且准确回填，包括资源库规则/稳定性；编辑 ID 保持只读，
  未展示配置原样保留。
  正常入口/刷新/认证续转不自行打开配置卡片或保存。
- [ ] 一次显式保存发布真实 Active，成功后可浏览正确库；无效/重复输入、已存在的并发
  拒绝、读/保存失败和未知结果保持真实状态、可修正输入和原合法下一步。禁用能沿现有
  Web 路径恢复；配置添加/编辑/移除均不创建、迁移或删除物理目录/文件。
- [ ] 两页菜单与移除确认对象正确、层级清楚，媒体库名称不误称资源库；边缘/窄屏及键盘
  操作可达。取消无发布，引用阻塞显示实际原因，过期确认重新读取后由用户明确确认，
  无权限不放行；不删引用或调用条目 Delete 来移除配置。
- [ ] 可控慢读从首次进入到库信息、目录内容就绪，两页均有协调加载反馈且无假“未添加库/
  空目录”。真实空、无 Active、403/401、读取失败可辨并有合法下一步；同条件刷新保留
  可用内容，快速切库/路径及迟到响应不串库/路径；缓存和快速读取无需完整播放占位。
- [ ] 桌面 1536×1024 / 390px 窄屏实际检查长名称/路径、菜单边缘、四卡片及确认、打开到
  加载/就绪/关闭过程，正文有界滚动、底部/关闭可达，背景滚动和宽度稳定；焦点/键盘与
  reduced-motion 可用。动态证据与实际截图都要查看，不以固定 CSS/像素值代替用户结果。
- [ ] 原普通文件维护、当前页面操作状态及资源库整理/返回继续可达且归属正确；同名库 ID
  不混种类。关闭卡片不取消任务；成功刷新不重放成功项，并保留仍有效的无关选择。例如
  两个文件已选中，其中一个操作成功并刷新后，另一个仍有效且不受该操作影响的选择保留。
  开关卡片/菜单、浏览和加载不准入或重放变更；保持独立成功/失败/未知效果、
  原 pins/权限与 C 使用 A 命名/分类仍为 C 的已有自动化覆盖。

### Required Tests

测试分工按 [workflow §6](docs/development-workflow.md#6-test-levels)。T4 原因是两页同时
改动 Active 配置/引用与文件命令入口、共享样式及异步上下文呈现。Developer 只跑受影响
门禁；B 独立审查从上述 Task Base 到候选 Head 的完整累计差异，先复现关键问题，再跑
适用完整门禁。所有介质/数据库/Provider 都用隔离临时或本地合成环境。

### Developer — affected tests

以下命令 cwd `web/`，按最终实际改动加入新增测试文件，不扩大为全仓套件：

```sh
npm run test -- run src/features/library/StorageFilesPage.test.tsx src/features/library/MediaLibraryFilesPage.test.tsx src/features/library/MediaLibraryConfigDialogs.test.tsx src/features/library/LibraryFileOperationsDialog.test.tsx
npm run typecheck
npm run build
npm run test:e2e -- tests/e2e/library-files.spec.ts tests/e2e/medialib-files.spec.ts tests/e2e/medialib-config.spec.ts
npm run test:e2e -- --config=playwright.direct-files.python.config.ts tests/e2e/direct-files.python.spec.ts --grep 'reopens its own durable operation status|confirms once, waits for the real Worker'
```

以上覆盖既有两页浏览/配置、操作状态及基本 Worker 往返；新增/修改的场景必须运行，若不在
上述命令选集内，按实际文件/名称另加命令并记入交接，不依赖统一前缀或固定测试文件。
若改共享卡片逻辑，追加 `npm run test -- run src/shared/ui/modal-card.test.tsx`；若影响
存储消费者，追加 `npm run test -- run src/features/storage/StorageManagementPage.test.tsx`。
共享样式/外壳改动按实际影响补既有消费者场景；仅新增库页局部样式不自动要求存储/自动化
原生回归。ESLint/Prettier 只检查实际改动文件（`npx eslint <实际文件>`、
`npx prettier --check <实际文件>`），根目录运行
`.venv/bin/python scripts/check_governance.py`、`git diff --check`。修改 Python harness 时
补对应 Ruff/compile 检查与受影响原生场景；不要求 Developer 全量 Python/Web/E2E。

### B — acceptance and full regression

1. 审查完整 Base..Head，按上述真实入口验证全部 acceptance，核对实际 Active 与文件
   保留结果，桌面/窄屏查看截图及加载/弹卡进出动态。先核对交付，不先扩写过程工具。
2. 执行 [shared full gates](docs/development-workflow.md#shared-full-regression-commands)
   的 Python、Web、示例、禁止依赖、wheel/源码外 smoke 与适用安全覆盖。Docker/Compose/
   服务重启矩阵在仅前端呈现且未改部署/后端/schema/常驻合同的候选不适用，不能因此声称
   生产发布验证通过；若实际越过此边界，先重评范围与门禁。
3. cwd `web/`，生产构建后以下原生命令分别启动新临时环境，避免共享 fixture 被前一模块
   改动；完整 direct-files 覆盖既有普通操作/结果归属，live-files 覆盖两种库实时有界读取、
   精确路径和零变更。另须运行新增/修改的配置卡片与加载场景，证明两种库各自的真实
   Add/Edit/移除与 Active 读回、物理文件保留及本 Task 加载验收；可扩展既有模块或按职责
   组织测试文件，在评审记录写明实际命令和覆盖。需要的合成数据复用既有 harness，
   不建立另一套应用入口。

```sh
npm run test:e2e -- --config=playwright.direct-files.python.config.ts tests/e2e/direct-files.python.spec.ts
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/live-files.python.spec.ts
```

若共享卡片逻辑或共享样式实际影响存储/自动化消费者，按受影响对象运行以下原生模块，
各自使用新环境；仅库页局部改动不触发这些模块：

```sh
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/storage-dialog.python.spec.ts
npm run test:e2e -- --config=playwright.python.automation.config.ts tests/e2e/automation-create-dialog.python.spec.ts
```

保存精确候选、命令/cwd、实际结果/失败/skip及必要截图至现有稳定 ignored 证据目录。
复用 B 自己的旧结果须满足 workflow 的执行输入一致条件，变化的输入重新验收。
不把缺证据或时限未跑完记为产品缺陷或 PASS。

**本轮及后续每个实施/复核轮次，测试执行时间须小于该轮实际工作时间的 50%。**
用实际起止时间记录，失败运行也计入，多测试并行按占用时间区间并集统计；不空等凑比例。
优先代码/旅程审查，再安排风险对应测试；发现明确阻塞可提前 FIX REQUIRED，完整门禁未完
保持待验收，不删除断言、加重试或降低门禁来满足时间要求。不另建计时/验收平台。

### Non-goals 与全 Slice 重评

- 本 Task 不实现侧栏主页面切换，不重做其他页面业务或已接受 Task50.1/50.2 结果。
- 不增加 Provider/文件命令、任务/恢复类型、统计/缩略图、替代目录树、主题/动画设置，
  不重构后端配置/权限/队列或引入自动未知重放，不推送/部署。
- 当前：RO-1 已由 Task50.2 PASS；RO-2 与自动化稳定性由 Task50.1 PASS；RO-3 及两种库
  加载待本 Task 完整验收；RO-4 侧栏主页面切换仍未交付。本轮保存核对/冲突继续未通过，需同 Task 修正。
  本 Task 未来 PASS 后再次核对全部结果；侧栏切换仍缺则不能提交 Slice Closure Packet。

### Developer Completion Report / B Review Result

**READY FOR B REVIEW。** 候选为 `07e6b89f`，在 `main` 上单个实现 checkpoint；Task Base
仍为 `073e75a97d08f5ad02d4cbe9e2d9cc1efc89564d`。未推送、未部署，未自验收。

实现事实：

- 两页删除页内目录树、仅树消费的目录构建/记忆/发现链及空白占位；文件区占满释放宽度，
  文件夹行、面包屑、根目录、搜索、刷新、视图、选择与有界分页保持原入口。共享 Shell
  侧栏未改。
- 添加/编辑资源库与媒体库四个入口改为共享居中卡片；资源库保留规则与三项稳定性字段，
  编辑 ID 只读；显式编辑先显示精确读取状态，投影返回后才可保存，读取失败保留
  `重新读取`、原 `刷新 Active 状态` 与取消；保存失败保留输入与旧 Active。
- 两页对库信息未返回、目录读取、真实空、无 Active、拒绝与失败分别呈现；新增共享
  `library-loading.tsx` 与 reduced-motion 静态兜底；同条件刷新保留内容并显示刷新状态，
  查询键/认证边界未改，迟到旧响应不替换新库/路径。
- 选中库菜单按库种类命名（资源库/媒体库），普通/危险动作、图标、间距、focus/disabled
  与窄屏位置调整；移除确认、引用阻塞与文件保留说明沿用原实现。
- 仅删除本页失效的树/抽屉几何 CSS，保留 Storage 生命周期与 Rules/Storage 表单仍在
  消费的 `.mf-files-drawer`、步骤/正文/面板等共享类。

主要改动文件：`web/src/features/library/{StorageFilesPage.tsx,MediaLibraryFilesPage.tsx,
LibraryCardStrip.tsx,library-loading.tsx}`、共享样式 `web/src/shared/ui/styles.css`，
以及两页组件测试、媒体库配置弹卡测试、媒体库命令测试和受布局替换直接影响的三份
fake E2E 与 `operations-inventory.python.spec.ts` 的入口断言。

**Developer 实际验证（cwd `web/`）：**

| 命令 | 实际结果 |
|---|---|
| `npm run test -- run src/features/library/StorageFilesPage.test.tsx src/features/library/MediaLibraryFilesPage.test.tsx src/features/library/MediaLibraryConfigDialogs.test.tsx src/features/library/LibraryFileOperationsDialog.test.tsx` | 4 files / 99 tests passed |
| `npm run test -- run src/features/library`（直接受影响的整个库特性目录） | 7 files / 128 tests passed |
| `npm run typecheck` | passed |
| `npm run build` | passed |
| `npm run test:e2e -- tests/e2e/library-files.spec.ts tests/e2e/medialib-files.spec.ts tests/e2e/medialib-config.spec.ts` | 79 passed |
| `npm run test:e2e -- --config=playwright.direct-files.python.config.ts tests/e2e/direct-files.python.spec.ts --grep 'reopens its own durable operation status\|confirms once, waits for the real Worker'` | 4 passed |
| `npx eslint <实际改动 TSX/测试>`、`npx prettier --check <实际改动文件>` | passed |
| `python3 scripts/check_governance.py`、`git diff --check` | PASS |

实际查看了 1536×1024 文件页配置卡片截图和 390px 两页添加卡片/库菜单截图；窄屏菜单
标签不再逐字换行、普通/危险动作与图标可辨，卡片正文在视口内、底部操作可达。截图位于
ignored `web/test-results/`，动态进出过程与 reduced-motion 仍由 B 在验收中亲查。

**未执行（B 自有门禁）：** 完整 Web/Python 套件、`live-files` 与 Storage/自动化原生
模块、wheel/源码外 smoke、Docker/重启；这些不是 Developer 本轮失败的证据。剩余风险：
窄屏表格列仍沿用既有压缩规则（本 Task 未重做表格）；分页/动画/迟到响应的更广组合和
真实 Worker 慢读由 B 的完整门禁覆盖。测试运行约 7 分钟，约占本轮实际工作时间的 16%，低于 30%。

B 给 PASS 或 FIX REQUIRED，修复留在同一 Task，不另立修复任务。

### B Review Result — 2026-11-06

```text
Reviewed Base: 073e75a97d08f5ad02d4cbe9e2d9cc1efc89564d
Reviewed Head: bb75221cfc4e3ad6115a021b2d190535dc7ee508
Decision: FIX REQUIRED
Resolved: B50.3-01 — 合法未命名 Storage 不再阻塞两种库编辑
Task blockers: B50.3-02 — 保存结果未知被误报为未保存，并发冲突缺少保留输入的核对/继续
Slice Required Outcomes / Surfaces all satisfied: NO
Next: SAME TASK FIX LOOP
```

结合前轮完整审查，本轮核对完整 Base..Head 的 24 文件清单、全部修复增量及其现有消费
链路；产品修正为 `c52456b3`，随后 `bb75221c` 仅更新交接记录。B 未改产品或测试。
前轮结论与证据保留于 `1e3955b2:TASK.md`，本轮不重置 Task Base 或抹去前轮失败。

**B50.3-01 已修复。** 在同一既有真实 Python/API/SQLite/临时 Local harness 中，Active
仍含未命名 `media-target`；资源库 `source`、媒体库 `movies` 都能由菜单进入编辑，显示
原值及稳定 Storage ID，并各提交一次名称修改，后端成功发布、真实 `/edit` 读回新名称。
本次也审查了缺省启用的修正与新增两种库真实保存测试；没有要求用户先改无关 Storage。

**B50.3-02 / P1：保存结果未知与版本冲突没有可完成的核对/继续。**

这是原 Acceptance 第 3 条及 Slice AC-7 的失败/未知/并发恢复缺口，保留四入口和现有
后端合同，不新增配置能力、历史回执系统或通用重试引擎。

- **成功响应丢失：** 从添加资源库、编辑资源库、添加媒体库、编辑媒体库四个正常入口
  填写合法内容并保存。实际请求先交真实 API 完成，随后仅截断返回浏览器的成功响应，
  模拟断连；四次后端均 HTTP 200，各仅发 1 次变更。独立读取真实 `/edit` 均已保存，
  卡片却显示“候选…未保存，当前 Active 未被本次操作替换”，仍允许再次保存，且没有
  核实状态入口。这里没有伪造 API 成功或直接改数据库，配置确实已经发布。
- **真实两窗口冲突：** 两个独立浏览器上下文从同一库菜单打开编辑，分别输入名称。
  B 窗口先成功保存；A 窗口提交被真实 API 返回 `configuration_version_conflict`。
  卡片只提示“请刷新当前状态后重试”，但卡片内没有刷新/重新读取/核对动作，背景不可
  操作。再次点其现有保存按钮仍带同一旧版本，两种库均连续返回 409。用户只能取消后
  重开并重输本地修改，未完成要求的保留输入后核对并明确继续。

原因：`submitAutomationMutation` 把网络未确认返回为 `ok:false/transport_unavailable`
（成功体不可读取/解析返回 `malformed_response`），进入两页 `onSuccess(!result.ok)`，
并不会进入声称“结果未知”的 `onError`。两种 `*SaveFailure` 默认分支却把未确认当成
“确定未发布”。现有查询失效只刷新背景清单，未形成卡片内可见核对，也不更新原
`editExpected`；“重新读取/刷新 Active 状态”仅在打开编辑读失败时出现。

**Developer 修正指导（同一 Task）：**

1. 在两种库的 Add/Edit 保存状态中区分确定拒绝、结果未确认、成功及版本冲突。未确认
   只能说明结果待核实，不能断言旧 Active 未变；卡片说明/确认提示也应适用于这个实际
   状态。保留候选输入与提交对象，核对前不让普通 Save 变成重复提交，不自动重发。
2. 复用现有 Active/对象读取提供卡片内可达的只读核对。读取失败仍保留输入和未确认状态；
   核对成功只陈述能证明的当前配置，不能把“当前值相同”说成已证明原命令历史成功。
   当前对象已为所提交内容时应给出准确结果与合法退出；当前不同则说明现状，让用户复核
   后明确选择下一步。关闭/重开不能丢失尚待核对的上下文或静默再发；沿用既有权限与
   当前配置入口，不要求用户复制内部版本，也不引入新的后端能力。
3. 对确定的版本冲突，给出卡片内读取当前精确投影、保留本地意图、复核后明确保存的路径。
   新值与其 Active 身份必须配对；不自动覆盖别人变更、不只替换版本号、不自动合并提交。
   取消仍可退出，正常成功/无效输入/禁用/绑定变化及物理文件保留语义保持。
4. 参照已有 Storage 卡片的未知结果呈现/核对做法，仅复用适用行为；不要把 Storage 或
   自动化模型搬入库业务。补四个入口的真实成功后丢响应、核对读取失败与恢复，以及两种
   库的真实并发冲突→保留输入→读取当前值→明确继续场景。使用已有 API、浏览器上下文
   和隔离 fixture；不通过删断言、扩大超时、自动重试或新产品入口解决。

Developer 只运行新增/修改/直接受影响测试。cwd `web/` 的适配/组件基础命令：

```sh
npm run test -- run src/shared/api/library-api.test.ts src/shared/api/media-library-config-api.test.ts src/features/library/StorageFilesPage.test.tsx src/features/library/MediaLibraryFilesPage.test.tsx src/features/library/MediaLibraryConfigDialogs.test.tsx
npm run typecheck
npm run build
npm run test:e2e -- tests/e2e/library-files.spec.ts tests/e2e/medialib-config.spec.ts
```

另按实际组织运行新增原生保存/核对/冲突用例并记录精确命令；完整 T4 仍由 B 承担。

**来源与前序修复边界：** 未知误报由既有库保存失败分支继承：资源库源于 `a7cb15d6`
（2026-09-15），媒体库源于 `20fcf5f8`（2026-09-23）。B 使用 Task Base 的原始 Web 构建，
经相同真实 API 分别从两种库添加入口成功发布后截断响应，也复现相同误报；不是凭旧代码
猜测 Base 失败。后端/harness 在 Base..Head 无变化。`07e6b89f`（2026-11-06）的新弹卡把
背景设为不可操作，现有失败分支却仍指向背景刷新，没有接入卡片内核对/冲突继续。
本轮 `c52456b3` 修复的是编辑投影，它没有改动这些保存分支；前项已修复，本项仍须完成。

**本轮实际验证：**

- 当前候选生产构建 PASS；四个正常添加/编辑入口的丢响应结果均与真实 Active 对照；
  两种库双上下文冲突各完成一次真实先后保存和两次 409 对照；查看了窄屏未知结果截图。
- Task Base 两种库添加入口也复现未知误报。Base 产物复用前轮自原始源码独立构建的
  `073e75a9` Web，构建输入/依赖未变；只用于来源判断，不用作当前产品通过。
- 发现明确 P1 后提前 FIX REQUIRED，完整 Python/Web/E2E、wheel、其余原生/视觉/加载
  门禁未运行；不是以 Developer 缺这些结果为阻塞。治理与 whitespace PASS，文档消费者
  `test_release_security.py` **8 tests / OK**，不宣称完整验收。
- 稳定本地证据 `.git/validation-evidence/bb75221c/B50.3-review/`：`build.json`、
  `native-probe.json`（两种编辑）、`add-unknown-probe.json`（当前两种添加与 Base 对照）、
  `conflict-probe.json`、对应原始日志/探测源码/PNG；`doc-checks.json`、`review-timing.json`
  保存最终文档门禁与测试时间。证据仅本地可取，未接触用户数据、媒体或私有配置。
  本轮从 `13:01:21 UTC` 至计时记录工作 341.69 秒，测试区间并集 8.07 秒；计入环境准备/
  零散检查的保守 30 秒上界后总计 38.07 秒，低于本轮 12%，满足小于 50%。

**全 Slice 重评：** RO-1（Task50.2）、RO-2 与自动化稳定性（Task50.1）保留既有 B PASS；
RO-3 的保存恢复尚未通过，加载实现待完整验收；RO-4 主页面切换仍未交付。Slice50 保持
ACTIVE，修复留在 Task50.3，不规划下一 Task，不交 Closure Packet，不宣告 Slice 关闭。

### Developer Fix Report — 2026-11-06

**READY FOR B REVIEW。** 修正候选为 `c52456b3b5e4eee3166ad79c6e361458fedb729c`，
在 `main` 上单个实现 checkpoint；Task Base 仍为
`073e75a97d08f5ad02d4cbe9e2d9cc1efc89564d`。未推送、未部署，未自验收。

实现事实：

- `fetchLibraryEditProjection` 现在接受合法 Active 中未填写的 Storage 显示名称
  （`null`、缺省或空字符串），仅在展示标签上回退稳定 Storage ID；提交仍使用精确
  Storage ID，种类、只读、启用及 Active fence 校验不变，非文本名称继续按
  `malformed_response` 失败关闭。读取卡片不改写、不发布配置。
- 同一次真实菜单验证暴露出同一编辑旅程的默认启用合同缺口：合法 Active 可省略
  库的 `enabled`，而原适配器把缺省判为 `false`，只改名称也会把库保存为停用。两种库
  的编辑归一化现按运行时与 Save 合同把缺省视为启用，显式 `false` 仍为停用。
- 新增 `playwright.direct-files.python.config.ts` 原生场景：真实 Python/API/SQLite/
  临时 Local fixture 的 Active 含合法未命名 Storage `media-target`；分别从文件页
  `source` 菜单和媒体库页 `movies` 菜单进入编辑，确认原值、只读 ID、未命名 Storage
  以 ID 展示；只改名称保存后从真实 `/edit` 读回名称、启用、Storage 绑定与根，并对
  保存前后真实文件列表做等值核对。资源库场景中的未命名 Storage 与当前绑定无关。
- 未改后端、harness、产品入口或共享页面结构；没有为测试构造不可达状态。

**本轮实际验证（cwd `web/`）：**

| 命令 | 实际结果 |
|---|---|
| `npm run test -- run src/shared/api/library-api.test.ts src/shared/api/media-library-config-api.test.ts` | 2 files / 45 tests passed |
| `npm run test -- run src/features/library/StorageFilesPage.test.tsx src/features/library/MediaLibraryFilesPage.test.tsx src/features/library/MediaLibraryConfigDialogs.test.tsx src/features/library/LibraryFileOperationsDialog.test.tsx` | 4 files / 99 tests passed |
| `npm run typecheck` | passed |
| `npm run build` | passed |
| `npm run test:e2e -- tests/e2e/library-files.spec.ts tests/e2e/medialib-files.spec.ts tests/e2e/medialib-config.spec.ts` | 79 passed |
| `npm run test:e2e -- --config=playwright.direct-files.python.config.ts tests/e2e/direct-files.python.spec.ts --grep 'reopens its own durable operation status\|confirms once, waits for the real Worker'` | 4 passed |
| `npm run test:e2e -- --config=playwright.direct-files.python.config.ts tests/e2e/direct-files.python.spec.ts --grep 'both library edit cards accept a legal Active with an unnamed Storage'` | 1 passed |
| `npx eslint <实际改动文件>`、`npx prettier --check <实际改动文件>` | passed |
| `python3 scripts/check_governance.py`、`git diff --check` | PASS |

新增/修改测试：两份 API 适配测试各覆盖未命名 Storage 回退、缺省启用和非文本名称
拒绝；原生场景覆盖两种库的真实菜单、Active 读回与零文件变化。失败的早期探测保留
在本地 ignored `web/test-results/`，未删除断言、未加重试或放宽超时。

**未执行（B 自有门禁）：** 完整 Web/Python 套件、`live-files`、Storage/自动化原生
模块、wheel/源码外 smoke、Docker/重启及完整 T4 视觉/加载验收；这些不是 Developer
本轮失败的证据。剩余风险：未命名 Storage 的展示标签现为稳定 ID，若未来产品要求
独立显示名需另立设计；B 仍需在相同原生 fixture 上复核真实菜单与保存结果。

本轮从 `2026-11-06T12:48:52Z` 开始，约 `12:56Z` 交接（约 7 分钟）；测试执行约
100 秒（含失败重跑与直接受影响 E2E），约占本轮实际用时的 24%，低于 30%。

### Developer Fix Report — 2026-11-06 (B50.3-02)

**READY FOR B REVIEW。** 修正候选为 `fd4df8ea36fefb59f003f494f06724b35ccc9d2e`，在 `main` 上两个实现 checkpoint（`ec3dbc3b` 恢复旅程 + `fd4df8ea` 按入口保留待核对上下文）；
Task Base 仍为 `073e75a97d08f5ad02d4cbe9e2d9cc1efc89564d`。未推送、未部署，未自验收。

实现事实：

- 新增共享 `library-save-recovery.tsx`：保存结果按 `definite / unknown / conflict` 区分。
  收到明确 `candidateState: not_*` 的 5xx 仍算确定拒绝；`transport_unavailable`、
  `malformed_response`、`internal_error`、`service_unavailable`、status 0 或缺少候选
  状态的 5xx 算未确认；`configuration_conflict` / `configuration_version_conflict`
  单列。卡片内提示复用现有 `mf-storage-verify` 呈现，只提供“核对当前配置”一个读取。
- 两种库的 Save 失败映射新增 `outcome` 与可选 `status`。未确认消息改为“响应没有送达
  或无法解读，候选…可能已经发布…不会自动重发…请核对当前 Active”；不再声称旧 Active
  未被替换。冲突消息改为“请核对当前配置后再决定是否保存”。卡片说明与确认提示由
  “失败时”改为“被拒绝时”，避免把未确认结果说成已证明未发布。
- 两页 Add/Edit 保存：未确认/冲突时保留提交候选、编辑身份、原绑定 baseline 与提交时
  Storage 选项；普通 Save 被禁用并给出原因，核对前不会重复提交。核对复用既有精确
  `/edit` 投影：读取失败保留输入和待核对状态；成功且当前配置等于提交内容时只陈述
  “当前 Active 已是本次提交的配置”，以唯一“关闭”退出；当前不同则列出名称、Storage、
  根路径与状态，保留输入并把刚读到的 Active 身份配给下一次显式保存；Add 的
  `*_not_found` 证明未发布并允许显式重试；Edit 的对象已消失时给出唯一合法退出。
- 关闭/重开：未确认保存按精确入口（一个添加槽位、每个编辑库一个）保留并跨关闭恢复，
  重开同一库/添加入口直接显示提交候选及其 Storage 选项，不读投影、不重发；无关库的
  成功保存不会清除或替换该上下文。确定冲突在关闭后清除，重开编辑照常读取当前投影。
  核对结束后焦点交给底部仍可用的主操作（显式保存或唯一关闭）。
- 显式继续时使用刚核对的 `expectedRevisionId/expectedVersion/expectedDigest` 与保留
  候选一起提交；不自动 rebase、合并、覆盖别人变更或重发。未加后端能力、产品路由或
  新入口；正常成功、无效输入、禁用、绑定变化与物理文件保留语义不变。

**新增/修改测试：** 两页组件测试覆盖未确认 Add、编辑未知结果的关闭/重开、核对读取
失败与恢复、冲突后读取当前值再显式保存（断言 PUT 携带新 Active 身份）；媒体库卡片
测试覆盖核对块、Save 门禁、核对失败提示、已核对后的唯一退出；共享分类与候选匹配
（规则/稳定性）各有断言。原生 `direct-files.python.spec.ts` 新增四个真实场景：两种库
各覆盖（a）Add 与 Edit 的真实 API 已完成、仅浏览器成功响应被中断，候选保留、Save
门禁、核对证明当前 Active、关闭/重开保留、核对读取 503 后重试恢复；（b）两个真实
浏览器上下文先后保存，A 收到真实 409、保留输入、核对到获胜名称后显式保存成功。
后端确实发布，只截断浏览器响应，未伪造 API/数据库。

**本轮实际验证（cwd `web/`）：**

| 命令 | 实际结果 |
|---|---|
| `npm run test -- run src/features/library/StorageFilesPage.test.tsx src/features/library/MediaLibraryFilesPage.test.tsx src/features/library/MediaLibraryConfigDialogs.test.tsx src/features/library/LibraryFileOperationsDialog.test.tsx` | 4 files / 109 tests passed |
| `npm run test -- run src/features/library` | 7 files / 138 tests passed |
| `npm run typecheck` | passed |
| `npm run build` | passed |
| `npm run test:e2e -- tests/e2e/library-files.spec.ts tests/e2e/medialib-files.spec.ts tests/e2e/medialib-config.spec.ts` | 79 passed |
| `npm run test:e2e -- --config=playwright.direct-files.python.config.ts tests/e2e/direct-files.python.spec.ts --grep 'library save recovery\|reopens its own durable operation status\|confirms once, waits for the real Worker'` | 8 passed（4 新增 + 4 既有） |
| `npx eslint <实际改动文件>`、`npx prettier --check <实际改动文件>` | passed |
| `python3 scripts/check_governance.py`、`git diff --check` | PASS |

实际查看了 1536×1024 与 390px 媒体库添加卡片的未确认状态截图（ignored
`web/test-results/`）：候选值、核对动作与底部操作均在视口内可达。失败的早期探测保留在
本地 ignored 结果目录，未删除断言、未加重试或放宽超时。

**未执行（B 自有门禁）：** 完整 Web/Python 套件、`live-files`、Storage/自动化原生
模块、wheel/源码外 smoke、Docker/重启及完整 T4 视觉/加载验收；这些不是 Developer
本轮失败的证据。

剩余风险：重开未确认 Add 时 Storage 下拉使用当前已启用集合，提交的 Storage ID 仍是
候选原值；若该 Storage 期间被停用，Save 仍被核对门禁挡住，B 可复核该边缘。确定冲突的
上下文在关闭后清除（下次编辑读取当前投影）；未确认上下文按页面内精确入口保留并跨
关闭/重开恢复，但不跨整页重载，因为本轮未引入新的持久客户端记录或后端能力。核对只证明当前配置，不证明原命令
历史成功，文案保持该边界。窄屏动态过程与 reduced-motion 仍由 B 的 T4 验收覆盖。

本轮从约 `2026-11-06T13:14Z` 开始，约 `13:50Z` 交接（约 36 分钟）；测试执行约
6.5 分钟（含失败运行与重跑），约占本轮实际用时的 18%，低于 30%。

### 激活基线与前序接受事实

激活前分支 `main`、HEAD `b067b34e30f63631477a5a092eba99956cecb893`；治理预检 PASS，
workspace/Git 可写。相对原 Task Base 的累计差异仅为 `TASK.md` 草案及断言修订，产品、
测试、harness 与依赖均未改变，保留原 Task Base、Goal、Scope、High/T4 和修订后验收。

Task50.2 的 B PASS 及完整报告保留于 `073e75a97d08f5ad02d4cbe9e2d9cc1efc89564d:TASK.md`，
精确已审范围为 `575898ebaae593568be59699bb40116f9e6f2d91..61d37285652c0eae2553f3bc970895476277bc0f`；
本 Task 的修订草案保留于 `b067b34e30f63631477a5a092eba99956cecb893:TASK.md`。
激活不重开前序 Task，不代表本 Task PASS 或 Slice 关闭。

预存 `mediaflow/.DS_Store` 修改及未跟踪 `.DS_Store`、日志、`15`、`output/` 产物全部保留，
不纳入 checkpoint；不接触用户数据库、私有配置或生产媒体。本轮只执行 Developer 受影响
测试与静态检查，不声称完整回归或 Slice 验收；测试运行时间低于本轮实际用时的 30%。
