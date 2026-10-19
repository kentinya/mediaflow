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
Next Action: DEVELOPER FIXES WORK-SCOPED STABILITY FOR SUPPORTED REMAINING-SCOPE RECOVERY; B RETAINS FULL ACCEPTANCE
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

READY FOR B REVIEW at implementation HEAD `<FILLED AFTER COMMIT>`
(Task Base `3e2cb31aca211a7dcb7fa7c4ba4883d55b951974`; previous reviewed candidate
`8732c2588cda76646a72dfbea60bd72abc93e935`). Same Task, Base / Goal / T4 unchanged.

### 本轮（B 第三次 FIX REQUIRED）修正：剩余范围恢复改为持久工作内观察

**复现（先于修复）。** 直接运行 B 的 `reproduce_remaining_stability.py`（supported organize
Task，stable-size 0 对照 / 1s 反例，真实等待后第二次请求）：旧实现两次均 409 `source_not_ready`，
`media_discovery_observations=0`，任意次数等待/刷新都无法跨越非零稳定期。

**根因。** 内联的 `ManualOrganizePreviewService.create_remaining_scope_from_task` →
`_source_identity_from_storage` 每次调用都以 `unchanged_previous=False, observed_since=None`
做 `stability_decision`，拒绝即退出且不保存本次观察，因此非零 stable-size 区间永远无法被证明。

**修复（复用既有有界发现/Worker，不新建引擎）。**

1. 原生 `POST /api/v1/tasks/{id}/remaining-scope-previews` 改为通过既有
   `MediaDiscoveryService.admit_recovery_preparation` 持久准入一次 remaining-scope recovery
   preparation：解析原 Task 身份→原发布 pin→`remaining_scope()`→原库/root 精确剩余范围；
   每个 chain 已记录来源作为持久排除项；admitted primary bound = 原剩余预算。响应 202 + discovery
   文档，不再内联生成 Preview。
2. 观察/冻结/分析完全交给既有 `MediaDiscoveryWorker`：首次观察持久化，设置真实
   `next_observation_at`，非零区间由真实二次 `stat` 证明；size/mtime/validator 变化重置区间；
   重开继续同一记录。冻结后经既有 `_analyze` 运行完整分析链并链接精确 Preview。
3. 排除项在 walk 中真正跳过（不 observe/list/计数），已记录 sibling 不会被重新提供，也不会
   挤占剩余来源或触发 primary bound。
4. 空剩余范围在准入期以有界只读探针给出真实 `no_remaining_scope` 409，而不是准入一个必然
   无发现的 preparation。
5. `MediaDiscovery` 增加 `recovery_source_task_id` / `recovery_excluded_paths`（runtime schema
   49，additive migration，fresh 无新增产品表）；`find_open_recovery_discovery` 保证重复/丢响应
   收敛同一准备；`_analyze` 把 `recovery_source_task_id` 链接到 Preview，运行概览的 durable
   recovery link 与旧内联路径一致。
6. 删除已死的内联 `create_remaining_scope_from_task` / `_scope_library` /
   `_remaining_scope_sources`（约 250 行），共享 scope 解析抽到纯 `application/task_scope.py`，
   不保留第二套恢复引擎。
7. Web `submitRemainingScopePreview` 改为返回 discovery 投影；`OperationsLanding` 在当前面板
   轮询同一 discovery（不重复 POST），链接 Preview 后进入既有同页摘要→精确子集确认。

**边界不变。** 原 pin/剩余范围/预算/权限不放宽；准备阶段零 Provider（等待）/零媒体 mutation/
零执行权；成功/忽略/未知效果 sibling 不重新纳入；丢证据重新观察，不用旧 mtime/单次 stat 伪造稳定。

### 实际受影响命令/结果（本轮）

- 新增 `.git/validation-evidence/task45.5-developer-fix/verify_remaining_scope_recovery.py`：
  stable-size=0 → 首遍 analyzing，随后 completed 并链接 `Incoming/Left.2005.mkv`；stable-size=1 →
  首遍 `waiting_stability`、立即重读 `None`（不可领取）、真实等待 1.1s 后 completed 且链接同一来源；
  两例 Provider 1 次（仅分析阶段）、kept/left 内容不变、target 0、recoverySourceTaskId 一致。
