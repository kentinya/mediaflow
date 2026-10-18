# Slice 45 — V2 Task Center, Recovery and FileIndex Retirement

```text
Slice ID: 45
Name: V2 Task Center, Recovery and FileIndex Retirement
Owner: A — Slice Owner / Architect / Final Reviewer
Status: ACTIVE
Base SHA: a72252091d5d46edf3e2114b994036ae21b08e2e
Implementation Head: NOT SET
Working Branch: slice/45-scope-pending
Development Authorization: CONTRACT REVISED BY A; B RECHECKS TASK45.4 BEFORE CONTINUING
Risk: High
Final Test Level: T4
Next Action: B RECHECKS TASK45.4; COMPLETE RO-7 BEFORE SLICE FINAL
```

## Authority and baseline

用户于 2026-10-15 指定 A 冻结 Slice43，并从已接受的 Slice44 基线预留 Slice45；随后确认
任务中心重构、独立 Scan 完整退役、整理内取消独立 Preview 页面、九个横向标签及跨任务
分类恢复列表，最终选择“同页先显示计划摘要，再确认执行”，并要求将最终方案写入文档。

本次检查点激活该完整 Contract，仅是范围与 TARGET 设计授权，不是实现、B PASS 或 A 交付验收。
B 仍须先定义合法 Task；本次不创建 Developer Task、不导入冻结代码、不推送。

不可变 Base 保持为 Slice44 closure `a72252091d5d46edf3e2114b994036ae21b08e2e`
（接受的 Implementation Head 为 `8be263ea778df08aa374e9433f138a218c1d4af9`）。
当前分支的 scope-pending 名称是保留的历史名称，不改变其现在的 ACTIVE Contract。
前期范围说明检查点保留在 Git，未发生产品实现。

### A Contract revision — 2026-10-18

用户明确授权调整附件语义：主文件执行并验证完成即可视为主项完成；附件若失败、未执行或目标
冲突，必须保留逐附件原因、来源/目标、已完成步骤和按已绑定策略决定的处理指引；人工移动只是
策略允许时的示例，不是统一动作。本 Slice
不新增附件-only 自动恢复、补偿执行器或主文件重放路径。附件仍须进入计划摘要、持久结果、详情、
导出和审计；附件警告不得被显示为无警告的完整成功，也不得把未知效果改成可重试。

该修订保持 Storage confinement、OrganizerExecutor-only mutation、精确确认、逐项状态、未知
效果只核查和固定 pin 不变；它明确收窄的是附件-only 继续整理的产品承诺，而不是安全规则。

### A Contract clarification — 2026-10-18

附件异常的下一步必须从实际固定的 OrganizePolicy/策略能力投影，使用有界、可操作且不越权的
说明；不得把“手动移动”硬编码为所有附件的恢复动作。策略允许跳过、重命名、覆盖确认、重新
分析或其他既有动作时，只展示该策略实际允许的动作；策略不允许安全继续时，展示原因和核查/补正
路径。未知效果仍只能核查，不得给出暗示状态已知的移动或重放指引。

例如主文件的固定 OrganizePolicy 为 `MOVE`，附件发生目标冲突，而主文件已成功并验证完成时，
附件结果应显示具体冲突名，并给出“有冲突：<具体冲突名>，请修正后再进行‘移动’操作”这类
以主文件策略动作标签为准的下一步。该提示不代表系统会自动重放主文件，也不取得附件 mutation
许可；它只告诉用户修正冲突后应按既有策略处理该附件。其他主文件策略必须显示其实际动作标签，
不能统一写成“手动移动”。

### A Contract revision — 2026-10-18，未上线的 Scan 退役范围

本节记录较早授权；薄拒绝和定义模式冻结例外已由下方“Scan 按首次部署不存在处理”修订取代。

用户确认服务尚未上线，不存在需要兼容的生产旧 Scan 任务，并明确授权当前代理使用 A 权限，
同步调整已开始开发的 Task45.4。本次是材料性范围收窄，不是仅修改文案：取消 RO-5 / S-7
原有的旧独立 Scan 在途停止、接管、升级迁移与专用历史读取/取消/导出兼容义务。

