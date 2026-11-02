# Task47.6 — 三项运行设置迁入系统设置，删除失效判定参数

Authority: 用户于 2026-11-03 先选择“全部放到系统设置”，并已让 Developer 停工，随后明确
“把失效判定时间这个参数删掉，保留现在的判断逻辑”。本计划因此仅迁移剩余三项，删除
失效判定参数并撤销新增无进展观察。[Development Workflow](docs/development-workflow.md) 管理生命周期。
用户进一步授权本代理行使 A 权限调整相关文档；已在
`390a1a012495ad705f766bc4d568168a10b9dd4b:SLICE.md` 提交范围合同及相关需求/旅程/架构，
B 已核对并对齐本 Task。该角色例外仅用于范围/文档，不构成独立 A 终审或产品接受。
原“合同未同步”阻塞已解除；Developer 仍按用户停工状态保留，本轮不启动实现。
保持 RO-1–6、已有安全要求及 A-P1-1/B-P1-1 已修复事实；AC-2/12/26、V2-TASK-011 和
V2-AUTO-001/007/008 已同步，不能把旧隔离验收标成新方案 PASS。

```text
Task ID: 47.6
Task Type: SLICE
Parent Slice: 47
Status: PLANNED
Task Base: c8657032dae768d93b12387a5e58db502e23a7ee
Difficulty: High
Test Level: T4
Planner / Reviewer: B
Current correction: Three system-owned runtime settings, shared organizing capacity, retire stale-age parameter
Implementation gate: CONTRACT ALIGNED AT 390a1a01; Developer remains stopped by user
```

## Replanning decision / preflight

- 本轮起点：`/Users/songzhidong/mediaflow`，branch `main`，HEAD
  `d2669f237e3576704da071354e428983c2b28793`；governance PASS，workspace/Git 可写。
  A 文档合同提交为 `390a1a012495ad705f766bc4d568168a10b9dd4b`，提交后 governance PASS，
  B 核对 committed Contract 后对齐 Task。ID/真实 Base/High/T4 不变，不实施、接受或提交
  停工中的产品改动。
- 预存 tracked 修改共 21 个文件：application 的 `automation.py`、
  `automation_run_once.py`、`execution_authorization.py`、`manual_organize_execution.py`、
  `manual_task_engine.py`、`media_discovery.py`、`resident_runtime.py`、`task_scheduling.py`；
  `domain/task_scheduling.py`、`final_cli.py`、`infrastructure/sqlite_runtime.py`、
  `interfaces/service_api.py`；`scripts/operations_inventory_harness.py`；
  tests 的 `test_automation_settings_management.py`、`test_automation_settings_resident.py`、
  `test_automation_task_admission.py`、`test_configuration_snapshot.py`、
  `test_manual_task_engine.py`、`test_media_discovery.py`、`test_task_scheduling.py`；
  `web/tests/e2e/automation-settings.python.spec.ts`。全部保留，不暂存、不重置、不冒充候选。
  原有 OS 文件、日志、`15`、docs 参考图、output 参考目录/ZIP/HTML 全部保持原状。
- Slice Base 保留 `5144ab1fc2344b06194969cc2c496835729664c0`；Slice FIX REQUIRED，
  Roadmap ACTIVE。A 最后审查候选仍为 `5c808d4a67bedfbafb71d88a1ffa8d3480ef5316`；
  Task47.1–47.5 历史与 `7ac253dd:TASK.md` packet 不变，不重新包装成当前方案接受。
- 旧规划在 `d0c071c8:TASK.md`、`abbbd5af:TASK.md`、`8168878a:TASK.md`、
  `5c7d8ba5:TASK.md`。已复现的 Save 1025 → CLI/Web 拒绝、Save 1024 → 实际效果事实保留，
  证据在 `.git/validation-evidence/c8657032/b-planning-47.6/` 和
  `.git/validation-evidence/5c808d4a/a-final-review/web-capacity/`。
  旧“只让自动化消费、手动独立 100/5s、双范围计数/周期”的指导及测试预期被本计划取代。
