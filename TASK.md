# Task PATCH-20261107-1 — V2 任务详情可读性与导航稳定性修正

Authority: 用户本次六项界面修正、已确认的第三项展示设计及 2026-11-07 的 Task 激活指令；
独立修正路径遵循
[workflow §3.1](docs/development-workflow.md#31-independent-minor-bugs)。
本 Task 已完成首次实现并经独立 B 复核，当前为 **FIX REQUIRED**；Developer 在同一 Task
修正下列已证实的交付缺口，原六项范围、Base 与测试等级不变。未授权推送或部署。

Slice50 是相关已接受基线，不是 Parent；其 **PASS / CLOSED**、原 Base/Head、审查及延期
保留于 [SLICE.md](SLICE.md#final-validation-closure-packet-and-a-final-review)、
[Progress](docs/progress.md) 和
[B 固定收尾包](https://github.com/kentinya/mediaflow/blob/60798c3e50fdc62a6d46b6ee439e2406751ecfd3/TASK.md)。
不重开它，也不改原 Base/Head/关闭结论或
SLICE/Roadmap/Progress。B/Developer 分别读取相应 [角色经验](AGENTS.md#testing-and-roles)。

```text
Task ID: PATCH-20261107-1
Task Type: STANDALONE MINOR BUG
Parent Slice: NONE
Status: FIX REQUIRED
Task Base: fcfc1d2070932e0aaf354d8cc3c3b83f4b67574c
Difficulty: High
Test Level: T3
Planner / Reviewer: B
Working Branch: main
Development Authorization: USER AUTHORIZED — THIS TASK ONLY
Next Action: DEVELOPER FIXES THIS TASK
```

激活前分支 `main`，HEAD `ba12493cbcd81aa073e687a31263251e8669478c`，治理检查 PASS。
原 Task Base 到该 HEAD 仅 `TASK.md` 规划与澄清变化，没有执行源码/测试/依赖/构建配置变化；
保留原 Base、六项范围、已确认设计、验收及测试计划，原调查继续适用。预存 dirty/untracked
仍保留；本轮仅 checkpoint `TASK.md`。Developer 开始前重跑治理并核对当时 HEAD/工作区。

### Goal

操作者从左侧栏切换主页面、打开任务详情及文件证据时，能够直接读懂结果和可用操作，
并看到连贯的加载与切换过程；自动化页删除右上角常驻刷新按钮及打开新建时该按钮的闪动。
六项在同一 Task 内实施、交接和独立 B 审查，修正留在同一 Task 的 fix loop，不另拆后续 Task。

**范围原则：** 只完成上述六项及用户确认的第三项展示设计。取消、四类恢复、权限、日志、
导出及自动化编辑等已有能力，按本次改动的实际影响验证不退化，不重新开发，也不把其他
已有体验问题纳入修复目标。与本 Task 无关的既有问题不作为本 Task 新增关闭条件。

| 用户范围 | 本 Task 的明确结果 |
|---|---|
| 1. 删除截图中的运行控制区 | 删除说明型“运行控制”整块；真实可用的取消操作移到任务操作区，必要的进行中/失败/结果待核对反馈就近显示。 |
| 2. 更详细证据难读 | 删除详情中链接回同一任务详情的“更详细证据”字段；文件结果、计划解释、日志/审计可查，现有任务级导出保持可用。 |
| 3. 口径、成功含义等防御性说明 | 按下方用户确认的展示设计，以“流程状态→处理进度→文件结果”表达事实；删除常驻解释，异常才在对应文件或区域简短说明。 |
| 4. 查看证据内容难懂 | 以当前文件的处理结果、来源与目标、处理经过、失败原因/现有可用动作组织正文；技术 ID、原始字段和详细记录进入有层级的诊断。 |
| 5. 侧栏主页面切换不流畅 | 修正现有九个侧栏主页面的共享切换与加载接入，覆盖快/慢读取、缓存返回及快速往返；同页导航不重播整页动画。 |
| 补充. 自动化顶部刷新闪动 | 删除自动化右上角常驻刷新按钮，消除打开新建时该按钮的文案、禁用和宽度闪动；保留必要的异常重新加载和已有操作后更新。 |

适用要求：`UX-001–003/005/007`、`V2-UX-001–006/012/013`、`V2-OPS-005/007/012/016`、
`V2-TASK-003/007/012–014` 及 `V2-AUTO-001/002/014/015`。完整现行旅程见
[任务详情/切页/弹卡](docs/product-experience.md#current--v2-dialog-readability-and-navigation-experience-slice50-pass--closed)、
[任务与逐项处理](docs/product-experience.md#tasks-results-and-per-item-recovery)、
[自动化创建编辑](docs/product-experience.md#current--automation-forms-and-direct-run-once-slice49-pass--closed)
及自动化工作区的读取失败恢复；技术边界见
[Architecture CURRENT](docs/architecture.md#current--v2-dialog-readability-and-navigation-experience-slice50-pass--closed)。

**完整旅程：** 从侧栏、任务名称或合法深链进入；先看任务/文件实际状态，展开文件处理详情，
需要时使用已有取消或四类处理；已结束且无操作的任务不出现空控制区。失败或结果未确认时
清楚呈现受影响文件、失败阶段、已知结果和原有合法下一步。关闭/返回保留合法列表上下文，
切页和开关卡片不执行工作。自动化创建/保存成功自动读回列表，读取失败仍能在对应区域
重新加载；未知提交仍核对原命令。

### 用户已确认的第三项展示设计

用户确认“用状态和结果本身表达清楚，删掉常驻的解释段落”，并明确要求写入本 Task。
详情上方按**流程状态→处理进度→文件结果分布**安排主次，例如：

```text
流程已完成

已处理 12 / 12
━━━━━━━━━━━━━━━━━━━━

成功 10    部分成功 1    失败 1
```

这是混合结果的展示示例，不是固定数量或仅支持三类结果；实际数量、未知总数及其他已有
处置沿用当前任务证据，进度表示已处理范围，文件结果独立呈现。流程完成但有失败时，直接
显示完成状态与失败数量，不再附加“流程完成不代表文件成功”的教程。

**常驻文字的删除范围：** “口径：上方数值来自……”“成功含义：已验证的存储操作成功”、
“处理进度，非成功率”“附件步骤单独计数，不计入主条目”以及等价的重复实现说明。
不将这些段落换个标题继续常驻，或默认展开到其他区域。

**异常按对象就近说明：**

| 实际情况 | 展示方式 |
|---|---|
| 全部成功 | 默认概览直接显示状态、进度和结果，不附加重复防御说明；展开后的必要业务解释保留。 |
| 部分文件失败 | 展示失败数量，在具体文件旁显示简短原因。 |
| 主文件成功、字幕失败 | “主文件已整理；字幕复制失败”，保留两者独立结果。 |
| 文件效果无法确认 | “目标文件结果尚未确认”，不能推断为成功或未发生操作。 |
| 处理结束但没有结果记录 | “文件处理已结束，结果未记录”，不能用完成状态补出成功结果。 |

示例短句根据实际记录采用，不虚构字幕失败或目标效果。异常若已有合法下一步，沿用该
入口就近呈现；不增加通用重试。任务状态、进度和结果数量在字号、间距及分组上分清主次，
异常才使用提示色，避免正常成功页常驻警示。技术来源仍按本 Task 的诊断层级可查。
这里删除的是默认概览中重复解释统计或安全机制的段落，不禁止展开后查看识别、命名、
分类等已有业务解释，也不删除帮助理解实际结果的必要信息。

### Observed behavior and root cause

- `OperationsLanding.tsx` 只检查 lifecycle 是否存在就挂载 `RunLifecycleControls`；后者
  对终态也平铺 `knownEffects/nextAction/permission/unavailableReason`，部分直接来自后端
  英文。`RunDetailFacts` 的“更详细证据”又指向本任务本页。
- `RunDetailTabs.tsx` 的 `ProgressCard` 常驻 `basis/successMeans`，执行步骤重复解释来源；
  `RunEvidenceSection`、`PlanEvidenceBlock` 和 `EvidenceSectionDetails` 按内部记录排列，
  拼接英文状态、原始 key/value、技术 ID 与缺失说明。既有部分测试断言“口径”必须可见。
- `AppShell.tsx`/`styles.css` 当前按主页面身份立即替换路由正文，再从 opacity 0.2 做
  200ms 淡入；它与后续数据就绪脱节。隔离 fake API 增加 450ms 读取延迟后，存储淡入约
  280ms 结束，正文约 540ms 才出现；Files 的库/目录读取则分别稍后替换占位。此测量证明
  内容接入断点，不证明用户浏览器所有现场掉帧的原因。
- 自动化列表和创建卡片共享 `operations.automation-lifecycle-authority` 查询；卡片
  `refetchOnMount: "always"` 触发读取，而顶部按钮把包括权限读取在内的 `isFetching`
  合成“刷新中…”。隔离浏览器已复现新建时按钮换节点、正常/禁用切换及宽度约
  57→83→57px，主页面动画未重播。删除入口不等于删除权限读取。

调查基线为上述 Task Base，生产资产 `index-BBNz3k9m.js`/`index-BUcXw9MU.css` 与关闭
报告所列一致；仅本地 fake API 和浏览器观测，未接触用户运行数据库、配置或媒体。
规划前治理 PASS。预存 `mediaflow/.DS_Store` 修改，以及 `.DS_Store`、日志、`15` 和
`output/` 等未跟踪内容保留且不纳入 checkpoint；实施和 B 审查分别重新记录当时完整状态。

### Implementation Scope

只修正 Web 呈现、为其服务的读取状态衔接及直接受影响测试；必要共享呈现复用属于同一
Task。继续使用现有 API/Query/Router 和业务命令，不修改后端、schema、权限/执行规则或
CURRENT 架构边界。按以下顺序完成一个整体候选：

1. **用实际入口固定问题。** 在现有测试中补上终态详情、混合文件结果、长路径/证据、
   慢读取切页和自动化新建闪动场景；读取/动画只观察，不提交业务命令。把旧文案存在断言
   改为对应业务事实与操作可达性断言，保留对独立结果、缺失/未知和重复提交的真实约束。
2. **精简任务正文和操作。** 删除截图说明区、自链接及常驻重复解释；优先呈现任务流程、
   文件结果和待处理项，第三项采用上方用户确认的展示顺序与异常文案规则。已有取消按钮
   按后端 advertised availability 出现，不从状态自行
   推断权限。请求受理、真正取消及结果未知使用短中文反馈；保留在途禁用、版本校验和原
   未决请求核对，关闭重开或切任务不丢上下文，不让隐藏区块阻断必要核对。
3. **重组文件详情。** 按“处理结果→来源/目标→处理经过→需处理原因/已有动作”排列，
   识别、元数据、命名、分类和实际执行用业务名称解释，取自该任务固定历史事实。主文件与
   附件各自展示。成功项无需修复教程；未执行、结果缺失、部分失败、未知效果分别简洁
   标注。技术诊断按需展开，保持计划、日志、审计及有界脱敏 JSON 可达；不能仅把原平铺
   内容整体折叠来代替可读正文，也不从当前配置重新推断旧任务结果。
4. **修正切页到正文就绪的过程。** 复用主页面身份及现有局部加载状态，调整共享淡入与
   占位/正文接入，使慢读取时后续内容也自然呈现，快速/缓存响应直接可用。共享 Shell
   主内容容器保持挂载，保留 Router 管理的 AuthBoundary/Outlet 生命周期及 CURRENT
   主表面透明度过渡边界。不得用整棵路由 keyed 重挂载、旧页错属新 URL、全局 ready
   等待门或人为延时掩盖问题；同页轮询/筛选/详情/目录/弹卡不重播整页动效。若帧间仍有
   明显停顿，再沿实际渲染链路定位直接原因，不引入全局性能重构。
5. **移除自动化常驻刷新按钮。** 删除自动化工作区页头刷新入口及打开新建时该按钮的
   文案、禁用和宽度闪动；不以此扩展为新建/关闭/编辑背景或弹卡的整体稳定性改造。
   保持必要权限/定义读取、已有局部读取失败恢复、操作后读回和未决命令核对。其他弹卡
   表现只按共享改动的实际影响做不退化检查；若出现本次改动引入的退化，在同一 Task
   修正。不取消必要读取、不增加轮询，也不删除其他页面的 `RefreshControl`。
6. **完成整体受影响验证并交接。** 检查桌面/窄屏、键盘、滚动/焦点和实际动态过程；
   更新与实现直接相冲突的页面说明时，只对齐本 Task 的已实现事实，不扩大需求或改写
   历史接受记录。本轮激活只修改 `TASK.md`。Developer 完成后交一个连贯候选及实际结果，
   由独立 B 对完整 Base..Head 验收，六项全部满足后结束。

### Acceptance Criteria

- [ ] **AC-1 / 用户1：** 截图中的“运行控制”说明区不再出现；已结束且无可用动作时没有
  空控制块、权限码或不可用控制清单。真正可用的取消仍易找到，同一次明确操作不重复
  提交；请求中/拒绝/结果未知反馈清楚。结果未知时先核对，关闭重开仍可核对且不盲目
  重发；明确拒绝后可读取最新状态，并在后端仍允许时由用户再次明确操作。
- [ ] **AC-2 / 用户2：** 当前任务详情中不再出现“更详细证据”自链接；从每个文件的详情
  入口仍能查看对应已记录结果、计划解释及关联日志/审计，缺失时如实表示，不串其他文件
  或任务。原有任务级结果导出保持可用，不要求新增逐文件导出。
- [ ] **AC-3 / 用户3：** 正常详情没有“口径”“成功含义”及等价常驻防御段落。无需阅读
  解释教程即可从“流程状态→处理进度→文件结果”读懂当前任务；“处理进度，非成功率”、
  附件单独计数等常驻注释也删除。完成流程配混合结果时，直接呈现实际成功/部分成功/失败
  数量，不追加教程。全成功时默认概览不附加重复防御说明，展开后的必要业务解释保留；
  部分失败在对应文件旁显示原因，主文件成功/
  字幕失败、效果未确认、结束但结果未记录分别按已确认设计简短表达，必要事实和已有
  合法下一步可达；正常与异常的视觉主次清楚。未知不能当零，completed 不补出文件成功。
- [ ] **AC-4 / 用户4：** 文件详情正文能直接回答“哪个文件、发生了什么、去了哪里、为何
  失败或需要处理”。不以原始 key/value、技术 ID 和英文内部状态作为主要信息；主文件/
  附件独立结果和已完成步骤可读，诊断可展开，长名称/路径、无计划/日志/Result 也可用。
  四类决定→分析→摘要→明确继续保留，成功/不确定项不被重放，技术失败不新增通用重试。
- [ ] **AC-5 / 用户5：** 九个现有侧栏主页面连续切换协调；冷/热进入、慢接口、快速往返
  和前后退过程无明显闪白、残影、挤压、长时间淡化或旧页错属。正文实际就绪后的接入也
  纳入可见过程验收，不只证明最初淡入存在；快速读取不被动画拖延。
- [ ] **AC-6 / 补充：** 自动化页头不再有常驻刷新按钮，打开新建时不再出现该按钮的
  文案、禁用或宽度闪动。删除入口不影响必要读取、已有局部重新加载、操作后列表更新
  或未决命令核对。新建/编辑背景及弹卡的其他表现只验证本次改动没有引入退化，不列为
  额外体验修复目标；开关弹卡零业务提交。
- [ ] **AC-7 / 共同兼容：** 主页面内标签、详情深链、切库/目录、开关卡片和轮询不重播
  整页动画。身份/认证续转、401/403 查询隔离、合法列表条件/分页/滚动/回焦、未保存退出
  和在途保护均保留。本次调整区域在桌面及390px可读，不引入新的页级水平溢出；长表格
  可在自身区域滚动。无关页面的既有布局问题不作为新增阻塞；reduced-motion 有稳定静态反馈。
- [ ] **AC-8 / 验收完整性：** 使用同一候选的生产构建查看默认正文、展开详情及切换过程；
  选取直接相关的真实 Python/API/SQLite/Worker 用例核对文件结果与详情读取，取消及四类
  恢复按实际受影响入口补充回归。缺失/拒绝/读失败不冒充空态或成功；未执行的门禁如实
  披露，六项不以局部修复或测试标签代替整体完成。

### Required Tests

遵循 [workflow §6](docs/development-workflow.md#6-test-levels)。T3 依据是 Web/Query/Router
与真实 API 的集成呈现，不改变 mutation、权限、Active、持久化或并发语义。若实际实施必须
触及这些边界，先回 B 重新评估 Test Level，必要时交 A 明确范围；不能静默当作 UI 改动。

**按场景核对覆盖：** 以下六项都须由实际选中的用例或可见交互检查对应到验收结果；
测试名称、匹配数量及命令通过本身不能证明覆盖完整。若筛选遗漏某项，补充或调整该项
直接相关用例；同一用例可覆盖多项，不要求每个场景在所有测试层重复验证。

| 用户要求 | 需核对的场景重点 |
|---|---|
| 1 / AC-1 | 说明区删除、可用取消、单次操作不重复提交、未知先核对及明确拒绝后的合法新操作。 |
| 2 / AC-2 | 自链接删除、文件证据归属/缺失展示、原有任务级导出可用。 |
| 3 / AC-3 | 默认概览简洁、混合/未知/未记录结果准确、展开后的必要业务解释保留。 |
| 4 / AC-4 | 文件详情可读、主文件/附件独立结果、长内容及缺失记录可理解。 |
| 5 / AC-5 | 侧栏主页面切换、实际加载到正文接入、快速往返及同页不重播。 |
| 补充 / AC-6 | 自动化页头刷新删除、新建时无该按钮闪动、必要读取及原有局部恢复不退化。 |

兼容性 AC-7/8 随直接受影响场景核对，不把无关既有问题纳入修复。布局断言检查本次调整
区域的可读性和新引入的溢出，必要时对照 Base 区分原有问题。

#### Developer — affected tests

仓库根运行 `python3 scripts/check_governance.py`、`git diff --check`。以下命令 cwd 为
`web/`；两个详情组件文件是本次直接修改的边界，其余较大的文件按相关用例筛选。新增的
本 Task 场景名称包含 `PATCH-20261107-1`，便于单独执行；选择器不是验收标准，须检查实际
匹配用例覆盖对应行为。测试因实现改名/迁移时，交接中更新精确命令，不得空跑或漏掉原断言。

```sh
npm run test -- run src/features/operations/RunLifecycleControls.test.tsx src/features/operations/RunDetailTabs.test.tsx
npm run test -- run src/features/operations/OperationsInventory.test.tsx -t 'completed mixed run|slow overview|late overview|unknown control outcome|reopened run|PATCH-20261107-1'
npm run test -- run src/shared/ui/AppShell.test.tsx -t 'one routed surface|rapid navigation|narrow navigation|PATCH-20261107-1'
npm run test -- run src/features/operations/AutomationRouter.test.tsx -t 'Active identity|withholds the action|same create dialog|PATCH-20261107-1'
npm run typecheck
npm run lint
npm run format:check
npm run build
npm run test:e2e -- tests/e2e/page-transition.spec.ts
npm run test:e2e -- tests/e2e/operations.spec.ts --grep "terminal run exposes no control|center's own run detail|selected run detail|one item's evidence|opening and closing the centered detail|selected run overview|native action downloads|PATCH-20261107-1"
npm run test:e2e -- tests/e2e/task-center-layout.spec.ts --grep 'detail card item table|PATCH-20261107-1'
npm run test:e2e -- tests/e2e/automation-presentation.spec.ts --grep 'PATCH-20261107-1'
```

上述覆盖终态/可用取消/未知重开、逐项证据、流程与文件结果、返回/认证以及共享切页。
`RunDetailTabs.test.tsx` 与详情浏览器场景验证第三项的全成功、混合结果、主文件成功但
字幕失败、效果未确认及结果未记录；同时核对正文层级和常驻解释已删除，不只断言文字
不存在。示例数量不作为生产固定值或新的统计口径。
`page-transition.spec.ts` 补充冷/缓存/慢读取与正文接入的过程断言，不能只测 opacity 到1；
`automation-presentation.spec.ts` 单独补充本 Task 的页头刷新删除、新建时无该按钮闪动、
必要读取及已有局部失败恢复场景，不预派整个自动化呈现文件。仅改页头不预派创建表单、
编辑/复制/运行一次、普通文件操作等其他模块的完整回归；若实际修改到相关共享组件或
读取/核对链路，再明确列出直接受影响用例和精确命令。不将全库套件改名为受影响测试。

#### B — acceptance and regression

B 独立检查完整 Task Base..候选和六项结果；先复现截图终态、证据正文、慢读取切页及新建
时刷新按钮闪动，再跑门禁。检查并复用自身相同候选/输入的匹配证据；不以 Developer 报告
代替验收。在生产 build 上执行上方静态检查及筛选后的 fake API 用例；真实集成按下面的
直接相关场景执行，不再预派五个完整测试文件。cwd 为 `web/`：

```sh
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts --grep 'the selected run detail reads progress|the eligible run exports|an indeterminate run|a real Manual Organize Worker run|a real standalone pipeline run|PATCH-20261107-1'
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/task-flow.python.spec.ts --grep 'mixed file population|saved flow failure|acknowledged cancellation'
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/automation-create-dialog.python.spec.ts --grep 'creates one disabled definition from the list card and keeps the list context|opening and cancelling the canonical create deep link creates nothing|PATCH-20261107-1'
```

- 上述选定用例核对真实详情/文件结果、已知及未知总数、计划/步骤/导出、流程与文件结果
  分离，以及删除刷新后新建的零额外提交与原有成功读回。可更新因布局变化失效的选择器，
  保留业务/安全断言。全成功、部分失败、无 Result/未知效果等直接需求场景须在相应单元
  或浏览器用例中覆盖，不要求每种状态同时在所有测试层重复证明。
- 同一桌面视口与390px检查任务默认/展开长证据及自动化刷新删除后的新建；九主页面覆盖
  快速连续导航，慢读取选择有代表性的存储及两种库，另验快速/缓存返回、读失败、前后退、认证
  续转、键盘及 reduced-motion。观察动画起始、加载中、正文接入、退出全过程，保留必要
  PNG/trace/过程测量；不把固定毫秒、单一坐标、DOM节点身份或任意FPS作为用户验收标准。
- 路由/开关/只读刷新观测 API 方法，确认没有额外业务提交；取消及未知核对使用隔离
  fixture。四类恢复、编辑/复制/运行一次、并发/丢响应等只对实际受影响入口补充回归，
  不列为额外交付目标。若需扩测，B 记录“具体改动→影响链路→选定用例及命令”，先选
  对应用例；只有明确共享影响不能由选定用例覆盖时才扩大到模块/套件。
- 若两种库普通操作链路实际受影响，使用 `playwright.direct-files.python.config.ts`
  从 `tests/e2e/direct-files.python.spec.ts` 挑选对应操作/状态用例，并记录带 `--grep` 的
  实际命令；不能用 operations harness 代替专用配置，不预派普通文件操作完整套件。
- 本 Task 未改后端/发行/服务生命周期，T3 不预派全量 Python/Web/E2E、wheel 或 Docker
  矩阵；如候选引入超出该判断的共享风险，由 B 给出具体理由调整适用门禁。升为 T4 后
  B 执行 [共享全量门禁](docs/development-workflow.md#shared-full-regression-commands)，不转交 Developer。
- 记录精确候选、命令/结果/skip/限制与本地证据于 `.git/validation-evidence/<sha>/<run>/`；
  不使用生产媒体、用户数据库/凭据或真实外部 Provider/Storage，不宣称本地产物远程可取。

### Non-goals

不新建/重开/关闭 Slice，不增加 Task 状态、恢复类型、后端能力、API/schema 或任务引擎；
不更改统计口径、权限、配置发布、存储变更、历史结果或不确定效果处理。保留 Pause/Job/
独立 Preview 等已退役边界。除上述六项直接需要的共享呈现/读取衔接外，不重做其他页面
业务、设计系统、Router/Auth 或缓存架构；不引入全局就绪注册、新轮询/预加载产品、动画
设置、通用自动重试或媒体回滚。删除自动化页头刷新不删除其他页面刷新或原命令核对。
不扩展为自动化新建/编辑背景或弹卡的整体改造；其他已有功能只验证本次改动不使其退化。

### Developer Completion Report

**READY FOR B REVIEW。** 本轮源码实现 checkpoint 为
`a1b591db5b46f9e5f9bdf8cfa2ddfaef38c34b5e`（Base `fcfc1d2070932e0aaf354d8cc3c3b83f4b67574c`）；
本段文档更新随后单独 checkpoint，源码/测试身份以该实现提交为准。未推送、未部署，不自评 PASS。

**实际变化（六项）**

1. `RunLifecycleControls` 改为任务操作区内的紧凑动作：终态且无可用动作时不渲染空块、权限码或
   不可用控制清单；取消仍按后端 advertised availability 出现，请求中/受理/拒绝/未知均为短中文，
   未知先核对且关闭重开仍保留核对上下文。动作放入 `任务详情/操作记录/导出` 同一操作行。
2. 移除详情中的“更详细证据”自链接；文件证据仍保留执行结果、计划解释、日志、审计及任务级导出。
3. 任务详情按“流程状态→处理进度→文件结果”重排；删除 `口径`、`成功含义`、“处理进度，非成功率”、
   “附件步骤单独计数”等常驻说明。file results 使用成功/部分成功/失败独立值，并在有真实记录时
   就地显示“目标文件结果尚未确认”“文件处理已结束，结果未记录”。附件步骤总数等不再作为默认
   常驻统计出现。
4. 文件证据正文按“处理结果→来源/目标→处理经过→需处理原因”组织，使用文件名标题、中文失败/
   阻塞/步骤业务名称；主文件与每个附件结果独立显示；计划、日志、审计、原始 ID、固定配置和
   捕获的 key/value 收进默认可展开的“技术诊断”。四类恢复面板与导出入口保留。
5. 共享 Shell 仍只应用主页面身份过渡；存储页与两种库页增加内容形状加载占位，真实正文接入时
   只播放一次局部 settle，不重挂路由、不重播整页动画。内容 settle 仅用 opacity，避免固定定位
   弹层被 transform 约束；reduced-motion 下静态呈现。
6. 删除自动化工作区页头常驻刷新入口；打开新建卡片前后均无该按钮的文案/禁用/宽度变化。列表
   读取、权限读取、错误横幅局部刷新、保存后读回和未决命令核对未删除。

**受影响验证（实际执行，cwd `web/`）**

- `python3 scripts/check_governance.py`（仓库根）: PASS；`git diff --check`: PASS。
- `npm run typecheck`、`npm run lint`、`npm run format:check`: PASS。
- `npm run test -- run`: 94 files / 1398 tests passed（含本 Task 的 `PATCH-20261107-1` 单元场景）。
- `npm run build`: PASS（生产资产 `index-Ka6fboag.js` / `index-C3MJm0DP.css`）。
- `npx playwright test tests/e2e/page-transition.spec.ts`: 6 passed（九页切换、慢读取正文接入、
  快速往返/前后退/reduced-motion、弹卡不重播）。
- Operations fake 选中 10 条: 10 passed（终态无控制、混合结果、附件失败、未记录结果、未知效果、
  自链接删除、导出）。
- `task-center-layout` 选中 2 条: 2 passed（含 390px 文件证据可读、无横向溢出）。
- `automation-presentation` 全文件: 3 passed（含页头刷新删除与新建读取）。
- 真实 Python harness 选中用例: operations-inventory 5 passed（详情进度/混合文件结果/未知总数/
  Manual Worker/standalone pipeline/导出）；task-flow 3 passed（混合文件 population、保存失败、
  已确认取消）；automation-create-dialog 2 passed；automation-lifecycle 受影响 2 passed。
- 已更新因布局变化失效的既有断言，保留业务/安全事实与零提交断言；未删除安全约束。

**已知失败/限制（不冒充通过）**

- 单独运行完整 `tests/e2e/operations-inventory.python.spec.ts` 时，
  “new task selection reconciles...” 在既有运行总数期望（`SEEDED_RUN_TOTAL + 1`）处失败；失败
  早于本 Task 任一 UI 断言，本次未改后端、运行总数或该流程，未能在 Base 构建上复跑，故作为
  既有测试顺序/总量期望风险披露，不计为本 Task 修复或通过。其余 41 条真实 Python 用例通过。
- Node fake 未实现 Task 级 recovery 读取，390px 文件证据截图中的恢复面板显示既有
  “Record not found”占位；真实 Python harness 的同一入口可加载，未将其当作产品结果或新增门禁。
- 本轮未运行完整 Python 单元/ruff/全量 E2E 或打包矩阵（T3，按 Task 分工留给 B 的选定验收）。

**剩余风险**

- 取消按钮从独立区块移入 tab 操作行后，桌面/窄屏的触达与焦点顺序依赖既有按钮样式；已由
  单元和选中浏览器用例覆盖存在性/禁用/核对，仍建议 B 在真实取消入口复核窄屏与键盘。
- 内容 settle 只覆盖存储与两种库的代表性慢读取页面；其他主页面仍使用原有占位与共享 Shell
  过渡，未扩大为新的全局就绪机制。

### B Review Result — 2026-11-07 — FIX REQUIRED

独立审查完整范围：`fcfc1d2070932e0aaf354d8cc3c3b83f4b67574c..e8f5669d1e9086515fe77b41f08bfb1df16108f1`，
共 27 个文件，源码候选 `a1b591db5b46f9e5f9bdf8cfa2ddfaef38c34b5e`；其后仅交接文档。
分支 main；审查开始治理 PASS。预存 `mediaflow/.DS_Store` 修改及所有未跟踪日志、
`.DS_Store`、`15`、`output/` 等保留，未读取私有运行配置/数据库/媒体。本轮只修改 TASK.md。
Slice50 仍 PASS / CLOSED，独立 Task 不重开或改写其接受记录。

**交付核对：** 运行控制说明区和自链接已删除，流程→进度→文件结果的层级、自动化页头刷新
删除、存储/两种库正文接入已有实现与通过证据。文件证据的正常成功正文及业务处理解释
仍不满足 AC-3/4，故六项尚未整体完成。AC-5/7/8 的其余指定验收留待修正候选完成；
以下是范围内的必需结果，不增加产品能力、后端修改或新的恢复流程。

#### 阻塞项及 Developer 开发指导

**B-01 / P1 — 成功文件的证据同时把它说成技术失败，正文仍有内部字段和常驻说明。**

完整复现：使用现有 `playwright.python.config.ts` 对应的隔离 Python harness，沿现有
`operations-inventory.python.spec.ts` 的 `run-manual-organize` 场景产生真实 Worker 整理结果；
从任务中心刷新→点击 `One.2001.mkv` 的任务名称→查看证据。
正文先显示“文件已整理 / 成功 / 已验证完成”，随后却显示：
`第 1 次执行：SUCCESS`、`未继续原因：replay_not_offered: item has a terminal outcome`，
再平铺 `completed / verified_complete / unsafe` 和“这是一个技术失败条目……”整段说明。
用户无法判断成功文件是否还需要修复。后端已正确记录成功；问题在证据的呈现组合。

开发指导：

1. 在 `RunDetailTabs.tsx` 的证据正文和 `TaskItemRecoveryPanel.tsx` 的呈现边界共同处理。
   根据现有真实结果区分成功、实际失败、未知效果和四类待处理，不把“终态不提供重放”当成
   业务失败/需处理原因。正常成功正文只保留必要结果和事实；只读 checkpoint、拒绝码及
   安全机制说明进入诊断，不默认显示修复教程。已有待处理、在途和未知命令核对保持可见。
2. 对真实接口返回的 Result 状态（本例为大写 `SUCCESS`）使用正确中文业务名称；正文中的
   已知操作使用业务名称，原 token 保留在诊断。无需增加泛化转换框架或改后端枚举。
   附件仍按各自结果呈现，失败/未执行/未知不能合并为成功。
3. 在真实 Worker 成功旅程补断言：默认文件证据没有错误的“技术失败”定性、英文拒绝码及
   常驻安全教程；实际失败/未知仍保留对应事实。若改变恢复面板的呈现，选取已有四类
   决定→分析→摘要→明确继续及未决核对用例，证明动作没有被折叠隐藏或重新提交。

**B-02 / P1 — “处理经过”仍缺少可读的识别、元数据、命名、分类解释。**

同一真实入口中，目标为 `Movies/Movies/Anime/One (2001) [tmdbid-101]/One (2001).mkv`，
“处理经过”只有创建目录、移动及源目录清理状态。用户看不出匹配到什么作品、如何命名、
为什么归入 Anime。展开技术诊断后仍主要是原有英文状态、策略 ID 和 key/value。
实际响应已经包含 `planEvidence.plan.analysis` 的 metadata/naming/classification：作品 One
(2001)、命名目录/文件名、分类规则 japanese-animation 及电影/动画/日本匹配证据。
这不是缺少 API 数据，也不能仅把原平铺内容整体折叠就算完成本 Task 第 3 步。

开发指导：

1. 从该条目已捕获的 plan/analysis/evidence 提取短业务说明，放进“处理经过”：识别/作品匹配、
   命名结果、分类到目标库/相对路径的依据，以及实际存储步骤。按实际可用证据显示，缺失
   如实说明；不查询当前配置/Provider 来补算旧任务，也不编造命中理由。
2. 复用现有类型和数据，保留 RecognitionType C、Naming A、Classification A 的独立身份；
   原始计划、日志、审计及 ID 继续在诊断可查。不要增加后端能力或新的状态/恢复入口。
3. 用现有真实 Manual Worker 场景核对：用户从任务列表打开文件证据，不展开原始诊断也能
   读懂作品、名称及 Anime 归类依据；缺少计划的历史条目仍准确。桌面及 390px 检查长路径，
   并保持附件独立结果、导出、关闭回焦和四类处理可用。

#### B 本轮实际验证与限制

生产 build PASS（保留大 chunk 提示），资产 `index-CCbQLlCe.js` / `index-C3MJm0DP.css`。以下 cwd 为 web/：

- `npm run test -- run src/features/operations/RunLifecycleControls.test.tsx src/features/operations/RunDetailTabs.test.tsx`：
  **2 files / 26 PASS**，含取消反馈、未知核对和混合结果。
- `npx playwright test tests/e2e/operations.spec.ts tests/e2e/task-center-layout.spec.ts tests/e2e/page-transition.spec.ts tests/e2e/automation-presentation.spec.ts --grep 'PATCH-20261107-1|one item.s evidence|all nine sidebar' --output=../.git/validation-evidence/e8f5669/B-review/fake-results --trace=on`：
  **7 PASS**，涵盖九页、存储慢读、混合/未知结果、390px 和刷新删除。
- `npx playwright test --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts --grep 'the selected run detail reads progress|a real Manual Organize Worker run|a real standalone pipeline run' --output=../.git/validation-evidence/e8f5669/B-review/python-results --trace=on`：
  **3 PASS**，真实详情、计划、导出与重启读回；通过用例未断言本轮发现的可读性缺口。
- 独立原生交互复现上述真实 Manual Worker 旅程，检查响应、默认/展开正文并查看桌面 PNG，
  确认 B-01/B-02。没有构造新的产品入口或使用用户运行数据。

本地证据 `.git/validation-evidence/e8f5669/B-review/`：build/unit/fake/python 日志、
各浏览器 trace/截图、`native-evidence-default.png`、`native-evidence.json`（默认/展开正文与
真实 API 响应）。本地产物不宣称远程可取。测试及浏览器复现执行累计不足 1 分钟，
审查/阅读/分析/写回耗时超过该值，测试占本轮总时间低于 50%。未执行的其余静态门禁、
选定集成/兼容验收不宣称通过；已有明确阻塞，按 workflow §6 在昂贵门禁前返回修正。
Developer 披露的完整 inventory 测试总数失败未经 Base 复现，本轮既不认定为既有问题，
也不据此新增阻塞。全量 Python/Web/E2E、wheel/Docker 未运行，当前 T3 无新增适用理由。

**Next Action：Developer 在同一 Task 修正 B-01/B-02，运行新增/修改及直接受影响测试，
交接新 checkpoint；B 继续审查完整原 Base..新候选并完成剩余适用验收。**
