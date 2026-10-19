# Task45.5 — FileIndex 完全退出与 CLI/Web 库级实时列表统一

Authority：已提交 [SLICE.md](SLICE.md) 与 [Development Workflow](docs/development-workflow.md)。
角色经验：[B](docs/agent-experience/task-planner-reviewer.md) /
[Developer](docs/agent-experience/developer-implementation-role.md)。

```text
Task ID: 45.5
Parent Slice: 45
Status: FIX REQUIRED
Task Base: 3e2cb31aca211a7dcb7fa7c4ba4883d55b951974
Difficulty: High
Test Level: T4
Planner / Reviewer: B
Required Outcome: RO-7; S-8 / S-9; AC-7; affected RO-1–6 safety and journeys
Next Action: DEVELOPER FIXES RETRY STABILITY BYPASS AND WORKER TRUST-STATE CHECK IN THE SAME TASK
```

## Goal

操作者通过 `mediaflow files list`、资源库文件页和媒体库页读取同一精确 Active 库/目录的
真实 Storage 条目；打开、刷新、翻页只读，不保存文件目录或产生工作。明确发起整理后，
无 FileIndex 装配仍完成真实稳定观察→分析→同页摘要→就绪子集确认→Worker 执行→结果/
安全恢复。失败说明阶段、持久状态、已知效果及修复/重新读取/安全重新检查的下一步。

完整旅程和退出边界见 [FileIndex 退役设计](docs/file-index-retirement-spec.md) 第1–7节、
V2-FILES-005/006、REQ-SCAN-002/003/005/006、REQ-ORG-012、REQ-WEB-003、REQ-SAFE-009
的当前修订；整理/恢复遵循 [任务中心规范](docs/task-center-page-spec.md) 第3–5节。

实际缺口：`final_cli.py` 的 files list/show/stats 仍装配 FileCatalog/SQLiteFileIndex；
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
# cwd web/；先完成production build
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/live-files.python.spec.ts tests/e2e/operations-inventory.python.spec.ts tests/e2e/operations-task-center-visual.python.spec.ts
npm run test:e2e -- --config=playwright.python.unicode-principal.config.ts tests/e2e/operations-principal-identity.python.spec.ts
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
fresh无索引、同版本重开/重启、受影响支持版本迁移和失败原子性必需，不扩成旧索引生产迁移。
实际检查1536×1024及380×720截图、键盘、深链/返回/重连。日志/截图/脚本/产物digest保存于
`.git/validation-evidence/<candidate-sha>/task45.5/`，报告cwd/命令/结果/数量/skip/不可用。
必需环境不可用由B保留pending，不判完整T4 PASS，不冒充产品缺陷返工。

执行输入改变则刷新分配的验收；仅报告变更证明源码/测试/harness/依赖/配置/产物不变，
跑受影响文档检查。匹配结果可复用到Slice-final，缺失覆盖由B补齐，不机械重跑Final。

## Non-goals

- RO-8独立Preview完整退出尚未交付，本Task不因此宣称Slice ready。
- 旧FileIndex迁移/双写/FileID兼容/同步恢复，无用户数据清空/删除。
- Slice43工作区重设计、MediaLibrary Organize、新Provider/引擎、附件-only自动恢复、
  未知效果重放、无限遍历或跨任务批量mutation。
- 改A-owned Slice/Roadmap/Progress边界、重开45.4或补记其历史全量PASS、自行关闭Slice。

## Developer Completion Report

READY FOR B REVIEW at implementation HEAD `72682d1e3277343b674d62e5ceda99a824036c00`
(Task Base `3e2cb31aca211a7dcb7fa7c4ba4883d55b951974`).

### 行为与关键决策

- FileIndex 产品端到端移除：删除 `domain/file_index.py`、`domain/file_catalog.py`、
  `domain/file_lifecycle.py`、`application/file_catalog.py`、
  `application/file_index_lifecycle.py`、`infrastructure/sqlite_file_index.py`、
  `infrastructure/memory_file_index.py`、`infrastructure/file_index_schema.py`；
  相关测试模块一并删除。fresh 运行库不再创建任何索引表。
- 来源证据保留为有界值对象：新增 `domain/source_evidence.py`
  (`OccurrenceState`/`SourceFingerprint`/`source_fingerprint`/`occurrence_id_for`)、
  `domain/source_reviews.py`，以及 `infrastructure/task_source_schema.py`。它们只服务显式
  Task/Result/Intent/Preview 工作，不构成长期每文件目录、无 New/Modified/Missing 对账。
- `mediaflow files list` 复用 `RuntimeFilesBrowserService`：互斥 `--resource-library ID` /
  `--media-library ID` 加 `--path/--limit/--cursor`；新增
  `infrastructure/read_only_active_configuration.py` 用 `mode=ro` 读取 Active，因此列举
  不创建、不升级、不加写锁运行库。
- `StorageScanner` 改为无状态只读遍历器（无 catalog 参数，接受 `previous` 观察映射）；
  `FileScanStatus`/`FileChange` 移除 `MISSING`；`stable_since` 表示真实稳定区间。
