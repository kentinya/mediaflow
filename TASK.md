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

## Planning-only draft — PATCH-20261109-1 删除文件页整理记录并统一目录接入

用户于 2026-11-09 根据截图调查要求规划 Task，随后明确提出删除“整理记录”。
本草案按该方向更新，保留上方 NO ACTIVE IMPLEMENTATION TASK，实施时再激活。
依据 [Development Workflow §3.1](docs/development-workflow.md#31-independent-minor-bugs)，
由 B 规划和独立验收；角色经验见 [B experience](docs/agent-experience/task-planner-reviewer.md)。

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

用户进入“文件”浏览资源库，库上下文之后直接呈现目录的加载、列表、空态或错误。
文件页删除整块“整理记录”；整理工作的状态、结果、摘要和确认使用已有任务中心入口。
用户从文件选择发起整理仍进入原准确准备／摘要页面；提交结果未知时继续核对原请求。

Base 的 `StorageFilesPage.tsx` 仅在目录数据未返回及网络异常分支挂载
`OrganizeWorkPanel`，目录成功后整块移除。本地浏览器复现了截图对应的临时记录区、
400ms 后出现目录等待区以及成功后记录消失；媒体库页直接呈现目录读取区域。
当前 `fetchFilesOrganizeWork` 同时供提交响应丢失后的准确 `requestId` 核对使用。
该共享调用与界面记录列表的生命周期分别处理。

适用 `REQ-WEB-003/005`、`UX-001/002/007`、`V2-UX-012/015`；完整旅程见
[Real Storage Files](docs/product-experience.md#real-storage-files)、
[Manual organize](docs/product-experience.md#manual-organize) 和
[CURRENT 读取接入](docs/product-experience.md#current--slice52-experience-refinement-slice52-pass--closed)。
本次用户选择替换旧旅程中文件页展示整理历史的呈现约定，沿用其准确核对及已有工作可达性。

### Implementation Scope

1. 删除文件页 `OrganizeWorkPanel`、两处挂载、专用状态／文案及专用查询 hook。
   按实际消费者清理 `organize-work-query.ts` 和对应导入／测试依赖；
   `fetchFilesOrganizeWork` 及其请求身份核对能力按现有消费者保留。
2. 文件页保持提示、库卡片及路径上下文，其后直接呈现目录区。
   收敛等待／异常／成功分支中的重复组合，复用现有 `FileBrowseView` 和授权边界；
   目录快读／缓存直接接入，慢读显示现有协调占位，同条件刷新保留列表。
   需要时仅调整文件页局部布局，保持内容接入、路径、工具栏及普通操作入口可用。
3. 修正整理提交错误中“在资源库文件页的整理记录中继续处理”等悬空提示，
   指向已有任务中心查看已受理工作。保留按准确 requestId 核对并进入对应摘要的路径。
   核对失败时明确受理尚未确认、可去任务中心核查；提示和导航均不重复提交。
4. 验证从任务中心查看本次手动整理任务、打开其当前摘要并明确确认的完整旅程，
   包括目录离开／返回、刷新／重认证和提交响应丢失的场景。
   更新直接受影响测试，新增精确浏览器场景可集中到
   `web/tests/e2e/files-read-handoff.spec.ts`。

### Acceptance Criteria

- [ ] AC-1：文件页首次进入、快／慢目录读取、缓存返回、成功、空目录、网络及业务错误、
  手动刷新和切库／切路径全过程都没有“整理记录”标题、说明、列表及分页。
  普通浏览不发起记录列表查询或其轮询；目录区直接承接当前库上下文。
- [ ] AC-2：等待反馈、真实文件列表及错误恢复按实际读取状态显示，提示／卡片／路径各一次；
  同条件刷新保留内容，快切和迟到响应归属正确。桌面1536×1024与390×844下
  等待和就绪接入平顺，键盘可用、长路径可读、无水平溢出；reduced-motion 反馈清楚。
- [ ] AC-3：文件整理成功受理后进入准确准备／摘要；用户离开后从任务中心仍能找到
  同一任务、查看摘要、明确确认及查看独立结果。刷新／重认证后该入口继续可达。
- [ ] AC-4：提交响应丢失时，仍按原 requestId 核对并定位对应工作；核对暂不可用时
  提示准确且任务中心可供核查。界面没有指向已删除区域的指引；核对及查看不重发提交。
- [ ] AC-5：媒体库浏览、文件页普通操作状态、无 Active／无库／无效路径和401／403
  保持原行为。浏览／刷新／返回只读；整理仍由现有明确确认触发。

### Required Tests

测试责任依 [workflow §6](docs/development-workflow.md#6-test-levels)。Web 命令均在 `web/` 运行。

**Developer — affected tests**

```sh
npm run test -- run src/features/library/StorageFilesPage.test.tsx src/features/library/MediaLibraryFilesPage.test.tsx
npm run typecheck
npm run build
npm run test:e2e -- tests/e2e/files-read-handoff.spec.ts
```

组件测试覆盖各目录状态下记录区及其普通浏览请求退出、错误后重读、迟到响应，
并保持现有准确 requestId 核对、未知响应及准确导航断言。
新增浏览器场景使用真实路由／生产构建和本地夹具，检查快慢读取的中间状态、
桌面／窄屏、任务中心重开准确摘要以及请求台账。
修改文件另跑精确路径 `npx eslint <changed-ts-tsx-paths>` 和
`npx prettier --check <changed-web-paths>`；根目录运行
`python3 scripts/check_governance.py`、`git diff --check` 后交实现检查点。

**B — acceptance and regression**

独立审查 Task Base..候选，在最终候选构建并执行：

```sh
npm run typecheck
npm run lint
npm run format:check
npm run build
npm run test -- run src/features/library/StorageFilesPage.test.tsx src/features/library/MediaLibraryFilesPage.test.tsx src/features/library/LibraryFileOperationsDialog.test.tsx
npm run test:e2e -- tests/e2e/files-read-handoff.spec.ts tests/e2e/library-files.spec.ts tests/e2e/medialib-files.spec.ts tests/e2e/page-transition.spec.ts
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/live-files.python.spec.ts tests/e2e/organize-source-history.python.spec.ts
```

覆盖两库目录接入、普通操作入口、真实 Python live list 的只读／错误恢复及整理摘要确认。
B 补验文件页受理后离开、任务中心找到同一任务并确认摘要、刷新／重认证返回，
以及响应丢失后准确核对与核对失败指引；新增断言复用现有本地夹具。
逐阶段检查桌面／窄屏画面和实际操作，原始结果保存到
`.git/validation-evidence/<candidate>/patch-20261109-1/`。
T3 验收范围为文件页呈现、记录入口退出及直接依赖。

### Non-goals

后端记录／查询 API、任务数据和历史保留；任务中心沿用现有入口及摘要确认。
本 Task 不涉及后端／权限／Active／schema／Storage／执行引擎变更，
共享动画／等待门限和其他页面业务功能保持。
Slice52、Roadmap、Progress 和既有接受身份保持；本轮只更新 Task 草案。

### Developer Completion Report

待实施后填写检查点、实际受影响测试结果、剩余工作及 READY FOR B REVIEW。

### B Review Result

待独立审查后记录精确 Base..Head、实际验收结果与 PASS／FIX REQUIRED。
PASS 后按独立修正流程恢复紧凑 NO ACTIVE IMPLEMENTATION TASK。
