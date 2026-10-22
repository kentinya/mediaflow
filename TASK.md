# Task45.6 — 独立 Preview 完整退出与整理分析/固定计划统一

Authority：已提交 [SLICE.md](SLICE.md) RO-8 / S-10 / AC-8、
[Preview 退役设计](docs/preview-retirement-spec.md) 与
[Development Workflow](docs/development-workflow.md)。
角色经验：[B](docs/agent-experience/task-planner-reviewer.md) /
[Developer](docs/agent-experience/developer-implementation-role.md)。

```text
Task ID: 45.6
Parent Slice: 45
Status: FIX REQUIRED
Task Base: 2687e5b3eaa6f686d54c51930765e0ba904f69b5
Difficulty: High
Test Level: T4
Planner / Reviewer: B
Required Outcome: RO-8 / S-10 / AC-8; affected RO-1–7 safety and journeys
Next Action: SAME TASK — ROUTE INTENT-PAGE ANALYSIS THROUGH DURABLE WORKER/FENCE; B RETAINS T4 GATES
```

## Goal

操作者从任务中心/Files的新建整理或原任务恢复入口显式分析，在当前界面查看完整固定
计划的摘要、主文件/附件、冲突与未就绪原因，选择合法就绪子集后明确确认，再跟踪
Worker执行和独立结果。CLI `organize` 不带 `--execute` 保留同义完整零媒体变更分析。
不再存在可独立创建、调度、查询、控制或续跑的 Preview 产品；Rules/配置检查及
Automation授权前校验仍使用原候选/定义/权限的共享分析。失败说明阶段、持久状态、
效果和原界面的补正/重读/重新分析动作；成功与未知效果不重放。

完整适用旅程：Preview退役设计第1–5节、任务中心规范第3–5节、Product Experience
的Manual organize/Tasks与TARGET独立Preview旅程；稳定ID为V2-OPS-010/012/013、
V2-RULES-006、REQ-SAFE-001–008及REQ-RECOVERY-006/007/009。

真实缺口（Base）：final_cli注册 `preview` / `batch preview` / `jobs submit preview`，
AutomationCommand.PREVIEW、Preview-only Interval/Cron Schedule及可续跑Task支持集合仍在。
V2 router仍装配PreviewNew/Detail、OrganizePreview、AutomationPreview、PreviewAnalysis页面；
service_api保留独立路由/aliases和PreviewAnalysisService/Worker装配。SQLite fresh仍创建
preview_analyses、manual_previews/items和automation_task_definition_previews/items。
后两组同时承载真实整理计划/确认/恢复证据，不能盲删。CLI DryRun主要走
MediaOrganizerService，Web计划还由ManualOrganizePreviewService/StrategyTestRunner编排；
`_analysis_only_preview`只覆盖特定后台Preview，直接organize分析仍需统一finding语义。

前项45.5已由B在 `3e2cb31aca211a7dcb7fa7c4ba4883d55b951974..d9a1f429fddeaf7f2c82fa6fc1ebf8e6b7631d44`
判PASS，结果在Task Base的TASK.md；用户授权B恢复4项测试的角色例外到此结束。
本Task不改写前项结论，不把它当RO-8或整个Slice通过。

## Implementation Scope

一个完整跨层行为单元，不按路由/表/测试拆Task。按以下顺序实施：

1. 沿CLI/API/V1/V2→应用→既有Task/Worker→仓储列出可运行Preview及共享消费者。
   检查final_cli、service_api/operator_ui、routes/router、operations DTO/API client、
   domain automation/task_persistence/scope_continuation、preview_analysis、
   manual_organize_preview、automation_task_definition_preview、恢复与Automation
   grant/execution/run_once、RulesObjectAnalysis/ConfigurationObjectService。
   简述每项删除或真实职责承接位置；对象局部试算/历史结果用词不等于独立产品。
2. 将Web创建/Files/恢复与CLI不执行模式统一到Organize DryRun共享应用分析/计划行为。
   复用Scanner/真实有界稳定观察、策略/Provider/Planner/附件/冲突与已有Task/Worker；
   API直接调用应用服务，不启动CLI，不另造分析引擎/队列。保持真实scope、合法历史pin、
   当前候选配置与策略选择。仅分析的识别/Metadata/分类/冲突未就绪保留findings及补正入口，
   不写正式执行WAITING_CONFIRM/Review/Conflict/Recovery待办，不取得单次/无人值守权限；
   分析失败/取消不冒充整理成功。真正执行及其恢复的阻塞仍保留原职责。
3. 在整理职责下持久保存完整固定计划和逐项来源/配置/版本/附件/能力/冲突/effect证据，
   再投影当前页摘要。承接现Preview记录及确认/恢复关联，移除独立产品生命周期和专属schema；
   不以只改名继续暴露独立产品。精确子集确认后原子绑定该份计划、实际权限和破坏性范围，
   重验来源/计划/许可后由既有Worker/OrganizerExecutor执行；实质变化先更新摘要再确认。
   保留去重、丢响应核对、claim/lease/fence、结果/audit、主文件/附件独立性、原pin与非重放。
4. 删除独立Preview全部CLI注册/帮助、V1/V2路由/导航/按钮/深链、API及aliases、
   Job/Task/command/定时配置/调度/Worker dispatch/retry/resume/continue/readiness/action，
   专用服务/模型/仓储/回调/装配和死代码。diagnostic/scheduled/definition-bound无独立保留例外。
   旧输入经正常auth和共享支持类型校验走普通not-found/参数/不支持类型错误，必须在
   Storage发现/Provider/Task或Job准入/许可前停止；不自动转成organize，不新增410/退役页/
   提示/专用拒绝guard/隐藏executor。旧Preview-only schedule不可因默认值删除变成执行。
5. Rules对象局部测试、完整流程检查、Naming/Classification等纯试算与配置发布边界保持；
   需要完整规划的消费者复用共享链，不能强迫局部测试解析无关策略/访问Provider。
   Automation授权前分析继续绑定精确定义/范围/候选配置，分析不授权，Run once/已授权
   自动整理仅替换必需耦合，不重做冻结43页面、指标/设置或调度引擎。
6. 更新测试/fixture、wheel/Docker/Worker/browser harness，使其从合法整理分析/计划或
   显式受支持工作构造证据；保留等义零变更/权限/来源变化/pin/并发/混合结果和非重放断言，
   只删除独立产品专属覆盖，不扩大重试/超时或隐藏skip。fresh不建独立产品schema；
   支持的整理数据重开/重启和失败原子性保持。不DROP/清空/重建现有运行库，不建设旧
   Preview迁移/停止/接管/历史兼容。必要CURRENT/TARGET事实准确，A负责最终文档闭合。

### 开发者执行细则

以下细则展开上面六步，不新增 Task、产品状态或验收范围。按依赖顺序完成；每步的
“自查”是下一步的前提，不要求每步单独提交，也不要每步重跑全部测试。这里列出的
文件/方法是当前代码导航锚点，不要求保留旧 Preview 命名或照搬旧模块边界。

#### 0. 开始前：固定范围，保护现有工作

1. 阅读 AGENTS、workflow、`git show HEAD:SLICE.md`、本 Task、Developer 经验，以及
   Preview 退役设计全文、任务中心规范第3–5节和对应 Product Experience/Architecture
   CURRENT/TARGET。当前 Task Base 不因开始开发或补充本指导而改变。
2. 运行 `python3 scripts/check_governance.py`，记录当前 branch、完整 HEAD 和
   `git status --short`。检查工作区及 Git 可写；只在当前授权分支继续，不切换到旧快照开发。
   已有图片删除、日志、截图、压缩包、`.DS_Store` 和私有文件不属于本 Task，原样保留。
3. 正式实施时按 workflow 更新 Task 为 IN PROGRESS；不要改 Slice Base、RO、Roadmap、
   旧 Task PASS 或 Slice 状态。遇到必须扩大 Contract 才能完成的真实问题，交 B/A 处理。
4. 只用临时 Storage、fake Provider、local server 和测试数据库；不读取用户运行库、
   `config/alist.json`、私有配置或真实媒体，不通过清库解决开发/测试问题。

#### 1. 先画调用清单：按职责分类，不按字符串删除

先用 `rg` 和调用方阅读形成简短清单；有了下表涉及的主链即可开始修改，不做全仓漫游。

| 当前导航锚点 | 要确认什么 | 应有处理 |
|---|---|---|
| `mediaflow/final_cli.py` | parser、batch/jobs、schedule、任务控制、Worker 装配和 `_analysis_only_preview` | 删除独立命令及专属分支；保留 organize 不执行模式并接共享行为 |
| `mediaflow/interfaces/service_api.py`、V1 operator UI | 独立路由/alias、服务构造、现有整理创建/摘要/确认/恢复调用 | 移除独立产品入口；共享消费者直调应用服务 |
| `mediaflow/application/media_organizer.py`、同目录 `strategy_test.py` | CLI 生产处理、逐项分析、冲突/决定/恢复记录的写入点 | 收敛共享分析/规划语义，不复制处理链 |
| `mediaflow/application/manual_organize_preview.py`、同目录 `manual_organize_execution.py`、`manual_recovery_continuation.py` | 当前计划生成、来源绑定、权限准入和恢复关联 | 先承接真实整理职责及证据，再移除产品生命周期 |
| `mediaflow/application/media_discovery.py` | 有界发现、稳定观察、冻结、准备分析与计划关联 | 保留发现能力；更换对独立分析服务和旧计划生命周期的耦合 |
| `mediaflow/application/preview_analysis.py` 及对应 domain/持久化 | 独立分析准入、查询、控制、claim/Worker | 独立生命周期删除；长准备所需能力放回既有整理/Task/Worker职责 |
| `mediaflow/application/automation_task_definition_preview.py`、同目录 `automation_run_once.py`、`automation_definition_execution.py` 及授权服务 | 定义绑定的计划证据、授权校验、Run once 耦合 | 保留共享分析和明确授权；删除独立定时 Preview，不重做43 |
| `mediaflow/application/rules_object_analysis.py`、同目录 `configuration_objects.py` | 局部试算、完整检查、候选与发布边界 | 局部能力保留；需要完整规划时接共享链 |
| `mediaflow/domain/automation.py`、同目录 `task_persistence.py`、`scope_continuation.py`；`mediaflow/infrastructure/sqlite_runtime.py` | 支持工作类型、序列化、调度、重试/继续、数据库初始化 | 移除独立类型与专属 schema；支持整理持久化不回归 |
| `web/src/routes/router.tsx`、operations 页面、entities/operations 和 API client | 路由、导航、动作、DTO、创建/恢复页内摘要 | 不留独立 Preview 页面；原界面使用整理准备/计划数据 |
| `tests/`、`scripts/`、打包/容器/browser harness | 哪些 fixture 用旧 Preview 播种支持工作 | 改为合法整理分析/计划，保留仍适用的安全断言 |

