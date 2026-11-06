# Task50.2 — 任务详情弹卡与可读性

Authority：已提交 `575898ebaae593568be59699bb40116f9e6f2d91:SLICE.md` 的 RO-1、
AC-1/2、适用 AC-10/11；遵循 [Development Workflow](docs/development-workflow.md) 与
[Task 模板](Task/TEMPLATE.md)。用户于 2026-11-06 明确授权激活 Task50.2，作为当前唯一
活动实施 Task。最新 B 结论为 FIX REQUIRED：原三项交互复现均已通过，详情主条目表格仍有窄屏路径/状态叠字，需在本 Task 内完成可读性修复。

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
| RO-1 任务详情卡片/可读性 | 交互修复已复验；主条目表格窄屏叠字仍阻塞，Task50.2 未验收。 |
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

## 既有交接与复核指针

完整计划和原失败事实保留在 Git，不重设 Task Base：

- 初次实现与 B 返修：`46be457f:TASK.md`、`ddec4856:TASK.md`。
- 决定在途/滚动修复与 B 复核：`d911995f:TASK.md`、`88ab8899:TASK.md`。
- 确认迟到成功修复与完整 Developer 交接：`ba2fe44ef97774ae6f09e82fd8e70bf6d0b22214:TASK.md`。
  Developer 报告受影响组件 84 passed、Node E2E 37 passed、真实 Python 子集 9 passed；
  本轮 B 独立运行结果如下，不把 Developer 报告作为 B 门禁。

## B Review Result — 最新候选

**FIX REQUIRED — 2026-11-06。** 唯一已证实的产品阻塞是下方 B50.2-03（P1）；前序三个
交互问题的修复保持，不为旧复现重复返工，不另建 Task。

```text
Task Base: 575898ebaae593568be59699bb40116f9e6f2d91
Product Candidate: ba2fe44ef97774ae6f09e82fd8e70bf6d0b22214
Reviewed Head: eac82c77273df15bd51787a6191e671ffcd9f1fb
B test/document checkpoints: 3cefd1b8 + a82948f0 + eac82c77
Branch: main
Decision: FIX REQUIRED — SAME TASK 50.2
```

结合前次完整审查，核对完整 Base..Reviewed Head 的生产、测试与文档差异；本轮独立审查
确认守卫及测试增量，并执行真实入口、全量门禁和视觉检查。B 没有改产品代码；三个后续
checkpoint 只修正本轮验收用例的实际操作入口及 Task 的测试责任标题。预存 `.DS_Store`、
日志、`15`、`output/` 等未动、未暂存，没有 push 或部署。

### 已通过的关键复验

- 列表滚动与决定在途/未知重开保留前轮修复，本轮完整 Node 相关回归通过；按精确主体/
  Task/条目保留会话，关闭不自行取消、重发或丢失原核对。
- 确认整理真实 202 成功响应迟到：原生识别恢复 → 决定/分析 → 新计划摘要 → 确认 →
  关闭详情。释放成功响应后 URL 仍在原 `view=recognition&problemRun=…` 列表；重开原条目
  可读到“本次确认已经受理”，只有主动点“查看关联执行结果”才进入执行详情。POST 仅 1 次。
- 真实 Python/SQLite 八视图名称入口均能打开/关闭居中卡片，原列表不挤窄；卡内标签/记录、
  键盘与回焦可用。独立八视图只读探测记录 API mutationCount=0。
- 已检查 1536×1024 与 390×844 的实际详情截图；居中、标题、关闭和滚动正文可用，下面的
  主条目表格可读性问题尚未通过，不能以通过脚本代替可见结果。

### B50.2-03 — 主条目表格的源路径与状态叠字（P1）

**用户完整旅程：** 任务中心 → 识别恢复 → 某任务“查看问题文件” → 文件证据与恢复记录 →
在详情卡里阅读“条目”表。390px 窄屏下，`source-storage:Recovery.2005.mkv` 的路径伸进旁边
“等待识别决策/阻塞”所在列；两列文字重叠，不能清楚对应源文件、状态和阶段。

B 先在多条目截图发现，再用已有 `seed-task-item-recovery?kind=recognition` 的真实生产
准入/恢复链路独立复现；普通 `Recovery.2005.mkv` 即能触发，未制造超长输入、伪造入口或
依赖旧 paused/partial_success 状态。只查看和截图，没有提交该项恢复或执行媒体操作。
证据：`native-current-items-390.png`、`native-current-items-probe.mjs/.log`。

**开发指导与修复验收：**

1. 从 `RunDetailTabs.tsx → RunItemsSection` 的实际八列表格及共享 `.mf-run-table-wrap`
   样式定位。为详情条目表格安排合适的列宽、源路径/技术身份换行及表格内横向滚动，保证
   每列文本留在自己的阅读区域。具体布局由实现选择；保留完整路径和状态，不通过隐藏、
   截断后无完整读取方式或压缩字号掩盖。不为此重做任务列表或共享设计系统。
