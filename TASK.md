# Task 58.2 — 通用 CLI 与配置 schema 11 退出

Next Action: B REVIEWS TASK 58.2 BROWSER TEST ENTRY CUTOVER

用户已授权激活 Task 58.2。Developer 提交的首轮修正为 `f162cf0e`，B 已复审并给出 FIX REQUIRED；
Developer 已完成浏览器验收入口切换并提交 `e2cb3028`，交 B 复审。
[Slice 58 合同](SLICE.md#required-outcomes-and-surfaces) · [开发工作流](docs/development-workflow.md)

```text
Task ID: 58.2
Task Type: SLICE
Parent Slice: 58
Status: READY FOR B REVIEW
Task Base: 307eaaf8b006527a11fa2514de839a5528e6c202
Difficulty: High
Test Level: T4
Planner / Reviewer: B
Implementation Authorization: AUTHORIZED BY USER FOR TASK 58.2
```

## Developer 交接 — 浏览器验收入口切换

```text
Candidate: e2cb3028
Scope: 六个旧入口浏览器验收脚本退役 + 三处过期引用
```

- 删除 `files_toolbar_browser_proof.py`、`storage_settings_browser_proof.py`、
  `classification_destination_browser_proof.py`、`rules_identity_browser_proof.py`、
  `rules_object_analysis_browser_proof.py`、`rules_workspace_browser_proof.py`。它们都从
  `.venv/bin/mediaflow config import/validate-draft/activate` 起步，58.2 已删除该 console script
  与命令，因此运行即在启动阶段退出。修正后的工作区已无旧命令的可执行调用；其余引用只剩
  `tests/` 中的退役断言。
- 删除前逐个核对现行自动化：
  - 两种库的精确目录、条目、超长名、边界空白、游标分页与读取零效果 →
    `web/tests/e2e/live-files.python.spec.ts`（真实 Python + 真实 Storage 读）。
  - 长路径工具栏与面包屑 → 结构断言 `web/src/shared/ui/files-toolbar-styles.test.ts`、
    行为断言 `web/src/shared/ui/files-path.test.tsx`、命令与列表/网格
    `web/tests/e2e/library-files.spec.ts`、`medialib-files.spec.ts`、`medialib-commands.spec.ts`；
    生产镜像上的同一测量矩阵仍在 `scripts/docker_files_toolbar_browser_proof.py`。
  - Storage 卡片的 checked 保存与回读 → `web/tests/e2e/storage-dialog.python.spec.ts`；
    空库首次设置与空 Active → `scripts/docker_empty_baseline_smoke_test.py`。
  - Rules 对象身份、发布、复制与引用影响 → `web/tests/e2e/rules-identity.spec.ts`。
  - Rules 对象分析与 C 复用 A 的 Naming/Classification 策略后仍为 C →
    `tests/test_v2_rules_object_analysis.py` 与 `web/src/features/rules/RulesObjectTestPanel.test.tsx`。
  - Rules 工作区八张导航卡、七族表单、B54-02/03/05/06 与卡片样式 →
    `web/src/features/rules/RulesWorkspacePage.test.tsx`、`RulesEditPage.test.tsx`、
    `web/src/shared/ui/rules-form-styles.test.ts`。
  - 分类目标契约、历史前缀保留与导出不持久化只读键 →
    `tests/test_classification_destination_contract.py`、
    `web/src/features/rules/ClassificationDestinationForm.test.tsx`。
  核对后没有仅存在于这些脚本、且在现行入口下仍可发生的合同断言缺口，因此未新增用例；
  历史截图与定量结果从原 Git 检查点取得。
- 三处指向已删脚本的过期引用改为现行证据位置：
  `scripts/docker_files_toolbar_browser_proof.py` docstring、
  `web/src/shared/ui/rules-form-styles.test.ts`、
  `web/src/features/rules/RulesWorkspacePage.test.tsx`。

本轮实际运行（仓库根目录，除注明外）：

- `python3 scripts/check_governance.py` → PASS；`git diff --check` → 无输出。
- `.venv/bin/ruff check .` → All checks passed；`.venv/bin/ruff format --check .` → 356 files
  already formatted；`.venv/bin/python -m compileall -q mediaflow tests scripts` → 通过。
- 定向 Python：`test_container_deployment test_container_probe test_resident_services
  test_runtime_lease test_sqlite_backup test_sqlite_restore test_file_index_retirement
  test_runtime_strategy_configuration test_release_validation test_release_security` → 125 项通过；
  `test_automation_entrance_recovery test_resident_correction test_configuration_snapshot`
  → 45 项通过。
- `web/`：`npm run typecheck`、`npm run lint`、`npm run format:check`、`npm run build` 通过。
- `web/`：`npx vitest run src/shared/ui/rules-form-styles.test.ts
  src/features/rules/RulesWorkspacePage.test.tsx` → 60 项通过。
- `web/`：`npm run test:e2e -- --config=playwright.python.config.ts
  tests/e2e/live-files.python.spec.ts` → 6 项通过（登录后两个库的真实目录、分页与零效果）；
  `tests/e2e/storage-dialog.python.spec.ts` → 8 项通过（Storage 卡片 checked 保存与回读）；
  `npm run test:e2e -- tests/e2e/files-interactions.spec.ts tests/e2e/rules-identity.spec.ts`
  → 8 项通过；`--config=playwright.python.automation.config.ts
  tests/e2e/configuration-settings.python.spec.ts` → 10 项通过（Settings checked 发布）。

剩余风险与待 B 验收：

- 被删脚手架曾产出定量几何与截图证据。现行仓库仍在 Docker 工具栏脚本、
  `rules-readiness.spec.ts` 等处以真实浏览器测量保留同类断言，历史数值只存于原 Git 检查点。
- `docs/v2-requirements.md` 的 schema 11 切换例外、`docs/architecture.md` 的 switch 描述与
  `docs/requirements.md` 的 CLI 命令清单尚未随退役实现同步，按 Task 由 A 终审时更新。
- 全量 Python/Web/E2E、源码外安装、wheel、候选镜像与固定 Slice Base 接续仍归 B。

## B 复审 — FIX REQUIRED

```text
Reviewed Base: 307eaaf8b006527a11fa2514de839a5528e6c202
Reviewed Head: 1daad11a500aaab876f465f142f8164681d8bdf2
Decision: FIX REQUIRED
Slice Outcomes / Surfaces complete: NO
```

**P1 / RO-4：仍可执行的浏览器验收脚本没有完成入口切换。** 维护者构建 Web 后，按仓库
现有入口运行 `.venv/bin/python scripts/files_toolbar_browser_proof.py`，目的是在真实 API
上打开资源库、浏览长路径并检查工具栏。脚本创建临时库后在 API 启动阶段退出。预检指出
历史文件和媒体根与部署配置不符，浏览器尚未打开。脚本还保留旧 `mediaflow` 的导入、
验证和激活调用。真实 Rules 识别验收脚本也在启动阶段退出，源码核对共发现六个仍执行
旧命令的脚本。Task Base 已带有未切换的设置代码，58.2 删除了它们仍引用的通用命令。

首轮三项修正已复验。旧库校验和发布指引给出原版本或新目录的去向。两个专属文件列表模块
已从候选 wheel 移除。整理、来源历史和元数据回归从 Files、Run once 等现行入口受理。
首轮细节见 `03464d11:TASK.md`。

### 本轮返工开发指导

1. 核对 `scripts/` 下的 `files_toolbar_browser_proof.py`、
   `storage_settings_browser_proof.py`、`classification_destination_browser_proof.py`、
   `rules_identity_browser_proof.py`、`rules_object_analysis_browser_proof.py` 和
   `rules_workspace_browser_proof.py`。现行自动化已覆盖的场景直接清除重复脚本，历史证据从
   原 Git 检查点取得。先对照 `live-files.python.spec.ts`、`files-interactions.spec.ts`、
   `storage-dialog.python.spec.ts`、`rules-identity.spec.ts` 与
   `tests/test_v2_rules_object_analysis.py`，把仍缺的合同断言接到已有测试。
2. 保留的验收从最小 bootstrap、真实管理员会话和 Settings／正式配置 API 的 checked
   publication 起步。复用现有隔离夹具，保留两种库的精确浏览和零效果、Storage 只读检查、
   Rules 分析与 C 使用 A/A 策略后仍为 C 的断言。沿用现行服务启动入口。
3. 在修正后的工作区核对旧命令的可执行调用已清除。用现有测试从启动、登录或配置发布走到
   至少一个受影响的浏览器任务结果。运行相关场景、`python3 scripts/check_governance.py`
   和 `git diff --check`。全量验收和固定 Slice Base 接续仍由 B 负责。

### 本轮验证与 Slice 重评

- Python 全量 2326 项，2319 通过、7 跳过。定向 80 项通过。治理、Ruff、编译、依赖、
  样例和禁用依赖检查通过。Web 静态检查、1642 单测及 289 常规浏览器用例通过。
- 源码外 wheel 冒烟通过。独立的安装后恢复脚本首跑缺 `tests/account_fixtures.py`，在
  测试清单临时补入现有夹具后，同一 wheel 的两个恢复用例通过，仓库脚本未改动。
- 正式 Compose 空库、媒体挂载、重启故障和发布安全冒烟通过。Colima 首跑无法访问系统临时目录，
  使用 Docker 可访问的临时目录后重跑。启动、账号和离线恢复继承 58.1 已验收的范围，本轮也
  核对了更新后的旧库恢复指引及当前库的 wheel 备份恢复。
- 原生合跑记录 44 项通过、3 个 Task Center 用例失败、1 项中止、40 项未运行。
  其中运行列表和整理计划历史两项分别在 Task Base 与候选的独立夹具中通过。合跑结果保留，
  后续由 B 复验。RO-4 的浏览器脚手架和固定 Slice Base 接续尚待验收。

日志、浏览器产物和制品标识在
`.git/validation-evidence/1daad11a500aaab876f465f142f8164681d8bdf2/b-review/`。

## 目标与当前缺口

完成 RO-4，保留 RO-1 至 RO-3。部署者用现有四个服务入口启动实例，按主机指引领码、找回密码、停机备份和恢复。
管理员登录 Web 后，从系统设置发布配置，从库文件页浏览、整理与传输，从原 Task 查看结果和继续适用操作。
集成仍用既有 `/api/*` 和原权限令牌。重开当前受支持库后，原任务、结果、审计、快照和原请求仍可核对。
当前版本发现旧配置 schema 11 时，启动、探针和主机维护在写入前拒绝并给出原版本处理或新数据目录初始化的去向。

Task 58.1 已切换部署和主机维护。Task Base 仍包含通用 console script、CLI 专属 Worker 路径、
旧列表夹具及 schema 11 切换逻辑。候选已移除这些入口及实现，剩余可执行验收脚本见本轮复审。

## 实施范围与开发指导

1. **迁移保留行为的调用。** 先核对 `final_cli.py` 的生产、脚本及测试消费者。把仍有效的断言接到
   已有共享用例或真实 Web/API。优先改 `scripts/operations_inventory_harness.py` 与
   `web/tests/e2e/live-files.python.spec.ts`，用两个现行库文件 API 与页面核对精确目录名、条目、
   游标分页、权限、失败恢复及读取零效果，再删除旧列表夹具入口。保留配置发布、计划解释、
   有界任务控制、审计和通知的现行断言。
2. **退役命令和专属 Task 路径。** 删除 console script、`mediaflow.cli`、`mediaflow.final_cli`、
   旧解析、过渡分派及专属命令实现。核对 `resident_entry.py`、
   `application/automation_definition_execution.py` 与 `application/manual_task_continuation.py`
   的真实调用关系，删除仅为 CLI 受理、执行和续作服务的路径，包括 `direct-organize`。
   保留现行 Web 人工整理、Automation 到期及 Run once、普通文件传输、有效固定快照和同 Task 续作。
   共享 Storage、Provider、计划、执行、审计、权限及读回逻辑留在现有应用边界。
3. **统一数据库适用性。** 在 `sqlite_applicability.py` 对配置标记落实当前 schema 12 规则；
   运行库 schema 60 和 store origin 规则保持。启动、探针、发码、备份校验及恢复统一复用适用性判断。
   删除 `configuration_data_switch.py`、仓储的 `apply_data_switch` 与切换事务、结果及旧处理指引。
   检查空库和当前仅配置库的创建／重开，保持来源备份、原库和所有合法历史的原值。
4. **切换制品和门禁。** CI 和工作流的样例校验复用实际配置加载与校验逻辑，可将
   `tests.test_runtime_strategy_configuration.RuntimeStrategyConfigurationTests` 的现行验证断言
   改为由加载入口验证样例，作为源码门禁。wheel 冒烟在源码外用同一加载逻辑验证样例，检查
   安装物中两个旧模块和旧命令缺席。镜像、冒烟、部署及恢复指引使用现有正式入口。
   A 终审时同步 V2 现行契约与接受账本。

## 验收标准

- [ ] 源码和清单、源码外安装的 wheel 与候选镜像均无旧入口、旧模块、分派或 CLI 专属工作路径。
  用已有调用、有效配置和隔离媒体通过正式入口核对拒绝，期间没有新增 Task、配置发布、Provider 请求
  或媒体效果。两种库的 Web/API 可照常浏览、翻页和读取受理结果。
- [ ] 用仓库现有 schema 11 夹具走四服务启动、探针、主机发码与恢复。启动和写入类入口在修改前拒绝，
  校验区分文件完整性与版本拒绝，源库／备份摘要不变，空恢复目标保持不存在。空库、当前仅配置库和
  当前运行库可启动或重开，当前备份可恢复。四服务和五项主机操作保持可用。
- [ ] 用 Slice Base 的实际 Web/API 与 Automation 建立受支持库和合法任务。候选重开原库后，读回原账号、
  令牌权限、配置、审计、请求、Task／Item／Result、原摘要和固定快照。通过正式 Web/Worker 在原 Task
  显式续作可处理条目，已完成及效果不确定项零重放。完成空库设置、文件夹整理、普通传输、Automation
  到期与 Run once、Webhook 投递和同版本恢复的合同验收。
- [ ] 样例继续通过同一配置验证行为，无 Storage 变更或工作受理。正向业务与安全断言覆盖现行入口，
  其中 RecognitionType C 复用 A 的 NamingPolicy 与 ClassificationPolicy 后仍为 C。

## 测试分工

### Developer — affected tests

从仓库根目录运行下列范围。测试随入口迁移改名时，在交接中记录对应测试和实际命令。

```bash
python3 scripts/check_governance.py
PYTHONPATH=tests .venv/bin/python -m unittest \
  test_container_deployment test_container_probe test_resident_services test_runtime_lease \
  test_sqlite_backup test_sqlite_restore test_file_index_retirement \
  test_runtime_strategy_configuration test_release_validation test_release_security
PYTHONPATH=tests .venv/bin/python -m unittest \
  test_automation_entrance_recovery test_resident_correction test_configuration_snapshot
git diff --check
```

另运行本 Task 转接或修改的对应测试模块，并在 `web/` 从受影响的真实文件列表入口验证：

```bash
npm run build
npm run test:e2e -- --config=playwright.python.config.ts --output=test-results/task58.2-live-files tests/e2e/live-files.python.spec.ts
```

### B — acceptance and full regression

- 按 [T4 共享门禁](docs/development-workflow.md#6-test-levels) 执行 Python、Web、源码外安装、
  wheel 和候选 release-security。对有正式配置的隔离候选核对旧入口拒绝、schema 11 拒绝及零效果。
- 用 `.venv/bin/python scripts/docker_empty_baseline_smoke_test.py --image "$candidate_image"` 和
  `.venv/bin/python scripts/docker_restart_fault_smoke_test.py --image "$candidate_image"` 验证正式
  Compose，复验根页领码找回、停机恢复与两个库的现行业务。运行适用的真实 Python Playwright
  文件、账号、整理与恢复旅程，分别保留产物。
- 以 `SLICE.md` 的固定 Base 创建隔离实例和真实受理记录，再用候选接续同一库完成 AC-05，
  保存两端制品标识、原 ID 与快照／效果读回。按合同完成需要补齐的 Slice 终验并交 A。

## 非目标

范围限于合同中的入口退役、数据库适用性及当前行为接续。沿用现有账号、权限、Web/API、Task 内核与
媒体效果模型。跨版本迁移、旧 CLI 工作接管及媒体备份沿用 Slice 明确范围。

## 上一项验收 — Task 58.1 PASS

```text
Reviewed Base: c8d8d30fa77c908bba4a73a1f9b9660ba51f4bfb
Reviewed Head: 307eaaf8b006527a11fa2514de839a5528e6c202
Decision: PASS
Slice Outcomes / Surfaces complete: NO
Next: TASK 58.2 PLANNED
```

B 独立审查完整 Task Base..Head。首个 Task 由 A 代 B 规划的用户授权例外限于规划。

- 本轮 `.venv/bin/python -m unittest discover -s tests` 运行 2374 项，2367 通过、7 跳过、零失败。
  治理、Ruff、编译、依赖一致性、样例配置与禁用依赖审计通过。精确候选 wheel 构建与源码外安装通过。
- 候选镜像 `sha256:33b31a99b243e56e7760dd2a5c6749e1fa80b1d0b447e65ee22ffc40b3b86c13` 的
  `docker_empty_baseline_smoke_test.py` 两段通过。无挂载空库可初始化、读回同一 Active，原进程领到
  到期工作并投递 Webhook。媒体挂载段在正式 API 受理、分析和核对期间零效果，显式确认后同一 Task
  完成一份原字节 COPY，两种库的普通 Copy 均完成，四个服务身份保持一致。
- 对比 `c0315d87..307eaaf8`，只有 Task／发布文档、空库冒烟和配置包单测变化。
  Web、原生浏览器夹具、Docker 构建及其他发布检查的相关输入一致，标准镜像 Config 和 RootFS
  也一致。复用 B 上轮 Web 单测 1642、常规 E2E 289、原生整理 E2E 18、Docker 重启故障和发布安全
  的通过结果，以及镜像页面建号／密码重置／旧会话撤销和源码／Compose 备份恢复的结果。
  本轮核对恢复指引中的 API 启动步骤与 Git 忽略路径。
- RO-1 至 RO-3 在 Task 58.1 的范围内已验收。RO-4 仍有旧入口、专属工作路径和 schema 11 切换，
  由 Task 58.2 完成，并补做合同的 Slice Base 合法任务接续验收。

本轮日志和制品摘要在
`.git/validation-evidence/307eaaf8b006527a11fa2514de839a5528e6c202/b-review/`。
复用的 B 结果在 `.git/validation-evidence/c0315d8795fb042448fdc22f1e05b1fb43fcb29f/b-review/`。
原 Task 和返工记录见 `307eaaf8:TASK.md`。