- 已提交合同明确：剩余三项由系统设置统一管理；整理额度由各整理入口共享；
  Worker 轮询作用于共享后台工作；Scheduler 仅负责到期检查；删除失效判定参数，不新增
  无更新观察。现有 Worker 心跳、任务租约及 Provider/Storage 调用超时判断保持原语义。
  B 核对后解除合同阻塞；Developer 停工状态及本轮仅文档边界保持。
- 本轮完成 A 合同/相关文档与 B Task 对齐；计划检查结果见 B Review Result。未运行或宣称通过产品验收，
  预存实现仍未接受；此前三项迁页/容量方向保留，旧四字段及观察验收不再适用。

## Goal / complete journeys

**在现有系统设置页统一管理三项运行参数，移除失效判定参数及自动化页的重复设置表面，使剩余设置
有明确、真实的消费行为。** 共用现有 Task/调度权威/Worker/Executor，不引入第二队列、
并行度、抢占或新的运行身份。其余三项沿用已有配置键，保留不可变旧快照，不为迁页批量改写配置。

1. **设置与正常整理：** 用户进入“系统设置” → 查看三项当前发布值及作用范围 →
   修改并保存 → 看见本次发布成功，以及各实际消费者已采用/等待采用/显式覆盖状态。
   随后 Files 单选/多选/文件夹/混选 → 整理 → 原摘要 → 明确确认 → 实际文件效果和 Result。
   普通 CLI/API/远程整理及自动化 due/Run once 均能使用合法容量，无需降值或重启。
2. **统一额度已满：** 系统整理额度设为 1，文件 A 的手动或自动化任务占用该名额；
   对另一个文件 B 发起任一整理入口时，明确说明“系统整理队列已满”、现有工作状态和
   下一步。等名额释放后显式重试原操作即可；due 保留到期状态供后续正常检查。
   不创建孤儿、不消耗授权、不丢摘要/选择/结果，不通过改入口或来源标签绕过额度。
3. **后台检查周期：** 调整 Worker 轮询后，真实常驻 Worker 在安全边界采用；手动和
   自动化整理、两类库的普通复制/移动/删除均遵守共享的空闲检查周期。调度器轮询只影响
   发现“定义已到期”的时机，不改变 Cron/间隔定义、并行数或单次处理速度。
   心跳和配置检查继续独立；已有工作处理完可以继续领取，不承诺固定秒数完成。
4. **参数删除与现有判断：** 用户不再看到或填写“失效判定时间”。Files 发起整理或普通
   复制/移动/删除后，仍依据现有 Worker 心跳、任务租约和每次外部调用的超时处理。
   任务总运行时间长不因此被判失败；进程失联、执行权到期和调用失败继续按原状态/证据
   展示、控制和恢复。已发送文件操作但效果未知时，不因超时而自动重做。
5. **失败与恢复：** 非法/过期/无权限 Save 不发布，原 Active 与输入保留；未知 Save
   按同一提交证据核对。进程停止/未上报/覆盖值如实展示。同版本重启后仍能读取已发布
   设置、原 Task/pin/Result；旧自动化设置链接仅导航到系统设置，不产生发布或媒体效果。

## Three settings / precise consumer boundary

| 沿用的配置键 | 系统页含义及消费边界 |
|---|---|
| `automation.maximumActiveJobs` | 显示为“整理任务队列上限”或等价清晰名称。1–10000 的整数；所有进入同一整理内核的 Files、direct CLI/API/remote、due、Run once 及同 Task 机器工作重入共享一个额度。普通复制/移动/删除保留原有独立准入规则，不因迁页改造它们的队列或计数。页面说明额度是整理 Task 数，不是线程/文件并行数。 |
| `automation.workerPollSeconds` | 共享处理 Worker 的空闲工作检查间隔，覆盖其整理与普通异步文件操作 runner；不是心跳、lease、处理耗时或并行度。沿用合法有限正数及显式运行 override。 |
| `automation.schedulerPollSeconds` | 共享 Scheduler 检查自动化定义到期的间隔；不控制手动准入、Worker 领取或通知投递，不修改定义的 Cron/时区/周期。 |

