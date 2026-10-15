# Task 45.1 — 九视图任务查询与当前问题定位

遵循 [Development Workflow](docs/development-workflow.md)，从属于已提交的
[Slice45 Contract](SLICE.md)。规划/审查读取 [B 经验](docs/agent-experience/task-planner-reviewer.md)，
实现读取 [Developer 经验](docs/agent-experience/developer-implementation-role.md)。

```text
Task ID: 45.1
Parent Slice: 45
Status: READY FOR B REVIEW
Task Base: 99cbf2fd9233cd01d9b6d9c8d29748a52bd7a914
Difficulty: High
Test Level: T4
Planner / Reviewer: B
Next Action: B REVIEWS TASK 45.1
```

## Goal

操作者通过九个原生任务视图，在完整授权总体中找到运行或当前问题，准确知道涉及哪些文件，
进入该任务/问题类型的文件清单查看证据和下一步，并返回原筛选/分页上下文。
完成 **RO-1** 及 **RO-3 的跨任务类型列表和问题文件定位部分**，保留 RO-4 既有详情、
记录、导出和控制能力，满足本改动涉及的 RO-6 共享权威与验证边界。

本次是完整的查询、诊断与定位旅程。RO-2 创建同页摘要、RO-3 新恢复处理/摘要确认、
RO-4 继续时同页重新授权及 RO-5 全入口 Scan 退役仍待后续 Task，不宣称这些结果完成。
适用要求：V2-OPS-001–005/009、V2-UX-001–003、V2-AUTH-001–003、V2-SAFE-001、
UX-001–005/007/010、REQ-TASK-*、REQ-RECOVERY-002/006、REQ-RESULT-*、REQ-SAFE-*。

## Why This Task Exists

规划已完成必读清单、[最终页面规范](docs/task-center-page-spec.md)及九张参考图检查。
已提交 `HEAD:SLICE.md` 与 Roadmap 对应行均为 ACTIVE，工作树 Contract 与 HEAD 一致；
`python3 scripts/check_governance.py` 通过。Slice Base 保持
`a72252091d5d46edf3e2114b994036ae21b08e2e`；Task Base 为上方实际 HEAD。

实际代码/测试表明：

- `sqlite_runtime.py:operations_runs_window` 已在同一读事务提供显式关联去重、总体查询/计数与
  双向分页；`service_api.py` 已绑定 cursor 的筛选和 principal。应扩展这一读模型。
- `operations_run.py` 的 attention 集合和 `OperationsRunOverview.__post_init__`、SQLite
  `_run_query_clauses`、API `attention_count`、前端 `run.ts` 的严格校验，都仍将 attention
  等同于状态集合，包含普通 Pending。该旧语义必须跨层一起修正。
- `OperationsLanding.tsx` 仍是单清单与选中详情，缺九个同级视图、来源筛选和五类跨任务聚合。
  只加标签或前端筛选无法满足总体查询要求。
- `ProcessingCheckpointService`、`TaskItemRecoveryService` 和 review/conflict、recovery request /
  continuation / manual-recovery 关联可复用。`list_task_items_needing_attention` 只是已选 Task
  的有界窗口，不能作为全总体恢复计数权威。
- `RunDetailTabs`、结果包、生命周期控制、`operations-return` 和
  `operations_inventory_harness.py` / real-Python Playwright 可复用；无需建立第二套引擎。

规划反馈：`.venv/bin/python -m unittest tests.test_operations_run_inventory tests.test_processing_checkpoint`
通过，51 tests / 2.779s。环境 Python 3.13.14、Node v22.23.3、npm 10.9.9；系统没有 `python`
命令，下面使用 `.venv/bin/python`。这是 Base 规划反馈，不是新行为或 T4 验收证据。

这是 Repository/Application/API→Web→原生浏览器的行为单元，不按标签、字段或层拆 Task。
预计后续按创建确认、恢复确认/控制、Scan 完整退役等主要旅程推进，总体约四项主要 Task；
这不是预先授权的 Task 清单，每次 PASS 后仍重新检查全部 RO，再决定下一步。

## User Journey