独立 Scan 的 Web/API/CLI 准入、执行、重试、继续和专用编排仍必须完整移除；必要的薄退役
拒绝只说明功能已移除并指向新建整理，不能启动发现、自动转换成 Organize 或保留可运行后门。
不要求为开发测试记录保留独立 Scan 历史服务、页面、路由、数据模型或启动清退机制；
无其他消费者的专用代码应删除。遇到不支持的独立 Scan 命令仍须在执行前拒绝，这不要求迁移
或重建旧任务状态。

本次不执行媒体/运行数据库/历史数据清空，不削弱其他受支持任务的结果、pin、权限、审计和
未知效果非重放规则。整理内部发现、过滤、真实稳定性观察和既有限制保留。该次修订曾将
FileIndex 完全退出留给后续 Slice；该安排由下方新增 RO-7 的用户修订取代。
冻结 Slice43 的定义绑定模式范围不变。

Slice ID、ACTIVE 状态和不可变 Base 保持。A 先提交本 Contract 修订；B 随后核对实际未提交
改动，判断 Task45.4 在相同 ID/Base 下合法调整后继续。当前代理此前执行过 B 审查；本次用户
仅授权 A 的范围调整，不进行对自身 B 结论的 A Final Review，也不宣布 Task/Slice 验收完成。

### A Contract revision — 2026-10-18，FileIndex 纳入当前 Slice

用户随后明确要求 FileIndex 完全退役纳入当前 Slice，并使 `mediaflow files list` 与文件页、
媒体库页统一为实时 Storage 列表，只列举、不保存文件记录；同样不建设未上线系统的旧数据兼容。
这替换上一修订的 FileIndex 延期安排，新增 RO-7 / S-8、S-9 / AC-7；不是交付声明。
Slice ID、ACTIVE 状态和原 Base 保持，正式名称反映扩展后的业务范围。

完整范围与 CLI TARGET 方式见 [FileIndex 退役设计](docs/file-index-retirement-spec.md)。
“列表不记录”不取消显式整理/维护 Task、Result、精确来源、计划、审计和稳定性工作证据。
FileIndex 的产品/运行装配/全局目录仓储与 schema、后台同步和专用死代码全部退出；
不能只隐藏入口、加 no-op 仓储或更名为全局缓存。旧 FileIndex/Scan 兼容机制不要求建设，
也不授权清空运行库或媒体。其他受支持工作的安全/持久结果保持。

A 提交后 B 重核 Task45.4：已开发的独立 Scan 退役仍是合法完整单元，可在相同 ID/Base
继续；新增 FileIndex 全部退出和 CLI 统一在随后一个连贯 Task 内规划，当前不并行创建第二个
活动 Task。所有 Required Outcomes（含 RO-7）满足后才能 Slice-final/交 A，不提前关闭。
冻结 Slice43 不因共享 FileIndex 依赖移除而恢复开发；下方最新 Scan 修订仅另行选入模式删除，
其余页面/Run once/指标/设置消费继续延期。

### A Contract revision — 2026-10-18，Scan 按首次部署不存在处理

用户在核对 Task45.4 的实际实现后明确要求：Scan 相关产品按从未存在处理，当前服务按首次部署
验收，不考虑旧版或 V1 的 Scan 兼容。本修订取代上方及先前 Task 中保留薄退役入口、410、
退役页/指引、Scan 专用防线和定义绑定 Scan 例外的要求，不是仅更换错误文案。

删除独立 Scan 的页面/路由/导航、API/aliases、CLI 注册/帮助、Job/调度/执行/重试/继续分支、
readiness/action matrix 专用字段、模型/服务/仓储/专用 schema 和无消费者代码；不保留墓碑页、
专用退役错误、迁移/转换/接管/历史读取或 V1 兼容入口。旧 URL 使用正常认证边界下的普通
not-found，旧 CLI 使用 argparse 未知命令/非法参数错误，通用提交/Worker 使用共享支持集合的
普通不支持类型校验，均在发现、准入和执行权限生成前停止，不自动转换成整理。

