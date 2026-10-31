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

当前产品候选为 `084ad15598a10b8cea12869b931e772f85e6f3b6`，Task Base不变。

- 已有Files原子Task/discovery/scheduling准入与resident engine，发现/分析/人工等待/确认执行
  初步链已接入，旧runner排除kernel-managed工作；不重复开发内核或另造队列。
- 共存容量原101项复现已纠正，保留共同容量判定、幂等与源占用；仍需原计划的完整竞争/部署验收。
- 本候选删除了CLI pause/resume命令、发现/Run once的按钮/动作及普通传输暂停/继续投影，
  新手动和普通操作的相应API有退役拒绝；这些局部结果不等于全部M10完成。
- 执行阶段CANCEL仍未正确安全确认，Task/execution会滞留running/claimed并占名额；真实两文件
  执行中取消已复现，详见B Review P1-1。
- 非kernel organizing Task仍保留专用legacy resume投影/提交Job分支，注释误称合同要求保留；
  这与用户已取消全部暂停且不要求暂停兼容系统的合同不符，详见P1-2。无需构造历史paused任务。
- M4完整四类同Task恢复/混合项历史和M8完整真实Web结果闭环仍待按合同交付/验收；不要把
  初始识别补正后的单个正向用例替代全部结果。due/Run once引擎切换及Job迁移删除仍为后续。

## Next implementation order

1. 先实施Scope 8/M10：整理和普通操作的Pause/从暂停继续从页面、DTO/API/CLI到专用活跃分支
   一并退役；取消、四类继续、等待/安全栅栏保留，不增加暂停任务迁移或兼容系统。
2. 验证并补齐M5取消闭环：从真实两文件执行中点击取消验证正常安全结算；保留已完成项与unknown
   效果保护，不继续走“修好暂停后可恢复”的旧路线。
3. 对照M1–M8补齐完整手动Task旅程，重点四类问题→分析→摘要→确认→逐项结果，以及同Task
   身份/历史/混合项、重开与Web结果。保留已完成实现，不为未证实的问题做额外重构。
