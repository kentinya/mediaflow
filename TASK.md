# Task50.2 — 任务详情弹卡与可读性

Authority：已提交 `575898ebaae593568be59699bb40116f9e6f2d91:SLICE.md` 的 RO-1、
AC-1/2、适用 AC-10/11；遵循 [Development Workflow](docs/development-workflow.md) 与
[Task 模板](Task/TEMPLATE.md)。用户于 2026-11-06 明确授权激活 Task50.2，作为当前唯一
活动实施 Task。B 已复核修复候选：原滚动及决定在途重开复现通过；确认成功的迟到响应仍会强制离开已返回列表，结论继续 FIX REQUIRED。

激活前现场：分支 `main`，HEAD `5b5f319b1d77b9673a447bf60c5d7a21fcbcc956`；治理预检 PASS，
仓库与 Git 可写。Task Base 保持原值，纯文档提交不重设它。预存 `mediaflow/.DS_Store` 修改
及未跟踪 `.DS_Store`、日志、`15`、`output/` 等均保留，不纳入 checkpoint。

```text
Task ID: 50.2
Task Type: SLICE
Parent Slice: 50
Status: FIX REQUIRED
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
| RO-1 任务详情卡片/可读性 | 原两项复现已修复；原生确认迟到成功后仍强制跳转，Task50.2 未验收。 |
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

### B — acceptance and full regression

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

**FIX REQUIRED — 2026-11-06，B 独立审查。**

- Task Base：`575898ebaae593568be59699bb40116f9e6f2d91`（保持不变）。
- 候选 Head：`46be457f5d415efdea4fe7090774d3146f58253c`。
- 现场：分支 `main`，工作区/Git 可写；预存 `.DS_Store`、日志、`15`、`output/` 等
  未触碰、未暂存。本轮只更新 `TASK.md`，没有产品实现或推送。
- 审查完整 Base..Head 的 15 个文件：规划/激活文档、全部生产改动、组件测试和 E2E 改动，
  并追踪共享外壳、Router、条目恢复及真实 Python harness 消费链路。未将 Developer 的
  测试报告当作 B 的独立验收。
- 已实现居中卡片、列表不再因详情挤窄、状态/事实/诊断分层及取消控制会话保留；以下两个
  必需结果仍不满足，均为 P1，留在 Task50.2 修复。未发现或声称媒体已重复执行。

### B50.2-01 — 打开详情后返回丢失原列表位置

**用户旅程：** 在 390px 窄屏的任务中心向下浏览，点击任务名称，查看详情再关闭。
预期继续阅读原来的行；候选打开时背景已回到页顶，关闭后仍在页顶，需重新寻找任务。

B 从现有 UI 名称按钮操作，未增加入口或修改页面高度：

- fake API 的真实 `Movies，手动整理详情` 行：打开前 `scrollY=461`，打开后/关闭后均为 `0`。
- 真实 Python/SQLite harness 的列表行：打开前 `scrollY=329`，打开后/关闭后均为 `0`。
- reduced-motion 下同样发生；入口焦点虽已返回，所在列表位置未恢复。

**开发指导与修复验收：**

1. 在 `OperationsLanding.tsx` 的真实详情打开、关闭及同卡片内 URL 状态切换链路，采用已有
   局部保滚动导航方式。连同问题文件打开证据/关闭返回检查，保留其真实列表/分页上下文。
   普通跨主页面导航维持原语义，不能全局关滚动重置或先回顶再滚回。
2. 从已滚动列表实际点击任务名，检查首帧/读取/正文/关闭/Escape/浏览器返回；增加桌面和
   390px 回归，验证原列表可见位置、日期/页及焦点。断言用户仍能接着阅读原行，不以停稳
   后卡片居中或单一 CSS 断言替代。精确链接/认证续转的合法返回保持。

### B50.2-02 — 原生条目决定在途时，关闭重开又允许保存

**用户旅程：** 任务中心 → 识别恢复 → 查看问题文件 → 查看该文件证据与恢复记录 → 选择
Special → 保存决策并继续安全分析。网络仍在等待时关闭卡片，再从原问题文件入口重开，
重新选择 Special。原请求仍未返回，候选却重新开放保存；没有原请求的在途/核对提示。

B 使用现有 `seed-task-item-recovery?kind=recognition` 隔离数据及真实 Python API/SQLite，
仅延迟浏览器实际发出的 `/recovery/decision` 请求：已发 POST 1 次、仍在途，重开后
`saveEnabled=true`、核对入口数 `0`。没有点击第二次保存，也没有调用执行器或用户媒体。

**开发指导与修复验收：**

1. 沿 `RunDetailTabs → 条目证据 → TaskItemRecoveryPanel` 修复真实四类处理会话生命周期。
   当前 landing 提升的是取消控制与旧剩余范围会话，不能据此认定原生条目决定/继续/确认
   已覆盖。让实际在途请求及未决核对信息跨允许的关闭/重开保留，绑定当前主体及精确
   Task/条目/请求或准备身份；换任务、换条目不混用。
2. 同一请求未结束时重开保持等待；结果未知时保留原核对入口，成功/明确拒绝则展示其实际
   结果。迟到响应不能把用户带回已关闭的旧卡片或丢失结果。复用现有持久读回与原权限/
   checkpoint/pin，不新建通用命令框架，不增加自动重试或重放。
3. 在原生入口添加“在途关闭重开”及“未知结果关闭重开后核对”的回归，覆盖决定与精确
   摘要确认的实际状态归属，并组合验证切换条目/任务隔离。保持原 POST 次数，明确核对后
   才能按实际结果决定后续；成功兄弟与未知效果不重放。按现有四类共享实现选择必要代表
   场景，不要求无意义的全排列，不探测退役 Pause/剩余范围入口。

### 本轮验证与证据

稳定本地证据：`.git/validation-evidence/46be457f/B50.2-review/`（ignored，本地可取，
不宣称远程可取）。含三个探测脚本、实际日志、原生窄屏前/开/关截图及桌面条目重开截图；
B 已打开检查原生截图。它们证明上述阻塞，**不是完整视觉验收或 T4 PASS**。

| cwd / 命令 | B 实际结果 |
|---|---|
| 根目录 `python3 scripts/check_governance.py` | 复核前与文档更新后均 PASS。 |
| `web/` `npm run build` | PASS，既存大 chunk 提示保留；核对生产 JS/CSS 构建产物。 |
| 根目录 `node .git/validation-evidence/46be457f/B50.2-review/detail-probe.mjs` | 正常入口完成；记录 fake 列表位置丢失。 |
| 根目录 `node .git/validation-evidence/46be457f/B50.2-review/detail-native-probe.mjs` | 正常入口完成；真实 Python 重现列表位置丢失。 |
| 根目录 `node .git/validation-evidence/46be457f/B50.2-review/recovery-probe.mjs` | 正常原生决定入口完成；重开误开放保存，保留 1 次在途 POST。 |
| 根目录 `git diff --check` | 文档更新后 PASS。 |

首次 fake 探测因窄屏侧栏折叠而等待链接超时，随后按现有 E2E 先在桌面进入再转窄屏；首次
条目探测仍查找保存前按钮文案，但提交后实际变为“正在保存…”，发生断言超时，修正选择器
后完成真实旅程，初次日志保留为 `recovery-probe-selector-failure.log`。这两次均是探测脚本
问题，不作为产品阻塞或已通过测试。最终脚本没有增加重试或放宽超时。

时间分配：复核在 `03:47:21 UTC` 已记录现场时间，至 `03:50:39 UTC` 已超过 3 分 18 秒，
此前阅读及后续记录另计；构建及所有成功/失败探测的执行墙钟保守上界 60 秒，低于这一
已可核对工作时段的 31%，故本轮测试时间小于总工作时间的 50%。未空等凑比例。

按 workflow §6，已有真实 P1 阻塞，本轮提前 FIX REQUIRED。完整 T4、完整 Python/Web/E2E、
wheel/源码外消费及最终视觉/安全验收均 **待修复候选由 B 执行**；未豁免、未声称通过，也不
把这些 B 工作转交 Developer。Developer 跑本 Task 原有受影响计划及本轮新增/失败用例后，
提交新的完整修复 checkpoint，不能改写已审提交。

### 全 Slice 结果与下一步

RO-1 仍未满足；RO-2 存储和 RO-4 自动化稳定性保持 Task50.1 的已接受事实；RO-3 两种库
与 RO-4 主页面切换/库加载仍未交付。Slice50 保持 ACTIVE，本轮不另建 Task，不交 Closure
Packet，不进行 A 终审或关闭。下一步为 Developer 在 **同一 Task50.2** 修复上述两项后重新交接。

## Developer Completion Report — B50.2 修复轮

状态：**READY FOR B REVIEW**（两项 B P1 已修复，Developer 交接，未自审 PASS）。

```text
实现 checkpoint: 本报告所在提交（单个修复 checkpoint）
分支: main
Task Base: 575898ebaae593568be59699bb40116f9e6f2d91
B 审查范围: Task Base..本报告提交 HEAD
本轮工作/测试时间: 全轮约 35 分钟；测试运行墙钟合计约 2 分钟（含失败重跑、真实探测和并行命令，低于 30%）
```

工作区预存的 `mediaflow/.DS_Store` 修改及未跟踪 `.DS_Store`、日志、`15`、`output/` 等保持原样，
未暂存、未纳入 checkpoint。共享 `modal-card.tsx`、`AppShell`、存储和自动化生产代码未修改。

### B50.2-01 — 列表滚动位置

- 在 `OperationsLanding.tsx` 的真实打开/关闭链路使用 TanStack Router 已有局部保滚动方式：
  `selectRun`、`closeRun`、`applyDetailState`、`openProblemRun`、`closeProblemRun`、
  `turnProblemPage`、`openProblemItemEvidence` 均传 `resetScroll: false`。详情打开、卡片内
  tab/filter/证据切换、关闭、问题文件打开证据与返回不再把页面导航回顶部；普通筛选、视图
  切换和跨主页面导航保持原 reset 语义。未改共享滚动锁，也没有先回顶再滚回。
- 新增 Node E2E：从已滚动列表实际点击 `Movies，手动整理详情`，在 1536×600 和 390×844
  分别验证打开、关闭按钮/Escape、浏览器 Back 后 `scrollY` 仍为打开前的值、入口行仍在视口
  且焦点回到入口。另新增组件回归：问题文件打开和“返回任务列表”期间不调用重置滚动的
  `window.scrollTo`，URL 保留 `view` 并清除 `problemRun`。
- B 的原始 fake 探测脚本在修复后得到 `before/opened/closed = 461/461/461`；入口焦点仍回到
  原名称按钮。

### B50.2-02 — 原生条目决定在途/未知的重开

- 新增 landing 级 `task-item-recovery-session.tsx`，在可关闭卡片之上按
  `principal + runId + taskId + itemId` 保存每项的请求生命周期：`busy`、`pendingAction`、
  `message`、`repeatLocked`、`submittedPreparationId`。provider 由当前认证 token 作 key，
  换主体即重建；换 Task/条目使用不同 key，迟到结果不会串入其他主体。
- `TaskItemRecoveryPanel` 的决定、忽略、Metadata 搜索、继续分析、生成摘要和精确摘要确认
  统一写入该会话。关闭卡片不会取消实际请求；重开时：
  - 请求仍在途：显示“操作请求仍在进行”和原动作名称，表单、决定与确认按钮禁用；
  - 未知结果：保留原核对入口和锁定，显式核对读回当前持久状态后才解锁；
  - 成功/明确拒绝：显示实际结果；确认未知仍绑定原 `submittedPreparationId` 核对，
    不会把另一份摘要当成原请求。
  - “继续此条目的安全分析”现在也在请求期间置 busy，避免同一条目并发提交。
- 新增组件回归覆盖：原生决定在途关闭/重开保持等待且迟到成功落到重开面板；未知决定
  关闭/重开后保留核对入口并只发 1 次 POST；精确摘要确认在途关闭/重开后保持锁定，未知
  响应后按原 preparation 核对并显示已受理；切换条目不会显示另一条目的未知状态。

### 实际执行结果（cwd、命令、结果）

- 根目录 `python3 scripts/check_governance.py` → PASS（实施前、提交前）；`git diff --check` → 无输出。
- 根目录 `node .git/validation-evidence/46be457f/B50.2-review/detail-probe.mjs` → 正常完成，
  `scrollY` 由修复前的 `461/0/0` 变为 `461/461/461`。
- 根目录真实 Python/SQLite harness 下逐项探测（同 B 的 `seed-task-item-recovery?kind=recognition`
  与原生入口，仅延迟实际 `/recovery/decision`）：在途重开 `saveEnabled=false`、
  `radioEnabled=false`、核对入口 0、POST 1；释放为未知后 `saveEnabled=false`、核对入口 1、
  POST 1；显式核对后显示“已重新读取此 TaskItem 的持久状态”，POST 仍为 1。
- `web/`：`npm run test -- run` 指定 7 个受影响文件 → 83 passed（含新增 4 个用例）。
- `web/`：`npm run typecheck` → PASS；`npm run lint` → PASS；`npm run format:check` → PASS；
  `npm run build` → PASS（仅既存 chunk >500 kB 提示）。
- `web/`：`npm run test:e2e -- tests/e2e/operations.spec.ts tests/e2e/task-center-layout.spec.ts`
  → 37 passed（含新增滚动回归）。
- `web/`：`npm run test:e2e -- --config=playwright.python.config.ts --workers=1
  tests/e2e/operations-inventory.python.spec.ts --grep 'the selected run detail reads|detail tab
  and filter context|dated views and 21-file|native .*recovery|native Metadata correction|
  policy-permitted overwrite'` → 9 passed。