为彻底删除 Scan 产品，定义绑定 `scan-only` / `scan-and-plan` 值、别名、默认值及其专用
发布/准入/调度/dispatch/继续分支的删除纳入 RO-5 / Task45.4。这是用户授权的冻结边界窄例外；
Slice43 其余页面、Run once、统计和设置消费继续冻结，不导入其未验收分支，不宣称完成其工作区。
普通 diagnostic Preview/DryRun、自动整理所用的零变更计划/发现和实际支持的 scheduled Preview
等其他功能不因名称含 scan/preview 被一并删掉；逐项依真实消费者和当前支持意图判断。

保留其他支持功能需要的 Scanner/Storage list-stat、过滤/临时排除、真实稳定观察、精确来源/计划/
pin、Result/审计、权限/锁/fence 和不确定效果非重放。首次部署不取消同版本正常运行后的重启、
重开、逐项恢复和失败原子性。无旧 Scan 升级/V1 parity/历史兼容验收义务，但不自动清空或
重建现有工作区数据库、媒体、用户文件或 Git 历史，也不做无关 V1 整体下线。

Slice ID/ACTIVE/Base、Task45.4 ID/Base 和 RO-7 后续完整 FileIndex 单元不变。A 先 checkpoint
本材料性修订，B 随后重核并调整同 Task；既有实现/报告/审查是旧候选事实，本修订不表示
代码已完成，不授予 Task PASS 或 Slice closure。

## Suspended work preservation

- Slice43 original Base: `853973dbbf8289fa2ad40657033e94e870a690e4`.
- Latest executable candidate: `727317168cc62f859f19db1b54b8175cb08449de`.
- Latest Developer report checkpoint: `78ec108d4473e8c140174c1356d0e88a1ae42b34:TASK.md`.
- Exact pre-hold Contract and Task43.3 plan/B decision snapshot:
  `c539429c2c3aaeaab4842b87d3c858e77106fed1:SLICE.md` / `c539429c2c3aaeaab4842b87d3c858e77106fed1:TASK.md`.
- Frozen Contract checkpoint: `ed974e0df8b263f631bfe48b524da461013d8780`.
- Preservation branch: `frozen/slice-43-2026-10-15`.
- Slice43 status: PLANNED; Development Hold: FROZEN BY USER. Task43.1/43.2 are B PASS only;
  Task43.3 remains PLANNED / NOT STARTED and suspended in the exact snapshot.
- Inventory/statistics, consolidated history and actual engine-settings adoption remain incomplete.
  Slice43 has no final validation, Closure Packet or A PASS / CLOSED.

The same agent previously performed B review and is now explicitly authorized by the user for
A's hold/reservation action. No A final review of its own prior B decisions is performed here.
Git history and locally retained evidence remain available; nothing is pushed or claimed remotely
reachable. Resuming Slice43 requires explicit A reactivation and reassessment of intervening changes.

## User Goal

操作者在一个原生任务中心中发起并确认真实整理、跟踪各文件结果，通过问题类型直接找到
跨任务的待处理工作，并完成明确、低摩擦、安全的恢复，无需独立 Scan/Preview 页面、
CLI 回退或内部授权材料。统一创建、分析、执行、结果与恢复的完整用户旅程。
CLI 文件列表、文件页和媒体库页共用实时 Storage 浏览，文件目录索引及相关运行依赖完全退出。

最终页面/旅程规范：[任务中心最终方案](docs/task-center-page-spec.md)。
九张参考图统一位于 `docs/pics/任务中心-标签名.png`，其结构、层级及风格适用；
样本名称、数量、时间和路径不构成运行数据或固定验收 fixture。

## Applicable Requirements

- V2-OPS-001–008 的既有统一工作、结果、权限及恢复基线，按 V2-OPS-009–012 的显式
  TARGET 产品修订实现新的入口、九标签、同页摘要与跨任务类型视图。
- V2-UX-001–003、V2-AUTH-001–003、V2-SAFE-001、V2-MIG-001–003。
- V2-FILES-005/006；REQ-SCAN-004、REQ-ORG-012、REQ-WEB-003、REQ-SAFE-009 等旧 FileIndex 义务
  按本次明确 V2 修订替换；精确来源、稳定性、结果持久化和安全不变量保留。
- UX-001–010，REQ-GEN-*，REQ-ORG-*，REQ-RECOVERY-*，REQ-TASK-*，
  REQ-SAFE-*，REQ-RESULT-* 与适用的 Storage/Library/Recognition/Metadata 要求。
