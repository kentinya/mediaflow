# NO ACTIVE IMPLEMENTATION TASK

Slice50 已由 A 于 2026-11-07 独立最终审查 **PASS / CLOSED**；原八项要求及自动化新建/编辑
稳定性补充全部接受。没有活动实施 Task；下一步 **A SELECTS THE NEXT LARGE SLICE**，另行选择。
本次关闭不自动实施、推送或部署。用户于 2026-11-07 授权将下方六项调查结果合为一个独立
Task 并开始规划，随后确认第三项的具体展示设计并授权写入 Task；本文件下方为已规划草案，
未授权实施。流程遵循
[Development Workflow](docs/development-workflow.md)。

```text
Last Task: 50.4 — V2 侧栏主页面切换体验
Task Decision: PASS (B)
Task Reviewed Base: ea8aad6166d60c5524aaeb4a46f5c7ebb7ccb749
Task Reviewed Head: ab5589340b7a9c72f30b0cbc955a95924a089b87
Slice: 50 — PASS / CLOSED
Slice Base: 6cd881f0311c9e53bfc6b0ab754bfbe9acefbfd0
Slice Implementation Head: 6b0927328a7bf0873faffce9cb38007fd4607764
B Closure Packet: 60798c3e50fdc62a6d46b6ee439e2406751ecfd3:TASK.md
Development Authorization: NONE
Next Action: A SELECTS THE NEXT LARGE SLICE
```

