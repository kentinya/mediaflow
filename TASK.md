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

当前审查候选为 `a7db756e963aef4592187d4a36e0c835d1da6858`；产品提交`8f66d1cc`，
后继仅改报告。Task Base、High/T4及schema55不变。

- 前轮三项局部修正已复核：原Task现在回读business_problem及prepared摘要；跨Task旧Rename
  不再套用，新任务有独立pending conflict；失败子集不再终结另一文件的合法处理。
- 新native摘要ID只绑定discovery，确认又读取其最新preview：旧页面确认可执行重新分析后的
  另一份计划。真实两页面场景已在临时Storage执行到新版未审阅的目标，阻塞M3精确意图。
- 普通精确确认会删除原分析TaskItem，原处理链接在Worker运行前即404；新ID能读不等于旧
  深链/原历史已保留。M4已明确允许内部ID变化且要求旧链接可读，无需另行确认“ID恒等”。
- 两部均ready只确认第一部后，第二部也被native摘要投影为confirmed并关联第一部execution；
  第二部仍waiting_confirm/真实文件存在/无Result，继续却409 uncertain_effects，原位处理断链。
- 三项详见B Review，均在原Task范围。自动入口切引擎、Job迁移/删除仍为后续；完整原生/T4/
  升级发布验收由B承担，不以新增Developer全套测试或用户额外授权代替产品修正。

## Next implementation order

1. 按P1-1把native摘要的确认与精确回读绑定到用户实际审阅的不可变preview/计划、所选scope和
   影响范围；旧页面不得在后台改绑新计划执行。复用现有计划/授权记录，不造第二套准备系统。
2. 按P1-2保留原TaskItem历史与旧链接：可以复用ID，也可以版本化并建立明确耐久关系，但不能
   删除旧行后仅要求页面改用当前ID。补原页面确认成功/未知响应后的精确回读。
3. 按P1-3分别表达本次已确认子集和仍待确认的来源；每个文件只关联真正包含自己的execution，
   未选项在原Task继续，保留真实unknown保护、完成项不重放和准确统计。
4. Developer交上述真实入口新增/变更/直接受影响结果与限制；B再独立审完整Base..Head并完成
   M1–M10、真实Web与T4/升级/发布门禁。不先规划47.3，不恢复暂停。

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

Checkpoint: `8f66d1cc243746bbbc849842ee5ddbc63760f673`(Base `c942c4b4` 不变),
Status READY FOR B REVIEW。完整 T4/升级/发布与 PASS 判定仍由 B 负责,本报告不宣称 STOP。

**变更行为(3 项 B Review 阻塞)**

1. **P1-1 原生摘要/确认接入 Task Center(Business problem, 非 technical history)。**
   `mediaflow/infrastructure/sqlite_runtime.py` 新增共享谓词
   `_native_current_decision_kind_sql`/`_native_pending_confirmation_sql`:一个
   kernel 管理的 TaskItem 处于 `waiting_confirm`、其 Task 有已链接的
   `media_discoveries.organize_task_id`+`preview_id`、且该 item 自身有最新
   RESOLVED 四类决定时,归入对应四类 `business_problem`(不再落入 technical
   history);新增 additive 索引 `media_discoveries_organize_task`,旧库开库即补,
   无版本跳变。`mediaflow/application/manual_recovery_continuation.py` 新增
   `native_preparation_summary`/`confirm_native_preparation`/`prepare_native_summary`:
   直接投影 Task 自己那条已有 Files discovery/Preview 为可回读摘要,并用**既有**
   `ManualOrganizeExecutionService.begin_web_execution`(同一 Files execute 服务)
   在**同一 Task** 上确认 ready subset、重新登记执行;不新建 Job、子 Task、第二套
   preparation 或兼容 executor,确认前零变更、不消费执行授权。`service_api.py` 在
   `GET .../recovery`、`POST .../recovery/decision`、`POST .../recovery/prepare-summary`、
   `POST /manual-recovery-preparations/{id}/confirm` 按 `native:` 前缀分流;错 principal
   以 403 拒绝;满容量/陈旧摘要/陈旧 checkpoint 均有界拒绝且保留决定/摘要/结果。
   Web `TaskItemRecoveryPanel` 在已有持久摘要时不再重复显示“生成计划摘要”按钮。