- REQ-SCAN-001 的独立手动扫描产品入口被当前 V2 修订取代；内部扫描、过滤、稳定性、
  SourceIdentity 保留。独立 Scan 存量兼容按上方未上线修订取消，其他受支持任务历史语义
  保留。通用 DryRun 和 Rules 测试不整体退役。
- Slice42 的“全局 Review 列表延期”不限制本次明确选择的跨任务分类列表；跨任务批量
  mutation 仍不在本 Slice。闭合 Slice 的交付事实和原有接受证据不重写。

## Required Outcomes

### RO-1 — 九标签原生任务中心与权威查询

提供同一横向导航行中的 `全部任务 / 进行中 / 需要处理 / 已结束 / 识别恢复 /
元数据恢复 / 分类恢复 / 冲突处理 / 失败恢复` 九个独立可深链列表，默认全宽清单无详情选中。
共享 Shell、来源/类型或状态/时间/文字筛选、有界分页、统计和可见活跃轮询。

后端基于完整授权总体与一致读口径决定列表、计数和当前问题；不能只过滤浏览器当前页。
任务数和文件数分开，重叠视角说明清楚，普通排队不自动算作需要人工处理。
历史名称/范围、进度、主文件/附件及未知数据真实可解释。Job/Task 仅按持久关联去重，
排队及 pre-Task 失败可见，仍受支持的诊断和普通文件维护/传输历史不丢失或改写为整理。
退役独立 Scan 不要求专用历史兼容，不得因此删除或改写其他工作记录。

### RO-2 — 新建整理与同页计划摘要确认

新建仅提供真实整理，选择 Active ResourceLibrary 与有界目录/文件范围；Files 的单项、
多项及文件夹整理接入相同应用行为和返回上下文。普通操作者无需先跑 Scan 或切到独立 Preview。

显式准备操作复用真实有界发现/稳定性和完整分析链，长操作走持久任务与既有 Worker。
当前创建界面先显示计划摘要：来源、完整性、主文件/附件数、就绪和未就绪项、操作、
媒体库/目录、可展开逐项来源→目标、策略解释、冲突及覆盖/来源清理影响。
准备零 Storage mutation、无执行许可，不因预览准备制造正式执行阻塞待办。

用户检查后明确“确认整理 N 项”；仅精确确认的就绪子集取得执行许可，附件和破坏性
权限绑定实际计划。未选/未就绪项保留独立准备状态与补正入口，不隐藏、不自动执行。
完整性受实质边界影响时不得悄悄选择前 N 项执行。

原子准入、防重复、丢响应核对、固定配置和实时来源校验沿用现有权威。
计划或来源实质变化回到同页更新摘要，不执行未确认的新方案；合法固定历史快照不随
当前 Active 变化而改绑。确认后按原生入口跟踪真实 Worker/OrganizerExecutor 与独立结果。

### RO-3 — 五类跨任务恢复列表与任务内文件处理

五类恢复标签各自列出该类型尚需处理的任务，一行一个任务，展示对应问题、文件数和操作；
同任务可在多类型页出现，旧已解决阻塞不继续占用待处理清单。

行内操作进入该任务该类型的原生文件处理界面，识别、Metadata 候选/纠正、分类、冲突、
失败修复分别提供适合的输入和说明。仅使用后端当前允许的选择/动作。
保留现有任务内有界批量分析恢复及独立准入/拒绝结果，不新增跨任务批量执行。

安全分析可在保存后组合，但保存决定不取得 mutation 权限。恢复界面直接展示新计划摘要、
必要影响确认及明确继续；取消原来强制的独立 Preview 跳转，不要求操作者处理内部 DryRun Task。
主文件执行并验证完成即可形成主项成功；附件步骤独立记录，附件失败/未执行/冲突显示具体原因、
来源/目标和按策略处理指引（策略允许时可包含人工移动），不自动进入附件-only 恢复。成功、忽略和未知效果不被重新执行；配置
修复与效果核查明确区别于可安全继续。
解除问题后按真实持久状态更新列表/计数，保留其他任务/文件、返回上下文与关联历史。

失败后的必需用户流转为：

