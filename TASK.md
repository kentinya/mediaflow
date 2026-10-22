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
Next Action: DEVELOPER UPDATES SHARED-GRANT TEST FIXTURE WITH REAL PREFLIGHT; B CONTINUES T4 GATES
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
Candidate Head: 4e23a53403657e8ccb9b5ab36c9fc4ab5fdbcc52
Status: READY FOR B REVIEW
Round: fourth round; fixes B's FIX REQUIRED on 2e84e8883250c3f166f61b978b33a46c641379f6
       (full-Python fixture lacks the shared-analysis evidence the grant requires)
```

### 本轮修正交付（对应 B 的 full-Python fixture 阻塞）

B 在 `2e84e88` 上运行全量 Python 时，`test_configuration_snapshot.py`
`test_worker_rechecks_current_principal_between_real_effect_boundaries` 在第 2072 行直接调用
`UnattendedExecutionGrantService.grant`，而该服务现已按 Task 要求拒绝没有真实 Run once
共享分析证据的授权，于是报 `unattended_execution_analysis_unavailable`。这是被改变的授权前置
条件未同步到同一 Task 的测试夹具，不是服务校验本身的问题。本轮只修夹具，不改产品行为。

1. **夹具改走真实授权前置。** 新增模块级 `_produce_shared_analysis`（配 `_snapshot_analysis_api`
   与 `_SnapshotTMDBProvider` 合成 Provider），沿真实生产装配
   `admit_definition_run_once` → `claim_and_run`（真实有界发现与稳定观察）→
   `AutomationRunOnceService.finalize`（冻结清单 + 共享零变更整理分析）产出证据，并断言
   `previewed`/`zero_mutation`。该分析与授权绑定同一份已发布 Active 修订。
2. **不绕过 preflight。** 同一份确认授权在分析产出前仍被拒绝：断言
   `unattended_execution_analysis_required` 且 `list_unattended_execution_grants() == ()`；
   分析产出后同一确认授权成功，随后 Worker 才产生媒体效果。
3. **原有断言全部保留。** 首项成功后当前 principal 被撤销、后续 effect 前重新核权、
   Alpha 成功 / Beta 失败的独立结果、`unattended_authority` 类别、
   `permitted_action_ids == ("investigate",)`、`len(effect_calls) == 1`、目标目录内容与
   恢复 principal 后无待处理工作，均未放宽、未跳过、未加重试。

#### 受影响检查（本轮 Developer 实际结果，仓库根）

```bash
python3 scripts/check_governance.py                                  # PASS
.venv/bin/ruff check tests/test_configuration_snapshot.py            # All checks passed
.venv/bin/ruff format --check tests/test_configuration_snapshot.py   # already formatted
.venv/bin/python -m compileall -q tests/test_configuration_snapshot.py  # OK
git diff --check                                                     # clean
PYTHONPATH=tests .venv/bin/python -m unittest test_configuration_snapshot \
  test_automation_unattended_grant test_v2_automation_operations \
  test_automation_run_once                                          # Ran 101, OK
PYTHONPATH=tests .venv/bin/python -m unittest test_preview_retirement \
  test_v2_automation_run_once test_automation_definition_execution \
  test_automation_authorized_execution_matrix test_manual_organize_preview \
  test_media_discovery                                             # Ran 190, OK