| 环节 | 本 Task 必需行为 |
|---|---|
| 用户目标 | 找到真正需要关注的运行及本类型问题文件，理解当前状态与安全下一步 |
| 入口 | 共享 Shell 单个“任务中心”入口；九视图深链；原 Task/Job 链接 |
| 可见状态 | 全宽清单默认无选中详情；历史业务名称/范围、阶段/结果、任务数与文件数、当前问题、未知数据 |
| 可用动作 | 切换视图、筛选/分页/刷新，查看详情/记录/导出，进入 Task/type 文件清单，查看逐项证据及既有合法动作/指引 |
| 成功结果 | 找到完整授权范围内的任务，定位准确问题文件并理解下一步；返回保持原列表上下文 |
| 失败结果 | 无权限、读取不可用、过期 cursor、问题已变化或旧证据不足均明确显示，不伪造空清单、零或成功 |
| 恢复路径 | 刷新问题/合法动作、重置过期分页、重连，或按指引修复依赖/核查效果；读取和返回不提交工作 |

## Implementation Scope

### 1. 共享权威查询与当前问题语义

- 九个同级独立可深链列表：`全部任务 / 进行中 / 需要处理 / 已结束 / 识别恢复 /
  元数据恢复 / 分类恢复 / 冲突处理 / 失败恢复`。可共享 route/view 参数与组件，但各 URL
  独立表达视图；不能用详情抽屉的嵌套 tabs 代替九页。
- 后端提供 view/problem/source 查询与计数。来源按持久 trigger/origin 等真实证据提供选项，
  缺失显示未知；保留类型/状态或本视图问题子类、时间、文字过滤，不以自由文字冒充来源筛选。
  名称/范围来自准入或历史 pin，不从今天的 Active 补写。
- 全部任务保留已受理/历史各工作类型：普通维护/传输、diagnostic DryRun、旧 Scan、discovery、
  独立 Task、排队与 pre-Task 失败不丢失、不改写为整理。Job/Task 只按明确持久关系去重，
  恢复尝试保留独立关联历史，不按名称、路径或时间猜关联。
- 进行中收录真实未终结工作，包括排队、执行和可继续暂停；已结束保留完成/部分成功/失败/
  取消。需要处理依据当前人工决定/修复/核查，可与其他视图重叠；普通排队和内部稳定性等待
  不因状态名自动报警。其他人工问题在需要处理中解释，不伪造为五类中的技术失败。
- 五类恢复在完整授权总体按真实 Task/run 聚合，一行一个任务，仅计算本类型当前受影响文件。
  Metadata 候选/correction 同属元数据视图。附件冲突计入所属主文件并单独解释附件问题，
  多条附件步骤不重复算主文件。任务数、distinct 文件数和步骤数分别标注。
- 分类复用 checkpoint/review/结果/明确恢复关联的生产语义，不能只看 Task.status、error 文本、
  历史 failed Result 或有限 attention 窗口。成功/忽略/跳过不因旧失败占待办，已解决 review
  不继续作为旧 blocker；保存决定/分析受理/执行受理不等于整理恢复成功，仍需的后续人工动作
  不能消失。关联尝试的新 blocker/再次失败/实际完成按耐久事实更新类型和计数，不改写原结果
  或成功兄弟项；分析 DryRun 成功不等同于媒体执行成功。
- Python 统一决定当前问题、bounded 解释和允许动作，repository 提供全总体有界查询；
  列表、计数和类型文件清单共用同一语义。既有生命周期/恢复服务仍为动作准入权威。
  允许补必要的持久关联/索引，不建立第二套 blocker 生命周期，不在读取时回写旧历史。
- 页、统计、问题分类使用一致读口径。cursor 只限窗口，不限总体，绑定 principal、view、
  source、问题/状态/类型、文字、时间等全部实际条件。非法输入明确拒绝；禁止 API 逐页扫完
  历史、逐行重建完整 runtime 或前端拉若干页再过滤/计数。

### 2. 原生九页与任务内问题文件定位

- 按九张参考交付标题、真实统计、提示、同一横向导航行、筛选、完整列表和分页；共用 Shell，
  只改任务中心必要导航/breadcrumb。样本数量/名称不固定，统计不可得时不能显示零。
