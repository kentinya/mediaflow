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
Implementation checkpoint SHA: 53299fd5b3105919c240b0067eac3ebfa889ddc6
Task Base: 99cbf2fd9233cd01d9b6d9c8d29748a52bd7a914
Correction of: 7b7f833cd7b0640e7218b13e3d5a4a245628c9f9 (B review 4 FIX REQUIRED)
```

### Changed Files

This correction adds to the previous Task range: `mediaflow/domain/operations_run.py`, `mediaflow/infrastructure/sqlite_runtime.py`, `mediaflow/interfaces/service_api.py`; `tests/test_operations_task_center.py`; `scripts/operations_inventory_harness.py`; `web/src/entities/operations/run.ts`, `web/src/features/operations/OperationsLanding.tsx`, `web/src/features/operations/OperationsInventory.test.tsx`; `web/src/shared/ui/styles.css`. No schema, migration, dependency or runtime-configuration change.

### Implemented

- AC-2/3/5 (B P1-1 — run-level current problem): the authoritative read model now covers the durable run-level repair/verification work that exists before any Task is created. A **failed** Job whose `failure_category` and `failure_next_action` are durably recorded, and which never produced a Task, contributes `derived_attention = 1` with `attention_reason = "run_repair"`; it has no TaskItem, so it is deliberately **not** placed in any of the five file lists and publishes no fabricated file count. A plain queue admission (no structured fields), a generic exception failure (`failure_category IS NULL`), an operator-requested cancellation (which also records bounded evidence) and a Job that later created a Task (owned by that Task's item evidence) are all excluded. The predicate reads only stable structured columns, never free-form error text, and the list, the summary cards and the native detail share the same one-snapshot judgement.
- AC-1/4/5 (B P1-2 — nine-view body): the task center now renders the reference structure: a full-width four-card statistics row, an alert strip, and one bounded panel containing the nine sibling tabs on a single horizontal row, the filter bar and the list with row hierarchy and spacing. The `需要处理` row for a run-level repair offers a real `查看原因与修复指引` action that opens the run's existing Job detail (where the structured repair guidance lives), while a safe-continuation row still opens its own evidence/next-step surface; a Task/type problem still opens its exact server-filtered file list. All query, permission, URL/return and unknown-state behaviour is unchanged.
- The run-level repair row and the new `attention_reason` / `attention_failure_category` / `attention_failure_next_action` fields are projected through the repository, the API document and the typed frontend model with fail-closed normalization (an unknown reason, a repair without its category/next action, or repair evidence on a non-repair row all reject the whole response).
- No new execution capability, Provider call or Storage mutation; reads remain bounded, authorized and GET-only.

### Tests and Results / Evidence Index

Durable index and raw logs: `.git/validation-evidence/53299fd5b3105919c240b0067eac3ebfa889ddc6/developer-t4-fix5/INDEX.md`; the nine production screenshots, narrow and problem-file captures, `metrics.json` and `capture.cjs` are beside it. All executable evidence is pinned to the candidate SHA above.

- Governance: PASS. Ruff format/lint, compileall, pip check, both example config validations and the no-FFmpeg/FFprobe scan: PASS.
- Full Python regression: **2461 tests, 1 failure, 7 skipped**. The one failure (`test_scan_cli_needs_no_path_or_metadata_token`) is the documented pre-existing environment failure: the working tree's ignored `.mediaflow/mediaflow.sqlite3` is schema 48 while this version expects 45. Independently reproduced at Task Base `99cbf2fd` in a detached worktree with that ignored file copied in (`FAILED`, same assertion); the same Base without the file passes. That file was neither read as a fixture nor modified. All focused/related Task tests pass (`tests.test_operations_task_center` now includes the run-level repair and cancellation regressions).
- Web typecheck, lint, format check and production build: PASS (Vite >500 kB chunk warning retained). Full Vitest: **1115 passed (75 files)**. Full fake Playwright E2E: **246 passed**.
- Real-Python/SQLite inventory: **25 passed**; Unicode-principal: **1 passed**; production Task Center visual capture: **1 passed**.
- Required Docker release-security smoke: **PASS** on the exact candidate image (`mediaflow:task45.1-security`, `sha256:82ed2d392807…`); `TMPDIR` set to a Colima-shared evidence path because Colima does not share the host default `/tmp`; no leftover containers.
- B's own probes rerun against this candidate: `pre-task-real-probe.py` now reports `attention total = 1` for all seven real pre-Task configuration failures (was 0); `pre-task-probe.py` reports the injected `configuration_snapshot_unavailable` run in `attention` with `problem_types = []` (was absent); a cancelled-Job probe reports `attention total = 0`.
- Focused regression: `tests.test_operations_task_center` adds `test_pre_task_repair_failure_is_attention_without_a_file_list`, `test_plain_queue_and_unstructured_failure_are_not_run_level_repair`, `test_cancelled_job_with_evidence_is_not_run_level_repair`, and `test_run_level_repair_evidence_never_leaks_into_a_linked_task`; `OperationsInventory.test.tsx` adds the run-level repair row/locate-action case.
- Visual inspection at `1536×1024`: four cards each 273×92 spanning the panel width; nine tabs on one row (single `top`); data rows 68px with 36px filter controls; the run-level repair row and its `查看原因与修复指引` action; narrow 380px keeps the tabs in one scrollable row. Problem-file and failure views inspected. Not pixel-identical and no fixture counts are asserted.
- `git diff --check`: PASS. No migration was run because the diff contains no schema change.

### Decisions

- A pre-Task failure is a current problem only when it carries durable structured repair evidence; otherwise it is history, not a manual to-do. This mirrors the existing `blocked` vs `failed` occurrence classification without duplicating it.
- Run-level repair work has no file members, so the row uses a general attention explanation and the existing Job detail rather than fabricating file counts or a five-type membership.
- The nine-view body is implemented with the task center's own scoped styles reusing the shared shell/components; global styles were not changed and all query/permission/return behaviour is untouched.

### Remaining In-Slice Work

RO-2 same-page creation/confirmation, RO-3 new recovery handling and summary confirmation, RO-4 same-page reauthorization on continuation, RO-5 retirement of Scan from all entry points, and Slice-level final verification remain outside this Task. This report does not claim all Slice Required Outcomes or Task PASS.

### Risks / Deviations

The production bundle retains Vite's >500 kB chunk warning. The main working tree's ignored schema-48 runtime DB causes one pre-existing full-suite failure (proven at Task Base). User-preserved dirty screenshots/`.DS_Store` files, the deleted pre-existing screenshot, `output/imagegen/slice45-task-center-v1.zip`, B's active Task review edits and ignored `config/alist.json` were not staged or removed; `config/alist.json` was not read. This is Developer handoff for B review only; no PASS, Slice review or closure is declared.

## B Review Result

```text
Reviewed: 99cbf2fd9233cd01d9b6d9c8d29748a52bd7a914..7b7f833cd7b0640e7218b13e3d5a4a245628c9f9
Report Head: b9f229b6f00f5b25a5bd2e4dc2856c70a571a493 (TASK.md only successor)
Decision: FIX REQUIRED
Slice Required Outcomes all satisfied: NO
Next: SAME TASK FIX LOOP
```

B review 4，完成于 2026-10-16。Task ID/Base/Goal/Scope/AC/Difficulty/T4 不变。
历史 B 决定保留在 Git 和原耐久证据；本轮不创建下一 Task。

### 上轮三个 P1 已修正

- **需要处理定位：** 独立 Chromium 点击混合任务的“识别问题”，实际挂载准确 Task/type 文件
  清单、发出 problem=recognition GET，显示 2 个文件；刷新并重新认证仍恢复同一 Task/type。
  代码及组件测试还覆盖单类型与无技术类型的安全后续动作分支。
- **保存决定的中间状态：** 独立完整元数据恢复 probe 在保存决定后、下一次准入前观察到
  failure=0、metadata=0，通用待继续 attention 保留；实际明确执行成功后 attention=0。
- **矛盾进度：** 原真实 WSGI probe 的实际 1 个 waiting item / 声明总量 0 现在返回
  processed_items=null，页面显示不可用；未再发布 0/0 的已处理比例。

### 当前 Task 阻塞项（P1）

1. **当前问题投影遗漏尚未生成 Task 的明确配置修复工作（RO-1；AC-2/3/5）。**
   `_run_query_document` 的 attention_sql 只探测 TaskItem，整个 Job 分支没有消费持久
   failure_category / failure_durable_state / failure_next_action 等 pre-Task 证据。
   独立执行已有真实 `DefinitionScopedExecutionTests` 的 claim-boundary failure 旅程：
   `snapshot_digest_mismatch`、`resource_library_missing` 等失败均由生产 Scheduler/handler/
   Worker 写入，task_id=null 且有明确修复动作，但 all/ended 各 total=1、attention total=0。
   另一个 AutomationWorker/SQLite/WSGI probe 同样复现固定配置不可用的修复项被遗漏。
   普通排队无 attention 的修正有效；不能因此把无 TaskItem 的真实修复工作也一概排除。

   修正方向：在同一权威读模型中覆盖当前仍需人工修复/核查的 run-level 证据，并与历史已结束
   问题区分；列表、统计和原生详情/下一步保持一致。无文件成员时不能编造文件数或硬塞进五类
   文件恢复；使用适用的通用 attention 解释和既有诊断入口。不要重新将所有 failed/Pending
   状态都视为待办，不新增自动重试、配置改绑或执行权限。以真实 pre-Task 失败、普通排队和
   仅有历史终态的对照验证。这里要求修正任务中心投影，不实施冻结 Slice43 的配置/模式工作。

2. **九页主体仍未实现约定的参考结构与信息层级（RO-1；AC-1/7）。**
   实看 production build 的九张独立截图，并对照九张参考：现状是旧页面上追加标签和列，
   四个小统计块聚在内容左半边，提示为连续普通段落；导航/筛选/表格/分页没有形成参考中的
   完整清单面板，筛选仍是浏览器默认控件，普通表格行紧贴、名称与类型挤在同一行。
   1536×1024 原生测量中来源/状态控件高 19px，普通数据行高 22px；失败页的文件数、日期与
   定位按钮在宽屏仍被挤成碎行。各恢复页同样复用这一紧凑表格。单行横向九标签已经修正，
   但不足以满足本 Task 已承诺的参考结构、层级与视觉验收。

   修正方向：在任务中心限定范围内完成统计区、提示条、同级九导航、可用筛选栏和有行层级/
   间距的清单及分页布局；保留真实数据、权限、查询/返回行为及未知状态。复用项目既有设计
   组件/样式，避免全局样式回归。数值、样本、精确坐标和装饰图标不作为新增要求，亦不要求
   像素一致。Developer 在提交前实际查看九页与窄屏截图；脚本只生成截图不能判定视觉通过。
   本项只要求既定查询/定位旅程的页面实现，不提前引入后续创建/恢复摘要协议。

### 给 Developer 的简版修复方案

继续 Task45.1，先修查询语义，再统一九页主体；沿用当前 Task Base、验收和 T4 计划。

**第一步：补齐“需要处理”的运行级问题。**

- 从 `sqlite_runtime.py:_run_query_document` 入手，把已有文件项问题与 Job 的结构化修复/
  核查证据统一纳入当前 attention 判断；使用稳定类别及耐久状态，不匹配错误文案。
- 保留 Job/Task 的现有去重及同一读快照，让列表、计数和详情共用判断。明确区分普通排队、
  当前需修复和纯历史失败；解除依据已有耐久处置/关联结果，不能猜测新 Active 已修好旧 pin。
- 没有文件项的修复工作显示业务原因及“查看原因与修复指引”，进入该运行的既有诊断详情；
  文件数显示尚未生成/不可用。不为它伪造文件恢复成员，也不新增重试或执行入口。
- 先用审查证据中的 `pre-task-real-probe.py` 复现，再补正式回归：真实准入后、Task 创建前
  失败仍可定位；普通排队不报警；历史失败与有处置证据的问题不会被一律当作未解决。

**第二步：用一套任务中心布局完成九页。**

- 在 `OperationsLanding.tsx` 和任务中心限定样式中复用现有设计组件，按参考组织：标题区 →
  横向四卡统计 → 提示条 → 包含九标签、筛选、列表及分页的完整清单面板。
- 桌面四卡铺满可用区域；统一筛选控件高度与间距；任务名称/辅助说明分层；表格增加行间距
  与分隔。给日期、文件数和操作保留合理空间，长业务名称/路径按既有方式截断或展开。
- 保留每个视图已有的真实列和动作；窄屏保持九标签单行可滚动，筛选可换行，表格有界滚动，
  问题文件界面可正常阅读。所有数据、权限和 URL/返回逻辑继续由现有实现承担。
- 先构建并实际打开“全部任务 / 需要处理 / 元数据恢复 / 失败恢复”检查布局，再逐页检查全部
  九页及窄屏、键盘、重连；样本值和像素坐标不作为实现常量。

**第三步：按原计划验证和交接。**

先跑新增/受影响测试及真实浏览器关键路径，修完已知问题后，在最终候选完成原定 T4 gates。
报告列出修复 SHA、两个阻塞项对应证据、九页与窄屏截图及原始日志；提交 `READY FOR B REVIEW`。
不新建 Task，不改 Slice/冻结范围；上轮已确认修复的三个 P1 纳入回归。

### 独立验证、证据与复用边界

- 治理 PASS；已提交 Slice/Roadmap ACTIVE，工作树 Contract 与 HEAD 一致。读取治理、产品、
  架构、当前 Slice/Task、页面规范与 B 经验；范围仍以已提交 Contract 为 authority。
- 审查 Task Base..candidate 的完整 manifest、当前修正 diff、测试/平台门禁修正及报告。
  `7b7f833..b9f229b` 仅 TASK.md；本轮没有产品源码、测试、依赖、schema 或 A-owned 文档修改。
- `.venv/bin/python -m unittest tests.test_operations_task_center tests.test_operations_run_inventory tests.test_recovery_continuation tests.test_operations_workspace tests.test_operations_run_detail tests.test_scope_continuation tests.test_recovery_batch`：
  **258 tests / 18.372s / OK**，无 skip；ResourceWarnings 保留原文。
- 独立 recovery/progress probes、pre-Task Worker/WSGI probe，以及已有真实 claim-boundary
  测试上的只读观察均完成；后者 7 个配置失败场景全部复现 attention 遗漏。
- 独立 Chromium 使用 production build / 真实 Python harness / 临时 SQLite 和假 Provider：
  验证混合 Task/type 定位、重连、未知效果仅核查、成功兄弟项保留、九页、轮询和窄屏。
  终态失败页在 6.1 秒内 2→3 行，库存 GET 11→12；产品请求全部 GET。
  九页默认无详情，窄屏九标签单行且键盘聚焦可横向滚动。这些通过事实不代表视觉验收 PASS。
- 查阅 Developer 索引与原始日志，确认记录了 Python **2457 / OK / 7 skipped**、
  Vitest **1114 passed / 75 files**、fake E2E **246 passed**、real-Python inventory **25 passed**、
  Unicode **1 passed**、visual capture **1 passed** 及 Docker release-security smoke 成功输出。
  Python 全量在干净候选 worktree 执行，用户预存 schema48 DB 保留；build 日志中的资产名与
  B 实际使用的产物一致，B 另存当前 build/dependency SHA256。未将截图生成或报告文字当作
  全部 AC 已满足的证明。
- 因已实证 P1，本轮未独立重复昂贵全量 Python/Web/fake/real-Python/Unicode/Docker 门禁，
  未给出全部 T4 门禁的无条件复用/PASS。修正 executable candidate 后仍完成原定 T4 gates，
  保留候选身份、原始日志、截图/trace 与完整结果；文档 successor 按 workflow 证明输入不变。
- 耐久索引：`.git/validation-evidence/7b7f833cd7b0640e7218b13e3d5a4a245628c9f9/b-review4-20261015/INDEX.md`。
  目录命名是审查开始日期；交接完成日期见本节。证据仅本地可达，未推送。
- 本轮仅更新 B-owned TASK.md 和 ignored 审查证据，保留所有预存用户脏文件与私有 ignored
  配置；审查服务在交接前停止。没有 A Final Review、Slice 关闭或新实现授权。

Slice 复核：RO-1 仍有当前问题遗漏与页面验收缺口；RO-2、完整 RO-3、RO-4 同页继续授权、
RO-5 全入口 Scan 退役和 RO-6 Slice-final 验证仍未完成。继续同一 Task45.1 修正，不创建下一
Task，不提交 Closure Packet，不改 Slice/Roadmap/稳定需求，不恢复冻结 Slice43。

可复用经验候选：当前问题投影应同时检查 item-level 和 pre-Task/run-level 的耐久问题，避免
只修正状态集合后漏掉整类准入失败；视觉验收必须看实际页面构成，截图生成成功不代表交付。
留待 A 于 Slice 收尾合并。
