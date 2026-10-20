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
Next Action: DEVELOPER PRESERVES THE EXACT PAUSED SOURCE DIRECTORY; SAME TASK; B OWNS FULL GATES
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

READY FOR B REVIEW. Same Task, Base `3e2cb31aca211a7dcb7fa7c4ba4883d55b951974` / Goal / High /
T4 unchanged; implementation HEAD is this checkpoint's SHA (recorded in the B handoff). B's latest
finding was **FIX REQUIRED — recovery trims the admitted directory and reviews a different
sibling** (P1). This round fixes only that root cause, its shared resolver, the missing-scope
refusal and its tests; the previous per-source eligibility fix remains in place.

### 先复现（本轮修复前）

B 的精确时序：同一资源库有两个真实目录 `Folder `（末尾一个空格）与 `Folder`，前者只有
`Left.2005.mkv`，后者只有 `Right.2006.mkv`。真实 CLI `organize '<库>/Folder ' --limit 1` 创建 Task 后
由真实 pause API 暂停（exit75），持久 `scope_path` 逐字保留末尾空格且无任何已发现项。真实
`POST /remaining-scope-previews` 返回202 并完成分析，摘要却列出 `Incoming/Folder/Right.2006.mkv`
而非原范围 `Incoming/Folder /Left.2005.mkv`。

用 B 的独立探针在修复前复现：`reproduce-b-p1-before.log`（`offered_wrong_sibling=true`）。

### 根因与修正

`mediaflow/application/task_scope.py` 的共享 `resolve_resource_library_scope` 对持久 scope 调用
`.strip()`，并把纯空白字符串当成“未指定范围”，于是目录名末尾空格被删除，解析落到近似邻目录
`Folder`。修正只改共享解析，不在输出端补名字：

- 只有 `None` 或确切空串表示未指定范围（保留原“恰好一个 enabled ResourceLibrary”语义）。
- 真实路径逐字保留，不再 `.strip()`；`PurePath` 分量、绝对 display-root 映射、分隔符/越界校验
  均保持原样。目录名首/尾空格、纯空白组件、Unicode/长名不再被改写或误判为整库。

原精确目录缺失/不可读时，`_resolve_entry_kind` 仍以既有 `source_missing`（404，
`sideEffects=none`，`relativePath` 逐字）拒绝并保留原 Task，不回退到 trim 目录、父目录或整库。

### 新增真实旅程与聚焦测试

- `tests/test_scope_continuation.py` 新增
  `test_a_paused_run_reviews_its_exact_space_suffixed_directory`：真实 CLI 创建 + 真实 pause API +
  真实恢复 Worker，断言摘要恰为 `Incoming/Folder /Left.2005.mkv`，邻目录不被观察/变更，源字节
  不变、零目标 mutation。去掉修正后该用例明确错选 `Right`。
- 新增 `test_a_missing_exact_scope_directory_never_falls_back_to_its_sibling`：原精确目录缺失时
  以 `source_missing` 拒绝，原 Task/兄弟文件保持、零 mutation。
- 新增 `tests/test_task_scope.py`（14 个聚焦用例）：未指定范围、首/尾空格与纯空白组件、Unicode/
  长名、绝对 display 路径及其同名兄弟、库根、越界与多库歧义/停用库。

### 实际受影响命令/结果（仓库根，`PYTHONPATH=tests`）

- `test_task_scope test_scope_continuation test_media_discovery test_media_discovery_provider_manifest test_organize_preparation` → **232 OK**
- `test_manual_organize_preview test_manual_organize_execution test_recovery_continuation test_task_center_recovery_lineage test_recovery_batch test_task_persistence test_sqlite_backup test_sqlite_restore test_operations_run_inventory test_operations_run_detail test_operations_task_center` → **320 OK**
- `test_automation_task_definition_preview test_automation_definition_execution test_automation_authorized_execution_matrix test_configuration_organize test_metadata_correction_continuation test_v2_manual_organize test_manual_organize_intent test_file_index_retirement test_runtime_files_browser test_media_library_browser test_storage_browser test_scanner test_resource_library_pipeline test_scan_retirement_stability test_direct_file_operations test_manual_operations_contract test_operations_task_center` → **286 OK**
- 独立复现：B 探针修复前 `offered_wrong_sibling=true`（`reproduce-b-p1-before.log`）；修正后同一真实旅程
  摘要恰为 `Incoming/Folder /Left.2005.mkv`（`verify-exact-scope.log`，`offered_exact_intended=true`）。
