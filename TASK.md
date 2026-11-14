# Task PATCH-20261114-2 — 文件浏览工具栏与表头呈现修复

Next Action: Developer 按本 Task 开始实施，完成受影响测试后提交 READY FOR B REVIEW。

用户于 2026-11-14 在规划检查点 `d3d984a50d3364d06f9e763a1231d4299b5a1e9b`
后明确“激活 Task”，本 Task 正式启用并授权实施。原 ID／Base／目标／范围／测试分工
保持；激活检查点仅更新本文件，不改产品代码、现行产品文档、SLICE、Roadmap 或 Progress。

```text
Task ID: PATCH-20261114-2
Task Type: STANDALONE MINOR BUG
Parent Slice: NONE
Status: PLANNED
Task Base: 4107c299d8f99b817fcd3cbdffa274de1f5598ea
Difficulty: Medium
Test Level: T3
Planner / Reviewer: B
Implementation Authorization: USER AUTHORIZED ON 2026-11-14
```

### Goal and authority

修复截图所示文件浏览排序栏／表头的视觉层级与可用性：两种库页采用协调、紧凑的
排序状态、显示设置和表头，让文件内容成为主体，恢复操作保持易找且不抢占常驻一行。
这是既有浏览能力的有界呈现修复，不增加业务能力，不重开已接受 Slice。