配置键的历史名称属于兼容实现，不要求用户理解 Job 或填写内部字段；不为位置变化
新增一组同义配置、每来源默认额度或手动独立周期。通知服务保留自己的轮询/lease；
同步浏览、重命名、新建目录等不因迁页变成后台调度任务。

**删除 `automation.staleJobAgeSeconds`，不改名迁移。** 从可编辑字段、校验/表单元数据、
运行配置模型、传参及有效设置/采用读回中退出；新默认配置不再生成该键。已有不可变
Active/快照可保留原始旧字段并兼容读取、忽略其值，不批量删除、不改旧 digest/pin，
不要求用户手工清理后才能启动或保存剩余三项。兼容读取不让它重新成为可编辑/生效参数，
也不新增旧任务或跨版本升级支持。心跳阈值公式、各 runner 的租约与续约、调用超时和
不确定效果保护均不调整；两个轮询间隔也不作为任务执行超时。

## Actual-code gaps and stopped implementation

| 实际代码依据 | 本 Task 开发指导 |
|---|---|
| `ConfigurationPage.tsx` 的 `/ui-v2/configuration` 已嵌入 `AutomationSettingsPanel`；`AutomationInventory.tsx` 仍有 settings tab，系统 generic editor 也列出四键 | 复用系统页现有表单，仅保留三项系统运行设置；自动化保留定义/记录表面。删除旧参数在各设置投影中的展示/编辑，不留下另一入口；不重做整个系统页。 |
| `domain/system_settings.py` 已 allowlist 四键；`application/automation_settings.py` 的 focused Save 已有四字段 checked publication、submission 核对和逐实例 cadence 证据 | 将 focused 字段契约及通用编辑器中的运行设置子集收敛为三项，复用 managed authority、验证及精确提交核对。已有 API 路径可沿用，无需另建存储/endpoint；提交已删除字段应明确拒绝、零发布，不能默默成功。其他系统字段及通用 Draft 生命周期不变。 |
| 已提交 `domain/task_scheduling.py` 上界 1024；SQLite 全体 queued/claimed 计数；Files/CLI/API/remote 与继续路径读相同自动化值 | 统一修到合法 1–10000，并明确从当前系统运行策略取额度。各入口和所有重入都使用同一权威、同一原子计数；不能只改新建 Files。 |
| 已提交 `_run_worker` 的一个业务轮询驱动混合 `ResidentProcessingWorker.run_next`；`_files_transfer_worker_context` 包括两类库 transfer/delete | 保持共享检查周期及现有串行调度；核对普通操作也真实采用。pin 候选、注册、claim 必须一致，不把当前 Active 当成已准入工作的执行 pin。 |
| `stale_job_age_seconds` 传入 API `_build_runtime_binding` 后未使用；`domain/automation_settings.py` 的 typed values/字段清单、`domain/system_settings.py`、`infrastructure/runtime_configuration.py`、两层 `configuration_snapshot.py`、CLI/API 及 Web 均携带它 | 删除这条无效配置链及新默认值，更新类型/解码/错误恢复/采用投影/测试夹具。兼容读取既有配置原文而不改 digest/pin；不补观察器，不为删参数改任务详情或状态机。 |
| `domain/automation.py` 的 Worker 心跳阈值为 `max(3 × 心跳间隔, 10s)`；`domain/task_scheduling.py` 按 `claim_expires_at` 判断执行权，runner 续约；各 Provider/Storage 有自己的调用超时 | 保留现有公式、租约/续约及调用超时处理。既有 API 的有效租约参数不是待删字段；不统一各 runner 的默认时长，不增加总运行截止时间，不将失联/租约到期变成自动失败或未知操作重放。 |
| 停工修改已加入独立 manual/automation capacity、scope count、dual cadence、API binding 及相应测试 | Developer 恢复前逐项对照本计划，仅保留符合新目标的改动，改写不适用的隔离测试与组合。B 本轮不回退这些文件；Developer 也不得用全仓 reset/restore 覆盖其他工作。上界修复、源互斥等有效安全改动可复用。 |

