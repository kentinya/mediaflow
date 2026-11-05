# Slice 49 — 自动化任务创建、编辑与直接运行

```text
Slice ID: 49
Name: Automation Task Creation, Editing and Direct Run Once
Owner: A — Slice Owner / Architect / Final Reviewer
Status: PASS / CLOSED
Base SHA: 02fb77dd713bad4dd51c29b6cfc5556ddd6d5b4e
Implementation Head: 9d6b78147d90b950ed2333f9747facc77bf0391a
Working Branch: main
Development Authorization: COMPLETE; NO ACTIVE IMPLEMENTATION TASK
Risk: High
Final Test Level: T4
Next Action: A SELECTS THE NEXT LARGE SLICE
```

## Authority and accepted baseline

用户先要求调查来源范围失败、列表运行一次不可用、编辑体验与新建不一致和新建缺少启用选项，
随后明确要求规划新 Slice，并确认使用下一编号 **Slice49**。用户进一步明确：删除编辑页
“运行一次”，创建后仍可启用/停用；创建启用的内部命令顺序不作为用户硬要求。用户随后
明确要求激活 Slice 和 Task。A 先 checkpoint ACTIVE Contract，B 随后确认既有 Task49.1
草案并转为正式 PLANNED Task；Developer 仅实施正式当前 Task。原激活轮只调整治理状态，
没有产品代码、B 验收或 A Final Review；现已完成两项 Task、B
最终验收和下方独立 A 终审。生命周期与测试责任仅遵循
[Development Workflow](docs/development-workflow.md)。

