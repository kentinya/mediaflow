# Task 47.2 — Files 手动整理接入 Task 引擎与操作暂停退役

Authority: committed [SLICE.md](SLICE.md) at `c1e616113f87420d6f7411c3e6287ce81c1f5331`；
[Development Workflow](docs/development-workflow.md) 管理生命周期与测试分工；
[B experience](docs/agent-experience/task-planner-reviewer.md) /
[Developer experience](docs/agent-experience/developer-implementation-role.md)。

```text
Task ID: 47.2
Task Type: SLICE
Parent Slice: 47
Status: READY FOR B REVIEW
Task Base: c942c4b4b9d3abf105341e8163c1be2d95d9a671
Difficulty: High
Test Level: T4
Planner / Reviewer: B
Authorization: PLAN ONLY — 2026-10-31; USER-AUTHORIZED IMPLEMENTATION — 2026-10-31
```

## Goal

让**本轮接入后新提交的 Files 手动整理**从首次准入开始，由 Task47.1 内核承担唯一调度权威，
贯通有界发现/稳定性观察、分析、初始摘要确认、OrganizerExecutor、逐项 Result、协作控制和
现有四类问题处理后的安全续作。全程保持一个顶层 organizing Task，不再为该工作产生 Job 或
恢复子 organizing Task。已有 intent/discovery/preview/authorization/execution/checkpoint 记录
保留证据职责，不再为新工作独立排队或领取。另按用户明确改约，退役整理及普通文件操作的
暂停/从暂停继续，保留安全取消和四类问题处理后的继续整理。

这是 RO-1、RO-2 的**手动生产入口**、RO-3 的**新手动工作**与 RO-5 对应 Files/Task Center
旅程的完整纵向交付；不是三触发统一或 Job 退休完成。保持 `V2-TASK-001/002/003/005/006/007` 的
适用部分，`V2-OPS-014–017`、`V2-FILES-007`、`REQ-TASK-002/005/006/007/009/010`、
`REQ-RECOVERY-006`、适用 `REQ-RESULT-*`、`REQ-SAFE-*` 和部署 readiness 不变量。

完整旅程：资源库 Files 选择文件/文件夹 → 整理 → 立即可回读原 Task 与发现/分析阶段 →
同页查看完整计划摘要 → 明确确认所选文件/破坏性影响 → resident Worker 执行 → 逐项结果。
遇到识别、元数据候选/补正、分类、冲突，沿用现有页面保存决定、分析、摘要与显式继续，仍回到
原 Task。刷新/认证续接/重启按精确 request/Task 读回；失败保留原因、已知效果、安全性与下一步。
技术失败和 uncertain 保持既有只读/检查边界，附件告警不重放主文件。

## User scope change — all-operation Pause retirement

用户于2026-10-31明确取消整理暂停功能；A范围变更已提交于上述 Contract checkpoint，再由 B
调整同一 Task。Task ID/Base 与此前真实实施历史不变，High/T4 不变。此前 A 范围权限用于这次
合同动作，B角色继续负责Task；未实施代码、未做A最终审查或宣告PASS。

本 Task 增加整理及普通文件操作 Pause / resume-from-pause 的完整退役：手动、定时、Run once、
Copy/Move等操作及既有Web/API/CLI控制入口均不再提供该能力；这仅改控制，不切换自动入口引擎。
保留取消；取消后不提供“继续本次执行”。保留未取消工作四类问题处理后的显式继续、摘要确认、
人工/稳定性等待和安全栅栏。普通文件 Copy/Move 等也取消暂停/从暂停继续，其取消和效果保护保留。
用户确认当前没有已暂停的整理任务：不开发专项暂停任务迁移、恢复或兼容执行，不新增这类
历史场景作为必过门禁。通用历史读取仍保留，不删记录、不自动重放或清除效果保护。旧暂停缺陷记录在Git，
本次按用户改约取消其修复义务，不把“移除要求”记成“原缺陷已修好”。

## Actual-code gap — current candidate

当前产品候选为 `4659536c2f3f230b0d7ef271c1b375048e259216`，Task Base不变，实际schema为55。

- 上轮两项局部修正已确认：重复分析复用未解决review，部分补正可确认就绪子集，随后第二项
  可经Files discovery分析/摘要在原Task完成；暂停专用remaining-scope接口改为无效果拒绝，
  `_run_scope_continuation`及其Worker执行接线已退役。不重复开发这些已完成部分。
- schema55移除manual_executions.task_id唯一约束以支持同Task分批执行；保留历史关系、授权
  唯一性与旧Job。定向迁移模块通过，但不等于完整真实53/54升级/发布验收。
- Task Center原有保存→继续分析仍调用legacy recovery/continue并创建recovery-continuation Job，
  原Task仍WAITING_HUMAN，未接入同Task引擎。底层Files analyze能走通不能代替真实Web入口。
- 两文件分两次执行均成功且有2条Result，但Task和Run接口仍total_items=1、completed_items=1；
  当前execution的selected数量覆盖了顶层Task聚合，未完成原M4/M8准确文件数要求。
- 等待决定/确认时从Task Center取消，Task/items已cancelled且零名额/零效果，但discovery仍为
  completed且cancel_requested=false；新requestId重发同一文件被旧admission拒绝。
