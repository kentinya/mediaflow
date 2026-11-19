# Task55.8 — 交付唯一现行 V2，走通首次部署

用户要求「激活Task」，据此将已提交的 Task55.8 草案激活为正式实施 Task。

Task55.7 **PASS**。B 已审查完整范围
`27789283a0e1b04bc1e9204002ecdb8cfc44e946..96e7c2b8f35f15969292e5b8c98312fa01781e6a`。
复核结果和全部 Slice 结果重评见 `git show 3e3e3ccdbf8bd2b57c1b15515de3ece7302aaaf4:TASK.md`。

依据已提交 Slice55 的 RO-6 和 RO-2 中旧全局审核实现的退出要求，覆盖
V2-RETIRE-002、009、010。测试和交接按开发流程执行。
参见 [Slice55](SLICE.md)、[V2 需求](docs/v2-requirements.md#target--complete-v1-and-migration-residue-retirement-slice55-active)
和 [开发流程](docs/development-workflow.md)。

```text
Task ID: 55.8
Task Type: SLICE
Parent Slice: 55
Status: FIX REQUIRED
Task Base: 3e3e3ccdbf8bd2b57c1b15515de3ece7302aaaf4
Difficulty: High
Test Level: T4
Planner / Reviewer: B
Development Authorization: TASK55.8 IMPLEMENTATION AUTHORIZED
Next Action: DEVELOPER FIXES B55.8-02
```

规划从 `/Users/songzhidong/mediaflow` 的 `main` 开始。上述 HEAD 的工作区和暂存区干净，
工作区与 Git 可写，规划前治理检查通过。Slice Base 仍为
`2b2e7c1824fa5681864455714d0f97b26555c7dc`。
激活前 `main` 的 HEAD 为 `4bc6a390258a3a5bb42e071adf78c755e5d20353`，工作区和暂存区干净，
治理检查通过。Task Base 至草案提交仅变更本文件。

重评沿用 Task55.7 同期候选的 B 证据。RO-1 的现行入口和旧路由退出、RO-3 的唯一配置权威
和正式键、RO-4 的五态和有效 V2 库、RO-5 的原请求核对已有验收。RO-2 的旧全局传输入口已
注销，仍有下述测试专用写入。RO-6 待交付公开空实例命令、当前操作说明及整体验收。

### 目标与用户旅程

管理员按部署指南启动四服务空实例，在「系统设置」看到没有生效配置，显式创建首个草稿。
重开页面后可恢复同一草稿。从「高级配置」验证并按本修订要求完成发布前检查，点击「激活配置」。
空基线激活后显示媒体业务尚未配置，Task 和通知投递仍为空。管理员通过现有 Storage、两种库、
七类规则、自动化和通知页面配置实际业务。在条件满足时，原常驻服务采用新发布的设置，Scheduler
受理到期工作，Notification Worker 向原配置接收方投递。检查失败时显示失败项，草稿和原生效配置
仍可核对，修正后从同一设置流程继续。使用 Local 媒体挂载的整理和文件维护在独立的有挂载实例验证。

操作员随后从 Files 整理，到任务中心打开原 Task。需要人工决定的文件各自保存决定并重新分析。
查看选中项的精确摘要后显式确认，处理结果仍回到原 Task。过期决定需要重读，结果未知的文件可
核对证据。成功兄弟项和结果未知的效果都不重放。CLI 中现行的 `tasks ignore-item` 和
`tasks ignore-pending` 继续通过持久恢复准入处理现有等待项。

### 当前代码依据

- 仓库公开入口 `scripts/docker_empty_baseline_smoke_test.py` 在系统设置等待「需要创建首个
  Draft」，激活部分也使用旧控件和旧标题。`ConfigurationPage.tsx` 的现行入口依次是配置状态
  摘要中的「创建首个草稿」和「高级配置」内的「验证草稿」「激活配置」。脚本还将旧
  `partial_success` 当作 Task flow 的结束状态。Task55.6 的固定 B 记录里有仓库命令超时和
  当前页面接通后实际通过的独立记录。参见 `git show 27789283:TASK.md`。
- `recognition_review.py`、`metadata_review.py`、`metadata_correction.py` 的
  `resolve_pending` 仅由旧正向测试调用，连到各自专用的 pending 查询、批量 DTO 和
  `sqlite_runtime.py` 的批量写入。现行 `task_item_recovery.py` 使用单项 `resolve`，
  `task_runtime.py` 仍为 Task 创建实际审核记录。Files 的来源历史还读取 Metadata 审核证据。
- `mediaflow tasks --help` 和 `mediaflow tasks ignore-pending --help` 确认现行 CLI。
  `final_cli.py` 为该命令传入 `RecoveryAdmissionService`。在 `manual_ignore.py`，
  未传入准入服务的旧批量直写仅由旧正向测试触发，`_legacy_ignore` 无调用。
- README 的安装步骤仍将完整策略样例用作启动定位文件，配置指南仍将 JSON bootstrap 描述为
  业务权威并列出「远程执行」编辑组。部署指南把空基线激活描述为 API 操作，发布说明尚需在
  现有版本语境中明确 Slice Base 的有效 V2 数据继续使用边界。

### 开发指导

1. **清退旧全局写入。** 从三个 `resolve_pending` 删除各自专用的 pending 查询、请求类型、
   SQLite 批量写入及剩余引用。保留 Task 单项 create/resolve、已保存记录、来源历史及当前读回。
   将 CLI 普通参数错误断言留在现有测试中。按实际覆盖缺口，把并发决定、版本拒绝、审计原子性
   和 C 复用 A 仍为 C 的断言落到现行 Task 决定与结果链路。
2. **让现行 Ignore 走同一个准入。** 保留 CLI 的有界筛选、顺序、可选 `--task-id`、actor/note
   及已有输出。批量逐项走现行的 checkpoint 和准入，复用同一单项行为。删除
   `_legacy_ignore`、缺准入服务时的批量直写分支及各自专用的仓库写入和请求类型。把旧
   整批事务断言改为验证当前每项的原子性与耐久结果。保留现行读取和审计历史。
3. **接通仓库已有空实例 smoke。** 在当前设置的状态摘要显式创建草稿，读取同一草稿，按实际
   页面验证、检查并激活。使用现有的请求与响应观察核对 `checked: true`、精确版本及生效
   修订，保留秘密未落浏览器存储和点击前后零工作断言。沿用已有的候选镜像、受控 HTTPS 接收方
   和挂载验证。为无挂载阶段的后续发布采用已实证的容器可访问隔离根，使用正式 entrypoint
   运行容器 CLI，使其取得部署环境。等待当前 Task flow，单独核对授权文件效果与两种库的 Copy
   结果。保留空实例、四服务同身份采用、签名投递和换目标后只在原目标恢复的检查。B 从同一
   空实例沿现有页面验证完整 typed 配置旅程，复用各工作区已有的表单操作和检查。
4. **校准当前操作说明和制品。** README、配置／部署／发布指南使用最小管理 bootstrap、
   系统设置的现行控制和可运行命令。说明规范配置样例的 Draft 导入用途、有效 V2 数据的原 ID
   和 pins 继续使用、同版本备份恢复，以及 V1／废弃形态退出。检查这些说明引用的脚本、样例、
   CI 和 wheel／镜像内容。正式需求、旅程与架构的 CURRENT 协调列入交 A 的 Closure Packet。

### 验收

- [ ] **AC-1（Slice AC-02/04/06/09）** 三个旧批量写入从源码及已安装产物退出，实际存在过的
  旧 CLI 命令仍为普通参数错误。当前识别、候选选择、元数据修正、分类和冲突决定可从原 Task
  分析到精确摘要、确认及结果。原请求可核对，过期或并发决定保留已提交结果，兄弟项各自独立，
  已完成及不确定效果零重放。保留的 CLI Ignore 使用持久准入，范围和耐久结果与原命令一致。
- [ ] **AC-2（Slice AC-08/10/11）** 原仓库空实例命令对候选镜像通过。四服务无媒体挂载也
  能正常等待。管理员重复打开设置后仍可恢复原草稿，验证及适用检查对应同一修订，显式激活后
  页面显示实际生效版本和媒体业务未配置，原库仍为零 Task、零投递。首次业务发布后原常驻服务
  采用配置，真实签名通知及原目标恢复通过。独立媒体栈完成实际整理和两种库 Copy，Task flow
  与文件效果独立验证。
- [ ] **AC-3（Slice AC-03/05/11/12）** 按当前指南操作能完成部署，规范样例可验证并作为
  Draft 导入。候选 Web 构建、wheel 源码外安装与 Docker 四服务使用相同的当前契约。源、
  注册、schema、消费者、产物和说明相符。完整 Slice 验收另逐项核对适用的既有实证和候选
  缺口，包括 Slice Base 稳定 V2 数据继续使用和保留的安全边界。

### 测试

**Developer** 运行受影响用例及当前空实例命令。将三个旧批量正向测试的当前断言和退出断言
分别归入现有审核模块测试。以下命令从仓库根执行。

```sh
PYTHONPATH=tests .venv/bin/python -m unittest \
  test_recognition_review test_metadata_review test_metadata_correction \
  test_manual_ignore test_manual_ignore_batch test_processing_recovery_admission \
  test_manual_task_engine test_container_deployment
(cd web && npm run test:e2e -- tests/e2e/configuration-settings.spec.ts)
.venv/bin/python scripts/docker_empty_baseline_smoke_test.py --image mediaflow:task55-8-dev
git diff --check
```

**B** 在收到固定交接后独立审查完整 Task Base..Head。复验 AC-1 的当前同 Task 入口与真实
退出命令，按 [T4 共享门禁](docs/development-workflow.md#shared-full-regression-commands)
核对候选。专项从原测试配置执行。

```sh
(cd web && npm run test:e2e -- --config=playwright.python.config.ts \
  tests/e2e/operations-inventory.python.spec.ts tests/e2e/manual-organize-dialog.python.spec.ts)
(cd web && npm run test:e2e -- --config=playwright.python.automation.config.ts \
  tests/e2e/automation-lifecycle.python.spec.ts tests/e2e/automation-run-once.python.spec.ts \
  tests/e2e/automation-settings.python.spec.ts)
(cd web && npm run test:e2e -- --config=playwright.direct-files.python.config.ts \
  tests/e2e/direct-files.python.spec.ts)
.venv/bin/python scripts/docker_empty_baseline_smoke_test.py --image mediaflow:task55-8-b
```

B 在 Task PASS 后按 Slice AC-01–12 逐项重评。先比对匹配的已有证据，再跑候选所缺门禁。
重点核实同一空实例从设置到 typed Storage、两种库、七类规则、自动化及通知的完整路径，
C 复用 A 仍为 C，真实 Slice Base 数据与原请求继续使用，以及桌面、390px、矮窗口的可读、
键盘和返回。Docker 发布安全和重启、wheel 源码外消费按实际制品身份记录。测试时间包括构建
及失败重跑，每轮少于该轮总时间的 50%。全项满足后交 A 的 Closure Packet。

**范围边界** 以 Slice55 当前合同为准。产品入口、现行审核行为与历史数据以本 Task 的保留
验收为准。发布和用户部署由原授权边界管理。

### Developer 交接 — Task55.8（2026-11-19，北京时间）

```text
Task Base: 3e3e3ccdbf8bd2b57c1b15515de3ece7302aaaf4
Implementation Candidate: ba9e026a9dbe85243749c9176a2b85f7a3ec715a
Branch: main
```

候选是实现检查点；随后仅本文件记录交接。B 审查完整
`3e3e3ccdbf8bd2b57c1b15515de3ece7302aaaf4..ba9e026a9dbe85243749c9176a2b85f7a3ec715a`。

**已实现**

- 删除 `RecognitionReviewService.resolve_pending`、`MetadataReviewService.resolve_pending` 和
  `MetadataCorrectionService.resolve_pending`，同时删除各自专用的 pending 查询、批量请求 DTO、
  SQLite 批量写入和 `ManualIgnoreBatchRequest`。保留单项 create/resolve、TaskItem 状态转换、
  既有审计/历史及 C 复用 A 仍为 C 的现行断言。旧 `recognition-reviews`、`metadata-reviews`、
  `metadata-corrections` 命令仍走普通 argparse 参数错误并零写入。
- `tasks ignore-pending` 保留有界筛选、顺序、可选 `--task-id`、actor/note 和原输出，但逐项
  复用现行 checkpoint 与 `RecoveryAdmissionService`；删除 `_legacy_ignore`、缺准入服务时的
  批量直写及 `ignore_waiting_item(s)`。测试覆盖三种等待类型、limit/task 过滤、逐项原子性
  （前项已提交、后项失败不回收、后续项未执行）、无准入服务时无直写，以及 CLI 不构造 Storage。
- 空实例 smoke 改为真实 Settings 页面旅程：`配置状态摘要` 显式 `创建首个草稿`，reload/重连后
  `恢复草稿（编辑版本 N）` 读取同一修订，`验证草稿` 后确认空基线 `该草稿没有适用检查`，
  `激活配置` 使用 `checked: true` 和精确版本。浏览器观察核对创建/验证/激活响应的 revision、
  version、digest，激活后页面显示 `空配置已生效`，`诊断` 显示实际 Active 身份和
  `配置已激活，媒体业务尚未配置`；token 不落 URL、storage、cookie 或页面。无挂载后续发布改用
  各服务容器内可访问的隔离根，使用正式 entrypoint 执行 `api credentials check` 证明取得部署环境；
  Task 等待只接受五态 `completed`。独立媒体栈继续完成真实 Organize 和两种库 Copy，并保留
  进程身份、签名投递及换目标后仅原目标恢复断言。
- README、配置、部署和发布指南改用最小管理 bootstrap、现行 Settings 控件和可运行命令；说明
  `config/strategy.example.json` 是规范化 Draft 导入来源而非启动文件、激活输入省略部署身份、
  同版本备份恢复边界，以及 Slice Base 有效 V2 数据原 ID/pins 继续使用。`make_deployment_config.py`
  增加 `--database-path` 供本地非容器运行，`config/mediaflow.activation.json` 纳入忽略。

**实际验证（cwd `/Users/songzhidong/mediaflow`）**

```text
PYTHONPATH=tests .venv/bin/python -m unittest \
  test_recognition_review test_metadata_review test_metadata_correction \
  test_manual_ignore test_manual_ignore_batch test_processing_recovery_admission \
  test_manual_task_engine test_container_deployment
→ 98 项通过（5.221 秒）

(cd web && npm run test:e2e -- tests/e2e/configuration-settings.spec.ts)
→ 12 项通过（8.1 秒）

MEDIAFLOW_SMOKE_TEMP_DIR="$PWD/.dsh-docker-tmp" \
  .venv/bin/python scripts/docker_empty_baseline_smoke_test.py --image mediaflow:task55-8-dev
→ media-free 与 media-mount 两栈均 PASS（74.71 秒）；空实例页面首草稿/重载/验证/
  精确 checked 激活、零 Task/投递、签名投递与原目标恢复、entrypoint 部署环境、
  Organize 及两种库 Copy 全部通过

.venv/bin/python -m pip wheel . --no-deps -w <临时目录>
→ wheel SHA-256 8871350e14404fe7bd2e9ec802975ed16db8a7bdab8eaeeb3bf68306133c28e7；
  包内三个 resolve_pending、ManualIgnoreBatchRequest、ignore_waiting_item(s) 计数均为 0
```

首次 smoke 两次失败均为测试脚本严格定位器命中多个同名文本（`配置已激活`、同一 revision 的
两个 `<code>`），修正定位器后最终通过；原失败保留在本地日志。另运行
`python3 scripts/check_governance.py`（PASS）、`ruff format --check`／`ruff check`（14 个改动
Python 文件通过）、`compileall`、`git diff --check`，并实际执行 README 的
`make_deployment_config.py ... --database-path ... --configuration-output ...` 与
`config draft-import`（exit 0）。测试、构建及两次失败重跑累计约 2.5 分钟，小于本轮总用时
（约 17–20 分钟）的 30%。

**未由 Developer 执行（不记为通过；B 的 T4 门禁）**

- 完整 Python/Web/E2E、真实 Slice Base 数据与原请求连续性、typed Storage/两种库/七类规则/
  自动化/通知的完整 B 旅程，以及 Docker 发布安全/重启、候选 wheel 源码外安装。
- Task55.8 AC-2/AC-3 中需 B 从同一空实例验证的完整 typed 配置、桌面/390px/矮窗口可读、
  键盘与返回行为；本报告不构成 PASS。

**剩余风险／需 B 核对**

- `docs/requirements.md` 仍保留历史上对三项全局 batch resolve-pending 和 `tasks retry-failed`
  的叙述；TASK 已将正式需求/旅程/架构的 CURRENT 协调列入交 A 的 Closure Packet，本轮未改。
- 空实例后续发布使用容器内 `/tmp` 隔离根，只证明无挂载发布/调度路径；真实文件效果由独立
  媒体挂载栈证明。
- 本轮未改 Web 源码或 API 响应结构；浏览器配置规格复用现有 fake API，真实页面由 smoke 覆盖。

### 交接状态

Developer 已完成本 Task 的实现检查点和实际受影响验证，状态为 READY FOR B REVIEW。
B 独立审查完整 Task Base..Head，给出 PASS 或 FIX REQUIRED；本报告不构成独立验收。

### B 独立复核 — 2026-11-19（北京时间）

**FIX REQUIRED**。从干净的 `main` 完整审查
`3e3e3ccdbf8bd2b57c1b15515de3ece7302aaaf4..ba9e026a9dbe85243749c9176a2b85f7a3ec715a`。
交接提交 `99f490fa7b84325e0b72b03a7acb98963b2cb31f` 仅更新本文件。

**B55.8-01（P1，Task AC-3，Slice RO-6 / AC-08、AC-12）**
首次设置指南的命令跳过了发布前检查。管理员生成配置，填入本地媒体路径，导入并验证业务草稿。
在新实例上，系统设置使用的激活请求返回 `409`，提示先做存储只读检查，并保留原草稿。
接着执行 README 和配置指南列出的 `config activate`，命令返回成功，同一草稿成为生效配置，目标目录仍不存在。

#### 开发指导

1. README 和配置指南保留生成 bootstrap、调整本地路径及导入草稿的命令。导入后写清楚如何在
   「系统设置 → 高级配置 → 查看配置」选回同一份草稿，执行「验证草稿」，完成该版本列出的存储、
   离线识别策略和目标预检，再点击「激活配置」。用现有页面和命令交付这条路径。
2. 写清一次实际可恢复的情形。目标目录尚未创建时，检查会提示不可用。创建草稿指定的目录或修好
   对应挂载，回到该草稿重新检查。首次设置在检查通过前仍无生效配置。显式激活后，
   「诊断」显示该草稿对应的生效版本。
3. Developer 使用新的临时部署和生成的示例，从命令行导入一直走到浏览器激活。
   先核对路径错误时的检查结果与草稿状态，再修好路径并核对同一草稿成功发布。
   执行 `git diff --check`，报告实际操作、结果和候选 SHA。B 在修订候选上复验这条旅程及原 T4 验收。

#### 实际验证与 Slice55 重评

治理预检和完整范围 whitespace 检查通过。使用现有生成器、CLI、真实本地 API 和临时 SQLite
复现 B55.8-01。审核、Ignore、Task 引擎、容器配置及发布检查相关的 Python 用例共 109 项通过。
复现和 Python 测试分别约 1 秒、6 秒，含检查在内的测试时间少于本轮总用时的 50%。
日志位于 `.git/validation-evidence/ba9e026a9dbe85243749c9176a2b85f7a3ec715a/task55-8-b/`
的 `documented-first-publication.log` 与 `focused-python.log`。完整 T4、候选四服务旅程及最终制品门禁待 B 复验。

| Slice 结果 | 本轮核对 |
|---|---|
| RO-1 | 候选无 Web 路由或静态入口改动。旧路径退出与九页旅程沿用已有检查点，最终候选验收待完成。 |
| RO-2 | 三条旧全局批量写路径及直写 Ignore 已从源码删除。定向测试通过，覆盖旧命令解析失败及现行 Ignore 持久受理。现行同 Task 原生旅程待验收。 |
| RO-3 | 当前 bootstrap 可导入和验证规范样例。按现行系统设置请求发布仍检查该修订的证据。首次设置指南的发布步骤须按 B55.8-01 修正。 |
| RO-4 | 本候选移除批量写方法。五态、Slice Base 数据和原 pins 见既有证据，最终候选连续性待复验。 |
| RO-5 | 候选无会话或未知请求协议改动。原请求核对有 Task55.7 固定证据，当前候选原生门禁待完成。 |
| RO-6 | B55.8-01 阻止验收。四服务空实例、同实例 typed 配置和最终制品门禁仍待 B 执行。 |

修正仍在 Task55.8 内。Slice55 保持 ACTIVE。

### Developer 交接 — Task55.8 修订（B55.8-01，2026-11-19，北京时间）

```text
Task Base: 3e3e3ccdbf8bd2b57c1b15515de3ece7302aaaf4
Implementation Candidate: 18d848dee56d9675e62be7d0b201c9f0ce45133a
Prior Candidate: ba9e026a9dbe85243749c9176a2b85f7a3ec715a
Branch: main
```

候选是实现检查点；随后仅本文件记录交接。B 审查完整
`3e3e3ccdbf8bd2b57c1b15515de3ece7302aaaf4..18d848dee56d9675e62be7d0b201c9f0ce45133a`，
其中 `ba9e026a..18d848de` 仅含本修订；中间的 `cd263b23` 是 B 自己的审查记录提交。

**已实现（B55.8-01）**

- README 首次设置：保留生成 bootstrap、编辑本地路径与 `config draft-import` 命令；发布步骤
  改为系统设置 checked 旅程——`高级配置 → 查看配置` 选回同一草稿、`验证草稿`、完成该版本
  列出的存储只读检查／离线识别策略测试／目标预检，再点击 `激活配置`；写明适用检查未全部
  通过前无生效配置、被拒激活保留草稿与原 Active，以及可恢复情形（目标存储根不可达时目标
  预检报 `暂不可用`；存储根可达但媒体库根缺失时报 `目标库根路径不存在`；创建草稿指定的
  目录或修好挂载后回到同一草稿重跑），激活后页面显示发布版本且「诊断」显示对应生效
  修订／版本／摘要。README 同时说明生命周期 CLI 仍用于已验证修订的高级发布，且
  `config activate` 不执行设置页发布前检查。
- `docs/configuration.md` 引导段同步改为「导入不发布」＋同一 Web checked 旅程＋可恢复
  情形；「Managed lifecycle」的 CLI 清单后新增 CLI activate 边界说明（仅发布已验证修订、
  不要求设置页发布前检查证据，首次设置与常规发布走 Web checked 旅程）。未改任何源码、
  测试、脚本或 API/Web 行为。

**实际验证（cwd `/Users/songzhidong/mediaflow`；日志与脚本存于
`.git/validation-evidence/18d848dee56d9675e62be7d0b201c9f0ce45133a/task55-8-dev-fix/`）**

1. 临时部署：`make_deployment_config.py` 生成最小 bootstrap 与规范样例输入，两个 Local
   Storage 根改指 `/tmp/t55-8-verify/media/{incoming,organized}`（均不存在）；
   `config draft-import` 建立草稿 `58303a40-1214-4654-ad9a-7409490e9da1` 版本 1；
   `mediaflow api serve` 用同一构建产物提供真实 Python API＋页面。
2. 浏览器阶段 A（Playwright 驱动真实页面）：`恢复草稿（编辑版本 1）` → `验证草稿` →
   发布前检查显示 4 项适用检查；source-storage 存储检查 → `只读检查未通过：根路径不存在`；
   目标预检 → `目标预检未通过：暂不可用`；`激活配置` 发送 `{"expectedVersion":1,
   "checked":true}` 得 409，message 为 `the read-only Storage check for 'source-storage'
   failed with category not_found`，`durableState: draft_preserved`、`sideEffects: none`；
   页面确认草稿保留（`编辑版本 1（已验证）`）且无生效配置——即 B55.8-01 的复现路径。
3. 仅创建两个存储根目录后阶段 B（同一草稿、同一页面流程）：两个存储检查重跑通过；识别
   策略测试完成；目标预检 → `目标库根路径不存在`；按页面建议创建 `organized/Movies`、
   `organized/TV Shows` 后重跑同一草稿的目标预检 → 通过；`激活配置` → 200，`status: active`、
   `version: 1`、`revisionSequence: 1`、digest 与导入一致（`83485064…`）；页面显示
   `配置已激活`／`配置已生效`／`序号 1`，「诊断 → 配置身份」显示 Authority MANAGED、
   生效修订＝该草稿 revisionId、生效版本 1。
4. CLI 边界核对（第二临时库 `/tmp/t55-8-cli`）：未验证草稿 `config activate` → exit 2
   `configuration must be successfully Validated before activation`；`config draft-validate`
   后 `config activate --expected-version 1` → exit 0 发布为 Active，全程未创建任何目标
   目录，与文档新增边界表述一致（首次设置不使用该命令）。
5. `git diff --check` 干净；`python3 scripts/check_governance.py` PASS；两文件代码围栏配对。
   浏览器与 CLI 验证（含三次定位器修正重跑）合计约 8 分钟，低于本轮总用时（约 40 分钟）
   的 30%。

**未由 Developer 执行（不记为通过；B 的 T4 门禁）**

- 本修订无源码变更，上一轮已交的 Python/E2E 结果不受影响，本轮未重跑；B 复验时可按原
  Task 测试清单执行。
- 完整 T4、候选四服务空实例、同实例 typed 配置旅程、桌面／390px／矮窗口与最终制品门禁
  仍按 TASK 既有 B 计划执行。

**剩余风险**

- 无新增；上一轮交接中「docs/requirements.md 历史叙述」与「空实例容器内隔离根」两条
  剩余风险保持不变。

### 交接状态（修订后）

Developer 已完成 B55.8-01 修复、实际旅程验证和检查点 `18d848dee56d9675e62be7d0b201c9f0ce45133a`，
状态为 READY FOR B REVIEW。B 独立复验该旅程并重评原 T4 验收，给出 PASS 或 FIX REQUIRED；
本报告不构成独立验收。

### B 修订复核 — 2026-11-19（北京时间）

**FIX REQUIRED**。审查完整 `3e3e3ccdbf8bd2b57c1b15515de3ece7302aaaf4..18d848dee56d9675e62be7d0b201c9f0ce45133a`。
本轮从干净 `main` 开始，交接提交 `95908e9c9b687cf14bf71f94a1951eb5b3065b1a` 只更新本文件。
对照上次复核的 `ba9e026a`，本候选的实现差异只涉及 README 和配置指南。

**B55.8-01 已修复。** B 在隔离新实例命令行导入规范样例，从「高级配置 → 查看配置」选中同一草稿。
根目录不存在时，发布前检查显示失败，激活返回 `409`，原草稿和无 Active 状态保留。补齐存储根和媒体库根，
重跑检查并显式激活后，页面诊断与运行库确认原修订 ID 和摘要成为 Active。

**B55.8-02（P1，Task AC-3，Slice RO-6 / AC-08、AC-12）。** 两份指南导入规范样例时，管理员无法
按现有步骤到达包含该样例的草稿。在新终端依照配置指南生成文件并运行导入，CLI 以 `--config or
MEDIAFLOW_CONFIG is required` 退出 2。按 Docker 指南运行 `mediaflow config import`，在 Compose
已绑定 bootstrap 的条件下得到的是 0 项 Storage 的草稿。显式指定生成的输入文件后，草稿中才有样例的
2 项 Storage。Docker 指南所指的系统设置页面提供草稿选择和发布检查，未提供上传该文件的控件。

#### 开发指导

1. 配置指南的同一命令段明确指定本次生成的 bootstrap 和样例输入，例如
   `mediaflow --config config/mediaflow.json config draft-import --file config/mediaflow.activation.json`。
   使用本地部署时，生成器的数据库路径应与随后启动的服务一致。
2. Docker 指南给出可直接运行的导入命令，使用同一 Compose 项目及其 `/data` 卷和正式入口，明确传入生成的
   样例文件。B 已在隔离 Compose 项目验证
   `docker compose run --rm --no-deps -T api config draft-import --file /dev/stdin < config/mediaflow.activation.json`。
   写清执行时机和已有媒体挂载项目所用的 Compose 文件。导入完成后，在「系统设置 → 高级配置 → 查看配置」
   选回该草稿，执行适用检查并显式激活。配置指南的导入段和 Docker 指南使用同一套页面名称。
3. Developer 在隔离路径下从未设置 `MEDIAFLOW_CONFIG` 的新终端复跑配置指南，再按 Docker 指南将样例导入
   测试项目。从系统设置读回对应草稿及样例里的两项 Storage，确认导入阶段不产生 Active，随后按已修订的
   检查与激活步骤继续。执行 `git diff --check`，记录实际结果和候选 SHA。

#### 实际验证与 Slice55 重评

治理与完整范围 whitespace 检查通过。B 的真实浏览器旅程约 4 秒，另复核新终端命令、CLI 导入的草稿内容，
以及正式 Compose 入口在同一 `/data` 卷写入并重读样例草稿。测试时间少于本轮总用时的 50%。
原始结果位于 `.git/validation-evidence/18d848dee56d9675e62be7d0b201c9f0ce45133a/task55-8-b/`。

| Slice 结果 | 本轮核对 |
|---|---|
| RO-1 | Web 源码和路由输入与上一轮相同，已记录的退出和现行入口证据继续适用。 |
| RO-2 | 审核退休和 Ignore 持久受理的 109 项定向证据对应同一代码，最终候选原生验收待完成。 |
| RO-3 | 已复验规范样例的精确 checked 激活和失败后的草稿恢复，导入指引由 B55.8-02 修正。 |
| RO-4 | 持久化代码与上一轮相同，Slice Base 数据和原 pins 的最终候选连续性待复验。 |
| RO-5 | 会话与未知请求协议沿用 Task55.7 的固定证据，最终候选原生门禁待完成。 |
| RO-6 | B55.8-02 阻止首次部署指南验收。完整 T4、同一四服务实例的 typed 配置旅程及 Slice 最终制品门禁待 B 执行。 |

修正留在 Task55.8 内。Slice55 状态为 ACTIVE。

### Developer 交接 — Task55.8 修订（B55.8-02，2026-11-19，北京时间）

```text
Task Base: 3e3e3ccdbf8bd2b57c1b15515de3ece7302aaaf4
Implementation Candidate: fb243ea688d31b8b2242b56bfe732771b9ea0965
Branch: main
```

候选是实现检查点；随后仅本文件记录交接。B 审查完整
`3e3e3ccdbf8bd2b57c1b15515de3ece7302aaaf4..fb243ea688d31b8b2242b56bfe732771b9ea0965`。
`28019b34` 为 B 的审查记录；本候选相对它只改 README、配置指南和 Docker 指南，未改源码、测试、
脚本、API/Web 响应或持久化格式。

**已实现（B55.8-02）**

- `docs/configuration.md` 的生成／导入命令段同时指定 `--output config/mediaflow.json` 与
  `--file config/mediaflow.activation.json`，导入显式使用 `mediaflow --config config/mediaflow.json`，
  并说明缺少 `--config`／`MEDIAFLOW_CONFIG` 时命令拒绝运行。本地部署的生成器带
  `--database-path "$PWD/.mediaflow/mediaflow.sqlite3"`，与随后启动的服务共用同一数据库；容器布局
  保留 `/data/mediaflow.sqlite3` 默认值。生命周期 CLI 清单补上 `--file` 及 bootstrap 选择说明。
- `docs/deployment.md` 删除“通过 `/ui-v2/configuration` 或 `mediaflow config import` 导入”的表述，
  改为先 `docker compose up -d`（使用 Local Storage 时带 media overlay），再用同一 Compose 文件集、
  正式 entrypoint 和 `/data` 卷执行
  `docker compose ... run --rm --no-deps -T api config draft-import --file /dev/stdin < config/mediaflow.activation.json`。
  写明 `-T`／stdin、entrypoint 从 `config` 开始接收参数、非默认项目的 `-p`／`COMPOSE_PROJECT_NAME`、
  导入只产生 inactive Draft、不产生 Active／Task／投递／媒体变更、无需重启，以及省略 `--file` 会回退到
  管理 bootstrap（0 项 Storage）。随后统一为「系统设置 → 高级配置 → 查看配置」选回草稿、
  「验证草稿」、完成该版本「发布前检查」、「激活配置」，并与配置指南使用同一页面名称。
- `README.md` 的规范样例导入命令也显式带 `--config config/mediaflow.json`，并说明可用已导出的
  `MEDIAFLOW_CONFIG` 代替。

**实际验证（cwd 与隔离路径）**

1. 配置指南：在 `/tmp/t55-8-b02/local` 复制生成器与规范样例，建立本地媒体库根，未设置
   `MEDIAFLOW_CONFIG` 的新 shell 中执行指南命令。修复前形态
   `mediaflow config draft-import --file ...` 复现 exit 2
   `mediaflow error: --config or MEDIAFLOW_CONFIG is required`；指南命令成功导入草稿
   `4f8498d2-8a51-4b6f-b35c-f53841bec131` 版本 1，随后 `config status` 为
   `MANAGEMENT_BOOTSTRAP`、`active: null`、`SETUP_REQUIRED`。真实 Python API＋页面中，
   摘要显示「已有草稿待恢复」且生效配置为「无」，在「高级配置 → 查看配置」选回该草稿，
   页面「配置 JSON」含 `source-storage`、`media-target` 两项 Storage 且不含 `persistence`；
   「验证草稿」通过，两项存储只读检查、识别策略测试和目标预检均显示「已通过」，
   「激活配置」返回 `active` 版本 1，摘要显示「配置已生效／序号 1」，Active JSON 仍含两项 Storage。
   导入、验证、检查和激活前无其他配置写入。
2. Docker 指南：在 `.dsh-docker-tmp/t55-8-b02-docker` 建立隔离 Compose 项目，使用
   `compose.yaml`＋`compose.media-mounts.yaml`、临时媒体根、共享 `/data` 卷、正式镜像
   `mediaflow:task55-8-dev`（ID `51720df53efc`，构建自 `ba9e026a`；此后仅文档差异）。四服务启动后，
   按指南命令从 stdin 导入样例草稿 `8846abb9-df5e-4af3-9d97-d8f9022a2507` 版本 1；同一卷的
   `config status` 为 `active: null`。真实页面同样读回两项 Storage，验证、两项存储检查、识别策略
   测试、目标预检全部通过并显式激活为版本 1；随后 `down -v` 清理临时项目。
3. `git diff --check` 干净；`python3 scripts/check_governance.py` PASS；三个文档代码围栏配对；
   `git status` 仅三个文档改动。浏览器定位器首次未捕获激活响应、Docker 首次因 Docker daemon
   不可见主机 `/tmp` 而失败，均按实际原因修正后重跑；原始日志保留于
   `.git/validation-evidence/task55-8-fix-b02/`（`local-cli.log`、`local-web.log`、
   `docker-import.log`、`docker-web.log` 及脚本）。
4. 本轮约 30 分钟；测试（含生成、导入、Compose 启动、浏览器旅程、两次失败重跑与环境清理）约 7–8
   分钟，低于本轮总用时的 30%。

**未由 Developer 执行（不记为通过）**

- 本候选无源码／测试／Web 变更，上一轮已交的定向 Python、Web E2E 和空实例 smoke 结果不受影响，
  本轮未重跑。完整 T4、候选四服务 typed 配置旅程、桌面／390px／矮窗口与最终制品门禁仍按 TASK
  既有 B 计划执行。

**剩余风险**

- Docker 旅程复用 `mediaflow:task55-8-dev` 镜像验证文档命令，未重建仅文档变化的候选镜像；
  可执行代码与候选相同（候选相对 `ba9e026a` 仅文档）。B 的最终制品门禁仍以候选镜像身份为准。
- 上一轮「`docs/requirements.md` 历史叙述」与「空实例容器内隔离根」两条剩余风险保持不变，
  CURRENT 文档协调仍属交 A 的 Closure Packet。

### 交接状态（B55.8-02 修订后）

Developer 已完成指南导入通道修复、配置指南与 Docker 指南的实际旅程验证及检查点
`fb243ea688d31b8b2242b56bfe732771b9ea0965`，状态为 READY FOR B REVIEW。B 独立复验该旅程并重评
原 T4 验收，给出 PASS 或 FIX REQUIRED；本报告不构成独立验收。
