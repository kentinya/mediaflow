# Task PATCH-20261108-3 — OpenList 元数据解耦及现有测试失败修复

Authority: 用户在本会话明确提出 OpenList `stat()/exists()` 改查目录、仅真正读取内容时
获取 115 链接，并以取链接接口恒定 405、仅目录列表及原生移动／重命名成功验证完整文件页
整理链路；先只读调查，随后授权规划本独立修正，并进一步明确授权按该草案实施。
用户进一步明确：复用 OpenList 自带缓存，不允许强制更新存储；目录查询保持 `refresh: false`。
2026-11-08 用户扩大本轮修复授权：“现有测试还有哪些失败的，这次修复要一并处理掉，
最终是全部测试变绿，包括本Task之外的”。因此当前实际失败及后续完整验收发现的既有失败
一并在本 Task 修复，不再以原 Task 边界或历史已知失败豁免；仍是已有行为的纠错，
不新增业务能力，不重开已接受 Slice。
[Development Workflow](docs/development-workflow.md) §3.1、§5–8 管理生命周期、测试与提交。

```text
Task ID: PATCH-20261108-3
Task Type: STANDALONE MINOR BUG
Parent Slice: NONE
Status: READY FOR B REVIEW
Task Base: 6db3647c7e77d54f3a49b6725c804f0794fc7fbb
Reviewed Head: cf680df6e24725ba40ada378e158d6a0e44710e5
Correction Candidate: cf680df6e24725ba40ada378e158d6a0e44710e5
Difficulty: High
Test Level: T4
Planner / Reviewer: B
Development Authorization: IMPLEMENTATION COMPLETE; B REVIEW; NO TEST-TOOL DEVELOPMENT
```

## Goal and observed gap

恢复已有 OpenList 属性查询的纯元数据语义，使不需要读取内容的同一 Storage 原生
Move／Rename 路径不因下载链接不可用而在提交、分析、执行前检查或执行后校验阶段失败。
普通文件属性仍是真实目录项的名称、类型、大小和修改时间；不能用“存在即成功”或省略
校验实现零取链接。

同时修正现有测试与当前合法产品旅程的实际差异及其揭示的产品缺陷；最终固定候选必须
通过全部现有适用测试和 T4 门禁，不能只验证 OpenList 或保留“Task 外失败”。

实际代码缺口：
`OpenListStorage.stat()/exists()` 调用 `HttpOpenListClient.stat()`，后者直接请求
`/api/fs/get`；`open_read()` 又依赖这个 `stat()` 获取 `raw_url`。
源证据、目标冲突、Worker 再检查和结果核验因此都可能触发取链接；原生 Move＋Rename
本身已经不流式读取媒体。HTTP 405 当前映射为 unknown，不会令属性查询自动切回目录。

本会话在上述 Base 用真实适配器＋内存 HTTP Mock 复现：单文件原生移动执行阶段正常时有
7 次 `/api/fs/get`；该接口始终 405 时执行前失败；移动之后才 405 时文件已在目标，
结果为 PARTIAL／attempted_unverified。现有 `tests.test_openlist_storage` 24 项通过，
但大部分使用独立 fake stat，没有覆盖 HTTP 层元数据查询与取链接的耦合。
这些是调查证据，不是未来修复的验收；未连接真实 115，也未完成本 Task 的原生 Web 验证。

