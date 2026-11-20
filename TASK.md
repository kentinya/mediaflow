# Task PATCH-20261120-5 — 彻底退役配置草稿

用户授权将配置草稿退役作为独立 Task 激活，旧草稿功能直接退役。原 PATCH-20261120-4 的草稿管理方案已在 `e793431c` 撤回。按[开发流程 §3.1](docs/development-workflow.md#31-independent-minor-bugs)登记。

```text
Task ID: PATCH-20261120-5
Task Type: STANDALONE MINOR BUG
Parent Slice: NONE
Status: PLANNED
Task Base: e279077c4bca208ab7168983d15eca66ec8833d1
Difficulty: High
Test Level: T4
Planner / Reviewer: B
Implementation Authorization: USER AUTHORIZED
```

### 目标与现状

配置只在用户明确应用后成为持久的已发布快照。设置、首次初始化、恢复、通知和导入今天都有显式草稿操作，部分已支持直接保存的业务页仍通过持久草稿发布。用户需要在业务表单完成校验和应用，系统自动读回结果。旧草稿入口、状态、内容和兼容逻辑一起退役。

以[配置旅程](docs/product-experience.md#configuration-lifecycle)、[通知旅程](docs/product-experience.md#notification-definitions-and-deliveries)与[配置权威和运行时绑定](docs/architecture.md#configuration-authority-and-runtime-binding)为基准，保留权限、校验、证据、审计和快照绑定。变更范围限定受管配置。媒体任务的执行、原请求核实和逐项恢复沿用各自契约。

### 实施范围与顺序

1. **统一直接发布。** 通过现有应用服务归并 Web、API 和 CLI 的检查与发布规则。检查候选内容可产生脱敏证据，绑定该候选、依赖范围和当前生效基线。明确应用时后端复核基线、权限、证据及运行时可用性，原子写入已发布快照与审计。普通校验失败保留当前 Active 和输入。对并发后的同字段冲突提供明确处理。响应未知时按原请求身份自动只读核实，持续区分该次发布结果和当前生效值。未提交输入、只读证据和提交结果各自只服务于对应操作。持久配置修订只包含当前和历史已发布快照。
2. **闭合各入口。** 设置默认表单显示当前生效值和改动，单组点击「应用更改」，就地处理所需检查和重启提示。移除三个手动刷新入口，进入、切回、重连、提交完成自动同步，编辑中保留输入、焦点和基线。JSON 与脱敏导出按需打开。新实例可明确初始化为空配置。损坏配置通过权限校验和明确应用完整替换内容恢复。通知针对表单明确执行签名测试，再应用当前对象修改。Rules、Storage、资源库、媒体库、自动化及运行设置保留业务表单直接保存的旅程。配置 JSON 和脱敏包导入经明确核对及发布。进程采用以真实读回为准。
3. **一次退役旧草稿契约。** 移除 Web 草稿以及创建、选择、恢复、验证和发布草稿的独立操作。删除对应 API、旧 Web 深链、CLI 子命令及别名、旧草稿参数和格式、仓储分支及随仓调用方。旧请求按未知入口或无效输入处理，不设兼容转接。更新现行需求、旅程、架构和操作指引中的本次范围。保留只读的配置检查、已发布历史和脱敏导出。
4. **定义数据切换。** 对临时 Base 库副本验证一次切换至正式结构。新结构排除未发布的配置草稿及其专属验证证据。已发布配置、历史 ID、摘要、审计、任务固定引用及结果可继续使用。切换前列明受影响记录，遇到未发布记录仍被已受理任务引用时停止并定位。失败可完整回滚。实际旧库清理属于后续部署操作，依照经确认的数据范围执行。

### 验收条件

- [ ] 桌面和 390px 窄屏完成设置直接应用、自动同步、按需查看 JSON。异常时看到旧生效值、待检查或待核实的原因。后台读回保留编辑状态，发布后正确区分已发布、待采用及需重启。
- [ ] 真实 Web、API 和 CLI 完成空配置初始化、完整替换恢复、导入及业务对象保存。检查不足、输入变更、越权或基线过期时发布次数为零。Webhook 的一次明确测试只发一次探测。普通检查和发布产生零媒体写入、零新媒体任务和零通知投递。
- [ ] 同一配置基线的两个冲突发布只有一个成功。持久化写入失败时 Active 和审计一起回滚。服务端已提交但回包丢失时自动核实同一请求，核对期间的发布请求次数为零。恢复连接继续使用已受理任务的原配置引用。
- [ ] 旧草稿 API 在有效身份下返回 JSON `404`，旧 Web 深链按未知路由处理，旧 CLI 参数报错，旧草稿包不接受。所有入口的正常检查和应用均无可恢复的配置草稿，仓储和产物没有备用旧草稿流程。
- [ ] 用 Base 生成带已发布历史、未发布草稿、证据和已受理任务的临时库。切换后精确比较已发布身份、摘要、固定任务引用、审计和结果，确认旧草稿及其专属证据退出新结构。模拟切换失败和异常引用，核对完整回滚与重开结果。

### 验证计划

**Developer** 运行受影响测试。在根目录运行 `.venv/bin/python -m unittest tests.test_configuration_snapshot tests.test_configuration_status tests.test_configuration_package_exchange tests.test_configuration_destination_activation tests.test_system_settings_management tests.test_automation_settings_management`，覆盖发布、术语退役后的输入契约、并发和恢复。重点 SQLite 切换及旧入口拒绝的用例纳入这些受影响套件。在 `web/` 运行 `npm run typecheck`、`npm run test -- run src/features/configuration src/features/operations/AutomationSettingsPage.test.tsx` 和 `npm run test:e2e -- tests/e2e/configuration-settings.spec.ts tests/e2e/notifications.spec.ts`。运行 `git diff --check` 并提交实际结果。

**B** 对候选版本执行[适用的 T4 全量门禁](docs/development-workflow.md#shared-full-regression-commands)。在真实 Python、SQLite、浏览器和 CLI 上验收旧接口的负向矩阵与直接发布。使用隔离 SQLite 副本、两个浏览器会话和故障注入核对旧库切换、发布冲突、丢响应及进程采用。新增此链路的 `web/tests/e2e/configuration-settings.python.spec.ts`，在 `web/` 运行 `npm run build` 及 `npm run test:e2e -- --config=playwright.python.automation.config.ts tests/e2e/configuration-settings.python.spec.ts --output=test-results/configuration-retirement`，检查桌面及窄屏的真实页面和持久状态。配置退役按独立 Task 验收，基准和实际验证结果写入 B 检查点。