清单只需记“入口/调用方 → 当前职责 → 删除或承接位置”。例如：
`PreviewAnalysisService.admit_manual/admit_definition` 是旧准入锚点；
`ManualOrganizePreviewService.create` 中的固定计划不是可以随服务名一起丢弃的数据。
禁止先全仓替换 `Preview` 为 `Plan`，也不要求局部试算/历史结果中的这个词零匹配。

自查：至少能指出一次正常创建和一次恢复从 UI/API 到持久计划、确认准入、Worker 的
实际链路；明确每个要删服务的共享消费者由谁承接，避免删到一半再用兼容 wrapper 补洞。

第一处实际修改不要从全仓删文件开始：选临时根里的一个直接文件和fake Provider，
先让共享 Organize 分析产出一个零媒体变更结果，再让 CLI 不执行与手动计划调用方复用。
接上完整计划持久化/同页摘要/精确确认后，再扩展目录、恢复、其他消费者并删除独立入口。
这是同一 Task 的增量做法，不是另拆“先只交后端”的 Task，也不允许把中间态当最终交付。

#### 2. 统一 analysis-only：先让共享行为正确

1. 从 `MediaOrganizerService`、`StrategyTestRunner` 和手动计划生成的真实调用处切入，
   提取/复用同一应用层分析与规划行为。复用已有 Scanner、Parser、Recognition、Metadata、
   Naming、Classification、Planner、附件匹配，不再写一个 Web 专用规划引擎。
2. Web 创建/Files/恢复和 CLI `organize` 不执行模式使用同一生产决策语义，保留各入口
   原本合法的 scope、配置快照和策略选择。不要为比较结果强制所有入口使用当前 Active。
   API 不启动 subprocess，不调用 CLI main，不解析 CLI 输出生成计划。
3. 当前 `_analysis_only_preview` 只对特定后台 Preview 生效；不能简单删参数或改命令名。
   把只分析语义放到共享应用行为，在所有仅分析入口显式生效，同时保留真实执行及恢复
   写入正式阻塞状态的职责，不能把整个执行链一律改成 analysis-only。
4. 对识别歧义、Metadata 未选/失败、分类未命中、目标冲突，分别检查写入链：只分析时
   保存 finding/未就绪原因、证据和合法补正动作，不新增正式执行的 WAITING_CONFIRM、
   Review、Conflict 或 Recovery 待办；明确执行尝试产生的真实阻塞仍正常持久化。
5. “零媒体变更”不等于“不能保存分析记录”：长准备可使用既有持久 Task/Worker，保存
   分析进度和完整计划。禁止的是执行准入、单次/无人值守授权和媒体 mutation，不是要求
   所有分析场景的 Task 总数为零。不得另建一套分析队列、调度器或隐藏 Preview executor。
6. 分析取消/失败/范围不完整保持其真实状态；完成一次分析不能标为媒体整理成功。
   不确定总数不编造进度；完整性触及实质边界时，不把截取前 N 项当作可确认完整范围。

自查：同一个冲突样本在 CLI 不执行与 Web 准备中都有可查看解释，Storage mutation、
执行权限及新增正式执行待办为零；同样冲突在真实执行流程中的决定/恢复职责没有消失。

#### 3. 承接固定计划持久化：不能只存摘要，也不能盲删表

1. 阅读手动计划和定义计划的 domain、仓储协议、SQLite fresh 初始化、读写/重开逻辑。
   在 `sqlite_runtime.py` 追踪 `manual_previews`、`manual_preview_items`、
   `automation_task_definition_previews`、`automation_task_definition_preview_items` 和
   `preview_analyses` 的实际消费者，分别判断独立生命周期数据和支持整理所需数据。
2. 在整理自己的职责中保存/关联完整固定计划。至少保持现有证据：来源库/Storage/相对路径
   与 Storage 取得的来源指纹；操作者、固定配置 snapshot/digest、输入/项版本；识别和
   Provider 身份、实际策略、目标/操作、主文件/附件、冲突/能力、完成/未知效果和恢复关联。
   这是必须保住的信息，不是要求另建重复字段/表；复用合理的数据结构和已有约束。
3. 同页摘要从该份持久计划投影，确认/Worker读取同一份权威计划。浏览器传回的目标路径、
   指纹、策略结果或摘要文本都不能成为执行权威；不在确认时另算新计划并直接执行。
4. 计划、版本、逐项关系及确认/恢复关联保持原子性；失败不发布半份可执行计划。
   保持已支持整理数据的 reopen/restart 和失败原子性，包括它们当前使用的必要存储版本
   处理；不借此建设旧独立 Preview 的迁移、双写、历史兼容或自动数据重建框架。
5. 最终 fresh 数据库不创建独立产品专属 schema。不要对已有运行库执行 DROP、清空或
   重建，不把“首次部署退出”解读为允许破坏既有数据库。删除旧代码前，确认共享证据
   已由整理职责承接；只改表名而保留独立产品准入/调度/续跑不算完成。

自查：关闭并重新打开测试仓储后，仍能从合法整理记录读取完整计划及确认/恢复关联；
fresh schema 不含独立产品表；没有运行时清库、删除旧用户数据或依赖旧服务才能反序列化。

#### 4. 接通新建整理和 Files：同页分析，不绕回旧页面

1. 以 `OrganizeCreationPage.tsx` 及其 API client/DTO 为主要落点；保留 Files 单文件、
   多文件、文件夹/混合选择的返回上下文。ResourceLibrary 是来源，不能顺手开放
   MediaLibrary Organize，也不能从浏览器接受任意 Storage 路径作为授权来源。
2. 显式“分析/生成摘要”后，走真实有界发现与过滤/稳定性观察，再到共享分析。
   从 `MediaDiscoveryService._begin_preparation_analysis/preparation_preview_id` 等调用处
   检查发现→分析→固定计划的关联，不要只改页面调用后留下后台旧装配。
   直接文件和目录遍历都适用真实 elapsed stable-size；不能用旧 mtime、首次 stat、
   空 observation 或固定 sleep 伪造稳定，也不能重新引入 FileIndex/预Scan。
3. 原页面展示准备进度和摘要：来源及完整性、就绪/未就绪/排除项及原因、主文件和附件、
   可展开来源→目标、实际操作/策略、冲突、能力和覆盖/来源清理影响。未就绪项留在
   准备界面补正；刷新/进入页不暗中调用 Provider、重新分析或执行。
4. 只允许明确选择合法就绪项，确认按钮按实际选择显示 N。未选/未就绪项不被隐式纳入，
   不因确认某子集被覆盖成成功/忽略；没有合法范围或存在实质不完整时不给可执行确认。
5. 失败展示阶段、已保存状态、是否有媒体效果及下一动作；保留可修正输入。
   来源/方案变了，原页重分析并更新摘要，再明确确认；不要只显示“失败，请重试”。

自查：直接文件、含附件的目录、就绪/未就绪混合输入均能在原页完成；没有旧 Preview
页面跳转，没有操作者复制 token/版本/hash 的步骤，也没有点击分析就自动授予执行权。

#### 5. 接通确认和恢复：沿用权威准入，不另写执行器

1. 阅读 `ManualOrganizeExecutionService.begin_web_execution`、授权/admit 和仓储事务，
   把其中精确计划绑定接到承接后的计划模型。保留服务端管理单次权限、所选项/版本、
   固定上下文、来源/能力/冲突再验和独立覆盖/清理许可；不能用一个 `confirmed=true`
   绕过既有约束。确认必须原子绑定计划/子集/权限/持久执行身份。
2. 执行继续走既有 Worker、claim/lease/fence、锁与 `OrganizerExecutor`。准入之前和
   每个尚未发生的媒体变更之前保持相应权威校验；不能在 API handler 或计划服务直接搬文件。
3. 重复/并发确认只对精确等价绑定核对已有执行；不同子集、权限或版本不能合并成同一个
   “最近任务”。确认响应丢失先按原持久请求核对，状态不明时不自动重发或补发权限。
4. 沿 `ManualRecoveryContinuationService.prepare_summary/confirm_prepared`、通用
   recovery/scope continuation 和 `TaskItemRecoveryPanel.tsx` 接好五类恢复。
   保存识别/Metadata/分类/冲突决定或修复依赖均不执行；重分析只作用于合法问题范围，
   新阻塞按真实类型呈现；新摘要在当前处理界面，再明确确认就绪子集。
5. 合法历史 pin 不随新 Active 改绑；pin 缺失/不可恢复时拒绝并说明补救，不能用当前配置
   兜底。成功/忽略/效果未知项不进入重跑；主文件验证成功保持成功，附件异常独立保留
   来源/目标/原因/步骤与实际固定策略指引，不新增附件-only恢复或为了附件重放主文件。