- 静态/治理：`python3 scripts/check_governance.py` PASS；`git diff --check` 干净；
  `python -m compileall -q mediaflow tests scripts` OK；`ruff check` / `ruff format --check` 覆盖
  3 个改动 Python 文件 → passed / formatted。

证据（本机 ignored 存储，非远程 CI）：`.git/validation-evidence/task45.5-developer-fix7/`：
`reproduce-b-p1-before.log`、`verify_exact_scope_fixed.py`、`verify-exact-scope.log`、`README.md`。

### 已知风险/边界

- 共享解析只改“未指定范围”判定与去 `.strip()`；未触碰 `final_cli.py` 的 display-root 映射、
  `scope_continuation` 的 ancestry 逐字比较或既有 pin/锁/准入语义。
- runtime schema 仍为 49（无新列/表）；wheel/隔离安装、生产 Docker、fresh/reopen 与支持版本迁移、
  完整 Python/Web/E2E/视觉矩阵仍是 B 的 T4 门禁，本轮未运行也未声称通过。
- 同文件既有 `a paused run continues only its remaining scope through the real Worker` 在上一轮基线上
  即失败，本轮未改变其范围；留给 B 判定。
- 本轮测试执行合计约 1.2 分钟，占本开发轮次总时长约 25%，低于 30% 上限。

预存修改保留且不纳入 checkpoint：删除 `docs/pics/操作与任务.png`；未跟踪
`docs/pics/自动化页-全局设置.png`、`docs/pics/自动化页.png`、各处 `.DS_Store`、
`output/imagegen/slice45-task-center-v1.zip`、`web/test-results-*` 及开发 `.log` 文件。
私有 ignored 配置不读取、不暂存。RO-8 未交付，本 Task 不宣称 Slice ready，也不自判 PASS。

## B Review Result

```text
Reviewed candidate: 1e965c095b355eab0feee7ef5ea4b2b1a4d8da08
Product implementation: 90b697f3b689b57d1d8a155076781d1501a4525c
Review range: 3e2cb31aca211a7dcb7fa7c4ba4883d55b951974..1e965c095b355eab0feee7ef5ea4b2b1a4d8da08
Decision: FIX REQUIRED — recovery trims the admitted directory and reviews a different sibling
Slice outcomes/surfaces all satisfied: NO — RO-7 / RO-8 pending
Next: SAME TASK FIX; B CONTINUES ORIGINAL BASE..CORRECTED HEAD REVIEW AND ASSIGNED T4
```

main、已提交Contract、治理PASS、Git/workspace可写。预存图片删除、未跟踪文件/日志/
截图/ZIP/浏览器结果及私有配置保持，不暂存。不改A-owned Slice/Roadmap/Progress、45.4
历史接受或冻结43。已复核适用需求、完整列表/整理/恢复旅程及CURRENT/TARGET。
候选相比`90b697f`仅修改B报告及下面的B-owned原生测试定位，不改产品代码。

### P1：真实CLI暂停后，恢复摘要改选了另一个目录

独立复现只使用隔离Managed Active、临时Local Storage、真实CLI/API/SQLite及恢复Worker，
Provider为离线fixture。暂停时序钩子仅在真实CLI创建Task后调用真实暂停API，未手工写Task/
TaskItem状态、未伪造结果或替换安全判断：

1. 同一资源库有`Folder `（末尾一个空格）和`Folder`两个真实目录，前者只有Left、后者
   只有Right。真实CLI执行`organize '<资源库>/Folder ' --limit 1`。
