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

本轮修正checkpoint为`2f682703ce899dee691eedfc910742b2a729c809`；Task Base、High/T4与schema55不变。
B对前候选`8f67b3a2`的独立审查确认上轮三项已修；完整浏览器验收暴露旧Worker测试接线和
暂停退役断言未更新。用户明确“你自己改一下得了”，授权本代理转Developer直接修同一Task。
接入真实Task engine后进一步复现：两部均无需人工决定时，ready来源没有TaskItem，首部执行后
Task提前完成，使未选第二部修正/再分析失败。本checkpoint同时修正该实际用户断链。

现有harness路由复用真实Task claim/fence与原服务，新/旧工作仍各自由原合法runner推进；
不新增验收平台。分析摘要、每个具体来源的TaskItem和文件计数同一事务发布，保持原历史、
单次授权、完成/uncertain不重放。受影响测试已通过，当前状态是开发交接，不是独立B PASS。

## Next action

独立B审查完整`c942c4b4..2f682703`及报告后继，核验M1–M10，完成剩余适用T4/真实Web/升级/
发布门禁并重评全部Slice结果。本代理本轮已实施修正，不自审PASS；不先规划47.3、不恢复
暂停、不切自动入口引擎、不扩张为工具重构。修正与直接受影响结果见末尾Completion Report。

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

## B Review Result — pre-fix checkpoint

Reviewed Head: `8f67b3a23586287d65d85194b5b5d95409ecf993`；产品checkpoint
`89090b078780d6b9a0ad9a1a48b37ae8eeb15be4`，二者差异只有TASK报告；完整Task Base..Head为63文件。
Decision: **FIX REQUIRED (修正前候选)**。未发现新增P0；上轮三项产品阻塞的B复现均通过。

| 上轮问题 | B实际回读 |
|---|---|
| 旧页面确认被重新分析后的计划替代 | 新旧preparationId不同；旧页409 preparation_stale，无授权消费/执行/变更 |
| 确认后原item深链404 | 原链接在准入前、准入后、执行后持续200，指向本条目的真实execution/Result |
| 未选第二部借用首部execution且无法继续 | 第二部保留自身stale摘要、execution=null、selected=[]；原Task安全分析202 |

### 本轮修正前阻塞与指导

1. **P1 — 真实浏览器验收仍接旧Worker。** `operations-inventory.python.spec.ts`完整44项，
   38通过、6失败。其中第12/13/14/16/35项的新Files工作只能由Task领取，既有
   `run_discovery_worker_once/for`与`run_manual_worker_once`却只调用旧runner；正常页面停在
   queued，尚未到达响应丢失/第二部修正等实质断言。让这些既有helper复用resident组装的
   `ManualTaskEngineWorker`和既有应用服务，保持真实领取/发布、历史runner与原行为断言；
   不新增路由/假状态、不恢复旧runner领取新工作、不放宽timeout/重试。
2. **同一验收配套 — 暂停退役旧期望。** 第18项调用remaining-scope-previews实际409
   `scope_continuation_retired`，仍期待`snapshot_unavailable`及恢复旧pin。按用户合同更新为
   退役拒绝；保留无变更、无新摘要/继续和历史可读，不创建专项暂停迁移/恢复门禁。

上述指导由用户随后授权本代理直接实施。开发时接通Task engine后的首次完整浏览器为
43通过/1失败：首部执行后第二部修改得到`analysis_rejected`。真实根因是ready且从未进入
四类审核的来源未建TaskItem；不是测试等待问题。该原M1/M4/M8交付缺口保持同Task修正。

### 修正前候选的独立证据（不能冒充新checkpoint全量验收）

统一原始证据目录：`.git/validation-evidence/b-task47.2-8f67b3a2/`，保留命令/cwd/耗时JSON、
日志、失败trace和桌面/窄屏截图。全部临时SQLite/Local Storage/合成Metadata，未访问用户媒体、
运行库或私有配置；无数据库改状态式探测。原有未跟踪文件全部保留，未纳入提交。

| 验证 | 实际结果 |
|---|---|
| Python完整unittest discover | 2974 tests OK，skipped=7；354.687s，`python-full.json/log` |
| Web typecheck/lint/format/build | 全通过；`web-full.json` |
| Web完整单测 | 88文件/1320项通过；`web-unit.log` |
| Web常规E2E | 253 passed；120.719s，`web-e2e.log` |
| operations-inventory真实Python E2E | 38 passed/6 failed；97.172s，`inventory.log`、`failed-browser-results/` |
| 实际新Task页面四类链 | Files→识别→Metadata候选→分类→冲突Rename→摘要→明确确认→同Task已完成Result；1536/380截图已查看，原目标保留 |
| wheel构建/安装smoke | 通过；SHA256 `0ac7cf770ea6dc16a5c21034f231bbedf723419d1b30acc1f9f18938d2dd9656` |
| 源码外已安装wheel原生API/Task Worker | site-packages导入，7个真实链/重开/取消/不确定保护用例通过；`installed-native.log` |
| 真实Task Base54→55及Slice Base53→55 | 两组schema rehearsal通过，保留及失败原子证据见日志 |
| Docker54→55升级/注入失败/恢复/API-Web持久性 | 使用Colima共享隔离临时目录后通过；初次默认tmp挂载失败保留，未记产品失败 |
| Docker发布安全 | 通过；`docker-security.log`，候选image `sha256:8bff6a05c054212f1ffb9c5922d35b848d10c25d913d47dcf9d3416a680f5fe8` |
| Docker empty-baseline | 4服务无媒体挂载健康/就绪；后续浏览器仍等待Task Center旧management/readiness区域而超时，未通过。未在Base复现，不声称Base失败，也不恢复已移走的旧Task Center区域 |
| ruff/compile/pip/examples/禁用依赖检查/空白 | 通过，无FFprobe/FFmpeg匹配；`quality.json`、`manifest.txt` |

B在确认上述门禁阻塞后未继续启动剩余TaskCenter visual/direct-files/automation浏览器组及
Docker restart。新版checkpoint改变了可执行输入；以上全量/制品/部署证据仅归属修正前候选。
独立B须对新版完成适用门禁；Docker empty-baseline旧页面假设先按当前已验收旅程核实，
不因验收脚本假设给本Task增加服务状态页面功能。ResourceWarnings与本地浏览器探针选择器
错误保留；临时页面探针的错误由正确入口/选择器回读核实，未包装成产品缺陷。

### 全部Slice结果重评（尚未关闭）

| Outcome | 当前边界与结论 |
|---|---|
| RO-1 | 手动调度/同Task执行已接；本轮补齐直接ready来源的TaskItem/独立计数，修正候选待独立验收 |
| RO-2 | 手动生产链已接；due/Run once/独立API-CLI切引擎仍后续，不算已完成 |
| RO-3 | 现有四类链复用，精确确认/原链接/逐项作用域修正已有证据；新候选仍须完成适用验收 |
| RO-4 | schema55加法与53/54升级演练已验证；完整Job迁移/删除仍后续，未完成 |
| RO-5 | 真实新Task页面四类→摘要→Result已走通；本Task/全部入口最终验收仍待B/A |

Slice47保持ACTIVE，不宣告Slice PASS/CLOSED，也不以可选工具整理追加Task。

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
- 根Task保持READY FOR B REVIEW，不自审PASS、不规划下一Task、不关闭Slice。