B 的原始 `recovery-probe.mjs` 在修复后停在重开面板的 `Special` radio，因为该控件现在按设计
禁用，脚本未再尝试重选；这不代表产品失败。逐项探测使用同一真实入口与数据，只改为读取
“正在保存…”按钮和核对入口。

### 剩余风险与留给 B 的验收点

- 会话只在任务中心 landing 生命周期内保留；关闭/重开卡片保留，离开任务中心页面再返回按
  普通页面导航处理，不宣称跨路由持久化。表单草稿不持久化；在途/未知时表单禁用并给出
  原请求提示。
- 新的 Node E2E 桌面回归使用 1536×600（同桌面宽度、内容可滚动），390×844 使用 B 的窄屏
  场景；1536×1024 的全量截图/视觉验收仍由 B 执行。
- 原生条目四类共享实现的完整全排列不再重复；本轮覆盖决定在途/未知、精确摘要确认在途/
  未知和条目隔离。其余四类与完整 T4、wheel/源码外消费、最终视觉/安全验收仍由 B 执行。


## B Review Result — 修复候选 d911995f

**FIX REQUIRED — 2026-11-06。** 同一 Task50.2、同一 B50.2-02 的关闭后结果处理仍有残留，
不新增 Task、不重开已通过的原复现。

```text
Reviewed Base: 575898ebaae593568be59699bb40116f9e6f2d91
Reviewed Head: d911995f49eed4fad34bd3123439e573b152b85b
本轮修复增量: ddec4856..d911995f
Branch: main
Next Action: DEVELOPER FIXES THE SAME TASK; NO PUSH / DEPLOYMENT
```

