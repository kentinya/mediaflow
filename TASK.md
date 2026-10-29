# Task PATCH-20261029-4 — 整理规则页头与概览展示修正

用户于 2026-10-29 明确要求激活本 Task；已从规划草案提升为正式独立 Task，范围可交 Developer 实施。
当前状态为 IN PROGRESS，Developer 已开始本 Task 实施，不自动启动其他角色或 agent，
不授权推送或部署。生命周期遵循 [Development Workflow §3.1](docs/development-workflow.md#31-independent-minor-bugs)。

Authority：用户要求修正现有整理规则页，并明确以现行任务中心为标题/刷新排版基准。
用户随后明确认可图示八分类卡片这一行的 UI 与交互，本 Task 保留该行，不改成任务中心标签。
用户进一步认可除概览外七类清单现有的排版和格式；七类清单内部 UI/交互均为保留项，
包括本地搜索及状态筛选。不得再以“统一风格”重排清单或修改其边框、字号、间距、表格密度。
[AGENTS.md](AGENTS.md) 与 [Development Workflow](docs/development-workflow.md) 约束范围与交付。
角色经验：[B](docs/agent-experience/task-planner-reviewer.md)、
[Developer](docs/agent-experience/developer-implementation-role.md)。

```text
Task ID: PATCH-20261029-4
Task Type: STANDALONE MINOR BUG
Parent Slice: NONE
Status: IN PROGRESS
Authorization: USER-ACTIVATED TASK — 2026-10-29
Task Base: 739a9c49a39187f1cf48aa3a62c241aaea22d9a9
Difficulty: Medium
Test Level: T2
Planner / Reviewer: B
```

上一独立 Task `PATCH-20261029-3` 已由 B 独立评审 **PASS**：
`542496a8cb9b69e5146fe8c702cd6f695752accd..74241e6cc2f76be0f071ff8e497a232df2f06bbc`。
完整验收记录保留在 `92807b0a:TASK.md`，现行任务中心要求保留在 `739a9c49`。
Slice46 仍为 **PASS / CLOSED**；其 Base、Implementation Head、SLICE、Roadmap 与 Progress 不变。

## Goal

用户从侧栏进入 /ui-v2/rules，先看到与任务中心一致的内容区页头，再选择概览或规则分类。
修正页头与刷新位置，移除顶栏重复搜索、内部序号常驻展示和正常态设置跳转；
仅对概览内部做有限的信息精简与排版整理。八分类导航及七类清单的现有设计完整保留，
维持规则管理、精确 Active、只读导航及失败恢复语义。

- **Entry / state：** 侧栏、分类深链及编辑返回均到达正确清单；可读工作区只有一个页面主标题。
  概览、七类清单、加载、空配置及只读用户采用统一骨架；鉴权/读取失败沿用现有共享边界。
- **Action：** 分类切换、清单搜索/状态筛选与页头刷新；
  现有添加、复制、编辑、启停、移除、对象测试与完整流程检查保留原权限与语义。
- **Success：** 搜索范围清楚、当前分类明确，刷新读回实际配置并保留当前分类、关键字与状态筛选。
  只有原有显式保存/命令才可发布配置，布局操作不创建候选或工作。
- **Failure / recovery：** 无 Active、读取失败、异常响应、权限不足和未知保存结果继续明确区分；
  保留可修正输入、未保存提示及条件式设置恢复。刷新不重发保存，也不把旧缓存冒充最新 Active。

适用要求：`UX-001/002/004/007/008`、`V2-UX-001–004`、`V2-SHELL-001`、
`V2-RULES-001/002/004/006–009`、`V2-SAFE-001`。
完整旅程以 [Recognition and rules](docs/product-experience.md#recognition-and-rules) 为准；
[CURRENT Rules architecture](docs/architecture.md#current--v2-organizing-rules-workspace-slice-41)
中的读取、保存、发布和分析边界不变。Slices41/44/46 仅为已接受基础，不是本 Task 的父 Slice。

## Observed Gap and Baseline

已在同一浏览器视口观察任务中心、整理规则概览、类型策略/命名清单和自动化页，并核对源码：

- AppShell.tsx 为 /rules 单独组合标题、搜索和账户同行的加高顶栏；任务中心在内容区拥有
  独立标题/说明与右侧刷新。规则页错位来自既有特殊分支。
- RulesWorkspacePage.tsx 在分类导航之后插入 Active 序号、设置链接及刷新行；
  顶栏搜索与清单搜索共用 useRulesSearch，概览还显示禁用搜索及重复解释。
- styles.css 为 Rules 提供独立顶栏几何；概览有重复搜索提示及偏重的技术说明。
  用户已认可八分类卡片与七类清单的现有排版，它们及其响应式规则不作为待改问题，
  清单的外层面板/内层表格边框也不作为本 Task 的“冗余边框”删除。
- 概览直接展示英文关系节点；类型绑定直接展示英文摘要与 ID。流程节点可做有限中文文案调整，
  但策略名称解析与引用展示增强不作为本次布局修正的实现或验收要求。
- Shell/Rules 单元测试、rules-readiness.spec.ts 和 rules_workspace_browser_proof.py
  锁定了旧页头、双搜索、设置链接或刷新文案，需要同步修正。

规划及激活前预检：`python3 scripts/check_governance.py` PASS；分支 main，HEAD 为上述 Task Base；
初次规划无已跟踪文件改动，激活前仅 TASK.md 为本会话草案改动，工作区/Git 可写。
既有未跟踪项包括各级 .DS_Store、.mgmt.log、.t.log、
.t_test_*.log、15、两张自动化参考图及 output/imagegen/slice45-task-center-v1.zip；
均不纳入 Task，不移动、清理或暂存。实施前重新记录实际 status。

## Implementation Scope

页头及顶栏改动仅针对 /ui-v2/rules 工作区及其 section 查询，不套用到 /rules/edit 等独立路由。
“唯一主标题”只指工作区页级“整理规则”，不删除分类标题、弹窗标题或正常侧栏入口。
“概览零搜索/清单一个搜索”指未打开表单或完整流程检查时的工作区清单搜索，
不限制既有编辑器/测试面板的输入，也不借此移除其他页面的搜索。

1. **统一页头与刷新。**
   移除 Rules 专属顶栏标题/搜索/说明组合，公共顶栏保留通知和账户。
   内容区左上放“整理规则”，下一行放简短说明（建议“管理识别类型、规则和整理策略。”）；
   页头右侧放“刷新”，请求中显示“刷新中…”并阻止重复点击。
   桌面对齐 Task Base 任务中心的内容边界、主标题字号/行高、说明色阶及页头间距；
   只复用所需样式，不改任务中心，不复制任务统计卡片。
   窄屏允许页头自然换行，保持标题/说明与刷新可见可用，不强制桌面同一行几何。
   可读工作区在正常、加载、空配置及无 Active 分支采用同一页头，主内容无重复位置标题。
   未连接、401/403 及请求失败继续由现有共享边界处理，不为展示页头绕开鉴权或改变缓存清理；
   允许错误边界使用现有错误标题/只读重试，不要求所有失败状态强行渲染业务页头与刷新。
   正常读取成功的刷新仅更新规则工作区数据，保留当前分类、关键字与状态筛选，
   不额外打开/关闭表单或重置未保存输入。读取失败或鉴权失效时，允许现有共享边界接管画面；
   输入恢复沿用既有同身份草稿机制，不要求表单始终挂载，也不为保留输入绕过身份/权限清理。
   不承诺浏览器整页重载后持久化本地筛选，分类仍按既有 URL 语义恢复。

2. **收拢配置状态信息。**
   删除规则内容区正常态工具行中的 Active 序号及“前往系统设置”链接。
   这不是全局禁用 Active 文案或设置链接；侧栏设置、必要失败证据及异常恢复入口保留。
   不为迁就序号增加“配置版本”折叠区或常驻 Active 徽标；版本/摘要等诊断沿用既有系统设置。
   后端精确 Active 校验、保存时的版本约束和必要失败证据不删除，也不改变系统设置诊断能力。
   读取失败沿用现有错误边界，不将旧数据标为已刷新；不新增保留旧数据的缓存/陈旧状态产品。
   无 Active/配置不可用状态仍提供上下文设置恢复入口及原 returnTo/returnSection 回程；
   Settings→规则族链接和正常侧栏设置入口保持可用。

3. **保留分类导航，消除重复搜索。**
   概览、类型策略、识别类型、识别规则、元数据策略、命名规则、分类规则、整理策略的
   卡片设计、图标、名称/副说明两行文字、顺序、分隔线、圆角、选中背景、悬停/聚焦样式与
   点击切换交互保留；URL、当前项语义及既有响应式规则不变，不主动调整内部字号/间距。
   页头迁移可调整整行位置、外围间距及跟随内容容器自然变化的宽度；不改为紧凑标签、
   横向滚动条或新导航组件。以相同可用宽度下原卡片的设计一致性验收，不要求截图逐像素相等，
   不借“整体协调”改变这行设计。窄屏沿用已有分类布局。
   删除公共顶栏规则搜索后，七类清单现有本地搜索框及状态筛选原位保留，样式不变；
   概览不渲染搜索框或“不支持搜索”提示。
   保持现有匹配字段、状态筛选规则、换分类清空关键字、URL/前进后退及草稿恢复行为；
   不新增跨分类搜索。移除仅服务顶栏的 Rules 搜索接线时，不改变 Files/Storage 搜索。

4. **仅整理概览，保留七类清单。**
   概览范围限于：移除重复搜索解释、压缩重复技术说明、改善概览内部文字层级与分区留白，
   将已知关系节点映射为现有中文业务名称。保持服务端关系顺序及识别身份含义，
   不新增流程图交互、统计维度或页面功能。真实总数/启用数、配置缺口、补齐入口和
   独立完整流程检查继续保留且易于找到，不以美化为由删减失败证据或必要操作说明。
   概览按“规则关系 → 数量概况 → 配置缺口（有缺口时）→ 完整流程检查”组织：
   规则关系保留“规则关系概览”标题，简述识别规则确定媒体类型、类型策略关联后续策略；
   已有流程节点使用中文业务名称，窄屏自然换行。
   数量概况保留七类统计卡片及进入对应清单的行为，按“分类名称 → 总数 → 已启用数量”
   明确信息层级，使用真实数据，不增加统计指标。
   配置缺口仅按真实缺口/缺失对象显示，保留前往相应分类和既有补齐顺序指导；
   正常状态不新增成功提示横幅。
   完整流程检查置于概览底部并与统计适当分隔，说明可采用“检查当前配置下的识别、元数据、
   命名、分类和整理计划，不执行文件整理。”；保留原按钮及后续交互，不自动发起检查。
   七类清单完整保留现有分类标题/说明、左侧添加、右侧搜索/状态筛选、外层卡片、
   表格边框/列/行密度、名称/ID/摘要、状态标记、引用影响与行操作样式及布局。
   各族由后端权限决定的操作差异保留，不强行补齐按钮，不增加“更多”菜单。
   只允许页头和原 Active 工具行调整导致清单整体位置/外围间距及容器宽度自然变化；
   不重排清单内部、不主动改内部字号/圆角/边框/间距，窄屏沿用现有布局规则。
   概览局部样式不得外溢到分类导航、七类清单、抽屉或编辑页；
   不新增策略名称解析、引用关联查询或运行时绑定/就绪推导，不重写后端摘要。

5. **更新受影响测试和验收脚本。**
   将旧同行标题/双搜索/常驻设置断言替换为本 Task 可见结果断言；保留分类卡片及七类清单
   内部的样式/交互检查，仅更新相对新页头的位置及已移除顶栏搜索的断言。
   rules_workspace_browser_proof.py 当前报告标识与页头比较说明指向本 Task，
   明确分类卡片及七类清单沿用原设计；
   历史参考图保持原样，未改变的表单验收继续保留。不得以旧参考图覆盖本次明确选择，
   也不得删除零写入、精确 Active、草稿/拒绝保存恢复等无关安全断言。
   产品实现限于 Web；允许修改直接受影响测试、隔离夹具及验收脚本，
   不改 Python 业务、API schema、配置模型、运行时或媒体操作。

优先文件：web/src/shared/ui/AppShell.tsx、styles.css、
web/src/features/rules/RulesWorkspacePage.tsx、web/src/entities/rules/rules-workspace.ts
及直接测试。允许必要的 Rules 展示 helper，不进行全局组件体系重构。

## Acceptance Criteria

- [ ] AC-1：可读工作区的正常/加载/空配置/无 Active/只读用户状态有唯一内容区主标题；
  桌面标题层级、说明和刷新对齐方式参照任务中心，公共顶栏无规则标题或规则搜索。
  只检查工作区页级标题，不删除清单标题/侧栏入口，不给独立编辑路由加工作区标题；
  窄屏允许页头换行，不要求与桌面保持同一行位置。
  未连接、401/403 及读取失败继续使用既有共享边界，不因页头迁移暴露受限内容。
- [ ] AC-2：规则内容区的正常态工具行不再常驻 Active 序号或设置跳转，也不新增版本面板；
  侧栏设置、系统设置诊断及异常恢复入口保留。正常成功刷新保留当前分类/关键字/状态筛选及
  未保存输入，请求中有反馈且防重复点击；失败不显示成功刷新、不重发保存/命令。
  失败/鉴权分支可沿用既有画面切换及输入恢复/清理，不要求表单一直可见；
  成功保存后的清单仍由既有流程读回真实新版本。
- [ ] AC-3：八分类卡片的原设计、文字/图标、交互、响应式规则及深链保留；
  在相同可用宽度下对照 Task Base 验收设计一致性，容许整体位置、外围间距和容器适配，
  不以像素完全相等或指定组件实现作为唯一门禁。
  默认未开表单/测试面板的概览无清单搜索，清单仅一个本地搜索；不误删其他上下文输入。
  搜索/清除/状态过滤及换分类行为正确，
  非法 section 安全回到概览且不回显危险输入。
- [ ] AC-4：概览无重复搜索解释，技术说明精简，流程使用中文业务名称且不改变关系含义；
  按规则关系、数量概况、条件式配置缺口、底部完整流程检查形成清晰分区；
  真实统计、卡片进入清单、缺口/补齐入口及完整流程检查原交互保留，不新增指标或自动检查。
  七类清单内部 UI 与 Task Base 相同可用宽度
  下的设计一致：标题/说明、添加/筛选、面板/表格、状态、引用与行操作保持原样，
  仅整体位置/外围间距及容器适配可变化。不改变现有数据/引用语义或各族操作差异；
  C 复用 A 策略的既有身份回归覆盖保留。
- [ ] AC-5：无 Active、坏响应、读取失败及权限不足不伪装为空清单或正常生效；
  适用的设置恢复/返回原分类仍能完成，拒绝/未知保存的提示、输入及恢复能力保留。
- [ ] AC-6：默认进入或切换分类不自动打开抽屉/编辑；添加/复制、编辑返回、未保存提示、
  引用确认及对象测试的既有行为与权限不因布局迁移改变，错误边界例外按 AC-2 处理；
  刷新不重试保存、发布、Provider 测试或媒体工作。
- [ ] AC-7：实看 1536×1024、760×1024、390×844 截图，无整页横向溢出、内容遮挡；
  表格必要滚动限于容器内，键盘可达所有分类、搜索和刷新且焦点可见；
  分类导航和七类清单沿用既有响应式布局。此项检查本次调整引入的回归，
  不借验收重做保留区的原有设计或修复无关历史问题。
- [ ] AC-8：任务中心既有页头/筛选、Files/MediaLibrary/Storage 搜索及 Rules Edit 独立标题
  无回归；隔离夹具初始化完成后的只读导航/搜索/刷新不改变 Active revision/digest、
  激活次数或 Task/Job 数量。该零写入断言不套用于另行显式执行的保存/启停/移除旅程。

## Required Tests

按 [workflow §6](docs/development-workflow.md#6-test-levels) 分工。
本 Task 是 Web 展示/只读交互修正，T2；用聚焦浏览器证据核对共享 Shell 影响，
不要求全仓 Python/Web/E2E、发布矩阵或外部服务回归。若需改变配置发布、权限或后端行为，
交 B 重新判断边界和 Test Level，不随本界面修正扩展。

### Developer — affected tests

根目录：`python3 scripts/check_governance.py`；结束前 `git diff --check`。

web/ 下执行：

```sh
npm run test -- run src/shared/ui/AppShell.test.tsx src/features/rules/RulesWorkspacePage.test.tsx src/features/rules/RulesEditPage.test.tsx src/features/rules/RulesObjectTestPanel.test.tsx src/entities/rules/rules-workspace.test.ts
npm run typecheck
npx eslint src/shared/ui/AppShell.tsx src/shared/ui/AppShell.test.tsx src/features/rules/RulesWorkspacePage.tsx src/features/rules/RulesWorkspacePage.test.tsx src/features/rules/RulesEditPage.test.tsx src/features/rules/RulesObjectTestPanel.test.tsx src/entities/rules/rules-workspace.ts src/entities/rules/rules-workspace.test.ts tests/e2e/rules-readiness.spec.ts
npx prettier --check src/shared/ui/AppShell.tsx src/shared/ui/AppShell.test.tsx src/shared/ui/styles.css src/features/rules/RulesWorkspacePage.tsx src/features/rules/RulesWorkspacePage.test.tsx src/features/rules/RulesEditPage.test.tsx src/features/rules/RulesObjectTestPanel.test.tsx src/entities/rules/rules-workspace.ts src/entities/rules/rules-workspace.test.ts tests/e2e/rules-readiness.spec.ts
npm run build
npm run test:e2e -- tests/e2e/rules-readiness.spec.ts
```

新增/修改 helper 与测试须加入受影响命令。覆盖 AC-1–6 的延迟加载、无权限、失效响应、
请求失败、既有发布后读回、搜索/筛选保留与恢复；使用既有隔离夹具。
浏览器检查真实入口与迁移控件的交互，不只断言 DOM 类名或 CSS 常量。

修改验收脚本后在根目录执行：

```sh
.venv/bin/ruff check scripts/rules_workspace_browser_proof.py
.venv/bin/ruff format --check scripts/rules_workspace_browser_proof.py
MF_PROOF_ARTIFACTS="$PWD/.git/validation-evidence/patch-20261029-4/developer-rules" .venv/bin/python scripts/rules_workspace_browser_proof.py
```

沿用临时 SQLite/Local 根、一次性 token 和已构建 V2 资产；不访问用户运行库、生产媒体或
外部 Provider。完成新改及直接受影响检查后交 READY FOR B REVIEW。

### B — acceptance

独立审查完整 Task Base..candidate，先复现页头/双搜索/刷新/正常态设置问题已消除，
再验证异常恢复及共享 Shell；保留实际命令、精确 SHA、截图与结论。

web/ 下执行：

```sh
npm run typecheck
npm run lint
npm run format:check
npm run build
npm run test:e2e -- tests/e2e/rules-readiness.spec.ts tests/e2e/rules-identity.spec.ts tests/e2e/task-center-layout.spec.ts
```

根目录独立执行：

```sh
python3 scripts/check_governance.py
MF_PROOF_ARTIFACTS="$PWD/.git/validation-evidence/patch-20261029-4/b-rules" .venv/bin/python scripts/rules_workspace_browser_proof.py
git diff --check 739a9c49a39187f1cf48aa3a62c241aaea22d9a9..HEAD
```

检查三个视口的概览/代表性清单、错误/空状态及抽屉/编辑回程；只对页头参照同视口任务中心，
核对标题/刷新位置，检查概览的信息层级及本次调整是否引入遮挡、溢出或焦点问题。
七类清单均检查现有结构和入口仍保持，复杂/长内容选代表性清单在三个视口实看；
分类卡片行与七类清单内部另与 Task Base 相同可用宽度截图对照，确认原设计/交互及响应式规则
保留。它们以用户认可的原设计验收，不套用任务中心的标签或表格样式。
检查 Files/MediaLibrary/Storage 的共享搜索和 Rules Edit 标题，可使用既有 Shell 测试与
隔离浏览器夹具；按风险补跑上述受影响单元测试，不以可选全量回归延后独立 Task 完成。
新增验收不要求七分类 × 全部状态 × 三个视口的笛卡尔积：七类默认清单逐一检查，
窄屏选择概览和代表性复杂清单；共享错误/权限分支用代表入口覆盖，独有分支另测。
现有必要安全检查继续保留，不为本布局修正新增完整规则引擎或发布流程的重复验收。

## Non-goals

不改变规则算法、RecognitionType 身份、保存/自动激活、执行权限、分析/测试语义、API/schema；
不改八分类卡片导航与七类清单内部的 UI/交互/响应式规则、编辑器字段、抽屉结构、
Settings 产品、自动化页或其他页面设计；
不增加跨族搜索、批量管理、主题、Provider、媒体任务或全局设计系统；
不新增配置版本面板、策略名称解析或陈旧数据缓存机制；
不修改历史参考图，不重新打开/关闭 Slice，不更改 Roadmap/Progress 或选择后续 Task。

## Developer Completion Report

尚未开始实施。Developer 按本 Task 实施后记录完整 checkpoint SHA、实际改动、受影响测试与剩余风险；
交 READY FOR B REVIEW，由 B 独立验收。

## B Review Result

尚未开始实施验收。激活及治理检查不构成产品 PASS。
Next: **DEVELOPER IMPLEMENTS PATCH-20261029-4**；开始实现时转 IN PROGRESS。