## Implementation Scope / Developer guidance

1. **先核对合同与停工差异。** 本 Task 已对齐上述 committed Contract，保持 ID/Base。
   Developer 恢复工作时，在原停工差异上整理出一套一致方案；先列实际保留/调整文件，
   不启动第二套队列，不把旧实现或旧测试标签直接当成已接受。
2. **先完成系统页旅程。** 把剩余三项 focused 表单及读回放在系统设置中作为唯一常用入口，
   去掉自动化 settings tab 和重复编辑项；同步已存在的导航/旧 deep link/auth 返回。
   三字段 Save 仍从精确 Active 创建 checked successor，只发布三项，不夹带其他 Draft。
   不要求用户手填 revision/claim。已有 focused API 可沿用，后台和页面不继续误称自动化专用。
3. **统一额度与事务。** 修正上界和全部 admission/确认/重新分析/四类继续/remote 消耗路径。
   同一 repository 事务核对当前额度、源所有权、due 唯一性和授权，不能先 count 再写库。
   pending machine/active/stability waiting 每个整理 Task 占 1；全部人工等待占 0；
   在途取消不提前释放。重复请求满时仍读回原工作，拒绝不续授权、不自动登记继续。
   原始 trigger/provenance 继续用于身份、审计、定义语义和幂等，不用来分配两套额度。
4. **接好常驻实际消费。** 使用共享 Worker 业务周期、Scheduler 自己的到期检查周期，
   复用安全边界采用、空闲配置重查、逐实例证据和显式 override。取消旧方案要求的来源
   独立周期及默认 100/5s；保留启动无 Active 时必要的既有基础默认。
   不以固定对象个数/wake 次数/deadline 数值验收，不新增 Worker/线程并行度或抢占。
5. **完整移除无效参数，保留现有判断。** 沿上表实际配置链删除字段，不仅隐藏输入框。
   新建配置及三字段 Save 不依赖旧键；既有 Active 带旧键仍可读取、同版本重启并保存三项，
   不改原快照摘要或执行 pin。focused/general 字段编辑均不能再写入该参数，错误指出字段
   已不支持并保留原 Active/输入。同步维护新默认/示例和配置说明，标明剩余三项及实际范围；
   保留历史记录事实。撤销原无进展观察开发/测试要求；不增加观察器或超时状态机，
   不改变现有心跳、有效租约字段、续约、调用超时及未知效果不重放逻辑。
6. **补真实回归并交接。** 从系统页保存 1025/10000，再经 Files 摘要/确认产生真实效果；
   经真实入口准备容量 1，占满/释放/显式重试，双向验证手动与自动化共享额度。
   验证常驻空闲轮询、普通 transfer/delete 的推进；从真实系统设置入口证明旧参数已退出，
   无旧键的新配置与带旧键的既有 Active 均可正常使用，现有失联/租约/调用超时保护不回归。
   只在已有入口造临时任务，不直接 INSERT 队列或构造不可达“漏洞”。交受影响结果及
   READY FOR B REVIEW，B 再独立审完整 Task Base..candidate 和执行 T4。

## Acceptance Criteria