结合前次完整审查，核对全部 Base..Head 的 18 个文件；本轮独立审查全部修复增量，追踪
原生决定、继续、准备/确认与父层导航回调，保留原 Task Base。预存 `.DS_Store`、日志、
`15`、`output/` 等未动、未暂存，本轮只修改本 Task 的复核记录。

### 已修复的原复现

- **B50.2-01 通过本轮关键复验：** 390px 从既有任务名打开/关闭，fake 的
  `scrollY=461/461/461`，真实 Python/SQLite 为 `526/526/526`；入口焦点返回。
  原生首个小列表不产生滚动，因此后续通过已有 `seed-task-center-problems` 增加真实测试
  任务再复验；不把 `0/0/0` 当作已滚动证明，也未修改页面高度或制造新入口。
- **B50.2-02 的决定在途/未知重开通过：** 从识别恢复的问题文件进入原生条目表单，仅
  延迟真实 `/recovery/decision`；重开保持 busy、radio 禁用；未知结果保留核对并继续禁用。
  再关闭/重开、显式核对后恢复合法选项，全程 POST 仍为 1。

### 唯一已证实的剩余阻塞（P1，B50.2-02）

**完整用户旅程：** 任务中心 → 识别恢复 → 查看问题文件 → 条目证据 → 选择 Special →
保存决定并继续分析 → Worker 完成零变更分析 → 本界面生成新计划摘要 → 确认继续整理 1 项。
网络仍在等待时点击“关闭详情”，用户已回到原问题列表；成功响应迟到后，页面却自动跳到
“整理执行情况”，打断刚恢复的列表阅读。关闭本身合法，并不取消已受理整理。

