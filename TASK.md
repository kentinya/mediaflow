# Task55.2 — 自动化只依赖当前定义、发布意图与 Task

Next Action: DEVELOPER STARTS TASK55.2 IMPLEMENTATION。

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
Status: PLANNED
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

尚未实施，无本 Task 候选和 PASS／FIX REQUIRED。Developer 按模板报告精确 SHA、
READY FOR B REVIEW、行为／关键决定、受影响测试实际结果／剩余项。B 随后独立审查
完整 Base..Head，给 PASS 或同 Task FIX REQUIRED；PASS 后重评全部 Slice 结果。

本轮规划检查：治理与 whitespace PASS；仅 TASK.md 变化，2项现有测试通过（0.161秒），
连同 CLI help 和文档检查不足1秒，低于本轮代码／合同核对及规划总耗时的50%。
未运行产品全量／原生／Docker门禁，未将规划检查记为产品验收。