- CLI/API/V1/V2：移除 FileIndex list/detail/stats/reprocess、`/files`、`/file-index`
  路由与 V1 页面、Dashboard 索引指标、Result 索引同步与
  `file-index-reconciliation` 动作；单文件整理入口改为
  `POST /api/v1/resource-libraries/{id}/files/organize`，metadata-correction continuation
  改以 `(task, item, review)` 定位。
- 所有支持消费者（manual organize/preview/execution、continuations、Automation 基础、
  direct files、dashboard）改由工作内精确来源 + live Storage 校验，缺索引不再拒绝运行。

### 实际受影响命令/结果

- `python3 scripts/check_governance.py` → PASS。
- `PYTHONPATH=tests .venv/bin/python -m unittest test_file_index_retirement test_runtime_files_browser test_media_library_browser test_storage_browser` → 33 tests OK。
- `... test_scanner test_resource_library_pipeline test_media_discovery test_scan_retirement_stability test_organize_preparation` → 154 tests OK。
- `... test_manual_organize_intent test_manual_organize_preview test_manual_organize_execution test_v2_manual_organize test_recovery_continuation test_task_center_recovery_lineage` → 152 tests OK。
- 条件消费者组（task_persistence/sqlite_backup/sqlite_restore、direct_file_operations/
  manual_operations_contract/operations_task_center、automation_task_definition_preview/
  automation_definition_execution/automation_authorized_execution_matrix/configuration_organize、
  metadata_correction_continuation/recovery_batch）全部 OK。
- 全量 Python 快照：`unittest discover -s tests -t .` → 2642 tests OK (skipped=7)。
- `.venv/bin/ruff check scripts/ tests/ mediaflow/` → All checks passed；
  `ruff format --check` → 350 files already formatted；`git diff --check` 干净。
- Web：`npm run typecheck` 干净；`npm run test -- run` → 81 files / 1173 tests passed；
  `npx eslint` 相关文件干净；`npx prettier --check` 干净；`npm run build` 成功。
- `npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/live-files.python.spec.ts`
  → 5 passed；`operations-inventory.python.spec.ts` → 38 passed；
  Node fake suite `npm run test:e2e` → 240 passed。

### 已知失败/风险

- `tests/e2e/direct-files.python.spec.ts` 的 “MediaLibrary Files renames a file and
  directory” 在 Task Base 的干净 worktree 上同样 3/3 失败（既有 flaky，非本 Task 引入）；
  其兄弟用例通过。B 独立复核时可确认。
- 依赖真实 SMB/OpenList/S3/TMDB、wheel/隔离安装、生产 Docker 镜像与 1536×1024/380×720
  截图等 T4 门禁仍 pending B（Developer 不跑全量/发布矩阵）。
- RO-8 独立 Preview 完整退出未交付；本 Task 只清理其必要索引耦合。
- 剩余 Slice 工作：B 复核全部 RO/Surfaces；满足则交 Closure Packet。

预存修改保留且不纳入 Task checkpoint：删除 `docs/pics/操作与任务.png`；未跟踪
`docs/pics/自动化页-全局设置.png`、`docs/pics/自动化页.png`、各处 `.DS_Store`、
`output/imagegen/slice45-task-center-v1.zip`、`web/test-results-batch-check/`、
`web/test-results-real-python-final/` 及开发 `.log` 文件。私有ignored配置不读取、不暂存。

## B Review Result

```text
Reviewed: 3e2cb31aca211a7dcb7fa7c4ba4883d55b951974..a3fbb36c7f86ed08629e08247a08e5f154d4adbb
Decision: FIX REQUIRED — retry bypasses stability; Worker promotes untrusted source state
Acceptance runs: 6 new CLI tests OK (6.778s, zero skips); four independent B scripts with actual JSON
Task blockers: long/changed-source stability continuation; unverified/legacy Worker admission
Slice Required Outcomes / Surfaces all satisfied: NO — RO-7 / RO-8 pending
Next: SAME TASK FIX LOOP; B COMPLETES REMAINING DIFF REVIEW / ASSIGNED T4 ON CORRECTED CANDIDATE
```

实现固定为上述候选；交接 `b0f070b1801754d2d53ab9f992374fbc3e7ea3f9` 相对候选仅改
`TASK.md`。已读适用需求/完整旅程/架构及父 Contract 无变更，本轮核对当前指针、契约、修正
生产 diff，并沿原 Task Base..Head 检查来源/观察/恢复链。workflow §6 允许已证实阻塞
提前拒绝；未声称完成整个 Task 全部 diff 审查、T4 或 Slice-final。

已独立确认本次进展：fresh CLI 初次 Provider 失败前已有 verified 来源证据，排队后替换
会拒绝（Worker exit1、0 Provider、无续作项/结果）；1秒稳定间隔的未变来源实际进入分析。
B-1 历史修正保持，相关配置校验源码未改；这些事实不等同于整个 RO-7 通过。

### 同一 Task 的必需修正

1. **P1 — 稳定观察必须约束重试与执行。** 本轮真实反例：配置61秒，首次
   `organize --execute` 记录 unstable_source/failed；立即
   `tasks retry-failed TASK_ID --execute` 在整个流程0.083秒内实际 MOVE 成功。
   当前 `resolve_source_evidence=False` 只对比 fingerprint，既不读取/验证原稳定观察，
   也不重新满足策略。必须将“来源身份可验证”与“稳定区间已满足”分开；所有受支持的
   retry/resume/recovery/Worker/Automation 调用在 Provider/执行前仍校验原pin下的稳定策略。
   长区间、变化后再次等待、重开/新进程都不能绕过。稳定证据缺失时重新开始观察，不能
   将当前stat/旧mtime/指纹相等直接当作区间已满足，也不能把 `resolve_source_evidence`
   布尔开关当作跳过稳定性的许可。
