# NO ACTIVE IMPLEMENTATION TASK

Task51.1 — B PASS（2026-11-07）。完整已审范围
`3c8053b06c218e76084ec1c06cf57f03259da84c..9efe8ccd480b257e12eee29b9b90075ee8f809f6`，
产品实现 `de86eab84e8627c0f656e51cea66e17e8ef1baf2`。
完整 B 结论、原始失败、独立同义验证、基线复现、证据和测试时间限制见
`01f4e05d5cc03822d2e9ced3dfa91a2838990f62:TASK.md`；原计划／Developer 交接见
`9efe8ccd480b257e12eee29b9b90075ee8f809f6:TASK.md`。这些限制未被本草案改写为全绿。
Slice50 和 PATCH-20261107-1 接受身份保持，原指针继续见上述已提交 Task。

以下是本轮 B 基于现有入口与代码编写的 **Task51.2 待激活草案**，不授权实施。
已提交 Slice 的 Development Authorization 仅限 Task51.1；本轮只规划，未启动 Developer，
未改合同、Roadmap、Progress 或接受账本。激活时须明确授予本 Task 实施授权并协调合同
中的授权／Next Action 事实；不改变 Slice Base 或已接受 Task51.1 的身份。

## Task51.2 — Dashboard API／CLI、专属后端与消费者完整退出（DRAFT）