- `test_scope_continuation` 新增 `test_remaining_scope_recovery_proves_a_nonzero_stability_interval`
  （真实 elapsed，非手改时间戳）；三个既有恢复用例改为驱动持久 Worker 契约（202 + discovery）。
- `test_scope_continuation test_media_discovery test_media_discovery_provider_manifest test_scan_retirement_stability test_organize_preparation` → 187 OK。
- `test_manual_organize_intent test_manual_organize_preview test_recovery_continuation test_task_center_recovery_lineage` → 93 OK。
- `test_scanner test_resource_library_pipeline test_media_discovery test_scan_retirement_stability test_organize_preparation test_manual_organize_intent test_manual_organize_preview test_manual_organize_execution test_v2_manual_organize test_recovery_continuation test_task_center_recovery_lineage` → 329 OK。
- `test_task_persistence test_sqlite_backup test_sqlite_restore test_processing_checkpoint test_direct_file_operations test_manual_operations_contract test_operations_task_center test_automation_task_definition_preview test_automation_definition_execution test_automation_authorized_execution_matrix test_configuration_organize test_metadata_correction_continuation test_recovery_batch` → 271 OK。
- `test_file_index_retirement test_runtime_files_browser test_media_library_browser test_storage_browser` → 40 OK。
- `test_organizer test_conflict_resolution test_organizer_rollback test_organizer_mutation_authority` → 59 OK；
  `test_recognition test_policy_mapping`（C→A 身份回归）→ 17 OK。
- `python3 scripts/check_governance.py` → PASS；`git diff --check` 干净；
  `.venv/bin/python -m compileall -q mediaflow tests scripts` → OK。
- `.venv/bin/ruff check` / `ruff format --check` 覆盖全部新增/修改 Python 文件 → passed / formatted。
- Web：`npm run typecheck` 通过；`npm run test -- run organize.test.ts OrganizeRouter.test.tsx StorageFilesPage.test.tsx MediaLibraryFilesPage.test.tsx OperationsInventory.test.tsx operations-api.test.ts RunLifecycleControls.test.tsx` → 160 passed；`npm run build` 通过。
- E2E（production build）：`npx playwright test --config=playwright.python.config.ts tests/e2e/live-files.python.spec.ts` → 5 passed；`tests/e2e/operations-inventory.python.spec.ts` → 38 passed；`tests/e2e/operations-task-center-visual.python.spec.ts` → 2 passed。
- 本轮测试实际耗时保守合计约 300s，占本轮开发时间不足 30%；未跑全量/unicode-principal/wheel/Docker/release matrix。

### 已知失败/风险

- `tests/e2e/direct-files.python.spec.ts` 既有 flaky 仍待 B 独立确认（非本 Task 引入）。
- runtime schema 由 48→49（additive）；相应断言已更新为 49。B 需在真实 wheel/Docker 上确认
  fresh/reopen 与支持版本迁移；Developer 未跑 Docker/release matrix。
- 长区间（>60s）等待仍走既有 discovery `next_observation_at` + Worker 重 claim；本轮真实验证了
  1s 区间，更长的真实区间与恢复仍待 B 在真实 Worker 路径确认。
- wheel/隔离安装、生产 Docker、真实 SMB/OpenList/S3/TMDB 与 1536×1024/380×720 截图等 T4 门禁仍 pending B。
- RO-8 独立 Preview 完整退出未交付；本 Task 只清理其必要索引耦合。

预存修改保留且不纳入 Task checkpoint：删除 `docs/pics/操作与任务.png`；未跟踪
`docs/pics/自动化页-全局设置.png`、`docs/pics/自动化页.png`、各处 `.DS_Store`、
`output/imagegen/slice45-task-center-v1.zip`、`web/test-results-*` 及开发 `.log` 文件。
私有 ignored 配置不读取、不暂存。

### 前一轮报告（历史）

READY FOR B REVIEW at implementation HEAD `8732c2588cda76646a72dfbea60bd72abc93e935`
(Task Base `3e2cb31aca211a7dcb7fa7c4ba4883d55b951974`; previous reviewed candidate
`204441f70c0678e9b6526a54f6af8aac75b126f4`). Same Task, Base / Goal / T4 unchanged.

### 前一轮（B 第二次 FIX REQUIRED）修正：安全拒绝必须持久为真实失败