B 在真实 Python API、临时 SQLite/Local 与合成 Provider 下走完上述现有入口，只在浏览器
延迟实际确认请求的 **真实 202 成功响应**，没有伪造成功或构造新入口。确认 POST 仅 1 次；
关闭后 URL 是 `/ui-v2/operations?view=recognition&problemRun=…`；释放响应后自动变为
`/ui-v2/operations/organize/execution/…?returnOps=…`。截图已人工打开检查。确认后没有再运行
执行 Worker；本结论是导航/返回上下文阻塞，不声称重复执行或数据损失。

**开发指导：**

1. 修复 `TaskItemRecoveryPanel.tsx` 的确认成功回调及其父层导航归属。结果照常写入精确
   条目会话并刷新真实持久读回；只有原处理界面仍是当前有效操作上下文时才沿用正常成功
   跳转。卡片已关闭或用户已切换任务/条目时，迟到结果不能再替用户导航。
2. 关闭后保留原列表/问题文件上下文；用户重新打开原条目时可看见实际受理结果，并通过
   既有明确链接主动查看执行。正常保持卡片打开时的成功旅程、未知核对、原权限/pins 与
   非重放不变，不增加关闭限制、重复确认、通用框架或后端能力。
3. 在真实卡片/父层 Router 接入下补“确认在途 → 关闭 → 成功响应迟到”的回归，验证 URL/
   选定任务不被旧回调改写、确认 POST 仅 1 次、重开能读到原结果；组合一次切换任务或条目
   以验证归属。现有 `RecoveryPanelHarness` 未传导航回调，其未知响应测试不能覆盖这个
   成功跳转分支。Developer 运行新增/失败及直接受影响测试后提交新 checkpoint。