- 以上三项详见B Review。原M1–M10仍须整体验收；due/Run once/独立API-CLI引擎切换及Job
  迁移删除为后续，未把它们扩大到本Task。完整T4仍由B承担，不因Developer报告未同步加阻塞。

## Next implementation order

1. 按P1-1接通现有Task Center四类保存后的实际continue/摘要入口到原Task调度与同一引擎，
   保留Save零变更/不入队、分析零变更、摘要与显式确认，不新建Job或顶层恢复Task。
2. 按P1-2修正整个Task的聚合发布，分别保留execution子集统计与Task全来源/结果；新准入和
   逐项结果都不能把顶层计数重置为当次selected数量。
3. 按P1-3收齐取消后的关联准入/源占用，安全取消且无未确定效果的旧工作不能阻塞合法新请求；
   不清除unknown保护、不把新请求当作恢复已取消工作，不删记录。
4. Developer补这三条现有入口回归，运行新增/变更/直接受影响测试和静态检查，交准确checkpoint、
   实际结果/限制；B再独立审完整Base..Head，完成真实Web与其余T4/升级/发布验收。

## Implementation Scope

1. **接入现有 Files 准入与证据事务。** 复用生产 `service_api.py` 的现有 Files 整理入口、
   `MediaDiscoveryService` 和 `create_files_organize_work` 关系；新 Task、调度资格、发现/请求
   outcome、display 与可确定的源占用原子提交。保留 direct/folder/mixed、同源收敛/显式扩展、
   principal/library/pin 隔离；满容量无孤儿/半套扩展，精确重复满时仍回原请求。不要接管旧行。

2. **建立可复用的 organizing 应用执行路径并接 resident Worker。** 以 Task claim+原 pin 驱动
   原发现、解析/识别/Metadata、Naming/Classification/Planner 和 Executor；直接复用/抽取现有
   实现，不能复制完整 pipeline。新工作只由 Task 领取，原 discovery/execution runner 必须排除它；
   这些记录仍可读、可关联。沿用现有 resident 进程、注册/schema/支持命令与长调用心跳；不新增
   常驻进程、线程并行或 API 启动 Worker。原 pin 在 Active 改变后仍可合法消费，缺 pin 有界拒绝。

3. **贯穿 claim 与效果边界。** 同一 owner 栅栏保护 discovery/manifest、TaskItem、计划/checkpoint、
   evidence、Result 和聚合发布；保留现有 source ownership、执行锁及安全释放。Executor 前验证
   claim、精确源版本、计划/权限/能力/冲突与授权范围，派发变更前耐久记录边界；派发后未可靠
   落结果保持 uncertain，不因到期/重启/无 Result 自动重放。分析与读操作零 Storage mutation。

4. **接入人工等待、确认和协作控制。** 全部人工等待且无机器工作时释放名额，混合机器工作与尚未
   确认的 in-flight 控制保留名额。确认/继续在一个事务内检查摘要/版本/pin/可执行 subset、容量，
   消费既有精确单次授权并重新登记原 Task 机器工作；失败保留选择/摘要/原状态且不消费权限。
   准入事实与后来确认事实须可区分；若旧 execute_authorized 字段需要改变，只能由显式合法
   授权事务完成，不放宽通用机器发布 guard，也不把一个布尔值当作全部 mutation 权限。
   Save 决定不入队；安全分析按原交互动作入队且零变更。取消有请求和安全确认，不中断调用；没有整理暂停/从暂停继续的入口。

5. **四类恢复与现有安全续作回到原 Task。** 复用现有 decision/checkpoint/source validation、
   analysis/summary/selected confirmation 服务及表单，把新手动工作的机器阶段交给同一引擎。
   新的分析/执行证据可以有独立 ID，但不是另一个顶层 organizing Task/Job 或领取队列。
   可复用或版本化 item ID；后者保存明确耐久历史关系、旧链接与正确文件数。原成功/ignored/
   skipped/partial/uncertain siblings 独立保留；不新造技术恢复、附件重放或任意历史 Reprocess。
   不能因容量不足登记将来自动继续，也不能清掉已接受 CANCEL。旧工作保留本次退役范围之外的合法恢复路径；不新增历史暂停整理的专用恢复路径。

6. **保证分期共存安全。** 定时/Run once/既有已准入工作本轮仍走原路径，不双写或自动改绑。
   共享容量配置的实际 admission 检查须在事务内覆盖新 Task 与仍受旧队列限制的工作，并按明确
   已有关系去重；两种入口竞争最后名额不得超额。只做必要的兼容计数/排除，不增加另一个 queue
   对象或兼容执行器。沿用现有配置键及 immutable JSON/digest，不重写已发布 pin；部署消费者和
   readiness 必须真实使用该值。不同入口共享源锁；新旧 Worker 不得同时写同一新 Task/源。