**复现（先于修复）。** 直接运行 B 的 `reproduce_refusal_completion.py`（replaced / missing /
unverified 三例）与 `reproduce_discovery_refusal.py`：拒绝本身正确（exit1、Provider0、零媒体变更、
原指纹保留），但重开数据库后 Task 均为 `completed / total_items=0 / failed_items=0`，
无 TaskItem / Result，`tasks show` 只显示 `Total: 0`。脚本断言旧缺陷（exit0 表示复现成功）。

**根因。** `process_file` 的 `resolve_source_evidence=False` 分支在 `begin_item` 之前命中
`_persisted_source_refusal` 并以 `_failed(..., tracked_item=None, stage="storage")` 返回；
`_complete` 因没有 tracked item 不发布任何 TaskItem/Result，`PersistentTaskCoordinator.finish`
读取空持久 items 且无 scan_errors，于是把该次尝试汇总成 Completed/0。首次目录整理在发现与处理
之间的来源竞态走同一 `except Exception` → `_failed(tracked_item=None)` 路径，同样假成功。

**修复（复用既有持久完成路径，不新增结果库）。**

1. `_persisted_source_refusal` 返回 `FailureExplanation` 而非裸字符串，按真实原因区分
   `source_changed` / `source_missing` / `source_unverified` / `storage_failure`（含
   `StorageErrorCode.NOT_FOUND` 与连接类错误），不再把来源缺失/连接故障混为泛化 storage。
2. 新增 `_refused_source_item`：以原 occurrence/fingerprint/verified state/`source_observed_at`
   调用既有 `begin_item`，再走既有 `_failed`/`_complete`/`complete_item` 发布该次尝试的逐文件
   TaskItem + Result；不重建旧可信证据、不覆盖成功兄弟、不授予分析/执行权、零 Provider、零 mutation。
3. `process_file` 的通用 `except Exception`：当 `tracked_item is None` 且不是
   `TaskLockError/TaskPauseRequested/TaskClaimLost`（这些已在 `begin_item` 内发布自身拒绝）时，
   同样经 `_refused_source_item` 发布，堵住首次目录整理的竞态假成功。
4. `_failed` 对已分类的 `FailureExplanation` 一律持久化其 envelope（CLI 路径也如此），
   `_failure_message` 兼容 `FailureExplanation`。
5. `ErrorCategory` 增加 `source_changed` / `source_missing` / `source_unverified`；
   `failure_explanation` 增加同类别 message/next action 与文本归类；`classify_failure` 直传
   已构造的 `FailureExplanation`。
6. `tasks show` 用 `decode_failure_explanation` 渲染 category/message/next action，不再打印原始
   `mediaflow-failure-v1:` token。
7. Web `ProblemFilePanel` 增加三个类别的中文原因/下一步；不改动任何既有 category 文案。

**汇总语义。** 拒绝项现在进入 `failed` counts，Task 汇总为 FAILED；真正的空目录/合法零项仍为
Completed/0（未改 `finish` 聚合逻辑，也不伪造 scan error）。

### 实际受影响命令/结果（本轮）

- 修复前：B 两个复现脚本分别命中旧断言（Task completed/0、无 item/result）。修复后：
  `reproduce_refusal_completion.py` 三例均 `failed / total 1 / failed 1 / items 1 / results 1 / provider 0 / target 0 / fp_unchanged`；
  `reproduce_discovery_refusal.py` 为 `failed / 1 / 1 / items 1 / results 1 / source_changed / provider 0 / target 0 / 源内容保留`。
- 新增 `tests/test_recovery_continuation.RefusedSourceCompletionTests`（5 cases）：replaced→
  `source_changed`、missing→`source_missing`、unverified→`source_unverified`、Storage 连接故障→
  `storage_failure`（retry-safe，区别于来源变化）、首次目录竞态→`source_changed`；每例断言重开
  数据库后 status/counts/error、TaskItem、Result、effect_certainty、原证据保留、`tasks show`
  解码与零 Provider/零 mutation。
