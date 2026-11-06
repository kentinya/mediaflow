# Task50.2 — 任务详情弹卡与可读性

Authority：已提交 `575898ebaae593568be59699bb40116f9e6f2d91:SLICE.md` 的 RO-1、
AC-1/2、适用 AC-10/11；遵循 [Development Workflow](docs/development-workflow.md) 与
[Task 模板](Task/TEMPLATE.md)。用户于 2026-11-06 明确授权激活 Task50.2，作为当前唯一
活动实施 Task，状态 PLANNED，等待 Developer 实施。本轮仅激活，不启动开发、推送或部署。

激活前现场：分支 `main`，HEAD `5b5f319b1d77b9673a447bf60c5d7a21fcbcc956`；治理预检 PASS，
仓库与 Git 可写。Task Base 保持原值，纯文档提交不重设它。预存 `mediaflow/.DS_Store` 修改
及未跟踪 `.DS_Store`、日志、`15`、`output/` 等均保留，不纳入 checkpoint。

```text
Task ID: 50.2
Task Type: SLICE
Parent Slice: 50
Status: PLANNED
Activation: USER AUTHORIZED — 2026-11-06
Task Base: 575898ebaae593568be59699bb40116f9e6f2d91
Difficulty: High
Test Level: T4
Planner / Reviewer: B
```

## 已接受前序与 Slice 结果

Task50.1 保持 **PASS**，B 已审完整范围
`f24dce7a0a97e035078879e2a93855de02d74f54..8573445f13a3f67cc434a576ee87e1d048d8362a`。
其完整计划/交接见 `8573445f:TASK.md`；B 实际门禁、证据、限制与时间偏差见
`575898ebaae593568be59699bb40116f9e6f2d91:TASK.md`，接受事实不变。

| Slice Required Outcome | 当前结果 |
|---|---|
| RO-1 任务详情卡片/可读性 | 未交付，由当前 Task50.2 实施。 |
| RO-2 存储三卡片/更多菜单 | Task50.1 已验收。 |
| RO-3 两种库去树/菜单/配置卡片 | 未交付，待后续规划。 |
| RO-4 自动化新建/编辑稳定性补充 | Task50.1 已验收。 |
| RO-4 侧栏主页面切换/两种库加载 | 未交付，待后续规划。 |

Slice50 保持 ACTIVE；本轮不提交 Closure Packet，不宣告 Slice PASS / CLOSED。

## Goal 与完整用户旅程

落实 `V2-UX-005/006`：在任务中心点击名称，以保持原列表宽度和上下文的居中详情卡读懂
“哪个任务、流程到哪一步、文件实际如何、有什么需要处理”，并完成已有允许的操作。

- **入口：** 八个现有视图的任务名称、原精确任务链接、刷新和认证续转到达同一任务。
- **可见状态：** 优先让用户读懂任务身份、五态流程、阶段/等待、进度、独立文件/附件
  结果和当前业务问题；来源/目标、条目、记录、诊断分层可查。具体排列、分组和标签按
  内容设计。读取中有协调卡片，不闪假成功。
- **动作：** 已有控制、四类决定→分析→精确摘要→明确继续，以及计划、日志/审计、记录、
  JSON 导出仍可达；只使用后端已经允许的动作。
- **成功/退出：** 能读懂“流程已完成；部分文件失败”；关闭/返回恢复原合法视图、日期、
  页、问题文件定位、滚动和入口焦点。开关卡片不执行或取消工作。
- **失败/恢复：** 缺失、拒绝、读取失败、流程失败、未知效果/无 Result 如实显示，保留
  原有合法下一步。允许的退出/重开不丢原请求核对；技术终结失败保持事实查看。