```

失败先于修正复现：父候选 `2e84e88` 上同一用例报
`unattended_execution_analysis_unavailable`（B 报告一致）；本候选通过。

#### 未执行 / 剩余风险（交 B）

- 全量 Python/Web/E2E、production assets、wheel/安装消费者/Docker/Worker/restart/
  release-security 属 B，本轮未执行。
- 仅改测试夹具，无产品代码、schema 或迁移改动；`UnattendedExecutionGrantService` 的
  授权前校验保持原样。
- 夹具新增合成 Provider 只服务该测试的本地临时根，不访问真实 TMDB/私有配置/用户媒体。

本机稳定证据（未声称外部可访问）：
`.git/validation-evidence/developer/task45.6-fix-shared-analysis-fixture/` 含
`affected-python.log`、`affected-python-2.log` 与
`verify_shared_analysis_fixture.py/.log`（独立探针：无分析 grant 被拒且 grant 行数为 0；
真实 Run once 分析后同一确认 grant 成功；来源 bytes 不变、目标为空；重开数据库后授权仍在）。

不自判 PASS，不关闭 Slice，不规划下一 Task。

### 上一轮修正交付（对应 B 的 shared Automation authorization preflight 阻塞，已被 B 核实修正）

B 在 `5b5f863` 上复现的 P1：删除独立 Preview 后，`UnattendedExecutionGrantService.grant` /
`project_eligibility` 只校验定义/配置形状、边界与当前权限，任何已激活定义无需任何真实
分析即可授予无人值守整理权限。本轮在保留的 Automation 授权旅程内承接**共享零变更整理
分析/完整固定计划**作为授权前证据，不恢复独立 Preview 产品、不另建分析队列/执行引擎。

1. **共享分析权威新增只读解析**。`MediaDiscoveryService.latest_definition_analysis`
   与仓储 `latest_frozen_definition_run_once` 按“定义身份 + 不可变 Active 配置 pin
   (revisionId/digest)”返回最近一次定义绑定 Run once 的冻结清单（真实有界发现→稳定
   观察→内部冻结→共享分析链产出的完整计划）。Run once 的 Preview 经其持久 `intent_id`
   关联，不依赖 `discovery.preview_id` 列；重新发布 Active 会使旧分析对新授权失效。

2. **授权前校验与准入共用同一后端权威**。`UnattendedExecutionGrantService` 新增
   `_require_shared_analysis` / `_validate_shared_analysis`（及 `_invalid_analysis_items`），
   `grant` 与 `project_eligibility` 都调用它：缺失→`unattended_execution_analysis_required`；
   定义身份/指纹/配置版本/ResourceLibrary/来源范围/run mode/Storage/工作量边界不匹配→
   `unattended_execution_analysis_mismatch`；过期或非零变更→`unattended_execution_analysis_stale`；
   非完成态→`unattended_execution_analysis_ineligible`；存在 blocked/failed/stale/unavailable/
   truncated/cancelled 项→`unattended_execution_analysis_item_blocked`；服务缺失→
   `unattended_execution_analysis_unavailable`(503)。全部 fail-closed，拒绝时不写 grant/audit/
   Task/Storage。`project_eligibility` 中把分析校验放在当前权限校验之后，使被禁用主体仍返回
   `unattended_permission_invalid`（保持既有断言）。

3. **生产装配接通**。`MediaFlowApi` 构造 `UnattendedExecutionGrantService` 时注入
   `discovery_service=self._media_discovery`、`preview_service=self._manual_previews`。
   CLI 的 grant 服务只用于 `assert_live`（执行期实时权威重读），不经授权前准入，保持
   `discovery_service=None`；唯一 `.grant()` 调用点在 `service_api`。

4. **测试与回归**。`test_preview_retirement` 新增 `RetainedAuthorizationPrecedentTests`：
   经真实 API/Run-once 装配证明“无分析→409 且 grant/audit/Storage 不变；eligibility 同步
   为不 eligible；真实 Run once 产出共享分析后 eligibility 转 eligible、同一确认 grant 返回
   201，仍零 mutation”。`test_v2_automation_operations` 与 `test_automation_unattended_grant`
   的 grant 用例改为先跑共享分析再授予，并新增“无分析被拒”断言；直接单测用
   `_shared_analysis_stub`/`_grant_service` 承接授权前门（测试 grant 服务自身逻辑）。

### 本轮修正交付（对应 B 的 durable in-context Run-once plan 阻塞）

B 在 `bb0b1f3` 上复现的 P1：Run once finalize 把计划写在 linked intent 上，但
`AutomationRunOnceService.document` 读取该路径从不写入的 `discovery.preview_id`，
于是普通 GET 返回 `phase=frozen / previewId=null`，`actions.preview.available`
为 true 而 `path=null`；同页摘要只靠 React 局部 `admittedPlanPreviewId`，重开即消失。
本轮只恢复持久权威解析与投影，不恢复独立 Preview 产品、不新建分析/队列/兼容页。

1. **持久权威解析**。`AutomationRunOnceService` 新增 `_durable_plan_id`：优先
   `discovery.preview_id`（真实 preparation 路径），否则经 linked intent 的
   `preview_service.latest_readonly` 读取该次运行已产出的精确计划。这是有界、
   非发布式只读投影：普通 GET 不重新发现、不重新分析、不生成第二份计划、不标记
   证据过期、不变更 Storage。读取失败是真实的“无计划”，不从最近记录猜测。
2. **投影与广告一致**。`document()` 的 `previewId` 与 `actions.preview.path`
   使用同一解析结果，因此不会再出现“可用但没有地址”的动作；已冻结清单仍不提供
   第二次 finalize。
3. **同页恢复**。`AutomationRunOncePage` 与意图页同一模式：finalize 成功后把
   精确计划身份写入旅程 URL（合并保留的 Files/Operations 返回上下文），重载/
   前进后退/重开链接按 URL 提示恢复；URL 计划不得覆盖更新的持久计划；
   `OrganizePlanConfirmation` 绑定 `expectedIntentId`，非本运行意图的计划不显示、
   不提供执行。读取不取得任何权限。
4. **测试与回归**。`test_v2_automation_run_once` 新增
   `test_frozen_run_once_plan_survives_a_plain_read_and_a_reopen`（真实 HTTP
   finalize201→同 URL GET200 同一 previewId、action path、零二次 finalize/分析、
   source/target mutations 为空、SQLite 重开后 `get_latest_manual_preview` 仍为
   同一份）与 `test_unfrozen_run_once_publishes_no_plan_identity`；
   `test_preview_retirement` 新增 `RetainedRunOncePlanTests`，从真实 API/Run once
   装配复述同一条链路。新增 `web/src/features/operations/AutomationRunOncePage.test.tsx`
   覆盖同 URL 空 cache 重载恢复、冻结态、陈旧 URL 计划被持久计划取代、冻结前只有
   finalize。两条 Python 回归与 Web 重载回归在父候选 `bb0b1f3` 上均为红，在本候选为绿。

### 受影响检查（本轮 Developer 实际结果，仓库根除注明外）

```bash
python3 scripts/check_governance.py                                  # PASS
.venv/bin/ruff check mediaflow tests                                 # All checks passed
.venv/bin/ruff format --check mediaflow tests                        # 320 files already formatted
.venv/bin/python -m compileall -q mediaflow tests scripts            # OK
git diff --check                                                     # clean
PYTHONPATH=tests .venv/bin/python -m unittest test_preview_retirement \
  test_scan_retirement test_file_index_retirement                   # Ran 39, OK