6. 受理不等于已解决。原失败记录、恢复尝试与逐项 Result/审计保留；列表/计数按持久
   当前问题更新。结果写入失败或 stale owner 不能触发媒体重放；未知效果仅提供核查动作。

自查：验证精确子集、双击/并发、丢响应、来源变化、新 Active/旧 pin、缺 pin、混合结果
和附件警告。必要场景用真实生产准入链构造，不把人工拼出的状态当作已证明的生产路径。

#### 6. 接好 Rules、配置和 Automation：保能力，不保独立产品

1. Rules 对象局部分析保持局部：Naming/Classification 的纯试算不强行访问 Provider，
   不因无关策略缺失而拒绝。完整流程检查才使用需要的完整分析/计划依赖。
2. 配置测试仍针对明确候选/修订；编辑使相关证据失效，未发布候选不冒充 Active。
   保持发布校验，不用“已成功分析”代替发布/执行授权；保留 C用NamingA/ClassificationA
   仍为C 的自动化回归。
3. Automation 授权前校验绑定精确定义、范围、配置与版本，分析不授予无人值守权限；
   现有授权执行/Run once 只改必要共享依赖，不重做43页面、指标、设置和调度引擎。
4. 删除 Preview-only Interval/Cron、定义绑定命令和调度/Worker分支。旧配置值必须被
   普通支持类型校验拒绝，不能通过 `get(..., ORGANIZE)`、兜底默认值或省略验证变成执行。

自查：不装配独立 Preview 服务/仓储也能完成上述支持行为；只分析零执行授权；旧定时
Preview 被拒绝，没有创建替代 organize Job，也没有继承不匹配的破坏性权限。

#### 7. 删除独立产品全部入口与装配：最后按调用闭环收网

逐项删除并查调用方，不只隐藏导航、不留无消费者实现：

- CLI 注册/帮助：`preview`、`batch preview`、`jobs submit preview`，相关 options/文档。
- Web/V1 路由/页面/按钮/深链：PreviewNew/Detail、OrganizePreview、AutomationPreview、
  PreviewAnalysis；共享摘要组件可内联复用，但不能保留独立可运行页面。
- API 创建/读取/列表/控制/导出及 aliases；客户端方法、DTO、action/readiness、链接生成。
- Job/Task/AutomationCommand 支持集合、调度配置/准入、dispatch、retry/resume/continue；
  默认值、序列化和运行端校验一起核对，不能只删 argparse 入口。
- 专用服务/domain/仓储/schema/回调/Worker构造、启动 wiring、打包/示例/fixture死依赖；
  手动/定义计划的共享职责已在前面承接后再删，不通过保留 import stub 让安装测试过关。

旧URL走正常认证后的普通 not-found；旧命令/配置走普通参数或共享不支持类型错误。
验证顺序必须保证在 Storage发现、Provider调用、任何工作准入和执行许可之前停止。
不新增 `if preview: retired_error`、410、退役提示、重定向、自动转换或隐藏兼容执行器。
源码检索只用于找漏项，真实拒绝行为要测试；不要删除纯局部 `naming_preview` 等合法能力。

#### 8. 按风险写受影响测试：先修实现，再跑必要组

在下方 Required Tests 的既定命令/分工内落实以下场景。测试名按最终模块命名调整，
改名/删除模块时同步命令；不得为维持旧命令而保留产品，也不得把仍适用断言删掉。

| 场景 | 至少断言什么 |
|---|---|
| 旧CLI/API/URL/通用Job/配置值/继续请求 | 正常auth/解析边界的普通拒绝；没有Storage发现、Provider、工作准入、权限或媒体变更 |
| CLI不执行与Web分析 | 同输入/合法pin/策略的完整计划、目标、附件、冲突/未就绪等义，不比较随机ID/时间戳 |
| 四类准备未就绪 | finding可读、可补正；没有新增正式执行待办/执行授权，分析失败/取消不冒充整理成功 |
| 直接文件与目录 | 真稳定观察、有界完整性、附件；不预Scan、不索引，不偷偷执行first-N |
| 确认就绪子集 | 精确选中项/版本/计划/权限绑定；未选/未就绪兄弟独立，未确认媒体bytes不变 |
| 来源/计划变化与pin | 实质变化要求新摘要/确认；合法旧pin保持，缺pin安全拒绝，不用新Active兜底 |
| 重复/并发/丢响应/stale lease | 核对同一精确持久请求、不重复准入/消费许可；旧owner和不同选择不能执行 |
| 恢复与混合结果 | 真实五类处理链可继续；成功/忽略/未知不重放，附件警告不重跑主文件，结果失败无自动重放 |
| Rules/配置/Automation | 无独立服务仍可用；候选/定义/权限边界、局部试算和RecognitionType身份不变 |
| fresh/reopen/失败原子性 | 无独立schema；支持整理计划/结果/关联可重开，不清库、不发布半份可执行计划 |

可用一个小型混合样本贯穿自查（仅测试数据，不是新增产品规则）：A为合法就绪主文件并带字幕，
B为Metadata待选，C为目标冲突。首次分析显示三项及各自原因，但执行许可/正式执行待办/
媒体变更为零；只确认A后仅执行A及其确认附件，B/C仍可在准备界面补正。另用一次真实执行
失败的原任务验证恢复，不能拿B/C的准备finding伪造正式执行失败。再分别插入“确认前来源
变化”和“确认成功但响应丢失”，验证前者要求新摘要/确认，后者核对同一执行而非重放。

新增 `tests/test_preview_retirement.py` 并从真实解析/服务装配/仓储入口验证，不只查源代码
是否包含字符串。底层用 spy/fake计数与临时真实Storage核对效果，不能把所有权威逻辑都mock掉。
先跑新增失败用例与直接相关组；检查生产 wiring/导入和修改fixture，但不由Developer执行
B的全Python/Web/E2E、wheel/Docker/release矩阵。计时/质量检查沿用下方已有要求。

#### 9. 交接：一个连贯候选，报告真实结果

1. 重新核对调用清单：每个独立入口已删除，每个共享消费者有承接；不留第二套运行链。
   受影响测试覆盖失败/恢复，不仅是“正常文件可以复制”。
2. 按下方 Developer 命令执行实际受影响检查与 `git diff --check`，记录真实命令/结果、
   skip、失败和未验证项。测试发现缺陷修根因；不放宽断言、加重试/超时或隐藏skip。
3. 检查完整diff和 `git status --short`；只暂存本Task文件，保留开工前的dirty/private文件，
   不用 `git add .`。按workflow创建连贯本地checkpoint，不amend已审历史，不push。
4. 报告固定SHA、主要行为/承接位置、删除/迁移断言简述、受影响检查及风险，交
   READY FOR B REVIEW。验收未做写pending；不自判PASS，不关闭Slice，不规划下一Task，
   也不等待或代跑B全量门禁才交接。

## Acceptance Criteria

- [ ] Web/V1/API/CLI/Job/定时/Worker/重试/继续/包内装配均无可运行独立Preview产品、
  专用schema或退役兼容层；逐入口旧输入普通拒绝且零发现/Provider/准入/许可/媒体变更。
- [ ] 真实临时Storage及fake Provider完成直接文件/有界目录→真实稳定观察→完整生产
  分析→持久完整计划→同页摘要；CLI不执行模式与Web对同输入/pin/策略有等义计划、附件、
  目标、冲突/未就绪解释。Web直接应用服务，不从CLI输出或摘要文本重建执行计划。
- [ ] 未确认零媒体mutation/执行许可；各类未就绪只留准备findings、不制造正式执行待办。
  原界面补正并重新分析，成功兄弟独立；取消/失败/不完整不显示无警告成功或执行first-N。
- [ ] 确认合法就绪子集才执行固定计划；未选/未就绪项保留，实质来源/计划变化需新摘要/
  新确认。重复/丢响应、并发准入、stale owner、权限/来源/pin缺失均安全且可恢复。
- [ ] 合法旧pin不随Active改绑；真正执行的等待决定及五类恢复仍可用。主文件验证完成
  不因附件异常重放，附件原因/目标/策略指引可见；未知效果只核查，结果保存失败不重放。
- [ ] 无独立Preview装配仍完成Rules局部/完整检查、配置分析发布、Automation授权前校验
  与受支持执行；保持C用NamingA/ClassificationA仍为C及候选配置/定义/权限边界。
- [ ] fresh及支持整理数据重开/重启/失败原子性、普通维护/传输/任务历史/结果均保持；
  清洁wheel/源码外消费者/生产Docker/常驻Worker/served assets实际匹配候选。
- [ ] Developer受影响检查已交接；B固定候选完整range、独立关键复现及适用T4门禁有实际
  结果。未提供必需门禁pending，不由旧Task PASS推定。全部Slice RO完成才交A，B不关闭。

## Required Tests

