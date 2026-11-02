# Task47.6 — 三项运行设置迁入系统设置，删除失效判定参数

Authority: 用户于 2026-11-03 先选择“全部放到系统设置”，并已让 Developer 停工，随后明确
“把失效判定时间这个参数删掉，保留现在的判断逻辑”。本计划因此仅迁移剩余三项，删除
失效判定参数并撤销新增无进展观察。[Development Workflow](docs/development-workflow.md) 管理生命周期。
用户进一步授权本代理行使 A 权限调整相关文档；已在
`390a1a012495ad705f766bc4d568168a10b9dd4b:SLICE.md` 提交范围合同及相关需求/旅程/架构，
B 已核对并对齐本 Task。该角色例外仅用于范围/文档，不构成独立 A 终审或产品接受。
原“合同未同步”阻塞已解除。用户于 2026-11-03 明确恢复 Developer 实施；本轮已完成
实现并交 B 审查，未自签 PASS、未关闭 Slice、未推送。
保持 RO-1–6、已有安全要求及 A-P1-1/B-P1-1 已修复事实；AC-2/12/26、V2-TASK-011 和
V2-AUTO-001/007/008 已同步，不能把旧隔离验收标成新方案 PASS。

```text
Task ID: 47.6
Task Type: SLICE
Parent Slice: 47
Status: READY FOR B REVIEW
B Review Decision: PASS
Task Base: c8657032dae768d93b12387a5e58db502e23a7ee
Difficulty: High
Test Level: T4
Planner / Reviewer: B
Current correction: Three system-owned runtime settings, shared organizing capacity, retire stale-age parameter
Implementation gate: B PASS AT 5134c78b; NO NEXT IMPLEMENTATION TASK; SLICE READY FOR A REVIEW
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

## B correction guidance — current capacity at confirmation (resolved)

本轮 B 审查 `c8657032dae768d93b12387a5e58db502e23a7ee..43d3fdeb9ea1143856474c14df688e3218a32ffe`
（产品实现 `bf6968c11e1f40890454bad2c743d99d16888e4a`；后续仅 Task 报告）。
保持 Task47.6/Base/High/T4，不新建 Task，不修改 Slice 边界。以下为原阻塞及修复指导；
本轮已按真实入口复验通过，B-P1-2 已解除，具体接受结果见 B Review Result。

**B-P1-2：旧摘要确认绕过当前系统整理额度。** 系统页保存额度 1025 → Files 选择
`Three.2003.mkv` 整理并生成摘要（人工等待不占名额）→ 系统页降为 1，已有自动化工作
占唯一名额 → 新选 `Four.2004.mkv` 整理正确提示已满 → 返回 Three 的旧摘要并确认，
实际仍返回 **202 / admitted**，页面进入“整理执行情况”。应保持摘要等待并返回满额，
不能因为摘要创建时额度更大而重新占用超额名额。此旅程使用真实 Web/API/SQLite 和既有
harness 推进 Worker，没有 INSERT 队列、伪造状态或新增产品入口。

开发指导：
1. 沿 `service_api.py` 的现有 organize preview execute → `begin_web_execution` →
   `admit` → `execute` 修正容量来源。`manual_organize_execution.py` 目前在
   `execute` 默认从 `_load_runtime` 取得的旧执行快照读取 `automation_maximum_active_jobs`；
   `admit`/`begin_web_execution` 没有把当前系统额度传下去。使正常确认和四类继续的同类
   确认读取当前权威系统额度，同时保持已准入任务的旧执行 pin、策略、来源和结果。
   复用现有 runtime/configuration authority，不新增设置存储或队列。
2. 保留 SQLite `admit_manual_execution` 中容量计数、等待→queued、授权消耗、锁和写入
   的同一事务；满额拒绝不消耗权限、不改变摘要/选择/结果、不注册自动继续。当前额度
   无法可靠取得时明确拒绝并给下一步，不回退旧 pin 的额度。已准入精确重复仍读回原工作。
3. 补真实回归：上述降低额度的旧摘要应 409、原工作仍等待、授权未消费；释放占用者后
   显式再确认能成功。反向从低额度生成摘要再提高额度时也用当前值；至少证明原 snapshot
   ID/digest 和既有结果未改。初始确认与四类恢复共用修复路径时补代表性恢复证明，避免
   仅测试直接传入 `scheduling_capacity` 的内部方法而漏掉真实页面链路。
4. Developer 运行新增/失败回归及直接受影响的 `tests.test_manual_task_engine`、
   `tests.test_manual_organize_execution`、`tests.test_operations_task_center`、
   `tests.test_task_scheduling`、`tests.test_system_settings_management`、
   `tests.test_automation_settings_management`，以及实际修改的 native settings 场景和
   changed-file 静态检查。B 复核该阻塞后继续原 T4 门禁；全量/安装包/Docker 仍由 B 承担。
   保持每轮测试时间低于总用时 50%。本轮复现脚本可从下述 ignored 证据目录取用，
   应将必要业务回归融入现有测试组织，无需扩建测试平台。

## Acceptance Criteria

- [x] **AC-S1 — 位置和发布完整。** 系统设置三项可读/可编辑/可 checked Save，自动化不再
  提供独立设置 tab/form；旧链接安全到达系统入口，不发布、不丢认证返回。仅三项 Save
  不发布无关 Draft；invalid/stale/denied/unknown 分阶段解释并保留输入/原 Active。
  真实消费者采用与发布区分，不能用 generic API binding “consumed”替代真实证据。
- [x] **AC-S2 — 合法范围与所有整理消费者。** 容量 1/1025/10000 均有实际整理消费证明，
  分配覆盖 due/Run once、Files 和普通 CLI/API/remote；0/10001/bool/小数/错误类型拒绝。
  poll 有限正数校验保持严格；不静默截断/限幅。无需 10000 个任务或全组合。
- [x] **AC-S3 — 统一容量和恢复。** 手动占最后名额会限制新自动化，反向亦然；不是保留两套
  来源额度。满额新建及同 Task 重入保持原等待/摘要/选择/结果，消费授权和写库原子；
  due 不推进，已准入重复请求精确读回。释放后通过正常重试/下一 due 检查成功。
  等待/稳定/在途取消计数正确；四类继续保留 Task、来源、pin 及合法授权。
- [x] **AC-S4 — 真实周期。** 实际 resident 安全采用两个周期，包括 idle/长等待/override/
  stopped/pending/同版本 restart；共享 Worker 的手动、自动化及普通文件操作符合其说明。
  Scheduler 只检查 due；不改定义计划或通知周期。配置/心跳 wake 不冒充业务检查。
  验收领取/推进结果，不要求每个任务固定等待/完成秒数，也不把正常串行等待当故障。
- [x] **AC-S5 — 参数删除且现有判断不变。** 系统/自动化设置及其字段元数据、有效运行
  设置/采用读回不再把旧参数列为可配置或生效字段；focused/general 字段编辑提交它时
  明确拒绝且零发布。新默认配置无该键亦能启动/保存/执行；既有 Active 带旧键仍能
  读取、保存三项并同版本重启，旧快照 digest/pin 不变。原文 JSON/历史中出现该键不算
  仍在生效，不以全仓字符串零命中或固定内部类型布局验收。复用/补必要受影响测试证明
  心跳失联、租约到期/续约、调用超时和未知效果不重放保持原语义；不新增无进展提醒、
  总运行超时、自动失败/取消/释放额度/重排/重放。使用受信测试时钟或本地受控失败，
  不为此实等分钟级超时或扩建通用超时测试平台。
- [x] **AC-S6 — 完整 Web 和普通操作。** 系统页 Save→本次 Active→Files 选择→持久接收
  →摘要→正常确认→真实 Worker/Executor→正确文件/Result/pin；1025/10000 都覆盖。
  多选/文件夹/混选范围及过滤保留；确认前零变更。两类库普通复制/移动/删除的本地
  状态与实际效果保留。桌面/窄屏关键操作可读可用，
  不锁定 DOM/CSS/截图像素、测试名称或文案全文。现有 HTTP 兼容检查不替代用户结果。
- [x] **AC-S7 — 安全/持久化。** 同源互斥、原子最后名额竞争、due 并发唯一、RBAC、
  claim/fence、在途取消、成功兄弟保留、未知非重放及 A-P1-1/B-P1-1 不回归。
  设置迁页/发布/同版本 restart 不改旧配置 digest、已准入执行 pin、来源或结果。
  新系统额度可影响机器重入准入，但不改执行快照或赋予新权限。
- [x] **AC-S8 — 独立接受和停止。** A 新合同已 checkpoint；B 审完整原 Task Base..candidate，
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

六项结果已按修订后合同完成 B 重评；完整交接包见文末。Task47.6 PASS，停止规划，
SLICE READY FOR A REVIEW。A 仍须独立审查 Slice Base..Head，B 不关闭 Slice。

## Developer Completion Report

本节保留 Developer 交接时的结果及 pending 清单；其后 B 执行与最终决定见下节，
不把交接时 pending 误作当前仍未完成。

Status: READY FOR B REVIEW. B-P1-2 correction candidate:
`dc513d7f749a8f5bee41676925318af162e81aaf` on `main`, parent
`1678a498...` (previous review checkpoint `43d3fdeb...`; Task Base
`c8657032dae768d93b12387a5e58db502e23a7ee` unchanged). This report-only commit follows
the product candidate. No push, deployment or independent PASS.

What was delivered for B-P1-2:
- `ManualOrganizeExecutionService` now accepts a current-capacity resolver bound by the API
  composition root to its refreshed runtime binding. Normal summary confirmation
  (`/operations/organize/previews/{id}/execute`), direct execution-authorization/Preview
  execution, and all Task Center recovery confirmations share that one execution service and
  therefore read the current Active allowance when re-entering the shared queue.
- Confirmation keeps the reviewed Preview's immutable pin for policies, Storage authority, saved
  selection and the Task. Only the scheduling allowance is current. The old pinned
  `automation_maximum_active_jobs` is no longer used as the confirmation allowance.
- Missing, unreadable or invalid current capacity fails closed with an explicit next action; an
  adopted kernel Task cannot silently fall back to its old pin. Atomic admission still performs
  the capacity count, waiting→queued transition, authority consumption and writes in the same
  SQLite transaction (unchanged).
- No second queue, setting store, automatic retry, timeout or replay behavior was added.

New/updated regression coverage (real API routes, real SQLite, real Task engine and real Local
Storage over temporary roots; no direct `scheduling_capacity` injection):
- `test_lowered_system_capacity_applies_to_an_already_prepared_summary`: summary prepared at
  1025, successor Active set to 1, a real competing Files Task takes the slot, old summary
  confirmation returns 409 `capacity_full`; Task stays waiting, no execution or consumed
  authority, Preview pin/digest unchanged; after release the same explicit confirmation succeeds
  and the real Worker completes the MOVE.
- `test_raised_system_capacity_applies_to_an_already_prepared_summary`: summary prepared at 1,
  a competitor fills the old slot, successor Active raises the allowance to 2; the old summary is
  admitted, proving the current value rather than the old pin.
- `test_recovery_summary_confirmation_uses_current_system_capacity`: a native Task Center
  four-type recovery summary prepared at 1025 is refused with 409 after the current allowance is
  lowered and a competitor fills it; release then admits the same recovery confirmation.
- Native browser scenario `system runtime settings keep an old summary at the current organizing
  capacity`: real System Settings Save 1025 → real Files summary → Save 1 → competing Files
  request → return to the old summary → real confirm response is 409, no execution page, source
  unchanged.

Actual affected verification (cwd `/Users/songzhidong/mediaflow` unless noted):
- `.venv/bin/python -m unittest tests.test_system_settings_management tests.test_automation_settings_management tests.test_automation_settings_resident tests.test_resident_services tests.test_configuration_snapshot` — **177 tests OK / 55.609s**.
- `.venv/bin/python -m unittest tests.test_task_scheduling tests.test_task_scheduling_fencing tests.test_task_source_ownership_race tests.test_automation_task_admission tests.test_automation_run_once tests.test_automation_entrance_recovery tests.test_execution_authorization` — **152 tests OK / 6.184s**.
- `.venv/bin/python -m unittest tests.test_media_discovery tests.test_manual_organize_execution tests.test_manual_task_engine tests.test_operations_task_center tests.test_direct_file_transfers tests.test_direct_file_operations` — **417 tests OK / 83.929s**.
- Additional affected integrations: `.venv/bin/python -m unittest tests.test_v2_automation_run_once tests.test_organize_preparation tests.test_v2_manual_organize tests.test_manual_operations_contract` — **111 tests OK / 9.746s**; `tests.test_manual_task_engine` alone — **35 tests OK / 5.317s**.
- `.venv/bin/ruff check` and `ruff format --check` on changed Python files — PASS; `compileall -q mediaflow tests scripts` — PASS; `scripts/check_governance.py` — PASS; `git diff --check` — PASS; both example `config validate` commands — exit 0.
- `web/`: `npm run typecheck` PASS, `npm run lint` PASS, `npm run format:check` PASS, `npm run build` PASS. Real-Python E2E `automation-settings.python.spec.ts` — **15 tests PASS / 20.2s**, including the new old-summary capacity scenario (the `system runtime settings` subset is 5 tests PASS / 10.2s).

Known risks / remaining work for B:
- Full T4 regression, packaging/wheel/installed-consumer, Docker, restart, full native E2E and the rest of the prior candidate's acceptance remain B-owned and pending.
- The correction intentionally leaves already-admitted execution pins, policies, source and results
  unchanged; only new queue re-entry uses the current allowance.
- No independent A/B acceptance, Slice closure, push or deployment was performed.

## B Review Result

```text
Decision: PASS
Task Base: c8657032dae768d93b12387a5e58db502e23a7ee
Reviewed Head: 5134c78b22057781d472e6ebf61a1799d9e40324
Product implementation: dc513d7f749a8f5bee41676925318af162e81aaf
Developer handoff: 05772d667724db1d984ba273db10e2bc7cee0f97
Branch: main
Blocking findings: NONE — B-P1-2 resolved
Next: SLICE READY FOR A REVIEW; no next implementation Task
```

B 独立复核完整原 Task Base..Head；结合上轮范围审查，核对当前完整清单和本轮修复增量，
没有改 Base 或以 Developer 报告代签。起始 tracked 工作区干净；预存 OS/log/图片/output
未跟踪文件保持原状。治理检查通过，无 push/部署、历史重写或用户媒体/数据库访问。

### 用户结果与修复接受

- **旧摘要确认遵循当前额度。** 原 B 浏览器复现现在返回 **409 capacity_full**，仍停留
  摘要；源码中的相同链路覆盖普通确认、直接授权确认及任务中心恢复确认。额度从
  1025 降到 1 后，竞争任务占满，原 Task 保持人工等待，没有执行记录或已消费授权，
  源文件和摘要 pin/digest 不变；竞争者到人工边界释放后，显式再确认能完成真实 MOVE。
  反向从 1 提升到 2，旧摘要也能使用新额度，不被旧快照限制。
- **三项设置完整工作。** 系统页是唯一常用表单，自动化旧链接安全跳转；非法/陈旧/
  未知保存的纠正和核对保留。真实系统页保存 1025、10000 后，Files 的选择→摘要→
  正常确认→Worker/Executor→真实目标效果通过。容量 1 的自动化占用→Files 拒绝→
  释放→显式重试，以及反向手动占用阻止 due 的证据齐全。
- **周期与普通操作保留。** 实际 Worker/Scheduler 进程的空闲/长周期/覆盖值/多实例/
  重启采用测试通过；配置检查和心跳不成为业务轮询。源码核对同一个 Worker 业务 step
  依次消费整理和两类库普通 runner，Scheduler 只 tick due。两类库真实复制/跨 Storage
  移动/删除、独立结果/取消/状态恢复和本地效果通过，不纳入整理额度或新增并行度。
- **旧参数退出并兼容读取。** 默认配置及有效/可编辑/采用字段不再包含 stale-age；
  focused/general 字段编辑明确拒绝且零发布。安装产物的真实 Worker 读取含旧键的
  immutable Active，重启后仍采用剩余设置，原 digest 和原文旧键保留；不新增观察器、
  总超时或自动重放。现有心跳、租约/续约、调用超时及未知效果保护回归通过。

### 实际验收与证据

本机 ignored 根：`.git/validation-evidence/05772d66/b-review-47.6/`。
原始命令、cwd、日志、分组清单/时间、截图/trace、产物身份及初始失败保留；不宣称远程可访问。
Python/包装命令 cwd 为 repository root；Web 命令 cwd `web/` 或等价 `npm --prefix web`。

| 门禁 | 实际结果 |
|---|---|
| 全 Python | 四组模块清单与 unittest discover 的总数一致，无重漏：637+637+637+636 = **2547 tests OK**，7 项可选外部服务/耐久环境 skip；含并发、授权、pin、租约、未知非重放、C→A 身份和前序 A-P1-1/B-P1-1。`python-full-plan.json`、`python-full-{0..3}.log`。 |
| Web 质量/单元 | typecheck/lint/format/build PASS；**88 files / 1268 tests PASS**。B 修改验收脚本后补 typecheck、相关 ESLint/Prettier 和 whitespace 检查。 |
| Fake E2E 全范围 | 初始 254 项中 251 通过；2 个展示用例仍点已移除的 settings tab，1 个真实 Python 用例误入 fake runner。B 按合同修正原导航、窄屏正常打开菜单、断言旧 tab 不存在，保留所有原业务/视觉/零写入断言，2 项通过；真实用例只从 fake runner 排除并在原生运行中通过。最终 fake 适用 **253 项覆盖通过（251+2）**，不是伪称原单次全绿。 |
| Native 设置 | `playwright.python.automation.config.ts` + `automation-settings.python.spec.ts` **15 passed / 22.4s**；另保留原 B 精确复现 **1 passed / 2.3s**。 |
| Native 自动化/恢复 | Run once + workspace 全范围先 **12 passed / 1 failed**，失败为同一个旧 settings-tab 断言；修正原测试的设置入口后该用例 **1 passed / 1.9s**。合计 **13 项覆盖通过**；含成功兄弟保留、真实冲突恢复和原记录。 |
| Native Files/普通操作/历史 | `playwright.python.config.ts` 下 live Files、Task Center visual、source history **8 passed**；`playwright.direct-files.python.config.ts` 下两类库普通操作 **22 passed / 40.2s**，含实际 Move/Delete、批量及失败/取消恢复。 |
| 视觉 | 实看系统页 1536/390px、真实 Files 整理 380px、普通跨 Storage Move 结果截图；三字段/保存/采用状态可读可达，普通操作各项结果可读，无页面横向溢出。实例诊断表在自己的滚动区域内。 |
| clean wheel | 从 `git archive 05772d66` 重建；169 个 Python 模块与提交逐字节相同，无缺失/多余。wheel smoke PASS，SHA-256 **987b9056a1d147c51ae88f9160e3278286122d9d2f42019c19ccf1997d507b72**。 |
| 源码外 installed consumers | 新 venv、cwd 在源码之外、确认 import 来自 site-packages；补齐声明的 TMDB 可选依赖后 **53 tests OK / 48.462s**。额外经系统保存→实际 CLI COPY 1025/10000、API Run once→实际 MOVE 1025/10000，以及含旧键 Active→实际 Worker→同版本重启→digest 不变均通过。 |
| Docker fresh/security | `scripts/docker_release_security_smoke_test.py --image mediaflow:task47-6-05772d66` PASS；四服务、RBAC/零效果拒绝、真实 Files 整理、non-root、秘密隔离及生产静态产物。 |
| Docker 同版本 restart/fault | `scripts/docker_restart_fault_smoke_test.py --image mediaflow:task47-6-05772d66` PASS；真实 due/COPY、四服务重启、pin/身份、旧 owner fence 和未知效果非重放。image 为 **sha256:f79c1de40cec65c921f7c89526ba0905d8552740fffd76c4c93ab1150309669c**；image 已安装 CLI 的退役 retry-failed 正常 exit 2。 |
| 公共质量 | governance、Ruff 全仓 check/format、compileall、pip check、两份公开配置 validate、源码/pyproject 禁用依赖检查及 diff whitespace PASS。 |

当前治理脚本拒绝 active Task 的 `Status: PASS`，且 committed Slice 仍为 FIX REQUIRED
时拒绝 NO ACTIVE notice。本次按 workflow §7 在本节记录正式 PASS，保留上方 Developer
交接状态元数据并明确 B Review Decision，不改治理工具、不擅改 A-owned Slice 状态；
本 Task 已无进一步实施授权。首次文档检查的状态格式拒绝已纠正，不是产品失败。

B 在 `5134c78b` 仅提交了三份验收文件的上述导航/runner 修正，没有做产品修复。
`production-reuse-input-diff.txt` 为空：与 05772d66 相比，Python、Web 产品源码、锁文件、
harness、配置与构建输入均未改变，当前 wheel/image 与产品实现对应。未受影响的完整
Python/unit/安装包/容器验收保持有效；改变的浏览器用例已用原业务断言重新执行。

**初始失败及 B 处置：** 源码外 no-deps 环境缺少配置所需的 TMDB/httpx 可选依赖，导致
一个空 Task 的 Worker 用例等待超时；补齐依赖后原 53 项全部通过。额外旧键重启探针
曾误写既有 helper 名，改成实际 `wait_adoption` 后通过。首次普通 Files native 使用了
不含其既有控制入口的 inventory harness，22 项失败；使用该文件注释指定的
`playwright.direct-files.python.config.ts` 后 22 项全过。一次 B 导航修正漏开窄屏菜单，
补正常 Open menu 操作后通过。均保留日志，不归咎产品，不改超时/重试/删除断言。

可选真实远端/耐久环境未运行；旧任务/跨版本升级及 V1 仍按用户边界排除。数据库
ResourceWarning、jsdom scrollTo 未实现提示不影响断言；不为这些非阻塞项另造 Task。
本轮测试时间分配的实际记录见 evidence `timing.json`：完整回归及 B 验收环境纠正使
已计时区间的测试占比超过用户要求的 50%，这是本轮执行偏差；没有空等补比例或
隐瞒初始失败，也不把它包装为产品阻塞。后续不得沿用此偏差作为测试预算豁免。

## Entire Slice reassessment / Closure Packet for A

```text
Slice: 47 — Unified Task Scheduling and Organizing Execution
Slice Base: 5144ab1fc2344b06194969cc2c496835729664c0
Implementation / Reviewed Head: 5134c78b22057781d472e6ebf61a1799d9e40324
Product head: dc513d7f749a8f5bee41676925318af162e81aaf
Required Outcomes and Surfaces: COMPLETE under committed user amendments
Tasks completed: 47.1–47.5 accepted facts retained; 47.6 B PASS
Blocking findings: NONE
Decision: SLICE READY FOR A REVIEW — stop planning
```

| 全部结果/验收 | 当前重评与完整用户旅程 |
|---|---|
| RO-1 / AC-1–3 | 完成。手动或自动化提交→同一 Task→机器阶段占一个名额→全人工等待释放名额→确认/继续按当前额度原子重入；精确重复读回、同源互斥、due 并发唯一、在途取消及 fence 保留。 |
| RO-2 / AC-4–6 | 完成。Files、due/Run once、普通 CLI/remote 用共享引擎；1025/10000 已有 Web/installed 实际效果。目录/混选/过滤/完整边界/稳定等待/附件与入口权限差异由当前全量和 native 覆盖，原解析/CLI 修复保留。 |
| RO-3 / AC-7–8 | 完成。四类决定→分析→原 Task 摘要→明确确认；满额保留选择/结果/授权、释放后显式成功。已有成功兄弟、旧 pin、原 Automation 结果及未知效果不重放由 full/native/installed/restart 共同覆盖。 |
| RO-4 / AC-9–12 | 完成适用 fresh→新工作→同版本 reopen/restart；无独立 Job 执行系统。旧配置原文含退役键仍可读取/保存三项并重启，digest/pin 不改；源码、clean wheel 和 image 身份一致。 |
| RO-5 / AC-13–19 | 完成。系统设置新入口与旧链接、八视图/Attention、Files 本地普通操作、Automation 原记录、Dashboard/日志/导出/API/CLI/健康及 Pause 退出基础保留；实际新入口/窄屏/状态恢复已验收。A 独立终审仍待进行，B 不代签关闭。 |
| RO-6 / AC-20–25 | 完成。最新 failed/partial 历史→自动排除/自由兄弟、手动提醒→正常确认→新真实效果；原始结果/未知证据/时间/pin 不改，CLI retry-failed 退役。Task47.5 与 A 已核对的事实保留，当前全量/native/installed/restart 覆盖其共享链路。 |
| 三项系统设置 / AC-26 | 完成。三字段保存/真实采用、统一额度双向满额/释放/重入、普通操作共享 Worker 周期、due-only Scheduler、旧参数退出与可读历史均有上述代码及行为证据，无第二队列或新超时机制。 |

**Documentation Reconciliation Needed：** A 独立复核完整 Slice Base..Head 后维护 A-owned
`SLICE.md` 的候选/Next Action 与 Roadmap/Progress 现有 PLANNED/STOPPED 旧指针；
保留旧 A review/Base/accepted ledger。A PASS 后再统一 CURRENT/TARGET 与正式关闭记录。
本 B checkpoint 只交包，不关闭 Slice、不更新旧接受事实、不启动下一 Task。