2. 原Task创建后，真实`POST /api/v1/tasks/{id}/pause`返回200；CLI在正常边界确认暂停，
   exit75。持久Task为paused、scope_path逐字等于CLI输入，尚未发现任何文件。
3. 真实`POST /api/v1/tasks/{id}/remaining-scope-previews`返回202，实际Worker完成分析。
   正式摘要列出的来源为`Incoming/Folder/Right.2006.mkv`，而非原范围的
   `Incoming/Folder /Left.2005.mkv`。两份源内容保持、目标文件为零，未请求执行。

这是可从正常入口到达的精确范围错误，不依赖上轮已撤回的跨Task忽略语义。原固定来源/
范围不能在恢复时改写；目录边界空白也已被FileIndex退役设计§2明确要求保留。

**根因与引入点。** `mediaflow/application/task_scope.py:68`对持久scope调用`.strip()`，
将目录名末尾空格当成输入装饰删除；line55还把纯空白字符串视作“未指定范围”，可能回退
库根。`MediaDiscoveryService`在`media_discovery.py:726`使用该结果构造恢复scope entries，
后续范围/计划检查沿用改错的范围，不能恢复原路径。该helper由`4afeb5eea39130325e1739a9eb2602f57262719b`
于2026-10-19 21:12:21+08:00引入，当前候选仍存在。Task Base中无此helper。

### Developer必需修正与顺序

1. **先增加上述真实入口回归。** 两个目录同时存在且名字只差边界空白；用真实CLI创建、
   真实暂停动作及正常acknowledge，再走恢复准入/Worker。修改前明确看到错选Right；修正后
   精确摘要只含Left，Right不被观察为本次候选、不进入摘要或确认范围。时序钩子可以发真实
   控制请求，不能在暂停后直接把条目改成Processing或手工改终态。
2. **修正共享scope解析，不在输出端补名字。** 区分文档定义的未指定scope（None/确切空串）
   与真实路径；不要对持久路径/目录名做`.strip()`或用空白判断把有效名字变成库根。
   保留绝对display-root映射与库相对路径的精确组件，以及现有分隔符/越界校验。`PurePath`
   转换后也要确保实际解析的库和相对范围仍对应原输入，不能切换到近似名字的邻目录。
3. **失败保持原范围。** 原精确目录消失、不可读或无法唯一归属时明确拒绝并保留原Task/
   具体恢复指引；不得改试trim后的目录、父目录或整库。现有歧义/越界/停用库/原pin拒绝
   不放宽；默认整库语义只属于原本明确未指定范围的合法工作。
4. **验证完整行为。** 覆盖首尾空格、纯空白目录组件、Unicode/长名；同名近似邻目录的冲突
   情况；无邻目录时正常恢复及原目录缺失时不回退；绝对display路径和持久相对路径；重开
   后范围逐字保持。有预算和满额undecided两种范围均保留原边界，不增加索引/第二恢复引擎。
   合法摘要确认后Worker只处理原范围，未确认零效果，兄弟文件及已完成/未知效果不重放。
5. 保持Task45.5的Base/Goal/High/T4及此前合法修正，提交连贯修正和真实受影响测试结果。
   不展开RO-8、冻结43或新增跨Task撤权功能，不改Slice/Roadmap/Progress，不另造Task。

### Developer受影响验证

增加聚焦scope解析用例（可放`tests/test_task_scope.py`），以及上面的真实CLI/API/Worker
集成用例；该新增回归随实际命名显式执行。现有直接受影响用例已核对：