2. **P1-2 决定消费限定本 Task/来源。**
   `_native_review_decisions` 只消费 `confirmation.task_id == 当前Task` 且
   `item_id` 属于当前 Task 的 RESOLVED conflict 决定;`ManualOrganizePreviewService._resolve_conflicts`
   的 plan_id 兜底(plan_id 由 source/target 确定性生成,跨 Task 会碰撞)在
   `problem_task_id` 存在时也只接受同一 Task 的 confirmation。不同 Task/新请求不再
   因路径相同继承已取消旧 Task 的 Rename;本 Task 自己的合法决定仍正常消费。
3. **P1-3 逐项独立结算 + 整项聚合。**
   `ManualTaskEngineWorker._finish_execution`:任一 terminal execution(含 FAILED)只
   要在途 sibling 非 PROCESSING 即保留为人工等待(零名额)而非终结整项;仍有
   PROCESSING sibling 则保名额继续;全部来源 settled 时用
   `task_work_status(全部 TaskItem)` 汇总,后续成功不再抹掉先前 failed/partial;
   CANCEL 语义保持原样。

**受影响测试(实际命令与结果,cwd 仓库根)**

| 命令 | 结果 |
|---|---|
| `.venv/bin/python -m unittest tests.test_manual_task_engine tests.test_task_scheduling tests.test_task_scheduling_fencing tests.test_task_scheduling_migration` | 88 tests OK(含 4 个新回归:新 Task 独立冲突、失败子集保留 sibling、native 摘要确认、Metadata 候选 native 确认;均在真实 API/SQLite/Local Storage/Executor 链上) |
| `.venv/bin/python -m unittest tests.test_media_discovery tests.test_manual_organize_intent tests.test_manual_organize_preview tests.test_manual_organize_execution tests.test_task_center_recovery_lineage tests.test_recovery_continuation tests.test_processing_checkpoint` | 305 tests OK |
| `.venv/bin/python -m unittest tests.test_automation_admission tests.test_automation_job_fencing tests.test_automation_definition_occurrence tests.test_v2_automation_run_once tests.test_processing_worker_readiness tests.test_automation_settings_resident tests.test_direct_file_transfers tests.test_media_library_transfers` | 230 tests OK |
| `tests.test_operations_task_center tests.test_operations_run_detail tests.test_operations_run_inventory tests.test_operations_workspace tests.test_recovery_batch tests.test_task_pause_resume tests.test_scope_continuation tests.test_operator_ui tests.test_operator_observability tests.test_restart_fault_boundary tests.test_automation_run_once tests.test_automation_definition_execution tests.test_automation_unattended_grant tests.test_automation_workspace_read_model` | 424 tests OK |
| `tests.test_task_persistence tests.test_task_retry tests.test_task_scope tests.test_processing_recovery_admission tests.test_organize_preparation tests.test_v2_automation_operations tests.test_v2_manual_organize tests.test_manual_operations tests.test_manual_operations_contract tests.test_manual_ignore tests.test_manual_ignore_batch tests.test_direct_file_operations tests.test_batch_cli` | 251 tests OK |
| 补充:`tests.test_conflict_resolution tests.test_manual_organize_preview tests.test_recovery_continuation tests.test_task_center_recovery_lineage` | 118 tests OK |
| 迁移/索引:`tests.test_task_persistence`(新增断言 `media_discoveries_organize_task` 开库后存在);`tests.test_migration_rehearsal tests.test_sqlite_backup tests.test_sqlite_restore tests.test_runtime_lease tests.test_runtime_files_browser` | 28 + 25 tests OK |
| `web: npm run test -- run ...OrganizeRouter/OrganizeDiscoveryPage/OrganizeCreationPage/TaskItemRecoveryPanel/OperationsInventory/LibraryFileOperationsDialog` | 6 files, 101 tests OK |
| `web: npm run typecheck` / `npm run lint` / `npm run format:check` | 全部 exit 0 |
| `.venv/bin/ruff format --check mediaflow tests scripts` / `.venv/bin/ruff check mediaflow tests scripts` / `.venv/bin/python -m compileall -q` / `python3 scripts/check_governance.py` / `git diff --check` | 全部通过 |

