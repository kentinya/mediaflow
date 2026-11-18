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
Status: PLANNED
Task Base: 3e3e3ccdbf8bd2b57c1b15515de3ece7302aaaf4
Difficulty: High
Test Level: T4
Planner / Reviewer: B
Development Authorization: TASK55.8 IMPLEMENTATION AUTHORIZED
Next Action: DEVELOPER STARTS TASK55.8 IMPLEMENTATION
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

### 交接状态

Task 已获实施授权，状态为 PLANNED。Developer 按本 Task 实施，运行直接受影响的测试，提交
固定候选和实际测试结果后标记 READY FOR B REVIEW。B 独立审查完整 Task Base..Head，给出
PASS 或 FIX REQUIRED。