1. 原任务保留成功、失败、等待决定、效果未知的逐文件及附件结果；按当前问题进入对应恢复页，
   不是把所有未成功项都归为普通失败。同一任务在各页仅统计该类型涉及的文件。
2. 从行内“处理失败”等动作进入该任务/类型的文件列表，逐项解释失败阶段、来源/目标、
   已完成步骤、是否发生变更、效果确定性与当前允许动作。
3. 用户补充合法决定或按指引修复网络/权限等条件，再显式重新检查并生成摘要；可组合安全分析，
   不重跑整个任务。仍不满足条件的项保留原因，新遇到的识别/元数据/分类/冲突转入对应处理。
4. 当前界面显示所选安全范围的新摘要：可继续文件及实际剩余步骤、附件结果、目标/操作、
   已完成且不重复的步骤、未就绪原因及破坏性影响；用户可选就绪主文件子集，再明确
   “确认继续整理 N 项”。主文件成功而附件未完成时，保留附件原因和人工移动指引，不创建
   附件-only 执行确认。
5. 受理后跟踪关联恢复尝试的排队、执行和逐项结果，保留原失败历史；受理不等于已解决，
   不允许重复准入。列表/计数按当前真实问题更新，再次失败提供新原因与下一步。

效果未知仅提供证据、来源/目标核查和日志/导出路径，不提供直接重试、强制重放或自动回滚。
修复依赖后仍校验原固定上下文；发布新 Active 不改绑旧任务。原上下文不可恢复时明确拒绝继续，
只有既有准入允许的新方案才可重新准备、摘要确认，不扩展成任意历史 Reprocess。
未知确认响应先核对该次持久请求，成功/忽略及效果不确定项均不进入恢复执行选择。
准备摘要的未就绪项仍在原准备界面补正，不伪造正式执行失败或恢复待办。
完整分支、示例及动作语义见最终页面规范第 4 节；按钮文案可按共享设计体系细化。

### RO-4 — 详情、协作控制、结果与异常连续性

原生详情提供阶段、逐文件与附件结果、源/目标、策略/失败解释、附件按策略处理指引、持久执行步骤、相关日志/审计、
恢复链及有界脱敏 JSON 导出，受支持工作的现有 Task/Job 深链仍可到达真实记录。
普通工作不依赖两套 Task/Job 管理入口或内部 UUID。

后端决定各工作类型的暂停/取消/继续可用性，区分请求和确认生效；不声称在途效果回滚。
继续重验剩余范围和真实许可，必要摘要/重新授权在当前界面完成。
Worker 不可用、固定上下文缺失、权限不足、过期输入、未知响应与不确定效果均有行动指引。
持久状态经刷新/重连/重启可追溯，已完成与不确定 mutation 不自动重放。

### RO-5 — Scan 产品首次部署移除与共享依赖收敛

移除独立 Scan 的 Web 页面/按钮、API/CLI 准入与创建/执行/重试/继续分支，以及仅供该产品
使用的运行编排和死代码；隐藏、改名或保留兼容执行器不满足要求。按首次部署完全不存在处理，
不保留退役页/410/指引或专用拒绝层；旧输入走普通 not-found/未知命令/不支持类型错误，
不能自动转成真实整理或通过其他入口绕过。

保留整理/组织共用的 Scanner、Storage 发现、过滤、临时文件排除和稳定性。
当前依赖“先手动 Scan”的稳定性/恢复指引必须转为原工作流内部有界观察，不降低检测要求。
服务尚未上线，不建设旧独立 Scan 的停止/接管、升级迁移、历史页面/API/取消/导出兼容，
也不为这些目标保留专用服务和死代码。共享支持集合在发现/准入前拒绝不支持的命令；
本次不执行媒体/数据库/历史数据清空，其他受支持任务及共享 pin/结果/审计不受影响。
定义绑定 scan-only/scan-and-plan 的删除纳入本 Outcome；仅此删除跨入原冻结范围，
不借本 Outcome 实现 Slice43 完整工作区，也不移除其他功能需要的内部发现/计划/诊断能力。

### RO-6 — 统一架构、验证与文档真实性

Web/API/Worker 使用同一应用行为、权限、固定来源/计划和恢复服务；不建立第二套任务、
队列、配置或恢复引擎。必要持久化变更保留原版本、结果、历史模式和来源身份。
任务运行状态、文件处置、待处理问题与效果确定性分开表达。