B 的三项复现脚本在该候选上的真实结果:cancel 旧 Task 后新 Task **不再**自动沿用 Rename,
而是生成自己的 `pending` 冲突;第一部来源执行前消失后整项仍 `running`/`waiting_human`、
第二部 `recovery/continue` 返回 202;同 Task 分析后 `GET .../recovery` 返回
`recoveryKind=business_problem`、`manualRecoveryAvailable/AnalysisReady=true`、
`manualRecoveryPreparation.status=prepared`、`manualRecoveryLink=null`、零 Job、零变更。

SQLite ResourceWarning 与历史相同,未新增 skip/retry/超时放宽,未访问用户运行库、媒体或私有配置。
未运行 B 的全量 Python/Web/E2E/截图/wheel/容器/53→55 升级门禁。

**剩余风险与已知限制(交 B 判定,非本地 PASS)**

- 确认执行时既有 Files 执行准入会把分析包装 TaskItem 替换为同源执行 TaskItem(不同
  item_id,既有 `admit_manual_execution` 行为);按当前 item id 仍可回读同一确认执行
  (`manualRecoveryPreparation.status=confirmed`+execution_id),但旧 item id 本身
  404。B 若把“旧 item 深链恒等可读”视为 P1-1/M4 必过,需要另行确认范围(本次未改
  既有“一源一 item”的准入设计)。
- `prepare_native_summary` 的 `actor` 仅用于校验,无副作用;native confirm 按 discovery
  actor 做 principal 隔离。
- 未验证新真实 Web/截图/wheel/容器/升级;未复跑 53/54→55 迁移。

## B Review Result

```text
Reviewed Base: c942c4b4b9d3abf105341e8163c1be2d95d9a671
Reviewed Head: a7db756e963aef4592187d4a36e0c835d1da6858
Product checkpoint: 8f66d1cc243746bbbc849842ee5ddbc63760f673
Contract: c1e616113f87420d6f7411c3e6287ce81c1f5331
Decision: FIX REQUIRED — mutable native confirmation; old item readback lost; unselected sibling shown confirmed
Slice Required Outcomes / Surfaces all satisfied: NO
Next: SAME TASK FIX LOOP; preserve Task47.2 ID/Base/Goal and amended scope
Evidence: .git/validation-evidence/b-task47.2-a7db756e/
```

B独立核对完整Base..Head的62文件manifest，承接前轮生产接线/容量/取消/退役等审查，检查
本轮native准备/确认/回读、决定收集、聚合、SQL四类归属和测试删改。8f66d1cc..a7db756e仅
TASK报告，执行输入不变；本轮验证均在Reviewed Head。main起点无tracked edits，既有OS/log/
图片/ZIP等untracked原样保留、不暂存；只更新TASK，无产品/测试/A-owned合同编辑、push、
历史改写或子代理。没有猜造路由、修改DB/claim或读取用户运行库/媒体/私有配置。

**对已知限制的范围核对：** 原Scope 5、M4及V2-TASK-003明确：内部TaskItem ID可以复用或
版本化，但须保留耐久历史关系、旧链接与准确文件数。要求旧item深链可读不等于要求ID恒等。
Developer报告的“旧item ID 404”因此是原交付未完成，不需要用户再次授权或A改约；可以选择
合适的兼容读取/保留关系实现，不要求另造恢复系统或合并历史Task。

### P1-1 — 旧页面的确认被绑定到新计划，实际执行了用户未审阅的目标（M3/M8）

**实际用户操作与结果：** 在同一新Files Task处理同名冲突，选择Rename，原Task Center
读到prepared摘要A，目标为`One (2001) (1).mkv`。该页面保持打开；另一个文件到达此目标，
用户在另一页面对同Task显式重新分析，得到摘要B，目标为`One (2001) (2).mkv`。
两份preview ID不同，但`preparation_id=native:<discovery_id>`相同，selected item IDs也相同。
旧页面按A的准备ID/选择提交现有confirm接口，返回202；Task Worker真实执行了B，将来源
移动到`(2).mkv`。原`(1).mkv`仍为外部已有内容。本轮只在合成临时Storage执行，未改用户媒体。

**原因与开发指导：**

