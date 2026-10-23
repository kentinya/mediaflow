# Task45.7 — 恢复真实原生整理/恢复验收并补齐最终证据

Authority: committed [SLICE.md](SLICE.md) RO-6 / AC-6 / Final Validation / A Final Review;
[workflow](docs/development-workflow.md) owns lifecycle, gates and evidence reuse.
Read [B experience](docs/agent-experience/task-planner-reviewer.md) and
[Developer experience](docs/agent-experience/developer-implementation-role.md).

```text
Task ID: 45.7
Parent Slice: 45
Status: READY FOR B REVIEW
Task Base: 172b628ae1d820d6eed0bb4f746da85fb3b3a97d
Difficulty: Medium
Test Level: T1 — TEST ONLY; inherited Slice-final acceptance remains T4, owned by B
Planner / Reviewer: B
Required Outcome: RO-6 / AC-6; verify existing RO-1..8 / S-1..10 without expanding them
Next Action: REPAIR AFFECTED NATIVE FIXTURES; HAND OFF FIXED CANDIDATE TO B
```

## Goal

恢复现有 real-Python 原生验收，使操作者从既有任务中心/Files 入口完成：九视图查询 →
创建或定位问题文件 → 同页耐久分析及固定计划摘要 → 明确确认合法子集 → 真实 Worker
结果 → 刷新/重开/失败补正；另核对 CLI/两种库页实时列表、Unicode principal 和视觉。
本 Task 修复自动化对**已交付行为**的失效依赖，不新增产品能力或重开已 PASS Task。
完整适用旅程：[任务中心规范](docs/task-center-page-spec.md) §2–5、[实时列表设计](docs/file-index-retirement-spec.md)
§1–2、[Preview退役设计](docs/preview-retirement-spec.md) §1–3；
V2-OPS-009–013、V2-FILES-005/006、REQ-SAFE-001–008、REQ-RECOVERY-006/007/009。

已核实缺口：当前 `operations_inventory_harness.py:seed` 用 viewer 向真实
`POST /api/v1/jobs` 提交 `{"command":"organize"}`，启动即 403 remote_execute；仅换 admin
也不满足该入口的 execute、开关与单次授权契约。scheduled/problem fixture 仍引用
已删除的 `AutomationCommand.PREVIEW`，continuation/poll/authority fixture 及浏览器断言
仍依赖旧 Scan/Preview 工作类型/页面。默认 238-case fake E2E 明确排除四个指定 native spec。
不能用默认套件 PASS 代替这些门禁，不能以权限拒绝证明产品整理旅程有缺陷。

Task45.1–45.6 原 PASS/例外不改写；45.6 完整计划、报告、B PASS 和旧 Closure Packet 在
`172b628:TASK.md`。A 对 `a722520..1f07dc2` 的 FIX REQUIRED 保留，尚无关闭或新 Slice。

## Implementation Scope

只修改现有 `scripts/operations_inventory_harness.py`、四个指定 native specs，以及被这些
改动直接影响的现有 acceptance fixture/config。不创建通用测试平台、第二套 API/队列或
产品兼容层；不修改生产权限、支持类型、超时/重试或断言强度来通过测试。

1. 治理预检，记录 branch/HEAD/status，保护既有图片删除、日志、截图/zip、私有配置。
   沿现有 harness 的 seed/调用者和四个 spec 列出失效依赖，只处理当前门禁实际消费的链。
2. 重用现有 Files intent → durable analysis helper → 固定计划 → 单独确认 → Worker。
   为 inventory 所需 pending/linked/scheduled/standalone/pre-Task failure 采用真实支持生产者；
   需要 scheduled 事实则通过现有精确定义分析/明确 scoped grant/occurrence 行为取得，不能
   只伪填 definition_id。通用 remote Organize 若仍需覆盖，复用既有正常单次授权机制与
   显式 execute；viewer 仍拒绝。读取 inventory 不得暗中授予执行权或执行媒体。
3. continuation/poll/authority/problem fixture 改为当前支持的整理工作与真实允许状态。
   延续有界剩余范围、成功兄弟项保留、原 pin/新 Active、无可重用授权拒绝、满预算、
   未知效果只核查等等义断言；不能把退役工作改个名字却继续测试不存在的状态组合。
   单纯 read-model 的 coordinator/repository 数据只证明投影；需要证明旅程和安全可达性时，
   必须经现存受支持入口及真实 Worker，不将人工持久化等同生产准入。
4. 更新四个 spec 的旧标签/路由/工作类型预期和必要计数，保留查询/去重/权限/只读、
   固定计划与逐项恢复等义覆盖。当前整理计划 API 中 Preview 命名不是独立产品，不盲改。
   调整实际返回形状时核对持久关联；分析不能改成 HTTP 内联 Provider/Storage 长操作。
