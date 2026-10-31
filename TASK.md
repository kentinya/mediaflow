# Task 47.2 — Files 手动整理接入 Task 引擎与操作暂停退役

Authority: committed [SLICE.md](SLICE.md) at `c1e616113f87420d6f7411c3e6287ce81c1f5331`；
[Development Workflow](docs/development-workflow.md) 管理生命周期与测试分工；
[B experience](docs/agent-experience/task-planner-reviewer.md) /
[Developer experience](docs/agent-experience/developer-implementation-role.md)。

```text
Task ID: 47.2
Task Type: SLICE
Parent Slice: 47
Status: FIX REQUIRED
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

本轮B复核冻结候选`82a0739df84a60040dcf896b39c888ac6a0222ca`，完整Task Base..Head为64文件。
Task Base、High/T4与schema55不变。结论FIX REQUIRED；本轮只审查/验证并更新Task，不实施修复。

上轮两项复现现已得到修正：ignored来源不再进入同一Task的新摘要；初次分析全部技术失败、
最后一项ignore能够结算。但既有未结束条目在重新分析遇到技术失败时，失败没有同步到原条目，
仍会留下永久running/waiting_human的Task。这是当前唯一确认的P1，详见B Review。

## Next implementation order

1. 修正现有fenced plan/discovery发布事务：区分已结束历史与本次重新分析的未结束来源，
   将实际技术失败同步到该来源既有TaskItem，不因“已有item”而跳过；保留ID/精确源版本/pin、
   已保存决定、审核审计和兄弟历史，不能覆盖成功、ignored、cancelled或uncertain效果。
2. 复用既有计数、`task_work_status`和安全结算：无合法人工/机器工作时按真实结果结束；仍有
   待决定/待确认、queued/claimed或in-flight工作时不提前结束，不新增队列或第五恢复入口。
3. Developer补真实入口ready→重新分析失败及混合兄弟对照，交修改与直接受影响测试/风险；不要求Developer
   重跑全套。独立B复审完整Base..新Head，再完成适用M1–M10和T4/发布门禁。
   不新增通用恢复、暂停或第二套系统，不先规划47.3，不做验收平台重构。

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

## B Review Result — current candidate

Reviewed Task Base: `c942c4b4b9d3abf105341e8163c1be2d95d9a671`。
Reviewed Head: `82a0739df84a60040dcf896b39c888ac6a0222ca`。
范围：完整Base..Head的64文件，含已提交范围改约、生产链、消费者及测试退役/替换。
Decision: **FIX REQUIRED**，一项确认的P1；未宣告Task/Slice PASS。

本轮以B执行独立复核，未实施产品修复、未使用子代理。治理通过；main无既有tracked edits，
原有OS/log/图片/zip等untracked原样保留且不暂存；未访问用户运行库、媒体或私有配置。
已核对手动Task链、逐项历史/聚合、分析/确认/执行、取消、四类续作、暂停退役、新旧Worker共存
及API/CLI/Web消费者。大量删测对应用户已取消的暂停恢复旅程，不能视为这些旧旅程修复通过；
保留退役入口的拒绝/零效果/历史读取验证。当前原生浏览器组的部分四类seed仍走legacy链，
其44项通过不能单独证明新Task链的全部M4。本轮只报告真实已确认的可达问题。

### 已验证修正的前两项复现

- `ignored-source-repro.py`：同一Task重新分析只含Two；One保持ignored且源仍存在，最终
  partial_success，只有Two的1个Result、无Job。已忽略文件重新被实际整理的旧复现未再出现。
- `settled-analysis-repro.py`：最后一项ignore→partial_success/settled；初次分析全技术失败
  →failed/settled；均零Storage变更。此修正确实有效，但不覆盖下述既有条目的重新分析失败。

### P1 — 重新分析失败未同步原条目，Task仍永久等待

**真实操作：** Files提交一部影片，第一次分析正常，原TaskItem到waiting_confirm。用户通过
现有“重新分析”入口重算同一工作，此时Metadata Provider超时。新摘要该项为failed，原条目却
仍是waiting_confirm、无error；Task/API仍running，调度为waiting_human且不占容量，没有问题
类型和可执行工作。再运行真实Task engine五次仍不改变，零Result、零Storage变更。
这不是暂停任务、额外恢复类型或猜造入口；只替换synthetic Provider的正常返回/超时，未改DB/claim。

**根因：** `mediaflow/infrastructure/sqlite_runtime.py:publish_media_discovery_plan_with_plan`
在本次分析发布事务中按task/storage/path查到任何existing item就无条件continue。保留历史的
意图连同未结束条目一起跳过了，导致新失败只存在于摘要，原TaskItem仍被当作人工待确认项。
`manual_task_engine.py:_wait_for_human`的新“全部settled”判断因此无法触发。

**同Task修正与验收：**

1. 在既有claim/fence保护的原子发布事务内，区分已settled历史与本次精确来源的未结束条目；
   将实际技术失败发布到既有条目，保留ID/源版本/pin、决定/审计/attempt和兄弟结果，不笼统
   重置所有existing项，也不覆盖ignored/success/cancelled/uncertain。
2. 复用现有计数/聚合/安全结算；最后一个合法未结束来源失败后，Task/API按真实失败结束，
   failure stage/原因与安全下一步可回读。仍有合法待决定/待确认、queued/claimed或in-flight
   工作时保留正确等待/名额/效果保护，不新增恢复或调度系统。
3. 从现有Files/API+生产Task engine增加ready→重新分析超时回归，核对新摘要、原item、Task、
   API和重开一致、零变更/无Job；增加直接相关混合对照，另一待决定/待确认项不被提前结束，
   已成功/ignored兄弟保持原结果且不重放。Developer仅跑失败及直接受影响测试，B负责T4。

证据：`.git/validation-evidence/b-task47.2-82a0739d/reanalysis-failure-repro.py`及同名`.log`。
本问题阻塞M1/M4/M8的逐项状态、失败完成与用户结果闭环；其余门禁通过不能替代此交付缺口。

### 本轮门禁与限制

证据根：`.git/validation-evidence/b-task47.2-82a0739d/`，命令/结果清单见`review-summary.md`。
原始复现及完整测试日志保留在本地忽略存储，不宣称远程可访问。

| 验证 | 当前候选实际结果 |
|---|---|
| 治理、完整diff/manifest、ruff format/check、compileall、pip check、两份示例配置、diff空白 | 通过；398 Python文件格式检查通过 |
| Web typecheck/lint/format:check/build | 通过；build有常规大chunk提示 |
| Web完整单测 | 88文件/1320项通过；`web-unit.log`，103.61s |
| 真实Python浏览器operations-inventory组 | 44 passed；`browser-inventory.log`，71.50s；上述新/旧链证明范围限制保留 |
| 前两项真实入口复现 | 当前候选已修正；`ignored-source-repro.log`、`settled-analysis-repro.log` |
| 本轮重新分析失败复现 | 确认P1，原item不更新、Task不结束；五次空闲Worker推进无效 |
| 完整Python unittest discover | 确认P1后主动Ctrl-C停止，257.15s/exit130；未完成，无最终计数，不记PASS或产品断言失败 |
| 常规Web E2E、其余三组原生浏览器/截图QA、当前wheel/源码外消费者、53/54升级、Docker fresh/restart/security | 因已确认P1未执行；修正候选由B补齐适用门禁 |

Python中断时的ResourceWarnings/KeyboardInterrupt保留；未放宽timeout/retry/skip。旧候选全量、
wheel/Docker和Developer受影响测试不能替代当前T4。测试并行墙钟及本轮时间约束记录于证据清单；
发现P1即停止昂贵测试，后续仅完成代码/文档审查与受影响治理检查。

### M1–M10与全部Slice结果重评

| Task验收 | 当前结论 |
|---|---|
| M1 | 新工作同Task/无Job链已接；本次重新分析失败后不能结束，P1阻塞 |
| M2 | 有界发现/稳定性/附件范围不变；本轮无新增确认阻塞，全部当前原生门禁尚未完成 |
| M3 | ignored重入旧复现已修正，精确确认/权限/身份约束仍需完整当前T4；不据局部结果宣告通过 |
| M4 | 重新分析失败与原条目不一致，失败/独立历史闭环被P1阻塞；四类完整新链证明尚未完成 |
| M5 | claim/取消/未知效果边界已审；当前完整并发/部署门禁未完成，不记PASS |
| M6 | 新旧共享容量/原子准入仍在本Task；未完成当前全部共存门禁，不记PASS |
| M7 | ignored兄弟不重放旧复现已修正；其余安全续作要求保持，当前完整门禁未完成 |
| M8 | 新摘要failed、原Task/API永久running，实际用户结果被P1阻塞 |
| M9 | 当前完整Python、打包/升级/容器验收未完成；由B在修正候选上完成 |
| M10 | Pause退役及拒绝入口已有代码/测试；无新增暂停迁移义务，当前全量验收未完成 |

| Slice outcome | 当前结论 |
|---|---|
| RO-1 | 手动生产链已接；既有条目重新分析失败后的终态不实，未完整交付 |
| RO-2 | 手动链已接；due/Run once/独立API-CLI引擎切换仍为后续工作，本Task不承担切换 |
| RO-3 | 四类复用/同Task已实现接线；本次逐项失败/完成语义仍有缺口，完整新链验收未完成 |
| RO-4 | schema55加法在本Task范围；Job历史迁移/删除仍后续，当前升级门禁未完成 |
| RO-5 | Files/Task Center重新分析失败结果未闭环；其他新表面仍需完整验收 |

同Task修复这一项P1；Slice47保持ACTIVE，不规划下一Task，不修改A-owned合同/路线图/进度。
以下Developer报告是历史实施交接，本轮状态与结论以上文为准。

## Developer Completion Report — user-authorized direct fix

Checkpoint: `2f682703ce899dee691eedfc910742b2a729c809`。
Status: **READY FOR B REVIEW**。用户授权后本代理由B转为Developer实施，本段不是独立B复审。

**交付行为**

- 分析完成的原子plan/discovery发布事务内，为尚无TaskItem的具体来源创建耐久条目；ready项
  等待明确确认，技术失败保留失败事实。检查同一Task的live claim/token，再一并更新文件计数；
  任一步失败整体回滚。已有审核/尝试/效果/已完成兄弟项不覆盖，未新增表或恢复系统。
- 两部直接ready的影片先整理一部后，Task保持2项/完成1项并等待人工；第二部仍属于原Task，
  可以修改RecognitionType、再分析并单独确认；最终2/2、两个独立Result，首部不重放。
- 既有浏览器helper保留旧runner并接真实Task engine；按精确Task/execution关系及前后耐久
  execution记录回读本次推进结果，不凭时间/文件名猜关联、不报告上一子集为新执行。
- remaining-scope接口的旧pin恢复断言改为退役拒绝，保留409/零效果/无摘要/历史对照。

**修改与直接受影响测试（当前checkpoint实际结果）**

| 命令（仓库根，Web命令在web/） | 结果 |
|---|---|
| `.venv/bin/python -m unittest tests.test_manual_task_engine tests.test_task_scheduling tests.test_task_scheduling_fencing tests.test_task_scheduling_migration tests.test_media_discovery tests.test_manual_organize_preview tests.test_manual_organize_execution tests.test_processing_checkpoint` | 310 tests OK，32.551s；`ready-affected-python.log` |
| `.venv/bin/python -m unittest tests.test_task_center_recovery_lineage tests.test_scope_continuation` | 59 tests OK，7.146s；`adapter-python-final.log` |
| `npm run test:e2e -- --config=playwright.python.config.ts --workers=1 tests/e2e/operations-inventory.python.spec.ts` | 44 passed，1.3m；`inventory-final-fix.log`；原6项及真实首部完成后第二部修正均通过 |
| 修改3个Python文件ruff format/check、compileall；修改Web spec的Prettier、`git diff --check` | 通过；无timeout/retry/skip放宽 |

新增自动回归从既有Files API准入两部无需人工决定的来源，覆盖首次等待零变更、首部确认后
2/1计数/等待态、剩余项同Task再分析/确认、2/2独立Result、首部结果保留、无Job、重开一致。
为定位修正前原因，在当前依赖中只加载`8f67b3a2`原publish方法运行该新例，复现`2 != 0`；
这是精确旧方法对照，不冒称整个旧版本全量回归（`ready-subset-before-fix.log`）。

本轮自`2026-10-31 07:06:27 UTC`开始；截至`07:38:37 UTC`已用约1930秒。测试并行墙钟
区间合并约901秒（复用日志的起止区间连中间空档也保守计入），另计零碎检查保守不超过
940秒，低于本轮50%；`timing.json`保留测量口径。未为凑比例等待或重复已通过测试。

**交接限制**

- schema55未变；本轮只修改当前Task内4个执行/测试文件与TASK报告，未改A-owned合同/路线图。
- 本checkpoint未重跑完整Python/Web/新wheel/Docker及其余真实浏览器组；独立B负责，旧制品
  hash与旧2974项全量不能作为新checkpoint PASS。新回归总测试数相应增加。
- 已关闭本代理启动的两个临时原生页面服务器并清理其fixture；浏览器harness随测试正常退出。
- 本次开发交接当时为READY FOR B REVIEW；当前独立B判定见上文，不自审PASS、不规划下一Task、不关闭Slice。

## Developer Fix Report — P1-1/P1-2 second round

Status: **READY FOR B REVIEW**.本段由 Developer实施并交接,不是独立B复审,不自审PASS。
起点为记录B复审的 `4e7d99d7`;修复checkpoint见本次提交(真实源码身份由 `git log` 给出)。
Task Base、High/T4、schema55与父Slice边界不变;只修B已确认的两项P1,不新增恢复系统。

**修改行为**

- **P1-1(已忽略来源不再回到同一Task可执行范围)。** 原生(非 recovery)分析在冻结manifest
  求剩余scope时,除既有执行准入外,再按本Task自身耐久TaskItem的 `(storage_id, source_path)`
  settled disposition(ignored/success/failed/skipped/cancelled/dry_run)排除已结束来源,仍保留
  等待决定/等待确认的合法兄弟。确认/准入事务内对同一 `(task_id, storage_id, source_path)`
  断言未settled:一个stale summary或直接确认不能把已ignored项覆盖回pending/success,整笔
  确认回滚且保留原选择与结果。诚实修正“无剩余scope”提示,使其同时覆盖“已执行/已忽略/已失败”。
- **P1-2(全部条目结束后Task正确结算)。** 分析完成时若整个耐久条目集已全部settled且无
  queued/processing,复用 `task_work_status`/计数/claim settle安全结算(纯技术失败→Failed,
  纯ignored→保留非成功语义的PartialSuccess),不再永久Running/waiting_human。最后一项ignore
  在既有 `admit_recovery_request` 事务内、仅当该Task处于WAITING_HUMAN且无claim/control/
  in-flight effect时,按真实条目聚合结算并释放名额。仍有待决定/待确认/机器工作/in-flight时
  绝不提前结算;合法性取消、四类继续与源/权限/pin保护不变。

**B两项复现脚本在真实入口下的当前结果**

- `ignored-source-repro.py`:`REANALYZE`只含Two;`FINAL`为 `partial_success`,One保持`ignored`、
  源仍存在、仅1个Result、0 Job(日志`.git/validation-evidence/dev-task47.2-fix/p1-1-repro.log`)。
- `settled-analysis-repro.py`:`ALL_IGNORED`→`task=partial_success, queue=settled`;
  `ALL_TECHNICAL_FAILED`→`task=failed, queue=settled`(日志`p1-2-repro.log`)。

**新增自动回归(真实Files/Task/Executor链)**

`tests/test_manual_task_engine.py`新增4例:ignored来源经Provider正常新返回后不再进重分析summary、
仍保持ignored/源在/无新Result、兄弟正常完成并跨重开一致;最后一项ignore结算Task(API终态、
零变更、重复Worker无新增);纯技术失败结算Failed;同类兄弟仍待决定时ignore不得提前结算。

**修改与直接受影响测试(当前工作区实际结果)**

| 命令(仓库根) | 结果 |
|---|---|
| `.venv/bin/python -m unittest tests.test_manual_task_engine tests.test_task_scheduling tests.test_task_scheduling_fencing tests.test_task_scheduling_migration tests.test_media_discovery tests.test_manual_organize_intent tests.test_manual_organize_preview tests.test_manual_organize_execution tests.test_task_center_recovery_lineage tests.test_recovery_continuation tests.test_processing_checkpoint` | 401 tests OK,46.286s;`affected-python-1.log` |
| `.venv/bin/python -m unittest tests.test_automation_admission tests.test_automation_job_fencing tests.test_automation_definition_occurrence tests.test_v2_automation_run_once tests.test_processing_worker_readiness tests.test_automation_settings_resident tests.test_direct_file_transfers tests.test_media_library_transfers` | 230 tests OK,110.997s;`affected-python-2.log` |
| `.venv/bin/python -m unittest tests.test_manual_ignore{,_batch} tests.test_processing_checkpoint tests.test_scope_continuation tests.test_task_center_recovery_lineage tests.test_recovery_continuation tests.test_manual_operations{,_contract} tests.test_operations_task_center tests.test_processing_recovery_admission tests.test_task_pause_resume tests.test_task_persistence tests.test_task_retry tests.test_task_scope tests.test_v2_manual_organize tests.test_organize_preparation tests.test_preview_retirement tests.test_recovery_batch tests.test_manual_preview tests.test_organizer_rollback` | 307 tests OK,20.502s;`affected-python-3.log` |
| 4个改动Python文件 `ruff format --check`/`ruff check`、`compileall -q mediaflow tests scripts`、`git diff --check` | 通过;无timeout/retry/skip放宽 |

**交接限制与剩余风险**

- 本轮未跑完整Python/Web/新wheel/Docker/真实浏览器门禁,由独立B在修正候选上执行T4;
  旧候选日志与全量制品不能作为本checkpoint PASS。
- 确认/准入事务内的settled断言是纵深保护:经当前单操作员HTTP入口,新summary已不再包含
  ignored来源,因此该断言未构造产品级不可达场景的单测;主保护由真实入口回归覆盖。
- 只改本轮Task内3个执行文件、1个测试文件与TASK报告;未改A-owned合同/路线图,未推进Slice关闭。

## Developer Fix Report — P1 reanalysis-failure item sync (third round)

Status: **READY FOR B REVIEW**.本段由 Developer 实施并交接,不是独立 B 复审,不自审 PASS。
本轮起点为记录 B 复审阻塞的 `cf1a7d1d70376cd74e3bf4dcb016ef70167d7791`;修复 checkpoint 见本次提交
(真实源码身份由 `git log` 给出)。Task Base、High/T4、schema55 与父 Slice 边界不变;只修 B 已确认的
唯一 P1(既有条目重新分析技术失败未同步、Task 永久 running),不新增恢复/调度系统、不改范围。

**修改行为**

- 在既有 claim/fence 保护的 `publish_media_discovery_plan_with_plan` 原子发布事务内,对同一
  `(task_id, storage_id, source_path)` 的既有 TaskItem 不再无条件跳过:
  - `SETTLED_ITEM_STATUSES`(success/ignored/failed/skipped/cancelled/dry_run)保持原样,连同其决定、
    审计、attempt、Result 与效果一律不覆盖;
  - 新分析为 `PREVIEWED` 的既有项不改动(链接 plan 已携带新摘要);
  - 新分析为真实四类问题(已由 `publish_task_item_problem` 投影为对应 waiting 项)不改动;
  - 其余真实技术/规划失败则就地把该来源既有条目置为 `FAILED`/`analysis_failed` 并记录 `error`,
    保留 item_id、精确源版本/pin、occurrence/fingerprint 与兄弟历史,随后沿用既有
    `_refresh_task_item_counts_locked` 与 `manual_task_engine._wait_for_human` 的安全结算。零 Storage
    变更、无新 Job、无第二套队列。
- 新增纯函数 `manual_preview_plan_problem(plan)`(domain/manual_organize_preview.py),按共享分析
  自身写入 plan 的字段识别四类原生问题(recognition/metadata/metadata_correction/classification/
  conflict);Provider 错误、缺策略、source admission、naming/storage 失败与 capability gap 均返回
  `None`,因此只有真实技术失败会同步到既有条目,不误伤任何四类人工等待。

**B P1 复现脚本在真实入口下的当前结果**

- `reanalysis-failure-repro.py`:重新分析超时后 `task=failed, queue=settled`,既有条目
  `failed/analysis_failed/error=synthetic upstream timeout on explicit re-analysis`,零 Result、零
  Storage 变更、无 Job;再跑 5 次空闲 Worker 不变(日志 `reanalysis-failure-repro.log`)。
- `ignored-source-repro.py` 与 `settled-analysis-repro.py` 保持已修正结果(partial_success/failed +
  settled、零变更),日志同名。

**新增自动回归(真实 Files/API + 生产 Task engine)**

`tests/test_manual_task_engine.py` 新增3例:ready 来源重新分析超时→既有条目 FAILED、Task/API 结算
Failed 且重开一致、零变更/无 Job;两部中成功兄弟保持 SUCCESS+Result/源效果、另一部超时→
PartialSuccess/2-1-1、不重放;一待决定 + 一已决定重新分析超时→已决定项 FAILED、待决定兄弟仍
WAITING_RECOGNITION 且保持 pending 复核与等待,不被提前结束。三例在未打补丁的 HEAD 源码上分别复现
`waiting_confirm != failed`(已用 `git checkout --` 精确对照,修复后恢复)。
`tests/test_manual_organize_preview.py` 新增 `ManualPreviewPlanProblemTests` 两例锁定四类分类与
技术/ready 反向判定。

**修改与直接受影响测试(当前工作区实际结果)**

| 命令(仓库根) | 结果 |
|---|---|
| `.venv/bin/python -m unittest tests.test_manual_task_engine tests.test_manual_organize_preview tests.test_task_scheduling tests.test_task_scheduling_fencing tests.test_task_scheduling_migration tests.test_media_discovery tests.test_manual_organize_intent tests.test_manual_organize_execution tests.test_task_center_recovery_lineage tests.test_recovery_continuation tests.test_processing_checkpoint` | 406 tests OK,45.163s;`affected-python-1.log` |
| `.venv/bin/python -m unittest tests.test_automation_admission tests.test_automation_job_fencing tests.test_automation_definition_occurrence tests.test_v2_automation_run_once tests.test_processing_worker_readiness tests.test_automation_settings_resident tests.test_direct_file_transfers tests.test_media_library_transfers` | 230 tests OK,111.284s;`affected-python-2.log` |
| `.venv/bin/python -m unittest tests.test_manual_ignore tests.test_manual_ignore_batch tests.test_scope_continuation tests.test_operations_task_center tests.test_processing_recovery_admission tests.test_task_pause_resume tests.test_task_persistence tests.test_task_retry tests.test_task_scope tests.test_v2_manual_organize tests.test_organize_preparation tests.test_preview_retirement tests.test_recovery_batch tests.test_manual_preview tests.test_organizer_rollback` | 342 tests OK,22.006s;`affected-python-3.log` |
| 3 个 B 复现脚本(真实 Files/API/engine) | 全部符合预期;三个同名 log |
| 4个改动Python文件 `ruff format --check`/`ruff check`、`compileall -q mediaflow tests scripts`、`git diff --check` | 通过;`quality-gates.log`;无timeout/retry/skip放宽 |

证据根:`.git/validation-evidence/dev-task47.2-p1-reanalysis/`(本地忽略存储,不宣称远程可访问)。

**交接限制与剩余风险**

- 本轮未跑完整 Python/Web/新 wheel/Docker/真实浏览器门禁,由独立 B 在修正候选上执行 T4;
  旧候选日志与全量制品不能作为本 checkpoint PASS。
- 四类识别由 plan 文档派生而非读取 `_PreviewOutcome.problem`;单测与技术/ready 反例已锁定当前共享
  分析写入的字段形状。若后续共享分析新增第五类原生问题或改变 plan 字段,该派生需同步更新(现有
  `publish_task_item_problem` 与 plan 文档仍一一对应,未发现偏离)。
- 只改本轮 Task 内 2 个执行文件、2 个测试文件与 TASK 报告;未改 A-owned 合同/路线图,未推进 Slice 关闭。
