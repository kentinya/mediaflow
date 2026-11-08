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
Candidate Checkpoint: 9f6f2f301d4908e02750055366d8c24759772807
B Reviewed Head: a3094876dd98cdd6b1d5601155da6fa0b0e426da
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

B 独立复核发现：原规划将任务中心的“查看状态／证据”当成了返回初次摘要的入口，
实际并不存在。AC-3 保留；本次修正允许补齐同一任务到既有准备页的只读关联和导航。
这是删除原唯一入口所需的旅程接续，不新建摘要或确认机制。

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
4. 在任务中心该手动整理 Task 的详情中提供“继续整理”入口，返回该 Task 已有的
   `/operations/organize/new?discoveryId=…` 准备页。后端详情读取提供准确持久关联，
   前端解析该关联并导航；复用既有准备页的读取、分析、摘要、确认和执行情况。
5. 验证从任务中心查看本次手动整理任务、打开其当前摘要并明确确认的完整旅程，
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
- [x] AC-3：文件整理成功受理后进入准确准备／摘要；用户离开后从任务中心仍能找到
  同一任务、查看摘要、明确确认及查看独立结果。刷新／重认证后该入口继续可达。
  本轮新增 Task 详情的持久准备关联及“继续整理”入口，原生旅程已从同一摘要确认一次并核对结果。
- [x] AC-4：提交响应丢失时，仍按原 requestId 核对并定位对应工作；核对暂不可用时
  提示准确且任务中心可供核查。界面没有指向已删除区域的指引；核对及查看不重发提交。
- [x] AC-5：媒体库浏览、文件页普通操作状态、无 Active／无库／无效路径和401／403
  保持原行为。浏览／刷新／返回只读；整理仍由现有明确确认触发。

## Developer guidance — 本次修正

1. 从 `mediaflow/interfaces/service_api.py::_operations_run_overview` 的准确 Task 身份出发，
   使用已有 `get_media_discovery_for_task(task_id)` 读取其持久准备关联；在详情响应中添加
   一个小型可选关联（例如 `filesPreparation`，包含 `discoveryId/resourceLibraryId`）。
   沿用现有读取权限和准备所属关系；没有关联时不提供入口。不要从文件名、最近记录、
   当前 Active 或浏览器记忆推算关联，也不要在列表逐项加载整份准备。
2. 在 `web/src/entities/operations/run.ts` 接入该详情字段；在
   `web/src/features/operations/OperationsLanding.tsx::RunDetailPanel` 放置可读的
   “继续整理”链接。复用 Router 已注册的准备路由及现有返回上下文，点击后读取原准备。
   覆盖尚在分析和已等待初次确认的真实工作，刷新／重认证后仍从持久关联进入。
3. 保持 `manual_recovery_continuation.py::_files_native_summary` 的四类恢复职责。
   此处补的是初次准备的返回入口；不要为显示链接把普通 WaitingConfirm 标成冲突／Attention，
   也不要改已有确认服务。已确认工作的返回由原准备页展示已受理状态／执行情况。
4. 从 Files 实际选文件创建工作，记录原 Task／准备身份，离开到任务中心并点击新入口；
   进入同一摘要后明确确认一次，驱动本地 Worker，核对原 Task 的结果。
   同时做刷新／重新连接及未知提交核对场景。导航、刷新和重新连接只读取。
5. 按下面受影响测试交检查点，报告实际修改及结果。文档只协调本 Task 的呈现变化：
   原“Files 保留记录列表”的现行说明改为“Files 发起、任务中心返回同一准备”；
   不改 Slice52 的历史合同／接受身份、Roadmap 或 Progress。

测试等级保持 **T3**：本轮修正增加详情只读投影及既有路由入口，执行与权限规则不变。
风险集中在读取与导航整合，按该实际范围验收。

## Required Tests