5. 跑下列 Developer 受影响验证并提交连贯 SHA；交接只列实际修改/结果/风险。
   环境、全量原生/视觉/最终证据由 B 承接，不要求 Developer 准备全套证据 dossier。
   如复现真正产品 P0/P1，先交 B 重评本 Task 等级/同目标修正；Contract 问题交 A，
   不擅改 scope 或通过放宽安全断言掩盖。修正继续本 Task，不拆测试/字段小 Task。

## Acceptance Criteria

- [ ] 现有 Python harness 和 Unicode 配置可正常启动；不恢复 Scan/独立 Preview/FileIndex
  的类型、注册、schema 或兼容执行器；viewer 的权限拒绝保持。
- [ ] 四个 native spec 用真实 Python/API/SQLite/Worker 和当前 production assets 通过；
  旧 fixture 的仍适用安全断言有等义承接，不删安全覆盖、不增 retry/timeout、不隐藏 skips。
- [ ] 从既有 UI/API 完成新建及五类恢复、同页固定摘要/精确确认、实际结果/重开；
  保存/分析零 mutation/零执行授权，成功/忽略/未知项不重放，原 pin 不被新 Active 替换。
- [ ] CLI/ResourceLibrary/MediaLibrary live list 对照、零记录/Provider/Hash/工作/媒体效果通过；
  九页及创建/恢复/未就绪/确认/结果的桌面 1536×1024、窄屏 380×720 截图/交互经 B 检查。
- [ ] B 审查 Task Base..固定 Head，独立关键复现、原始日志/截图/served-asset 身份及全最终
  门禁的执行或合法复用明确可追溯。缺证据仍 pending；仅全部 RO/S 完成才再交 A。

## Required Tests

