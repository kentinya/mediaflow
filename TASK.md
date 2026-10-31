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

当前产品候选为 `acaed9fa485bca7543e0f6fea57487b7e8831303`，Task Base不变。

- Files原子Task/discovery/scheduling准入、resident engine和共存容量修复已接入；不重复开发内核。
- 上轮执行中CANCEL滞留已修正：真实两文件链中第一项结果保留，未开始项取消，原Task和execution
  结算cancelled，名额释放。unknown保持marker/占用/不重放的定向用例也通过。
- Task的pause/resume路由已统一退役，旧resume→Job提交及生命周期resume投影已删；但暂停专用
  remaining-scope preparation接口与旧Worker scope-continuation执行dispatch仍在，M10未完成。
- 新手动混合批次中，只补正第一项再分析，会将另一项现有识别待办改成processing并滞留。
  摘要已有1项ready，确认却409；剩余项Save也409，持续占容量，阻塞M3/M4/M6/M8。
- 完整四类同Task恢复、混合项历史/结果和真实Web闭环仍需按M1–M10交付/验收；不能用全部
  文件一次补齐的单个正向用例替代独立项处理。due/Run once引擎切换及Job迁移删除仍为后续。

## Next implementation order

1. 按B Review P1-1修正重复分析的逐项问题发布：已有未解决待办保持可操作的人工等待，
   使“只补正一部→分析→确认就绪子集”走通；接着验证成功项不重放、剩余项仍可在原Task继续。
2. 按P1-2收完暂停专用remaining-scope preparation和Worker执行接线；保留通用历史读取、
   四类问题继续与取消，不新增暂停任务迁移/兼容系统，不因本项删除所有旧Job。
3. 对照M1–M10补齐真实手动旅程与直接受影响回归，保留本轮已修正的取消/unknown/容量保护。
   不为未证实的问题做额外重构，不为全部理论中断点新增恢复承诺。
4. Developer仅运行新增/变更/直接受影响测试与静态检查，报告准确checkpoint/实际结果/限制，
   交接READY FOR B REVIEW；B在修正候选上独立审完整Base..Head并完成剩余T4验收。

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

本轮用户通知开发完成，实际产品提交为 `acaed9fa485bca7543e0f6fea57487b7e8831303`。
本提交增加执行中取消的协调结算和两项真实执行/unknown回归，并删除旧resume提交与生命周期
投影。尚无同步的Developer测试报告；B依据实际代码与入口审查，不据报告缺失新增产品阻塞，
也不代填Developer未提供的结果。修正后交准确checkpoint、受影响测试实际结果与剩余限制；
完整T4与发布证据仍由B负责。前轮交接/审查保留在Git。

## B Review Result

```text
Reviewed Base: c942c4b4b9d3abf105341e8163c1be2d95d9a671
Reviewed Head: acaed9fa485bca7543e0f6fea57487b7e8831303
Contract: c1e616113f87420d6f7411c3e6287ce81c1f5331
Decision: FIX REQUIRED — mixed-item analysis stalls; dedicated paused-scope execution remains
Slice Required Outcomes / Surfaces all satisfied: NO
Next: SAME TASK FIX LOOP; preserve Task47.2 ID/Base/Goal and amended scope
Evidence: .git/validation-evidence/b-task47.2-acaed9fa/
```

B按完整Base..Head的47文件manifest复核：承接既有生产接线/容量审查，检查本次取消事务、
manual execution/engine/claim发布、暂停控制及测试/浏览器删改；没有将局部通过等同全部交付。
本轮只更新TASK，不改产品/测试/A-owned合同。开始main/Reviewed Head，无tracked edits；
既有OS/log/图片/压缩包等untracked保留、不暂存。没有push、历史改写或子代理。

### P1-1 — 只补正部分文件后，分析卡住，就绪文件和剩余待办都不能继续（M3/M4/M6/M8）

**用户场景：** Files选两部影片，系统都提示选择识别类型。用户先给第一部选好类型，点击分析，
想先整理第一部，稍后再补第二部。这是已有的就绪子集确认与逐项处理，不要求一次解决所有文件。

**真实入口和结果：** 用现有Files admission、TaskItem recovery/decision、discovery/analyze及
preview/execute接口，真实临时SQLite、Local Storage与合成Metadata，未篡改DB/claim或构造路由。
摘要回读第一部previewed、第二部blocked；但TaskItem第二部变为processing/analysis。
第一次驱动12轮后再驱动12轮，queue仍queued/analysis且占1名额；确认第一部返回409
`task_not_waiting`。再尝试第二部原有识别决定返回409 `decision_rejected`，再次分析也409。
无Storage变更、无Result，刷新/重复Worker不能使该链前进。复现脚本与原始日志在Evidence目录。

**原因与开发指导：**

1. `SQLiteTaskRepository.publish_task_item_problem()` 对既有待办先独立提交PROCESSING，随后
   `RecognitionReviewService.create()`按同一item生成相同review ID、再次INSERT已有review，
   触发review唯一约束；`ManualOrganizePreviewService._publish_problem()`吞掉异常后仍发布摘要。
   engine `_wait_for_human()`将遗留PROCESSING视为机器工作反复入队，无法进入WAITING_HUMAN。
   不要通过放宽execute的WAITING_HUMAN校验、取消owner栅栏或删除review历史绕过问题。
2. 在现有逐项问题发布边界正确处理重复分析：同一源版本/同一未解决问题复用合法现有review，
   保留人工等待及其可用决定；若问题确实变化，按现有证据/版本规则建立准确关系。问题证据、
   waiting item与分析发布须一致，不先耐久留一个无法完成的processing过渡；失败应有界可见，
   不能吞错后展示一个实际上无法确认的就绪摘要。保留成功/ignored/skipped/partial/uncertain，
   不重开已结束项、不重置已保存决定或给内部item ID增加恒等要求。
