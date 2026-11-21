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
