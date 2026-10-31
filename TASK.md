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

本轮B复核冻结候选`b72675ef35beffe5d14b3e4b9910abfae618fbdb`，完整Task Base..Head为66文件。
Task Base、High/T4与schema55不变。结论FIX REQUIRED；本轮只独立审查/验证并更新Task，不实施修复。

原三项复现均已修正：ignored来源不再回到新摘要/执行，全部技术失败或最后ignore能够结算，
既有ready条目重新分析超时也能同步FAILED并结束。但正常长批次分析没有续Task claim：累计分析
超过默认300秒后，活着的Worker无法发布摘要，Task永久running/claimed并占名额。这是当前唯一
确认的P1；它来自本Task早期接线，而非本次失败同步补丁。完整复核不能只验最后一笔delta。

## Next implementation order

1. 沿现有`ManualTaskEngineWorker._run_discovery`→`MediaDiscoveryService.run_claimed/_analyze`
   →共享Preview链补齐长分析保活。复用已有阶段/Provider前后`analysis_checkpoint`及现有lease-keeper
   能力，使真实Task owner与容器内父Worker在批量分析和单个慢调用期间续租/更新liveness；不新建
   队列、执行引擎或并行处理系统，也不以单纯延长租约掩盖缺失的保活。
2. 保持claim token/generation/有效期、取消与原子plan发布栅栏；真正丢失owner时不得发布摘要、
   写入后续条目或执行效果。不能放宽过期fence、自动抢占已开始工作或通过重置状态绕过保护。
   保留前轮三项修正、独立兄弟结果/历史、精确pin、授权与uncertain非重放。
3. 在现有Files/API+生产Task engine fixture补正常短批次与超过300秒长批次对照，使用可控时钟/
   本地Provider而非长时间sleep；证明原Task完整摘要、正确文件数、人工等待释放容量、零变更/无Job。
   覆盖单次慢调用的现有保活机制及真正owner丢失/取消的直接受影响边界。Developer仅跑新增/失败及
   直接受影响测试；B复审完整Base..新Head并承担T4。既有验收harness的失配由B处理，不转嫁全套
   门禁给Developer。不先规划47.3、不改摘要交互或增加“有效但错误元数据”的新人工纠正能力。

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
Reviewed Head: `b72675ef35beffe5d14b3e4b9910abfae618fbdb`。
范围：完整Base..Head的66文件，包括范围改约、生产链、共享writer/消费者及测试退役/替换；不是只审最后5文件补丁。
Decision: **FIX REQUIRED**，一项确认的P1；未宣告Task/Slice PASS。

B独立复核；main无既有tracked edits，治理PASS。原有OS/log/图片/zip等untracked原样保留、不暂存；
未读取用户运行库/媒体/私有配置，未实施产品修复、未使用子代理、不push、不改A-owned文档。
已核对准入、发现/分析/摘要/确认/执行、原条目与兄弟历史、四类续作、取消、容量、claim与效果栅栏、
resident组装、新旧runner排除及API/CLI/Web消费者。所有探测沿已有Files/API/Worker入口，不改数据库
制造状态，不恢复已取消的暂停旅程；不把用户只讨论的元数据人工修订纳入范围。

### 已验证的本次修正

- `reanalysis-failure-repro.log`：ready来源重新分析超时，原item为failed/analysis_failed，Task为
  failed/settled；再推进5次Worker不变，零Result/Storage变更、不占容量。上一轮唯一P1已修正。
- `ignored-source-repro.log`：新摘要仅含合法Two；One仍ignored、源保留，最终partial_success，
  只有Two的1个Result、无Job。`settled-analysis-repro.log`证明最后ignore及初次全技术失败正常结算。
- 新增helper按真实plan producer字段区分四类人工问题与技术失败；核对现有共享producer及其消费者，
  未确认分类偏离。成功/ignored/uncertain兄弟不应因失败同步被重置。

### P1 — 正常长批次分析未保活，过期后永久卡住并占名额

**用户触发：** 从现有资源库Files入口选择一批合法影片并整理；元数据请求都正常完成，但整批分析
累计超过5分钟。当前新Task链分析期间不续Task claim，摘要最终不能发布，页面/API一直处理中，
没有摘要、没有人工待处理项，仍占一个调度名额。不是进程崩溃/历史暂停/额外技术恢复场景。

