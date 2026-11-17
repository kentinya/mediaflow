# Task55.4 — 唯一当前配置：管理启动、发布与运行消费

Task55.3 已由 B 独立验收 **PASS**；完整接受范围
`b73c36353e5427cbe60fbb7c1b8cc85b139edca4..78d3e252090ca13149bf953b803eeb37918d9b30`。
原计划、B55.3-01–05 修正、实际门禁、失败／跳过和复用限制保留于
[64006c8d:TASK.md](https://github.com/kentinya/mediaflow/blob/64006c8d3b0a2791e5228417420250a064c75cea/TASK.md)。
Task55.1／55.2 的接受事实保持。Slice55 仍 ACTIVE，尚未满足全部结果。

用户现明确要求“激活Task吧”，据此将已规划的 Task55.4 激活为正式实施 Task。
Goal／Scope／Task Base／High／T4／验收与测试分工保持原计划。
Next Action: **DEVELOPER STARTS TASK55.4 IMPLEMENTATION**。
本轮仅激活 TASK；SLICE／Roadmap／Progress 保持原合同和接受身份。

Authority: committed [Slice55](SLICE.md) RO-3，以及本单元相关 RO-5／6、AC-03／05／07／08／11／12。
生命周期和测试分工以 [Development Workflow](docs/development-workflow.md) 为准；
实施前读 [Developer 指南](docs/agent-experience/developer-implementation-role.md)。

```text
Task ID: 55.4
Task Type: SLICE
Parent Slice: 55
Status: PLANNED
Task Base: 64006c8d3b0a2791e5228417420250a064c75cea
Difficulty: High
Test Level: T4
Planner / Reviewer: B
Development Authorization: TASK55.4 IMPLEMENTATION AUTHORIZED
```

规划基线 main，上述 HEAD；初始 tracked／untracked 工作区干净，TASK 与 Git 可写，
`python3 scripts/check_governance.py` PASS。该 Base 固定，不以草案／激活提交重设；如有
介入产品改动，B 先核对集成与本计划适用性。
本轮激活前 main／HEAD `6463cee9d1278d46a12b6410bc2b27f2f0c9fdbb`，工作区干净、
治理 PASS；Task Base 至该 HEAD 只有本 Task 草案文档提交，无介入产品改动。

### Goal 与完整用户旅程

只由部署最小 bootstrap＋`api.principals` 启动管理服务，由真实 managed Active／原工作 pin
提供业务配置；新提交只接受当前正式配置，不再通过旧字段合并、忽略或默认策略得到另一套行为。
对应 `V2-RETIRE-004/006/009/010`、相关 `008`，保留 `REQ-CONFIG-001–012`、
`V2-SETUP-001/002`、`V2-CONFIG-001–004`、`V2-RULES-002/004/005/010–012` 的当前义务。
适用旅程为 Product Experience 的 TARGET、Configuration lifecycle、First-time setup、
Recognition and rules／Object-scoped tests／Naming and classification destination、Slice54 dialogs；
适用架构为 TARGET Configuration、Configuration authority/runtime binding 与 Empty business runtime。
TARGET 仅替换其中明确退出的兼容义务。

1. 管理员生成最小 bootstrap，启动无媒体挂载的四服务，连接其明确配置的 principal。
   系统设置准确显示未初始化；查看页面不创建 Draft 或业务工作。
2. 显式创建／恢复首个 Draft，检查并激活空 Active；之后在 Storage、两种库、七类规则、
   自动化和通知的当前表单保存配置。高级设置仍能查看／导出 JSON、导入当前文档、完成
   适用检查并激活；整份 JSON 是配置输入，不直接成为运行权威。
3. 配置通过时只有精确候选成为 Active，运行服务实际采用；旧工作继续读取原 pin。
   填错旧字段、引用或并发版本时，界面保留输入和原 Active，说明字段／阶段及修改、
   刷新权威或重做检查的下一步。丢失 Save 响应时核对原请求，不能自动重提。
4. 已有稳定 V2 实例使用同一数据库继续浏览、编辑、发布、读取历史和完成合法在途工作。
   例如原分类目标为 `/Media/Movies/Anime/作品/文件`，升级后查看、无关改名、分析和原 Task
   执行仍指向该位置，不能因删除 `library` 支持而变成 `/Media/Anime/作品/文件`。

### 真实代码缺口与现有入口

| 链路 | 当前事实与本单元交付 |
|---|---|
| 启动／权威 | `final_cli._configuration` 在无 managed Active 时回落完整 `load_runtime_configuration`；`configuration_snapshot.status_document` 广告 JSON_BOOTSTRAP 可运行。移除这个运行来源，保留 management-only、空 Active、坏 Active 恢复和合法原 pin 读取。 |
| 身份 | `runtime_configuration` 的两个配置类、`service_api.MediaFlowApi` 单 bearer 构造器和 `_CurrentConfiguredPermissionAuthority` 仍生成 legacy-admin；`domain/configuration_management.py` 还把单 token 与 principals 视为等价。退出这些授权回落；保留部署 principal 身份、角色、实时权限检查和导入的身份不可改写规则。`api.principals[*].tokenEnv` 是当前秘密引用，继续保留。 |
| 运行配置 | `runtime_configuration._storage` 合并顶层连接参数与 options，ResourceLibrary 读取 rootPath 别名，automation.taskDefinitions／notifications.webhooks 双位置读取，staleJobAgeSeconds 仍入允许表。新输入只接受当前表达，当前业务 reader 不再承担纯迁移转换。 |
| 规则输入 | `strategy_user_configuration` 和 `configuration_objects` 接受／忽略旧 MetadataPolicy.mediaType、overwrite、分类 library/category/subcategory／旧扁平形状及旧命名模板字段。对照当前表单生产者逐项收敛；不能把候选自身类型、分类条件 mediaType、Storage／MediaLibrary.rootPath 或正式模式误删。 |
| 当前发布／投影 | `configuration_objects`、`configuration_snapshot`、API 的 Webhook 边界比较和能力投影仍读 nested spellings；RulesObjectForm 仍提供“移除旧版前缀并改用修订目标”。退出纯迁移输入／转换 UI，保留合法 V2 规则的完整目标含义和普通编辑。 |
| 事件／默认 runner | `NotificationEventType.parse` 映射 job.*，并暴露 JOB_*；`pyproject.toml` 注册 strategy-test，`cli.py` 仍有独立 runner、默认业务策略及可执行入口；`RecognitionTypePolicyRegistry` 是旧 bootstrap 包装。删除专属入口／装配／别名，当前 analyze、规则测试、规划、C→A 身份与共享引擎继续可用。 |
| 交付消费者 | 两份现有完整示例包含 nested Webhooks、job.*、分类前缀及 overwrite；部署生成器 `--mode media` 仍可生成完整运行配置。更新为唯一当前 bootstrap 与规范配置输入，改接 CI／wheel／Docker／harness 的真实配置发布，不能只改正向测试名称。 |

本轮在临时目录从已注册 CLI 执行：示例 `config validate` 成功；同文件 `config status`
返回 `authority=JSON_BOOTSTRAP, runtimeConfigured=true, active=null`；改为 `api.tokenEnv`
后 `api credentials check` 显示 legacy-admin/admin（环境引用未设置，exit1）；混用资源库
rootPath 与新增 MetadataPolicy.mediaType 均 `config validate` exit0。无 Provider／媒体操作。
原始结果 `.git/validation-evidence/64006c8d/task55-4-planning/existing-entry-probes.json`，
5 次入口验证共0.784秒；源码事实不冒充产品验收。

### Implementation Scope 与 Developer 开发指导

按下面顺序完成一个配置生命周期，不按字段另拆 Task。复用现有 loader、managed service、
checked publication、配置包和 UI；不新增配置平台、迁移服务或额外操作步骤。

1. **先固定当前生产者和保留样本。** 从部署生成器、当前 V2 首次设置／typed Save／高级
   导入、CLI config 命令、各常驻服务及原 pin resolver 跟到 loader。按上表记录“新输入／
   当前正式生产者／已接受 V2 数据读取／纯兼容专属”的调用关系，直接写进相应测试或交接，
   无需新工具。用 Slice Base 与 Task Base 真实代码在隔离库经当前入口建立首个 Draft、
   Active、带完整分类前缀的现有规则、后继 Draft、已准入待分析／待确认／已确认工作和结果；
   候选直接继续使用。不能拿候选手工拼数据库代替这个保留样本。
2. **收敛启动与身份。** 正式 API／Worker／Scheduler／Notification Worker／CLI 共享最小
   部署边界，业务解析只从精确 Active 或合法已发布 pin 取得。删除完整 JSON runtime、
   tokenEnv→legacy-admin、单 bearer 构造器及其等价比较；实际调用方和测试使用显式
   principals。保留当前 `api token generate`、凭据状态、配置校验／导入／导出、备份恢复等
   实际共享能力；`config validate` 校验规范完整文档不等于批准该文档直接启动业务。
   无 Active 返回首次设置；曾有 Active 而损坏／缺失时仍进入恢复，不能伪装新实例。
3. **在现有提交边界采用同一当前规则。** Draft import／更新／validate／activate、配置包、
   typed 对象 Save／对象测试、高级设置与 CLI 文件校验均拒绝本单元纯废弃字段；覆盖单独
   旧写法和与当前字段混用，不能让“当前字段优先”或脱敏／部署绑定先抹掉旧输入而通过。
   规范字段为 Storage.options、ResourceLibrary.displayRootPath、根级
   automationTaskDefinitions／webhooks、MetadataPolicy.mediaQueryType、conflictStrategy、
   Classification mediaLibraryId＋path 及现行模板字段。沿真实调用核对同类命名／模式／包
   别名，只删除已证实的纯兼容读取；当前正式枚举值和包 schema 名称不能因含 v1 或年代旧
   被改名。保留 maximumActiveJobs、CANCEL_JOB/cancel_job、三项参数及实际采用／override。
4. **把现有 V2 的合法读取作为当前职责保留。** 原 revision 文档、ID／digest、Draft 内容、
   pins 和任务证据不重写；已有有效工作不重新受理，原四类恢复／未知请求仍能核对。
   新输入约束不能直接套在所有历史读取上。先以 Base 真实入口样本确认合法性，再收敛
   必要 reader；不能用新补的版本标志或“缺字段／旧名称”猜测其无效。分类保留目标路径，
   移除专门的迁移卡／删前缀动作后仍可用当前 MediaLibrary＋path 编辑同一目标；普通
   名称修改、复制、系统设置或其他对象 Save 不能顺带丢掉前缀、丢规则或使原 pin 不可读。
   这不是对纯 V1 输入新增转换支持，也不建立通用格式接管。
5. **移除纯事件／默认装配并接回当前功能。** 新 Webhook 只用 task.*／schedule.emitted；
   删除 job.* 别名生产／消费及默认 runner 的独立入口／默认策略接线，当前纯分析和零变更
   规则测试继续走现有引擎。合法历史通知／投递保留原 ID、payload、状态和效果，不重投。
   cli.py 中仍被当前 CLI 使用的渲染／辅助函数按真实引用保留；不顺手重构引擎或移动整包。
6. **同步本单元消费者和说明，交可复核候选。** 示例、生成器、CI、安装后 smoke、Docker
   和浏览器夹具从管理启动后经当前 import／检查／发布获得业务配置。去掉旧运行生成模式
   及纯旧示例引用；可保留现行规范输入样例。若更换示例路径，同提交更新所有实际引用及
   workflow 的命令路径。README／configuration／deployment／release 只修本单元实际
   行为，不把整个 Slice TARGET 提前改 CURRENT。删除旧正向测试时把其当前功能／权限／
   零效果断言接到当前入口。完成 affected tests 后提交 READY FOR B REVIEW。

### Acceptance Criteria

- [ ] AC-1：四服务仅管理 bootstrap 启动；明确 principals 正常鉴权和角色隔离，无隐式管理员。
  无 Active／空 Active／坏 Active 可辨；原来完整 JSON 直接运行和旧单 token 输入不再获得
  业务／管理员权威。状态、CLI help、默认装配及安装产物不再广告这些路径。
- [ ] AC-2：当前完整配置文档仍能校验、作为 Draft 导入／编辑、完成检查并显式原子激活；
  配置包和高级 JSON 能查看／导出／恢复，部署身份不可经它们修改；没有默认业务对象。
  新输入里的指定旧字段／纯别名及混合表达在现有边界准确拒绝，未发布、未创建业务 Task、
  未调用媒体变更；允许正常拒绝审计，不能以401／503代替输入判断。
- [ ] AC-3：Storage／两种库／七类规则、Automation／Webhook 和设置当前保存可用，权限、
  引用、exact evidence、并发更新／两管理员、失效检查和未知 Save 核对保持。错误指明实际
  阶段、保留状态及具体下一动作；当前未保存输入、返回和重认证归属保持。
- [ ] AC-4：Slice Base 与 Task Base 的上述真实 V2 样本由候选重开并继续读取／发布／执行；
  原 Draft／Active／digest／pins／Task／结果／审计不丢失，不重发任务，成功／未知效果不
  重放。分类原完整目标、普通编辑／复制后目标和原 Task 目标相同，迁移转换入口已退出。
- [ ] AC-5：maximumActiveJobs 和 CANCEL_JOB/cancel_job 名称不变；当前容量、Worker／
  Scheduler 实际采用、取消、Enabled／Run once 权限与合法原工作上下文保持；C 用 A
  Naming／Classification 仍为 C。新旧读取的配置校验／发布／分析没有媒体变更。
- [ ] AC-6：strategy-test console、默认业务策略装配和本单元纯兼容别名退出源码及 wheel／
  镜像；共享规则测试、CLI analyze、手工整理／due／Run once／四类恢复与通知仍可完成。
  新事件使用当前名称；现有合法通知记录、投递和未知结果不被转换重投或删掉。
- [ ] AC-7：从空四服务 → 系统设置建首 Draft／空 Active → typed 配置／高级检查激活 →
  真实业务使用与同版本重启通过。桌面／390px／矮窗口的规则目标编辑及设置失败／恢复
  可读，键盘动作和原来源返回可达；无旧转换卡。wheel／源码外安装、Docker 和当前说明
  与本 Task 行为一致，T4 实际门禁完成后才可 PASS。

### Required Tests

按 [测试分工和 shared full gates](docs/development-workflow.md#6-test-levels) 执行。
运行时记录测试／构建区间；本轮验证墙钟合并时间须小于本轮工作总时间50%。先核对用户
结果、定位关键失败，再运行适用门禁；B 负责完整验收，Developer 不跑全仓套件或发布矩阵。

**Developer — 新增／修改与直接受影响测试**（仓库根；只执行此次改动涉及的组）：

```sh
.venv/bin/python -m unittest tests.test_management_setup tests.test_configuration_snapshot tests.test_api_security tests.test_configuration_management tests.test_configuration_package_exchange
.venv/bin/python -m unittest tests.test_runtime_storage_configuration tests.test_runtime_strategy_configuration tests.test_configuration_objects tests.test_configuration_successor_draft tests.test_system_settings_management
.venv/bin/python -m unittest tests.test_configuration_classification tests.test_configuration_destination tests.test_configuration_naming tests.test_configuration_organize tests.test_v2_rules_workspace_commands tests.test_v2_rules_object_analysis
.venv/bin/python -m unittest tests.test_strategy_cli tests.test_strategy_configuration tests.test_notifications tests.test_webhook_management tests.test_notification_delivery_management tests.test_container_deployment
```

第一组覆盖管理启动／身份／原 pin／配置交换，第二组覆盖严格格式和后继保存，第三组覆盖
原路径与共享 checked publication，第四组改接退休 runner／事件／产物消费者的当前断言。
在这些现有测试中增加 AC-1–6 具体案例；若旧 runner 测试文件彻底退出，把当前引擎断言
迁入对应保留测试，再在交接写实际替代命令。Base 样本连续使用属于本改动的直接验证。
改过的 Python 文件运行 `.venv/bin/ruff check <changed-python-files>` 与
`.venv/bin/ruff format --check <changed-python-files>`；两份规范样例运行现有 `config validate`
命令（若替换路径则同步命令），治理与 `git diff --check`。

Web（cwd `web/`）：

```sh
npm run typecheck
npm run test -- run src/features/configuration/ConfigurationPage.test.tsx src/features/rules/ClassificationDestinationForm.test.tsx src/features/rules/RulesWorkspacePage.test.tsx src/features/rules/RulesObjectTestPanel.test.tsx src/entities/rules/rules-form.test.ts
```

增加新格式输入／原目标可编辑与未知 Save 的直接受影响断言；改文件运行对应 ESLint／
Prettier。按当前 UI 的实际改动运行定向浏览器旅程，不把 DOM 字段删除当作结果证明。

**B — 独立验收与完整回归**：

- 审查完整 `Task Base..candidate`，先复现表中已存在的启动／CLI／输入链路，再从真实
  V2 空初始化及 Base 样本验证 AC-1–6。Base 样本使用隔离工作副本、临时根和 fake／本地
  Provider；同一库换候选继续用，核对原 ID／digest／路径、发布与一次实际 Worker 效果。
- 执行 workflow shared full gates 的 Python／Web／Node E2E／质量／依赖／规范示例。
  需要样例替换时按候选已更新的实际命令执行；不能以删样例绕过门禁。
- `web/` 构建后运行：
  `npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts tests/e2e/manual-organize-dialog.python.spec.ts tests/e2e/organize-source-history.python.spec.ts tests/e2e/task-flow.python.spec.ts`；
  用独立实例运行
  `npm run test:e2e -- --config=playwright.python.automation.config.ts tests/e2e/automation-settings.python.spec.ts tests/e2e/automation-lifecycle.python.spec.ts tests/e2e/automation-run-once.python.spec.ts`。
  核对当前身份、设置采用、原摘要确认／四类恢复与兄弟非重放。
- 仓库根运行 `.venv/bin/python scripts/storage_settings_browser_proof.py`，验证真实管理启动、
  首个 Draft、空 Active 和来源返回。在同一现有 Python/API 浏览器入口补本单元的规则
  目标普通编辑／高级配置成功、错误与未知核对旅程，检查实际桌面／390px／矮窗口截图；
  不恢复旧独立编辑页或建设通用探测框架。
- 干净精确候选构建 wheel，按 shared gates 做源码外安装和当前 consumers；同候选镜像跑
  `scripts/docker_empty_baseline_smoke_test.py --image <candidate-image>`、
  `scripts/docker_smoke_test.py --image <candidate-image>`、
  `scripts/docker_release_security_smoke_test.py --image <candidate-image>`、
  `scripts/docker_restart_fault_smoke_test.py --image <candidate-image>`（均用 `.venv/bin/python`）。
  证明管理启动、实际发布／采用、媒体操作和重启后的原工作；不触碰用户部署。
- 记录实际命令、计数／失败／跳过、精确候选和包／镜像身份，证据存稳定忽略目录。
  前一 Task 全量不是本 Task 可执行改动的通过结果；按 workflow 的输入一致性规则复用。

### Non-goals 与全部 Slice 结果重评

| Slice 结果 | 本轮核对与边界 |
|---|---|
| RO-1 | Task55.1 已接受的 Web 入口退出保持；本 Task 仅调整配置／规则内指定转换表面。 |
| RO-2 | 55.2／55.3 已接受的 schedules／grant／票据／非内核整理退出保持。全局审核和剩余 manual-* 传输表面仍在，后续独立完整单元处理；当前手工整理和四类恢复服务保留。 |
| RO-3 | 本 Task 交付配置运行权威／身份／新旧输入／默认 runner 收敛；必须用本 Task 验收证明，当前仍未完成。领域旧 Task 模型等与 flow／schema 耦合部分留在相应单元。 |
| RO-4 | 55.3 的专属旧链结构退出保持。全局 schema 升级／重建、五态与 paused 字段清理不在本 Task；本 Task 不重设 schema 身份、不改原数据／digest。 |
| RO-5 | 本 Task 清理配置／事件／分类转换消费者。Run once／Copy／Settings 缺 baselineValues 等 session 和其他协议适配仍在；仅因本 Task 触达页面不能扩大为全站 session 改造。 |
| RO-6 | 同步本 Task 的样例／生成／安装／部署／说明；其他单元和 Slice 最终全交付物门禁未完成，不提交 Closure Packet，不提前声明 CURRENT／完全退役。 |

不新增 API 版本、权限／容量键、身份系统、配置／恢复引擎、Provider／Storage、默认业务
对象、通用迁移工具或新设置平台；不改 accepted Slice、Roadmap 边界，不推送或发布。
Task PASS 后 B 重评全部 RO，仍有必需缺口才规划下一单元；满足即交 A。

### Developer Completion Report

由 Developer 实施后填：精确候选 SHA、READY FOR B REVIEW、实际改动／删除与保留
理由、affected commands／结果、已知失败和剩余风险。B 全量验收仍由 B 执行。

### B Review Result

尚无 Task55.4 产品候选；本轮仅激活正式 Task，未给本 Task 产品 PASS／FIX REQUIRED。
后续独立审查完整 Base..Head，按上述 AC 给出结论；产品返工留在同一 Task。
Task55.3 PASS 保持。Slice55 Required Outcomes 尚未全部满足，下一步为 Developer 实施。

草案规划核验（6463cee9）：治理 PASS；`tests.test_governance` 20 tests OK，6.531秒；TASK 本地链接及
`git diff --check` 通过；仅 TASK 改动。已有入口验证0.784秒，合计测试不足10秒，
小于本轮规划耗时50%。这些是规划检查，不是 Task55.4 的产品 T4 验收。
