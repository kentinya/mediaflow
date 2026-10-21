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
Next Action: DEVELOPER FIXES TASK45.6 SAME TASK; B RECHECKS FIXED CANDIDATE
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
PYTHONPATH=tests .venv/bin/python -m unittest test_automation_task_definition_preview test_automation_preview_grant_gate test_automation_definition_execution test_automation_authorized_execution_matrix
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
Candidate Head: b765198f2a71fe82b7169061e162986351cdbc37
Status: READY FOR B REVIEW
Round: fix round after B FIX REQUIRED on c71ec21 (previous report in Git)
```

### 修正交付（对应 B 的四项 Required correction）

1. **公共 CLI 分析不再制造正式执行待办**。`organize`/`batch organize` 带 `--execute`
   与否决定 `analysis_only`：不执行即共享零变更分析。识别歧义、Metadata 待选、
   Metadata 纠正、分类未命中、目标冲突五条分支统一走
   `MediaOrganizerService._analysis_finding`，只写完整计划/附件/冲突/未就绪
   evidence 与 DRY_RUN 逐项 Result，不写 `WAITING_CONFIRM`、pending
   `ConflictConfirmation`、Recognition/Metadata/Classification Review，不取得单次或
   无人值守权限。真实执行/恢复链的阻塞职责保持不变（`wait_for_*` 未改）。
   `render_summary` 对分析项输出 `ANALYSIS` + `outcome=` + 补正 next action；
   plan 未到达时 evidence 的 `unavailable_reason` 也带补正动作。
   复现 B 的 target-conflict 场景：exit 0、item `dry_run`、confirmations 0、
   Result 目标与 attachments=1 保留、两侧媒体 bytes 未变。
2. **删除独立计划页**。`OrganizePreviewPage`、`/operations/organize/preview/$previewId`
   路由与 `operations-organize-preview` destination 全部删除；完整固定计划摘要与精确
   确认改由新的共享 `OrganizePlanConfirmation` 在产生它的界面呈现：
   `OrganizeIntentPage`（分析后同页）与 `AutomationRunOncePage`（finalize 后同页）。
   保留原来的就绪子集选择、破坏性 effect 绑定/失效、持久执行历史锁定、丢响应
   有界核对与“不自动重提”。`OperationsLanding` 的运行详情直接内联同一份摘要
   （不再跳转），`OrganizeExecutionPage` 的返回目标改为整理意图。Intent 页不再
   分析后跳转，故重新分析会生成新计划（旧计划与其准入历史不可被新计划吞并）。
3. **同上下文与拒绝行为**。Run once 文档新增精确 `previewId` 与 preview action
   `path`（分析结果本身仍不带权限），刷新/重连/重启从持久记录恢复同一份计划摘要；
   旧 `/operations/organize/preview/...` URL 走普通 `Route not found`，零 API 请求、
   无退役提示/重定向/守卫（新增 router 测试）。
4. **删除 `preview-analyses` 兼容分支**。`service_api.py` 中 5 处显式分支全删，
   旧输入落到普通认证后 not-found 路由边界，无专用消息/guard。
5. **测试与 harness 迁移**。`tests/test_preview_retirement.py` 从“只验证不存在”扩展为
   真实入口证明：冲突 findings（含附件/目标/冲突类型/next action）、四类未就绪
   findings（无 review/confirmation/authority 行、零媒体变更）、分析不能被
   `tasks retry-failed --execute` 提权、以及同一 source/pin/策略下 CLI 分析与 Web
   准备计划的 target/operation/attachments/conflicts/policies 等义。Web 组件/路由测试
   迁移到同页旅程；harness/fixture 改为通过合法分析构造证据（fake server 新增
   session 级 plan-variant 与 malformed-grant 选择器，用于已在生产的同一入口）。

### 受影响检查（Developer 实际结果，仓库根除注明外）

```bash
python3 scripts/check_governance.py                                  # PASS
PYTHONPATH=tests .venv/bin/python -m unittest test_preview_retirement # Ran 12, OK
PYTHONPATH=tests .venv/bin/python -m unittest test_final_integration test_v2_manual_organize \
  test_manual_organize_execution test_organize_preparation test_v2_automation_run_once \
  test_automation_run_once test_manual_operations_contract           # Ran 169, OK
