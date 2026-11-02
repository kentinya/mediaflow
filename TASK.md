# Task47.5 — FIX REQUIRED：批量根目录文件的解析输入

B 已独立复核候选 `46f44be43a39a81cf17146aa5db2c077bcde97ee`。A-P1-1 的普通 CLI
名额结算修复通过，终态/人工等待/取消三处接通已有安全规则，不要求重做。
当前唯一 P1 为 **B-P1-1**：真实 `batch organize` 对资源库根目录文件把 Storage 展示前缀
混入媒体标题，错误转为人工元数据修正；同文件目录入口成功。该问题在原 Task Base 也
存在，不是 `2e1e293e` 引入；它属于原 AC-C3 与 RO-2/AC-4/24 明确包含的普通批量入口。
继续同一 Task ID/Base/Goal，按末尾当前修复指导完成；无新 Task、无 Slice 范围变更。
Developer 已按该指导完成修正并交 B 复核；本轮未声明 PASS、SLICE READY FOR A REVIEW 或关闭。

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
Current correction: B-P1-1 — batch root-file parsing; A-P1-1 verified fixed
This turn: DEVELOPER B-P1-1 CORRECTION — READY FOR B REVIEW
```

## Preflight / checkpoint / prior facts

- 本轮起始 branch `main`，HEAD `001ff5bae318656709e02d4f47443a63882f4237`；
  `python3 scripts/check_governance.py` PASS，无预存 tracked 修改，工作区/Git 可写。
  原有 OS/log、`15`、docs 参考图片、output 参考目录/ZIP/HTML 等未跟踪内容全部保留、不暂存；
  不访问用户数据库、媒体或私密配置。
- B 在 `46f44be43a39a81cf17146aa5db2c077bcde97ee` 确认 A-P1-1 已修复、仅余 B-P1-1；
  Developer 从 `245b2a7b` 继续同一 Task，修正 checkpoint 为 `32db236e`，未 rebase/重写历史。
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

## A-P1-1 planning gap / bounded scope（本轮修复已通过）

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

## A-P1-1 Developer guidance（保留；本轮不重做）

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

- [x] **AC-C1 — 真实 CLI 磁盘满结束。** 上述单文件 COPY 产生 partial 与真实已知步骤/
  attempted_unverified/uncertainEffects；源保留、无虚构目标成功。CLI 输出 Task ID 和失败
  摘要，返回业务失败 1；Task aggregate 与项目结果一致，queue settled、容量 0，临时
  Worker 已停止。旧 Result、步骤、未知证据和 pin 不因结算被清空/改写。
- [x] **AC-C2 — 后续准入与同版本持久化。** 容量为 1；移除故障后，另一独立文件 B
  经真实 CLI 正常准入、实际整理并再次释放名额。重开同一 DB，A 的失败和未知记录不变，
  A/B 结束状态与容量 0 保留；不靠重开、读页面或清库才释放，不产生 A 的新执行。
- [ ] **AC-C3 — 批量/人工等待。** `batch organize`/目录同一路径保留成功、失败与等待
  决定的独立结果。全终态混合批次结束占 0；partial/unknown 与人工等待混合、机器工作
  均返回后为 waiting_human、占 0，待决定文件仍不能被另一任务抢占。原四类决定→分析→
  摘要→确认可在同 Task 继续；本次不替失败/未知兄弟项续作。已有正常单文件成功、零效果
  失败、四类继续与零变更分析不退化。
- [x] **AC-C4 — 取消与活动保护。** CLI pass 在目标故障后收到取消，安全确认能完成并
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

## Prior planning assessment — 001ff5ba（历史结论）

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

## Developer Completion Report — B-P1-1 correction — READY FOR B REVIEW

```text
Task: 47.5 (same ID/Base/Goal; B-P1-1 correction only)
Implementation checkpoint: 32db236e5534b15bd4b92aa12c5b9ab18511e96a
Task Base: 75ddff55f8d5b2b1206c81804bfb5cbe9ed279a1
Correction start: 245b2a7b (B review checkpoint 46f44be4; no rebase)
Status: READY FOR B REVIEW
```

### 实际改动

- `mediaflow/application/media_organizer.py`：`_run_read_only_strategy` 不再把展示用
  `source` 交给 Parser；解析使用 `process_file` 已持有的确切 `storage_path`
  （`storage_path or source` 仅作无路径兜底）。`source` 仍用于 TaskItem/Result 展示身份、
  日志、来源所有权、pin/授权；未按冒号切割字符串、未改 Parser/Provider/RecognitionRule/
  Storage/Executor/容量或 schema。目录/子目录、root 文件、NFO 上下文和来源锁继续使用同一
  Storage-relative 证据。
- `tests/test_automation_entrance_recovery.py`：复用 managed fixture、真实 CLI/SQLite/
  LocalStorage/Executor 和 fake Provider，新增两个真实 `batch organize` 旅程：
  1. 根目录 `One`/`Two` 的 Provider 查询记录为 `One`/`Two`，一项真实 COPY 成功、另一项目标
     写入 `ENOSPC`；断言 `partial_success`、独立 item/Result/unknown、exit 1+摘要、
     queue settled/容量 0、reopen 不重放。
  2. `Movies/With: Colon.2003.mkv` 由 directory RecognitionRule 命中，证明子目录证据来自
     Storage-relative path、真实冒号文件名未被裁剪，来源/Result/展示身份分别正确。
  fixture 仅增加可选 `recognition_rules`，不改变既有旅程的默认配置。
- 未修改 A-owned 文档、Web、Worker/内核默认拒绝；未 push/部署。

### 实际验证（本机，临时隔离媒体/SQLite/fake Provider）

| 命令 | 实际结果 |
|---|---|
| 修复前复跑两条新回归（临时还原旧解析输入，已恢复） | 2 tests FAILED，分别 `1 != 0` 与 Provider 查询 `[]`，确认测试命中 B-P1-1 |
| 两条新真实 `batch organize` 旅程定向 | 2 tests OK，0.160s |
| `.venv/bin/python -m unittest tests.test_automation_entrance_recovery tests.test_resource_library_pipeline tests.test_final_integration tests.test_media_parser tests.test_organize_source_history tests.test_task_scheduling tests.test_task_scheduling_fencing tests.test_recognition tests.test_nfo_parser tests.test_manual_task_engine tests.test_task_source_ownership_race tests.test_manual_organize_execution tests.test_task_persistence tests.test_batch_cli tests.test_task_retry tests.test_manual_organize_preview` | **256 tests OK**，15.546s；仅既有 SQLite/SSL ResourceWarning，无失败/skip |
| `ruff check` + `ruff format --check`（media_organizer、entrance tests） | 全部通过 |
| `compileall`（两个修改模块）、`check_governance.py`、`git diff --check` | 全部通过 |

本轮测试执行约 16 秒，低于本轮用时的 30%。证据（本地 ignored）：
`.git/validation-evidence/developer-b-p1-1/`（`affected-tests.log`、
`static-checks.log`、`pre-fix-regression.log`）。

### 已知失败 / 剩余风险

- 未运行 B-owned 的完整 Python/Web/native/wheel/Docker/restart T4 验收；没有自称 PASS、
  SLICE READY FOR A REVIEW 或关闭 Slice。
- 共享 `_run_read_only_strategy` 现在对所有 `process_file` 入口使用 Storage-relative
  path 解析；这是本 Task 要求的解析输入修正，已用 recognition/NFO/manual/CLI 回归覆盖。
  B 仍应按 T4 复核现有规则若依赖展示根绝对前缀时的实际配置语义。
- 未新增不同 Storage ID 的多资源库 batch 专属旅程；既有 multi-storage pipeline 测试通过，
  修复未触碰 Storage/source ownership 代码。B 的独立验收仍应覆盖其清单。

## B Review Result — FIX REQUIRED（当前）

```text
Task Base: 75ddff55f8d5b2b1206c81804bfb5cbe9ed279a1
Reviewed Head: 46f44be43a39a81cf17146aa5db2c077bcde97ee
Implementation checkpoint: 2e1e293ed7901b897ac316209c26c4ae4cd29556
Correction comparison: 5d56e9ec..46f44be4
Branch / entry state: main; no tracked edits; pre-existing untracked files preserved
Decision: FIX REQUIRED
A-P1-1: FIX VERIFIED
Remaining Task blocker: B-P1-1 — batch root-file parsing uses display identity as media path
Next: SAME TASK FIX LOOP; no new Task or Slice closure
```

已核对完整原 Task Base..Head 的 36 文件清单，结合此前完整范围审查重评现存结果，
逐行复核本轮 3 个执行/测试文件的增量及真实调用链；另 1 文件为交接报告。
产品改动只有 CLI 三个安全结算调用，没有修改内核默认拒绝、schema、Web 或 Provider。
未把 Developer 报告或之前的全量 PASS 当作当前候选的接受结论。

### 已通过的交付结果

- **原 A 复现改为正确结果断言后通过。** 单文件真实目标写入 ENOSPC → partial/
  attempted_unverified/CREATE_DIRECTORY/mutation_outcome 保留 → CLI exit 1、Task ID +
  SUMMARY → queue settled、容量 0；另一独立文件随后 exit 0，reopen 后容量仍 0。
- **混合终态和人工等待通过。** Developer 的目录成功/部分失败、部分失败/人工等待及
  取消旅程由 B 重新执行；71 项 scheduling/fencing/entrance 组合全部通过（3.018s）。
  等待人工时 queue 为 waiting_human、容量 0，记录未知效果不再被当作活跃调用。
- **真实活动调用与取消通过。** B 在实际目标 Storage 写入处暂停，通过现有
  `tasks cancel <taskId>` 发出取消；调用仍阻塞时容量 1、无 Result，未提前释放。
  放行调用使真实写入返回 ENOSPC，随后 Task cancelled、容量 0，partial/unknown Result
  保留，CLI 输出正常。内核仍拒绝用完成标志释放 processing 兄弟项。

### 唯一 P1 — 批量根目录文件被错误识别为需要人工修正

**完整操作旅程：** 临时资源库根目录放 `One.2001.mkv`、`Two.2002.mkv`，配置合法
电影规则、COPY 策略和明确可匹配的本地 Provider 候选，执行已有命令
`mediaflow --config <bootstrap> batch organize --execute --limit 5`。实际 Provider 搜索
标题为 `source:One` / `source:Two`，两个文件进入 waiting_metadata_correction、无 Result、
无目标媒体。用户本来提交正常批量整理，却被要求人工修正本可自动识别的文件。
相同配置/内容使用 `organize <source-directory>`，查询为 One / Two、两个真实 COPY 成功；
使用 batch 处理 `Movies/` 子目录中的同名文件也成功，定位到根目录文件路径差异。

**真实原因：** `MediaOrganizerService.process_all_libraries` 构造展示用
`StorageID:relative/path` 并传给 `process_file`；`_run_read_only_strategy` 再把这个展示
字符串当作真实解析路径传给 `StrategyTestRunner.run_path`。根目录文件没有目录分隔符，
`file_context_from_path` 的 filename 因而含 `source:`，随后污染标题和 Provider 查询。
这不是 fixture 未提供候选，也不是要求解析真实媒体内部流。

**来源与范围：** B 在干净 `git archive 75ddff55` 上用同一真实入口重新执行，现象一致，
没有虚构 Base 故障。展示字符串构造在历史 `7d957971`（2026-08-21）已存在，当前策略
接缝可追溯 `ae18b208e`（2026-08-23）；未独立确定最早哪次组合开始触发此 bug，不归因
于本轮三处结算修改。Task 的 AC-C3 明确要求 batch/目录，Slice RO-2/AC-4/24 保留普通
CLI/batch 能力；因此本次不能用“目录测试已过”或“旧链路未改”豁免该缺口。只修现有
路径输入，不扩展 Parser/Provider 功能，不另建独立 bug 或新 Slice。

### Developer 当前修复指导（仅 B-P1-1）

1. 在现有 `test_automation_entrance_recovery.py` 固化真实 batch 根目录回归。复用现有
   managed fixture，两个普通根目录文件、正确候选、真实 CLI/SQLite/Storage/Executor；
   记录实际 Provider 查询，断言标题 One/Two、实际结果/唯一目标媒体、Task/容量一致。
   同配置保留目录/子目录对照，不能给假 Provider 增加 `source:` 候选、宽松忽略前缀、
   手工选 metadata identity 或换用目录命令来绕过。
2. 在 `process_all_libraries → process_file → _run_read_only_strategy → run_path` 的
   实际接缝，区分展示身份和真实解析路径/上下文，使用已有确切 Storage-relative path
   等来源证据构造正确 filename/目录。保留显示/日志/结果的 Storage 身份与授权/版本绑定。
   不把 Storage 展示协议塞进 Parser，不全局按冒号切割用户路径，不直接改 Provider 搜索
   来掩盖输入污染。具体最小实现由 Developer 选择，不重构整条处理管线。
3. 保留 RecognitionRule 的路径语义、目录/NFO/多集/标签证据、跨库来源身份、命名/分类、
   source ownership、历史 gate、只由 Executor 写入和原 pin。若调整共享 StrategyTestRunner
   或上下文构造，补其直接受影响回归；无需新增路由、schema、Storage 能力或处理引擎。
4. 让真正 `batch organize` 到达已修好的结算：一项实际 COPY 成功、另一项目标写 ENOSPC，
   断言 partial_success/独立 Result/未知证据、exit 1 和正常摘要、结束容量 0、reopen 不重放。
   保留已通过的 A-P1-1 单文件/等待人工/取消保护。完成后交 READY FOR B REVIEW，B 再做
   新候选全量验收和全部 Slice 结果重评；不要提前判断 PASS 或扩大为其他缺口清理。

**补充验收（原 AC-C3 内的必需结果）：**

- [ ] 实际 root-file batch 使用正确文件名/目录证据查询 One/Two，正常 COPY 与目录入口
  一致；不制造人工元数据问题，不因改为宽松 Provider 或硬编码身份获得通过。
- [ ] root 与子目录、不同 Storage ID 的实际来源/Result/锁保持准确，无冒号字符串裁剪
  对真实文件名的误伤；若调整共享上下文，原 recognition/NFO/目录/标签等适用回归通过。
- [ ] root-file batch 的成功/真实写失败混合到达结算，保留每项事实并释放共享容量；
  单文件、真实取消/活动调用和原 AC-C1–6/AC-T1–7 不退化。

**Developer 受影响命令：**

```bash
.venv/bin/python -m unittest tests.test_automation_entrance_recovery tests.test_resource_library_pipeline tests.test_final_integration tests.test_media_parser tests.test_organize_source_history tests.test_task_scheduling tests.test_task_scheduling_fencing
```

若改变 Recognition 或共享上下文，追加 `tests.test_recognition`、`tests.test_nfo_parser`
及实际受影响模块；对实际改动文件跑 Ruff format/check、compileall、governance 和
`git diff --check`。只跑受影响测试；B 原 T4/native/干净 installed/容器计划继续有效。

### 实际结果、证据与 Slice 重评

本轮证据根：`.git/validation-evidence/46f44be4/b-review/`（本地 ignored）。
`cli-capacity-fixed.log`、`active-cancel.log` 为通过的原阻塞/实际活动保护；
`focused.log` 71 OK；`batch-entry.log` 保存三种真实入口对照；
`batch-entry-task-base.log` 是原 Task Base 干净上下文对照；
`batch-root-acceptance.log` 正确期望断言失败，明确指出 Storage 前缀进入真实查询。
相关 probe 只暂停/注入真实依赖处故障，不造端点或手填 Task 业务状态。

按 workflow 的已证实阻塞提前退回规则，本轮未运行昂贵完整 Python/Web/wheel/Docker
矩阵；没有宣称通过。修复后的候选仍须 B 完成原 T4 计划，不能仅凭 71 项通过接受。
B 本轮只编辑 TASK.md、保留原未跟踪文件，不改 A-owned 合同/指针或产品/测试代码。

| 全部 Slice 结果 | 当前重评 |
|---|---|
| RO-1 | A 的 CLI 容量结算缺口已在本候选修正；原共享容量/活跃调用/取消规则保持。 |
| RO-2 | **未完成**：普通根目录 batch 的解析输入错误，未完成现有正常整理旅程。 |
| RO-3 | 原四类同 Task 继续接受基线保留；本轮不能把错误解析制造的人工修正当正常恢复。 |
| RO-4 | Job 退出/fresh/同版本安全接受事实保留；本轮未改 schema，未声称新产物/重启验收。 |
| RO-5 | 原 Web/管理接受基线保留，普通 CLI batch 表面有命令但不能完成上述正常旅程。 |
| RO-6 | 自动历史 gate/Files 提醒/手动新整理/CLI retry-failed 退役的既有结果保留；没有新增历史规则，最终整体回归仍待修复候选。 |

Task 保持 FIX REQUIRED，不规划下一 Task，不交新的 SLICE READY FOR A REVIEW，不关闭 Slice。

本轮日志执行区间合并并为短检查预留 1s，测试上界 6.5s；保守总用时 413.6s，
测试占比上界 1.6%，小于 50%；见证据目录 `timing.json`。