**独立对照：** 复用`ManualTaskDiscoveryTests/_DiscoveryFixture`的真实认证Files API、SQLite、
已发布策略、LocalStorage及生产Task engine。20部/40部不同片名均在100上限内，synthetic Provider
每次正常search用fixture时钟前进10秒；未直接篡改claim/持久状态、未等待实际200/400秒。每个resident tick
按生产方式更新Worker注册，再调用原engine。`analysis-duration-control.py`当前断言结果：

| 输入 | 实际耐久结果（5次后续Worker轮询后仍相同） |
|---|---|
| 20部，模拟累计200秒 | completed discovery、有摘要、20 TaskItems、waiting_human、不占容量、零Result/变更 |
| 40部，模拟累计400秒 | discovery=analyzing、无摘要、0 TaskItems；Task=running/claimed、claim已过期、仍占容量、零Result/变更 |

后者API200仍为running/total_items=0/problem_types=[]，不是短时刷新延迟。
日志：`duration-control2-200s.log`、`duration-control2-400s.log`；均exit0（断言复现/对照符合预期，
不是产品验收PASS）。早期fixture/harness失败日志也保留，未当成产品缺陷。

**根因与定位：** `manual_task_engine.py:181–186`直接调用`run_claimed`，绕开旧
`MediaDiscoveryService.claim_and_run:3065`的lease keeper；`media_discovery.py:3305–3312`
进入`_analyze:4564`后，共享Preview creator调用没有传`analysis_checkpoint`，整批Provider阶段
既没有Task续租，也没有父Worker liveness更新。默认Task lease为300秒，发布仍正确受过期fence
拒绝；普通claim只可领取PENDING，已RUNNING任务不会被下一轮自动接管，因此一直卡住。
引入接线：`b5a21ea39315e4e742e8ff2079216c31b8043fc6`（2026-10-31 07:30:35 +08:00）。

**同Task修正：** 按Next implementation order恢复真实保活并补短/长批次与失去owner对照；
不能削弱过期fence、取消/uncertain保护或自动重放。阻塞M1/M5/M6/M8及M9的正常长运行闭环。
不因已有非重放约束就接受正常工作的必然超时，也不扩成所有崩溃点自动恢复。

### 本轮门禁与限制

证据根：`.git/validation-evidence/b-task47.2-b72675ef/`；本地忽略存储，不宣称远程可访问。
完整命令/时间/制品身份见该目录`review-summary.md`、`browser-gates.json`和原始日志。

| 验证 | 当前候选实际结果 |
|---|---|
| 治理、ruff format/check、compileall、pip check、两份示例配置、diff空白、禁用依赖检查 | 通过；398 Python文件；ffmpeg/ffprobe无匹配 |
| 完整Python unittest discover | 2984 tests OK，skipped=7，449.416s；`python-full.log` |
| 完整Web单测 | 88文件/1320 tests通过，99.1s；`web-unit.log` |
| Web typecheck/lint/format:check/build | 通过；build仅大chunk警告；`quality.log` |
| 常规Web E2E | 253 passed；`web-e2e.log` |
| 原生inventory / task-center visual / direct-files | 44 / 2 / 22 passed；对应同名日志 |
| 自动Run once原生浏览器组 | 3 passed / 2 failed；旧harness查找英文Refresh，而实际四类panel为“刷新”；`automation-run-once.log` |
| 新Task独立四类浏览器链 | 真实Files准入→识别→元数据→分类→冲突rename→摘要确认→MOVE/Result，原Task completed；`native-four-result.log` |
| 当前wheel、源码外安装消费者、迁移演练 | wheel smoke与7项installed native通过；TaskBase54→55及SliceBase53→55 rehearsal通过；`packaging.log`/`installed-native.log` |
| Docker release security / restart-fault / upgrade-recovery | 均通过；真实四服务/手动Task/权限与敏感信息/不确定效果/54→55故障原子性；`docker-*.log` |
| Docker empty-baseline | 未通过：旧脚本等待Slice46已移除的任务中心全局常驻服务/readiness区块；基础设施四服务已健康，未完成该脚本后续阶段 |
| 三项既有复现 / 长批次对照 | 前三项已修正；正常长分析确认P1，不能以全量通过代替实际交付 |

