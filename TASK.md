# Task 50.3 — 两种库的完整浏览布局、配置弹卡与加载体验

用户于 2026-11-06 明确授权激活本 Task。未命名 Storage、保存恢复及核对期间/完成后的
只读状态均已通过 B 复验，原生慢目录视觉验收已补完。认证测试的运行断言已通过，
但新回调与辅助函数签名不一致，类型检查失败；当前 FIX REQUIRED，同 Task 修正测试类型。

Authority：已提交 [Slice50](SLICE.md) 的 RO-3 全部、RO-4 两种库加载部分；对应
`V2-UX-009–011`、`V2-UX-012` 的加载部分及 AC-5/6/7/9、适用 AC-10/11。
生命周期、测试和 Git 按 [Development Workflow](docs/development-workflow.md)，角色按
[B 指南](docs/agent-experience/task-planner-reviewer.md)。本 Task 把同一库页的加载与
布局一并交付；合同允许 B 按真实依赖调整建议分组，侧栏主页面切换仍待后续任务。

```text
Task ID: 50.3
Task Type: SLICE
Parent Slice: 50
Status: FIX REQUIRED
Task Base: 073e75a97d08f5ad02d4cbe9e2d9cc1efc89564d
Candidate: 66ac0f06c3d7b2d63263626c3713335057ad8e3d
Difficulty: High
Test Level: T4
Planner / Reviewer: B
Working Branch: main
Development Authorization: TASK 50.3 ONLY; SAME TASK FIX LOOP
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
  加载交互已核对；完整门禁尚缺修正后的 Web 全量通过。RO-4 侧栏主页面切换仍未交付。
  认证测试运行已通过，辅助函数类型需同 Task 修正。
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
Reviewed Head: 66ac0f06c3d7b2d63263626c3713335057ad8e3d
Decision: FIX REQUIRED
Resolved: 未命名 Storage、保存恢复/只读一致性；认证空态断言；原生慢目录视觉证据
Task blocker: AuthBoundary.test.tsx 新回调与 stubFetch 类型不匹配，npm run typecheck 失败
Slice Required Outcomes / Surfaces all satisfied: NO
Next: SAME TASK FIX LOOP; CORRECT THE TEST HELPER TYPE
```

**完整范围与实际结果。** 延续前轮独立源码/旅程审查，本轮核对原 Task Base..Head 的
完整 26 文件累计差异和当前提交。`37465bd4..66ac0f06` 只改 TASK.md 与
`web/src/shared/auth/AuthBoundary.test.tsx`；全部产品源码、库测试、API、原生/fake E2E、
harness、依赖及配置未变。`5d60aae6..66ac0f06` 仅为文档交接。原 Base、Goal、Scope、
High/T4 均保留，B 未改产品或测试。前轮完整结论和日志指针保留于 `7c2824b6:TASK.md`。

用户已登录后直接进入媒体库：测试现在显式提供合法空列表与真实请求的 system status，
等待实际空态后验证仍在媒体库路由、token 保留、无待续转路径且未返回连接入口。这一
方向正确。B 独立运行认证与媒体库页面测试，**2 files / 24 passed**，包括读取未返回
不能显示假空态的既有用例。先前失败的运行断言已修正。

**唯一已证实的剩余阻塞是测试编译类型。** `npm run typecheck` 实际 exit 2：

- `AuthBoundary.test.tsx:75`：TS2345，`(input) => Promise<Response>` 不能作为
  `() => Promise<Response>` 参数；TS7006，`input` 隐含为 any。
- 当前文件的 `stubFetch` 仍把 implementation 声明为无参数函数，新实现却需要读取请求
  地址。Vitest 执行时可收到地址，但 TypeScript 严格检查不通过。这由 `5d60aae6`
  （2026-11-06 22:58 +08:00）新增 callback 引入；不是媒体库页面或认证产品故障。

**Developer 开发指导：**

1. 仅修正本文件 `stubFetch` 的 implementation 参数类型，使其表达实际 fetch 的请求
   输入及可选 init。可采用 `typeof fetch` 或与当前调用一致的准确函数签名；现有无参数
   callback 仍应可用。不要用 any、类型强转、ts-ignore 或关闭检查绕过问题。
2. 保留当前合法响应、空态和路由/token/续转断言，保留媒体库的 pending/真实空态测试。
   不改产品代码、加载语义、认证边界、共享测试工具或其他功能。
3. cwd `web/` 运行以下直接受影响检查，交一个完整 checkpoint，READY FOR B REVIEW。
   全量 Web/Python/E2E 仍由 B 负责，不交回 Developer：