PYTHONPATH=tests .venv/bin/python -m unittest test_manual_organize_intent \
  test_manual_organize_preview test_manual_organize_execution test_v2_manual_organize \
  test_organize_preparation                                          # Ran 117, OK
PYTHONPATH=tests .venv/bin/python -m unittest test_recovery_continuation \
  test_scope_continuation test_task_center_recovery_lineage \
  test_metadata_correction_continuation                             # Ran 185, OK
PYTHONPATH=tests .venv/bin/python -m unittest test_automation_run_once \
  test_v2_automation_run_once test_v2_automation_operations test_preview_retirement \
  test_automation_definition_execution test_automation_unattended_grant \
  test_automation_authorized_execution_matrix                       # Ran 121, OK
PYTHONPATH=tests .venv/bin/python -m unittest test_configuration_organize \
  test_v2_rules_workspace_previews test_task_persistence test_automation_admission \
  test_automation_job_fencing test_manual_operations_contract \
  test_media_discovery                                              # Ran 213, OK
cd web && npm run test -- run src/features/operations/AutomationRunOncePage.test.tsx \
  src/routes/router.test.tsx src/features/operations/OrganizeRouter.test.tsx \
  src/features/operations/OrganizeCreationPage.test.tsx \
  src/features/operations/OperationsInventory.test.tsx \
  src/features/operations/TaskItemRecoveryPanel.test.tsx            # 6 files, 76 tests OK
