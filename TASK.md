# NO ACTIVE IMPLEMENTATION TASK

Last Tasks: 49.1 / 49.2 — Slice49
Decision: SLICE49 PASS / CLOSED — A FINAL REVIEW, 2026-11-05
Next Action: A SELECTS THE NEXT LARGE SLICE

原始 Slice Base：`02fb77dd713bad4dd51c29b6cfc5556ddd6d5b4e`。
已审 Implementation Head：`9d6b78147d90b950ed2333f9747facc77bf0391a`。
完整范围、验收、独立验证和限制见 [SLICE.md](SLICE.md#final-validation-closure-packet-and-a-final-review)。

B 最终 Closure Packet / Task49.2 PASS：
`edef2b9dfb3726f8aca6b4d7c4a7ae233f900d2c:TASK.md`；
Task49.1 PASS：`7b7e9aaa24684ee59552ca95641843706dc7680d:TASK.md`。
既有拒绝、修正、完整测试结果及原始失败/skip均留在 Git 和对应本地证据中。
本通知记录已完成的 A 终审与闭环，不授权新实施或自动选择下一 Slice；独立小版本 bug 仍由 B 按流程处理。

---

## Planning-only draft — Task PATCH-20261105-1：自动化创建/编辑展示与列表复制入口修正

**仅规划草案，尚未授权实施。** 用户本轮要求“规划Task吧，不要扩大或收窄需求”。
保留上方 `NO ACTIVE IMPLEMENTATION TASK`；获得实施授权后才启用以下独立 Task，
原 Task Base 不因启用或规划提交而重设。不得把本草案当成实施、评审 PASS、push 或部署授权。

Authority：用户本轮及前两轮对截图问题确认的三项范围；生命周期、Git、测试和独立小 Bug
流程以 [Development Workflow](docs/development-workflow.md#31-independent-minor-bugs) 为准。
角色经验见 [B](docs/agent-experience/task-planner-reviewer.md) 和
[Developer](docs/agent-experience/developer-implementation-role.md)。

```text
Task ID: PATCH-20261105-1
Task Type: STANDALONE MINOR BUG
Parent Slice: NONE
Status: PLANNED
Task Base: 9fa51289539c5279687ad0420bc74de758414776
Difficulty: Medium
Test Level: T4
Planner / Reviewer: B
```

Slice49 仅为已接受行为的参考，不是本 Task 的父 Slice；其 Base、Implementation Head、
验收和关闭状态不变，不修改 `SLICE.md`、Roadmap 或 Progress。

### Goal

完整交付以下三项，作为一个连贯的自动化列表/创建/编辑界面修正，不拆成多个 Task：

| 用户需求 | 本 Task 的完整结果 |
|---|---|
| 点击新建/编辑后左上角出现英文 | 列表及承载同一列表背景的新建、编辑路由均无额外页面位置标签；打开弹窗不因这行标签使背景下移。包含旧新建地址及深链/刷新/登录续转。 |
| 删除“生命周期操作”，复制移到列表“编辑”旁边 | 移除截图中的“生命周期操作”标题及独立启停、复制、刷新按钮组；启停使用上方控件并随创建/保存生效。复制紧邻列表中的“编辑”，其他行操作保持原有相对顺序，实际显示仍服从相应权限/可用状态。复制在原列表完成并反馈，保留原业务语义和未知结果核对。 |
| 启用自动化任务的大对勾不协调 | 创建/编辑共用紧凑启用开关，与左侧处理上限输入框对齐，开关与文字同排、说明在下方；保留当前创建默认关闭、编辑真实回填及保存后生效的语义。 |

这里的“删除”指截图中的生命周期按钮组，不是删除自动化定义；现有“引用安全的移除定义”
能力独立保留。新建卡片目前没有该按钮组，不为它增加新的生命周期区。

引用现有要求：[UX-001/002/004/007/009](docs/requirements.md#operator-experience-requirements)、
[V2-AUTO-013/014](docs/v2-requirements.md#automation-forms-and-direct-run-once--current-slice49-pass--closed)、
[完整创建/编辑旅程](docs/product-experience.md#current--automation-forms-and-direct-run-once-slice49-pass--closed)、
[自动化工作区及复制/移除边界](docs/product-experience.md#current--complete-native-automation-workspace-accepted43-amended46)、
[CURRENT 表单/发布契约](docs/architecture.md#current--automation-forms-and-direct-run-once-slice49-pass--closed)。
本 Task 调整上述指定界面入口和展示，不增加复制能力、执行权限或新发布机制。

#### Observed behavior / root cause

- `AppShell.tsx` 仅精确排除 `/operations/automation` 的 `.mf-page-context`。
  新建的 `/operations/automation/lifecycle`、旧 `/operations/automation/new` 及编辑的
  `/operations/automation/lifecycle/$definitionId` 继续展示同一列表，却重新输出各自的英文
  `destination.label`。隔离浏览器在 1536px/390px 均复现，额外行及间距使背景标题下移 34px。
- `AutomationEditDialog.tsx` 在共享表单下另外渲染“生命周期操作”，重复提供即时启停，
  复制和复制结果核对也绑定在该编辑组件内；“引用安全的移除”与它共用一个外层 section。
  `AutomationInventory.tsx` 的列表行目前没有复制入口。
- `AutomationDefinitionFormFields.tsx` 的 checkbox 没有专属布局；
  `.mf-automation-create-field input` 将文本框的 `width: 100%`、`min-height: 40px` 等规则
  施加到它，`.mf-automation-create-toggle` 又没有对应布局样式。实际 CSS 隔离测量得到
  441×40px 的 input 布局盒，文字另起一行。
- 现有 focused Copy 会原子发布新 ID 的停用定义，不继承执行授权。原编辑组件保留按
  principal 和来源/提交基线绑定的待核对上下文；迁移按钮时不能丢掉这部分能力。

上述隔离测量值只用于解释现象，不是修复后的固定像素目标。

### Implementation Scope

1. **消除指定路由的多余提示。** 在共享外壳中统一上述列表背景路由的提示规则，覆盖
   规范新建、旧新建和编辑。检查普通点击、深链、刷新及重新登录后的相同体验；只修改
   此处多余提示，不批量隐藏或翻译其他页面，不靠修改标签文字留下多余空行。
2. **迁移列表复制及其完整结果处理。** 在“编辑”旁加入紧邻的“复制”，复用现有
   `copyAutomationDefinitionFocused`、后端权限/来源解析/版本校验和持久证据核对。
   使用所观察的已保存来源及对应发布基线，不复制编辑中未保存的输入，也不在冲突后
   偷换基线自动补发。保留现有可复制来源范围及 Draft-only/历史身份的真实区别。
   必要时只复用/补足本入口所需的现有只读投影和类型，不另建复制业务或命令框架。
3. **让复制在列表完成。** 一次明确点击提交既有复制命令；行内显示忙碌、防连点，
   成功后读取真实结果、更新列表/统计并标出副本，提供可识别的副本编辑入口，不强制跳页。
   保持筛选、分页、滚动及入口焦点；副本不在当前筛选/页中时说明原因并保留其明确入口。
   拒绝说明原因及下一步；丢响应、5xx 或畸形响应等无法证明结果时保留原提交上下文，
   刷新/重开后只核对，不自动再复制。不同来源行的忙碌和结果不串用。
4. **保留既有未决复制和发布。** 将复制会话/核对能力从编辑区迁至列表所需的最小
   共享代码，兼容现有 principal-scoped session 中的来源 ID 和原发布基线；来源被筛选掉、
   翻页后不在列表或已不在当前配置时，仍有可见的原命令核对入口。核对不能冒用另一行、
   另一主体或后一次复制的结果。证据不完整保持未知，不因移除编辑按钮解除重复提交保护。
   移除独立启停按钮后，既有未决启停/保存仍按当前发布核对能力可达。
5. **移除重复区并统一启用控件。** 移除“生命周期操作”标题及截图中的启停/复制/刷新
   按钮组；复制反馈/核对随入口迁移。“引用安全的移除定义”独立保留其入口、权限、
   影响证据、确认和行为；错误状态中必要的只读刷新/核对入口继续可达。
   创建/编辑启用控件参考现有规则页的紧凑开关视觉，与左侧输入框的控制行对齐，
   文字同排、说明下置。现有 44×24px 开关和约 40px 控制行是实现参考，不锁定精确尺寸
   或 DOM 结构；按实际协调性、可读性和可操作性验收。限定样式作用域，避免文本框规则
   再覆盖开关。保留可访问名称、正确状态、键盘操作、焦点、禁用说明和 reduced-motion；
   不复制另一套表单。
   开关仅改表单选择，点击创建/保存后才发布；与本次入口直接相关的中文提示应指向真实入口。
6. **补齐直接受影响验证并交接。** 更新旧按钮入口的测试，保留原业务断言而不是删掉
   复制/启停/移除用例。加入三项需求的实际路由、样式可见结果、复制成功/失败/未知与
   连续操作回归，完成下方 Developer 计划后提交一个连贯候选，由 B 独立验收。

主要影响：`web/src/shared/ui/AppShell.tsx`、`styles.css`，
`AutomationListPage.tsx`、`AutomationInventory.tsx`、`AutomationEditDialog.tsx`、
`AutomationDefinitionFormFields.tsx` 及直接使用的复制会话/API 类型/测试。
后端仅在该入口确实缺少必要只读投影时作最小兼容补足；复制/启停发布规则本身不重做。

### Acceptance Criteria

- [ ] **AC-1：英文与位移。** 列表、新建、旧新建及编辑的实际路由均无多余英文位置行
  或其占位；打开/关闭弹窗时背景标题不会因该提示上下移动。深链、刷新、登录续转和读取
  失败状态也成立，其他页面既有提示不受影响。
- [ ] **AC-2：指定区移除。** 创建/编辑不出现“生命周期操作”标题及该组即时启停、复制、
  刷新按钮；列表复制紧邻编辑。引用安全的移除定义独立可达，原权限、确认、历史保留不变。
- [ ] **AC-3：协调的共用开关。** 桌面上启用控件与处理上限框的控制行对齐，开关不被撑成
  大方框、不挤换文字；390px 下布局清楚且页面不横向溢出，既有宽表格可在自身容器内滚动。
  两种表单的开/关/禁用/焦点状态均可读可操作，键盘和 reduced-motion 可完成同一旅程；
  不能只用 DOM 属性或 CSS 数值证明视觉。
- [ ] **AC-4：启用语义保持。** 新建默认关闭，明确选中后创建并启用；编辑回填已保存状态，
  可通过同一开关和保存启用/停用，再次打开仍可继续编辑。拨动开关、取消或放弃不发布；
  权限拒绝、冲突、失败或未知结果保留原选择及当前既有安全恢复能力。拨动控件或发布命令
  本身不即时准入 Task；正常 Scheduler 后续按已保存计划准入的工作不属于违规副作用。
- [ ] **AC-5：真实列表复制。** 有权限且状态允许时，一次点击从后端认可的已保存来源生成
  新 ID 的停用副本，来源不变、副本不继承执行授权；不使用未保存表单。成功在列表如实提示
  并可编辑副本，保持原列表上下文，筛选/分页未显示副本时有明确说明。
- [ ] **AC-6：边界与冲突。** 无权限、非法/缺失来源、版本过期、读失败及发布拒绝均有
  明确中文原因和下一步。后端仍权威校验，前端不自行授予权限；被拒命令自身不发布
  Active 变更，并发修改必须明确重读后再决定，不自动替换来源/基线重发。不能要求
  整个系统的 Active 在此期间保持不变，也不能把其他主体的合法发布归为本命令的效果。
- [ ] **AC-7：未知与重复保护。** 连击不多建副本；复制中、拒绝、成功、待核对属于本次
  来源/主体/提交。丢响应/5xx/畸形响应、重开/刷新/重连后保留并核对原命令，不盲目重发。
  旧编辑页留下的未决复制仍能在列表核对，来源不可见也不丢失；持久证据缺失或不完整不得
  假报未发布，同一未决意图不产生第二副本，不串用其他主体或兄弟行反馈。
- [ ] **AC-8：原链路不回退。** 创建/编辑的字段、准确回填、启用权限、退出保护、未知发布
  核对、列表返回和“运行一次”保持既有语义；来源的 Draft-only/历史身份不伪装 Active。
  既有未决启停/保存可继续核对，移除定义仍经原安全链路完成。
- [ ] **AC-9：副作用边界。** 这些打开、浏览、关闭、读取和结果核对操作本身不发布配置、
  不准入 Task、不变更媒体；复制命令只发布停用副本，不触发 Run once/媒体操作，
  不修改来源 enabled/due 或原已准入 Task/结果。创建/保存仍只作原有显式发布。
  按实际提交命令及其可归因的效果核对，不用全局计数或整库状态冻结作为唯一证明；
  独立的合法并发操作和正常调度不应造成误判。
- [ ] **AC-10：可验收证据。** Developer 交受影响测试及准确候选；B 对完整
  Task Base..candidate 独立检查以上结果，提供桌面/390px 实际截图和适用 T4 验收结果。
  无法执行的必需门禁如实 pending，不以规划检查或旧 Slice 的 PASS 代替本次验收。

### Required Tests

遵循 [测试等级与所有权](docs/development-workflow.md#6-test-levels)。本 Task 为 T4；
下列实施/验收命令是后续执行计划，不表示本轮已实施或验证产品修复。

### Developer — affected tests

根目录：

```sh
python3 scripts/check_governance.py
.venv/bin/python -m unittest tests.test_automation_definition_publication tests.test_v2_automation_lifecycle
git diff --check
```

Python 模块作为实际复制发布/来源身份/权限/版本和持久未知核对的直接受影响回归；
如增加只读投影，在上述模块补对应验证。使用隔离 SQLite/Local/合成数据，不读私有配置或用户媒体。

`web/`：

```sh
npm run typecheck
npm run test -- run src/shared/ui/AppShell.test.tsx src/features/operations/AutomationRouter.test.tsx src/features/operations/AutomationCreateDialog.test.tsx src/features/operations/AutomationLifecyclePage.test.tsx src/features/operations/AutomationListRunOnce.test.tsx src/features/operations/automation-create-form.test.ts
npx eslint src/shared/ui/AppShell.tsx src/features/operations/AutomationListPage.tsx src/features/operations/AutomationInventory.tsx src/features/operations/AutomationEditDialog.tsx src/features/operations/AutomationDefinitionFormFields.tsx
npx prettier --check src/shared/ui/AppShell.tsx src/shared/ui/styles.css src/features/operations/AutomationListPage.tsx src/features/operations/AutomationInventory.tsx src/features/operations/AutomationEditDialog.tsx src/features/operations/AutomationDefinitionFormFields.tsx
npm run build
npm run test:e2e -- --config=playwright.python.automation.config.ts tests/e2e/automation-create-dialog.python.spec.ts tests/e2e/automation-lifecycle.python.spec.ts
```

新增/修改的复制会话、列表/API 类型或测试文件也须加入对应 Vitest、ESLint/Prettier 的实际
文件参数，交接写明精确命令；若有 Python 修改，对实际修改文件执行 Ruff format/check。
以上不是全量 Python/Web/E2E 或发布矩阵的转交。

测试覆盖：四个路由及开关样式/可访问性、共享创建/保存启停、列表副本回读/返回、重复点击、
当前/过期基线、权限拒绝、响应丢失/5xx/畸形响应、旧 session 核对与主体切换，以及原有
Run once/移除入口的直接回归。原生用真实 Python harness 和生产构建，验证实际效果，
不能仅用全 API 404 的隔离样式探针作为修复验收。

### B — acceptance and full regression

1. 独立审查整个 `9fa51289539c5279687ad0420bc74de758414776..candidate`，先复现三项
   用户结果和关键复制不确定性。逐项核对 AC-1–9，包括列表中连续复制、权限/并发拒绝、
   发布后丢响应、旧编辑待核对上下文、筛选掉来源/副本和改登录身份的真实结果。
2. 承担 [T4 共享完整门禁](docs/development-workflow.md#shared-full-regression-commands)：
   完整 Python/Web/默认 E2E、质量、安全/持久性和适用 wheel/安装消费者/容器门禁。
   执行顺序、匹配证据复用、实际失败/skip/环境限制及精确产物身份按 workflow 记录；
   不要求 Developer 先跑这些全量门禁才交候选。
3. 在 `web/` 用本候选新构建执行相关真实 Python 浏览器集合：

   ```sh
   npm run build
   npm run test:e2e -- --config=playwright.python.automation.config.ts tests/e2e/automation-create-dialog.python.spec.ts tests/e2e/automation-lifecycle.python.spec.ts tests/e2e/automation-run-once.python.spec.ts tests/e2e/automation-workspace.python.spec.ts
   ```

   浏览器证据须包含实际列表→新建/编辑→取消/保存、列表复制→成功/拒绝/未知→核对→
   编辑副本；桌面及390px、键盘/reduced-motion、开/关/禁用、读取失败/深链/登录续转。
   检查实际截图和背景位置、行操作的邻接顺序及无页面横向溢出，不只数 heading。
4. 确认复制的真实配置/审计/新旧定义身份、停用和无即时 Task/媒体副作用；确认原权限、
   固定上下文、RecognitionType C 使用 A 策略仍为 C、已完成/不确定效果不重放等原安全
   回归通过。优先使用上述完整测试中的既有证明，不另造超出本 Task 的业务能力。
5. 证据保存于 `.git/validation-evidence/<candidate>/patch-20261105-1/` 或 CI，记录
   candidate、实际命令/结果、截图及失败/skip/限制。全部必需验收满足后才 PASS；
   FIX REQUIRED 留在同一个 Task。独立 Bug 完成按 workflow §3.1 恢复无活动 Task 通知，
   不作 Slice closure 或另立后续 Task。

### Non-goals

- 不增加列表启停开关、批量复制、复制前新向导/确认流程或新的复制业务语义；不改变
  复制始终停用、不继承授权、显式保存启停及后端权威的既有规则。
- 不移除“引用安全的移除定义”能力，不重做详情、Draft 编辑、删除、执行记录、Task Center、
  全站路由提示/翻译、设计系统、Scheduler、队列、Storage 或媒体处理流水线。
- 不新增 schema、配置库、命令框架、自动重试/未知重放或历史数据改写，不做生产部署。
- 不改 `SLICE.md`、Roadmap、Progress 或其他产品文档来扩大/收窄三项需求；实现中仅允许
  与本入口直接相关的提示和测试同步，不顺手清理其他问题。

### Planning preflight / workspace

Repository：`/Users/songzhidong/mediaflow`；branch：`main`；起点/不可变 Task Base 如上。
规划前 `python3 scripts/check_governance.py` PASS；`TASK.md` 与 `.git` 可写，暂存区为空。
本轮只修改并 checkpoint 本草案，不实施产品代码。

预存变更全部保留且不纳入 checkpoint：tracked `mediaflow/.DS_Store`；untracked：

```text
.DS_Store
.mgmt.log
.t.log
.t_test_dashboard.log
.t_test_final_integration.log
.t_test_media_library_direct_commands.log
.t_test_operations_run_detail_log_isolation.log
.t_test_phase21_closure.log
.t_test_recognition_review.log
.t_test_workflow_retry.log
15
docs/.DS_Store
docs/pics/.DS_Store
docs/pics/自动化页-全局设置.png
docs/pics/自动化页.png
output/.DS_Store
output/database-reference-2026-11-01/
output/imagegen/slice45-task-center-v1.zip
output/organize-flow-2026-11-01.html
testdata/.DS_Store
web/.DS_Store
```

### Developer Completion Report

未实施；无 Developer checkpoint。后续由实施角色记录实际候选、改动、受影响测试、
失败/风险及 `READY FOR B REVIEW`；完整验收仍由 B 执行。

### B Review Result

尚无实施候选，未开始独立验收。本轮产物仅为规划草案，不是 PASS/FIX REQUIRED 评审。