完整 B 收尾包、逐项结果、原始日志/资产摘要、历史 Task/fix 指针及失败/skip/限制保留于
[不可变报告](https://github.com/kentinya/mediaflow/blob/60798c3e50fdc62a6d46b6ee439e2406751ecfd3/TASK.md)，不以本摘要替代。
A 的完整范围、独立复验、接受及延期见 [SLICE.md](SLICE.md#final-validation-closure-packet-and-a-final-review)；
[Progress](docs/progress.md) 记录原 Base/Head 与关闭事实。原两轮 Task50.4 阻塞与 B 测试耗时
比例偏差继续披露；未将过程偏差、外部服务 skip 或未运行的 Docker 矩阵记作通过。

---

## Planning-only draft — PATCH-20261107-1 — V2 任务详情可读性与导航稳定性修正

**仅规划，尚无活动实施 Task。** 用户先要求调查、不改文档代码，随后明确要求“合到一个
Task 吧，开始规划”；本次授权仅将该范围写为一个计划，不开始 Developer 实施、调用其他
角色、推送或部署。实施获授权时再用本草案替换顶部无活动任务通知；开始前重跑治理并核对
Base 后的实际变更，不能静默换 Base 或沿用过期调查。

Authority: 用户本次六项界面修正及合并规划指令；独立修正路径遵循
[workflow §3.1](docs/development-workflow.md#31-independent-minor-bugs)。
Slice50 是相关已接受基线，不是 Parent；不重开它，也不改原 Base/Head/关闭结论或
SLICE/Roadmap/Progress。B/Developer 分别读取相应 [角色经验](AGENTS.md#testing-and-roles)。

```text
Task ID: PATCH-20261107-1
Task Type: STANDALONE MINOR BUG
Parent Slice: NONE
Status: PLANNED
Task Base: fcfc1d2070932e0aaf354d8cc3c3b83f4b67574c
Difficulty: High
Test Level: T3
Planner / Reviewer: B
Working Branch: main
Development Authorization: NONE
Next Action: USER AUTHORIZES IMPLEMENTATION OF THIS SINGLE TASK
```

### Goal

操作者从左侧栏切换主页面、打开任务详情及文件证据、打开自动化新建/编辑卡片时，能够
直接读懂结果和可用操作，并看到连贯、稳定的加载与切换过程。六项在同一 Task 内实施、
交接和独立 B 审查，修正留在同一 Task 的 fix loop，不另拆后续 Task。

| 用户范围 | 本 Task 的明确结果 |
|---|---|
| 1. 删除截图中的运行控制区 | 删除说明型“运行控制”整块；真实可用的取消操作移到任务操作区，必要的进行中/失败/结果待核对反馈就近显示。 |
| 2. 更详细证据难读 | 删除详情中链接回同一任务详情的“更详细证据”字段；实际文件结果、计划解释、日志、审计及导出保持可达。 |
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
| 全部成功 | 直接显示状态、进度和结果，不附加说明段落。 |
| 部分文件失败 | 展示失败数量，在具体文件旁显示简短原因。 |
| 主文件成功、字幕失败 | “主文件已整理；字幕复制失败”，保留两者独立结果。 |
| 文件效果无法确认 | “目标文件结果尚未确认”，不能推断为成功或未发生操作。 |
| 处理结束但没有结果记录 | “文件处理已结束，结果未记录”，不能用完成状态补出成功结果。 |

示例短句根据实际记录采用，不虚构字幕失败或目标效果。异常若已有合法下一步，沿用该
入口就近呈现；不增加通用重试。任务状态、进度和结果数量在字号、间距及分组上分清主次，
异常才使用提示色，避免正常成功页常驻警示。技术来源仍按本 Task 的诊断层级可查。

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
5. **移除自动化常驻刷新并稳定背景。** 只移除自动化工作区页头刷新入口；检查新建/关闭
   和共享编辑路径上的背景切换，消除可见闪动。保持表单真实权限/定义读取、失败时局部
   重新加载、创建/保存/复制/运行一次后的已有读回以及未知发布/命令核对；不以放宽缓存
   权限、取消必要读取或增加后台轮询替代按钮。共用 `RefreshControl` 的其他页面保留。
6. **完成整体受影响验证并交接。** 检查桌面/窄屏、键盘、滚动/焦点和实际动态过程；
   更新与实现直接相冲突的页面说明时，只对齐本 Task 的已实现事实，不扩大需求或改写
   历史接受记录。本轮规划只修改 `TASK.md`。Developer 完成后交一个连贯候选及实际结果，
   由独立 B 对完整 Base..Head 验收，六项全部满足后结束。

### Acceptance Criteria

- [ ] **AC-1 / 用户1：** 截图中的“运行控制”说明区不再出现；已结束且无可用动作时没有
  空控制块、权限码或不可用控制清单。真正可用的取消仍易找到且仅提交一次；请求中/拒绝/
  结果未知反馈清楚，未知结果关闭重开仍可核对，核对前不重新提交。
- [ ] **AC-2 / 用户2：** 当前任务详情中不再出现“更详细证据”自链接；从每个文件的详情
  入口仍能查看对应结果、计划解释、关联日志/审计及导出，不串其他文件或任务。
- [ ] **AC-3 / 用户3：** 正常详情没有“口径”“成功含义”及等价常驻防御段落。无需阅读
  解释教程即可从“流程状态→处理进度→文件结果”读懂当前任务；“处理进度，非成功率”、
  附件单独计数等常驻注释也删除。完成流程配混合结果时，直接呈现实际成功/部分成功/失败
  数量，不追加教程。全成功没有说明段落；部分失败在对应文件旁显示原因，主文件成功/
  字幕失败、效果未确认、结束但结果未记录分别按已确认设计简短表达，必要事实和已有
  合法下一步可达；正常与异常的视觉主次清楚。未知不能当零，completed 不补出文件成功。
- [ ] **AC-4 / 用户4：** 文件详情正文能直接回答“哪个文件、发生了什么、去了哪里、为何
  失败或需要处理”。不以原始 key/value、技术 ID 和英文内部状态作为主要信息；主文件/
  附件独立结果和已完成步骤可读，诊断可展开，长名称/路径、无计划/日志/Result 也可用。
  四类决定→分析→摘要→明确继续保留，成功/不确定项不被重放，技术失败不新增通用重试。
- [ ] **AC-5 / 用户5：** 九个现有侧栏主页面连续切换协调；冷/热进入、慢接口、快速往返
  和前后退过程无明显闪白、残影、挤压、长时间淡化或旧页错属。正文实际就绪后的接入也
  纳入可见过程验收，不只证明最初淡入存在；快速读取不被动画拖延。
- [ ] **AC-6 / 补充：** 自动化页头不再有常驻刷新按钮；新建、关闭、重复打开及共享编辑
  路径的背景不因权限读取出现按钮/布局闪动。读取失败的局部重新加载、操作成功后的
  列表更新和未决命令核对仍可用；开关弹卡零业务提交，不跳过权限/定义读取。
- [ ] **AC-7 / 共同兼容：** 主页面内标签、详情深链、切库/目录、开关卡片和轮询不重播
  整页动画。身份/认证续转、401/403 查询隔离、合法列表条件/分页/滚动/回焦、未保存退出
  和在途保护均保留；桌面及390px无页级溢出，reduced-motion 有稳定静态反馈。
- [ ] **AC-8 / 验收完整性：** 使用同一候选的生产构建查看默认正文、展开详情及切换过程；
  真实 Python/API/SQLite/Worker 旅程证明结果、取消和四类恢复继续成立。缺失/拒绝/读失败
  不冒充空态或成功；未执行的门禁如实披露，六项不以局部修复或测试标签代替整体完成。

### Required Tests

遵循 [workflow §6](docs/development-workflow.md#6-test-levels)。T3 依据是 Web/Query/Router
与真实 API 的集成呈现，不改变 mutation、权限、Active、持久化或并发语义。若实际实施必须
触及这些边界，先回 B 重新评估 Test Level，必要时交 A 明确范围；不能静默当作 UI 改动。

#### Developer — affected tests

仓库根运行 `python3 scripts/check_governance.py`、`git diff --check`。以下命令 cwd 为
`web/`，使用现有测试文件扩充真实场景；若新增直接相关测试文件，将其明确加入交接命令。

```sh
npm run test -- run src/features/operations/RunLifecycleControls.test.tsx src/features/operations/RunDetailTabs.test.tsx src/features/operations/OperationsInventory.test.tsx src/features/operations/AutomationCreateDialog.test.tsx src/features/operations/AutomationRouter.test.tsx src/shared/ui/AppShell.test.tsx src/shared/navigation/destination-model.test.ts
npm run typecheck
npm run lint
npm run format:check
npm run build
npm run test:e2e -- tests/e2e/operations.spec.ts tests/e2e/task-center-layout.spec.ts tests/e2e/page-transition.spec.ts tests/e2e/automation-presentation.spec.ts
```

上述覆盖终态/可用取消/未知重开、逐项证据、流程与文件结果、返回/认证以及共享切页/弹卡。
`RunDetailTabs.test.tsx` 与详情浏览器场景验证第三项的全成功、混合结果、主文件成功但
字幕失败、效果未确认及结果未记录；同时核对正文层级和常驻解释已删除，不只断言文字
不存在。示例数量不作为生产固定值或新的统计口径。
`page-transition.spec.ts` 补充冷/缓存/慢读取与正文接入的过程断言，不能只测 opacity 到1；
`automation-presentation.spec.ts` 补充页头刷新删除及新建/关闭不闪动、局部读取失败恢复。
若修改共享操作/附件/认证/弹卡或两种库组件，再跑其直接受影响测试，例如
`LibraryFileOperationsDialog.test.tsx`、`AttachmentResults.test.tsx`、`AutomationListCopy.test.tsx`
和 `AutomationListRunOnce.test.tsx`；不将全库套件改名为受影响测试交给 Developer。

#### B — acceptance and regression

B 独立检查完整 Task Base..候选和六项结果；先复现截图终态、证据正文、慢读取切页及新建
闪动，再跑门禁。检查并复用自身相同候选/输入的匹配证据；不以 Developer 报告代替验收。
在生产 build 上执行上方静态检查和四个 fake API 浏览器文件，以及以下真实集成，cwd 为 `web/`：

```sh
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts tests/e2e/operations-task-center-visual.python.spec.ts tests/e2e/task-flow.python.spec.ts tests/e2e/automation-create-dialog.python.spec.ts tests/e2e/automation-lifecycle.python.spec.ts
```

- 真实集成核对四类恢复、未知/缺失结果、主文件/附件独立结果、历史计划/导出和取消；
  自动化核对创建/编辑、过期/拒绝权限、并发冲突、丢响应核对与成功后的列表读回。
  不同布局可以更新选择器，但须保留原业务/安全断言。
- 同一桌面视口与390px检查任务默认/展开长证据及自动化新建/编辑；九主页面覆盖快速连续
  导航，慢读取选择有代表性的存储及两种库，另验快速/缓存返回、读失败、前后退、认证
  续转、键盘及 reduced-motion。观察动画起始、加载中、正文接入、退出全过程，保留必要
  PNG/trace/过程测量；不把固定毫秒、单一坐标、DOM节点身份或任意FPS作为用户验收标准。
- 路由/开关/只读刷新观测 API 方法，确认没有额外业务提交；进行中取消与未知核对使用
  隔离 fixture。若两种库普通操作共用控件受影响，另执行
  `npm run test:e2e -- --config=playwright.direct-files.python.config.ts tests/e2e/direct-files.python.spec.ts`
  核对原页面归属和独立结果；不能用 operations harness 代替该专用配置。
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

### Developer Completion Report

未实施。授权后由 Developer 填：完整 checkpoint SHA、READY FOR B REVIEW、实际变化、
受影响测试结果/已知失败和剩余风险；完整 B 验收待独立审查，不自评 PASS。

### B Review Result

未审查；本轮只完成一个规划草案。实施后按 workflow 对同一 Task 给 PASS 或 FIX REQUIRED，
记录精确 Base..Head、实际验收结果与六项是否全部满足。独立修正 PASS 后恢复简洁的
NO ACTIVE IMPLEMENTATION TASK 通知并保留固定审查指针；不改 Slice50/Roadmap/Progress。