cd web && npm run test -- run src/features/rules/RulesObjectTestPanel.test.tsx \
  src/features/operations/AutomationRouter.test.tsx \
  src/features/operations/AutomationLifecyclePage.test.tsx \
  src/entities/operations/run-once.test.ts                          # 4 files, 52 tests OK
cd web && npx eslint src/features/operations/AutomationRunOncePage.test.tsx \
  src/features/operations/AutomationRunOncePage.tsx                 # clean
cd web && npx prettier --check src/features/operations/AutomationRunOncePage.test.tsx \
  src/features/operations/AutomationRunOncePage.tsx                 # clean
cd web && npm run typecheck                                          # OK
```

### 未执行 / 剩余风险（交 B）

- 全量 Python/Web/E2E、production assets、wheel/安装消费者/Docker/Worker/restart/
  release-security 属 B，本轮未执行。
- 未改 schema/迁移；`_durable_plan_id` 为纯只读查询，历史运行库不受影响。
- 授权前分析校验（`latest_frozen_definition_run_once`）的 503 fail-closed 行为沿用上轮结论。
- 共享分析校验依赖 `discovery.intent_id`→`preview_service.latest_readonly`；若某适配
  服务不提供 `latest_readonly`，Run once 读退化为“无计划身份”（动作 path 为 null），
  不会伪造计划。
- 未做冻结 Slice43 的页面/指标/设置重设计；本轮只恢复既有 Run once 同页持久关联。

本机稳定证据（未声称外部可访问）：
`.git/validation-evidence/da5e80107aae7fe7b93d231ebe8656e53a4ce923/task45.6/developer/`
含 `verify_positive.py/.log`（真实 API 准入202→Worker→finalize201→同 URL GET200 同一
previewId 与 action path、零二次 finalize/分析、source/target mutations 为空、SQLite
重开后同一份计划；同一探针在 `bb0b1f3` 上按 B 报告断言失败）、`web-verify.log` 与
`web-parent-failure.log`（新 Web 重载回归在本候选 4/4 通过，在父候选按同一断言失败）。

不自判 PASS，不关闭 Slice，不规划下一 Task。

### 上一轮记录（授权前分析阻塞，已被 B 核实修正）

#### 受影响检查（Developer 实际结果，仓库根除注明外）

```bash
python3 scripts/check_governance.py                                  # PASS
.venv/bin/ruff check mediaflow tests                                 # All checks passed
.venv/bin/ruff format --check <8 changed py>                         # already formatted
.venv/bin/python -m compileall -q mediaflow tests scripts            # OK
git diff --check                                                     # clean
PYTHONPATH=tests .venv/bin/python -m unittest test_preview_retirement \
  test_scan_retirement test_file_index_retirement test_automation_unattended_grant \
  test_v2_automation_operations test_automation_run_once \
  test_automation_definition_execution test_automation_authorized_execution_matrix  # Ran 127, OK
PYTHONPATH=tests .venv/bin/python -m unittest test_manual_organize_intent \
  test_manual_organize_preview test_manual_organize_execution test_v2_manual_organize \
  test_organize_preparation test_automation_admission test_automation_job_fencing \
  test_manual_operations_contract test_configuration_organize \
  test_v2_rules_workspace_previews test_task_persistence              # Ran 218, OK
PYTHONPATH=tests .venv/bin/python -m unittest test_recovery_continuation \
  test_scope_continuation test_task_center_recovery_lineage \
  test_metadata_correction_continuation test_v2_automation_lifecycle \
  test_automation_definition_occurrence test_v2_automation_run_once   # Ran 247, OK
cd web && npm run test -- run src/features/operations/AutomationRouter.test.tsx \
  src/routes/router.test.tsx src/features/operations/AutomationLifecyclePage.test.tsx  # 3 files, 31 tests OK
