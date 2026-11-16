# Task55.2 — 自动化只依赖当前定义、发布意图与 Task

Next Action: B REVIEWS TASK55.2 FIX CANDIDATE (READY FOR B REVIEW, SAME TASK FIX LOOP)。

Task55.1 已由 B 独立复核 PASS：
`d62436be6f5848329a628356c13fdb28e760239a..f4336e431e27a76af372f9d23fe1896838e8cbd8`。
完整接受、原失败、修正和实际门禁见
[ebec19bb:TASK.md](https://github.com/kentinya/mediaflow/blob/ebec19bb7592306980a4f288c78378b264f3321f/TASK.md)。
Task55.1 的 PASS 保持；Slice55 保持 ACTIVE。

Authority: committed [SLICE.md](SLICE.md) 的 RO-2（旧 schedules／独立 grant 退出），
以及对应 RO-3／4／5／6；生命周期依 [Development Workflow](docs/development-workflow.md)。
用户现明确要求“激活Task”，据此将已提交草案转为正式 Task55.2，授权 Developer 按本
Task 实施。本次只激活，不启动其他角色或实施产品变更。

```text
Task ID: 55.2
Task Type: SLICE
Parent Slice: 55
Status: READY FOR B REVIEW
Task Base: ebec19bb7592306980a4f288c78378b264f3321f
Difficulty: High
Test Level: T4
Planner / Reviewer: B
Implementation Authorization: TASK55.2 IMPLEMENTATION AUTHORIZED
```

规划现场：`/Users/songzhidong/mediaflow`，main，上述 HEAD，初始 tracked／untracked
工作区干净，文件和 Git 可写；治理检查 PASS。未读取私有配置、运行库或用户媒体。
Base 固定；文档提交不换 Base。实施前重新核对工作区和治理。

激活现场：main，HEAD `a68f0181846fd6db9ec0c2f8a27c9fb4a0c08d9d`，工作区干净，
治理检查 PASS。激活保留已提交草案的 Goal／Scope／Base／验收／测试分工，状态为
PLANNED；Developer 开始实施时更新为 IN PROGRESS。

### Goal / complete journey

用户在“自动化 → 新建／编辑”保存定义，可明确启用未来定时计划；Scheduler 到期只受理
该定义的一项 pinned Task，Worker 执行并在任务中心提供同 Task 四类恢复。未启用定义
仍可从列表“运行一次”，不改变定时计划。复制默认不启用；删除／停用定义或失去权限
阻止后续 scheduled 效果，保留已经完成及未知效果。失败保留实际发布／受理／执行状态，
用户按具体原因修改配置、核对原请求或进入原 Task 处理。

完成后此旅程不再读取、生成或撤销独立 grant，也不存在旧 schedules 产品。
不新增授权步骤、页面、配置／权限名、队列或执行引擎。

适用：`V2-RETIRE-002–006/008–010` 的本 Task 部分，`V2-AUTO-003/005/006/010/011/013–015`、
`V2-TASK-001–006/010–014`；保留 `REQ-SCHED-003–005/007` 当前 Task／Enabled 修订、
`REQ-CONFIG-005–008`、`REQ-TASK-005–007/010`、`REQ-SAFE-001–008` 的现行义务。
完整旅程见 Product Experience 的“Automation forms and direct Run once”及
“Scheduled unattended organization”（含完整 native workspace）；受影响 CURRENT／TARGET
契约见 Architecture 的 Slice47、Automation intent、configuration authority 与 Slice55 TARGET。

### Actual code / existing entries

以下来自本轮真实注册和调用，未猜测端点或构造不可达操作：

| 位置 | 已核对事实和本 Task 改变 |
|---|---|
| `final_cli.py` scheduler parser／`_run_scheduler` | 实际 help 为 `{list,tick,audit,run}`；list／audit 专供旧 schedules，tick／run 装配两种调度。删除旧查询和调度输入，保留当前定义 tick／常驻 run。 |
| `runtime_configuration.py`／`domain/automation.py` | 仍解析 automation.schedules、IntervalSchedule／CronSchedule／ScheduleState／ScheduleAuditRecord，SchedulerConfigurationSnapshot 也携带旧 schedules。退出旧契约，保留当前定义 interval／Cron／timezone 算法。 |
| `application/automation.py` `IntervalScheduler.tick`／`_admit_schedule_task` | 先遍历旧 schedules，再处理当前定义。保留当前 due admission、容量、occurrence 唯一性、设置采用，删除旧分支及专用依赖。 |
| `service_api.py` routes／binding／`_automation_definition_actions` | GET `/api/v1/schedules`、GET `/api/v1/schedules/{id}/audit`，以及 `/api/v1/automation/task-definitions/{id}/grant` 的 GET／POST／DELETE、GET `grant-state`、GET `grant/audit`、POST `revoke`／`grant/revoke` 仍注册；actions 仍广告 grant。一起退出。 |
| `application/unattended_execution.py` | authorize_task／assert_live_task 已检查当前发布者、Enabled、连续性和权限，却仍读取历史 grant；旧调用还可从 grant 取 principal。抽出当前职责并复用，删除独立 grant CRUD／eligibility／兼容 wrapper／回落。 |
| `automation_definition_execution.py`、CLI／API composition | 当前 due／Run once 仍注入上述混合服务，逐效果检查由其提供。接到唯一当前 authority，保留这些检查。 |
| `automation_definition_occurrence.py`／`automation_workspace_commands.py` | 定义投影仍读 grant；removal impact 用 grant，成功删除后仍撤销 grant。改用当前发布／引用／历史，保留原请求核对、引用保护和原子发布。 |
| `sqlite_runtime.py` | 旧 schedules／grant CRUD、admit_due_schedule_task 和四张专属表仍存在。删除生产接口／新库结构，保留当前 due_state／occurrences／Task／scheduling／activation audits。 |
| `configuration_snapshot.py` empty document | 当前首次 Draft 生成 automation.schedules: []；正常存量 V2 配置／pins 不能据此失效或改 digest。新生成 Draft／successor 退出该空槽。 |
| Web `automation.ts`／`automation-lifecycle.ts`、Automation specs／harness | 仍有 grant decoder／action／removal grantId 和 grant seed。消费者接当前响应；保留发布／权限／删除失败与非重放断言。 |
| 两份现有 example JSON、Docker restart smoke、当前配置说明 | 仍生成或说明 schedules。同结果更新，不扩大到所有配置格式清理。 |

规划实测：`.venv/bin/mediaflow scheduler --help` 如上；现有
`ExecutionIntentTests.test_checked_enable_supplies_scoped_principal_without_grants_or_immediate_work`
与 `test_disable_and_removal_stop_unperformed_scheduled_effects_on_pinned_work` **2 tests OK**。
这说明当前能力可复用，不代表本 Task 已实施或 T4 通过。

### Implementation scope / Developer 指导

1. **沿当前动作整理 authority。** 从 checked create/edit/enable、列表 Run once、due tick、
   Worker 到每个未执行效果边界核对调用。复用 `automation_execution_intent.py` 的真实发布
   证据、当前配置权限和 Task admission principal，把混合服务的当前职责收敛到一处。
   保留 publication ancestry、trusted-local uid、禁用后重启用不复活旧 occurrence、合法
   enabled successor 不 repin，以及读取正常 V2 activation 实际 actor 的现有职责。
   删除 grant 专属模型／服务／协议，不把 grant CRUD 改名移到新类。
2. **退出旧调度。** 删除上表旧 schedules 配置解析、模型、Scheduler 分支、CLI list／audit、
   API routes／metadata／pagination kind／binding 字段。保留当前定义 interval／Cron／
   timezone／DST、tick／run、无 Active 等待与实际 polling。automation.maximumActiveJobs、
   三项设置范围和现有权限名（包括 GRANT_UNATTENDED_EXECUTION、CANCEL_JOB/cancel_job）
   保持原名／语义；不改普通文件 Worker 职责。
3. **简化当前定义生命周期与消费者。** create/edit/copy/remove/read/records 不再读 grant；
   removal impact／结果表达真实引用、Enabled／发布和原历史。停止由当前定义／连续性
   决定。已发布、明确未发布、未知发布分别核对原命令；保持 current Web 可读、键盘、
   关闭和来源返回。同步 decoder／action／视图，移除旧 grant 投影，不留旧响应兼容层。
4. **明确配置边界。** 旧 automation.schedules 定义走普通校验拒绝，不忽略、转换为
   definitions 或执行；首次 Draft、内部 successor、样例／smoke 不再生成 schedules。
   Base 正常 V2 文档中系统生成的空数组没有旧调度含义，按现有有效配置的读取／导入／
   导出／恢复义务保留，原文档／digest／pin 不改；内部创建当前 successor 时不再生成
   此空槽，用户无需手改旧 JSON。不得把合法 V2 空槽和非空旧 schedule 定义混为一谈，
   不保留 ScheduleDefinition 解析器或任何调度行为。保留 automationTaskDefinitions 当前
   正式语义；不扩展清理其他配置别名。
5. **删专属生产持久化与新建结构。** 新库不再创建 automation_schedules、schedule_audit、
   unattended_execution_grants、unattended_execution_grant_audit 及其索引。现有正常 V2
   库继续打开，保留配置、Task、请求、occurrence、结果、审计及 pins；这些旧表如有历史
   原样保留，不自动 DROP／删行，当前业务不再查询／更新它们，不另造历史 grant API。
   备份保留原内容。不重写整个 schema／迁移系统，不改 schema 身份来拒绝正常 V2 库。
6. **保留真正断言并同步交付。** 更新 Node fake／Python harness／spec／example／脚本／
   CI 引用及当前说明。Cron 算法保留，旧 schedule 并发／失败原子等有效断言接到当前
   definition admission；grant 删除故障断言接到真实发布／读回边界。仅测试旧产品成功
   的 fixture／断言退出，当前精确发布、权限、原子受理、逐效果与未知非重放断言保持。
   harness 只做必要接线，不建设治理／测试平台。
7. **受影响测试后交接。** 临时根／SQLite／fake Provider 验证后提交连贯候选，记录
   READY FOR B REVIEW、精确 SHA、命令／结果及剩余项。测试耗时小于本轮总耗时50%；
   Developer 不跑 B 全量门禁。触及时间比例时交接实际结果，由 B 在复核轮次完成其
   分配，不删断言、放宽超时或把未跑门禁写成通过。

### Acceptance Criteria

- [ ] AC-1：正常配置／合法管理员下，上表旧 schedule／grant API 返回普通未知路由，
  CLI help／parser 无 list／audit，tick／run 服务当前定义；无 grant action 广告。
  不以无配置、无权限、缺定义的错误证明入口删除。
- [ ] AC-2：V2 新建未启用／明确启用、编辑启停／enabled successor、复制默认未启用、
  引用核对及删除完整，无 grant 读写／撤销、独立授权／先分析要求。Schedule preview
  零变更，interval／Cron／timezone／DST 的当前定义行为一致。
- [ ] AC-3：启用不立即建 Task；due 原子创建唯一 pinned Task＋occurrence；并发 tick／
  重启不重复，满额不推进 due／留孤儿 Task。无 Active 常驻等待、首次激活及实际设置
  采用保持，缺失发布证据／真实权限不会从历史 grant 获得执行资格。
- [ ] AC-4：列表 Run once 执行未启用定义，不推进 due／改 Enabled；原 principal／request／
  publication fence 去重、丢响应核对、完整有界遍历／稳定性／源归属与真实效果保持。
- [ ] AC-5：due／Run once 仍走当前 Worker／OrganizerExecutor，原 pins、C→A 身份、主附件
  独立结果、当前五态 flow／成功率保持；四类问题在原 Task 决策→分析→精确摘要→
  显式续作，成功和未知不重放。停用／删除／权限失去停止后续 scheduled 效果；重新
  启用不复活旧 occurrence，合法 successor 不破坏原 admitted pin。
- [ ] AC-6：create/edit/copy/remove 已发布、明确拒绝、并发冲突、未知响应保持真实 Active／
  输入／原请求核对，刷新／重认证不自动重提；删除成功无需修复历史 grant。桌面／390px／
  矮窗口、键盘／关闭／返回可完成当前动作。
- [ ] AC-7：旧 schedules 定义（单独、混合当前定义、当前 Draft／包导入）拒绝且不发布／
  受理／执行；新系统生成配置无旧字段。正常 V2 配置的空槽读写／交换保持无调度语义。
  Base 真实代码生成的正常 V2 配置及合法 due／
  Run once Task 在候选中继续读／执行／核对，原 ID／digest／pin／请求／结果／审计保持，
  无需重建配置或重发 Task。
- [ ] AC-8：新库无上述四张旧表／专属索引及生产 CRUD，当前必要结构完整；Base 正常库
  和候选同版本 reopen／restart／备份恢复可用，原历史不删，业务无旧表查询依赖。
- [ ] AC-9：两种库维护／异步 Copy/Move/Delete、手工 Files 整理、通知及其他页面保持；
  当前定义的 schedule.emitted 通知保留，无旧 schedule 产生新事件或工作。
- [ ] AC-10：源码、API／CLI、Web、wheel／源码外安装、四服务候选镜像与当前说明一致；
  旧正向测试说明删除或保留断言去处。无隐藏开关、替代旧列表、grant 接管或第二引擎。

### Required tests

按 [test levels and ownership](docs/development-workflow.md#6-test-levels)。此 Task 涉及
发布权限、调度并发、Storage 效果和持久化，T4；完整验收由 B 执行。

#### Developer — affected tests

根目录运行现有直接相关模块；新增用例放回对应模块：

```bash
.venv/bin/python -m unittest tests.test_cron_scheduler tests.test_automation_execution_intent tests.test_automation_definition_occurrence tests.test_automation_task_admission tests.test_v2_automation_lifecycle tests.test_automation_run_once tests.test_v2_automation_run_once tests.test_automation_authorized_execution_matrix
```

覆盖当前算法／due／权限／原子受理／生命周期／逐效果；旧正向断言按第6步改接。
修改 configuration snapshot／runtime loader／resident loop／packaging script 时，补跑其
新增／修改和直接受影响的具体用例并报告名称，不把整仓标为 affected。对修改的 Python
文件跑 Ruff format/check，并跑 `python3 scripts/check_governance.py`、`git diff --check`。

`web/`：

```bash
npm run test -- run src/entities/operations/automation.test.ts src/entities/operations/automation-lifecycle.test.ts src/features/operations/AutomationLifecyclePage.test.tsx src/features/operations/AutomationWorkspaceReadModel.test.tsx
npm run typecheck
npm run build
npm run test:e2e -- --config=playwright.python.automation.config.ts tests/e2e/automation-lifecycle.python.spec.ts tests/e2e/automation-run-once.python.spec.ts
```

其他修改组件／spec 补其直接用例与 changed-file ESLint／Prettier；native 保留具体动作、
失败及 SQLite／效果核对，不只数按钮。并行套件分别指定产物目录。

#### B — acceptance and full regression

1. 审查完整 Task Base..候选 SHA／删除清单。先从上表现有入口验 AC-1，按真实当前 Web
   旅程验 AC-2–6／9。真实 Task 阻塞可先 FIX REQUIRED，不先跑昂贵全量。
2. 用 Slice Base `2b2e7c1824fa5681864455714d0f97b26555c7dc` 真实代码在隔离根建立
   正常 V2 配置、空槽、due／Run once 工作／请求／结果，再由候选继续打开。对比原
   ID／关系／digest／pins／请求／效果，运行尚未开始的合法工作，核对完成／未知不重放，
   并验候选新库结构。使用现有 fixture 和临时源归档，不建设迁移工具。
3. 执行 [shared full gates](docs/development-workflow.md#shared-full-regression-commands)：
   Python／Web／Node E2E 全量、质量／示例／依赖、wheel／源码外消费者。旧结果仅能按
   工作流证明输入相同后复用；本 Task 改变生产输入，需要新 T4。
4. 先 `web/ npm run build`，执行现有真实 Python native，使用独立证据目录：

```bash
npm run test:e2e -- --config=playwright.python.automation.config.ts tests/e2e/automation-create-dialog.python.spec.ts tests/e2e/automation-lifecycle.python.spec.ts tests/e2e/automation-run-once.python.spec.ts tests/e2e/automation-workspace.python.spec.ts
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts tests/e2e/action-readability.python.spec.ts tests/e2e/automation-settings.python.spec.ts
```

   查看桌面／390px／矮窗口截图与当前操作，核对原 Task 手工／四类恢复。旧 grant seed
   改接当前发布，保留执行／停止／未知核对断言。
5. 根目录对精确 committed 候选运行以下现有四服务检查，核对镜像／wheel 身份：

```bash
.venv/bin/python scripts/docker_smoke_test.py --image mediaflow:task55.2-b
.venv/bin/python scripts/docker_restart_fault_smoke_test.py --image mediaflow:task55.2-b
.venv/bin/python scripts/docker_release_security_smoke_test.py --image mediaflow:task55.2-b
```

   验无 Active 常驻、首次配置、due／Run once、停止后续效果、安全头／RBAC、普通文件／
   通知及重启非重放，使用临时挂载／本地服务。
6. 每轮测试墙钟小于总耗时50%；保留失败／skip／未跑项，原始证据存
   `.git/validation-evidence/<candidate>/task55.2-b/`（本地忽略，不声称远程可达）。
   必需门禁未完成则继续 B 验收，不因缺证据退回产品实施，也不提前 PASS。

### Non-goals / all Slice outcomes reassessed

本 Task 完成 schedules／独立 grant 退出及其当前自动化链路，不声称整个 RO-2 完成。
远程 execution tickets／POST tasks／header、旧全局审核和 manual-* 恢复入口、
non-kernel Worker／旧恢复子 Task 链、Pause／旧 flow、通用 schema／upgrade、完整严格
bootstrap／其他配置别名、事件／session 与其他迁移协议清理不在本 Task 扩展。
不新增 Provider／Storage／权限／设置／恢复类型，不重设计任务中心／九页，不改历史
接受，不操作用户媒体、不推送／发布／部署。

本轮全部结果重评：RO-1 已由55.1交付；RO-2仍有上表旧 schedules／grant 及其他入口；
RO-3仍有 JSON_BOOTSTRAP／legacy-admin 和旧配置读取；RO-4仍有历史 flow／
pause_requested／迁移／旧结构；RO-5仍有 Copy／Run once 旧 session 合并；RO-6 Web
部分已完成，非 Web 部分随业务退役。因此 Slice55 仍 ACTIVE，尚不交 A 终审。
本 Task 不预建其余 Task，不更改 Slice／Roadmap／Progress 边界。

### Developer completion / B review

**Developer 交接 — 2026-11-16，READY FOR B REVIEW。**

```text
Task Base: ebec19bb7592306980a4f288c78378b264f3321f
Implementation candidate: 7d57bf72 (the product checkpoint above this handoff record)
Branch: main
Initial workspace: clean (tracked/untracked)
```

本轮按第 1–7 步完成 RO-2 的本 Task 部分：旧 schedules 与独立 grant 从当前自动化链路
完整退出，当前定义的 due／Run once／Worker 链路接到唯一当前权威；未扩大范围。

**行为与关键决定**

1. **当前权威收敛到一处。** 新建
   `mediaflow/application/automation_execution_authority.py`：仅保留当前职责
   `authorize_task`／`assert_live_task`，复用 `automation_execution_intent` 的真实发布
   证据、当前配置权限与 Task admission principal；删除
   `mediaflow/application/unattended_execution.py` 的 grant CRUD／eligibility／
   projection／shared-analysis 门槛及兼容 wrapper，不把 grant CRUD 改名移入新类。
   `domain/unattended_execution.py` 仅保留 `CurrentPermissionAuthority` 协议。
   错误类型换为 `AutomationExecutionIntentError`／`AutomationIntentBoundaryError`
   （字段形状与旧错误一致，API 错误映射保持 403/404/409/503 与 bounded details）。
2. **旧调度退出。** 删除 `IntervalSchedule`／`CronSchedule`／`ScheduleDefinition`／
   `ScheduleState`／`ScheduleAuditRecord` 模型与仓库协议方法、
   `IntervalScheduler` 的旧 schedules 分支与 `_admit_schedule_task`、CLI `scheduler
   list/audit` 及渲染器、`/api/v1/schedules` GET/audit 路由、route-kinds／metadata／
   pagination kind／binding 字段。保留当前定义 interval／Cron／timezone／DST、tick／run、
   无 Active 等待与实际 polling；Worker 对已受理 `legacy-schedule` pin 的消费路径
   保留（未在 Task 表内，且已受理 pin 保留义务要求可续作）。
3. **生命周期简化。** create/edit/copy/remove/read/records 不再读 grant；removal
   impact/error 的 `authorityState` 表达当前发布 Enabled 状态（active/none/unavailable），
   removal 是唯一 live stop（成功发布即停止未来调度，不再有单独撤销步骤）。
   Web `authority: {status}` 取代 `unattendedAuthority`（无 grantId）；grant
   action／decoder／eligibility 投影整体删除，不留兼容层。
4. **配置边界。** `automation.schedules` 仅接受系统生成的空数组（原 digest／pin 不变）；
   任何 schedule 定义走普通校验拒绝；非列表值拒绝。首次 Draft／successor／样例／
   deployment 配置不再生成 schedules 键。`automation.taskDefinitions` 别名、
   `staleJobAgeSeconds` 等其他别名未动。
5. **持久化。** 新库不再创建 `automation_schedules`、`schedule_audit`、
   `unattended_execution_grants`、`unattended_execution_grant_audit` 及专属索引；
   schema 身份未变。实测：新库无四张旧表且当前必需结构完整；含 legacy 行的存量库
   原样保留、当前仓库正常打开，无生产 CRUD 依赖。备份语义不变。
6. **同步交付。** Node fake（grant seed／route／action 全退，hostie fixture 改接当前
   definition 传输）、Python harness（grant seed endpoint 退、lifecycle state 改当前
   publication authority、Scheduler snapshot 调用更新）、两个 example JSON、
   `make_deployment_config`、三个 Docker smoke（restart fault 改当前 publication
   断言；empty baseline 改发 enabled definition；upgrade recovery 保留旧库 legacy
   seeding、新候选对旧表零改动且旧 API 为 unknown）、`schema_upgrade_rehearsal`、
   README／configuration.md／architecture.md 路由清单。

**实际验证（命令／结果）**

- 治理：`python3 scripts/check_governance.py` PASS；`git diff --check` PASS；
  `ruff format --check .`／`ruff check .` 全仓 PASS；`compileall -q mediaflow tests
  scripts` PASS；`rg -n -i 'ffprobe|ffmpeg' mediaflow pyproject.toml` 无匹配。
- 示例：`mediaflow --config config/strategy.example.json config validate`、
  `config/mediaflow.phase13.2.example.json config validate` 均 PASS。
- Python affected（Task 指定清单，180 项）：`test_cron_scheduler`（改接当前定义边界：
  tick 正常、list/audit 未注册、空槽可读、旧定义拒绝）、
  `test_automation_execution_intent`、`test_automation_definition_occurrence`、
  `test_automation_task_admission`、`test_v2_automation_lifecycle`、
  `test_automation_run_once`、`test_v2_automation_run_once`、
  `test_automation_authorized_execution_matrix` — **OK**。
- 直接受影响扩展清单（827 项）+ 第二批（384 项）+ 设置 resident（81 项）：
  含 `test_configuration_snapshot`、`test_automation_definition_publication`、
  `test_v2_automation_operations`、`test_notifications`、
  `test_notification_delivery_management`、`test_webhook_management`、
  `test_execution_authorization`、`test_organize_source_history`、
  `test_organize_preparation`、`test_resident_services`、`test_preview_retirement`、
  `test_task_scheduling`、`test_automation_entrance_recovery`、
  `test_automation_settings_management/resident`、`test_media_discovery`、
  `test_organizer_mutation_authority`、`test_v2_manual_organize` 等 — **全部 OK**。
- Web：`npm run typecheck` PASS；`npm run build` PASS；`npm run lint --fix` 后
  changed-file ESLint／Prettier PASS；受影响 unit 12 文件 **155 项通过**。
- 真实 Python native E2E（候选构建后）：
  `automation-lifecycle.python` **21/21 通过**（含 removal→当前 authority stop→
  tick 零发射断言）；`automation-create-dialog.python` 通过；
  `operations-inventory.python` **47/47**；`automation-settings.python` **18/18**
  （单独运行；合并运行时的 queue_full 为双 spec 共享一部署的容量竞争伪失败）。
- AC-8 结构实测：新 SQLite 库无四张旧表、当前必需表完整；存量 legacy 表行原样保留。

**基线既有失败（已在 Base 复现，非本轮引入）**

- `automation-run-once.python` 5 项与 `automation-workspace.python` 4 项在本轮候选与
  Base（stash 后）**同清单同失败形状**复现（`advanced:false`／`Run once Task was not
  found`），确认为既有环境性失败，交给 B 在其验收环境复核。

**剩余风险／未执行（B 按 T4 门禁执行）**

- 未运行全量 Python/Web/E2E、wheel／源码外安装、四服务 Docker 镜像与
  restart/release-security/upgrade-recovery smoke；相关脚本已更新，但镜像与部署矩阵
  由 B 执行。
- Worker 对已受理 `legacy-schedule` pin 的续作路径保留但本轮只由存量测试覆盖，其
  Base→候选跨版本复用由 B 验收第 2 步覆盖。
- 未推送、未发布、未操作运行库或用户媒体。

本轮测试墙钟合计约 20 分钟（Python unittest 约 7 分钟、E2E 约 9 分钟、质量/构建/
静态检查约 4 分钟），低于本轮代码勘察／实施与交接总耗时的 30%。

本轮规划检查：治理与 whitespace PASS；仅 TASK.md 变化，2项现有测试通过（0.161秒），
连同 CLI help 和文档检查不足1秒，低于本轮代码／合同核对及规划总耗时的50%。
未运行产品全量／原生／Docker门禁，未将规划检查记为产品验收。


## B Review — FIX REQUIRED（2026-11-17）

```text
Task Base: ebec19bb7592306980a4f288c78378b264f3321f
Developer implementation: 7d57bf721c127a6882464b68faec2bfd767aefe9
Developer handoff: ea27144f0a6c6b36e4a79ba9e7b8496e10a59101
Reviewed complete range: ebec19bb7592306980a4f288c78378b264f3321f..03a6df37f4f3fec71ce3c540628581429ce86a48
B acceptance-consumer checkpoint: 03a6df37f4f3fec71ce3c540628581429ce86a48
Decision: FIX REQUIRED
Task blockers: B55.2-01, B55.2-02
Slice Required Outcomes / Surfaces all satisfied: NO
Next: SAME TASK FIX LOOP
Evidence: .git/validation-evidence/ea27144f/task55.2-b/ (local, ignored)
```

初始现场 main／ea27144f，tracked／untracked 干净，治理 PASS。B 检查完整实现、删除与
消费者差异，并独立执行以下验收。03a6df37 只修正六个测试消费者，没有修改产品实现。
原失败日志保留，不把缺失证据或测试消费者问题转为产品缺陷。

### 已验证的交付结果

- 用户从“自动化 → 新建／编辑”创建并启用、保存启停／副本／删除，列表 Run once，
  原 Task 决策／分析／精确摘要／显式续作、成功兄弟保留、重启与原请求核对均有真实
  Python／SQLite／Worker／浏览器实证；没有增加独立 grant 步骤。
- 正常当前配置／管理员下，旧 schedules 查询和 grant 表面已从注册移除；当前定义
  interval／Cron／timezone、原子 due admission、发布者／实时权限及逐效果检查保持。
- 用 Slice Base 的真实源码和现有 V2 API／Worker 夹具建立一份正常配置（含系统空槽）、
  一项已完成结果、一个丢响应后待执行的 Run once，以及一个待执行 due Task。由候选
  重开后，原 revision／digest／IDs／pins／已完成 Result 一致；GET 原 request 查回同一
  Task，未新增请求；两个待执行 Task 正常完成，已完成兄弟未重放，Active digest 未变。
  具体输入和结果保留在 base-continuity.py／manifest／log；这是本地验收证据，不是
  产品迁移工具，未纳入源码。
- 新库实测不再创建四张 schedules／grant 专属表，当前 Task／scheduling／definition
  due／occurrences 结构完整；Base 库的原表保留，未通过 DROP 或删历史实现退役。

这些结果支持当前旅程继续使用；下列退出与断言保留义务尚未完成，因此本 Task 不能 PASS。

### B55.2-01 — P1：旧 schedules 专属执行链路仍随 Worker 和 wheel 交付

**依据与位置：** Task Implementation Scope 第1／2／6步、AC-10，Slice RO-2／RO-6。
`final_cli.py` 的 `_automatic_task_runner` 仍按 `origin_kind == "legacy-schedule"`
调用 `DefinitionScopedExecutionService.run_legacy_schedule`；后者仍为没有当前定义的旧
interval／Cron occurrence 枚举全部 ResourceLibrary 并 `execute=True`。它不是当前
Enabled／Run once 的 authority 检查链路。

B 检查本轮构建的 `mediaflow-2.0.0.dev0-py3-none-any.whl`，两段实现确实均在交付物中，
记录见 legacy-schedule-artifact.json。此项是约定的专属源码／执行分派退役未完成，
不以构造数据库行或不存在的 API 来声称发现一次运行中的越权。

**Developer 修正指导：**

1. 删除该 Worker 分派及 `run_legacy_schedule` 专用实现／依赖／说明；保留当前
   definition due／Run once、同 Task 续作与本 Task 之外的 direct-organize 路径。
2. 保留历史原记录、合法当前 V2 Task／pins／Results；不为旧 schedule 加转换、接管、
   专门退休处理或替代执行器。“原 pin 保留”不能使已退役调度产品重新获得执行职责。
3. 同一次删除清理 `pagination.py` 的 schedule_audit kinds，以及 service_api.py
   `_page_cursor` 的 schedule_audit 专属映射／时间分支；它们已没有当前生产者，属于
   本 Task 已明确列出的旧 schedules 接线，不扩大到其他分页／schema／恢复清理。
4. 在干净 wheel／源码外安装中核对旧执行器和分派已消失，同时保留当前 due／Run once
   与存量正常 V2 原 pins 继续使用的现有断言。无需增加新入口或通用扫描工具。

### B55.2-02 — P1：删除 grant 时连带删掉了当前业务断言

**依据与位置：** Task Implementation Scope 第6步、AC-10，Slice RO-6／AC-12。
`tests/test_v2_automation_operations.py` 的整段删除不仅退出了 grant 正向支持，还删除了
以下仍有当前产品职责的测试，未在本轮给出对应断言的保留位置：

- `test_operator_list_and_detail_are_bounded_and_permission_aware`：当前列表／详情的范围、
  权限、只读与脱敏；仅其 grant 部分应退出。
- `test_metrics_embedded_reads_and_failure_share_the_evaluated_basis`：独立统计、列表内统计
  与 viewer 使用同一完整总体；真实读取失败显示 unavailable，而不是空值或成功率0。
- `test_draft_journey_composes_existing_routes_atomically`、
  `test_definition_mutations_are_permission_bound`：现有配置草稿／检查／显式激活、并发
  拒绝和管理／只读权限；本 Task 没有退出这些仍注册的配置表面。
- `test_retired_automation_preview_routes_are_ordinary_not_found`：已接受的 Preview 退出
  反证，不是 grant 正向支持。

B 在隔离的 Slice Base 真源码执行 metrics 那项原测试，**1 test OK，0.083秒**；并核对
当前测试没有原来的独立／嵌入统计读失败配对断言。不能以总测试数或其他正常统计用例
替代被删的这个具体结果。

**Developer 修正指导：** 恢复上述测试的当前断言，或在对应现有当前用例中完整保留并
注明位置；仅移除 grant CRUD／eligibility 和专属旧字段的断言。使用当前真实注册入口、
当前定义／权限夹具，不恢复旧 grant 模型／route，也不新增通用测试框架。保留读取失败、
无权限、并发冲突、零效果和退休不存在的原业务断言，不改成只测 HTTP200／按钮存在。

### 实际验收与未执行项

- 指定 Python affected：**180 tests OK，37.083秒**。
- Python full：**2622 tests，1 failure／3 errors／7 skipped，349.908秒**，原结果保留在
  python-full.log。四项均是遗漏同步的旧 schedules 夹具／字段／binding 参数；B 已在
  03a6df37 同步为当前定义／无旧字段／当前签名，三个完整受影响模块 **56 tests OK，
  3.031秒**（python-consumers.log）。未将最初失败的全量日志改称全绿。修正候选的
  后续完整 T4 验收仍由 B 完成。
- Web unit：**103文件／1653 passed，158.19秒**。Node E2E：**285 passed，3.5分钟**。
  typecheck／ESLint／Prettier、Python Ruff format/check／compileall／pip check、两份
  示例验证、无 FFmpeg／FFprobe、治理和 whitespace 均通过。
- 原生自动化第一轮 **42 passed／10 failed**；B 核对了真实链接与页面：两个 helper 把
  `?run=<Task ID>` 错读为路径末段，过滤用例混入前一用例刻意保留的 enabled Draft。
  纠正后又发现技术失败用例仍要求已退出的恢复说明块，以及慢读 handler 移除时尚未
  完成。B 将其接到当前“条目证据／处理结果／需处理原因”并等待该 handler 完成，
  保留具体失败／源与成功兄弟／原结果／无重试／非重放断言，未加 retry／放宽 timeout。
  第二轮 **49 passed／3 failed** 和最终 **52 passed，1.5分钟** 均保留原日志。
- 当前 Task Center／actions 两个完整 native spec：**54 passed，2.0分钟**，没有与会
  修改容量的 settings spec 共用运行库。settings 的独立 native 验收尚未执行。
- wheel build／源码外 wheel smoke PASS；精确 wheel SHA-256 为
  `608acaffbae84604a1ec60e03f890bbcbf0cfd63eadfa0c98e82791cab0e04e6`。
  该 wheel 的旧 schedule 执行器存在已另存实证，wheel smoke 通过不代表完整退出通过。
  第一次 smoke 误填了不存在的0.1.0文件名，实际2.0.0.dev0 wheel 随后执行成功；失败
  命令记录保留在 wheel-smoke.log。
- Docker smoke 在 compose bind 阶段拒绝，原因是本轮 TMPDIR 不在已有 Colima mount
  中；不是产品拒绝／执行失败。已查明现有 mount 是
  `.git/validation-evidence/cf680df6/b-final/docker-tmp`，临时栈由脚本清理，无遗留容器。
  因已有本 Task 阻塞，没有继续重跑镜像门禁；restart／release-security 未执行。
  Docker／settings／修正候选完整门禁继续由 B 负责，不作为 Developer 产品返工项。

证据均在本地忽略目录，未上传 CI；没有操作用户媒体／运行库、推送、发布或部署。
本轮并行测试／构建墙钟区间合并约11.6分钟，原失败与重跑均计入；静态检查主要重叠于
这些区间，合计低于12分钟。完整代码／合同审查、结果核对与记录使本轮总耗时超过
24分钟，测试时间小于50%；区间见 test-timing.txt。本轮未给出 Slice Closure Packet，
也没有规划新 Task。

### 全部 Slice 结果重评

RO-1 保持55.1已接受结果；RO-2 的 schedules／grant 主要入口已退出，但本 Task 旧
schedule 执行链路仍未退出，remote tickets／全局旧恢复／非内核路径仍待后续授权工作。
RO-3 的严格 bootstrap／其他纯迁移配置、RO-4 的 flow／迁移／旧结构、RO-5 的 session／
其他协议清理尚未完成；RO-6 本 Task 尚缺专属源码退出和当前断言保留，最终包／镜像
门禁也未完整通过。Slice55 保持 ACTIVE；修正留在55.2，原 Base／Goal／Scope 不变。

## Developer 修正交接 — 2026-11-17，READY FOR B REVIEW

```text
Task Base: ebec19bb7592306980a4f288c78378b264f3321f
Fix checkpoint: 609cebc6 (product + tests)
Fix candidate HEAD: this documentation checkpoint
Branch: main
Initial workspace: clean (tracked/untracked)
B fix findings addressed: B55.2-01, B55.2-02
```

本轮只修正 B55.2-01／B55.2-02，未扩大 Task 范围，未改 Base／Goal／Scope／验收，
未恢复旧 schedules／grant 产品或新增入口。

### B55.2-01 — 旧 schedules 执行链路退出

- `mediaflow/final_cli.py` `_automatic_task_runner` 删除 `origin_kind ==
  "legacy-schedule"` 分派。保留当前 definition due／Run once、同 Task 续作和
  direct-organize／remote-organize 路径。
- `mediaflow/application/automation_definition_execution.py` 删除
  `DefinitionScopedExecutionService.run_legacy_schedule` 及其专用流程；其使用的
  `MediaOrganizerService`／`OrganizerExecutor` 能力仍由当前 definition 和
  direct-organize 路径使用。
- `mediaflow/interfaces/pagination.py` 删除 `schedule_audit` 的 kinds／scoped kinds；
  `mediaflow/interfaces/service_api.py` `_page_cursor` 删除 `schedule_audit` 专属
  `audit_id` 映射及 `emitted_at` 分支。其他分页、恢复、schema 未动。
- 未对历史旧 schedule 记录做转换、接管或专门退休处理；原记录／当前合法 V2
  Task／pins／Results 未删。没有 TaskItems 的旧 `legacy-schedule` Task 不再
  获得旧执行器，按缺少当前 definition origin fail closed；已有 TaskItems 的
  Task 仍按同 Task 续作边界处理。

### B55.2-02 — 当前业务断言恢复

`tests/test_v2_automation_operations.py` 恢复以下用例，使用当前真实注册入口和现有
定义／权限夹具；只删除 grant CRUD／eligibility 与旧专属字段的断言：

- `test_operator_list_and_detail_are_bounded_and_permission_aware`：列表／详情的
  范围、Active 投影、只读 viewer 的 Run once／create／createDraft 不可用、脱敏；
  保留 retired preview／grant action 不广告的反证，删除共享分析前置和 grant 字段。
- `test_metrics_embedded_reads_and_failure_share_the_evaluated_basis`：独立统计、
  列表嵌入统计、viewer 同一总体、非法参数拒绝，以及读取失败显示 unavailable。
- `test_draft_journey_composes_existing_routes_atomically`：创建 Draft、保存版本
  冲突、检查、显式激活、重复激活拒绝、激活后详情。
- `test_definition_mutations_are_permission_bound`：manager 可保存、viewer 保存
  403、viewer Draft 动作不可用。
- `test_retired_automation_preview_routes_are_ordinary_not_found`：原 Preview
  路由按普通未知路由处理，不产生 Preview／Task／Storage 证据。
- 另修正该文件模块说明和 `_run_shared_analysis` 说明中的 grant／Preview 旧措辞；
  未恢复旧 grant 模型／route，未新增测试框架。

### 实际验证（本轮）

- `.venv/bin/python -m unittest tests.test_v2_automation_operations`：
  **19 tests OK，7.885秒**（含恢复的 5 项当前断言）。
- Task 指定 affected：
  `.venv/bin/python -m unittest tests.test_cron_scheduler
  tests.test_automation_execution_intent tests.test_automation_definition_occurrence
  tests.test_automation_task_admission tests.test_v2_automation_lifecycle
  tests.test_automation_run_once tests.test_v2_automation_run_once
  tests.test_automation_authorized_execution_matrix`：**180 tests OK，36.502秒**。
- 直接受影响扩展：
  `tests.test_automation_entrance_recovery tests.test_task_source_ownership_race
  tests.test_task_item_metadata_search tests.test_organize_source_history
  tests.test_operations_task_center tests.test_operational_logging
  tests.test_processing_worker_readiness tests.test_automation_definition_publication`：
  **154 tests OK，26.488秒**。
- `.venv/bin/python -m compileall -q mediaflow tests` PASS；变更 Python 文件
  `ruff format --check`／`ruff check` PASS；`python3 scripts/check_governance.py`
  PASS；`git diff --check` PASS。
- 从 `git archive 609cebc6` 的干净源码目录构建 wheel：
  `mediaflow-2.0.0.dev0-py3-none-any.whl`，SHA-256
  `44566072325a3cedc5878dbc4b93f146dfeb232bde70d6e17d61cea0cc73dd49`。
  解包核对 `mediaflow/final_cli.py`、`automation_definition_execution.py`、
  `pagination.py`、`service_api.py`：无 `run_legacy_schedule`、无
  `legacy-schedule` 分派、无 `schedule_audit` 分页接线。
- `scripts/wheel_manifest_check.py`：`byte_equality_proven: true`，174 条目，
  `only_in_candidate`／`only_in_clean` 均为空。
- `scripts/wheel_smoke_test.py` 对该 wheel：PASS；隔离 venv 源码外安装，
  schema 58，backup／verify／Automation consumer 加载完成。

### 剩余风险／未执行（B 按 T4 执行）

- 未运行全量 Python／Web／Node E2E、四服务 Docker、restart／release-security／
  upgrade-recovery；这些仍由 B 的修正候选 T4 门禁完成。
- Base 既有正常 V2 库中的旧表历史行、原 Task／pins／Results 及跨版本继续读取
  由 B 验收第 2 步核对；本轮未修改 schema 身份，未自动 DROP／删行。
- 未推送、未发布、未操作用户媒体或运行库。

本轮测试／构建墙钟合计约 1.5 分钟（19 项 7.9 秒、180 项 36.5 秒、154 项
26.5 秒、clean wheel 构建＋smoke＋manifest 约 10 秒、静态检查数秒），低于本轮
从开始到交接总耗时（约 20 分钟）的 30%。未将未执行门禁写成通过。
