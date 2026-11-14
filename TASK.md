# NO ACTIVE IMPLEMENTATION TASK

Next Action: 独立修复已完成；本检查点记录 B 验收，后续保留简短结果指针。

## Accepted Task PATCH-20261114-2 — 文件浏览工具栏与表头呈现修复

用户于 2026-11-14 在规划检查点 `d3d984a50d3364d06f9e763a1231d4299b5a1e9b`
后明确“激活 Task”，本 Task 正式启用并授权实施。原 ID／Base／目标／范围／测试分工
保持；激活检查点仅更新本文件，不改产品代码、现行产品文档、SLICE、Roadmap 或 Progress。

```text
Task ID: PATCH-20261114-2
Task Type: STANDALONE MINOR BUG
Parent Slice: NONE
Status: PASS
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
Task Base 仍为原始产品基线，不因纯规划／激活提交重新设定。实施后候选状态为
PASS；B 已独立审查完整 Task Base..交接 Head。

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

- [x] 两页非空列表和网格都有紧凑、可读的当前页排序状态及显示设置入口；默认态不再
  单独占一行陈列恢复按钮，不显示“服务端”实现术语，不以新增大段提示替代旧行。
- [x] 名称／大小排序方向和作用域明确，未激活提示不抢视线；菜单恢复入口可发现，
  默认禁用、可执行时启用；顺序／列宽分别恢复，网格列宽动作不冒充可用。
- [x] 菜单鼠标与纯键盘均可完成，Escape／外点关闭、焦点和视口边缘定位正确；不被
  表格滚动区裁切，不抢文件右键菜单，不让恢复动作触发刷新或文件命令。
- [x] 四列调宽可发现且可操作，hover／focus／拖动有清楚反馈；双击恢复不排序。
  用户设定列宽与可见边界一致，剩余空白不被偷偷分摊回列内。
- [x] 名称／大小排序算法、目录大小未知、等值精确路径稳定排序和前后空白身份保留；
  列表／网格选择、计数、精确命令对象以及切目录／翻页／刷新／失败重试的会话保持通过。
- [x] `1536×1024`、`2048×1024`、`390×844`、`1280×600` 下，路径／操作／数据层级
  协调；长名、长路径、时间和选中态可读，溢出限于原有有界区域，不产生整页横向溢出。
  检查稳定画面、菜单开关、调宽过程及 reduced-motion，不仅凭 DOM／固定 CSS 数值验收。
- [x] 慢读取、真实空／无匹配、读取错误与恢复正确，快速切目录／视图不串状态，
  整页重载恢复默认；纯排序／调宽／菜单无额外目录读取、工作创建、配置发布或媒体变更。
- [x] 现行呈现说明与实际交付一致，既有接受身份及安全边界保持；所有必需验收有实际
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

```text
Candidate: 6a358085d1fc622c0257c545d83be41539d38620
Status: READY FOR B REVIEW
Scope: 4107c299d8f99b817fcd3cbdffa274de1f5598ea..6a358085d1fc622c0257c545d83be41539d38620
Branch: main
```

实现与测试均已完成，候选未推送、未发布、未部署。工作区开始时仅含本 Task 的规划／
激活文档提交，无预存产品改动；候选中未读取运行数据库、私有配置、凭据或用户媒体。

**实际变更与关键决定**

1. **工具栏收敛。** 用共用 `FilesDisplaySettings` 替换独立排序行：两页非空浏览区在
   工具栏右侧显示轻量 `当前页排序：…`（默认 `默认顺序`，不再显示“服务端”术语）和
   `显示设置` 入口。菜单经 portal 锚定并夹取在视口内，支持鼠标、Enter/Space、方向键、
   Home/End、Escape、外点与滚动／resize 关闭，关闭后回到触发按钮。
2. **恢复语义。** `恢复默认顺序`／`恢复默认列宽` 分别使用现有页面会话状态；各自在
   默认值禁用、互不重置。列表显示列宽动作，网格不冒充可用；网格保留排序状态和顺序
   恢复。触发菜单、排序、调宽不读取目录、不刷新、不创建命令。
3. **表头与排序。** 名称／大小仍只排序当前已读页；未激活方向图标仅在 hover／focus
   显示，激活列常显线性方向图标并保留 `aria-sort` 与可访问名称。表头使用淡底、柔和
   底边和一致内边距；名称列继续弹性填充，宽屏不设最大表宽。
4. **调宽反馈。** 四个数据列保留 8px 命中区、焦点轮廓、拖动／左右键与双击恢复；竖线
   默认轻提示，hover／focus／拖动增强，拖动状态不改变排序、选择或命令对象。
5. **测试与文档。** 共用组件、两页、CSS 结构和浏览器用例加入新菜单路径、默认禁用、
   独立恢复、网格缺省、键盘、窄屏与读取错误后恢复断言；Files／MediaLibrary visual
   spec 与 Product Experience 的现行呈现描述同步更新。

**实际执行结果（cwd 除注明外为 `web/`）**

```text
python3 scripts/check_governance.py                     PASS（根目录）
git diff --check                                        PASS（根目录）
npm run test -- run <5 affected files>                  5 files / 112 tests PASS
npm run typecheck                                       PASS
npm run lint                                            PASS
npx prettier --check <11 changed web files>             PASS
npm run build                                           PASS（299 modules；CSS 139.67 kB / JS 1,500.62 kB）
npm run test:e2e -- tests/e2e/files-interactions.spec.ts tests/e2e/files-read-handoff.spec.ts
                                                        8 tests PASS
