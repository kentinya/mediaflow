# Task PATCH-20261119-2 — 删除各页顶栏搜索框

用户于 2026-11-19 授权激活独立 Task，待 Developer 开始实施。
[独立修复工作流](docs/development-workflow.md#31-independent-minor-bugs) ·
[上一独立修复的 B 验收](https://github.com/kentinya/mediaflow/blob/ace169f4ee14feb4a101b7b2da2e917fe1c7c145/TASK.md#patch-20261119-1--b-验收-pass)

```text
Task ID: PATCH-20261119-2
Task Type: STANDALONE MINOR BUG
Parent Slice: NONE
Status: PLANNED
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
