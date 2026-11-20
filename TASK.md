# Task PATCH-20261120-4 — 系统设置自动同步与草稿管理

用户于 2026-11-20 授权激活独立 Task，待 Developer 开始实施。按[开发流程 §3.1](docs/development-workflow.md#31-independent-minor-bugs)登记。
[上一独立修复的 B 验收](https://github.com/kentinya/mediaflow/blob/455ad4f70c645b1a2e65f4af61378101a25435d8/TASK.md#patch-20261120-3--b-验收-pass)

```text
Task ID: PATCH-20261120-4
Task Type: STANDALONE MINOR BUG
Parent Slice: NONE
Status: PLANNED
Task Base: 91f97d22d2b15748fc9f843871287ffa937b44be
Difficulty: High
Test Level: T4
Planner / Reviewer: B
Implementation Authorization: USER AUTHORIZED ON 2026-11-20
```

### 目标与调查基线

从 `/configuration` 进入时直接看到当前生效值。修改设置时在同一组核对原值、改动和生效条件。系统负责读回和同步。需要暂存时可保存并继续编辑草稿，每实例最多两份可恢复草稿。操作完成后就地看到保存、发布或实际采用状态，以及遇到问题时的下一步。

- `ConfigurationPage` 有页头「刷新」和配置内容「重新读取」。状态查询继承了关闭聚焦和重连重取的默认设置，修订详情另外加载。`AutomationSettingsPanel` 已每五秒读取发布目标和采用状态，仍有自己的「刷新」。只删除按钮会留下配置状态和详情的同步缺口。
- 高级配置通过同一个「查看配置」下拉切换 Active 和 Draft。JSON 常驻桌面右栏。保存、验证、检查和激活分布在表单上下，验证完成即可发起激活请求，发布前检查不足由后端拒绝。
- `open_draft_revisions()` 的 `limit` 是列表读取限制。首次设置、后继草稿、JSON/配置包导入及业务页发布共用配置仓储，现有存储层没有每实例两份可恢复草稿的创建约束。现有「放弃本组修改」只清除本组表单输入。

依据 [REQ-CONFIG-004–012](docs/requirements.md#configuration-requirements)、[V2-CONFIG-001–004](docs/v2-requirements.md)、[配置与首次设置旅程](docs/product-experience.md#configuration-lifecycle)和[系统设置现行契约](docs/configuration.md#system-settings-web)。

### 实施范围与顺序

1. **设置页自动同步。** 设置页进入、切回、重连以及本页写入完成时读回权威状态。前台按有界频率捕捉外部发布和草稿变化，复用运行设置的定期读取来呈现采用进度，合并重复读取。先更新当前状态。表单干净时跟随最新值，编辑中保留输入和原基线，明确说明被其他会话改动的字段及处理方式。「配置内容」按打开和来源变化读取。失败时标记上次值并自动恢复读取，正常状态只展示简洁的配置与待处理状态。移除三个手动刷新入口及重复的读取时间卡片。
2. **表单内完成修改与发布。** 编辑分组占主栏，JSON 和脱敏导出移到按需打开的「配置内容」，技术身份归入「诊断」。当前值、未保存输入和已保存待应用的值在同一分组里用文字区分。保留本组保存和放弃本组输入的边界。草稿存在时通过「继续上次修改」进入，选择两份时能根据修改分组、时间和验证状态辨别。发布区与表单相邻，复用精确草稿验证和适用的只读检查，直接指出缺项和所需输入。确定性的结构验证由流程发起，证据齐备后由用户明确点击「应用更改」发布该版本。改动后旧检查证据失效。三项运行参数沿用专用保存和采用反馈，重启后生效的字段单独标注。
3. **统一草稿上限与释放。** 每实例最多两份供用户继续编辑的持久草稿，`Draft` 和 `Validated` 都计入。由共享后端在 SQLite 写事务内计数并创建，覆盖首次设置、设置页后继、显式业务草稿以及 API/CLI 的 JSON 或脱敏包导入。若业务页的单次保存使用临时候选，保留其原有发布语义。可独立恢复的候选须接受同一限额，失败的内部候选按原请求证据处理。名额满时返回明确上限及可继续编辑的草稿，保留尝试新建时的输入。应用成功后释放名额。允许管理员明确「放弃草稿」，按草稿身份和编辑版本核对，关闭其编辑和发布资格并保留审计。既有超额草稿全部保留，降到两份以下才开放新建。
4. **闭合异常和恢复。** 竞态由后端按 Active 基线、草稿版本和检查证据裁决。另一份草稿发布后，基线过时的草稿仍可查看和恢复，标出冲突，保留修改，由用户核对当前值后重新编辑。首次设置仍可明确创建或恢复并应用空配置。Active 损坏走已有恢复路径。写响应丢失时，系统自动只读核对该次操作的结果，无法证明时保持待核实并阻止重复写入。通过现有 RBAC、脱敏和审计边界呈现拒绝、已发布、待采用与需重启等结果。

「放弃草稿」限定为管理员针对单份未发布草稿执行的归档操作。归档标记、版本核对和审计在同一事务内写入，保留草稿原内容和摘要。共享后端据归档标记统一收回该草稿的编辑、验证及发布资格，并释放名额。现有修订状态和发布检查仍按受管配置契约执行。其他业务页面、API 和 CLI 的变更范围为共享草稿上限及其错误恢复。

### 验收标准

- [ ] 真机桌面和 390px 窄屏均能通过表单浏览和编辑设置。页内无三个原刷新入口，JSON 默认收起。反复切回页面、断线重连和其他会话发布后，页面自动显示最新权威值或清楚标出暂时无法同步。正在编辑的输入、焦点、所选分组和草稿保持稳定，同字段冲突有明确操作。
- [ ] 改一个高级字段，可区分当前值、待应用值及是否需重启。保存仅提交本组变化，重开可继续对应草稿。检查缺项就地可见，检查未通过时 Web 发送的激活请求为零。检查齐备后一次明确应用只发布确认的版本。失败保留旧 Active 和可修正输入，另一个同基线草稿依然可打开，应用过期版本由后端拒绝。
- [ ] 从一份草稿出发，用两个独立 SQLite 连接并发创建，最终两份可恢复草稿，只有一个新增成功。已验证草稿计入。达到上限仍能编辑和验证已有草稿。管理员应用或放弃指定草稿后能新建一份。Viewer 无写权限，过期版本和重复请求无法关闭别人的新版本。超额旧库重开时完整保留草稿，恢复路径可见。
- [ ] 首次创建、后继、显式业务草稿、原始 JSON 与脱敏包导入、CLI 和 API 无共同限额的旁路。拒绝创建时 Active、现有草稿和源数据不变。两份用户草稿存在时，专用运行参数保存和代表性业务页直发仍能成功，且失败不能留下第三份可恢复草稿。
- [ ] 断开并重连后自动核实丢失的保存、应用及放弃响应。分别验证已提交与未提交，读取和异常恢复均无重复写请求。首个空配置、损坏 Active、只读账号、脱敏导出和来源页返回继续通过。配置读、检查和发布的媒体写入、新任务与通知发送计数均为零。

### 验证计划

**Developer 运行受影响检查。** 在仓库根目录运行 `.venv/bin/python -m unittest tests.test_system_settings_management tests.test_configuration_successor_draft tests.test_configuration_status tests.test_configuration_package_exchange tests.test_configuration_destination_activation tests.test_automation_settings_management`。同组覆盖限额事务、越权、老库、配置包和检查证据。用 `.venv/bin/ruff check <改动的 Python 路径>` 检查受影响文件。在 `web/` 运行 `npm run typecheck`、`npm run test -- run src/features/configuration src/features/operations/AutomationSettingsPage.test.tsx` 和 `npm run test:e2e -- tests/e2e/configuration-settings.spec.ts`。用 `git diff --check` 检查提交边界。

**B 验收候选版本。** 按 T4 运行[适用全量门禁](docs/development-workflow.md#shared-full-regression-commands)。构建 Web 后，使用真实 Python、临时 SQLite 和两个浏览器会话验证两份上限、断线核实、废弃与并发发布。新增 `web/tests/e2e/configuration-settings.python.spec.ts` 作为真实链路验收入口。用 `cd web && npm run build && npm run test:e2e -- --config=playwright.python.automation.config.ts tests/e2e/configuration-settings.python.spec.ts --output=test-results/configuration-settings-python` 单独运行。检查实际桌面和窄屏截图、配额与审计记录、已准入任务的快照绑定及 Worker/Scheduler 采用反馈。若涉及持久化结构变更，核对旧库迁移与重开时的保留结果。Developer 交付受影响检查记录后，由 B 独立评审任务范围和接受证据。
