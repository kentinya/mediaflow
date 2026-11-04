# Slice 49 — 自动化任务创建、编辑与直接运行

```text
Slice ID: 49
Name: Automation Task Creation, Editing and Direct Run Once
Owner: A — Slice Owner / Architect / Final Reviewer
Status: ACTIVE
Base SHA: 02fb77dd713bad4dd51c29b6cfc5556ddd6d5b4e
Implementation Head: NOT SET
Working Branch: main
Development Authorization: USER ACTIVATED SLICE49; IMPLEMENTATION WITHIN FORMAL CURRENT TASK ONLY
Risk: High
Final Test Level: T4
Next Action: DEVELOPER IMPLEMENTS FORMAL TASK49.1; B REVIEWS CANDIDATE
```

## Authority and accepted baseline

用户先要求调查来源范围失败、列表运行一次不可用、编辑体验与新建不一致和新建缺少启用选项，
随后明确要求规划新 Slice，并确认使用下一编号 **Slice49**。用户进一步明确：删除编辑页
“运行一次”，创建后仍可启用/停用；创建启用的内部命令顺序不作为用户硬要求。用户现已
明确要求激活 Slice 和 Task。A 先 checkpoint 本 ACTIVE Contract，B 随后确认既有 Task49.1
草案并转为正式 PLANNED Task；Developer 仅可实施正式当前 Task。本轮只做激活，尚未写
产品代码，也不构成 B 验收或 A Final Review。生命周期与测试责任仅遵循
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

本 Slice 选择 [V2 Requirements](docs/v2-requirements.md#automation-forms-and-direct-run-once--target-slice49-active)
的 TARGET `V2-AUTO-013–015`。其中创建可选启用明确调整 `V2-AUTO-002/010` 与
[CURRENT 创建旅程](docs/product-experience.md#current--complete-native-automation-workspace-accepted43-amended46)
的“新建始终关闭、另行启用”结果；复制仍默认关闭且不继承授权。
其余为 `V2-AUTO-001/002/004/011` 既有结果的入口与正确性修正。
保持 `UX-001–007/010`、适用的 `REQ-SCHED-001–007`、`REQ-TASK-005–010`、
`REQ-SAFE-001–009` 和 `V2-TASK-001–014` / `V2-AUTO-012` 的现行 V2 语义。
新目标尚未交付；CURRENT 描述仍记录已接受产品，冻结 V1 含义不变。

完整目标旅程见 [Product Experience TARGET](docs/product-experience.md#target--automation-forms-and-direct-run-once-slice49-active)，
技术边界见 [Architecture TARGET](docs/architecture.md#target--automation-forms-and-direct-run-once-slice49-active)。

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

## Implementation planning and validation allocation

Task49.1“来源范围正确的列表一键运行”是首个选定实施单位，先完成 RO-1 / RO-2。
其当前状态、原 Base、具体验收及 Developer/B 计划以 [TASK.md](TASK.md) 为准；既有草案
须由 B 对本已提交 ACTIVE Contract 明确确认后转正式任务。RO-3 / RO-4 保持本 Slice 的
必需结果，但不扩入 Task49.1。B 后续按完整行为规划，不按字段、层或验收条目拆 Task，
不固定数量；本次激活不规划或实施下一 Task。

最终按 **T4**：范围消费和真实执行入口、Active 发布/权限以及未知响应/并发都受影响。
Developer 跑新增/修改/直接受影响测试与相关静态检查；B 按
[workflow §6](docs/development-workflow.md#6-test-levels) 承担完整回归和适用安全/打包/原生门禁。
聚焦验证至少包括：现有 Automation Run once / definition publication / intent / admission /
lifecycle / operations / authorized execution matrix，Task engine/源历史/四类恢复，以及 Web
创建/编辑/列表路由、命令 session、API models 和真实 Python 浏览器生命周期/Run once。

B 使用隔离临时 Storage、SQLite、合成 Provider，以真实 API→Task→Worker 验证来源矩阵，
通过真实浏览器从列表点击、创建/编辑、失联核对、并发发布、返回列表和桌面/窄屏截图。
故障注入绑定现有生产边界，不手写最终 Task/Result 冒充执行。适用 source-external wheel/
container 的 fresh与同版本重启、启用/准入/范围/权限消费证明沿用 workflow 门禁；不借机
要求生产媒体、真实账号或既有排除的跨版本升级。已知问题先复现再做昂贵门禁。

## Final validation, Closure Packet and A Final Review

**已激活，尚未实施或接受。** Implementation Head、B 实现候选/最终验收、Closure Packet
和 A Final Review 均未产生；正式 Task 状态以根 Task 为准。本轮只检查授权/文档/链接/治理，
调查探针与文档检查不等于缺陷已修复或本 Slice PASS。不得提前把 TARGET 写成 CURRENT。

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
