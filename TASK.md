# Task47.5 — B Review PASS；交 A 终审

完整审查范围：`75ddff55f8d5b2b1206c81804bfb5cbe9ed279a1..5c808d4a67bedfbafb71d88a1ffa8d3480ef5316`。
A-P1-1（CLI 结束名额）与 B-P1-1（批量根目录解析）均已验证修复，无剩余 P0/P1。
全部 Slice RO-1–6/适用 AC-1–25 已重评完成，**SLICE READY FOR A REVIEW**，不再规划实施。
原 Base/Goal 与用户边界不变；A-owned Slice 的上次 FIX REQUIRED 结论/状态由 A 复核新候选
后更新，B 不代 A 终审、改写合同或关闭 Slice。下方保留最后 Developer 交接元数据；
本次 B 的接受结论与新 Closure Packet 在末尾，未授权继续开发。

前序计划/修正历史见 `5d56e9ec:TASK.md`、`245b2a7b:TASK.md`、`5c808d4a:TASK.md`；
上一完整 packet 见 `62a566f9:TASK.md`，Task47.4 接受事实见 `980ce42a:TASK.md`。

Authority: committed [SLICE.md](SLICE.md#a-final-review--fix-required--2026-11-02)，
RO-1/2、AC-2/4/15/24 及原 RO-6/AC-20–25；
[Development Workflow](docs/development-workflow.md) 管修正、测试、审查和收尾。
要求依据：V2-TASK-001/002/003/005/006/008–010、REQ-TASK-005/006/007、
REQ-RECOVERY-006/009、REQ-RESULT-001–003、REQ-SAFE-*；按用户已提交修订解释。

## Latest Developer submission metadata

以下保留实现交接记录；当前 B 结论见文首和末尾 Review Result，已无待开发内容。

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
Current handoff: B ACCEPTANCE COMPLETE — A REVIEW PENDING
```

## Original planning preflight / prior facts

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
- [x] **AC-C3 — 批量/人工等待。** `batch organize`/目录同一路径保留成功、失败与等待
  决定的独立结果。全终态混合批次结束占 0；partial/unknown 与人工等待混合、机器工作
  均返回后为 waiting_human、占 0，待决定文件仍不能被另一任务抢占。原四类决定→分析→
  摘要→确认可在同 Task 继续；本次不替失败/未知兄弟项续作。已有正常单文件成功、零效果
  失败、四类继续与零变更分析不退化。
- [x] **AC-C4 — 取消与活动保护。** CLI pass 在目标故障后收到取消，安全确认能完成并
  释放名额，保留 partial Result；已完成/失败兄弟结果不被改成 cancelled。真正调用仍
  在进行或项目仍 processing 时占 1，取消请求本身不能提前归还；返回并完成允许的结果/
  取消结算后占 0。原 claim/fence/控制版本和没有结果的未知边界仍不能被此调整绕过。
- [x] **AC-C5 — 原 Task/Slice 行为保留。** 原 AC-T1–7 / Slice AC-20–25 保持：最新同版本
  failed/partial 自动排除、后来手动成功解除旧排除、Files 简短提醒与正常确认、原历史/
  pin/兄弟项不改写、活动来源互斥、四类同 Task 继续、CLI retry-failed 退役和普通 CLI/
  remote 的原有来源/授权规则。不得靠新恢复页、自动重放或放宽内核完成本修正。
- [x] **AC-C6 — 独立复核。** B 在完整原 Task Base..新候选上给出 PASS/FIX REQUIRED，
  完成适用 T4 验收，重评全部 Slice RO-1–6/AC-1–25；满足后更新 Closure Packet 交 A，
  不由 B 关闭 Slice，不将前序已通过范围作为新的任意扩展任务。

## Required Tests

遵守 [workflow §6](docs/development-workflow.md#6-test-levels)；每轮测试时间小于本轮总
用时 50%，优先真实关键复现，不用空等/删断言/重试/放宽超时凑比例。只用隔离临时媒体、
SQLite 和 fake/local Provider；不读取生产配置或真实远端。

### Developer — affected tests

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

### B — independent acceptance / full regression

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

## B Review Result — PASS

```text
Decision: PASS
Task Base: 75ddff55f8d5b2b1206c81804bfb5cbe9ed279a1
Reviewed Head: 5c808d4a67bedfbafb71d88a1ffa8d3480ef5316
Latest executable checkpoint: 32db236e5534b15bd4b92aa12c5b9ab18511e96a
Previous CLI correction: 2e1e293ed7901b897ac316209c26c4ae4cd29556
Branch / starting state: main; no tracked edits; pre-existing untracked files preserved
Blocking findings: NONE
Next: SLICE READY FOR A REVIEW — no further implementation Task
```

独立核对整个原 Task Base..Head 的 36 文件清单与既有完整范围审查结果，逐行检查本轮
解析接缝和测试增量，重新验证前序 CLI 收尾修复；没有只凭 Developer 报告接受。
`32db236e..5c808d4a` 只改交接文档。本轮 B 只维护 TASK.md，未改产品/测试、A-owned
合同/指针，未派生代理、push、部署或访问用户数据库/媒体/私密配置。

### 用户旅程与阻塞处置

- **批量根目录正常整理已完成。** 原独立失败探针现在查询 One/Two、真实 COPY 两项；
  与目录/子目录入口一致。新增实际 batch 成功/ENOSPC 混合旅程到达执行和结算，
  保留独立 success/partial Result 与未知效果，partial_success、exit 1/摘要、容量 0，
  reopen 不重放。真实冒号文件名未被拆分，目录规则仍命中。
- **跨 Storage 实际结果正确。** B 通过现有 managed import/validate/activate 发布双
  ResourceLibrary 配置，再执行真实 batch；新 Task 绑定该 Active pin，两种 Storage ID/
  相对路径/展示身份/Result 均保持正确，生成两个实际目标媒体，结束容量 0。没有只在
  fake Provider 添加带 Storage 前缀的候选来让测试通过。
- **原 CLI 名额和取消修复保留。** 磁盘满产生 partial/unknown → 正常 Task ID/失败摘要、
  exit 1、settled/容量 0；另一文件随后成功，reopen 仍占 0。真实写入暂停期间经现有
  tasks cancel 请求取消，仍占 1；调用返回 ENOSPC 后 cancelled、占 0，旧未知 Result
  保留。机器名额释放不等于清空文件所有权或重放原尝试。
- **原历史规则与人工继续保留。** 当前全量和原生覆盖 due/Run once 最新同版本失败
  排除、后来手动成功解除旧排除、自由兄弟项、Files 提醒→原确认→实际 MOVE、四类在同
  Task 分析/摘要/确认、当前 pin、原 Automation 结果/时间及未知效果不改写。
- **共享解析路径的影响已复核。** Parser/规则消费真实 Storage-relative 路径，展示
  身份仍保留在 Task/Result/日志；未修改 Parser 规则、Provider 查询容错或 Storage 协议。
  当前 recognition/path/directory、NFO、标签/剧集、普通 CLI/manual/remote 及四类回归
  通过，不把 `StorageID:path` 展示文本当媒体文件名，也未做全局冒号裁剪。

### 当前验收与证据

本地 ignored 证据根：`.git/validation-evidence/5c808d4a/b-review/`。
命令脚本、原始日志、截图、分组清单/计数、产物源码核对及 SHA 保留于此，不宣称远程可访问。

| 验证 | 实际结果 / 原始证据 |
|---|---|
| 全量 Python | 145 个模块四组无重漏执行，635+634+634+634 = **2537 tests**；7 项可选远端/耐久环境 skip。唯一失败是 B-owned Task 的测试分工标题与既有文档检查要求不同，已就地修正文档标题，并重跑该模块 **8 tests OK**；产品/测试执行输入未改，无剩余失败。`python-full-{0..3}.log`、`python-full-plan.json`、`release-doc-after-fix.log`。 |
| 独立真实入口 | `batch_root_acceptance.py` 的正确期望通过；`multi-storage.log`、`cli-capacity.log`、`active-cancel.log` 实际结果如上。新增真实 batch 混合/冒号旅程包含在全量与 clean installed 验证中。 |
| 当前 native | 源历史 1、Task Center 八视图/摘要 2、Automation lifecycle/Run once 17、桌面及 390px 窄屏源历史各 1，合计 **22 passed**。使用正式 build + real API/SQLite/Worker/临时 Storage。`native-e2e.log`、`task-center-native.log`、`automation-synchronized.log`、`desktop.log`、`narrow.log`。 |
| 视觉 | 实看 `desktop-summary.png`、`narrow-summary.png`、`narrow-confirm.png`：提醒、逐项旧效果和原确认可达，长路径换行，无横向溢出或新增知晓框/核查页。 |
| 质量/公开示例 | Ruff check/format、compileall、pip check、两份公开示例 validate、governance 与完整 Task diff whitespace 通过；生产源码/pyproject 无 FFmpeg/FFprobe。`quality.log/json`。 |
| Web 全量复用 | 复用 B 对 `3fb10500` 的 **88 files / 1267 unit passed、253 fake E2E passed** 及 typecheck/lint/format/build。`web-reuse-input-diff.txt` 为空，证明当前 Web 源码/测试/锁文件/配置、browser harness 和 pyproject 未变；依赖未重装，原 build 未替换。Python 输入改变的 native/full/installed/container 均重跑，未用旧 PASS 代替。 |
| clean wheel / installed | 从 `git archive 5c808d4a` 干净上下文重建，169 个 Python 模块与源码逐字节相同、无多余/缺失。wheel smoke、源码外安装后 **9 tests OK**，包括真实 CLI ENOSPC→下一准入→reopen、root batch 混合写失败、冒号路径及四类/原 Task 交接；退役 retry-failed exit 2、help 无入口、普通 organize 保留。`wheel-*.log`、`installed.log`、`artifact-source-proof.json`。 |
| Docker fresh/security | **PASS**；真实四服务健康、Files 手动整理、权限/拒绝零效果、non-root/秘密扫描；`docker-security.log`。 |
| Docker 同版本 restart/fault | **PASS**；真实调度/COPY、各服务重启、幂等、原记录/pin/旧 owner fencing、未知效果非重放；`docker-restart.log`。最终 image `sha256:16d9bfff29901279c0b4988dc6069dbbc3759663b2940f355200fb3ae0ca0b42`。 |
| image CLI 入口 | image 已安装 CLI 的 retry-failed exit 2，help 无入口，正常 organize help 通过；`image-retired-cli.log`。容器正式启动预检另由安全门禁覆盖。 |

clean wheel SHA-256：`7f75e4ed89ee0fd492228a302cb0d3f12644df04344473049e307fa54afee05d`。
7 项 skip 为未配置专用 SMB/S3/OpenList 和耐久 profile；未改这些适配器、未使用用户端点，
不把未执行的真实远端验证写成通过。旧任务/跨版本升级、V1 产品功能按用户边界排除。

**原始失败与 B 的处置均保留：**

- 全量里的 Task 标题检查属于 B 文档维护，已修为既有 Developer/B 分工标题；没有改测试
  或要求 Developer 返工。分组运行前的本地 runner 导入路径问题由 B 修正，最终计数与
  unittest discover 的 2537 一致，没有把加载失败算作业务失败或跳过。
- 原 Automation native 为 16 passed/1 failed：旧 Published 提示不能证明第二次 Save
  的最新定义读回完成。trace 证明 PUT 已发布 itemLimit 150，但 Run once 在其 GET 返回前
  2ms 发出旧 fingerprint；后端以 definition_changed/409、零效果拒绝。验收副本仅增加
  等待真实 GET 的新 itemLimit 和 Active revision 呈现，保留全部效果/数量/权限断言，
  17 项通过；无页面刷新、额外确认、sleep、retry 或放宽超时。原日志/trace 及副本保留。
  Save 后极快点击可遇到有界陈旧定义拒绝作为已有 P2 记录，不新增开发 Task 或弱化后端
  准入安全。

## Entire Slice reassessment / Closure Packet for A

```text
Slice: 47 — Unified Task scheduling and organizing execution
Slice Base: 5144ab1fc2344b06194969cc2c496835729664c0
Implementation Head: 5c808d4a67bedfbafb71d88a1ffa8d3480ef5316
Required Outcomes and Surfaces: COMPLETE under explicit user amendments
Tasks completed: 47.1–47.4 accepted baseline; 47.5 B review PASS
Blocking findings: NONE
Decision: SLICE READY FOR A REVIEW — no next implementation Task
```

| 全部结果/验收 | 重评 |
|---|---|
| RO-1 / AC-1–3 | 完成：同一 Task、全入口共享容量、机器工作/人工等待区分、原子准入/claim/control/fence；CLI 真实故障及活动取消补足此前漏项。 |
| RO-2 / AC-4–6 | 完成：Files/due/Run once/普通 CLI/remote 共用管线，root batch/目录/跨 Storage 实际效果闭环；保留入口意图、限制、稳定性/完整遍历/附件与明确授权。 |
| RO-3 / AC-7–8 | 完成：四类在同 Task 决定/分析/摘要/确认、合法旧 pin 和独立结果，成功/未知旧尝试不重放，当前 full/native/installed/restart 覆盖。 |
| RO-4 / AC-9–12 | 完成适用范围：Job 退出/fresh/配置和新数据同版本 reopen/restart 的接受事实保留，当前源码/clean wheel/image 复核；旧任务与跨版本迁移按用户排除，不声称已验证。 |
| RO-5 / AC-13–19 | 完成：八视图/Attention、Files、Automation 原记录/设置、Dashboard/通知/日志/导出/API/CLI/健康与 Pause 退出保留；AC-18 的 A 独立整个 Slice 终审尚待进行，B 不代签关闭。 |
| RO-6 / AC-20–25 | 完成：最新同版本历史、自动原子排除/自由兄弟/无工作真相、手动可见提醒和新效果、历史/pin/未知证据不改写、来源互斥/接管及 CLI 退役，当前适用 T4/native/产物证明完整。 |

**Documentation Reconciliation Needed：** A 复核新完整 Slice Base..Head 后更新 A-owned
Slice 的候选/上次 FIX REQUIRED 状态与 Next Action、Roadmap/Progress 指针；A PASS 后再
统一 CURRENT/TARGET、requirements/journey/architecture 和根 Task 的正式关闭衔接。
B 保留最后实施交接元数据和上次 A 审核历史，不用本次 B PASS 冒充 A 已接受/关闭。

**Known non-blocking / deferred：** 上述有界 Save/readback 点击时序 P2，以及未运行的
可选真实远端/耐久 profile。前序默认 E2E fake/native 路由和旧安装恢复脚本的证据维护
问题已由 B 使用对应上下文覆盖，不新增过程工具或后续 Task。没有新功能延期或新恢复承诺。

**Stop rule：** 六项结果已满足，停止规划，交 A 独立终审；本 Task 无进一步实施授权。

本轮并行日志区间合并 265.2s，另计人工图评/短检查预留 30s，测试上界
295.2s；保守总用时 789.1s，占比上界 37.4%，小于 50%。
无空等补时；精确区间见本轮证据 `timing.json`。
