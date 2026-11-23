# Task 58.2 — 通用 CLI 与配置 schema 11 退出

Next Action: DEVELOPER STARTS TASK 58.2 IMPLEMENTATION

用户已授权激活 Task 58.2。Developer 开始实施时将状态从 `PLANNED` 改为 `IN PROGRESS`。
[Slice 58 合同](SLICE.md#required-outcomes-and-surfaces) · [开发工作流](docs/development-workflow.md)

```text
Task ID: 58.2
Task Type: SLICE
Parent Slice: 58
Status: PLANNED
Task Base: 307eaaf8b006527a11fa2514de839a5528e6c202
Difficulty: High
Test Level: T4
Planner / Reviewer: B
Implementation Authorization: AUTHORIZED BY USER FOR TASK 58.2
```

## 目标与当前缺口

完成 RO-4，保留 RO-1 至 RO-3。部署者用现有四个服务入口启动实例，按主机指引领码、找回密码、停机备份和恢复。
管理员登录 Web 后，从系统设置发布配置，从库文件页浏览、整理与传输，从原 Task 查看结果和继续适用操作。
集成仍用既有 `/api/*` 和原权限令牌。重开当前受支持库后，原任务、结果、审计、快照和原请求仍可核对。
当前版本发现旧配置 schema 11 时，启动、探针和主机维护在写入前拒绝并给出原版本处理或新数据目录初始化的去向。

Task 58.1 已切换部署和主机维护。当前 wheel 仍安装由 `pyproject.toml` 注册的 `mediaflow`，
`mediaflow/cli.py` 转交 `final_cli.py`。Worker 仍识别 `direct-organize`，浏览器夹具仍从
`/__harness__/cli-files-list` 执行旧文件列表。当前 CI 与 wheel 检查运行 `config validate`；
schema 11 仍由 `configuration_data_switch.py`、配置仓储及调用者维持切换路径。

## 实施范围与开发指导

1. **迁移保留行为的调用。** 先核对 `final_cli.py` 的生产、脚本及测试消费者。把仍有效的断言接到
   已有共享用例或真实 Web/API。优先改 `scripts/operations_inventory_harness.py` 与
   `web/tests/e2e/live-files.python.spec.ts`，用两个现行库文件 API 与页面核对精确目录名、条目、
   游标分页、权限、失败恢复及读取零效果，再删除旧列表夹具入口。保留配置发布、计划解释、
   有界任务控制、审计和通知的现行断言。
2. **退役命令和专属 Task 路径。** 删除 console script、`mediaflow.cli`、`mediaflow.final_cli`、
   旧解析、过渡分派及专属命令实现。核对 `resident_entry.py`、
   `application/automation_definition_execution.py` 与 `application/manual_task_continuation.py`
   的真实调用关系，删除仅为 CLI 受理、执行和续作服务的路径，包括 `direct-organize`。
   保留现行 Web 人工整理、Automation 到期及 Run once、普通文件传输、有效固定快照和同 Task 续作。
   共享 Storage、Provider、计划、执行、审计、权限及读回逻辑留在现有应用边界。
3. **统一数据库适用性。** 在 `sqlite_applicability.py` 对配置标记落实当前 schema 12 规则；
   运行库 schema 60 和 store origin 规则保持。启动、探针、发码、备份校验及恢复统一复用适用性判断。
   删除 `configuration_data_switch.py`、仓储的 `apply_data_switch` 与切换事务、结果及旧处理指引。
   检查空库和当前仅配置库的创建／重开，保持来源备份、原库和所有合法历史的原值。
4. **切换制品和门禁。** CI 和工作流的样例校验复用实际配置加载与校验逻辑，可将
   `tests.test_runtime_strategy_configuration.RuntimeStrategyConfigurationTests` 的现行验证断言
   改为由加载入口验证样例，作为源码门禁。wheel 冒烟在源码外用同一加载逻辑验证样例，检查
   安装物中两个旧模块和旧命令缺席。镜像、冒烟、部署及恢复指引使用现有正式入口。
   A 终审时同步 V2 现行契约与接受账本。

## 验收标准

- [ ] 源码和清单、源码外安装的 wheel 与候选镜像均无旧入口、旧模块、分派或 CLI 专属工作路径。
  用已有调用、有效配置和隔离媒体通过正式入口核对拒绝，期间没有新增 Task、配置发布、Provider 请求
  或媒体效果。两种库的 Web/API 可照常浏览、翻页和读取受理结果。
- [ ] 用仓库现有 schema 11 夹具走四服务启动、探针、主机发码与恢复。启动和写入类入口在修改前拒绝，
  校验区分文件完整性与版本拒绝，源库／备份摘要不变，空恢复目标保持不存在。空库、当前仅配置库和
  当前运行库可启动或重开，当前备份可恢复。四服务和五项主机操作保持可用。
- [ ] 用 Slice Base 的实际 Web/API 与 Automation 建立受支持库和合法任务。候选重开原库后，读回原账号、
  令牌权限、配置、审计、请求、Task／Item／Result、原摘要和固定快照。通过正式 Web/Worker 在原 Task
  显式续作可处理条目，已完成及效果不确定项零重放。完成空库设置、文件夹整理、普通传输、Automation
  到期与 Run once、Webhook 投递和同版本恢复的合同验收。
- [ ] 样例继续通过同一配置验证行为，无 Storage 变更或工作受理。正向业务与安全断言覆盖现行入口，
  其中 RecognitionType C 复用 A 的 NamingPolicy 与 ClassificationPolicy 后仍为 C。

## 测试分工

### Developer 受影响测试

从仓库根目录运行下列范围。测试随入口迁移改名时，在交接中记录对应测试和实际命令。

```bash
python3 scripts/check_governance.py
PYTHONPATH=tests .venv/bin/python -m unittest \
  test_container_deployment test_container_probe test_resident_services test_runtime_lease \
  test_sqlite_backup test_sqlite_restore test_file_index_retirement \
  test_runtime_strategy_configuration test_release_validation test_release_security
PYTHONPATH=tests .venv/bin/python -m unittest \
  test_automation_entrance_recovery test_resident_correction test_configuration_snapshot
git diff --check
```

另运行本 Task 转接或修改的对应测试模块，并在 `web/` 从受影响的真实文件列表入口验证：

```bash
npm run build
npm run test:e2e -- --config=playwright.python.config.ts --output=test-results/task58.2-live-files tests/e2e/live-files.python.spec.ts
```

### B 验收与全量回归

- 按 [T4 共享门禁](docs/development-workflow.md#6-test-levels) 执行 Python、Web、源码外安装、
  wheel 和候选 release-security。对有正式配置的隔离候选核对旧入口拒绝、schema 11 拒绝及零效果。
- 用 `.venv/bin/python scripts/docker_empty_baseline_smoke_test.py --image "$candidate_image"` 和
  `.venv/bin/python scripts/docker_restart_fault_smoke_test.py --image "$candidate_image"` 验证正式
  Compose，复验根页领码找回、停机恢复与两个库的现行业务。运行适用的真实 Python Playwright
  文件、账号、整理与恢复旅程，分别保留产物。
- 以 `SLICE.md` 的固定 Base 创建隔离实例和真实受理记录，再用候选接续同一库完成 AC-05，
  保存两端制品标识、原 ID 与快照／效果读回。按合同完成需要补齐的 Slice 终验并交 A。

## 非目标

范围限于合同中的入口退役、数据库适用性及当前行为接续。沿用现有账号、权限、Web/API、Task 内核与
媒体效果模型。跨版本迁移、旧 CLI 工作接管及媒体备份沿用 Slice 明确范围。

## 上一项验收 — Task 58.1 PASS

```text
Reviewed Base: c8d8d30fa77c908bba4a73a1f9b9660ba51f4bfb
Reviewed Head: 307eaaf8b006527a11fa2514de839a5528e6c202
Decision: PASS
Slice Outcomes / Surfaces complete: NO
Next: TASK 58.2 PLANNED
```

B 独立审查完整 Task Base..Head。首个 Task 由 A 代 B 规划的用户授权例外限于规划。

- 本轮 `.venv/bin/python -m unittest discover -s tests` 运行 2374 项，2367 通过、7 跳过、零失败。
  治理、Ruff、编译、依赖一致性、样例配置与禁用依赖审计通过。精确候选 wheel 构建与源码外安装通过。
- 候选镜像 `sha256:33b31a99b243e56e7760dd2a5c6749e1fa80b1d0b447e65ee22ffc40b3b86c13` 的
  `docker_empty_baseline_smoke_test.py` 两段通过。无挂载空库可初始化、读回同一 Active，原进程领到
  到期工作并投递 Webhook。媒体挂载段在正式 API 受理、分析和核对期间零效果，显式确认后同一 Task
  完成一份原字节 COPY，两种库的普通 Copy 均完成，四个服务身份保持一致。
- 对比 `c0315d87..307eaaf8`，只有 Task／发布文档、空库冒烟和配置包单测变化。
  Web、原生浏览器夹具、Docker 构建及其他发布检查的相关输入一致，标准镜像 Config 和 RootFS
  也一致。复用 B 上轮 Web 单测 1642、常规 E2E 289、原生整理 E2E 18、Docker 重启故障和发布安全
  的通过结果，以及镜像页面建号／密码重置／旧会话撤销和源码／Compose 备份恢复的结果。
  本轮核对恢复指引中的 API 启动步骤与 Git 忽略路径。
- RO-1 至 RO-3 在 Task 58.1 的范围内已验收。RO-4 仍有旧入口、专属工作路径和 schema 11 切换，
  由 Task 58.2 完成，并补做合同的 Slice Base 合法任务接续验收。

本轮日志和制品摘要在
`.git/validation-evidence/307eaaf8b006527a11fa2514de839a5528e6c202/b-review/`。
复用的 B 结果在 `.git/validation-evidence/c0315d8795fb042448fdc22f1e05b1fb43fcb29f/b-review/`。
原 Task 和返工记录见 `307eaaf8:TASK.md`。