对应已有合同：
`REQ-STO-002/003/005/006`、`REQ-ORG-003/004/006/008/012`、
`REQ-SAFE-001–007/009`、`V2-OPS-010/017`、`V2-FILES-005/006`。
完整旅程参见 [Real Storage Files / Manual organize](docs/product-experience.md#real-storage-files)；
边界参见 [Storage abstraction](docs/architecture.md#storage-abstraction)、
[Files / Manual Organize authority](docs/architecture.md#ui-v2-files-and-manual-organize-authority-update--2026-09-13)。
本修正不重开已接受 Slice，不改 SLICE／Roadmap／Progress 或上述产品合同。

### User journey

- 入口／可见状态：用户进入文件页，浏览 OpenList ResourceLibrary 的真实目录，选择有界
  多文件或文件夹范围并提交整理；看到已有 durable Task、发现／稳定性／分析状态和精确摘要。
- 行动／成功：在同一 Storage ID 内按真实计划确认原生移动，Worker 完成移动与必要重命名，
  核验目标属性和源不存在，持久化每项 Result；文件页刷新和任务详情读回实际成功结果。
- 失败／恢复：列表读取、分页、权限、源变化、目标冲突、移动／重命名及结果核验的真实失败
  仍走现有每项状态和允许的恢复。执行前失败不由本任务修改源；已完成或不确定的效果不得
  自动重放，成功兄弟项不因其他项失败重跑。刷新／重复读回不提交第二次整理。

### Implementation scope and steps

产品改动以 `mediaflow/infrastructure/openlist_storage.py` 为主；复用 Storage port、
生产业务服务及现有原生 Move＋Rename。必要的新测试／隔离夹具在本 Task 内，不以固定
文件数代替行为边界。若现有测试 HTTP 夹具不满足真实分页／目录存在语义，仅作必要对齐。

1. **先建立 HTTP 层失败复现。** 在真实 HttpOpenListClient＋OpenListStorage 下记录所有
   请求，`/api/fs/get` 固定返回 HTTP 405；不得用 FakeOpenListClient 的独立 stat 替代。
   同时覆盖 HTTP 200／业务 code 405，以防只针对某种错误映射绕过。
2. **客户端 stat 仅用目录列表。** 普通条目按父目录分页查找精确 basename，沿用配置页长、
   DTO 校验、超时、重试和并发边界。目标可在第二页以后；名称含中文、空格及边界空白不
   改写。找到后即可返回真实目录项属性，不要求继续扫描剩余页；未找到时，只有完整、有效
   的遍历确认缺失才据此报 NOT_FOUND。父目录明确返回 NOT_FOUND 时沿用既有映射。
   未找到且遍历未完成时的页失败、总数表明仍有条目却返回空页等不能当作“不存在”；
   不得回退 fs/get。
3. **处理配置根与路径边界。** 配置根（包括空 rootPath、`/` 和非空挂载根）通过列自身
   验证目录可访问，不越界列配置根的父目录。根无自身条目时可沿用 S3 根目录的目录合成
   约定（size=0、固定 UTC epoch 作为未知 mtime 占位）；不使用当前时刻伪装远端修改时间，
   不将合成根属性当作普通文件版本／稳定性证据。服务端报告不存在、非目录、无权或返回
   格式错误时仍失败，不用合成属性掩盖错误。
4. **内容读取单独取链接。** `open_read()` 显式调用 fs/get 解码 raw_url 并按原流式路径
   读取；不再借用 metadata stat 获取 URL。保留真正 read 的成功、无链接和错误语义。
   `exists()` 仍只将 NOT_FOUND 转 false；健康检查、Delete 类型检查和上传的 absent
   检查通过同一 metadata stat 自然获益，不给业务层增加 OpenList 分支。
5. **保留真实结果核验。** 原生移动／重命名及相关附件的源／目标检查不删减；移动后仍
   校验目标存在、大小和源消失，必要时保留既有类型证据。所有目录请求显式保持
   `refresh: false`，复用 OpenList 自带缓存；查询未命中、冲突、失败或结果核验时也不得
   改用 `refresh: true`、清缓存、调用管理接口刷新存储或以其他方式绕过缓存强制更新。
   依赖 OpenList 正常缓存生命周期及原生操作后的缓存处理，不新增目录缓存或权限要求；
   正常未命中／到期可能触发的上游目录读取不属于强制刷新，也不承诺其请求数为零。
   用于某项效果核验的必要列表证据矛盾、不完整或读取失败时，不能据此标记该效果
   verified success；沿用既有失败／效果未核验语义，不因之后无关的浏览失败撤销已持久化
   的核验结果，不通过读媒体补证或自动重放。不要求识别上游返回中不可观察的陈旧状态，
   不扩展外部修改及提供商目录可见性窗口的既有一致性保证。
6. **补完整隔离证明。** 优先扩展现有适配器测试、整理集成测试及原生浏览夹具，经真实
   生产服务、API、SQLite、Worker 与真实 OpenList HTTP 适配器验证批量结果，并从生产
   构建文件页驱动提交、摘要确认和结果读回。复用不足时可新增最小测试辅助代码，文件名、
   文件数或独立脚本不是验收条件。禁止改生产业务路径来替换真实适配器或绕开准入／权限／
   pin／fence／稳定性。

### 本轮失败修正与 Developer 开发指导

先完成以下已复现问题，再交 B 全量验收；后续发现的真实失败仍留在同一 Task。修测试时
以当前合同与真实入口为依据，保留所验证的用户结果；不能删除用例、增加 skip／重试／
固定等待、放宽超时或恢复已退役功能。仅在可复现的产品缺陷处作最小生产修正。

1. **默认 E2E 误收 OpenList 原生用例。** 在 `web/playwright.config.ts` 沿用已有 Python
   spec 的 `testIgnore` 约定排除 `openlist-metadata.python.spec.ts`；专用配置继续执行
   真实 Python／HTTP adapter／Worker 完整证明。默认 Node 假服务不具有 One／Two fixture。
2. **403 探索权限恢复。** `web/tests/e2e/deep-link.spec.ts` 的 403 用例在过滤区和列表
   错误区找到两份相同说明而触发 strict locator。将权限说明、恢复链接断言限定到实际
   错误区域；保留已认证身份、无 token 泄露、与 401 区别，以及“权限不足 → 原有换身份
   入口 → Disconnect → 连接允许读取的身份 → 探索可见”的完整恢复。
3. **Files 行菜单消失。** `web/tests/e2e/manual-operations.spec.ts:214` 从初次文件页
   对 sample.mkv 按 Shift+F10，整理菜单已出现但在点击前脱离 DOM。现有 trace 显示状态和
   文件读取均已返回后才打开菜单，不能直接归因为“数据尚未读完”。沿
   `StorageFilesPage.tsx::FileBrowseView` 与 `RowActionMenu.tsx` 核对实际 focus、菜单
   测量、页面滚动／关闭事件及初次页面切换，定位触发关闭的真实原因；必要时修正菜单
   定位／焦点交接，遵循已有 modal 的 `preventScroll` 用法。若确属测试未等待产品已有的
   可操作状态，仅等待该可见状态；不能用 sleeps、重复打开菜单或 force click 掩盖。
   保留键盘入口，最终只提交 `paths:["sample.mkv"]` 一次并进入真实对应摘要。若修改共享
   菜单，直接回归 ResourceLibrary／MediaLibrary 的菜单操作、Escape／外部滚动关闭和
   焦点返回，不能禁用正常关闭行为。
4. **任务详情陈旧断言。** `web/tests/e2e/operations.spec.ts:487` 在已结束日期筛选中打开
   精确任务，却等待旧文案“在任务中心查看该运行的详情”。当前详情已直接展示任务／操作
   记录。改验该任务的真实身份、状态、触发方式及已有详情／记录内容，关闭及浏览器返回
   后仍保持相同 view／日期／任务上下文；不把断言简化为“任意弹窗可见”。
5. **Unicode 身份用例沿用已退役 Job 批次续跑。**
   `web/tests/e2e/operations-principal-identity.python.spec.ts` 使用
   `seed-task-item-recovery-batch` 技术失败历史，期待恢复复选框、`continue-batch` 返回
   202／job_id 及 recovery-batches 404。当前这些 Job 路径明确返回 410；相邻
   `operations-inventory.python.spec.ts` 已验证技术历史只读和退役拒绝，不能修改这个
   共享 fixture 使历史条目凭空可恢复，也不能恢复旧接口／创建 Job。
   复用该文件现有“new task selection reconciles a lost admission, completes in the Worker,
   and restores the selected run”旅程，重写 Unicode 专用用例：中文身份经真实 auth/principal
   核对，文件页选择 → 真实分析与选择 → 精确摘要 → 明确确认；让真实 API 受理后丢失浏览器
   响应，核对精确 admission／执行，刷新并重新连接同一中文身份，恢复同一任务上下文，
   真实 Worker 完成并读回逐项结果。确认 POST 仅一次，刷新／重连／读回不再提交，不重复
   移动。保留身份完整值与内存 token 约束；移除的旧批次请求断言由当前受支持的确认／
   核对／非重放断言替代，而不是另造浏览器恢复协议。使用现有 Unicode 配置和独立临时
   fixture，不照搬其他 spec 的累计测试序号／前置任务数。
6. **Task 文档消费检查。** `tests.test_release_security` 要求 Task 使用模板中的两个
   `###` 测试责任标题；原 Task 使用粗体标题。本次 B 规划直接纠正文档，不改测试断言。
   Developer 后续更新 Task 时保持这两个标题。

7. **本次 B 原生任务清单复核的两项旧断言。**
   `operations-inventory.python.spec.ts:1371` 在整理成功、SQLite/API 重启、同一身份重连并
   恢复同一任务证据后，直接要求默认折叠诊断中的“持久审核计划(已捕获)”可见。按用户
   真实操作先展开该条目“技术诊断（计划、日志与审计…）”，再检查已捕获计划、C 识别
   使用 A 命名／分类、原完成步骤；保留重启后的同一任务、成功效果和 Execute 仅一次。
   `:2232` 混合任务技术失败项仍等待已替换文案“技术失败条目”。改验当前“处理失败”
   及上方“目标存储拒绝操作”的事实，同时保留技术失败／成功／不确定兄弟项不可选择恢复、
   无通用继续按钮／修复邀请、真实 Recognition／Conflict Attention 及 API 类型断言。
   不恢复旧展示、不默认展开诊断、不删除持久计划／身份／非重放验证，不改共享种子以绕过。
   先跑完整 `operations-inventory.python.spec.ts`（同一 harness 有累计旅程，不能只 grep
   第 11 项而缺少前序任务），其他实际失败同样在本 Task 修正。Developer 只负责这份修改
   spec 及直接受影响检查；修正后仍由 B 负责剩余全量门禁。各 Playwright 进程使用独立
   `--output`，同端口 harness 串行；这是 B 的执行安排，不新增产品或过程工具。

8. **设置容量旅程仍等待已删除的目录树。** B 在当前候选完整运行
   `automation-settings.python.spec.ts`：12 passed、3 failed（第 13–15 项）。三个失败分别
   停于 `:996`（共用 helper）、`:1088`、`:1168` 的 `getByLabel("目录")`；同一文件
   `:1197` 也保留该已失效等待，须一起更新。现有 Files 已显示正确 source 根目录、表格及
   Three／Four／Two 文件复选框；用当前所选库／根路径和目标文件可见可操作状态衔接，
   复用该 spec 的选择与既有 Files 整理旅程，不恢复目录树，不增加测试专用产品入口。
   必须完成并保留原三项结果：保存 1025 与 10000 后各自完整整理、真实 Worker 移动并
   读回目标；容量 1 被自动化占用时 Files 明确拒绝且零媒体效果，释放后由用户明确再次
   提交并成功；高容量下的原精确摘要在降为 1 且槽位占用后确认被拒，原文件与摘要／
   确认权限保持，拒绝不产生新执行或自动续跑。不能只把等待删掉就认定后三段通过。
   真实后续失败仍按同一 Task 纠正，不改全局共享 seed、放宽容量／权限或删减结果证明。
   Developer 跑完整该 spec（独立 harness、无 grep；前后旅程共享已发布设置）及变更文件
   ESLint／Prettier／typecheck，命令见下方；其余完整门禁仍由 B 执行。本次是既有测试
   旅程修正，无新增产品能力、状态、并发机制或架构调整。

9. **Python 3.11 无法启动。** B 经声明的矩阵完整 discovery 与已安装的
   `mediaflow --help` 实测，`OperationsRunProgress` 的 `MappingProxyType({})` 字段默认值
   在 Python 3.11 导入时被 dataclass 拒绝，118 个测试模块因此不能加载。修正
   `mediaflow/domain/operations_run.py` 中 dispositions／effect_counts／scan_progress
   三个同源默认值，采用兼容的 default_factory，保留每个实例独立、只读映射及当前字段／
   构造语义；不降低支持版本、不改状态／schema 或删测试。Developer 用 Python 3.11
   执行安装后的 CLI help、现有 `tests.test_operations_task_center`、
   `tests.test_operations_run_detail_plan_evidence`、`tests.test_operations_run_detail_log_isolation`
   及相关新增／修改验证；3.12／3.13 跑同一直接受影响检查。B 负责修正候选三版本全量。
10. **动作可读性脚本按当前页面接入和编辑卡交互验证。**
    `action-readability.python.spec.ts` 当前两项失败：返回 Connected 后在页面淡入中途
    （opacity 0.75）测稳定态对比度；另一项等待旧英文编辑标题。B 隔离诊断继续执行又
    复现编辑卡被背景列表“新建”按钮截获 hover，以及 Task Center 失败读回中途测量。
    把稳定态测量与现有页面过渡完成条件衔接，保持原 4.5／3 对比度阈值、真实 normal／
    hover／键盘 focus 和 busy／disabled 断言；编辑使用现有“编辑自动化任务”标题，
    编辑／新建均在实际 dialog 内选择可操作控件。禁止 fixed sleep、force、放宽超时、
    关闭产品动画、删除桌面／窄屏／读失败／无重放场景或更改产品调色板来掩盖同步问题。
    B 临时诊断副本仅作上述对齐后完整 7 passed，候选原 spec 仍为 5 passed／2 failed；
    Developer 正式修正原 spec 并跑完整 7 项和 TS 静态检查，不直接提交 B 的诊断文件。
11. **Docker 安全脚本分别校验当前 V1／V2 CSP。**
    `scripts/docker_release_security_smoke_test.py::V2_SAFE_HEADERS` 仍以旧的无 img-src
    CSP 同时检查 V2 和 V1；V2 已在接受的探索合同中仅允许可信图片
    `img-src 'self' https://image.tmdb.org`。按实际路由分别保留两个精确期望，不把
    V2 的图片许可加给 V1，也不以宽松包含／忽略 CSP／通配域名替代；所有其他安全头、
    canary／RBAC／零副作用／常驻 Worker／结果与日志检查保持。B 诊断副本只作上述
    路由区分后完整安全 smoke 通过；正式脚本仍失败，Developer 修正并用固定候选镜像
    跑原脚本。原生传输 lifecycle smoke 已独立通过，无需为它改产品或放宽夹具。

第 12 项测试返工安排已撤销。用户明确禁止开发测试工具，并要求以实际产品旅程判断
阻塞。当前两项运行失败未显示产品旅程受损：复制被既有版本一致性检查拒绝并显示刷新
提示；慢读编辑的已保存值检查通过，错误来自测试 route 回调。它们不作为 Developer
产品返工项，不新增夹具、拦截器或测试工具。完整失败和独立通过的记录均保留；先前
“全部测试变绿”的要求不被改写为已经满足。

关联合同补充：`V2-AUTH-001–003`、`V2-SAFE-001`、`V2-OPS-001/004/005/007/008/012/014–017`；
完整 Task／结果／四类恢复旅程见 [Tasks, results and per-item recovery](docs/product-experience.md#tasks-results-and-per-item-recovery)。
无新状态、权限、恢复类型或 schema；技术历史、已完成与不确定效果仍按当前合同处理。

### Acceptance criteria

下述完整旅程零取链接／零内容读取、仅原生 Move／Rename 的断言适用于明确配置的 405
核心场景；NFO 解析、Hash 或跨 Storage 流式传输等真正内容需求保持既有语义。元数据
stat／exists 不取链接、不读内容，以及不强制刷新存储的约束不因场景而放宽。

- [ ] 所有 metadata-only stat／exists（文件、目录、配置根、缺失项）不请求 fs/get，
      不访问 raw_url／代理下载／其他内容端点；health 的既有 ping 可保留。
- [ ] HTTP 请求台账检查端点及请求体：所有 OpenList 目录请求显式为 `refresh: false`；
      正常与失败路径均无 `refresh: true`、清缓存、管理接口刷新存储或其他强制更新／绕过缓存
      请求。结果核验同样遵守此约束，不以强制刷新换取成功。
- [ ] 精确属性、跨页找到、完整缺失、空目录、合法根与路径约束正确。列表权限、超时、
      限流、非法 DTO 和中途页失败保持正确错误及有限请求，不吞错、不循环、不误报缺失。
- [ ] 显式 read 仍取链接并流式读取；链接 405 时 read 正常失败。NFO 解析、Hash 检测、
      跨 Storage 流式传输等真正内容需求保持原语义，不能为了零请求偷偷关闭产品功能。
- [ ] 405 核心场景使用同一 Storage ID，预置完整目标目录，Hash=none、无待解析 NFO、
      关闭源目录清理和无需回滚的正常成功路径；业务规则／元数据使用本地确定性夹具。
      媒体端仅允许 `refresh: false` 的 list／native move／rename 成功（另放行既有 health ping），
      其他内容、上传、复制、删除和建目录端点记录并拒绝。fs/get 即使收到请求也始终返回 405。
- [ ] 在真实 HTTP 适配器的同一 405 夹具下分别验证：仅移动（换目录、名称不变）、仅
      重命名（目录不变）以及同时移动并重命名；每条路径都完成属性核验，取链接和内容
      读取请求数均为零。可复用同一夹具／批次覆盖，不要求三套重复的完整浏览旅程。
- [ ] 从真实文件页浏览和至少两个主文件的有界提交，经现有 durable Task／实际稳定性、
      完整分析、精确摘要、显式确认、Worker 执行、逐项结果核验到刷新／任务详情读回全部
      完成，至少一项同时换目录和改名。Task flow 与各主文件的成功及 effect certainty
      分别有证明，不能只断言 completed。
- [ ] 对上述完整正常旅程，OpenList 取链接及文件内容端点的请求数均为零（包括 fs/get、
      raw_url／代理下载），不限制正常业务 API／元数据夹具／静态资源请求；确认之前媒体
      mutation=0；最终只有精确授权的 Move／Rename，各项源消失、目标大小正确，结果
      已持久化；刷新、重复结果读取及再次 Worker poll 不增加 mutation。
- [ ] 对受影响条目，未解决或未获授权的目标冲突、按现有源版本证据观察到的缺失／不匹配，
      在该项 mutation 前拒绝；不新增对任意元数据字段变化的拒绝规则。在既有能力与权限
      允许时，Skip／Rename／显式授权 Overwrite 保持现有策略语义，不要求全批次失败。
- [ ] 对实际执行原生 Move／Rename 且源目标路径不同的条目，目标不存在／类型或大小不符、
      原路径仍存在，或必要的执行后列表证据读取失败，不能标记该文件效果已核验成功。
      Skip／NoOp 按原结果及零 mutation 语义判断，不要求源消失；后续浏览失败不改写已核验
      的持久化效果。重命名失败保留现有补偿与不确定效果规则，批量一项失败不重放已成功
      兄弟项；现有故障语义及 C→A RecognitionType 身份回归不被放宽。
- [ ] 生产变更未扩大 Storage 能力、隐式 overwrite／delete／copy fallback、授权、
      配置／schema／Task 状态；测试不访问真实网盘、TMDB、用户媒体、运行数据库或私有凭据。
- [ ] 上述默认 E2E 的四项和 Unicode 原生测试全部通过；文档消费检查通过。权限恢复、
      初次键盘菜单、精确任务详情及中文身份失响应后的核对均有完整旅程证明。
- [ ] B 对最终固定候选完成完整 Python、Web unit、默认 E2E、全部既有 Python 原生
      browser specs、质量／构建／wheel／适用 Docker 与安全门禁，失败为零；新发现失败
      一并修复，不以 Base 已有失败豁免，不通过删测／跳过／缩小发现范围取得绿色。
- [ ] 原生用例按现有专用配置执行；从默认 Node 发现清单排除不等于跳过。必需门禁未跑
      或环境不可用时仍为 pending，不能宣称“全部测试变绿”。七项专用真实外部／耐久环境
      测试的现有 skip 单独列出；不伪造环境或凭据，也不以离线绿色冒充这些验证已执行。

字幕及其他附件属于已有行为的相关回归，由现有附件测试及直接受影响用例覆盖；不要求为
405 核心场景额外准备字幕，也不将独立字幕证明作为新增完成条件。发现本修改引入的附件
回归仍须在本 Task 修复。

### Required tests

按 [测试等级与分工](docs/development-workflow.md#6-test-levels)：
Developer 只跑新增／修改及直接受影响验证；B 对固定候选独立验收并完成 T4 全量门禁。
优先在已有入口补用例；实现后在本节及交接中写明新增／修改测试和最终原生浏览入口的
准确命令。以下是已存在的受影响测试命令，不代表新用例或完整浏览证明已经通过。

### Developer — affected tests

仓库根目录；已经通过且本轮未受影响的模块不机械重跑：

```sh
.venv/bin/python -m unittest tests.test_openlist_storage
.venv/bin/python -m unittest tests.test_storage_browser tests.test_storage_setup_check tests.test_runtime_storage_configuration tests.test_scanner
.venv/bin/python -m unittest tests.test_manual_organize_preview tests.test_manual_organize_execution tests.test_v2_manual_organize tests.test_organizer tests.test_attachments
.venv/bin/python -m unittest tests.test_direct_file_operations tests.test_direct_file_transfers
.venv/bin/ruff check mediaflow/infrastructure/openlist_storage.py tests/test_openlist_storage.py
.venv/bin/ruff format --check mediaflow/infrastructure/openlist_storage.py tests/test_openlist_storage.py
.venv/bin/python scripts/check_governance.py
.venv/bin/python -m unittest tests.test_release_security
git diff --check
```

将其他实际修改／新增的测试和夹具加入 changed-file check，并运行对应准确测试命令；
不因此把整个仓库全套交给 Developer。上述模块覆盖属性查询、root、发现／稳定性、准入
再检查、executor／附件和普通文件命令等同一 stat 的消费者。

本轮在 `web/` 执行实际失败／修改用例，已有 OpenList 模块未改则复用相同输入的通过结果：

```sh
npm run build
npm run test:e2e -- --list
npm run test:e2e -- tests/e2e/deep-link.spec.ts tests/e2e/manual-operations.spec.ts tests/e2e/operations.spec.ts
npm run test:e2e -- --config=playwright.python.unicode-principal.config.ts tests/e2e/operations-principal-identity.python.spec.ts
npm run test:e2e -- --config=playwright.openlist-metadata.python.config.ts tests/e2e/openlist-metadata.python.spec.ts
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts --output=test-results/inventory-correction
npm run test:e2e -- --config=playwright.python.automation.config.ts tests/e2e/automation-settings.python.spec.ts --output=test-results/settings-correction
```

若修改共享文件菜单，再运行
`npm run test -- run src/features/library/StorageFilesPage.test.tsx src/features/library/MediaLibraryFilesPage.test.tsx`
及实际受影响的既有菜单浏览用例；修改其他代码则补充其直接受影响测试。对实际变更 TS／
TSX 文件运行现有 ESLint／Prettier，对 TS 变更运行 typecheck；不把全套 Web unit／全量
E2E 交回 Developer。保留默认发现清单中普通测试，证明 OpenList 专用用例仍在专用入口运行。

在 `web/` 运行 `npm run build`，通过复用／扩展的原生浏览入口完成 405 核心旅程，并在
交接前补齐该入口的准确运行命令。该证明使用当前构建、临时配置／SQLite、本地 HTTP
OpenList 与本地元数据夹具和真实 Worker；请求台账覆盖启动／浏览至最终读回，最终报告
不可仅统计 executor 阶段。保存脱敏结果／截图和计数到
`.git/validation-evidence/<candidate>/openlist-metadata/`，不写用户配置，不把“脚本退出
0／SKIP”当作已完成核心证明。

### B — independent acceptance / full regression

1. 审查固定 Task Base..candidate 的完整 diff；先独立重现 HTTP 405 核心场景及故障反例，
   用上述 focused 模块／browser proof 检查 HTTP 台账、真实文件状态和持久化结果。
   用户已进一步要求“一次性查完”：发现失败继续完成其余独立入口，最终一次汇总；
   修正仍在同一 Task，诊断副本结果与候选正式结果分开。
2. 对真实候选执行 [shared full gates](docs/development-workflow.md#shared-full-regression-commands)
   的 Python 全量、质量／依赖／示例／禁用依赖、Web 全量检查／构建／E2E、wheel／外部安装
   smoke 及适用安全回归；这次 Storage T4 不能按“只改一个适配器”降为 T2 或省略全量。
   用户已要求本次修复所有现有失败；历史失败不再豁免。保留七项专用环境 skip 的真实原因，
   不新增跳过，也不把它们记为已通过。Python 已声明 3.11／3.12／3.13 的现有 CI 矩阵按
   原入口验证，复用须满足工作流的候选／输入一致性要求；不为触发 CI 擅自 push。
3. Docker resident OpenList 消费链属于适用门禁；构建固定候选的唯一镜像后运行：
   `docker build -t mediaflow:patch-20261108-3 .`；
   `.venv/bin/python scripts/docker_files_transfer_lifecycle_smoke_test.py --image mediaflow:patch-20261108-3`；
   `.venv/bin/python scripts/docker_release_security_smoke_test.py --image mediaflow:patch-20261108-3`。
   旧 HTTP 夹具如因合法分页／root 语义不完整而失败，修正其模拟语义并复验，不放宽产品断言。
   Docker 不可用或必需核心证明未执行，保留 pending／限制，不称该门禁 PASS。
4. 记录候选 SHA、实际命令／结果／跳过、构建身份和稳定证据路径。无 UI 变更不增加全站
   视觉重设计验收；原生文件页的可用提交、明确状态及结果读回仍必须实际查看。

全部 16 份既有原生 Python specs 都须验收，不能以默认 Node E2E 已绿代替。下表名称均为
`web/tests/e2e/<name>.python.spec.ts`，在 `web/` 使用
`npm run test:e2e -- --config=<config> tests/e2e/<name>.python.spec.ts`；按既有夹具隔离要求
运行，必要时每个 spec 启动新 harness。automation 与 direct-files 共用 4185，不并发。

| 现有配置 | spec 名称 |
|---|---|
| `playwright.python.config.ts` | `action-readability`、`storage-dialog`、`task-flow`、`operations-inventory`、`operations-task-center-visual`、`organize-source-history`、`live-files` |
| `playwright.python.automation.config.ts` | `automation-create-dialog`、`automation-lifecycle`、`automation-run-once`、`automation-settings`、`automation-workspace` |
| `playwright.python.unicode-principal.config.ts` | `operations-principal-identity` |
| `playwright.direct-files.python.config.ts` | `direct-files` |
| `playwright.python.explore.config.ts` | `explore` |
| `playwright.openlist-metadata.python.config.ts` | `openlist-metadata` |

本工作区预存未跟踪 `.explore_adapter_block.py` 语法错误会阻断根目录 ruff。B 在干净的
固定候选 checkout 执行 shared 原命令，原工作区文件原样保留；不能修改 lint 规则或把
未跟踪调查文件纳入修复来取得绿色。Docker、外部环境及未运行门禁的筹备／证据仍由 B
负责，只有实际代码／夹具缺陷交 Developer。每轮先核对交付和真实差异，再跑必要验证；
测试占用时间低于本轮有效工作时间的 50%，不靠重复验证或无效等待满足比例。

### Non-goals

不新增 Provider／Storage 操作、下载产品、缓存／限速／队列系统、自动风控重试、批量并发
优化、文件内容验证策略或新的恢复类型；不关闭已有 NFO／Hash／跨 Storage 读取能力。
不强制刷新存储、清缓存或绕过 OpenList 缓存，不增加识别不可观察陈旧缓存的要求。
不新增业务流水线或 UI 能力，不修改 schema、Active 发布合同、权限或 effect certainty 语义；
现有 UI 缺陷及其测试修正限于已授权的失败旅程。
不修复／迁移已失败的生产任务，不自动重放已移动或不确定项，不连接真实 115 做压力测试。
不改 Slice52、SLICE／Roadmap／Progress，不扩大至独立性能优化或与失败无关的清理重构。

### Workspace / checkpoint boundary

规划起点：`main`，HEAD 即 Task Base；规划前 `python3 scripts/check_governance.py` PASS，
暂存区为空，工作区与 Git 可写。预存已跟踪修改 `mediaflow/.DS_Store`，另有未跟踪系统
元数据、调查脚本、日志、`15` 及 `output/` 材料；全部保留，本次只 checkpoint TASK.md。
此前两项独立修正的 Base／接受身份、Slice52 已关闭状态与所有历史验证限制保留于 Git。

### Developer completion report — reviewed candidate

以下为已审候选的原实现报告；当前状态仍为 **FIX REQUIRED**。后续 Developer 应在同一
Task 的新 checkpoint 更新修正交接，不以这份原报告表示新修正已完成；未自签 PASS、
未推送或发布。

修改与关键决定：

- `mediaflow/infrastructure/openlist_storage.py`：`HttpOpenListClient.stat()` 只以
  `refresh: false` 的 `/api/fs/list` 定位父目录中的精确 basename，按配置页长跨页扫描，
  UTF-8／空格／边界空白不作改写；完整遍历才确认 NOT_FOUND，页失败、非法 DTO、返回数量
  大于声明总数、仍有余量却空页均失败而非误报缺失。配置根／`/` 列自身验证可访问并合成
  size=0、固定 UTC epoch mtime 的目录项；服务端缺失、非目录、无权、格式错误不合成。
  `open_read()` 改走独立 `_get_entry()` 调用 `/api/fs/get` 解码 raw_url；元数据 stat／
  exists 不再经过该端点。未新增目录缓存、权限、强制刷新或 fs/get 回退。
- `tests/test_openlist_storage.py`：新增真实 `HttpOpenListClient`＋`OpenListStorage`＋
  有界 HTTP fixture 的覆盖，记录端点／请求体并固定 `/api/fs/get` 为 HTTP 405 或业务
  code 405；覆盖文件、目录、根、跨页、完整缺失、分页失败／非法 DTO、读取仍取链接、
  三种 native move／rename 形态和 Delete 类型检查。全部目录请求断言 `refresh: false`。
- `tests/test_media_discovery_provider_manifest.py`：目录存在改由真实 list 语义提供，
  并把生产 HTTP discovery 断言收紧为只访问 `/api/fs/list`。
- `tests/test_direct_file_operations.py`：既有生产 OpenList HTTP 重命名／删除旅程增加
  `fs/get` 零请求断言。
- `scripts/operations_inventory_harness.py`：仅新增可选 `document_mutator` 测试夹具入口，
  默认行为不变。
- `scripts/openlist_metadata_browser_harness.py`、`web/playwright.openlist-metadata.python.config.ts`、
  `web/tests/e2e/openlist-metadata.python.spec.ts`：新增真实文件页入口的 405 核心旅程。
  同一 Storage ID、预置完整目标目录、Hash=none、无 NFO、关闭源目录清理；fs/get 恒定
  405，Media 端只放行 list／move／rename 与 health ping，其他内容／上传／复制／删除／
  建目录端点记录后拒绝。落实例实际显示 One.2001.mkv、Two.2002.mkv，浏览器有界多选、
  完整分析、精确摘要、显式确认，真实 Worker 完成两项“换目录并改名”的原生 Move＋Rename；
  刷新执行页并读回持久 Result。

实际验证（仓库根目录，除非注明）：

```sh
.venv/bin/python -m unittest tests.test_openlist_storage
# Ran 32 tests, OK
.venv/bin/python -m unittest tests.test_media_discovery_provider_manifest
# Ran 2 tests, OK
.venv/bin/python -m unittest tests.test_storage_browser tests.test_storage_setup_check tests.test_runtime_storage_configuration tests.test_scanner
# Ran 48 tests, OK
.venv/bin/python -m unittest tests.test_manual_organize_preview tests.test_manual_organize_execution tests.test_v2_manual_organize tests.test_organizer tests.test_attachments
# Ran 136 tests, OK
.venv/bin/python -m unittest tests.test_direct_file_operations tests.test_direct_file_transfers
# Ran 165 tests, OK
.venv/bin/python -m unittest tests.test_source_directory_cleanup
# Ran 15 tests, OK
.venv/bin/ruff check <changed Python files>            # All checks passed
.venv/bin/ruff format --check <changed Python files>   # 6 files already formatted
python3 scripts/check_governance.py                    # PASS
git diff --check                                       # clean
```

浏览器 405 核心旅程（`web/` 目录）：

```sh
npm run build
npm run test:e2e -- --config=playwright.openlist-metadata.python.config.ts   tests/e2e/openlist-metadata.python.spec.ts
# 1 passed
```

脱敏证据写入 `.git/validation-evidence/<candidate>/openlist-metadata/`；
`openlist-metadata.json` 记录 62 次 list（全部 `refresh: false`）、4 次 move/rename、
0 次 fs/get／内容端点、2 项 Result 均为 SUCCESS／verified_complete；截图同目录。
证据不写入用户配置或凭据。

已知限制／剩余风险：

- 未连接真实 115 或真实 OpenList 做外部验证；405 核心场景使用真实适配器＋有界本地
  HTTP fixture，B 仍需独立重现并执行 T4 全量门禁、Docker resident 消费链。
- B 需判定上游 list 分页在 live 目录变化下的实际表现；本实现只保证所消费响应的完整性，
  不识别不可观察的陈旧缓存。
- 浏览器证明使用临时配置／SQLite、本地确定性元数据夹具和内置 Worker 路由；未改变产品
  业务路径。

### B review result

**复核结论更正 — 2026-11-08：四类修正通过，未确认产品阻塞；撤回此前依据两项脚本失败作出的产品 FIX REQUIRED 及第 12 项返工安排。**

完整复核 `6db3647c7e77d54f3a49b6725c804f0794fc7fbb..cf680df6e24725ba40ada378e158d6a0e44710e5`，
含原 OpenList／共享菜单交付及本轮默认值、CSP、浏览器测试修正。所有剩余门禁已继续跑完，
没有因这两项失败而停止。全部本轮正式运行来自固定干净 checkout
`/tmp/mediaflow-b-review-cf680df6`；原工作区 `.DS_Store`、未跟踪／私有材料保持。
本轮仅改 TASK，不改 SLICE／Roadmap／Progress、不推送或发布。

**两项测试失败对应的实际操作：**

- 第一次复制显示成功后立即再次复制：完整运行中源行与配置授权还未同步到同一发布，
  产品明确拒绝且没有第二次 Copy POST；`:857` 脚本却期待已经发送并丢失响应。
  台账与可见拒绝均已核对，产品走的是既有拒绝与刷新提示，没有第二次复制效果。
- 启用保存后立刻重开编辑，在慢读尚未返回时只改名保存，再正常重开：`:1343` 的延迟
  route 回调在 `:1409` 继续一个已处理请求，报告 Route is already handled 并提前结束。
  已保存的启用状态与处理上限检查通过；该错误不构成产品值或权限错误。

完整 `automation-lifecycle` **19 passed／2 failed（1.4m）**；同一候选对两项用独立新
harness 定向复验 **2 passed（7.1s）**。前次 `34be1d96` 完整 21 passed 的事实保持；
这次是新时序暴露的间歇失败，不是上轮没运行该文件。不能用复验或自动 retry 抹掉失败。
对应测试分别来自 `7fac98cb5`（2026-11-05 22:02 +08）和 `9d6b78147`
（同日 19:04 +08），本轮未改该文件。第 12 项返工指导已撤销，失败保留为测试记录。

**本轮完整验收结果（未复用旧完整套件冒充当前结果）：**

| 门禁 | 实际结果 |
|---|---|
| Python 3.11.15 完整 discovery | 2658 项，**2651 passed／7 skipped，0 failures**；546.903s；重新把当前 checkout 安装到隔离环境，installed CLI help 成功 |
| Python 3.12.13 完整 discovery | 同上 **2651 passed／7 skipped**；557.427s |
| Python 3.13.14 完整 discovery | 同上 **2651 passed／7 skipped**；546.494s |
| Web unit | **97 files／1459 passed**；283.11s |
| 默认 Node E2E | **264 passed（4.3m）** |
| 全部 16 份原生 Python specs | **190 passed／2 failed**；失败仅上述 lifecycle 两项，逐文件计数见下 |
| Ruff format／lint、compile、pip check、两个示例、禁用依赖、typecheck／lint／format／build | 通过；Ruff 383 files，3.11／3.12 也分别 compile／pip check／示例验证通过 |
| wheel 构建＋原 installed-wheel smoke | **PASS**；外部安装与消费者通过 |
| 原 Docker transfer lifecycle smoke | **PASS**；真实四服务／OpenList／首次激活及慢调用消费证明 |
| 修正后的原 Docker release-security smoke | **PASS**；精确 V1／V2 CSP、non-root／mount／RBAC／canary／真实整理／持久结果与日志，均在正式脚本执行 |

原生逐文件：action-readability **7**、storage-dialog **8**、task-flow **3**、
operations-inventory **44**、operations-task-center-visual **2**、organize-source-history **1**、
live-files **5**、automation-create-dialog **14**、automation-lifecycle **19＋2 failed**、
automation-run-once **8**、automation-settings **15**、automation-workspace **9**、
operations-principal-identity **1**、direct-files **28**、explore **25**、openlist-metadata **1**。
全部沿现有专用配置，独立输出目录，同端口串行，无新增 skip 或 retry。

原四类修正已核验：3.11 的 118 个同源导入错误全部消失，三个默认映射独立只读；容量
三个完整后半旅程通过；动作真实过渡与编辑 dialog 的完整 7 项通过；正式 Docker 安全
脚本整条旅程通过。没有将已退役目录树／旧编辑页恢复，也没有放宽权限或对比度。

**OpenList 必需效果与恢复补充亦在本轮完成：**

- 原专用 spec 通过；另用同一既有 Files spec 的 B 补充旅程验证两文件浏览／分析／摘要／
  明确确认／Worker／Result、再次 poll 无新工作、精确关联任务详情及返回 Files。
  **1 passed（7.4s）**；63 次 list 全部 `refresh: false`、4 次原生 Move／Rename、
  0 次 fs/get／内容读取，两项 `SUCCESS / verified_complete`，Task flow completed，
  返回后源消失，重复核对不增加 mutation。
- 既有真实 HTTP fixture＋生产 OpenListStorage／OrganizerExecutor 的源缺失、目标冲突、
  执行后列表失败、目标大小不符、原源仍在五类补充全部符合原合同：前两项 FAILED／none
  且零 mutation；后三项 PARTIAL／attempted_unverified，不假报成功或读取内容补证。
  B 补充源与本轮执行输入可由前轮证据准确追溯，不构成新增产品入口。

证据根 `.git/validation-evidence/cf680df6/b-final/`：各完整套件日志、安装／CLI、退出
台账、失败 traces、独立复验、原生截图／HTTP 台账、Docker／wheel 构建和结果。
Python／原生每个完整入口均实际完成；七项专用真实服务／耐久环境 skip 仍是未执行，
未连接真实 115／SMB／S3／TMDB／用户数据库。Docker 使用独立 Colima mediaflow-review
profile 和已挂载临时根；结束已停止 VM，默认 context 未改。两个正式镜像 ID 保存在
`image-ids.txt`。B 临时补充 spec 已移除，未提交产品或过程工具。

本轮没有已确认的产品返工项；不开发测试工具，不向 Developer 分派未定位的问题。
两项测试失败如实保留，不宣称全部绿色。Task 返回 B 复核状态；Slice52 关闭身份和
所有此前通过／失败记录保持于 Git。

### Developer correction report — 2026-11-08

**Status: READY FOR B REVIEW. Authorized bug acceptance remains B’s; no self-approval.**

修正范围仅限本 Task 已授权的现有失败与直接受影响回归；不重开 Slice52，不改
SLICE／Roadmap／Progress，不新增产品能力、schema、权限或恢复类型。预存
`mediaflow/.DS_Store` 及全部未跟踪调查／日志／output／系统元数据原样保留，未纳入提交。

修改与根因：

- `web/playwright.config.ts`：默认 Node 假服务配置按既有 Python spec 约定排除
  `openlist-metadata.python.spec.ts`；专用 OpenList 配置仍独立执行该真实适配器旅程。
  当前默认发现清单为 264 项／18 文件，Python spec 与 OpenList spec 均为 0。
- `web/tests/e2e/deep-link.spec.ts`：403 权限说明会同时出现在筛选选项错误区；把标题、
  权限文案和恢复链接限定到承载换身份入口的 forbidden alert，保留 401 区别、已认证
  principal、token 不泄露及“Disconnect → 允许读取身份 → 探索可见”完整恢复。
- `web/src/features/library/RowActionMenu.tsx`：真实根因是 `row.focus()` 已排队的页面
  滚动事件在菜单挂载后才派发，菜单按“任何外部滚动即关闭”规则错误卸载；不是数据未读完。
  用菜单自身测量时间过滤早于挂载的视口事件，并把首个菜单项聚焦改为
  `preventScroll`。菜单在真正挂载后的滚动／resize／Escape／外部 pointer 关闭及焦点返回
  语义不变；初次 Files 键盘菜单现在稳定可操作。
- `web/tests/e2e/operations.spec.ts`：以当前详情直接验证精确 run 身份（`run=job-005`）、
  `失败` 流程状态、`自动化` 触发方式、文件结果及操作记录区的真实空流；保留关闭和浏览器
  返回后的 view／日期／任务上下文，不再等待已退役的“在任务中心查看该运行的详情”文案。
- `web/tests/e2e/operations-principal-identity.python.spec.ts`：移除已退役 Job 批次续跑；
  改用现有 Unicode 配置与独立临时 fixture 的真实旅程：中文身份经 auth/principal 核对，
  文件页选择、真实分析、C 识别选择、精确摘要、显式确认；真实 API 受理后丢失浏览器响应，
  核对唯一 admission／执行，刷新并重连同一中文身份，Worker 完成并读回逐项 Result 证据。
  断言 Execute POST 仅一次、重连／读回不重放、源消失且目标存在，token 不进入持久存储或 DOM。
- TASK 文档的两个 `###` 测试责任标题已由 B 规划修正，本轮未改测试断言。

实际验证（仓库根目录，除注明外）：

```sh
.venv/bin/python -m unittest tests.test_release_security
# Ran 8 tests, OK
.venv/bin/python scripts/check_governance.py
# governance check: PASS
.venv/bin/ruff check mediaflow/infrastructure/openlist_storage.py tests/test_openlist_storage.py
# All checks passed
.venv/bin/ruff format --check mediaflow/infrastructure/openlist_storage.py tests/test_openlist_storage.py
# 2 files already formatted
git diff --check
# clean
```

Web（`web/`）：

```sh
npm run build
# passed
npx playwright test tests/e2e/deep-link.spec.ts tests/e2e/manual-operations.spec.ts tests/e2e/operations.spec.ts \
  --grep "403 is visibly distinct from 401|Files row admits one eligible file|inventory count card applies"
# 3 passed (2.2s)
npm run test:e2e -- --config=playwright.python.unicode-principal.config.ts \
  tests/e2e/operations-principal-identity.python.spec.ts
# 1 passed (6.6s)
npm run test:e2e -- --list
# Total: 264 tests in 18 files; 0 Python/OpenList specs in the default Node entry
npm run test -- run src/features/library/StorageFilesPage.test.tsx src/features/library/MediaLibraryFilesPage.test.tsx
# 2 files passed, 74 tests passed
npm run typecheck
# passed
npx eslint src/features/library/RowActionMenu.tsx tests/e2e/deep-link.spec.ts \
  tests/e2e/manual-operations.spec.ts tests/e2e/operations.spec.ts \
  tests/e2e/operations-principal-identity.python.spec.ts playwright.config.ts
# no findings
npx prettier --check src/features/library/RowActionMenu.tsx tests/e2e/deep-link.spec.ts \
  tests/e2e/manual-operations.spec.ts tests/e2e/operations.spec.ts \
  tests/e2e/operations-principal-identity.python.spec.ts playwright.config.ts
# All matched files use Prettier code style
```

测试执行时间低于本轮有效开发时间的 30%，未用重复运行、sleep、skip、放宽超时或 force
click 取得结果。

剩余风险／待 B 独立验收：

- Developer 未运行 Python 全量、默认 E2E 全量、16 份原生 Python specs、wheel／外部安装
  smoke、Docker resident OpenList 消费链或真实 115；这些按本 Task 仍由 B 在固定候选上
  执行，当前不声明全部绿色或 PASS。
- OpenList 核心实现本轮未改，沿用既有真实 HTTP 适配器证据；B 仍须在最终候选重跑 405
  核心、故障反例与 T4 全量。
- RowActionMenu 为共享组件；已跑两个文件页 Web unit 和键盘菜单浏览器用例，B 的完整
  E2E／原生 Files 回归还需覆盖其他菜单消费者。
- 七项专用真实 OpenList／SMB／S3 与耐久环境 skip、Docker 不可用和全部未执行门禁仍为
  pending；未伪造环境或以离线绿色替代。

### Developer correction report — 2026-11-08（原生任务清单断言）

**Status: READY FOR B REVIEW. Authorized bug acceptance remains B’s; no self-approval.**

本轮按上方第 7 项与用户“现有失败全部修复、最终全部测试变绿”的授权，只修正既有
E2E 断言及同一根因的另一处既有失败；未改产品源码、OpenList 适配器、schema、权限、
恢复语义或 SLICE／Roadmap／Progress。预存 `mediaflow/.DS_Store` 与全部未跟踪调查／
日志／output／系统元数据原样保留，未纳入提交。

修改与根因：

- `web/tests/e2e/operations-inventory.python.spec.ts:1371`：`a1b591db` 把持久审核计划
  移入默认折叠的“技术诊断”。该旅程在重启后、尚未展开诊断时直接等待计划标题。现按
  真实用户操作先点击“技术诊断（计划、日志与审计…）”，再验证“持久审核计划(已捕获)”、
  `Metadata C · Naming A · Classification A`（C 识别使用 A 命名／分类）以及持久完成
  步骤“创建目录（CREATE_DIRECTORY）、移动（MOVE）”。重启后同一任务、成功效果、
  `/tmp/`／token 不泄露与 Execute 仅一次的断言全部保留；不默认展开诊断。
- 同文件 `:2232` 混合任务：`02323640` 用业务结果说明替换旧“技术失败条目”。现验上方
  “需处理原因”的“目标存储拒绝操作。”与只读面板的“处理失败；请查看上方失败原因与
  已记录结果。”；技术失败／成功／不确定兄弟项不可选择恢复、无通用继续按钮、真实
  Recognition／Conflict Attention 及 API 类型断言保留。原
  `not.toContainText("repair the destination Storage permission")` 会命中折叠诊断内的
  DOM 文本，与产品“原始服务指引按需保留在诊断中”的既有语义不符；改为断言该原始
  指引在关闭的诊断中不可见（`toBeHidden`），既保留“无可见修复邀请”，又不删除技术事实。
- 同文件 `:2356`（B 的 run 此前中止，未执行到该用例）等待同一被替换文案。改为当前
  “处理失败；请查看上方失败原因与已记录结果。”并验证上方“安全分析中断。”；只读
  恢复边界与批处理持久状态断言保留。
- `web/tests/e2e/automation-workspace.python.spec.ts` 两处：与 `:2232` 同源，仍等待当前
  源码中已不存在的“这是一个技术失败条目”。先在候选上实际复现 2 failed，再改为当前
  事实说明与上方“存储操作未完成。”；无通用重试／继续／摘要按钮、原始 population 与
  结果不重放的断言保留。此项属用户已授权的既有失败，不新增产品行为。

实际验证（仓库根目录，除注明外；`web/` 目录执行 Web 命令）：

```sh
# 修正前复现（旧断言）：2 failed，均为等待已移除文案
npm run test:e2e -- --config=playwright.python.automation.config.ts \
  tests/e2e/automation-workspace.python.spec.ts \
  --grep "a technical record preserves original results|two technical failures retain independent evidence" \
  --output=test-results/automation-stale-reproduction

# 构建当前候选后，完整既有入口（Playwright 自动启动真实 Python harness）
npm run build                                            # built in 151ms
npm run test:e2e -- --config=playwright.python.config.ts \
  tests/e2e/operations-inventory.python.spec.ts \
  --output=test-results/inventory-correction-developer-final
# 44 passed (1.3m)，无 skip、无 retry
npm run test:e2e -- --config=playwright.python.automation.config.ts \
  tests/e2e/automation-workspace.python.spec.ts \
  --output=test-results/automation-workspace-developer-full
# 9 passed (14.3s)
npx prettier --check tests/e2e/operations-inventory.python.spec.ts \
  tests/e2e/automation-workspace.python.spec.ts      # Prettier code style
npx eslint tests/e2e/operations-inventory.python.spec.ts \
  tests/e2e/automation-workspace.python.spec.ts      # exit 0，无 findings
npm run typecheck                                    # passed
python3 scripts/check_governance.py                  # PASS
git diff --check                                     # clean
```

测试执行时间约 5 分钟，低于本轮有效开发时间（约 18 分钟）的 30%；未用 sleep、skip、
重试、放宽超时或 force click 取得绿色。构建产物来自当前工作树，最终两轮 E2E 均在重新
构建后的 `dist/` 上执行，不是早先的 22:30 旧包。

剩余风险／待 B 独立验收：

- Developer 未运行默认 Node E2E、其余 14 份原生 Python specs、Python 全量、wheel／外部
  安装 smoke、Docker resident 消费链或真实 115；这些仍是 B 在固定候选上的 T4 门禁，当前
  不声明全部绿色或 PASS。
- 本轮只改动两个既有 spec；`automation-workspace.python.spec.ts` 的修正依据是实际复现的
  2 failed 与产品当前渲染，不是推断。其余 native spec 的文案漂移未在本轮扫描／运行。
- 折叠诊断中的原始英文服务下一步仍是既有技术事实（按需展开），不是用户可见的修复邀请；
  B 如认为需改变该产品呈现，应另立范围，本轮不擅自改 UI。
- 七项专用真实环境 skip、Docker 不可用及未执行门禁继续 pending，未伪造环境或用离线
  绿色替代。

证据：修正前 `automation-workspace` 2 failed 的 trace 与 error-context 已在
`web/test-results/automation-stale-reproduction/` 复现，并复制到
`.git/validation-evidence/<candidate>/inventory-assertions/`（脱敏、仅本机）；最终通过运行
的命令、计数与无 skip／retry 的事实见上表和本轮交接，不用重复运行制造日志。

### Developer correction report — 2026-11-08（3.11 启动、容量旅程、可读性同步与路由 CSP）

**Status: READY FOR B REVIEW. Authorized bug acceptance remains B’s; no self-approval.**

本轮按上方第 8–11 项修正 B 一次汇总的四个根因；不重开 Slice52，不改 SLICE／Roadmap／
Progress，不新增产品能力、schema、权限、恢复类型、skip 或超时放宽。预存
`mediaflow/.DS_Store` 与全部未跟踪调查／日志／output／系统元数据原样保留，未纳入提交。

修改与根因：

- `mediaflow/domain/operations_run.py`：`OperationsRunProgress` 的 dispositions／
  effect_counts／scan_progress 仍以 `MappingProxyType({})` 作为字段默认值；Python 3.11 的
  dataclass 拒绝该不可接受默认值，`mediaflow --help` 与 118 个测试模块在导入阶段即退出。
  三个同源默认值改为 `field(default_factory=_empty_counts)`；每个快照仍得到各自独立的
  只读空映射，字段集合、构造语义、不可变性与 repr／相等性不变。未降低支持版本、未改
  状态／schema。
- `tests/test_operations_run_progress_defaults.py`（新增）：把该契约固定为与解释器版本无关
  的回归用例——默认计数为空、只读（写入 `TypeError`）、每个实例独立，且三个计数字段
  确实声明了工厂默认值，避免同一写法再次以 3.11 导入失败的形式回归。
- `web/tests/e2e/automation-settings.python.spec.ts`：四处 `getByLabel("目录")` 等待的是
  已删除的旧侧栏目录树。改为等当前 Files 入口实际渲染的所选库文件表格
  （`role=table`）与精确目标文件复选框（`选择 Two.2002.mkv` 等）可见后再操作；原三项
  容量旅程（保存 1025／10000 后各自完整整理、容量 1 被占用时拒绝并释放后成功、旧摘要
  在降容后确认被拒）一字未减，未改共享 seed、容量或权限。
- `web/tests/e2e/action-readability.python.spec.ts`：新增 `expectSettledSurface()`，在
  `expectSurfaceReadable()` 起步处等待产品自身页面／内容／卡片入场过渡回到静止值
  （`.mf-page-surface`、`.mf-content-settle`、`[role=dialog]` 的 opacity 均为 1），不关闭、
  不缩短动画，也不使用固定 sleep；对比度阈值仍为 4.5／3，normal／hover／键盘 focus 与
  busy／disabled 断言保留。编辑卡标题改为当前真实卡片「编辑自动化任务」并断言其为
  dialog；编辑与新建的主／次操作均在各自 dialog 内选取，背景列表的「新建」不再截获
  hover。读回失败与 Connected 返回后的稳定态测量因此落在操作员实际看到的一帧上。
- `scripts/docker_release_security_smoke_test.py`：原先一个 `V2_SAFE_HEADERS` 常量用 V1 的
  无 img-src CSP 同时校验 V1 与 V2。拆为共享安全头 `STATIC_SAFE_HEADERS` 与按路由区分的
  `V1_STATIC_CSP`／`V2_STATIC_CSP`；V2 精确包含探索合同批准的
  `img-src 'self' https://image.tmdb.org`，V1 保持历史策略不变，未使用包含判断或通配域名。
  其余 canary／RBAC／零副作用／常驻 Worker／结果与日志校验未改。

实际验证（仓库根目录，除注明外；Web 命令在 `web/`）：

```sh
# Python 3.11.15（B 已建的同源解释器环境，运行当前工作树）
PYTHONPATH=/Users/songzhidong/mediaflow /tmp/mediaflow-review-py311/bin/mediaflow --help   # 正常输出用法
/tmp/mediaflow-review-py311/bin/python -m unittest \
  tests.test_operations_run_progress_defaults tests.test_operations_task_center \
  tests.test_operations_run_detail_plan_evidence tests.test_operations_run_detail_log_isolation
# Ran 42 tests, OK (3.0s)
# 3.11 下导入全部现有测试模块：imported 149/149 test modules（原 118 个导入错误消失）
/tmp/mediaflow-review-py312/bin/python -m unittest <同上四模块>   # Ran 42 tests, OK (3.0s)
.venv/bin/python -m unittest <同上四模块>                          # Ran 42 tests, OK (3.0s；3.13.14)
.venv/bin/ruff check mediaflow/domain/operations_run.py \
  scripts/docker_release_security_smoke_test.py tests/test_operations_run_progress_defaults.py
# All checks passed
.venv/bin/ruff format --check <同上三文件>        # 3 files already formatted
.venv/bin/python -m unittest tests.test_release_security   # Ran 8 tests, OK
python3 scripts/check_governance.py                        # governance check: PASS
git diff --check                                           # clean

# Web
npm run build                                              # passed
npm run typecheck                                          # passed
npm run test:e2e -- --config=playwright.python.config.ts \
  tests/e2e/action-readability.python.spec.ts --output=test-results/action-readability-developer-final
# 7 passed (26.3s)，无 skip／retry；原 5 passed／2 failed
npm run test:e2e -- --config=playwright.python.automation.config.ts \
  tests/e2e/automation-settings.python.spec.ts --output=test-results/settings-correction-developer
# 15 passed (20.3s)，无 skip／retry；原 12 passed／3 failed，且四处旧等待所在旅程全部执行
npx prettier --check tests/e2e/action-readability.python.spec.ts \
  tests/e2e/automation-settings.python.spec.ts             # All matched files use Prettier code style
npx eslint tests/e2e/action-readability.python.spec.ts \
  tests/e2e/automation-settings.python.spec.ts             # exit 0，无 findings
```

Docker（本轮实际启动 Colima `mediaflow-review` profile，用当前工作树构建并按原脚本执行）：

```sh
docker build -t mediaflow:developer-patch-20261108-3 .
# 成功；镜像 ID sha256:3037d73a291d7735fbd5e1165dc104ad1e262232ccfdbe33d43be1582173e99e
TMPDIR=<profile 已挂载的宿主临时目录> \
  .venv/bin/python scripts/docker_release_security_smoke_test.py \
  --image mediaflow:developer-patch-20261108-3
# Release-security smoke acceptance passed.（47.9s；含 V1/V2 静态共存与精确 CSP、
# 非 root／compose 拓扑、RBAC／canary／零副作用、常驻 Worker 消费与持久结果／日志检查）
```

测试与验证占用时间约 5 分钟（两轮浏览器 spec 53s、Docker 构建 14s 与安全 smoke 48s、
三版本受限模块约 10s、静态检查约 10s，另有首次因 Colima 未挂载默认临时目录而失败的
安全 smoke 16s），低于本轮有效开发时间的 30%；未用 sleep、skip、retry、放宽超时或 force
click 取得结果，未删除任何用例或断言。

剩余风险／待 B 独立验收：

- Developer 未运行 Python 全量、默认 Node E2E 全量、其余 14 份原生 Python specs、
  OpenList 405 核心旅程重跑、wheel／外部安装 smoke、Docker transfer lifecycle smoke 或
  真实 115；这些仍是 B 在固定候选上的 T4 门禁，当前不声明全部绿色或 PASS。
- `expectSettledSurface()` 只等待产品既有过渡的静止 opacity，不承诺上游读取何时完成；
  若某入口在未来加入新的入场动画元素，需要把它并入同一完成条件，而不是加固定等待。
- Docker 证据依赖 Colima `mediaflow-review` profile 的显式挂载：默认 `TMPDIR`
  （`/var/folders/...`）在 VM 内不可见，脚本会因 compose bind 源缺失而失败；这是本地
  虚拟化环境限制，不是产品缺陷。B 复验时须继续使用该 profile 已挂载的宿主目录作为
  临时根。
- 七项专用真实外部服务／耐久环境 skip、Docker transfer lifecycle 与全部未执行门禁仍为
  pending；未伪造环境或用离线绿色替代。

证据：`web/test-results/action-readability-developer-final/` 与
`web/test-results/settings-correction-developer/` 保存本轮两次完整浏览器运行的计数与
附件，`web/test-results/action-readability/` 保存各表面截图与实测读数；关键日志与
Docker 构建／smoke 输出复制到 `.git/validation-evidence/<本次候选 SHA>/correction-4/`
（脱敏、仅本机）。测试执行时间与命令见上表，不用重复运行制造日志。
