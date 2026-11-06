# Task 50.3 — 两种库的完整浏览布局、配置弹卡与加载体验

用户于 2026-11-06 明确授权激活本 Task。B 独立审查后给出 FIX REQUIRED：两种库的
真实编辑入口尚有阻塞，按下方指导在同一 Task 修正；本轮不推送或部署。

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
Candidate: 04992b8cd2c690112f4fe009cb0560e7663746cc
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
  加载待本 Task 完整验收；RO-4 侧栏主页面切换仍未交付。本轮两种库编辑未通过，需同 Task 修正。
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
Reviewed Head: 04992b8cd2c690112f4fe009cb0560e7663746cc
Decision: FIX REQUIRED
Task blockers: B50.3-01 — 合法 Active 含未命名 Storage 时，两种库均无法进入编辑表单
Slice Required Outcomes / Surfaces all satisfied: NO
Next: SAME TASK FIX LOOP
```

已审完整 Base..Head 的 20 个文件，包括规划/激活文档、两页与共享菜单/加载/样式、组件
和 E2E 的累计差异；B 未修改产品或测试。去树、四个卡片容器及加载分支已有实现，但
RO-3 的完整编辑旅程尚不成立；当前记录不代表其他场景已完成独立验收。

**B50.3-01 / P1：正常可浏览的库打不开编辑表单。**

在现有 `playwright.direct-files.python.config.ts` 使用的真实 Python/API/SQLite/临时
Local harness 中，Active 有一个合法未命名 Storage `media-target`。从文件页选择
`source`，点库菜单 → 编辑资源库；或从媒体库页选择 `movies` → 编辑媒体库，后端编辑
读取均返回 HTTP 200，卡片却显示“无法读取…请重新读取…确认权限和…状态”，没有名称
字段或保存入口。分别点“重新读取”仍失败，取消可退出；两条旅程均未发出变更命令。
这里没有伪造失败响应或输入，使用的是既有 harness 的已发布 Active 和正常库菜单。

原因在 `api-client.ts` 的 `fetchLibraryEditProjection`：它要求返回的每个 Storage 名称
必须为字符串；后端 `_edit_storage_projection` 对未填写名称的合法配置返回 `null`，
客户端因此把整份投影判为 malformed。即使未命名 Storage 不是该资源库当前绑定对象，
也会阻塞编辑。刷新或重新读取不改变这个合同差异，现有错误提示无法帮助用户完成目标。

**Developer 修正指导（同一 Task）：**

1. 对齐现有编辑投影与合法 Active 的显示名称语义。允许未填写的 Storage 显示名称，
   在需要可读标签时使用其稳定 ID（参照既有 Storage 投影/显示惯例）；保留精确 Storage
   ID、种类、路径、启用状态、Active fence 和其他已有校验。此修正只处理已支持配置的
   显示合同，不要求用户先给无关 Storage 补名称，不因读卡片而改写或发布配置。
2. 从两种库现有菜单验证：Active 含未命名 Storage（包括无关 Storage）时，编辑卡片
   能读到正确原值，ID 仍只读；只改名称并保存后读取真实 Active，库启用状态、绑定、
   根、未编辑配置与合法浏览位置保持原义，物理文件不变。保留真正拒绝/读失败的恢复。
3. 补直接受影响的 API 适配测试及两种库原生入口覆盖；复用当前已能触发问题的隔离
   fixture，不新增产品入口或一套验收平台。开发仅跑修改/直接受影响测试，交新精确
   checkpoint；完整 T4、剩余原生配置/加载/视觉验收仍由 B 承担。

API 适配受影响命令（cwd `web/`）：
`npm run test -- run src/shared/api/library-api.test.ts src/shared/api/media-library-config-api.test.ts`。
此外按上方 Developer 计划运行本次改变的组件/原生场景，并在交接记录实际文件与选择命令。

历史来源：源码追踪到 `1ecb278120776f4844d78b394c50ae254d6e7ecf`（2026-09-25），
这不是本 Task 新引入的回归。B 另用 Task Base 的原始 Web 源码构建产物，经同一真实 API/
临时配置，从相同 `source`/`movies` 页面菜单独立复现两种库编辑失败；后端/harness 在
Base..Head 无变化。这是当前未关闭 Slice/Task 必须交付的编辑结果缺口，留在本 Task 修正，
不改写旧 Slice 的接受事实、不另开独立小 bug。

**本轮 B 证据与门禁：**

- 当前候选生产构建 PASS；当前两种库编辑入口阻塞各复现 1 次，并分别显式重新读取验证，
  HTTP 200、字段数 0、变更命令数 0；已打开桌面/390px 窄屏错误截图检查。
- Base 的两种库相同入口均复现相同失败；证据仅用于确定历史来源，不计作当前产品通过。
- 首次计划验证保存结果的原生探测在进入资源库表单前就失败，未执行保存；首次 Base 探测
  的媒体库未指定库而落在无表格的空库，命令失败。原日志保留，之后显式选择真实 `movies`
  入口完成复现；没有修改断言、加重试或扩大超时。
- 治理预检/记录更新后检查、完整差异 whitespace PASS；文档消费者 `test_release_security.py`
  **8 tests / OK**。发现明确 P1 后提前 FIX REQUIRED，未运行完整
  Python/Web/E2E、wheel 或其余原生门禁；不以 Developer 缺少这些结果作为产品阻塞。
- 稳定本地证据：`.git/validation-evidence/04992b8c/B50.3-review/`。`build.json`、
  `edit-read.json`、`base-build.json`、`base-edit-read.json`、首次失败 JSON/log、探测源码和
  PNG 保留实际执行输入/结果；本地文件不宣称远程可取。计时及最终文档检查见 `review-timing.json`。
  从 `12:31:36 UTC` 起至计时记录已工作约 501 秒，带起止记录的测试区间并集 15.67 秒；
  加上环境准备/零散检查的保守 60 秒上界，总测试时间仍低于本轮 16%，满足小于 50%。

**全 Slice 重评：** RO-1（Task50.2）、RO-2 和自动化稳定性（Task50.1）保留既有 B PASS；
RO-3 本轮编辑阻塞，加载已有实现但待完整验收；RO-4 侧栏主页面切换仍未交付。Slice50
保持 ACTIVE，不规划下一 Task，不交 Closure Packet，不宣告 Slice PASS / CLOSED。

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
