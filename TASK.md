# Task PATCH-20261119-2 — 删除各页顶栏搜索框

Next Action: B RE-REVIEWS THE PATCH-20261119-2 FIX CANDIDATE

用户于 2026-11-19 授权激活独立 Task。B 已审查首个候选并退回，Developer 已按 B 的修正
指导完成修复，交回 B 审查（修正报告见本页末尾）。
[独立修复工作流](docs/development-workflow.md#31-independent-minor-bugs) ·
[上一独立修复的 B 验收](https://github.com/kentinya/mediaflow/blob/ace169f4ee14feb4a101b7b2da2e917fe1c7c145/TASK.md#patch-20261119-1--b-验收-pass)

```text
Task ID: PATCH-20261119-2
Task Type: STANDALONE MINOR BUG
Parent Slice: NONE
Status: READY FOR B REVIEW
Task Base: ac28d9bd480a5047f03680d80c5a83c6df28cb06
Difficulty: Medium
Test Level: T2
Planner / Reviewer: B
Implementation Authorization: USER AUTHORIZED ON 2026-11-19
```

### 目标与现状

连接前后以及访问任何主页面、子路由或深链时，共享顶栏仅提供账户入口。当前 `AppShell` 渲染
同一个搜索组件。文件和媒体库按名称筛选当前已加载的目录条目，存储管理向清单 API 发送
`q`；自动化、通知及连接页等呈现只读占位。删除后，文件和媒体库按面包屑、目录和分页浏览，
存储管理按提供商类型和分页查找条目。目录确实为空、存储清单为空或读取失败时，页面给出
对应状态以及适用的刷新、返回上一级或重试入口。[共享顶栏](web/src/shared/ui/AppShell.tsx) ·
[操作体验](docs/product-experience.md#v2-operator-web)

### 实施范围与步骤

1. 从 `AppShell` 删除搜索 DOM、专用路由分支、两个搜索 Context 及其 Hook、状态、订阅和
   Provider。从 `styles.css` 删除 `.mf-shell-search` 及其桌面、窄屏规则和搜索专用留白。
   保留页面定位文字和页面切换依赖的路由判断，账户入口继续靠右。
2. 文件与媒体库删除由顶栏驱动的关键词参数、行匹配、清空词和选择订阅、搜索无匹配文案。
   行列表直接使用当前有界目录结果。目录、翻页、刷新各自的选择生命周期继续由浏览页处理。
3. 存储管理删除 Web 清单选择与查询键中的关键词、关键词触发的游标重置和搜索提示，页面请求
   只发送适用的类型和分页参数。切换提供商类型时从第一页读取，后续游标沿用现有分页契约。
   按真实清单、类型筛选结果和读取失败分别提示后续操作。Web 页面沿用现有读取权限及 API，
   `GET /api/operations/storage-management/inventory` 的 `q` 属于独立调用契约。
4. 更新依赖旧顶栏搜索的测试。分页之后查看、复制或切换类型的用例改从现有分页和类型卡片
   到达目标，继续检查原业务结果。对照当前文档，修订共享顶栏、两种库视觉规格、存储管理
   搜索文案及对应现行需求中的搜索描述。已验收 Slice、Roadmap 和 Progress 作为历史依据。
   [文件视觉规格](docs/file-page-visual-spec.md) · [媒体库视觉规格](docs/media-library-page-visual-spec.md) ·
   [需求](docs/requirements.md) · [V2 需求](docs/v2-requirements.md)

### 验收标准

- [ ] 在 1536px 和 390px 检查连接页、九个侧栏主页面，另覆盖一个曾显示只读框的子路由直接
  进入、刷新和重连。顶栏 DOM 中搜索节点计数为零，含隐藏或禁用节点。键盘可达账户入口，
  账户靠右且顶栏无横向溢出。源码清除专用选择器、Context、关键词兜底和占位。
- [ ] 文件与媒体库展示当前页全部条目，保留列表／网格、按名排序、行选择、目录与分页浏览。
  空目录可刷新或回上级，读取失败沿用原安全重试。浏览和切页仅执行有界读取。
- [ ] 存储清单请求不携带 `q`。从后续页切换提供商类型时，首个请求从第一页读取，分页仍能
  到达超过首屏上限的条目。真实空清单、筛选空结果及读取失败均有正确反馈。
- [ ] 探索、整理规则、自动化的页内搜索以及库卡片溢出菜单、文件操作弹卡里的独立搜索仍可
  正常输入。相关现行文档与浏览器断言反映同一顶栏行为。

### Developer 受影响检查

- 在 `web/` 运行 `npm run typecheck`，再运行 `npx eslint src/shared/ui/AppShell.tsx src/features/library/StorageFilesPage.tsx src/features/library/MediaLibraryFilesPage.tsx src/features/storage/StorageManagementPage.tsx src/features/storage/storage-management-query.ts`，检查删除后的类型与 Hook 调用。
- 在 `web/` 运行 `npm run test -- run src/shared/ui/AppShell.test.tsx src/features/library/StorageFilesPage.test.tsx src/features/library/MediaLibraryFilesPage.test.tsx src/features/storage/StorageManagementPage.test.tsx`，检查顶栏、未筛选的目录条目、空态和类型筛选游标。
- 在 `web/` 运行 `npm run build`，再运行 `npm run test:e2e -- tests/e2e/page-transition.spec.ts tests/e2e/rules-readiness.spec.ts tests/e2e/storage-management.spec.ts tests/e2e/medialib-files.spec.ts`，覆盖共享顶栏、类型筛选和媒体库入口的变更。
- 在仓库根目录运行 `python3 -B scripts/check_governance.py`、`git diff --check`，以及
  `rg -n 'mf-shell-search|FilesSearchContext|StorageSearchContext|useFilesSearch|useStorageSearch' web/src --glob '!**/*.test.*'`。
  最后一条命令应无匹配，退出码为 1。

### B 独立验收

- 对候选构建独立复跑上述浏览器用例。在桌面、窄屏核对实际账户布局、键盘焦点、页内搜索和
  存储请求 URL。使用现有测试数据打开一个通知子路由或自动化子路由，验证刷新和重连。
- 在 `web/` 补跑 `npm run test:e2e -- tests/e2e/deep-link.spec.ts tests/e2e/files-interactions.spec.ts tests/e2e/automation-presentation.spec.ts` 和 `npm run test -- run src/features/explore/ExplorePage.test.tsx src/shared/api/storage-management-api.test.ts`，检查认证续转、两个库的浏览交互、页内搜索及独立 API 参数契约。
- 审查完整 Task Base 到候选的差异及现行规范，记录命令结果和 `PASS` 或 `FIX REQUIRED`。
  T2 验收聚焦共享顶栏和三个直接消费搜索值的页面。

## Developer Completion Report

```text
Task Base: ac28d9bd480a5047f03680d80c5a83c6df28cb06
Implementation Candidate: 9012bfa104c57e518e024e0c773453dc1431ff2d
Branch: main
Status: READY FOR B REVIEW
```

**实施结果**

- `AppShell` 删除顶栏搜索 DOM、文件／存储两个 Context 与 Hook、搜索状态／订阅／Provider、
  专用路由分支和搜索图标引用；顶栏只渲染靠右账户控件。`styles.css` 删除
  `.mf-shell-search` 的桌面、窄屏规则和搜索专用间距，保留定位文字、页面切换判断及账户布局。
- 文件与媒体库的行 VM 直接来自当前有界目录结果，删除关键词匹配、清空词、选择订阅和
  “无匹配搜索”文案；空目录继续显示“可以刷新或返回上一级目录”，刷新、目录与游标生命周期
  仍由浏览页处理。
- 存储管理的选择、Query key 与请求只含类型和分页参数；从后续页切换类型时由 render-phase
  basis 同步清空游标，下一请求从该类型第一页读取。清单范围、类型筛选空结果和真实空清单
  分别显示对应说明；独立 API `q` 契约未改。
- 受旧顶栏搜索影响的单元／浏览器用例已改为通过类型卡片、显式分页和原目录浏览到达目标；
  新增请求断言确认存储清单 URL 不含 `q`，并覆盖后续页切换类型不带旧游标。同步修订顶栏、
  两种库视觉规格、存储管理文案、现行需求和架构说明。

**实际验证（cwd `/Users/songzhidong/mediaflow`，候选工作树）**

```text
python3 -B scripts/check_governance.py                              -> PASS
git diff --check                                                   -> clean
rg -n 'mf-shell-search|FilesSearchContext|StorageSearchContext|
     useFilesSearch|useStorageSearch' web/src --glob '!**/*.test.*' -> exit 1 / no match
web: npm run typecheck                                             -> OK
web: npx eslint <AppShell + 4 affected feature files>              -> OK
web: npx prettier --check <changed files>                          -> All matched
web: npm run test -- run src/shared/ui/AppShell.test.tsx
     src/features/library/StorageFilesPage.test.tsx
     src/features/library/MediaLibraryFilesPage.test.tsx
     src/features/storage/StorageManagementPage.test.tsx           -> 4 files, 155 passed (18.16s)
web: npm run build                                                 -> built; Vite large-chunk warning only
web: npm run test:e2e -- tests/e2e/page-transition.spec.ts
     tests/e2e/rules-readiness.spec.ts tests/e2e/storage-management.spec.ts
     tests/e2e/medialib-files.spec.ts                               -> 67 passed (1.3m)
```

**剩余与风险**

- Developer 未运行 B 独立验收中的 `deep-link`、`files-interactions`、
  `automation-presentation` 浏览器用例，也未运行 `ExplorePage`／存储 API 参数测试；这些按
  Task 分工由 B 在候选构建上复跑。
- 未运行全量 Web／Python／打包门禁；桌面／390px 实际视觉截图与键盘顺序仍需 B 独立查看。
- 构建保留既有 Vite “chunk 超过 500 kB”警告，无新增失败；全量回归与最终风险判定由 B 负责。

## B Review Result — FIX REQUIRED

```text
Reviewed Base: ac28d9bd480a5047f03680d80c5a83c6df28cb06
Reviewed Head: 08929c1238009a41b37e90e3564402ec573ec5da
Implementation Candidate: 9012bfa104c57e518e024e0c773453dc1431ff2d
Decision: FIX REQUIRED
Next: SAME TASK FIX LOOP
```

连接后从侧栏进入「存储管理」。当配置有 105 项时，全部类型第一页显示 100 项。点击「SMB」后，
如果清单响应尚未返回，页面会显示「已应用类型筛选」，表里却还是本地存储。SMB 响应到达后
才只显示 NAS。`9012bfa1` 让清单提示根据刚选中的卡片声明筛选完成，而表格在这段时间继续
展示上一次读取结果。类型卡片是移除关键词搜索后查找存储的入口，用户需要知道所选类型的结果何时可用。
[清单渲染](web/src/features/storage/StorageManagementPage.tsx)

### Developer 修正指导

1. 使用清单查询已有的 `isPlaceholderData` 区分等待中的旧结果和已返回的结果。显示旧表时用
   清楚的读取提示标明它属于上次读取。新结果到达后按当前类型显示条目、分页提示或空态。
2. 在 `ProviderCards` 的 `onSelect` 一次完成类型更新和游标清空。查询直接使用这两个值，
   删除顶栏搜索退出后多余的 `pageBasis` 和 `effectiveAfter`。
3. 扩充现有 `storage-management.spec.ts` 大清单用例。通过「SMB」卡片实际发起读取，在响应
   等待期间核对旧行和读取提示，响应到达后核对 NAS 行。继续验证从后续页改类型时，请求只有
   新的 `family`，`after` 和 `q` 均缺席。执行 `npm run typecheck`、`npm run build`，以及
   `npm run test:e2e -- tests/e2e/storage-management.spec.ts -g 'legal over-limit inventory|shared topbar is account-only'`。

### B 本轮验证

治理检查、Base..Head 空白检查和 Web 构建通过。现有 3 个浏览器用例通过，覆盖桌面及窄屏账户
入口、存储请求无 `q` 和从后续页切换类型。通过已有侧栏入口对 SMB 请求施加延迟，复现上述
反馈错误。证据位于 `.git/validation-evidence/9012bfa1/patch-20261119-2-b/` 的
`storage-filter.log`、`storage-smb-response-pending.png`、`build.log` 和 `focused.log`。
修正候选交回后，B 继续执行本 Task 的 T2 验收。

## Developer Completion Report — B 反馈：类型筛选等待中的清单提示

```text
Task Base: ac28d9bd480a5047f03680d80c5a83c6df28cb06
Reviewed Fix Target: 08929c1238009a41b37e90e3564402ec573ec5da
Implementation Candidate: 69156b5908cfdc108ae2a6f2134605b1b51246b5
Branch: main
Status: READY FOR B REVIEW
```

**起点**

本轮从 `main`／`9967f7992d7761c74194a6acde6217f994a34f2e`（B 的 FIX REQUIRED 检查点）
开始，工作区与暂存区干净，无既存未提交文件；修正提交为 `69156b59`，本报告随后的
TASK.md 交接提交单独保存。

**修正结果**

1. 清单提示改由查询自身的 `isPlaceholderData` 判定：新类型或新页读取未返回时显示
   「正在读取所选的存储清单」并声明「已选择「SMB」（或当前选择）；新的清单读取尚未返回，
   页面保留上一次读取的结果」，旧表继续可见但不再被当作所选类型的结果。此时不显示
   `InventoryScopeNote`（“已应用类型筛选”、继续显示更多、返回第一页）也不再判定空态，
   避免用上一次读取的数据声明当前类型的分页或空结果。新结果到达后按当前类型显示条目、
   分页提示或空态。读取失败仍由 `AuthorizedReadBoundary` 呈现原安全重试。
2. `ProviderCards.onSelect` 在同一次事件中完成类型更新与游标清空，查询直接使用
   `{family, after}` 这两个值；删除顶栏搜索退出后遗留的 `pageBasis` 与 `effectiveAfter`。
3. 扩充 `tests/e2e/storage-management.spec.ts` 大清单用例：通过「SMB」卡片真实发起读取，
   在响应等待期间核对旧行（本地存储 000）、读取提示、无“已应用类型筛选”与无继续按钮，
   放行响应后核对 NAS 行、提示消失、旧行消失。该用例从后续页改类型的请求断言收紧为
   `searchParams.keys() === ["family"]` 且值为 `smb`，`after` 与 `q` 均缺席。
   另在 `StorageManagementPage.test.tsx` 新增同一等待窗口的单测（受控 Promise 延迟 SMB
   读取）：等待中显示提示与旧行、不显示所选类型行或筛选空态；到达后只显示所选类型行。

**实际验证（cwd `/Users/songzhidong/mediaflow`，候选工作树）**

```text
python3 -B scripts/check_governance.py                              -> PASS
git diff --check                                                   -> clean
rg -n 'mf-shell-search|FilesSearchContext|StorageSearchContext|
     useFilesSearch|useStorageSearch' web/src --glob '!**/*.test.*' -> exit 1 / no match
web: npm run typecheck                                             -> OK
web: npx eslint src/shared/ui/AppShell.tsx
     src/features/library/StorageFilesPage.tsx
     src/features/library/MediaLibraryFilesPage.tsx
     src/features/storage/StorageManagementPage.tsx
     src/features/storage/storage-management-query.ts
     tests/e2e/storage-management.spec.ts                          -> OK
web: npx prettier --check <3 changed files>                        -> All matched
web: npm run test -- run src/features/storage/StorageManagementPage.test.tsx
                                                                   -> 51 passed (7.4s)
web: npm run test -- run src/shared/ui/AppShell.test.tsx
     src/features/library/StorageFilesPage.test.tsx
     src/features/library/MediaLibraryFilesPage.test.tsx
     src/features/storage/StorageManagementPage.test.tsx           -> 4 files, 156 passed (17.8s)
web: npm run build                                                 -> built; Vite large-chunk warning only
web: npm run test:e2e -- tests/e2e/storage-management.spec.ts
     -g 'legal over-limit inventory|shared topbar is account-only' -> 2 passed (2.0s)
web: npm run test:e2e -- tests/e2e/page-transition.spec.ts
     tests/e2e/rules-readiness.spec.ts tests/e2e/storage-management.spec.ts
     tests/e2e/medialib-files.spec.ts                              -> 67 passed (1.2m)
```

**剩余与风险**

- 等待读取期间清单范围说明与其“继续显示更多／返回第一页”按钮暂时隐藏，新结果到达后
  恢复；这是为避免用上一次读取的 `nextAfter` 继续翻页所选的取舍，不是读取失败。
- `deep-link`、`files-interactions`、`automation-presentation` 浏览器用例和
  `ExplorePage`／存储 API 参数单测仍属 B 的独立验收范围，本轮未运行；1536px／390px 的
  实际截图与键盘顺序复核、全量回归和最终风险判定仍由 B 负责。
- 构建保留既有 Vite “chunk 超过 500 kB”警告，无新增失败。