```

首轮新 E2E 有 1 项焦点断言失败：菜单打开时浏览器在 Enter 激活后的焦点修复把焦点抢回
触发按钮；修正为测量完成后再于 `requestAnimationFrame` 聚焦首个可用项，并避免重复
位置更新，修正后上述 8 项全部通过。未删除或放宽断言。

使用新构建与本地 Node 假服务在 `1536×1024`、`2048×1024`、`390×844`、`1280×600`
实看两页默认呈现，并在 `1536×1024` 实看排序＋自定义宽度后的菜单；截图保存在本机忽略
目录 `.git/validation-evidence/6a358085d1fc622c0257c545d83be41539d38620/patch-20261114-2-developer/`。

**剩余风险与未执行项**

- 上述证据来自本地 Node 假服务与 Chromium；真实 Python／API／SQLite／Storage 活列表、
  真实长名称／失败恢复及独立 B 视觉验收尚未执行，按 Task 由 B 承担。
- 未运行全量 Web／Python／原生 E2E、wheel、Docker 或生产部署矩阵；本 Task 为 T3 呈现
  修复，未改后端、schema、权限、Storage 或执行协议。
- `prefers-reduced-motion` 仅由 CSS 结构与构建检查覆盖，实际动态观感需 B 在浏览器中
  复核；未对生产服务或用户媒体验收。

### B review result

#### PATCH-20261114-2 — B PASS

```text
Reviewer: B
Date: 2026-11-14
Task Base: 4107c299d8f99b817fcd3cbdffa274de1f5598ea
Implementation Head: 6a358085d1fc622c0257c545d83be41539d38620
Reviewed Handoff Head: a98403804f23a47d4bac771def3fc5f07234fcde
Decision: PASS
Task blockers: NONE
Authorized bug acceptance complete: YES
Next: NO ACTIVE IMPLEMENTATION TASK
```

**审查范围与交付结果。** B 独立阅读完整 Base..交接 Head 的 15 文件改动；实现 Head 后
仅有 TASK 交接文字，执行输入未变。两页共用工具栏状态／菜单、表头／图标、调宽反馈、
11 个 Web 文件及 3 份呈现文档均在授权范围，排序算法、选择身份和页面级设置沿用原实现。
未改后端、Active、权限、schema、Storage、依赖或执行协议。独立修复全部验收已满足，
无下一 Task；Slice54 保持原 PASS / CLOSED，SLICE／Roadmap／Progress 未变。

**实际用户旅程。** 从已有文件页选库，打开真实 `Live` 目录→名称排序→调宽→选择
`Gamma-Directory`→切换网格／列表，选择和设置一致。打开该实际目录时让本次目录请求
发生网络中断，页面显示原读取错误且不残留显示菜单；点击已有 `Refresh` 恢复到真实
`child.txt`，原排序／列宽仍在。恢复顺序保留列宽，恢复列宽保留顺序。经现有侧栏进入
媒体库，实际 `Live` 目录慢读取、长名称／前导空白、菜单与拖动通过；拖动的声明宽度
与可见边界均为 863px。两页补验 Space／Enter、方向键、Home／End、Tab、Escape、外点和
回焦；纯菜单／排序／调宽零额外目录读取，补充旅程实际 API 请求全为 GET。

**视觉。** 分别构建原 Base 和候选，用同一隔离 Node 假服务数据做两页四视口前后对照；
查看稳定画面、默认／自定义、菜单及真实临时库截图。独立重置行移除，淡色表头连贯，
菜单未被滚动区裁切，四视口无整页横向溢出。真实长名称、读取中间态／错误／恢复、
拖动状态和 390px 浏览可用。实际开启 reduced-motion 后操作正常，排序提示与调宽提示
的 transition duration 均为 0s；全页重载并正常重认证后，两种恢复项回到默认禁用。

**B 执行结果**（以下 npm／npx 命令 cwd 为 `web/`，完整参数同上方 Required tests）：

| 命令／范围 | 实际结果 |
|---|---|
| 5 个受影响 Vitest 文件 | 5 文件／112 项 PASS |
| `npm run typecheck`、`npm run lint` | PASS |
| 11 个改动 Web 文件 `npx prettier --check` | PASS |
| `npm run build` | PASS，299 modules；产物 SHA-256 已留存 |
| 4 个指定 Node E2E 文件，独立 `--output` | 71 项 PASS |
| `playwright.python.config.ts` 的 `live-files.python.spec.ts` | 6 项 PASS，真实临时 API／SQLite／Local 根 |
| 两页四视口、键盘与真实目录补充旅程 | PASS，截图／观测 JSON／请求记录已留存 |
| 治理、完整 Base..Head whitespace 和改动文档链接核对 | PASS |

上述自动化／静态命令含原失败及重跑的累计耗时约 130 秒；浏览器补充核对为短操作，
本轮主要用于完整代码／文档审查和结果核对，测试耗时低于本轮总耗时的 50%。
没有为完成比例人为等待或补跑无关套件。

**原失败和验证限制。** B 首轮并行启动 Node／Python E2E 时，两者使用默认
`web/test-results`，Node 在完成用例后关闭浏览器／归档 trace 遭遇 ENOENT，结果
70 PASS／1 归档失败。保留 `node-e2e.log`；Python 6 项通过，随后 Node 使用独立
`--output` 完整重跑 71 项通过，未修改断言、超时或重试设置。Vitest 有 jsdom 既有
`scrollTo` 未实现提示；构建保留大 bundle 提示，均非本次失败。收尾首次将 PASS 留在活动
Task 格式下时，治理检查拒绝；已按 §3.1 改为无活动实施 Task 的验收记录格式，复查通过。
全仓库全量、wheel、Docker
及生产环境未运行：本 T3 未改对应运行／包装路径，按原测试计划不适用，未宣称远程 CI。

本机证据：`.git/validation-evidence/6a358085d1fc622c0257c545d83be41539d38620/patch-20261114-2-b/`，
包含所有命令日志、`build-sha256.json`、`visual-review.json`、`requests.json`、原 Base 构建
和前后截图。证据目录被忽略，不进入产品提交。当前收尾只记 Task 结果，未 push／部署。

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