Authority: `01f4e05d5cc03822d2e9ced3dfa91a2838990f62:SLICE.md` RO-1、AC-11；
[开发流程](docs/development-workflow.md) 和 [B 指南](docs/agent-experience/task-planner-reviewer.md)。
需求：`V2-EXPLORE-001/010/011`、`REQ-WEB-002` 的 Slice51 amendment、
`REQ-WEB-006`、`REQ-API-002/003`；完整旅程与 CURRENT/TARGET 边界见
[Product Experience](docs/product-experience.md#target--v2-explore-homepage-slice51) 和
[Architecture](docs/architecture.md#target--v2-explore-homepage-slice51)。

```text
Task ID: 51.2
Task Type: SLICE
Parent Slice: 51
Status: PLANNED
Task Base: 01f4e05d5cc03822d2e9ced3dfa91a2838990f62
Difficulty: Medium
Test Level: T3
Planner / Reviewer: B
Implementation Authorization: NOT GRANTED — DRAFT ONLY
```

### Goal and observed gap

完成 RO-1 剩余退出链路。用户连接 V2 后继续浏览探索；用任务中心、自动化、通知及系统
状态查看各自已有信息。旧 Dashboard API 按普通未知路由返回 404，旧 CLI 在解析层报未知
命令；不存在跳转、别名、退役说明、空成功或新的替代统计入口。

现有真实入口／调用链（规划基线）：

| 入口 | 实际实现与待删除依赖 |
|---|---|
| `GET /api/v1/dashboard?recentLimit=10` | `service_api.py` supported_roots、GET 分支、`_dashboard_limit`、专属审计路由分类；`_ApiRuntimeBinding.dashboard` 及所有构造调用的库计数参数 |
| `mediaflow dashboard --recent-limit 5` | `cli.py` production_commands；`final_cli.py` parser、分派、`render_dashboard`、API 启动时专属计数注入 |
| Dashboard 聚合 | `domain/dashboard.py`、`application/dashboard.py`、`SQLiteTaskRepository.load_dashboard_state`；`_status_counts`、`_count_where`、`_recent_operational_failures` 和 `RecentOperationalFailure` 当前仅供该链路使用 |
| V1 `/ui/` → Connect | `operator_ui.py` Dashboard 按钮、初始 view、渲染函数和 load 分支仍调用旧 API |
| 认证／启动／安全验收 | `test_api_credentials.py`、`test_api_security.py`、`test_v2_ui.py`、`test_file_index_retirement.py`、`rules_identity_browser_proof.py`、`docker_release_security_smoke_test.py` 仍借旧入口验证其他责任 |
| review／整理／通知测试 | `test_metadata_review.py`、`test_classification_review.py`、`test_v2_manual_organize.py`、`test_v2_notification_operations.py` 仍直接消费 Dashboard；`test_dashboard.py` 是专属正向测试 |

这是尚未实施的合同结果，不是重新否定 Task51.1。只读删除不改变权限语义、Active、schema、
媒体执行或队列；如实施发现必须改变这些边界，先交 B 重评等级／A 决策。

### Implementation scope and developer guidance

1. **先沿现有入口核对引用，再删除整条专属链路。** 从表中 HTTP、CLI 和 V1 默认读取
   向后核对调用者，删除 API 注册／处理／专属 query 校验／审计分类、CLI 注册／分派／
   参数／渲染、domain/application 和 SQLite 专属聚合。三个 helper 删除前再次检查引用。
   不保留改名服务、空对象或兜底返回，不为退役入口新增防御分支。
2. **同步修改全部 runtime binding 构造路径。** 包括 API 初始构造、managed Active 重绑
   和 `final_cli.py` 启动注入；`_ApiRuntimeBinding` 当前使用位置参数构造，删除字段时核对
   后续 files/direct-files/transfers/settings 等字段仍对应正确值。保留共享初始化和原 pin，
   不改其他模块来迁就删除，不清表／迁移／删除运行记录。
3. **V1 只断接。** 移除 Dashboard 按钮／默认读取／渲染，复用现有 Configuration 视图作为
   初始 view 与选中按钮，使 Connect 后仍可使用已有配置界面；保留 readiness 对 setup／
   recovery 的原处理。不要调用另一统计接口冒充 Dashboard，不新增 V1 探索或重设计其他视图。
4. **按原验证目的改接探针。** 身份／401／403／审计与静态资产旁的认证读取优先改接已有
   `GET /api/v1/auth/principal`（READ、零 Provider、零媒体工作，已有独立权限测试）。
   FileIndex 的“正常 CLI 打开临时库后没有 FileIndex 表”改用已有 `tasks list` 等正常
   有界读取，并核对其实际参数；不要改成未知命令失败后检查未创建表。Review 原状态和
   通知失败／精确 delivery 的证据改查各自已有列表／详情；如果某断言仅为旧 Dashboard
   专属聚合则随产品删除，不能借机删掉决策持久化、权限、脱敏或零副作用断言。
5. **补充退出验收并修订直接受影响说明。** 可将 `tests/test_dashboard.py` 改成退役测试，
   删除旧正向 fixture。部署／发布操作说明使用探索、受支持的认证探针及各自状态页；
   `v2_ui.py` 的受支持深链示例改成探索。旧 Web 路径的负向测试可以保留。CURRENT/TARGET
   的整体转正留给 A 最终接受，历史文档／旧接受事实不改。用生产 Web 资产验证保留的首页。

### Acceptance criteria

- [ ] 正常配置、合法 READ 身份下，先调用受支持接口得到 200，再请求现有旧 API 及
  `?recentLimit=10`；均得到与普通未知路由相同的 404／`not_found`，没有兼容响应。
  原查询不再进入 Dashboard 参数解释，公共认证／审计保留；无身份仍按现有全局规则。
- [ ] 安装入口的顶层 help 不再注册 Dashboard；`mediaflow dashboard` 和带原
  `--recent-limit 5` 的命令在解析阶段以未知命令拒绝。相同临时配置下 `tasks list` 成功；
  不以配置错误、权限错误或仅非零退出作为注销证据。
- [ ] 代码引用确认专属模型／服务／repository 查询／helper／注入和可达消费者全部删除；
  旧请求无 Provider、媒体 Storage、任务准入、配置发布业务效果。公共初始化／审计不被
  误判为业务变更；共享 CSS、历史文本和负向测试无需清掉 dashboard 字符串。
- [ ] V1 打开 → Connect → 已有 Configuration 内容可读；Dashboard 按钮／请求消失。
  配置读取失败仍显示原错误并能按现有 Connect／导航重读；断开仍清空身份。只验这条窄链路。
- [ ] 正常启动与同版本 Active 绑定切换后，探索／任务／自动化／通知／系统状态已有读取
  正常；临时 SQLite 中已有 Task／Result／review／notification／audit 记录保持可读。
  不引入 schema 变更或改变任务状态、四类恢复、结果与非重放语义。
- [ ] 所有改接探针仍证明原权限／脱敏／有界读取／零媒体效果责任；真实 Python＋生产
  资产的探索“浏览 → 筛选／搜索 → 详情 → 返回”保持，其他合法深链继续可达。

### Required tests

遵循[测试等级与分工](docs/development-workflow.md#6-test-levels)。探测只使用以上已有入口和
仓库已有夹具／本地假服务；不用用户数据库、媒体或真实 Provider。未来新增用例在交接时
给出真实名称／命令，不把本计划记作执行结果。

**Developer — 新增／修改和直接受影响测试：**

根目录，执行以下现有模块（`test_dashboard.py` 在本 Task 中改写为退役验收）：

```sh
.venv/bin/python -m unittest discover -s tests -p 'test_dashboard.py'
.venv/bin/python -m unittest discover -s tests -p 'test_api_credentials.py'
.venv/bin/python -m unittest discover -s tests -p 'test_api_security.py'
.venv/bin/python -m unittest discover -s tests -p 'test_operator_ui.py'
.venv/bin/python -m unittest discover -s tests -p 'test_v2_ui.py'
.venv/bin/python -m unittest discover -s tests -p 'test_file_index_retirement.py'
.venv/bin/python -m unittest discover -s tests -p 'test_metadata_review.py'
.venv/bin/python -m unittest discover -s tests -p 'test_classification_review.py'
.venv/bin/python -m unittest discover -s tests -p 'test_v2_manual_organize.py'
.venv/bin/python -m unittest discover -s tests -p 'test_v2_notification_operations.py'
.venv/bin/python scripts/check_governance.py
git diff --check
```

这些模块覆盖实际改接消费者，不把全仓套件交 Developer。对实际改动的存活 Python 文件
执行 `.venv/bin/ruff check <files>` 和 `.venv/bin/ruff format --check <files>`（交接列出
真实文件清单）。改动安全脚本时，从其已有 probe 函数在临时本地 HTTP 环境验证改接后的
状态、权限和 canary 断言；复用现有夹具，避免为删除入口新建验收平台。
不要求 Developer 运行全仓 Python／Web／E2E 或发布矩阵。

**B — 完整 Base..Head 独立验收和 Slice 最终证据：**

1. 完整审查 Task Base..候选，先复现 AC-11 的合法身份／正常配置对照、CLI 解析拒绝、
   代码引用退出和 V1 窄链路；独立运行上面的受影响模块及
   `.venv/bin/python -m unittest discover -s tests -p 'test_explore*.py'`、
   `test_operations_task_center.py`、`test_v2_automation_operations.py`、
   `test_system_settings_management.py`（后三项使用相同 discover 命令分别指定文件）。
   这些回归针对共享 binding 与保留统计，不要求未改动执行引擎的全量验收。
2. `web/` 执行 `npm run typecheck`、`npm run build`，再执行
   `npm run test:e2e -- --config=playwright.python.explore.config.ts tests/e2e/explore.python.spec.ts`；
   检视桌面／390px 浏览到详情再返回。沿真实 Python 入口读取任务中心、自动化、通知和
   系统状态，验证 binding 没有因位置参数删除而错配；复用已有测试入口／夹具。
3. 根目录执行 `.venv/bin/python scripts/rules_identity_browser_proof.py`，验证改接后的
   认证探针及原身份／深链目的；对安全脚本改动运行 Developer 段所述本地 probe 验证。
   对 CLI／删除模块的分发影响，由 B 执行
   `.venv/bin/python -m pip wheel . --no-deps -w <isolated-wheel-dir>`，再用精确 wheel 运行
   `.venv/bin/python scripts/wheel_smoke_test.py <exact-wheel>`；补查源目录外安装入口
   help／未知命令／正常命令及已删除模块不再打包，不能用源码副本代替 wheel。
   本 Task 不变更 Docker／服务生命周期，不要求完整 Docker 发布矩阵；改动的安全探针
   本身必须有实际运行证据，不能因未跑 Docker 就声称该脚本整体通过。
4. Slice 最终逐项重评 RO-1–4／AC-1–11；Task51.1 的证据只在源、测试、夹具、依赖和
   资产匹配时复用，执行输入变化须补跑对应验收。覆盖完整最终候选后才提交 Closure Packet，
   A 负责 CURRENT 文档协调和 Slice 关闭。遇真实 T4 影响先重评，不沿用 T3 减免安全门禁。

每轮测试／构建／静态检查累计用时必须小于该轮总用时的 50%；先审查和关键复现再安排
较长门禁，记录命令／实际耗时。时间不足时诚实报告待验收，不能裁剪必需覆盖或虚报 PASS。
B 日志／截图保留于 `.git/validation-evidence/<candidate>/`；原失败和 skip 必须保留。

### Non-goals and Slice reassessment

不增加探索功能／Provider／新统计接口，不改队列、schema、权限、媒体流水线或部署，
不修无关既有测试／业务，不机械改名共享样式，不重开已接受 Slice。

| Slice outcome | 当前结论 |
|---|---|
| RO-1 首页与完整退出 | Task51.1 完成 V2 首页；API／CLI／专属后端／V1 和探针是本草案的剩余交付 |
| RO-2 浏览／筛选／搜索／分页 | Task51.1 PASS，保留其证据和限制，最终候选需确认不回归 |
| RO-3 海报／详情／返回 | Task51.1 PASS，同上 |
| RO-4 状态／恢复／只读安全 | Task51.1 PASS，同上；本 Task 验证退出的业务效果边界 |

预期这是最后一个实现单元，满足后停止规划并交 A；当前仍不满足全部结果，不能提交
SLICE READY FOR A REVIEW。合同／Roadmap／Progress 尚有“Task51.1 未实施”的旧阶段描述，
本草案明确实际状态，不以 B 规划改写 A 的合同或接受账本；激活／最终协调时更新事实。

### Developer completion report / B review

尚未实施，无新的候选可审，未作本 Task 的 PASS／FIX REQUIRED 决定。
Developer 激活后交完整 checkpoint SHA、READY FOR B REVIEW、实际改动／受影响命令与
结果、失败／限制和剩余工作；B 独立审完整 Task Base..Head 后决定 PASS 或 FIX REQUIRED。

### Planning checkpoint

本轮基线：`main` / `01f4e05d5cc03822d2e9ced3dfa91a2838990f62`；治理检查 PASS。
预存 `mediaflow/.DS_Store` 修改、所有未跟踪 `.DS_Store`、日志、`.explore_adapter_block.py`、
`15` 和 output 调查产物全部保留、不暂存。本轮仅修改 `TASK.md`，未改产品／仓库测试，
未运行功能验收、未推送或部署。检查仅限文档／引用／治理；不把规划当成产品通过。

本轮规划检查：`python3 scripts/check_governance.py`、`git diff --check` 均 PASS；
仅有文档／引用检查，检查用时低于本轮总用时的 50%。