2. 桌面与 390px 使用上述普通路径及代表性长路径、多条目、等待/失败/成功状态验收；
   路径、状态和阶段不叠字，查看证据等动作可通过表格内部滚动到达，卡片关闭保持可达，
   页面不被撑宽。检查同样受样式影响的记录/结果表格；允许独立局部修正，不增加业务能力。
3. 增加贴近真实卡片的直接受影响布局回归，并检查实际桌面/窄屏截图与滚动交互。保留现有
   行身份、分页/筛选、原生四类处理、核对和三项已修复交互。Developer 只跑新增/修改/
   直接受影响用例；完整门禁与 B 本轮未完成的原生验收仍由 B 承担。

### 本轮 B 实际门禁与证据

稳定本地 ignored 目录：`.git/validation-evidence/ba2fe44e/B50.2-review/`，仅本机可取。
`python.json` / `web.json` / `native*.json` 记录精确命令、cwd、起止时间和退出码，同名
日志保留失败与中断；manifest 记录产品/测试检查点及构建、脚本、截图摘要。

| 门禁 | B 实际结果 |
|---|---|
| 治理、差异 whitespace | 现场 PASS；本报告更新后再次检查。 |
| Python Ruff format/check、compileall、pip check、两个 example validate | PASS；禁用依赖搜索无匹配（预期 exit 1）。 |
| 全 Python | 2603 tests，7 skipped；唯一失败是 Task 的 B 测试责任标题不符合现有文档消费者约定。B 已修正文档标题，直接受影响 `test_release_security.py` 8 tests 重跑通过；原全量失败日志保留，不改断言。 |
| Web typecheck / lint / format | 在产品候选均 PASS；B 修订过的验收文件执行 ESLint、Prettier 与 typecheck。最后一处深链关闭步骤未另起昂贵测试，仍列入后续原生完整门禁。 |
| Web 单元/组件全量 | 94 files / 1361 tests passed。 |
| 生产构建 + Node E2E 全量 | PASS；254 passed。既存大 chunk 提示保留。 |
| wheel + 源码外消费者 | wheel build 与 `wheel_smoke_test.py` PASS，新 venv 安装/源码外实际消费者通过。 |
| 真实 Python E2E 完整计划 | **未通过完成。** 原用例有穿遮罩点击页头/侧栏/视图的旧操作；B 改为卡内刷新或关闭后操作，保留只读、结果/证据、返回、筛选等业务断言。本轮选择器修订也曾不完整及匹配两个刷新按钮，失败日志均保留。最后一轮 36 passed / 1 failed / 1 interrupted / 10 未运行；唯一失败仍是深链卡片打开时点击背景视图，已补显式关闭步骤但未复跑。发现上方真实视觉 P1 后停止余下测试，不把测试脚本问题退给 Developer 作为产品缺陷。 |
| 原生独立交互/截图 | 真实迟到成功关闭/重开/主动查看结果通过；八视图开关、标签/键盘及 390px 查看完成；窄屏表格叠字未通过。 |

Web 单元、Node E2E、Python 代码/依赖、wheel 输入在 B 的 test/document 后续提交中未改变；
这些执行结果只作为实际覆盖事实，**本 Task 没有 T4 PASS**。原生套件修订后的完整执行、
新布局修复后的匹配回归/视觉均待 B，不隐去中断或把未运行记成通过。

7 项可选外部服务/耐久 skips 保留，未连接生产服务。Python ResourceWarning、jsdom
scrollTo 和构建 chunk 提示保留。Docker/Compose/重启安全矩阵本轮未执行；Task 未改
部署/镜像/后端/schema/常驻服务合同，沿用前序前端呈现 Task 的适用性判定，不作发布批准。

**测试时间偏差：** 现场起始 `06:28:26 UTC`。带起止记录的测试命令区间并集为
537.25 秒（约 9 分钟），另有早期构建/独立探测和少量静态检查；截至本报告的本轮工作约
14 分钟，测试占比超过用户要求的 50%。这是 B 执行安排未满足约束，已停止更多测试，
不通过空等延长工作时间或隐藏失败改写比例。

### 全 Slice 结果与下一步

RO-1 的交互修复已验证，详情可读性及完整验收仍未完成；RO-2 存储与 RO-4 自动化稳定性
补充保持 Task50.1 的接受事实；RO-3 两种库与 RO-4 主页面切换/库加载仍未交付。
Slice50 保持 ACTIVE，不规划下一 Task、不交 Closure Packet、不进行 A 终审或关闭。
下一步只由 Developer 在同一 Task50.2 修复 B50.2-03；B 之后补齐自己的验收。