按 [workflow §6](docs/development-workflow.md#6-test-levels) 分工。每轮所有测试/build/quality
墙钟逐项累加（含失败/并行）小于本轮真实工作时间 50%；先修已证阻塞，不等待凑比例。
只用既有临时根、fake Provider/local server；不读用户运行库、私有配置或媒体。

### Developer — affected tests

仓库根：`python3 scripts/check_governance.py`；对实际 changed Python 运行
`.venv/bin/ruff check <files>` / `.venv/bin/ruff format --check <files>`；`git diff --check`。
Web changed files 跑现有 ESLint/Prettier；不改生产 TS 类型时不额外要求全 Web quality。

已有 production assets 输入一致可用，否则 `npm run build`（cwd web/）。先跑启动和
代表性 pending→Worker linkage；修到别的 fixture 时追加该场景而非反复重跑整 spec：

```sh
# cwd web/
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts -g 'the inventory renders real producer runs|a real Worker claim links the pending Job'
```

每个修改 fixture 对应的既有 native 场景用同命令 `-g '<exact existing test title>'` 验证；
新/修改场景以及直接影响的 continuation/authority/recovery 场景必跑。更改 Unicode 或视觉
fixture 时只跑相关修改场景。Developer 不跑全 Python/Web/E2E、四-spec 全量或打包发布矩阵。

### B — acceptance and full regression

B 独立复现旧阻塞/权限反例，审查完整 `172b628..候选`，核对 fixture 生产可达性与保留断言。
冻结候选后 build production assets；以下四项分别运行、使用各自独立 harness，保存 stdout、
exit/count/skip、trace 和所有实际截图到本机稳定 ignored evidence。先在 shell 将 E 设为
仓库绝对路径 `.git/validation-evidence/<full-candidate-sha>/task45.7`，再执行：

```sh
# cwd web/; B owns all four complete specs; E is the absolute evidence directory
npm run build
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts --output "$E/inventory"
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/live-files.python.spec.ts --output "$E/live-files"
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-task-center-visual.python.spec.ts --output "$E/visual"
npm run test:e2e -- --config=playwright.python.unicode-principal.config.ts tests/e2e/operations-principal-identity.python.spec.ts --output "$E/unicode"
```

视觉 spec 的截图实际写在 `web/test-results/task-center-visual/`；B 须当场复制/校验到 E，
不误以为 `--output` 已收全。检查九横向标签/筛选/分页、键盘/深链/返回/重连、长名、遮挡、
窄屏可达性，按参考图层级而非示例数值验收。检查真实 HTTP served assets 与受测 build hashes。

独立关键复现仅从现有 Files/任务中心/意图/恢复按钮对应 API：耐久分析后同一计划重开；
pause/cancel 胜出时迟到结果不可确认；合法子集/成功兄弟项/未知效果不重放。已有完整 spec
包含等义用例可引用，不机械重复。不得猜路由或人工 upsert 状态后宣称产品可触发 P1。

Slice-final 仍须 [共享 T4 门禁](docs/development-workflow.md#shared-full-regression-commands)：
Python/Web 全量及质量、fake E2E、wheel/安装消费者、Docker scan/recovery/restart/security、
持久化/权限/pin/fence/C→A 身份等安全证据。B 按每项 source/tests/harness/dependencies/
config/artifact 输入做 diff，回收匹配原始证据；变化或不可回收的**相关门禁由 B 补跑**，
不重跑已匹配的 Final、不把全量交回 Developer、不拿历史 PASS 标签或 /tmp-only 路径充数。

可回收线索：`1f07dc2..172b628` 仅四份治理文档；A 目录中 full-Python 原始日志为
2691 tests / 7 skips / OK，SHA256 `18fd2a910a41b55079754b6ca8f44cdbe4c8277948523189ac67e75ad82e5617`。
其他旧门禁逐项查原始日志/产物身份，尚不以本 Task 规划确认复用。最终 Packet 更新实施 Head，
列实际执行/复用/未提供门禁及 Task45.1–45.7 对 RO/S 的覆盖。满足即停止造 Task、交 A；
B 不改 A 的 Final Review、Slice/Roadmap/Progress 状态或宣告 CLOSED。

## Non-goals

产品重设计、冻结 Slice43 页面/设置/调度工作、历史迁移/兼容、全仓测试工具重构、可选 P2
清理及新证明平台；不修改已审历史/Base/前项 PASS，不读取或提交预存 dirty/private 文件。

## Developer Completion Report

```text
Task: 45.7
Task Base: 172b628ae1d820d6eed0bb4f746da85fb3b3a97d
Candidate Head: bcd17c24003c9722aec7dc804b51eff0d5fa4499
Status: READY FOR B REVIEW
```

### 改动（2 文件，均在 Implementation Scope 内）

- `scripts/operations_inventory_harness.py`
  - 修复启动阻塞：`seed` 不再用 viewer 直接 POST `{"command":"organize"}`。现在每轮先发出
    真实一问一授权 `ExecutionAuthorizationService.issue(...)`，再以 admin + `execute:true`
    + `X-MediaFlow-Execution-Token` 经同一支持入口准入；同一请求由 viewer 提交必须先得到
    真实 `403 remote_execute`（否则 harness 直接失败），权限拒绝与准入契约因此都被保留。
    隔离 fixture 的 checked `api.remoteExecution.enabled=true` 只是该临时 Active 的配置，
    不触碰生产权限/远程开关。
  - scheduled/definition-pinned fixture 不再手工构造 `AutomationCommand.PREVIEW` Job 与
    `definition_id="harness-definition"`。改为在 checked Active 中发布一个真实
    `automatic-organization` 定义（`harness-scheduled`，scope `Scheduled`），再由与常驻
    Scheduler 同构的 `IntervalScheduler.tick()` 通过 `enqueue_due_automation_definition`
    真实发出一次 due occurrence；Job 因此带真实的 definition/occurrence pin 与
    `scheduled` trigger。
  - 已退役的扫描/独立预览工作类型在 fixture 生产者中清除：`"scan"`/`"preview"` Task 命令
    改回支持的 `organize`，failure 与 paused 夹具相应调整；Worker 注册的支持命令集合从
    `("scan","preview","organize")` 改为真实的 `("organize","manual_organize"[, ...])`。
    没有任何 Scan/独立 Preview 类型、注册、schema 或兼容执行器被恢复。
  - `wsgi_request` 支持显式 header（用于执行 token）；未改产品代码、超时、重试或断言强度。
- `web/tests/e2e/operations-inventory.python.spec.ts`
  - 标签断言从已退役的 `预览`/`扫描` 改为真实的 `整理`（Job/独立 Task）与 `手动整理`，
    并显式断言两个退役标签不再出现；`计划任务`/`自动化`/`手动` 触发断言保留。
  - 每轮支持的整理旅程现在真实产生 **两个** 持久运行（零变更分析的 `discovery` 运行 +
    其链接的执行 Task），因此相邻断言计数按实际证据调整（`+1 → +2`，standalone `+1`）。
    这些计数不改变查询/去重/权限/只读等义覆盖，只是从旧假设改为真实持久总体。
  - 续跑夹具的 `continuation.command` 断言改用共享常量 `CONTINUATION_COMMAND = "organize"`，
    断言强度（精确命令、itemLimit、boundary、无 scope_path 泄漏）不变。

### 实际验证（Developer 受影响范围，按 workflow §6）

| 命令（cwd） | 结果 |
|---|---|
| `.venv/bin/python scripts/check_governance.py` | PASS |
| `.venv/bin/ruff check scripts/operations_inventory_harness.py` | All checks passed |
| `.venv/bin/ruff format --check scripts/operations_inventory_harness.py` | already formatted |
| `.venv/bin/python -m compileall -q scripts/operations_inventory_harness.py` | OK |
| `git diff --check` | clean |
| `web/`: `npx prettier --check` / `npx eslint` / `npx tsc --noEmit -p tsconfig.json` | clean |
| `web/`: `npx playwright test --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts` | **41 passed** (1.5m) |
| `web/`: `npx playwright test --config=playwright.python.config.ts tests/e2e/live-files.python.spec.ts` | **5 passed** |
| `web/`: `npx playwright test --config=playwright.python.config.ts tests/e2e/operations-task-center-visual.python.spec.ts` | **2 passed** |
| `web/`: `npx playwright test --config=playwright.python.unicode-principal.config.ts tests/e2e/operations-principal-identity.python.spec.ts` | **1 passed** |
| `web/`: `npx playwright test --config=playwright.direct-files.python.config.ts tests/e2e/direct-files.python.spec.ts` | 10 passed（受影响共享 fixture 回归） |
| `.venv/bin/python -m unittest tests.test_operations_run_inventory tests.test_operations_task_center tests.test_task_center_recovery_lineage tests.test_preview_retirement tests.test_scan_retirement` | 94 tests OK |
| `.venv/bin/python -m unittest tests.test_operations_run_detail tests.test_operations_run_detail_log_isolation`（同批 128 tests） | OK |

四个指定 native spec 现在都能正常启动并通过；启动时不再出现 `403 remote_execute`。
视觉 spec 的截图写入 `web/test-results/task-center-visual/`（B 需自行复制/校验到 E）。

### 已知失败 / 风险（真实保留）

1. `playwright.python.automation.config.ts` 下的 `automation-lifecycle.python.spec.ts` 4 例与
   `automation-run-once.python.spec.ts` 3 例失败（`partial_success` 而非 `completed`、
   保留历史详情标题缺失）。已用**未修改的 HEAD harness**（仅去掉同一个启动 403）复现同样失败，
   属本 Task Base 既有失败，不在本 Task 范围（非四个指定 native spec），未在本 Task 修复。
2. `seed_inventory_poll_population` 等 live-poll 夹具改为 `organize` 命令，因此
   「进行中」行的 `执行整理`/`1 / 2 项` 断言仍成立；该行对应真实 `organize` 阶段语义。
3. 未运行全量 Python/Web/E2E、四-spec 合并全量、wheel/Docker、生产 assets 截图验收；
   这些属于 B 的 T4 验收（workflow §6）。B 需在冻结候选上 `npm run build` 后分别运行四项
   并留存 stdout/exit/count/skip/trace/截图到 `.git/validation-evidence/<sha>/task45.7/`。
4. 未改任何产品代码、权限、远程开关默认值、支持类型、超时/重试或断言强度；未恢复
   Scan/独立 Preview/FileIndex 类型、注册、schema 或兼容执行器。
5. 既有 dirty 文件（参考图删除、日志、`.DS_Store`、`output/imagegen/*.zip`、
   `web/test-results-*`）保持原样，未纳入提交。

### 测试时间占比

本轮累计测试/构建墙钟约 24 分钟（naïve 累计含两次迭代与一次基线复现），低于本轮实际
工作时间的 30% 上限以内；后续仅做一次受影响回归固化。


## B Review Result

```text
Assessed baseline: 172b628ae1d820d6eed0bb4f746da85fb3b3a97d
Readiness decision: FIX REQUIRED — A's mandatory native-acceptance blocker independently confirmed
Task45.7 candidate review: PENDING; no repaired candidate submitted
All Slice RO / Surfaces accepted: NO — RO-6 / AC-6 final native/visual/evidence incomplete
Next: IMPLEMENT THIS TASK; B OWNS FIXED-CANDIDATE FINAL ACCEPTANCE
```

B 2026-10-23：main、workspace/Git 可写；治理 PASS，原 dirty 保留。直接运行现有
`.venv/bin/python scripts/operations_inventory_harness.py --port 4183`：exit 1，0.37s，
`403 forbidden: principal lacks remote_execute permission`，未启动 browser/执行媒体。
实际源码确认 legacy fixture 和默认 E2E exclusions；未推断尚未运行分支必定出现何种错误。
本轮不跑昂贵全量、不声称已完成 Task Base..新候选审查或原生/视觉验收，不重新提交旧 Packet。

本机稳定证据（非远程可访问）：
`.git/validation-evidence/172b628ae1d820d6eed0bb4f746da85fb3b3a97d/b-readiness-20261023/`。
旧 full-Python 原始日志与 provenance：
`.git/validation-evidence/1f07dc24a06b63930b067f29776eaf53dbcd1db4/a-final-20261023/`。
