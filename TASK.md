# Task45.5 — FileIndex 完全退出与 CLI/Web 库级实时列表统一

Authority：已提交 [SLICE.md](SLICE.md) 与 [Development Workflow](docs/development-workflow.md)。
角色经验：[B](docs/agent-experience/task-planner-reviewer.md) /
[Developer](docs/agent-experience/developer-implementation-role.md)。

```text
Task ID: 45.5
Parent Slice: 45
Status: READY FOR B REVIEW
Task Base: 3e2cb31aca211a7dcb7fa7c4ba4883d55b951974
Difficulty: High
Test Level: T4
Planner / Reviewer: B
Required Outcome: RO-7; S-8 / S-9; AC-7; affected RO-1–6 safety and journeys
Next Action: B CONTINUES FIXED-CANDIDATE ACCEPTANCE AFTER AUTHORIZED TEST RESTORATION
```

## Goal

操作者通过 `mediaflow files list`、资源库文件页和媒体库页读取同一精确 Active 库/目录的
真实 Storage 条目；打开、刷新、翻页只读，不保存文件目录或产生工作。明确发起整理后，
无 FileIndex 装配仍完成真实稳定观察→分析→同页摘要→就绪子集确认→Worker 执行→结果/
安全恢复。失败说明阶段、持久状态、已知效果及修复/重新读取/安全重新检查的下一步。

完整旅程和退出边界见 [FileIndex 退役设计](docs/file-index-retirement-spec.md) 第1–7节、
V2-FILES-005/006、REQ-SCAN-002/003/005/006、REQ-ORG-012、REQ-WEB-003、REQ-SAFE-009
的当前修订；整理/恢复遵循 [任务中心规范](docs/task-center-page-spec.md) 第3–5节。

Task Base 规划时的实际缺口：`final_cli.py` 的 files list/show/stats 仍装配 FileCatalog/SQLiteFileIndex；
StorageScanner 仍 upsert/reconcile 全局目录；CLI/API/Worker、部分恢复和 Automation 基础
消费者仍注入或要求索引；SQLite Result 自动同步、整理结果 DTO/Web 同步修复动作仍存在。
`RuntimeFilesBrowserService` 已有两种库的实时列表和隔离游标，应复用。

## Implementation Scope

一个完整 RO-7 行为单元，覆盖必要 domain/application/infrastructure/CLI/API/V1/V2、
schema、Worker 和安装/测试消费者，不按模块拆 Task。按以下顺序实施：

1. 沿真实调用列出索引产品/消费者及去向，区分全局目录与显式工作的来源、观察、pin、
   计划、锁、Result。检查 `file_catalog`、`file_index_lifecycle`、`scanner`、
   `manual_organize*`、`manual_source_validation`、各 continuation、
   `automation_task_definition_preview`、`automation_definition_execution`、
   `final_cli.py` / `cli.py`、`service_api.py` / `operator_ui.py` 和 SQLite 装配。
   交接简述实际移除/承接位置，不另建索引抽象、内存替身或 no-op 仓储。
2. files list 直接复用现有 `RuntimeFilesBrowserService` 库级行为：必须互斥选择
   `--resource-library ID` 或 `--media-library ID`，支持 `--path`、`--limit`、
   `--cursor`。CLI/Web 读取同一 Managed Active；不从竞争 JSON 快照列举、不复制遍历器、
   不经 shell/API 绕行。分离只读配置解析与运行库初始化：列表不创建/升级数据库，不装配
   Task/索引写仓储；缺 Active、配置损坏及缺库给出修复路径。保留精确名称、类型、
   大小/mtime、有界分页/截断和未知总量。移除旧索引筛选/时间/FileID 游标，非法输入不改义。
3. 移除 FileIndex list/detail/stats/reprocess 产品、V1/V2/API/CLI 链接、DTO/状态/
   Dashboard 索引指标、Result/普通维护同步与修复动作。旧索引入口删除或按设计薄拒绝并
   指向库级浏览/任务中心；无兼容查询引擎。移除 RuntimeFilesBrowser 无用索引参数。
   两库页现有普通维护、返回、错误/空态与任务结果保持，不制造整库统计。
