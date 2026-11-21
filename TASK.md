# Task PATCH-20261120-5 — 彻底退役配置草稿

用户授权将配置草稿退役作为独立 Task 激活，旧草稿功能直接退役。原 PATCH-20261120-4 的草稿管理方案已在 `e793431c` 撤回。按[开发流程 §3.1](docs/development-workflow.md#31-independent-minor-bugs)登记。

```text
Task ID: PATCH-20261120-5
Task Type: STANDALONE MINOR BUG
Parent Slice: NONE
Status: FIX REQUIRED
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

### B 复核

```text
Reviewed Base: e279077c4bca208ab7168983d15eca66ec8833d1
Reviewed Head: 8c41756eb82e114bd7bf4e88e1aeaacbe3ac190d
Decision: FIX REQUIRED
Authorized bug acceptance complete: NO
Next: SAME TASK FIX LOOP
```

- Python 定向用例 3 项通过，覆盖无效候选拒绝后修正发布、Active 缺失时通过 API 恢复，以及运行准备失败时保留旧 Active 和进程绑定。最后一项没有检查未发布修订。用同一夹具调用现有 `PUT /api/operations/automation/settings`，将队列上限改为 31 后触发运行准备失败，收到 `503` 和 `stage=prepare`，临时 SQLite 中仍有 `validated` 与 `active` 两条记录。
- Web 定向组件测试 4 项通过、7 项因筛选未运行。丢响应后点击「核实当前状态」才继续，损坏 Active 页面只显示恢复提示，签名测试覆盖的是已发布定义，配置 JSON 默认可见。这些结果记录了候选当前行为。
- 在已登录且可读取现有 Webhook 的会话中，旧草稿创建入口返回 JSON `404`，旧 Webhook 草稿发布入口返回 JSON `405`，与验收要求的 `404` 不符。
- 已确认以下阻塞，T4 全量门禁、Base 库切换和真实桌面及窄屏浏览器验收留待修复后的候选。

#### Developer 修复指导

1. **把现有保存入口接到直接发布。** 从运行设置的保存开始，连同 Rules、Storage、两类库和自动化一起移除先写草稿再激活的调用。让校验与证据对应本次输入和生效基线，最后一次事务写入已发布快照和对应审计。`publish_document` 当前先提交 `validated` 再清理，直接发布也要去掉这个持久中间状态。沿上述运行设置请求复测，准备失败后查询应只剩原有已发布修订，并检查失败写入的事务回滚。
2. **让设置页自动同步和核实。** 复用运行设置的原请求结果查询方式。设置页点击「应用更改」后丢响应时，自动只读核实本次请求，分别显示这次应用结果和当前生效值。覆盖另一会话随后发布的情况，核实期间发布请求保持一次。进入、切回、重连和提交完成时读回，保留正在编辑的输入及焦点。移除剩余刷新按钮，把 JSON 移到按需打开的入口。
3. **在通知表单先测再应用。** 从现有新建和编辑表单对当前地址和签名引用执行一次明确的签名测试。编辑地址或签名引用后，前一次证据失效。用户完成所需测试后可应用当前对象，普通检查和应用均不发送通知。把旧 Webhook 草稿发布请求归入未知入口并删除旧客户端调用。用已存在的 Webhook 重测 JSON `404`。
4. **把完整替换接回设置页和 CLI。** 从设置的损坏状态打开完整配置输入，沿用现有完整替换 API 的权限和校验，经明确应用后读回结果。CLI 的完整发布也应可完成同一恢复。更新部署指引中 `config draft-import` 后到 Web 选择草稿的步骤，并把仍操作配置草稿的 Web 测试换成现有页面上的直接发布旅程。

Developer 按原计划运行受影响用例，补上上述路径的回归断言，并在同一 Task 记录候选 SHA、命令和实际结果。B 对修复后的候选复核原验收条件及 T4 门禁。

### B 返工复核

```text
Reviewed Base: e279077c4bca208ab7168983d15eca66ec8833d1
Reviewed Head: 79f489eb2436c2e77f57671249044ea5a587aa2d
Decision: FIX REQUIRED
Authorized bug acceptance complete: NO
Next: SAME TASK FIX LOOP
```

- 运行设置准备失败后保留原 Active，SQLite 中没有未发布修订。旧草稿入口拒绝、设置按原请求核实、Webhook 表单操作及现有 API 的完整替换通过定向回归。Python 共 58 项定向用例通过，设置和通知的 Web 组件测试共 11 项通过。
- 从现有规则对象测试入口新建识别类型并执行测试，测试返回成功，SQLite 修订从 `active` 变为 `draft`、`active`。既有命名预览入口也留下 `validated` 修订。用户只测试表单，即使随后关闭且从未保存，配置内容已经写入数据库。
- 用独立的临时部署配置和 SQLite 运行 CLI。首次执行 `config initialize` 因缺少 `actor` 抛异常。随后执行 `config publish --file`，目标 Storage 根目录不存在，命令依然报告发布成功。修复目标目录并模拟已发布的 Active 缺失后，再次提交完整文件，命令提示需要明确替换，现有 CLI 无法提交替换。
- 按部署指南进入「系统设置 → 高级配置 → 配置 JSON」，页面只提供只读查看和脱敏导出。完整版输入仅在 Active 损坏时出现。首次导入完整配置、在可用配置上应用修改后的 JSON，以及重新导入脱敏包的 Web 旅程仍缺少提交入口。
- 确认以上阻塞后结束本轮产品测试。T4 全量、真实桌面及窄屏浏览器验收，以及由 Base 真实生成数据的切换验收待修复后执行。

#### Developer 修复指导

1. **整理规则的测试不保存表单。** 将规则对象测试和现有预览的候选改为本次检查期间使用的内容，复用当前候选解析和只读检查。需留存的结果只保留检查证据，绑定输入和生效基线。沿现有识别类型测试和命名预览执行一次，确认测试结果仍可读，关闭表单后重新打开 SQLite，配置修订清单和 Active 与进入时一致。
2. **闭合 CLI 初始化、检查和恢复。** 给 `config initialize` 设置发布所需的操作人，使用最小部署配置验证首次产生空 Active。`config publish --file` 使用 Web 同一套适用的只读检查，目标根目录不可达时拒绝发布，恢复目录后再发布。接入现有完整替换规则，让操作员在 Active 损坏时明确提交完整文件并读回新 Active。
3. **从高级配置导入并应用。** 在「系统设置 → 高级配置」提供完整 JSON 和脱敏包的核对、应用入口，保留现有按需只读 JSON。接入现有完整配置发布和包导入服务。覆盖首次导入和替换可用配置，检查失败时保留输入，修改后可重新应用。同步部署指引与实际页面操作。

Developer 在同一 Task 交付修复并记录上述入口的受影响测试结果。B 在新候选上继续原验收计划。

### B 第二次返工复核

```text
Reviewed Base: e279077c4bca208ab7168983d15eca66ec8833d1
Reviewed Head: 5dad384d48d4d0df283ae073f76944c7ae93864a
Decision: FIX REQUIRED
Authorized bug acceptance complete: NO
Next: SAME TASK FIX LOOP
```

- Python 定向测试 69 项通过，覆盖规则对象测试、规则预览、配置包交换、CLI 初始化、目标目录缺失时拒绝发布及显式替换恢复。Web 定向组件测试 38 项通过，覆盖高级配置 JSON 和脱敏包导入、规则对象测试及通知表单。规则测试后的 SQLite 修订只剩已发布的 Active。
- 用现有测试夹具中的配置管理员账号导出当前脱敏包，再应用原包。账号有配置管理权限，缺少激活权限。提交同包的完整 JSON 返回 `403`，通过现有包导入 API 应用返回 `200`，并产生新的 Active。导入在 `8c41756e` 改为直接发布时沿用了旧导入入口只检查管理权限的规则。
- 在整理规则表单改识别类型名称，仅执行对象测试。用响应给出的修订 ID 打开现有配置详情 API，仍得到 `200`，返回 `draft` 和刚测试的完整未提交配置。`20ad26f2` 把候选搬到共享的进程内修订表，规则测试命令完成后仍可按配置修订读取。
- T4 全量、真实浏览器和 Base 数据切换验收安排在修正后的候选上。

#### Developer 修复指导

1. 脱敏包应用沿用完整 JSON 发布的管理和激活权限。用配置管理员和具有发布权限的账号分别验证现有导入入口，核对拒绝请求前后的 Active 与审计，以及允许请求的发布结果。
2. 规则对象测试和预览将候选限定在检查请求内，命令结束后释放候选。规则界面按原表单展示检查结果，配置详情、对象和导出仅按已发布修订读取。沿现有规则测试和配置详情入口验证，测试成功后按返回身份读取配置修订应得到 `404`。
3. 更新现行配置与通知旅程中的旧草稿步骤。通知从新建或编辑表单测试当前输入，再明确应用。首次部署按现有设置页操作初始化空配置或导入完整 JSON。

### B 第三次返工复核

```text
Reviewed Base: e279077c4bca208ab7168983d15eca66ec8833d1
Reviewed Head: 86274af834b0564c48f9791f013a30c2a73ddf26
Decision: FIX REQUIRED
Authorized bug acceptance complete: NO
Next: SAME TASK FIX LOOP
```

- 69 项 Python 定向测试通过。脱敏包发布权限、规则对象测试和预览结束后配置详情返回 `404` 的回归通过。生产 Web 构建成功。
- **导入回包丢失后页面误报未发布。** 在 390px Chromium 中打开「系统设置 → 高级配置 → 导入配置」，修改日志保留天数并应用完整 JSON。真实 Python API 返回 `200`，SQLite 已切换到新发布版本。仅丢弃浏览器收到的回包，页面显示「完整配置未发布」。另一会话正常应用日志设置后，首个会话重连，仍需点击「核实当前状态」。页面只读取状态和修订，原请求核实次数为零，首个会话的发布请求共一次。
- **切回后设置表单仍展示旧生效值。** 两个真实浏览器会话分别在日志组发布 51 天和 52 天。第一个会话切回并重连，状态摘要读到 52 天对应的版本，表单仍读旧修订并显示 51 天，当时表单没有未提交输入。自动同步使用的是上一次应用选中的修订，而非新读到的生效修订。
- T4 全量门禁、完整桌面与窄屏验收及 Base 数据切换验收待修复后执行。

#### Developer 修复指导

1. 将完整 JSON、脱敏包和完整替换的发布接入设置现有的按请求核实流程。请求身份随发布结果持久化，应用回包丢失时显示待核实，重连自动只读查询原请求。沿真实 JSON 导入复测「首次发布成功 → 回包丢失 → 另一会话发布 → 重连」，页面应同时显示首次发布的结果和当前生效版本，首个会话的发布请求共一次。
2. 让设置表单随状态查询读到的最新生效修订更新。沿两个会话分别应用日志设置的旅程复测，切回或重连时摘要和未编辑字段对应同一个生效版本。另测第一个会话正在编辑的同一字段，保留原输入、焦点和编辑基线，显示该字段已被另一会话修改的情况。将真实浏览器规格中仍使用「保存到草稿」的相应场景改为直接应用旅程。

### B 第四次返工复核

```text
Reviewed Base: e279077c4bca208ab7168983d15eca66ec8833d1
Reviewed Head: 047a1581b28bb7fbbbfa93b41bc7e958b3d0d9ab
Decision: FIX REQUIRED
Authorized bug acceptance complete: NO
Next: SAME TASK FIX LOOP
```

- 35 项 Python 定向测试、12 项设置页组件测试和生产 Web 构建通过。真实 Chromium 连到 Python 和临时 SQLite 后，未编辑的设置表单在切回时读到了另一会话刚发布的值。390px 设置页导入完整 JSON，服务端先完成发布，另一会话接着应用日志设置，再丢弃首个会话的导入回包。页面自动按原请求确认首次发布已被后续版本替换，首个会话只发出一次发布请求。
- **首次核实还没有结果时，重连未继续核实。** 从同一个导入入口发送完整 JSON，让第一次只读核实先于原提交完成。真实 API 返回 `UNRESOLVED`。原提交随后完成，浏览器断开并恢复连接。页面刷新了当前配置，原请求仍显示待核实。点击「核实当前状态」后，同一请求才得到 `COMMITTED`。整个旅程对同一输入只发布一次。设置页自 `30f5c022` 只自动核实一次。`19216abc` 将完整配置导入接入该流程，但重连仍只刷新当前配置。
- 确认上述阻塞后结束定向验收。T4 全量和 Base 数据切换验证待执行。

#### Developer 修复指导

将已有重连和切回读回接到待核实的原请求。首次查询返回 `UNRESOLVED` 时继续保留请求身份，重连后用同一只读端点查询。复测「导入 → 回包丢失 → 首次查询尚无结果 → 原提交完成 → 重连」的真实页面操作。验收看重连后自动解除待核实，显示原请求发布结果和当前生效版本，发布请求总数为一次。复用现有测试入口，把对应的旧草稿场景更新为直接应用。

### B 第五次返工复核

```text
Reviewed Base: e279077c4bca208ab7168983d15eca66ec8833d1
Reviewed Head: e9196cc2c1cfc72fc8ffa55bce8fd11d999124e8
Decision: FIX REQUIRED
Authorized bug acceptance complete: NO
Next: SAME TASK FIX LOOP
```

- 生产构建和 13 项设置页组件测试通过。390px Chromium 连接真实 Python 和临时 SQLite，复测完整 JSON 导入回包丢失。首次核实返回 `UNRESOLVED`，原提交完成后重连，页面自动用同一请求身份读到 `COMMITTED` 并解除待核实。浏览器只发送了一次发布请求。
- 使用实际 Base 代码生成库，再复制给候选。库中含两份已发布快照、一份草稿、一份已验证候选、一条候选检查证据，以及固定到已发布历史版本的任务和结果。操作员用 `config status` 查看库的状态，命令把 schema 从 11 升到 12，删除两份未发布修订及其检查和相关审计，输出没有列出两个受影响的修订 ID。`8c41756e` 将清理放在打开配置仓储时，状态查询共用了这一入口。
- 在副本上核对了发布版本 ID、摘要、对应审计、任务记录和结果，均与切换前相同。用同一 Base 数据在独立副本上分别模拟异常任务引用和 SQLite 删除失败，两次都终止切换，重开后数据库逻辑内容与切换前一致。T4 全量门禁仍待执行。

#### Developer 修复指导

从现有状态查询和部署入口完成切换旅程。先让操作者只读查看受影响的未发布修订及证据范围，按 Task 已约定的部署范围确认后再执行清理。沿本轮 Base 副本验证首次查看仍是 schema 11 且数据未变，确认后才切换为 12。沿用现有切换事务，再核对已发布历史、审计、任务固定引用、结果，以及两种切换失败的回滚。

### B 第六次返工复核

```text
Reviewed Base: e279077c4bca208ab7168983d15eca66ec8833d1
Reviewed Head: 626f15648084bb9dd518991e7e330cedd39c6de3
Decision: FIX REQUIRED
Authorized bug acceptance complete: NO
Next: SAME TASK FIX LOOP
```

- 上轮旧库切换阻塞已解决。用实际 Base 生成的库副本执行 `config status`，看到两份未发布修订和一份检查证据。状态查询和未带 `--confirm` 的 `config retire-unpublished` 执行后，SQLite 文件校验和均与操作前一致。确认后切到 schema 12，清除所列记录。已发布修订 ID、摘要、对应审计、任务固定引用和任务结果逐项一致。异常任务引用和 SQLite 删除失败两种情况下均拒绝切换，重开后逻辑内容与各自操作前一致。
- Python 全量执行 2322 项，跳过 7 项，其余通过。Web 单测 104 个文件、1599 项通过。Node 设置与通知浏览器用例 13 项通过。生产 Web 构建、类型检查、Lint、Python 编译、依赖检查、两份示例配置验证和治理检查通过。日志及浏览器 trace 位于本地 `.git/validation-evidence/626f15648084bb9dd518991e7e330cedd39c6de3/b-review/`。
- **真实浏览器验收仍在执行旧草稿旅程。** Chromium 连接真实 Python 和临时 SQLite，从「系统设置 → 日志」修改保留天数，页面显示「应用更改」。`web/tests/e2e/automation-settings.python.spec.ts:1308` 仍等待「保存到草稿」，30 秒超时，未执行到发布和读回断言。同文件仍有以草稿为目标的并发和丢回包用例，Task 指定的 `configuration-settings.python.spec.ts` 尚未提交。本次失败定位在浏览器规格，直接应用的真实验收仍待完成。
- **质量检查失败。** `ruff check` 报 `mediaflow/interfaces/service_api.py:3075` 超长，`ruff format --check` 报 `tests/test_configuration_snapshot.py`。Web Prettier 报 `ConfigurationPage.tsx`、`ConfigurationPage.test.tsx` 和 `configuration-settings.spec.ts`。
- 完整 Node 浏览器门禁、真实设置页直接应用规格及适用的打包和生产验证待 B 在修正候选上完成。

#### Developer 修复指导

1. 用现有真实 Python Playwright 配置和夹具，把设置页的旧草稿用例迁移到 `web/tests/e2e/configuration-settings.python.spec.ts`，保留原文件的自动化业务用例。沿「系统设置 → 日志 → 修改保留天数 → 应用更改 → 读回当前生效值」覆盖桌面及 390px 窄屏。把原检查断言迁移到当前检查和发布入口，确认检查拒绝时仍显示原生效值并保留输入。两个会话在同一生效基线编辑同一字段时，只允许一次发布并保留另一会话的输入。丢回包测试让真实后端先提交，再从页面重连，确认自动只读核实原请求、显示对应结果，发布请求共一次。
2. 修复上列 Ruff 和 Prettier 问题。用 `playwright.python.automation.config.ts` 跑迁移后的设置规格及直接受影响的自动化浏览器用例，运行相关格式检查，并在同一 Task 记录实际结果。

### B 第七次返工复核

```text
Reviewed Base: e279077c4bca208ab7168983d15eca66ec8833d1
Reviewed Head: 38efbce447047ddb5433a99437a772f3645d2f1c
Decision: FIX REQUIRED
Authorized bug acceptance complete: NO
Next: SAME TASK FIX LOOP
```

- 上轮的设置页验收和格式检查已通过。生产 Web 构建后，用真实 Python 和临时 SQLite 运行 `configuration-settings.python.spec.ts` 与 `automation-settings.python.spec.ts`，共 20 项通过。桌面及 390px 直接应用、拒绝后保留输入、并发只发布一次、丢回包重连后自动核实均通过。Ruff、Prettier、Web 类型检查和 Lint 也通过。
- **真实通知列表无法使用。** 用管理员登录真实 Python Web，从侧栏打开「通知」，页面显示「通知定义暂时不可用」，看不到已有定义、新建或编辑入口。页面发出的 `GET /api/operations/notifications/webhooks` 返回 `200` 和一条已发布定义。将该响应交给页面解析函数，拒绝项为 `items[].actions.activate`。后端已禁用草稿激活并返回 `requiresConfirmation: false`，前端还要求旧动作必须为 `true`。Node 假服务仍返回 `true`，所以已有浏览器用例没有覆盖这个失败。真实 API 还把列表中的编辑权限绑在已退役的草稿上，管理员收到 `edit.available=false` 和空路径。
- 真实通知截图和日志位于 `.git/validation-evidence/38efbce447047ddb5433a99437a772f3645d2f1c/b-review/`。本轮确认通知阻塞后结束测试，B 在修正候选上完成 T4 全量及适用的打包和生产验证。

#### Developer 修复指导

让真实通知列表、详情和表单共同使用当前已发布 Webhook 和发布权限。调整 `service_api.py` 与 `notification.ts`，从通知响应和解析移除退役的草稿激活动作，并让管理员的编辑入口指向当前已发布定义。同时清理退出编辑时承诺保留草稿的提示，保留继续编辑和放弃输入的选择。用同样的响应契约更新 Node 夹具。用现有真实 Python 浏览器入口复测「通知列表 → 编辑已发布定义 → 签名测试当前输入 → 应用更改 → 回到列表读回新值」，核对测试只发一次请求、应用只发布一次，以及无发布权限账号只能查看。

### Developer 第八轮修复报告

```text
Task Base: e279077c4bca208ab7168983d15eca66ec8833d1
Candidate: 37039d70f3caa015d547c91e1d178a1c7c7502b1
Decision: READY FOR B REVIEW
Authorized bug acceptance complete: NO
```

- 通知列表、详情和表单统一读取当前已发布 Active Webhook。列表不再从打开草稿查找编辑目标；管理员的编辑、复制、启用、停用和签名测试绑定当前 Active 修订，且同时要求管理配置与发布配置权限。无发布权限账号只读。
- 从通知响应和前端解析移除退役的草稿创建、验证和激活动作；详情和列表不再显示草稿修订状态，编辑退出提示改为“当前生效配置不会被修改”。Node 假服务同步移除这些动作，真实 Python 通知列表与编辑旅程恢复可用。
- 真实 Python 浏览器旅程已更新为「通知列表 → 编辑已发布定义 → 签名测试当前输入 → 应用更改 → 回到列表读回新值」。应用写入真实 Python/SQLite；签名探测由浏览器本地路由承接，避免向 example.invalid 发送外部请求。实测发布请求 1 次、测试请求 1 次，读回最大尝试次数 7。
- Python `tests.test_v2_notification_operations` 26 项通过；Task 指定的六个配置相关 Python 模块 159 项通过。Web `src/features/operations` 32 个文件 390 项通过；Task 指定的配置组件 5 个文件 67 项通过。Node 通知浏览器用例 9 项通过；真实 Python 通知浏览器用例 1 项通过。
- `npm run build`、TypeScript、ESLint、Prettier、Ruff check/format、`py_compile`、`git diff --check` 与 governance check 通过。
- 未运行 T4 全量门禁、真实桌面/390px 通知截图验收及 Base 数据切换；按 Task 分工留给 B。外部 HTTPS 签名探测未在浏览器验收中真实外发，后端签名测试与失败分类仍由 Python 用例覆盖。

### B 第八次返工复核

```text
Reviewed Base: e279077c4bca208ab7168983d15eca66ec8833d1
Reviewed Head: d2b4019091d55253905c3acc37df3726b1d38b93
Reviewed Implementation: 37039d70f3caa015d547c91e1d178a1c7c7502b1
Decision: FIX REQUIRED
Authorized bug acceptance complete: NO
Next: SAME TASK FIX LOOP
```

- 上一轮通知列表阻塞已解决。生产 Web 构建通过，真实 Python 浏览器用例 1 项通过。管理员从通知列表打开已有定义，发送一次签名测试、应用一次，再回到列表读到最大尝试次数为 7。只读账号能查看该定义。浏览器验收使用本地签名测试响应，发布和读回经过真实 Python 与临时 SQLite。
- **签名测试没有约束后端发布的地址。** 从通知的实际定义详情取得测试和编辑入口，用现有 Python 通知夹具测试地址 A，再把地址改为 B 后提交。签名传输只收到一次发往 A 的请求。编辑接口返回 `200` 并将地址 B 写成新的生效配置，未创建通知投递。当前编辑接口只收配置内容和版本，发布前未核对签名测试对应的地址与密钥引用。
- **通知应用丢回包后没有自动核实。** 从通知列表打开编辑器，在 390px 下把最大尝试次数改为 7，完成签名测试后点击「应用更改」。真实后端已提交，仅丢弃浏览器回包。页面显示「命令结果未知」，重连后仍保持该提示，浏览器没有发出核实请求，「应用更改」已经可再次点击。本轮发布请求共一次。独立读取定义确认这次提交已经生效。
- 证据位于本地 `.git/validation-evidence/d2b4019091d55253905c3acc37df3726b1d38b93/b-review/`。确认以上阻塞后结束本轮测试，B 在修正候选上继续 T4 全量及适用的打包和生产验证。

#### Developer 修复指导

1. 将通知新建和编辑的现有签名测试接到同一发布检查。成功结果要能在后端对应到本次定义、被测地址、密钥引用和该次编辑使用的生效基线。提交时核对这份结果。沿现有通知详情公布的测试和编辑入口复测，测试 A 后改为 B 时应拒绝应用且保持生效配置与发布审计，测试 B 后再应用才产生一份新生效配置。普通应用仍发送零次探测，测试结果只保留核验所需的信息。
2. 通知表单应用复用现有配置发布的请求身份和只读核实机制。发布回包丢失时保留原请求身份，核实期间保持应用按钮不可提交。重连后自动核实该次请求，分别显示本次应用结果和当前生效定义。沿真实页面复测「编辑 → 签名测试 → 应用提交成功但回包丢失 → 重连」，断言原请求可确认且发布总数为一次。

### Developer 第九轮修复报告

```text
Task Base: e279077c4bca208ab7168983d15eca66ec8833d1
Candidate: e6363c6bf4e7f0efc498f0800ce11f88123ab40b
Implementation: 3e6b202b6cf4e2ebd9ef271cace94c39b2b36dfc
Decision: READY FOR B REVIEW
Authorized bug acceptance complete: NO
```

- 通知新建与编辑的签名测试现在提交当前表单及精确生效基线。成功探测在服务端留下有界证据，只含定义 ID、被测地址、密钥引用、操作者和基线身份；提交时在暂存候选前核对同一表单。先测试 A 再改为 B 会以 `409` 拒绝，Active 与发布审计不变；测试 B 后再应用才生成一份新生效配置。应用本身不发送探测，证据只保留核验所需信息。
- 通知新建和编辑的应用请求携带 `submissionId`，发布审计记录该身份。回包丢失时保留原请求，应用按钮保持阻止，自动及重连后只用同一只读端点核实；页面分别显示本次请求结果与当前生效定义，成功核实后刷新列表。首次核实为 `UNRESOLVED` 时保留身份，重连继续同一核实，发布请求总数保持一次。
- 创建表单复用同一请求身份、核实与按钮阻止语义。真实 Python 通知浏览器用例增加「签名测试 → 应用回包丢失 → 首次核实无结果 → 重连自动确认 → 列表读回」链路；正常编辑链路继续从列表读回当前定义。
- 相关旧草稿式 Webhook 测试夹具改为激活后经签名测试和证据应用；不安全定义仍由规范校验返回 `400`。浏览器运行器改为通过真实 API 的本地签名传输承接一次探测，仍由真实 Python 签名与证据门禁校验。

实际结果：

- `.venv/bin/python -m unittest tests.test_configuration_snapshot tests.test_configuration_status tests.test_configuration_package_exchange tests.test_configuration_destination_activation tests.test_system_settings_management tests.test_automation_settings_management tests.test_v2_notification_operations tests.test_webhook_management tests.test_webhook_url_security tests.test_notification_delivery_management`：217 项通过。
- 最终定向 `.venv/bin/python -m unittest tests.test_v2_notification_operations tests.test_webhook_management tests.test_webhook_url_security tests.test_notification_delivery_management`：58 项通过。
- `web/` 的 `npm run test -- run src/features/operations/NotificationRouter.test.tsx`：6 项通过；`npm run typecheck`、`npm run lint`、`npm run format:check`、`npm run build` 通过。
- `npm run test:e2e -- tests/e2e/notifications.spec.ts`：9 项通过。
- `npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts --grep "Notifications page edits|lost apply response"`：2 项通过。
- Ruff check/format、`py_compile`、`git diff --check` 与 governance check 通过。

剩余风险：真实浏览器中的外部 HTTPS 探测由隔离夹具的本地传输承接，实际外网连接仍由 Python 传输分类用例覆盖；T4 全量、真实桌面/390px 截图及 Base 数据切换按分工留给 B。未推送、未部署。

### B 第九次返工复核

```text
Reviewed Base: e279077c4bca208ab7168983d15eca66ec8833d1
Reviewed Head: 914d153ad06b709390f9a789a2f2c70f52d30e0c
Reviewed Implementation: e6363c6bf4e7f0efc498f0800ce11f88123ab40b
Decision: FIX REQUIRED
Authorized bug acceptance complete: NO
Next: SAME TASK FIX LOOP
```

- 上轮两处问题通过复验。Python 通知发布定向用例 6 项通过，覆盖测试 A 后应用 B 被拒绝、缺少成功测试证据时拒绝及原请求核实。真实 Python 浏览器的通知用例 2 项通过，覆盖编辑后读回，以及编辑提交成功但回包丢失时重连自动核实原请求。设置和自动化运行设置用例 20 项通过。
- Python 全量执行 2326 项，7 项跳过，其余通过。Web 单测 104 个文件、1595 项通过，完整 Node 浏览器套件 276 项通过。生产 Web 构建、类型检查、Lint、Prettier、Ruff、Python 编译、依赖和示例配置验证均通过。Python wheel 独立安装后的冒烟及恢复用例通过。真实 Base 库副本复验中，状态读取及未确认的切换保持文件一致，确认后已发布修订、审计、任务及结果仍一致。Docker 空配置及媒体挂载旅程通过，包括隔离 HTTPS 接收端收到签名通知。
- **新建通知重载后无法自动核实。** 从「通知 → 新建 Webhook」填写并完成签名测试，点击「应用更改」。真实后端返回 `200` 并发布了定义，仅丢弃浏览器回包，让第一次只读核实返回待核实。此时重载页面并以同一账号重新连接，页面显示空白新建表单，发出零次核实请求。浏览器仍保留待核实记录，SQLite 也读得到已发布定义。手动重新输入原标识符后，页面才查询原请求。本次只发出一次发布请求。`3e6b202b` 按用户输入的标识符保存请求身份，新建路由重载时没有标识符用于恢复。
- **Docker 重启和发布安全验收仍调用旧草稿 API。** 将临时目录移到 Colima 可挂载的位置后，两套脚本都已启动真实服务。`scripts/docker_health_smoke_test.py:113` 的共用初始化调用了已退役的 `POST /api/configuration/drafts`，两套脚本均收到 `404` 并提前退出，后续安全和重启断言尚未执行。
- 本地日志与截图位于 `.git/validation-evidence/914d153ad06b709390f9a789a2f2c70f52d30e0c/b-review/`。B 在修正候选上完成两条阻塞旅程和 T4 门禁。

#### Developer 修复指导

1. 新建页按当前账号和新建入口恢复待核实请求，从已保存的请求里取回原标识符。页面重新打开或重新连接时自动只读核实，核实期间阻止再次应用。复用现有通知签名测试夹具和原请求核实接口，覆盖「新建 → 签名测试 → 应用已提交但回包丢失 → 首次核实待定 → 整页重载 → 重新连接」，验证页面自动确认并打开已发布的定义，整个旅程只有一次发布。
2. 将 `docker_health_smoke_test.py` 的共用配置初始化改为现有 `POST /api/configuration/publish`，沿用空配置 Docker 验收中的直接发布请求和生效检查。保留各调用方原有断言。Developer 复验共用初始化可以在真实容器中发布并读回 Active，B 负责两套完整 Docker 门禁。

### Developer 第十轮修复报告

```text
Task Base: e279077c4bca208ab7168983d15eca66ec8833d1
Candidate: 0ae629b7a3bfb2bd7e0a7a2bfe0dae02409a3385
Decision: READY FOR B REVIEW
Authorized bug acceptance complete: NO
```

- 新建页的待核实请求改为按账号和新建入口保存，标识符随请求记录而不是作为键。整页重载或重新连接后从同一账号的已保存请求取回原标识符，自动用原 `submissionId` 只读核实；核实和待核实期间应用保持阻止。核实完成确认发布后直接打开对应已发布定义。原 `guardRef` 改为当前渲染的卡片守卫，避免核实先于守卫挂载时只显示结果却不导航。
- 共用 Docker 初始化 `activate_runtime` 改为 `POST /api/configuration/publish`，发布后读取 `/api/configuration` 核对 Active 的 revision 和 digest。`prepare_files`、transfer-impact 夹具补齐示例配置要求的 `Movies`、`TV Shows` 媒体库根目录；重启夹具的零效果断言改为只拒绝文件，允许已配置的空目录。
- 一并把 `docker_smoke_test.py`、transfer lifecycle 脚本和 `make_deployment_config.py` 说明中的旧草稿调用/描述切换为直接发布。

实际结果：

- `.venv/bin/python -m unittest tests.test_configuration_snapshot tests.test_configuration_status tests.test_configuration_package_exchange tests.test_configuration_destination_activation tests.test_system_settings_management tests.test_automation_settings_management`：159 项通过。
- `.venv/bin/python -m unittest tests.test_v2_notification_operations tests.test_webhook_management tests.test_webhook_url_security tests.test_notification_delivery_management`：58 项通过。
- `npm run test -- run src/features/operations/NotificationRouter.test.tsx`：7 项通过，含新建页丢回包后整页重载自动核实的新增用例。
- `npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts --grep "Notification"`：3 项通过。新增真实 Python 用例覆盖「新建 → 签名测试 → 应用已提交但回包丢失 → 首次核实待定 → 整页重载 → 重新连接 → 自动确认并打开已发布定义」，发布请求 1 次，核实至少 2 次。
- `npm run typecheck`、`npm run lint`、`npm run format:check`、`npm run build` 通过；构建产物为 `index-D5aKJ4_0.js` / `index-Tw5pYUJe.css`。
- Ruff check/format、`py_compile`、`git diff --check`、治理检查通过。
- `TMPDIR=<repo>/.git/smoke-tmp .venv/bin/python scripts/docker_health_smoke_test.py` 已通过共用初始化：真实容器内发布成功并从 `/api/configuration` 读回同一 Active。之后在 `chmod 000` 媒体根目录的降级步骤等待 API `unhealthy` 超时；Colima 的挂载未向容器反映该权限变化，完整健康套件未在本机通过。

剩余风险：T4 全量、重启/发布安全两套完整 Docker 门禁、真实桌面与 390px 截图、Base 数据切换按 Task 分工留给 B。仓库内仍有三个未被现行文档或门禁引用的历史浏览器证明脚本描述已退役草稿界面；它们不是产品入口或当前验证入口，本轮未改。

### B 第十次返工复核

```text
Reviewed Base: e279077c4bca208ab7168983d15eca66ec8833d1
Reviewed Head: c4d3b79d6d5d0aa7c0b6dcb87c7da17e323d6058
Reviewed Implementation: 0ae629b7a3bfb2bd7e0a7a2bfe0dae02409a3385
Decision: FIX REQUIRED
Authorized bug acceptance complete: NO
Next: SAME TASK FIX LOOP
```

- 上轮两处阻塞已解决。真实 Python 浏览器通知用例 3 项通过。新建 Webhook 应用后即使回包丢失，整页重载并重新连接也会自动核实原请求，打开已发布定义，整个旅程只提交一次。Docker 重启与故障验收、发布安全验收均通过。空配置和媒体挂载旅程通过。
- **自动化列表仍提供配置草稿筛选，并把生效版本标成一份草稿。** 管理员登录真实 Web，从「任务中心 → Automation」看到两条已发布任务。选择「发布状态 → 仅草稿」后，实际列表请求携带 `state=draft-only`，返回 `200` 和零条结果，页面显示「没有匹配的自动化任务」。清除筛选后两条任务重新出现。打开列表时，后端还给已发布行返回 `draftState.present=true`，其中的修订 ID 与该行的 Active 相同，并把旧的后继草稿创建动作标为可用。首轮退役把现有 Active 放进了原来的草稿合并逻辑，因此实际响应仍暴露退役状态和入口。
- Python 全量执行 2326 项，跳过 7 项，其余通过。Web 单测 104 个文件、1596 项通过，完整 Node 浏览器套件 276 项通过。真实设置和自动化运行设置浏览器用例 20 项通过。生产 Web 构建、类型检查、Lint、Prettier、Ruff、Python 编译、依赖检查、示例配置验证和治理检查通过。候选 wheel 冒烟及独立安装后的恢复用例通过。
- 复用先前 B 对真实 Base 库副本的切换证据。数据切换代码、CLI、配置仓库及相关测试自该候选未变。只读查询及未确认的切换不修改旧库，确认后保留已发布版本、审计、任务引用和结果。
- Developer 的 Docker 健康检查记录显示，容器直接发布及读回成功，媒体挂载权限降级阶段等待 API 变为 `unhealthy` 超时。完整健康旅程仍待验证。其余本轮证据在 `.git/validation-evidence/c4d3b79d6d5d0aa7c0b6dcb87c7da17e323d6058/b-review/`，包含自动化操作截图和实际列表响应摘要。

#### Developer 修复指导

1. 从自动化列表删除「发布状态」中的草稿筛选和对应查询。用当前生效配置直接投影列表，删除把 Active 当草稿合并的逻辑，以及列表和定义详情中的旧草稿状态、计数和创建动作。同步 Web 响应模型与测试夹具。原草稿筛选值按无效输入处理。
2. 从「任务中心 → Automation」复测有现存任务的列表。验证能通过启用状态筛选、打开详情、编辑并读回已发布值。沿此页面实际发送的列表请求核对响应只有当前发布状态，并用本轮已观察到的旧筛选参数验证拒绝。用现有空配置和历史定义入口验证引导指向初始化或查看记录。

### Developer 第十一轮修复报告

```text
Task Base: e279077c4bca208ab7168983d15eca66ec8833d1
Candidate: cdaa5d16cbfa90d4ebd3d7f0f702ed75c1e98821
Decision: READY FOR B REVIEW
Authorized bug acceptance complete: NO
```

- 自动化列表改为只投影当前 Active 中的定义：移除 `state` 查询与「发布状态」筛选、Active 当作草稿合并、`draftState`、`draftOnly` 计数及 `createDraft`/`draftCreate` 动作。旧 `state=draft-only`、`state=active`、`state=all` 均按无效查询返回 JSON `400`。
- 自动化定义详情不再读取或回退到 open Draft，不返回草稿状态和草稿动作；被移除定义仍以只读历史返回。同步删除仅服务于草稿激活的不可达实现。
- 列表行不再显示草稿徽标或「仅存在于草稿」，计数只显示已发布/已启用。空配置列表提供「系统设置」初始化入口。
- Web 模型、查询键、Node 夹具及真实 Python 浏览器规格同步当前响应。真实浏览器列表请求已核对无 `draftState`/`draftOnly`/`state`，旧筛选参数为 `400`。

实际结果：

- `.venv/bin/python -m unittest tests.test_v2_automation_operations tests.test_v2_automation_lifecycle`：44 项通过。
- `.venv/bin/python -m unittest tests.test_configuration_snapshot tests.test_configuration_status tests.test_configuration_package_exchange tests.test_configuration_destination_activation tests.test_system_settings_management tests.test_automation_settings_management`：159 项通过。
- `npm run test -- run src/entities/operations/automation.test.ts src/features/operations/AutomationRouter.test.tsx src/features/operations/AutomationWorkspaceReadModel.test.tsx src/features/operations/AutomationListCopy.test.tsx src/features/operations/AutomationListRunOnce.test.tsx`：75 项通过。
- `npm run test -- run src/features/operations/AutomationSettingsPage.test.tsx src/features/operations/AutomationLifecyclePage.test.tsx src/features/operations/AutomationCreateDialog.test.tsx`：61 项通过。
- `npm run test:e2e -- --config=playwright.python.automation.config.ts tests/e2e/automation-workspace.python.spec.ts --grep "inventory reads full-population"`：1 项通过。
- `npm run test:e2e -- tests/e2e/automation.spec.ts`：10 项通过。
- `npm run build`、`npm run typecheck`、`npm run lint`、`npm run format:check`、Ruff check/format、`py_compile`、`git diff --check`、治理检查通过。构建产物为 `index-BFVM_GYd.js` / `index-Tw5pYUJe.css`。
- 本轮测试实际耗时约 3 分钟，低于本轮开发总时间的 30%。

剩余风险：T4 全量、真实桌面及 390px 截图验收、Base 数据切换按 Task 分工留给 B；本轮未运行全量 Python/Node 套件，未推送、未部署。

### B 第十一次返工复核

```text
Reviewed Base: e279077c4bca208ab7168983d15eca66ec8833d1
Reviewed Head: 74f6ad99ccac6dc75c87f44919253ecf26532619
Reviewed Implementation: cdaa5d16cbfa90d4ebd3d7f0f702ed75c1e98821
Decision: FIX REQUIRED
Authorized bug acceptance complete: NO
Next: SAME TASK FIX LOOP
```

- 自动化列表复验通过。管理员打开列表并按启用状态筛选，实际列表响应只含已发布定义，旧草稿筛选返回 `400`。编辑保存后重新打开可读回新值，移除定义后仍可查看历史。真实 Python 浏览器相关用例 4 项通过。
- **通知和设置相关的当前接口仍依赖旧草稿契约。** 从侧栏进入「通知」，再打开已有 Webhook 的编辑卡或新建卡，真实后端的列表、列表项和定义详情都还返回 `draftState`。通知列表解析要求该字段，新建卡仍从该字段选择修订基线。编辑读请求取得的是已发布版本，但首轮退役加入的转换层仍把它包装成状态为 `validated` 的草稿模型。进入「系统设置」后，当前状态和版本详情都还接收 `setupDraft: null`。进入「存储管理」，实际清单还返回 `setup.setupDraftExists: false`，前端把它当成必填字段。这些普通入口仍生产或依赖旧结构，未达到彻底退役且不设兼容转接的要求。
- 真实设置浏览器用例 5 项通过，包括桌面和 390px 直接应用、并发拒绝和丢回包核实。真实通知用例 3 项通过，包括签名测试后应用及丢回包重连。生产 Web 构建、治理和完整范围的 `git diff --check` 通过。证据位于 `.git/validation-evidence/74f6ad99ccac6dc75c87f44919253ecf26532619/b-review/`。本轮确认接口阻塞后结束定向验收，候选的 T4 全量门禁及 Docker 健康旅程待完成。

#### Developer 修复指导

1. 通知列表、详情、新建和编辑直接使用已发布定义、当前生效版本与发布权限。同步删除后端 `draftState`、前端的草稿解析与把已发布版本转换成草稿的适配层。通过真实「通知 → 编辑／新建 → 签名测试 → 应用 → 读回」核对正常响应和表单。沿现有丢回包测试保留对原请求的一次提交及重连核实断言。
2. 从配置状态、版本详情、管理就绪响应和存储清单删除 `setupDraft` 与 `setupDraftExists`。同步前端模型及夹具。沿「系统设置」和「存储管理 → 去完成设置」核对正常和未初始化场景，未初始化引导指向现有的空配置初始化。

### Developer 第十二轮修复报告

```text
Task Base: e279077c4bca208ab7168983d15eca66ec8833d1
Candidate: 901b81beae4141a7956e40aec5c3ee9bf63c604c
Decision: READY FOR B REVIEW
Authorized bug acceptance complete: NO
```

- 通知列表、列表项、定义详情、新建和编辑现在直接消费当前已发布 Webhook 定义：后端移除 `draftState` 与 `definitionState`，列表只投影 Active 中的定义；详情增加 `supportedEvents` 供表单使用。前端删除草稿状态解析、新建卡从草稿选择基线的逻辑，以及把已发布版本包装成 `validated` 草稿的读取适配层。编辑直接使用 `webhook.activeConfiguration` 与 `webhook.document`，应用、签名测试、原请求核实和读回逻辑保持原样。
- 从配置状态、版本详情、管理就绪响应、系统状态快照和存储清单移除 `setupDraft`、`setupDraftExists`；同步前端模型、测试夹具和通知/存储浏览器假服务。未初始化时 Storage 仍指向现有 `/configuration`，由设置页执行空配置初始化。
- 清理通知列表、详情和编辑表单中的退役草稿徽标、草稿原因映射及旧断言；Node 通知夹具改为只返回已发布定义。

实际结果：

- `.venv/bin/python -m unittest tests.test_v2_notification_operations tests.test_management_setup tests.test_v2_storage_operations`：66 项通过。
- `.venv/bin/python -m unittest tests.test_configuration_snapshot tests.test_configuration_status tests.test_configuration_package_exchange tests.test_configuration_destination_activation tests.test_system_settings_management tests.test_automation_settings_management`：159 项通过。
- 通知定向 Python 用例最终 29 项通过，含详情不再返回 `draftState` / `definitionState`、列表与创建后定义只含发布状态。
- `npm run test -- run src/entities/operations/notification.test.ts src/features/operations/NotificationRouter.test.tsx src/features/operations/notification-presentation.test.ts src/entities/storage/storage-management.test.ts src/features/storage/StorageManagementPage.test.tsx`：144 项通过。
- `npm run test:e2e -- tests/e2e/notifications.spec.ts`：9 项通过；`tests/e2e/storage-management.spec.ts --grep setup`：5 项通过；`tests/e2e/rules-readiness.spec.ts --grep "no-Active family"`：1 项通过。
- 真实 Python 浏览器：`playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts --grep Notification` 3 项通过；`playwright.python.automation.config.ts tests/e2e/configuration-settings.python.spec.ts` 5 项通过。
- `npm run typecheck`、`npm run lint`、`npm run format:check`、`npm run build` 通过；构建产物为 `index-DU0t5_Q6.js` / `index-Tw5pYUJe.css`。
- Ruff check/format、`py_compile`、`git diff --check`、治理检查通过。

剩余风险：T4 全量门禁、通知真实桌面及 390px 截图验收、Base 数据切换与 Docker 套件按 Task 分工留给 B；未推送、未部署。

### B 第十二次返工复核

```text
Reviewed Base: e279077c4bca208ab7168983d15eca66ec8833d1
Reviewed Head: fa8f9dd8c3be69bf6460cd38335f03709fac71c1
Reviewed Implementation: 901b81beae4141a7956e40aec5c3ee9bf63c604c
Decision: FIX REQUIRED
Authorized bug acceptance complete: NO
Next: SAME TASK FIX LOOP
```

- 上轮接口问题已解决。用生产 Web 构建在真实 Python 上打开通知列表、新建与编辑卡，并核对实际通知、设置和存储响应，已移除上轮发现的草稿字段。真实通知浏览器 3 项通过，真实设置及自动化运行设置浏览器 20 项通过。
- Python 全量执行 2327 项，其中 7 项跳过，其余通过。Web 单测 104 个文件、1594 项通过，Node 浏览器 276 项通过。生产构建、类型检查、Lint、Prettier、Ruff、编译、依赖和示例配置检查通过。候选 wheel 安装冒烟通过。Docker 空配置与媒体挂载、重启与故障、发布安全验收均通过。
- 使用真实 Base 库的新副本再次执行数据切换。状态读取和未确认切换保持文件校验和一致。确认切换移除两份未发布修订，两份已发布修订、六条相关审计、一个固定任务及其结果逐项一致。异常引用和切换失败回滚由本轮 Python 全量覆盖。
- **Docker 健康验收仍按旧部署模型判断媒体权限。** 已有健康脚本通过启动、直接发布、Worker 停启和 API 密钥恢复，随后等待 API 因媒体目录权限变化变成 `unhealthy`，超时退出。候选镜像中 UID 10001 读到目录权限为 `000`，确认无法读取。该路径只在已发布配置中声明，容器健康探针读取的是管理 bootstrap，原 Compose 探针退出码为 0。B 另外从真实容器的「存储管理 → 查看来源存储 → 运行只读检查」复验，权限正常时通过，移除权限后报失败，此时 `/health` 返回 `200`，恢复权限后再次通过。三次操作都沿用同一个已生效版本，任务清单保持为空。
- **部分首次部署指引仍指向退役操作。** 可选媒体挂载 Compose 文件的开头要求进入设置创建草稿，当前《产品体验》的首次启动摘要还要求创建或恢复 Draft。新实例进入系统设置实际可直接初始化空配置。生成部署配置的 `--help` 也仍将导入、验证和激活写成分步操作。
- 本轮日志位于 `.git/validation-evidence/fa8f9dd8c3be69bf6460cd38335f03709fac71c1/b-review/`。

#### Developer 修复指导

1. 修正仓库已有 Docker 健康验收的媒体权限步骤。沿当前管道直接发布带媒体挂载的配置，保留 Worker 停启和 API 密钥缺失与恢复的原断言。权限变更后用现有存储只读检查确认媒体访问失败，恢复后确认读取通过，同时核对 API 存活、已生效版本和任务清单。同步部署指南对这两个信号的描述。
2. 把上述首次部署指引和配置生成命令帮助改为实际操作。新实例可从系统设置初始化空配置，已有完整输入可直接核对并应用。用现有 Docker 首次配置旅程和 `make_deployment_config.py --help` 核对说明。

### Developer 第十三轮修复报告

```text
Task Base: e279077c4bca208ab7168983d15eca66ec8833d1
Candidate: 2837d9bc6c0dcc1360b02ccf659922a121bba667
Decision: READY FOR B REVIEW
Authorized bug acceptance complete: NO
```

- Docker 健康验收不再把已发布配置的媒体根目录当作容器健康信号。启动并直接发布带媒体挂载的配置后，先对 `source-storage` 执行一次现行 Storage 只读检查并确认 `status=passed`；保留 Worker 停启及 API 密钥缺失／恢复的原断言。将宿主来源目录权限改为 `000` 后，同一检查按精确 Active 返回 `status=failed`、`failureCategory=permission_denied`，`sideEffects=none`、`retrySafe=true`；此时 `/health` 仍为 `200` 且 `processAlive=true`，`/api/configuration` 的 revision/digest 未变，任务清单为空。恢复权限后同一检查再次 `passed`，最终任务清单仍为空。检查请求使用现行 `POST /api/operations/storage-management/storage/{id}/check`，与存储页「运行只读检查」共用同一应用行为。
- 部署指南把「基础设施健康」与「已发布媒体访问」分开描述：管理 bootstrap 不含已发布 Storage，媒体根目录缺失或不可读由检查后的发布、Storage 只读检查及存储页报告，API 与 `/health` 保持存活；失败恢复条目分别覆盖 `/data` 与已发布媒体根目录，健康 harness 说明同步新信号。
- 首次部署指引改为实际操作：可选媒体挂载 Compose 文件说明从系统设置初始化空配置，产品体验的 Slice55 旅程摘要不再要求创建或恢复 Draft，`make_deployment_config.py` 的帮助与模块说明改为直接检查并发布生成输入。

实际结果：

- `.venv/bin/python -m unittest tests.test_container_deployment`：15 项通过。
- `TMPDIR=<repo>/.git/smoke-tmp .venv/bin/python scripts/docker_health_smoke_test.py`：通过，输出含直接发布、媒体只读检查、Worker 停启、API 密钥降级／恢复、媒体权限降级／恢复及 `Docker health/readiness smoke acceptance passed.`。
- `MEDIAFLOW_SMOKE_TEMP_DIR=<repo>/.git/smoke-tmp .venv/bin/python scripts/docker_empty_baseline_smoke_test.py`：两套真实栈均通过，默认无媒体挂载栈经真实设置页初始化空 Active，可选媒体挂载栈完成 ResourceLibrary、整理及两种库复制；耗时 72 秒。
- `.venv/bin/python scripts/make_deployment_config.py --help`：`--configuration` 与 `--configuration-output` 均说明检查并直接发布当前 Configuration lifecycle。
- `.venv/bin/ruff format --check`、`.venv/bin/ruff check`（两个改动脚本）、`py_compile`、`git diff --check`、`python3 scripts/check_governance.py` 通过。
- 本轮测试实际耗时约 3 分钟，低于本轮开发总时间的 30%。

剩余风险：T4 全量、真实桌面及 390px 截图验收、Base 数据切换按 Task 分工留给 B；本轮 Docker 运行使用本机隔离临时目录和本地引擎，未推送、未部署。