依据 [Development Workflow](docs/development-workflow.md) §3.1／§6、
[UX-001／002／007](docs/requirements.md#operator-experience-requirements)、
[V2-FILES-005](docs/v2-requirements.md#fileindex-retirement-and-shared-live-lists--current-slice45-pass--closed)、
[完整文件浏览旅程](docs/product-experience.md#real-storage-files)、
[排序与列宽旅程](docs/product-experience.md#browse-feedback-selection-and-table-controls)，以及
[Files](docs/file-page-visual-spec.md)／[MediaLibrary](docs/media-library-page-visual-spec.md)
现行规范。用户本次重设计意图仅替换排序独立行、重置入口和表头的具体呈现，原业务、
安全、会话和恢复语义保持；实施交付时再协调这些具体呈现措辞。

规划起点：仓库 `/Users/songzhidong/mediaflow`，分支 `main`，HEAD 为 Task Base，
规划前 tracked／untracked 工作区均无变更，TASK 与 Git 可写；治理预检 PASS。
未读运行数据库、私有配置、凭据或用户媒体。调查依据为用户截图、代码及约定，
尚未启动浏览器验收；截图中的大空白对应名称列默认吸收剩余宽度，不能误判为丢列。

激活前 HEAD 为上述规划检查点，分支 `main`，工作区无变更；治理检查 PASS。
Task Base 仍为原始产品基线，不因纯规划／激活提交重新设定。当前状态 PLANNED 表示
已授权、等待 Developer 开始；实际实施时更新为 IN PROGRESS，B 独立审查保持。

### Observed behavior and cause

- `files-browse-presentation.tsx` 的 `FilesSortScope` 在两页非空列表／网格上输出独立一行：
  `当前页排序：服务端默认顺序` 和两个重置按钮；未排序时仍常驻禁用的顺序重置，
  列宽重置入口也未表达是否存在自定义宽度。
- `FilesSortButton` 未激活时持续显示字符 `↕`；`styles.css` 让四列调宽竖线持续出现。
  状态、低频动作、表头标签和操作提示视觉权重接近，形成零碎、偏重的控制区。
- 两页分别在 `StorageFilesPage.tsx`／`MediaLibraryFilesPage.tsx` 将这行置于工具栏与
  文件内容之间；现有共用排序／调宽逻辑、页面级会话状态及测试可复用。
- 默认表格填满浏览区；用户调宽后精确总宽、列边界与 `aria-valuenow` 一致是已有
  修复结果，不能通过让表格重新分配剩余宽度来制造视觉齐整。

### Complete journey and target presentation

1. **进入／状态：** 从文件或媒体库正常选库，非空浏览区在现有工具栏右侧以轻量控件
   展示 `当前页排序：默认顺序` 和带可读名称的 `显示设置` 入口；移除独立重置行。
   保留面包屑、创建、刷新和列表／网格入口；窄屏允许协调换行，不挤没路径或截断操作。
   加载、真实空目录、无搜索匹配和读取失败继续使用原有状态，不出现假表头或残留菜单。
2. **排序：** 列表名称／大小表头仍是排序入口；首次升序、再次降序。未激活箭头在
   hover／focus 时提示，激活列始终有明确方向；持续可见的状态说明仅当前页排序。
   使用统一线性图标及对齐，保留 `aria-sort`／按钮可访问名称。类型、修改时间不新增排序。
3. **显示设置：** 原两个恢复动作统一进入工具栏的小型锚定菜单，保留
   `恢复默认顺序`／`恢复默认列宽` 名称；相应状态为默认时明确禁用，关闭菜单后仍能
   读出当前排序。网格保留排序状态和顺序恢复，不提供当前不可操作的列宽动作。
   不新增网格排序选择器、列显隐、密度、偏好持久化或新弹窗。
4. **表头／调宽：** 用与现有浅色页面协调的淡底、柔和底边、字重和间距形成完整表头；
   名称列仍弹性填充，其他列间距适合类型、大小和时间阅读，不设置宽屏任意最大表宽。
   调宽边界保留轻微可发现提示，hover／focus／drag 时增强；四列鼠标拖动、左右键、
   双击恢复完整。视觉弱化不能缩掉命中区、取消焦点或隐藏拖动中的边界。
5. **成功／恢复：** 名称／大小重排不读取更多页、不改选择和精确命令对象；切网格再
   返回保留顺序、选择和列宽。切目录／翻页／刷新及读取失败后的原入口重试保留会话
   设置；整页重载恢复默认。排序恢复和列宽恢复互不重置。菜单退出、切视图或读取
   卸载不遗留遮挡、焦点陷阱或失效动作；错误恢复不新增 mutation／自动重放。

### Implementation scope and ordered steps

1. 在共用浏览呈现组件中收敛排序状态与显示设置菜单，消费现有 sort／显式 widths
   状态判断禁用；菜单优先复用项目无业务含义的可访问模式，状态不另存第二份。
   实现触发器展开状态、键盘打开／导航／执行、Escape、外点关闭及合理回焦。
2. 两页将共用控件接入现有工具栏，删除独立排序行，协调列表／网格、空态、刷新／
   失败卸载和窄屏布局；沿用页面级 sort／widths 状态及真实数据来源。
3. 局部调整共用表头／排序图标／调宽反馈与列间距。保留默认填满、调宽后的精确总宽、
   内部横向滚动和 sticky 表头。只改必要 Files 选择器，不清理整份历史 CSS。
4. 更新直接受影响的组件／页面及浏览器测试，从新菜单路径验证真实恢复行为，保留
   原排序、拖动、选择、会话、命令对象和请求断言；补菜单键盘、窄屏与错误恢复覆盖。
5. 用新构建做相同视口前后对照，协调 Files／MediaLibrary visual spec 和 Product Experience
   中“独立行／服务端文案／恢复入口”的现行描述。仅在实际直接矛盾时改其他产品说明；
   不改已接受 Slice、Roadmap、Progress 的状态、Base、Head 或原接受记录。

### Acceptance criteria

- [ ] 两页非空列表和网格都有紧凑、可读的当前页排序状态及显示设置入口；默认态不再
  单独占一行陈列恢复按钮，不显示“服务端”实现术语，不以新增大段提示替代旧行。
- [ ] 名称／大小排序方向和作用域明确，未激活提示不抢视线；菜单恢复入口可发现，
  默认禁用、可执行时启用；顺序／列宽分别恢复，网格列宽动作不冒充可用。
- [ ] 菜单鼠标与纯键盘均可完成，Escape／外点关闭、焦点和视口边缘定位正确；不被
  表格滚动区裁切，不抢文件右键菜单，不让恢复动作触发刷新或文件命令。
- [ ] 四列调宽可发现且可操作，hover／focus／拖动有清楚反馈；双击恢复不排序。
  用户设定列宽与可见边界一致，剩余空白不被偷偷分摊回列内。
- [ ] 名称／大小排序算法、目录大小未知、等值精确路径稳定排序和前后空白身份保留；
  列表／网格选择、计数、精确命令对象以及切目录／翻页／刷新／失败重试的会话保持通过。
- [ ] `1536×1024`、`2048×1024`、`390×844`、`1280×600` 下，路径／操作／数据层级
  协调；长名、长路径、时间和选中态可读，溢出限于原有有界区域，不产生整页横向溢出。
  检查稳定画面、菜单开关、调宽过程及 reduced-motion，不仅凭 DOM／固定 CSS 数值验收。
- [ ] 慢读取、真实空／无匹配、读取错误与恢复正确，快速切目录／视图不串状态，
  整页重载恢复默认；纯排序／调宽／菜单无额外目录读取、工作创建、配置发布或媒体变更。
- [ ] 现行呈现说明与实际交付一致，既有接受身份及安全边界保持；所有必需验收有实际
  结果，未运行／失败／跳过如实交接，不删除断言或加重试掩盖问题。

### Required tests

遵循 [测试分工](docs/development-workflow.md#6-test-levels)。T3 覆盖两页共享 React 组件、
菜单／工具栏交互及会话集成；不改后端、Active、权限、schema、Storage 或执行／并发协议。
如果实现出现这些范围变化，先由 B 重新评估边界与 Test Level，不能沿此计划扩做。

**Developer — affected tests**（以下 Web 命令 cwd 为 `web/`）：

```sh
npm run test -- run src/features/library/FilesBrowsePresentation.test.tsx src/features/library/StorageFilesPage.test.tsx src/features/library/MediaLibraryFilesPage.test.tsx src/shared/ui/files-toolbar-styles.test.ts src/shared/ui/files-path.test.tsx
npm run typecheck
npm run lint
npm run build
npm run test:e2e -- tests/e2e/files-interactions.spec.ts tests/e2e/files-read-handoff.spec.ts
```

组件／页面覆盖新菜单与真实恢复、默认／非默认、视图共享、卸载和错误分支；浏览器覆盖
真实几何、拖动／键盘、会话保持和请求边界。对实际新增用例文件运行其精确命令；
对实际修改 Web 文件运行 `npx prettier --check <changed-web-files>`。
根目录运行 `python3 scripts/check_governance.py`、`git diff --check`，并检查改动 Markdown
的相对链接／锚点。Developer 完成受影响测试即冻结候选，不承担全仓库全量测试。

**B — independent acceptance**：

1. 审查固定 Task Base..candidate 完整范围，复现截图问题并核对目标视觉，独立执行
   上述受影响用例／类型／lint／构建／格式检查；相同候选下完整运行包含子集时无需重复。
2. 新构建后运行以下邻近浏览旅程（cwd `web/`）：

   ```sh
   npm run test:e2e -- tests/e2e/files-interactions.spec.ts tests/e2e/files-read-handoff.spec.ts tests/e2e/library-files.spec.ts tests/e2e/medialib-files.spec.ts
   npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/live-files.python.spec.ts
   ```

   Node 假服务验证展示和请求边界；真实 Python／API／临时 SQLite／Local 根验证两种库
   活列表、精确身份、分页、失败恢复及零副作用。沿实际产品入口补验排序→调宽→菜单
   分别恢复及切视图／目录，不把既有 CLI 对齐用例当成新菜单视觉证明。
3. 使用隔离本地假服务／真实临时实例，人工查看上述四种视口两页默认与自定义状态、
   长路径／名称、菜单边缘、纯键盘、慢读／失败重试及 reduced-motion；保留前后同视口
   截图、关键操作证据与实际请求记录。不得对生产服务、用户媒体或私有配置验收。
4. 记录精确候选、构建身份、命令／实际结果和必要证据于
   `.git/validation-evidence/<candidate>/patch-20261114-2-b/`。新 build 若改动受版本控制
   产物，按仓库原交付约定纳入候选并核对来源。全 Python／全 Web／全 E2E、wheel 和 Docker
   广域矩阵不作为本 T3 默认门禁：未涉及对应运行／包装路径；若实际共享影响扩大，
   B 说明具体原因再追加适用门禁，不要求 Developer 机械运行全量。

### Non-goals and frozen boundaries

不增加服务端／全目录排序或修改时间／类型排序，不改分页算法／游标、搜索语义、默认
排序算法、选择生命周期和精确路径身份；不持久化偏好、不增加列显隐／密度／主题。
不重设计库卡片、全站 Shell、文件内容行／网格整体、库配置弹窗、整理／任务／常规文件
命令；不改 API／后端／领域／依赖／权限／Active／schema／Storage／执行协议。
不重开 Slice、不改治理规则，不 push、发布或部署；实施仅限本 Task，不自行委派其他角色。

### Developer completion report

已授权，尚未实施。Developer 交接：完整候选 SHA、READY FOR B REVIEW、实际变更与关键决定、
受影响测试命令／结果及剩余风险；B 独立验收尚待执行。

### B review result

未开始实现审查，无 PASS／FIX REQUIRED 结论。独立 Task 经实际验收 PASS 后按 workflow
§3.1 恢复简短 no-active notice，保留精确 reviewed Base..Head 和结果指针；不宣布 Slice 关闭。

## Latest accepted Task — PATCH-20261114-1

```text
Task Type: STANDALONE MINOR BUG
Parent Slice: NONE
Decision: B PASS — 2026-11-14
Task Base: 6bf8f58b8283bc891c4b768208d343d2d52600f2
Reviewed Head: 754d7286ba27943be507e7c93b233f9e930aa6c6
Implementation Head: ecf2956f9c177010de73e473cebf331fc2a05416
Acceptance checkpoint: 280fc5fdedaf8c079dee52480e1eb4d3bf26449a
```

已完成合法冒号来源整理、规则单项重跑覆盖、准备页／逐项弹窗层级与局部过渡，
以及四项原失败测试修正。完整 Base..Head 审查、实际旅程、测试命令／结果、文档检查
失败及修正、7 项可选跳过、产物身份和本机证据目录见
[固定 B 验收](https://github.com/kentinya/mediaflow/blob/280fc5fdedaf8c079dee52480e1eb4d3bf26449a/TASK.md#patch-20261114-1--b-pass)。
原计划／Developer 交接见 `754d7286:TASK.md`，上轮 FIX REQUIRED 见 `966eefde:TASK.md`。

现行行为分别归入 [用户旅程](docs/product-experience.md)、[架构](docs/architecture.md)，
验证及发布限制归入 [Release](docs/release.md#current-v2-validation-boundary)。
依 [Development Workflow](docs/development-workflow.md) §3.1 保留本简短指针；
详细实施／测试记录留在 Git。Slice54 仍 PASS / CLOSED，原接受身份和延期保持。
