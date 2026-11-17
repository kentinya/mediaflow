# Task55.4 — 唯一当前配置：管理启动、发布与运行消费

Task55.3 已由 B 独立验收 **PASS**；完整接受范围
`b73c36353e5427cbe60fbb7c1b8cc85b139edca4..78d3e252090ca13149bf953b803eeb37918d9b30`。
原计划、B55.3-01–05 修正、实际门禁、失败／跳过和复用限制保留于
[64006c8d:TASK.md](https://github.com/kentinya/mediaflow/blob/64006c8d3b0a2791e5228417420250a064c75cea/TASK.md)。
Task55.1／55.2 的接受事实保持。Slice55 仍 ACTIVE，尚未满足全部结果。

用户现明确要求“激活Task吧”，据此将已规划的 Task55.4 激活为正式实施 Task。
Goal／Scope／Task Base／High／T4／验收与测试分工保持原计划。
Next Action: **DEVELOPER FINISHES TASK55.4 B55.4-05 CURRENT CONSUMER ASSERTION**。
本轮仅激活 TASK；SLICE／Roadmap／Progress 保持原合同和接受身份。

Authority: committed [Slice55](SLICE.md) RO-3，以及本单元相关 RO-5／6、AC-03／05／07／08／11／12。
生命周期和测试分工以 [Development Workflow](docs/development-workflow.md) 为准；
实施前读 [Developer 指南](docs/agent-experience/developer-implementation-role.md)。

```text
Task ID: 55.4
Task Type: SLICE
Parent Slice: 55
Status: FIX REQUIRED
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

```text
Task: 55.4
Candidate: 7962432a5aefbe8af9940b6d30eb9d7a6281e2d7
Range: 64a8f69e..7962432a (implementation); this report commit follows
Status: READY FOR B REVIEW
```

**实际改动／删除与保留理由**

- **启动与权威：** `final_cli._configuration` 不再在无 managed Active 时回落完整
  `load_runtime_configuration`；无 Active 只保留明确的
  `RuntimeSnapshotUnavailable(active_missing)`，API／四个常驻服务仍使用
  management-only bootstrap，合法 pinned revision 仍按原 ID／digest 读取。
  `configuration_snapshot.status_document` 不再产生 `JSON_BOOTSTRAP`；无 managed 激活时
  统一显示 `MANAGEMENT_BOOTSTRAP`、`setupRequired`、`runtimeConfigured=false`。
- **身份：** `RuntimeConfiguration`／`ManagementBootstrapConfiguration`、
  `MediaFlowApi`、`_ConfiguredPermissionAuthority` 和
  `_CurrentConfiguredPermissionAuthority` 删除 legacy-admin／单 bearer 回落；
  `api.tokenEnv` 在新输入、bootstrap 与 managed 文档中均被明确拒绝，
  `api.principals[*].tokenEnv` 环境引用保留。`bind_deployment_authority` 不再把单 token
  与 principals 视为等价，只接受精确 principal 身份。
- **新输入收敛：** 新增 `domain/configuration_input.py`，在现有 import／edit／validate／
  activate、typed Save／对象测试和 `config validate` 边界拒绝纯废弃写法：顶层 Storage
  连接字段、ResourceLibrary.rootPath、automation.taskDefinitions／schedules／
  staleJobAgeSeconds、notifications.webhooks、MetadataPolicy.mediaType、
  OrganizePolicy.overwrite、旧命名模板、分类 library/category/subcategory／扁平形状及
  job.* Webhook 事件。与当前字段混用同样拒绝；只有相对 baseline 完全未改变的历史对象可
  随无关编辑保留，原 Active／digest／pin 不重写。
- **分类目标：** 编辑投影把历史 `library` 前缀折叠进完整 `path`，普通保存即发布当前
  MediaLibrary＋path 表达且目标不变；删除旧前缀提示／“移除旧版前缀”迁移按钮。后端 typed
  Save 不再接受 library/category/subcategory，旧 Active 的运行时目标语义仍由 domain 保留。
- **事件与默认装配：** `NotificationEventType` 删除 JOB_* 与 job.* 解析别名；新 Webhook
  只接受 task.*／schedule.emitted。删除 `strategy-test` console 注册、`mediaflow/cli.py`
  独立 parser／runner／默认策略和 `RecognitionTypePolicyRegistry`；保留当前 `mediaflow`
  入口、`analyze`、规则对象测试／规划、C→A 身份及共享引擎。已持久化旧 job.* 投递行仅在
  `sqlite_runtime` 读取时做窄的历史映射，新配置不再接受。
- **消费者：** 两份规范示例改为根级 Webhooks、task.*、无 overwrite、分类前缀折叠；
  部署生成器只输出 management bootstrap 或经
  `--configuration-output`／`--configuration` 产出的规范配置输入；Docker/harness 的配置
  文件与激活输入分离，实际运行仍通过 import／validate／activate 发布业务配置。
  README／deployment 文案同步本单元行为。

**验证命令与实际结果**

- `.venv/bin/python -m unittest discover -s tests`：`Ran 2371 tests ... OK (skipped=7)`，
  263–268 秒；覆盖本轮全部 affected 组及既有回归。
- `.venv/bin/python -m unittest tests.test_management_setup tests.test_configuration_snapshot
  tests.test_api_security tests.test_configuration_management
  tests.test_configuration_package_exchange` 等 Task 指定 affected 组：通过。
- Web：`npm run typecheck` 通过；指定五个测试文件
  `124 passed`；改动文件 ESLint／Prettier 通过。
- `.venv/bin/ruff check <changed-python-files>` 与
  `.venv/bin/ruff format --check <changed-python-files>`：通过（121 files formatted）。
- `python3 scripts/check_governance.py`：PASS；`git diff --check` 通过。
- `config/strategy.example.json config validate`、
  `config/mediaflow.phase13.2.example.json config validate`：均成功。
- 现有入口探测：legacy `api.tokenEnv`、分类 `result.library`、`job.completed` 三项
  `config validate` 均 exit 2 并给出字段级拒绝；最小 bootstrap `config status` 返回
  `authority=MANAGEMENT_BOOTSTRAP, runtimeConfigured=false, workflowAvailable=false,
  setupRequired=true, active=null, bootstrapMode=MANAGEMENT_ONLY`。

**已知失败／跳过与剩余风险**

- Docker／wheel／浏览器 E2E 门禁未由 Developer 执行；按工作流由 B 在精确候选上运行。
- `scripts/docker_upgrade_recovery_smoke_test.py` 仍保留跨版本旧 schedule fixture，本 Task
  未运行该脚本；它不属于本轮启动／身份／输入收敛的验证范围，B 需按适用性决定。
- `sqlite_runtime` 对已持久化 `job.*` 投递记录保留只读历史映射，仅为保留原 ID／payload／
  状态／效果，不提供新配置别名或生产。
- `docs/architecture.md` 的 CURRENT `JSON_BOOTSTRAP` 段落未提前改为 TARGET；按 Task
  “不把整个 Slice TARGET 提前改 CURRENT”的边界，留待 Slice 接受时协调。
- 未推送、未发布、未改动用户数据库／媒体／秘密。

### B Review Result — 2062f7f4 再审

**FIX REQUIRED，仍为 Task55.4；B55.4-04 修正通过，B55.4-05 尚未完整通过。**
完整审查范围 `64006c8d3b0a2791e5228417420250a064c75cea..2062f7f4bebd6241e46e073e2651d2f64f1d5708`，
139个文件；实现候选 `60aced5eedd4ddccf2b60d830bdd1a43843ca79e`，之后只有 TASK 报告。
main，复核前 tracked／untracked 工作区干净，治理 PASS。固定 Base／Goal／High／T4 保持。
上一轮结论、原失败和指导保留于
[323f5918:TASK.md](https://github.com/kentinya/mediaflow/blob/323f59184917550019751f2961fef545c77240ee/TASK.md)。

#### 已验证的交付结果

- B55.4-01–03：真实 Base 首次草稿在候选继续 checked activate 成功；原 Active／后继
  草稿可读／可校验，storage list 正常。生成器 portable 输入修正保持。
- B55.4-04：B 以 Task Base 实际 CLI 建立 Active，候选经原规则 GET／PUT 只改分类 A
  描述，返回200；真实 Python 浏览器 Save 同样200并关闭编辑卡。已检查 desktop／
  390px／矮窗口画面；原路径继续完整显示。新增 parse_classification_policy 复用
  runtime 的同一领域读取，新输入仍受现有提交边界约束。
- Task Base 与 Slice Base 均有真实受理／继续使用证明：Base CLI 发布配置，Base Files
  API 保存 C→A 选择并受理分析；候选发布后继配置、继续原分析、读取精确计划并明确确认，
  由真实 Worker 各完成一次 MOVE。原 pin／digest／revision 文档保留，C 仍为 C，目标为
  原 `Movies/Movies/Anime/Alpha Movie…`，一次 SUCCESS／verified_complete。再次 Worker
  run-next 无待处理工作，Result ID、目标字节和 mtime 不变，无重放。
  Slice Base 的 V2 样本未配置本来就已退出的 schedules 产品；原未绑定 Task 的分析通过
  现有同请求核对入口接回原 discovery／pin 后继续，符合55.3已接受行为。最初包含旧
  schedules 的示例样本被准确拒绝，该结果不作为稳定 V2 回归。
- 新输入拒绝、权限／精确发布／并发／原 pins 等由本候选全量与直接旅程共同核对。
  没有用户配置、用户库／媒体或外部 Provider 参与；Provider 为本地 fake。

#### B55.4-05 剩余交付：原生路径断言仍期待已退出的表达

**实测和用户结果：** 当前真实 Worker 结果显示
`媒体库 movies，相对路径 Movies/Anime；规则 japanese-animation 命中…`，原最终目标
保持。`web/tests/e2e/operations-inventory.python.spec.ts:1190` 仍精确期待相对路径
`Anime`，因此原生门禁在真实整理已经完成后失败。当前规范把原 library 前缀纳入 path；
这个消费者尚未跟随本 Task 的示例／投影变化。

**Developer 开发指导：** 将该既有断言接到当前规范 fixture 明确的 `Movies/Anime`，
保留识别、命名、最终完整目标、导出和重启读回的断言。运行这个直接受影响的既有旅程：

```sh
# cwd: web/
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts --grep "a real Manual Organize Worker run keeps its reviewed plan"
npx eslint tests/e2e/operations-inventory.python.spec.ts
npx prettier --check tests/e2e/operations-inventory.python.spec.ts
```

交同一 Task 的 coherent checkpoint／READY FOR B REVIEW。当前未要求新的领域行为、
新探测工具或全仓回归；B 按输入一致性核对可复用证据并完成余下验收。

#### B 实际验证、失败定位与后续责任

证据根 `.git/validation-evidence/2062f7f4/task55-4-b/`；各 JSON 含实际命令／区间／退出码，
完整日志、截图、trace、wheel 和同源 archive 保留。报告中的通过、失败和复用分别记录。

- 新候选 Python 全量：**2385 tests OK，7 skipped，294.597秒**。Ruff format／check、
  compileall、pip check、两份规范示例 config validate、治理／whitespace 通过。
- Web source／lockfile／单元测试／Node fake 与299d6e25无差异（完整差异证明在
  `web-evidence-reuse.json`）；复用 B 的 **103 files／1636 tests**、typecheck／lint／
  format 和 **Node E2E 285 passed**。当前重新构建前端通过。Python 原生夹具变化部分
  均重新执行，没有复用其旧结果。
- 两组原生命令：Files／手工整理／Task 组 **57 passed、2 failed**；一处为上述路径
  断言，另一处为跨 spec 共用实例的固定 Task 总数假设。Automation 组 **46 passed、
  1 failed**，失败在满额拒绝用例把前序 Copy 已有的两个目标当成此次新增效果。
  同候选独立实例只跑完整 Settings spec **18 passed**，真实共享容量／拒绝无新效果成立。
  原失败日志与 trace 均保留；不把这些旧状态假设表述为新业务效果。
- B 后续须用明确初态核对跨 spec 的计数／文件状态，并保留零新增效果、已有成功结果
  不丢失的断言。另一次独立 Operations 重复在共享 fixture 状态上扩大失败，B 已中止，
  记录为 exit130／未完成；这次重复不计为通过，也未增加产品返工项。
- 精确 HEAD archive 的 wheel 构建和 `scripts/wheel_smoke_test.py <wheel>` 源码外安装／
  consumers 通过；同源 Docker 构建通过。artifact 身份在 `artifact-identities.json`。
- 同候选 `docker_smoke_test.py` 与 `docker_restart_fault_smoke_test.py` **通过**。
  前者验证四服务与 API 重启；后者验证真实发布／定义 Task、Worker／Scheduler 重启、
  逐项证据／未知通知与原效果保留。
- empty-baseline：B 用仓库当前 Settings 浏览器旅程替代旧按钮词的验收接线，真实四服务
  健康、首 Draft→精确版本 checked activate→空 Active 成功，零媒体 Task／投递，token
  未持久化。随后旧 media-free fixture 声明未挂载的 `/media/incoming`，发布准确拒绝。
  B 后续负责准备存在的隔离测试根并继续该门禁。
- release-security：镜像扫描／非 root／挂载／当前静态资源通过；旧 smoke 在首次 Active
  之前要求退休 POST /tasks 返回404，实际为无 Active 的503。该脚本的普通配置前提需由
  B 调整：保留无 Active 鉴权／零效果检查，在激活后核对退休入口404；当前未记整项 PASS。
  两项 Docker 验收接线问题不转成新的业务开发要求。

**结论：B55.4-01–04 的业务修正通过；05 还剩上述当前断言同步，完整 T4 尚未完成。**
Developer 只处理明确的当前消费者改动；初态隔离和余下矩阵由 B 继续，不转交全量测试。
测试／构建合并墙钟小于本轮50%，实际计时见 `review-timing.json`。

**全部 Slice 结果重评：** RO-1 及55.2／55.3已接受部分保持。RO-3 的本单元配置核心
已经上述真实入口核对，RO-5／6 的本单元消费者／完整验收仍待05完成；原后续 RO-2
全局审核／manual-*、RO-3 其余领域模型、RO-4 schema／五态、RO-5 其余 session／协议及
RO-6 最终交付物门禁保持原边界。Slice55仍 ACTIVE，55.1–55.3 PASS 保持；不新建 Task，
不提交 Closure Packet，不改 Slice／Roadmap／Progress。

### Developer Fix Report — 2026-11-17（B55.4-01–03）

```text
Task: 55.4
Fix Candidate: f6ab37c82be6f0dea5022b50997db7cdcaf7c348
Range: cbf930ed..f6ab37c8 (fix implementation); this report commit follows
Task Base: 64006c8d3b0a2791e5228417420250a064c75cea
Status: READY FOR B REVIEW
```

**根因与实际修正**

- **B55.4-01 — 已保存首次设置草稿：** 根因是 `validate`／`activate` 用
  `_base_document`（仅 `base_active_revision_id`）判断提交格式；首次草稿没有基线，
  已被接受的服务器生成字节被当成“无基线的全新输入”。现 `_accepted_baseline` 对已
  持久化的 revision 使用其自身不可变字节作为已接受基线：新输入仍只在 import／edit
  边界按当前格式判断，读取／校验／激活不重写原文档、ID、digest 或审计关系。
- **B55.4-02 — 已接受通知阻断读取：** 根因是 loader 的 `WebhookDefinition.from_document`
  对新输入与旧 Active／pin 共用一个严格枚举解析。现 `domain/notification.py` 提供单一
  读取映射 `accepted_notification_event_type`／`accepted_webhook_definition`（job.* 对应
  同一 Task 生命周期事件，重复别名收敛为一次），由 managed runtime loader、Webhook
  投影、Webhook 测试与已持久化投递行共用；新配置输入、typed Save 与变更对象仍由
  `reject_retired_configuration_input` 拒绝 job.*。`_reject_webhook_events` 也按对象
  比较：baseline 中已接受且未改动的定义可继续携带，改动对象必须使用当前事件名。
  原 revision 文档／digest、通知 ID／payload／投递状态与嵌套拼写保持原字节。
- **B55.4-03 — 生成的配置无法导入：** 根因是生成器把示例的 `local-admin` 身份写进
  配置输入，与生成的 `admin` bootstrap 冲突。`make_deployment_configuration` 现在输出
  与 managed export 相同的 portable 文档：不含 `persistence` 与 `api.principals`，导入时
  由接收 bootstrap 绑定自身 locator／principal，部署身份检查保持不变；默认及
  `--token-env` 输出都可直接成对使用。`scripts/docker_smoke_test.py` 删除夹具中替
  生成器覆盖身份的做法，并把 `http_request` 返回的 bytes 先解析为 JSON 再读取
  `revisionId`／`version`／`status`；断言保留。`docs/deployment.md` 同步该行为。

**实际验证（最终候选；仓库根目录）**

- **B55.4-01 真实 Base 样本：** 用 `64006c8d` 源码（`git archive`）创建真实首次
  Draft（无 base Active、嵌套空 Webhook 节），候选在同一隔离库上 validate →
  `validated`、无错误；activate → `active`；revision ID／digest／document 相同，
  `authority=MANAGED, runtimeConfigured=true, emptyActive=true, setupRequired=false`。
  原始脚本与结果：`.git/validation-evidence/f6ab37c8/task55-4-fixes/`
  `base_create.py`、`candidate_first_draft.py`、`*-first-draft.json`。
- **B55.4-02 真实 Base 样本：** 用 `64006c8d` CLI 在隔离目录执行规范示例
  validate／draft-import／draft-validate／activate，并建立后继 Draft（通知为
  `job.*`）。候选对同一库：`config status` 为 `MANAGED, runtimeConfigured=true,
  workflowAvailable=true`；`storage list` 正常列出 2 个 Storage（exit 0）；后继 Draft
  validate 为 `validated`、无错误；无关 `operationalLogging` 保存成功并再次校验通过；
  pin 读取得到原 Storage 与 Webhook，事件读取为对应 task.* 语义，持久化字节仍是
  原 `job.completed/failed/cancelled, schedule.emitted`。证据
  `base-example-candidate.json`、`base-example-cli.txt`。
- **B55.4-03 生成器成对输出：** 真实运行
  `scripts/make_deployment_config.py --output ... --configuration-output ...`，分别用
  默认与 `--token-env CUSTOM_ADMIN_TOKEN`；只把 bootstrap 的 `databasePath` 指向隔离
  库（配置输入不含 locator，无需修改），直接经 `config draft-import --file` →
  `config draft-validate` → `config activate`，两组均 exit 0 且 Active。证据
  `generated-pair.json`。
- **新增／修改回归：** `.venv/bin/python -m unittest` 上述 Task 指定四组 affected
  模块，另加 `tests.test_v2_notification_operations`、`tests.test_webhook_url_security`
  → **470 tests OK，0 skipped，测试报告18.955秒／命令墙钟19.167秒**；日志
  `.git/validation-evidence/f6ab37c8/task55-4-fixes/focused-tests.log`。新增用例：
  Base 形态首次草稿继续激活、已接受嵌套 `job.*` 通知的运行时读取与“未改动可携带／
  改动须当前名”、快照草稿继续发布、历史 Webhook 投影为可读定义、生成器成对输出可
  直接导入。原“新 job.* 输入拒绝”断言保留并通过。
- `.venv/bin/ruff check`／`ruff format --check`（全部改动 Python 文件）：PASS
  （`configuration_input.py` 原有格式漂移随本次格式化收敛）。
  `python3 scripts/check_governance.py` PASS；`git diff --check` PASS；两份规范样例
  `config validate` 均成功。

**已知失败／跳过与剩余风险**

- Docker／wheel／浏览器原生 E2E 未由 Developer 运行；按工作流由 B 在
  `f6ab37c8` 上执行。本轮未运行 Docker 脚本，只修正其消费者接线。
- 已接受 Webhook 的普通字节可继续读取并向运行时交付；但经 typed 表单显式编辑该
  对象时，提交内容必须采用当前事件名（拒绝信息已给出具体替换），这是本单元“新输入
  只用当前表达”的既定边界，不提供静默转换。
- `docs/architecture.md` 的 CURRENT `JSON_BOOTSTRAP` 段落仍未提前改为 TARGET；
  按 Task 边界留待 Slice 接受时协调。
- 未推送、未发布、未改动用户数据库／媒体／私密配置；B55.4-01 单元用例中的“已接受
  revision”通过 repository 持久化模拟旧版本留下的不可变行，真实 Base 代码样本另在
  上述隔离证据中验证。

**计时：** 本轮约 20:02–20:24（Asia/Shanghai，约22分钟）；产品测试与真实入口探测
墙钟合计约 1 分 10 秒（约 5%），小于本轮 30%。

下一步：B 独立审查 `64006c8d..本报告候选`，重跑三条失败旅程并按其 T4 验收计划给出
PASS 或 SAME TASK FIX REQUIRED；不规划下一 Task。

### Developer Fix Report — 2026-11-17（B55.4-04／05）

```text
Task: 55.4
Fix Candidate: 60aced5eedd4ddccf2b60d830bdd1a43843ca79e
Range: 323f5918..60aced5e (B55.4-04／05 implementation); this report commit follows
Task Base: 64006c8d3b0a2791e5228417420250a064c75cea
Status: READY FOR B REVIEW
```

**根因与实际修正**

- **B55.4-04 — 已接受规则无法参与共享检查：** 根因未放宽新输入。共享 checked
  Save 的整图读取 `_policy_resolution_catalog → _organize_policy` 与
  `_resolve_destination → _classification_policy` 之前调用只适用于新输入的
  `_normalize`，因此把原已接受规则的 `overwrite`／`library` 当作新提交字段拒绝。
  现两处读取改用与 runtime loader 相同的领域读取职责：
  `parse_organize_policy` 和新增的 `parse_classification_policy`。后者由现有
  `load_strategy_configuration` 的同一 `_classification_rule` 实现，并复用于 runtime
  loader，避免出现第二套分类读取。新输入边界未改：typed Save／对象分析仍经
  `_normalize`，import／edit／validate／activate 仍经
  `reject_retired_configuration_input`，单独及与当前字段混用的 `overwrite`／`library`
  继续拒绝。原 revision 字节、ID、digest 和原分类目标均未重写。
- **B55.4-05 — 当前夹具未同步：** `scripts/operations_inventory_harness.py` 改为从根级
  `webhooks` 启用示例定义；覆盖 fixture 只用 `conflictStrategy=overwrite`，不再写入
  已退出的 `overwrite`。同一根因下另同步两个现有当前消费者：
  `scripts/docker_empty_baseline_smoke_test.py` 的 successor 配置改为根级 Webhook；
  `scripts/notifications_workspace_browser_proof.py` 从根级示例生成其 proof Webhook。
  未新增探测框架或旧格式转换。
- **直接受影响用例：** 在 `tests.test_v2_rules_workspace_commands` 增加两个 Base 形态
  accepted Active 样本：无 `overwrite` 样本和保留分类 B `library` 的样本。均只编辑
  分类 A 的普通名称／描述并复制 A，断言 checked 发布成功、A 完整目标不变、B 原文档
  逐字节不变、原 Active revision/digest/document 保留。另在
  `tests.test_classification_destination_contract`、`tests.test_configuration_organize`、
  `tests.test_configuration_destination_precheck` 增加 accepted 读取成功／新输入继续
  拒绝的直接断言。

**实际验证（最终候选；仓库根目录）**

- `.venv/bin/python -m unittest` Task 指定四组 affected 模块及其现有相邻模块：
  **438 tests OK，0 skipped，测试报告 19.542 秒／命令墙钟 19.81 秒**；日志
  `.git/validation-evidence/task55-4-fixes2/final-affected-groups.log`，四组分别的
  原始日志为同目录 `group1.log`–`group4.log`。
- **真实 Base 样本：** 用 `64006c8d` 源码创建真实 Active，保留原
  `organizePolicies[*].overwrite=false`、分类 B `library="TV Shows"`／`path=["Series"]`
  和 `job.*` Webhook 事件。候选在同一库上经现有 typed 编辑打开并保存分类 A 的普通
  描述，再复制 A；两次 checked 发布均成功。前后目标均为
  `Movies/Action/The Matrix (1999) [tmdbid-synthetic]/The Matrix (1999).mkv`；B 文档
  未转换；原 revision 字节／digest 保留；用该原 revision 单独经
  `load_managed_runtime_configuration` 读取仍得到原 Storage、合法 legacy 分类 B 和
  对应 task.* 事件。证据 `.git/validation-evidence/task55-4-fixes2/base-sample/`
  （`base-create.json`、`candidate-continue.json` 及两个实际脚本）。
- **B55.4-05 真实入口：** 直接启动 `scripts/operations_inventory_harness.py` 于
  4199 端口，轮询 `/ui-v2/` 返回 200，日志确认 seed 完成且无启动异常；未运行完整
  Playwright 业务旅程。`notifications_workspace_browser_proof.build_configuration`
  的实际生成文档通过新输入边界并包含 `proof-webhook`。Docker 脚本只做上述消费者
  接线修正，未执行 Docker。
- 两份规范样例 `mediaflow --config … config validate` 均成功。
- 改动 Python 文件 `.venv/bin/ruff check`／`ruff format --check`／`py_compile`
  全部 PASS；`python3 scripts/check_governance.py` PASS；`git diff --check` PASS。

**已知失败／跳过与剩余风险**

- Developer 未运行 Docker、wheel、浏览器 E2E 或全量 Python/Web 套件；按工作流由 B
  在 `60aced5e` 上执行 T4。Docker 与 notifications proof 的消费者接线已同步，但
  尚无本候选上的 Docker／浏览器实际通过证据。
- 真实 Base 样本验证了原 revision 可独立重载，未在样本中创建新的在途 Task pin；
  B 仍需按 T4 在 Base 样本上核对原工作 pin 和一次实际 Worker 效果。
- 新输入中的 `overwrite`／`library` 及混合写法继续由现有边界拒绝；accepted 读取
  只对未改动对象生效，不提供静默转换。
- 未推送、未发布、未改动用户数据库／媒体／私密配置。

**计时：** 本轮约 21:17–21:35（Asia/Shanghai，约 18 分钟）；产品测试、真实入口
探测与静态检查墙钟合计约 50 秒（约 5%），小于本轮 30%。

下一步：B 独立审查 `64006c8d..本报告候选`，重跑 B55.4-04 的两个真实样本及
B55.4-05 两组原生业务旅程，并按 T4 验收计划给出 PASS 或 SAME TASK FIX REQUIRED；
不规划下一 Task。
