# Task55.8 — 修正 OpenList 示例的首次导入

Slice55 **FIX REQUIRED**。随仓 OpenList 示例按自身说明导入时失败。
复现、影响和退回条件见 [A Final Review](SLICE.md#a-final-review--fix-required)。
B 接续原 Task55.8。原计划及历轮交接见
`5c1921b9b8ce2eb1472bfb5584579556bdf6f3b8:TASK.md`。

```text
Task ID: 55.8
Task Type: SLICE
Parent Slice: 55
Status: FIX REQUIRED
Task Base: 3e3e3ccdbf8bd2b57c1b15515de3ece7302aaaf4
Implementation Head: fb243ea688d31b8b2242b56bfe732771b9ea0965
Reviewed Handoff: 5c1921b9b8ce2eb1472bfb5584579556bdf6f3b8
B Closure Packet Checkpoint: 573726541063115eeed6ce6d879004a40bf2624a
Difficulty: High
Test Level: T4
Reviewer: B
Next Action: DEVELOPER CORRECTS A55-01 IN TASK55.8
```

**Developer — 新增／修改与直接受影响测试**。
**B — 独立验收与完整回归**。执行范围见[测试分工](docs/development-workflow.md#6-test-levels)。

## A55-01 修正计划

### 目标与复核结论

B 在干净的 `main`（`4e8fdcc4`）核对 Task Base `3e3e3ccd` 至交付 `fb243ea6` 的变更。
交付至当前 HEAD 的后续提交仅包含治理文档。

管理员生成标准业务配置，把公开 OpenList 示例中的 `storage` 对象加到 `storages`，再按配置
指南用 `config draft-import --file` 导入同一个部署。B 复跑 A 的隔离复现。原 Slice Base 接受
旧示例，退回候选退出 2，提示 `storages[openlist-example].baseUrl is retired`。`config status`
显示 `SETUP_REQUIRED`、零草稿、无 Active。同一候选导入未追加 OpenList 的标准示例成功。
**当前候选 FIX REQUIRED**，涉及 Task AC-3 及 Slice RO-3／RO-6、AC-03／08／12。

现行 CLI 调用 `ManagedConfigurationService.import_draft`。该服务在保存之前校验新提交的字段。
随仓示例的连接参数仍在 `storage` 顶层，当前规范已将这些参数归入 `storage.options`。
管理员修正输入后可再次导入，到系统设置选中导入的草稿，依次验证、完成适用的发布前检查并激活。

### 开发指导

1. 修改 `config/alist.example.json`。将 `baseUrl`、`tokenEnv`、`connectTimeout`、
   `requestTimeout`、`maxConcurrency`、`maxRetries` 和 `pageSize` 原值移入 `storage.options`。
   保留外层 `storage` 对象，以及其 `id`、`name`、`type`、`rootPath` 和 `readOnly`。
2. 更新示例注释，并在 `docs/configuration.md` 的 OpenList 小节链接该文件。说明将 `storage`
   追加到生成的 `mediaflow.activation.json` 的 `storages`，替换 `options.baseUrl`，在实际
   执行检查或使用该存储的部署环境提供 `OPENLIST_TOKEN`。沿用指南已有的 `draft-import --file`
   命令与系统设置发布步骤。库引用该 Storage 时，在发布前检查运行对应的只读检查。
3. 在 `tests/test_container_deployment.py` 的 `ContainerArtifactTests` 加入示例导入回归。
   读取仓库中的公开文件，将 `storage` 原样追加到部署生成器的标准业务配置，用 `final_main`
   从实际 `draft-import --file` 命令导入隔离库。另用退回版本的示例形状验证原错误，并在
   同一隔离实例用已修正的输入继续。沿用现有部署测试的生成器、临时目录和 CLI。

### 验收

- [ ] 旧示例通过现行命令退出 2，错误指出顶层连接字段及 `Storage.options`。新实例仍为
  `SETUP_REQUIRED`、零草稿、无 Active。修正后同一命令返回一个可恢复的 Draft，配置中
  保留两个标准 Storage 和 OpenList 对象的原根路径、只读设置及环境变量引用。导入阶段不依赖
  OpenList 连通性。
- [ ] 在同一实例的「系统设置」读到导入的准确版本。完成验证与适用的发布前检查后，显式激活
  该版本，OpenList 可在「存储管理」查看。库引用 OpenList 时的只读发布检查沿用现行行为。
- [ ] 修正范围为公开样例、其配置指南和部署导入回归。以现行严格输入规则、已接受的 V2 数据
  连续性及原 Task55.8 AC-1–3 作为验收边界。

### 本轮测试

Developer 从仓库根执行部署导入回归及改动文件检查。

```sh
.venv/bin/python -m unittest discover -s tests -p 'test_container_deployment.py'
.venv/bin/ruff check tests/test_container_deployment.py
.venv/bin/ruff format --check tests/test_container_deployment.py
git diff --check
```

B 收到固定候选后复核完整 Task Base..Head。先按公开指南复验旧样例拒绝、修正样例导入和
实际 Web 发布旅程，沿用上轮的隔离配置和系统设置操作。T4 按工作流执行完整 Python 回归及
适用的原生、安全和制品门禁。对比最终候选与退回候选的执行输入和制品，按流程复用匹配证据，
重新运行受影响门禁。记录测试实际用时，测试和构建并行时按实际占用区间计时，低于本轮总用时
的一半。[完整回归命令及证据复用规则](docs/development-workflow.md#shared-full-regression-commands)

### Developer 交接 — A55-01 修正（2026-11-19，北京时间）

```text
Task Base: 3e3e3ccdbf8bd2b57c1b15515de3ece7302aaaf4
Implementation Candidate: 80334cca（完整 SHA 见 git log）
Previous Correction Candidate: 2eab5714
Branch: main
```

候选为实施检查点；随后仅本文件记录交接。B 复核完整
`3e3e3ccdbf8bd2b57c1b15515de3ece7302aaaf4..候选`。相较 `2eab5714`，本轮仅把
`docs/configuration.md` 中的样例文件引用改为真实的相对 Markdown 链接，并使用与仓库其他
指南链接一致的写法；样例内容与回归测试未变。

**已实现**

- `config/alist.example.json`：将 `baseUrl`、`tokenEnv`、`connectTimeout`、`requestTimeout`、
  `maxConcurrency`、`maxRetries`、`pageSize` 原值移入 `storage.options`；外层保留 `id`、
  `name`、`type`、`rootPath`、`readOnly`，数值与 `tokenEnv` 引用不变，`_comment` 改为
  描述追加到部署配置、替换 `options.baseUrl`、部署环境提供 `OPENLIST_TOKEN`。
- `docs/configuration.md`：OpenList 小节（“OpenList service root and Web recovery”末尾）
  链接该样例，说明将 `storage` 追加到生成的 `mediaflow.activation.json` 的 `storages`、
  替换 `options.baseUrl`、在实际检查或使用该存储的部署环境提供 `OPENLIST_TOKEN`；沿用
  指南已有 `draft-import --file` 命令与系统设置发布步骤，库引用该 Storage 时发布前检查
  运行对应只读检查。
- `tests/test_container_deployment.py` 新增
  `ContainerArtifactTests.test_openlist_example_imports_through_documented_first_setup`：
  用真实部署生成器产生 bootstrap 与标准业务配置（bootstrap 指向隔离临时库），先把退回
  版本示例形状（顶层连接字段）按现行 `draft-import --file` 命令导入，断言退出 2、错误
  指出 `storages[openlist-example].baseUrl is retired` 与 `Storage.options`，且
  `config status` 仍为 `setupRequired`、零 revisions、无 Active；随后在同一隔离实例用
  随仓修正后示例原样追加再导入，断言返回一个 `draft` 修订且 `config status` 只含该
  Draft；从隔离库持久化 payload 核对保留两个标准 Storage 与 OpenList 对象的原根路径、
  只读设置及 `OPENLIST_TOKEN` 环境引用；再经现行 `draft-validate` 命令确认该 Draft
  可恢复且结构有效。样例地址为不可解析的 `.invalid` 域名，导入成功同时证明导入阶段
  不联系 OpenList。

**实际验证（cwd `/Users/songzhidong/mediaflow`，候选 `80334cca`）**

```text
.venv/bin/python -m unittest discover -s tests -p 'test_container_deployment.py'
  → Ran 15 tests in 0.320s, OK（含 OpenList 示例回归）
.venv/bin/python -m unittest \
  tests.test_container_deployment.ContainerArtifactTests.test_openlist_example_imports_through_documented_first_setup -v
  → Ran 1 test in 0.042s, OK
.venv/bin/ruff check tests/test_container_deployment.py → All checks passed!
.venv/bin/ruff format --check tests/test_container_deployment.py → 1 file already formatted
.git diff --check → 无输出
python3 scripts/check_governance.py → governance check: PASS
```

本轮改动仅 `docs/configuration.md`；工作区无预存脏文件。

**剩余工作与风险**

- 验收第 2 条（同一实例系统设置读取、验证、发布前检查与显式激活，存储管理可见）属
  B 的真实 Web 旅程验收，本轮 Developer 测试计划未包含；
  `draft-validate` 仅证明 Draft 可恢复，未运行发布前检查。
- OpenList 值本身（`https://openlist.example.invalid`）与上轮交付一致，未做业务值变更。

### Slice 结果重评

这轮以退回候选及原始验证记录为依据。RO-1 的当前与旧入口、RO-2 的受理与执行、RO-4 的
新库和现有 V2 数据、RO-5 的原请求核对，仍由下方历史 Closure Packet 对应证据覆盖。RO-3
的现行严格输入规则已实测，RO-6 的 OpenList 样例与该规则冲突，首次用样例设置的旅程停在创建
草稿之前。Task55.8 待修订候选交接。B 复验后重评六项结果并重新提交 Closure Packet。

## Task55.8 独立复核（退回前的 B 记录）

2026-11-19 从干净的 `main` 审查完整 Task Base..Implementation Head。交接提交只更新本文件。
原目标、开发指导、各轮返工及 Developer 交接保留在 `5c1921b9:TASK.md`。
验收依据为[开发流程](docs/development-workflow.md#6-test-levels)。

| 验收 | 实际结果 |
|---|---|
| AC-1 | 三条旧全局审核批量写入和旧 Ignore 直写已退出源码及安装包。旧命令返回普通参数错误。现行 Ignore 通过持久受理逐项提交。真实 Task Center 的识别、元数据候选与修正、分类、冲突从原 Task 保存决定到确认和结果。成功和不确定效果保留各自记录。 |
| AC-2 | 仓库空实例命令通过。无媒体挂载时四服务等待，系统设置创建、重开、验证并激活同一空草稿，Task 和投递保持零。原常驻进程在之后的发布中持续运行并发出签名投递。更换接收地址后旧投递保持阻塞，恢复原地址后才续作。独立挂载栈完成整理及两种库 Copy，分别核对 Task 完成和文件效果。 |
| AC-3 | 本地新终端显式指定 bootstrap，Docker 通过同项目的入口和卷导入。两边都从系统设置读到原草稿及两项样例 Storage。完成发布前检查后，同一草稿在页面成为 Active。B55.8-01 的失败和修正旅程已实测。B55.8-02 的两条导入路径均已复验。wheel 源码外安装和三项 Docker 门禁通过。 |

## Slice55 Closure Packet

以下是退回前的 B 记录。

```text
Slice: 55 — Complete V1 and Migration Residue Retirement
Slice Base: 2b2e7c1824fa5681864455714d0f97b26555c7dc
Implementation Head: fb243ea688d31b8b2242b56bfe732771b9ea0965
Required Outcomes and Surfaces: complete
Decision: SLICE READY FOR A REVIEW
```

已完成 Task55.1–55.8。前七项 B 验收记录依次为 `ebec19bb`、`b73c3635`、`64006c8d`、
`8a9d2460`、`2e460b71`、`27789283` 和 `3e3e3ccd`。最终候选的重评如下。

| 结果 | 完成交付及证据 |
|---|---|
| RO-1 / AC-01 | 真实浏览器复验旧地址、带参数、刷新、重新认证及普通未找到。九页导航、正常深链与来源返回见当前原生测试和 Task55.1/55.4 记录。 |
| RO-2 / AC-02、04、09、10 | 旧调度、票据、grant、全局审核与恢复、非内核整理入口退出。候选真实 Files 到确认及同 Task 结果，Automation 到期与 Run once，原 Task 内四类恢复，两种库普通操作与通知均通过对应验收。 |
| RO-3 / AC-03、08 | 唯一管理 bootstrap 与精确 Active。约束保留 `automation.maximumActiveJobs` 和 `cancel_job`。从同一四服务空实例用表单保存 Storage、两种库、七类规则、自动化及 Webhook，进程身份保持。高级草稿按版本完成验证、检查与激活。C 复用 A 命名和分类仍为 C。 |
| RO-4 / AC-04、05、06 | 五态与独立文件效果在当前原生及重启用例中复验。复用 Task55.6 真实 Base 生成的摘要、已有 Task、两种库历史、失败原子及坏库零修改证据。候选在复制的隔离验收库重新打开原 Task，读取原配置修订和摘要并对照原 pin。Task55.6 到候选的 SQLite 变更为删除旧批量方法。候选 wheel 通过备份、校验和显式非覆盖恢复。 |
| RO-5 / AC-06、07、09、10 | Task55.7 的 Base 原请求跨候选读回证据覆盖运行一次、复制、设置和通知。Web 出包内容一致，候选原生测试重新覆盖丢响应、兄弟项独立、精确请求与结果、RBAC 和不确定非重放。 |
| RO-6 / AC-08、10、11、12 | 样例和操作指南与实际导入、检查、激活和失败恢复一致。核对了被删除的写入和测试、注册、CLI、现行消费者、wheel 和 Docker。相同实例的桌面、390px、矮窗口截图已检查，并验证键盘可达。 |

### 最终测试和制品

本地证据目录为 `.git/validation-evidence/fb243ea688d31b8b2242b56bfe732771b9ea0965/task55-8-b/`。

- Python 全量 2307 项，初跑 2299 项通过、7 项为既有可选跳过，唯一失败为 Task 文档的测试分工声明。
  B 对照模板纠正声明，并复跑 `test_release_security` 的 8 项，全部通过。初跑与复跑记录分别为
  `python-full.log`、`task-ownership-rerun.log`。治理、Ruff、compileall、pip check、正式样例和
  禁止依赖检查通过。
- Web 重建通过。源码、假服务、锁文件及全部 5 项构建产物与 Task55.7 已验收的 Web 输入和产物一致，
  复用 typecheck、lint、format、1631 项单测和 285 项默认浏览器结果。
- 候选真实 Python 浏览器的运营与手工整理 55 项、两种库 28 项通过。Automation 组合运行 46 项通过，
  容量用例读到了前序用例留下的两个改名目标。保留组合失败和 trace，在独立新实例以原断言复跑该用例通过。
  两次运行共覆盖该组 47 项。真实首次部署分别留有 `local-import-browser.log`、
  `compose-import-browser.log` 和 `typed-notification-final.log`。
- wheel 从归档候选构建，SHA-256 为
  `c7a0834bca371ed0630d4a9058fb16ce621c65848724750cfe7884d1a5b4f3d6`。
  源码外安装与消费者通过，161 个 Python 模块逐文件匹配候选，退休写入不存在。
- 候选 Docker 空实例、发布安全和四服务重启故障均通过。三次构建的镜像 ID 见 `docker-images.txt`。
  首次发布安全检查的临时目录在 Docker daemon 中不可见，使用可见目录重跑通过，原日志留存。
  同实例表单验证保留了缺部署凭据的结果，以及两次通知卡定位失败记录。使用隔离凭据和实际「编辑草稿」
  按钮后完成 Webhook 检查及发布。外部服务测试使用本地或隔离夹具。

测试与构建合并并行区间，计入首次失败、重试和收尾检查，占本轮用时不到 50%。

### 终审文档协调

A 终审通过后，将 Requirements、V2 Requirements、Product Experience 和 Architecture
的 TARGET 协调为 CURRENT，统一 Slice、Roadmap 和 Progress 的终审记录。Slice 合同中的
延期继续按原范围处理。