4. 所有支持的处理消费者改用工作内精确来源与 live Storage 校验，复用现有有界 discovery/
   持久观察、纯过滤及 ManualSourceValidator 等能力。来源/计划受原固定配置约束，
   来源替换/缺失在变更前拒绝。无全局 New/Modified/Unchanged/Missing 对账或长期
   occurrence/disposition 目录；同路径新文件不被旧结果永久压住。stable-size 必须跨真实
   区间，不能用旧mtime/首次stat替代；大小/mtime/有效指纹变化重置区间。重开保留合法观察，
   丢证据需重新观察。保留 scope/条目/时间边界、协作控制、claim/lease/fence、原子准入、
   重复/丢响应核对、精确就绪子集和主文件/附件独立结果。
5. 删除 domain 索引模型/协议、FileCatalog/lifecycle、SQLite/内存索引实现、专用 schema/
   初始化/后台写入和死代码。`file_lifecycle.py` / `file_index_schema.py` 中仍被 Task/计划
   使用的纯来源证据或 Task 字段迁到真实所属职责，不盲删安全证据、不保留更名全局目录。
   fresh 无索引表；受支持工作重开/重启/失败原子性保持。按未上线边界验收，不建设旧索引
   生产迁移/双写；不自动 DROP/清空/重建任何现存运行库或媒体。不支持的开发旧 schema
   明确拒绝并指向隔离新数据目录。
6. 更新索引播种 tests/fixture、wheel/Docker/Worker harness，从临时 live Storage 与显式
   工作证据出发，保留等义安全断言，不删断言/扩大重试超时/隐藏skip。必要说明仅陈述候选
   事实，不将未验收退役标为已交付 CURRENT；全 Slice 文档闭合由 A 处理。
   受影响验证后提交连贯实现 checkpoint，交 B 固定候选验收。

RO-8 独立 Preview 完整退出不在本 Task；清理其必要索引耦合，不新建索引兼容/修复服务，
不要求保留废弃 FileID 入口。共享分析/固定计划/Rules/配置/授权检查必须无索引可运行。
不得借此实施整个 Preview 生命周期重构，或冻结 Slice43 页面/Run once/指标/设置重设计。
若必须改变父 Contract，交 B→A，不自行放宽范围或安全语义。

## Acceptance Criteria

- [ ] CLI 两种库选择与对应 Web/API 同源；混合媒体/非媒体/目录、Unicode、长名/边界
  空白逐项一致，不套用整理过滤。游标绑定库种类/ID/root/配置/目录；同名跨种类库不混淆，
  非法/过期/跨目录游标与越界可恢复拒绝，不承诺无快照跨页静态一致性。
- [ ] 无/冲突库选择、旧参数、无Active、停用/不存在库、Storage故障/权限失败可解释，
  不显示为空、不回退JSON/索引；CLI只读不创建数据库或升级schema。
- [ ] 列举/导航/刷新/翻页前后无目录/观察/Task/Job/Result/许可写入，Provider/Hash/
  媒体mutation为零；允许配置读取及普通访问日志。fresh无索引专用表/索引。
- [ ] 生产源码/装配/包无可运行FileIndex产品、仓储、内存/no-op替身、全局目录/
  occurrence/disposition、同步/reprocess/修复与死代码；其他支持工作不因缺索引拒绝。
  按职责审查残余引用，不要求历史文本/否定断言字符串零匹配。
- [ ] 无预扫描/索引完成真实稳定观察、变化重置、同页摘要、精确子集确认、Worker执行、
  结果及安全恢复/重开；直接选择与目录遍历同约束，实质边界不完整不执行first-N。
  分析零mutation/零执行权；结果保存/显示失败不重放效果。
- [ ] 源变化、合法旧pin/缺pin、并发/重复准入/丢响应、stale owner和混合成功/失败/
  未知效果保持拒绝及恢复安全；成功兄弟和已完成主文件不因附件异常重放，附件原因/
  目标/按策略指引可见，未知效果只核查。C用NamingA/ClassificationA仍为C。