- 切换视图默认无详情；URL 保存已提交筛选与 cursor。可点击卡片应用自身标注的查询条件。
  清楚说明重叠视角和统计范围，不要求各恢复类计数相加等于总任务数。
- 恢复行直接进入 Task + type 的原生有界文件清单，由服务器按当前问题筛选/分页，展示原因、
  阶段、来源/目标、完成步骤、效果确定性、允许动作/下一步、原任务/续作关联。可复用已有
  证据和合法任务内恢复组件，不能只打开未筛选通用详情让用户翻找，或只定位当前页某一项。
- 新入口至少完整实现“查看本类问题→逐项证据/安全指引→返回”；不得有死按钮、占位处理页
  或假恢复成功。专用决策组合及同页摘要/确认由后续恢复 Task 完成。既有原生恢复入口保持
  可达，暂未重构的旧流程不宣称满足 V2-OPS-012。
- 保留原生详情、records、有界脱敏 JSON 导出、Task/Job 深链和后端允许的 pause/cancel/continue。
  区分控制请求与生效；未知效果仍仅核查，不新增直接重试或执行权限。
- 活跃查询有界可见轮询，隐藏时停止；失败提供刷新。当前问题更新不能仅依赖当前分页有
  active 行，终态原任务的关联恢复执行也须能刷新其列表/计数。写命令不自动重试，读/导航/
  刷新/导出不调用 Provider、不创建媒体工作、不授予执行权限。
- 窄屏九标签可发现并横向滚动；键盘、可见焦点、深链、Back/Forward、刷新、401 重连保持
  安全返回上下文。403、malformed/unavailable、空态、过滤空态和问题已解除均有可用下一步。

### 3. 持久兼容与改动所有权

- 范围限 run/problem 读模型、必要 domain ports/repository/API/typed client、Operations 页面、
  必要共享路由/返回上下文、tests/harness。schema 如有必要，只作增量变更，保留旧 pins、
  Result、review、恢复关联及历史语义，验证迁移/重开/失败原子性。
- 不改 `SLICE.md`、Roadmap、Progress、稳定需求及已接受 CURRENT 声明；完成报告记录实际
  状态，交 A 收尾 reconciliation。必要架构 Contract 或验收含义变化先交 B/A 判定。
- 保留预存脏文件：`docs/pics/操作与任务.png` 删除，未跟踪的 `自动化页.png`、
  `自动化页-全局设置.png`，根目录/docs/docs-pics 的 `.DS_Store` 及
  `output/imagegen/slice45-task-center-v1.zip`。`config/alist.json` 保持 ignored/untracked/unstaged，
  不读取或输出真实秘密，不夹带到 checkpoint。

## Acceptance Criteria

- [ ] **AC-1：** 九个独立深链列表及同一横向导航真实工作，默认无详情；参考结构/层级完整；
  每页支持来源及适用问题/状态/类型、文字/时间筛选、有界双向分页。
- [ ] **AC-2：** 大于一页的混合授权总体中任务全可达，页/卡片/任务数/distinct 文件数一致；
  并发 Job→Task 关联不重复，跨 view/filter/principal cursor 被拒绝。有限 Task/item 窗口
  不决定总体计数。
- [ ] **AC-3：** 同任务多类独立收录，普通排队不算待办，准备 findings 不冒充正式恢复。
  pending→resolve/ignore、恢复受理/运行/新阻塞/再次失败/实际完成均正确更新；已解决旧阻塞
  不残留，未解决问题不因点击/受理消失，原结果和成功兄弟项保留，未知效果仅核查。
- [ ] **AC-4：** 五类行内入口到准确 Task/type 的服务器筛选文件清单，逐项/附件证据、原因及
  合法下一步真实可见，返回保留 view/filter/cursor；问题解除、权限不足和旧证据缺失可恢复，
  无通用详情翻找、死按钮或假处理成功。
- [ ] **AC-5：** 历史身份/pin、未知数据、各诊断/维护/传输/旧 Scan/pre-Task 失败和恢复链可读；
  主文件/附件、进度/成功率区分。原 Task/Job 深链、详情/records/导出、合法控制及 Files/
  Organize 返回不回归。