7. **完成现有 Web/API 结果闭环。** Files 精确未知响应回读、原摘要/返回链接、Task Center 八视图/
   四类 union、detail/控制/逐项证据/JSON/日志在新身份下可用且一项工作计一次；初始确认不算
   Attention。只做所需 DTO/查询/链接/既有页面改接，不新增 picker/全局监控或 UI 重设计。
   旧 Task/Job/历史子 Task 链仍按原证据可读；普通两库文件操作不进入 organizing population。
   如必须增加持久字段/索引，采用连续版本的 additive、失败原子迁移并验证53/54升级/重开，
   不删除 Job 数据或改旧授权事实。只记录本轮确实完成的分期架构事实，遵循已提交的新 TARGET。

8. **退役所有操作的暂停能力。** 删除整理 Files/Task Center/相关详情、普通两库操作弹窗和
   CLI/API的Pause/从暂停继续动作、可用性投影及专用活跃分支。共享Task控制路由按真实
   command/kind拒绝已退役命令，提供有界无效果答复；不能只隐藏按钮留后门。保留取消及
   识别/元数据/分类/冲突处理后的“继续整理”。不开发用户确认不存在的暂停整理任务迁移/恢复
   或兼容执行；必要通用历史读取不受影响，不清表或自动改状态。执行中的取消在当前调用结果
   可靠后停止未执行项；已成功项保持成功，不将正常取消当技术失败；uncertain仍不可重放。

## Acceptance Criteria

M1–M9中的“同一Task”与新引擎要求，仅适用于本轮接入后首次准入的新Files手动工作及其后续
处理；M10的暂停退役另覆盖所有整理及普通文件操作，包括旧路径的当前控制入口。历史Task/Job/
子Task不合并、不重新编号；读取与退役范围之外的合法行为保持兼容。
TaskItem、分析、计划、授权、执行和 attempt 的内部 ID 不要求恒等；验收依据是同一顶层工作、
精确源版本/pin 的耐久关联、历史保留、准确文件数与不重复执行。

- [ ] M1：上述新手动工作的真实 Files direct/folder/mixed 请求在业务 readiness 前建立且只建立
  一个 organizing Task；发现、摘要确认、执行直到结果/重启同 ID；无新 Job、恢复子 organizing
  Task、双写/双领取。
  精确重复/扩展保留各请求 outcome，旧未完成工作可回读，不被新内核悄悄接管。
- [ ] M2：沿用直接文件与文件夹各自筛选、100 scope/primary 等现有上限、真实稳定观察和附件规则；
  未读完/超界不执行 first-N 前缀；空/不稳定/不可读/排除/成功状态和剩余范围准确。
- [ ] M3：手动初次及四类恢复的 Save/分析无效果；只有精确已确认 subset 在当时有效权限内执行。
  错 principal/源版本/摘要/pin/过期权限和 overwrite/cleanup 未授权拒绝；C 配 A 命名/分类仍为 C。
- [ ] M4：在上述新手动工作中，四类各完成决定→分析→摘要→显式继续→Result，刷新/重启后仍能
  读回原 Task，并在满足原安全/授权条件时显式继续；不要求任意中断后自动继续。
  同一混合批次每文件独立，历史 attempts/Result/附件效果不覆盖，旧 item 深链可读、文件数不膨胀；
  技术失败无第五入口，主文件已成功但附件告警不重放主文件。
- [ ] M5：真实双连接/Worker竞争只有一个有效 owner；旧 claim 的发布、变更前检查与锁清理无效。
  取消在安全边界结算；请求期间名额不提前释放，CANCEL 不被继续覆盖；已成功 sibling 保持成功，
  尚未执行项按取消语义结算而非标成技术失败；源/效果保护跨等待与取消安全边界保留。
- [ ] M6：新手动与旧 scheduled/Run once 竞争最后名额不超额、不重复计 linked work；全人工等待
  为零、混合机器工作为一。满时新请求无孤儿，确认/分析/继续不消费授权且原选择/结果不丢；
  释放后必须显式重试，不自动续作。普通 transfer 保持原容量及本次暂停退役之外的行为，不被整理计数误纳入。
- [ ] M7：只有现有支持的控制/恢复边界、有耐久证据证明剩余阶段安全，且重新通过源/pin/权限/
  claim 检查时，才可续原 Task。分别验证派发前的安全剩余工作和派发后尚无耐久结果证明的中断；
  后者保留 uncertain 与已知效果，超时/重启/租约失效/缺 Result 本身均不能成为重放理由。
  新旧路径不能因竞争或重复领取而重复执行同一工作/源版本；不将此断言扩大为永久禁止有合法
  新意图的新工作。不读用户库/媒体验证，不承诺所有崩溃点无缝恢复。
- [ ] M8：Files 关页/丢响应/认证续接、Task Center 计数/分页/四类问题/控制/证据/导出/日志闭环
  实际可操作。普通两库文件工作与旧历史可读；定时/Run once 仅验必要共存兼容：原启用/禁用、
  规则、授权、结果及跨路径容量/源占用保护不退化，不要求它们切换引擎或同 Task 化旧恢复链。
- [ ] M9：新建/54重开及必要的53/54升级、迁移故障回滚、源码外 wheel 和容器真实 resident Worker
  完成同一手动旅程。B 完成适用 T4 门禁；未运行/不可用不记 PASS。不要求本 Task 删除旧 Job。