2. **持久等待闭环，不用60秒阈值掩盖。** `_previous_observations` 目前仅在 Python 对象中，
   没有任何新的观察保存/加载路径；注释和报告称 durable 不能作为重开证据。复用现有
   discovery/工作checkpoint与Task/Worker，把观察起点、来源证据、固定作用域、到期时间和
   合法owner/fence落在该显式工作中；等待到期后真实重观察，变化重置，原证据丢失则重新
   观察。长等待可及时返回真实工作状态/身份与安全下一步，不需要同步阻塞整个区间；但立即
   Retry/Continue 只能继续观察/等待，不能直接进入分析或媒体变更。不得只删60秒上限、增加
   `sleep`、再加一次临时stat或删除重试入口来掩盖缺口。保留0秒无需等待、真实空目录可0项
   完成、协作控制和有界发现；不建第二队列/执行引擎或全局文件目录。
3. **B-2 / P1 — Worker 必须校验原证据的可信状态。**
   `PersistedSourceEvidence.has_exact_evidence` 当前只检查两个字符串非空，未检查
   `fingerprint_state`，所以真实 Worker 会将携带正确字段但标为 unverified/legacy 的原项
   分析为 completed/dry_run，并将续作改成 verified。让共享 validator 在消费原证据时明确
   要求其为可信 verified 状态；缺失/半缺失/unverified/legacy 一律 source_unverified，
   保留记录并引导重新选择/准备；不能根据当前stat将不可信原记录升级。恢复和元数据纠正
   Worker、普通重试必须采用同义检查，避免 `_persisted_source_refusal` 与
   `ManualSourceValidator` 两套判断继续漂移。完整可信来源未变及合法旧pin正例继续通过。
4. **先写可区分缺陷的反例，再修。** 稳定性用61秒配置立即重试即可快速验证“未到期零
   Provider/零mutation”，不必每次真等61秒。到期允许、变化重置与重开使用短真实间隔和
   受控时钟/持久观察组合，不能只改mtime假装已经观察。覆盖0、1、超过60秒，直接文件/
   单库目录/全部库及真实Worker续作，原成功兄弟/未知效果不重放。可信状态测试须保留原来
   **真实且匹配的 occurrence/fingerprint，只将状态设为 unverified/legacy**，然后驱动
   真实 `worker run-next`，断言拒绝、0 Provider/媒体变更和不伪造verified；只用伪造字符串
   或仅测直接CLI重试，无法区分“指纹不匹配”与“状态不可信”。

### Developer 执行顺序与代码定位

以下是上述两个阻塞的落地指引，不改变 Task Base/Goal/Scope；先完成证据链，再接稳定观察，
最后验证完整入口，不再按字段拆 Task。

| 位置 | 必须完成的改动 |
|---|---|
| `application/media_organizer.py` 的 `process_file` | 在首次 Provider/策略分析前取得并持久保存本次真实来源身份。调用方已带原证据时先比较，不能用当前stat覆盖原证据。 |
| 同文件的 `process_library` / `process_all_libraries` | 将 discovery 的真实来源证据传给处理边界；不能像当前只传 `file.path`，丢掉已观察到的 occurrence/fingerprint。 |
| `application/task_runtime.py` 的 `begin_item`，SQLite TaskItem/Result 保存 | 首次失败也保留来源证据；重开后仍可读；既有工作证据不能被重试悄悄改绑为当前来源。现有列足够时不另建schema。 |
| `application/manual_source_validation.py` 的 `validate_persisted_source` | 去掉“完整证据为空则信任当前stat”的分支；缺失/半缺失/不可信状态明确 `source_unverified`，来源不符为 `source_stale`，不在恢复时补成 verified。 |
| `final_cli.py` 的普通整理/重试/续跑，`automation_definition_execution.py` 的共用管线 | 接到同一来源与稳定性行为；不能只修手动执行 fixture，漏掉真实新建 CLI/Worker/仍支持的 Automation 消费者。 |
| `scanner.py` / `library_pipeline.py` 与现有 discovery/观察仓储 | 串起同一显式工作内的首观察→持久等待→到期重观察→就绪。`previous` 参数必须由真实工作证据提供，不能只增加可选参数却没有生产调用方。 |

1. **先明确 fingerprint 的含义。** 复用 `domain/source_evidence.py` 的 `source_fingerprint`
   与 `occurrence_id_for`：库/Storage/精确路径、大小、mtime足够时可自动生成来源证据。
   Provider 自带的 fingerprint/ETag/version 等是可选增强；缺少它们不能拒绝普通 Local/远程
   文件，也不要求用户填写 fingerprint、不新增全影片 Hash/FFprobe。这里的身份只证明
   Storage 可观察证据一致，不宣称字节级相同；原已观察到的有效 validator 仍须参与比较。