分工、复用与耗时规则以[workflow §6](docs/development-workflow.md#6-test-levels)及用户要求为准。
每轮测试/build/quality耗时（失败及并行逐项累加）必须小于该轮实际工作时间50%；
先读代码/修复已知阻塞，再做必要检查，不等待凑比例。仅用隔离临时根/fakes/local server，
不读用户运行库/私有配置/媒体。被退役测试模块改为等义整理测试后更新下列精确命令，
不得为了命令继续保留独立产品；删除与断言迁移在交接中简述。

### Developer — affected tests

仓库根，先governance；新增 `tests/test_preview_retirement.py` 覆盖旧输入拒绝、fresh无
独立schema、共享analysis-only的零执行准入/权限、合法整理入口和生产装配，不只查字符串。
按实际修改执行下列受影响组；核心新模块及直接失败用例必跑：

```bash
python3 scripts/check_governance.py
PYTHONPATH=tests .venv/bin/python -m unittest test_preview_retirement test_scan_retirement test_file_index_retirement
PYTHONPATH=tests .venv/bin/python -m unittest test_manual_organize_intent test_manual_organize_preview test_manual_organize_execution test_v2_manual_organize test_organize_preparation
PYTHONPATH=tests .venv/bin/python -m unittest test_recovery_continuation test_scope_continuation test_task_center_recovery_lineage test_metadata_correction_continuation
PYTHONPATH=tests .venv/bin/python -m unittest test_automation_run_once test_preview_retirement test_automation_definition_execution test_automation_authorized_execution_matrix
PYTHONPATH=tests .venv/bin/python -m unittest test_configuration_organize test_v2_rules_workspace_previews test_task_persistence
```

若修改调度/队列/普通CLI分析/持久控制，追加其直接受影响模块（例如
`test_automation_admission`、`test_automation_job_fencing`、`test_manual_operations_contract`）；
如原Preview专属模块退役，将其中仍适用安全断言迁入上述新模块并运行，不保留失效生命周期。
Python只对changed files运行ruff check/format。`git diff --check`必跑。

Web在web/运行本轮实际修改测试，最低覆盖路由退出、同页创建与恢复、共享客户端；
以下为当前真实文件，删除产品专用页面测试时迁移保留断言：

```bash
npm run test -- run src/routes/router.test.tsx src/features/operations/OrganizeCreationPage.test.tsx src/features/operations/OperationsInventory.test.tsx src/features/operations/TaskItemRecoveryPanel.test.tsx
npm run test -- run src/features/rules/RulesObjectTestPanel.test.tsx src/features/operations/AutomationRouter.test.tsx
```

对修改的Web文件运行 `npx eslint <changed-files>` / `npx prettier --check <changed-files>`；
对DTO连线执行 `npm run typecheck`。需要真实集成验证时只跑修改场景：
`npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts -g '<changed-scenario-title>'`。
Developer不跑全Python/Web/E2E、wheel或Docker/release矩阵，不准备全量证据包；
完成受影响检查即提交连贯checkpoint并交READY FOR B REVIEW。

### B — acceptance and full regression

B在明确提交SHA上审查 **Task Base..Head完整diff**，核对scope/消费者/专属删除/安全断言及
预存dirty；先独立复现阻塞，修正继续45.6，范围问题交A。B执行workflow
[共享全量门禁](docs/development-workflow.md#shared-full-regression-commands)的Python/Web/
示例/依赖/禁止依赖/compile/full E2E/清洁wheel/安装消费者/安全覆盖，不交回Developer。

生产build后，web/逐spec使用独立harness/output：

```bash
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts --output ../.git/validation-evidence/<candidate-sha>/task45.6/inventory
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/live-files.python.spec.ts --output ../.git/validation-evidence/<candidate-sha>/task45.6/live-files
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-task-center-visual.python.spec.ts --output ../.git/validation-evidence/<candidate-sha>/task45.6/visual
npm run test:e2e -- --config=playwright.python.unicode-principal.config.ts tests/e2e/operations-principal-identity.python.spec.ts --output ../.git/validation-evidence/<candidate-sha>/task45.6/unicode
```

B独立脚本/真实入口逐项核验，不能用源码检索/fixture标签替代：

1. 枚举旧CLI/API/URL/通用Job/定时/定义绑定/重试继续入口，真实auth/参数解析及支持类型
   边界拒绝；前后核对工作/许可/Provider/Storage计数及媒体bytes，未创建替代organize。
2. 同配置/来源的CLI不执行与真实API/Web整理计划对照，检查完整持久计划而非摘要。
   四类识别/Metadata/分类/冲突未就绪仅为findings，零正式执行待办；补正→同页新摘要→
   精确子集确认→真实Worker/Executor/结果/重开，直接文件/目录/附件及实质范围边界覆盖。
3. 原pin/新Active、来源/计划变化、重复/丢响应、准入事务竞态、stale lease、混合结果/
   附件警告/未知效果核查；核对原链和目标bytes，成功/忽略/未知不重放。人工upsert仅可
   验证存储契约，不把未证明的状态组合宣称生产可达P1。
4. 无独立服务/仓储的Rules局部/完整检查、配置候选/发布、Automation授权前分析及
   已授权执行；候选不变成Active、分析不授予权、删除旧scheduled Preview不改变执行权限。

wheel用固定提交git archive隔离清洁构建（含当前production assets），避免本机ignored
build/lib残留；smoke及离开源码的独立支持Python venv运行真实CLI/API/Worker/共享消费者。
固定候选生产镜像执行：

```bash
docker build -t mediaflow:task45-6-<candidate-sha> .
.venv/bin/python scripts/docker_scan_retirement_browser_proof.py --image mediaflow:task45-6-<candidate-sha> --artifacts .git/validation-evidence/<candidate-sha>/task45.6/scan-stability
.venv/bin/python scripts/docker_task_center_recovery_browser_proof.py --image mediaflow:task45-6-<candidate-sha>
.venv/bin/python scripts/docker_restart_fault_smoke_test.py --image mediaflow:task45-6-<candidate-sha>
.venv/bin/python scripts/docker_release_security_smoke_test.py --image mediaflow:task45-6-<candidate-sha>
```

容器fixture须已迁移合法整理分析/工作，不能通过保留旧Preview入口让脚本通过。
B另在镜像实际CLI/API/常驻Worker重复上方1–4关键消费者，检查fresh/schema、已安装模块/
import路径、wheel/image digest及实际HTTP served assets hash一致。检查1536×1024与380×720
的九列表、创建/恢复/未就绪/确认/结果截图、键盘/深链/返回/重连。只验当前支持整理数据
fresh/reopen/restart/失败原子性，不跑旧Preview/Scan/FileIndex迁移、历史或V1 parity矩阵。

命令cwd/实际数量/skip/失败与原始日志、独立脚本/截图/digests保存在本机稳定ignored
`.git/validation-evidence/<candidate-sha>/task45.6/`。未知或不可用门禁由B标pending；
执行输入相同可复用，变化则刷新对应验收。满足全部RO后只补缺失Slice-final证据并提交
Closure Packet，返回SLICE READY FOR A REVIEW，不机械再跑Final，不自行关闭。

## Non-goals

- 不实施冻结Slice43工作区/Run once/指标/设置重新设计、新Provider/队列/执行引擎。
- 不删除共享DryRun、局部Naming/Classification试算、真实发现/稳定性或必要计划/结果证据。
- 不建设旧Preview停止/接管/迁移/历史/V1 parity/别名/退役guard，不清空数据库或媒体。
- 不新增附件-only恢复、跨任务批量mutation、任意历史Reprocess、未知效果重放或自动回滚。
- 不因文案/视觉P2另造Task，不改父Slice/Roadmap边界，不push，不自判Slice关闭。

## Developer Completion Report

```text
Task Base: 2687e5b3eaa6f686d54c51930765e0ba904f69b5
Candidate Head: c7a725b1e78b1f59160f13e95eae6a9335b734a4
Handoff Head: HEAD (all commits above Candidate Head touch TASK.md only, so the
       reviewed executable input is exactly Candidate Head)
Status: READY FOR B REVIEW
Round: eighth round; fixes B's FIX REQUIRED on 58fee6e9bbfff937918d60bd35086923cb9397ef
       (only a *complete* walk handed its plan to the atomic publication, so a
       legal read_failure known subset wrote preview_id/prepared with no plan rows)
```

### Current round — 合法部分发现也发布完整计划（B 的当前阻塞）

#### 根因

`59c0f6e` 把计划写入改成“分析后原子发布”，但只对 `complete` 分支传了计划
（`plan=preview if complete else None`）。`read_failure` 的合法部分发现走的是同一个
`_analyze` 尾段却传 `None`，于是 `_publish_prepared_plan` 退回纯 discovery 写：
`preview_id`、`phase=prepared`、`prepared=true` 全部持久化，而计划行从未写入。B 在
`POST .../files/discoveries`（autoPrepare）→ 文件消失 → 真 Worker 的旅程里读到
`partial_success + prepared=true` 与非空 previewId，但该 ID 的既有计划 GET 404、
intent latestPlan=null、重开仍是悬空关联。

#### 本轮实现（同一 Task；未新增队列/状态机/独立 Preview 生命周期）

1. **完整性不再是“是否持久化计划”的开关**（`media_discovery.py::_analyze`）：
   分析产出的计划一律交给原子发布边界，`complete` 只决定 run 状态
   （`COMPLETED`/`PARTIAL_SUCCESS`）与逐项就绪，绝不再决定计划是否落库。
2. **计划参数变为强制**（`_publish_prepared_plan`）：`plan` 从 `object | None` 收紧为
   `object`；无计划时 fail-closed 抛 `DiscoveryUnavailable`，从类型/边界上排除“只有
   链接没有行”的悬空摘要。降级路径（有界测试替身仓储）同样先持久化计划再发布。
3. **部分计划的 fence 与完整计划完全相同**：仍是一条 `BEGIN IMMEDIATE` 事务内先写
   计划行（共享 `_publish_manual_preview_rows` 的 intent/item 守卫），再执行
   `discovery_id + version CAS + 精确 claim_token` 的 discovery 写入；控制/旧 owner
   赢时整体回滚，部分计划同样“一行都不存在”，不存在可确认残余。
4. **保留原有语义**：read_failure finding、material refusal 拒绝路径、定义来源不完整
   清单拒绝、Run once 的 `discovery_incomplete_manifest` 均未改动；未抹去错误、未自动
   执行、未把完整性当放行开关。
5. **回归（真实 API/SQLite/Worker/Provider，无人工 upsert）**：

| 位置 | 覆盖 |
|---|---|
| `test_organize_preparation` `test_a_legal_read_failure_subset_publishes_its_complete_plan` | 混合选择（消失的显式文件 + 可读目录）→ read_failure、无 material refusal、`prepared=true`；计划 GET 200 且恰为已知子集、逐项 `previewed`；intent latest-plan 与重开（`SQLiteTaskRepository` 新连接）一致；零执行准入/零 mutation；显式确认后才 1 项执行成功 |
| `test_organize_preparation` `test_a_legal_partial_plan_is_never_published_by_a_losing_write` | 仓储原子边界直接验证：版本 CAS 输 → `DiscoveryConflict` 且计划行/intent latest 全无；非精确 claim → `DiscoveryOwnershipLost` 且无残余；零 mutation |
| `test_organize_preparation` `test_a_pause_that_wins_a_partial_analysis_leaves_no_plan` / `test_a_cancel_that_wins_a_partial_analysis_leaves_no_plan` | 真 Worker 阻塞在真实合成 Provider，真实 API pause/cancel 先胜：paused/cancelled、`previewId=null`、`prepared=false`、intent 无计划、claim 已释放、零 Task/零 mutation；pause 后 Continue 再发布唯一真实计划 |
| 既有 `test_material_budget_refusal_never_becomes_an_executable_prefix` | 保留：预算/material refusal 仍拒绝、不冻结、无 previewId |

#### 本轮受影响检查（仓库根除注明外，均为实际结果）

```bash
python3 scripts/check_governance.py                                  # PASS
.venv/bin/ruff check <2 changed py>                                  # All checks passed
.venv/bin/ruff format --check <2 changed py>                         # 2 files already formatted
.venv/bin/python -m compileall -q mediaflow tests                    # OK
git diff --check                                                     # clean
PYTHONPATH=tests .venv/bin/python -m unittest test_organize_preparation   test_media_discovery test_automation_run_once test_v2_automation_run_once   # Ran 196, OK
PYTHONPATH=tests .venv/bin/python -m unittest test_organize_preparation   test_media_discovery test_automation_run_once test_v2_automation_run_once   test_manual_organize_intent test_manual_organize_preview   test_manual_organize_execution test_v2_manual_organize            # Ran 300, OK
PYTHONPATH=tests .venv/bin/python -m unittest test_manual_organize_intent   test_manual_organize_preview test_manual_organize_execution test_v2_manual_organize   test_manual_preview test_preview_retirement test_task_persistence   test_scan_retirement test_file_index_retirement                   # Ran 173, OK
PYTHONPATH=tests .venv/bin/python -m unittest test_preview_retirement   test_scan_retirement test_file_index_retirement test_recovery_continuation   test_scope_continuation test_task_center_recovery_lineage   test_metadata_correction_continuation test_task_persistence       # Ran 245, OK
```

#### 失败先于修正（父提交对照，真实入口探针）

`.git/validation-evidence/developer/task45.6-fix-partial-plan-publication/` 含
`verify_partial_plan.py`、`verify_partial_plan.log`（**32/32 通过**）与
`prefix_15294d0_repro.log`（父提交 **8 项失败 / 24 通过**）。

- 同一脚本在隔离父提交 `15294d0`（worktree，未改动工作区）上复现 B 的 P1：
  `plan GET resolves the published identity` → 404 `preview_not_found`；
  `plan carries the exact known subset` / `plan items are ready for explicit
  confirmation` / `intent latest plan is the same plan` / `reopen keeps the plan
  rows` / `reopen keeps the intent projection` / `continued plan is readable` /
  `continued plan carries the known subset` 均失败。
- 本候选：合法部分发现计划 GET 200、恰为已知子集、逐项 previewed、intent latest 与
  重开后一致、零执行准入/零 mutation/零 Task、claim 已释放；pause 先胜分支无计划行与
  链接、Continue 后发布唯一真实计划；同脚本 `test_organize_preparation` 全 17 例 OK，
  父提交上其中 2 例失败。

#### 未执行 / 剩余风险（交 B）

- 全量 Python/Web/E2E、production assets、逐 spec 原生浏览器、wheel/安装消费者/
  Docker/常驻 Worker/restart/release-security 属 B，本轮未执行。
- `_publish_prepared_plan` 的降级路径（仓储无原子边界时 `_persist_create` + fenced
  发布 + 补偿退役）仍非同一事务；本仓唯一实现 `SQLiteTaskRepository` 走原子边界，
  降级路径仅服务于有界测试替身。
- 若计划自身守卫在发布时拒绝（例如分析期间操作者保存了纠正），事务整体回滚、计划
  不落库，run 仍停在 `ANALYZING` 持有 claim，由操作者重新 `analyze` 收敛；该边界
  与既有 `request_analysis` 的“同页重新分析”语义一致，本轮未新增状态。
- 本轮测试/质量检查累计约 2.5 分钟（含 3 次真实入口探针与 1 次父提交复现），低于
  本轮实际工作时间的 30%。

本机稳定证据（未声称外部可访问）：
`.git/validation-evidence/developer/task45.6-fix-partial-plan-publication/`。

不自判 PASS，不关闭 Slice，不规划下一 Task。

### 上一轮记录（seventh round — 计划与运行关联的一次原子提交）

以下为 `59c0f6e`/`58fee6e` 轮的交付与检查记录，保留原样。

#### 第七轮记录 — 计划与运行关联的一次原子提交

#### 根因

上一轮的 fence 只保护了 discovery 的链接/状态/claim 写回；计划行本身仍先经
`ManualOrganizePreviewService._persist_create`（`create_manual_preview`）提交为
current。Provider 在途期间控制先赢时，窗口内的计划已是持久 current 记录，可从
intent 的 latest-plan 投影、计划 detail 与普通 `/execute` 准入确认（B 探针 202
admitted）。

#### 本轮实现（同一 Task，无新队列/状态机/独立 Preview 生命周期）

1. **计划行与运行链接成为一次原子提交**（新仓储边界
   `SQLiteTaskRepository.publish_media_discovery_plan_with_plan`）：在一条
   `BEGIN IMMEDIATE` 事务内先写计划行（与 Files 旅程共用同一套 intent/item
   守卫的 `_publish_manual_preview_rows`），再执行与原 fenced 发布完全相同的
   discovery UPDATE（`discovery_id + version CAS + 精确 claim_token`）。任一
   fence 或计划守卫拒绝即整体回滚——输掉竞争的计划**完全没有落库**，不存在可
   退役或可从 intent 读到的残余。Provider/Storage 调用仍在事务外，无长事务。
2. **服务层**（`media_discovery.py::_analyze`）：分析改用 `create(..., persist=False)`
   （既有能力），产出内存计划投影后再经原子边界发布；仅在该仓储无原子边界时
   （有界测试替身）退回旧路径 `_persist_create` + `publish_media_discovery_plan`
   + 补偿 `discard_uncommitted`。混合非 complete（PARTIAL_SUCCESS）计划的发布
   也走原子提交；补偿退役路径保留为降级兜底，不删除任何证据。
3. **不可确认保护的权威不再是退役**：原子提交下输家的计划行根本不存在，因此
   intent latest-plan、计划 detail 与 execute 准入读到的都是已获运行发布许可的
   计划；B 修正方案第2条的共享权威要求由“计划不可见”而非“补偿隐藏”满足。
4. **更新既有断言与新增回归**（全部真实入口，无人工 upsert）：

| 位置 | 覆盖 |
|---|---|
| `test_media_discovery.FinalizeHandoffFencingTests` 新增 `test_the_plan_rows_and_the_run_link_are_one_atomic_publication` | 控制先赢（版本 CAS 拒绝）→ 计划行与 discovery 链接均为零副作用；精确 claim 持有者发布一次 → 计划 current、intent latest、claim 释放同一次写；重复发布不可能产生第二份计划 |
| `test_automation_run_once.RunOnceJourneyTests` 新增 `test_a_control_that_wins_the_publication_window_leaves_no_confirmable_plan` | 真实 API cancel 在 Provider 在途先胜 → 输家分析返回后 `CANCELLED`、`list_manual_previews` 为空、`get_latest_manual_preview` 为 None、intent 投影 `latestPlan=null`、run GET 无 previewId/plan 动作、零 Task/零 mutation |
| `test_automation_run_once.RunOnceJourneyTests` 新增 `test_a_normal_analysis_publishes_one_exactly_confirmable_plan` | 无竞态分析 → 恰好一份 current 计划链接到 run、intent latest-plan 指向它、detail `actions.execute.available`（注册真实 resident Worker 后）、显式 POST `/execute` 202 admitted；分析本身零确认/零授权 |
| 既有 pause/cancel 竞态用例 | 断言从“计划已落库且被标 stale/current=0”更新为更强性质“计划行从未写入”（`list_manual_previews` 为空） |

#### 本轮受影响检查（仓库根除注明外，均为实际结果）

```bash
python3 scripts/check_governance.py                                  # PASS
.venv/bin/ruff check mediaflow tests                                 # All checks passed
.venv/bin/ruff format --check mediaflow tests                        # 320 files already formatted
.venv/bin/python -m compileall -q mediaflow tests                    # OK
git diff --check                                                     # clean
rg -n -i 'ffprobe|ffmpeg' mediaflow pyproject.toml                   # no match (exit 1)
PYTHONPATH=tests .venv/bin/python -m unittest test_media_discovery \
  test_automation_run_once test_v2_automation_run_once               # Ran 179, OK
PYTHONPATH=tests .venv/bin/python -m unittest \
  test_media_discovery.FinalizeHandoffFencingTests \
  test_automation_run_once.RunOnceJourneyTests                       # Ran 37, OK
PYTHONPATH=tests .venv/bin/python -m unittest test_v2_automation_run_once.RunOnceApiTests  # Ran 21, OK
PYTHONPATH=tests .venv/bin/python -m unittest test_manual_organize_intent \
  test_manual_organize_preview test_manual_organize_execution \
  test_v2_manual_organize test_organize_preparation                  # Ran 117, OK
PYTHONPATH=tests .venv/bin/python -m unittest test_recovery_continuation \
  test_scope_continuation test_task_center_recovery_lineage \
  test_metadata_correction_continuation                              # Ran 185, OK
PYTHONPATH=tests .venv/bin/python -m unittest test_preview_retirement \
  test_scan_retirement test_file_index_retirement \
  test_automation_definition_execution \
  test_automation_authorized_execution_matrix \
  test_automation_unattended_grant test_configuration_snapshot \
  test_configuration_organize test_v2_rules_workspace_previews \
  test_task_persistence                                              # Ran 197, OK
PYTHONPATH=tests .venv/bin/python -m unittest test_automation_task_definition \
  test_v2_automation_lifecycle test_automation_api \
  test_manual_operations_contract test_manual_operations \
  test_manual_preview                                                # Ran 95, OK
```

（以上为按修改影响的多组运行；合并去重后 Python 受影响总计约 795 例全部通过。）

#### 未执行 / 剩余风险（交 B）

- 全量 Python/Web/E2E、production assets、逐 spec 原生浏览器、wheel/安装消费者/
  Docker/常驻 Worker/restart/release-security 属 B，本轮未执行。
- `publish_media_discovery_plan_with_plan` 为新增仓储方法；仓库外测试替身或旧
  仓储走既有降级路径（`_persist_create` + fenced 发布 + 补偿退役），该路径
  不具备同事务原子性，属已知的降级边界；本仓 SQLite 实现走原子边界。
- 混合非 complete 计划同样经原子边界发布；若其发布成功后被控制拒绝，回滚也
  不留计划行（与 complete 分支一致），既有 `_stale_recovery_preparation`/
  findings 语义未变。
- 上一轮的 `discard_manual_preview`/`discard_uncommitted`/`publish_media_discovery_plan`
  保留为降级兜底与历史退役能力，主保证不依赖补偿退役。
- 本轮测试/质量检查累计约 4 分钟，低于本轮实际工作时间的 30%（先修后测，
  未等待凑比例）。

不自判 PASS，不关闭 Slice，不规划下一 Task。

### 上一轮记录（sixth round — 计划发布与 pause/cancel 协调）

以下为 `764291d`/`98c65b4` 轮的交付与检查记录，保留原样。

#### 第六轮记录 — 计划发布与 pause/cancel 协调

#### 根因

`MediaDiscoveryService.claim_and_run` 的分析分支位于并发控制冲突协调 `try` 之外：
`_analyze` 先持久化完整计划、再以旧 discovery 版本/claim 写回。Provider 阻塞期间
operator control 更新了版本/释放了 claim，于是计划已落库而 run 写回失败——Worker 以
`DiscoveryConflict`/`DiscoveryOwnershipLost` 逃出循环（记录既不暂停也不终态），
`AutomationRunOnceService._durable_plan_id` 又从 intent 的 `latest_readonly` 取计划，
不区分 pause/pause-request/terminal，导致"已暂停/已取消仍可确认摘要"。

#### 本轮实现（同一 Task，无新队列/状态机/独立 Preview 生命周期）

1. **计划发布成为一次受控提交**（`media_discovery.py::_analyze`）：
   Provider/Storage 分析完成后，用新的仓储边界
   `SQLiteTaskRepository.publish_media_discovery_plan`
   在**单条 UPDATE** 中同时写 status/version/progress/sources/preview_id 并清空
   claim，且以 `discovery_id + version CAS + 精确 claim_token` 三重 fenced。控制或
   successor 赢得任一 fence 时，计划的链接完全未提交。Provider 调用前后均无长事务、
   无全局锁。
2. **分析结果不再逃出 Worker 循环**：`run_claimed` 把 `_analyze` 纳入与遍历同一套
   `DiscoveryConflict`/`DiscoveryOwnershipLost` 处理，由 `_settle_after_conflict`
   按**最新持久状态**结算：pause 先胜 → 安全边界确认暂停（同 intent/scope/pin 保留，
   可 Continue）；cancel 先胜 → 保持终态 `CANCELLED`；claim 转交 → 旧 owner 只退出、
   不写任何字段。
3. **未提交的计划被退役而非删除**：新增
   `ManualOrganizePreviewService.discard_uncommitted`，把落库但未链接/未确认的计划逐项
   标为 `stale` 并置 `current=0`（证据保留为历史），因此它既不能成为 intent 的最新摘要，
   也不能被 paused/cancelled run 重新展示。
4. **Continue 回到同一冻结分析**：`resume` 对已冻结（linked intent）run 直接回到
   `ANALYZING`，不重走 scope、不重冻结；未冻结记录仍按原 `QUEUED` 继续。
5. **Run once 投影以控制为先**（`automation_run_once.py`）：
   - 相位新增 `pausing`（请求已耐久、等安全边界确认）/`paused`（可 Continue）/
     `cancelled`（终态），不再把 paused 报成 `analyzing`、把 cancelled 报成 `refused`；
   - `_durable_plan_id` 对 cancel_requested/cancelled/paused/pause_requested 一律返回
     `None`，不再用 intent 的 `latest_readonly` 绕过控制状态；
   - `actions.preview.available` 只在确有可发布计划或分析仍在进行且无控制时成立；
   - pause/resume/cancel 动作按当前相位与请求旗标计算（pending 不再可重复 pause，
     acknowledged 才有 resume，终态无任何恢复/确认入口）。
6. **Web 服从后端动作**（`AutomationRunOncePage.tsx`、`run-once.ts`）：只有
   `actions.preview.available` 才允许从 `previewId`/URL 提示挂载
   `OrganizePlanConfirmation`；`pausing`/`paused`/`cancelled` 各有明确说明，
   pending 显示禁用的"等待暂停确认"、acknowledged 显示"继续分析"、cancelled 无确认/恢复。
7. 未新增执行授权、未新增队列/执行器、未改 schema：确认仍需计划出现后单独显式执行。

#### 本轮受影响检查（仓库根除注明外，均为实际结果）

```bash
python3 scripts/check_governance.py                                  # PASS
.venv/bin/ruff check mediaflow tests                                 # All checks passed
.venv/bin/ruff format --check mediaflow tests                        # 320 files already formatted
.venv/bin/python -m compileall -q mediaflow tests scripts            # OK
git diff --check                                                     # clean
PYTHONPATH=tests .venv/bin/python -m unittest test_media_discovery   # Ran 114, OK
PYTHONPATH=tests .venv/bin/python -m unittest test_media_discovery.FinalizeHandoffFencingTests  # Ran 9, OK
PYTHONPATH=tests .venv/bin/python -m unittest test_media_discovery \
  test_automation_run_once test_v2_automation_run_once \
  test_preview_retirement test_manual_organize_preview               # Ran 203, OK
PYTHONPATH=tests .venv/bin/python -m unittest test_manual_organize_intent \
  test_manual_organize_execution test_v2_manual_organize \
  test_organize_preparation test_recovery_continuation \
  test_scope_continuation test_task_center_recovery_lineage \
  test_metadata_correction_continuation                              # Ran 289, OK
PYTHONPATH=tests .venv/bin/python -m unittest test_automation_unattended_grant \
  test_automation_definition_execution test_automation_authorized_execution_matrix \
  test_configuration_organize test_v2_rules_workspace_previews \
  test_task_persistence test_v2_automation_operations \
  test_configuration_snapshot                                        # Ran 175, OK
PYTHONPATH=tests .venv/bin/python -m unittest test_preview_retirement \
  test_scan_retirement test_file_index_retirement \
  test_automation_task_definition test_v2_automation_lifecycle       # Ran 82, OK
cd web && npm run test -- run src/features/operations/AutomationRunOncePage.test.tsx \
  src/entities/operations/run-once.test.ts                           # 2 files, 11 tests OK
cd web && npm run test -- run src/routes/router.test.tsx \
  src/features/operations/OrganizeCreationPage.test.tsx \
  src/features/operations/OperationsInventory.test.tsx \
  src/features/operations/TaskItemRecoveryPanel.test.tsx \
  src/features/operations/OrganizeDiscoveryPage.test.tsx             # 5 files, 51 tests OK
cd web && npm run test -- run src/features/rules/RulesObjectTestPanel.test.tsx \
  src/features/operations/AutomationRouter.test.tsx \
  src/features/operations/OrganizeRouter.test.tsx                    # 3 files, 54 tests OK
cd web && npm run typecheck                                          # OK
cd web && npx eslint <3 changed web files>                           # clean
cd web && npx prettier --check <3 changed web files>                 # clean
```

新增/扩展的回归（全部走真实 API/Worker/仓储，不 mock 权威）：

| 位置 | 覆盖 |
|---|---|
| `test_automation_run_once.RunOnceJourneyTests` | 真实 Run once API + 阻塞合成 Provider：pause → 200 `pausing`、释放 Provider 后持久 `PAUSED`、计划未链接且被退役、GET `paused`、无 confirm/execution、Continue 后同一 run 链接唯一新计划；cancel → `CANCELLED`、迟到计划被退役、GET 终态无 plan/resume/confirm；旧 owner 失去 claim → 不写任何字段、successor 可完成 |
| `test_v2_automation_run_once.RunOnceApiTests` | 真实 V2 API：pause-request 期间无 plan 身份/动作、Worker 确认后 `paused` 可 Continue 并最终链接计划；cancel 终态、迟到 Worker 无 claimable 工作、无 current plan；重开后仍是 CANCELLED 且无计划 |
| `test_media_discovery.FinalizeHandoffFencingTests` | 新增 `test_fenced_plan_publication_requires_the_exact_live_claim`：错误 claim → `DiscoveryOwnershipLost` 且零副作用；正确 claim → 计划链接与 claim 释放在同一次写；重复发布不可能产生第二份计划。新增 `test_discarding_an_unpublished_plan_is_scoped_to_its_own_identity`：退役只作用于该 `preview_id`，同 intent 的合法 sibling 计划保持 current 与 item 行 |
| `AutomationRunOncePage.test.tsx` | pausing（无 plan、无重复 pause、禁用等待提示）、paused（Continue、无 confirm）、cancelled（含 stale `?plan=` 也不得挂载确认） |

#### 独立探针证据（真实入口，非源码检索）

`.git/validation-evidence/developer/task45.6-fix-pause-cancel-plan-fence/` 含
`verify_pause_cancel.py/.log`（**40/40 通过**）与 `prefix_dfc59a4_repro.log`（父候选 13 项失败）：

- 真实 `MediaFlowApi` WSGI 路由 + 真实 Run once 服务 + 真实 Worker + 隔离 SQLite/临时
  Local Storage；仅把 `SyntheticMetadataProvider.search_movie` 用 `Event` 暂缓，
  Provider 在途时通过真实 `POST .../pause` / `.../cancel` 发控制。
- 父候选 `dfc59a4c`：pause 后相位仍 `analyzing`；cancel 后相位 `refused`、
  `actions.preview.available=true` 且返回真实 `path`、`manual_previews` 留有一份
  `previewed/current` 计划 —— 与 B 的复现一致。
- 本候选：控制返回 `pausing`/`cancelled` 且无 plan 身份与 plan 动作；Worker 返回后
  `PAUSED`/`CANCELLED`、`preview_id` 为空、claim 已释放、迟到计划 `current=0`；
  GET 无 plan、pause 可 Continue、cancel 无恢复与确认；两种分支来源/目标 mutation、
  Task 行、unattended grant 均为零；无竞态成功路径仍链接唯一 current 计划。

### 未执行 / 剩余风险（交 B）

- 全量 Python/Web/E2E、production assets、逐 spec 原生浏览器、wheel/安装消费者/
  Docker/常驻 Worker/restart/release-security 属 B，本轮未执行。
- `publish_media_discovery_plan` 是新增的仓储方法；本仓唯一实现为 SQLite
  `SQLiteTaskRepository`，服务层保留"无该方法时退回 `_persist` + `_release_claim`"的
  兼容路径（用于测试替身），该退回路径不具备同事务 fence，属已知的降级边界。
- provider 阻塞期内的 heartbeat 仍由既有 lease keeper 维持；本轮未改租约/心跳语义。
- `discard_manual_preview` 同为新增仓储方法（按精确 `preview_id`、只作用 still-current
  行）。缺该方法时服务层退回到"仅当仍是该 intent 最新计划才按 item 退役"的保守路径，
  主保证（未链接即不可确认执行）不依赖退役本身，也不会删除任何证据。
- E2E harness 的 `run-automation-run-once-worker` 与既有 browser proof 未修改：它们仍以
  `previewId` 链接作为分析完成信号，与新的 fenced 发布路径一致；B 的原生浏览器门禁需
  在候选上重新执行。
- 分析期间 Web 仍按 2s 轮询；`pausing`/`paused`/`cancelled` 停止轮询（`pausing` 的
  确认需操作者刷新或等待下一次交互，与既有 discovery 协作控制一致）。
- 本轮测试/质量检查累计约 3 分钟（含 3 次全新运行的真实入口探针与一次父候选复现），
  低于本轮实际工作时间的 30%。

本机稳定证据（未声称外部可访问）：
`.git/validation-evidence/developer/task45.6-fix-pause-cancel-plan-fence/`。

不自判 PASS，不关闭 Slice，不规划下一 Task。

### 上一轮记录（fifth round — 日志脱敏与耐久分析承接）

以下为 `068fb07`/`dfc59a4` 轮的交付与检查记录，保留原样。

### 第五轮修正交付（对应 B 的两个已核实阻塞）

#### 阻塞1 — 通用API异常日志绕过脱敏

`mediaflow/interfaces/service_api.py` 的通用 `except Exception` 分支删除了
`repr(exception)` stderr 写出与 `traceback.print_exc()`（`c71ec218` 引入）。操作者可见的
JSON 错误与持久审计行本就承载有界、无凭据的证据；原始异常链可能含凭据形状内容，不再写入
任何流/日志（AGENTS 日志不变量、REQ-LOG-003）。扩展既有
`test_audit_failure_blocks_job_creation_before_mutation`：捕获真实 stderr，断言合成
`token=secret` 标记不出现在响应、stderr 或 traceback 中，且仍返回 500、零 Job 准入、
审计失败 fail-closed；未改弱故障或断言。

#### 阻塞2 — 共享分析退回HTTP内联，未由现有Task/Worker承接

Run once `finalize` 不再在 HTTP 请求内调用 `previews.create`；共享零变更整理分析重新由
**现有发现 Worker 的耐久分析阶段**承接（不恢复独立 Preview 产品、不另建队列/执行引擎/专用
schema）。要点：

1. `MediaDiscoveryService.begin_frozen_analysis`：对已冻结（linked intent）的 Run once
   发布一次版本化 `ANALYZING` 阶段（与既有 `request_analysis` 共用 `_enter_analysis`）；
   `run_claimed` 的分析入口从 `auto_prepare` 记录扩展到一切已冻结 intent 的记录，Worker
   在同一 run 上执行完整生产分析链并回链精确计划。重复/丢响应请求收敛于已排队分析。
2. `AutomationRunOnceService.finalize`：冻结后委托耐久阶段并返回 `(analyzing, None)`；
   构造签名移除不再使用的 `intent_service` 参数。投影新增 `analyzing` 相位（计划生成中），
   ANALYZING 期间 pause/cancel 可用；plan 路由在计划链接前如实为 `available+null path`，
   链接后由既有 `_durable_plan_id`/`preview_id` 解析同一计划。
3. API finalize 响应：201 + `phase=analyzing`、`previewId/previewPath/analysisId/
   analysisPath` 全部为 null；普通 GET（重载/重连/重启）从同一 run 恢复计划身份。
4. Web：`AutomationRunOncePage` 显示耐久分析阶段说明（冻结清单/运行身份已保存、完成前无
   可执行范围、零执行授权），按 URL/持久 `previewId` 恢复摘要；分析期间提供"打开整理意图"
   之外的明确分析中状态。`run-once.ts` 归一化接受 `status=analyzing`。
5. Harness/E2E：`run-automation-run-once-worker` 推进分析阶段直至 `previewId` 链接；
   原生 browser proof 在冻结后驱动真实 Worker，混合恢复旅程同。授权前分析/grant 夹具
   （`test_configuration_snapshot`/`test_automation_unattended_grant`/
   `test_v2_automation_operations`）改为驱动真实 Worker 旅程取得共享分析。
6. 未新增任何执行授权：分析全程零 mutation、零 grant/审计行；确认仍须在计划出现后单独
   明确执行；`latest_frozen_definition_run_once`/授权前校验链不变（分析完成前 fail-closed）。

#### 受影响检查（本轮 Developer 实际结果，仓库根除注明外）

```bash
python3 scripts/check_governance.py                                  # PASS
.venv/bin/ruff check <11 changed py>                                 # All checks passed
.venv/bin/ruff format --check mediaflow tests scripts                # 349 files already formatted
.venv/bin/python -m compileall -q mediaflow tests scripts            # OK
.venv/bin/python -m pip check                                        # No broken requirements found
.venv/bin/mediaflow --config config/strategy.example.json config validate  # OK
rg -n -i 'ffprobe|ffmpeg' mediaflow pyproject.toml                   # no match (exit 1)
git diff --check                                                     # clean
PYTHONPATH=tests .venv/bin/python -m unittest test_api_security      # Ran 14, OK
PYTHONPATH=tests .venv/bin/python -m unittest test_automation_run_once \
  test_v2_automation_run_once test_preview_retirement                # Ran 70, OK
PYTHONPATH=tests .venv/bin/python -m unittest test_v2_automation_operations \
  test_automation_unattended_grant                                   # Ran 19, OK
PYTHONPATH=tests .venv/bin/python -m unittest test_configuration_snapshot  # Ran 45, OK
PYTHONPATH=tests .venv/bin/python -m unittest test_manual_organize_intent \
  test_manual_organize_preview test_manual_organize_execution test_v2_manual_organize \
  test_organize_preparation                                          # Ran 117, OK
PYTHONPATH=tests .venv/bin/python -m unittest test_recovery_continuation \
  test_scope_continuation test_automation_definition_execution \
  test_automation_authorized_execution_matrix test_manual_operations_contract \
  test_media_discovery                                               # Ran 316, OK
PYTHONPATH=tests .venv/bin/python -m unittest test_configuration_organize \
  test_v2_rules_workspace_previews test_task_persistence test_automation_admission \
  test_automation_job_fencing                                        # Ran 97, OK
PYTHONPATH=tests .venv/bin/python -m unittest test_automation_api \
  test_processing_worker_readiness test_automation_task_definition \
  test_v2_automation_lifecycle test_automation_definition_occurrence \
  test_automation_definition_publication                             # Ran 150, OK
PYTHONPATH=tests .venv/bin/python -m unittest test_sqlite_backup \
  test_sqlite_restore test_manual_preview                            # Ran 17, OK
cd web && npm run test -- run src/features/operations/AutomationRunOncePage.test.tsx  # 5 tests OK
cd web && npm run test -- run src/routes/router.test.tsx \
  src/features/operations/OrganizeCreationPage.test.tsx \
  src/features/operations/OperationsInventory.test.tsx \
  src/features/operations/TaskItemRecoveryPanel.test.tsx \
  src/features/operations/OrganizeDiscoveryPage.test.tsx             # 5 files, 51 tests OK
cd web && npm run test -- run src/entities/operations/run-once.test.ts \
  src/features/rules/RulesObjectTestPanel.test.tsx \
  src/features/operations/AutomationRouter.test.tsx \
  src/features/operations/OrganizeRouter.test.tsx                    # 4 files, 60 tests OK
cd web && npx eslint <4 changed web files>                           # clean
cd web && npx prettier --check <4 changed web files>                 # clean
cd web && npm run typecheck                                          # OK
```

失败先于修正复现：父候选 `cd92a85f` 上（a）B 的 stderr 探针出现合成 secret 与原始
traceback，本候选 stderr 为空且无标记；（b）B 的 inline-analysis 探针 finalize POST 在
Provider 在途时被阻塞且 `phase=frozen`，本候选同一场景（真实 API 装配、合成 Provider
Event 暂缓）finalize 在 Provider 在途时返回 201 `phase=analyzing`、`previewId=null`，
Provider 释放后同一 Worker 链接精确计划。两个探针均经真实生产入口构造，见下。

### 独立探针证据（真实入口，非源码检索）

`.git/validation-evidence/developer/task45.6-fix-durable-analysis-and-log-redaction/`
含 `verify_fixes.py/.log`：15/15 检查通过。

- 日志脱敏（真实 `MediaFlowApi` WSGI 入口，POST /api/v1/jobs，损坏的审计依赖，
  合成 `token=secret`）：500、零 Job 准入、JSON 无 secret、**stderr 为空**
  （无原始异常、无 `INTERNAL ERROR`、无 `Traceback`）。
- 耐久共享分析（真实 Run once 旅程 + 合成 Provider Event 暂缓）：admission 202 即时；
  有界遍历完成；**finalize POST 在 Provider 在途时返回 201 `phase=analyzing`、
  `previewId/analysisId=null`**；持久记录为 `ANALYZING` 且无 linked plan；
  `manual_previews` 为 0 行；来源/目标 bytes 零变化；grant 表为 0 行；Provider 释放后
  同一 Worker `claim_and_run` 在同一 run 上链接精确计划；普通 GET 解析同一 `previewId`；
  SQLite 重开后经 durable intent 仍读到同一份零变更计划。

### 第五轮未执行 / 剩余风险

- 全量 Python/Web/E2E、production assets、逐 spec 原生浏览器、wheel/安装消费者/Docker/
  常驻 Worker/restart/release-security 属 B，该轮未执行。
- Run once 分析期间的暂停/恢复沿既有 discovery 协作控制（ANALYZING 可 pause/cancel，
  Worker 在安全边界确认）；自动恢复路径与准备旅程共用同一 `_analyze`，语义未改。
- `UnattendedExecutionGrantService` 与 `latest_frozen_definition_run_once` 未改动；
  分析进行中（非 terminal）的 run 不会被授权前分析解析到，grant fail-closed。
- Web 计划恢复依赖轮询（分析中 2s）；`OrganizePlanConfirmation` 仍按精确计划只读渲染，
  URL plan 提示不覆盖更新的持久计划。
- `AutomationRunOnceService` 构造签名变更（移除 `intent_service`）影响仅限本仓内三处
  装配/测试构造，已同步更新。

本机稳定证据（未声称外部可访问）：
`.git/validation-evidence/developer/task45.6-fix-durable-analysis-and-log-redaction/`。

不自判 PASS，不关闭 Slice，不规划下一 Task。

### 第五轮之前的记录

更早各轮（授权前分析、同URL固定计划、shared-analysis grant fixture）的
报告与证据边界保留于 Git（`4e23a53:TASK.md` 及更早）；本机稳定证据保留在
`.git/validation-evidence/` 下相应目录。

## B Review Result

### Current candidate review — 2026-10-22

```text
Reviewed handoff: c4c9efc4614493c30126f5468ff7e5178538b5b8
Executable candidate: c7a725b1e78b1f59160f13e95eae6a9335b734a4
Task range: 2687e5b3eaa6f686d54c51930765e0ba904f69b5..c4c9efc4614493c30126f5468ff7e5178538b5b8
Decision: FIX REQUIRED
Stage: proven P1; complete Task-range/final T4 acceptance remains pending
Required Outcomes / Surfaces all satisfied: NO
Next: SAME TASK FIX LOOP; no new Task or Slice closure
```

Governance PASS；候选到交接仅 TASK.md，执行输入一致。main/HEAD、预存 dirty 与工作区/
Git 可写已核对并保留。本轮仅更新 B 的审查/修正要求；先前报告保留于
`c4c9efc4614493c30126f5468ff7e5178538b5b8:TASK.md` 和更早 Git，不倒改前项 PASS。

**上一阻塞已修正：** B 独立从真实 Files 混合选择准入，文件随后消失，Worker 对合法已知
子集分析；计划 GET 200、intent latestPlan、完整计划行及重开 SQLite 一致。原子发布探针
的 pause/cancel/正常三分支也通过：控制先胜出不留下计划；正常发布唯一计划，另一次明确
确认才准入一个 Task。均零媒体 mutation。

**P1 — 意图页“生成分析摘要”仍绕过耐久分析和运行发布 fence。**

位置：`web/src/features/operations/OrganizeIntentPage.tsx` 的 previewMutation →
`web/src/shared/api/api-client.ts:submitOrganizePreview` →
`mediaflow/interfaces/service_api.py` 的
`POST /api/v1/operations/organize/intents/{intentId}/previews` →
`_manual_previews.create`。该消费者由
`c71ec218ca46efa7d73e53c9c82b29f3af88bd91`（2026-10-21 17:25:39 +0800）
从耐久分析准入改成直接 HTTP 分析；后续 Run once 的修正没有承接此现存入口。

B 从已有 UI 链接/按钮对应的真实 API 独立复现，未 upsert 持久状态、猜路由或运行媒体执行：

- Files autoPrepare → 正常 Worker 完成 → “打开整理意图” → 保存页面提供的识别选择 →
  “生成分析摘要”。只延迟真实 Storage Stat 返回，请求仍阻塞于 HTTP 线程；关联运行仍为
  completed、版本不变，没有可 claim 的分析；现有 pause API 返回 409 discovery_not_open。
  Storage 恢复后请求 201 并写入第二份计划，但 discovery 仍关联旧计划。长操作没有同一
  耐久进度/暂停/重开承接，不能以原运行“已完成”代表正在分析的当前状态。
- Run once → 已有 finalize → analyzing → 页面现有“打开整理意图” → “生成分析摘要”。
  真实 Provider 调用阻塞期间，原 Run once cancel 返回 200/phase=cancelled；释放 Provider
  后，意图页请求仍返回 201、写入 current 计划。原运行 previewId=null，却能从该意图页
  读取新计划，execute.available=true；另一次显式确认返回 202 并创建一个 Task。
  这不是自动执行，但已取消分析仍发布可确认残余，绕过新原子发布保护。

根因是同一受支持共享分析还有 HTTP 直接持久化旁路；仅修 Worker 发布不能约束它。
不符合 AGENTS 的长操作耐久性及 Slice RO-2/RO-8 的同一整理旅程、取消语义和固定计划关联，
属于当前 Task P1，非界面优化或新功能要求。

**同一 Task 修正步骤：**

1. 意图页生成/重新生成完整摘要也接入已有整理运行的耐久分析阶段；请求只记录版本化准入，
   Storage/Provider/完整规划由现有 Worker 执行。复用 intent 对应运行及现有服务，保持原
   scope/pin/选择，不恢复独立 Preview 生命周期或新建队列。合法无关联运行的受支持 intent
   消费者也须由既有整理职责承接，不能只隐藏按钮留下同一 API 旁路。
2. 计划行、intent latest、运行关联及 claim 释放统一经现有原子发布/fence；取消/暂停/旧
   owner 已胜出时，不得通过该入口发布新的 current/可确认计划。页面显示真实分析/控制
   阶段，重载/重开读取同一运行和精确计划；丢响应先核对持久状态，不声称“没有保存更改”。
3. 用实际页面按钮对应的 API 补回归：Files 保存合法纠正后慢 Storage/Provider → 请求迅速
   返回耐久阶段 → Worker 发布 → 同页新摘要/重开；Run once 分析期间打开意图页，cancel/
   pause 先胜出后迟到结果不得落为可确认计划。保留正常确认、合法部分计划、旧 pin、
   预算拒绝及零 mutation/零执行授权。原独立产品保持退出，明确确认仍不可省略。
4. Developer 只跑新增/修改与直接受影响验证：
   `PYTHONPATH=tests .venv/bin/python -m unittest test_organize_preparation test_media_discovery test_automation_run_once test_v2_automation_run_once`；
   加实际修改影响的 manual 计划/执行/API 用例。Web 在 web/ 运行
   `npm run test -- run src/features/operations/OrganizeRouter.test.tsx src/features/operations/AutomationRunOncePage.test.tsx`
   及 `npm run typecheck`、changed-file lint/format、`git diff --check`。
   全量 Python/Web/E2E、打包及发布矩阵仍由 B 负责，不交回 Developer。

**本轮实际验证与边界：**

- 全量 `.venv/bin/python -m unittest discover -s tests`：2688 tests，OK，7 skips；进程墙钟
  257.584s，测试框架报告 257.221s。该绿测没有覆盖上述意图页旁路。
- 独立 partial-plan、atomic-publication、intent-inline-analysis、intent-cancel-bypass 探针
  均运行；前两项验证修正，后两项证实 P1。源/目标 mutation 均为零。
- 治理及候选到交接的输入差异已检查；Task Base..handoff whitespace 通过。
- 依 workflow 提前 FIX REQUIRED；完整 Task-range 最终审查、其他 Python quality/Web/
  E2E/真实浏览器截图、wheel/安装消费者及 Docker/restart/security 尚未全部执行，留待 B
  在修正固定候选完成。旧执行输入不同的证据不冒充当前 PASS；不提交 Closure Packet。

本机稳定证据（未声称远程可访问）：
`.git/validation-evidence/c4c9efc4614493c30126f5468ff7e5178538b5b8/task45.6/b-review/`。
含脚本、原始日志、全量结果/计时及预存 status；累计测试/质量耗时与本轮占比在该目录
`review-summary.json` 记录。未改产品/Slice/Roadmap/Progress，不 push，不关闭 Slice。