- [ ] **AC-6：** 新读路径/轮询/导航/导出无工作准入、Provider 调用、Storage mutation 或执行
  授权；RBAC、memory-only token、脱敏、immutable pin、OrganizerExecutor-only mutation 与
  RecognitionType C→A 策略身份不变量不变。
- [ ] **AC-7：** production build 九页视觉、窄屏/键盘/深链/重连及 real-Python/SQLite 混合问题
  更新通过；T4 gates 有精确候选与耐久原始证据，checkpoint 仅包含本 Task。

## Required Tests

按 workflow 分阶段执行与复用。T4 源于跨层当前问题/权限投影、一致性和可能的关联/schema
变更；不因只读表面降低检查。旧 attention 状态断言应替换为当前问题的实质覆盖，禁止删除
测试、弱化安全断言或用 retries/skip 制造通过。

### Development and correction feedback

根目录使用 `.venv/bin/python`，前端在 `web/` 运行 `npm`。先新增/修改测试，再受影响回归：

1. `.venv/bin/python -m unittest tests.test_operations_run_inventory tests.test_processing_checkpoint`：
   总体/分页/身份/脱敏/checkpoint/效果语义。新增测试可扩展现有或建立连贯模块，报告给出实际
   可执行命令与 AC 映射。
2. `.venv/bin/python -m unittest tests.test_operations_workspace tests.test_operations_run_detail tests.test_scope_continuation tests.test_recovery_continuation tests.test_recovery_batch`：
   权限/控制、当前问题与恢复关联、独立批次/历史、受理与解决区别。
3. `npm run test -- run src/features/operations src/entities/operations src/shared/navigation src/shared/api/operations-api.test.ts`：
   typed 合约/失败、九视图/返回、计数、query key 与轮询；加跑实际修改的 route/Shell 相关测试。
4. 扩展现有 `operations_inventory_harness.py` 与 real-Python spec：混合任务包含成功、至少两类
   待决定、主/附件冲突、零效果技术失败和未知效果，另有普通排队、其他任务及超过一页数据。
   用真实 repository/服务建 fixture，真实 review/recovery API/Worker 转换状态，验证类型
   计数/文件定位/返回，不硬编码产品 API 响应。

覆盖还包括超过一个内部证据窗口的问题项、Metadata 两子类、resolved 后仍需下一步、问题转类、
恢复已受理但未完成、再次失败、缺 pin、准备与正式阻塞分离、跨连接一致读、非法 filter/cursor、
401/403、secret-shaped 搜索、Active 更名及 DB 重开。

### Final checkpoint gates

最终 executable candidate 上完成；full suite 包含 focused cases 时不机械重复：

- 根目录：`.venv/bin/python scripts/check_governance.py`、`.venv/bin/ruff format --check .`、
  `.venv/bin/ruff check .`、`.venv/bin/python -m unittest discover -s tests`、
  `.venv/bin/python -m compileall -q mediaflow tests scripts`、`.venv/bin/python -m pip check`。
- 示例/依赖安全：`.venv/bin/mediaflow --config config/strategy.example.json config validate`、
  `.venv/bin/mediaflow --config config/mediaflow.phase13.2.example.json config validate`；
  `rg -n -i 'ffprobe|ffmpeg' mediaflow pyproject.toml` 无匹配（exit 1）。核查新增依赖，以及
  read-only/no-Provider 计数、C→A 身份回归在全量中的实际覆盖。
- `web/`：`npm run typecheck`、`npm run lint`、`npm run format:check`、`npm run test -- run`、
  `npm run build`、`npm run test:e2e`。共享路由/返回及严格模型变化需要全量 Web 和既有
  fake-API browser regressions，不能只跑新增页面。
- `web/`：`npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts`，
  以及 `npm run test:e2e -- --config=playwright.python.unicode-principal.config.ts tests/e2e/operations-principal-identity.python.spec.ts`，覆盖生产静态
  产物、真实 API/SQLite/Worker、受影响既有创建/控制/恢复与 principal-bound 返回/提示。
