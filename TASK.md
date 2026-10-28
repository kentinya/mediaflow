# Task 46.5 — 自动化可用详情、启用即定时执行与真正运行一次

Authority: committed [Slice46](SLICE.md) **RO-5**、AC-9/11/12/13/17/18；衔接已验收
RO-2/RO-4 所需的 AC-5/8/14/15/16。[Development Workflow](docs/development-workflow.md)
是生命周期与测试分工的唯一依据；实施前阅读 [Developer experience](docs/agent-experience/developer-implementation-role.md)。

```text
Task ID: 46.5
Parent Slice: 46
Status: FIX REQUIRED
Task Base: 63c5c92e771054e30281617e2c652b7d5b486eb4
Difficulty: High
Test Level: T4
Planner / Reviewer: B
```

## Goal

用户从自动化列表的名称或“打开”进入已保存定义，能读到真实配置和执行就绪情况；在同一
编辑页保存后继续修改 Enabled、再次保存或直接启停，不因自己的成功保存产生假冲突。
启用代表允许按已保存范围定时执行，不再要求单独授权或先做授权预分析；点击“运行一次”
直接受理并执行该已保存范围的一次整理，不要求先选文件、生成摘要再确认一次。

完整旅程：自动化列表 → 详情/编辑 → 查看保存范围、上限及整理策略效果 → checked Save/
启用 → 正常到期产生一次工作，或显式运行一次 → 立即获得持久整理任务 → 后台发现、真实
稳定性检查与完整规划 → 就绪文件执行、四类业务问题进入任务中心恢复 → 查看逐项真实结果。
禁用仍可运行一次；该命令不启用定时或推进下次到期。失败说明阶段、持久状态、已知效果和
明确下一步；丢失响应先查本次请求，不盲目重发，四类恢复继续保留显式安全续作。