7个skip来自真实SMB/S3/OpenList专用验收环境缺失（3项）及Local/SMB/S3/OpenList专用耐久环境
缺失（4项）；`skip-reasons.txt`列出原有装饰器原因，未改skip或读取生产环境。Python既有SQLite/
TemporaryDirectory ResourceWarnings原样保留。源码外消费者确实来自独立venv的site-packages，
不是源码PYTHONPATH；该7项不冒称包含本次新增三项失败同步测试。

部分inventory四类seed仍走legacy，44项本身不等于新链全覆盖。本轮另跑新Task的四类串联及
明确subset确认/真实MOVE，刷新重连后原Task/Result仍可读，完成桌面1536/窄屏380结果截图实看。
少数过渡截图未捕获完整表单，不冒称每张都证明全部状态。第一次浏览器helper的Refresh语言及
刷新后未重连错误保留，修正helper后结果成功；未改产品来迁就harness。

Run once与empty-baseline的旧harness失配与代码/已接受Slice46语义一致，不能当本Task产品P1，
也不能把这两项标PASS；未来修正候选由B维护验收并补齐。当前已确认真实P1，停止昂贵门禁，
不让Developer先重构测试平台。测试墙钟区间合并及总时长口径见`timing.json`；遵守本轮测试
小于总用时50%，没有通过空等或重复测试凑比例。

### M1–M10与全部Slice结果重评

| Task验收 | 当前结论 |
|---|---|
| M1 | 新手动同Task/无Job链成立；正常长分析不能产生摘要，P1阻塞完整旅程 |
| M2 | 有界direct/folder/mixed、稳定性/附件测试与原生门禁通过；无新增确认缺口 |
| M3 | Save/分析零变更、精确subset确认/权限/pin、C→A身份及ignored排除已有回归；无新增确认缺口 |
| M4 | 本轮新Task四类真实串联至Result成立，旧深链/兄弟与原失败同步已验证；整体仍受长分析P1影响 |
| M5 | 失效owner拒绝与效果栅栏保留；正常owner却因缺保活过期，长运行要求未满足 |
| M6 | 短链共享容量/拒绝保护已覆盖；长分析永久占名额，P1阻塞 |
| M7 | 已成功/ignored/uncertain非重放、取消/重启证据通过；不以自动接管绕过本轮缺口 |
| M8 | 新链实际四类/摘要/结果、导出/历史多数已验证；长批次API永久running，P1阻塞；Run once旧harness待B补正 |
| M9 | 当前全量/打包/installed/53与54升级/安全容器已执行；empty-baseline旧harness未通过，长分析仍不能验收 |
| M10 | 全操作Pause退役、真实入口拒绝/零效果及取消/四类继续已覆盖；不恢复暂停迁移义务 |

| Slice outcome | 当前结论 |
|---|---|
| RO-1 | 内核与手动生产链已接，但正常分析租约/容量生命周期存在本轮P1；未完整交付 |
| RO-2 | 手动新引擎已接；due/Run once/独立API-CLI切换仍后续，本Task不承担该切换 |
| RO-3 | 新手动四类同Task已实际完成，旧三项失败/历史缺口修正；长分析尚会阻断续作，无新增恢复种类 |
| RO-4 | additive55、53/54升级及故障原子性已验证；Job历史转换/删除尚未做，仍属后续 |
| RO-5 | 新手动多数现有Web/API/容器表面已证；长批次无摘要/结果闭环，全部触发表面仍未交付 |

同Task修正这一项P1；Slice47保持ACTIVE，不规划下一Task，不修改A-owned合同/路线图/进度。

## Developer handoff — current reviewed implementation

Checkpoint: `b72675ef35beffe5d14b3e4b9910abfae618fbdb`。Developer提交时为READY FOR B REVIEW，
本轮独立B结论以上文为准；此前详细fix-round报告保留在Git，不在当前Task重复流水账。

本次实现：fenced plan/discovery事务对尚未结束的既有精确来源同步技术失败，保留ID/源版本/pin/
审核/兄弟历史及settled结果；纯helper区分四类人工问题与技术失败，复用原聚合结算。
新增3项真实Files/API/engine回归（单项失败结算、成功兄弟不重放、待决定兄弟不提前结束）与
2项helper分类测试。Developer实际affected组406/230/342 tests均OK，3个B复现脚本和修改文件
质量检查通过，证据`.git/validation-evidence/dev-task47.2-p1-reanalysis/`。未要求Developer跑全套；
本轮B的当前候选T4结果、限制和新增P1单独记录于上文。