- 九页 `1536×1024` 实际截图，加窄屏九标签/Task-type 文件页/失败与重连截图；人工检查参考
  层级、完整列表、无默认详情、焦点与遮挡，不以脚本退出码代替视觉验收。
- 有 schema/关联持久化变更时，增加并在全量执行真实旧 schema45 和相关更早 fixture 的
  migration/reopen/failure-atomicity 测试，证明旧 pin/结果/Scan/DryRun/恢复链不改写。
  无 schema 变化则报告实际 diff，不虚构 migration PASS。
- 本 Task 不改安装/容器/Worker 装配，不重复 Docker 全矩阵；若实际触及该边界，先交 B 调整
  Required Tests，增加 installed wheel/Docker 相关生产产物证明，不得自行免除 Slice-final gates。
- B 于本轮 review 补正原计划漏列的仓库既有 release-security 门禁：
  `.venv/bin/python scripts/docker_release_security_smoke_test.py --image mediaflow:task45.1-security`。
  `tests/test_release_security.py` 要求每个 active Task 记录该命令；这不是新增产品范围或要求
  Docker 全矩阵。实际执行结果、Docker 不可用时脚本的 SKIP 和适用缺口均须如实留证；
  不修改/删除既有 policy test。Task ID/Base/Goal/Scope/AC/Difficulty/T4 均不变。
- `git diff --check`，检查完整 diff、manifest、private/frozen scopes 与全部预存脏文件保留。

### B independent verification

B 审查 Task Base..实际 Head 与原始证据，独立在 real-Python production build 复现：
普通排队不入需要处理；跨页发现混合任务；Metadata/冲突/失败页各自文件数准确；进入正确
Task/type 清单；真实决定/恢复转换后旧 blocker 解除、新问题转类、受理不算完成；未知效果
仅核查、成功兄弟项不变；刷新/重连/返回保持 view/filter/cursor，读取不产生工作。
B 实看九页与窄屏截图；匹配的 Developer 门禁证据可复用，不机械重复，缺失/矛盾则重跑相关门禁。

### Evidence and rerun rules

在 `.git/validation-evidence/<full-source-sha>/<run-id>/` 或 CI artifacts 保存索引与原始
logs/traces/screenshots，记录完整 SHA/dirty manifest、命令/cwd、runtime/lockfile 身份、
安全 fixture、Worker 设置、build digest、exit/counts/duration/首次失败与重复、AC 映射和缺口。
`/tmp` 不作唯一交接位置。报告-only successor 仅在明确 diff 证明 executable inputs 不变后
复用；source/tests/harness/config/artifact 改变后，修正 T4 候选重做完整指定 checkpoint gates。
规划反馈不复用为实现验收，外部门禁不可用须明确披露，不隐藏 skip 或写已通过。

## Non-goals

- 新建/恢复的同页摘要及新执行选择/确认协议；任意历史 Reprocess、跨任务批量 mutation、
  批量覆盖、未知效果重放或通用回滚；不新增 execute 权限。
- 本 Task 不实施独立 Scan 的 API/CLI/Worker 完整退役，也不整体移除通用 DryRun/Rules tests。
  新九页不新增 Scan/Preview 产品入口；旧未重构路径是明确剩余工作，不是 Slice45 交付事实。
- 冻结 Slice43 的代码、Automation 模式退役、Run once、统计和 engine settings；不导入其分支。
- 改 Slice/Roadmap/稳定需求/CURRENT 声明，新 Provider/身份/queue/恢复引擎，其他页面重构，
  与 AC 无关的文案、可选证明、测试碎片或清理。

## Developer Completion Report

```text
Status: READY FOR B REVIEW
Implementation checkpoint SHA: a032a245346c34605b8d90c79c51cdba44f73c13
Task Base: 99cbf2fd9233cd01d9b6d9c8d29748a52bd7a914
```

### Changed Files