适用：`V2-AUTO-001–006/010/011`、`V2-OPS-014/016/017`、`UX-001–009`、
`REQ-SCHED-003–007`、`REQ-TASK-002/003/005–010`、`REQ-RECOVERY-004–009`、
`REQ-SAFE-001–009`、`REQ-API-002/003`。旧 separate-grant / Run once 先分析再确认的 V2
实现由 `V2-AUTO-010/011` 明确替代；Files 手动摘要/确认和四类决定/分析/续作不变。
完整适用旅程与边界见 [Product Experience](docs/product-experience.md#target--slice46-readable-actions-and-organizing-only-task-center)
及 [Architecture](docs/architecture.md#target--slice46-presentation-and-work-query-ownership) 的 TARGET
和下文 Automation CURRENT；当前 Task 不把 TARGET 写成已交付。

### Actual code gap and reuse

- `web/src/routes/router.tsx` 的现有定义详情是 `AutomationDetailPage`；其 typed model
  `entities/operations/automation.ts` 仍读取 grant/eligibility，后端
  `service_api.py::_automation_definition_operator_detail` 仍调用独立 grant eligibility。
  要完成真实读取链路，不能只让类型校验忽略所有坏数据或修补废弃授权预分析。
- 正常 focused Save/Edit 是 `AutomationLifecyclePage`，不是旧 Draft editor；其
  `saveMutation.onSuccess` 只 invalidates/navigates，保留的 `formEntry.authority` 没有同步
  本次成功发布结果，后续 Enabled 命令仍可能携带旧 Active 身份。复用现有 route-context、
  candidate fence、request identity/unknown reconciliation，不能普遍丢弃未保存输入。
- `automation_workspace_commands.py::save_object/set_enabled/_publish/remove_object` 已有
  focused successor、完整校验、checked activation、audit 和并发控制；当前 enabled 只改
  调度状态，remove 仍围绕 grant 撤销。`ConfigurationObjectService`、managed activate、
  API/configuration/本地 CLI 等同样可发布定义，必须共享意图/权限规则，不能只改 V2 按钮。
- `IntervalScheduler._tick_automation_definitions` 已按 Active/Enabled 发出固定快照的
  occurrence/Job；`DefinitionScopedExecutionService.run` 却在创建 Task 前要求独立 grant，
  `_run_scan_and_plan` 的逐变更检查也绑定 `assert_live`。复用现有 Job/Worker/Executor、
  current permission authority、scope ownership 和 Results，替换意图依据而不是删除检查。
- `AutomationRunOnceService.admit/finalize`、API 现有
  `/api/v1/operations/automation/task-definitions/{id}/run-once` 及
  `AutomationRunOncePage` 目前是 discovery → frozen analysis → 单独执行确认；POST 仅要求
  SUBMIT_DRY_RUN。复用已保存 definition/pin、有效上限、请求核对及真实执行链，改为一次命令
  的真实整理 admission；旧分析记录不因此获得执行权。
- `MediaOrganizerService.process_library` / `scan_filters.stability_wait_seconds` 已实现真实
  age/size 观测及无就绪文件时的单次短等待。`DefinitionScopedExecutionService` 已接入原子
  source ownership。保留这些能力；接通 Run once 后核对完整性、逐项业务恢复及最终汇总。

### All Slice outcomes reevaluated at planning

| Outcome | 当前状态与本 Task 责任 |
| --- | --- |
| RO-1 | Task46.1可读动作已验收；保留共享颜色/焦点/禁用/忙碌状态，新增动作使用现有组件 |
| RO-2 | Task46.3先受理/范围占用/任务内摘要确认已验收；本Task不改变Files手动确认 |
| RO-3 | Task46.2原库普通操作持久查看保留；既有菜单/non-localhost原生限制保留，不宣称已修复 |
| RO-4 | Task46.4 PASS：`63c5c92e:TASK.md`，产品76553772、测试3b101d55；八视图/四类/真实完成保留并接纳本Task真实自动化工作 |
| RO-5 | **未完成**；本Task交付完整自动化详情、保存/启停、执行意图、定时与真正Run once旅程 |

上一Task全量Python为2903 / OK / 7 skipped；其余匹配Web/native/package证据和限制见
`63c5c92e:TASK.md`。它们是前一候选的事实，不是本Task新执行/授权实现的验收通过证明。

## Implementation Scope

1. **统一显式执行意图与现有权限边界。**
   将 scheduled 的依据改为已 checked 发布的 Enabled 定义及明确的 enabled-successor Save；
   Run once 的依据是当前主体对该保存定义的一次显式命令。两者都绑定来源、scope、有效
   item limit、配置/definition pin、实际权限主体、审计及请求/工作身份，执行时仍使用后端
   实际计划。复用现有持久事实，禁止使用任意 actor 字符串或前端 flag 冒充授权。
   沿用现有权限：长期定时意图使用 `GRANT_UNATTENDED_EXECUTION` capability 加适用配置/
   激活权限（保留权限ID不等于保留独立grant流程）；Run once 必须具有现有
   `EXECUTE_MANUAL_ORGANIZE` 执行权限，纯 SUBMIT_DRY_RUN/READ 不能触发真实效果。
   API/Worker 的当前权限判定必须使用真实配置的主体，缺失/不可读 fail closed；CLI 保留
   其真实受信调用边界，不能由可伪造的 `--actor` 文本绕过远程权限。

2. **把检查放到所有实际 publication/admission 入口。**
   focused Save/enable、已有定义/对象管理、通用配置激活及受信 CLI 的相关入口共用检查。
   已启用 successor 的刻意 Save 需验证新的有效范围/效果与执行权限并审计；新建/copy仍关闭。
   unrelated publication 不得创建或静默扩大执行意图，未改变的合法范围不要求重复授权。
   已发布 enabled/no-grant 定义直接采用新语义，不要求旧grant、重分析或关开一次；从现有
   可信publication/配置证据明确其权限与范围来源，不补造管理员/用户授权。旧grant/revocation
   只留历史，不能成为额外门控、恢复 disabled 的权力或使旧失败重放。
   如确需持久化意图来源/请求关联，限定为兼容的必要新增字段/表，解释来源及事务边界，
   覆盖fresh/reopen/升级/失败原子性；不能再建一套授权产品、任务队列或执行引擎。

3. **完成详情与同页保存。**
   名称、“打开”和直接链接读取同一实际保存定义，含 disabled、unavailable、removed history；
   用有界 enabled/execution-readiness 取代独立grant预分析/按钮和独占读取依赖。其他有效字段
   的malformed、401/403/not-found/read error仍明确拒绝或显示错误，读取不启动工作。
   confirmed own Save/toggle 后以该命令实际发布结果更新同一表单的值及publication identity；
   保留 peer-change 的旧候选/冲突提示、输入和 exact unknown reconciliation。不得将一次
   refresh 当成对旧输入的重新授权，也不得在请求期间丢掉用户后来输入。显示启用范围/上限/
   策略效果；移除 grant/revoke/pending-authorization 文案和正常流程中的额外授权步骤。

4. **接通到期执行与逐变更检查。**
   Scheduler仍只负责正常到期 admission/idempotency；checked enable不立即创建Job/Task。
   Worker通过固定快照进入既有pipeline，不再读独立grant决定可执行。到期受理前以及每个
   尚未实施的变更边界重查当前权限与 scheduled Enabled/removed 状态；禁用/删除/权限丢失
   停止后续定时效果，不回滚完成项、不打断正在进行的Storage调用、不将旧工作repin。
   覆盖同一主文件之后的附件、冲突覆盖/cleanup等边界及scope continuation的合法上下文；
   live check不能只在HTTP或主文件前执行一次。重新启用不补跑旧失败或积攒禁用期间ticks。

5. **把现有 Run once 命令改为真实整理。**
   使用已有保存定义/观察到的revision fence和principal-scoped请求身份，prompt地原子受理
   真实整理工作，再交现有Worker发现/稳定性/分析/规划与执行；规则/元数据/目标尚未就绪
   不能阻止任务创建。正常首次执行没有文件选择、预分析或第二次摘要执行确认；现有后端
   plans/源证据/策略/效果校验仍完整执行。已disabled定义可运行一次，不用定时grant，不
   改Enabled/next due，不受仅针对scheduled的停用检查误拦；合法已受理工作保持自己的pin。
   受理后页面显示准确任务/结果链接，刷新/重连/重开不重发。重复请求和丢失响应按本次
   exact request读回；并发due/Run once/Files/恢复对同一真实源使用已有原子占用边界。
   Run once有效primary上限固定 `min(definition.itemLimit, 100)`；完整有界遍历/可读性/预算
   证明先于任何效果，overflow/incomplete不执行first-N。定时仍保留既有配置上限及明确
   bound-reached语义，不将达到上限说成scope已耗尽。healthy empty才no-work，失败不可伪装空。

6. **在任务内完成四类处理和真实统计。**
   就绪文件执行，识别/元数据/分类/冲突阻塞独立进入既有四类问题/计数/恢复链；Save决定、
   分析或排队不等于成功，后续恢复仍经精确摘要与显式安全续作。技术/权限/Storage/效果
   不确定错误保持事实历史而非第五类。Job/Task/Run once origin和恢复尝试准确关联；一次
   真实执行在Automation和中心各自统计中只算一次，纯分析和旧准备不变成执行历史。
   既有analysis-only/已受理旧工作、结果、pins和unknown请求保持可读，不自动升级执行。

7. **保留并验证稳定性合同。**
   age使用mtime距现在对比max(minimum-age, modified-threshold)；stable-size正间隔必须
   有相隔真实时长的未变化观测，不能凭旧mtime伪造。只有不稳定候选且没有ready时，最短
   剩余间隔在 `(0,60]` 秒才保留一次等待/复扫；已有ready直接处理，超过60秒不作同步等待。
   复扫稳定的文件可执行；剩余不稳定文件无效果且真实失败，仅此类失败为Failed，稳定成功
   加不稳定失败为PartialSuccess，不能no-work或四类Attention。后续普通到期/Run once仍走
   当前保存范围/筛选/真实稳定性，不新增选择旧失败、自动重试或跨run观测机制。Files不变。

8. **同步必要消费者和当前架构事实。**
   改 typed API/model、Automation列表/详情/编辑/Run once和真实harness的受影响组合；保留
   read-only执行记录、全局设置、normal调度统计及RO-1–4的入口/恢复语义。更新Architecture
   受影响的CURRENT/TARGET和必要面向用户说明，保留旧历史事实；不更改A-owned合同/路线。
   用新失败/成功/并发/边界用例替代过时“必须grant/第二次初始确认”前提，保留其原安全证明。

## Acceptance Criteria

- [ ] 名称/打开/direct detail在启用前后与保存后都显示真实保存配置；无独立grant依赖/控件，
      正常disabled可读，401/403/404/malformed/read failure有界且零工作/零媒体变更。
- [ ] 同页 Save→再改Enabled并Save、Save→直接启用/禁用、连续成功toggle可完成并持久读回；
      自身成功发布不假冲突，peer更改仍拒绝旧命令并保留输入，unknown先核对且不重放。
- [ ] 保存enabled successor和每个实际启用/发布入口验证执行+配置权限及有效范围/效果并审计；
      单纯读取/分析/无关publication/失效或无权命令不能创建/扩大意图，新建copy仍disabled。
- [ ] 当前已enabled且没有grant或旧grant已撤销的定义，在正常due可真实执行，无需off/on或
      预分析，无missing-grant失败；启用本身不启动工作，grant历史不覆盖Enabled及当前权限。
- [ ] 定时受理前及未实施效果边界的disable/remove/permission-loss竞争安全停止；附件与
      overwrite/cleanup不漏查；已有合法pins/结果/正在进行调用保留，无静默repin/回滚/重放。
- [ ] enabled/disabled定义的Run once一次点击即产生真实任务并执行ready文件；规则未就绪
      先受理再进入四类恢复，无文件picker或第二次初始确认，且不改变定时/next due。
- [ ] Run once保留保存范围/自动筛选及min(limit,100)；同名不同源不混淆，重复/unknown/
      并发trigger及重启核对准确，原子占用阻止重复执行且合格兄弟独立；overflow/incomplete/
      unreadable/permission故障不得first-N、伪装empty或成功。healthy empty有明确no-work。
- [ ] 自动化四类问题在八视图/Automation记录中可追踪并经原生Web恢复至实际结果，成功兄弟
      不重跑；mixed/ignored/technical/uncertain不会虚假全成功，旧Results/analysis不改写。
- [ ] 定时与Run once均证明真实age/size、一次短等待/复扫、ready避免等待、>60秒不等、
      zero duration/源变化/复扫后仍不稳定；真实Failed/PartialSuccess，无四类待办膨胀。
- [ ] current permissions、RBAC/redaction、Storage confinement/capabilities、C搭配A命名/
      A分类仍是C、执行/请求fences、成功/不确定非重放通过；Delete/Overwrite/cleanup仍需
      已有显式policy/effect intent，不因Enabled或Run once新增破坏性默认。
- [ ] 新实现的真实Worker/Scheduler、SQLite/API重开、已安装消费者及适用发布安全证明通过；
      desktop/narrow实际页面和键盘/busy/disabled可用。Developer受影响验证后交候选，最终
      T4由B负责；Task PASS后再核对全部Slice outcomes，满足即交A，不在本Task关闭Slice。

## Required Tests

按 [workflow §6](docs/development-workflow.md#6-test-levels) 分工。仅使用现有Web/API/CLI/
Scheduler/Worker入口、临时DB/媒体根和fake/local Provider；不猜造用户无法触发的入口，
不动用户配置/数据库/媒体。记录本轮测试/构建/探测墙钟时间及总用时，严格小于50%，不靠
等待填充分母；在预算内先核对Task实际交付和关键复现，不重复无关过程矩阵。

### Developer — affected tests

1. shared意图/publication/API权限：
   `.venv/bin/python -m unittest tests.test_automation_definition_publication tests.test_v2_automation_lifecycle tests.test_automation_task_definition`。
   扩展actual focused及generic/CLI入口，覆盖成功、非法输入、peer/stale/unknown、权限缺失、
   enabled-successor/旧enabled适配及关闭/删除，保存不带入siblings Draft；依据真实改动补
   直接受影响的config激活测试，不把全量suite当“受影响测试”。
2. 两条执行入口与原安全矩阵：
   `.venv/bin/python -m unittest tests.test_automation_definition_execution tests.test_automation_run_once tests.test_v2_automation_run_once tests.test_automation_authorized_execution_matrix tests.test_automation_definition_occurrence`。
   用当前Task语义修正旧grant/analysis前提；真实claim/Worker/Storage临时效果、effective bound、
   healthy empty/技术失败、四类/独立兄弟、live权限/disable及稳定性必须有直接证明。
3. 准入/源占用/续作与中心：
   `.venv/bin/python -m unittest tests.test_automation_admission tests.test_automation_job_fencing tests.test_scope_continuation tests.test_operations_task_center tests.test_task_center_recovery_lineage`。
   新增本Task实际并发入口用例，保留已有成功/不确定非重放、非整理排除、Files确认和源占用。
   若变更due算法或schema，分别补 `tests.test_cron_scheduler`、`tests.test_upgrade_preflight` /
   `tests.test_migration_rehearsal` 的实际受影响测试；不为本Task重写Scheduler或迁移工具。
4. `web/`：
   `npm run test -- run src/entities/operations/automation.test.ts src/entities/operations/automation-lifecycle.test.ts src/entities/operations/run-once.test.ts src/features/operations/AutomationLifecyclePage.test.tsx src/features/operations/AutomationRunOncePage.test.tsx src/features/operations/AutomationWorkspaceReadModel.test.tsx src/features/operations/AutomationRouter.test.tsx`。
   增加同页多次成功后操作、对等冲突/unknown、typed detail与直接运行一次读回测试；不能只
   mock一份自洽payload绕开真实Python契约。运行 `npm run typecheck`、`npm run lint` 和改动
   文件format检查；Python改动文件ruff/format、`git diff --check`及governance。
5. 改动生产资产后build，用现有真实Python入口执行关键native：
   `npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/automation-lifecycle.python.spec.ts --grep 'one checked Save|edit, enable'`；
   `npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/automation-run-once.python.spec.ts --grep 'disabled published definition runs once|successful sibling'`。
   在这些已有场景中补同页保存再启停及新的一次点击真实执行语义；从渲染控件发命令、实际
   Worker落结果，不以仅POST或Node fake代替。不得因旧断言失效而跳过整段安全/范围证明。

以上及本次确实修改/新增用例通过即可冻结完整候选并交READY FOR B REVIEW；全量Python/
Web/default E2E、完整native矩阵、wheel/Docker发布证明由B运行，不转交Developer。

### B — acceptance and full regression

B独立审查完整Task Base..Head，先从真实列表→详情→同页Save/Enabled、normal due和Run
once复现关键结果，再按 [shared full T4 gates](docs/development-workflow.md#shared-full-regression-commands)
运行全量Python/Web/static/default E2E及本Task安全矩阵，不只读取Developer PASS标签。

- 构建精确候选Web资产后，在 `web/` 分别干净启动运行以下完整real-Python specs（每个单独
  一次 `npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/<以下文件>`）：
  `automation-lifecycle.python.spec.ts`、`automation-run-once.python.spec.ts`、
  `automation-workspace.python.spec.ts`、`automation-settings.python.spec.ts`、
  `operations-inventory.python.spec.ts`、`operations-task-center-visual.python.spec.ts`。
  覆盖真实scheduled和Run once原生消费、四类恢复、只读历史、源占用/unknown/重开、全局
  settings的现有resident消费；实际查看desktop/narrow与键盘/焦点/disabled/busy状态。
  同时跑的Playwright用独立output目录，避免重现前轮产物目录竞争；不放宽timeout/加retry。
- 在真实current permission authority和两个repository/进程边界验证disable/remove/permission
  loss、due/Run once/Files/continuation竞争及主文件后附件边界；入口不得硬编码绕过授权。
  已enabled/no-grant、旧revoked grant及旧analysis/unknown记录均须在重开后验证新语义和
  retained history，不凭迁移标签或把Task布尔值当授权。稳定性fast覆盖加至少必要的真实
  elapsed原生证据，不等待60秒造覆盖；不重复大量同义sleep用例。
- 本Task改Worker授权/消费：必须fresh wheel + `scripts/wheel_smoke_test.py <exact-wheel>`，
  在源码外安装后验证本Task实际定义/到期及Run once消费者和快照/权限读回，并验证常驻
  Worker/Scheduler安全边界重开，不能只import模块。若有schema变更补当前升级/失败原子性。
- 发布安全采用现有 `docker build -t mediaflow:task46.5 .` 和
  `.venv/bin/python scripts/docker_release_security_smoke_test.py --image mediaflow:task46.5`；
  当前消费/权限变更所需容器重启/升级路径由B补现有证明，未提供环境明确pending，不能
  用上一Task只改read model时未跑Docker的理由豁免，也不要求Developer预跑发布矩阵。
- 最终保留候选SHA、实际命令/结果/skip和原始日志/资产身份；输入完全相同才按workflow
  复用B自己的证据。现有7个外部Storage/endurance环境skip及Task46.2菜单限制不隐藏，
  本Task造成的真实回归仍须在同一Task修复。没有未执行门禁的PASS声明。

## Non-goals

不新增Provider/文件命令/认证体系/全局授权管理产品，不重建queue/Scheduler/Worker supervision
或执行引擎；不恢复Scan/Preview/FileIndex、旧失败回收或兼容迁移产品。不添加失败项选择/
自动retry、跨run稳定性观察或新的等待生命周期。不改变Files手动初始摘要确认、普通操作
原库归属和四类恢复的显式安全续作。不做无关页面/翻译/全局设置/统计重设计、历史清理或
大规模重构，不改SLICE/Roadmap/Progress、不push，也不由B/Developer关闭Slice。

## Workspace and planning validation

Planning branch `main`；启动HEAD/Task Base `63c5c92e771054e30281617e2c652b7d5b486eb4`。
无pre-existing tracked dirty。原有untracked OS/private/log文件（`.DS_Store`、`.mgmt.log`、
`.t*.log`、`15`）、两张中文Automation参考图、`output/imagegen/slice45-task-center-v1.zip`
及各子目录OS文件全部保持原样/未暂存。只维护root TASK；源码、用户runtime DB/配置/媒体、
A-owned SLICE/Roadmap/Progress均未修改。写入和本地checkpoint验证workspace/Git可写。

规划只执行governance/document consistency和diff whitespace检查，未跑或声称产品测试通过。
已核对模板、已提交合同、完整适用Automation旅程/CURRENT与TARGET以及上述真实代码入口。
A-owned旧“首个Task”指针不代表当前交付状态；保留待A最终文档对账，不据此扩大/关闭Slice。

## Developer Completion Report

**READY FOR B REVIEW — 实施完成，未自行声明 Task PASS / Slice CLOSED。**

- Task Base：`63c5c92e771054e30281617e2c652b7d5b486eb4`。
- 本轮启动：`main / 90193491e2d006a1bb9f76d4201d0a769e44a561`。
- 产品/受影响测试 checkpoint：`8968a06c0765e57e48f00f99561fe3a7fbb13470`。
- 最终验证 checkpoint：`f18ca67617c70b2f48291b476fb799108232eef4`；相对产品 checkpoint
  只改真实浏览器 spec：键盘 Enter 启动、截图前复位滚动。Python/Web生产源码、单元测试、
  harness、依赖与资产未变；该 spec 的最终5项已重新运行。后续交接提交只改本报告。
- 启动已有四个 tracked 后端改动（definition execution、unattended execution、domain automation、
  sqlite runtime）已在同一 Task 内完成并验证后纳入产品 checkpoint；没有丢弃或静默重置。
  原始 patch 保留在 `.git/validation-evidence/task46.5-detail/preexisting-backend.patch`，sha256
  `58f5b45610d22db23cdb9a06357fbfbb5747d1da1a126782f6c04de227560ce7`。
  OS/private/log、`15`、两张中文参考图和 imagegen zip 均保留且未暂存；未动用户配置/DB/媒体、
  SLICE/Roadmap/Progress，未 push/发布。用户最新“忽略时间限制”替代此前30%测试时间约束。

### 已实施的最终行为

1. 普通列表/详情不依赖独立 grant；保存状态、执行就绪、Draft/removed/unavailable保留真实
   身份。confirmed Save/toggle推进同页发布身份并保留后续输入；peer冲突不重新授权旧候选。
   unknown Save/toggle持久保留主体/候选/action/base，按精确命令和实际激活审计只读核对。
2. focused/object/generic/CLI activation共用 Enabled execution intent 检查；激活审计与Active
   同事务记录实际主体、有效上下文摘要和本地信任来源。远程检查真实当前权限，不能由候选
   自授或任意 actor 冒充。无关管理发布沿用合法意图；已启用旧记录使用真实旧审计主体，
   不补造管理员。旧grant/revocation仅留历史，不再是执行门控。
3. Scheduler正常due前检查；启用本身零Job/Task。Worker固定pin并逐效果检查当前权限、
   Enabled/removed与激活继承链，覆盖附件/cleanup的既有Executor边界；经历停用的旧工作
   不因重启用复活。已完成兄弟/正在进行的Storage调用不回滚，合法enabled successor不repin。
4. Run once按保存定义、真实主体和exact request原子创建Pending整理Task+Job+origin，
   先受理再发现/规划/真实执行；禁用也可运行，不改due，不要求picker或第二次初始确认。
   并发请求、队列满、写失败、重开、Pending取消和已进入Task的claim恢复均保留安全边界。
   后者拒绝重新扫描/重放已完成或不确定效果。
5. Run once完整枚举先于任何效果：min(limit,100)，沿用条目/目录/分页/深度/时间/路径预算，
   失败、overflow、unsafe/duplicate entry、invalid/repeated cursor不得first-N或伪装empty。
   保留真实age/size观测及一次<=60秒等待/复扫；ready避免等待，超时不等，余下不稳定项
   真实Failed/PartialSuccess且不进入四类Attention。
6. 四类业务阻塞沿用Task Center；定义Task接通原有单项分析、精确源证据、摘要和显式续作。
   修正真实恢复plan身份与Storage相对根的一致性；保留成功兄弟Result。记录页按原始项及
   持久恢复关联计数，分析/准备不算成功，一个真实run不重复计数，技术兄弟仍失败时不全成功。
   历史analysis不自动升级执行；Files初始确认不变。CURRENT架构/旅程说明已同步。

### 实际验证与证据

本地稳定证据目录：`.git/validation-evidence/task46.5-completion/`；完整命令/cwd/输入与结果索引
见 `README.md`，源码/lockfile/资产sha256见 `candidate-identity.json`。这些是本机证据，未上传。

| 验证 | 实际最终结果 | 原始日志 |
| --- | --- | --- |
| Required Tests 中20个受影响Python模块，含新增intent、恢复/checkpoint、cron及升级迁移 | 501 / OK，无skip | `candidate-python.log` |
| 8个受影响Web实体/页面/恢复组件模块 | 93 / 93 | `web-final.log` |
| real-Python Run once：禁用直接执行、重启读回、冲突恢复、独立技术兄弟、实际范围上限 | 5 / 5；最终含键盘Enter | `keyboard-native.log` |
| real-Python workspace：技术失败只读/独立事实、真实历史排序 | 3 / 3 | `candidate-workspace.log` |
| real-Python lifecycle：同页Save/启停/再Save及copy/remove | 2 / 2 | `candidate-lifecycle.log` |
| typecheck、lint、build、改动文件prettier、Python ruff/format、compileall、governance、diff whitespace | 通过 | 对应 `*-final.log` 与交接检查 |
| forbidden dependency scan | 无FFmpeg/FFprobe匹配，预期exit 1 | `forbidden-dependencies.log` |

生产JS：`web/dist/assets/index-CUseHErF.js`，sha256
`f0e1ab4b2485077f019125ae7f4edd82760ce288e6b3c45f5f1874b54d5ba039`。
实际查看1536px桌面和380px窄屏四张截图：`keyboard-native/.../definition-{desktop,narrow}.png`、
`run-once-{desktop,narrow}.png`；动作可读、窄屏无横向溢出，真实键盘Enter仅产生一次受理。
busy/disabled、unknown核对与保留后续输入由受影响组件测试覆盖；不是全站视觉验收。

上述native从实际UI checked Save/Run once入口发命令，通过真实API/SQLite/Worker/Executor
操作临时Local Storage。四类阻塞的实际Task/中心归属有Python覆盖；本轮native完整恢复聚焦
冲突及其混合技术兄弟，不将它冒称四类完整native矩阵。Metadata使用合成Provider；技术失败
使用既有Executor的已知零效果测试接缝，其他兄弟真实执行，不构造产品不存在的通用重试入口。

开发中的失败日志全部保留：修复SQLite字段绑定、恢复上下文/plan身份、业务阻塞历史计数及
旧grant/初始确认夹具等问题后重跑。旧workspace用例还要求Task46.4已移除的技术失败通用
Web重试；已替换为真实只读/不重放断言，并在现有业务冲突入口补回分析不算成功、精确续作、
受影响项独立恢复和历史不重复计数证明。没有增加retry或放宽timeout掩盖失败。

### 剩余风险与 B 交接

- 当前受影响验证没有未修复失败。日志中有SQLite ResourceWarning、jsdom scrollTo未实现提示、
  Vite chunk大小及NO_COLOR提示；未隐藏或称其已消除，B全量时需关注连接生命周期警告。
- 本地CLI意图绑定真实发布UID；跨UID Worker或旧审计actor无法对应当前有效主体时安全拒绝，
  不推断管理员权限。需要通过受信身份/现有checked发布建立可验证来源。
- 激活继承链live检查成本随历史深度增长；分页/时间预算不能中断已经进入的Storage调用，
  仍依赖现有Provider超时。长期/远程Storage与多进程部署性能不在本轮实测范围。
- B按原Required Tests执行完整T4、四类完整native与workspace/settings/中心组合、wheel/安装/
  Docker/发布安全矩阵；本报告未声称这些门禁通过。B审查完整Task Base..最终验证checkpoint，
  决定Task PASS/FIX REQUIRED并重新评估Slice全部outcomes。Developer不规划下一Task、不关闭Slice。
- 下方B Review Result保留B所有权；本轮修复回应其B46.5-01/02及失败验收，不把旧结论当成本轮
  实现结果。

### 修复轮次 — B46.5-01 / B46.5-02（READY FOR B REVIEW）

- 轮次起点：`main / d1ce622f`；源码修复checkpoint：`c98b8767`。Task Base仍为
  `63c5c92e771054e30281617e2c652b7d5b486eb4`，未改Task目标/范围，未push/关闭Slice。
- **B46.5-01 已修复，真实入口可复现：** `automation_workspace_commands.py` 的
  `_definition_command_evidence` 现在对无来源ID的create仅按候选定义ID识别该条审计；
  edit/toggle/copy仍核对各自真实source。actor、action、原revision、完整候选指纹及实际
  发布证据检查全部保留；未发布/错主体/错候选/错base仍返回unknown，不自动重发、不建Task。
  新增API用例从真实checked create后核对，并覆盖错主体/候选/base/未发布证据；新增原生
  Web旅程：真实create后端已提交但响应丢失→刷新/重连→核对一次成功→同页edit+enable，
  全程只有一个定义、无第二次create或媒体工作。
- **B46.5-02 已修复：** `ProcessingWorkerService` 当前schema默认值与runtime的53一致，
  真实API组合显式传入`SCHEMA_VERSION`，保持application不导入infrastructure；旧版本
  Worker仍以真实schema mismatch拒绝，快照不匹配仍单独报告。
- 按B失败逐组适配：7个当前schema标记更新为53（旧source-schema fixture与数据/失败原子性
  保留）；read-model与successor setup改为disabled-first/真实admin checked publication；
  snapshot用例改为真实remote principal发布，证明工作前和真实效果之间检查当前权限；
  preview-retirement改为新Run once精确request身份+历史analysis旧记录读回；生命周期
  native删除场景改为Enabled/current-intent并验证删除后真实tick不再产生occurrence。
  未恢复独立grant控件、额外授权或Run once第二次初始确认。

实际验证（本机，全部为真实现有入口/临时fixture，未读用户媒体/DB/配置）：

| 验证 | 实际结果 |
| --- | --- |
| Task Required Tests #1–#3及B失败相关共27个模块，包含新增intent/readback用例 | 648 / OK，无skip，85s |
| `web/` 7个受影响实体/页面/路由模块 | 7 files / 86 passed |
| real-Python `automation-lifecycle.python.spec.ts` 完整12项（含新create lost-response与Enabled删除） | 12 / 12 |
| real-Python Run once既有 `disabled...runs once` 与成功兄弟场景 | 3 / 3 |
| typecheck、lint、改动spec prettier、Python ruff/format、compileall、governance、diff whitespace | 通过 |
| forbidden dependency scan（FFmpeg/FFprobe） | 无匹配，预期exit 1 |

native继续使用上一候选已构建的`web/dist`；本轮未改Web生产源码，只改spec，故未重新build。
B需按原计划fresh build后重跑完整T4。B日志中`test_manual_operations_contract`全量失败的原因同为
schema53 Worker被按52判定；schema默认修复后该模块独立通过，不是放宽fixture比较。

剩余风险：Developer未跑全量Python/Web/E2E、wheel/安装/Docker/发布安全矩阵，均由B负责；日志中
SQLite ResourceWarning、jsdom scrollTo及前端构建提示仍保留未隐藏。本报告未声称T4 PASS或
Slice关闭。轮次起点2026-10-28T07:28:50Z、本报告09:56Z；实际执行测试/构建并集约300s，
未用等待填充，未重复无关矩阵。


## B Review Result

```text
Reviewed: 63c5c92e771054e30281617e2c652b7d5b486eb4..75fbaa9aca3e8d862757fb40ebc72daf9c369f44
Decision: FIX REQUIRED — 2026-10-28 / B
Acceptance runs: independent results below; final T4 remains pending
Task blockers: B46.5-01 / B46.5-02 and failed acceptance cases below
Slice Required Outcomes / Surfaces all satisfied: NO — RO-5 recovery and Worker readiness regression
Next: SAME TASK FIX LOOP; preserve Task ID/Base/Goal; no next Task or Slice closure
```

### 本轮修复执行指导（Developer）

继续 Task46.5，保留原 Task Base/目标/范围，不另开 Task。按以下顺序修复；下面英文条目保留
精确复现、代码位置和命令。不要把所有测试失败都当作产品缺陷，也不要仅修改断言来掩盖缺陷。

1. **先修复“保存成功但收不到响应后卡住”。** 在
   `automation_workspace_commands.py::_definition_command_evidence` 中区分新建与其他命令：
   新建本来没有来源ID，应按候选定义ID识别该条审计；编辑/启停/复制仍核对各自真实来源。
   后续主体、操作、原配置版本、完整候选及实际发布证据检查全部保留。不能仅因为当前存在
   同名定义就认定本次保存成功，也不能靠清空未决状态或自动重发保存“解锁”。
   **验收：** 从真实新建表单保存，后端实际提交后丢失响应；刷新/重连后点击“核对本次发布”
   能找回这一次成功结果，再编辑、保存、启用均可完成。全程只有一次新建，核对不创建任务
   或产生媒体变更。错误账号/候选/原版本及未发布记录不能误报成功。
2. **再修复“正常Worker被误报版本不匹配”。** 将
   `automation.py::ProcessingWorkerService` 的当前schema默认值与本Task的53保持一致，
   核对真实API/CLI组合是否仍传入旧值；保持应用层与基础设施层的依赖方向，不做版本管理重构。
   **验收：** 当前53版本Worker、有效心跳、支持命令和匹配快照时真实就绪；旧版本Worker仍
   被拒绝，快照不匹配仍准确报快照问题。不能强制返回ready或把期望值改回52。
3. **按真实失败逐组适配测试。** 当前版本断言更新到53，但历史升级输入版本及数据保留检查
   不变；测试建数据走合法主体/关闭后创建再明确启用的流程；旧分析记录继续验证历史读回，
   新Run once使用精确请求身份并真实执行。核对API契约差异后才更新fixture。浏览器删除用例
   改查Enabled/当前意图，继续完成实际删除、后续定时停止及历史保留证明。不要恢复独立grant
   按钮、额外授权或Run once第二次初始确认来迎合旧测试。
4. **交付同一Task的修复检查点。** Developer执行下列已知失败及直接受影响测试、必要静态检查，
   记录实际结果/遗留风险后交READY FOR B REVIEW；不自行PASS、不承担全量发布矩阵。
   B随后审查完整原Base..修复Head并补齐T4；全部Slice结果满足前不交A收尾。

本轮开发/复核继续遵守用户最新约束：从轮次开始记录总墙钟时间，测试/构建/探测并集严格
小于该轮总用时50%；不靠等待填充分母。仅用已有真实入口和临时fixture，不读取用户媒体、
运行数据库或私密配置。时间预算不足的B验收保持pending，不省略失败或虚报通过。

### B46.5-01 — P1: committed Create cannot reconcile its unknown response

Existing entry: Automation new-definition checked Save, followed by the existing exact
`POST /api/v1/operations/automation/definitions/{id}/publication-intent` reconciliation.
B used the existing lifecycle API fixture with temporary databases, original candidate/action/
observed revision and the same authenticated actor. Create returns 200 and Active contains the
definition; two exact reconciliation reads both return 200 / `state=unknown` / `publication=null`.
No Job/Task or media effect was created. Raw result: `create-reconciliation.log` below.

`automation_workspace_commands.py::_definition_command_evidence.accept` recognizes a create
candidate without a source ID, then unconditionally rejects it because `str(source_id)` is not
the definition ID. New creates legitimately have null route/source IDs. The browser retains that
unknown command and `pendingPublication` blocks Save/enable/disable. AC-12 and the Task's explicit
unknown-command recovery are therefore incomplete.

1. Match source-less create evidence by its exact candidate ID; retain route/source identity
   checks for edit/toggle/copy. Keep actor/action/observed revision/candidate fingerprint and actual
   activation proof checks; absence must still remain unknown, never authorize a blind replay.
2. Add real API success-after-committed-create reconciliation coverage using existing entries.
   Cover wrong actor/candidate/base and unpublished evidence. Add the actual new-form lost-response
   browser journey: one committed create, reload/reconnect/reconcile, then same-page permitted
   edit/enable; no second create, sibling publication or media work from reconciliation.
3. Run `.venv/bin/python -m unittest tests.test_automation_execution_intent tests.test_v2_automation_lifecycle`
   and the changed Web component/native cases. Do not fix this solely by mocking a successful
   reconciliation response. Keep this correction in Task46.5.

### B46.5-02 — P1: schema53 Worker is evaluated against schema52

The Task bumps SQLite runtime `SCHEMA_VERSION` to53, but
`automation.py::ProcessingWorkerService.__init__` still defaults to52. The existing
`GET /api/v1/workers/readiness` test observes `expectedRuntimeSchemaVersion=52` on the schema53
candidate. The inventory test registers a real current-schema Worker with matching snapshot,
then readiness incorrectly returns false. This is production contract drift, not permission to
rewrite those assertions to expect52 or skip readiness.

1. Keep the application default and production composition consistent with schema53, preserving
   application/infrastructure dependency direction and actual old-worker schema-mismatch refusal.
2. Run `.venv/bin/python -m unittest tests.test_processing_worker_readiness tests.test_operations_run_inventory`.
   Retain real API/current-Active/Worker registration coverage, correct expected version and
   true-ready vs snapshot/schema-mismatch distinctions. Do not force readiness true.

### Remaining failed acceptance — adapt fixtures/contracts without losing their proofs

Full Python run: **2919 tests / 13 failures / 16 errors / 7 skips**, real324.34s. Every traceback
is retained in `python-full.log`; no claim that any failure also occurs at Task Base (not run).
Besides B46.5-02, the observed failures group as follows:

- Seven hardcoded `SCHEMA_VERSION == 52` failures in classification/destination/destination-activation/
  destination-precheck/organize configuration and the two persistence upgrade cases. Update current
  marker expectations to53 while retaining the old source-schema fixtures and data/failure-atomicity
  checks. Do not mechanically turn genuine upgrade/source-version checks into current-version checks.
- Three `test_automation_workspace_read_model` errors publish enabled definitions as unconfigured
  `tester`; thirteen `test_configuration_successor_draft` setup errors activate enabled definitions
  as `setup` through an API-bound authority before any Active exists. Use legitimate disabled-first
  setup/current authorized checked publication for the unchanged sorting/successor behaviors;
  preserve unauthorized/first-activation refusal. Do not weaken production permission checks or
  let a candidate authorize itself. Any actual first-publication defect found must be corrected.
- `test_configuration_snapshot...test_worker_rechecks_current_principal_between_real_effect_boundaries`
  no longer gets its expected pre-Task authority refusal. Reconcile its publisher/authority fixture
  with current intent semantics and prove the real remote principal is checked before work and
  between real effects; retain completed siblings and zero later effects. A trusted local publication
  must not be mislabeled a remote-principal permission proof.
- `test_preview_retirement...test_frozen_run_once_plan_is_reread_from_the_durable_intent` POSTs the
  new Run once entry without request identity and gets400. Test retained historical analysis through
  its supported old record, and the new normal entry with exact identity; do not restore new analysis
  admission/second initial confirmation or drop durable old-plan readback proof.
- `test_manual_operations_contract...test_real_api_documents_match_the_frontend_fixture` fails its
  exact payload comparison. Review the actual diff against the typed contract, correct production or
  update the fixture only for intended changes; retain malformed/authority/source assertions.

Developer runs these failed cases, directly affected module suites and changed-file checks. B runs
fresh full acceptance after the correction checkpoint. Full suites remain B-owned.

### Failed native acceptance — update obsolete grant-dependent assertion

Full existing `automation-lifecycle.python.spec.ts`: 10 passed / 1 failed. Line285 waits for
`unattended authority active`, a normal-flow label this Task intentionally removed. That prevents
the remaining explicit Remove, durable removed-definition and retained-history assertions from
executing. Update this scenario to the Enabled/current-intent contract and retain its actual
deletion/stop/history proof. Historical grants may be retained evidence; do not restore their UI
or execution gate, delete the scenario, add retries or weaken its timeout. Developer runs this
complete directly affected spec after fixing; B still owns the remaining T4 gates.

### B evidence and all-outcome reevaluation

Candidate: `75fbaa9a`; complete Task Base..Head manifest contains 45 files, including production,
tests/harness and documentation. B inspected the cross-layer publication, authority, execution,
scope/stability, recovery/query and typed UI changes and the handoff evidence; Developer labels
are not acceptance. Branch `main`; no pre-existing tracked changes. All pre-existing untracked
OS/private/log/reference-image/zip files remain untouched and unstaged. No user runtime data,
configuration or media accessed; only TASK is changed by B. No push or implementation by B.

Stable local-only evidence: `.git/validation-evidence/b-task46.5-review/`.

- Governance preflight and `git diff --check`: PASS.
- Independent Web full `npm run test -- run` (cwd `web`): **87 files / 1270 passed**, real99.80s;
  `web-full.log`. Existing jsdom scrollTo warnings retained.
- Independent native lifecycle command (cwd `web`):
  `npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/automation-lifecycle.python.spec.ts`:
  **10 passed / 1 failed**, real24.61s; `native-lifecycle.log`. Used existing Developer-built assets;
  diagnostic failure evidence, not a fresh-build final acceptance claim.
- Independent Python full regression (root `.venv/bin/python -m unittest discover -s tests`):
  **2919 / 13 failures / 16 errors / 7 skips**, real324.34s; `python-full.log`.
  ResourceWarning/temporary-directory warnings remain visible; no new skip/retry/timeout changes.
- Fresh-build remaining native four-type/settings/center matrix, static/package/installed consumer/
  Docker/release gates are **pending**. A proven P1 permits early FIX REQUIRED under workflow §6;
  these gates stay B-owned and are not transferred to Developer. No full T4 PASS claim.
- Timing: Web/native overlapped the Python run; actual test window is about325s, not the sum
  of three durations. Turn-start UTC was not captured, so the precise total-review denominator/
  percentage cannot be independently audited; no fabricated <50% certification or waiting padding.
  No further product gates were started after the proven blockers.

| Slice outcome | B reevaluation |
| --- | --- |
| RO-1 | Accepted46.1 shared action implementation retained; no new palette/Entry redesign |
| RO-2 | Accepted46.3 Files admission/initial confirmation retained; current-schema Worker readiness regresses; shared execution/recovery changes still need final T4 |
| RO-3 | Accepted46.2 local ordinary-work behavior retained; its disclosed native menu/non-localhost limits remain |
| RO-4 | Accepted46.4 organizing-only/four-type semantics retained in intent; shared query/recovery changes still need final T4 |
| RO-5 | Incomplete: B46.5-01/02 and failed acceptance; no PASS or readiness packet |

No additional Task is planned. A-owned old first-Task pointers remain for final reconciliation;
they neither override the real Task46.5 checkpoint nor authorize closure.
