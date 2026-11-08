# PATCH-20261109-1 — 删除文件页整理记录并统一目录接入

```text
Task ID: PATCH-20261109-1
Task Type: STANDALONE MINOR BUG
Parent Slice: NONE
Status: READY FOR B REVIEW
Task Base: 45674526b04d3366f533b86e864b3c8d179736ed
Difficulty: Medium
Test Level: T3
Planner / Reviewer: B
Development Authorization: USER-AUTHORIZED IMPLEMENTATION OF B'S COMMITTED DRAFT
Candidate Checkpoint: cc6ffbb1496685d440e731421c0f45ee44953995
```

用户于 2026-11-09 根据截图调查要求规划 Task，随后明确提出删除“整理记录”，并授权
按已提交草案实施。B 负责规划与独立验收；本轮由 Developer 直接实施该已提交草案，
未经 B 预审、不自签 PASS。依据
[Development Workflow §3.1](docs/development-workflow.md#31-independent-minor-bugs)。

## Goal and observed gap

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

## Implementation Scope

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

## Acceptance Criteria

- [x] AC-1：文件页首次进入、快／慢目录读取、缓存返回、成功、空目录、网络及业务错误、
  手动刷新和切库／切路径全过程都没有“整理记录”标题、说明、列表及分页。
  普通浏览不发起记录列表查询或其轮询；目录区直接承接当前库上下文。
- [x] AC-2：等待反馈、真实文件列表及错误恢复按实际读取状态显示，提示／卡片／路径各一次；
  同条件刷新保留内容，快切和迟到响应归属正确。桌面1536×1024与390×844下
  等待和就绪接入平顺，键盘可用、长路径可读、无水平溢出；reduced-motion 反馈清楚。
- [ ] AC-3：文件整理成功受理后进入准确准备／摘要；用户离开后从任务中心仍能找到
  同一任务、查看摘要、明确确认及查看独立结果。刷新／重认证后该入口继续可达。
  **BLOCKED（见 Developer Completion Report）：现有任务中心对普通初次待确认的手动整理
  只提供状态／取消／证据读取，不提供该准备的摘要与确认入口；本轮未新增后端或任务中心入口。**
- [x] AC-4：提交响应丢失时，仍按原 requestId 核对并定位对应工作；核对暂不可用时
  提示准确且任务中心可供核查。界面没有指向已删除区域的指引；核对及查看不重发提交。
- [x] AC-5：媒体库浏览、文件页普通操作状态、无 Active／无库／无效路径和401／403
  保持原行为。浏览／刷新／返回只读；整理仍由现有明确确认触发。

## Required Tests

测试责任依 [workflow §6](docs/development-workflow.md#6-test-levels)。Web 命令均在 `web/` 运行。

**Developer — affected tests**

```sh
npm run test -- run src/features/library/StorageFilesPage.test.tsx src/features/library/MediaLibraryFilesPage.test.tsx src/features/library/LibraryFileOperationsDialog.test.tsx
npm run typecheck
npm run build
npm run test:e2e -- tests/e2e/files-read-handoff.spec.ts
```

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

## Non-goals

后端记录／查询 API、任务数据和历史保留；任务中心沿用现有入口及摘要确认。
本 Task 不涉及后端／权限／Active／schema／Storage／执行引擎变更，
共享动画／等待门限和其他页面业务功能保持。
Slice52、Roadmap、Progress 和既有接受身份保持。

## Developer Completion Report

```text
Implementation commit: cc6ffbb1496685d440e731421c0f45ee44953995
Base:                  45674526b04d3366f533b86e864b3c8d179736ed
Branch:                main
Role exception:        用户直接授权 Developer 实施 B 的已提交草案；未获 B 预审，未自签 PASS
```

### Changed files

- `web/src/features/library/StorageFilesPage.tsx`：删除 `OrganizeWorkPanel`、
  `ORGANIZE_WORK_STATUS_LABELS`、两处挂载及专用查询导入；新增局部
  `renderBrowseContext`（提示／库卡片／切换提示）供等待与异常分支复用，成功分支仍由
  `FileBrowseView` 渲染同一上下文；整理提交两处未确认提示改为指向任务中心。
- `web/src/features/library/organize-work-query.ts`：删除（唯一消费者为已删除面板）。
- `web/src/features/library/StorageFilesPage.test.tsx`：普通浏览、慢读取、读取失败断言
  无记录区且不发起 `/files/organize-work`；未确认整理的两种提示断言任务中心文案与
  不重发；既有准确 `requestId` 核对、他 binding／等价未决记录拒绝、精确导航断言保持。
- `web/tests/e2e/files-read-handoff.spec.ts`：新增 4 个真实路由／生产构建场景：
  快读、1200ms 慢读（等待→表格）、读取失败后唯一只读重试、390×844 无水平溢出；
  每个场景都从实际请求台账断言无 organize-work 列表读取，且页面无“整理记录”。

`fetchFilesOrganizeWork`、`api-client` 的准确 `requestId` 核对能力与全部消费者保留；
目录读取、授权边界、等待门限、刷新、选择、工具栏与普通操作行为未改。

### Actual results

| 命令（cwd `web/`） | 实际结果 |
|---|---|
| `npm run test -- run src/features/library/StorageFilesPage.test.tsx src/features/library/MediaLibraryFilesPage.test.tsx src/features/library/LibraryFileOperationsDialog.test.tsx` | 3 files, 90 passed |
| `npm run typecheck` | PASS |
| `npm run build` | PASS |
| `npm run test:e2e -- tests/e2e/files-read-handoff.spec.ts` | 4 passed |
| `npm run test:e2e -- tests/e2e/library-files.spec.ts tests/e2e/page-transition.spec.ts` | 59 passed（附加受影响回归） |
| `npx eslint <changed paths>` | PASS |
| `npx prettier --check <changed paths>` | PASS |
| `python3 scripts/check_governance.py` | PASS |
| `git diff --check` | PASS |

首轮浏览器场景因 glob 写成 `files?*` 未命中真实 API（请求无 query），两例等待超时；
改为 `**/api/v1/resource-libraries/*/files` 后 4 例全部通过。组件测试首轮
`tsc` 报 `release?.()` 控制流收窄错误，改为显式 gate 对象后通过。

### AC-3 blocker（必须由 B／用户决定）

以真实 Python 栈（`scripts/operations_inventory_harness.py`，生产构建 + 真实 API/SQLite/
Worker）实际复现：

1. Files 选择 `Three.2003.mkv` → 受理并生成计划摘要，页面仍在
   `/operations/organize/new?discoveryId=…`，摘要页有确认入口。
2. 经侧栏进入任务中心：该工作显示为“手动整理 / 进行中”，条目为
   “等待确认 / waiting_confirm”；详情只有 `取消运行`、`导出结果 JSON`、`查看证据`。
3. 打开条目证据：显示“审核与恢复 — 此文件没有待处理操作”，没有计划摘要或确认按钮。

代码佐证：
`mediaflow/application/manual_recovery_continuation.py::_files_native_summary` 对
“普通初次待确认、无四类问题、无已受理执行”的条目显式返回 `None`；
`web/src/features/operations/RunDetailTabs.tsx` / `TaskItemRecoveryPanel.tsx` 仅在
`manualRecoveryPreparation` 存在时渲染摘要确认；Web 侧没有任何
Task/run → `/operations/organize/new?discoveryId=…` 的入口（该入口此前仅由被删除的
Files 面板提供）。

因此本候选移除面板后，**已受理但尚未确认的手动整理准备没有重新进入摘要的入口**：
任务中心可看状态、取消、导出与证据，但不能查看摘要或确认。这与 AC-3 及已接受契约
“Files retains initial confirmation and exact task/preparation readback”冲突。

**本轮没有做的事（按 Non-goals 与不扩范围要求）**：未新增后端读取字段、未在任务中心
构造新入口、未用 mock/自造路由证明不存在的旅程。请 B／用户选择：

- 方案 A（推荐，跨层）：任务中心为该 Task 暴露精确准备身份并链接回同一准备／摘要；
  需要后端读取与 Task Center UI 变更，超出本 Task Non-goals，需重新定级（T4）。
- 方案 B（保留删除）：接受“离开准备页后无法回到未确认摘要”，并明确修改已接受旅程与
  AC-3；属于产品行为变更，需 A 或 user 明确决定。
- 方案 C：保留文件页唯一一个“继续未确认整理”入口（不是原记录列表），以满足可达性；
  同样需要 B／用户确认，因为与“删除整理记录”的呈现约定相邻。

若不选择 A/C 而按现状验收，本候选会让未确认准备孤立；Developer 不将 AC-3 标为通过。

### Remaining risks

- AC-3 未满足，见上；提示文案“请在任务中心查看是否已有该资源库的整理任务”对状态／结果
  真实，但不能替代摘要确认入口。
- 未运行 B 的完整 lint/format/全量 E2E/Python 验收；未截图逐一核对桌面／窄屏视觉，
  仅以真实浏览器场景断言无水平溢出与无记录区。
- 本机 Python harness 进程已停止；临时探针脚本已删除，未纳入检查点。

## B Review Result

待独立审查。请先决定 AC-3 blocker 的处理方向，再按上面的 B acceptance 计划执行。