Base 是调查时的既有源码基线；纯文档规划/激活提交不重设 Base。Task49.1 原 Task Base
`129d1c060dea05a91755dbd2ed70632f09655fd4` 同样保留，不因激活重设。
[Slice48 Contract / A review](https://github.com/kentinya/mediaflow/blob/02fb77dd713bad4dd51c29b6cfc5556ddd6d5b4e/SLICE.md)
保留原 Base `ba84272721961c970f1eb85d616a0d129523ab92`、已审实现
`a80015e2f7d46e3ad1b8f7b14c453d1030e62104` 和 **PASS / CLOSED**。
上一独立修正 `BUG-AUTO-CREATE-UX` 的 B PASS 与完整计划/证据保留在
`b0bbc8125d06057d042b139469bb170c3284cc79:TASK.md`。不重开旧 Slice/Task，不改写原验收。

## User goal and requirement traceability

操作者在自动化列表一次点击就能启动已保存定义的一次真实整理；整个资源库和子目录来源
都能正确运行。新建、编辑使用同一套中文卡片、字段交互和动画；新建时能明确选择是否
启用定时运行，创建后也可通过编辑启用或停用。错误说明实际失败阶段、持久状态、已知效果和
可执行的下一步；提交未知时核对原请求，不能误重复创建或整理。

本 Slice 选择 [V2 Requirements](docs/v2-requirements.md#automation-forms-and-direct-run-once--current-slice49-pass--closed)
的 CURRENT `V2-AUTO-013–015`。其中创建可选启用明确调整 `V2-AUTO-002/010` 与
[CURRENT 创建旅程](docs/product-experience.md#current--complete-native-automation-workspace-accepted43-amended46)
原有的“新建始终关闭、另行启用”结果；当前旅程已对齐本次接受，复制仍默认关闭且不继承授权。
其余为 `V2-AUTO-001/002/004/011` 既有结果的入口与正确性修正。
保持 `UX-001–007/010`、适用的 `REQ-SCHED-001–007`、`REQ-TASK-005–010`、
`REQ-SAFE-001–009` 和 `V2-TASK-001–014` / `V2-AUTO-012` 的现行 V2 语义。
四项结果已接受为 CURRENT；冻结 V1 和旧 Slice 的原始验收含义不变。

完整旅程见 [Product Experience CURRENT](docs/product-experience.md#current--automation-forms-and-direct-run-once-slice49-pass--closed)，
技术边界见 [Architecture CURRENT](docs/architecture.md#current--automation-forms-and-direct-run-once-slice49-pass--closed)。

## Investigated gaps

| 现有触发与事实 | 根因及范围判断 |
|---|---|
| 非空资源库根 `Incoming`，选择整个库 Run once；空目录、有文件均在 Storage 读取前失败，记录显示“来源范围设置无效” | `automation_run_once.py` 拼接出 `Incoming/`；`automation_definition_execution.py` 以严格相对路径规则拒绝 Task 范围的末尾空段。属于内部路径表示不一致，不能靠放宽危险路径或改成 completed 修补。 |
| 列表点击运行一次跳详情，详情没有运行按钮 | `AutomationListPage.tsx` 的 `onRunOnce={openDefinition}` 只导航；真实浏览器 mutation 请求为零，编辑页才提交运行命令。 |
| 新建是中文卡片，编辑是英文长页、小原生输入框和技术说明 | `AutomationCreateDialog` 与有 ID 的 `AutomationLifecyclePage` 是两套表单；上次独立修正明确排除了编辑/详情/Run once。 |
| 新建无启用选项，提示却说可在列表启用 | 前端始终 enabled=false，后端拒绝 enabled=true 创建；列表也没有直接启用控件。这次选择调整创建结果，并纠正相关入口提示。 |

隔离 API→SQLite→Worker→执行记录探针：空 Storage 根/整个库正常，非空库根/整个库两组
复现失败，非空库根/子目录与 Scheduler due 对照正常。原有测试库根为空，列表测试只验证
按钮存在，未覆盖真实点击准入。浏览器已检查桌面和 390px 窄屏。
调查没有读取用户那条 Task 的运行数据库，不能宣称已核对其具体 ID。
本地原始材料在 `.git/validation-evidence/02fb77dd713bad4dd51c29b6cfc5556ddd6d5b4e/automation-investigation/`，
不声称远程可取；本表保留不依赖本地附件的触发与根因。

## RO-1 — 正确、受限且可解释的来源范围

从保存的 ResourceLibrary 根和可选子范围解析同一个受限来源，准入、持久 Task、Worker
验证与执行一致。覆盖 Storage 根、非空/多层库根、整个库、子目录、中文和空格，以及当前
配置合法接受的库根表示。规范化已验证组成部分的拼接结果，不把用户传入的绝对路径、
越界、`..`、非法分隔符等静默转换成合法输入；保留 Storage 身份和库根约束。

健康空目录或完整过滤后的无工作正常 completed，并诚实显示无待处理文件；有可处理文件
就走完整生产策略链。来源目录缺失，或目录读取失败导致无法证明来源范围完整，以及范围
超限、固定上下文不匹配，仍按现行 Task 流程失败，不能伪装空成功或执行前 N 个。
单个文件读取/处理技术失败保留该文件失败事实；其尝试结束、其他工作处理完且无人工待办
或真实在途调用时，Task 可以 completed，不因文件失败改成 Task failed。系统内部拼接错误
不能被当成操作者填错目录。
失败只提供现有合法后续动作；修正保存后新发起运行不等于重放旧失败 Task。

## RO-2 — 列表一次点击直接运行已保存定义

`自动化 → 任务列表 → 某行运行一次` 是真实命令入口。一次明确点击绑定操作者读到的
已发布定义、来源、配置快照及请求身份，直接准入一个 Task；不先跳详情/编辑，不要求用户
重新选文件、手动分析或再次做初始摘要确认；后台仍完整分析、生成计划和执行安全校验。
停用定义在有手动执行权限时同样可运行，不启用
计划、不推进 due 状态；未保存编辑值不参与本次运行。

提交中在原列表显示该行忙碌状态并拦截连击。受理后保留列表筛选、分页、滚动及焦点，
显示“已提交”及本次工作可核对的入口；受理不称为文件成功，不强制跳页。操作者可主动
查看原有本次运行/Task 状态，四类问题继续由 Task Center 处理。删除编辑页/编辑卡片的
“运行一次”按钮，定义一次手动运行的普通 Web 入口统一到列表；不移除共享后端准入/核对能力。
旧编辑入口已提交的未决请求仍可在列表精确核对，不因删除按钮丢失上下文。

明确拒绝说明原因并保留列表；并发变更要求重新读取已保存定义后明确再提交，不能偷偷
替换快照重试。丢响应在原界面显示“结果待核对”，保留按 principal、definition、request
绑定的上下文，关闭/刷新/重连后核对原请求，不自动重发。其他行不共享错误或伪造受理状态。
未知结果的缺失查找不是未受理证明；不增添泛化恢复或成功/不确定效果重放入口。

## RO-3 — 新建和编辑共用普通操作者表单

列表的“新建自动化任务”和“编辑”都在列表背景上打开同一套卡片体验；已有保存定义的
生命周期编辑地址及实际普通编辑入口进入相同体验，深链/刷新/登录续转也可到达。
已有创建卡片是视觉基准：中文分组、输入样式、来源目录浏览、间隔数值+单位、每日/每周
时间、高级 Cron/时区、后端计算的近期运行时间、上限、主次按钮、过渡和 reduced-motion。
实现应共享字段组件/校验/展示能力，保留创建与编辑的身份和命令差异，避免复制第二套表单。

编辑精确回填已保存值，ID 不变；任意合法 Cron/小数间隔与子范围不得因便利控件默认值
被改写。保留现行字段能力及启用状态，不把内部 ID、Active revision、digest 或 Draft
发布步骤变成日常必填/教程。必要诊断可有界查看；复制/删除仍有现有入口、权限与确认，
不借表单统一重做其业务能力。普通保存无需独立 Validate/Activate 操作。

未修改直接关闭；修改后退出提供可见的继续编辑/放弃修改。保存/创建中禁止重复提交与
意外离开；未知结果保留原命令，允许按已有安全规则离开并重开核对。保存成功平顺返回
原列表，更新真实行/统计；若被筛选掉解释原因。取消、放弃、返回、保存和深链返回都保留
合法列表条件、页、滚动和入口焦点。错误定位字段且保留输入，窄屏不溢出，键盘可完成。
确认自己的保存成功后，再打开同一定义可继续编辑/更改启用并再次保存；新输入不被旧响应覆盖。

## RO-4 — 新建可选启用，创建后可启用或停用

创建表单提供中文“启用自动化任务”开关，**默认关闭**。未选择时创建停用定义；明确
选择时主按钮/邻近说明清楚表达“创建并启用”，普通成功流程一次界面提交完成所选结果。
复用既有 focused create/enable 和 Managed Configuration 权限、校验与发布能力；可采用
单次原子发布或安全编排既有命令，不把后端命令数量/顺序锁成验收条件。

创建完成后，有相应权限的用户可在同一套编辑卡片明确启用或停用并保存；不论创建时
选了什么，都保留后续启停能力。启用/停用与列表“运行一次”是不同操作，计划启停沿用
现行对未来调度及剩余 scheduled effects 的安全边界，不回滚已有结果。

创建启用与编辑启用使用同一后端权限、校验、审计和受限 scheduled intent：除既有配置
管理/激活权限外，要求当前 `GRANT_UNATTENDED_EXECUTION`。没有权限仍可在满足配置权限
时创建停用定义；前端解释不可选原因，伪造 API 请求同样拒绝。省略 enabled 保持关闭，
非法类型不能按 truthy 启用；不得因已有计划、读取/预览或其他发布隐式获得执行意图。
复制继续关闭且不继承授权。

成功提示区分“已创建，未启用”和“已创建并启用”，并读取真实 Active 状态。配置命令
本身不准入 Task、不请求 Run once、不调用媒体变更；Scheduler 后续按真实计划和当前权限
正常准入，不是发布命令的即时执行副作用。每个被拒绝的命令保留其提交前的 Active；若分步
编排发生创建成功、启用失败或未知，必须显示“已创建，未启用/启用结果待核对”的真实状态，
保留已有定义身份，不假报全部成功、不重新创建，也不静默当作用户改选停用。
版本冲突/未知响应保留原用户选择及每个实际提交命令的动作、候选和基线，先核对未知步骤，
不得靠换 ID、盲目补发启停或自动重试掩盖未知。已确认创建成功且后续启用明确未执行/被拒绝时，
允许基于现有定义和当前权限/版本明确完成启用；正常创建后的启用/停用始终保留。

## Required surfaces and technical boundary

- Web：自动化定义列表、创建/编辑卡片、对应深链/返回与直接运行反馈；相关成功/空态提示
  必须指向真实可用入口。详情仅改与这些入口直接相关的链接/过时说明，不重做详情产品。
- API/application：既有 focused create/edit/enable、表单权限投影、发布核对、Run once 准入与
  必要只读投影；共享校验/权限/审计，不能只修 Web 让直接 API 留洞。
- Runtime/persistence：合法范围准入和固定上下文消费、Task/Worker、Scheduler 对照、去重与
  记录/统计/Task Center 回读；精确历史和已准入快照不重写，缺陷历史不批量改成功。
- 复用已有 Managed Configuration、审计、SQLite Task engine、Storage/Provider 接口和前端
  受限 session 上下文；不建立第二配置库、队列、工作引擎或通用命令框架。无新增 schema
  产品需求；如 B 发现必须改持久化结构或扩大兼容边界，先交 A 明确调整 Contract。

## Invariants and explicit exclusions

仅 OrganizerExecutor 通过 Storage 变更媒体。读/目录浏览/计划时间预览零变更；准入/发布
权限后端权威，固定快照、完整遍历/稳定性、容量、source ownership、claim/fence、审计脱敏、
显式破坏性许可和成功/不确定效果不重放均保留。RecognitionType C 使用 Naming A /
Classification A 后仍为 C，必须有自动化覆盖。

保留五态 Task 流程、独立文件/附件/操作结果、四类人工决定→分析→摘要→明确继续，以及
自动化 due+Run once 的 completed/(completed+failed) 统计。受理/启用/完成都不保证文件成功。
不恢复 Scan/独立 Preview/FileIndex/Job/Pause/retry-failed，不新增运行模式/Storage/Provider、
批量运行、跨 Task 恢复、自动重试、自动不确定重放、补偿回滚或调度/队列/设置重构。
不重新设计执行记录、Task Center、整个详情/复制/删除或其他页面；不要求列表新加启停
开关，相关提示应与实际入口一致。旧失败任务修复/迁移、跨版本升级/回滚、V1、外部服务
专项验收和生产部署不在本 Slice；不删除数据、改写历史或清除媒体来通过测试。

## Acceptance

| ID | Required proof |
|---|---|
| AC-1 | Run once 和 due 在合法的空/非空/多层库根、整个库/子目录、中文空格路径组合中指向同一受限目录；非空库根+整个库不再因系统尾斜杠失败。准入到 Worker 的原生链路证明实际目标范围，不只测字符串函数。 |
| AC-2 | 绝对/越界/穿越/非法子范围、固定范围不匹配、缺失/禁用库和 Storage 均正确拒绝；不以规范化掩盖危险输入或扩大来源。已准入快照不随当前编辑重设。 |
| AC-3 | 健康空目录 completed/noWork；非空来源执行完整策略链。目录读取失败导致无法证明来源范围完整、真实超限/不完整仍为 Task failed 且零前缀执行；单个文件读取/处理技术失败不单独使 Task failed，尝试结束且无其他未完成工作/人工待办/真实在途调用时可 completed，文件失败事实仍保留。稳定性与历史过滤不变。 |
| AC-4 | 从真实列表一击提交一个已保存定义 Task，连击不重复；提交和受理反馈留在原列表，原条件/页/滚动/焦点保持。没有先导航、文件重选或第二次初始确认，后台完整分析/计划/校验保留；明确查看才离开列表。编辑页/卡片不再出现“运行一次”按钮。 |
| AC-5 | 停用定义在正确权限下可 Run once，不改变 enabled/due；编辑未保存值不执行。权限不足、队列满、过期配置和读失败有中文纠正路径，不能自动重试/替换权限与快照。 |
| AC-6 | 运行响应丢失/5xx/畸形响应后，在原列表及刷新/重连后精确核对原 principal/definition/request；删除编辑运行按钮前已提交的未决上下文也能在列表核对，无重复 Task/媒体效果，其他行不串状态。改登录身份不读取/操作他人未决上下文。 |
| AC-7 | 新建/编辑实际使用一致的中文卡片、字段交互、目录选择、时间便利控件/高级 Cron、主次按钮、动画/reduced-motion、校验与焦点；桌面与390px窄屏实际截图/交互证明可读可用。 |
| AC-8 | 编辑精确回填并保存所选来源、任意合法 Cron/时区、小数间隔、上限与 enabled；普通深链/旧入口进入同一编辑体验。既有 Draft-only/不可读状态不伪装已发布定义，复制/删除现有能力仍可达。 |
| AC-9 | 新建和编辑的取消/修改后退出/保存成功/失败均保持真实状态、输入及列表返回上下文；提交中防重复/意外离开，未知可重开核对。保存成功返回列表，再开同一定义改 enabled/其他字段并保存有效，旧响应不覆盖后来输入。 |
| AC-10 | 新建默认关闭，省略 enabled 不隐式启用；明确选启用时一次界面提交完成创建及启用，后端命令数量/顺序不作为硬条件。创建后可经编辑明确启用、停用并保存，往返切换有效。成功文案与真实 Active 一致，不自动 Run once；复制仍关闭/无继承授权。 |
| AC-11 | Web/API 都验证配置管理/激活及启用所需当前权限；无 scheduled 权限可按原权限创建停用定义，却不能伪造 true 启用。非法类型、校验/引用/权限失败及冲突不能产生未经授权的发布，每个拒绝命令保持其提交前 Active。若采用分步编排，已创建但启用失败/未知如实显示，保留已有定义、不重建、不假报全成功；审计绑定真实主体/候选/来源/版本，无兄弟 Draft 搭车。 |
| AC-12 | 含启用选择的未知创建/编辑/启停跨关闭/刷新/重连精确核对实际提交的命令/候选/基线；不换 ID 重复创建、不在未知时盲目补发启停、不因“没找到”自动重发。分步时按真实阶段核对；确认已有定义且后续启用未执行/明确拒绝，可基于当前版本和权限明确启用。自身发布与他人并发发布可区分，current/prior/unknown 不混淆。 |
| AC-13 | 创建/编辑/启用命令无 Task admission/媒体变更；Scheduler 按计划的后续真实准入使用已审范围/权限。禁用/撤销、当前权限丢失、固定上下文、并发源所有权及已完成/不确定不重放回归通过。 |
| AC-14 | Run once 的 Task Center/执行记录/成功率回读沿用五态流程和独立文件结果，一次运行计数一次；空 completed、流程失败、四类等待、取消及文件失败不误标，原运行时间/尝试/结果保留。 |
| AC-15 | Fresh新工作、同版本重启/重开保留定义的明确启用、发布核对、原请求/Task/结果及合法继续；READ/analysis零媒体变更、C→A身份不变及源/目标约束有自动化证明。 |
| AC-16 | B 提供匹配候选的适用完整 T4/原生/安装包与容器证据及失败/skip/限度；A 独立审查原 Base..Implementation Head 的全部 RO/表面后才可 PASS / CLOSED，并做 CURRENT 文档对齐。 |

## Implementation and validation allocation

Task49.1（RO-1/RO-2）与 Task49.2（RO-3/RO-4）均由 B 独立验收 PASS。
Task49.1完整 B 结论在 `7b7e9aaa24684ee59552ca95641843706dc7680d:TASK.md`；
Task49.2和最终 Closure Packet 在
`edef2b9dfb3726f8aca6b4d7c4a7ae233f900d2c:TASK.md`。Task Base 与原 Slice Base 均未重设。
创建可选启用采用单次原子发布，不存在分步创建成功/启用失败的中间结果；Contract 对
安全编排的允许不是本实现已交付另一种路径的声明。

风险保持 **T4**。Developer 执行新增/修改/直接受影响测试，B 承担完整回归及适用安全/
打包/原生门禁；A 独立审查完整 Slice 并核对关键不确定性，没有代替 B 自我验收。
隔离 Local/SQLite/合成 Provider 经真实 API→Task→Worker/现有浏览器入口证明行为，未手写
最终 Task/Result 冒充执行，未读取私有配置、用户运行数据库或生产媒体。

## Final validation, Closure Packet and A Final Review

**PASS / CLOSED — 2026-11-05，A 独立终审。**

- Reviewed range：`02fb77dd713bad4dd51c29b6cfc5556ddd6d5b4e` →
  `9d6b78147d90b950ed2333f9747facc77bf0391a`，42个文件，含全部实现/测试/harness/文档。
  不只审最后一次修正。B最终验证候选 `6baa0e508658d33a6d44843deea86f0faafca2c6`；
  后继至本轮起点 `edef2b9dfb3726f8aca6b4d7c4a7ae233f900d2c` 仅 TASK.md 文档，
  执行输入未变。闭环提交只对齐已审事实，不新增产品行为。
- B Closure Packet：上述 `edef2b9d:TASK.md`，Required Outcomes/Surfaces COMPLETE，
  Tasks49.1/49.2 PASS，Decision SLICE READY FOR A REVIEW。A 核对原始日志、失败/重跑、
  精确产物与执行输入，未把 PASS 标签代替证据。

| 结果 / 验收 | A 完整范围判断 |
|---|---|
| RO-1，AC-1–3 | PASS。只规范化已验证来源组成的拼接，准入与严格 Worker 消费一致；实际非空根整体库整理及due对照通过。危险子范围/固定上下文不匹配拒绝，完整遍历、健康空与流程失败/独立文件失败不混淆，无前N执行或历史重写。 |
| RO-2，AC-4–6 | PASS。真实列表一击提交已保存定义，当前行防重复并保留列表/精确Task入口；停用可运行且不改due。拒绝/未知、连续两次运行及旧编辑未决请求保持独立身份，刷新/重连只核对、不重放；编辑运行按钮退出。 |
| RO-3，AC-7–9 | PASS。创建/普通编辑与深链共用中文字段和卡片，精确计划/范围/启用回填、目录浏览、取消/放弃/提交保护/返回/连续保存可用。定义与同次读取基线绑定，立即重开不把旧字段配新版本。桌面/390px、键盘、reduced-motion证据可读可用。 |
| RO-4，AC-10–12 | PASS。默认关闭、明确创建启用、后续启用/停用保存有效。Web投影与后端权限/严格类型/原子拒绝/审计复用既有边界。未知发布原身份可核对，并区分当时成功与当前已修改/移除/不可读，不重复创建或盲目启停。 |
| 运行及安全，AC-13–15 | PASS。发布/读取/预览不即时准入或变更媒体，后续Scheduler消费真实受限intent；权限丢失/禁用、pins/fences、源所有权、C使用A策略仍为C、四类恢复及成功/不确定不重放有自动化证明。五态/独立文件结果、原时间和统计保留；fresh/同版本重开覆盖。 |
| 交接与全表面，AC-16 | PASS。Web/API/application/runtime/persistence均纳入；T4、原生、source外安装包/容器和文档证据匹配。原Base、已审实现及既有延期不变，无未解决P0/P1，不另造Task或提前选择下一Slice。 |

### A independently executed

- 仓库根 `.venv/bin/python -m unittest tests.test_automation_definition_publication
  tests.test_automation_execution_intent tests.test_v2_automation_lifecycle
  tests.test_v2_automation_run_once`：**149 tests OK / 59.167秒**。覆盖真实范围消费、权限/
  发布、核对、Task/Worker及运行结果边界。
- `web/` 中用 `playwright.python.automation.config.ts` 跑create-dialog/lifecycle/run-once的
  9项关键原生用例：**9 passed / 15.5秒**。包括真实Incoming媒体整理、连续运行失联核对、
  发布后同伴变更、编辑退出/提交未知、启用后立即重开与窄屏/键盘/reduced-motion。
- 独立复跑 B 的原始慢读取探针，只改本地证据输出目录：**1 passed / 3.3秒**。
  从现有列表创建→编辑启用保存→暂缓真实定义GET回复→立即重开只改名称→保存；请求和
  SQLite回读仍为enabled=true，没有伪造定义回复或最终状态。检查本轮桌面/390px截图，
  临时spec已撤出工作树，探针源码保留。首次探针命令因cwd路径错误未启动用例，修正后执行；
  首轮日志保留，不算产品失败或隐去命令错误。
- 核对B manifest全部15项文件SHA256匹配；实际source/wheel/container三模块hash一致，
  精确wheel `eb244e651dc952d94318dd8ac164974e69b901e86e350e60d0c9f923e14974ca`，
  镜像 `mediaflow:b-task49-2-6baa0e50` / ID
  `sha256:3cfac7148ba68a383f8ae422b18be279bc29a8ada372bb3ced6d393f13f29666`。
  未机械重复B全量/发布矩阵。本轮164个本地Markdown链接/锚点检查通过。文档/治理
  consumer提交前28项中1项按规则拒绝未checkpoint的Contract（其余通过），提交后复验；
  两轮实际日志保留于 `documentation.log` / `documentation-after-checkpoint.log`，不伪报首轮通过。

A本地证据：`.git/validation-evidence/edef2b9dfb3726f8aca6b4d7c4a7ae233f900d2c/a-slice49/`；
`focused-python.log`、`native.log`、`reopen-corrected.log`、probe源码/JSON/截图与review manifest
可核对实际命令及结果。仅本地可取，不宣称远程可用。

### B final evidence and retained limits

B实际全Python **2603 tests / failures=1 / skipped=7**；唯一失败为Task文档测试分工标题，
`054602e6`仅修文档后同一文档消费者 **8 tests OK**，其他执行输入未变，合法复用其余证据。
不把原全量命令写成OK。Web **1324 passed / 92文件**，默认E2E **253 passed**；首轮
252/1的trace输出ENOENT与独立目录完整复跑均保留。原生首轮 **46 passed / 1 failed**，
重开编辑读取超过期限；当轮collection GET约10.8秒，具体原因未证实。隔离完整复跑
**47 passed**；A此次关键重开/未知用例亦通过，尚无可重复产品阻塞证据，原失败trace不删除。
wheel/smoke/container安全通过，source外安装消费者与无网络容器各 **24 tests OK**。

7项skip仍为未配置真实OpenList/SMB/S3及Local/SMB/OpenList/S3耐久性专项，属既有合同排除。
ResourceWarning与既有构建warning保留。未知响应是实际发布/准入后的浏览器回复注入，不是
物理网络分区。未核对用户历史Task数据库；无旧任务修复、跨版本升级、生产外部服务验收或
部署声明。B49.1测试占比未达用户限制；B49.2本轮活动墙钟642.2/1440.9秒=44.6%，累计
进程1299.0秒不满足低于50%口径，执行偏差保持披露，不用空等或省门禁修饰。

CURRENT要求、旅程、架构、README/release指引及Slice/Roadmap/Progress/Task指针在本次
闭环一致对齐。复盘已读A/B/Developer经验；新增一条A可复用核对经验，无新增B/Developer
条目。此前B49.1-01及B49.2-01/02/03的拒绝、原证据和修正留在Git，不改写历史。

## Planning workspace（原规划记录）

仓库 `/Users/songzhidong/mediaflow`，分支 `main`，起始 HEAD 与 Base 如上。
治理预检 PASS，tracked 工作树干净，工作区和 Git 可写。保留全部预存 untracked OS 文件、
`.mgmt.log`/`.t*.log`、`15`、docs/pics 的两张自动化参考图、既有 output 目录/文件与
各 `.DS_Store`；完整起始清单在同 Base 的本地 `slice49-planning/workspace-before.txt`。
本次只 checkpoint 本 Contract、必要 TARGET 要求/旅程/架构及 Roadmap/Progress/Task 指针，
并修正 README / Task Center 文档中指向旧 Slice48 的链接。
不读取用户运行数据库/私有配置/生产媒体，不改产品代码、不 push/部署/改写历史。

## Activation workspace

仓库 `/Users/songzhidong/mediaflow`，branch `main`，激活起始 HEAD
`9d70d0c211db1403bbcf536d8e619672ffd8b3d1`；原 Slice / Task Base 不变。治理预检 PASS，
tracked 工作树干净，工作区/Git可写，预存 untracked 文件完整保留、不入提交；起始清单在
该起始 HEAD 的本地 `slice49-task49.1-activation/workspace-before.txt`。原 Task Base 到激活
起点的生产代码/测试/harness diff 为空。此次按用户明确指令先由 A 提交 ACTIVE Contract，
再由用户指定的 B 代行者确认并正式激活 Task49.1；没有 Developer 实施、B 验收或 A 终审。
只改变治理状态与事实指针，不读用户数据库/私有配置/生产媒体，不 push/部署/改写历史。

## A review workspace

仓库 `/Users/songzhidong/mediaflow`，main，起点
`edef2b9dfb3726f8aca6b4d7c4a7ae233f900d2c`，治理预检PASS、tracked起点干净，工作区/Git可写。
预存untracked清单保存在A证据 `workspace-before.txt`，全部保留且不入提交。过程中另观察到
tracked `mediaflow/.DS_Store` 变化，同样保留不入提交；不推断其来源、不恢复覆盖。
本轮只提交A终审/闭环相关文档；临时probe退出后移除，原证据保留。不读用户运行数据库/
私有配置/生产媒体，不push、部署、改写历史或规划新Task。