- [ ] **AC-S1 — 位置和发布完整。** 系统设置三项可读/可编辑/可 checked Save，自动化不再
  提供独立设置 tab/form；旧链接安全到达系统入口，不发布、不丢认证返回。仅三项 Save
  不发布无关 Draft；invalid/stale/denied/unknown 分阶段解释并保留输入/原 Active。
  真实消费者采用与发布区分，不能用 generic API binding “consumed”替代真实证据。
- [ ] **AC-S2 — 合法范围与所有整理消费者。** 容量 1/1025/10000 均有实际整理消费证明，
  分配覆盖 due/Run once、Files 和普通 CLI/API/remote；0/10001/bool/小数/错误类型拒绝。
  poll 有限正数校验保持严格；不静默截断/限幅。无需 10000 个任务或全组合。
- [ ] **AC-S3 — 统一容量和恢复。** 手动占最后名额会限制新自动化，反向亦然；不是保留两套
  来源额度。满额新建及同 Task 重入保持原等待/摘要/选择/结果，消费授权和写库原子；
  due 不推进，已准入重复请求精确读回。释放后通过正常重试/下一 due 检查成功。
  等待/稳定/在途取消计数正确；四类继续保留 Task、来源、pin 及合法授权。
- [ ] **AC-S4 — 真实周期。** 实际 resident 安全采用两个周期，包括 idle/长等待/override/
  stopped/pending/同版本 restart；共享 Worker 的手动、自动化及普通文件操作符合其说明。
  Scheduler 只检查 due；不改定义计划或通知周期。配置/心跳 wake 不冒充业务检查。
  验收领取/推进结果，不要求每个任务固定等待/完成秒数，也不把正常串行等待当故障。
- [ ] **AC-S5 — 参数删除且现有判断不变。** 系统/自动化设置及其字段元数据、有效运行
  设置/采用读回不再把旧参数列为可配置或生效字段；focused/general 字段编辑提交它时
  明确拒绝且零发布。新默认配置无该键亦能启动/保存/执行；既有 Active 带旧键仍能
  读取、保存三项并同版本重启，旧快照 digest/pin 不变。原文 JSON/历史中出现该键不算
  仍在生效，不以全仓字符串零命中或固定内部类型布局验收。复用/补必要受影响测试证明
  心跳失联、租约到期/续约、调用超时和未知效果不重放保持原语义；不新增无进展提醒、
  总运行超时、自动失败/取消/释放额度/重排/重放。使用受信测试时钟或本地受控失败，
  不为此实等分钟级超时或扩建通用超时测试平台。
- [ ] **AC-S6 — 完整 Web 和普通操作。** 系统页 Save→本次 Active→Files 选择→持久接收
  →摘要→正常确认→真实 Worker/Executor→正确文件/Result/pin；1025/10000 都覆盖。
  多选/文件夹/混选范围及过滤保留；确认前零变更。两类库普通复制/移动/删除的本地
  状态与实际效果保留。桌面/窄屏关键操作可读可用，
  不锁定 DOM/CSS/截图像素、测试名称或文案全文。现有 HTTP 兼容检查不替代用户结果。
- [ ] **AC-S7 — 安全/持久化。** 同源互斥、原子最后名额竞争、due 并发唯一、RBAC、
  claim/fence、在途取消、成功兄弟保留、未知非重放及 A-P1-1/B-P1-1 不回归。
  设置迁页/发布/同版本 restart 不改旧配置 digest、已准入执行 pin、来源或结果。
  新系统额度可影响机器重入准入，但不改执行快照或赋予新权限。
- [ ] **AC-S8 — 独立接受和停止。** A 新合同已 checkpoint；B 审完整原 Task Base..candidate，
  执行适用 T4，重评全部修订后 Slice 结果/必需表面。全部满足交 fresh Closure Packet 给 A，
  否则同 Task FIX REQUIRED；B 不关闭 Slice，不以计划/停工改动代替接受。

## Required Tests

