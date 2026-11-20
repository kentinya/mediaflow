# Task PATCH-20261120-2 — 手动整理主文件超限后的任务收尾

Next Action: B RE-REVIEWS THE PATCH-20261120-2 FIX CANDIDATE

用户于 2026-11-20 授权激活独立 Task，当前候选经 B 审查后进入同一 Task 的返修；Developer 已完成修正，交回 B 审查（修正报告见本页末尾）。
[上一独立修复的 B 验收](https://github.com/kentinya/mediaflow/blob/66e1e799b5bc5ada7b8ea81bd15052969c40b38a/TASK.md#patch-20261120-1--b-验收-pass)

```text
Task ID: PATCH-20261120-2
Task Type: STANDALONE MINOR BUG
Parent Slice: NONE
Status: READY FOR B REVIEW
Task Base: 1323d56c71390551424b0134f3500d25f77fb9d9
Difficulty: High
Test Level: T4
Planner / Reviewer: B
Implementation Authorization: USER AUTHORIZED ON 2026-11-20
```

规划基线为 `mediaflow` 的 `main`，规划前工作区干净，Git 与工作区可写，治理检查通过。
依据 [Development Workflow §3.1](docs/development-workflow.md#31-independent-minor-bugs)、
[`V2-TASK-012–014`、`V2-OPS-010/017–019`](docs/v2-requirements.md) 和
[Files 手动整理旅程](docs/product-experience.md#current--manual-organize-dialog-slice53-pass--closed)。

### 目标和现状

用户在资源库 Files 对目录或混合选择发起整理。发现第 101 个合格主文件后，系统将任务标为准备失败，
解除本次准备的来源占用，让用户从原文件页缩小范围后重新发起。

发现服务已持久保存 `primary_limit` 和最多 100 个扫描发现，并拒绝生成可执行方案。任务引擎仍将这次发现归入等待人工。
关联任务仍在运行且没有文件条目，来源占用判定便继续保护已记录的来源。缩小范围后若选到同一文件，新请求返回 `source_already_organizing`。
[超限记录](mediaflow/application/media_discovery.py#L4113) · [任务结算](mediaflow/application/manual_task_engine.py#L267) · [来源占用](mediaflow/infrastructure/sqlite_runtime.py#L12851)

### 实施范围和步骤

1. **结算新任务。** 在 Files 关联任务的发现收尾处识别持久的 `primary_limit`，兼顾拒绝列表和旧版不完整原因字段。
   将 Task 标为 `failed`，调度标为 `settled`，记录「准备阶段超限」及结束时间。复用受版本、任务认领和控制条件保护的结算路径，
   在同一提交中发布任务终态与调度结果，由现有终态判定解除本次来源占用。保留发现、范围、配置 pin 和诊断。
   Finalize、分析、确认和执行入口拒绝这份截断清单。
2. **自动收尾旧记录。** 由驻留 Worker 对当前受支持数据库中的卡住记录做有界、幂等核对，覆盖已经停在 `waiting_human` 的任务。
   要求精确关联到 Files 手动任务，存在持久的超限停止证据，发现未冻结且无方案，任务从未受理执行，
   且无进行中、已完成或效果不明的文件操作证据。提交时在同一事务内复核关联、任务版本、执行历史和控制条件。
   发现有效认领、竞争中的控制请求或证据不足时，交给现有生命周期处理并维持来源保护。自动收尾复用失败结算，保留历史和审计。
3. **呈现原因和下一步。** 整理弹窗依据后端超限事实显示「本次未执行整理。最多支持 100 个主文件，请缩小选择范围后重新发起。」
   用户关闭弹窗回到原目录和选择，调整后提交新请求。任务中心显示「失败／准备阶段超限」，按后端终态隐藏「继续整理」。
   通过旧地址打开准备记录时只读。

### 验收条件

- [ ] 目录含 101 个合格主文件时，旧任务进入「失败」且调度结算。`primary_limit` 和扫描历史可读取，方案、执行受理和媒体变更均为零。直接调用 Finalize 也无法把截断清单变成可执行方案。
- [ ] 无需取消旧任务，在一个新小批次中选中旧记录保留的同一个文件，能成功受理并生成可确认方案。弹窗有指定提示，任务中心结束详情无「继续整理」，原准备地址只读。
- [ ] 恰好 100 个合格主文件能得到完整的待确认方案。正常待确认任务仍拦截同一来源的重复受理，实际修改仍由原有显式确认授权。
- [ ] 用当前版本已有记录模拟服务重启。可证实从未执行的旧超限任务经驻留 Worker 自动结算，重复启动或轮询保持同一结果。旧任务 ID、发现记录、配置 pin 和历史保留，重复提交旧请求仍按原身份对账。
- [ ] 自动收尾跳过已有执行受理、活跃认领、效果证据或无法证明未执行的旧记录。覆盖取消或状态竞争、结算提交失败后重试，
  并验证已完成或效果不确定的文件仍受原有防重放规则保护。

### 测试与分工

**Developer 受影响检查**

- 仓库根目录运行 `.venv/bin/python -m unittest tests.test_media_discovery.RetainedTaskKernelFilesJourneyTests tests.test_manual_task_engine.ManualTaskDiscoveryTests`。在现有类中覆盖 100/101、同一来源重新受理、旧记录重开及并发或失败注入，用临时 SQLite/Storage 核对历史和零变更。
- 在 `web/` 运行 `npm run test -- run src/features/operations/ManualOrganizeDialog.test.tsx src/features/operations/OperationsInventory.test.tsx` 和 `npm run typecheck`。检查明确提示、返回原文件页、旧任务只读及正常待确认入口。提交候选前运行 `git diff --check`。

**B 验收**

- 独立审查 Task Base 至候选检查点，用真实 API、SQLite 和 Worker 复核超限、旧任务安全收尾及竞争条件。用更新前格式的当前受支持记录验证数据库重开。
- 在 `web/` 运行 `npm run build` 和 `npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/manual-organize-dialog.python.spec.ts`。在现有原生测试中覆盖从 Files 触发超限、任务中心查看结束详情、回到 Files 用同一文件发起小批次并进入确认。
- 执行[适用的 T4 全量门禁](docs/development-workflow.md#shared-full-regression-commands)，记录实际结果和候选 SHA。

### 边界

本次使用现有 100 个主文件上限，适用资源库 Files 手动整理及其 API。可配置上限属于独立能力。
自动化／CLI 行为、其他扫描预算及普通读取失败的子集确认仍依各自现行契约。

### 交接与评审记录

```text
Reviewed Base: 1323d56c71390551424b0134f3500d25f77fb9d9
Reviewed Head: 808a020da153d9a633a3ac74dcaa0ead981e4998
Decision: FIX REQUIRED — 2026-11-20
Authorized bug acceptance complete: NO
Next: SAME TASK FIX LOOP
```

B 审查了完整 Base..Head。101 个主文件拒绝执行且同一来源可重新受理、100 个主文件生成完整摘要、旧任务重开、已取消任务和不确定效果保护共 5 项 Python 定向测试通过。Web 生产构建通过。使用真实 API、临时 SQLite、Local Storage 和构建产物复现下列两个阻塞。T4 全量验收留待返修候选。

### Developer 返修指导

1. **让打开的整理弹窗读到任务终态。** 用户从资源库选择 101 个主文件的目录并发起整理。扫描超限和任务结算分别提交。B 在真实 Worker 的结算提交前延时，浏览器读到了「扫描超限、任务运行中」，随后因已有扫描拒绝而停止刷新。后台已标记失败，原弹窗仍停留在通用超限提示。调整 `ManualOrganizeDialog` 已有的准备状态轮询。收到主文件超限且关联任务仍在运行时，继续读取同一准备记录，直到任务结束。用户看到可以缩小范围重新发起的提示时，同一来源已可重新受理。
2. **用现有位置展示准确的失败事实。** 超限任务从 Files 或既有历史地址打开时，弹窗同时声称「原计划摘要保留为只读历史」和「从未生成过计划摘要」。用超限专用提示准确说明准备阶段停止、本次没有生成方案或执行，以及如何缩小范围。任务中心结束详情的现有流程状态处保留「失败／准备阶段超限」和提示，移除新增的「文件整理准备」区。保存过方案的历史任务沿用现有只读摘要。参考 [V2-OPS-019](docs/v2-requirements.md#current--manual-organize-dialog-slice53-pass--closed)。
3. 使用现有 Python 浏览器测试覆盖从 Files 提交目录、弹窗读到扫描超限后继续读到任务失败、任务中心无准备区或继续入口、历史地址只读，以及回原目录选择同一个文件重新进入确认。增加组件断言，确保没有已保存摘要的提示。按上面的 Developer 受影响检查复跑，记录候选 SHA 和实际结果后交 B。

## Developer Completion Report — B 反馈：继续读取超限终态与准确失败事实

```text
Task Base: 1323d56c71390551424b0134f3500d25f77fb9d9
Reviewed Fix Target: f849f7df3a67b97c0adf9ca926b14c3570e6601f
Implementation Candidate: 031ac45b805360713f82fd9bc0349fcdfb86c1af
Branch: main
Status: READY FOR B REVIEW
```

**起点**

本轮从 `main`／`f849f7df`（B 的 FIX REQUIRED 检查点）开始，工作区与暂存区干净，无既存
未提交文件。实现提交为 `031ac45b`，本报告与 TASK.md 交接单独提交。

**修正结果**

1. **超限后发现与任务结算的轮询间隔。** `ManualOrganizeDialog` 的既有准备轮询新增一个
   明确条件：持久发现已有 `primary_limit`，且其精确关联的 `organizeFlow.continuable`
   仍为真时，继续以同一 1.5 秒间隔读取同一条准备记录；任务结算提交后，`continuable`
   变为假，弹窗直接进入真实结束状态。等待期间提示「正在结束关联任务」，不再让操作员在
   来源仍被占用时误以为可以立即重提交。没有新增提交入口、重试按钮或本地推断终态。
2. **准确展示超限失败事实。** 超限任务结束时只显示专用提示：本次未执行整理、最多 100 个
   主文件、检查在第 101 个合格主文件处停止、本次没有生成方案或受理执行，以及关闭返回原
   文件页缩小范围后重新发起。没有已保存摘要时不再同时声称「原计划摘要保留为只读历史」和
   「从未生成过计划摘要」；保存过方案的历史任务仍沿用既有只读摘要。任务中心保留
   「失败／准备阶段超限」和同一提示，移除新增的「文件整理准备」区；结束详情没有
   「继续整理」入口。旧 hosted 地址仅呈现只读结束事实和关闭操作。
3. **真实入口的回归证明。** 在现有 Files→整理弹窗和任务中心路径上补充组件断言与真实
   Python 浏览器旅程。新增浏览器夹具目录 `PrimaryLimit` 恰好 101 个合格主文件；harness
   仅在真实 Worker 的发现发布与任务失败结算之间增加可释放等待，未伪造阶段或产品状态。
   旅程覆盖目录提交、弹窗先读到扫描超限再读到任务失败、任务中心结束详情、旧地址只读，
   以及回到原目录选择同一 `DialogLimit.2032.mkv` 重新受理并进入确认。

**实际验证（cwd `/Users/songzhidong/mediaflow`，候选工作树）**

```text
python3 scripts/check_governance.py                                   -> PASS
git diff --check                                                      -> clean
.venv/bin/ruff format --check .                                       -> 361 files already formatted
.venv/bin/ruff check <changed Python and harness files>               -> All checks passed
.venv/bin/python -m unittest tests.test_media_discovery.RetainedTaskKernelFilesJourneyTests
    tests.test_manual_task_engine.ManualTaskDiscoveryTests            -> 51 tests OK (6.004s)
web: npx prettier --write <5 changed TS/TSX files>                    -> formatted
web: npm run test -- run src/features/operations/ManualOrganizeDialog.test.tsx
     src/features/operations/OperationsInventory.test.tsx             -> 2 files, 85 tests passed (36.85s)
web: npm run typecheck                                                -> OK
web: npm run build                                                    -> built dist (Vite, 302 modules)
web: npm run test:e2e -- --config=playwright.python.config.ts
     tests/e2e/manual-organize-dialog.python.spec.ts -g "101-file directory"
                                                                      -> 1 passed (6.5s)
```

组件覆盖包括：超限等待态继续轮询到任务结算；结束后没有已保存摘要提示、只读摘要区、
确认或重新分析入口；任务中心无准备区或继续入口。浏览器旅程使用真实的 API、SQLite、
Local Storage、Worker claim／settlement 与构建产物，未构造不存在的入口。

**剩余与风险**

- Developer 未运行 T4 全量 Python/Web/E2E、完整 `manual-organize-dialog.python.spec.ts`
  文件或 Docker／封装矩阵；这些仍按 Task 由 B 在冻结候选上验收。
- 本轮未连接真实 TMDB、SMB、OpenList 或 S3/R2；101 文件、旧记录重开、取消竞争与结算
  失败注入由现有临时 SQLite／Local Storage／模拟 Provider 测试覆盖，B 仍需用真实 API
  和更新前格式记录复核。
- 超限准备继续轮询依赖后端发布的 `organizeFlow.continuable`；若 Worker 长时间未结算，
  弹窗保持「正在结束关联任务」并允许关闭，来源保护仍由后端权威状态维持。