- `test_recovery_continuation test_task_persistence test_scope_continuation test_final_integration test_workflow_retry test_resource_library_pipeline` → 160 OK。
- `test_file_index_retirement test_runtime_files_browser test_media_library_browser test_storage_browser` → 40 OK。
- `test_scanner test_resource_library_pipeline test_media_discovery test_scan_retirement_stability test_organize_preparation test_manual_organize_intent test_manual_organize_preview test_manual_organize_execution test_v2_manual_organize test_recovery_continuation test_task_center_recovery_lineage` → 369 OK。
- `test_task_persistence test_sqlite_backup test_sqlite_restore test_processing_checkpoint test_operations_run_detail test_operations_task_center test_direct_file_operations test_manual_operations_contract test_automation_task_definition_preview test_automation_definition_execution test_automation_authorized_execution_matrix test_configuration_organize test_metadata_correction_continuation test_recovery_batch` → 305 OK。
- `test_automation_definition_execution test_automation_authorized_execution_matrix` → 33 OK；
  `test_processing_checkpoint test_operations_run_detail test_operations_task_center test_task_center_recovery_lineage` → 74 OK；
  `test_direct_file_transfers test_operations_run_detail` → 134 OK；
  `test_organizer test_conflict_resolution test_organizer_rollback test_organizer_mutation_authority test_direct_file_operations test_media_library_direct_commands` → 147 OK；
  `test_processing_recovery_admission test_task_retry test_processing_worker_readiness test_scan_retirement test_scope_continuation test_configuration_snapshot` → 148 OK；
  `test_task_pause_resume test_scan_retirement test_sqlite_backup test_sqlite_restore` → 27 OK；
  `test_metadata_correction test_recognition_review test_classification_review test_metadata_review test_file_media_detail` → 36 OK。
- `python3 scripts/check_governance.py` → PASS；`git diff --check` 干净；
  `.venv/bin/python -m compileall -q mediaflow tests scripts` → OK。
- `.venv/bin/ruff check` / `ruff format --check` 覆盖
  `failure_explanation.py media_organizer.py domain/processing_checkpoint.py final_cli.py tests/test_recovery_continuation.py` → passed / formatted。
- Web：`npm run typecheck` 通过；`npm run test -- run OperationsInventory.test.tsx OperationsRouter.test.tsx run-detail.test.ts` → 82 passed；
  `npx prettier --check` / `npx eslint` 修改文件通过。
- 本轮测试实际耗时保守合计约 180s，占本轮开发时间不足 30%；未跑全量/Web build/E2E/wheel/Docker。

### 已知失败/风险

- `tests/e2e/direct-files.python.spec.ts` 既有 flaky 仍待 B 独立确认（非本 Task 引入）。
- 长区间等待上限 `_MAX_STABILITY_WAIT_SECONDS=60s` 的持久 waiting item + retry 交互已由单元测试覆盖，
  真实入口 61s 反例与恢复仍待 B 在真实浏览器/Worker 路径确认。
- wheel/隔离安装、生产 Docker、真实 SMB/OpenList/S3/TMDB 与 1536×1024/380×720 截图等
  T4 门禁仍 pending B；Developer 不跑全量/发布矩阵。
- RO-8 独立 Preview 完整退出未交付；本 Task 只清理其必要索引耦合。

预存修改保留且不纳入 Task checkpoint：删除 `docs/pics/操作与任务.png`；未跟踪
`docs/pics/自动化页-全局设置.png`、`docs/pics/自动化页.png`、各处 `.DS_Store`、
`output/imagegen/slice45-task-center-v1.zip`、`web/test-results-batch-check/`、
`web/test-results-real-python-final/` 及开发 `.log` 文件。私有ignored配置不读取、不暂存。

## B Review Result

```text
Reviewed candidate: 8732c2588cda76646a72dfbea60bd72abc93e935
Review range: 3e2cb31aca211a7dcb7fa7c4ba4883d55b951974..8732c2588cda76646a72dfbea60bd72abc93e935
Handoff: 03c4c2d08ffce5002ac3df0051bd2ca73f35ad86 (TASK.md only; execution inputs identical)
Decision: FIX REQUIRED — remaining-scope recovery cannot complete any nonzero stable-size interval
Previous durable-refusal blocker: independently fixed, four real CLI/SQLite cases
Slice outcomes/surfaces all satisfied: NO — RO-7 / RO-8 pending
Next: SAME TASK FIX LOOP; B FINISHES ORIGINAL BASE..CORRECTED HEAD REVIEW / ASSIGNED T4
```

本轮 main 固定上述候选；治理 PASS，Git/workspace 可写。预存图片删除、未跟踪截图/日志/
ZIP/浏览器结果及私有配置均保持。读毕 AGENTS/workflow/B experience、已提交 Contract/
Task/当前指针，核对适用需求、列表/整理/恢复完整旅程及 CURRENT/TARGET。无 A-owned
边界变化；继续原 Base..Head 的共享来源/持久化/控制/恢复及 API/Web 消费者审查。
发现确定 P1 后按 workflow §6 提前拒绝；未声称全部 diff 或完整 T4 已完成。

