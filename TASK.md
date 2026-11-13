# NO ACTIVE IMPLEMENTATION TASK

以下 `PATCH-20261113-2` 是用户于 2026-11-13 要求的**独立修复规划草案**，仅授权规划；
尚未激活，不授权产品实现、其他角色工作、推送或部署。实施须另获用户授权，再将本通知
替换为正式 Task 状态。此前独立修复的 PASS 记录保留在本文末尾。

## PATCH-20261113-2 — 两种库文件浏览的提示、交互反馈与表头调节（规划草案）

Authority: 用户本轮三项问题及“规划一版独立修复Task”；
[Development Workflow](docs/development-workflow.md#31-independent-minor-bugs) 为生命周期依据。

```text
Task ID: PATCH-20261113-2
Task Type: STANDALONE MINOR BUG
Parent Slice: NONE
Status: PLANNED
Task Base: 9811df4559d94db5b648f6152476f39035a12ae5
Difficulty: Medium
Test Level: T3
Planner / Reviewer: B
Implementation Authorization: NOT GRANTED — PLANNING DRAFT ONLY
```

规划前治理检查 PASS；分支 `main`，HEAD 为上述 Task Base，暂存区／工作区干净，
工作区与 Git 可写。未读取运行数据库、私有配置、凭据或用户媒体。

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
   宣称新后端能力。现阶段仅提交本 Task 草案，不修改产品、测试或其他文档。

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

尚未实施。实施后以一个连贯 checkpoint 交 `READY FOR B REVIEW`：实际改动与决策、
受影响测试精确命令／结果、剩余问题／风险；完整验收由 B 独立完成。

### B Review Result

尚未提交候选、未验收。仅规划草案完成，不是产品通过。PASS 后按 workflow 记录精确
Base..Head 与真实结果，恢复简洁 `NO ACTIVE IMPLEMENTATION TASK`，不关闭任何 Slice。

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