2. **区分“首次选择”与“继续旧工作”。** 首次明确选择可从 live stat 建立原证据，在
   Provider 失败前也保存到该任务；恢复/重试只能验证已保存的原证据。不能在通用
   `begin_item` 或恢复 validator 中加“为空就补当前值”，否则替换来源仍会被接纳。
   核对 TaskItem→Result→恢复请求/Job→Worker→续作结果的字段逐段一致；配置始终用该工作
   原 pin。无法证明原来源时保留记录，提示从 Files/当前支持入口重新选择并准备新方案，
   不自动重新准入，不要求用户修数据库或手动提供指纹。
3. **稳定期只消费已配置的策略。** 缺 `stability` 或 stable-size=0 保持现有无需稳定间隔
   的行为，不新加默认等待或修改用户配置。配置非0时，首观察记录该工作的范围/来源和时间，
   显示或持久保留等待状态；到期实际再stat，未变才进入分析，变化重置间隔。复用已有
   `MediaDiscoveryService`/观察仓储、`ObservedSource`、`stability_decision`/
   `stability_wait_seconds`，不写另一套稳定算法或独立队列。若受支持的CLI需要转交现有
   Worker，返回真实持久工作身份与当前等待/下一步，不能将等待伪装为 completed/0。
   观察按工作、配置pin、库/Storage/root/路径隔离，同名跨库不共用；真实空目录/全部合法
   排除仍可正常0项结束。重开恢复已有合法观察，观察丢失重新开始区间，不用mtime回填。
4. **用真实入口验证，再交接。** 下表各行写入相应现有测试模块；优先扩展真实 CLI/Worker
   fixture，不用全部手工灌入原指纹的测试替代首处理。B目录中的复现脚本用于理解操作步骤，
   其旧结果是审查证据，不修改/覆盖；Developer在仓库tests内写目标断言，B自行更新独立复现。

| 输入/操作 | 必须观察到的结果 |
|---|---|
| fresh库，Storage无自带fingerprint/ETag，普通有效size/mtime，CLI整理遇Provider故障 | 原TaskItem/Result已有真实来源证据；该证据来自首次处理，不来自后续恢复。 |
| 上述失败项排队恢复后，同路径替换文件 | Worker拒绝旧工作；0 Provider请求、无误标完成/错误来源关联或媒体变更；原历史及原因保留。 |
| 原证据缺失、只有一半，或状态为unverified/legacy | 明确拒绝并提示重新选择/准备；不读取当前文件后自动补成原身份。 |
| 原证据完整且来源未变，期间发布新Active | 在合法原pin下完成分析；原身份、原结果和其他成功项不被改写或重放。 |
| stable-size默认0 | 不增加固定等待；有效来源继续现有完整分析。 |
| stable-size=1秒，来源未变 | 首观察后保持真实等待；超过1秒实际重观察后进入分析，不能两次CLI都 completed/0。 |
| stable-size=61秒，首次等待项后立即Retry/Continue，含 `--execute` | 原稳定区间未满足时继续观察/等待；0 Provider/零媒体mutation，不能仅凭指纹相同执行。 |
| 等待期间大小/mtime/有效validator变化，或同一工作重开 | 变化重新计时；合法持久观察可恢复，丢失证据重新观察；未满足前零执行权/媒体mutation。 |

Developer 本次先跑下列新增/修改和直接受影响组；其他实际改动按本 Task 原分配追加对应组
及 changed-file ruff 检查。不得把 B 全量/发布矩阵交给 Developer：

```bash
python3 scripts/check_governance.py
PYTHONPATH=tests .venv/bin/python -m unittest test_file_index_retirement test_recovery_continuation test_metadata_correction_continuation test_task_persistence
PYTHONPATH=tests .venv/bin/python -m unittest test_scanner test_resource_library_pipeline test_final_integration test_scan_retirement_stability test_organize_preparation
PYTHONPATH=tests .venv/bin/python -m unittest test_automation_definition_execution test_automation_authorized_execution_matrix test_task_center_recovery_lineage
PYTHONPATH=tests .venv/bin/python -m unittest test_task_retry test_scope_continuation test_processing_recovery_admission test_task_pause_resume
git diff --check
```

B 在修正固定 SHA 重做独立关键复现、审完原 Base..新 Head，并负责 Required Tests 原清单中
全部 T4/真实入口/wheel/安装消费者/Docker/视觉门禁。匹配 B 证据可复用；执行输入改变刷新
分配验收。尚未运行的全量均 pending，不以环境/证据缺口要求 Developer 改产品。
Developer 原报告的 direct-files Base/flaky 归因仍未由 B 独立确认，不作为豁免。

本轮本机 ignored evidence：
`.git/validation-evidence/a3fbb36c7f86ed08629e08247a08e5f154d4adbb/task45.5/b-review/`。
四脚本及JSON：`fresh-task-evidence.json`、`cli-short-stability.json` 为已修正反例；
`long-stability-retry.json` 是61秒策略在0.083秒内通过立即重试实际MOVE（临时fixture媒体）；
`untrusted-worker-evidence.json` 两种状态均被Worker分析 completed、1次Provider、续作verified。
`focused-tests.log` 为6 tests OK/无skip；全部B执行的测试命令耗时少于15秒，复核超过3分钟，
低于用户50%上限。真实MOVE只发生于隔离临时根，未触碰用户媒体/数据库。