```bash
python3 scripts/check_governance.py
PYTHONPATH=tests .venv/bin/python -m unittest test_task_scope
PYTHONPATH=tests .venv/bin/python -m unittest test_scope_continuation.ScopeContinuationWorkerJourneyTests.test_native_remaining_scope_preview_reviews_only_the_eligible_items test_scope_continuation.ScopeContinuationWorkerJourneyTests.test_native_remaining_scope_preview_never_widens_an_unresolvable_scope test_scope_continuation.ScopeContinuationWorkerJourneyTests.test_remaining_scope_recovery_proves_a_nonzero_stability_interval test_scope_continuation.ScopeContinuationWorkerJourneyTests.test_a_fully_recorded_budget_still_recovers_its_undecided_item test_scope_continuation.ScopeContinuationWorkerJourneyTests.test_a_full_budget_never_lets_a_new_file_borrow_the_pending_unit
.venv/bin/ruff check <changed-python-files>
.venv/bin/ruff format --check <changed-python-files>
git diff --check
```

`test_task_scope`是本次建议新增模块，创建后执行；不可把尚不存在的用例算已通过。
若实际修正触及更多消费者，追加对应直接受影响用例。Developer不跑完整Python/Web/E2E/
wheel/Docker矩阵，不补B全量证据包。已修复的原生定位由B维护，本次不要求Developer改Web。

### B本轮结果、证据与后续门禁

- 原生续跑失败已定位为测试将全列表中所有“预览+已完成”行算作本次续作。B改为点击原运行
  的真实“打开链接的继续运行”，断言URL指向精确child Task且详情已完成；保留原来源、精确
  剩余清单、重启和单次续作等全部断言。初次focused真实Python浏览器用例1 passed；初次
  Prettier检查失败，随后修正格式。最终精确候选再验**1 passed**（1.9s，外部进程2.364s），
  changed ESLint/Prettier均通过；不是放宽断言或加重试，完整原生门禁仍待产品修正候选。
- 精确候选完整Python回归已启动；独立确认上述P1后主动SIGINT停止，187.119s、exit -2，
  无完整结果/数量，**INTERRUPTED / PENDING，不是PASS，也不是产品回归FAIL**。原始日志保留，
  不隐去中断或ResourceWarning。未继续启动完整Web/E2E/wheel/Docker/视觉门禁。
- 已做原Base..Head清单及部分消费者/安全重点审查，发现P1后按workflow§6提前FIX REQUIRED；
  不宣称131文件全部diff已审完。已审读取路径含CLI只读Active/游标、来源证据、稳定观察、
  scope解析/恢复及原生续跑。剩余完整范围审查与Required Tests中的全部T4由B继续承担。
- 先前冻结混合、已完成不重放、真实稳定观察，以及正常暂停/元数据待处理/已解决三种忽略
  状态的独立事实保留于前轮证据。已撤回的“执行中忽略旧项即P1”不重新作为修复要求。
- Docker daemon实际可达（29.5.2）；本轮没有执行镜像矩阵，不以环境不足豁免。

本机稳定ignored证据：
`.git/validation-evidence/1e965c095b355eab0feee7ef5ea4b2b1a4d8da08/task45.5/b-review/`
中的`probe_scope_whitespace.py`、`scope-whitespace.log/json`、`python-full.log/json`、
`review-manifest.txt`、`b-harness-fix.patch`、README/耗时记录。原生定位通过日志及trace策略见
`.git/validation-evidence/77da20c26491af2a3190f2bc9aae445615c34ef2/task45.5/full-review/`。
本地证据不冒充远程CI；不机械复用已改执行输入的完整门禁，不机械重跑Final。

B在同一修正候选独立验证精确路径和失效不回退，继续原Base..Head审查和既定完整Python/
Web/E2E/原生与视觉/wheel隔离安装CLI/API/Worker/固定候选Docker/fresh/reopen/支持版本与
失败原子性门禁。上述中断结果不复用为完整通过，不将这些门禁交回Developer。

本轮所有测试、探索和检查累计保守上限210秒；记录时本轮总耗时530.3秒，验证上限
占比39.6%，低于50%，详细记录见review-timing.json，无等待凑时。
治理及git diff --check通过，用户预存变化保持。
RO-7未通过、RO-8尚未实现，不规划下一Task、不提交Closure Packet、不关闭Slice。