- [ ] M10：整理及普通文件操作（包括Copy/Move）的Web/API/CLI不再提供Pause/从暂停继续；
  旧请求通过真实入口被有界拒绝且无变更。安全取消仍完整，四类问题处理后的显式继续仍在
  原Task完成。用户已确认无现存暂停整理任务，不以暂停任务迁移/恢复/兼容执行作为验收项；
  原有通用历史读取、结果、权限与非重放保障不丢失。

## Required Tests

以下是实施后的要求，本次规划没有运行或宣称产品验收；测试所有数据使用临时根/SQLite/fake
Provider/local servers，禁止生产 SMB/OpenList/S3/TMDB 或用户媒体。优先扩展已有 fixtures、API、
Worker seams；新增用例须从已存在的真实入口触发，不能猜造路由来证明不可触发的缺陷。

### Developer — affected tests

1. 扩展已有 `tests/test_manual_task_engine.py` 及直接受影响的既有恢复模块；需要时可新增
   恢复测试文件，交接列出真实模块命令，不强制创建测试骨架。覆盖M1–M7/M10的服务/SQLite/Executor链、
   独立连接竞争、控制/授权事务故障及关闭重开，不只 mock 调度或比较 ID。

   ```sh
   .venv/bin/python -m unittest tests.test_manual_task_engine tests.test_task_scheduling tests.test_task_scheduling_fencing tests.test_task_scheduling_migration
   .venv/bin/python -m unittest tests.test_media_discovery tests.test_manual_organize_intent tests.test_manual_organize_preview tests.test_manual_organize_execution tests.test_task_center_recovery_lineage tests.test_recovery_continuation tests.test_processing_checkpoint
   ```

2. 共存计数、源占用、Worker 接线直接受影响回归：

   ```sh
   .venv/bin/python -m unittest tests.test_automation_admission tests.test_automation_job_fencing tests.test_automation_definition_occurrence tests.test_v2_automation_run_once tests.test_processing_worker_readiness tests.test_automation_settings_resident tests.test_direct_file_transfers tests.test_media_library_transfers
   ```

   补新手动/旧 due/Run once 最后名额竞争与去重断言；既有 Task47.1 的字段不变断言只可为明确
   合法授权事务补正向例子，不能放松旧 owner、任意扩权、错源版本/pin 或 uncertain 保护。

3. 若改 Web，运行受影响文件（以下为已存在的核心组，新增/其他直接受影响文件一并列入）：

   ```sh
   cd web
   npm run test -- run src/features/operations/OrganizeRouter.test.tsx src/features/operations/OrganizeDiscoveryPage.test.tsx src/features/operations/OrganizeCreationPage.test.tsx src/features/operations/TaskItemRecoveryPanel.test.tsx src/features/operations/OperationsInventory.test.tsx src/features/library/LibraryFileOperationsDialog.test.tsx
   npm run typecheck
   npm run lint
   npm run format:check
   ```

4. 对 Base..Head 实际变更的 Python 文件执行 ruff format/check、compileall；执行治理和
   `git diff --check`。Developer 只交新增/变更/直接受影响测试结果，不承担 B 的全套门禁。

### B — acceptance and full regression

- 独立审完整 Task Base..candidate，先重现 M3/M5/M6/M7/M10；核对真实 admission、resident assembly、
  变更前授权/claim、所有逐项 writer，以及新旧 runner 排除，不用报告或命中字符串代替链路。
