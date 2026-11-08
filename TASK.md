# NO ACTIVE IMPLEMENTATION TASK

上一独立修正 **PATCH-20261108-2** 已经 B 独立验收 PASS；固定接受记录见
[`6db3647c:TASK.md`](https://github.com/kentinya/mediaflow/blob/6db3647c7e77d54f3a49b6725c804f0794fc7fbb/TASK.md)。
Slice52 保持 PASS / CLOSED，原接受 Base、Head、失败及验证限制不变。

以下是用户于 2026-11-08 授权“规划 Task”的**规划草案**。本轮只授权 TASK.md 规划及本地
checkpoint，不授权产品实施、其他代理、推送或部署。得到实施授权后，先重跑治理检查并将
本草案提升为正式活动 Task，保持同一 Task ID、Base、Goal 和 Scope；不得静默重设 Base。

## Task PATCH-20261108-3 — OpenList 元数据查询与下载链接解耦

Authority: 用户在本会话明确提出 OpenList `stat()/exists()` 改查目录、仅真正读取内容时
获取 115 链接，并以取链接接口恒定 405、仅目录列表及原生移动／重命名成功验证完整文件页
整理链路；先只读调查，随后授权规划本独立修正。
[Development Workflow](docs/development-workflow.md) §3.1、§5–8 管理生命周期、测试与提交。

```text
Task ID: PATCH-20261108-3
Task Type: STANDALONE MINOR BUG
Parent Slice: NONE
Status: PLANNED
Task Base: 6db3647c7e77d54f3a49b6725c804f0794fc7fbb
Difficulty: Medium
Test Level: T4
Planner / Reviewer: B
Development Authorization: PLANNING ONLY — IMPLEMENTATION NOT AUTHORIZED
```

### Goal and observed gap

恢复已有 OpenList 属性查询的纯元数据语义，使同一 Storage 内的原生 Move／Rename 不因
下载链接不可用而在提交、分析、执行前检查或执行后校验阶段失败。普通文件属性仍是真实
目录项的名称、类型、大小和修改时间；不能用“存在即成功”或省略校验实现零取链接。

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
  仍走现有每项状态和允许的恢复。失败前无 mutation 则保留源；已完成或不确定的效果不得
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
   改写。找到后返回真实目录项属性；只有完整、有效的查找确认缺失才报 NOT_FOUND。
   后续页失败、非空总数对应空页等不完整证据不能当作“不存在”；不得回退 fs/get。
3. **处理配置根与路径边界。** 配置根（包括空 rootPath、`/` 和非空挂载根）通过列自身
   验证目录可访问，不越界列配置根的父目录。根无自身条目时可沿用 S3 根目录的目录合成
   约定（size=0、固定 UTC epoch 作为未知 mtime 占位）；不使用当前时刻伪装远端修改时间，
   不将合成根属性当作普通文件版本／稳定性证据。不存在、非目录、无权或格式错误仍失败。
4. **内容读取单独取链接。** `open_read()` 显式调用 fs/get 解码 raw_url 并按原流式路径
   读取；不再借用 metadata stat 获取 URL。保留真正 read 的成功、无链接和错误语义。
   `exists()` 仍只将 NOT_FOUND 转 false；健康检查、Delete 类型检查和上传的 absent
   检查通过同一 metadata stat 自然获益，不给业务层增加 OpenList 分支。
5. **保留真实结果核验。** 原生移动／重命名及相关附件的源／目标检查不删减；移动后仍
   校验目标存在、大小和源消失，必要时保留既有类型证据。复用当前列表语义，不引入长期
   目录缓存或全局强制 refresh／新增权限要求。用 mutation 后变化的列表验证最新状态；
   陈旧／矛盾或读取失败的证据不能被当作 verified success，不能通过读媒体补证或自动重放。
   保留外部修改及提供商目录可见性窗口的既有限制，不承诺对任意最终一致后端原子确认。
6. **补完整隔离证明。** 新增 `tests/test_openlist_metadata_organize.py`，经真实生产服务、
   API、SQLite、Worker 与真实 OpenList HTTP 适配器验证批量结果；新增
   `scripts/openlist_metadata_organize_browser_proof.py` 复用现有原生浏览证明方式，从
   生产构建文件页驱动提交、摘要确认和结果读回。允许最小测试夹具辅助，禁止改生产业务
   路径来替换真实适配器或绕开准入／权限／pin／fence／稳定性。

### Acceptance criteria

- [ ] 所有 metadata-only stat／exists（文件、目录、配置根、缺失项）不请求 fs/get，
      不访问 raw_url／代理下载／其他内容端点；health 的既有 ping 可保留。
- [ ] 精确属性、跨页找到、完整缺失、空目录、合法根与路径约束正确。列表权限、超时、
      限流、非法 DTO 和中途页失败保持正确错误及有限请求，不吞错、不循环、不误报缺失。
- [ ] 显式 read 仍取链接并流式读取；链接 405 时 read 正常失败。NFO 解析、Hash 检测、
      跨 Storage 流式传输等真正内容需求保持原语义，不能为了零请求偷偷关闭产品功能。
- [ ] 405 核心场景使用同一 Storage ID，预置完整目标目录，Hash=none、无待解析 NFO、
      关闭源目录清理和无需回滚的正常成功路径；业务规则／元数据使用本地确定性夹具。
      媒体端仅允许 list／native move／rename 成功（另放行既有 health ping），其他内容、
      上传、复制、删除和建目录端点记录并拒绝。fs/get 即使收到请求也始终返回 405。
- [ ] 从真实文件页浏览和至少两个主文件的有界提交，经现有 durable Task／实际稳定性、
      完整分析、精确摘要、显式确认、Worker 执行、逐项结果核验到刷新／任务详情读回全部
      完成。至少一项同时换目录和改名，另一项带无需内容解析的匹配字幕；真实计划含附件。
      Task flow 与各主文件／字幕的成功及 effect certainty 分别有证明，不能只断言 completed。
- [ ] 对上述完整正常旅程，fs/get 请求数=0、所有内容读取请求数=0，确认之前媒体
      mutation=0；最终只有精确授权的 Move／Rename，各项源消失、目标大小正确，结果
      已持久化；刷新、重复结果读取及再次 Worker poll 不增加 mutation。
- [ ] 已有目标冲突或源元数据变化在 mutation 前拒绝；目标大小错误／源仍存在／执行后
      列表失败不能变成成功；重命名失败保留现有补偿与不确定效果规则。批量一项失败不重放
      已成功兄弟项，现有故障语义及 C→A RecognitionType 身份回归不被放宽。
- [ ] 生产变更未扩大 Storage 能力、隐式 overwrite／delete／copy fallback、授权、
      配置／schema／Task 状态；测试不访问真实网盘、TMDB、用户媒体、运行数据库或私有凭据。

### Required tests

按 [测试等级与分工](docs/development-workflow.md#6-test-levels)：
Developer 只跑新增／修改及直接受影响验证；B 对固定候选独立验收并完成 T4 全量门禁。
以下新增测试／脚本名称是计划入口，当前尚未实现，不能记录为已通过。

**Developer — affected tests，仓库根目录：**

```sh
.venv/bin/python -m unittest tests.test_openlist_storage tests.test_openlist_metadata_organize
.venv/bin/python -m unittest tests.test_storage_browser tests.test_storage_setup_check tests.test_runtime_storage_configuration tests.test_scanner
.venv/bin/python -m unittest tests.test_manual_organize_preview tests.test_manual_organize_execution tests.test_v2_manual_organize tests.test_organizer tests.test_attachments
.venv/bin/python -m unittest tests.test_direct_file_operations tests.test_direct_file_transfers
.venv/bin/ruff check mediaflow/infrastructure/openlist_storage.py tests/test_openlist_storage.py tests/test_openlist_metadata_organize.py scripts/openlist_metadata_organize_browser_proof.py
.venv/bin/ruff format --check mediaflow/infrastructure/openlist_storage.py tests/test_openlist_storage.py tests/test_openlist_metadata_organize.py scripts/openlist_metadata_organize_browser_proof.py
.venv/bin/python scripts/check_governance.py
git diff --check
```

如另改夹具，将其加入 changed-file check 和直接受影响用例；不因此把整个仓库全套交给
Developer。上述模块覆盖属性查询、root、发现／稳定性、准入再检查、executor／附件和普通
文件命令等同一 stat 的消费者。

在 `web/` 运行 `npm run build`，然后回仓库根运行
`.venv/bin/python scripts/openlist_metadata_organize_browser_proof.py`。
该脚本使用当前构建、临时配置／SQLite、本地 HTTP OpenList 与本地元数据夹具和真实 Worker；
请求台账覆盖启动／浏览至最终读回，最终报告不可仅统计 executor 阶段。脚本应保存脱敏
结果／截图和计数到 `.git/validation-evidence/<candidate>/openlist-metadata/`，不写用户配置，
不把“脚本退出 0／SKIP”当作已完成核心证明。

**B — independent acceptance / T4：**

1. 审查固定 Task Base..candidate 的完整 diff；先独立重现 HTTP 405 核心场景及故障反例，
   用上述 focused 模块／browser proof 检查 HTTP 台账、真实文件状态和持久化结果。
   若有实质阻塞，先 FIX REQUIRED，修正在同一 Task 内。
2. 对真实候选执行 [shared full gates](docs/development-workflow.md#shared-full-regression-commands)
   的 Python 全量、质量／依赖／示例／禁用依赖、Web 全量检查／构建／E2E、wheel／外部安装
   smoke 及适用安全回归；这次 Storage T4 不能按“只改一个适配器”降为 T2 或省略全量。
   所有既有失败／skip 按原结果保留；声称 Base 已有失败须同输入独立复现。
3. Docker resident OpenList 消费链属于适用门禁；构建固定候选的唯一镜像后运行：
   `docker build -t mediaflow:patch-20261108-3 .`；
   `.venv/bin/python scripts/docker_files_transfer_lifecycle_smoke_test.py --image mediaflow:patch-20261108-3`；
   `.venv/bin/python scripts/docker_release_security_smoke_test.py --image mediaflow:patch-20261108-3`。
   旧 HTTP 夹具如因合法分页／root 语义不完整而失败，修正其模拟语义并复验，不放宽产品断言。
   Docker 不可用或必需核心证明未执行，保留 pending／限制，不称该门禁 PASS。
4. 记录候选 SHA、实际命令／结果／跳过、构建身份和稳定证据路径。无 UI 变更不增加全站
   视觉重设计验收；原生文件页的可用提交、明确状态及结果读回仍必须实际查看。

### Non-goals

不新增 Provider／Storage 操作、下载产品、缓存／限速／队列系统、自动风控重试、批量并发
优化、文件内容验证策略或新的恢复类型；不关闭已有 NFO／Hash／跨 Storage 读取能力。
不修改业务流水线、UI 产品、schema、Active 发布合同、权限或 effect certainty 语义。
不修复／迁移已失败的生产任务，不自动重放已移动或不确定项，不连接真实 115 做压力测试。
不改 Slice52、SLICE／Roadmap／Progress，不扩大至独立性能或其他已知 Web 测试问题。

### Workspace / checkpoint boundary

规划起点：`main`，HEAD 即 Task Base；规划前 `python3 scripts/check_governance.py` PASS，
暂存区为空，工作区与 Git 可写。预存已跟踪修改 `mediaflow/.DS_Store`，另有未跟踪系统
元数据、调查脚本、日志、`15` 及 `output/` 材料；全部保留，本次只 checkpoint TASK.md。
此前两项独立修正的 Base／接受身份、Slice52 已关闭状态与所有历史验证限制保留于 Git。

### Developer completion report

尚未实施。授权实施并完成受影响验证后，填写真实 checkpoint／READY FOR B REVIEW、
修改与关键决定、实际测试／已知失败／风险；完整验收由 B 完成，不能自批 PASS。

### B review result

尚未提交实现候选；无产品验收结论。B 独立审查后记录固定 Base..Head、PASS／FIX REQUIRED、
实际门禁结果和 Authorized bug acceptance complete。接受后恢复紧凑
`# NO ACTIVE IMPLEMENTATION TASK`，不新增 Slice 关闭记录或下一项工作。
