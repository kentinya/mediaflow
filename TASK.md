# NO ACTIVE IMPLEMENTATION TASK

Task PATCH-20261108-3 — OpenList 元数据解耦及现有失败修正 — **B PASS**。

```text
Task Type: STANDALONE MINOR BUG
Parent Slice: NONE
Decision: PASS
Task Base: 6db3647c7e77d54f3a49b6725c804f0794fc7fbb
Accepted Implementation Head: cf680df6e24725ba40ada378e158d6a0e44710e5
Reviewer: B
Review Date: 2026-11-08
```

用户进入 OpenList 文件页选择两个文件，经分析、精确摘要、明确确认及 Worker 执行，
完成原生移动与重命名，持久结果均为 SUCCESS / verified_complete。再次 Worker poll、
关联任务读回、返回文件页及刷新保持同一结果；63 次目录读取全部 refresh=false，
4 次 Move／Rename，取链接与内容读取均为 0。

源缺失、目标冲突、执行后列表失败、目标大小不符及原源仍在的结果符合现有语义。
Python 3.11 启动、容量设置完整整理、动作可读性及 V1／V2 CSP 修正均已验收。

| 验证 | 完整运行结果 |
|---|---|
| Python 3.11／3.12／3.13 | 每版 2651 passed、7 skipped，共 2658 项 |
| Web unit | 97 files、1459 passed |
| 默认 E2E | 264 passed |
| 16 份原生 Python specs | 190 passed、2 项脚本失败；两项独立运行 2 passed |
| Python／Web 静态检查、构建、示例及依赖检查 | PASS |
| wheel 构建与外部安装 smoke | PASS |
| Docker 原生传输 lifecycle smoke | PASS |
| Docker release-security smoke | PASS |

两项脚本记录对应第二次复制前的列表／授权同步，以及慢读编辑的 route 回调。
产品分别显示既有拒绝与刷新提示、保持已保存的启用状态和处理上限。按用户本轮明确的
产品旅程与范围要求收尾；第 12 项测试工具返工安排已撤销。完整运行的两项失败及
七项专用外部服务／耐久环境跳过保留在验收记录中。

完整复核、实际命令、逐文件结果及前次决定见 Git `64f3910b:TASK.md`；本轮收尾仅更改
TASK。源码与测试执行输入相对接受实现没有变化。原始证据位于本机
`.git/validation-evidence/cf680df6/b-final/`，包含日志、traces、截图、HTTP 台账、构建身份
及 Docker 启停记录。Colima 测试 VM 已停止，默认 context 保持原值。

Slice52 的接受身份和关闭结果保持。工作区预存文件保持。
生命周期依据 [Development Workflow](docs/development-workflow.md) §3.1；独立修正至此完成。

---

## Planning-only draft — PATCH-20261109-1 文件页目录接入与整理记录稳定呈现