九页面、创建→摘要→确认→执行、各类恢复、独立 Scan 退役及其他受支持任务的历史路径
通过自动化和原生浏览器验证。
CURRENT 文档只在实际验收后更新；本次文档和图仍是 TARGET，不宣称实现。

### RO-7 — FileIndex 完全退役与实时文件列表统一

`mediaflow files list`、文件页与媒体库页通过同一库级应用浏览行为，以精确 Active 的
ResourceLibrary/MediaLibrary→Storage/root 与库相对目录进行有界 list/stat。
CLI 明确选择资源库或媒体库；同名跨种类库、游标、越界、空白/长名与错误规则一致。
浏览显示真实目录条目，不受旧索引成员、媒体扩展名、识别或处理状态限制；不记录文件目录/
扫描观察/任务/结果、不授予执行权、不调用 Provider/Hash、不变更媒体。

FileIndex 的 CLI/API/V1/V2 专用列表/详情/统计/reprocess、domain/仓储/内存替代/装配、
全局 occurrence/disposition 目录、schema、后台/Result/文件维护同步、修复路径及死代码
完整退出，新建运行库不创建其专用表。所有实际消费者（含 Worker、普通整理/恢复及现有
Automation 基础消费者）都能不装配 FileIndex 而完成支持的行为；不得只让 Files 不依赖它。
共享模块内的必要依赖移除允许实施，冻结 Slice43 的业务功能不扩展、不导入。

精确来源/计划/pin/版本、当前锁/准入去重、已完成/未知效果和真实稳定性观察仍按显式工作
范围保存在既有 Task/Result/checkpoint/发现工作中，不形成更名的长期文件目录。
普通工作重连/重启和恢复正常；取消全局 New/Modified/Unchanged/Missing 索引产品与自动同步
义务，来源变化与禁止错误重放的安全含义保持。

仅按未上线环境验收，不建设旧 FileIndex 迁移、双写、历史 FileID/API 兼容或索引同步修复；
旧入口薄拒绝并指向库级浏览/任务中心。不自动清空、drop 或重建现存运行数据库/媒体。
完整旅程、边界和验收见上述设计，默认只读 CLI 不触发数据库初始化/升级。

## Required Surfaces

| Surface | 必需结果 |
|---|---|
| S-1 任务中心九标签 | 独立可达、原生查询/统计/筛选/分页，默认无选中详情 |
| S-2 创建与 Files 接入 | 有界真实来源选择、同页摘要与明确确认、正确返回 |
| S-3 识别/元数据/分类恢复 | 跨任务类型列表及任务内专用文件处理 |
| S-4 冲突/失败恢复 | 独立影响、许可与安全范围；附件异常给出人工处理指引；效果未知只核查 |
| S-5 详情/记录/导出/控制 | 真实结果、历史链与后端允许的协作动作 |
| S-6 API/Worker/Persistence | 与 Web 同权威，耐久准入、固定上下文、去重和非重放 |
| S-7 Scan 首次部署移除及内部依赖收敛 | 独立及定义绑定 Scan 产品/兼容层不存在，旧输入普通报错；其他功能所需发现/稳定性/计划保留 |
| S-8 CLI/Web 实时文件列表 | files list 与文件页/媒体库页共享库级 live browse，只读、不存文件记录、同边界/分页/错误 |
| S-9 无 FileIndex 的运行链 | 新库/装配/API/Worker/整理/恢复/结果和现有共享消费者不依赖索引，无索引产品或后台写入 |

## Product Experience / UX Constraints

完整 goal→entry→state→action→success→failure→recovery 见
[最终页面规范](docs/task-center-page-spec.md)第 3–5 节。
入口自然、中文业务名称优先、只为实际意图/权限升级/歧义/未知效果/破坏性影响增加确认。
九类页面不靠抽屉中的嵌套通用字段替代，关键状态不以原始异常或 token 呈现。
窄屏、键盘、深链、返回、空态、无权限、不可用及过期输入均能完成同样的用户结果。

## Safety Invariants

