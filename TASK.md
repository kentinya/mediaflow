# Task PATCH-20261111-1 — 元数据修正作品搜索采用当前年份

Authority: 用户反馈“整理时元数据修正作品搜索无结果，直接保存并继续分析可以识别”，
随后明确“规划一个独立修正 Task，按 B 的权限”，并于 2026-11-11 明确“激活 Task”，
正式授权本 Task 范围内的实施。按
[Development Workflow §3.1](docs/development-workflow.md#31-independent-minor-bugs) 规划，
由 B 独立复核和完成；不需要 A 新建或关闭 Slice。

```text
Task ID: PATCH-20261111-1
Task Type: STANDALONE MINOR BUG
Parent Slice: NONE
Status: PLANNED
Task Base: e9241d484e33ccb0b1a8def2ab81c17cb1a3d577
Difficulty: Medium
Test Level: T3
Planner / Reviewer: B
Implementation Authorization: USER AUTHORIZED ON 2026-11-11
```

### Authorization and accepted baseline

本 Task 从规划草案提升为正式可实施的 PLANNED Task；原 ID／Base／Goal／Scope、
Medium／T3、验收与测试分工保持。Developer 开始实施时转为 IN PROGRESS；B 独立复核，
本次激活不构成实施完成或验收通过，也不授权启动其他角色、推送、发布或部署。

Slice54 已于 2026-11-11 经独立 A Final Review **PASS / CLOSED**；Task54.1 的 B Reviewed
Head 为 `aef044e51dc91655372bf5fe39c6116da976c3b4`，Task Base 为
`6351b60433f0e79dac6f5f7150884a1fecb0da43`。完整 B 验收、B54-01–07 修正、
原始失败／限制与 Closure Packet 交接保留于
[固定 B 终审](https://github.com/kentinya/mediaflow/blob/9220f34420bc4807d4c0bbbe98cf7dece5f100dd/TASK.md#b-final-task-review)；
原 Task 计划／Developer 交接保留于 Git。A 的完整范围及独立验收见
[固定 A 终审](https://github.com/kentinya/mediaflow/blob/05b51268f60f8cc932f6c71d9cfa1efac1227b3e/SLICE.md#a-final-review--pass--closed)。
下一大 Slice 仍由 A 另行选择；本独立修正不重开 Slice54 或其他已接受 Slice。

### Goal and observed gap

修正现有 Metadata correction 的作品搜索：用户在同一文件中填写的标题、Movie／TV、
年份（含明确留空）同时支配显式搜索与后续保存分析。搜索的候选浏览仍是只读；选择候选
或保留查询后，由现有保存／重新分析生成精确摘要，再由独立确认授权整理。

实际缺口已定位：

- `web/src/features/operations/TaskItemRecoveryPanel.tsx` 的 `searchMetadata` 仅发送
  checkpoint、query、mediaType；保存决策则发送当前 correctedYear，空值为 null。
- `mediaflow/interfaces/service_api.py` 的 metadata-search 路由只接受上述三个字段。
- `mediaflow/application/task_item_recovery.py` 的 `metadata_search` 固定使用
  `review.original_year`；`strategy_test.py` 的既有修正分析使用已保存的 corrected year。
- 隔离内存假 Provider 复现：原始年份 2025、改填 2024，搜索仍发 2025 得零候选，保存后
  分析发 2024 得 MATCHED；清空年份后分析能得到候选，但是否自动匹配仍由既有阈值决定。
  未改年份的对照组仍为 NOT_FOUND。该证据证明确定的参数缺陷，尚未取得用户具体作品／
  年份，不能将所有无结果或 Provider 故障归因于此。

对应已有 `REQ-META-001/002/004/005/008/010`、`V2-OPS-012/018/019`。完整旅程见
[Manual organize](docs/product-experience.md#manual-organize)、
[当前逐文件整理弹窗](docs/product-experience.md#current--manual-organize-dialog-slice53-pass--closed)、
[任务与逐项恢复](docs/product-experience.md#tasks-results-and-per-item-recovery)；
保留 [Manual organize 架构](docs/architecture.md#manual-organize) 与现有 Provider 抽象。

### Workspace and planning preflight

- 工作区 `/Users/songzhidong/mediaflow`，分支 `main`，规划前 HEAD 与 Task Base 相同；
  工作区／Git 可写，暂存区为空，`python3 scripts/check_governance.py` PASS。
- 预存 `mediaflow/.DS_Store` 修改；未跟踪的根／docs／docs/pics／output／testdata／web
  `.DS_Store`、`.explore_adapter_block.py`、`.mgmt.log`、`.t*.log`、`15`，以及
  `output/database-reference-2026-11-01/`、`output/imagegen/slice45-task-center-v1.zip`、
  `output/organize-flow-2026-11-01.html`、`output/slice50-motion-preview/`、
  `output/slice52-task52-1/` 全部保留，不纳入本 Task 检查点。
- 已接受 Slice 的 Base／Head／状态不变，`SLICE.md`、Roadmap、Progress 不改。
- 激活前分支 `main`，HEAD `8f1a5d23a035fb2a8ffdd17e24dbcee8c2dbaeb9`；原 Base 至该
  HEAD 仅有 TASK 规划文字变更，无实施输入变化。治理检查 PASS，工作区／Git 可写、
  暂存区为空，上述预存文件原样保留；本激活检查点仅修改 `TASK.md`。

### User journey

1. 从 ResourceLibrary Files 的整理弹窗，或已有 Task 的元数据恢复进入当前文件的
   “修正作品搜索”；显示原始查询，可编辑标题、媒体类型和可留空年份。
2. 显式点击搜索，使用点击时的当前输入；填写年份就是按该年份查询，清空就是不限制年份。
   可见候选属于该文件、checkpoint 和这次查询。搜索不保存审核、不发起分析或文件执行。
3. 选中候选后保存并重新分析，或者不选候选直接保存查询并分析；沿用现有持久决策、
   Worker 和精确摘要。两条路径采用相同查询条件，但不要求候选浏览等同自动匹配结论。
4. 无效年份需纠正后搜索；真实零结果可修改条件再次搜索；Provider 失败说明搜索未完成，
   保留输入与已保存状态，允许按既有流程显式重搜。已过期／无权限的条目按原拒绝和刷新
   动作处理，不自动切换 pin、保存、继续分析或重放成功／不确定效果。

### Implementation scope and steps

生产范围为 `TaskItemRecoveryPanel.tsx`、`shared/api/api-client.ts`、
`interfaces/service_api.py`、`application/task_item_recovery.py` 及直接配套类型／测试。
必要的隔离夹具可扩展现有 `scripts/operations_inventory_harness.py`；不另建产品引擎。

1. **先固定失败用例。** 新增 `tests/test_task_item_metadata_search.py`，复用现有临时
   SQLite／已发布快照／API 夹具，使用会按 query、media type、year 返回不同结果的
   本地假 Provider。记录真实 Provider 入参，覆盖旧年份、改年、清空与未改年的对照；
   不只断言 HTTP 200 或让固定候选掩盖参数错误。
2. **贯通年份输入并保持兼容。** Web 显式搜索总是提交当前 `year: integer | null`，
   校验与现有保存语义一致，合法整数范围 1870–2100。API 接受可选 year，严格拒绝非法
   类型、布尔、非整数、越界和未知字段，拒绝发生在 Provider 调用前。显式 null 必须
   到达 Provider 为 None，不能回退原始年份；旧 API 调用省略 year 时保留原始年份语义。
   服务区分“未提供”和“明确清空”，仍由既有 MediaType 和 MetadataPolicy 决定合法类型。
3. **使结果对应当前输入。** 两种共用呈现采用同一输入处理。年份／标题／媒体类型改变
   后，对旧搜索结果及旧选中候选作必要失效；保存时不能无意携带旧查询的 Provider ID。
   沿用已有 item／checkpoint 草稿、busy 与 session 约束，晚到响应不得覆盖另一文件或
   新 checkpoint。仅修正本次搜索的上下文关联，不重构通用会话、保存或导航状态机。
4. **保留现有分析与失败边界。** 不改变保存决策、评分阈值、TV／Movie 选择、候选确认、
   精确摘要和执行授权。真实零结果与 Provider 错误分别显示；输入可纠正，搜索失败不
   修改耐久决策。Movie 的既有去年份回退、TV 的年份过滤、缓存键／TTL／刷新语义不改。
5. **补完整入口证明。** 增加一个聚焦的
   `web/tests/e2e/metadata-search-year.python.spec.ts`，使用现有真实 Python harness、
   新生产资产、临时 Local 根／SQLite 与年份敏感的专用假 Provider。覆盖 Files 弹窗和
   Task 元数据恢复；必要的夹具增量仅服务此证明，不改变其他测试的候选或全局数据。

### Acceptance criteria

- [ ] 两个 Web 入口均提交点击时当前年份；原年 2025→2024 的 TV 搜索发送 2024 并显示
      正确候选，清空后发送 null／Provider None，不再偷偷带回 2025；未改年份保持原行为。
- [ ] Movie／TV、年份上下界、初始无年份均正确；旧 API 省略 year 的兼容语义有测试。
      参数非法时返回既有有界错误，不调用 Provider、不保存决策、不创建工作。
- [ ] 修改搜索条件后不会把旧候选当成本次结果／选择保存；分页返回仍保留当前文件的
      合法草稿，另一文件和新 checkpoint 不受晚到结果污染。
- [ ] 同一输入下，候选选择→保存→分析，以及未选候选→直接保存→分析均可完成现有旅程。
      真实身份／RecognitionType 保持，原 Task pin 不变；不强制零年份自动匹配或选择首项。
- [ ] 真实零结果、Provider timeout／异常、RBAC 拒绝、stale checkpoint、blocker 已改变、
      pin／policy 不可用保持明确失败和合法后续动作，错误不伪装成零结果且不泄漏凭据。
- [ ] 单独搜索前后耐久审核／TaskItem／结果／Task 数及媒体内容无变化；选择候选与保存
      分析也不执行媒体变更。既有成功／不确定兄弟项、执行确认与 Task 交接不受影响。
- [ ] 改动限于上述查询一致性、必要结果关联及直接测试；无 schema、Provider、缓存、
      核心 pipeline、权限／pin 协议、UI 布局或执行引擎变更。

### Required tests

按 [Test levels and ownership](docs/development-workflow.md#6-test-levels) 分工。
以下为实施后命令，不是本次规划已运行结果；测试只用假服务／临时根，不连接真实 TMDB 或用户库。

**Developer — affected tests**

仓库根目录：

```sh
python3 scripts/check_governance.py
.venv/bin/python -m unittest tests.test_task_item_metadata_search tests.test_metadata_correction tests.test_metadata
.venv/bin/ruff check mediaflow/application/task_item_recovery.py mediaflow/interfaces/service_api.py tests/test_task_item_metadata_search.py
.venv/bin/ruff format --check mediaflow/application/task_item_recovery.py mediaflow/interfaces/service_api.py tests/test_task_item_metadata_search.py
git diff --check
```

若改现有 Python 夹具／测试，将实际变更文件加入上述 Ruff 命令，并运行新增／修改及直接
受影响用例。Python 新用例同时覆盖服务与真实 API 校验、只读性、pin／权限拒绝；既有
metadata 用例约束 Movie／TV、匹配阈值和修正分析结果不变。

`web/` 目录：

```sh
npm run test -- run src/features/operations/ManualOrganizeDialog.test.tsx src/features/operations/TaskItemRecoveryPanel.test.tsx src/shared/api/api-client.test.ts
npm run typecheck
npm exec eslint src/features/operations/TaskItemRecoveryPanel.tsx src/shared/api/api-client.ts src/features/operations/ManualOrganizeDialog.test.tsx src/features/operations/TaskItemRecoveryPanel.test.tsx src/shared/api/api-client.test.ts tests/e2e/metadata-search-year.python.spec.ts
npm exec prettier --check src/features/operations/TaskItemRecoveryPanel.tsx src/shared/api/api-client.ts src/features/operations/ManualOrganizeDialog.test.tsx src/features/operations/TaskItemRecoveryPanel.test.tsx src/shared/api/api-client.test.ts tests/e2e/metadata-search-year.python.spec.ts
```

Web 覆盖准确 year/null 请求、两个呈现、无效输入、真实零结果／错误、条件改变后的候选
失效、文件／checkpoint 隔离及既有 Save→analysis 顺序。Developer 通过受影响测试后交
固定候选，不承担全量 Python／Web／E2E 或发布矩阵。

**B — acceptance**

独立审查固定 Task Base..candidate，先复现改年／清空／未改年的对照，再验收上述完整
矩阵。复核 Developer 的匹配结果，新增／变更测试与失败用例不能以重复运行掩盖失败。
仓库根目录执行：

```sh
.venv/bin/python -m unittest tests.test_task_item_metadata_search tests.test_metadata_correction tests.test_metadata tests.test_processing_checkpoint tests.test_v2_manual_organize tests.test_operations_task_center
python3 scripts/check_governance.py
git diff --check
```

`web/` 目录执行：

```sh
npm run typecheck
npm run lint
npm run format:check
npm run test -- run src/features/operations/ManualOrganizeDialog.test.tsx src/features/operations/TaskItemRecoveryPanel.test.tsx src/shared/api/api-client.test.ts
npm run build
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/metadata-search-year.python.spec.ts tests/e2e/manual-organize-dialog.python.spec.ts tests/e2e/operations-inventory.python.spec.ts
```

原生证明须观察 Provider 收到的 year 与浏览器可见结果、真实保存／Worker 分析和摘要；
记录两种入口改年／清空后的状态及零媒体变更，不用 Node 固定响应替代。保存后应有精确
结果读回，已有主文件／兄弟项及最终确认／准确 Task 交接回归沿用现有用例。

T3 验收不要求无依据的整仓全量、wheel 或 Docker 矩阵；仅修改只读搜索输入与配套上下文，
不改核心 pipeline、持久协议、权限或媒体 mutation。若实际实现需要越过该边界，先由 B
重评范围与 Test Level，不以本 Task 直接授权。记录实际候选 SHA、命令／结果／失败／限制；
原始证据可留 `.git/validation-evidence/<candidate>/patch-20261111-1/`。

### Non-goals

不调查或修复所有元数据未找到原因，不新增 Provider／多语言算法、放宽评分／TV 年份限制、
修改 TMDB 回退或缓存、改变手动 ID 权限／保存协议、重试引擎／数据结构／Task 状态、
重做整理弹窗或 Task 详情、改其他规则／文件功能。不重开或关闭已接受 Slice，不修改
SLICE／Roadmap／Progress，不读取私有配置／真实媒体。本次仅激活已授权的修正实施，
不包含推送／发布／部署。

### Developer completion report

已获实施授权，尚未开始实施。Developer 交接时填写固定 checkpoint、READY FOR B REVIEW、
实际变更／决策、受影响测试结果和剩余风险；完整验收由 B 负责。

### B review result

NOT STARTED — 本 Task 已激活并获实施授权，尚未实施／验收，未授予 Task PASS。
实施后 B 独立审查精确 Base..Head 并运行验收；问题保留在同一 Task 修正。PASS 后记录
实际结果／限制并按工作流恢复简明 `NO ACTIVE IMPLEMENTATION TASK`，无需 A 关闭 Slice。