用户于 2026-11-09 要求根据截图调查结果规划 Task。本节为规划草案，保留上方
NO ACTIVE IMPLEMENTATION TASK；实施开始时再按工作流激活本 Task。
授权范围：修正资源库文件页在目录读取期间临时展示整理记录、目录成功后记录消失的行为，
使文件浏览与记录查看各自稳定可用。独立修正依据
[Development Workflow §3.1](docs/development-workflow.md#31-independent-minor-bugs)，
规划／验收由 B 负责；角色经验见 [B experience](docs/agent-experience/task-planner-reviewer.md)。

```text
Task ID: PATCH-20261109-1
Task Type: STANDALONE MINOR BUG
Parent Slice: NONE
Status: PLANNED
Task Base: 45674526b04d3366f533b86e864b3c8d179736ed
Difficulty: Medium
Test Level: T3
Planner / Reviewer: B
Development Authorization: PLANNING ONLY
```

### Goal and observed gap

从侧栏“文件”进入 `/ui-v2/resourcelib/files`，用户先选择资源库、浏览目录，
并可在本页查看本账号提交的整理记录，打开准确计划摘要继续处理。
目录和记录分别显示自己的读取、成功、空态或失败；目录成功后记录入口及内容仍可访问。

Base 的 `StorageFilesPage.tsx` 仅在 `filesQuery.data === undefined` 和
`filesQuery.isError` 两个分支挂载 `OrganizeWorkPanel`，成功分支只有 `FileBrowseView`。
本地浏览器已复现：目录尚未返回时先出现“整理记录”，400ms 等待门限之后出现目录加载区，
成功后记录整块消失；网络失败时记录保留。媒体库页的库卡片后直接呈现目录读取区域。
该复现使用本地夹具与受控响应，截图中的示例记录可独立于目录请求先返回。

适用要求：`REQ-WEB-003/005`、`UX-001/002/007`、`V2-UX-012/015`；完整旅程见
[Real Storage Files](docs/product-experience.md#real-storage-files)、
[Manual organize](docs/product-experience.md#manual-organize) 和
[CURRENT 读取接入](docs/product-experience.md#current--slice52-experience-refinement-slice52-pass--closed)。
记录归属沿用 [CURRENT local readback](docs/architecture.md#current--slice46-presentation-and-work-query-ownership)。

### Implementation Scope

1. 调整 `web/src/features/library/StorageFilesPage.tsx` 的呈现组合：共用当前资源库的
   提示／库卡片／路径上下文；其后为目录区，目录区下方为独立的“整理记录”区。
   同一库内目录从等待到成功／失败、刷新和翻目录时，记录区保持同一组件身份与位置关系，
   展开状态和记录分页不因目录状态变化重置。成功列表复用现有 `FileBrowseView`，
   使提示、卡片和上下文各显示一次。
2. 目录区独立沿用现有等待门限、加载组件、列表／网格、真实空目录、读取错误及重读入口。
   快响应／有效缓存直接接入内容；慢读取显示协调等待，成功后平顺替换目录区。
   同条件刷新保留文件列表和现有刷新反馈。必要时仅补文件页局部布局样式，
   以正常目标内容高度接入保持阅读连续。
3. 记录区沿用现有有界 API、当前账号／资源库范围、状态说明、前三条／展开、
   后端游标分页及准确摘要链接。记录请求与目录请求独立进行；记录有自己的等待、
   空态、失败及明确只读重读入口。目录读取失败仍可打开已读记录；
   记录读取失败仍可浏览目录。切换资源库重置记录分页／展开并读取新库记录，
   迟到响应保持其原库归属；记录与文件路径切换分别维护各自状态。
4. 补充组件和浏览器回归：分别控制目录与记录的返回顺序，覆盖原截图阶段、
   成功后的记录可达性、错误恢复和跨库迟到响应；对照媒体库现有呈现。
   复用本地夹具，新增精确场景可集中在 `web/tests/e2e/files-read-handoff.spec.ts`。

### Acceptance Criteria

- [ ] AC-1：从侧栏首次进入文件页，目录先于记录／记录先于目录两种返回顺序均可用；
  页面保持库上下文 → 目录区 → 整理记录的清楚层级，记录内容按其自身读取状态呈现。
  快读、缓存返回和慢读全过程均没有“临时记录页再整块换成文件列表”的现象。
- [ ] AC-2：目录成功、有文件或真实空目录时，整理记录仍可查看；同库翻目录、刷新、
  列表／网格切换保持记录展开及合法分页。正常目录等待和就绪替换平顺，
  文件选择、路径、工具栏和普通操作状态入口保持原行为。
- [ ] AC-3：目录网络失败及业务失败分别显示现有可操作错误，记录仍可查看；
  显式重读成功后恢复目录。记录等待、空态、读取失败及显式重读分别真实，
  记录失败不阻挡文件浏览。无 Active、无库、无效路径、401／403 保持原入口和权限语义。
- [ ] AC-4：快速切库／路径和迟到响应保持正确归属；切库后的记录从新库第一页开始，
  同库目录状态变化保持记录分页。记录“查看更多／返回上一页”可达；打开准确记录、
  返回文件页以及刷新／重认证后仍可按当前账号和资源库读回记录。
- [ ] AC-5：桌面1536×1024与390×844检查进入、等待中、就绪、错误恢复和展开记录；
  记录长文件名、分页、键盘操作可用，内容宽度协调且没有水平溢出。
  媒体库页保持原有文件浏览层级；reduced-motion 下等待与接入仍清楚。
- [ ] AC-6：单纯进入、读取、翻页、展开、重读及返回只读取现有范围；
  请求台账确认未提交整理／普通文件命令，记录链接保留准确工作与返回上下文。
  “当前页面操作状态”继续只承载原普通文件工作。

### Required Tests

测试责任依 [workflow §6](docs/development-workflow.md#6-test-levels)。以下 Web 命令均在 `web/` 运行。

**Developer — affected tests**

```sh
npm run test -- run src/features/library/StorageFilesPage.test.tsx src/features/library/MediaLibraryFilesPage.test.tsx
npm run typecheck
npm run build
npm run test:e2e -- tests/e2e/files-read-handoff.spec.ts
```

组件测试覆盖 AC-1–4 的独立读取、空／失败／重读、正确归属、目录状态变化保持记录状态和
记录分页；新增浏览器场景使用实际路由及生产构建，覆盖两种返回顺序、成功后记录入口、
快／慢读取中间状态、桌面／窄屏和零命令请求。修改文件另跑精确路径的
`npx eslint <changed-ts-tsx-paths>`、`npx prettier --check <changed-web-paths>`。
根目录运行 `python3 scripts/check_governance.py` 和 `git diff --check` 后提交实现检查点。

**B — acceptance and regression**

独立审查精确 Task Base..候选，在最终候选重新构建并执行：

```sh
npm run typecheck
npm run lint
npm run format:check
npm run build
npm run test -- run src/features/library/StorageFilesPage.test.tsx src/features/library/MediaLibraryFilesPage.test.tsx src/features/library/LibraryFileOperationsDialog.test.tsx
npm run test:e2e -- tests/e2e/files-read-handoff.spec.ts tests/e2e/library-files.spec.ts tests/e2e/medialib-files.spec.ts tests/e2e/page-transition.spec.ts
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/live-files.python.spec.ts tests/e2e/organize-source-history.python.spec.ts
```

范围分别覆盖文件页组合／普通操作入口、两库实际浏览与读取接入、真实 Python live list 的
只读及错误恢复和整理摘要／确认旅程。B 补验从已就绪目录的记录链接打开准确摘要、
返回／刷新／重认证后重开，以及同库记录翻页后目录刷新、跨库迟到响应；
需要新增断言时复用上述本地夹具。保存桌面／窄屏的等待与就绪画面和实际中间过程，
结合可见层级、阅读连续性及交互验收；原始结果放在
`.git/validation-evidence/<candidate>/patch-20261109-1/`。
本 Task 的影响范围为文件页组合及直接依赖，T3 验收执行上述门禁。

### Non-goals

文件页局部呈现及其回归之外的产品代码、后端／API／权限／Active／schema／Storage／
执行引擎、整理状态或恢复机制、共享动画／等待门限、九页整体重设计和媒体库业务功能均在范围外。
Slice52、Roadmap、Progress 和已接受修正的身份保持；本轮文档变更仅此 Task 草案。

### Developer Completion Report

待实施后填写检查点、实际受影响测试结果、剩余工作及 READY FOR B REVIEW。

### B Review Result

待独立审查后记录精确 Base..Head、实际验收结果与 PASS／FIX REQUIRED。
PASS 后按独立修正流程恢复紧凑 NO ACTIVE IMPLEMENTATION TASK。