cd web && npm run typecheck                                          # OK
```

本机稳定证据（未声称外部可访问）：
`.git/validation-evidence/task45.6-fix-preflight/verify_positive.py` 与 `verify_positive.log`，
用真实 `_journey` 证明：无分析 grant 409（`unattended_execution_analysis_required`，grant/audit=0）；
真实 Run once 分析后 eligible=true、grant 201、grant/audit=1、`manual_previews>=1`，且来源
bytes 不变、目标为空、source/target mutations 均为空。

#### 未执行 / 剩余风险（当时交 B）

- 全量 Python/Web/E2E、production assets、wheel/安装消费者/Docker/Worker/restart/
  release-security 属 B，当时未执行。
- 未改 schema/迁移；`latest_frozen_definition_run_once` 为纯只读查询，历史运行库不受影响。
- 共享分析校验依赖 `discovery.intent_id`→`preview_service.latest_readonly`；若某适配仓储
  不提供 `latest_frozen_definition_run_once`，授权前门返回 503（fail-closed）而非放行。
- Web 未改：`AutomationDetailPage` 已按 `grantEligibility.eligible` 渲染说明/隐藏授权按钮，
  不 eligible 时不显示确认框；当时未新增 Web 分析发起入口（Run once 页面既有的共享分析即
  授权前分析来源），未做冻结 43 的页面重设计。


## B Review Result

### Current review — `2e84e8883250c3f166f61b978b33a46c641379f6`

```text
Reviewed candidate: 2e84e8883250c3f166f61b978b33a46c641379f6
Task range: 2687e5b3eaa6f686d54c51930765e0ba904f69b5..2e84e8883250c3f166f61b978b33a46c641379f6
Decision: FIX REQUIRED
Review stage: durable Run once recovery and focused gates pass; full regression blocker found
Task blocker: full Python regression fails because a direct grant fixture has no shared-analysis evidence
Next: SAME TASK FIX LOOP; B owns remaining full/native/packaging/security/restart gates
```

- 上轮 Run once 刷新阻塞已修复。本轮从真实授权详情动作，经HTTP Run once admission/finalize、
  同URL GET、 intent计划GET及明确grant再次独立验证通过：planId相同、操作只读、授权需分开确认，
  来源bytes不变、目标为空、Storage mutation为空。Python受影响组 **84 passed**；Web受影响组
  **10 files / 128 passed**。候选实现 diff（`bb0b1f3..HEAD`）及新增的同URL刷新/陈旧URL/
  冻结前保护测试已审，未发现新的生产行为阻塞。此前授权前分析修复保持有效。
- **全量 Python 失败，夹具欠缺共享分析证据。** `.venv/bin/python -m unittest discover -s tests`
  结果 `Ran 2672 tests in 253.967s; FAILED (errors=1, skipped=7)`：
  `tests/test_configuration_snapshot.py::ManagedConfigurationSnapshotTests.test_worker_rechecks_current_principal_between_real_effect_boundaries`
  在行2072直接调用 `UnattendedExecutionGrantService.grant`，但该服务现在按Task要求拒绝没有真实
  Run-once共享分析证据的grant（`unattended_execution_analysis_unavailable`）。这是被改变的授权前置
  条件尚未同步到同一Task测试夹具，不是允许去掉服务校验；要求该测试以合法、真实的共享分析前置
  建立grant，保留逐effect权限重检断言。无skip/放宽权限/制造内存preview作为替代。
- Python全量之外的 B 质量门禁通过：ruff format检查（384 files）、ruff check、compileall、
  pip check、两个示例配置验证、无FFmpeg/FFprobe命中、`git diff --check`。Web typecheck、lint、
  format和production build通过（有现有bundle >500kB提示）。B已开始但中止全量Web Vitest；
  因Python全量不绿且本轮测试时间预算接近50%，Web全量及E2E/native/asset/wheel/installed consumer/
  Docker/Worker/restart/release-security等门禁尚未完成，均保留为B责任，不是豁免或交回Developer。
- 复核所有入口均基于已存在路由/真实组件；未构造虚假产品状态。未改Slice/Roadmap/Progress，
  保留预存dirty/private工作，未访问私有配置、用户运行库或真实媒体。治理PASS。

#### Required correction — Task45.6 的测试/夹具修正

1. 修复 `test_configuration_snapshot.py` 上述真实worker权限边界测试的setup：grant写入前使用现有
   受支持的 Automation Run once 和共享整理分析链，绑定相同定义、Active revision/digest/version、
   source scope与Storage；不直接省略grant校验。已有共享分析fixture/辅助方法可复用。
2. 保留原测试“一个文件效果成功后当前principal撤销，后续effect前重新核权并保留已完成项”的
   原断言。Developer运行此测试、`test_automation_unattended_grant`、`test_v2_automation_operations`、
   `test_automation_run_once`及changed-file质量检查；仅当共享fixture有改动时补充对应受影响测试。
   不跑全仓套件；提交同Task连贯handoff。
3. B重跑修正后的全Python门禁，然后在原固定候选上继续未完成的Web全量、指定Python-backed
   浏览器journeys、独立关键CLI/API/Worker证明、clean wheel/安装消费者、Docker/restart/security，
   并完成完整Task Base..Head审查。按执行输入复用本轮通过的匹配证据；Slice-final只补缺项。

本轮开始 `2026-10-22 10:20 +0800`；full Python约254s、受影响Python约11s、受影响Web约13s，
质量/构建及不完整Web尝试合计仍在本轮实际用时50%以内。所有run实际结果和输出保存在：
`.git/validation-evidence/2e84e8883250c3f166f61b978b33a46c641379f6/task45.6/b-review/`。

### Previous B review — `bb0b1f314916d316ef384430ce3633e6220b3e21`

```text
Reviewed candidate: bb0b1f314916d316ef384430ce3633e6220b3e21
Task range: 2687e5b3eaa6f686d54c51930765e0ba904f69b5..bb0b1f314916d316ef384430ce3633e6220b3e21
Decision: FIX REQUIRED
Review stage: early proven-blocker review; complete Base..Head/T4 acceptance remains pending
Task blocker: Run once shared-plan summary/confirmation is not restored at the same durable URL
Required Outcomes / Surfaces all satisfied: NO — RO-8 / S-10 / AC-8 retained shared journey incomplete
Next: SAME TASK FIX LOOP; B owns corrected-candidate full T4 acceptance
```

### 已核实交付与边界

- Governance PASS；branch main，固定候选为上述 SHA；工作区与 Git 可写。预存图片删除、
  日志、截图、压缩包及 `.DS_Store` 原样保留；未访问私有配置、运行库或真实媒体。
  未改 Slice/Roadmap/Progress；Task45.5 的 RO-7 PASS 与先前接受/验证例外不变。
- **上轮授权前分析阻塞已修正。** B 沿真实定义详情广告的 grant/runOnce 动作，使用隔离
  Local/SQLite/fake Provider：无分析 grant 409 (`unattended_execution_analysis_required`)，
  grant/audit=0；HTTP Run once 准入202→真实 discovery claim/run→HTTP finalize201→共享
  计划 GET200。合格分析后 eligibility=true，但仍 grant=0；另行明确 grant POST201 后
  grant/audit各1。来源 bytes不变、目标为空、两侧 mutation为空。没有手工 upsert 工作状态。
  这证明本次核心修正的正反路径，不代替全部 stale/mismatch/运行期或原生浏览器验收。
- **P1：该实际共享消费者重开后丢失同页固定计划。** 同一次 HTTP finalize201 返回精确
  `previewId`，随后对既有 Run once URL GET200 却返回 `phase=frozen / previewId=null`，
  finalize不可用，preview action虽available但path=null；原共享计划仍GET200且没有新增计划。
  B把这些真实响应送入现有完整 router/component：点击“冻结清单并生成计划摘要”后摘要
  可见；相同URL、空query cache重新挂载后“来源清单已冻结”可见，但摘要及其确认区消失，
  POST仍仅1次。期望同页恢复的断言 **1/1失败**，不是伪造状态或不存在的入口。
- 页面仍有“打开整理意图”跳转，不能宣称整个整理流程不可恢复、计划丢库或发生越权变更。
  阻塞是本Task已要求的**原旅程持久证据/同页摘要恢复**未完成；本轮Developer还将Run once
  作为保留的授权前分析入口，因此不能以冻结43页面重设计延期豁免这个必要共享耦合。
  只修持久计划解析/投影，不要求重做43工作区、指标或设置。
- 根因：`AutomationRunOnceService.finalize` 将计划写入intent的共享计划记录；
  `document/_actions` 却读取未被该路径写入的 `discovery.preview_id`。Web finalize后靠
  React局部 `admittedPlanPreviewId` 展示；重开时回退到空的 `model.previewId`，因此不挂载
  既有 `OrganizePlanConfirmation`。新grant逻辑已正确从intent解析计划，Run once读取没有同步承接。

本机稳定证据（不声称外部可访问）：
`.git/validation-evidence/bb0b1f314916d316ef384430ce3633e6220b3e21/task45.6/b-review/`。
含 `public-run-once-probe.py/.log`、真实 `public-api-documents.json`、
`AutomationBReview.test.tsx`、`router-reload.log`、计时与review摘要。Python探针断言观察事实；
Web测试断言应有恢复行为，当前为红。初次探针误期望准入201（实际202）的harness错误日志保留，
修正harness后公共链路完成；不作为产品失败或隐藏重试。

本轮审查本次修正及Task范围内相关Run once/计划/授权消费者；**完整Task Base..Head与全量
Python/Web/E2E、production/native/wheel/installed-consumer/Docker/security/restart门禁仍pending**。
依据workflow §6，在已证明P1后提前返回，不豁免、不交回Developer、不把受影响测试冒充B全量。
旧候选结果只按匹配执行输入复用；本候选没有机械重跑Final。未验证的harness环境事项不列产品阻塞。

### Required correction — durable in-context shared plan

1. 在现有Run once→intent→完整共享计划关系上恢复持久权威：正常GET/重连可解析该次运行
   已产出的精确计划身份；投影与现有同页组件一致。可复用共享只读解析，不新建独立产品/
   生命周期/队列或兼容页，不从客户端缓存、最新全局计划或不相关intent猜测。
2. 冻结/分析成功后，清空浏览器内存、重连以及同版本数据库重开仍能在原URL查看同一份
   来源/配置/版本/附件/冲突/未就绪摘要；已准入执行仍显示原持久结果并阻止自动重放。
   读取不得重新分析、调用Provider、生成第二份计划、授予权限或执行。若无合法计划，明确
   原旅程安全补正动作；不能“frozen但没有摘要且不能继续”。不要求已过期计划恢复可执行。
3. 保留本轮已证实的缺分析拒绝/合格分析不授权/另行grant成功，以及intent页先前刷新修正。
   补充真实HTTP finalize→GET、SQLite重开及真实router空cache恢复断言，不能只填fixture字段
   或只断言POST响应；当前B红测可作最小复现参考。现有跳转恢复不是同页持久关联的替代。

### Developer — 受影响验证与 B 最终门禁

Developer仅执行新改/直接受影响验证，仓库根：

```bash
python3 scripts/check_governance.py
PYTHONPATH=tests .venv/bin/python -m unittest test_v2_automation_run_once test_automation_run_once test_v2_automation_operations test_preview_retirement
```

若更改共享计划/发现持久化，追加 `test_manual_organize_preview`、`test_media_discovery` 及
实际直接受影响存储测试；若更改grant，追加 `test_automation_unattended_grant`。
Web在现有Automation旅程测试内加入Run once刷新回归，在web/运行对应changed test；
若触及共享组件，再跑 `src/features/operations/OrganizeRouter.test.tsx`。运行changed-file
ruff/eslint/prettier、DTO的typecheck及 `git diff --check`。提交同Task连贯候选并报告实际结果；
不跑全Python/Web/E2E或发布矩阵，不补B全量证据包。

B在纠正候选上独立复核上述阻塞，审完整Task Base..Head，并执行本Task原定全部适用T4门禁；
覆盖与执行输入匹配才复用，完整覆盖可同时满足Slice-final，不机械重跑。实际测试/build/quality
累计远低于本轮实际工作时间50%，包括失败探针和Web红测；具体计时见证据目录。
RO-8仍未满足，不造下一Task、不提交Closure Packet、不宣告SLICE READY FOR A REVIEW或自行关闭。
