# Task 48.1 — 任务流程结束与文件结果分开（A48-01 修正计划）

Authority: committed [Slice48](SLICE.md) RO-1/3/4、AC-4/7/8/11/13–16 和
[A48-01](SLICE.md#a48-01--p1-recovered-file-proof-overrides-a-durably-failed-task-flow)；
[Development Workflow](docs/development-workflow.md) 管理生命周期、测试分工与交接。
这是原 Task48.1 的修正，不新建 Task、不重置 Base、不缩小原目标/验收。

```text
Task ID: 48.1
Task Type: SLICE
Parent Slice: 48
Status: READY FOR B REVIEW
Task Base: 4f11762d617d50555f3b106357e8f41988f7c2f9
Correction planning Head: 35e6b2dbe637ceb27625cdbf8ef63b6730e99139
Implementation Head: a80015e2 (fix(task48.1): keep the durable failed flow authoritative across reads)
Difficulty: High
Test Level: T4
Planner: Codex — user-requested B planning responsibility, 2026-11-04
Reviewer: INDEPENDENT B REVIEW PENDING
Development Authorization: USER-AUTHORIZED DEVELOPER IMPLEMENTATION OF THIS CORRECTION, 2026-11-04
Next Action: INDEPENDENT B REVIEW OF THE SUBMITTED CANDIDATE (F-1–F-8)
```

用户本轮要求“规划一个修复Task”。本轮按该指令仅承担 B 的规划职责；此前的 A 终审不是本计划的
独立 B 验收。后续 Developer 实施、独立 B 验收和 A 终审分别交接，不在本轮执行或自我批准。
父 Slice 保持 FIX REQUIRED，Roadmap 保持其未关闭修正循环；计划不构成 Slice 接受或 CURRENT 对齐。

## Goal / Required Outcome

保留原 Task48.1 的完整目标：从 Files、支持的 API/CLI、due 或定义“运行一次”进入整理后，
Task 的 pending/running/completed/failed/cancelled 表示流程状态；文件成功、部分成功、失败、
缺失结果或未知效果独立显示。人工待办/真正在途工作保持未结束，安全取消和同 Task 四类恢复保持。
两种库的普通操作仍在原库页查看独立效果。

本次只修正 A48-01：**文件已经成功，也不能把已保存的 Task 流程失败显示成“完成／恢复成功”。**
同一 Task 的详情、任务中心列表/计数/过滤、自动化记录各状态字段和成功率必须采用一致的当前
持久化流程状态；现有文件成功、原始执行时间和尝试历史照实保留。

需求追踪：`V2-TASK-013/014`、`V2-AUTO-012`，保留 `V2-TASK-001–011`、
`V2-OPS-014–017`、`REQ-SAFE-*` 和父 Slice 未变的安全/延期。以 Slice48 TARGET 修订解释
[完整任务/恢复旅程](docs/product-experience.md#tasks-results-and-per-item-recovery)、
[完整自动化旅程](docs/product-experience.md#current--complete-native-automation-workspace-accepted43-amended46)
与 [TARGET 架构契约](docs/architecture.md#target--task-flow-status-and-automation-success-rate-slice48-active)。
旧 CURRENT 聚合/记录措辞的最终对齐仍由 A 在接受后完成。

### 本次必须走通的既有旅程

1. 已保存自动化定义 → 点击“运行一次” → Worker 在识别问题等待；任务中心显示进行中及该问题。
2. 使用现有识别决定 → 继续分析 → 查看精确摘要 → 明确确认；同一个 Task 执行，文件实际移到目标。
3. 在真实 SQLite 终态保存边界仅注入一次 `sqlite3.OperationalError("database is locked")`；
   后续原始 repository 成功保存流程失败。注入只模拟这个实际写操作的故障，不新建产品入口，
   不直接植入 Task/status/Result，不声称生产中自然发生了锁错误。
4. 查看同一 Task：任务中心/自动化记录显示“流程失败”，另行保留“文件成功 1 个”；不能显示
   “恢复成功”、已无效的人工待办、无工作或没有发生文件操作。自动化指标为 completed 0、
   failed 1、evaluated 1、成功率 0%。刷新/同版本重开仍一致，不重复移动已成功文件。
5. 查看失败阶段、已保存状态和已完成效果；下一步沿既有事实查看/刷新核对，不能把旧识别决定
   当作仍需处理的当前问题，也不能新增通用重试、附件重试或其他执行入口。

若终态始终未能保存，显示最后成功保存的状态或读不可用，不编造 failed/completed。
正常完成但文件失败的对照场景仍为 completed，并按 Task48.2 的现有口径计流程成功。

## Implementation Scope / 简单实施步骤

1. **将已证实旅程变成正式回归。** 在 `tests/test_v2_automation_run_once.py` 复用
   `RunOnceApiTests.test_recognition_decision_continues_analysis_summary_and_execution_on_one_task`
   的真实准入、决定、分析、摘要、确认及 Worker 组装；在
   `SQLiteTaskRepository.release_scheduled_claim` 的第一次 completed 发布上注入一次 SQLite
   写失败，其余写操作用原实现。断言注入命中、真实文件效果及后续 durable failed，随后检查
   当前 Task、run、records、metrics；修复前应明确失败在状态矛盾，不能捕获断言后算通过。
   原 A probe 仅作为可复现参考，不把 ignored 脚本变成测试依赖。
2. **让共享读取先服从当前 Task 流程事实。** 修改
   `mediaflow/infrastructure/sqlite_runtime.py::_run_query_document` 的 `derived_status` 和
   `recovered_completion`：支持的当前 Task 状态不能被 `recovered_success` 的文件/确认摘要证据
   覆盖。检查同一 SQL 消费者的 overview、服务端状态条件/分区/总数/游标、Automation latest/records。
   同步核对 `domain/operations_run.py::derive_run_status` 的语义，不建立第二套流程计算器。
   恢复成功的独立证据若保留，必须同时满足真实流程完成和必要文件恢复已证实；仅有 completed
   或已无四类问题不能宣称文件恢复成功。保留现有合法历史只读行为，不迁移/批量改写旧状态。
3. **对齐记录状态及当前说明，保留原始历史。** 核对
   `::_automation_record_query_document`、`::automation_record_failure_evidence`、
   `service_api.py::_automation_record_document / _automation_record_failure_stage` 和
   `application/automation_record_display.py`。顶层 `status`、`result.status`、`recordOutcome.status`
   与同 Task 的流程事实一致；当前文件计数/待办/效果说明使用适用的 durable 证据，不能把
   `task_initial_executions` 冻结的旧 waiting/unreadable 或零成功数当成当前失败原因/文件结果。
   流程失败但文件成功时，保留成功事实和有界、脱敏的流程失败说明；缺失的具体原因诚实显示
   不可读，不能捏造文件失败或零效果。原始 start/end、初始阶段、append-only 尝试/Result/pin
   保持事实；不改写它们来迎合当前状态。成功率沿用 Task48.2 的公式/人群/月份，不调整分母。
4. **完成现有 Web 消费和防矛盾展示。** 核对 `web/src/entities/operations/run.ts`、
   `automation.ts` 及 `OperationsLanding.tsx` / `AutomationInventory.tsx` 的真实消费者。
   列表、详情、记录和卡片均可同时读懂流程失败与文件成功；failed/cancelled/running 不因恢复
   字段而显示完成。对矛盾/不可用证据保持拒绝或不可用，不在浏览器自行推导成功。保留八视图、
   四类 Attention、记录的紧凑只读结构及当前入口；只修改实际需要的类型/校验/呈现，不重做页面。
5. **补齐同一旅程的查询、重开及原生证明后交接。** 从上述准入构造真实多 Task 人群，核对
   status/outcome 过滤、counts、跨页与同 Task 去重；验证重开/后续 Worker 零重放和正常恢复对照。
   原生浏览器在现有 `scripts/operations_inventory_harness.py` / `task-flow.python.spec.ts`
   链路验证桌面/窄屏读回；如需注入，扩展已有测试 Worker seam，在准确 Task 的真实写边界
   一次性触发，禁止增加产品路由或 seed 最终状态。完成 Developer 受影响测试后冻结一个完整
   checkpoint，交独立 B；不得用读时修正去写回 Task 或改变结算/执行权限。

## Acceptance Criteria

| ID | 可核验结果 |
|---|---|
| F-1 | 上述真实恢复链确实执行一次文件移动；注入一次终态 completed 写失败后，后续 Task failed 成功持久化。现有 Task GET、run 详情和 records 顶层/result/recordOutcome 均为 failed；无完成/恢复成功提示。原文件 Result 仍 SUCCESS、成功数量为 1。 |
| F-2 | 流程失败的阶段/说明与当前事实一致，不再提示已解决的识别待办或虚构文件失败；已知文件效果、缺失结果、未知效果各自诚实。不可读/未保存终态不编造状态、结果或零效果；页面不暴露原始异常/内部令牌。 |
| F-3 | 同一已授权总体上，服务端 status/outcome=failed 查到该 Task，completed 过滤排除它；列表、详情、statusCounts、total、前后分页和 latest 一致。All/Ended 可见，Running 排除；已解决四类问题不因流程技术失败重入 Attention。非法过滤/过期游标和无权限仍按既有规则拒绝。 |
| F-4 | 自动化该 Task 只计一次：成功 0、失败 1、评估 1、成功率 0%。同 Task 继续不新增准入；due/Run once 人群、completed/(completed+failed)、取消排除、月份边界和不可用规则不变。 |
| F-5 | 正常四类恢复仍在同 Task 完成；待决定/分析/确认和真正本地在途工作仍未结束，确认取消仍保留取消。正常完成但全失败/partial/缺 Result/未知效果仍按现有技术结束规则 completed，不把本修正改成文件成功门槛。completed 自身不等于文件恢复成功。 |
| F-6 | 刷新/断线重连/同版本 SQLite 重开后，当前流程状态、记录、指标仍一致；原始执行时间、首次阶段、尝试/Result、pin、权限证据不被重写。后续 Worker 不移动/复制已成功或未知效果的文件，未受影响兄弟保持独立。 |
| F-7 | 真实 Python/API/SQLite/Worker 浏览器旅程在桌面和窄屏同时读懂“流程失败”和独立文件成功；记录仅查看结果/原因/下一步，无新增执行或恢复控件。相同响应在严格 Web decoder 下可读；矛盾/缺失证据不被转成成功。 |
| F-8 | 原 Task48.1 已有安全/入口/四类恢复结果及 Task48.2 指标结果保留，独立 B 完成修正后的实际验收和最终适用 T4 证据。通过后重新评估全部 Slice 结果，满足即更新 Closure Packet 交 A，不继续拆可选改进 Task。 |

## Required Tests

按 [workflow §6](docs/development-workflow.md#6-test-levels) 分工。下面是未来实施/验收命令，
**本规划未执行这些验收，也未宣告修正通过**。仅运行 A 原有 probe 确认当前矛盾仍可达。

### Developer — 新增、修改与直接受影响测试

根目录：

```sh
python3 scripts/check_governance.py
PYTHONPATH=tests:. .venv/bin/python -m unittest -v test_v2_automation_run_once test_operations_task_center test_v2_automation_operations test_task_flow_status test_manual_task_engine test_automation_entrance_recovery
```

将 F-1/2 的正式 fault regression 与 F-3/4/6 的真实查询/重开断言放入上述对应模块；保留并运行
原有识别同 Task 完整恢复、`test_conflict_recovery_keeps_the_original_automation_record`、
`test_scheduled_decision_summary_belongs_to_the_continuing_operator`、文件 partial/failed 独立计数、
8/9 分母、技术结束缺 Result、未返回调用、取消和终态不可写等直接受影响用例。此命令是受影响
模块回归，不是全仓 discovery；若实际改动触及其他读取消费者，补充对应受影响测试即可。

`web/`：

```sh
npm run test -- run src/entities/operations/run.test.ts src/entities/operations/automation.test.ts src/features/operations/OperationsInventory.test.tsx src/features/operations/AutomationWorkspaceReadModel.test.tsx src/features/operations/AutomationRouter.test.tsx
npm run typecheck
npm run build
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/task-flow.python.spec.ts --workers=1
```

覆盖失败状态不能被 recovered 字段覆盖、独立成功文件、记录各状态一致、错误/不可用形状和桌面/
窄屏实际读回。浏览器必须走原生恢复/确认/Worker 路径，不能只改 fake JSON 然后声称修正完成。
对实际修改的 Python 文件运行 `.venv/bin/ruff check <changed-python-files>` 和
`.venv/bin/ruff format --check <changed-python-files>`；对实际修改的 Web 文件运行
`npx eslint <changed-web-files>`、`npx prettier --check <changed-web-files>`；根目录 `git diff --check`。
占位符由真实本次修改清单替换，不扩大成 Developer 的全仓质量/测试验收。

### B — 独立验收、完整回归和 Slice-final 证据

- 审查原 Task Base..候选的完整范围，以及本修正 starting Head..候选；独立从 F-1 的真实入口
  复现故障，确认 F-1–8。必须有自动断言的修正后用例；旧 probe 捕获的 success-only assertion
  不能冒充通过。核对 schema/Result/初始时间未写回、源/目标实际效果和后续 Worker 零重放。
- T4 完整门禁使用 [workflow 共享命令](docs/development-workflow.md#shared-full-regression-commands)：
  全 Python、Web 质量/单元/默认浏览器、配置、依赖、RBAC/pin/fence/零变更/C→A/非重放，全部由 B
  执行记录。后端 SQL/API/native 输入已变的证据不能沿用旧候选；纯文档后继或确实同输入的证据
  复用须按 workflow 给出等价 diff 和实际身份，不把旧报告中的 PASS 当作新验收。
- `web/` 在 `npm run build` 后分别启动全新 harness 执行下列原生 spec，避免跨 spec 共享状态：

  ```sh
  npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/task-flow.python.spec.ts --workers=1
  npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts --workers=1
  npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/automation-workspace.python.spec.ts --workers=1
  npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/automation-run-once.python.spec.ts --workers=1
  ```

  核对 F-1 浏览器截图/交互，及八视图/四类恢复、记录过滤和成功率的正常对照；不是用历史 seed
  的 partial/paused 行证明当前生命周期。普通操作/源历史等最终覆盖仍按父 Slice 及实际共享影响补齐。
- 更新 wheel/容器安装消费者对 F-1/6 的同版本证明：从精确已提交候选的干净导出构建，先核对
  包内业务模块/前端资产与源码，避免旧 build/lib 残留；源树外执行现有真实准入/确认/fault/reopen
  用例。适用 wheel smoke、Docker security/restart/transfer 及其他最终制品门禁按共享规则由 B
  完成。保留每个包/镜像 digest、命令/cwd/候选、实际结果与稳定忽略目录下原始日志/截图。
- 原 7 项真实外部服务/耐久环境 skip 及初始 wheel/fake-server 失败等历史保留，不删断言、隐藏
  skip、加重试或放宽超时；本修正没有新增延期。Developer 无需先跑这些完整门禁才交接。

## Non-goals

不修改 Slice48 的用户结果、Task/Slice Base 或 Task48.2 的公式/原始自动化准入人群；不对旧
Task/status 做迁移、批量重标或跨版本升级。不新增生命周期/数据库权威/调度队列，不重做
Worker、结算、重试、权限或 Storage 操作。不通过改变后台 failed 为 completed 掩盖读取矛盾。
不增加第五恢复类型、通用技术失败恢复、附件自动重试、跨 Task 批量操作、未知效果重放、
自动回滚、页面布局改版或用户额外确认。普通操作、CLI/通知及其他消费者只在该共享读取改动
实际影响范围内修正/验证，不扩展产品。A-owned CURRENT/Closure/Roadmap 边界不由本计划修改。

## Planning checkpoint / 历史和验证指针

- 本轮起始：`/Users/songzhidong/mediaflow`，`main`，HEAD 为上述 Correction planning Head；
  tracked 干净，工作区/Git 可写，治理 preflight PASS。原有未跟踪 OS/log/reference/output 和
  `15` 均保留、不暂存；仅修改本 TASK.md。没有用户数据库/媒体、私有配置、实现、push 或部署。
- 当前 HEAD 与已审实现 `2d4f1ae037cc4642b7bcd4231a840cf40d70e7b6` 之间仅有文档变化。
  本轮复用且实际重新运行 A48-01 已有 SQLite probe，仍观察 durable failed、run completed、
  recordOutcome failed、metric failed 1；命令成功执行不表示缺陷修复通过。
- 原完整 Task48.1 计划/交接：`6f2115d1033779aa2d21a7f0b6ebd9f558f66345:TASK.md`；
  原 B PASS：`469ecc076c6efc660055f47277d7917a0b64a9aa:TASK.md`；
  Task48.2 PASS：`d448ce5d392865daadccb085af61e39d98f786c8:TASK.md`；
  原 Slice Closure Packet：`6c39d6ecdf40cad8f06e5e97f58bf47bdc388b49:TASK.md`。
  原 B 的通过/失败/跳过/制品限度保持历史事实，不代表本修正接受；本文件不复制旧证据流水账。
- A 的 probe/完整 JSON/summary 在本机忽略目录
  `.git/validation-evidence/2d4f1ae037cc4642b7bcd4231a840cf40d70e7b6/a-review/`；
  `recovery-sqlite-publication-probe.py` 的 SHA256 为
  `5cc04f467400c124c7466be28fe9f24fd12c012c5332599f24bd932817504458`。
  正式测试必须自包含，不能依赖该本机目录或声称远程可访问。

## Developer Completion Report

```text
Reviewed: DEVELOPER CHECKPOINT SUBMITTED, INDEPENDENT B REVIEW PENDING
Implementation Head: a80015e2f7d46e3ad1b8f7b14c453d1030e62104 — see git show --stat for the exact 7-file range
Base..Head: 35e6b2dbe637ceb27625cdbf8ef63b6730e99139..a80015e2f7d46e3ad1b8f7b14c453d1030e62104 (only this correction; parent docs untouched)
Decision: READY FOR B REVIEW — A48-01 corrected in the shared read basis, records display and Web decoder
Task blockers: none known to Developer; A48-01 readback now matches durable flow at Task/run/record/metric level
Next: INDEPENDENT B REVIEW (F-1–F-8), then refreshed Slice-final packet for A
```

### 实施内容（对齐计划步骤）

1. **正式故障回归（步骤 1，F-1/2/6）。** 新增
   `test_v2_automation_run_once.RunOnceApiTests.test_publication_write_failure_keeps_the_durable_failed_flow_authoritative`：
   复用既有真实准入/识别等待/决定/继续/分析/摘要/确认旅程，在
   `SQLiteTaskRepository.release_scheduled_claim` 的首次终态 completed 发布注入一次
   `sqlite3.OperationalError("database is locked")`（仅命中一次，断言 `injection==1`），
   随后用原 repository 断言 durable `failed`、Result `SUCCESS`、真实文件移动；再核对
   run 详情、status=failed/completed 过滤、All/Ended/Running 分区、attention=0、records
   顶层/result/recordOutcome/`已确认整理 1 个文件`、metrics（failed 1、evaluated 1、成功率 0）、
   零重放（再次 Worker 无可领取工作、文件与 Result 数量不变）与同版本重开。修复前用旧谓词
   复跑该用例确认失败于 `recovered_completion=True` 的状态矛盾（不是捕获后算通过）。
2. **共享读取服从流程事实（步骤 2）。** `mediaflow/infrastructure/sqlite_runtime.py`
   `_run_query_document`：`recovered_success` 由 `status IN ('failed','partial_success')`
   改为 `status = 'completed'`，并从 `derived_status` CASE 中移除该覆盖分支——终态分支是唯一
   流程权威；`recovered_completion` 仅在真实流程完成 + 确认恢复摘要 + 逐项已证实效果时为 1。
   同一 SQL 的 overview、服务端 status/outcome 过滤、分区/总数/游标、Automation latest
   全部自动对齐；`domain/operations_run.py::derive_run_status` 本就只读 durable 状态，未建第二套计算器。
3. **记录当前说明与历史保留（步骤 3，F-2）。** `_automation_record_query_document` 新增
   `current_waiting_count/current_unreadable_count/current_success_count`（当前 durable 证据列），
   冻结的 `task_initial_executions` 窗口/计数列原样保留；`automation_record_display` 的
   当前解释（recordOutcome.successItems、failed 分支等待/不可读原因、“已确认整理 X 个文件”）
   改读当前列，pending/running 的等待说明同样改读当前列。`service_api.py` 顶层/result/
   recordOutcome 与 failureStage 核对无需再改（其状态均来自同一 overview/record SQL）。
   缺失具体原因诚实显示“当前不可读”，原始异常不外泄（断言 `database is locked` 不在文档中）。
4. **Web 防矛盾展示（步骤 4，F-7）。** `web/src/entities/operations/run.ts`：解码层将
   `recoveredCompletion` 限定为 `status === "completed"` 才可能为真，failed/cancelled/running
   携带矛盾恢复字段时拒绝为 false，不自行推导成功；`OperationsLanding`/`AutomationInventory`
   渲染位置核对无需改动（其展示键控于该字段）。新增 `run.test.ts` 用例覆盖
   completed+facet、failed+矛盾 facet、running+矛盾 facet 与字段缺省形状。
5. **原生证明（步骤 5）。** `scripts/operations_inventory_harness.py`
   `run-automation-run-once-worker` 新增 `failureFixture=publication`：在真实引擎同一边界一次性
   注入 SQLite 写失败（无产品路由、无最终状态 seed）。`web/tests/e2e/task-flow.python.spec.ts`
   新增原生用例：真实 UI 冲突决策→继续→分析→摘要→确认→发布失败；桌面/窄屏读回“失败”+
   独立“成功 2”、无“已完成（恢复成功）”，record/recordOutcome/过滤器/指标增量（+1 failed、
   +1 evaluated、成功率=completed/evaluated）、零重放与 `/__harness__/restart` 后一致。

### 实际受影响测试（本轮全部实跑）

- `python3 scripts/check_governance.py` → PASS（实施前与收尾各一次）。
- `PYTHONPATH=tests:. .venv/bin/python -m unittest -q test_v2_automation_run_once
  test_operations_task_center test_v2_automation_operations test_task_flow_status
  test_manual_task_engine test_automation_entrance_recovery` → **154 passed**（含新增故障回归、
  修订后的 `test_conflict_recovery_keeps_the_original_automation_record`，修复前后各跑一次）。
- 新故障回归对旧谓词的失败复现：临时还原旧状态条件复跑 → 失败于 `recovered_completion True`
  矛盾；随后恢复修复代码。
- `web/ npm run test -- run src/entities/operations/run.test.ts src/entities/operations/automation.test.ts
  src/features/operations/OperationsInventory.test.tsx src/features/operations/AutomationWorkspaceReadModel.test.tsx
  src/features/operations/AutomationRouter.test.tsx` → **5 files / 124 tests passed**。
- `web/ npm run typecheck` → PASS；`npm run build` → PASS（产物已用于原生 spec）。
- `npx eslint` / `npx prettier --check`（run.ts、run.test.ts、task-flow.python.spec.ts）→ PASS。
- `.venv/bin/ruff check` + `ruff format --check`（sqlite_runtime.py、automation_record_display.py、
  test_v2_automation_run_once.py、operations_inventory_harness.py）→ PASS；根目录 `git diff --check` → 干净。
- 原生 e2e（全部实跑通过）：`tests/e2e/task-flow.python.spec.ts --workers=1` → **3 passed**
  （含新增 A48-01 原生用例）；直接受 harness 改动影响的
  `tests/e2e/operations-inventory.python.spec.ts --workers=1` → **43 passed**、
  `tests/e2e/automation-run-once.python.spec.ts --workers=1`（python.automation 配置）→ **5 passed**。

### 计划内既有断言的修订（1 处）

- `test_conflict_recovery_keeps_the_original_automation_record` 原断言成功恢复后
  `recovered_completion` 为 False；按 A48-01 修订语义（真实流程完成 + 必要文件恢复已证实）
  改为 assertTrue 并注明修订依据。该旅程的其余断言（冻结窗口、冻结计数、handling、metrics、
  重开）全部保持不变并通过；其余既有用例零改动。

### 剩余风险与移交说明

- 冻结证据列（`success_count/waiting_count` 等）仍保持冻结值供历史只读与 B 级检查；
  仅当前解释改读当前列。若 B 认为 completed 记录的 `recordOutcome.successItems` 也应
  展示冻结初值，需在 B 验收中裁决（当前实现展示当前成功数，与 F-1“成功数量为 1”一致）。
- 记录 failed 分支的 skipped/cancelled/attachment 原因仍读冻结优先列：A48-01 观察到的矛盾
  仅涉及 waiting/unreadable/零成功；若真实旅程中冻结与当前在这些类别上分叉，需另行评估
  （当前无已入口可发生的分叉场景，未扩大范围）。
- B 需按 Task 清单完成全量 Python/Web/其余原生 spec 与 wheel/容器消费者证明；
  Developer 未运行全仓回归（按 workflow 分工）。
- 工作区原有未跟踪文件（日志/output/`15` 等）与历史保持原样，未暂存、未清理。

## B Review Result

```text
Reviewed: NOT SUBMITTED
Decision: FIX REQUIRED — A48-01 REMAINS OPEN; CORRECTION ACCEPTANCE PENDING
Acceptance runs: NOT RUN FOR A CORRECTED CANDIDATE
Task blockers: A48-01
Slice Required Outcomes / Surfaces all satisfied: NOT YET RE-ESTABLISHED
Next: SAME TASK FIX LOOP; AFTER INDEPENDENT B PASS, REFRESH PACKET FOR A
```