1. `native_preparation_id()`只编码discovery；`confirm_native_preparation()`从该discovery
   当前preview重读计划，再把当前intent_version交给begin_web_execution。确认并未携带/证明
   用户实际审阅的那份preview/计划。底层执行服务虽精确验证B，也不能证明用户审阅并确认过B。
2. 确认对象必须耐久绑定不可变preview/精确计划、所选文件、源版本/pin与影响scope；可以用
   已有不可变计划身份构造native引用或让请求显式携带被审阅身份，再按现有乐观并发机制检查。
   不能仅以discovery、当前intent版本或“最新计划”替代被审阅计划，也不需新建Job/Task或
   第二套preparation表。重读同一摘要身份稳定，重新分析后的新摘要不能复用旧确认资格。
3. 原计划已被替代、来源/摘要变化时，旧确认必须在创建/消费授权和执行准入前有界拒绝，保留
   原选择、摘要与结果，指引审阅新摘要后重新明确确认。不能静默切换目标、宽松接受或自动重试。
   原确认已受理而响应未知时，精确回读那次提交及执行，不能借同一discovery误认其他执行。
4. 新增上述真实两页面回归：旧A确认拒绝、零新执行/零媒体效果/不消费权限；用户明确审阅B再
   确认才准入并执行。保留正确当前摘要、权限/源/容量拒绝和未知响应对照，沿实际Web client/
   API字段验证，不只直接调用begin_web_execution或仅断言current preview可执行。

### P1-2 — 普通确认后原条目链接立即404，原页面无法按原身份回读（M4/M8）

**独立正常流程复现：** 新Files单影片→原生决定/continue→当前prepared摘要→不做任何计划
变化，直接精确确认，返回202。随后原`/tasks/{task}/items/{old_item}/recovery`在Worker
运行前即404，执行完成后仍404；当前新item ID的同接口200/confirmed且有1条Result。
这里读取的是TaskItem处理/历史链接，不是要求已过时的preview继续具有执行资格。

**原因与开发指导：**

1. `admit_manual_execution()`对同Task/source直接DELETE掉旧analysis TaskItem，再写另一个
   执行item；没有保留旧ID的耐久可读关系。`TaskItemRecoveryPanel`确认后及未知响应reconcile
   仍按原taskId/itemId回读，因此仅改用新ID的测试不能证明当前页面/旧深链闭环。
2. 采用复用原item身份，或保留历史/建立明确的同Task、同具体源版本/pin的后继关系与有界
   只读解析，使旧链接仍能读原决定、历史与这次准入/执行/Result。实现可选择ID变化；禁止仅按
   路径/时间猜映射或删除旧review/attempt来消除404，不扩大为合并任意历史Task。
3. 原已确认摘要不重新变成可执行。确认响应丢失后，从原上下文应精确读出已受理的执行及选择，
   供用户跟踪而非重发；成功项不重放，数据/权限/源/unknown保护保留。关联身份、统计与结果
   必须按同一耐久来源去重，不因保留历史版本增加文件数。
4. 扩展普通当前摘要确认回归：确认前的旧item URL在准入后、执行后、重开后均可读，保留原
   决定/历史并指向准确执行；模拟未知确认响应仍能从原页面核对。保留新ID存在的实现自由，
   不把“换成list_items()[0]再GET”当作旧链接通过，也不开发第二套恢复系统。

### P1-3 — 只确认第一部，未选择的第二部也显示“已确认”且没有后续入口（M4/M8）

**真实入口与结果：** 新Files Task两部影片均保存决定并分析为ready；在Task Center现有
native confirm中只选择第一部，Worker成功生成第一部Result。第二部仍waiting_confirm、
来源存在且没有Result，但其recovery回读`manualRecoveryPreparation.status=confirmed`，
execution_id和selected_item_ids均属于第一部。checkpoint仅investigate，页面因此展示已确认
步骤而非第二部的待确认摘要；尝试原生continue返回409 uncertain_effects。

**原因与开发指导：**

1. `native_preparation_summary()`只按preview查任一execution，发现后便对当前任意item
   返回confirmed；`_native_admitted_execution()`取列表第一条，没有校验该execution确实
   包含当前来源/当前确认subset。阶段转换为waiting_confirm后，通用checkpoint无该文件Result
   的fallback又把它视作unknown，原生continue被效果保护拒绝。未知效果guard本身应保留。
