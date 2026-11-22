# Task PATCH-20261122-3 — 精简手动整理准备页并纠正后台状态误报

```text
Task ID: PATCH-20261122-3
Task Type: STANDALONE MINOR BUG
Parent Slice: NONE
Status: READY FOR B REVIEW
Task Base: c714e0806620bb54701639a8776517ba5e1e9685
Difficulty: Medium
Test Level: T3
Planner / Reviewer: B
```

## 目标与现状

在「文件」页对资源库的单文件、多文件或文件夹发起整理后，用同一个短小弹窗等待首份方案。
当前弹窗同时显示阶段卡、准备进度、诊断和后台提示。标题下的小字贯穿各阶段，排队时正文又在多处
重复同一状态。用户已确认单文件、多文件和后台暂不可用三种效果图。
[弹窗实现](web/src/features/operations/ManualOrganizeDialog.tsx#L1645) ·
[V2-OPS-017](docs/v2-requirements.md#slice46-authorized-amendments--current) ·
[V2-OPS-018/019](docs/v2-requirements.md#current--manual-organize-dialog-slice53-pass--closed) ·
[手动整理旅程](docs/product-experience.md#current--manual-organize-dialog-slice53-pass--closed)

用户实测每次整理都会显示「处理 Worker 暂不可用」，随后仍进入复核。自 `c1c21908` 起，
生产 Worker 由 `ManualTaskEngineWorker` 处理文件发现，却在注册时漏报 `media_discovery`。
准备接口按这项能力检查就绪，因此返回 `unsupported_command`，弹窗据此显示误报。
在临时 SQLite 和测试文件中已复现同一任务一边报告不可用、一边生成方案，准备期间没有修改文件。
生产 CLI 登记也复现了缺项，实验性补录能力后就绪检查返回 `ready`。
[生产装配](mediaflow/final_cli.py#L2485) ·
[Worker 注册](mediaflow/application/automation.py#L483) ·
[准备接口](mediaflow/interfaces/service_api.py#L10814)

## 实施范围与步骤

1. 对齐生产 Worker 装配和已注册的命令能力。在接入实际负责文件发现的处理器后、首次登记前，
   声明 `media_discovery`，沿用既有注册和心跳机制。就绪继续由后端按存活、运行库版本和命令能力判断。
   文件页整理仍按 `manual_organize` 认领，使用原配置快照和执行权限检查。
2. 在共享整理弹窗内限定首份方案的准备视图。标题只显示「整理所选文件」。正文居中显示加载动画和
   「正在准备」，下方只有「来源资源库」和「受理范围」。提交和读回期间可以使用页面已有的来源，
   受理范围从本次请求的实际受理记录读取。范围行内沿用可展开的确切路径，供需要时核对。
3. 后端已报告至少两个主文件时，加一行「整理进度」，例如「已找到 8 个主文件」。
   用实际发现的主文件数，单文件和目录扫描尚未确定有多个主文件时省略该行。准备视图移除常驻阶段卡、
   独立后台提示框、技术诊断和重复说明。
4. 后台不可用且请求已保存时，在动画原位显示「后台暂不可用」和「请求已保存，请联系管理员。」
   沿用对同一准备的自动读取。只有发生未受理、排除或读取等异常时，才就近提供简短原因和下一步。
   保留同一准备或摘要的重新读取、现有按权限开放的分析恢复，以及超限后回文件页缩小范围的入口。
   已知的未受理项及原因从范围处可核对，整批复核中的对应证据沿用基线。
5. 沿用现有 ModalCardShell、读取和轮询。首份可复核方案读到后，自动切换到既有逐文件复核。
   逐文件复核、复核内重新分析、整批确认、执行交接、历史和任务中心详情以基线为验收参照。
   任务中心「继续整理」打开的原工作仍处于首轮准备时，复用同一准备视图。

## 验收

- [ ] 生产 CLI 路径启动的健康 Worker 实际注册 `media_discovery`。同一准备在正常排队时已返回
      `worker.ready: true`，弹窗保持「正在准备」，随后 Worker 生成该任务的首份方案。
      停止、心跳过期、运行库版本不兼容或缺少对应能力的 Worker 仍按已有条件判为不可用。
- [ ] 桌面和 390px 的单文件准备只显示动画、状态和两行事实，关闭可用，键盘焦点留在正确的弹窗层。
      减少动态效果时，静态状态仍可读。
- [ ] 多文件或目录从未发现到发现多个主文件时，在原位出现真实发现数。进度数字以主文件计，
      目录条目、附件和未受理项不计入，未知总量不显示百分比。
- [ ] 后台不可用时以原位提示代替动画。后台恢复、刷新、关闭后重新打开仍读取同一准备。
      从发起到恢复只发送一次受理 POST，进入首次复核前执行请求和媒体变更均为零。
- [ ] 部分未受理、读取失败、分析恢复和 101 个主文件超限仍各有原有的合法下一步。
      100 个主文件可进入复核。首次方案加载完成后进入原复核，复核内重分析期间始终保留
      原工作上下文、已存方案和既有确认门槛。

## 验证计划

- Developer 从仓库根目录运行
  `.venv/bin/python -m unittest tests.test_processing_worker_readiness tests.test_manual_task_engine.ManualTaskDiscoveryTests.test_new_files_discovery_runs_as_one_task_until_human_confirmation`。
  在 Worker 就绪用例中走生产 CLI 注册，以临时 SQLite、测试文件和实际准备 GET 验证
  「先排队且就绪、后在同一任务生成方案」，并覆盖不可用的对照条件。测试读取真实注册记录，
  浏览器夹具自行登记的能力可用于界面测试。
- Developer 在 `web/` 运行 `npm run test -- run src/features/operations/ManualOrganizeDialog.test.tsx src/features/library/StorageFilesPage.test.tsx src/features/operations/OperationsInventory.test.tsx`，
  覆盖首轮准备、已读范围、进度显示和同卡复核。更新锁定旧文案的断言时保留原受理次数、同一任务及零文件效果的断言。
- Developer 在 `web/` 运行 `npm run typecheck`、`npm run build` 和
  `npm run test:e2e -- library-files.spec.ts -g 'preparation|bounded discovery|multi-file intent|Organize admission'`。
  用 Files 入口检查受理、准备、刷新及首份方案交接。
- B 独立核对 Base 到候选的差异，从仓库根目录运行
  `.venv/bin/python -m unittest tests.test_processing_worker_readiness tests.test_manual_task_engine`，
  核对由真实注册证据得到的就绪和不可用状态，以及同一任务生成方案。
  在 `web/` 用候选的生产构建运行
  `npm run test:e2e -- --config playwright.python.config.ts manual-organize-dialog.python.spec.ts`。
  用临时媒体根目录和真实 Worker 验证后台恢复、目录多文件进度、部分拒绝和超限。核对桌面与 390px 首屏，
  以及首份方案到逐文件复核、整批确认和准确任务交接的原有流程。

## Developer 交接 — 精简准备页与 Worker 就绪

```text
Candidate: 6bda4d4533cde0e6890c05a7f47315637463994f
Task range: c714e0806620bb54701639a8776517ba5e1e9685..6bda4d4533cde0e6890c05a7f47315637463994f
```

- 生产装配的 `ResidentProcessingWorker` 在接入实际负责任务发现的 `ManualTaskEngineWorker` 后声明
  `media_discovery`；若此前已登记则失效，由下一次同一边界重新登记。健康 Worker 的排队准备因此
  返回真实就绪，停止、过期、运行库版本不兼容和缺少命令的 Worker 仍按原条件拒绝。文件页整理的
  认领、原配置快照和执行权限检查未改。
- `ManualOrganizeDialog` 的首份方案准备视图只保留「整理所选文件」标题、居中的加载状态「正在准备」、
  「来源资源库」和「受理范围」两行事实。受理范围沿用可展开的确切路径，并同时列出来自本次请求的
  已受理、同一工作已受理和未受理条目及原因。发现至少两个主文件时增加「整理进度：已找到 N 个主文件」
  事实，不显示未知百分比。提交时使用页面已有的资源库与所选路径，读回后使用实际受理记录。
- 后台不可用时在原加载位置显示「后台暂不可用」/「请求已保存，请联系管理员。」，不显示动画；
  同一准备的读取、轮询与恢复保持不变。失败、遍历不完整、排除和分析请求结果只在异常时就近说明
  原因与下一步；101 个主文件上限仍保留关闭并回文件页缩小范围的入口。首份方案读入后继续进入
  原有逐文件复核、整批复核、确认和执行交接。常驻阶段卡、准备计数区、独立后台提示框和技术诊断
  已从该准备视图移除。
- 测试初始化补充 `media_discovery` 命令就绪的不可用对照；新增生产 CLI 登记 → 排队准备 GET
  `worker.ready: true` → 同一 Task 生成首份方案的真实 SQLite/本地文件用例。界面用例覆盖单文件
  两行事实、可展开确切路径、拒绝项、至少两个主文件的真实进度、后台不可用原位提示与自动恢复。
- 实际执行（仓库根目录 / `web/`，候选 `6bda4d4533cde0e6890c05a7f47315637463994f`）：
  - `.venv/bin/python -m unittest tests.test_processing_worker_readiness tests.test_manual_task_engine`
    → 66 passed。
  - `npm run typecheck` → PASS。
  - `npm run test -- run src/features/operations/ManualOrganizeDialog.test.tsx src/features/library/StorageFilesPage.test.tsx src/features/operations/OperationsInventory.test.tsx`
    → 161 passed（既有 jsdom `scrollTo` 提示）。
  - `npm run build` → PASS；310 modules，产物 `index-CmzshM9b.js` 1,580.78 kB（既有大包提示）。
  - `npm run test:e2e -- library-files.spec.ts -g 'preparation|bounded discovery|multi-file intent|Organize admission'`
    → 9 passed。
  - `npm run test:e2e -- --config playwright.python.config.ts manual-organize-dialog.python.spec.ts -g 'follows the completed walk|preparation analysis refusal|pending owned file'`
    → 3 passed；`-g '101-file directory'` → 1 passed。
  - `npm run lint`、`npm run format:check`、`.venv/bin/ruff format --check mediaflow tests`、
    `.venv/bin/ruff check mediaflow tests`、`git diff --check` → PASS。
- 测试修正说明：原先真实解析恢复用例名为「analysis request as accepted」，实际匹配的是旧阶段卡
  文案，并没有证明后端受理；在 Worker 仍持有该 Task 阶段的真实窗口中，后端返回
  `analysis_rejected`（无变更）。新准备视图不再显示该阶段卡后，用例改为断言可见的拒绝说明仍出现在
  同一准备旁，并在释放 Worker 后进入原逐文件复核。该用例名称与断言变化请 B 一并核对；准备页的
  按权限分析动作本身保留。另修正 `library-files.spec.ts` 中两处早于基线的失效定位（批量摘要的
  `dt`/`dd` 与不存在的「零变更摘要」拼接文本），业务断言未降低。
- 剩余风险：Developer 未运行全量 Python/Web/E2E 和打包矩阵，按 Task 由 B 执行；未保存桌面与
  390px 截图，也未用真实 Worker 覆盖后台从不可用到恢复的浏览器旅程。来源资源库仍显示准备记录中的
  库标识（既有模型未发布名称）；准备页在后台自动关联方案期间仍可能显示后端公布的分析恢复动作，
  该动作在 Task 阶段仍被持有时会得到上述可见拒绝，而不是静默失败。