### 本轮实际门禁、时间与证据

本地 ignored 目录：`.git/validation-evidence/d911995f/B50.2-review/`，含脚本、实际日志、
前/开/关及迟到成功截图、构建与证据 SHA256 manifest；仅本机可取。

- 根目录 `python3 scripts/check_governance.py`、`git diff --check 575898eb..d911995f`：PASS；
  本记录更新后再次检查治理和 whitespace。
- `web/` `npm run build`：PASS（既存 chunk 大小提示）；`npm run format:check`：PASS。
  首次构建日志重定向路径错误，构建未执行；修正路径后重新构建成功，不使用旧产物。
- 根目录运行上述证据目录的 `detail-probe.mjs`、`detail-native-probe.mjs`、
  `recovery-probe.mjs`：正常完成，结果如上。
- 同目录 `late-confirm-probe.mjs`：正常真实旅程完成，证实确认迟到成功后强制跳转；
  `late-confirm-probe.log` 与 `confirm-closed.png` / `confirm-late.png` 保存原始证据。
- 现场起始 `05:00:32 UTC`，至截图检查 `05:04:08 UTC` 已工作至少 3 分 36 秒；构建、格式
  和全部探测的执行墙钟保守上界 45 秒，小于该已记录工作时段的 21%，满足本轮低于 50%
  的限制。未靠空等凑比例。

已有真实 P1，按 workflow §6 提前 FIX REQUIRED；完整 T4、Python/Web/E2E 全回归、
wheel/源码外消费及最终视觉/安全门禁仍待 B 在修复候选上执行，未豁免，也不交给 Developer。
本轮没有把 Developer 报告算作 B 的独立门禁。

### 全 Slice 重评

RO-1 仍未完成验收；RO-2 与自动化稳定性补充保持 Task50.1 已接受事实；RO-3 两种库及
RO-4 主页面切换/库加载仍未交付。Slice50 保持 ACTIVE；不规划下一 Task、不提交 Closure
Packet、不进行 A 终审或关闭。下一步只修本 Task 上述剩余返回行为。

## Developer Completion Report — 确认迟到成功导航修复轮

状态：**READY FOR B REVIEW**（B50.2-02 剩余 P1 已修复，Developer 交接，未自审 PASS）。

```text
实现 checkpoint: 本报告所在提交（单个修复 checkpoint，d5c45b19 内容并入）
分支: main
Task Base: 575898ebaae593568be59699bb40116f9e6f2d91
B 审查范围: Task Base..本报告提交 HEAD
本轮工作/测试时间: 全轮约 20 分钟；测试运行墙钟合计约 3 分钟（约 15%，含缺陷复现验证，低于 30%）
```