按已证实阻塞提前停止昂贵门禁。Required Tests 的全部B T4/真实入口/wheel/安装消费者/
Docker/视觉门禁仍pending B，修正固定SHA再执行；匹配证据按workflow复用，不机械重跑Final。
Developer的全量报告与未核实的direct-files Base/flaky归因不作为B验收或豁免。
45.4历史PASS/验证例外保持；未规划新Task，未改Slice/Roadmap/Progress，RO-8仍待实现。
本轮preflight：main@b0f070b1801754d2d53ab9f992374fbc3e7ea3f9，治理PASS，workspace/Git可写。
预存图片删除、未跟踪截图/.DS_Store/ZIP/浏览器结果/开发log全部保留，不纳入checkpoint；
未读取或修改私有ignored配置、用户运行库或媒体。此前详细复核保留在Git及原证据目录。

## Developer Fix Round Report (B-1 / B-2 / B-3)

READY FOR B REVIEW at implementation HEAD `906def76fc596acf4208767ed2dcdee7d2076f06`
(Task Base `3e2cb31aca211a7dcb7fa7c4ba4883d55b951974`; previous reviewed candidate
`72682d1e3277343b674d62e5ceda99a824036c00`). Same Task, Base / Goal / T4 unchanged.

### 行为与关键决策

- **B-1 精确 Active。** 提取纯完整性规则到 `domain/configuration_integrity.py`
  (`MANAGED_CONFIGURATION_DOCUMENT_SCHEMA_VERSION` / `canonical_document_digest`)；
  `application/configuration_snapshot.py` 复用同一常量与函数（行为不变）。
  `infrastructure/read_only_active_configuration.py` 在构造 Storage 前调用
  `_verified_revision`，对文档 schema 与 canonical payload digest 执行与 managed runtime
  同义校验；损坏/不支持返回有界 `digest_corrupt` / `schema_unsupported` 原因、未变更状态及
  Settings/恢复指引，仍为 `mode=ro`，不创建/升级/写入仓库。
- **B-2 恢复来源。** `ManualSourceValidator.validate_persisted_source` 复用同一 live
  pinned-Storage 边界，按原 pin 重读原 TaskItem 的 Storage/library/path，对比精确
  occurrence/fingerprint；缺失/替换/不可验证分别以 `source_missing` / `source_stale` /
  `source_unverified` 拒绝并给出重新选择/准备路径。`RecoveryContinuationWorkerService` 与
  `MetadataCorrectionContinuationWorkerService` 在消费旧决定/Provider 前调用它，并把
  **live 已验证** occurrence/fingerprint 写入新 TaskItem/Result，而非复制旧标签。
  `final_cli` 通过 `_SharedResolvedStorages` 让校验与 pipeline 共用一次 Storage 装配
  （linkage 失败仍先于任何 adapter 构造）；`ManualIntentError` 分支把拒绝原因写入 continuation
  的 error/recovery，不形成成功续作。旧 Active pin 在新发布后仍合法（校验绑定 Job 的 pin，
  不重绑当前 Active）。
- **B-3 测试方法。** `test_worker_continuation_preflight_rejects_stale_occurrence_before_pipeline`
  改为真实 Worker + 本地 LocalStorage + 计数 fake Provider：排队后替换来源被拒绝、零 Provider
  请求、零媒体变更、continuation failed。新增缺失来源反例与“未变来源完成分析 + 旧 pin 合法”
  正例；`test_file_index_retirement` 增加 payload 篡改与不支持 schema 两个真实 CLI 反例；
  `test_metadata_correction_continuation` 增加 live Storage 替换来源反例。

### 实际受影响命令/结果

- `python3 scripts/check_governance.py` → PASS。
- `PYTHONPATH=tests .venv/bin/python -m unittest test_file_index_retirement test_runtime_files_browser test_media_library_browser` → 23 tests OK（含 2 个新增 Active 反例）。
- `... test_recovery_continuation test_metadata_correction_continuation test_manual_organize_intent test_task_center_recovery_lineage` → 72 tests OK。
- `... test_scanner test_resource_library_pipeline test_media_discovery test_scan_retirement_stability test_organize_preparation` → 154 tests OK。
- `... test_manual_organize_intent test_manual_organize_preview test_manual_organize_execution test_v2_manual_organize test_recovery_continuation test_task_center_recovery_lineage` → 154 tests OK。
- 条件消费者组（task_persistence/sqlite_backup/sqlite_restore、direct_file_operations/
  manual_operations_contract/operations_task_center、automation_task_definition_preview/
  automation_definition_execution/automation_authorized_execution_matrix/configuration_organize、
  metadata_correction_continuation/recovery_batch）全部 OK。
- 相关配置/Automation 组：`test_configuration_snapshot/management/status/successor_draft/package_exchange/objects` → 157 OK；
  `test_automation_task_definition_preview/definition_execution/definition_occurrence/preview_grant_gate/v2_automation_lifecycle` → 100 OK。
- `.venv/bin/ruff check mediaflow/ tests/` → All checks passed；`ruff format --check` → 322 files already formatted；
  `python -m compileall -q mediaflow tests scripts` → OK；`git diff --check` 干净。
- Web（cwd `web/`）：`npm run typecheck` → 干净。

### B 独立复现对照（同一 ignored 脚本）