2. 分开表达整份计划、当次确认子集及每个来源自己的状态/执行关系。已确认的第一部只关联
   自己的准入/Result；未选第二部仍有原位合法的待确认摘要或按现有鲜度规则分析后的确认路径，
   不借用其他文件的execution、不把整份计划一次确认当作全部文件已确认。
3. 若durable selected scope/逐项执行证据能证明某来源从未准入/派发，应按该精确证据维护
   真实待确认状态；不得只凭缺Result清除unknown或改全Task的效果确定性。真正已派发、partial/
   unknown来源仍只读检查和不重放。新的选择仍需精确确认、权限/源/计划/pin与容量检查。
4. 补两部均ready→仅确认第一部→第二部仍可在原Task Center确认→两部独立Result的回归，
   核对每个条目的prep/execution/selected scope/效果和未知响应回读，首部不重放、计数2/2且
   重开一致；保留真实unknown/取消对照。不要靠用户去Files绕过、强制一次全选或新增通用Retry。

### B实际验证与限制

| 验证 | 当前候选实际结果 |
|---|---|
| engine、调度/栅栏/迁移、Operations workspace、Task pause/CLI、media library transfers | 144 tests OK，runner8.232s/外层8.431s；`focused.json/log` |
| TaskItemRecoveryPanel直接影响单测 | 1 file / 8 tests OK，Vitest1.52s/外层2.103s；`web-focused.json/log` |
| 前轮原生摘要缺失/跨Task Rename/失败子集三场景 | API定向复核修正；对应3个既有repro脚本/log。不把局部修正当作M1–M10全部通过 |
| 精确摘要替换后的旧确认 | 旧A请求202却执行B真实MOVE；`native-stale-confirm-repro.py/log`，0.165s；未发生覆盖已有文件的效果 |
| 普通确认后旧链接 | 不改变计划的正常链，原item在准入前200、准入后/执行后404，当前新item200/confirmed；`native-old-link-repro.py/log`，0.141s |
| 两部均ready的所选子集回读 | 未选第二部被标confirmed并借用首部execution，continue409；`native-subset-readback-repro.py/log`，0.139s |
| 本次8个Python文件ruff format/check、完整Base..Head空白 | PASS；`static.json`，manifest62文件 |
| 完整Python/Web/E2E/新截图/wheel/容器/真实53/54→55升级与失败原子 | 已确认产品阻塞，按workflow提前FIX；修正候选由B完成，不记PASS、不要求Developer补全套 |

治理/链接/工作区复核见`review.json`。SQLite ResourceWarnings、CLI退役命令拒绝与Web jsdom
scrollTo提示保留，无skip/retry/timeout放宽。所有探测均从既有正常API及文件变化入口开始，
用临时SQLite/Local Storage/合成Metadata，不改DB/claim；未访问用户媒体/运行库/私有配置。
开始`2026-10-31 06:10:53 UTC`；测试/探测/检查保守总上界30秒，低于本轮总用时50%。
尚未跑新的真实浏览器截图，未据API定向通过虚报完整Web验收；完整T4仍由B承担。

### 后续交接与Slice全结果重评

同一Task修正三项并核对M1–M10。精确确认、旧链接和所选逐项结果均是原交付；不要求内部
ID恒等、不恢复暂停、不新增第五类恢复或新的执行/恢复系统。Developer交新增/变更/直接
受影响结果后由B验收；未跑全套不是Developer缺陷，不先规划47.3。

| Slice outcome | 当前结论 |
|---|---|
| RO-1 | 手动生产链与原生摘要已接入，精确确认/所选逐项回读和历史关系仍阻塞 |
| RO-2 | 自动due/Run once/独立API-CLI引擎切换仍后续，未完成 |
| RO-3 | 原三项已有修正；native确认与独立文件状态/历史闭环未完成 |
| RO-4 | schema55分批支持保留，完整升级与Job迁移/删除仍后续，不扩大本Task |
| RO-5 | Task Center出现原生摘要，但确认/旧链接/剩余项原位继续仍未完整 |

Task47.2保持FIX REQUIRED，Slice47仍ACTIVE，未达到交A关闭条件；原Base与历史全部保留。