工作区预存的 `mediaflow/.DS_Store` 修改及未跟踪 `.DS_Store`、日志、`15`、`output/` 等保持
原样，未暂存、未纳入 checkpoint。共享 `modal-card.tsx`、AppShell、存储和自动化生产代码未修改。

### B50.2-02 剩余阻塞修复

- **守卫归属（B 开发指导 1）：** `TaskItemRecoveryPanel.tsx` 新增 `contextActiveRef`
  （挂载即真、卸载即假）。确认成功仍照常写入精确条目会话、作废持久读回缓存；仅当本面板
  实例仍是当前处理上下文（卡片开着且未换条目/主体）才沿用原成功跳转。卡片已关闭、已切换
  任务/条目或主体时，迟到成功不再替用户导航；重开面板经持久读回显示"本次确认已经受理"
  与既有"查看关联执行结果"显式链接。同卡片内结构相同的**剩余范围确认**（`RunDetailPanel`
  的 `confirmRemainingScope`）按同一模式加守卫：关闭/换任务后迟到成功保留列表上下文，
  受理结果经 `remainingSession.admitted` 的显式链接可达。正常打开卡片时的成功旅程、未知
  核对、原权限/pins 与非重放不变；未增加关闭限制、重复确认或后端能力。
- **真实卡片/Router 回归（B 开发指导 3）：** `RunDetailTabs.test.tsx` 新增
  "keeps a late confirmation success from navigating a closed card"：真实 renderApp +
  名称点击 → 条目证据 → 生成计划摘要 → 确认在途（gate）→ 切到 item-1 证据（其面板不显示
  item-2 的确认状态，验证归属）→ 关闭证据、关闭详情（URL 回列表、无 `run=`）→ 释放真实
  202 → 断言 URL 保持 `/ui-v2/operations` 且不出现 `organize/execution`、详情卡不重开、
  confirm POST 恒为 1 → 重开原条目读到"本次确认已经受理"+ 可用显式链接。
  stub 扩展仅加 `planSummary`（Preview GET/确认 POST）测试入口，未改生产代码路径。
- **回归有效性验证：** 临时移除面板守卫后该用例真实失败
  （`expected '/ui-v2/operations/organize/execution/…' to be '/ui-v2/operations'`，
  与 B 复现一致），恢复守卫后通过；验证后未保留任何临时代码。

### 实际执行结果（cwd、命令、结果）

- 根目录 `python3 scripts/check_governance.py` → PASS（实施前、提交前）；`git diff --check`
  → 无输出。
- `web/` 指定受影响组件/单元（7 文件 84 用例，含新增用例）：`npx vitest run
  src/features/operations/OperationsInventory.test.tsx src/features/operations/
  RunDetailTabs.test.tsx src/features/operations/TaskItemRecoveryPanel.test.tsx
  src/features/operations/RunLifecycleControls.test.tsx
  src/features/operations/run-detail-state.test.ts
  src/shared/navigation/operations-return.test.ts
  src/features/operations/OperationsRouter.test.tsx` → 84 passed。
- `web/` `npm run typecheck` → PASS；`npx eslint`（3 个实际变更文件）→ PASS；
  `npm run format:check` → PASS；`npm run build` → PASS（仅既存 chunk >500 kB 提示）。
- `web/` Node E2E：`npm run test:e2e -- tests/e2e/operations.spec.ts
  tests/e2e/task-center-layout.spec.ts` → 37 passed。
- `web/` 真实 Python 栈 E2E（`--config=playwright.python.config.ts --workers=1`）指定
  grep 子集 → 9 passed（detail reads / filter context / 21-file / native 四类恢复 /
  Metadata correction / policy-permitted overwrite）。

### 已知失败

无。守卫移除的失败是有效性验证，已恢复。

### 剩余风险与留给 B 的验收点

- 剩余范围确认的"在途关闭→迟到成功"未单独立真实入口 E2E：该旅程此前无现成 harness，
  本轮仅按同一守卫模式修复并在组件层复用原生条目回归覆盖守卫机制；B 验收可按需补探测。
- 迟到成功的可见结果依赖重开后持久读回与 landing 级会话（本页生命周期内），
  刷新后以服务器持久 continuation/preparation 证据为准，与既有语义一致。
- 完整 T4、全量 Python/Web/E2E、wheel/源码外消费及最终视觉/安全验收仍由 B 执行。