Backend: mediaflow/domain/operations_run.py, mediaflow/infrastructure/sqlite_runtime.py,
mediaflow/interfaces/service_api.py.
Harness/tests: scripts/operations_inventory_harness.py, tests/test_operations_task_center.py,
tests/test_recovery_continuation.py.
Web contract/API/navigation: web/src/entities/operations/run.ts, run.test.ts,
web/src/shared/api/api-client.ts, operations-api.test.ts, web/src/shared/navigation/
destination-model.ts, destination-model.test.ts, operations-return.ts,
operations-return.test.ts.
Web surfaces/tests: web/src/features/operations/OperationsLanding.tsx, ProblemFilePanel.tsx,
OperationsInventory.test.tsx, web/playwright.config.ts,
web/tests/e2e/library-files.spec.ts, manual-operations.spec.ts, manual-organize.spec.ts,
operations-inventory.python.spec.ts, operations-task-center-visual.python.spec.ts,
operations.spec.ts.

### Implemented

- AC-1/AC-2, RO-1 query: the nine peer views support source, status, operation type, text, and
  time filters; links and return paths retain the active view and pagination context. The page,
  summary, and authorized source options use the same SQLite read snapshot and query scope.
  Job-to-Task associations are deduplicated, and per-type file counts use the actual associations
  and row-level problem items.
- AC-3, current problems: real pending decisions and recovery work remain visible, resolved blockers
  clear, and new blockers appear under their current type. Zero-effect and unknown-effect outcomes
  remain distinct. Work awaiting continuation is not presented as a technical failure.
- AC-4, file location: each problem view opens the correct Task/type file list with cursor
  pagination, evidence and recovery-chain detail, bounded explanations, and a safe next step.
  Returning preserves the view and filters. Unknown categories and internal failure enums are not
  rendered.
- AC-6, permissions and safety: source scopes use shared validation; reads and refreshes do not
  admit work, call a Provider, or mutate Storage. Existing details, records, redacted export,
  controls, and Files/Organize return paths remain available.
- No schema, migration, or dependency changes; existing Task, Job, item, and recovery records are
  reused.

### Tests and Results / evidence index

The durable index, raw logs, Task Base comparisons, build hashes, and screenshots are at
.git/validation-evidence/a032a245346c34605b8d90c79c51cdba44f73c13/task45.1-t4-fix2-20261015/INDEX.md.
The implementation checkpoint is a032a245346c34605b8d90c79c51cdba44f73c13. The isolated Python
suite used the active B Task text containing the added release-security command; after this report
was updated, the Task document policy test was rerun on the final report text.

- Python unittest discover -s tests: 2451 tests, failures=1, errors=2, skipped=7. The two errors
  are macOS temporary-path ENAMETOOLONG cases; the single failure compares /var/folders with the
  resolved /private/var/folders path. All three exact cases were independently reproduced at the
  Task Base. The isolated Scan CLI test passed. The first main-workspace run also hit a runtime
  database schema mismatch from the pre-existing .mediaflow/mediaflow.sqlite3; its mtime predates
  this run and that database was not read or changed.
- Root gates: governance, Ruff format/lint, compileall, pip check, both example config validations,
  diff check, and the no-FFmpeg/FFprobe scan passed.
- Web typecheck, lint, and format check passed. Production build passed; aggregate build-manifest
  SHA256 is cbab9c8f8523402f453213c6a933a9a08d1075210ca4a51d6c71d5202b865c8d.
- Full Web unit suite: 1108 passed and 2 failed. Both failures are in unchanged
  StorageManagementPage.test.tsx and were independently reproduced at Task Base.
- Full fake E2E: 240 passed and 3 failed. The old Scan pagination, narrow MediaLibrary row-menu,
  and Rules Add-form failures were independently reproduced at Task Base. Three later cases in the
  serial Scan group did not run after its first failure; the three cases were rerun separately and
  passed. The final suite used one worker because the fake API has process-global mutable fixtures.
- Real-Python/SQLite E2E: operations inventory 24 passed, principal identity 1 passed, production
  visual 1 passed, and Task Center keyboard journey 1 passed. Coverage includes mixed problems,
  pagination across 21 problem files, linked counts, source filters, recovery restart, and failed
  reads. The Docker release-security smoke passed; image ID is
  sha256:177ee4caa19a161e87b2fc4a7dbe51a7091d91213b82938d73e573eab84169a9.