测试责任依 [workflow §6](docs/development-workflow.md#6-test-levels)。Web 命令均在 `web/` 运行。

**Developer — affected tests**

```sh
npm run test -- run src/features/library/StorageFilesPage.test.tsx src/features/library/MediaLibraryFilesPage.test.tsx src/features/library/LibraryFileOperationsDialog.test.tsx
npm run test -- run src/entities/operations/run.test.ts src/features/operations/OperationsInventory.test.tsx src/features/operations/OrganizeCreationPage.test.tsx
npm run typecheck
npm run build
npm run test:e2e -- tests/e2e/files-read-handoff.spec.ts
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts --grep "initial manual preparation remains reachable from Task Center"
```

在现有 `operations-inventory.python.spec.ts` 添加上面标题的原生场景；复用现有
Files 选择、注册 Worker 和推进分析／执行的夹具，不构造不存在的用户入口。
后端在 `tests/test_operations_task_center.py` 加入对应 Task 到准备的读取断言，并运行：

```sh
.venv/bin/python -m unittest discover -s tests -p test_operations_task_center.py
.venv/bin/ruff check mediaflow/interfaces/service_api.py tests/test_operations_task_center.py
.venv/bin/ruff format --check mediaflow/interfaces/service_api.py tests/test_operations_task_center.py
```

覆盖准确关联／无关联、原读取权限及读取不准入；前端覆盖链接、刷新／认证续转、
返回同一准备、明确确认一次及确认后独立结果。

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
npm run test -- run src/entities/operations/run.test.ts src/features/operations/OperationsInventory.test.tsx src/features/operations/OrganizeCreationPage.test.tsx
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/live-files.python.spec.ts tests/e2e/organize-source-history.python.spec.ts
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts --grep "initial manual preparation remains reachable from Task Center"
```

覆盖两库目录接入、普通操作入口、真实 Python live list 的只读／错误恢复及整理摘要确认。
B 补验文件页受理后离开、任务中心找到同一任务并确认摘要、刷新／重认证返回，
以及响应丢失后准确核对与核对失败指引；新增断言复用现有本地夹具。
逐阶段检查桌面／窄屏画面和实际操作，原始结果保存到
`.git/validation-evidence/<candidate>/patch-20261109-1/`。
B 另执行上面的后端 Task Center 模块测试。T3 验收范围为文件页呈现、记录入口退出、
Task 到既有准备的只读接续及直接依赖。

## Non-goals

不恢复文件页记录列表；不新增任务中心创建入口、摘要产品或恢复类型。
保留后端记录查询 API、任务数据、历史及现有执行／权限／Active／schema／Storage／引擎。
允许修改现有详情读取和任务中心导航以满足 AC-3；共享动画门限及其他页面业务保持。
Slice52、Roadmap、Progress 和既有接受身份保持。

## Developer Completion Report

```text
Implementation commit: 9f6f2f301d4908e02750055366d8c24759772807
Base:                  45674526b04d3366f533b86e864b3c8d179736ed
Branch:                main
Role exception:        用户直接授权 Developer 实施 B 的已提交草案并完成 FIX REQUIRED 修正；未自签 PASS
```

### Changed files

- `mediaflow/interfaces/service_api.py`：`_operations_run_overview` 新增
  `_operations_run_files_preparation`，只使用 `get_media_discovery_for_task(task_id)` 读取
  该 Task 自己持久关联的准备，并校验 `discovery.organize_task_id == task_id`；详情响应新增
  小型 `filesPreparation`（`discoveryId/resourceLibraryId`）。无关联、非该 Task 的准备或
  无 Task 身份时为 `null`，不从文件名、最近记录、当前 Active 或浏览器记忆推算；
  列表逐项读取不含该字段。
- `tests/test_operations_task_center.py`：新增准确关联、兄弟 Task 不借用、无关联为空、
  列表不投影准备、普通 READ 可读及无身份读取 401 的断言；读取不新增 discovery。
- `web/src/entities/operations/run.ts`：接入 fail-closed 的 `filesPreparation` 归一化；
  无 Task 身份却出现关联视为矛盾，畸形字段使整份详情读取失败而不是渲染近似链接。
- `web/src/features/operations/OperationsLanding.tsx`：`RunDetailPanel`／`RunDetailFacts`
  使用 Router 已注册的准备路由显示“继续整理”链接，携带当前运行、列表与详情状态的
  `returnOps` 上下文；打开链接只读取原准备，不重发提交。
- `web/src/features/operations/OperationsInventory.test.tsx`、`web/src/entities/operations/run.test.ts`：
  覆盖真实链接、准备身份、刷新式重新读取、返回同一准备上下文与畸形／无关联拒绝。
- `web/src/shared/ui/styles.css`：仅新增该准备事实块的本地可读样式。
- `web/tests/e2e/operations-inventory.python.spec.ts`：新增原生场景
  “initial manual preparation remains reachable from Task Center”：真实 Files 选择、
  真实 discovery Worker 生成摘要、不确认即离开到任务中心、打开同一运行、刷新／重认证后
  仍见“继续整理”，返回同一摘要明确确认一次，真实 manual Worker 完成并核对源文件移动；
  再次从该入口查看已受理执行，全程无重复 POST。
- `docs/product-experience.md`、`docs/v2-requirements.md`：仅协调“Files 发起、任务中心
  返回同一准备”的现行呈现，不改 Slice52 合同、Roadmap、Progress 或既有接受身份。

### Actual results

| 命令 | 实际结果 |
|---|---|
| `.venv/bin/python -m unittest discover -s tests -p test_operations_task_center.py` | 26 passed |
| `.venv/bin/ruff check mediaflow/interfaces/service_api.py tests/test_operations_task_center.py` | PASS |
| `.venv/bin/ruff format --check mediaflow/interfaces/service_api.py tests/test_operations_task_center.py` | PASS |
| `npm run test -- run src/features/library/StorageFilesPage.test.tsx src/features/library/MediaLibraryFilesPage.test.tsx src/features/library/LibraryFileOperationsDialog.test.tsx`（cwd `web/`） | 3 files, 90 passed |
| `npm run test -- run src/entities/operations/run.test.ts src/features/operations/OperationsInventory.test.tsx src/features/operations/OrganizeCreationPage.test.tsx`（cwd `web/`） | 3 files, 85 passed |
| `npm run typecheck`（cwd `web/`） | PASS |
| `npm run build`（cwd `web/`） | PASS；保留现有大 chunk 提示 |
| `npm run test:e2e -- tests/e2e/files-read-handoff.spec.ts`（cwd `web/`） | 4 passed |
| `npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts --grep "initial manual preparation remains reachable from Task Center"`（cwd `web/`） | 1 passed，8.3s |
| `npx eslint <changed web paths>` | PASS |
| `npx prettier --check <changed web paths>` | PASS |
| `python3 scripts/check_governance.py` | PASS |
| `git diff --check` | PASS |

首轮把两条 Playwright 套件放在同一 `test-results` 目录并行执行，trace 文件复制冲突导致
原生场景报 ENOENT；单独重跑同一最终源码／构建后 1 passed。该失败是测试运行器产物竞争，
不是产品失败，未删除断言、加跳过或放宽等待。

### Remaining risks

- 新入口按持久 `organize_task_id` 精确关联；若该 discovery 行损坏，读取该运行详情会按
  既有 fail-closed 读取语义失败，而不是显示猜测链接。
- Developer 只执行 T3 受影响范围，未跑全量 Python／Web／全套浏览器矩阵；T3 验收与
  其他 Slice 回归由 B 在最终候选执行。
- 原生场景使用一个未确认的 Files 准备；已确认后的返回由同一入口展示原准备的已受理
  执行，本轮已在完成 Worker 后核对，但不新增摘要或恢复机制。
- 现有未知提交核对由 `StorageFilesPage.test.tsx` 的既有准确 `requestId` 用例覆盖并
  随上述 90 passed 重跑；导航、刷新和重新连接均为只读。

下方 `B Review Result` 保留上一轮 FIX REQUIRED 的原始决定，供 B 本轮复核对照。

## B Review Result

```text
Reviewed Base: 45674526b04d3366f533b86e864b3c8d179736ed
Reviewed Head: a3094876dd98cdd6b1d5601155da6fa0b0e426da
Implementation: cc6ffbb1496685d440e731421c0f45ee44953995
Decision: FIX REQUIRED
Blocker: AC-3 — 离开初次准备后无法从任务中心返回同一摘要确认
Authorized bug acceptance complete: NO
Next: SAME TASK FIX LOOP
```

B 独立审查完整 Base..Head 的全部 5 个变更文件，包括产品删除、共享查询消费者、
全部新增／修改测试和 Task 说明；实现后至 Reviewed Head 只有 Task 报告变化。
代码删除及目录接入符合本次呈现目标，准确 requestId 核对调用仍保留。

**实际用户复现：** 使用生产 Web 构建和现有真实 Python/API/SQLite/Worker 本地夹具，
从 Files 选择 `Two.2002.mkv`，产生计划摘要及“确认整理 1 项”；不确认，经侧栏进入任务中心，
打开该文件的手动整理任务。详情显示“等待确认”，只有取消／导出／查看证据，
无返回准备的链接；证据显示“此文件没有待处理操作”，确认按钮为 0。
该次任务中心读取／导航的产品 POST 为 0。`Three.2003.mkv` 的独立初次准备亦保持未确认。

根因是原记录列表包含准确 `discoveryId` 链接，而普通初次 WaitingConfirm 不属于
`_files_native_summary` 发布的四类恢复摘要。删除链接后没有等价入口。
这是既有 AC-3 的实现缺口，按本次指导修正，不恢复原列表、不新建 Task。

| B 本轮验证 | 实际结果 |
|---|---|
| `python3 scripts/check_governance.py`（根目录） | PASS |
| `git diff --check 45674526..a3094876`、工作区 `git diff --check` | PASS |
| `npm run build`（web） | PASS；现有大 chunk 提示保留 |
| `npm run test:e2e -- tests/e2e/files-read-handoff.spec.ts`（web） | 4 passed，3.3s |
| 真实 Files → 原准备摘要 → 侧栏任务中心 → 原任务详情／证据 | 复现 AC-3 不满足 |
| 1536×1024／390×844 文件页实图 | 已检查，库上下文后为目录，无整理记录区 |

先确认阻塞，依 workflow §6 提前返回 FIX REQUIRED；其余 B 静态／组件／集成验收待修正候选，
未宣称全部 AC 通过。上方勾选为 Developer 的交付报告，不替代 B 最终验收。
本轮测试及浏览器验证用时少于总用时的 50%。
原始截图、请求台账、复现脚本和 `center-result.log` 在本机
`.git/validation-evidence/a3094876dd98cdd6b1d5601155da6fa0b0e426da/patch-20261109-1/`；
仅本机可达，不含用户运行数据。现有 Python harness 已停止。

起点为 main / Reviewed Head，Git 与工作区可写；预存 `mediaflow/.DS_Store` 变更，
未跟踪 `.DS_Store`、`.explore_adapter_block.py`、`.mgmt.log`、`.t*.log`、`15`、
`docs/`、`output/`、`testdata/`、`web/` 下原有材料保持，不纳入本次文档检查点。
本轮仅修改本 Task；Slice52 已关闭，不重开、不替 A 再终审，也不规划下一项。
