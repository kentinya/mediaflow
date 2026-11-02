# Task47.5 — FIX REQUIRED：补齐普通 CLI 的安全结束结算

A 的完整 Slice 终审以 **A-P1-1** 退回；B 已从现有 CLI 独立复现并完成本修正计划；
Developer 已按该计划完成修正并交 B 复核。继续同一个 Task47.5，保留原 ID/Base/Goal，
不另建 Task47.6 或独立小 bug，不改 Slice 边界。B 的规划未实施产品修复，也未声明 PASS、
SLICE READY FOR A REVIEW 或关闭。

Authority: committed [SLICE.md](SLICE.md#a-final-review--fix-required--2026-11-02)，
RO-1/2、AC-2/4/15/24 及原 RO-6/AC-20–25；
[Development Workflow](docs/development-workflow.md) 管修正、测试、审查和收尾。
要求依据：V2-TASK-001/002/003/005/006/008–010、REQ-TASK-005/006/007、
REQ-RECOVERY-006/009、REQ-RESULT-001–003、REQ-SAFE-*；按用户已提交修订解释。

```text
Task ID: 47.5
Task Type: SLICE
Parent Slice: 47
Status: READY FOR B REVIEW
Task Base: 75ddff55f8d5b2b1206c81804bfb5cbe9ed279a1
Difficulty: High
Test Level: T4
Planner / Reviewer: B
Current correction: A-P1-1 — ordinary CLI finished-pass capacity settlement
This turn: DEVELOPER CORRECTION IMPLEMENTED — READY FOR B REVIEW
```

## Preflight / checkpoint / prior facts

- 本轮起始 branch `main`，HEAD `001ff5bae318656709e02d4f47443a63882f4237`；
  `python3 scripts/check_governance.py` PASS，无预存 tracked 修改，工作区/Git 可写。
  原有 OS/log、`15`、docs 参考图片、output 参考目录/ZIP/HTML 等未跟踪内容全部保留、不暂存；
  不访问用户数据库、媒体或私密配置。
- Slice Base 保留 `5144ab1fc2344b06194969cc2c496835729664c0`；committed Slice 为
  FIX REQUIRED、Roadmap ACTIVE。A 的候选 `3cf1b6b4b59dbea0bbd2159c404e760f7bcd9417`
  未接受；本轮修正的比较起点为 `001ff5ba`，不是重设 Task/Slice Base。
- Task47.1–47.4 接受事实及 Task47.5 前序已通过场景保留。原完整计划/验收/六结果 packet：
  `62a566f9c7395fae14b5ee5df9dae987bb4bb201:TASK.md`；本次 A 结论：
  `001ff5ba:SLICE.md`。前序 B PASS 是该检查点的历史事实，不覆盖 A 新发现的缺口。
- 不修改 A-owned SLICE/Roadmap/Progress、CURRENT/TARGET 或接受历史；不派生代理、push、部署。

## Goal / complete journey

保留 Task47.5 原 Goal：同一来源版本最近一次正式整理结果为失败或部分失败：定时/运行一次
不自动处理；后来手动整理成功，就不再因更早失败排除，仍接受普通过滤/冲突规则。用户在
资源库 Files 明确选中整理时，可以看到上次失败/已知部分效果/未知效果的明显提醒，按原
摘要确认后执行一次新的正常整理。只用现有 Task 引擎、计划、冲突策略和确认，不再找独立
CLI 失败重试，不建立远端核验或附件恢复系统。

本修正补齐普通 CLI 原有能力的收尾，防止一个已经结束的失败请求堵住共享准入：

1. **入口/动作：** 使用现有 `mediaflow --config <bootstrap> organize <source> --execute --limit 1`；
   批量入口 `batch organize` 归一到同一调用链。权限、范围、pin 和执行意图不变。
2. **失败可见：** 目标写入磁盘满，已经完成的步骤、partial/unknown Result、源/目标事实
   保留；CLI 正常输出 Task ID 与本次摘要，报告业务失败，不以收尾异常吞掉结果。
3. **结束状态：** 所有调用已返回、没有待处理机器工作且持久结果满足已有安全条件时，
   Task 诚实结算并归还名额；全部只剩人工决定则等待人工、占 0，保留待决定文件所有权。
   取消在安全边界确认，保留已完成/失败结果，不中断正在进行的 Storage 调用。
4. **后续操作：** 磁盘恢复后，用户整理另一独立文件 B，可以正常准入和完成；reopen 后
   结果、未知证据和容量仍一致。对原失败 A 的后续新请求沿用原手动/自动入口规则，
   释放名额本身不重放 A，不把未知效果改成已验证。

## Actual-code gap / bounded scope

B 对照实际调用链核对 A 的结论，并独立复跑其真实入口探针：

- `final_cli.py` 的 `final_main` 先经 `_admit_direct_organize_task`、
  `_drive_direct_organize_claim` 取得共享 Task/claim，再由 `MediaOrganizerService` 和真实
  OrganizerExecutor 处理文件；`batch organize` 在同文件归一为 `organize`。
- `_settle_direct_organize` 在终态分支调用 `scheduling.settle`、人工等待分支调用
  `defer_to_human`，均未启用已有 `close_recorded_unknown_boundary`。`final_main` 中该
  pass 返回后的 `acknowledge_control` 同样未传；需一起核对，不能只修正常终态分支。
- 现有 `ManualTaskEngineWorker` 已在其 pass 完成后的 settle/defer/control 使用该边界。
  `TaskSchedulingService` 与 SQLite `release_scheduled_claim` 已提供 claim/control revision、
  持久结果、没有机器兄弟项等核对；本次优先接通这些规则，不另写宽松清理实现。
- CLI 的 `finally` 停止临时 Worker 注册，不等于结算 Task/claim/容量；不得以删注册、
  删锁、改容量统计过滤条件或读时修数据库代替真正收尾。
- `_drive_direct_organize_claim` 的 begin_work 失败处理发生在 pass 尚未运行时，不能
  因同样调用 acknowledge_control 就一律套用“调用已返回且结果已持久化”的完成声明。
- 修改面预期为 `mediaflow/final_cli.py` 与实际直接受影响的测试。仅发现现有共享边界不能
  满足本修正时，才最小调整 application/kernel；保留默认拒绝及原有安全检查。没有新增
  schema、队列、Web 页面、恢复类型、远端探测或整个 CLI/Worker 统一重构的授权。

## Developer guidance — 简单实施顺序

1. **先固化真实失败回归。** 复用
   `tests/test_automation_entrance_recovery.py::entrance_journey` 的 managed 配置、临时
   SQLite/LocalStorage、fake Provider 和真实 `final_main`。只在目标 staging 写入处注入
   `OSError(ENOSPC)`；不得 mock 整个 Executor/settle 或手填终态来替代主回归。修改前
   断言应暴露：业务 partial 已落库但 CLI exit 2、无摘要、Task running/claimed、容量 1。
2. **在真实 pass 返回后的边界接入已有安全结算。** 逐一处理 `_settle_direct_organize`
   的终态/等待人工，以及 `final_main` 的取消确认分支。可使用已有
   `close_recorded_unknown_boundary=True`，前提是该调用点确为本轮处理已返回的安全边界；
   实际处理中的项、缺失结果、claim 丢失或控制请求变化仍由内核拒绝释放。不要全局修改
   默认值、在 finally 无条件释放，或把超时/进程退出视为远端效果不存在的证明。
3. **保持当前状态与摘要真实。** 用持久的本 Task/item 结果计算 aggregate/计数，保留
   已接受取消及正确的人工等待状态，避免旧 task 对象覆盖当前状态。让正常 Task ID /
   `render_summary` 路径走完；partial/失败按现有业务失败约定返回 1，成功 0，取消保留
   既有约定；真正准入/安全拒绝仍按原规则报错，不 catch 后伪装成功。临时 Worker 按原
   finally 退场；不重新分析、不重做成功兄弟项、不改 Result/unknown/pin。
4. **补齐同一缺口的可达分支并交接。** 覆盖下面 AC-C1–5。混合人工等待必须由真实
   规则/Provider 输入产生，再让另一项真实写失败；确认这两个分支实际都到达。
   活跃调用/取消可在真实 Storage 调用暂停，用现有取消入口发起，再放行调用，验证
   归还名额前后。claim/缺 Result 的安全反例复用现有 kernel 测试，不虚构用户路由。
   先跑受影响测试，提交可审查 checkpoint、READY FOR B REVIEW 和实际结果/风险；不跑
   全仓验收、不自判 PASS、不规划下一 Task。

## Acceptance Criteria

- [ ] **AC-C1 — 真实 CLI 磁盘满结束。** 上述单文件 COPY 产生 partial 与真实已知步骤/
  attempted_unverified/uncertainEffects；源保留、无虚构目标成功。CLI 输出 Task ID 和失败
  摘要，返回业务失败 1；Task aggregate 与项目结果一致，queue settled、容量 0，临时
  Worker 已停止。旧 Result、步骤、未知证据和 pin 不因结算被清空/改写。
- [ ] **AC-C2 — 后续准入与同版本持久化。** 容量为 1；移除故障后，另一独立文件 B
  经真实 CLI 正常准入、实际整理并再次释放名额。重开同一 DB，A 的失败和未知记录不变，
  A/B 结束状态与容量 0 保留；不靠重开、读页面或清库才释放，不产生 A 的新执行。
- [ ] **AC-C3 — 批量/人工等待。** `batch organize`/目录同一路径保留成功、失败与等待
  决定的独立结果。全终态混合批次结束占 0；partial/unknown 与人工等待混合、机器工作
  均返回后为 waiting_human、占 0，待决定文件仍不能被另一任务抢占。原四类决定→分析→
  摘要→确认可在同 Task 继续；本次不替失败/未知兄弟项续作。已有正常单文件成功、零效果
  失败、四类继续与零变更分析不退化。
- [ ] **AC-C4 — 取消与活动保护。** CLI pass 在目标故障后收到取消，安全确认能完成并
  释放名额，保留 partial Result；已完成/失败兄弟结果不被改成 cancelled。真正调用仍
  在进行或项目仍 processing 时占 1，取消请求本身不能提前归还；返回并完成允许的结果/
  取消结算后占 0。原 claim/fence/控制版本和没有结果的未知边界仍不能被此调整绕过。
- [ ] **AC-C5 — 原 Task/Slice 行为保留。** 原 AC-T1–7 / Slice AC-20–25 保持：最新同版本
  failed/partial 自动排除、后来手动成功解除旧排除、Files 简短提醒与正常确认、原历史/
  pin/兄弟项不改写、活动来源互斥、四类同 Task 继续、CLI retry-failed 退役和普通 CLI/
  remote 的原有来源/授权规则。不得靠新恢复页、自动重放或放宽内核完成本修正。
- [ ] **AC-C6 — 独立复核。** B 在完整原 Task Base..新候选上给出 PASS/FIX REQUIRED，
  完成适用 T4 验收，重评全部 Slice RO-1–6/AC-1–25；满足后更新 Closure Packet 交 A，
  不由 B 关闭 Slice，不将前序已通过范围作为新的任意扩展任务。

## Required Tests

遵守 [workflow §6](docs/development-workflow.md#6-test-levels)；每轮测试时间小于本轮总
用时 50%，优先真实关键复现，不用空等/删断言/重试/放宽超时凑比例。只用隔离临时媒体、
SQLite 和 fake/local Provider；不读取生产配置或真实远端。

### Developer — new / changed / directly affected

在现有 `test_automation_entrance_recovery.py` 增加真实 CLI 结算旅程，复用已有 fixture；
必要的边界反例放现有 `test_task_scheduling.py` / fencing 测试，避免新造过程工具。

```bash
.venv/bin/python -m unittest tests.test_automation_entrance_recovery tests.test_task_scheduling tests.test_task_scheduling_fencing tests.test_batch_cli tests.test_task_retry tests.test_organize_source_history
.venv/bin/ruff check mediaflow/final_cli.py tests/test_automation_entrance_recovery.py tests/test_task_scheduling.py tests/test_task_scheduling_fencing.py
.venv/bin/ruff format --check mediaflow/final_cli.py tests/test_automation_entrance_recovery.py tests/test_task_scheduling.py tests/test_task_scheduling_fencing.py
.venv/bin/python scripts/check_governance.py
git diff --check
```

compileall 对实际修改的模块执行。若修改共享 application/repository，追加
`tests.test_manual_task_engine`、`tests.test_task_source_ownership_race`、
`tests.test_manual_organize_execution` 等直接受影响模块及 changed-file 静态检查。
主回归必须穿过实际 CLI，并断言 stdout/退出码/持久 Task/item/Result/容量和文件效果，
不能只有“函数收到 True”或 mock 调用断言；非法/队满/冲突/失败与重要边界由这组直接
受影响测试保留。本计划不把全 Python/Web/E2E、容器与发布矩阵交给 Developer。

### B — independent acceptance / T4

- 在新候选上独立重现 A 的原命令和 AC-C1–4，重点检查“命令已失败退出 → 别的文件
  能准入 → reopen 后仍诚实”，以及真实活动调用/取消不提前释放。A 的旧探针断言
  当前 bug，修复验收需改为断言正确结果，不能把旧脚本的非零退出误认成回归。
- 审完整 `75ddff55f8d5b2b1206c81804bfb5cbe9ed279a1..candidate`，同时复核本轮
  相对 `001ff5ba` 的修复增量；原 Scope/Base/安全规则及已通过结果均须保留。
- 执行 [shared full T4 gates](docs/development-workflow.md#shared-full-regression-commands)：
  新候选完整 Python、质量/公开示例/禁依赖、适用真实原生、干净 wheel/source-external
  CLI、Docker fresh/security/同版本 restart。安装包中也实际验证本次 CLI 故障/后续准入
  及结果，不以源码测试或旧 CLI help 拒绝测试代替。构建使用干净 committed context，
  避免预存 build/lib 混入已退役模块；这是 B 的验收准备，不新增构建平台。
- Web 全量 unit/fake E2E/static/build 只有在执行输入/依赖/配置/产物均未改变且有明确
  diff 时，才能复用 B 匹配证据；变更后的 Python native 旅程重新执行。复核 Files
  提醒/确认、四类继续、Automation 原记录和容量/来源所有权区别；若共享执行输入改变，
  相应 installed/container/native 不用旧 PASS 替代。完整测试/准确命令、复用、skip、
  失败及耗时由 B 如实记录，环境和证据准备问题不自动转成 Developer 返工。
- 只有所有 Required Outcomes/Surfaces 满足才重新提交 SLICE READY FOR A REVIEW。
  旧任务/跨版本升级及 V1 支持仍明确排除，不将未运行外部耐久 profile 写成已通过。

## Non-goals / frozen boundaries

不新增 Task/队列/Worker 并行系统，不重构整个引擎/CLI，不修改默认安全拒绝或容量定义；
不新增 schema/来源接管规则/历史删除；不清空旧未知效果、不自动重放、不恢复 retry-failed
或 Pause/resume；不新增远端停止/完成证明、附件重试、通用恢复/回滚、UI 例行确认；
不改变入口权限、pin、计划/冲突/覆盖/删源授权；不修改 Storage/Provider、不做旧任务/
跨版本升级/V1 支持；不改 A-owned 合同、Roadmap/Progress 或关闭 Slice。

## B planning assessment / current decision

```text
Inspected checkpoint: 001ff5bae318656709e02d4f47443a63882f4237
Decision: FIX REQUIRED — A-P1-1 independently reproduced; correction plan complete
Implementation this turn: NONE
Task/Slice remaining outcome: ordinary CLI finished-pass settlement and required acceptance
Next: Developer implements this same Task correction; B reviews fresh candidate
```

B 本轮实际复现与 A 一致：partial Result 已持久化，但 CLI exit 2、无摘要、Task running /
queue claimed、容量 1；下一不同文件 queue-full；reopen 后仍占 1。探针只在真实目标写入
处注入 ENOSPC，不造路由/手填业务状态。用时约 0.33 秒，远低于本轮用时 50%；没有跑
产品全量或宣称修复通过。证据：
`.git/validation-evidence/001ff5bae318656709e02d4f47443a63882f4237/b-correction-plan/`。
详细 A 证据与前序 B 验收留在对应 Git/ignored 目录；未重写历史 PASS，也未交新的就绪 packet。

## Developer Completion Report — READY FOR B REVIEW

```text
Task: 47.5 (same ID/Base/Goal; A-P1-1 correction only)
Implementation checkpoint: 2e1e293ed7901b897ac316209c26c4ae4cd29556
Task Base: 75ddff55f8d5b2b1206c81804bfb5cbe9ed279a1
Correction start: 001ff5bae318656709e02d4f47443a63882f4237
Status: READY FOR B REVIEW
```

### 实际改动

- `mediaflow/final_cli.py`：仅在普通 CLI pass 已返回的安全边界启用已有
  `close_recorded_unknown_boundary=True`：
  `_settle_direct_organize` 的终态 `settle`、人工等待 `defer_to_human`，以及
  `final_main` 的取消/控制 `acknowledge_control`。`_drive_direct_organize_claim` 的
  begin_work 失败路径未加该标志；默认安全拒绝、容量定义和内核检查未改。
- `tests/test_automation_entrance_recovery.py`：复用现有 managed fixture、真实
  `final_main`、SQLite/LocalStorage/Executor 和 fake Provider，只在目标 Storage 写入
  处注入真实 `OSError(ENOSPC)`。新增真实 CLI 磁盘满→partial/unknown→exit 1/摘要/
  settled/容量 0→另一文件正常准入→同版本 reopen；目录成功+失败混合批次；partial+
  人工等待混合；故障后取消。均断言 Task/item/Result/容量/文件效果，不只 mock 调用。
- `tests/test_task_scheduling.py`：新增 close-boundary 反例，证明 pass 标志不会在
  仍有 processing 兄弟项时释放 claim/容量。
- 未改 schema、队列、Storage/Provider、权限、pin、Web 或 A-owned 文档；未 push。

### 实际验证（本机，临时隔离媒体/SQLite/fake Provider）

| 命令 | 实际结果 |
|---|---|
| 新增 4 条真实 CLI 旅程 + 1 条 kernel 反例（定向） | 5 tests OK，0.314s |
| `.venv/bin/python -m unittest tests.test_automation_entrance_recovery tests.test_task_scheduling tests.test_task_scheduling_fencing tests.test_batch_cli tests.test_task_retry tests.test_organize_source_history` | **97 tests OK**，6.312s；有既有 SQLite/SSL ResourceWarning，无失败 |
| `.venv/bin/python -m unittest tests.test_task_persistence tests.test_manual_organize_execution tests.test_task_source_ownership_race` | **68 tests OK**，2.760s |
| `ruff check` + `ruff format --check`（final_cli、两个测试模块、fencing） | 全部通过 |
| `compileall`（final_cli、两个修改测试模块）、`check_governance.py`、`git diff --check` | 全部通过 |

本轮实际测试执行约 10 秒，远低于本轮用时的 30%。A 的旧探针断言的是修复前 bug，
修复后其旧断言必然失败；实际输出已变为 exit 1、Task ID+SUMMARY、partial/unknown
Result 保留、queue settled、容量 0，随后另一文件 exit 0，reopen 后容量仍 0。未把
该旧断言失败误报为产品回归。

### 已知失败 / 剩余风险

- 未运行 B-owned 的完整 Python/Web/native/wheel/Docker/restart 验收；没有自称 PASS、
  SLICE READY FOR A REVIEW 或关闭 Slice。
- 尝试用 fixture 的多候选 `batch organize` 做端到端混合批次时，`process_all_libraries`
  的 `storage:path` source 被 parser 当作标题，两个候选进入 waiting_metadata_correction，
  未到达结算。该链路本轮未修改；本修正以目录入口覆盖同一 `final_cli` 结算分支，
  batch 端到端证据留给 B 判断是否需要另案处理。
- 人工等待场景的 Task aggregate 仍沿用现有 direct CLI 语义（queue waiting_human、
  Task pending），本轮只修正容量结算，未扩大为状态重设计。