3. 本场景分析完成后，没有实际机器工作时原Task进入人工等待、释放名额；第一部可按摘要显式
   确认执行，第二部待办仍可操作。只执行本次已确认子集，不迫使用户先解决所有文件。
4. 接着走完原M4：第一部Result持久化后，第二部保存决定→分析→新摘要→显式继续仍回同Task，
   第一部不重放、不覆盖Result/attempt/附件效果；顶层Task不能仅因某个subset执行结束就丢掉
   剩余待办，文件数按真实来源而非本次selected数量。这里是修复后的原验收路径，未将尚未跑到
   的后续阶段宣称为第二个已复现缺陷；取消与unknown保护继续有效。
5. 在已有 `tests/test_manual_task_engine.py` 增加上述真实两文件回归：首次两个待办→只补一项→
   分析后ready1/blocked1、人工等待/零名额→执行第一项→补第二项→在原Task完成，检查真实
   效果、独立历史、文件数及重开回读。四类中存在相同重复发布模式的部分一并按现有入口核对，
   不另造恢复系统。Developer跑该失败场景、新增/改动和直接受影响模块；真实Web由B按原M8验收。

### P1-2 — 暂停控制已拒绝，但暂停专用剩余范围准备/执行接线未退役（M10 / AC-19）

上轮指出的 `/tasks/{id}/resume`→submit Job与生命周期resume投影已删除，确认该局部修正。
但 `service_api.py` 仍注册 `POST /api/v1/tasks/{id}/remaining-scope-previews`，继续调用
`_operations_run_remaining_scope_preview()`→`admit_recovery_preparation()`；函数和eligibility
明确只为paused source Task恢复剩余范围。`final_cli._run_queued_workflow()`仍分派
`AutomationCommand.SCOPE_CONTINUATION`→`_run_scope_continuation()`执行旧暂停续作。
当前变更还保留其“separate zero-mutation review remains available”正向断言。
这是专用活跃接线的静态合同核对，不声称用户有历史paused工作，也未新增/制造历史paused场景
进行探测。它不是四类识别/元数据/分类/冲突处理后的继续；仅去掉resume按钮仍未完成明确退役。

**开发指导：**

1. 退役上述暂停专用remaining-scope准备请求与活跃执行dispatch，使旧请求有界拒绝且无
   discovery/intent/preview/authorization/Job/Task或Storage变更；不让遗留命令启动兼容executor。
   清理仅支撑这条暂停产品路径的接线/投影/测试，检查Web API client与现有Worker接线的直接依赖。
2. 保留历史scope-continuation关系/Task/Result/原pin的通用只读回读；复用代码中的通用源验证、
   历史去重、权限/效果保护和四类问题分析不能按scope/resume名称批量删除。不迁移/重标旧记录，
   不删除Job数据库/全部Job系统，不恢复或新增暂停整理兼容执行。
3. 从已有正常整理入口核对暂停相关动作不再发布；现有旧专用请求明确无效果拒绝。用现有
   ordinary Copy/Move及四类继续用例核对直接影响。无需构造暂停记录证明能恢复，也不把历史
   暂停迁移/续作当必过门禁。保留本轮真实取消与unknown回归。

### B实际验证与限制

| 验证 | 本轮实际结果 |
|---|---|
| manual engine、调度/栅栏/迁移、Operations workspace、Task pause/CLI、scope continuation、media library transfers | 234 tests，OK；runner14.595s，外层14.794s；`focused.json/log` |
| 上轮执行中取消复现 | CANCEL200；首项success/1条Result，余项cancelled，Task/execution cancelled、queue settled、零名额；`previous-cancel-repro.py/log`，0.142s |
| 新混合批次真实API复现 | ready1/blocked1；未解决item遗留processing、反复queued且占名额，确认/后续Save/分析均409，零效果；`mixed-selection-repro.py/log`，最终运行0.152s |
| 完整范围manifest、治理、空白与文档 | PASS；见`review.json`；不据旧状态/报告缺失增加阻塞 |
| 完整Python/Web/E2E/截图/wheel/容器/升级安全 | 产品阻塞后未继续，按workflow提前FIX；待修正候选由B完成，无豁免，不转交Developer全套门禁 |

SQLite ResourceWarnings及CLI退役命令预期argparse输出保留。没有改测试断言/skip/retry/timeout；
定向旧测试通过不等于暂停专用系统应保留。所有运行使用既有合成fixtures/临时SQLite/Local Storage，
未读用户运行库、媒体或私有配置。开始`2026-10-31 02:57:37 UTC`；测试/探测/检查保守总上界
30秒，低于本轮总用时50%，准确命令和计时见Evidence；未跑全量不记PASS。

### 后续交接与Slice全结果重评

同一Task修正两项并核对M1–M10。完整四类、混合批次历史和真实Web闭环仍是原交付，
没有因取消暂停而免除；也不扩大为任意历史恢复。Developer交受影响结果后由B验收，不先规划47.3。

| Slice outcome | 当前结论 |
|---|---|
| RO-1 | 手动生产链部分接入、容量/执行取消已有修正；混合批次分析仍阻塞 |
| RO-2 | 自动due/Run once/独立API-CLI引擎切换仍后续，未完成 |
| RO-3 | 完整四类同Task尚未完成，当前混合项真实链阻塞 |
| RO-4 | schema54/旧Job仍保留，历史转换与Job删除尚未做，不扩大本Task范围 |
| RO-5 | pause/resume控制/投影已有修正，暂停专用剩余范围路径尚存，完整界面闭环待验收 |

Task47.2保持FIX REQUIRED，Slice47仍ACTIVE；不恢复暂停，不宣告Task/Slice通过。