- `reproduce_active_integrity.py`：两反例现均 `cli_explicit_integrity_rejection=true`、
  不读被改写/未发布 root、数据库字节不变；合法 Active 仍正常列举发布 root。
- `reproduce_replaced_recovery.py`：替换来源后 `worker_exit=1`、Provider 请求 0、
  `continuation_status=failed`、无新 TaskItem/Result、媒体 mutation 0。

### 已知失败/风险

- B 上轮披露的 `tests/e2e/direct-files.python.spec.ts` 既有 flaky 未在本轮处理（非本 Task 引入，
  仍由 B 独立确认）。
- wheel/隔离安装、生产 Docker、真实 SMB/OpenList/S3/TMDB 与 1536×1024/380×720 截图等
  T4 门禁仍 pending B；Developer 不跑全量/发布矩阵。
- 未变来源仍会构造一次 Storage（校验需要），但只在 linkage 通过后发生；linkage/eligibility
  失败仍是零构造。

预存修改保留且不纳入 Task checkpoint：删除 `docs/pics/操作与任务.png`；未跟踪
`docs/pics/自动化页-全局设置.png`、`docs/pics/自动化页.png`、各处 `.DS_Store`、
`output/imagegen/slice45-task-center-v1.zip`、`web/test-results-batch-check/`、
`web/test-results-real-python-final/` 及开发 `.log` 文件。私有ignored配置不读取、不暂存。

## Developer Fix Round Report (B-2 evidence chain / CLI stability)

READY FOR B REVIEW at implementation HEAD `a3fbb36c7f86ed08629e08247a08e5f154d4adbb`
(Task Base `3e2cb31aca211a7dcb7fa7c4ba4883d55b951974`; previous reviewed candidate
`906def76fc596acf4208767ed2dcdee7d2076f06`). Same Task, Base / Goal / T4 unchanged.

### 行为与关键决策

- **B-2 从首次处理到恢复保持精确来源。** `MediaOrganizerService.process_file` 在首次明确选择、
  任何 Provider 调用前，用一次 live Storage `stat` 生成 occurrence/fingerprint/state 并写入
  `begin_item`；`process_library`/`process_all_libraries` 把 discovery 已观察到的 `DiscoveredFile`
  证据透传到处理边界（不再只传 `file.path`）。恢复/重试（`resolve_source_evidence=False`）只
  验证已保存证据：`_persisted_source_refusal` 在 Provider 前拒绝缺失/半缺失/legacy/unverified
  或不符来源，绝不把当前 stat 补成原身份。`final_cli` 的普通重试/续跑、metadata-correction 与
  recovery continuation 均改为只消费原证据。
- **验证器 fail-closed。** `ManualSourceValidator.validate_persisted_source` 去掉“空证据信任
  当前 stat”分支：缺失/半缺失/legacy/unverified 明确 `source_unverified`，来源不符
  `source_stale`，均给出重新选择/准备路径，不在恢复时补成 verified。
- **CLI 真实稳定观察闭环。** `process_library`/`process_all_libraries` 与直接单文件选择在
  `stableSizeDurationSeconds` 非0时，先记录本工作自己的真实观察时间，等待剩余真实区间后
  重新 `stat` 同一范围；未变才进入完整分析。稳定观察按工作/库隔离（`(library_id, path)`），
  变化重置区间，重开恢复合法观察；超过 `_MAX_STABILITY_WAIT_SECONDS`（60s）的长区间不阻塞
  同步命令，记录为带重试下一步的等待项。复用 `scan_filters` 的
  `stability_decision`/`stability_wait_seconds`，不新建稳定算法或全局缓存。
- **fixture 反映生产。** `tests/test_recovery_continuation._seed_failed_item` 现在按真实首处理
  记录来源证据；缺证据的 legacy 反例由直接 SQL 构造，`test_recovery_batch` 的 sibling 在准入
  前先落盘。

### 实际受影响命令/结果

- `python3 scripts/check_governance.py` → PASS；`git diff --check` 干净。
- `PYTHONPATH=tests .venv/bin/python -m unittest test_file_index_retirement test_recovery_continuation test_metadata_correction_continuation test_task_persistence` → 95 tests OK。
- `... test_scanner test_resource_library_pipeline test_final_integration test_scan_retirement_stability test_organize_preparation` → 47 tests OK。
- `... test_automation_definition_execution test_automation_authorized_execution_matrix test_task_center_recovery_lineage` → 38 tests OK。
- `... test_manual_organize_intent test_manual_organize_preview test_manual_organize_execution test_v2_manual_organize test_recovery_continuation test_task_center_recovery_lineage` → 160 tests OK。
- 条件消费者组（task_persistence/sqlite_backup/sqlite_restore、direct_file_operations/
  manual_operations_contract/operations_task_center、automation_task_definition_preview/
  automation_definition_execution/automation_authorized_execution_matrix/configuration_organize、
  metadata_correction_continuation/recovery_batch）全部 OK。
