# Task PATCH-20261113-2 — 两种库文件浏览的提示、交互反馈与表头调节

用户于 2026-11-13 明确“激活Task”，现将已提交规划转为正式、已授权实施的独立修复
Task。保留原 Task ID／Base／Goal／Scope／Medium／T3，不重设基线或扩大范围。
激活检查点记录为 `PLANNED`；Developer 已交付候选，B 于 2026-11-13 独立复核后
返回 `FIX REQUIRED`，修正与复核继续留在同一 Task。此前 PASS
记录保留在本文末尾。

Authority: 用户本轮三项问题、“规划一版独立修复Task”及“激活Task”；
[Development Workflow](docs/development-workflow.md#31-independent-minor-bugs) 为生命周期依据。

```text
Task ID: PATCH-20261113-2
Task Type: STANDALONE MINOR BUG
Parent Slice: NONE
Status: FIX REQUIRED
Task Base: 9811df4559d94db5b648f6152476f39035a12ae5
Difficulty: Medium
Test Level: T3
Planner / Reviewer: B
Implementation Authorization: USER AUTHORIZED ON 2026-11-13
```

规划前治理检查 PASS；分支 `main`，HEAD 为上述 Task Base，暂存区／工作区干净，
工作区与 Git 可写。未读取运行数据库、私有配置、凭据或用户媒体。
激活前治理检查 PASS；分支仍为 `main`，HEAD 为规划提交
`f232b51382825d8ddb835a254385c78f1dc0f8a1`，暂存区／工作区干净；该提交只改 Task，
原 Task Base 保持不变。

### Goal / existing behavior

用户在文件页或媒体库页浏览真实文件／文件夹时，能清楚感知悬停、焦点、按下与选中，
直接调整表格阅读空间并使用现有排序入口；文件页不再重复展示无操作价值的蓝色说明。
完整旅程为打开库／目录 → 读取条目 → 悬停／选择／调整表头 → 清晰反馈与准确选择 →
继续浏览或原有明确操作；读取失败仍使用原有错误、重试和路径纠正入口。

已读实际实现，尚未做本轮浏览器复现：

- `StorageFilesPage.tsx` 的 `FILES_BANNER` 在正常浏览和加载／失败上下文各有渲染；
  移除必须覆盖所有读取状态，不能误删保存、删除、权限或未知效果提示。
- 两页列表只通过复选框设置按精确 path 保存的选择，并用 `is-selected` 瞬时变色；
  共享 CSS 无文件行／网格的悬停和选中过渡。两份 GridView 没有选择控件或选中样式绑定。
- 两页名称／大小旁 `⇅` 都是 `aria-hidden` 的静态 span；表格使用固定布局和 CSS 列宽，
  没有排序控制、拖动手柄或列宽状态。后端 `StorageBrowserService.browse_revision`
  只调用受限 `list_page`，并在返回页内按名称／路径稳定排列，不提供整目录排序参数。

本版将截图“无法调节”解释为**列宽可调整，以及现有名称／大小箭头可操作**。
排序是明确标注的“当前页排序”，只重排已读取的本页条目；不承诺跨游标的整目录顺序，
不通过抓取所有页模拟全目录排序。若用户要求全目录排序，应先另定范围，不能悄悄扩入本修复。

关联当前约定：[文件页规范](docs/file-page-visual-spec.md)、
[媒体库页规范](docs/media-library-page-visual-spec.md)、
[完整浏览／维护旅程](docs/product-experience.md#real-storage-files)、
`V2-MEDIALIB-001/002/004` 及现有 Files 视觉约定。保留 Slice37／38／50／52／53／54
接受身份，不重开 Slice；SLICE、Roadmap、Progress 不变。

### Implementation Scope / ordered steps

1. **删除目标说明。** 移除文件页 `FILES_BANNER` 及两处渲染，正常、慢读取、缓存返回、
   空目录与读取失败均无该说明或空占位。保留其他真实状态提示；调整只依赖旧文案的断言。
2. **统一列表／网格反馈与选择。** 复用共享样式与必要的业务无关呈现逻辑，覆盖两页、
   文件／目录、已选／未选。悬停用轻量背景／边框过渡，选中保持可辨且悬停不覆盖选中；
   按下反馈不造成列表位移，焦点清晰，`prefers-reduced-motion` 下即时反馈且不播放位移动画。
   网格增加与列表共用原 path 集合的复选框、受支持的全选／清除入口及选中外观；按 Space
   可切换聚焦复选框，切换视图保持同一选择和数量。保留后端 `selectable` 等现有规则。
   文件夹名称／图标／原列表空白区域左击仍打开；勾选不触发导航，普通文件单击不新增业务动作。
3. **让现有排序箭头真实工作。** 名称／大小改为语义按钮，支持键盘、升／降序状态和
   `aria-sort`；就近可见地说明“当前页排序”，不依赖悬停 tooltip 才能理解范围。
   初始保持服务端默认顺序；选字段首次升序，再次降序；提供轻量恢复默认入口。
   依据原始名称／数值字节排序，不按格式化大小字符串排序；相等值以精确 path 稳定决胜，
   目录／不可用大小不伪装成 0 字节，置于有效大小之后。不得修改名称／path 原值。
   先保留原搜索结果集合再排序；列表与网格采用同一展示顺序，排序不发 API 请求或改变
   游标、选择、操作证据和提交路径。菜单绑定 path，不能在排序后指向另一项。
4. **支持列宽调节。** 保留五列及固定选择列，名称／类型／大小／修改时间的边界提供
   可发现的拖动手柄和调整光标；表头排序按钮与手柄不抢事件。手柄键盘可聚焦，左右键
   调宽，具备可读名称与当前值；双击手柄或轻量“恢复默认列宽”入口恢复默认。
   指针捕获期间越出手柄仍可完成；取消／失焦／卸载正确清理，拖动不排序、不选择、不导航。
   最小宽度保证控件可用，窄屏必要溢出限于表格容器，表头粘附、条目纵向滚动及底栏保持。
   不给列宽本身加拖尾过渡，不产生整页跳动。排序／列宽只保存于各自主页面会话状态，
   同页切目录、翻页、刷新读取和列表／网格切换保持；整页重载可恢复默认，不新增持久偏好。
5. **验证并协调直接相关说明。** 补充有意义的选择／排序／调宽行为测试及真实视觉检查；
   后续实施只协调两份页面规范中已变化的 banner／交互描述，不修改已接受 Slice 边界或
   宣称新后端能力。本激活检查点只更新 Task；产品、测试及上述说明在 Developer 实施时完成。

### Acceptance Criteria

- [ ] 两页现有库／目录读取、空态、失败与恢复完整；文件页指定说明在所有状态消失，
  真实错误、保存结果和未知效果核对仍可见且不自动重放。
- [ ] 列表及网格中的文件、文件夹均有实际可见的悬停／焦点／按下／选中反馈；选中
  与悬停能区分，离开鼠标后选择仍清楚，无抖动、条目重排或点击延迟。
- [ ] 两视图可勾选／取消、全选／清除；不可选条目不借新控件获得选择资格。视图切换、
  排序和调宽保留精确 path 选择及汇总；翻页／切库／切目录沿用原有选择生命周期。
- [ ] 名称／大小排序两方向、恢复默认及 `aria-sort` 正确；中文、数字、前后空白、
  同名／同大小、目录、零字节和长名称可辨。按原值稳定比较，不改变后端原数组或证据。
  两页均明确“当前页排序”；有下一页时不产生全目录排序假象或额外读页。
- [ ] 列宽可拖动、键盘调整、恢复默认；达到边界、取消、松手在容器外、切目录／卸载
  都能结束拖动。拖手柄不误触排序、选择、打开目录或菜单；排序按钮仍易于点击。
- [ ] 排序／调宽后打开目录、右键／键盘菜单、复制／移动／删除及 Files 整理仍操作
  原精确条目；不会因展示索引变化、迟到读取或跨库同 ID 而串路径、选择或请求。
- [ ] 桌面 1536×1024、390px 窄屏与短窗口实际可操作；长名完整查看、五列表头、粘附、
  内部横纵滚动和底栏可用，无文档横向溢出。实际观察动画及 reduced-motion，不仅断言 CSS。
- [ ] 普通浏览／悬停／勾选／排序／调宽不新建 Task、不发布配置、不访问 Provider，
  不发媒体变更请求；原权限、类型／根隔离、游标和显式危险操作意图保持。

### Required Tests

按 [测试分工](docs/development-workflow.md#6-test-levels) 执行。T3 用于共享两页的呈现、
选择和命令入口交互；本 Task 不改后端、Storage／执行／权限／schema／pins／游标协议，
不因页面含有文件操作就把纯呈现修复扩为执行引擎改造。发现必须改变这些边界时交 B 重评。

**Developer — affected tests**（以下 Web 命令 cwd `web/`）：

- 新增 `src/features/library/FilesBrowsePresentation.test.tsx`，验证共享排序／调宽行为及
  边界，不为每条 CSS 声明写镜像测试；在现有两页用例覆盖控件接线、精确选择及失败恢复。
- `npm run test -- run src/features/library/FilesBrowsePresentation.test.tsx src/features/library/StorageFilesPage.test.tsx src/features/library/MediaLibraryFilesPage.test.tsx src/shared/ui/files-toolbar-styles.test.ts src/shared/ui/files-path.test.tsx`
- 新增 `tests/e2e/files-interactions.spec.ts`，两页覆盖实际 hover／选择／视图切换、鼠标与
  键盘调宽、排序与菜单 path 关联；使用至少两页的本地假数据，记录无额外读页／写请求。
- `npm run build` 后，`npm run test:e2e -- tests/e2e/files-interactions.spec.ts tests/e2e/files-read-handoff.spec.ts`
- 在 `tests/e2e/live-files.python.spec.ts` 补两页排序／选择后打开同一真实条目的用例，
  用临时根及原生服务验证呈现未改身份；运行
  `npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/live-files.python.spec.ts`。
- `npm run typecheck`；对实际新增／修改文件执行 `npx eslint <changed-ts-tsx-files>` 与
  `npx prettier --check <changed-web-files>`，交接列出展开后的精确命令；根目录
  `python3 scripts/check_governance.py`、`git diff --check`。
- 手动检查一次两页桌面及窄屏动画／reduced-motion，交接实际结果与已知限制。
  新测试文件名若随合理实现调整，交接给出对应路径，不为满足命名创建空测试文件。

**B — independent acceptance**：

- 审查固定 Task Base..candidate 全部差异并逐项核对上述验收；Developer 不自审，
  规划不授权另起代理或自动开展其他角色工作。
- cwd `web/`：`npm run typecheck`、`npm run lint`、`npm run format:check`、`npm run build`；
  运行上述受影响单元命令；
  `npm run test:e2e -- tests/e2e/files-interactions.spec.ts tests/e2e/files-read-handoff.spec.ts tests/e2e/library-files.spec.ts tests/e2e/medialib-files.spec.ts`。
- 真实临时 Python／SQLite／Storage 浏览：
  `npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/live-files.python.spec.ts`；
  核对新增用例确实证明排序／选择后同一真实条目的打开／读回（不接生产服务）。
- 真实普通操作路径回归：
  `npm run test:e2e -- --config=playwright.direct-files.python.config.ts tests/e2e/direct-files.python.spec.ts -g 'renames a file and directory|durably deletes a selected batch'`，
  保留两种库的独立入口／精确目标和临时媒体效果验证。
- 桌面／390px／短窗口、键盘与 reduced-motion 实看；截图对照改前／改后，确认四种
  交互状态、加载／失败无多余留白、长名、窄表、粘附和底栏，不用截图单独证明动画。
- 根目录治理与差异检查；记录实际命令／结果／首次失败／跳过／未验证项。
  T3 无后端／依赖／打包运行路径变化，不要求全 Python／Web／E2E、wheel 或 Docker
  矩阵；有实质共享影响时由 B 补充有依据的覆盖，不转交 Developer 全量验收。

### Non-goals

整目录／跨游标排序、后台枚举／索引／新排序 API、Provider／Storage 改造；新文件命令、
执行／权限／配置／恢复模型；批量范围扩大、跨页全选、拖拽文件、缩略图、上传／下载、
双击改导航、Shift／Ctrl 范围选择、其他页面动效或全站主题／偏好设置。仅修当前两个
文件浏览表面，不重新设计库卡片、整理弹窗或任务中心；不改 SLICE／Roadmap／Progress。

### Developer Completion Report

实施检查点 `31466c1d600f850f06cf26c2c42f62b1ba555ebf`（Task Base 保持
`9811df4559d94db5b648f6152476f39035a12ae5`）；报告提交在其后，B 以实际候选 HEAD 复核。
分支 `main`；未推送、未部署、未改 SLICE／Roadmap／Progress。

实际改动：

- 删除文件页 `FILES_BANNER` 的成功、加载与失败上下文渲染；保留空库、操作核对等真实状态提示。
- 新增共享 `files-browse-presentation`：当前页名称／大小排序（原始值、精确 path 决胜、
  目录不参与有效字节排序）、col-resize 手柄、会话列宽、`aria-sort`／`当前页排序`／恢复入口。
- 两页接入同一排序行集合；名称／大小表头改为语义按钮，四个数据列支持指针拖动、左右键、
  失焦／取消／卸载清理和双击／显式恢复默认列宽；窄屏横向溢出留在表格容器。
- 列表和网格共享精确 path 选择；网格增加复选框、全选／清除、选中与悬停／按下外观；
  空格切换原生复选框；保留文件夹左击打开与普通文件无新增动作。
- 同步两份页面规范中的 banner 与交互描述；新增共享行为测试、两页接线测试、Node 交互
  E2E 与真实 Python/Storage 打开用例；调整依赖旧 banner 文案的断言和新建对话框定位。

实际命令与结果（cwd `web/`）：

- `npm run typecheck`：PASS。
- `npx eslint`（上述 10 个变更 TS/TSX 文件）：PASS。
- `npx prettier --check`（上述文件 + `src/shared/ui/styles.css`）：PASS。
- `npm run build`：PASS；仅现有 chunk >500 kB 体积提醒。
- `npm run test -- run src/features/library/FilesBrowsePresentation.test.tsx
  src/features/library/StorageFilesPage.test.tsx
  src/features/library/MediaLibraryFilesPage.test.tsx
  src/shared/ui/files-toolbar-styles.test.ts src/shared/ui/files-path.test.tsx`：
  **104 passed / 5 files**。
- `npm run test:e2e -- tests/e2e/files-interactions.spec.ts
  tests/e2e/files-read-handoff.spec.ts`：**6 passed**（新增 2 条交互用例 + 原读取交接 4 条）。
- `npm run test:e2e -- --config=playwright.python.config.ts
  tests/e2e/live-files.python.spec.ts`：**6 passed**；新增用例在两页排序、勾选并保持
  Gamma-Directory 精确身份后打开真实子项 `child.txt`。
- 根目录 `python3 scripts/check_governance.py`：PASS；`git diff --check`：无问题。
- 手动浏览器检查：1536×1024、390×844、900×520 两页；文档横向溢出均为 false，
  窄／短窗口横向滚动只在表格容器；表头粘附、底栏在滚动容器外；手柄默认可见；
  `prefers-reduced-motion: reduce` 下列表单元格与网格 transition 均为 `0s`。
  截图证据在本机临时路径，不随 Git 推送。

初次失败与限制：完整 `library-files.spec.ts` 首轮有 1 条旧用例以
`getByLabel("名称")` 同时匹配新建对话框和可访问的“调整名称列宽”手柄；已改为在新建
文件夹对话框内定位后通过。未执行 B 的完整验收、全量 Python／Web／E2E 矩阵或 direct-files
两条危险操作回归；排序明确仅当前页，不提供整目录排序；列宽为页面会话状态，整页重载恢复默认；
短窗口底栏仍需随页面纵向滚动到达（不产生文档横向溢出）。本机无屏幕阅读器实测。

### Developer Fix Report — 2026-11-13 (B13-2-01 / B13-2-02)

修正检查点 `a2effc4b0ed4503d230ff9b684d3d1e869793e95`；Task Base 保持
`9811df4559d94db5b648f6152476f39035a12ae5`。分支 `main`；未推送、未部署，
SLICE／Roadmap／Progress 未改。本报告单独提交，B 以实际报告 HEAD 复核。

针对 B13-2-01（进入子目录丢失排序与列宽）：

- 两页分别把当前页排序与会话列宽提升到各自页面组件，跨目录读取的加载／失败分支不再
  卸载该状态；浏览组件仍持有 DOM 测量与指针交互，并把用户调整写回页面。两库状态互不
  共享，选择集合与游标的原有清理规则不变。
- 新增两页操作链用例：排序＋键盘调宽 → 首次进入现有子目录 → 读取失败后重试 →
  返回根目录 → 下一页，逐步检查展示顺序、`aria-sort` 与实际列宽值保持。

针对 B13-2-02（拖动距离与可见列边界不一致）：

- 用户设置列宽后改为 `<colgroup>` 列宽加表格宽度等于五列总宽，浏览器不再把剩余宽度
  按比例回填到名称列；默认未调整时仍为 `width:100%` 铺满。测量、拖动起点、键盘步长、
  可见边界与 `aria-valuenow` 使用同一像素口径；普通拖动不加动画。
- E2E 直接测量表头 `getBoundingClientRect()`：键盘右调、指针右拖和左拖后边界与播报值
  误差不超过 1px，双击恢复默认后回到原边界；排序状态未被调宽误触。
- 页面规范补充“用户设定宽度后表格恰为五列总宽、剩余面板空间留在表格外、默认仍铺满”。

实际命令与结果（cwd `web/`）：

- `npm run typecheck`：PASS。
- `npx eslint`（7 个变更 TS/TSX 文件）：PASS；`npx prettier --check`：PASS。
- `npm run build`：PASS；仅现有 >500 kB chunk 提醒。
- `npm run test -- run`（Task 指定 5 个受影响文件）：**106 passed / 5 files**，
  10.96s。
- `npm run test:e2e -- tests/e2e/files-interactions.spec.ts
  tests/e2e/files-read-handoff.spec.ts`：**8 passed**（含两页新增的边界与跨目录／翻页
  保留用例，6.1s）。
- `npm run test:e2e -- --config=playwright.python.config.ts
  tests/e2e/live-files.python.spec.ts`：**6 passed**；真实临时 Python／SQLite／Storage
  用例在两页排序、调宽、勾选后打开 Gamma-Directory，并核对新目录仍保持排序与宽度。
- 根目录 `python3 scripts/check_governance.py`：PASS；`git diff --check`：无问题。
- 手动浏览器检查（Node 假服务、当前构建）：1536×1024 两页名称列 927→943px，
  可见表头宽度 943px、播报 943px；390×844 下文档无横向溢出，横向滚动只在表格容器；
  `prefers-reduced-motion: reduce` 下列表单元格 transition 为 `0s`。

本轮测试命令实际执行约 1 分钟（含一次手动浏览器脚本），低于本轮总用时 30%。修正后
没有产品用例首次失败。未执行 B 的完整验收矩阵、direct-files 两条危险操作回归或屏幕
阅读器实测；排序仍只针对当前页，列宽为用户调整后表格精确宽度、剩余面板空间在表格外，
整页重载恢复默认，均为本 Task 既有边界。

### B Review Result

```text
Reviewer: B
Reviewed Base: 9811df4559d94db5b648f6152476f39035a12ae5
Reviewed Head: 159d15095a6c92a9c9db9fdd0a532dd4e7c466a0
Product Checkpoint: 31466c1d600f850f06cf26c2c42f62b1ba555ebf
Decision: FIX REQUIRED — 2026-11-13
Authorized bug acceptance complete: NO
Next: SAME TASK FIX LOOP
```

B 已审查完整 Base..Head 的 14 个文件，包含实现、两份规范、测试及规划／交接提交。
本轮前分支 `main`，HEAD 如上，工作区干净，治理检查 PASS。Slice54 已接受的规则弹窗
三项结果不在本独立修复范围内，保持原关闭；SLICE／Roadmap／Progress 不改。

**结果核对：** 指定蓝色说明已从两处渲染移除；列表悬停、网格选中／Space 切换及
当前页排序／重置入口已有实际交付。B 使用新构建从现有登录、侧栏、文件夹和表头入口
核验，媒体库网格保留所选项，Space 可取消；390px 文档宽度为 390px，无整页横向溢出，
reduced-motion 网格 transition 为 0s。列宽调整与跨目录保留尚未完成，阻塞如下。

#### B13-2-01 — P1：进入子目录就丢失排序与列宽

实际旅程：文件页根目录 → 点击名称升序 → 按方向左键调宽 → 点击已有 Movies 文件夹；
子目录显示后排序变回服务端默认，列宽样式清空。媒体库通过侧栏进入 → 名称升序 →
按方向右键调宽 → 点击已有 Breaking Bad 文件夹，同样丢失。文件页调宽值 911 变回 927；
媒体库 943 变回 927，两页 `aria-sort` 均从 ascending 变为 null。

原因：新状态位于 `FileBrowseView`／`MediaBrowseView` 内；首次进入未缓存目录时，
页面先展示读取分支并卸载浏览组件，随后新组件重新初始化 sort 和 widths。不能用
同一目录内的列表／网格切换测试证明跨目录保留。问题由产品提交 `31466c1d` 引入，
不满足本 Task 第 4 步和页面规范承诺的同页切目录／翻页保持。

开发指导：

1. 将排序、用户列宽状态放到各自主页面中跨目录读取保持挂载的位置，再传给浏览组件；
   DOM 测量和指针交互留在实际表格侧。沿用普通 React 会话状态，无需持久化或新偏好系统。
2. 保持两种库各自独立；切目录／翻页保留呈现设置，选择集合继续采用原有清理规则。
3. 在现有两页浏览用例增加“排序＋调宽 → 首次进入现有子目录 → 返回 → 下一页”的
   操作链，检查显示顺序和真实列边界仍保持；现有读取失败后重试也沿用该会话设置。

#### B13-2-02 — P1：拖动距离与可见列边界不一致

实际旅程：1536×1024 文件页 → 打开 Movies → 把名称列右边界向左拖 240px 并松手。
名称列实际从 927px 变为约 849.11px，只缩短约 77.89px，而手柄播报 687px。
这会让用户拖到想要的位置后仍看到列边界偏离鼠标，继续调节时又以不一致的宽度为起点。
不是像素风格问题，是“调整列宽”未准确控制可见宽度。

原因：共享 hook 只写各列 CSS 宽度和 table 的 minWidth，表格仍为 `width:100%`；
列宽合计小于容器时，浏览器重新分配剩余空间，实际宽度偏离控制器状态。现有浏览器
测试只检查 `aria-valuenow` 变化，未检查真正的列边界。问题同样由 `31466c1d` 引入。

开发指导：

1. 统一列宽状态与实际表格几何：用户调整后采用能落实这些列宽的 table／col 布局，
   明确剩余空间归属；保留默认铺满和内部横滚，选择列不随剩余空间被拉宽。
2. 测量值、拖动起点、可见边界、键盘步长及 `aria-valuenow` 使用同一实际宽度口径。
   普通拖动不加动画，不增加独立校正服务或轮询。
3. 现有交互用例测量表头 `getBoundingClientRect()`：向左／右拖、键盘调整后，边界
   跟随预期变化（允许取整误差），并继续验证恢复默认、窄屏横滚及未误触排序。

**实际验证与证据：**

- cwd `web/`：`npm run build` PASS（保留现有 >500 kB chunk 提醒）；
  `npm run typecheck` PASS；计划指定 5 个受影响单元文件 **104 tests PASS**，
  单元耗时 10.26s，保留 jsdom `Window.scrollTo` 未实现输出。
- B 实际浏览按上述已有入口复现两项阻塞，记录几何、排序状态及截图；另实际核对
  悬停、网格选择、Space、390px 与 reduced-motion。浏览仅使用 Node 假服务的现有数据。
- 本机证据 `.git/validation-evidence/159d1509/patch-20261113-2-b/`：
  `resource-retention.json`、`media-retention.json`、`resource-resize.json`、`feedback.json`、
  对应截图、`unit.log`／`typecheck.log`。这是本机证据，不声明为远程 CI。
- 初次浏览脚本导入 Playwright 失败，改用现有包的 createRequire 后进入页面；一次在
  Dune 目录等候表格超时，其结果未用于产品结论。媒体库复现改用现有验收入口 Breaking Bad。
- 已确认阻塞，依 workflow 提前返回；未运行本轮完整 lint／format、Node 文件页回归、
  Python 原生／直接文件操作验收及完整视觉矩阵，修正后由 B 完成。测试／浏览探测用时
  小于本轮总用时 50%；代码与差异审查、结果核对和开发指导为本轮主要工作。

以上两项修正完成后 Developer 运行失败用例和受影响检查，交新的连贯候选；B 再独立
审查原 Base..新 Head 并完成剩余验收，不另建 Task，不改原接受范围。

---

独立小修 `PATCH-20261113-1` 已由 B 独立验收 **PASS — 2026-11-13**，授权范围完成。
生命周期遵循 [Development Workflow](docs/development-workflow.md#31-independent-minor-bugs)。
Slice54 保持原 **PASS / CLOSED**；下一大 Slice 仍由 A 另选。

## PATCH-20261113-1 — B PASS

```text
Task Type: STANDALONE MINOR BUG
Parent Slice: NONE
Difficulty / Test Level: Medium / T3
Reviewer: B
Decision: PASS — 2026-11-13
```

完整审查范围：`31f4b56936831699f75590f5afd49d58d630ba9c..5e809ac85a700762379950b8b076d27e58d66fa4`。
产品修正：`ce09e116c82db577611443e0141aa5ba25409190`；后继 `5e809ac8` 只补 B 浏览器验收。
[固定 B 验收](https://github.com/kentinya/mediaflow/blob/e8d7d33ff2a3d421cabbab952e15bcfc1a78ca19/TASK.md#patch-20261113-1--b-pass)
保留十项验收重评、实际命令／结果、B13-01 原始返工、测试断言修正、截图及证据限制；
[原计划与开发指导](https://github.com/kentinya/mediaflow/blob/b9d9fc038624ce518e14f6fd2e372d8b3b31d8cd/TASK.md)
保留完整实施范围和交付。

用户打开任务 → 查看文件证据 → 阅读当前结论、依据和逐次历史 → 按需展开统一诊断。
同一失败的相同下一步只显示一份，不同值保留来源；同状态的不同 Result 仍逐条保留。
四类恢复、附件警告、读取失败、未知提交核对及操作记录／导出保持。
实际验收：123 项受影响单元、42 项不同 Node 浏览器用例、56 项真实 Python 浏览器用例
通过；静态／构建／治理检查及三个视口前后视觉核对完成。原生未知效果样例在 Base 与
候选均因 Result 契约不一致而显示证据暂不可用，未确认效果正文使用已有 Node 用例验证；
该限制及首次失败均保留在固定验收。[Release](docs/release.md#current-v2-validation-boundary)
统一记录验证边界；本机原始证据不随 Git 推送。

文档治理仅协调导航、固定验收链接和验证范围；当前产品旅程见
[任务正文与文件证据](docs/task-center-page-spec.md#current--任务正文与文件证据)。

## PATCH-20261112-2 — B PASS

[前一独立修复的固定 B 验收](https://github.com/kentinya/mediaflow/blob/f3bca4cf72a8cdaa15f5646f13d72f45ad954678/TASK.md#patch-20261112-2--b-pass)
保留精确范围、实际结果、原始失败和限制。