- 执行 [共享 T4 全量门禁](docs/development-workflow.md#shared-full-regression-commands)。
  本 Task 改共享 writer/调度/授权/容量与真实 mutation，需完整 Python/Web/static/examples/
  packaging/security 回归。保留失败、跳过及限制，测试时间按用户要求小于本轮总用时50%。
- build 后在 `web/` **分别启动新 harness**：

   ```sh
   npm run test:e2e -- --config=playwright.python.config.ts --workers=1 tests/e2e/operations-inventory.python.spec.ts
   npm run test:e2e -- --config=playwright.python.config.ts --workers=1 tests/e2e/operations-task-center-visual.python.spec.ts
   npm run test:e2e -- --config=playwright.direct-files.python.config.ts --workers=1 tests/e2e/direct-files.python.spec.ts
   npm run test:e2e -- --config=playwright.python.automation.config.ts --workers=1 tests/e2e/automation-run-once.python.spec.ts
   ```

  扩展真实 Files 新请求及四类恢复的断言为**从准入至继续保持同 Task**，并检查真实文件/效果/
  Result/attempt/计数/授权及未知响应只回读；旧历史测试保持原关系，不能整体改期望抹掉历史。
  新工作的内部 item/attempt ID 变化以耐久关系与效果验证，不追加 ID 必须相等的断言。中断测试
  限于 M7 的两类现有可触发边界；既验证可证明安全时能继续，也验证效果不确定时不能重放，
  不枚举理论上无法从现有入口触发的崩溃组合。自动流程测试保留原执行路径和历史关系断言。
  M10新增真实入口对照：整理及普通操作pause/resume均被拒绝且无变更，页面/弹窗无相应
  动作，四类继续不被误删。按用户改约将旧暂停正向测试更新为退役拒绝，同时保留原RBAC/
  版本/效果/非重放断言；不因没有现存暂停整理而增加专项历史迁移/恢复门禁。取消补两文件
  “第一部执行中点击取消”的实际场景，验证当前调用不中断、首项真实结果保留、余项不执行，
  不被失败兜底或后续继续覆盖；普通两库Copy/Move取消也保留已知效果与安全边界。
  对桌面1536与窄屏380/390的摘要、四类输入、结果/错误/返回实际截图作可见性检查。自动化组
  只证明本轮必要共存兼容，不作为 automatic 入口已改接的证据。
- 新候选真实 wheel 源码外安装后经 Task API/Worker 跑手动链，核对 site-packages、结果重开及
  artifact hash。运行 Docker security/fresh/restart 与实际 Task Base 升级/失败恢复：

   ```sh
   .venv/bin/python scripts/schema_upgrade_rehearsal.py --base-sha c942c4b4b9d3abf105341e8163c1be2d95d9a671 --expect-schema 54 --expect-candidate-schema 55
   .venv/bin/python scripts/docker_upgrade_recovery_smoke_test.py --base-sha c942c4b4b9d3abf105341e8163c1be2d95d9a671 --base-schema 54
   ```

  当前候选schema55；若后续实现再次改变，以真实版本更新命令。另验证真实 Slice
  Base53→candidate 的保留与失败原子链。Docker 使用 Colima 可共享的临时目录；复用已有隔离
  脚本/维护租约，不新造验收平台，不把脚本 SKIP/exit0 冒充有效门禁。

## Non-goals

- 不开发暂停整理任务的专项迁移、恢复或兼容执行系统；用户已确认不存在这类现存任务。
  普通操作只移除暂停能力，保留取消/进度/结果等行为，不扩张为普通文件管理重设计。

- 本轮不切换 Scheduler due、saved-definition Run once 或独立 API/CLI organizing 的执行引擎；
  只改它们与手动新路径共存所必需的计数、排除/保护及兼容消费者。
- 不转换/合并历史 Job/Task，不删除 Job 表/接口/CLI/前端模型，不做全部 settings 命名迁移。
  历史迁移、自动触发接入和最终 Job 退休仍是 Slice 后续必须完成的工作，不是永久豁免。
- 不增加第二套 Organizer/恢复系统、并行度、过期抢占、全崩溃点自动恢复、技术失败 Web 恢复、
  附件自动重放、MediaLibrary Organize 或普通文件管理重设计。不扩改整个项目。

## Workspace / predecessor / Slice reevaluation

规划起点：`main` / `c942c4b4b9d3abf105341e8163c1be2d95d9a671`。治理 preflight PASS；
无 tracked edits；既有 OS/log/图片/压缩包等 untracked 原样保留、不暂存。只写本草案，不改产品、
A-owned Contract/Roadmap/Progress 或需求；不 push、不改历史、不使用子代理。
本次草案澄清从 `01e3ab7699950cb5d62761743e8aeb07f7121155` 开始，仍无 tracked edits；
仅明确新手动工作适用范围、可证明安全的条件续作及自动流程共存验收，Task Base/Goal/等级不变。

Task47.1 的 T1–T10 已 PASS；本次对全部 Slice 结果重评：RO-1 内核已就绪但生产链未接；RO-2
三个触发未统一；RO-3 新工作四类恢复尚未同 Task；RO-4 additive54 已通过但历史转换/删除未做；
RO-5 原界面兼容已验而 Task 化全表面未交付。因此继续规划本 Task，Slice 不满足交 A 关闭条件。
本 Task 通过后必须再次核对全部 RO，不预先宣称自动触发、历史迁移或 Job 退役完成。

## Developer Completion Report

Checkpoint: `61b30847c0e6d760224e42225574fdf39026d9a0`（Base `c942c4b4` 不变），
Status READY FOR B REVIEW。完整 T4/升级/发布与 PASS 判定仍由 B 负责，本报告不宣称 STOP。

**变更行为（3 项 B Review 阻塞 + 2 项同候选回归）**

1. P1-1：`POST /tasks/{task}/items/{item}/recovery/continue` 现在按真实 Task Owner 分流。
   Task 有 `task_scheduling` 行时，新增 `application/manual_task_continuation.py` 在
   checkpoint 版本/效果确定性/原 pin 与 kernel Task 身份校验通过后，调用既有
   `MediaDiscoveryService.request_analysis` 把**同一 Task** 的零变更分析经
   `requeue_scheduled_analysis` 重新登记；响应为 `nativeAnalysis`（同一 discovery/版本），
   不含 `job_id`、不建子 Task、不消费执行授权。满容量/取消/不确定效果给出有界 409/503 且
   保留决定、摘要与结果，不登记自动继续；旧（无 scheduling 行）Task 保持原 Job 路径。
   旧 Job 批处理入口对 kernel Task 改为无效果拒绝（同 Task 逐项继续），不再静默造 Job。
   Web `api-client` 的 ack 归一化接受并标记 `nativeAnalysis`，面板据此说明“原 Task 已重新
   排入零变更分析”，并对 `capacity_full`/`continuation_exists` 给出下一步。
2. P1-2：新增 `domain/task_persistence.task_item_counts/task_work_status`；
   `admit_manual_execution` 在 kernel 采纳的同事务内按整项 TaskItem 种群重算
   total/completed/failed，`_task_after_item`（kernel 路径）、engine 的 analysis/human-
   wait/finish/terminal settlement 统一按耐久来源发布。分批确认不再把顶层计数重置为当次
   selected 数量，部分完成不再显示 completed；Task 行、`/tasks`、`/operations/runs` 一致。
3. P1-3：取消在 claim 安全边界结算时，`_publish_discovery_control_locked` 也把 linked
   discovery 投影为 `cancelled`/`cancelRequested=true`（保留 counters/findings/preview
   链接，仅改阶段与取消事实），使“分析已完成但仍在等确认”的准入不再占源；新 requestId 的
   同文件请求经正常权限/版本/占用检查成为新的 organizing Task，旧 Task 保持 cancelled 与
   可回读证据。in-flight/uncertain/已迁移来源仍被源保护拒绝（回归断言）。
4. 同候选回归 A：`da6d9630` 退役暂停专用 remaining-scope 时删除了
   `_assert_reconciliation_binding` 但保留了调用，Run once 重复 requestId 会 AttributeError
   崩溃；按原语义恢复该 fence（definition/pin/revision 不一致时 409）。
5. 同候选回归 B：`test_paused_definition_relative_scope_continues_in_the_real_worker` 仍断言
   已退役的暂停续作；改写为真实 Worker 对历史 queued scope-continuation Job 的有界拒绝：
   Job FAILED、无 Task/Item/Result/授权、原暂停 Task 与源树不变、重开一致。

**受影响测试（实际命令与结果，cwd 仓库根）**

| 命令 | 结果 |
|---|---|
| `.venv/bin/python -m unittest tests.test_manual_task_engine tests.test_task_scheduling tests.test_task_scheduling_fencing tests.test_task_scheduling_migration` | 84 tests OK（含 4 个新回归：同 Task continue/满容量/取消后新请求/两批计数 + 不确定源保护） |
| `.venv/bin/python -m unittest tests.test_media_discovery tests.test_manual_organize_intent tests.test_manual_organize_preview tests.test_manual_organize_execution tests.test_task_center_recovery_lineage tests.test_recovery_continuation tests.test_processing_checkpoint` | 305 tests OK |
| `.venv/bin/python -m unittest tests.test_automation_admission tests.test_automation_job_fencing tests.test_automation_definition_occurrence tests.test_v2_automation_run_once tests.test_processing_worker_readiness tests.test_automation_settings_resident tests.test_direct_file_transfers tests.test_media_library_transfers` | 230 tests OK |
| 直接受影响补充：`tests.test_operations_task_center tests.test_operations_run_detail tests.test_operations_run_inventory tests.test_operations_workspace tests.test_recovery_batch tests.test_task_pause_resume tests.test_scope_continuation tests.test_operator_ui tests.test_operator_observability tests.test_restart_fault_boundary tests.test_automation_run_once tests.test_automation_definition_execution tests.test_automation_unattended_grant tests.test_automation_workspace_read_model` | 424 tests OK |
| 补充：`tests.test_task_persistence tests.test_task_retry tests.test_task_scope tests.test_processing_recovery_admission tests.test_organize_preparation tests.test_v2_automation_operations tests.test_v2_manual_organize tests.test_manual_operations tests.test_manual_operations_contract tests.test_manual_ignore tests.test_manual_ignore_batch tests.test_direct_file_operations tests.test_batch_cli` | 251 tests OK |
| `web: npm run test -- run …OrganizeRouter/OrganizeDiscoveryPage/OrganizeCreationPage/TaskItemRecoveryPanel/OperationsInventory/LibraryFileOperationsDialog` | 6 files, 101 tests OK |
| `web: npm run typecheck` / `npm run lint` / `npm run format:check` | 全部 exit 0 |
| `.venv/bin/ruff format --check mediaflow tests scripts` / `ruff check` / `compileall -q` / `python3 scripts/check_governance.py` / `git diff --check` | 全部通过 |

SQLite ResourceWarning 与历史相同，未新增 skip/retry/超时放宽，未访问用户运行库、媒体或私有配置。
未运行 B 的全量 Python/Web/E2E/截图/wheel/容器/53→55 升级门禁。

**剩余工作与已知限制（交 B 判定，非本地 PASS）**

- kernel Task 的原位“摘要/确认”仍是同一 Task 的 Files preview（`GET/POST
  /operations/organize/previews/{id}`）；TaskItem 面板的 `manualRecoveryPreparation`
  仍来自旧 Job recovery 链，原生继续后不出现“同页摘要”区块。B 若把面板内原位摘要视为
  M4/M8 必过，需要另行确认范围（本次未新增第二套准备/授权系统）。
- 已退役暂停作用域的历史 queued `SCOPE_CONTINUATION` Job 由 Worker 以通用失败记录（无
  `failure_category`），零副作用、零 Task、不可重放；本次未新增类别文案。
- 未验证新真实 Web/截图/wheel/容器/升级；未复跑 53/54→55 迁移。

## B Review Result

```text
Reviewed Base: c942c4b4b9d3abf105341e8163c1be2d95d9a671
Reviewed Head: 4659536c2f3f230b0d7ef271c1b375048e259216
Contract: c1e616113f87420d6f7411c3e6287ce81c1f5331
Decision: FIX REQUIRED — native continuation still queues Job; aggregate counts wrong; cancelled admission retains source
Slice Required Outcomes / Surfaces all satisfied: NO
Next: SAME TASK FIX LOOP; preserve Task47.2 ID/Base/Goal and amended scope
Evidence: .git/validation-evidence/b-task47.2-4659536c/
```

独立核对完整Base..Head的54文件manifest：承接前轮生产接线/容量/取消审查，检查本次引擎、
逐项问题发布、四类决定消费、schema55 rebuild、暂停退役接线及测试删改，并沿Web实际client
追到API/应用调度，没有只审最后一笔提交或以局部正向测试替代完整交付。
本轮只更新TASK；main/Reviewed Head起点无tracked edits，既有OS/log/图片/ZIP等untracked
原样保留、不暂存。无产品/测试/A-owned合同编辑、push、历史改写或子代理。

### P1-1 — Task Center保存决定后的继续仍创建旧Job（M1/M4/M8）

**用户场景与复现：** Files新提交一部影片，Task Center为该条目选择识别类型并保存。
`TaskItemRecoveryPanel.saveDecision()`看到retry后实际调用 `continueTaskItemAnalysis()`，即
`POST /api/v1/tasks/{task}/items/{item}/recovery/continue`。B从真实Files准入开始，使用已配置
operator角色，保存决定后按此相同接口提交当前checkpoint：返回202、`job_id`非空，数据库
新增1个pending recovery-continuation Job；原Task仍WAITING_HUMAN，Task Worker再运行4轮
不进入该分析。零Storage变更。这不是虚构路由，也不是旧Task或历史暂停场景。

**原因和开发指导：**

1. 当前 `service_api.py` 仍无条件调用 `RecoveryContinuationService.submit()`，该服务仍提交
   旧Job续作；新增 `_native_review_decisions()`仅使Files analyze消费决定，未改Web实际入口。
2. 新手动kernel-managed工作沿现有continue应用入口重新登记原Task的安全分析，复用已经
   实现的四类决定、discovery分析、摘要/所选确认和引擎；不再创建独立Job/恢复顶层Task。
   旧工作维持本轮退役以外的原合法路径，不接管/合并它们。不能通过隐藏四类处理按钮解决。
3. 保留Save仅保存决定；独立continue分析按原Task、源版本/pin、checkpoint、CANCEL、unknown
   与共享容量检查准入。满时保留原决定/摘要/结果且不消费授权/不登记将来自动继续；成功后
   仅做零变更分析，摘要仍需现有精确显式确认。返回DTO/client normalizer和查询投影如需适配，
   应真实表达原Task的进度/摘要，不伪造job_id满足旧响应类型。
4. 沿原Task Center页面走完四类（含Metadata候选/补正）保存→分析→原位摘要→确认→Result。
   核对现有单项/批量继续消费者，不另造恢复系统；内部证据ID可变但耐久关系/历史不丢。
   Developer在现有集成fixtures补同一真实continue接口回归，断言无新Job/子Task、原Task推进、
   零变更分析和逐项结果；不能只直接调用Files analyze代替Web使用的入口。B修正后验真实浏览器。

### P1-2 — 分批执行覆盖顶层Task计数，两部成功仍显示一部（M4/M8）

**真实结果：** 从现有两文件混合批次开始，第一部决定→分析→确认→执行，第二部保留待办，
然后补正并执行第二部。原Task、2个来源/TaskItem和2条Result均保留。但首批后Task/Run接口
`total_items=1, completed_items=1`；两部全部完成后仍为1/1。Run同一响应的progress却为
`known_total=2, confirmed_success=2, results_total=2`，与顶层字段矛盾。当前Web运行详情
直接显示run.totalItems/completedItems，故不是仅测试内部对象的计数差异。

**原因和开发指导：**

1. `admit_manual_execution()`采用原Task时以len(selected execution items)重置总数/完成数；
   `ManualOrganizeExecutionService._task_after_item()`再次按本execution.items覆盖Task聚合。
   `_finish_execution()`虽保留剩余待办，却沿用该局部计数；schema55支持多次execution后仍
   保留了一次执行等于整个Task的旧假设。
2. execution保持自己的所选/完成/失败统计；kernel Task的总数/完成/失败/当前状态则根据整项
   工作的耐久具体来源及各自结果汇总，在同一owner/授权/取消边界发布。首次确认、后续确认、
   逐项结果和最终结算都不能覆盖成当次selected数量或归零已成功siblings。
3. 不以Result条数直接当文件数（attempt/附件可能多条），也不要求内部item ID恒等。保持已有
   真实来源/版本关系，成功/跳过/忽略/失败/partial/unknown/待办各自语义，当前状态和原attempt
   结果分开。Task/Run/API/Web/导出所表达的同一工作统计须一致，不靠前端显示补丁掩盖错误。
4. 扩展已新增两文件分批回归：首批后总数2、完成1、待办1；次批后总数2、完成2、两条独立
   Result、原结果不变，Task/Run接口与重开一致；保留失败/非成功与重复分析的直接影响对照。

### P1-3 — 等待时取消后，原文件仍被旧准入占用，不能重新整理（M5/M7/M8/M10）

**真实入口与结果：** Files新提交一部影片，Worker完成分析进入人工等待；从现有
`POST /api/v1/tasks/{id}/cancel`带当前expectedUpdatedAt取消，返回200。再运行4轮Task
Worker后Task=cancelled、item=cancelled、queue=settled、零名额、零Result/零Storage效果；
但关联discovery仍completed、cancel_requested=false。用户用新的requestId重新发起同一
未改动文件，得到409 `source_already_organizing`，被指回已经取消的旧工作。
这验证的是明确的新意图，不是继续已取消Task或自动重放。

**原因和开发指导：**

1. Task Center取消通过 `request_scheduled_task_control()`将discovery传入release，但
   `_publish_discovery_control_locked()`的取消UPDATE排除了COMPLETED/PARTIAL_SUCCESS。
   分析completed仅表示摘要就绪，顶层工作仍未确认；`_discovery_source_owners_locked()`仍把
   此类未执行准入当owner，形成Task已终结、发现准入仍占源的矛盾。
2. 在现有安全取消结算内统一Task/items、关联准入的当前可执行资格/取消事实及源占用判定。
   对已安全取消且无未确定效果的来源，新意图应能经过正常权限/版本/占用检查重新准入；
   不再让只读分析的completed阻止该协调。不删发现/计划/决定/结果，不伪造历史执行结果，
   不恢复旧Task或清掉CANCEL。允许实现采用一致的取消投影或权威资格查询，无需新恢复系统。
3. 保留in-flight当前调用、partial/unknown/已有效果的非重放与源保护；不能按Task终态无条件
   放行任何来源。Task Center和Files两个现有取消入口遵循同一应用语义/owner栅栏。
4. 新增上述人工等待→Task Center取消→新requestId重发→新Task合法准入的真实API回归，
   验原Task保持cancelled、原请求仍回原工作、无自动重放/效果；另保留在途/unknown取消对照。
   跨重开保持相同结果，不以增加“再次取消发现”或手动清内部记录作为普通用户操作。

### 已确认进展、B验证和限制

| 验证 | 当前候选实际结果 |
|---|---|
| manual engine、迁移、scope continuation模块 | 65 tests OK，runner4.573s；`focused.json/log` |
| 调度/栅栏、Operations workspace、Task pause/CLI、media library transfers | 119 tests OK，runner4.917s；`affected.json/log`；与上组无重叠，共184项 |
| 原混合识别卡住回归、分批完成/重开、Metadata候选同Task、取消/unknown | 在当前定向模块通过；计数与真实continue仍按上述复现阻塞 |
| Classification/Conflict决定→Files分析→确认→Result | 真实临时SQLite/Local Storage/合成Provider接口链通过，无新Job；`four-type-probe.py/log`；不声称Task Center入口已通过 |
| 原暂停专用准备接口/Worker | 请求退役及已删除执行接线的定向检查通过；不恢复历史暂停门禁 |
| P1-1/P1-2/P1-3现有入口复现 | `native-continue-repro.py/log`、`four-type-probe.py/log`、`cancel-source-ownership-repro.py/log`；均只用既有API，不改DB/claim或猜造入口 |
| 本次变更15个Python文件ruff format/check，完整Base..Head空白 | PASS，见`static.json`；manifest54文件 |
| 完整Python/Web/E2E/截图/wheel/容器/真实53/54→55升级与失败原子 | 产品阻塞后未继续，按workflow提前FIX；待修正候选由B完成，不记PASS、不交Developer跑全套 |

SQLite ResourceWarnings和CLI退役命令的预期argparse输出保留。没有增加retry/skip/timeout或
改产品/测试；未访问用户运行库、媒体和私有配置。本轮开始`2026-10-31 04:05:36 UTC`，
测试/探测/检查保守总上界30秒，小于总用时50%；命令、结果和计时见Evidence/review.json。
辅助跨Task冲突探测在合法新请求被源占用拒绝处停止，未将未达到的跨Task决定继承当作已复现
问题；本报告P1-3另以无需冲突决定的最简正常取消场景确认。完整T4仍待B验收。

### 后续交接与Slice全结果重评

同一Task完成上述三项并核对M1–M10；它们均是原Task交付，不新增范围或恢复暂停义务。
Developer只跑新增/变更/直接受影响测试后交接；B负责剩余原生/全量/升级/发布门禁，不先规划47.3。

| Slice outcome | 当前结论 |
|---|---|
| RO-1 | 手动生产链部分接入；Task Center继续仍新建Job，取消关联与聚合未完整 |
| RO-2 | 自动due/Run once/独立API-CLI引擎切换仍后续，未完成 |
| RO-3 | Files底层四类决定消费已有进展，真实Task Center入口未完成同Task闭环 |
| RO-4 | schema55支持分批，真实完整升级/Job迁移删除仍未完成，不扩大本Task范围 |
| RO-5 | 暂停专用产品接线已有修正；Task Center续作/统计/取消后的新意图仍有缺口 |

Task47.2保持FIX REQUIRED；Slice47仍ACTIVE，未达到交A关闭条件。