### 上轮修正已独立通过

替换、缺失、unverified 的真实 CLI 重试，及首次目录发现→处理间替换来源，四例均保持
Provider0 / 零媒体 mutation，重开后保存为 Failed / total1 / failed1，存在1 TaskItem /
1 Result，分别保留 source_changed / source_missing / source_unverified、下一步和原证据。
真实 tasks show 能显示失败原因。B 复用旧独立脚本的 fixture，但已更新断言为修正后结果；
没有把旧缺陷脚本 exit0 或 Developer 标签当作产品通过。

### 当前 P1：剩余范围摘要每次都丢弃稳定观察

独立 fixture 使用 **受支持的 organize Task**，不是要求保留独立 Preview 产品：
精确 Managed Active + SQLite + LocalStorage，原 Task 已暂停、一次性执行权限不可复用，
保留成功兄弟 Kept.2006.mkv，尚需处理 Left.2005.mkv；原 pin、库/目录和预算固定。
真实 API `POST /api/v1/tasks/{id}/remaining-scope-previews` 是当前原生“重新生成剩余范围
摘要”的消费者；临时文件旧mtime已超过一天，内容全程未变。

| 原pin策略 | 第一次请求 | 真实等待后的第二次请求 | 工作内观察 / 计划 |
|---|---|---|---|
| stable-size=0 | 201，真实生成精确计划摘要 | 无需第二次 | 1 intent / 1 plan；成功兄弟未选入 |
| stable-size=1秒 | 409 source_not_ready | 等1.129秒后仍409 source_not_ready | 0观察 / 0 intent / 0 plan，Provider0 |

错误仍让操作者“等待稳定区间、刷新并重新选择”。但再次读取总是首次观察，任意次数等待/
刷新都无法跨越非零稳定期。安全拒绝没有放宽，但受支持普通整理的剩余范围恢复已无法
完成，违反 RO-7 无索引稳定观察→摘要/恢复、RO-4 控制与重开及 Task 的完整失败恢复旅程。
这不是要恢复旧 Scan/FileIndex 或保留独立 Preview 的兼容产品。

### Developer 必需修正与执行顺序

1. **先复现真实剩余范围恢复。** 沿上述 organize Task 路径使用稳定期0成功对照和1秒反例。
   固定原 pin/预算/成功兄弟，核对第一次请求后究竟持久保存了什么；真实等待后第二次仍
   拒绝必须可复现。不要仅测试 CLI process_file，因为其真实等待已经修好，此处是另一个
   实际消费者。不要把 fixture command=preview 作为支持范围前提。
2. **修正工作内观察生命周期，复用现有能力。**
   `ManualOrganizePreviewService.create_remaining_scope_from_task` → `_remaining_scope_sources`
   → `_source_identity_from_storage` 当前每次调用
   `stability_decision(... unchanged_previous=False, observed_since=None)`，拒绝即退出，且未
   保存本次观察。继续使用 `scan_filters` 的同一稳定性规则；把首次观察、真实间隔、二次
   stat、变化重置及完成条件放进该显式恢复准备工作的既有持久上下文，重开能继续。
   优先消费同一 Task/工作已有的可信 observation；尚无观察时复用已有有界
   MediaDiscovery/Worker 的观察、next_observation_at、claim/lease/fence 和 finalize 能力，
   做必要内部适配，不另建扫描产品/索引、全局文件观察缓存或另一套稳定性/恢复引擎。
3. **原pin/剩余范围/权限不可放宽。** 重用 Discovery 时注意其普通 admit 默认取当前 Active，
   不能直接拿新 Active 重建旧任务的剩余方案；只从服务端核验的原 Task 身份解析原发布
   pin、库/Storage/root、精确剩余范围和原预算。必要内部历史pin适配必须默认保持普通新建
   请求的当前 Active 规则，不能允许浏览器提交任意pin/来源证据。
   同路径换文件、size/mtime/有效validator变化重置观察或明确要求重新准备；丢证据重新观察，
   不用旧mtime/单次stat/虚构时间当稳定证明。成功/忽略/未知效果兄弟绝不重新纳入；准备仍
   零 Provider（等待阶段）/零媒体 mutation/零执行权，完整摘要后保持精确子集确认。