4. Developer运行新增/变更/直接受影响测试与静态检查，更新准确checkpoint/结果/限制，交接
   READY FOR B REVIEW；此时B再独立审完整Base..Head并执行M9及共享T4门禁。

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
   .venv/bin/python scripts/schema_upgrade_rehearsal.py --base-sha c942c4b4b9d3abf105341e8163c1be2d95d9a671 --expect-schema 54 --expect-candidate-schema <actual-version>
   .venv/bin/python scripts/docker_upgrade_recovery_smoke_test.py --base-sha c942c4b4b9d3abf105341e8163c1be2d95d9a671 --base-schema 54
   ```

  `<actual-version>` 仅由实际实现决定，交接替换为确切数字。若 schema 改变，另验证真实 Slice
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

本轮用户通知开发完成，实际产品提交为 `084ad15598a10b8cea12869b931e772f85e6f3b6`。
该提交包含暂停退役的代码和测试，但尚无更新的Developer测试报告；B按真实代码/入口复核，
不因报告未同步添加产品阻塞，也不代填未提供的执行结果。前轮报告与审查均保留在Git。
修正后Developer给出准确checkpoint、受影响测试实际结果与剩余限制；不承担B全套发布门禁。

## B Review Result

```text
Reviewed Base: c942c4b4b9d3abf105341e8163c1be2d95d9a671
Reviewed Head: 084ad15598a10b8cea12869b931e772f85e6f3b6
Contract: c1e616113f87420d6f7411c3e6287ce81c1f5331
Decision: FIX REQUIRED — execution cancellation does not settle; pause retirement incomplete
Slice Required Outcomes / Surfaces all satisfied: NO
Next: SAME TASK FIX LOOP; preserve Task47.2 ID/Base/Goal and amended scope
Evidence: .git/validation-evidence/b-task47.2-084ad155/
```

B核对完整Base..Head的43文件：包含已审的内核生产接线/容量修复、用户范围修订和本次25文件
退役实现/测试；检查实际API/CLI与投影/dispatch，未只看删除行数或把“移除暂停”当作取消已正确。
本轮未改产品或测试，无角色例外；开始main/Reviewed Head，无tracked edits，既有untracked文件
保留不暂存。A-owned合同本轮未改。旧暂停修复义务仍按用户改约撤销，不恢复历史暂停验收要求。

### P1-1 — 执行中取消已接受，但Task一直运行/占容量（M5/M7/M8）

**实际入口与结果：** 从真实Files API提交 `One.2001.mkv` 与 `Two.2002.mkv`，沿现有识别决定、
分析、精确摘要确认准入执行。第一个真实Executor调用返回、结果尚未发布时，从现有
`POST /api/v1/tasks/{id}/cancel` 带当前expectedUpdatedAt取消，返回200。该边界模拟用户在第一部
正在整理时取消，不改claim、不篡改DB、不造路由。第一部成功并有1条Result，第二部未执行；
Worker返回且再运行3轮后：Task=running，queue=claimed，control=cancel，mutation_in_flight=false，
capacityHeld=true，manual execution=running，第二部=pending。已没有未确定的当前调用效果，
却未按接受的取消安全结算，任务和名额滞留。

**原因与开发指导：**

1. `ManualOrganizeExecutionService._run_worker_items()` 在下一项 `begin_existing_item()`
   遇到已接受CANCEL后抛TaskControlRejected；engine将其交 `_record_failure()`。该失败分支
   不能越过取消保护进行terminal settle，又吞掉异常，导致没有路径确认取消。
2. 在现有逐项执行的安全边界正常观察和确认CANCEL；当前Provider/Storage调用不中断。
   当前结果可靠落库后，保留已成功item/Result/附件效果，对尚未执行项按取消结算，并将Task、
   execution、逐项状态和调度资格协调持久化；释放名额与临时执行锁须遵守owner栅栏。
   不移除CANCEL保护，也不把正常取消改成技术失败来逃离当前状态。
3. 若当前效果仍未确定，保持marker/占用/检查和非重放；不以取消清除unknown。后续确认/分析/
   四类继续不能重新打开已取消工作。控制收尾和普通异常处理应区分，真实技术错误仍保留原因。
4. 在现有 `tests/test_manual_task_engine.py` 补这条两文件API回归，验证首项仅一次真实效果、
   余项无效果/取消、原Task和execution终结、名额释放、重开仍正确。另补queued/分析期间取消、
   当前结果写入失败/unknown与旧owner对照，不扩张到所有理论崩溃点。

### P1-2 — 仍保留非kernel整理任务的暂停恢复专用dispatch（M10 / AC-19）

这是明确接口退役范围的代码核对结论，不声称用户存在历史paused任务，也没有造此类数据探测。
用户已经取消整理和普通操作的Pause/resume-from-pause，并明确不需要暂停任务兼容执行系统。

但 `service_api.py` 的 `tasks/{id}/resume` 只对kernel-managed/ordinary Files拒绝，其余类型仍
调用 `_scope_continuations.submit()` 创建旧暂停剩余范围Job。`task_lifecycle_document()` 的
`execution.continuable` 分支仍发布resume动作/剩余范围preview；注释误称Contract要求保留旧暂停
恢复。`test_scope_continuation` 还将原API暂停改成直接coordinator.request_pause，维持该旧正向链。
此分支不是Recognition/Metadata/Classification/Conflict的决定后继续，不应据旧合同保留。

**开发指导：**

1. 所有整理/普通操作的暂停和从暂停继续请求统一走现有有界无效果退役拒绝；移除遗漏的
   legacy paused-scope resume执行dispatch和相应控制投影，CLI已删的命令保持退役。
2. 清理仅为上述暂停继续产品使用的活跃分支/接线/测试。共用的pin/source/权限/checkpoint与
   四类问题处理/分析/摘要服务继续复用；不要按resume字样批量删掉四类继续或配置Draft恢复。
   不新增历史暂停迁移/兼容executor，不为迁移历史自动改状态或清数据。
3. 从真实现有organizing入口形成正常非Paused工作，核对生命周期不再有暂停恢复动作，旧
   pause/resume请求无状态/队列/授权/Storage变更。无须先造paused记录来证明旧恢复可用。
   旧暂停正向用例按新合同改为退役拒绝，保留共用权限/历史/效果安全覆盖。

### 已确认的进展与B实际验证

| 验证 | 本轮结果 |
|---|---|
| 新手动engine、调度/栅栏/迁移、Operations workspace、Task pause/CLI模块 | 105 tests，OK；runner5.227s；`focused.json/log` |
| 两文件执行中取消的现有API复现 | 取消200，首项成功，Task/execution仍running且占1名额；`execution-cancel-repro.py/log`，约0.136s |
| CLI及新手动/普通操作的退役拒绝相关定向用例 | 在上述105项中通过；不能替代全部Web/旧整理投影退役 |
| 完整范围manifest/治理/空白/文档 | PASS；没有业务/测试编辑、push或历史改写 |
| 完整Python/Web/E2E/截图/wheel/容器/升级安全 | 产品阻塞确认后未继续，按workflow提前FIX；待修正候选由B完成，无豁免 |

SQLite ResourceWarnings及CLI拒绝旧命令的预期argparse输出均保留。所有运行使用合成临时SQLite/
Local Storage/fake Metadata，未用用户运行库、媒体或私有配置；没有新增/猜造入口、增加retry/
skip或放宽timeout。开始于 `2026-10-31 02:11:41 UTC`；测试/探测/检查保守总上界15秒，低于
本轮总时长50%，范围与计时记录在 `review.json`。旧候选76项结果不作为当前全量验收。

### 后续交接与Slice全结果重评

继续同一Task修正上述两项并核对M1–M10完整交付。原M4全部四类、混合项历史和M8真实Web闭环
不能由局部正向或按钮消失代替。Developer仅跑新增/变更/直接受影响测试后交接；完整T4与
原生/发布证据仍由B负责，不把本轮未跑全量当作Developer缺陷，不先规划47.3。

| Slice outcome | 当前结论 |
|---|---|
| RO-1 | 手动生产链部分接入，共存容量已有修复；执行取消仍阻塞 |
| RO-2 | 自动due/Run once/独立API-CLI引擎切换仍后续，未完成 |
| RO-3 | 完整四类同Task与效果/历史闭环待完整验收，未完成 |
| RO-4 | schema54/旧Job仍保留，历史转换和Job删除尚未做，非本Task新增范围 |
| RO-5 | 暂停退役部分完成，legacy resume专用dispatch尚存，取消/完整界面仍未闭环 |

Task47.2保持FIX REQUIRED，Slice47仍ACTIVE；不恢复用户已取消的暂停功能或专项历史兼容要求。