```sh
npm run typecheck
npm run test -- run src/shared/auth/AuthBoundary.test.tsx src/features/library/MediaLibraryFilesPage.test.tsx
npx eslint src/shared/auth/AuthBoundary.test.tsx
npx prettier --check src/shared/auth/AuthBoundary.test.tsx
```

根目录运行治理与 whitespace 检查。修正留在本 Task，不增加新任务或新产品能力。

**B 补完的原生视觉验收。** 在同一现有临时 Python/API/SQLite/Local harness 和未变的
生产资产上，通过正常两页入口，保持真实库信息响应、目录响应分别等待后释放；本轮
匹配实际带/不带 query 的现有 files URL，修正了上轮 B 取证漏拦根目录响应的问题。
1536×1024 / 390×844 两种库共四种组合均完成“库读取→目录读取→真实文件→刷新保留
内容”。B 已逐张查看四份实际目录加载截图：协调占位、正确库/根、无假空目录；再释放
真实响应后显示内容。原生慢目录取证欠项已完成，不留给 Developer。
同时复核四入口卡片的慢读到就绪/关闭、菜单/移除取消、焦点回交、背景锁定释放与
reduced-motion；四种组合均无变更请求、无页面横向溢出，卡片几何稳定。

**门禁与复用。** 当前新跑 typecheck FAIL、受影响单元测试 24 PASS，以及上述真实
交互 PASS。匹配输入的上轮 B 结果仍有效：Python 2603 tests / OK（7 原有条件 skip）、
Ruff/compileall/pip check/两个配置示例/禁止依赖检查、Web build、默认 E2E
255、原生 direct/live/operations/storage **27/5/43/8**、wheel/源码外 smoke 均通过。
生产产物仍为 `index-CSCBu9QV.css` / `index-DZ6qj7GM.js`，与上轮构建日志一致。
当前 Web 测试文件已改变，上轮全量 lint/format 仅保留为历史结果；未复用上轮失败的
全量单元运行作为通过。发现编译阻塞后未
启动该昂贵门禁，修正后仍须由 B 跑全量 Web 单元与变化输入对应的检查才可 PASS。
Docker/重启未因纯测试改动新增适用性，不声称生产部署通过；未推送、未部署。

证据：本地稳定 ignored `.git/validation-evidence/66ac0f06/B50.3-review/` 中
`web-typecheck.*`、`affected-unit.*`、`visual.*` 与四组合 PNG；匹配上轮证据在
`.git/validation-evidence/37465bd4/B50.3-review/`。治理与 whitespace PASS，文档消费者
`test_release_security.py` **8 tests / OK**。本轮自 `15:07:16 UTC` 至计时记录共
238.95 秒，测试/门禁区间并集 16.95 秒，另计准备与零散检查保守 10 秒后
上界 26.95 秒（11.3%），低于 50%；见 `review-timing.json`，未空等凑比例。
预存 dirty/untracked 全部保留，本轮 B checkpoint 仅含 TASK.md。

**全 Slice 重评。** RO-1（Task50.2）、RO-2 与自动化稳定性（Task50.1）保持既有 B PASS；
RO-3 和库加载的交互已验证，但 Task50.3 的 T4 尚缺当前类型/全量 Web 通过。RO-4 侧栏
主页面切换仍未交付。Slice50 保持 ACTIVE；同 Task 修正，不自动规划下一 Task，不交
Closure Packet，不宣告 Slice PASS / CLOSED。

### Developer Fix Report — 2026-11-06 (B50.3-01 auth test)

**READY FOR B REVIEW。** 修正候选为 `5d60aae6f49e4219db7ce4a47f0841c8ed81dd2a`，
在 `main` 上单个测试 checkpoint；Task Base 仍为
`073e75a97d08f5ad02d4cbe9e2d9cc1efc89564d`。未推送、未部署，未自验收。

实现事实：

- `AuthBoundary.test.tsx` 的 `keeps a still-authenticated operator on the deep route`
  现为页面实际请求的 `/api/v1/media-libraries` 返回合法空列表，为
  `/api/v1/system/status` 返回合法状态；未命中测试请求会直接失败，不隐藏额外调用。
- “尚未添加媒体库”仍在显式空列表返回后断言，不再充当读取未完成时的路由成功标志。
  同时断言真实 router 停留于 `/medialib/files`、token 保留、intended path 为空且
  未回到 API token 连接入口。
- 未改产品加载分支、认证/恢复语义或其他测试；`MediaLibraryFilesPage.test.tsx` 中
  的“等待期间无假空态、空列表返回后才出现空态”断言保持不变。

**本轮实际验证（cwd `web/`）：**