完整依据：[TARGET 任务详情旅程](docs/product-experience.md#target--v2-dialog-readability-and-navigation-experience-slice50-active)、
[CURRENT Tasks/results/recovery](docs/product-experience.md#tasks-results-and-per-item-recovery)、
[任务中心规范](docs/task-center-page-spec.md)、
[Architecture TARGET](docs/architecture.md#target--v2-dialog-readability-and-navigation-experience-slice50-active)。
沿用 `UX-001–010`、`REQ-TASK-*`/`REQ-RESULT-*`/`REQ-RECOVERY-*` 的现行 V2 修订、
`REQ-WEB-004/005`、`REQ-SAFE-001–009`、`V2-OPS-014/016`、`V2-TASK-012–014`。

## 真实代码与范围

- `OperationsLanding.tsx`：`RunTable → selectRun → ?run= → RunDetailPanel` 是名称点击
  链路；`listSearch`/`applyDetailState`/`closeRun` 管列表、详情和问题定位返回。
- `shared/ui/styles.css`：`.mf-run-layout.mf-run-has-detail` 按约 34% 分配侧详情，并
  配套缩窄列表；窄屏详情占满视口。替换目标布局，按实际使用者保留其他布局。
- `RunDetailTabs.tsx` 已有进度、文件/附件、条目证据、记录、导出和同页摘要；
  `RunDetailFacts` 将业务内容与 Worker/固定配置等技术信息并列，需重排信息层级。
- `shared/ui/modal-card.tsx` 的 `ModalCardShell`、`useModalLayer`、`useModalCardExit`
  已提供无业务依赖的居中外壳、进出、滚动占位、inert、键盘/焦点能力。
- `routes/router.tsx`、`run-detail-state.ts`、`shared/navigation/operations-return.ts`
  已有精确链接和返回状态；`operations.spec.ts` 明确断言旧“桌面右列/窄屏全屏”几何。

范围是该完整详情旅程的 Web 呈现、必要导航/状态生命周期适配及测试。复用现有 typed API、
Query 与 Task/结果/恢复行为，不改变 API/application/runtime/schema、八视图总体和日期语义。

## 开发指导

1. 从上述真实入口梳理列表/详情 URL、问题文件返回、控制与恢复请求的状态归属，确认哪些
   状态须跨卡片退出保留。沿用既有业务语义，允许必要的组件与状态归属调整；未决请求
   的身份和核对上下文须保留。
2. 为选中任务实现协调的居中卡片，列表保持完整宽度，背景约束正确。优先复用现有共享
   外壳、锁滚动/占位、焦点和退出能力，允许按详情内容作必要适配，以可见交互和业务语义
   验收。处理首个聚焦点，避免旧 Escape/回焦与外壳重复响应。
   详情导航采用已有局部保滚动做法；深链没有原入口时给合法列表返回和焦点落点。
3. 让用户优先读懂任务、流程、文件效果和待处理项；具体排列、分组、标签及折叠方式由
   开发按内容设计。技术 ID、Worker、固定配置等诊断保持可查，失败阶段/未知效果/
   待处理项保持明显。历史名称、状态和计数使用已有任务证据。长路径和多列表格有界
   滚动/换行，关闭与必要操作在窄屏/键盘下可达。保留既有用户可见业务信息和必要证据
   的可达性，允许合并重复展示、折叠诊断，不要求展示所有内部字段。
4. 接入既有条目/记录过滤分页、单项证据、导出、控制、四类恢复和精确摘要。
   用真实在途/未知响应后的关闭、返回、重开验证核对保留；仅在实际链路需要时调整状态
   生命周期，不增加通用命令框架，不把展示重排变成新的执行入口。
5. 慢读取、拒绝/缺失/失败使用协调卡片；正文接入和退出平顺，reduced-motion 可用。
   关闭后晚到响应不重开旧任务，快速换任务不串结果，同条件刷新保留可用内容/阅读位置。
   不为动画延时，也不以重发业务命令更新界面。
6. 更新旧几何断言及受影响说明，完成下面 Developer 测试后交接一个完整 checkpoint。
   共享外壳如有修改，补直接受影响的存储/自动化回归；不顺带清理旧不可达恢复代码或
   重做其他中心业务。完整验收由 B 负责。

## Acceptance Criteria

- [ ] **卡片/返回（AC-1）：** 八视图真实名称点击打开协调居中卡片，原列表不挤窄。
  关闭、Escape、遮罩、浏览器返回遵循合法退出规则；视图/日期/页/问题定位/滚动/焦点
  保留。精确链接、刷新/认证续转到达正确任务，缺少原入口时可回合法列表。
- [ ] **可读性（AC-2）：** 流程、阶段/等待、处理进度与独立文件/附件效果层级清楚。
  混合结果、completed+技术失败/未知/无 Result、failed、cancelled、等待确认不互相冒充；
  未知总数不造百分比，恢复成功仍要求既有精确证据。按用户能否读懂和完成操作验收，
  允许不同排列、分组和标签设计，以及合并重复展示、折叠诊断；既有用户可见业务信息
  和必要证据保持可达。
- [ ] **证据/操作（AC-2/10）：** 来源/目标、结果、计划解释、日志/审计、记录/过滤/分页、
  导出和合法控制可达；四类处理完成原同一 Task 旅程。技术终结失败保持事实查看，成功
  兄弟项/未知效果不重放。纯查看/导航/刷新不发执行、取消或决定请求。
- [ ] **核对/并发（AC-10）：** 显式提交保持原权限、意图、身份及 pins/fences；允许的
  退出/重开仍核对原请求，不能变成再次提交。换任务不串选择、权限、核对或结果。
- [ ] **加载/失败：** 读取中到正文稳定，缺失/拒绝/读失败可辨且保留原合法下一步；
  晚到读取不重开旧卡，快速换任务只显示当前任务，同条件刷新不清空可用内容。
- [ ] **可见交互（AC-11）：** 1536×1024 / 390px 长名称、路径、多文件和证据可读，内部
  有界滚动，关闭/必要操作不遮挡，焦点留在卡内并正确返回；背景宽度/滚动稳定，进出与
  自动化/存储协调，reduced-motion 可用。截图与动态操作共同验收。
- [ ] B 完成适用完整 T4 与真实入口验收后才 PASS。共享呈现若受影响，存储/自动化已接受
  旅程保持；RBAC、显式破坏性意图、独立结果、核对和成功/未知效果非重放保持。

## Required Tests

遵循 [workflow §6](docs/development-workflow.md#6-test-levels)。使用既有隔离 harness、临时
SQLite/Local 根及合成 Provider；从真实 UI/已实现链路进入，只对该链路实际请求注入慢响应/
失败，不构造不存在的入口。场景按风险组合覆盖，不要求全排列。

每轮记录实际工作和测试时间，测试运行墙钟时间须少于本轮实际工作时间的 50%；并行运行
计区间并集。先完成实际代码/旅程审查和用例选择，不靠空等凑比例、不把 B 全回归交给
Developer。可证实阻塞先 FIX REQUIRED；必需门禁未完成不得 PASS。

### Developer — affected tests

在 `web/` 运行：

```sh
npm run test -- run src/features/operations/OperationsInventory.test.tsx src/features/operations/RunDetailTabs.test.tsx src/features/operations/TaskItemRecoveryPanel.test.tsx src/features/operations/RunLifecycleControls.test.tsx src/features/operations/run-detail-state.test.ts src/shared/navigation/operations-return.test.ts src/features/operations/OperationsRouter.test.tsx
npm run typecheck
npm run build
npm run test:e2e -- tests/e2e/operations.spec.ts tests/e2e/task-center-layout.spec.ts
npm run test:e2e -- --config=playwright.python.config.ts --workers=1 tests/e2e/operations-inventory.python.spec.ts --grep 'the selected run detail reads|detail tab and filter context|dated views and 21-file|native .*recovery|native Metadata correction|policy-permitted overwrite'
```

覆盖布局/返回、状态与文件结果、证据/导出及真实四类恢复；将新增慢读取、焦点/退出、未知
提交重开用例纳入受影响测试执行。替换旧几何断言，保留有效业务断言。对实际变更文件跑
ESLint/Prettier；仅修改下列生产文件时示例为：

```sh
npx eslint src/features/operations/OperationsLanding.tsx src/features/operations/RunDetailTabs.tsx
npx prettier --check src/features/operations/OperationsLanding.tsx src/features/operations/RunDetailTabs.tsx src/shared/ui/styles.css
```

新增/修改的测试和其他文件同样加入检查。如修改共享 modal，另跑
`npm run test -- run src/shared/ui/modal-card.test.tsx src/features/storage/StorageManagementPage.test.tsx src/features/operations/AutomationCreateDialog.test.tsx`
及 `storage-dialog.python.spec.ts` / `automation-create-dialog.python.spec.ts` 的直接受影响用例。
Developer 不承担完整 Python/Web/E2E 或发布矩阵。

### B — acceptance / full regression

1. 独立审查完整 Task Base..候选 Head，先从真实名称/原精确链接验证关键旅程，含关闭返回、
   五态/文件结果、四类处理、在途/未知后重开。实际阻塞留在同一 Task 修复。
2. 运行 [shared full gates](docs/development-workflow.md#shared-full-regression-commands)
   的适用完整 T4：Python/Web 全回归/质量、构建、示例、依赖、wheel/源码外消费及适用
   安全用例。Docker/重启矩阵按实际修改和部署合同选择并说明理由/限制；纯前端呈现不
   自动增加生产部署验收。不得用缺少 Developer 全回归作为产品阻塞。
3. `web/` 构建后运行真实 Python 浏览器：

   ```sh
   npm run test:e2e -- --config=playwright.python.config.ts --workers=1 tests/e2e/operations-inventory.python.spec.ts tests/e2e/operations-task-center-visual.python.spec.ts
   ```

   在既有真实 harness 补齐桌面/390px 新详情截图和动态交互，人工检查信息层级、长内容、
   加载/失败、键盘/焦点、reduced-motion；旧八视图截图不能代替新详情验收。
4. 记录精确 SHA、命令/cwd、实际结果/失败/skip、原始日志及视觉证据，放稳定 ignored
   目录或 CI。仅复用自己的匹配执行输入/产物并给出差异证明。
5. PASS 后重评所有 Slice 结果：本 Task 只覆盖 RO-1；RO-2 和自动化稳定性仍已接受，RO-3
   与 RO-4 切页/库加载仍待交付。不自动规划/实施下一 Task，不提前交 A 终审。

## Non-goals

两种库去树/配置卡片、侧栏主页面切换和库加载另行规划。不新增 Task 状态/恢复、通用重试、
跨 Task 批量操作、引擎/队列/后端/schema、Provider、动画设置或生产部署；不重做其他列表
业务。不以固定像素/毫秒/DOM 结构作为唯一验收，不把可选清理变成阻塞。

## Developer Completion Report

状态：**READY FOR B REVIEW**（Task50.2 实现完成，Developer 交接，未自审 PASS）。

```text
实现 checkpoint: 本报告所在提交（单个实现 checkpoint）
分支: main
Task Base: 575898ebaae593568be59699bb40116f9e6f2d91
B 审查范围: Task Base..本报告提交 HEAD
本轮工作/测试时间: 全轮约 78 分钟；测试运行墙钟合计约 11 分钟（约 14%，并行取区间并集）
```

工作区预存的 `mediaflow/.DS_Store` 修改及未跟踪 `.DS_Store`、日志、`15`、`output/`
等均保持原样，未纳入本次 checkpoint。共享 `modal-card.tsx` 未修改，故未触发存储/
自动化共享外壳附加回归（按 Task 要求免跑）。

### 关键变化

- **居中详情卡（AC-1）：** `RunDetailPanel` 由列表旁 34% 右列改为复用
  `ModalCardShell`+`useModalLayer`+`useModalCardExit` 的居中卡片（`accessibleName="运行详情"`，
  `cardClassName="mf-run-detail-card"` 宽 min(1080px,100%)，`mf-modal-body-scroll` 有界正文滚动）。
  列表保持完整宽度：`mf-run-has-detail` 布局仅保留给问题文件面板
  （`ProblemFilePanel` 类名改为 `mf-problem-panel`，原桌面 sticky/窄屏全屏 CSS 重命名后原样保留）。
  关闭按钮/遮罩/外沿/Escape 走共享退出（160ms，reduced-motion 立即），退出后 `closeRun`
  替换 URL 并作废 overview 缓存；打开时焦点落关闭按钮（与存储卡一致），关闭回焦触发行按钮，
  深链无原入口时回焦页面标题 `mf-operations-heading`；浏览器返回照旧直接丢弃选择。
  旧面板自有 Escape 监听/回焦 effect 已移除，与外壳不重复响应。
- **信息层级（AC-2）：** 卡片标题=业务名称（sourceScope，缺失时回退操作名），描述=操作说明；
  正文顺序为运行控制→剩余范围→选项卡→`状态与流程`（状态+诚实注记、当前阶段、当前业务问题，
  新区块）→两列事实表（触发方式/目标范围/时间/条目/更详细证据）→折叠的`技术诊断`（Worker/
  固定配置）→进度→条目表（`RunDetailTabs` 中 facts 移到进度之前）。删除与标题重复的
  业务名称/范围行；其余既有业务信息与证据保持可达。
- **核对保留（AC-10）：** 生命周期控制与剩余范围确认的会话状态提升到 landing 按 runId 存储
  （`RunControlSession`/`RunRemainingSession`）：未知控制结果锁、提交结果、未决确认身份、
  已受理执行标识、已选子集与破坏性选择在卡片关闭/重开后保留，仍核对原请求而非重发；
  提交改用 `mutateAsync`+显式会话写入，卡片在请求在途时关闭也不丢结果。换任务按 runId 隔离。
- **测试同步：** 旧“桌面右列/窄屏全屏”几何断言替换为居中卡+列表宽度断言；全部 68 处
  `region 运行详情` 查询改为 `dialog 运行详情`（含 task-flow/manual-organize 等直接受影响 spec）。

### 实际执行结果（cwd、命令、结果）

- 仓库根：`python3 scripts/check_governance.py` → PASS（实施前与提交前各一次）；
  `git diff --check` → 无输出。
- `web/`：`npm run typecheck` → PASS；`npm run lint` → PASS；`npm run format:check` → PASS；
  `npm run build` → PASS（仅既存 chunk >500 kB 提示）。
- `web/` 指定受影响单元/组件（7 文件 79 用例）：`npm run test -- run src/features/operations/
  OperationsInventory.test.tsx src/features/operations/RunDetailTabs.test.tsx
  src/features/operations/TaskItemRecoveryPanel.test.tsx src/features/operations/
  RunLifecycleControls.test.tsx src/features/operations/run-detail-state.test.ts
  src/shared/navigation/operations-return.test.ts src/features/operations/OperationsRouter.test.tsx`
  → 79 passed。含新增 4 用例：慢读取协调卡、关闭后迟到响应不重开、未知控制结果跨关闭/重开
  锁定且不重发（仅 1 次 POST）、换任务后旧任务结果不串。
- `web/` 全量单元套件（B 回归前的额外 sanity，非替代 B 全回归）：`npm run test -- run`
  → 94 文件 1356 用例全部通过。
- `web/` Node E2E（构建产物+fake API）：`npm run test:e2e -- tests/e2e/operations.spec.ts`
  → 25 passed（含新居中卡几何用例）；`tests/e2e/task-center-layout.spec.ts` → 11 passed；
  `tests/e2e/manual-organize.spec.ts`、`dashboard.spec.ts`、`deep-link.spec.ts` → 全部通过。
- `web/` 真实 Python 栈 E2E（`playwright.python.config.ts --workers=1`）：指定 grep 子集
  （detail reads/filter context/21-file/native 四类恢复/Metadata correction/overwrite）
  → 9 passed；`operations-task-center-visual.python.spec.ts` → 2 passed；
  `task-flow.python.spec.ts` 抽取 2 用例（已确认取消、保存后失败含 390px 断言）→ 2 passed。
- 视觉抽查：fake API+构建产物下 1536×1024 与 390×844 卡片截图人工检查——居中、宽度、
  状态条、两列事实、折叠诊断、窄屏可读均符合；产物仅为本地 /tmp 截图，未存为验收证据。

### 已知失败

无。首轮 Node E2E 曾因 dist 未重建而 13 failed（旧构建产物），重建后全部通过，非产品缺陷。

### 剩余风险与留给 B 的验收点

- `task-flow.python.spec.ts` 3 个用例中仅实跑 2 个（选择器已全部同步为 dialog）；
  `operations-inventory.python.spec.ts` 其余用例与全量 Web/Python 回归按分工归 B。
- 打开卡片时背景 inert：卡片开着时侧栏/列表不可点（与自动化/存储卡一致）；
  `task-center-layout` 的侧栏 Files 用例已改为先 Escape 关卡再导航。
- 卡片打开时首焦点为关闭按钮（存储卡同款）；信息排列为开发者按内容设计，
  满足 AC-2 的“用户能读懂”验收需 B 以真实截图/交互判定。
- 剩余范围确认会话仅在 landing 生命周期内保留（页面刷新丢失，刷新后以服务器持久
  continuation 证据为准）；与既有重挂载语义一致，未跨页持久化。

## B Review Result

Task50.2 已激活、尚未实施，无实现候选，待 Developer 交接后由 B 独立验收。后续须记录完整
Base..Head、实际门禁、阻塞及其用户影响、全部 Slice 结果和下一步。