4. **原生等待与可恢复操作要可完成。** 在当前任务处理上下文显示实际观察进度/等待原因，
   用户无需反复猜测刷新时间、管理内部token或先跑Scan。长区间走现有持久Worker，HTTP请求
   不长时间 sleep；刷新/读取不偷偷重新准入或调用 Provider。重复/丢响应收敛同一准备工作，
   pause/cancel/reopen 的已观察事实和安全边界保留；满足真实区间后能够生成可确认摘要。
   如仅修复错误文案仍永远拒绝，不满足本 Task。
5. **同源消费者与边界。** 盘点此 helper 当前支持的整理/恢复调用，修复同一根因影响的
   路径；独立 Preview 专用产品退出仍留 RO-8，不为它新建保留/兼容流程。本次要求保留的是
   organize 的共享准备/剩余范围恢复，不提前实施整个 RO-8。若确需改变父 Contract，报B→A，
   不自行取消必需恢复、改Base或降低稳定性。修正继续 Task45.5 / High / T4。

### Developer 本次受影响验证

```bash
python3 scripts/check_governance.py
PYTHONPATH=tests .venv/bin/python -m unittest test_scope_continuation test_media_discovery test_media_discovery_provider_manifest test_scan_retirement_stability test_organize_preparation
PYTHONPATH=tests .venv/bin/python -m unittest test_manual_organize_intent test_manual_organize_preview test_recovery_continuation test_task_center_recovery_lineage
# 实际改变持久化/任务控制时，追加对应直接消费者
PYTHONPATH=tests .venv/bin/python -m unittest test_task_persistence test_processing_checkpoint test_task_pause_resume
.venv/bin/ruff check <changed-python-files>
.venv/bin/ruff format --check <changed-python-files>
git diff --check
# cwd web/；有实际Web/契约变化才追加直接受影响测试及
npm run typecheck
npm run build
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts
```

新增真实 organize 剩余范围场景：非零区间到成功摘要、首次等待零Provider/媒体/许可、变化
重置、观察重开、成功/未知兄弟排除、旧合法pin在新Active发布后保持、重复/未知响应不重复
准入、真实剩余预算及取消。至少一个短区间真实 elapsed 到成功；可控时钟单测分开标识，
不能手改 observation timestamp 后声称真实等待已通过。普通 Files 浏览仍只读不记录观察。

Developer 只跑修改/失败与直接受影响组，提交固定候选即可。B 完成原 Base..Head 审查，
承担 Required Tests 中原分配的完整 T4 / Python / Web / E2E / 原生与视觉 / wheel / 安装
消费者 / Docker / 安全、持久化和独立关键复现。匹配输入/产物证据按 workflow 复用，不
机械重复 Final；本轮中断/未执行门禁不算 PASS，不交回 Developer 补全量证据。

### 本轮实际验证与证据

本机稳定 ignored storage（非远程CI）：
`.git/validation-evidence/8732c2588cda76646a72dfbea60bd72abc93e935/task45.5/b-review/`。

- `verify_refusal_completion.py` / `refusal-completion.json`、`verify_discovery_refusal.py` /
  `discovery-refusal.json`：上轮四例修正独立通过，核对持久状态、原因/下一步和实际 effects。
- `reproduce_remaining_stability.py` / `remaining-stability.json`：受支持 organize Task 的
  真实 API / SQLite / LocalStorage 正反例；0秒201，1秒真实等待后两次409，0工作观察。
  脚本 exit0 表示已证实缺陷和成功对照，非产品 PASS。
- 全 Python unittest discover 启动后发现确定 P1，核实子进程后 SIGINT 终止；
  外层149.39秒、exit130，原始输出/ResourceWarning/中断栈保留，无完整数或PASS声明。
- 治理与 git diff --check 通过。未启动 Web/E2E/wheel/Docker/视觉等完整门禁，继续 pending B；
  不用旧执行输入的历史结果冒充本候选通过。完整日志、命令和时间见同目录 README / timing。
- 验证命令保守累计上限160秒；本轮收尾低于总复核时间50%，不靠空等增加分母。

本轮仅 checkpoint Task 审查及执行指导，不含预存用户变化；Slice/Roadmap/Progress、45.4
历史接受/例外不变。RO-7未通过、RO-8未实现，不造新Task、不提交Closure Packet、不关闭。