| 命令 | 实际结果 |
|---|---|
| `npm run test -- run src/shared/auth/AuthBoundary.test.tsx src/features/library/MediaLibraryFilesPage.test.tsx` | 2 files / 24 tests passed |
| `npx eslint src/shared/auth/AuthBoundary.test.tsx` | passed |
| `npx prettier --check src/shared/auth/AuthBoundary.test.tsx` | passed |
| `python3 scripts/check_governance.py`、`git diff --check` | PASS |

**未执行（B 自有门禁）：** 全量 Web/Python 套件、typecheck/build、E2E 与原生模块；
本修正只改测试 fixture/断言，未改产品代码，不把这些门禁记为 Developer 通过或失败。
剩余风险：测试中的空列表响应为立即完成，真实 pending 与迟到场景继续由既有
`MediaLibraryFilesPage` 测试和 B 的完整门禁覆盖。

本轮从约 `22:50 +08:00` 开始，约 `22:59 +08:00` 交接；测试执行约 4 秒，连同
静态检查约 8 秒，低于本轮实际用时的 30%。预存 dirty/untracked 全部保留。

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

本轮从约 `2026-11-06T13:14Z` 开始，约 `13:56Z` 交接（约 42 分钟）；测试执行约
8 分钟（含失败运行、按入口恢复修正后的重跑），约占本轮实际用时的 19%，低于 30%。

### Developer Fix Report — 2026-11-06 (B50.3-02 input state)

**READY FOR B REVIEW。** 修正候选为 `995bce3bcbda138e370147888585ffd5832d3b0c`，
在 `main` 上单个实现 checkpoint；Task Base 仍为
`073e75a97d08f5ad02d4cbe9e2d9cc1efc89564d`。未推送、未部署，未自验收。

实现事实：

- `ResourceLibraryConfigCard` / `MediaLibraryConfigCard` 的正文输入在
  `recovery !== null` 或 `verified !== null` 时禁用：保存结果待核对、核对进行中，以及
  核对证明当前已是本次提交或编辑对象已不存在时，只展示提交值；步骤、核对和原关闭/
  取消入口继续可用。核对证明当前 Active 与提交不同时，父页面清空待核对状态，正文
  恢复编辑，显式保存沿用刚读到的 `expectedRevisionId/expectedVersion/expectedDigest`。
- 编辑 ID 的既有只读、精确投影、提交重发门禁、未知/冲突分类和按入口保留恢复上下文
  均未改变；未新增草稿/版本系统、后端能力或产品入口。
- 新增/修改组件测试覆盖待核对与核对中只读、核对完成后仅关闭、核对不同后恢复编辑并
  提交新候选；页面测试覆盖真实菜单/添加入口的待核对只读、编辑后以新 Active 身份保存；
  原生 `direct-files.python.spec.ts` 的四个既有恢复场景各补真实入口只读断言。

**本轮实际验证（cwd `web/`）：**

| 命令 | 实际结果 |
|---|---|
| `npm run test -- run src/features/library/StorageFilesPage.test.tsx src/features/library/MediaLibraryFilesPage.test.tsx src/features/library/MediaLibraryConfigDialogs.test.tsx src/features/library/LibraryFileOperationsDialog.test.tsx` | 4 files / 114 tests passed |
| `npm run typecheck` | passed |
| `npm run build` | passed |
| `npm run test:e2e -- --config=playwright.direct-files.python.config.ts tests/e2e/direct-files.python.spec.ts --grep 'library save recovery'` | 4 passed |
| `npx eslint <实际改动文件>`、`npx prettier --check <实际改动文件>` | passed |
| `python3 scripts/check_governance.py`、`git diff --check` | PASS |

原生首次运行有 2 个测试失败：新增的“保存并激活”可用性断言放在第 1 步，按钮只存在于
第 3 步；将断言移到两步导航之后重跑，4 passed。该失败是测试断言位置错误，不是产品
行为失败，已保留为实际执行记录。

**未执行（B 自有门禁）：** 完整 Web/Python 套件、`live-files`、Storage/自动化原生
模块、wheel/源码外 smoke、Docker/重启及完整 T4 视觉/加载验收；这些不是 Developer
本轮失败的证据。剩余风险：只读态依赖现有禁用呈现，B 仍需在实际桌面/窄屏与键盘/
reduced-motion 旅程中确认视觉与可达性；核对不同后的编辑恢复由 B 复核真实输入。

本轮从约 `2026-11-06T14:02Z` 开始，约 `14:15Z` 交接（约 13 分钟）；测试执行约 70 秒
（含一次断言位置修正的失败重跑），约占本轮实际用时的 9%，低于 30%。

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