PYTHONPATH=tests .venv/bin/python -m unittest test_scan_retirement test_file_index_retirement \
  test_manual_organize_intent test_manual_organize_preview test_recovery_continuation \
  test_scope_continuation test_task_center_recovery_lineage \
  test_metadata_correction_continuation test_automation_definition_execution \
  test_automation_authorized_execution_matrix test_automation_unattended_grant \
  test_automation_admission test_automation_job_fencing test_configuration_organize \
  test_v2_rules_workspace_previews test_task_persistence test_conflict_resolution \
  test_file_media_detail                                              # Ran 390, OK
.venv/bin/ruff check .                                                # All checks passed
.venv/bin/ruff format --check .                                       # 384 files already formatted
.venv/bin/python -m compileall -q mediaflow tests scripts             # OK
git diff --check                                                     # clean
cd web && npx tsc --noEmit -p tsconfig.json                           # OK
cd web && npx eslint .                                                # OK
cd web && npx prettier --check "src/**/*.{ts,tsx}" "tests/**/*.{ts,tsx,mjs}"  # OK
cd web && npm run test -- run                                          # 78 files, 1150 tests OK
cd web && npm run build                                                # OK (dist rebuilt from final source)
cd web && npx playwright test                                          # 238 passed (fake-API suite)
cd web && npx playwright test tests/e2e/{manual-organize,automation,manual-operations,operations,library-files}.spec.ts  # 57 passed on rebuilt dist
```

`test_automation_task_definition_preview` / `test_automation_preview_grant_gate` 已在上一轮
随退役模块移除（TASK 旧命令列表已过期）；本文列出的是当前真实模块。

### 未执行 / 剩余风险（交 B）

- `playwright.python.automation.config.ts` 与 `playwright.python.config.ts` 的 Python harness
  当前启动即失败：`scripts/operations_inventory_harness.py` 用 operator principal 提交
  `POST /api/v1/jobs {command: organize}`，真实 API 现在要求 `remote_execute` 权限 +
  已启用的 remote execution + `execute=true` + execution token，因此 harness seed 报
  `403 principal lacks remote_execute permission`。复现：
  `.venv/bin/python scripts/operations_inventory_harness.py --port 4199`。属 B 的环境/
  证据工作（上一轮 harness 改动遗留，非本轮产品缺陷），故本轮未跑 Python browser specs。
- 因此 `web/tests/e2e/automation-run-once.python.spec.ts` 已按同页计划旅程改写
  （finalize 后不再跳转、重启后从持久 previewId 恢复、恢复确认改用
  prepare-summary/confirm），但**未实际执行**；`operations-inventory/live-files/visual/
  unicode` 四个 python spec 未由 Developer 运行。
- wheel/清洁构建、安装消费者、production Docker/常驻 Worker/release-security/restart-fault
  门禁按 workflow 属 B，本轮未执行。
- `AutomationDetailPage` 的无人值守授权已改为绑定已发布 definition revision（不再要求
  Preview 身份）；Web `authorize/executeTaskItemRecoveryOrganize` legacy link transports 仍
  留在 API client（后端路由仍受支持，Web 已不再使用）；是否需要删除留给 B/A 判定。
- 历史运行库若含已退役专属表不会被删除；fresh 库不创建它们（不变）。

不自判 PASS，不关闭 Slice，不规划下一 Task。

## B Review Result

```text
Reviewed: 2687e5b3eaa6f686d54c51930765e0ba904f69b5..c71ec218ca46efa7d73e53c9c82b29f3af88bd91
Decision: FIX REQUIRED
Review stage: early proven-blocker review; full range acceptance is incomplete, not PASS
Acceptance runs: governance PASS; test_preview_retirement 8/8; existing router/component reproduction 1 passed, 19 unselected; real public CLI and authenticated API reproductions confirm blockers; full gates NOT STARTED
Task blockers: analysis-only CLI creates formal execution backlog; separate executable OrganizePreview journey remains; dedicated Preview retirement guards remain
Slice Required Outcomes / Surfaces all satisfied: NO — RO-8 / S-10 / AC-8 incomplete
Next: SAME TASK FIX LOOP — Developer affected checks; B owns fixed-candidate full T4 acceptance
```

Candidate `c71ec218ca46efa7d73e53c9c82b29f3af88bd91` matches report successor
`c6c0824` in all executable inputs (`git diff` shows only the Candidate Head line in TASK).
Local reproduction scripts/logs and the compact command record are under
`.git/validation-evidence/c71ec218ca46efa7d73e53c9c82b29f3af88bd91/task45.6/b-review/`;
these local artifacts are not claimed remotely accessible. Developer's reported full runs are
handoff facts, not B's completed acceptance. Packaging/browser/security/restart and full diff/test
review remain pending B after correction; no gate is waived or transferred to Developer.
Prior Task45.5's B result at Task Base records RO-7 PASS and RO-1–6 retained/rechecked;
that conclusion and 45.4's disclosed exception remain unchanged. The older parent progress prose
does not erase that delivery. RO-8 is still incomplete, so no new Task or Closure Packet is created.

### Required correction — shared analysis and first-deployment Preview absence

1. Make public CLI `organize` without `--execute` use the same application-level analysis/plan
   semantics as Web preparation. In the reproduced real target-conflict case, only findings/plans
   may be recorded: no `WAITING_CONFIRM`, pending ConflictConfirmation or other formal execution
   backlog. Preserve real execute/recovery blocker persistence and full plan/attachment evidence;
   do not merely suppress the UI, mark blockers resolved, or replace the production chain with mocks.
   Add real CLI-entry regression assertions for conflict and the other required unready branches,
   compare meaningful plan/target/attachment/policy evidence with Web, and verify no mutation or
   execution authority. Existing actual reproduction yields exit 0, unauthorized analysis Task,
   item `waiting_confirm`, and pending confirmations 0→1 with both media byte sets unchanged.
2. Remove `OrganizePreviewPage`, its `/operations/organize/preview/$previewId` route and all actual
   navigation/deep-link producers. In particular, `OrganizeIntentPage` generates analysis then
   navigates to it; `AutomationRunOncePage.finalize` and the API `previewPath` also point there.
   Keep complete pinned plan storage and confirmation authority; show the summary and exact
   confirmation in the current organize/recovery/Run once context through existing shared behavior.
   Do not replace the old page with a redirect, retired-route guard or hidden executable alias.
3. Follow surviving links from Operations/Execution/intent/Run once to their supported destination;
   keep return context, unknown-admission reconciliation, exact subset/effect controls, old-pin and
   completed/uncertain non-replay. Replace the old-page tests with same-context journey assertions
   and an ordinary authenticated not-found assertion for the removed route.
4. Remove the surviving explicit `preview-analyses` compatibility branches in `service_api.py`
   (including the focused definitions handler), not just their underlying service. Unsupported old
   input must fall through the ordinary authenticated route/type boundary, without dedicated
   Preview-unavailable messages or guards. Retain legitimate local Rules/schedule calculations.
5. Recheck deleted-test coverage against still-supported consumers. The retirement test module
   currently tests absence/rejection/schema only; it does not prove its docstring's shared analysis,
   no-execution-authority and grant claims. Cover the surviving shared analysis/plan and native
   same-context confirmation through their real entry points; do not manufacture unreachable states.

Developer reruns changed/new tests and directly affected groups only, including:

```bash
PYTHONPATH=tests .venv/bin/python -m unittest test_preview_retirement test_final_integration test_v2_manual_organize test_manual_organize_execution test_organize_preparation test_v2_automation_run_once
cd web && npm run test -- run src/routes/router.test.tsx src/features/operations/OrganizeRouter.test.tsx src/features/operations/OrganizeCreationPage.test.tsx src/features/operations/OperationsInventory.test.tsx src/features/operations/TaskItemRecoveryPanel.test.tsx src/features/operations/AutomationRouter.test.tsx
```

Update filenames if obsolete-page tests are moved; keep equivalent safety assertions. Run changed-file
static checks, typecheck and `git diff --check`. B retains ownership of full regression, native,
wheel/image/security/restart gates on the next fixed candidate; none are assigned back to Developer.

B also notes a harness concern for its own later acceptance: the restart smoke's schedule command
was changed to organize, but its fencing fixture still advertises preview and its descriptions are
stale. No failure is claimed from strings alone; B must use the existing harness entry, establish
an actual failure if any, and repair environment/evidence work without inventing a product blocker.