1. Scan/Discovery、Parse、Recognition、Metadata、Naming、Classification、Planner 和摘要分析
   全部零 Storage mutation；读取/刷新/切换标签不创建工作或调用 Provider。
2. OrganizerExecutor-only mutation，Storage confinement/capabilities、无静默 fallback、
   明确许可的覆盖/删除/来源清理、审计/脱敏、RBAC 不变。
3. ResourceLibrary→实时 Storage 是整理来源权威；MediaLibrary 非整理源。三种列表均是库级
   实时 Storage 读取；没有 FileIndex 或替代全局目录作来源/执行权威。结果持久化/显示失败
   不引发已完成或未知 mutation 重放。
4. 不可变配置与精确来源/计划/选择绑定、乐观并发、claim/lease/fence 和原子准入保留；
   当前 Active 不替代合法旧 pin，已消费/撤销许可不因 Continue 重新获得。
5. 逐项状态独立；主文件成功不因附件异常被重放，附件异常保留原因并提示策略允许的处理；成功、
   忽略及不确定 effects 不自动重试；未知提交先查持久状态。
6. RecognitionType C 复用 A 策略后仍是 C；Provider 接口、secret-free 解释和无 FFprobe 不变。
7. 保留无关用户脏文件、参考图删除意图、私有 ignored 配置及不可变已审历史。

## Explicitly Deferred

- 冻结 Slice43 的页面、Run once、指标与实际全局设置消费；不得导入其未接受实现。
  scan-only/scan-and-plan 产品/模式专用路径删除已由本次用户修订选入 RO-5，不再作为冻结例外保留。
- 整体 DryRun 退役、Rules 测试删除、其他诊断命令或 Provider/身份/配置体系重设计。
- 跨任务批量 mutation、批量覆盖、历史删除/保留策略、任意旧结果 Reprocess、通用回滚、
  不确定 mutation 自动重放、V1 UI 全面退役。
- 新 Storage/Metadata Provider、Upload/Download、MediaLibrary Organize、新调度/并行执行引擎。
- 附件-only 自动恢复、附件补偿执行器和为补附件而重放主文件；附件异常只提供持久原因、目标
  和按策略处理指引，人工移动仅在策略允许时出现。
- 超出现有有界发现/主文件限制、自动拆大批、保证所有旧 discovery 异常无缝续跑。
- 已闭合 Slice 的非阻塞清理和无关页面重构；后续未确认产品点不自动进入本 Slice。

## Slice Acceptance Criteria

- AC-1：九个标签和列表真实可达；查询覆盖完整授权总体，任务/文件数、重叠视图和多页筛选一致；
  不可用不显示零，历史名称/身份不因当前配置变化而改写。
- AC-2：单项、多项、文件夹新建整理在同页完成摘要与精确子集确认，未确认零媒体变更；
  附件、未就绪、边界不完整和破坏性影响均清楚，准入/响应丢失不重复执行。
- AC-3：每类恢复从跨任务列表到任务内文件处理、同页新摘要及确认继续完整可用；
  多问题/多任务互不覆盖，解除和新阻塞正确反映，原始历史和成功兄弟项保留。
  网络/权限修复后重新分析、决定后新阻塞转类、就绪子集确认、恢复再次失败和未知响应核对均可见；
  原配置不可用不得暗中改绑，已完成步骤及不确定 effects 不重放，准备未就绪不冒充执行失败。
  主文件验证成功即可保留主项完成；附件失败/未执行/冲突必须显示原因、来源/目标和按策略处理
  指引（人工移动仅是策略允许时的示例），不新增附件-only 自动恢复或把附件警告显示为无警告成功。
- AC-4：详情、记录、导出、可用控制、Worker 等待与重连/重启恢复真实；
  原 Task/Job 深链可诊断，主旅程不回退 CLI/V1 或独立 Preview。
- AC-5：独立和定义绑定 Scan 产品按首次部署不存在处理：Web/API/CLI/Job/调度/执行/恢复路径、
  scan-only/scan-and-plan 模式、专用投影/schema/退役兼容层均删除；旧地址/命令/工作类型走普通
  not-found/参数/不支持类型错误，不暗中执行或转换。其他功能所需发现/过滤/真实稳定性/计划可用。
  不要求旧 Scan/V1 parity、停止/接管、迁移或专用历史兼容；不删除媒体/运行数据，其他受支持工作
  的结果、pin、权限和历史不回归。FileIndex 依赖按 RO-7 另一个连贯 Task 完整移除。