- Production screenshots: nine views, problem files, narrow screen, reconnect, and read failure,
  13 images total. Wide images are 1536x1024; narrow is 380x720. I inspected every image. Hashes
  are in the evidence directory.

### Decisions

- Keep the stable API fields and return the list and summary from one query window so they share
  one snapshot and filter scope.
- Derive current problem and recovery evidence from existing durable records; no schema was added.
- Run the complete fake browser suite with one worker because its process-global fixtures are
  mutable; the interrupted serial cases were run separately.

### Remaining In-Slice Work

RO-2 same-page creation/confirmation, RO-3 new recovery handling and summary confirmation, RO-4
same-page reauthorization on continuation, RO-5 retirement of Scan from all entry points, and
Slice-level final verification remain. This Task does not claim all Slice Required Outcomes.

### Risks / Deviations

- The two Python path-length errors and one path-normalization failure, two Web unit failures, and
  three fake E2E failures reproduced at Task Base; logs are in the evidence index. The main-workspace
  Scan CLI failure did not reproduce in isolation. The existing runtime database timestamp predates
  this run, and the database was left untouched.
- Vite reports a 1.23 MB main JavaScript chunk above its 500 kB warning threshold; the Task Base
  build reports the same bundle size.
- Only the Task-required release-security smoke ran, not the Docker matrix. No schema changed, so
  no migration run or migration PASS is claimed.

## B Review Result

```text
Reviewed: 99cbf2fd9233cd01d9b6d9c8d29748a52bd7a914..9aee56976ab6dbdd7cba219c790ef099815c4201
Report Head: 0b4d8be4ee7c980cc39a51c5779bee8cb1f3154f (TASK.md only successor)
Decision: FIX REQUIRED
Slice Required Outcomes all satisfied: NO
Next: SAME TASK FIX LOOP
```

### 本轮 Task 阻塞项（P1）

1. **来源筛选未完成（AC-1/2）。** 新九页没有来源筛选控件，也没有把 source 放入查询/URL
   返回链。API 虽解析 source，却未传给 `operations_runs_window`；实际有 alpha/beta 两个
   scope 时，`source=alpha` 仍返回 total=2。summary 发出的合法 `Movies/alpha` source 选项
   又被 command-token 正则拒绝为 400。完成同一来源语义的 Web/API/分页/返回及校验，不能
   仅把来源选项列在未消费的 summary 中。
2. **类型文件计数错误（AC-2/3/4）。** `_run_summary_files_locked` 使用 `task_id IN
   (SELECT anchor_id ...)`，Job 关联 Task 后 anchor 是 Job ID；真实一项 linked run 有
   2 个识别文件，summary 却为 0。`RunTable` 每行又直接渲染全总体
   `page.summary.problemFiles[view]`：两任务分别有 2/1 个问题文件，行内均显示 3；独立原生
   浏览器中两个各 1 文件的失败任务均显示 2。按真实关联计算逐任务/类型 distinct 文件数，
   再计算适用查询范围的总体；行内和文件清单必须一致，附件计数仍保持原 AC 语义。
3. **列表与新增统计不在一致读口径（AC-2）。** API 先完成 window 的读事务，再独立调用
   `operations_run_summary()`。B 在两者之间用第二 SQLite 连接准入一个任务，得到同一
   unfiltered 响应 `total=1` / `summary.total=2`。summary 也没有消费当前筛选。把本次
   响应的页面、类型/文件数及所声明统计范围绑定同一数据库快照和实际查询条件；若保留另有
   意义的全局统计，明确其范围，不能拿它代替筛选范围或行内计数。
4. **问题文件定位不能完成（AC-4/5）。** `ProblemFilePanel` 固定 `cursor:null`，无分页控件
   或 URL 状态；实际 21 项时 API 提供 next_cursor，Web 只能查看前 20。卡片也没有完成步骤、
   附件/恢复链证据或进入精确已有 evidence/recovery 的动作，只输出 raw `investigate` 等标识；
   原生浏览器此 panel 的按钮仅有“返回任务列表”。补全有界分页/深链/重连和准确逐项证据/
   安全下一步，链接既有原生能力；不要求提前实现后续 Task 的新摘要执行协议。未知效果仅核查。
