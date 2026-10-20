# Task45.6 — 独立 Preview 完整退出与整理分析/固定计划统一

Authority：已提交 [SLICE.md](SLICE.md) RO-8 / S-10 / AC-8、
[Preview 退役设计](docs/preview-retirement-spec.md) 与
[Development Workflow](docs/development-workflow.md)。
角色经验：[B](docs/agent-experience/task-planner-reviewer.md) /
[Developer](docs/agent-experience/developer-implementation-role.md)。

```text
Task ID: 45.6
Parent Slice: 45
Status: PLANNED
Task Base: 2687e5b3eaa6f686d54c51930765e0ba904f69b5
Difficulty: High
Test Level: T4
Planner / Reviewer: B
Required Outcome: RO-8 / S-10 / AC-8; affected RO-1–7 safety and journeys
Next Action: DEVELOPER IMPLEMENTS THIS TASK AND HANDS OFF A FIXED CANDIDATE
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
独立schema、共享analysis-only的零工作/权限、合法整理入口和生产装配，不只查字符串。
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

Pending implementation. 报告固定SHA、实际行为/主要取舍、受影响命令/结果及剩余风险；
不自判PASS，不规划下一Task，不等待B全量门禁。

## B Review Result

```text
Reviewed: NOT YET
Decision: PENDING
Acceptance runs: pending B fixed-candidate review
Task blockers: not assessed
Slice Required Outcomes / Surfaces all satisfied: NO — RO-8 implementation pending
Next: DEVELOPER IMPLEMENTS TASK45.6
```