- AC-6：架构与全部安全不变量通过验证，C→A 策略身份回归通过；
  文档/视觉状态、CURRENT/TARGET、受测候选与证据真实一致，未完成项不冒充交付。
- AC-7：三入口对同库/目录的真实列表和有界分页一致，列举不产生文件记录或工作/权限/媒体
  变更。新库/生产装配和所有支持的处理消费者不再包含/调用 FileIndex，不保留全局目录替身、
  索引同步/reprocess/兼容引擎；无索引仍完成稳定观察→摘要确认→执行→恢复/重开。
  不要求旧 FileIndex 生产迁移或历史兼容，不清空现存运行库/媒体；其他任务持久结果和安全保持。

## Final Validation Expectations

Final Test Level 为 T4；本次激活文档只执行治理/链接/图片完整性/范围/私有文件和 whitespace 检查。
实现候选按 workflow 分阶段验证，B 在各 Task 给出精确命令、风险与独立关键复现，最终至少覆盖：

- 全 Python regression：`python -m unittest discover -s tests`；
  quality 中适用的 `ruff format --check .`、`ruff check .`、
  `python -m compileall -q mediaflow tests scripts`、依赖/示例配置及禁止依赖审计。
- Web typecheck/lint/format、完整 unit/component tests 与 production build；
  实际构建产物上的原生九页面视觉、窄屏/键盘/深链/重连、各恢复及完整创建确认旅程。
- Real-Python API/SQLite/Worker 浏览器证明：跨页全总体计数、混合类型/逐项解除、准入去重、
  来源变化、未知提交核对、配置 pin、协作控制、恢复与不确定 effects 非重放。
- 首次部署无 Scan 产品/注册/专用 schema 或退役层；旧 URL/CLI/通用提交使用普通不存在/
  不支持错误且不构造发现/准入/执行权；定义绑定模式不绕过。支持工作在空库完成真实稳定观察
  →摘要→确认→执行→重启/恢复；不要求旧 Scan 升级或 V1 兼容证明。
- 恢复旅程包含混合成功/待决定/冲突/技术失败任务的分类计数，修复后重分析与新阻塞转类，
  精确就绪子集/附件摘要与按策略处理指引、受理与解决区分、再次失败、原固定上下文缺失和效果未知只核查。
- 实际 mutation 使用临时 Local / fake / local-server Storage、假 Provider，检查操作及权限；
  不接生产媒体/外部生产服务，分析段以 mutation/Provider 计数等证明其边界。
- 涉及 schema 时验证仍受支持版本的迁移/重开及失败原子性；未上线的旧 Scan/FileIndex schema
  不要求迁移，不得以自动清库替代拒绝。涉及安装、生产产物/Worker 装配时验证 wheel/Docker
  内同一确认/恢复路径及常驻消费，不以 mock 替代实际边界。
- 对 9 张实际截图及布局作视觉检查；例图数量不当作测试常量，缺失外部门禁明确披露。
- CLI/文件页/媒体库页的真实 Storage 对照、反复 list/分页零文件记录/工作/Provider/媒体变更；
  跨种类同名库、游标/路径/配置边界与无Active/权限/Storage故障验证。新库没有索引专用 schema，
  源码/装配/产物无可运行索引、后台同步或 no-op 替身；完整消费者在无索引的 wheel/Docker
  中实际执行。验证当前支持工作重开/故障原子性，不要求旧索引生产迁移矩阵。

证据保存和复用按 workflow，完整 source SHA、实际命令、配置/依赖、结果计数及原始日志位于
耐久证据索引；文档/报告 successor 只在明确证明 executable inputs 不变时复用。
B 在满足全部 Required Outcomes 后提交一个 Closure Packet，停止继续生成微型 Task。

## Closure Packet

Not submitted. Task45.4 is in development; this scope revision is not Slice-final validation or closure.

## A Final Review

Reviewed Range: NOT REVIEWED
Decision: NOT REVIEWED
P0/P1 Blockers: NOT ASSESSED
Closure Reconciliation: NOT PERFORMED