- 追加直接受影响组：`test_classification_review`/`test_file_media_detail`/`test_metadata_correction`/
  `test_metadata_review`/`test_recognition_review`/`test_workflow_retry` → 45 OK；
  `test_operations_run_detail_log_isolation`/`test_resource_library_activation`/
  `test_media_library_activation` → 49 OK；`test_scan_retirement`/`test_task_retry`/
  `test_scope_continuation`/`test_processing_recovery_admission`/`test_restart_fault_boundary`/
  `test_task_pause_resume`/`test_queued_job_execution_boundary` → 104 OK；
  `test_operations_task_center`/`test_operations_run_inventory`/`test_operations_run_detail`/
  `test_operations_run_detail_plan_evidence`/`test_operations_workspace` → 129 OK。
- 新增 `test_recovery_continuation.FreshCliSourceEvidenceAndStabilityTests`（6 cases）覆盖：
  fresh CLI 失败项已有 verified occurrence/fingerprint 且写入 Result；替换来源恢复在 Provider 前
  拒绝、零 Provider/零 mutation；空/半缺失/legacy/unverified 证据拒绝；stable-size=1s 真实等待
  后分析未变来源；默认0不等待；等待期间来源变化重置且不分析。
- `.venv/bin/ruff check`/`ruff format --check` 改动文件全部通过；`python -m compileall -q mediaflow tests scripts` OK。
- Web（cwd `web/`）：`npm run typecheck` 干净；`npm run test -- run` 指定 4 文件 → 93 passed；
  `npm run build` 成功。

### B 独立复现对照（同一 ignored 脚本，行为已翻转）

- `reproduce_fresh_task_missing_evidence.py`：现 `initial_occurrence`/`initial_fingerprint` 非空、
  `initial_fingerprint_state=verified`；替换来源后 `worker_exit=1`、Provider 请求 0、
  `continuation_status=failed`、无新 TaskItem/Result、`target_entries=0`。脚本末尾
  `assert original.source_fingerprint is None` 正是旧缺陷断言，现已不再成立。
- `reproduce_cli_stability.py`：现真实等待约1.1s 后两次 CLI 均进入完整分析（`provider_search_requests=2`），
  旧断言 `len(tasks)==2 and not items` 已不再成立。

### 已知失败/风险

- B 上轮披露的 `tests/e2e/direct-files.python.spec.ts` 既有 flaky 未在本轮处理（非本 Task 引入，
  仍由 B 独立确认）。
- wheel/隔离安装、生产 Docker、真实 SMB/OpenList/S3/TMDB 与 1536×1024/380×720 截图等
  T4 门禁仍 pending B；Developer 不跑全量/发布矩阵。
- 稳定等待上限 `_MAX_STABILITY_WAIT_SECONDS=60s`：更长的配置区间不阻塞同步 CLI，而是记录等待项
  与重试下一步；B 可在真实入口确认该交互。

预存修改保留且不纳入 Task checkpoint：删除 `docs/pics/操作与任务.png`；未跟踪
`docs/pics/自动化页-全局设置.png`、`docs/pics/自动化页.png`、各处 `.DS_Store`、
`output/imagegen/slice45-task-center-v1.zip`、`web/test-results-batch-check/`、
`web/test-results-real-python-final/` 及开发 `.log` 文件。私有ignored配置不读取、不暂存。

## Developer Fix Round Report (B stability bypass / untrusted Worker evidence)

READY FOR B REVIEW at implementation HEAD `52e13ce2c316aafa0bd1c2b424587572cee41d06`
(Task Base `3e2cb31aca211a7dcb7fa7c4ba4883d55b951974`; previous reviewed candidate
`a3fbb36c7f86ed08629e08247a08e5f154d4adbb`). Same Task, Base / Goal / T4 unchanged.

### 行为与关键决策

- **P1 稳定观察约束重试与执行。** `PersistentTaskItem`/`PersistentResultRecord` 新增
  `source_observed_at`（runtime schema 48，additive 列，fresh 创建、旧库原地升级不回填）。
  `MediaOrganizerService.process_file` 首次选择记录该工作自己的真实首观察时刻；retry/resume/
  recovery/Worker/Automation 调用在 Provider/执行前用同一 `stability_decision` 策略、按工作原
  pin 与 live `stat` 重新判定。`resolve_source_evidence=False` 只允许继续观察/等待，不再把
  “指纹相同”当作“区间已满足”。稳定证据缺失时从当前时刻重新计时。
- **P2 持久等待闭环。** 观察起点/来源证据落在该显式工作的 TaskItem/Result（`source_observed_at`），
  重开/新进程可读；合法证据继续、丢失证据重新观察。到期后真实重观察，来源变化重置区间。
  长区间（>60s）不阻塞同步命令，记录为等待项并由 retry 继续观察；0 秒不新增等待、真实空目录
  仍 0 项结束。未建第二队列/全局目录。
- **B-2/P1 Worker 校验原证据可信状态。** `PersistedSourceEvidence.has_exact_evidence` 现在同时
  要求 `fingerprint_state == verified`。`ManualSourceValidator.validate_persisted_source` 与
  `_persisted_source_refusal` 对缺失/半缺失/unverified/legacy 一律 `source_unverified` 拒绝，
  保留记录并指向重新选择/准备；不再根据当前 stat 升级不可信原记录。真实 Worker 续作与直接
  CLI 重试采用同义检查。
- **fixture 反映生产。** 稳定性反例用 61 秒配置的立即重试快速验证“未到期零 Provider/零
  mutation”，不必真等；到期允许与重开用受控持久观察（改 `source_observed_at`，非 mtime）
  验证。可信状态反例保留真实且匹配的 occurrence/fingerprint，只把状态改为 unverified/legacy，
  再驱动真实 `worker run-next`。

