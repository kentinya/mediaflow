# Task PATCH-20261105-1 — 自动化创建/编辑展示与列表复制入口修正

B 于 2026-11-05 独立复核完整 Task Base..候选，结论 **FIX REQUIRED**。
三项界面修正已有实现，但列表复制的本次结果、冲突恢复和所见配置绑定尚未满足验收。
修复继续留在本 Task；下方 B Review Result 给出真实用户触发、证据及开发指导。
Task Base、三项需求、Difficulty / Test Level 与既有边界不变。

Authority：此前确认的三项截图需求、Task 激活及本轮 B 独立复核指令；生命周期、Git、测试和独立小 Bug
流程以 [Development Workflow](docs/development-workflow.md#31-independent-minor-bugs) 为准。
角色经验见 [B](docs/agent-experience/task-planner-reviewer.md) 和
[Developer](docs/agent-experience/developer-implementation-role.md)。

```text
Task ID: PATCH-20261105-1
Task Type: STANDALONE MINOR BUG
Parent Slice: NONE
Status: READY FOR B REVIEW
Task Base: 9fa51289539c5279687ad0420bc74de758414776
Difficulty: Medium
Test Level: T4
Planner / Reviewer: B
```

Slice49 仅为已接受行为的参考，不是本 Task 的父 Slice；其 Base、Implementation Head、
验收和关闭状态不变，不修改 `SLICE.md`、Roadmap 或 Progress。
已接受实现与闭环指针见 [SLICE.md](SLICE.md#final-validation-closure-packet-and-a-final-review)；
原无活动 Task 通知及规划版本保留在上述激活前 checkpoint。

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
下列实施/验收命令是后续执行计划，不表示本轮激活已实施或验证产品修复。

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

### Activation preflight / workspace

Repository：`/Users/songzhidong/mediaflow`；branch：`main`；不可变 Task Base 如上，未重设。
激活起点 HEAD：`df05111f1cb551d3267a370173e3838574a28d92`。
激活前 `python3 scripts/check_governance.py` PASS；暂存区为空。
本轮只修改并 checkpoint Task 激活状态，不实施产品代码。

激活时预存变更全部保留且不纳入 checkpoint：tracked `mediaflow/.DS_Store`；untracked：

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
output/.DS_Store
output/database-reference-2026-11-01/
output/imagegen/slice45-task-center-v1.zip
output/organize-flow-2026-11-01.html
testdata/.DS_Store
web/.DS_Store
```

### Developer Completion Report

**状态：`READY FOR B REVIEW`。实施候选已本地 checkpoint：
`7fac98cb5aeb69d449eba04800c9be2c97209b7a`
（`fix(automation): bind list copy feedback and authority to one observed row`）。
以下验证均在该 checkpoint 的同一源码/测试树上执行；Task Base 仍为
`9fa51289539c5279687ad0420bc74de758414776`，未改 `SLICE.md`、Roadmap、Progress，未推送。
本轮按 B Review Result 的 B-PATCH-01/02/03 修复，不重设 Base、不另立 Task。**

**改动（仅本 Task 列表复制入口）：**

1. **B-PATCH-01 本次结果不再被旧成功覆盖。** `clearCopyRowFeedback` 现在同时移除该行
   已显示的 `copiedCopies` 成功记录；一次新的明确复制开始后，旧“已复制为停用副本”
   与“编辑副本”立即退出，只显示本次提交、拒绝、未知或核对结果。兄弟行与其它未决意图
   保持不变；待核对时仍显示本次“核对复制结果”，核对后“编辑副本”打开本次副本。
2. **B-PATCH-02 409 与页面刷新同时恢复来源和授权。** `refreshDefinitionRead` 除列表外
   同步失效并重读表单授权查询；页面“刷新”也走同一恢复，且在列表/授权读取期间禁用，
   避免用户按旧提示再次提交同一版本。更新后的下一次明确点击绑定重新读取的配置。
3. **B-PATCH-03 所见来源与命令基线配对。** 新增 `readCopyBaseline`：仅当行的
   `activeConfiguration` 与表单授权 `active` 的 `revisionId`、`revisionSequence` 和
   `version` 完全一致且 digest 非空时才允许提交；授权读取先返回新版本而旧行仍显示旧值时，
   本次明确点击不发 POST，只做只读重读并保留可见说明；用户看到最新值后再次点击才提交。
   不在原点击里换基线自动补发，也不把新授权静默配给旧行。无权限、授权读失败和不可用
   授权继续给出中文原因与下一步。

**实际验证（本工作区候选；命令均在仓库根或 `web/` 实际执行）：**

- `python3 scripts/check_governance.py` → `governance check: PASS`。
- `.venv/bin/python -m unittest tests.test_automation_definition_publication
  tests.test_v2_automation_lifecycle` → **91 tests OK**（46.8s）。
- `git diff --check` → 无输出。
- `npm run typecheck`（两份 tsconfig）→ 通过。
- `npm run test -- run src/shared/ui/AppShell.test.tsx
  src/features/operations/AutomationRouter.test.tsx
  src/features/operations/AutomationCreateDialog.test.tsx
  src/features/operations/AutomationLifecyclePage.test.tsx
  src/features/operations/AutomationListRunOnce.test.tsx
  src/features/operations/AutomationListCopy.test.tsx
  src/features/operations/automation-create-form.test.ts
  src/entities/operations/automation-lifecycle.test.ts`
  → **8 files / 108 tests passed**（15.6s）。
- `AutomationListCopy.test.tsx` 新增 4 项并保留原 7 项，共 **11 项**：旧成功后第二次
  丢响应只显示本次待核对、核对出第二个副本并可编辑；旧成功后第二次明确拒绝不再显示旧
  成功；409 后列表与授权一起更新，页面刷新后的下一次明确复制用新版本成功；行先返回、
  授权后返回且中间已保存新值时，旧行不发 POST，重读显示新值后才提交。断言真实 POST
  次数、请求中的 `expectedRevisionId`/`expectedVersion`/`expectedDigest`、副本 ID/上限
  和 session 清理。
- `npx eslint`（本次 3 个改动源/测试文件及 TASK 所列入口文件）→ 无输出；
  `npx prettier --check`（上述改动文件及 `styles.css`）→ 通过。
- `npm run build` → 成功（`index-1dc4Y-rF.js`、`index-UWKGzSrN.css`，仅既有
  chunk >500 kB warning）。
- 原生 Python E2E（真实 API + 临时 SQLite + 上述生产构建，单 worker）：
  `npm run test:e2e -- --config=playwright.python.automation.config.ts
  tests/e2e/automation-create-dialog.python.spec.ts
  tests/e2e/automation-lifecycle.python.spec.ts`
  → **35 passed（54.6s）**（创建 14、生命周期 21）。新增 3 条真实生命周期旅程：
  - 第一次复制成功→第二次响应丢失→当前行只显示第二次待核对→核对第二个真实 ID/上限→
    编辑第二个副本；两次 POST 分别携带第一次和第二次观察的 Active fence。
  - 列表行先显示 5、授权 GET 被延迟；另一标签页真实编辑保存 9 后授权才返回；旧行点击
    复制不发 POST，只读重读显示 9，再次明确点击才发布复制 9 的停用副本。
  - 列表行/授权仍为旧版本时另一标签页保存 9；原列表复制收到 409；列表与授权重读并
    显示 9，页面刷新后下一次明确复制以新 revision/digest 成功。
  原有创建/编辑、共享开关、未知发布核对、移除与复制回归同时通过。

**用时：** 本轮约 30 分钟，测试/门禁执行约 3 分钟（Python 47s、Vitest 16s、
E2E 55s + 新增用例复跑约 19s、静态/构建约 20s），约 10%，低于 30% 上限。

**剩余风险 / B 注意：**

1. 复制入口是否显示仍以后端表单授权 `actions.copy`（配置管理 + 配置激活）为准，不使用
   列表行 draft-gated 的旧 `actions.copy` 字段；这是 Task 既有可复制范围，本轮未改变，
   请 B 按真实权限矩阵复核。
2. 行列配对依赖列表行携带的 `activeConfiguration`。若某来源没有该只读身份，复制会被
   拒绝并说明；本轮未新增 schema 或后端投影。
3. 列表复制反馈仍是当前列表挂载期状态；进入副本编辑再返回后，副本在真实列表/统计中，
   但该行成功提示不跨路由重挂载保留。
4. 未执行 B 的 T4 全量/默认 E2E/wheel/安装消费者/容器门禁；未改私有配置或用户媒体。
   工作区原有未跟踪文件（含 `mediaflow/.DS_Store`）全部保留，未纳入候选。

### B Review Result

**Decision: FIX REQUIRED — 2026-11-05，B 独立审查。**

Reviewed range：`9fa51289539c5279687ad0420bc74de758414776..7881139688a00ae50c9184318a3688749de4e93a`，
完整 17 文件（含计划/交接、实现和测试），不是只看最后提交。
产品候选 `d6e8f979c491f9101c926c4f2854a5fb33e4383a`；其后到被审 Head 仅
`TASK.md` 报告变更，执行输入相同。三个问题均由该实现提交引入
（2026-11-05 21:35:30 +0800）。修复不重设 Base，不另立 Task。

#### 已核对的交付与未完成结果

- 实际创建/编辑卡片和列表已移除多余位置行；复制紧邻编辑，编辑区不再有生命周期
  按钮组，引用安全移除仍可见。共用开关桌面紧凑对齐，390px 中文字可读；检查了实际
  截图、开/关、键盘焦点和 reduced-motion。这里只确认所观察的结果，未将全部 AC 勾为通过。
- **AC-7 未满足：本次未知被上次成功覆盖。** 用户在列表复制一次成功，随后再次点击同一行
  复制；第二次后台已产生另一个停用副本，但响应丢失。当前行仍显示第一次“已复制为停用
  副本”和第一次的“编辑副本”，没有第二次的“核对复制结果”。本次待核对信息实际仍在
  session 中；继续点复制被提交保护静默拦住，当前页面不能完成本次核对。页面重载后可找回
  核对，不等于当前结果准确。根因：`clearCopyRowFeedback` 没清理该行 `copiedCopies`，
  `copyFeedback` 又让旧成功优先于当前 pending。**P1，B-PATCH-01**。
- **AC-6 未满足：按提示刷新后仍无法恢复复制。** 用户先打开列表，另一标签页正常创建
  一个任务；原列表点击复制收到 409。列表已重读并显示另一标签页的新任务，用户再按页面
  “刷新”并明确重新点击复制，仍为 409，两个请求携带完全相同的旧版本。
  根因：409 和页面刷新只重读列表，未更新复制所用的表单授权查询。
  恢复说明让用户核对最新内容再复制，却持续提交旧配置。**P1，B-PATCH-02**。
- **AC-5/6 未满足：所见来源与命令配置版本分离。** 用户打开列表时行已读出上限 5，
  独立的授权读取较慢；另一标签页通过普通编辑保存上限 9，随后原页的授权读取完成。
  原列表仍显示 5，用户点击复制却 200 成功并复制上限 9。这里仅延迟真实 GET、使用现有
  编辑/保存/复制入口，没有构造不存在的命令。根因：`submitCopy` 只从行取 ID，直接配
  独立查询返回的 `copyBaseline`，没有绑定行所观察的配置。**P1，B-PATCH-03**。

#### Developer 修复指导（按顺序完成同一 Task）

1. 修复当前行的新旧反馈交接。一次新的明确复制开始时移除该行旧成功反馈；本次提交、
   拒绝、未知和核对结果必须对应本次命令。第二次未知应立即显示本次核对入口；核对后
   “编辑副本”打开第二个副本。保留兄弟行状态和已有未决意图，不新增通用命令框架。
2. 将复制来源与其读到的配置配对。复用行的 `activeConfiguration` 和现有授权身份；
   不一致时只读重读并让用户看到当前来源，再由下一次明确点击提交。不得把新授权悄悄
   配给旧行，也不得在原点击里换基线自动补发。若现有投影确实不足，仅补本入口所需的
   最小只读信息。Draft-only/历史来源继续按原可复制范围处理。
3. 让 409 后和页面“刷新”的只读恢复同时更新复制需要的来源与授权；更新后的可用复制
   必须绑定相同观察配置。无权限/读失败应有可用的恢复说明；重读本身不发复制命令。
4. 在 `AutomationListCopy.test.tsx` 及真实 Python 生命周期 spec 补上述三条完整旅程：
   第一次成功→第二次丢响应/5xx/畸形响应→核对第二次→可编辑第二副本；旧成功后第二次
   明确拒绝不显示旧成功；并发发布→409→页面刷新→下一次明确复制成功；行先返回、授权
   后返回且中间有合法保存时，旧行不能复制未展示的新值。断言真实副本 ID/字段、请求次数
   和原提交版本，不只检查按钮重新可点。保留现有测试的原权限/复制停用/未知不重发断言。
5. 执行本 Task 原 Developer affected-test 计划及新增失败用例，提交新连贯候选并更新交接。
   B 复核这些阻塞消除后负责剩余 T4 门禁；不把全量回归转交 Developer。
   本轮和修复轮均遵守用户要求：测试执行时间小于该轮总用时的 50%。

#### B 实际验证与证据

本地稳定证据根：
`.git/validation-evidence/7881139688a00ae50c9184318a3688749de4e93a/patch-20261105-1/`。
只在本机可取，不声称远程可达。命令/结果/构建身份摘要见该目录 `manifest.json`。

- `python3 scripts/check_governance.py`：PASS（审查前）。
- `git diff --check 9fa51289..HEAD`：通过；`web/` 的 `npm run build`：成功，
  使用 `index-BPlF38lR.js` / `index-UWKGzSrN.css`，保留既有 chunk warning。
- B 新建独立 Playwright 探针置于上述 ignored 证据目录，以真实
  `scripts/operations_inventory_harness.py`、临时 SQLite、生产构建和 Chromium 执行。
  从现有 UI 创建/编辑/保存/复制；丢响应只拦响应，慢读取只延迟真实授权 GET。
  每条业务写入仍经过实际 API 与配置发布，不读用户数据库或媒体。
- 首轮 `npx playwright test --config=<证据根>/review.config.mjs`：**1 passed / 2 failed**，
  12.68 秒；B-PATCH-01 实证失败。另一个失败是探针 `exact` 文本定位遗漏图标，不算
  产品问题；保留 `review.log` 和 `results/`，修正探针定位后继续确认。
- `--grep 'B conflict|B copy source'`：**2 failed**，5.83 秒；
  B-PATCH-02 的两次 409 同一提交版本，B-PATCH-03 的所见 5 / 复制 9 已记录，
  见 `review-confirmation.log` 和 `results-confirmation/`。
- `--grep 'B visual|B conflict'`：**1 passed / 1 failed**，3.34 秒；
  显式点击页面“刷新”后仍复现 B-PATCH-02；视觉用例在 reduced-motion 下重新截图，
  包含桌面和390px开关、编辑移除入口及键盘操作，见 `review-final.log` / `results-final/`。
  已实际查看四张创建/编辑截图。三次浏览器总执行约 **21.85 秒**；计时段
  21:39:15–21:43:25 已超过4分钟，构建不足2秒，测试占该已计时段不足10%，整轮低于50%。
- 按 workflow §6 的“已证实阻塞可提前 FIX REQUIRED”，**未运行**完整 Python/Web/默认
  E2E、剩余原生集合、wheel/安装消费者/容器门禁；这些保持 B pending，并非免除或 PASS。
  Developer 原交接结果保留为其报告，不冒充 B 本轮独立执行。

本轮仅更新并 checkpoint `TASK.md`；原预存文件原样保留，不纳入提交。
`SLICE.md`、Roadmap、Progress 不变；没有新 Slice、push 或部署。