遵守 [workflow §6](docs/development-workflow.md#6-test-levels)。每轮测试时间小于本轮
总用时 50%；不空等补比例、不删业务断言/加重试/放宽超时。用临时根/DB、本地 fake
Provider/Storage、受信时钟和既有 harness，不用用户服务/媒体。未跑门禁保持 pending。

覆盖按风险分配：1025 为已知回归，10000 为上界，1 为满额/释放；各入口、四类继续、
普通文件操作、两个视口和两个轮询均有行为证据，无需数值 × 入口 × 视口全组合。
旧隔离断言应改成统一额度/周期结果，不机械删除；测试文件/标题可按现有组织调整，
交接实际选中命令与覆盖，零匹配不算通过。

### Developer — affected tests

按真实改动补成功/非法输入/满额/冲突/失败/竞争、参数退出及兼容读取，运行以下直接受影响模块：

```bash
.venv/bin/python -m unittest tests.test_system_settings_management tests.test_automation_settings_management tests.test_automation_settings_resident tests.test_resident_services tests.test_configuration_snapshot
.venv/bin/python -m unittest tests.test_task_scheduling tests.test_task_scheduling_fencing tests.test_task_source_ownership_race tests.test_automation_task_admission tests.test_automation_run_once tests.test_automation_entrance_recovery tests.test_execution_authorization
.venv/bin/python -m unittest tests.test_media_discovery tests.test_manual_organize_execution tests.test_manual_task_engine tests.test_operations_task_center tests.test_direct_file_transfers tests.test_direct_file_operations
.venv/bin/python scripts/check_governance.py
git diff --check
```

第一组覆盖系统页权威/三字段发布/实际采用及旧字段编辑拒绝，第二组覆盖统一额度/授权/
原子性/各入口和原有租约保护，第三组覆盖手动/恢复及普通文件操作。第一组的
`tests.test_configuration_snapshot` 覆盖配置模型、空白默认、旧快照读取与 digest/pin；运行配置
解析、Worker 心跳和调用超时复用现有受影响用例，不要求无关 Provider 全矩阵重测。
不新建通用验收平台。Python 改动文件跑 ruff check、ruff format --check、compileall。

在 `web/` 对受影响组件/路由/导航跑 unit、静态检查及真实单场景回归：

```bash
npm run typecheck
npm run lint
npm run test -- run src/features/configuration/ConfigurationPage.test.tsx src/features/operations/AutomationSettingsPage.test.tsx src/routes/router.test.tsx
npm run build
npm run test:e2e -- --config=playwright.python.automation.config.ts tests/e2e/automation-settings.python.spec.ts --grep 'system runtime settings'
```

建议新增/调整场景统一使用 `system runtime settings` 标题前缀；若文件移动，更新实际
命令。真实系统表单、导航、Files 选择/确认使用页面动作，既有 harness 只推进真实后台、
提供本地受控失败和读取事实，不 route mock 成功。补齐受影响导航/ordinary-operation
测试，Developer 不承担全仓 Python/Web/E2E、wheel/Docker 或发布矩阵。

### B — acceptance and full regression

- 先核对 A 新合同、精确实现 SHA 和全部预存差异的处理，审完整
  `c8657032dae768d93b12387a5e58db502e23a7ee..candidate`；不 repin Base、不把旧
  Automation-only 测试通过当成新方案接受。独立验证 AC-S1–7，先复现关键旅程再跑昂贵门禁。
- 按 [shared full T4 gates](docs/development-workflow.md#shared-full-regression-commands)
  执行全 Python、适用 Web/static/unit/fake E2E、安全/并发/持久化、clean wheel/source-external
  installed consumers 与 Docker fresh/security/同版本 restart。安装产物证明系统容量
  1025/10000 可实际 CLI/自动化执行，满额统一拒绝，轮询来自真实消费者；新默认配置
  不依赖失效参数、同版本既有快照读取不破坏 pin/digest，现有超时/失联/租约安全保持。
  不以 help/配置回显替代。旧任务/跨版本升级与 V1 沿用用户边界排除。
- native 在 `web/` build 后运行：
  `npm run test:e2e -- --config=playwright.python.automation.config.ts tests/e2e/automation-settings.python.spec.ts`；
  自动化定义/Run once 原旅程另开新 harness 运行
  `npm run test:e2e -- --config=playwright.python.automation.config.ts tests/e2e/automation-run-once.python.spec.ts tests/e2e/automation-workspace.python.spec.ts`。
  不并行共用可变 Active。补必要 Files、普通 transfer/delete 及恢复的真实桌面/窄屏证明。
- 原始日志/截图/产物身份放稳定 ignored 路径；记录 SHA、cwd、命令、实际结果/skip/耗时。
  仅按 workflow 的相同 source/tests/harness/dependencies/config/artifact 证据复用原验收。
  设置范围和调度变化的执行证明必须重新覆盖；最后重评 Slice 原 Base
  `5144ab1fc2344b06194969cc2c496835729664c0..candidate` 全部修订后结果，满足即停止。

## Non-goals

新增系统页、第二设置存储/同义配置键、来源双额度/双周期、新队列/Worker/引擎/并行度/
抢占/公平调度产品、普通文件操作队列容量重做、10000 Task 压测、全局告警/监控平台、
自动 unknown 重放/超时失败/强制取消/自动续授权、第五恢复、旧任务/跨版本升级、V1、
历史/pin/digest 改写、无关重构或过程平台、A 终审/关闭。新增无进展观察、统一超时策略或
调整现有心跳/租约/调用超时时长也不在范围内。迁移三项表单、删除无效参数及必要兼容
读取/组合/投影调整属于本 Task。

## Current whole-Slice reassessment

| 结果 | 新方案下当前判断（不是产品接受） |
|---|---|
| RO-1 | 统一 Task/claim/fence 基础保留；共享额度合同已同步，实际有界准入和合法上界仍待验收。 |
| RO-2 | 共享引擎保留；所有整理入口及继续必须使用统一系统运行策略。 |
| RO-3 | 四类同 Task 恢复事实保留；统一满额恢复/授权/pin 需要新验收。 |
| RO-4 | 同版本/pin/digest 安全保留；三项真实消费、参数删除/既有配置读取与 restart 待验收；现有失联/租约/调用超时判断不变。 |
| RO-5 | 系统页迁移、自动化 tab/导航调整、常驻普通操作及明确错误/恢复待完成。 |
| RO-6 | Task47.5 与 A 验证事实保留；历史结果、原始来源、同源互斥和失败提示不回归。 |

## Developer Completion Report

Developer 已由用户叫停，预存实现未提交/未接受。Contract gate 已满足，本轮不恢复实现。
之后交完整 checkpoint SHA / READY FOR B REVIEW、最终行为/文件/关键决策、
受影响测试实际命令结果与耗时、失败/风险/剩余工作；full acceptance pending B。

## B Review Result

决策：同一 Task47.6 按用户最新指示删除失效判定参数，剩余三项迁入系统设置；取消新增
无进展观察，保留现有心跳、租约/续约及调用超时判断。旧隔离开发指导不恢复。
本轮先按用户授权提交 A 范围/文档，再以 B 身份核对 committed Contract 并对齐本 Task，
保持 PLANNED。没有新实现候选，不签产品 PASS，不关闭 Slice，也不以本次角色例外代替
今后的独立 A 终审。合同未同步阻塞已解除，无需再等 A 调整同一范围。
文档检查 PASS：governance、相关 diff whitespace、九份文档 126 个本地链接及原 Slice
身份/验收 ID/已接受 ledger 保持检查；`.venv/bin/python -B -m unittest tests.test_release_security`
为 **8 tests OK / 0.021s**，测试耗时小于本轮总用时 50%。产品验收仍 pending，
Developer 停工状态保留。