### 实际受影响命令/结果

- `python3 scripts/check_governance.py` → PASS；`git diff --check` 干净；
  `python -m compileall -q mediaflow tests scripts` → OK。
- `PYTHONPATH=tests .venv/bin/python -m unittest test_file_index_retirement test_recovery_continuation test_metadata_correction_continuation test_task_persistence` → 98 tests OK。
- `... test_scanner test_resource_library_pipeline test_final_integration test_scan_retirement_stability test_organize_preparation` → 47 tests OK。
- `... test_automation_definition_execution test_automation_authorized_execution_matrix test_task_center_recovery_lineage` → 38 tests OK。
- `... test_task_retry test_scope_continuation test_processing_recovery_admission test_task_pause_resume` → 85 tests OK。
- `... test_manual_organize_intent test_manual_organize_preview test_manual_organize_execution test_v2_manual_organize test_recovery_continuation test_task_center_recovery_lineage` → 108 tests OK。
- 条件消费者组（task_persistence/sqlite_backup/sqlite_restore、direct_file_operations/
  manual_operations_contract/operations_task_center、automation_task_definition_preview/
  automation_definition_execution/automation_authorized_execution_matrix/configuration_organize、
  metadata_correction_continuation/recovery_batch）全部 OK。
- 追加直接受影响组：`test_classification_review`/`test_file_media_detail`/`test_metadata_correction`/
  `test_metadata_review`/`test_recognition_review`/`test_workflow_retry` → 45 OK；
  `test_operations_run_detail_log_isolation`/`test_resource_library_activation`/
  `test_media_library_activation`/`test_scan_retirement` → 58 OK；
  `test_restart_fault_boundary`/`test_queued_job_execution_boundary`/`test_operations_run_detail`/
  `test_operations_workspace`/`test_operations_run_inventory` → 105 OK；
  `test_operator_observability`/`test_processing_checkpoint`/`test_direct_file_transfers` → 126 OK；
  `test_media_discovery`/`test_scan_retirement_stability`/`test_automation_task_definition_preview` → 133 OK；
  `test_processing_worker_readiness`/`test_configuration_status`/`test_api_security` → 39 OK；
  `test_sqlite_backup`/`test_sqlite_restore`/`test_migration_rehearsal`/`test_upgrade_preflight` → 18 OK。
- 新增 `FreshCliSourceEvidenceAndStabilityTests`（9 cases）覆盖：fresh CLI 失败项已有 verified
  occurrence/fingerprint；替换来源恢复在 Provider 前拒绝；空/半缺失/legacy/unverified 拒绝；
  61 秒配置立即重试仍等待（0 Provider/零 mutation，含 `--execute`）；记录的区间真正到期后
  dry-run 继续分析；1 秒真实等待；默认 0 不等待；变化重置；真实 Worker 对 unverified/legacy
  原证据拒绝（0 Provider/零 mutation、无新项/结果）。
- `.venv/bin/ruff check mediaflow/ tests/` → All checks passed；
  `.venv/bin/ruff format --check mediaflow/ tests/` → 322 files already formatted。
- Web（cwd `web/`）：`npm run typecheck` 干净；`npm run test -- run` 指定 4 文件 → 93 passed。

### B 独立复现对照（同一 ignored 脚本，行为已翻转）

- `reproduce_long_stability_retry.py`：61 秒配置下首次 `organize --execute` 仍
  failed/unstable_source（0 Provider/0 目标）；立即 `tasks retry-failed --execute` 现为
  exit1、0 Provider、来源仍在、0 目标文件（旧结果 exit0/completed/success/实际 MOVE 已不再成立）。
- `reproduce_untrusted_worker_evidence.py`：unverified/legacy 两种状态现均 `worker_exit=1`、
  Provider 0、continuation failed、无新项/结果（旧结果 exit0/completed/verified 已不再成立）。
- `verify_fresh_task_evidence.py` / `verify_cli_short_stability.py` 保持通过（fresh 证据链与
  1 秒真实等待进入分析）。

### 已知失败/风险

- 仍待 B 独立确认 `tests/e2e/direct-files.python.spec.ts` 的既有 flaky（非本 Task 引入）。
- 稳定等待上限 `_MAX_STABILITY_WAIT_SECONDS=60s`：更长的配置区间不阻塞同步 CLI，而是记录
  等待项与 retry 下一步；B 可在真实入口确认该交互。
- wheel/隔离安装、生产 Docker、真实 SMB/OpenList/S3/TMDB 与 1536×1024/380×720 截图等
  T4 门禁仍 pending B；Developer 不跑全量/发布矩阵。
- RO-8 独立 Preview 完整退出未交付；本 Task 只清理其必要索引耦合。

预存修改保留且不纳入 Task checkpoint：删除 `docs/pics/操作与任务.png`；未跟踪
`docs/pics/自动化页-全局设置.png`、`docs/pics/自动化页.png`、各处 `.DS_Store`、
`output/imagegen/slice45-task-center-v1.zip`、`web/test-results-batch-check/`、
`web/test-results-real-python-final/` 及开发 `.log` 文件。私有ignored配置不读取、不暂存。