5. **已解决决定被伪装成失败（AC-3）。** SQL 将任何 pending 的 `*_resolved` 都放进 failure；
   真实 `RecognitionReviewService.resolve` 后，没有技术失败的项直接进入失败恢复。
   新测试 `test_resolved_problem_leaves_the_list_and_a_new_blocker_transfers` 甚至固定该错误预期。
   保留待继续的人工作业，但按当前真实问题/允许动作分类，不把安全分析待继续伪造为失败。
   同时基于真实 continuation/manual recovery 关联验证受理、分析、再次失败、新阻塞与实际
   完成后列表变化；不能仅复制原 item status/stage 谓词并永久保留旧失败。
6. **T4 证据与完成声明不可验收（AC-7）。** 报告所指 `.git/validation-evidence/base-failure-check/`
   仅含三份 Markdown 结论，无当前候选完整运行索引/原始日志、SHA/dirty-input 对应、build
   digest、完整失败/重跑；Python 失败数在报告与该目录文字间亦不一致。报告所指
   `web/test-results/task-center-visual/` 当前不存在，现存 test-results 为后续 fake suite 产物。
   B 不据这些文字接受“全部 Base 可复现”或九图验收。修正候选按完整 T4 计划保存耐久证据，
   有实测 Base 原始证明才归类既有问题；隔离测试运行的私有/旧 schema DB 干扰，不删除用户数据。
   本轮实看 production-build 宽/窄截图也未接受参考结构：页面仍是旧“操作与任务”的密集
   表格，业务名称以操作名+UUID 为主，缺来源与本类型问题筛选等必需构成。按九图/AC-1
   完整实现结构、信息层级及自然业务说明，再保存九页/关键错误/重连截图供复审；不要求像素一致。

### 本轮独立验证与停止范围

- 治理检查通过；`9aee569..0b4d8be` 仅改 `TASK.md`，用于确认本轮实际 executable candidate。
  必读产品/流程/架构文档与上轮已读版本无变化，本轮重读 AGENTS、Slice、Task 和 B 经验并核对
  当前 Contract；未改 A-owned 文档、生产代码或用户脏文件。
- `.venv/bin/python -m unittest tests.test_operations_task_center tests.test_operations_run_inventory`：
  54 tests / 2.989s / OK；这些通过不能排除上面的独立反例。
- B probe 在临时 SQLite/真实 WSGI/review 服务及双连接 interleaving 中复现上述来源、关联
  计数、一致性、误分类及 21 项分页问题；原生 Chromium 使用新 production build、真实
  Python harness/SQLite，确认行内错误数字、缺来源控件、只有返回按钮、宽/窄实际布局。
  该浏览器旅程的产品 API 请求全部为 GET，未发现该旅程准入工作或媒体 mutation。
- 证据：`.git/validation-evidence/9aee56976ab6dbdd7cba219c790ef099815c4201/b-review-20261015/INDEX.md`，
  含可重跑 probe、结果、原始日志、浏览器 trace、实际截图与候选/产物身份。
- 因已证明 P1，按 workflow 提前拒绝；未重跑全量 Python/Web/fake/real-Python suites、Docker，
  未进行剩余九页完整视觉验收，也未认可 Developer 的全量证据复用。修正后仍须完整 checkpoint
  gates，不能用本轮 focused pass 替代。
- Slice 复核：RO-1 尚有以上缺口；RO-2、RO-3 完整恢复、RO-4 同页继续授权、RO-5 及 RO-6
  最终验证仍未满足。继续同 Task 修正，不创建下一 Task，不提交 Closure Packet。

本次仅为 B Task review，不是 A Final Review 或 Slice 关闭。
冻结 Task43.3/先前 B 决定仍保存在 `c539429c2c3aaeaab4842b87d3c858e77106fed1:TASK.md`，
冻结 Contract 为 `ed974e0df8b263f631bfe48b524da461013d8780:SLICE.md`，位于
`frozen/slice-43-2026-10-15`，本 Task 不恢复或关闭 Slice43。