- [ ] 普通维护/传输、任务历史/详情/控制/导出、共享分析/检查及仍支持的Automation
  基础授权/执行消费者不装配索引仍可用；不强制恢复已合并43专属UI。
- [ ] 受影响验证与B指定T4/真实入口/产物门禁有实际结果；未提供门禁pending，
  不由旧PASS或Task45.4历史例外推定通过。

## Required Tests

分工/复用遵循 [workflow §6](docs/development-workflow.md#6-test-levels)。
使用临时根/fake/local-server Provider，不读用户库、私有配置或真实媒体。

### Developer — affected tests

仓库根执行；`PYTHONPATH=tests` 仅提供测试模块导入路径：

```bash
python3 scripts/check_governance.py
PYTHONPATH=tests .venv/bin/python -m unittest test_file_index_retirement test_runtime_files_browser test_media_library_browser test_storage_browser
PYTHONPATH=tests .venv/bin/python -m unittest test_scanner test_resource_library_pipeline test_media_discovery test_scan_retirement_stability test_organize_preparation
PYTHONPATH=tests .venv/bin/python -m unittest test_manual_organize_intent test_manual_organize_preview test_manual_organize_execution test_v2_manual_organize test_recovery_continuation test_task_center_recovery_lineage
git diff --check
```

新增 `tests/test_file_index_retirement.py` 覆盖CLI/API live parity、旧索引输入退出、只读
无建库/升级、副作用计数及fresh/重开无索引事实。scanner/fixture随职责调整，不要求
保留索引专属测试，但保留其过滤、稳定性与安全等义覆盖。

若修改下列消费者，追加对应直接受影响组；已知失败修复必须重跑失败用例：

```bash
PYTHONPATH=tests .venv/bin/python -m unittest test_task_persistence test_sqlite_backup test_sqlite_restore
PYTHONPATH=tests .venv/bin/python -m unittest test_direct_file_operations test_manual_operations_contract test_operations_task_center
PYTHONPATH=tests .venv/bin/python -m unittest test_automation_task_definition_preview test_automation_definition_execution test_automation_authorized_execution_matrix test_configuration_organize
PYTHONPATH=tests .venv/bin/python -m unittest test_metadata_correction_continuation test_recovery_batch
```

对实际新增/修改Python文件运行 `.venv/bin/ruff check <files>`、
`.venv/bin/ruff format --check <files>`，报告实际路径/结果，不跑全仓替代受影响检查。
Web在 `web/`：

```bash
npm run typecheck
npm run test -- run src/entities/operations/organize.test.ts src/features/operations/OrganizeRouter.test.tsx src/features/library/StorageFilesPage.test.tsx src/features/library/MediaLibraryFilesPage.test.tsx
npm run build
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/live-files.python.spec.ts
```

新增 `live-files.python.spec.ts`，复用/调整现有real-Python harness，在production build上
验证两库列表/分页/错误恢复/只读；同一隔离fixture调用真实CLI对照条目，不播种索引、
不用mock API。其他前端测试有修改则追加精确路径，changed files运行 `npx eslint <files>` /
`npx prettier --check <files>`。Developer不跑全Python/Web/E2E或Docker/release matrix，
不准备B的全量证据包；受影响检查后即可交接。

### B — acceptance and full regression

在READY FOR B REVIEW明确SHA上检查 **Task Base..Head全部diff**、消费者/死代码与文档，
核对用户脏文件及frozen43/RO-8边界；先独立复现已知P0/P1，可提前FIX REQUIRED，修正留45.5。

B执行 [共享全量门禁](docs/development-workflow.md#shared-full-regression-commands) 的全部
Python/Web/示例/依赖/禁止依赖/编译/完整E2E/wheel/安装消费者/安全覆盖，另执行：

```bash
# cwd web/；先完成production build。各spec独立harness，output不共用。
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/live-files.python.spec.ts --output ../.git/validation-evidence/<candidate-sha>/task45.5/live-files
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts --output ../.git/validation-evidence/<candidate-sha>/task45.5/inventory
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-task-center-visual.python.spec.ts --output ../.git/validation-evidence/<candidate-sha>/task45.5/visual
npm run test:e2e -- --config=playwright.python.unicode-principal.config.ts tests/e2e/operations-principal-identity.python.spec.ts --output ../.git/validation-evidence/<candidate-sha>/task45.5/unicode
```

B独立关键复现，不能以源码检索或Developer测试标签替代：

1. 隔离Managed Active、同ID/Storage/root两种库、混合非媒体/目录/Unicode/长名/空白名与
   多页条目，真实CLI/Web/API比对；跨种类/目录/配置游标拒绝，无Active/403/Storage故障→
   修复→重读。前后核对媒体、工作/观察/许可记录、Provider/Hash/mutation计数；库不存在/
   数据库缺失/旧schema只读不建库不升级。检查生产源码/包/fresh schema无索引/替身。
2. 新来源零预扫描：直接文件和文件夹分别真实stable-size等待/替换重置→同页摘要，
   未确认零效果，子集确认后实际Worker执行。独立核对来源变化、重复/丢响应、旧pin/
   新Active、混合失败/附件/未知效果及重启/重开，不能重放成功或未知效果。
3. wheel隔离安装、离开源码运行真实CLI/API/Worker和无索引整理/恢复，核对import路径、
   wheel hash、served assets与fresh/重开。B编写/保存必要独立脚本，不把证据补齐交回Developer。

生产Docker使用固定候选新建镜像；`<candidate-sha>`替换为实际完整SHA，不误用同名旧镜像。
B执行现有harness，实施中的必要索引fixture改动应纳入本Task：

```bash
docker build -t mediaflow:task45-5-<candidate-sha> .
.venv/bin/python scripts/docker_scan_retirement_browser_proof.py --image mediaflow:task45-5-<candidate-sha> --artifacts .git/validation-evidence/<candidate-sha>/task45.5/scan-stability
.venv/bin/python scripts/docker_task_center_recovery_browser_proof.py --image mediaflow:task45-5-<candidate-sha>
.venv/bin/python scripts/docker_restart_fault_smoke_test.py --image mediaflow:task45-5-<candidate-sha>
.venv/bin/python scripts/docker_release_security_smoke_test.py --image mediaflow:task45-5-<candidate-sha>
```

B另在该镜像真实CLI/API/常驻Worker复现第1–2项及普通维护、仍支持的Automation基础消费者。
按本轮用户明确修订，不涉及旧版/A版升级兼容；只验fresh无索引、当前版本重开/重启和
当前版本失败原子性，不跑Base/旧版数据升级、历史字段兼容或升级回滚矩阵。
实际检查1536×1024及380×720截图、键盘、深链/返回/重连。日志/截图/脚本/产物digest保存于
`.git/validation-evidence/<candidate-sha>/task45.5/`，报告cwd/命令/结果/数量/skip/不可用。
必需环境不可用由B保留pending，不判完整T4 PASS，不冒充产品缺陷返工。

执行输入改变则刷新分配的验收；仅报告变更证明源码/测试/harness/依赖/配置/产物不变，
跑受影响文档检查。匹配结果可复用到Slice-final，缺失覆盖由B补齐，不机械重跑Final。

## Non-goals

- RO-8独立Preview完整退出尚未交付，本Task不因此宣称Slice ready。
- 旧版/A版升级、旧数据/字段兼容、跨版本迁移及升级回滚验证（用户本轮明确排除）；
  旧FileIndex迁移/双写/FileID兼容/同步恢复，无用户数据清空/删除。
- Slice43工作区重设计、MediaLibrary Organize、新Provider/引擎、附件-only自动恢复、
  未知效果重放、无限遍历或跨任务批量mutation。
- 改A-owned Slice/Roadmap/Progress边界、重开45.4或补记其历史全量PASS、自行关闭Slice。

## Developer Completion Report

READY FOR B REVIEW. 同一 Task，Base `3e2cb31aca211a7dcb7fa7c4ba4883d55b951974` / Goal / High /
T4 不变；实现代码 SHA `f155522fefaaca0d34cbb5d322c55c2ef4cb0ee6`（本报告随后单独 docs 提交，
交接 HEAD 以交接响应完整 SHA 为准）。B 上一轮判定 **FIX REQUIRED — remaining-scope admission
performs an unbounded synchronous Storage probe**；本轮仅修该阻断，留在同一 45.5。上一轮的
preparation-read / explicit GET recovery 修复保持有效，未回退。

### 先复现（修复前，实际确认）

按 B 提供的独立反例脚本在修复前代码上实跑（`.git/validation-evidence/cbe1d1b…/task45.5/
b-review/recovery-probe-bounds.py`、`recovery-probe-scope.py`）：

- 游标类反例（重复游标空页、不同游标连续空页）：配置 `max_page_fetches=2000`，两例都同步
  **2005** 次 `list_page` 后返回 **202**，探测无自身停止条件；
- 精确范围反例：任务范围 `Media/Allowed`，provider 对该目录返回错误父目录的
  `Media/Sibling` 条目，探测实际 `stat`+`list_page` 了 `Media/Sibling` 后 202；
- 两例守卫 mutation 计数全 0、媒体 fixture 字节不变——与 B 结论一致，是边界缺口，非媒体损害。

### 根因与修正（`mediaflow/application/media_discovery.py`）

`admit_recovery_preparation` 的准入前存在性探测 `_scope_has_remaining_candidate` 直接遍历：
不消耗页数/条目数/目录数/深度/活动时间预算、不检测游标重复/无进展、跟随 provider 原始
`StorageEntry.path` 而不验证精确子条目；空页不增加条目计数，`max_visited_entries` 无法约束
纯空页游标。改为 `_probe_remaining_scope`，返回三态 `_RemainingScopeProbe`
（`REMAINING` / `NONE` / `INCOMPLETE`）：

- 探测完全复用 Worker 遍历的同一边界：`_list_page`（游标类型/长度校验）、
  `_admit_provider_entry`（精确子条目/父目录/库内校验）、纯 include/exclude/depth 策略，以及
  全部 `DiscoveryBudgets`——页数、条目数、目录数、safety depth、`max_active_seconds`
  （空页同样消耗页数与时间预算，用注入的 monotonic 时钟，不新增真实等待）；
- 任一边界耗尽、游标循环/无进展、读取失败、unsafe entry、目录循环 → `INCOMPLETE`：不冒充
  空范围，正常受理该耐久准备，由有界 Worker 记录真实未完整原因（既有 durable preparation
  机制，无新队列/引擎/状态复制）；
- 只有探测在边界内真正走完且无候选才返回 `NONE`，此时保留原有真实
  `no_remaining_scope` 409（与 inline boundary 同一拒绝，零 durable 工作）；
- 全程只读：零媒体 mutation、零执行权、精确原 pin/预算/排除集、重复准入收敛
  （`_reconcile_recovery`）与已完成/未知效果非重放均不变。

### 新增测试（`tests/test_scope_continuation.py`，9 个真实 API 用例）

均经 `mock.patch.object(api._media_discovery, "_guarded_storage", …)` 注入真实
`ReadOnlyStorageGuard` 包装的 fake 分页 storage（stat 委托真实 LocalStorage），走真实 API
`POST /api/v1/tasks/{id}/remaining-scope-previews`；不改产品超时/重试，不弱化断言：

1. `…_stops_at_the_page_budget_instead_of_hanging`：游标永不推进的空页 provider，探测受
   `max_page_fetches=3` 约束（实测 ≤3 次 `list_page`），202 受理、守卫零 mutation、媒体不变。
2. `…_refuses_a_provider_entry_outside_the_exact_scope`：范围 `Incoming/Allowed`，provider 返回
   错误父目录 `Incoming/Sibling`；探测不再 stat/list 兄弟目录，202 受理（不完整→Worker 记录）。
3. `…_refuses_a_repeated_cursor`：同一非空游标重复，≤2 次 `list_page` 停止。
4. `…_honours_the_entry_budget`：每页 1 条目 + `max_visited_entries=2`，≤3 次分页停止。
5. `…_refuses_a_storage_failure_instead_of_claiming_empty`：list_page 抛真实
   `StorageError(CONNECTION_LOST)` → 202 受理（不冒充 `no_remaining_scope`），零 mutation。
6. `…_still_refuses_a_safely_empty_scope`：仅非媒体/临时文件的真实空范围仍 409
   `no_remaining_scope` + `sideEffects=none`，无 Preview、无媒体变更。
7. `…_stops_at_the_safety_depth_boundary`：`max_depth=0` 时深层子树从未被读取。
8. `…_refuses_a_provider_directory_cycle`：子目录列表指回祖先条目 → 精确校验拒绝，
   `list_page` 只发生在两个真实目录上。
9. `…_honours_the_active_time_boundary`：注入假 monotonic（每 tick +400s），
   `max_active_seconds=600` 内 ≤2 次分页停止。

**修复前基线验证**：把生产文件回退到父版本重跑 9 例 → **6 FAILED**（1/2/3/7/8/9），证明是
真实回归覆盖；4/5/6 为 B 要求的边界保持检查（修复前后都必须成立）。修复后 9/9 通过。

### 实际受影响命令/结果（本轮全部实际执行）

仓库根：
- `python3 scripts/check_governance.py` → **PASS**（实施前与收尾各一次）
- B 反例脚本 `recovery-probe-bounds.py` / `recovery-probe-scope.py`：修复前确认缺陷（见上）；
  修复后重跑 → 两脚本的旧断言（缺陷成立）不再成立（页预算耗尽→202 受理但
  `list_page` 从 2005 降为受预算约束；兄弟目录不再被 stat/list），即缺陷消失
- `PYTHONPATH=tests .venv/bin/python -m unittest test_scope_continuation test_media_discovery
  test_organize_preparation` → 修复前基线 **216 tests OK**；修复后（含 9 个新用例）
  → **225 tests OK，15.321s**
- `test_scope_continuation` 单独：**100 tests OK，7.44s**
- `.venv/bin/ruff check` / `.venv/bin/ruff format --check`（`media_discovery.py`、
  `test_scope_continuation.py`）→ 全部通过（初版 format 报 1 处，`ruff format` 修正）
- `.venv/bin/python -m compileall -q`（两个改动文件）→ 通过
- `git diff --check` → 干净

未运行 Web/E2E：本轮为纯后端边界修正，API/Web 契约未变（202/409 语义、响应字段不变），
按 B 指示不要求重复 Web/原生套件。

### 已知风险/边界

- 完整 Python/Web/E2E、Unicode principal、视觉、wheel、生产 Docker 等 T4 门禁本轮未运行也未
  声称通过，仍由 B 执行；本机无远程 CI。
- `INCOMPLETE` 探测沿用既有受理路径：操作者会看到准备被受理、随后 Worker 记录真实的
  budget/cursor/depth/read-failure 未完整原因；与“探测证明空范围→409”是两种不同真实结果。
- 探测的读放大仍存在但已受全部既定预算约束（至多一次预算内的同步预检读）；未新增异步预检
  任务或第二套遍历器，符合“不另开 Task / 不新增队列”的要求。
- 预存修改保留、未纳入 checkpoint：删除 `docs/pics/操作与任务.png`；未跟踪 `.DS_Store`、
  `.t*.log`/`.mgmt.log`、`docs/pics/自动化页*.png`、`output/imagegen/slice45-task-center-v1.zip`、
  `web/test-results-*`。私有 ignored 配置不读取、不暂存。
- RO-8 未交付，本 Task 不宣称 Slice ready，不自判 PASS，不规划后续 Task。
- 时间：测试命令实际执行累计约 3–4 分钟（2 次反例复现、3 轮受影响批、1 次修复前基线回退
  验证、若干单例验证），本开发轮次总时长约 45 分钟（读文档/代码、实现、调试测试 fixture、
  报告），测试占比约 7–9%，低于 30% 上限；未用等待凑比例。

## B Review Result

```text
Reviewed candidate: 4d1556c12c1a895501897f21ffef62eaac7ce61d
Review range: 3e2cb31aca211a7dcb7fa7c4ba4883d55b951974..4d1556c12c1a895501897f21ffef62eaac7ce61d
Decision: FIX REQUIRED — retained safety regression assertions removed/weakened
Task blockers: tests/test_operator_ui.py; mandatory test-preservation requirement
Slice Required Outcomes / Surfaces all satisfied: NO — RO-7 acceptance pending; RO-8 not delivered
Next: SAME TASK FIX LOOP; no next Task / Closure Packet / Slice closure
```

### 同一 Task 的精确修正

本 Task Implementation Scope 第6步要求保留等义安全断言，允许删除索引专属测试；当前
`tests/test_operator_ui.py` 却删除了仍保留行为的3个测试，并缩减了另1个测试。它们不读取
FileIndex，覆盖计划详情、未就绪/过期项恢复、执行阻塞入口和独立显式授权，不能作为
FileIndex 专属退出内容删除。独立 Preview 的 RO-8 完整退出不在45.5范围，不能提前据此
豁免其仍保留行为。本结论是验收覆盖退化，不声称当前产品功能已发生运行时故障。

1. 对照 Task Base 的 `tests/test_operator_ui.py`，恢复以下4个方法的完整原有断言；其中
   第1个方法仍存在但断言被缩减，后3个方法已被删除。无需修改产品或增加新功能：
   - `test_persisted_preview_detail_renders_scope_occurrence_and_mutation_state`
   - `test_persisted_preview_blockers_and_stale_items_expose_recovery_without_authority`
   - `test_manual_execution_blocker_section_and_resolution_are_served`
   - `test_manual_recovery_link_controls_are_served_and_bounded`
2. 保持本 Task 已有索引退役断言。检查同文件的其余删减，只移除确属退役索引的断言；
   仍保留行为的断言保留或明确迁移到等义覆盖，不用弱化断言解决失败。
3. Developer 只运行以下直接受影响检查后提交同一45.5固定候选，报告实际结果：

```bash
PYTHONPATH=tests .venv/bin/python -m unittest test_operator_ui
.venv/bin/ruff check tests/test_operator_ui.py
.venv/bin/ruff format --check tests/test_operator_ui.py
python3 scripts/check_governance.py
git diff --check
```

B 已从 Base 原文提取这4个方法，在当前候选生产 `APP_JS` 上独立运行：**4 tests PASS**。
原文件、加载器、命令、log/json保存在下方当前证据根的 `base-operator-ui-tests.py`、
`retained-ui-assertions-proof.py`、`retained-ui-assertions.*`。因此无需假设新的用户并发或
注入业务状态，也不要求恢复已退役索引产品。修正后 B 核对具体 delta，继续剩余
Base..Head内容审查及受影响验收；全量门禁仍由 B 承担，不交回 Developer。

### 已撤回的场景结论

前次“运行首项时原任务pending次项可合法忽略”的P1保持撤回。原脚本人工upsert
processing/blocker/ignored，未证明生产入口可达；正常入口独立复现为无blocker、仅允许
investigate，ManualIgnoreService返回 `invalid_action`，状态不变。循环外读取资格是代码
事实，但不据未成立的触发链要求逐项刷新、故障注入或实现“运行中任意忽略”。证据与
撤回决定仍见本机 `.git/validation-evidence/2cf7efab4daf70547138ce8e36a99bb8ac3c63c6/task45.5/b-scenario-audit/`。

### B 实际门禁与证据复用

证据仅在本机稳定ignored目录，不声称远程CI可达：

- 本轮：`.git/validation-evidence/4d1556c12c1a895501897f21ffef62eaac7ce61d/task45.5/b-acceptance/`
- 匹配前轮：`.git/validation-evidence/056ac8501109eb5f4acacc2903e2ff403ad5631a/task45.5/b-review/`

两候选只差 `TASK.md`；`preflight.json` 与前轮 `web-reuse-inputs.json`记录源码、测试、
harness、配置、依赖和Web树/产物匹配。原始失败与重跑日志保留，不从PASS表中抹除。

| B 门禁 | 实际结果与限制 |
|---|---|
| 治理、Python质量、示例、禁止依赖 | 本轮governance PASS；复用前轮全仓ruff/compileall/pip check/两示例/禁止依赖/diff检查PASS |
| Python全量 | 复用2734 tests OK / skipped7；ResourceWarning原样保留 |
| Web静态、单测、build | 复用typecheck/lint/format/build，81 files /1181 tests PASS；Web树079741b421b92ee2df9dcb0a9126f121782d5dcd及四项产物hash一致 |
| 普通与真实入口E2E | 复用普通240 PASS、real live-files 5 PASS、real inventory 41 PASS；真实API/SQLite/Worker、隔离fixture |
| 已知边界独立复现 | 前轮重复空游标2页停止、不同游标2000页预算停止、错误父目录兄弟不stat/list；API202、零mutation、字节不变 |
| 本轮原生视觉/Unicode | native-visual 2 PASS、native-unicode 1 PASS；16张九标签/桌面/窄屏等图已看；另6张滚动后的实际问题面板、真实创建计划/确认桌面和窄屏图已看。补图未点击执行，不以截图名替代完成态 |
| wheel | 当前HEAD git archive清洁构建、smoke PASS；离开源码独立Python3.13 venv的12个真实CLI/API/Manual/Automation Worker消费者PASS；无8个退役模块 |
| Docker消费者/行为 | 本轮安装消费者12 PASS；复用前轮稳定性mounted及recovery PASS，真实elapsed稳定性/变化重置/确认/Worker/当前版本重启非重放 |
| Docker生产安全 | 当前HEAD清洁源码release-security PASS、restart-fault PASS，后者覆盖四常驻服务/离线Provider/重启/fence/未知效果非重放 |
| 产物一致性 | 容器164个已安装模块与清洁源码逐项一致，wheel同样匹配；真实MediaFlowApi+wsgiref HTTP返回的4项Web资源bytes与容器/本机build逐项hash一致 |
| 本轮覆盖保留反证 | Task Base四项原断言对当前生产资产4 PASS，证明这些断言仍适用，不应随索引退役删除 |

旧wheel的smoke不能证明无索引包：本机ignored `build/lib`残留使旧wheel含8个已删除模块；
该项退役证据已撤销，未清理用户build，改由git archive隔离清洁构建替代。新wheel SHA256
`eff181a4870de8895d53ae17dce028e8b933382cc3b0e997e5418fafaa1d3860`。
`packaging-correction.json`、`clean-wheel-identity.json`记录原因/替代；旧wheel消费者失败、
误用Python3.14导致requires-python拒绝、Docker挂载/runner启动错误均留存并计时。
本轮Docker安全镜像 `mediaflow:task45-5-4d1556c-security`，实际image ID
`sha256:70d54e9c54794e13b6082d57ddbdde672fdf28775c04dff39f822b06f8f222f5`。

本轮已继续审查来源/稳定性、同pin恢复、Scope预算/探测、SQLite原子准入、CLI/API装配、
纯来源证据、测试fixture替换及Web读取失败恢复；发现上述确实违反Task保留要求的删减后
停止判PASS。135文件manifest已核对，**尚不宣称135文件所有内容审查完成**；其余测试/
harness/Web差异仍由B在修正后续审，不能把全量通过当作整个range审查通过。

预存21条dirty/untracked完整保留；本轮只改B-owned TASK.md，不改产品/测试、A-owned
Slice/Roadmap/Progress、冻结43或私有配置；无push。已停止本轮自启harness。
本轮累计测试/build/quality含失败与并行逐次累加、短检查保守预算及实际总时间比例，
记录于当前证据根 `review-timing.json`，小于50%；未等待凑比例。

### 用户授权的测试恢复 checkpoint

用户明确要求 B 直接补回并继续验收，本次仅例外兼任这4项测试恢复的实施；不修改产品，
不代替 A Final Review。上述4个方法的原断言已恢复；`test_operator_ui` 52 tests OK、
该文件ruff check/format及diff check PASS。首次format检查因插入后的空行失败，已格式化
后重跑通过，原失败日志保留。详细日志位于
`.git/validation-evidence/298abc3ca2a1e2e47c5deab7c633ab1d165e53fc/task45.5/b-restored-acceptance/`。
状态恢复READY FOR B REVIEW；此前测试覆盖阻塞已修正，B继续剩余range审查及当前候选
受影响门禁，本段不是最终PASS。
