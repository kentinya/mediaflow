# MediaFlow 总体实施计划

## Phase Gate

流程与关闭规则仅以 [development-workflow.md](development-workflow.md) 为准；本文件只记录
Phase gate，不复制测试日志或流程正文。

| Gate | Status | Commit SHA | High Audit / Next boundary |
|---|---|---|---|
| Phase 22.4 Recognition integration Slice | PASS / CLOSED | `d95ea2b64a6fce559341d7eb5824977e07794dff` | PASS；已推送 `origin/main`；允许 Phase 22.5 reconstruction |
| Phase 22.5 recovered integration checkpoint | PASS / CLOSED | `d68a19ddd4bb62bc27e77bab013edb20c9eb53e5` | PASS — SAFE TO INTEGRATE；已推送 `origin/main`；不扩大下文产品边界 |
| Development Workflow Git Capability Gate | PASS / CLOSED | `9777ee187972d53f02f6f30d7682535b03f2b447` | PASS；已推送 `origin/main`；不重新打开 |
| Phase 22.5-C Candidate Confirmation | PASS / CLOSED | `d68a19ddd4bb62bc27e77bab013edb20c9eb53e5` | PASS；允许 Phase 22.5-D same-Provider correction test |
| Phase 22.5-D Managed Live Metadata Correction Test | PASS / CLOSED | `55769be58a75596461879994560a0c58c3a7c9dc` | PASS；允许 Phase 22.5-E 单项 Metadata correction DryRun continuation；Provider switching 仍后置 |
| Phase 22.5-E Single-Item Metadata Correction DryRun Continuation | PASS / CLOSED | `dce5c0ba53bb4fc91f18d1b5d6d56564cd3cfe62` | PASS — 2026-08-27，F1 correction checkpoint 独立复审通过；被拒 checkpoint `08dfd4f921728755209b6d52347d28f221121c47`（FIX REQUIRED）保留 |
| Phase 22.5 Metadata 配置与修正旅程（A/B/C/D/E） | PASS / CLOSED | `dce5c0ba53bb4fc91f18d1b5d6d56564cd3cfe62` | PASS — 2026-08-27 phase-level Final Closure Audit；已推送 `origin/main`；允许 Phase 22.6 Naming/Classification/Organize 配置旅程 |
| Phase 22.6-A Managed NamingPolicy + Offline Naming Preview | PASS / CLOSED | `30af69ac82b30f8a45ad66afbd3c9747597c8fe7`；被拒 checkpoint `90ce13a6c6c39912dd389f71a1189314ff24eb5d` 保留 | PASS — 2026-08-28 独立复审：五项 operator-UI 与两项 service-boundary 可证伪对照全部先失败后通过，生产树与被拒 checkpoint 逐字节相同；已于 2026-08-28 在显式操作员授权下推送 `origin/main`；下一合法 Slice 为 Phase 22.6-B |
| Phase 22.6-B Managed ClassificationPolicy + Offline Classification Preview | PASS / CLOSED | `5e2da5c634f1fa72a40e5f50b035260418fe1a37` | PASS — 2026-08-28 独立审核：五项 operator-UI 与三项 service-boundary 可证伪对照全部先失败后通过，marker 6→7 前向升级与 Runtime marker 22 均已复核，归一化对 runtime 语义为恒等；已于 2026-08-28 在显式操作员授权下推送 `origin/main`；下一合法 Slice 为 Phase 22.6-C |
| Phase 22.6-C Managed OrganizePolicy + Offline Organize Authority Explanation | PASS / CLOSED | `47096eeaf1769b79cf3d0c67bcdf0c75b6c344aa` | PASS — 2026-08-28 独立审核：五项 operator-UI 挂载、两项被收窄断言与四项 service-boundary 可证伪对照全部先失败后恢复通过；另独立复核 22 组非默认字段归一化零语义漂移、零副作用与 C 身份保持、marker 7→8 前向升级与 Runtime marker 22；已于 2026-08-28 在显式操作员授权下推送 `origin/main`；下一合法 Slice 为 Phase 22.6-D |
| Phase 22.6-D Managed Exact-Revision Offline Composed Destination Preview | PASS / CLOSED | `c7ec192b3b20f236cca5a70ed59cad43e0851242` | PASS — 2026-08-28 独立审核：四项 operator-UI 挂载、共享 composition 安全守卫、unsafe 判定短路与 RecognitionType C 身份共七项可证伪对照全部先失败后恢复通过；另独立复核与真实 `OrganizePlanner.plan` 的 8 组 composition parity、零 Storage/Provider/Planner/Executor 构造、marker 8→9 前向升级与 Runtime marker 22；已于 2026-08-28 在显式操作员授权下推送 `origin/main`；下一合法 Slice 为 Phase 22.6-E |
| Phase 22.6-E Managed Exact-Revision Read-Only Destination Precheck (Local) | PASS / CLOSED | `ee5225dd0e74a7382b6747c6315776413f7fd249`（经 Phase 22.6-E-F1 修正接受；被拒 checkpoint `7353b0d22497e6e3e596c93c7052eea34daf27df` 保留，不得 amend/squash/改写） | PASS — 2026-08-28 独立审核：六项可证伪对照（同步路径与 worker 内注入 Provider 构造、互换 `relativeDestination`/`destinationPath`、截断 `directoriesToCreate`、删除 Web destination-path 字段行、移除防御性 `INVALID_DESTINATION` 拒绝）全部先失败后恢复通过；另复核零 Provider/Executor/Task/queue/Job/authority 与十张 Runtime 表为空、fully-missing subtree 完整创建列表且 partial 证明未被削弱、不可达 `invalid` 投影已在生产消解、被拒 SHA 与其 FIX REQUIRED 记录保留且 `docs/progress.md` 仅追加、marker 10 与 Runtime marker 22 不变、842 项离线回归与 wheel smoke；已于 2026-08-28 在显式操作员授权下推送 `origin/main`；下一合法 Slice 为 Phase 22.6-F |
| Phase 22.6-F Checked Activation Requires Current Local Destination Precheck Evidence | PASS / CLOSED | `e68e901a73107484dc0521b47b1b0001eed2b853` | PASS — 2026-08-28 独立审核：四项可证伪对照（删除 `activate_checked` 中的 `require_current_destination_precheck` 调用致 3 项失败、删除 Web not-applicable 行致 operator-UI 失败、强制 `applicable` 为真致 2 项报错、停用 `capability_gap` 分支致 1 项失败）全部先失败后恢复通过；另复核门禁顺序（Local check → Strategy Test → destination precheck）、缺失/过期/失败/`capability_gap` 四类有界拒绝与显式 next action、document-level 仅 Local 适用规则与可见的 not-applicable、completed 投影空间完备（`ready`/`skip`/`rename`/`overwrite_requires_confirmation`/`manual_confirmation_required` 之外的不安全目标一律 FAILED，不存在 completed-but-unsafe 漏网）、门禁路径零探测零构造且十张 Runtime 表在拒绝与成功两条路径均为空、Web/API 同权限 `ACTIVATE_CONFIGURATION` 与同一 409 `configuration_conflict`、无新增 evidence key 与请求/响应字段、marker 10 与 Runtime marker 22 不变、22.6-D 与 22.6-E 套件逐字节未改、846 项离线回归与 wheel smoke；已于 2026-08-28 在显式操作员授权下推送 `origin/main`；下一合法 Slice 为 Phase 22.6-G |
| Phase 22.6-G Web Checked-Activation Controls Cover All Three Requirements | PASS / CLOSED | `5ca1247156e6de4615dff53f5fc8e421bd8bf264`（经 Phase 22.6-G-F1 修正接受；被拒 checkpoint `b9cc35e2677a35920042b5695f87b50a80025ef0` 保留，不得 amend/squash/改写） | PASS — 2026-08-28 独立审核：十一项可证伪探针全部被捕获，且每次只有 `test_destination_precheck_blocking_sentence_contract_is_body_scoped` 失败（分别删除 `:705`/`:708`/`:716` 三处 blocked 文案之一、把 `:712` failed 模板截断为父提交曾断言的前缀、从 `:719` 返回对象删掉 `message`、把 `:727` 渲染载荷换成固定字面量、删除 `:713` 与 `:717` 的 `style = 'error';`、从返回对象删掉 `style`、去掉三条简单句的句末句号、互换 missing 与 stale 两条 `nextAction`），其中后五项超出修正 TASK 要求，证明两种 error 样式、句末标点与分支归属亦已受约束；另复核生产文件与被拒 checkpoint 逐字节一致（`git diff --exit-code b9cc35e 5ca1247 -- mediaflow scripts config pyproject.toml` 为空）、`tests/` 零删除、无文档改动、Completion Report 已补齐、三份冻结套件逐字节未改、marker 10 与 Runtime marker 22 不变、850 项离线回归（849 → 850 纯增量）、operator-UI 模块 21 项、ruff/format/compileall/`pip check`/两份示例配置校验/Markdown 链接检查/机密扫描与 wheel 隔离 smoke 全绿；已于 2026-08-28 在显式操作员授权下推送 `origin/main`；下一合法 Slice 为 Phase 22.6-H |
| Phase 22.6-H Bounded Multi-Sample Local Destination Precheck + Cross-Item Collision Detection | PASS / CLOSED | `4455198a6ef3b93fe1e92cef73660039620e756e`（经 Phase 22.6-H-F1 证据修正接受；被拒 checkpoint `d8c2ae04e578955ddbbd29c413f235bf4cf08f42` 保留，不得 amend/squash/改写） | FIX REQUIRED — 2026-08-28 于 `d8c2ae0`：TASK 要求的七项可证伪探针全部被捕获且每次只有其命名测试失败，另加十三项独立探针；多样本 composition、逐样本独立状态与恢复、经生产 `OrganizePlanner` + `claimed_destinations` 真实产生的 `TARGET_COLLISION`、`duplicate_destination` 与 `multiple_destination_storages` 两类有界失败、逐字节未变的 activation gate、单样本与既存 evidence 兼容、零变更零授权、有界无机密证据、marker 10 与 Runtime marker 22 不变、`tests/` 零删除（850 → 859）、三份文档 CURRENT 声明均已复核接受；唯一被拒原因是 most-severe verdict 聚合不可证伪（换成 `outcomes[0]` 后 859 项套件仍全绿）。PASS — 2026-08-28 于 `4455198`：修正仅改 `tests/test_configuration_destination_precheck.py`（+138/-0）与 `TASK.md`，`git diff --exit-code d8c2ae0 HEAD -- mediaflow scripts config pyproject.toml` 为空即生产树逐字节未改，两项新测试把最严重样本置于 index 1；独立复跑五项 TASK 探针（`outcomes[0]`、`outcomes[-1]`、`min(...)` 各使 Required Test 1 失败，末样本 details 使 Required Test 2 单独失败，comment-only control 不触发）与五项自选探针（删除聚合 `verdict` 覆盖、颠倒 severity 表均使两项新测试失败；逆序行使模块内四项失败；末样本 identity 因运行内策略同一而无差异；常量 verdict 未被捕获，记为非阻塞观察）；861 项离线回归 `OK (skipped=7)`、47 项聚焦、ruff/format/compileall/`pip check`/两份示例配置/Markdown 链接/机密扫描/FFmpeg 与业务层写操作审计全绿、wheel 隔离 smoke 报告 Runtime schema 22；未推送；下一合法 Slice 为 Phase 22.6-I |
| Phase 22.6-I Web Run-Level Destination Precheck Summary Separated From the First Sample | PASS / CLOSED | `6c0ba745772e315b941c1c3b314ab47e66e8f35a` | PASS — 2026-08-29 独立审核：checkpoint 仅改三个文件（`mediaflow/interfaces/operator_ui.py` +62/-29、`tests/test_operator_ui.py` +50/-1、`TASK.md`），且生产改动全部落在 `renderDestinationPrecheck` 之内，`git diff 4455198 6c0ba74 -- mediaflow/application mediaflow/domain mediaflow/infrastructure mediaflow/interfaces/service_api.py mediaflow/cli.py scripts config pyproject.toml` 为空；多样本分支先渲染 18 项 run 级字段（含 `Run verdict (most severe sample)`）并 `append(runList)`，再输出「First sample destination」标题与 8 项真正逐样本字段（共 26 项，与单样本列表同一集合、各自保持原相对顺序，仅 verdict 标签不同）；单样本 `else` 分支 26 组标签与表达式逐字节未改（标签仍为 `Verdict`），分支之后的逐样本行表、碰撞表与九条有界文案（含 `!result.destinationRootExists` 未改的 not-ready 门禁）逐字节未改且各出现一次，evidence key 读取方式不变，故既存 22.6-H 证据仍可渲染；`tests/` 22 → 24（零删除零改名，仅一处 TASK 明确许可的断言替换），两项新测试均经 `_js_function_body` + 计括号的 `_js_braced_body` 限定在分支体内；TASK 要求的六项探针全部被捕获（run 列表移回标题之后、`Destination path` 移入 run 列表、`if (true)` 去掉 `sampleCount > 1` 守卫、多样本分支改用普通 `Verdict` 标签、删除无碰撞文案，comment-only control 不触发），另六项自选探针确认边界（单样本分支误用 run 标签被捕获；删除 run 级 `Message`、改标题文案、单样本字段换序、改写 not-ready 文案不被捕获——字段划分本轮由源码分析核验，与 TASK 要求一致，已记为非阻塞观察）；离线回归 863 项 `OK (skipped=7)`、聚焦三模块 49 项、ruff/format/compileall/`pip check`/示例配置校验/Markdown 链接（120 文件 25 链接 0 断链）/机密扫描/FFmpeg 与业务层写操作审计全绿、wheel 隔离 smoke 报告 Runtime schema 22 且 configuration marker 10 不变；零文档改动本轮正确（无 CURRENT 声明描述字段分组）；未推送；下一合法 Slice 为 Phase 22.6-J |
| Phase 22.6-J An Undetermined Destination Observation Stops Printing as "NO" | PASS / CLOSED | `ccbddf2af92c1abf18d1162d0a6c37da9ee0a7cd` | PASS — 2026-08-29 独立审核：checkpoint 仅改三个文件（`mediaflow/interfaces/operator_ui.py` +9/-4、`tests/test_operator_ui.py` +61/-0、`TASK.md`），`git diff --exit-code 6c0ba74 HEAD -- mediaflow/application mediaflow/domain mediaflow/infrastructure mediaflow/interfaces/service_api.py mediaflow/cli.py scripts config pyproject.toml` 为空，故 evidence key、聚合规则、失败类别、route、权限、表与两个 marker 均未动；生产改动为四行渲染加五行新 helper，除 helper 自身外全部落在 `renderDestinationPrecheck` 之内。`determinationText` 只定义一次且紧随未改的 `boundedSetupText`，`true`/`false`/其他分别映射为 `YES`/`NO`/`NOT DETERMINED`，六处调用正是 TASK 指定的四个渲染点（多样本 run 级 root 组合、多样本首样本 `Target exists`、单样本两处），且全文件对这三个 key 再无 `=== true ? 'YES' : 'NO'`；因 `:739` 把缺失载荷归一化为 `{}`，此前无 `result` 的 FAILED 运行会把从未判定的项印成 `NO`，现在读作 `NOT DETERMINED`。完成态与两类 root 失败类别逐字未变，已在 application 侧独立复核（`:1742`/`:2046` 身份为 `(True, True)`，`:1747`/`:2207` 的 `targetExists` 为真布尔，`:1639` `(False, False)`、`:1651` `(True, False)`；`:2236`/`:2252` 的 `None` 仅存在于逐样本行，而行表只渲染 index/destinationPath/projectedOutcome/failureCategory）。not-ready 门禁（含 `!result.destinationRootExists`）、其文案与 `'error'` 样式逐字节未改，未判定的 root 仍算 not ready，呈现层未软化门禁；十处 `evidence.retrySafe` 与块外全部 `YES`/`NO` 未改。`tests/` 24 → 27 为纯增量（零替换零删除零改名），三项新测试均经 `_js_function_body` 与计括号的 `_js_braced_body` 限定在函数体内，且把每个 key 的调用计数钉为 2。TASK 要求的六项探针全部只让其命名测试失败（折叠未判定分支、折叠 `false` 分支、首样本恢复旧内联 `targetExists`、单样本恢复旧内联 root、门禁改 `=== false`），comment-only control 27 项全绿；另七项自选探针（改文案为 `UNKNOWN`、helper 移到 `boundedSetupText` 之前、多样本恢复旧内联 root、单样本恢复旧内联 `targetExists`、改写 not-ready 文案（同时触发既有 blocking-sentence 契约测试）、单样本右半误用 `destinationRootExists`）均被捕获，唯一未被捕获的是把块内 `Retry safe` 改走 `determinationText`，记为非阻塞观察。离线回归 866 项 `OK (skipped=7)`（863 + 3）、聚焦三模块 52 项、ruff/format（308 文件）/compileall/`pip check`/`git diff --check`/两份示例配置校验/Markdown 链接（120 文件 25 链接 0 断链）/机密扫描/FFmpeg 与业务层写操作审计全绿、wheel 隔离 smoke 退出 0 且 schema 22 与 marker 10 不变；零文档改动本轮正确；未推送；下一合法 Slice 为 Phase 22.6-K |
| Phase 22.6-K Per-Sample Destination Rows Carry Each Sample's Own Bounded Message | PASS / CLOSED | `f2db70b28edb8f753ebed0d3805be7143b521264` | PASS — 2026-08-29 独立审核：checkpoint 仅改四个文件（`mediaflow/interfaces/operator_ui.py` +3/-2 单一 hunk、`tests/test_operator_ui.py` +24/-1、`tests/test_configuration_destination_precheck.py` +53/-0、`TASK.md` +94/-14），`git diff --exit-code 37202cf f2db70b -- mediaflow/application mediaflow/domain mediaflow/infrastructure mediaflow/interfaces/service_api.py mediaflow/cli.py scripts config pyproject.toml docs` 为空（中间的 `37202cf` 是我自己的 22.6-J 审核记录，只动 `docs/progress.md`、`docs/roadmap.md` 与 `TASK.md`），故 evidence key、聚合、失败类别、激活门禁、route、权限与两个 marker 均未动。逐样本行表改为五列并以未改的 `boundedSetupText(item.message)` 渲染每行自己的 `message`：该字段自 22.6-H 起就已持久化（`configuration_objects.py:2241`，`_bounded_utf8(message, 384)`），而 run 级 `Message`/`Next action` 只取最小下标失败样本（`:2015-2023`，`failures[0]`），因此在本 Slice 之前第二个失败样本自己的解释存在于证据与 API 响应却无处可见。已只读复现：三样本运行中 run 级为 `Destination composition failed (invalid_input)`，而 row 1 携带自己的 46 字节 `ClassificationPolicy 'A' failed (invalid_rule)`；row 2 的 `message: None` 经未改的 `boundedSetupText` 印为 `-`，故成功行不新增文本、22.6-K 之前的证据仍可渲染；路径仍为 Storage-relative，无凭证、端点、主机路径或原始异常文本。not-ready 门禁（含 `!result.destinationRootExists`）、其文案与 `'error'` 样式、run 级字段清单、22.6-J `determinationText` 定义与六处调用、碰撞表与 `1-8 samples` 控件逐字节未改。`tests/test_operator_ui.py` 27 → 28 且仅有 TASK 点名的一处表头断言替换（零删除零弱化），`tests/test_configuration_destination_precheck.py` 18 → 19 纯增量；新 UI 测试经 `_js_function_body` 后再把行表达式切在表头与 `])));` 之间，钉住 message 单元格存在、只出现一次、位于失败类别之后且行表达式内无 `evidence.message`；新证据测试用离线 SQLite 仓库驱动三样本，证明两个失败行各自保留互不相同的有界 message、run 级取 row 0、row 1 的 message 既不等于 run 级 message 也不等于 run 级 next action。TASK 要求的七项探针全部只让其命名测试失败（表头删列、删第五单元格、改读 `evidence.message`、`'Message'` 移到首位、行内 `"message": None`、`failures[0]` 改 `failures[-1]`），comment-only control 28 项全绿；另六项自选探针（互换类别与 message 单元格、重复渲染 message、表头改小写 `'message'`、`'Message'` 移到第三位、所有失败行写同一常量 message、run 级 next action 改取末样本 message）全部被捕获，无一静默通过。离线回归 868 项 `OK (skipped=7)`（866 + 2）、聚焦三模块 54 项、ruff/format（308 文件）/compileall/`pip check`/`git diff --check`/两份示例配置校验/Markdown 链接（120 文件 25 链接 0 断链）/机密扫描/FFmpeg 与业务层写操作审计全绿、wheel 隔离 smoke 退出 0 且 schema 22 与 marker 10 不变；零文档改动本轮接受但已记录限定：`docs/product-experience.md:301-302` 与 `docs/architecture.md` 的 CURRENT 逐样本行描述现在是不完整而非错误，其刷新并入 22.6-L 且仍是 Final Closure 条件；未推送；下一合法 Slice 为 Phase 22.6-L |
| Phase 22.6-L Each Failing Destination Precheck Sample Carries Its Own Recovery Action | PASS / CLOSED | `b198c9662595c3e9c92d70602170561867763c10`（经 Phase 22.6-L-F1 证据修正接受；被拒 checkpoint `74919a33ac5ec9cde5b104a591ef3fdfb25a1bf3` 保留，不得 amend/squash/改写） | FIX REQUIRED — 2026-08-29 于 `74919a3`：scope 与全部机械证明均独立复核通过——checkpoint 只改 TASK 允许的七个文件（`mediaflow/application/configuration_objects.py` +2/-0、`mediaflow/interfaces/operator_ui.py` 单一 hunk、`tests/test_operator_ui.py` +28/-2、`tests/test_configuration_destination_precheck.py` +133/-0、`docs/product-experience.md` +7/-5、`docs/architecture.md` +5/-0、`TASK.md`），`git diff --exit-code f2db70b HEAD -- mediaflow/domain mediaflow/infrastructure mediaflow/interfaces/service_api.py mediaflow/cli.py scripts config pyproject.toml` 为空，`git diff BASE(23adc9b) HEAD -- docs/progress.md docs/roadmap.md` 亦为空，故 evidence key、聚合、失败类别、激活门禁、route、权限、表、迁移与两个 marker（10 / 22）均未动。被要求的行为确实落地：`_destination_sample_failure_row` 只多一个取自既有 `_destination_sample_next_action(category)` 的 `nextAction`、`_destination_sample_resolution_row` 写 `None`、该 map 相对 `f2db70b` 逐字节不变、行表六列且第六格为 `boundedSetupText(item.nextAction)`；run 级与单样本 `Next action`、`failures[0]`、碰撞表、not-ready 门禁及其文案、22.6-J `determinationText` 六处调用、`1-8 samples` 控件逐字节未改。质量闸门在被拒 checkpoint 上全绿（回归 871 `OK (skipped=7)`、聚焦 57、ruff/format 308 文件、compileall、`pip check`、两份示例配置校验、wheel 隔离 smoke 退出 0 且 marker 不变、`git diff --check`、FFmpeg 与业务层写操作审计、alist ignore、Markdown 120 文件 25 链接 0 断链、机密扫描），故本轮不是构建或回归失败。阻塞缺陷只有一条：我独立跑了 16 项探针（逐次一处改动、`git checkout --` 还原并核对干净树），15 项按要求命中（含 TASK 指定的八项与 comment-only control），唯一未命中的是把 `_destination_sample_resolution_row:2259` 被要求的 `"nextAction": None` 换成默认失败句子后 `tests.test_configuration_destination_precheck` 仍 `Ran 21 tests ... OK`——原因已在代码中确证：该 builder 只在 `multiple_destination_storages` 提前返回处（`:1491`）可达，而 Required Test 1 的成功样本由 `_probe_destination_sample`（`:2192-2202`）内联构造且完全不带该键，因此 `assertIsNone(items[2].get("nextAction"))` 是对另一个 builder 的空洞断言，Closure Checklist 中对应的 `[x]` 无证据支撑；一旦该行漂移，`multiple_destination_storages` 页面上每个成功解析的样本都会显示失败恢复动作，正是本 Slice 要消除的逐样本误配。此缺陷源于我自己 Phase 22.6-L Task 的措辞（Required Test 1 未指明由哪个 builder 产生成功行，而 Technical Scope 又禁止改该文件任何其它行），不计入实现角色偏离。判定沿用 2026-08-28 Phase 22.6-H 的同类先例（被要求行为被替换后全绿即拒），修正同形且更小：仅两条断言、零生产改动，且我已先验证其可满足且可证伪（在既有 `test_multiple_destination_storages_is_bounded_failure`（`tests/test_configuration_destination_precheck.py:783`）后加 `assertIsNone(result["items"][0]["nextAction"])` 与 `items[1]` 等价断言，在 shipped tree 通过、在上述变异下让该命名测试失败）。非阻塞观察四项：`_probe_destination_sample` 的行完全省略该键而非显式 `None`（页面两种情况都印 `-`，但 API 消费者下标取值会 `KeyError`，形状统一另开 Slice）、探针还原用了反向 patch 而非 TASK 规定的 `git checkout --`（最终树经我自己的 diff 确认逐字节正确，仅程序问题）、新列标签仍只由一条精确表头字符串钉住、22.6-H-F1 与 22.6-I 记录的残留证明缺口未变；未推送；`TASK.md` 当时只含仅证据的 Phase 22.6-L-F1 修正，生产树必须保持与 `74919a3` 逐字节一致。PASS — 2026-08-29 于 `b198c96`（Phase 22.6-L-F1 仅证据修正）：checkpoint 只改两个文件——`tests/test_configuration_destination_precheck.py` +2/-0 与 `TASK.md` +75/-9；`git diff --exit-code 74919a3 HEAD -- mediaflow scripts config pyproject.toml` 为空，实现角色自身窗口 `git diff --exit-code cf99c6b HEAD -- mediaflow docs scripts config pyproject.toml` 亦为空（`cf99c6b` 是我自己的 22.6-L 审核记录，只动 `docs/progress.md`、`docs/roadmap.md` 与 `TASK.md`），`tests/test_operator_ui.py` 与 `tests/test_configuration_destination_activation.py` 自 `74919a3` 逐字节未改，无测试新增/改名/删除，marker 仍为 10 / 22。被要求的两条断言逐字出现在 `test_multiple_destination_storages_is_bounded_failure` 的 `projectedOutcome` 断言之后（`tests/test_configuration_destination_precheck.py:784-785`），均为直接下标而非 `.get`，且该运行的两行都出自 `_destination_sample_resolution_row`。我自己重跑九项探针（逐次一处改动、`git checkout --` 还原并核对干净树）：把该 builder 的 `"nextAction": None` 换成默认失败句子后命名测试 FAIL（`'correct the destination or conflict policy, then rerun precheck' is not None`）——正是在 `74919a3` 上静默通过的那处变异，唯一阻塞缺陷已闭合；删除该行后同一测试以 `KeyError: 'nextAction'` ERROR，证明用的是下标而非 `.get`；把 `_destination_sample_failure_row` 的 map 查表改成 `None` 后 `test_destination_precheck_per_sample_rows_carry_their_own_next_action` 仍 FAIL，证明本修正未挤掉或弱化 22.6-L 的既有证明；comment-only control `Ran 21 tests ... OK`；另三项自选变异（`""`、`False`、`:1491` 调用点改建失败行）亦全部被同一测试捕获。闸门全绿：回归 871 `OK (skipped=7)`、聚焦 57（29+21+7）、ruff/format 308 文件/compileall/`pip check`/两份示例配置校验/wheel 隔离 smoke 退出 0 且 `Schema: 22`/`git diff --check`/FFmpeg 与业务层写操作审计/alist ignore/Markdown 120 文件 25 链接 0 断链/机密扫描。非阻塞观察四项（不得升格为 blocker）：Closure Checklist 两个 `[x]` 在 `HEAD` 上字面为假——它们引用的 `74919a3` 相对命令包含 `docs`，而我自己的中间记录 `cf99c6b` 动过 `docs`，故 `git diff --numstat 74919a3 HEAD` 实为四条路径而非两条；报告 Validation Evidence 已如实说明并给出 BASE 相对与仅生产的等价命令，我已复核其为空且精确，措辞缺陷在我自己的 Task，下一 Task 的 identity 命令改以 BASE 与接受 checkpoint 为锚。对我上一条记录的精确化：22.6-L 的 `.get` 断言并非完全空洞——给 `_probe_destination_sample` 的行写非空动作确实会让该测试失败，未被覆盖的只是 resolution builder，而这正是本修正钉住的。同类新缺口一项：删除 `_destination_sample_resolution_row` 的 `"message": None`（22.6-H 落地的键）不会让任何测试失败（`Ran 21 tests ... OK`）。行形状不对称比我在 `74919a3` 记录的更宽：四个产行点中有两个完全省略 `nextAction`（`_probe_destination_sample:2201` 与单样本完成行 `:1768-1780`），API 消费者下标取值仍可能 `KeyError`，CURRENT 文档“逐样本行携带 `nextAction`”的说法也略微超前于代码；我已只读验证这两处各加一行即可让观察到的五种行形状成为同序十键元组，且回归仍 871 `OK`。22.6-H-F1 与 22.6-I 记录的残留证明缺口未变。Phase 22.6-L 由此 **PASS / CLOSED**（被拒 `74919a3` 与其 FIX REQUIRED 记录保留不改写），Phase 22.6 保持开放；未推送；下一合法 Slice 为 **Phase 22.6-M**（统一逐样本目标行形状并加以证明：两处内联行各加 `"nextAction": None`、一项跨分支形状测试、resolution 行其余恒 `None` 键补直接下标证明） |

## 当前节点

截至 2026-08-27，项目完成了安全优先的核心执行链、Phase 21 有界人工/文件管理基础、
Phase 22.1 内部 Storage 配置 CRUD 基础、Phase 22.2 whole-document Active authority，以及
Phase 22.3 Local Storage + Library guided journey。Phase 22.3 的全部 correction slices 和
phase-level Final Closure Audit 均为 **PASS / CLOSED**；Phase 22.4 Recognition Configuration +
Strategy Test 也已在 F2 恢复指导修复后独立验收 **PASS / CLOSED**。Phase 22.5 Metadata 配置与
修正旅程的全部 Slice（22.5-A offline resolution preview、22.5-B live Metadata test + F1、
22.5-C candidate confirmation + F1/F2、22.5-D same-Provider correction test 及其 correction、
22.5-E 单项 Metadata correction DryRun continuation + F1）均已独立 High PASS；其中 22.5-E 的
首个 checkpoint `08dfd4f921728755209b6d52347d28f221121c47` 曾被判定 **FIX REQUIRED**（Files
detail Web continuation section 未挂载到 DOM），该记录保留不改写，F1 correction checkpoint
`dce5c0ba53bb4fc91f18d1b5d6d56564cd3cfe62` 已挂载该 section 并补齐可失效 Web 回归证据，于
2026-08-27 通过独立 High re-review。同日 phase-level Final Closure Audit 判定 Phase 22.5
**PASS / CLOSED**。下一合法边界是 Phase 22.6 Naming / Classification / Organize 配置与离线
预览旅程，起始 Slice 为 Phase 22.6-A；Provider switching、通用 Task resume 与更宽的逐项
checkpoint 恢复仍为 TARGET。`dce5c0ba53bb4fc91f18d1b5d6d56564cd3cfe62` 已于 2026-08-27 在显式
操作员授权下推送到 `origin/main`，Phase 22.5 的收口 push gate 已满足。
Phase 22.6-A 首个 checkpoint `90ce13a6c6c39912dd389f71a1189314ff24eb5d` 已于 2026-08-27
独立审核判定 **FIX REQUIRED**：NamingPolicy Managed Draft CRUD、引用阻断、exact-revision 零变更
离线命名预览与零 Storage/Provider 证据均已验证通过，但 Web 端 `renderNamingPreview` 挂载缺少可
失效回归（删除挂载行后 810 项离线测试仍全绿），且 invalid template 仅通过私有 `_normalize`
验证，未在 service/API 边界证明 "Draft unchanged" 与"修正模板后预览成功"。该记录与被拒 SHA 保留
不改写。当前唯一合法 Slice 是 Phase 22.6-A-F1 correction（仅补测试与文档，不改产品行为）；
Phase 22.6 尚未关闭，Phase 22.6-B ClassificationPolicy 编辑与目标解析预览、目标冲突/能力预检和
activation evidence 不得提前开始。
Phase 22.6-A-F1 correction checkpoint `30af69ac82b30f8a45ad66afbd3c9747597c8fe7` 已于
2026-08-28 通过独立 High re-review，Phase 22.6-A 判定 **PASS / CLOSED**。复审独立复现了可证伪
性：删除 preview 挂载、删除 NamingPolicy list 挂载、把 preview 挂载移到 `detail.hidden = false;`
之后、把 preview 控件与标题从 `detailContent` 脱挂，五项 operator-UI 对照全部失败；`_normalize`
接受空模板与渲染器接受路径分隔符两项 service-boundary 对照亦全部失败，未改动树全部通过。
`git diff 90ce13a 30af69a` 仅触及测试与文档，`mediaflow/`、`scripts/`、`config/` 与
`pyproject.toml` 逐字节相同，产品行为、API 契约、evidence key、schema marker 与 activation
语义均未变化。Phase 22.6 尚未关闭：下一合法 Slice 是 **Phase 22.6-B**（managed
ClassificationPolicy 编辑 + exact-revision 离线分类预览）；OrganizePolicy 编辑、组合最终目标
路径预览、目标冲突/能力/存在性预检与 combined activation evidence 仍为 TARGET，不得提前开始。
Phase 22.6-B checkpoint `5e2da5c634f1fa72a40e5f50b035260418fe1a37` 已于 2026-08-28 通过独立
High Review，判定 **PASS / CLOSED**：ClassificationPolicy managed CRUD、规则摘要、
RecognitionTypePolicy 引用阻断、MediaLibrary 解析解释和 exact-revision classified/unclassified
离线预览均已验证；配置 schema marker 前向升级至 7（marker 6 数据库可原地重开且命名预览证据完好），
Runtime marker 仍为 22。复审独立复现了八项可证伪对照（五项 operator-UI 挂载、三项 service-boundary
规则）全部先失败后通过，并验证 managed 归一化对 runtime 语义为恒等（示例文档 6 条规则经归一化后
由生产 loader 装载得到完全相同的 `ClassificationRule`），路径与规则安全仍由生产 domain 拥有。
Phase 22.6 未关闭：下一合法 Slice 是 **Phase 22.6-C**（managed OrganizePolicy 编辑 +
exact-revision 离线组织授权解释）。组合最终目标路径预览、目标冲突/能力/存在性预检、Storage 能力
探测与 combined activation evidence 仍为 TARGET，不得提前开始。`5e2da5c634f1fa72a40e5f50b035260418fe1a37`
与文档记录 `279904c` 尚未推送 `origin/main`；Slice 级关闭不要求推送，Phase 22.6 的收口关闭需显式
操作员授权后推送。
Phase 22.6-C checkpoint `47096eeaf1769b79cf3d0c67bcdf0c75b6c344aa` 已于 2026-08-28 通过独立
High Review，判定 **PASS / CLOSED**。复审独立复现了十一项可证伪对照（五项 operator-UI 挂载、两项
被收窄的 `overwrite` 断言、四项 service-boundary 规则）全部先失败后恢复通过，并独立复核了 22 组
非默认字段组合的归一化零语义漂移与幂等、零副作用与 RecognitionType C 身份保持、
marker 7→8 前向升级与 Runtime marker 仍为 22，以及编辑限制未改动 loader。本 Slice 交付 managed
OrganizePolicy CRUD/Copy、`organize_policy:<id>` 引用阻断、仅接受 Move/Copy/HardLink/SoftLink 的
编辑限制（拒绝 `delete` 与 `create_directory`），以及经生产 `RecognitionTypePolicyResolver` 解析、
零 Storage/Provider/Planner/Executor 构造的精确 revision 组织授权解释。
Phase 22.6 未关闭：下一合法 Slice 是 **Phase 22.6-D**（exact-revision 组合最终目标路径预览，
仅计算与解释 `MediaLibrary.RootPath + ClassificationPolicy relativePath + NamingPolicy 目录/文件名`
的组合结果并持久化其证据），已写入 `TASK.md`。目标存在性/冲突/能力预检、Storage 能力探测、
combined activation evidence、Planner/Executor 改动与任何 activation gate 变更仍为 TARGET，
不得提前开始。`47096eeaf1769b79cf3d0c67bcdf0c75b6c344aa` 及其文档记录尚未推送 `origin/main`；
Slice 级关闭不要求推送，Phase 22.6 的收口关闭需显式操作员授权后推送。

Phase 22.6-D checkpoint `c7ec192b3b20f236cca5a70ed59cad43e0851242` 已于 2026-08-28 通过独立
High Review，判定 **PASS / CLOSED**。本 Slice 把 planner 的 composition 与 path-safety 判定提取为
`mediaflow/domain/organizer.py` 中唯一的共享 owner，Planner 与 managed preview 由同一份代码回答
"文件最终去哪里"；Web/API 按 composition 顺序展示解析后的 RecognitionType C 身份、
RecognitionTypePolicy、MediaLibrary rootPath、ClassificationPolicy relativePath、NamingPolicy 目录
段与文件名、root-relative 与 Storage-relative 目标，并持久化 current/stale 或可恢复失败证据。复审
独立复现了七项可证伪对照（四项 operator-UI 挂载、共享 classification 路径守卫、unsafe 判定短路、
RecognitionType 取自 NamingPolicy ID）全部先失败后恢复通过，并独立复核了与真实
`OrganizePlanner.plan` 的 8 组 composition parity、未改动的 organizer/planner/executor 与
Phase 22.6-C 套件、零 Storage/Provider/Planner/Executor 构造、证据中不含 Storage rootPath 或私有
路径、marker 8→9 前向升级与 Runtime marker 仍为 22。
Phase 22.6 未关闭：下一合法 Slice 是 **Phase 22.6-E**（managed exact-revision 只读目标预检，仅
Local 目标 Storage），已写入 `TASK.md`。该 Slice 只做只读探测：经 `ReadOnlyStorageGuard` 复用生产
`OrganizePlanner.plan` 与 `ConflictResolver.apply_configured` 报告目标根/目标存在性、最深已存在
祖先、按配置 ConflictStrategy 的冲突投影与 declared-vs-actual Storage 能力比对，禁止任何写入或
mutation 探测。远端 SMB/OpenList/S3 目标预检、重复媒体与跨项碰撞检测、附件预检、绝对挂载路径展示、
combined activation evidence 与任何 Planner/Executor/执行改动仍为 TARGET，不得提前开始。
`c7ec192b3b20f236cca5a70ed59cad43e0851242` 及其文档记录尚未推送 `origin/main`；Slice 级关闭不要求
推送，Phase 22.6 的收口关闭需显式操作员授权后推送。

Phase 22.6-E checkpoint `7353b0d22497e6e3e596c93c7052eea34daf27df` 已于 2026-08-28 经独立 High
审核判定 **FIX REQUIRED**，该 SHA 保留、不得 amend/squash/改写，且未推送。审核已接受的部分：共享
`_validate_destination_request`/`_resolve_destination` 抽取行为等价且 22.6-D 套件逐字节未改仍绿；目标
Storage adapter 由未修改的 revision document 构造并在包装前读取声明能力；全部探测在
`ReadOnlyStorageGuard` 子类内进行且七个 mutation 计数在产出证据前断言为零；复用未修改的生产
`OrganizePlanner.plan` 与 `ConflictResolver.apply_configured` 并按每种配置 ConflictStrategy 断言冲突
投影；declared-vs-required 能力比对、全部有界失败类别与"其余证据不变"断言、精确 version/digest 与
stale/Active 语义、marker 9→10 加 9→10 与 8→10 前向升级、Runtime marker 仍为 22、API 400/409/503 与
Web/API 同一权限与状态门禁。判定 FIX REQUIRED 的原因是该 checkpoint 缺失自身 Required Test 的四项
断言：RT10 要求"asserted, not assumed"的 zero-Provider/zero-Executor/zero-Task 非构造证明完全缺席
（本 Phase 前序 Slice 均以注入 `AssertionError` double 证明同类主张）；RT4 枚举的
`relativeDestination` 与 `destinationPath` 无任何断言，而 `renderDestinationPrecheck` 直接读取
`result.destinationPath` 并把假值送入红色"Destination is not ready"横幅；RT4 的 fully-missing
subtree 用例已执行但从未断言 `deepestExistingAncestor` 或 `directoriesToCreate`，多条"将创建目录"
列表无证明；RT5 的 `invalid` 投影既不可达（`_resolve_destination` 在构造任何 Storage 之前即以
`unsafe_destination` 拒绝，而 Planner 由同一 `composition.safe` 判定 `INVALID_DESTINATION`）也未被
证明，而 `docs/progress.md` 声称投影会报告它。唯一合法下一 Slice 是 **Phase 22.6-E-F1**（已写入
`TASK.md`）：除消解不可达 `invalid` 分支并使实现/测试/文档一致外仅补证据，不得扩大产品范围。远端
SMB/OpenList/S3 目标预检、写入式能力探测、重复与跨项碰撞检测、附件预检、combined activation
evidence 与任何执行改动仍为 TARGET，不得开始。

Phase 22.6-E-F1 correction checkpoint `ee5225dd0e74a7382b6747c6315776413f7fd249` 已于 2026-08-28 经
独立 High 复审判定 **PASS**，Phase 22.6-E 随之 **PASS / CLOSED**；被拒 SHA
`7353b0d22497e6e3e596c93c7052eea34daf27df` 及其 FIX REQUIRED 记录保留，`docs/progress.md` 仅追加。
四项 blocker 均以可证伪对照复核通过：同步路径注入 `MetadataProviderRegistry(())` 使两个 subtest 均以
`AssertionError: destination precheck constructed Provider` 失败，worker 内注入则经有界 `unavailable`
转换失败；互换 `relativeDestination`/`destinationPath` 与删除 Web destination-path 字段行各自使对应
断言失败；截断 `directoriesToCreate` 只让 fully-missing subtree 用例失败而 partial 用例仍通过；移除新
增的防御性 `INVALID_DESTINATION` 拒绝使 `unsafe_destination` 用例失败。marker 保持 10 / 22，842 项离线
回归、聚焦 34 项、ruff、compileall、`pip check`、两份示例配置校验、120 个 Markdown 文件 25 条本地链接
零断链、wheel 构建与隔离 smoke 均通过；`config/alist.json` 仍被忽略、未跟踪且未读取。

Phase 22.6 未关闭：下一合法 Slice 是 **Phase 22.6-F**（checked activation 要求当前目标预检证据，仅
Local 目标 Storage），已写入 `TASK.md`。该 Slice 只把既有 22.6-E 证据接入 `activate_checked` 门禁并给
出可执行的 Web/API 拒绝与恢复，不新增探测、不改 schema marker、不做任何写入。远端 SMB/OpenList/S3 目标
预检、写入式能力探测、重复与跨项碰撞检测、附件预检、绝对挂载路径展示与任何执行改动仍为 TARGET，不得
开始。已关闭的 22.6-A 至 22.6-E checkpoint 及其文档记录尚未推送 `origin/main`；Slice 级关闭不要求推
送，Phase 22.6 收口关闭需显式操作员授权后推送。

Phase 22.6-F checkpoint `e68e901a73107484dc0521b47b1b0001eed2b853` 已于 2026-08-28 经独立 High 审核判定
**PASS**，Phase 22.6-F 随之 **PASS / CLOSED**，Phase 22.6 仍未关闭。已接受：`activate_checked` 在既有
两项要求之后调用新的 `require_current_destination_precheck`，缺失、过期（version 或 digest 不符）、
失败（复述已存有界类别）与 `capability_gap` 四种情形各以有界、无秘密的说明加单一 next action 拒绝，
拒绝发生在任何激活之前，既有 Active 配置与全部已存证据一律不变；适用性规则为 document-level 且仅
Local（文档声明至少一个 `storageId` 指向 `type=local` Storage 的 MediaLibrary 时适用，其余包括完全没有
MediaLibrary 的文档一律显式 not applicable），远端-only Draft 不会被本 Phase 尚无法满足的要求锁死；
completed 投影空间经独立复核完备，缺失或非目录 root、不支持的 Storage 类型与不安全组合均已判为 FAILED，
不存在 completed-but-unsafe 放行；门禁路径零探测、零 Storage/Provider/Planner/Executor 构造，十张
Runtime 表在拒绝与成功两条路径上均为空；Web/API 以相同权限与相同 409 拒绝相同情形，且未新增 evidence
key、请求字段、响应字段、权限或状态码，marker 保持 10 / 22。非阻塞观察（延后，不构成关闭条件）：Web 的
`checkedActivationEvidenceIsCurrent` 仍只汇总 Local setup check 与 Strategy Test，因此仍有 Local Draft
看到可点击的 checked 激活控件而由服务端有界拒绝——属控件标注缺口而非安全缺口，正是下一 Slice 的核心；
适用性为文档级，声明了未被路由的 Local MediaLibrary 的 Draft 会被拒绝直到修正或改走 unchecked 激活。
下一合法 Slice 是 **Phase 22.6-G**（Web checked-activation 控件与告警覆盖全部三项要求，并补上
Executor double 的模块命名空间断言），已写入 `TASK.md`。远端 SMB/OpenList/S3 目标预检、写入式能力探测、
重复与跨项碰撞检测、附件预检、绝对挂载路径展示与任何执行改动仍为 TARGET，不得开始。已关闭的 22.6-A 至
22.6-F checkpoint 及其文档记录尚未推送 `origin/main`；Slice 级关闭不要求推送，Phase 22.6 收口关闭需显式
操作员授权后推送。

Phase 22.6-G checkpoint `b9cc35e2677a35920042b5695f87b50a80025ef0` 已于 2026-08-28 经独立 High 审核判定
**FIX REQUIRED**，Phase 22.6-G 未关闭，Phase 22.6 仍未关闭；被拒 SHA 及本记录一律保留，不得 amend、
squash 或改写历史。已接受：Web 侧 checked activation 判定收敛为单一 predicate
`destinationPrecheckActivationRequirement`（Local 适用性、证据当前性、`completed`、`capability_gap` 四
个条件），`renderDestinationPrecheck`、`checkedActivationEvidenceIsCurrent` 与
`destinationPrecheckBlocksCheckedActivation` 共用同一规则，guided 面板、revision 详情与预检区块不可能
互相矛盾；四条 Web next action 与服务端 `require_current_destination_precheck` 的四条 `next_action` 逐
字一致，适用性与 stale 判定与门禁同源（`_objects(redact_remote=True)` 保留 Local Storage 的 `id`/`type`，
`_destination_precheck_document` 用同一 version/digest 比较），两个插值均在领域层有界 500 字符且父提交
已在同页展示，本 Slice 未新增任何泄密面；两项延后项均已可证伪落地——适用性补上
`"mediaLibraries" in revision.document` 守卫（回退该守卫即以 `ValueError` 失败），激活模块命名空间经
`TYPE_CHECKING` 加 `__getattr__` 与调用点 `organizer_application.OrganizePlanner()` 硬化，注入真实
module-level `OrganizerExecutor` import 与让 `__getattr__` 返回可遮蔽定义点的 import-time alias 两个独立
探针均使命名空间断言失败；marker 保持 10 / 22，两份冻结套件逐字节未改，22.6-F 套件零删除，849 项离线
回归、ruff、compileall、`pip check`、两份示例配置校验与 wheel 隔离 smoke 全部通过。判定 FIX REQUIRED 的
原因是本 Slice 的核心操作员可见文案与承载它的 predicate 契约完全无断言：删除 `operator_ui.py:705/708/716`
三处 ``message = `Checked activation blocked: ${nextAction}.` `` 赋值后整套 849 项测试仍全绿，而其后果是
`message` 保持 `null`、预检区块渲染 `text` 助手的裸 `-`、`!requirement.message` 守卫返回 `null`，于是
guided 面板重新静默隐藏按钮、revision 详情回退到两项要求文案——正是本 Slice 要消除的缺陷可在三个界面同时
复现；从 `:719` 返回对象中删掉 `message` 同样全绿；把 `:727` 的渲染载荷替换为 `'Checked activation
blocked.'` 字面量（丢失 next action 与 `error` 样式）亦全绿，而父提交 `f601606` 曾逐字断言四条完整句子，
这些断言正在本次 21 行删除之中，属证明强度回退。此外 `TASK.md` 再次未写 Completion Report，而 22.6-F 复
核已明确要求后续 Slice 必须记录。唯一合法下一 Slice 是 **Phase 22.6-G-F1**（已写入 `TASK.md`）：仅补测
试与 Completion Report，禁止改动任何生产文件。远端 SMB/OpenList/S3 目标预检、写入式能力探测、重复与跨项
碰撞检测、附件预检、绝对挂载路径展示与任何执行改动仍为 TARGET，不得开始。已关闭的 22.6-A 至 22.6-F
checkpoint 及其文档记录尚未推送 `origin/main`；Slice 级关闭不要求推送，Phase 22.6 收口关闭需显式操作员
授权后推送。

Phase 22.6-G-F1 checkpoint `5ca1247156e6de4615dff53f5fc8e421bd8bf264` 已于 2026-08-28 经独立 High 审核
判定 **PASS**，Phase 22.6-G 由此 **PASS / CLOSED**（经修正接受），被拒 checkpoint
`b9cc35e2677a35920042b5695f87b50a80025ef0` 与其记录保留；Phase 22.6 仍未关闭。修正严格限于证据范围：仅
`tests/test_operator_ui.py`（+58/-0）与 `TASK.md`（+157/-23，状态行加 Completion Report）变更，
`git diff --exit-code b9cc35e 5ca1247 -- mediaflow scripts config pyproject.toml` 为空，生产文件逐字节
未改，`tests/` 零删除，无任何文档改动，marker 保持 10 / 22。新增的
`test_destination_precheck_blocking_sentence_contract_is_body_scoped` 以 `_js_function_body` 加
`_js_braced_body` 把断言下沉到具体分支，因此三处逐字节相同的 blocked 文案首次可各自证伪：十一项独立探
针全部被捕获且每次只有该测试失败（删除 `:705`/`:708`/`:716` 任一处文案、截断 `:712` failed 模板、从
`:719` 删掉 `message`、把 `:727` 载荷换成固定字面量、删除 `:713`/`:717` 的 `style = 'error';`、从返回对
象删掉 `style`、去掉三条句子的句末句号、互换 missing 与 stale 的 `nextAction`），其中后五项超出 TASK 要
求，且互换探针证明分支归属此前确实未被证明。离线回归 849 → 850（纯增量），operator-UI 模块 20 → 21，三
份冻结套件逐字节未改，ruff、compileall、`pip check`、两份示例配置校验、Markdown 链接检查、机密扫描与
wheel 隔离 smoke 全部通过。修正 TASK 自身的 Required Test 8 措辞有误——评审记录提交 `ed17ebb` 位于两个
checkpoint 之间——实现方如实报告并给出等价证明，后续修正 TASK 必须把此类 diff 限定到生产路径。
下一合法 Slice 是 **Phase 22.6-H**（有界多样本 Local 目标预检与跨项目标碰撞检测：单一 RecognitionType、
最多 8 个样本、复用生产 `OrganizePlanner` 的 `claimed_destinations` 与 `TARGET_COLLISION`、逐项独立状态
与恢复、碰撞判为 FAILED `duplicate_destination`、样本跨目标 Storage 判为 FAILED
`multiple_destination_storages`、不改激活门禁、不改 marker、仍为只读且零变更），已写入 `TASK.md`。远端
SMB/OpenList/S3 目标预检、写入式能力探测、单次请求多 RecognitionType 或多目标 Storage、known-media 重复
检测、附件预检、绝对挂载路径展示与任何执行改动仍为 TARGET，不得开始。已关闭的 22.6-A 至 22.6-G
checkpoint 及其文档记录尚未推送 `origin/main`；Slice 级关闭不要求推送，Phase 22.6 收口关闭需显式操作员
授权后推送。

2026-08-28 在显式操作员授权下执行了 Phase 22.6 的首次推送：`main` 快进推送至 `origin/main`
（`be38631` → `3ace53c7cdcc3312033f388d8f68d2d7d1a159ae`，共 17 个 commit）。`origin/main` 现已包含
Phase 22.6-A 至 22.6-G 的全部已关闭 checkpoint、被保留的被拒 checkpoint（`90ce13a…`、`7353b0d…`、
`b9cc35e…`）与全部审核记录，历史保持线性，未 amend/squash/改写。推送前复核：工作树干净、850 项离线
回归 `OK (skipped=7)`、`git diff --check` 干净、`config/alist.json` 仍被忽略且未跟踪、被推送 diff 中
无凭据、私有端点、header、cookie 或绝对用户路径。本推送记录提交本身在同一授权下随后推送，因此
`origin/main` 与本地 `main` 保持一致。Slice 级关闭仍不要求推送；Phase 22.6 的收口关闭仍需
phase-level Final Closure Audit，Phase 22.6-H 的 checkpoint 在获得新授权前仍只保留在本地。

2026-08-29 在新的显式操作员授权（"推送到github"）下执行了 Phase 22.6 的第二次推送：`main` 快进推送至
`origin/main`（`a9473c6` → `af9ca9a`，共 10 个 commit），历史保持线性，未 amend/squash/改写。本次推送把
Phase 22.6-H、22.6-H-F1、22.6-I、22.6-J、22.6-K 的 checkpoint、它们的审核记录，以及 22.6-K 的 PASS 记录与
Phase 22.6-L 的 TASK 定义（`af9ca9a`）一并送上 `origin/main`。被保留的被拒 Phase 22.6-H checkpoint
`d8c2ae04e578955ddbbd29c413f235bf4cf08f42` 仅作为祖先随历史进入远端，并非作为接受被推送，仍然是被拒状态。
推送前复核：工作树干净、`git diff --check` 干净、`config/alist.json` 仍被忽略且未跟踪且未被任何被推送
commit 触碰、被推送 `mediaflow`/`scripts`/`config`/`pyproject.toml` diff 中无凭据、token、私有端点、
header、cookie 或绝对用户路径。`origin/main` 与本地 `main` 现同为 `af9ca9a`。Slice 级关闭仍不要求推送；
本次推送满足了 Phase 22.6 的 push gate，但**不构成 Phase 关闭**，phase-level Final Closure Audit 仍未执行。
上文 2026-08-28 段落中"Phase 22.6-H checkpoint 仍只保留在本地"的说法按当时事实记录，由本段取代。

Phase 22.6-H checkpoint `d8c2ae04e578955ddbbd29c413f235bf4cf08f42` 已于 2026-08-28 经独立 High 审核判定
**FIX REQUIRED**，被拒 checkpoint 保留且未推送，`main` 仍只领先 `origin/main` 一个 commit；Phase 22.6-H
未关闭，Phase 22.6 仍未关闭。本次审核接受的部分包括：恰好十个允许文件（+1338/-71）且
`docs/progress.md`、`docs/roadmap.md` 正确留给评审角色；单一 RecognitionType 一次解析、1–8 样本逐索引前
置校验、一次容量租约、一个 `_ReadOnlyDestinationStorage` 守卫、一次 worker 提交与一个整体超时；逐样本独
立的 `destinationPath`/`projectedOutcome`/`plannerConflicts`/`failureCategory` 与有界 message，中间样本失
败不掩盖也不改写邻居行；跨项碰撞由生产 `OrganizePlanner` 在 `claimed_destinations` 与逐索引不同的合成源下
真实产生 `TARGET_COLLISION`；`duplicate_destination` 与 `multiple_destination_storages` 两类有界失败各带
明确 next action 且被激活门禁拒绝（门禁逐字节未改，放宽门禁的探针会使拒绝测试失败）；零变更、
`authorityGranted` 恒为 `none`、证据路径仅相对且注入绝对 `rootPath` 立即被测试捕获；单样本文档语义与既存
evidence 渲染兼容（`sampleCount` 默认 1，仅新增三个 key）；859 项离线回归 `OK (skipped=7)`、`tests/` 零删
除（850 → 859）、marker 10 与 Runtime marker 22 不变、wheel 隔离 smoke、ruff/format/compileall/
`pip check`/两份示例配置校验/Markdown 链接检查/机密扫描/FFmpeg 审计/业务层写操作审计全绿；三份文档的
CURRENT 声明与实现一致，远端预检、写入式能力探测、`ConflictType.DUPLICATE_MEDIA`、附件预检、绝对挂载路
径展示与执行仍为 TARGET。唯一阻塞项：Required Test 1 的 most-severe verdict 聚合不可证伪——
`test_multiple_samples_success_most_severe_verdict_and_distinct_rows` 的样本序为
`["manual_confirmation_required", "ready", "ready"]`，最严重结果位于 index 0，因此把生产聚合
`max(outcomes, key=severity)` 换成 `outcomes[0]` 后 859 项套件仍 `OK`，仓库中没有任何断言能区分「取最严重
样本」与「取第一个样本」，违反 `TASK.md` 第 228 行、Required Test 1 自身的括注与已勾选的 Closure Checklist
声明。生产运行时行为看来正确，缺的是证据。修正 Slice **Phase 22.6-H-F1** 已写入 `TASK.md`：纯证据修正，
不得改动任何生产文件，需新增一项最严重样本既不在首位也不在末位的多样本测试，使其在 `outcomes[0]`、
`outcomes[-1]` 与 `min(outcomes, key=severity)` 三种替换下均失败，并断言聚合 `verdict` 可与顶层首样本投影
不同。评审同时记录了若干非阻塞观察（单次运行仅两种投影可达故严重度表的细分序当前不可达、逐样本
capability-gap 循环与只看首样本等价、`plan.target` 与 `composition.target` 在所有覆盖场景一致、守卫计数复
查属纵深防御、API 两处形状校验与服务层重复、验证标签未被断言、`sampleCount > 1` 时 run 级字段渲染在
「First sample destination」标题之下、归一化输入取首个成功归一化的样本），这些不是 22.6-H-F1 的关闭条件，
也不得在该 Slice 中改动。

Phase 22.6-H-F1 checkpoint `4455198a6ef3b93fe1e92cef73660039620e756e` 已于 2026-08-28 经独立 High 审核
判定 **PASS**，Phase 22.6-H 由此 **PASS / CLOSED**（经证据修正接受），被拒 checkpoint
`d8c2ae04e578955ddbbd29c413f235bf4cf08f42` 与其 FIX REQUIRED 记录保留；Phase 22.6 仍未关闭。修正严格限于
证据范围：仅 `tests/test_configuration_destination_precheck.py`（+138/-0，零删除行）与 `TASK.md` 变更，
`git diff --exit-code d8c2ae0 HEAD -- mediaflow scripts config pyproject.toml` 为空，生产与文档逐字节未
改，marker 保持 10 / 22。两项新测试把 `manual_confirmation_required` 样本放在 index 1，因此
`outcomes[0]`、`outcomes[-1]`、`min(...)` 三种替换与「顶层首样本 details 换成末样本」四项探针分别使
Required Test 1 或 Required Test 2 失败，comment-only control 不触发；另五项自选探针中，删除聚合
`"verdict"` 覆盖（让首样本自身 verdict 生效）与颠倒 severity 表都使两项新测试失败，说明严重度序本身亦已受
约束。离线回归 859 → 861（纯增量），聚焦模块 47 项，ruff、compileall、`pip check`、两份示例配置校验、
Markdown 链接检查、机密扫描、FFmpeg 与业务层写操作审计、wheel 隔离 smoke（Runtime schema 22）全部通过。
非阻塞观察：全样本均为 `ready` 的多样本运行尚无 verdict 断言，因此把聚合换成常量仍不会被捕获（位置、顺序与
严重度序三类变异均已被捕获，`ready` 下界由单样本路径证明）；新测试的结果序为回文，行序颠倒由模块内另外三
项测试捕获；Web 多样本页面仍把 run 级字段（含聚合 verdict）渲染在「First sample destination」标题之下。
下一合法 Slice 是 **Phase 22.6-I**（把 Web 目标预检证据中的 run 级摘要与首样本区块分开，使聚合 verdict 不再
呈现为首样本的投影：仅改 `mediaflow/interfaces/operator_ui.py` 与 `tests/test_operator_ui.py`，单样本渲染
字段顺序不变、无新 evidence key、无新 route/权限/marker，仍为只读零变更），已写入 `TASK.md`。远端
SMB/OpenList/S3 目标预检、写入式能力探测、单次请求多 RecognitionType 或多目标 Storage、known-media 重复
检测、附件预检、绝对挂载路径展示与任何执行改动仍为 TARGET，不得开始。被拒 checkpoint、修正 checkpoint 与
本轮审核记录均未推送；Phase 22.6 收口关闭仍需 phase-level Final Closure Audit 与新的显式授权。

Phase 22.6-I checkpoint `6c0ba745772e315b941c1c3b314ab47e66e8f35a` 已于 2026-08-29 经独立 High 审核判定
**PASS**，Phase 22.6-I 由此 **PASS / CLOSED**，无被拒 checkpoint；Phase 22.6 仍未关闭。scope 严格落在
TASK 边界：仅 `mediaflow/interfaces/operator_ui.py`（+62/-29，全部在 `renderDestinationPrecheck` 之内）、
`tests/test_operator_ui.py`（+50/-1）与 `TASK.md`，对全部禁改路径的 diff 为空，marker 保持 10 / 22。多样本
运行现在先渲染 18 项 run 级字段并 `append(runList)`，其中聚合 verdict 的标签明确写作
`Run verdict (most severe sample)`，之后才输出「First sample destination」标题与 8 项真正逐样本字段；两个
列表合起来正是原单样本列表的 26 项，各自保持原相对顺序，因此聚合 verdict 不再被读成首样本投影，而逐样本
行表仍让操作员看清每个样本自己的状态与恢复。单样本分支 26 组标签与表达式逐字节未改，分支之后的行表、碰撞
表、stale/not-ready/无授权文案与 `1-8 samples` 控件亦逐字节未改，evidence key 读取不变，既存证据仍可渲染。
测试为纯增量 22 → 24，仅一处 TASK 明确许可的断言替换，且两项新测试都用 `_js_function_body` 与计括号的
`_js_braced_body` 限定在分支体内，无法靠脚本别处的同名文本通过。TASK 要求的六项探针全部被捕获，另六项自选
探针确认边界；离线回归 863 项 `OK (skipped=7)`、聚焦三模块 49 项，静态门禁、示例配置校验、Markdown 链接、
机密扫描、FFmpeg 与业务层写操作审计、wheel 隔离 smoke 全绿。非阻塞观察：26 项字段列表现在存在两份，日后
改标签必须同改两处而无测试比对；单样本字段顺序仍未被测试固定（既有问题，本轮由程序化核验代替）；删除某个
run 级字段（如 `Message`）不被任何测试捕获。同时更正我此前在 Phase 22.6-I Non-goals 中写下的一处事实错误：
多样本运行不可能在「First sample destination」下显示后续样本的目标——任何带 `failureCategory` 的样本都会让
整次预检经 `_destination_precheck_failure` 变为 FAILED，因此完成态证据的顶层 details 恒来自 index 0，索引
准确性不构成 Slice；而 22.6-H 关于**持久化归一化输入**取首个成功归一化样本的观察仍然成立且未改。真正的缺陷
是另一件事：FAILED 证据只携带 `sampleCount`、`items`、`collisions`（外加 `guardMutationCalls`、
`authorityGranted`），甚至可能没有 `result`，而 Web 用 `result.X === true ? 'YES' : 'NO'` 渲染，于是把从未
判定过的项打印成 `NO`。
下一合法 Slice 是 **Phase 22.6-J**（仅 Web 呈现：`destinationRootExists`、`destinationRootIsDirectory` 与
`targetExists` 缺失或非布尔时必须渲染为有界的 `NOT DETERMINED` 而不是伪造的 `NO`，单样本与多样本两个分支
都要改；仅改 `mediaflow/interfaces/operator_ui.py` 的 `renderDestinationPrecheck` 与
`tests/test_operator_ui.py`，不得改 evidence key、聚合逻辑、not-ready 门禁表达式、失败类别、route、权限、
行表与 marker），已写入 `TASK.md`。远端 SMB/OpenList/S3 目标预检、写入式能力探测、单次请求多 RecognitionType
或多目标 Storage、known-media 重复检测、附件预检、绝对挂载路径展示与任何执行或授权改动仍为 TARGET，不得
开始。本轮 checkpoint 与审核记录均未推送；Phase 22.6 收口关闭仍需 phase-level Final Closure Audit 与新的
显式授权。

2026-08-29 独立审核 Phase 22.6-J checkpoint `ccbddf2af92c1abf18d1162d0a6c37da9ee0a7cd` 判定 **PASS /
CLOSED**。该 Slice 只做 Web 呈现：新增唯一 helper `determinationText`（紧随未改的 `boundedSetupText`），把
`destinationRootExists`、`destinationRootIsDirectory`、`targetExists` 的渲染从 `=== true ? 'YES' : 'NO'`
改为 `true`/`false`/其他 → `YES`/`NO`/`NOT DETERMINED`，覆盖单样本与多样本共四个渲染点；生产改动四行加五行
helper，禁改路径 diff 为空。由于 `renderDestinationPrecheck` 把缺失载荷归一化为 `{}`，而 FAILED 证据通常只带
`sampleCount`、`items`、`collisions`（甚至没有 `result`），此前页面会把从未判定的项印成 `Destination root
exists / directory: NO / NO` 与 `Target exists: NO`——后者读起来像「不会覆盖任何东西」，正是失败预检无权作出
的断言；现在它读作未判定。完成态与 `missing_destination_root`、`destination_root_not_directory` 两类真实
root 失败的输出逐字未变（已在 application 侧核验 `(True, True)`、`(False, False)`、`(True, False)` 三种身份
与真布尔 `targetExists`；`None` 只出现在行表不渲染的字段上）。not-ready 门禁连同 `!result.destinationRootExists`
逐字节未改，未判定的 root 仍算 not ready，呈现层未软化门禁。测试 24 → 27 为纯增量、零替换，六项 TASK 探针
全部只让其命名测试失败且 control 全绿，另七项自选探针确认边界；离线回归 866 项、聚焦 52 项与全套静态门禁、
示例配置、Markdown 链接、机密扫描、FFmpeg 与写操作审计、wheel 隔离 smoke 全绿，marker 10 与 22 不变。
非阻塞观察：块内 `Retry safe` 与块外全部 `YES`/`NO` 无测试固定（本轮字节一致由人工核验）；逐样本行表仍丢弃
每个样本自己的有界 `message`（`configuration_objects.py:2241` 已持久化，run 级 `Message`/`Next action` 只取
最小下标失败样本 `failures[0]`，`:2009-2029`），因此第二个失败样本自己的解释在页面上无处可见；即便补上该列，
evidence 仍无逐样本 `nextAction`，不同类别的失败样本仍共用一条 run 级动作；22.6-H-F1 与 22.6-I 记下的证明
缺口（全 `ready` 多样本运行未断言 `verdict == "ready"`、单样本字段顺序未固定、两分支字段清单无对照测试）依旧
开放。
下一合法 Slice 是 **Phase 22.6-K**（仅 Web 呈现：逐样本目标行必须显示每个样本自己的有界 `message`，使一个
失败样本不再遮蔽另一个样本的诊断；只改 `mediaflow/interfaces/operator_ui.py` 的行表、`tests/test_operator_ui.py`
与 `tests/test_configuration_destination_precheck.py` 的一项新增证据测试，仅允许一处 TASK 明确点名的表头断言
替换，不得新增 evidence key、不得改聚合与门禁、marker 保持 10 与 22），已写入 `TASK.md`。逐样本 `nextAction`
入证据、远端 SMB/OpenList/S3 目标预检、写入式能力探测、单次请求多 RecognitionType 或多目标 Storage、
known-media 重复检测、附件预检、绝对挂载路径展示与任何执行或授权改动仍为 TARGET，不得开始。本轮 checkpoint
与审核记录均未推送；Phase 22.6 收口关闭仍需 phase-level Final Closure Audit 与新的显式授权。

2026-08-29 独立审核 Phase 22.6-K checkpoint `f2db70b28edb8f753ebed0d3805be7143b521264` 判定 **PASS /
CLOSED**。该 Slice 只做 Web 呈现：逐样本目标行表由四列扩为五列，末列以未改的
`boundedSetupText(item.message)` 渲染每个样本自己的有界 `message`；生产改动是一个 hunk（+3/-2），禁改路径与
`docs` 的 diff 为空。该字段自 22.6-H 起就已持久化（`configuration_objects.py:2241`，384 字节上界），而 run 级
`Message`/`Next action` 只取最小下标失败样本（`:2015-2023`，`failures[0]`），因此在本 Slice 之前第二个失败
样本自己的解释存在于证据与 API 响应却在页面上无处可见——违反「一个项目不得遮蔽另一个项目的诊断」。已只读
复现：三样本运行的 run 级为 `Destination composition failed (invalid_input)`，row 1 现在自带 46 字节
`ClassificationPolicy 'A' failed (invalid_rule)`；成功行的 `message: None` 经未改的 `boundedSetupText` 印为
`-`，故 22.6-K 之前的证据仍可渲染，路径仍为 Storage-relative 且无机密。not-ready 门禁、run 级字段清单、
22.6-J 的 `determinationText` 六处调用、碰撞表与两个 marker 逐字节未改。测试 27 → 28（仅一处 TASK 点名的表头
断言替换）与 18 → 19（纯增量），七项 TASK 探针全部只让其命名测试失败且 control 全绿，另六项自选探针全部被
捕获；离线回归 868 项、聚焦 54 项与全套静态门禁、示例配置、Markdown 链接、机密扫描、FFmpeg 与写操作审计、
wheel 隔离 smoke 全绿。非阻塞观察：证据仍无逐样本 `nextAction`，所有失败样本共用 `failures[0]` 派生的单一
run 级动作，因 MediaLibrary root 缺失而失败的样本会被要求去改 Draft 组合；`_destination_sample_next_action`
（`:2273-2289`）只区分六类 storage 级类别、把全部 composition 类别归入同一句，故逐样本动作列必须证明的是
composition 与 storage 级之间有区别，而不是类别两两不同；22.6-H-F1 与 22.6-I 记下的三处证明缺口依旧开放。
零文档改动本轮接受但已记录限定：`docs/product-experience.md:301-302` 与 `docs/architecture.md` 的 CURRENT
逐样本行描述现在是不完整而非错误，其刷新并入 22.6-L 且仍是 Phase 22.6 Final Closure 条件。
下一合法 Slice 是 **Phase 22.6-L**（每个失败样本自带并渲染自己的恢复动作：`_destination_sample_failure_row`
增加取自既有 `_destination_sample_next_action` 的 `nextAction`、成功行为 `None`、Web 行表增加末列
`Next action`，句子集合逐字节不变，run 级聚合、激活门禁、route、权限与 marker 均不动，另加有界的 CURRENT
文档刷新），已写入 `TASK.md`。远端 SMB/OpenList/S3 目标预检、写入式能力探测、单次请求多 RecognitionType 或
多目标 Storage、known-media 重复检测、附件预检与绝对挂载路径展示自本轮起正式记录为**移出 Phase 22.6**，
在后续 Phase 交付；任何执行或授权改动仍不得开始。本轮 checkpoint 与审核记录均未推送；Phase 22.6 收口关闭
仍需 phase-level Final Closure Audit 与新的显式授权。

2026-08-29 独立审核 Phase 22.6-L checkpoint `74919a33ac5ec9cde5b104a591ef3fdfb25a1bf3` 判定
**FIX REQUIRED**。scope 与全部机械证明均已独立复核通过：只改 TASK 允许的七个文件
（`configuration_objects.py` +2/-0、`operator_ui.py` 单一 hunk、两个测试模块纯增量、两份 CURRENT 文档、
`TASK.md`），禁改路径自 `f2db70b` 的 diff 为空，review-owned 的 `docs/progress.md` 与 `docs/roadmap.md` 自
BASE `23adc9b` 的 diff 为空，marker 仍为 10 / 22。被要求的行为确实落地且质量闸门全绿（回归 871
`OK (skipped=7)`、聚焦 57、ruff/format/compileall/`pip check`/两份示例配置/wheel 隔离 smoke 退出 0/
`git diff --check`/FFmpeg 与业务层写操作审计/alist ignore/Markdown 0 断链/机密扫描），八样本最坏情形
`result` 编码 5,751 字节远低于 32,768 上限。阻塞缺陷只有一条：两项被要求的生产改动之一没有任何测试证明。
我跑的 16 项探针里 15 项按要求命中（含 TASK 指定八项与 comment-only control），唯一未命中的是把
`_destination_sample_resolution_row:2259` 的 `"nextAction": None` 换成默认失败句子后整个证据模块仍
`Ran 21 tests ... OK`——该 builder 只在 `multiple_destination_storages` 提前返回（`:1491`）可达，而 Required
Test 1 的成功行由 `_probe_destination_sample`（`:2192-2202`）内联构造且不带该键，故
`assertIsNone(items[2].get("nextAction"))` 空洞通过。若该行漂移，`multiple_destination_storages` 页面上每个
成功解析的样本都会显示失败恢复动作，正是本 Slice 要消除的误配。缺陷源于我自己 Task 的措辞而非实现偏离；
判定沿用 Phase 22.6-H 的同类先例。非阻塞观察（不得升格为 blocker）：`_probe_destination_sample` 的行省略该
键而非显式 `None`、探针还原用了反向 patch 而非规定的 `git checkout --`、新列标签只由一条精确表头钉住、
22.6-H-F1 与 22.6-I 的残留证明缺口未变。下一合法 Slice 是 **Phase 22.6-L-F1**（仅证据修正：在既有
`test_multiple_destination_storages_is_bounded_failure` 内补两条下标断言，生产树与 `74919a3` 逐字节一致，
不得新增测试、不得改文档、不得开始任何新功能），已写入 `TASK.md`。Phase 22.6-L 未关闭，Phase 22.6 保持开放，
被拒 checkpoint `74919a3` 保留不得 amend/squash/改写；本轮 checkpoint 与审核记录均未推送；移出 Phase 22.6 的
六项能力维持后置。

2026-08-29 独立审核 Phase 22.6-L-F1 checkpoint `b198c9662595c3e9c92d70602170561867763c10` 判定 **PASS**，
Phase 22.6-L 由此经其 F1 修正 **PASS / CLOSED**。scope 精确：只改
`tests/test_configuration_destination_precheck.py`（+2/-0）与 `TASK.md`；`74919a3` 相对的生产树
（`mediaflow scripts config pyproject.toml`）为空，实现角色自身窗口（`cf99c6b` 起，含 `docs`）亦为空，
另两个测试模块逐字节未改，无测试新增/改名/删除，marker 仍 10 / 22。被要求的两条直接下标断言逐字落在
`test_multiple_destination_storages_is_bounded_failure` 的 `projectedOutcome` 断言之后，而该运行的两行都出自
`_destination_sample_resolution_row`。我重跑九项探针（逐次一处改动、`git checkout --` 还原、核对干净树）：
默认失败句子替换让命名测试 FAIL（即 `74919a3` 上静默通过的那处变异，阻塞缺陷闭合）、删键让同一测试
`KeyError: 'nextAction'`（证明下标而非 `.get`）、失败行 map 查表改 `None` 让 22.6-L 的 Required Test 1 仍 FAIL
（未挤掉既有证明）、comment-only control 21 项全绿，另 `""`、`False` 与调用点改建失败行三项亦被捕获。
闸门全绿：回归 871 `OK (skipped=7)`、聚焦 57、ruff/format/compileall/`pip check`/两份示例配置/wheel 隔离
smoke 退出 0 且 `Schema: 22`/`git diff --check`/FFmpeg 与业务层写操作审计/alist ignore/Markdown 0 断链/
机密扫描。非阻塞观察：Closure Checklist 两个 `[x]` 因我自己 Task 把 identity 命令锚在 `74919a3`（其间我的
审核记录动过 `docs`）而字面为假，报告已如实披露并给出正确的 BASE 相对与仅生产等价命令；`_probe_destination_sample`
（`:2201`）与单样本完成行（`:1768-1780`）仍完全省略 `nextAction`，下标取值可 `KeyError`，CURRENT 文档说法略微
超前；`_destination_sample_resolution_row` 的 `"message": None` 同样无任何测试证明；22.6-H-F1 与 22.6-I 的
残留证明缺口未变。下一合法 Slice 是 **Phase 22.6-M**（统一逐样本目标行形状并加以证明：`configuration_objects.py`
两处内联行各加一行 `"nextAction": None`、零删除，一项跨分支形状测试钉住同序十键，并为 resolution 行其余恒
`None` 键补直接下标证明；仍只读、零变更、不改 run 级聚合、门禁、route、权限与 marker），已写入 `TASK.md`。
Phase 22.6 保持开放，被拒 `74919a3` 与其记录保留；本轮 checkpoint 与审核记录均未推送；移出 Phase 22.6 的
六项能力维持后置。

本次 Product/UX Rebaseline 明确：内部模块完成不等于
最终产品完成，后续按 `docs/product-experience.md` 的纵向用户旅程验收。

```text
Runtime Configuration
→ ResourceLibrary Scan
→ Parser
→ Recognition
→ Metadata / CandidateMatcher
→ Naming
→ Classification
→ MediaLibrary Resolution
→ OrganizePlan
→ OrganizerExecutor
→ Execution History
```

当前可通过 CLI 扫描配置中的资源库、预览确定性计划，并在显式 `--execute` 时执行。
计划携带源/目标 Storage 身份，可处理 Local、SMB、OpenList、S3-compatible 的同存储与
跨存储组合。默认不覆盖、不静默删除，DryRun 零变更。隔离 Local/Samba/OpenList/MinIO 已完成
生命周期、传输、128 文件、128 MiB 流式对象和中断恢复 profile。该节点定义为“核心执行链与
有界发布硬门完成”，而不是“完整产品完成”。

## 能力矩阵

| 领域 | 状态 | 当前能力 | 主要缺口 |
|---|---|---|---|
| Storage | 已完成（有界验收） | Local、SMB、OpenList、S3/R2 Adapter、JSON Runtime、隔离 Samba/OpenList/MinIO 矩阵 | AWS/R2、第三方 driver、远端原子与多小时专项验收 |
| Scanner/FileIndex | 已完成 | 扫描、稳定性、全量/增量、生产 SQLite FileIndex | 后续管理/清理工具 |
| Parser | 已完成 | 文件名/路径/NFO、电影/剧集、多集、标签、受限 XML 与冲突证据合并 | NFO 生成不属于 Parser；更多格式按样本扩展 |
| Recognition | 已完成当前配置旅程 | 引擎、Web 规则配置、优先级/引用校验、持久 Strategy Test 解释/恢复、C 身份保持、人工决策和重评请求 | 后续按真实样本扩展，不作为当前 blocker |
| Metadata | 部分完成（引擎成熟） | TMDB、缓存、候选评分、本地化标题、年份语义、持久人工候选/查询修正 | Provider 切换、配置激活、同页恢复闭环 |
| Naming | Phase 22.6-A/22.6-D PASS / CLOSED；22.6-E PASS / CLOSED（经 22.6-E-F1 修正接受，被拒 checkpoint 保留）；22.6-F 至 22.6-K 均 PASS / CLOSED（22.6-G 与 22.6-H 各经其 F1 修正接受，被拒 checkpoint 保留） | 安全模板、Unicode、多集、Managed Draft 编辑、引用影响、exact-revision 离线预览（含可证伪 Web 挂载回归），以及与 Planner 同源的组合目标贡献归属 | 组合目标已可只读预检（22.6-E PASS / CLOSED，仅 Local）；combined activation evidence 已落地：checked activation 要求当前目标预检证据（22.6-F PASS / CLOSED，仅 Local）；22.6-G PASS / CLOSED（经 22.6-G-F1 修正接受，被拒 checkpoint `b9cc35e2677a35920042b5695f87b50a80025ef0` 保留）；22.6-L PASS / CLOSED（经 22.6-L-F1 证据修正接受，`b198c9662595c3e9c92d70602170561867763c10`；被拒 checkpoint `74919a33ac5ec9cde5b104a591ef3fdfb25a1bf3` 与其记录保留）；下一 Slice 为 Phase 22.6-M（统一逐样本目标行形状并加以证明：两处内联行各加 `"nextAction": None`、跨分支形状测试、resolution 行其余恒 `None` 键补下标证明） |
| Classification | Phase 22.6-B/22.6-D PASS / CLOSED；22.6-E PASS / CLOSED（经 22.6-E-F1 修正接受，被拒 checkpoint 保留）；22.6-F 至 22.6-K 均 PASS / CLOSED（22.6-G 与 22.6-H 各经其 F1 修正接受，被拒 checkpoint 保留） | 确定性规则、媒体库选择、持久人工规则选择/恢复、Managed Draft CRUD、引用阻断、exact-revision 离线分类预览（含可证伪 Web 挂载回归），以及 MediaLibrary/relativePath 在组合目标中的归属 | 自由路径修正明确禁止；目标存在性/冲突/能力预检已在 22.6-E 实现（PASS / CLOSED，仅 Local）；combined activation evidence 已落地：checked activation 要求当前目标预检证据（22.6-F PASS / CLOSED，仅 Local）；22.6-G PASS / CLOSED（经 22.6-G-F1 修正接受，被拒 checkpoint `b9cc35e2677a35920042b5695f87b50a80025ef0` 保留）；22.6-L PASS / CLOSED（经 22.6-L-F1 证据修正接受，`b198c9662595c3e9c92d70602170561867763c10`；被拒 checkpoint `74919a33ac5ec9cde5b104a591ef3fdfb25a1bf3` 与其记录保留）；下一 Slice 为 Phase 22.6-M（统一逐样本目标行形状并加以证明：两处内联行各加 `"nextAction": None`、跨分支形状测试、resolution 行其余恒 `None` 键补下标证明） |
| Organize | Phase 22.6-C/22.6-D PASS / CLOSED（配置、授权解释与组合目标预览）；22.6-E PASS / CLOSED（经 22.6-E-F1 修正接受，被拒 checkpoint 保留）；22.6-F 至 22.6-K 均 PASS / CLOSED（22.6-G 与 22.6-H 各经其 F1 修正接受，被拒 checkpoint 保留） | managed OrganizePolicy CRUD、引用阻断、仅 Move/Copy/HardLink/SoftLink 的编辑限制、exact-revision 零副作用组织授权解释（所需 Storage 能力声明而非探测、显式无回退、破坏性告警），以及与 Planner 同源的 Storage-relative 组合目标预览 | 远端目标预检与写入式能力探测待做；combined activation evidence 已落地：checked activation 要求当前目标预检证据（22.6-F PASS / CLOSED，仅 Local）；22.6-G PASS / CLOSED（经 22.6-G-F1 修正接受，被拒 checkpoint `b9cc35e2677a35920042b5695f87b50a80025ef0` 保留）；22.6-L PASS / CLOSED（经 22.6-L-F1 证据修正接受，`b198c9662595c3e9c92d70602170561867763c10`；被拒 checkpoint `74919a33ac5ec9cde5b104a591ef3fdfb25a1bf3` 与其记录保留）；下一 Slice 为 Phase 22.6-M（统一逐样本目标行形状并加以证明：两处内联行各加 `"nextAction": None`、跨分支形状测试、resolution 行其余恒 `None` 键补下标证明） |
| Planner/Executor | 部分完成 | 计划、冲突、附件、Hash 证据、同次调用 Rollback、空目录清理、DryRun、跨存储执行 | 历史/崩溃恢复、Hash 持久复用、逐项恢复体验 |
| Task/History | 部分完成 | 持久 Task/Item/Result/Job、Worker、取消、pause/resume、批量请求、claim fencing/心跳 | 统一 Processing Checkpoint 与 stage-aware recovery |
| API/UI/Scheduler | 部分完成 | API/RBAC/审计、操作台、Dashboard、Files 列表/筛选/详情/部分动作、Cron/通知 | 完整人工/配置/恢复旅程、登录/外部身份源 |
| Managed Configuration | Phase 22.3/22.4/22.5 与 Phase 22.6-A/22.6-B/22.6-C/22.6-D 均 PASS / CLOSED；22.6-E PASS / CLOSED（经 22.6-E-F1 修正接受，被拒 checkpoint 保留）；22.6-F 至 22.6-K 均 PASS / CLOSED（22.6-G 与 22.6-H 各经其 F1 修正接受，被拒 checkpoint 保留） | 既有能力加 NamingPolicy、ClassificationPolicy 与 OrganizePolicy CRUD、引用阻断、exact-revision 离线命名/分类/组织授权与 Storage-relative 组合目标预览，以及仅 Local 目标的只读目标预检（configuration marker 10） | combined activation evidence 已落地：checked activation 要求当前目标预检证据（22.6-F PASS / CLOSED，仅 Local）；22.6-G PASS / CLOSED（经 22.6-G-F1 修正接受，被拒 checkpoint `b9cc35e2677a35920042b5695f87b50a80025ef0` 保留）；22.6-L PASS / CLOSED（经 22.6-L-F1 证据修正接受，`b198c9662595c3e9c92d70602170561867763c10`；被拒 checkpoint `74919a33ac5ec9cde5b104a591ef3fdfb25a1bf3` 与其记录保留）；下一 Slice 为 Phase 22.6-M（统一逐样本目标行形状并加以证明：两处内联行各加 `"nextAction": None`、跨分支形状测试、resolution 行其余恒 `None` 键补下标证明）；远端目标预检、写入式能力探测、Provider switching、通用 Task resume 后置 |

## 总体阶段计划

### Phase 14：持久化与可恢复任务基础（已完成）

- 将 CLI Scanner 从 InMemoryFileIndexRepository 切换到配置化 SQLite FileIndex。
- 定义持久 Task、TaskItem、ResultRecord 仓储和数据库版本迁移。
- 保存每个阶段状态、错误、计划 ID、重试次数和时间信息。
- 实现同一 `StorageID + Path` 的任务互斥。
- 支持取消、恢复中断任务、仅重试失败项；重启后不得重复成功的变更操作。
- 保持 Scanner/Parser/Recognition/Metadata/Naming/Classification/Planner 零变更边界。

验收结果：生产 CLI 已接入持久 FileIndex；Task/TaskItem/Result/Lock 使用版本化 SQLite；
显式 resume/retry 排除成功终态并重新要求执行授权；DryRun 仍零 mutation。

### Phase 15：冲突与人工确认（已完成）

- 完整实现 Skip、Rename、Manual；Overwrite 仅在显式高风险策略和确认后允许。
- 建立目标冲突 NeedConfirm 队列；元数据候选和分类人工选择留给后续交互层。
- 加入 Provider ID、媒体类型和季集范围的重复检测身份；Hash 读取仍保持关闭。
- 不把冲突解决逻辑放入 Naming、Classification 或 Storage Adapter。

验收范围：目标冲突的 Skip/Rename/Manual/Overwrite 决策、SQLite NeedConfirm 与审计、显式
高风险覆盖授权和剧集范围重复身份已经实现。元数据候选与分类人工选择留给后续交互层。

### Phase 16：附件与媒体集合（已完成）

- 字幕、NFO、Poster、Fanart、Trailer 和同名附件发现。
- 主文件与附件形成一个原子计划集合，保留字幕语言/Forced/SDH 后缀。
- 部分失败必须可恢复，不删除未知文件，默认不清理源目录。

验收范围：附件策略默认关闭；启用后通过 Storage 只读发现同目录关联文件，生成安全的文件
集合计划并由 OrganizerExecutor 统一执行。部分结果保存已完成步骤，不清理未知文件。

### Phase 17：运行时适配器与运维完善（已完成）

- 为 SMB、S3/R2 增加环境变量持有密钥的 JSON Runtime 配置构造。
- 增加连接测试、只读验证、能力预检和专用实机验收套件。
- 配置导入导出、版本迁移、日志轮转和缓存维护。

验收范围：SMB/S3/R2 JSON Runtime 装配、环境变量密钥、配置校验和只读 Storage 预检已
完成。持久缓存管理和文件日志轮转将在相应持久后端引入时实现，不提供空操作命令。

### Phase 18：服务化与自动化（已完成当前范围）

- REST API、Task Worker、Scheduler、Cron、Webhook 和通知。
- API 复用 Application Service，不复制策略引擎或绕过 OrganizerExecutor。
- 先提供只读查询和 DryRun API，再开放受保护的执行 API。

Phase 18.1 已完成持久 scan/preview 队列、单作业原子领取 Worker、只读 Task/Job/
Confirmation REST 查询，以及只允许 DryRun 工作的受鉴权提交接口。远程真实执行未开放。

Phase 18.2 已完成常驻 Worker、跨扫描/批处理边界的协作取消、显式陈旧作业恢复和持久
interval 调度。调度仅允许 scan/preview；Cron 日历表达式与远程真实执行仍未开放。

Phase 18.3 已完成五字段 Cron、IANA 时区、DST 确定性语义和不可变调度发出审计。Cron 与
interval 都只允许 scan/preview；远程真实执行仍未开放。

Phase 18.4 已完成持久通知 Outbox、HMAC 签名 Webhook、受限重试/死信、独立投递 Worker
和只读通知查询。通知失败不改变作业终态，也不触发任何 Storage 或媒体操作。

Phase 18.4.1 已完成通知投递租约与进程崩溃后的过期领取恢复；稳定 Delivery ID 支持接收端
在 at-least-once 语义下去重，自动恢复不会重置尝试次数。

Phase 18.5 已完成默认关闭的本机一次性远程执行票据、摘要持久化、原子消费/Job 创建和审计。
普通 API Token 不能单独授权变更，Scheduler 仍禁止 organize。

Phase 18.6 已完成配置化 API Principal、最小权限角色、401/403 路由授权和 SQLite v9 脱敏
安全审计。Executor 角色仍必须另外消费 Phase 18.5 一次性票据。

Phase 18.7 已完成面向 CLI/API/未来 Web UI 的只读运营 Dashboard Read Model；通过 SQLite
聚合 FileIndex、Task、Job、待确认和通知状态，不访问 Storage 或网络，也不暴露原始错误路径。

Phase 18.8 已完成受 RBAC 保护的冲突确认列表/详情/审计和 Skip/Rename 决策 API。确认、审计
与 TaskItem 转换原子提交；远程 Overwrite 和自动重试/执行仍被禁止。

Phase 18.9 已完成持久元数据复核队列：NeedConfirm/Ambiguous 候选以受限、Provider-neutral
快照持久化，TaskItem 原子进入 `waiting_metadata` 并释放源锁；CLI/API/Dashboard 只提供
脱敏可见性，不选择候选、不访问 Provider、不自动恢复或执行。

Phase 18.10 已完成显式元数据候选选择与恢复接线：仅允许选择持久快照 rank，决策/审计/
TaskItem 状态原子提交；选择本身零网络、零 Storage、零 Job，只有后续显式 `tasks resume`
才校验策略并通过现有 Provider-ID 详情流程继续处理。

Phase 18.11 已完成分类复核队列与显式配置规则选择：未分类项目持久保存当前策略的启用规则
选择，决策/审计/TaskItem 原子提交；不允许任意媒体库或路径，显式 resume 会重新校验当前
规则后才进入 Planner。

### Phase 19：最小安全操作台与生产发布硬门（已完成有界范围）

- Dashboard、Storage/Library/Policy 管理、候选确认、冲突处理、任务和历史页面。
- 权限、审计、备份恢复、升级指南、可观测性和发布流水线。
- 完成跨平台、长时间批处理、故障注入和真实存储矩阵验收。

Phase 19.1 已实现最小安全操作台：同一 WSGI 进程提供无依赖 Dashboard 和三类复核界面，
Token 仅存于页面内存，受控决策继续通过现有 RBAC/审计 API。任务控制、真实执行、Overwrite、
配置编辑、用户数据库/OIDC 和 TLS 发布仍未开放。

Phase 19.2 已实现 API 凭证生命周期与 HTTP 部署护栏：提供系统随机 Token 生成和脱敏环境
状态检查，记录双 Principal 手工轮换流程；开发服务器默认只允许回环监听，非回环明文 HTTP
必须显式危险确认。TLS 终止、OIDC 与 Secret Store 仍不在应用内实现。

Phase 19.3 已实现 Task/Job/Result 只读操作台：列表和 TaskItem/Result 详情均受 1–100 上限
约束，SQLite 使用 limit+1 判断截断；UI 不提供提交、取消、恢复、重试、授权或执行操作。

Phase 19.4 已消除大型历史只能查看首页的风险；Phase 19.5 进一步为 Task/Job 与
TaskItem/Result 提供稳定复合键双向 keyset 游标，不使用 OFFSET。操作台提供显式
Previous/Next，仍无任意页跳转、总数扫描或任何任务控制权限。

Phase 19.6 已补齐 Scheduler 与 Notification 的只读运维可见性：调度定义/状态、限定条数的
发生审计，以及按状态过滤的限定条数投递记录均进入现有安全操作台。Webhook 地址/正文/
签名和原始异常不暴露，也没有 tick、编辑、投递或重排控制。

Phase 19.7 已将相同的双向稳定 keyset 游标扩展到通知投递与单个调度发生审计。通知游标
绑定状态过滤器，调度游标绑定调度 ID，跨 scope 复用会失败；不使用 OFFSET 或总数扫描。

Phase 19.8 已建立默认关闭的结构化脱敏运行日志：SQLite v13 仅保存固定事件和安全标识，
提供本地有界查询及显式年龄/条数保留清理，不保存路径、原始错误或任意上下文。

Phase 19.9 已为同一安全日志模型加入只读 API/Web 双向 keyset 浏览，游标绑定最低级别
过滤器；Web 不提供 prune、全文搜索、实时 tail 或任何工作流控制。

Phase 19.10 已实现 SQLite Runtime 在线一致性备份和只读校验：目标必须是新的本地文件，
完整性/Schema 校验通过后原子发布，绝不覆盖；破坏性的 Restore 仍明确不提供。

Phase 19.11 已建立可复现发布验证基线：Python 3.11–3.13 只读 CI 重复执行离线质量门，独立
wheel 作业检查包内容并在仓库外的新虚拟环境验证 CLI、示例配置和数据库备份。流水线不持有
生产密钥、不访问真实媒体存储，也不自动发布或部署。

Phase 19.12 已加入只读升级预检：对配置 Runtime 数据库与操作员显式提供的新备份复用相同
完整性/Schema 校验，报告 Python/应用/Schema 兼容性、迁移需求和备份时效。预检不打开可迁移
Repository、不访问媒体 Storage，也不执行升级、恢复或替换。

Phase 19.13 已加入非覆盖式离线恢复：已验证本地备份只能原子创建到完全空缺的配置 Runtime
路径；现有数据库、目录、符号链接和 SQLite sidecar 一律拒绝。系统不移动/删除旧库、不检测
进程存活，停机和旧数据保留仍是明确的人工步骤。

Phase 19.14 已加入 POSIX 协作式 Runtime 维护锁：普通生产命令持共享锁，确认恢复在服务调用
前必须取得独占锁，冲突立即失败且崩溃由内核释放。稳定空锁文件不删除；该机制不覆盖绕过
生产 CLI 的程序、分布式主机或尚未实现等价独占语义的平台。

Phase 19.15 已加入隔离式 Schema 迁移演练：显式备份被复制到私有临时 SQLite，只有副本通过
真实 Repository 前向迁移，再验证当前 Schema 和 Task/Result/审计/日志计数后清理。配置
Runtime 与备份不改变；生产迁移、自动回滚和服务编排仍未实现。

Phase 19.16 已加入只读系统与配置状态：生产 API 启动时从已验证的归一化配置生成有界不可变
快照，Web System 页只显示兼容性以及 Storage/Library/Policy 安全接线。路径、规则值、模板、
分类目录、端点、环境变量和凭证结构性排除；没有编辑、连通性检查、轮询或工作流控制。

Phase 19.17 已将既有 Automation Job 协作取消安全接入操作台：Pending/Running 详情需要请求
与确认两步，Operator/Executor/Admin 继续由 `cancel_job` RBAC 和审计约束。取消不提交新 Job、
不控制 Task、不授予执行权限、不回滚已完成操作，也不构造任何媒体或 Storage 服务。

Phase 19.18 已将既有 scan/preview DryRun Job 提交接入操作台：表单、审核、确认三步生成仅含
command/可选有界 limit 的请求，Operator/Executor/Admin 仍由 `submit_dry_run` 权限约束。
入队不构造工作流或 Storage，UI 不提供 organize、execute、Scheduler 或 Task 控制。

Phase 19.19 已加入持久活动 Job 准入：配置化上限原子约束 Pending+Running，手工 DryRun、
Scheduler 和受保护 organize 共用容量。满队列不创建 Job、不推进调度状态/审计、不消费一次性
票据，也不清理现有队列；API 返回受审计的 409，System 页只显示配置上限。

Phase 19.20 已加入陈旧 Running Job 的只读运维可见性：统一配置年龄阈值，SQLite 稳定有界
查询，认证 API 与显式加载 UI 只显示安全状态字段。真实执行授权 Job 会被标记为仅人工恢复；
系统不推断 Worker 死亡，也不提供自动重排、强制取消、重试或执行操作。

Phase 19.21 已加入 Automation Job claim fencing 与协作心跳：每次领取生成新的不透明随机 token，
心跳和终态按 Running+token 原子校验，重排清除旧 token。旧 Worker 无法覆盖新 claim 或发布其终态
通知；token 不进入 API/UI/CLI/日志。阻塞中的外部调用仍无后台心跳，也不提供自动恢复。

Phase 19 总体验收仍为 BLOCKED：此前子阶段 PASS 只代表各自范围通过，不代表真实 SMB/OpenList/
S3-R2、跨存储矩阵、长时间批处理与故障注入完成。Phase 19.22 开始纠偏，先建立权威矩阵并完成
LocalStorage 原子目标发布及跨存储 MOVE 大小不一致保源回归。

Phase 19.23 的隔离 OpenList 验收工具与四重破坏性门禁已实现，但当前环境未提供专用 URL、Token、
`mediaflow-acceptance-*` 空测试根和确认值，因此实机矩阵状态为 BLOCKED/NOT RUN。不得因工具和
fake 回归通过而推进 Phase 19.24；应先提供隔离环境并执行、留存 19.23 证据。

Phase 19.23.1 补齐验收工具自身的空根只读证明和原子非覆盖 JSON 证据记录：真实运行还必须显式
指定新报告文件，预检非空/不可读/非目录时零远端 mutation。当前仍未提供五项专用前提，因此
结果继续为 BLOCKED/NOT RUN；这不是推进 Phase 19.24 的依据。

Phase 19.23.2 已获授权自建回环隔离 OpenList v4.2.2 并实际执行。真实空目录响应使用
`content: null`，现有生产 HTTP mapper 只接受数组，空根预检以 `io_error` 失败；任何 mutation
前即停止，容器与临时秘密均已销毁。19.23 状态由 BLOCKED 转为 FAIL，下一任务必须单独修复该
DTO 兼容性并重跑完整矩阵，仍禁止推进 Phase 19.24。

Phase 19.23.3 已严格兼容 `content: null, total: 0` 并拒绝不一致组合；重新部署官方 v4.2.2 后，
OpenList 生命周期、Local↔OpenList、OpenList↔OpenList COPY/MOVE、内容/大小/源状态和白名单清理
全部实机通过。自建 Local driver 范围记为 ISOLATED PASS，不代表第三方云盘驱动或远端原子发布
认证。OpenList 硬门已关闭，下一任务可进入 Phase 19.24 的隔离 Samba 与 MinIO/S3-R2 矩阵。

Phase 19.24 已部署回环隔离 Samba 4.20.6 与 MinIO RELEASE.2025-07-23。MinIO 完整矩阵及清理
ISOLATED PASS；Samba 在真实 EEXIST 错误映射阶段失败并且适配器清理未完成，传输行按 fail-fast
未执行。Phase 19.24 当前 FAIL，下一任务只能单独修复 SMB EEXIST/清理语义并完整重跑 Samba，
不得提前进入 Phase 19.25。

Phase 19.24.1 已按结构化 errno 修复 Samba `EEXIST` 等错误分类，并消除目录枚举在非默认端口上
隐式回退 445 的二次 stat。新空根完整通过生命周期、Local↔SMB、SMB↔SMB、内容/源状态验证和
白名单清理。结合 19.24 的 MinIO PASS，Phase 19.24 在自建 Samba 与通用 S3-compatible MinIO
范围内关闭；AWS/R2 服务特性与远端原子发布仍未认证。下一任务进入 Phase 19.25 长时间批处理、
大文件、中断恢复与一致性验证，Phase 19 总体仍为 BLOCKED。

Phase 19.25 已用生产 Adapter 与 OrganizerExecutor 在全新隔离 Local、Samba、OpenList 和 MinIO
上完成统一的 128 文件批次、128 MiB 流式对象、确定性源流中断、MOVE 保源、目标状态检查、显式
重试和白名单清理。四个 profile 均 ISOLATED PASS，MinIO 无遗留 multipart；SMB 暴露的部分目标
被明确识别且未被当作成功。Phase 19 的可复现有界发布硬门关闭，整体记为 PASS。多小时 soak、
进程/主机断电、AWS/R2 服务特性和远端原子发布仍是部署专项限制，不作已认证声明。下一阶段按
计划进入 Phase 20 核心引擎收口，不继续扩展 Phase 19 操作台。

## 规格差距评估（2026-08-24，基于 Phase 22.2R 与 Product/UX Rebaseline）

对照《影视媒体资源自动整理系统需求规格说明书》V1.1 全量章节逐项评估：

| 领域 | 当前状态 | 主要剩余缺口 |
|---|---|---|
| 核心引擎（§1–§79） | 引擎成熟、产品闭环部分完成 | 历史/崩溃恢复、Hash 持久复用、Provider 切换与完整人工整理旅程 |
| 存储层（§4–§10） | 有界发布矩阵 PASS | AWS/R2、第三方 driver、远端原子发布、Range Read/大对象服务端 Copy 仍未认证或未实现 |
| 任务与自动化（§62–§70、§98） | 持久基础成熟、恢复体验不完整 | 统一 Processing Checkpoint、stage-aware 逐项恢复、定时缓存/日志清理 |
| API 与 Web UI（§93–§96、§102） | 有界操作台/文件视图/部分动作已实现；配置快照恢复管理已接入 | 决策→继续→结果/逐项恢复闭环、对象级配置管理、手工整理和 Provider 切换 |
| 配置管理（§5、§86–§89） | Phase 22.2/22.2R whole-document Draft/Validated/Active 及恢复安全边界 | 对象级 Storage/Library/Policy CRUD、依赖影响、连通性测试、Secret Store、完整首次设置旅程 |
| 安全与审计（§99–§101） | RBAC/脱敏/执行审计成熟 | 用户/外部身份源决策、完整配置激活审计与逐项恢复审计 |

从本次重基线开始，不再用“模块百分比”作为产品完成度。MediaFlow 的核心媒体引擎接近完整，
但最终 V1 仍缺少配置、恢复和人工处理的完整 Web 用户旅程；内部仓储或命令通过不能提高这些
旅程的完成状态。

## 历史阶段完成状态

### 阶段 I：发布硬门（Phase 19.23–19.25，已完成有界范围）

本阶段已由 Phase 19.25 关闭；历史执行期间 Phase 19 整体不得提前 PASS，且暂停了一切操作台
横向增强、OIDC 和高级调度。

- Phase 19.23：隔离真实 OpenList 验收矩阵 + Local↔OpenList / OpenList↔OpenList
  故障注入（roadmap 现行第 1 条）。
- Phase 19.24：隔离真实 SMB 与 S3/R2 验收矩阵，形成可复现验收报告
  （roadmap 现行第 2 条）。
- Phase 19.25：长时间批处理、大文件、中断恢复与一致性验证
  （roadmap 现行第 3 条）。
- 验收证据规则沿用 docs/storage-acceptance.md：fake/mock 只计 UNIT PASS，
  真实隔离环境才计 ISOLATED PASS；远端破坏性验收必须专用凭证 + 空测试根 +
  显式操作员确认。

### 阶段 II：核心引擎收口（Phase 20.x，已完成有界范围）

- Phase 20.1 NFO Parser 已完成：Storage-only 有界读取、安全 XML、确定性证据合并和生产管线接入。
- Phase 20.2 Hash 重复检测已完成：不计算/快速/完整，默认不计算；证据只读且失败闭合。
- 有界整理 Rollback 已完成：只补偿同次调用记录且再次验证的效果，不触碰未知文件；历史/崩溃恢复不在该边界（§49、§69）。
- 任务暂停/继续语义（§66）与只读工作流有界自动重试（§79）已完成；变更操作和不确定结果明确不自动重试。
- Phase 20.6 空目录清理已完成：默认关闭、成功 MOVE 后、ResourceLibrary 根排他边界、未知内容失败闭合。
- 完成后可发布 CLI/API 完整版 v1.0。

### 阶段 III：人工处理基础（Phase 21.x，已完成有界范围）

- Phase 21.0 已完成：Unrecognized 条目持久等待、启用类型有界快照、显式 RecognitionType
  决策审计和 resume；无隐藏默认、不修改规则，C 身份保持。
- Phase 21.1 已完成：Metadata NOT_FOUND 条目持久等待，支持关键词、年份、Movie/TV、
  配置 Provider 的直接 ID 修正，保持决策审计 + 显式 resume 和 C 身份。
- Phase 21.2 已完成：Recognition/Metadata 人工等待项支持显式、持久、可审计的单项忽略；
  ignored 不计成功且不触碰媒体、索引、规则或未来扫描。
- Phase 21.3 已完成：Unrecognized 等待项可在外部规则更新后显式请求重新识别，再由独立
  Task resume 使用当前配置重跑真实引擎；无隐藏默认或规则写入。
- Phase 21.4 已完成：有界、可审计、可选的 Task 范围批量请求重新识别；pending Recognition
  Review 与匹配 WAITING_RECOGNITION 项在同一事务中最先到期优先处理，仍由独立 Task resume
  使用当前配置重跑真实引擎；无隐藏默认或规则写入。
- Phase 21.5 已完成：有界、可审计、可选的 Task 范围批量忽略；Recognition、Metadata 候选和
  Metadata NOT_FOUND 修正等待项在同一事务中最先到期优先标记为 IGNORED，仍不触碰媒体、索引、
  规则或未来扫描。
- Phase 21.6 已完成：有界、可审计、可选的 Task 范围批量人工 RecognitionType 决策；pending
  RecognitionReview 与匹配 WAITING_RECOGNITION 项在同一事务中最先到期优先以同一启用类型
  RESOLVED，仍由显式 resume 消费持久 selection；无隐藏默认、不修改规则，C 身份保持。
- Phase 21.7 已完成：有界、可审计、可选的 Task 范围批量 Metadata NOT_FOUND 修正；pending
  MetadataCorrectionReview 与匹配 WAITING_METADATA_CORRECTION 项在同一事务中最先到期优先以
  同一合法 query/year/movie-TV/provider-ID 输入 RESOLVED，仍由显式 resume 消费持久 correction；
  C 身份保持。
- Phase 21.8 已完成：有界、可审计、可选的 Task 范围批量 Metadata 候选选择；pending
  MetadataReview 与匹配 WAITING_METADATA 项在同一事务中最先到期优先以同一持久候选 rank
  RESOLVED，仍由显式 resume 消费持久 MetadataSelection；C 身份保持。
- Phase 21.9 已完成：有界只读 FileIndex 文件目录 CLI；可按 ResourceLibrary、Storage、
  scan status 与 path/filename 查询，稳定排序并显示单项索引记录；不构造 Storage/Provider/
  工作流，也不读取文件内容。
- Phase 21.10 已完成：同一文件目录支持稳定 keyset cursor 分页；`--after/--before` 配合
  `--cursor-file-id` 使用既有 `(updated_at DESC, file_id DESC)` 顺序，不使用 OFFSET。
- Phase 21.11 已完成：`files show` 为索引文件追加最新持久 Task Result 详情；缺失结果显式
  显示为空，不伪造历史，也不构造 Storage/Provider/工作流。
- Phase 21.12 已完成：`files list` 增加 RecognitionType、Provider、Provider ID、Title、
  Task ID 与 Year 的派生过滤；基于同一 source Storage/path 的最新 Task Result，且仍为只读
  有界 FileIndex 查询。
- Phase 21.13 已完成：FileIndex 文件目录基础过滤、cursor 和 limit 下沉到参数化仓储查询；
  应用层只保留最新 Task Result 派生过滤。
- Phase 21.14 已完成：最新 Task Result 派生过滤也已下沉为 FileIndex 与 TaskResult 的
  参数化 join，SQLite 路径不再逐文件查询最新结果。
- Phase 21.15 已完成：有界批量失败项重试请求；FAILED/PARTIAL TaskItem 可在同一事务中原子
  回到 PENDING，并由显式 `tasks resume` 执行真正的重试。
- Phase 21.16 已完成：`files stats` 提供有界只读 FileIndex 状态统计，可按 ResourceLibrary
  与 Storage 过滤；不构造 Storage/Provider/工作流。
- Phase 21.17 已完成：文件目录只读 Web UI；认证 API 提供 list/detail/stats，操作台 Files
  视图支持有界列表与详情查看，不提供写入或执行操作。
- Phase 21.18 已完成：Files 视图增加只读搜索/筛选控件，可组合 ResourceLibrary、Storage、
  scan status、path/filename、Recognition/Provider/Title/Task/Year 过滤。
- Phase 21.19 已完成：显式 `batch preview` / `batch organize` 命令复用无路径全
  ResourceLibrary 管线，明确批量 DryRun/整理入口。
- Phase 21.20 已完成：`files show`/Web 详情返回同一 source Storage/path 的关联
  Recognition/Metadata review 链接，操作员可跳转到对应 Task/复核队列；只读不修改。
- Phase 21.21 已完成：`files re-recognize` 为存在 pending RecognitionReview 的文件发起
  重新识别请求；真正重评仍由 `tasks resume` 执行。
- Phase 21.22 已完成：`files re-match` 为存在 pending MetadataCorrectionReview 的文件执行
  有界 Metadata 修正/重新匹配；真正 Provider 查找仍由 `tasks resume` 执行。
- Phase 21.23 已完成：`files re-plan` 为最新 FAILED/PARTIAL 结果的文件发起单项重试请求，
  原子返回 PENDING；真正重新规划/整理仍由 `tasks resume` 执行。
- Phase 21.24 已完成：Phase 21 收口 smoke test 与文档一致性核对；CLI/UI 只读边界和
  禁止依赖审计保持通过。
- Phase 21.25 已完成：Files 详情 Web UI/API 增加 re-recognize 与 re-plan 请求入口；仅在
  对应 pending review 或 FAILED/PARTIAL 状态显示，实际执行仍需显式 Task resume。
- Phase 21.26 已完成：补齐 file re-match 的 Web UI/API；Phase 21 已按当前有界范围收尾，
  下一阶段进入 Phase 22 配置管理系统。
- Phase 22.0 已完成：配置管理架构决策与领域骨架；JSON 作为运行时输入、SQLite 作为变更/
  审计存储、凭证保持环境或 Secret Store 归属，12+ 配置对象分类与引用/审计模型已建立。
- Phase 22.1 已完成：第一批 Storage 配置内部 CRUD/校验/乐观版本/Before-After 审计与
  SQLite 引用阻断；支持六类 Storage 形状并拒绝字面/嵌套 secret。该入口尚未接入运行时
  JSON、API/UI/CLI、Storage 构造或媒体工作流。
- Phase 22.3 已完成并通过 Final Closure Audit：在 Managed Draft 中接入 Local Storage、
  ResourceLibrary、MediaLibrary 的 Web/API 编辑、完整直接引用影响/阻断、远端脱敏只读、
  host-absolute/Storage-relative 路径边界、容量和超时受限的只读 Local setup check、持久失败/
  陈旧恢复、checked activation，以及行为可辨的 Preview Job → Worker → Task/Result immutable
  snapshot pin。远端 Storage 与策略对象不属于该已关闭 scope。

Phase 21 的上述条目是可复用的持久/API/Web 基础，不代表最终人工处理用户旅程已经完成。

## Product/UX 纵向实施路线（当前有效）

后续不再采用“先完成所有 Domain/Repository，再统一补 API/UI”的横向排期。一个配置切片在
适用时应包含：

```text
Domain
→ persistence
→ Application
→ API
→ Web UI
→ validation / test
→ activation
→ user acceptance tests
```

每个切片都必须明确用户目标、入口、可见状态、动作、成功、失败与恢复；若只完成其中一段，
报告必须明确仍是 CURRENT 基础而不是产品完成。

### 1. 架构纠正与引擎正确性

- Phase 22.2/22.2R 已建立 whole-document Managed Configuration 的 Draft → Validate → Activate →
  immutable Runtime Snapshot 单一权威链路，并补齐缺失/损坏 Active 的管理恢复与 fail-closed
  工作边界；后续切片必须沿用该 authority。
- Web/API 显示的 Active 必须与新 Task/Job 实际固定并消费的 snapshot ID/digest 一致；在途项目
  不被静默切换。
- JSON 只保留明确的 bootstrap/import/export/migration 角色；首次激活前标记 CURRENT
  `JSON_BOOTSTRAP`，激活后不得制造两个 Active source。
- 定义 TaskItem Processing Checkpoint 与 stage-aware Recovery 的兼容契约，但恢复旅程在第 6
  个切片实现，不在架构纠正中假装完成。

### 2. Storage + Library 配置用户旅程（Phase 22.3，PASS / CLOSED）

- 已修复独立复核确认的 P1：大段编辑不得截断丢失、Local root 必须是 host-absolute、
  Web 必须展示直接引用与陈旧/失败 check 恢复证据、setup check 必须容量受限且受
  fail-fast read-only guard 保护，并补齐 Active → Job → Worker Task/Result 同 pin 验收。
- 2026-08-25 phase-level Final Closure Audit 未发现组合 scope 内 P0/P1；远端 Storage 连通性与
  能力测试仍是后续范围。
- 复用 Phase 22.1 基础，不把“补齐 Library repository”单独作为产品完成。

### 3. Recognition 配置 + Strategy Test 用户旅程（Phase 22.4，PASS / CLOSED）

- 规则/类型/类型策略的编辑、优先级与引用校验、真实或合成路径的零变更 Strategy Test、解释、
  激活和 C 身份回归在同一切片交付。
- 2026-08-26 独立验收确认 matched/ambiguous/unrecognized 的持久证据、Web 解释和差异化恢复，
  以及 Local check + Strategy Test 双证据激活门；当前范围无 P0/P1。

### 4. Metadata 配置与修正用户旅程（Phase 22.5，PASS / CLOSED）

- Provider/MetadataPolicy 配置、语言/地区/阈值测试、候选解释、Provider 切换、人工修正、显式
  继续与新 Preview 形成闭环；凭证仍只来自批准的 Secret 边界。
- Phase 22.5-A 已完成 MetadataPolicy Managed CRUD、引用保护、精确 revision 的离线有效策略
  展示与 stale 恢复，并于 2026-08-26 独立验收 PASS/CLOSED。Phase 22.5-B 随后完成同一
  Validated revision 的有界 live Metadata 测试、候选/失败解释及 F1 修复，并已独立验收。
  Phase 22.5-C 已完成 persisted NeedConfirm/Ambiguous 候选确认及 F1/F2 durable CAS 修复并
  通过 final Integration Acceptance。Phase 22.5-D 的同 Provider query/year/Movie-TV/direct-ID
  correction test 已通过独立 High re-review 并 PASS/CLOSED；不包含 Provider switching、
  Files/Task continuation 或真实媒体变更。Phase 22.5-E 补齐一个已解决 correction 的显式单项
  DryRun continuation：Files detail 展示 source Task/TaskItem、correction 身份、固定 snapshot
  ID/digest、`Items selected: 1`、`Authority: DRY_RUN_ONLY`、`Storage mutation: NONE`，显式
  确认后生成一项不可执行 Job，并提供 queued/running/completed/failed/stale/cancelled 状态、
  有界失败/恢复文本、关联 Job 与 DryRun Task/Result、单项重试和显式 stale requeue。其首个
  checkpoint 因 Web section 未挂载被判定 FIX REQUIRED（记录保留），F1 correction checkpoint
  `dce5c0ba53bb4fc91f18d1b5d6d56564cd3cfe62` 已于 2026-08-27 独立复审通过。
- 2026-08-27 phase-level Final Closure Audit 判定 Phase 22.5 **PASS / CLOSED**，组合 scope 内
  无 P0/P1。Provider switching、通用 Task resume 与更宽的逐项 checkpoint 恢复仍为 TARGET，
  分别不在该已关闭 scope 内。

### 5. Naming / Classification / Organize 配置用户旅程（Phase 22.6，当前边界）

- 模板、分类规则、目标 MediaLibrary 与操作策略联动编辑；显示依赖影响，使用相同引擎预览，
  验证路径安全/冲突/能力后才允许激活。
- Phase 22.6 目标：把 NamingPolicy、ClassificationPolicy、OrganizePolicy 纳入既有 Managed
  Configuration 权威链路（Draft → Validate → checked Activate → immutable Runtime Snapshot），
  并对精确 revision 提供零变更的离线预览与可操作恢复。
- Phase 22.6 边界：沿用 whole-document revision authority、乐观版本、引用影响/阻断、
  Before/After 审计与 host-absolute/Storage-relative 路径规则；预览必须消费被指定的精确
  revision 而不是当前 Active，且不构造 Provider、不访问 Storage、不产生媒体变更。
- Phase 22.6 起始 Slice 22.6-A（managed NamingPolicy CRUD + 精确 revision 离线命名预览）已
  **PASS / CLOSED**（`30af69ac82b30f8a45ad66afbd3c9747597c8fe7`）；Slice 22.6-B（managed
  ClassificationPolicy CRUD + 精确 revision 离线分类预览，含 MediaLibrary 解析解释与
  RecognitionTypePolicy 引用阻断）已 **PASS / CLOSED**
  （`5e2da5c634f1fa72a40e5f50b035260418fe1a37`）。22.6-C（managed OrganizePolicy CRUD + 精确
  revision 离线组织授权解释）、22.6-D（Storage-relative 组合目标预览）、22.6-E（仅 Local 目标的只读
  目标预检，经 22.6-E-F1 修正接受）与 22.6-F（checked activation 要求当前 Local 目标预检证据）均已
  **PASS / CLOSED**。22.6-G（Web checked-activation 控件与告警覆盖 Local setup check、
  Recognition Strategy Test 与目标预检三项要求）已 **PASS / CLOSED**
  （`5ca1247156e6de4615dff53f5fc8e421bd8bf264`，经 22.6-G-F1 修正接受；被拒 checkpoint
  `b9cc35e2677a35920042b5695f87b50a80025ef0` 与其记录保留）；22.6-H（有界多样本 Local 目标预检与跨项
  目标碰撞检测：单一 RecognitionType、最多 8 个样本、复用生产 Planner 的 `claimed_destinations` 与
  `TARGET_COLLISION`、逐项独立状态与恢复、碰撞判为 FAILED `duplicate_destination`、样本跨目标 Storage
  判为 FAILED `multiple_destination_storages`）已 **PASS / CLOSED**
  （`4455198a6ef3b93fe1e92cef73660039620e756e`，经 22.6-H-F1 证据修正接受；被拒 checkpoint
  `d8c2ae04e578955ddbbd29c413f235bf4cf08f42` 与其记录保留）；随后三个纯 Web 呈现 Slice 亦已
  **PASS / CLOSED**：22.6-I（run 级摘要与首样本分离，`6c0ba745772e315b941c1c3b314ab47e66e8f35a`）、
  22.6-J（未判定的目标观测渲染为 `NOT DETERMINED` 而非伪造的 `NO`，
  `ccbddf2af92c1abf18d1162d0a6c37da9ee0a7cd`）、22.6-K（逐样本行携带各自的有界 `message`，
  `f2db70b28edb8f753ebed0d3805be7143b521264`）；22.6-L（每个失败样本自带并渲染
  自己的恢复动作）亦已 **PASS / CLOSED**（`b198c9662595c3e9c92d70602170561867763c10`，经 22.6-L-F1
  证据修正接受；被拒 checkpoint `74919a33ac5ec9cde5b104a591ef3fdfb25a1bf3` 与其记录保留）；当前 Slice
  是 22.6-M（统一逐样本目标行形状并加以证明：`_probe_destination_sample` 与单样本完成行各加一行
  `"nextAction": None`，一项跨分支形状测试钉住同序十键，resolution 行其余恒 `None` 键补直接下标证明），
  仍为只读、零变更、不授予 execute 权限。
- Phase 22.6 边界决定（2026-08-29 由审核角色记录）：远端 SMB/OpenList/S3 目标预检、写入式 Storage 能力
  探测、单次请求多 RecognitionType 或多目标 Storage、known-media 重复检测、附件预检与绝对挂载路径展示
  **移出 Phase 22.6**，在后续 Phase 交付；Phase 22.6 以仅 Local、有界、只读的目标预检旅程收口，其
  Final Closure Audit 不因这六项缺失而阻塞，但它们在交付前不得被当作已实现。
- 明确不在 Phase 22.6 范围：Provider switching、通用 Task resume、逐项 Processing Checkpoint
  恢复（第 6 项）、手工整理旅程（第 7 项）、无人值守 `organize --execute`，以及上一条记录的六项延后能力。

### 6. 批处理逐项恢复

- 建立 Task → TaskItem → Processing Checkpoint → stage-aware Recovery Strategy，并在 Web/API
  提供每项的已知效果、重试安全性和有效恢复动作；成功兄弟项永不重放。

### 7. Files / Media 详情与手工整理

- 在现有文件列表/筛选/详情基础上补齐端到端解释、历史、复核、手工 Preview/Organize 和恢复
  跳转；用户无需拼接内部 Task/Review 命令。

### 8. 自动化与最终生产加固

- 完善定时维护、Dashboard 指标、跨平台/多小时/云服务专项验收、静态类型检查与发布文档。
- 是否开放无人值守 `organize --execute` 必须另行完成权限、恢复、幂等和安全验收；当前仍禁止。

### 执行约束

1. 严格按上述优先顺序推进；不得跳回“所有 Repository 先做完、API/UI 最后补”的横向路线。
2. 每个 Phase 保持单一可验收用户切片和提交粒度，沿用 PASS/测试计数/审计证据风格。
3. User acceptance 必须覆盖成功、可操作失败、恢复、并发/陈旧状态及适用的零 mutation。
4. 实机验收遵循 `docs/storage-acceptance.md`，不得使用生产数据或凭证。
5. 持续安全基线与引擎边界不因 UX 工作而放宽。

## 下一步实施建议

Phase 22.2R-F1 独立验收曾给出 **FIX REQUIRED**；Phase 22.2R-F2 已于 2026-08-24 通过独立验收。
resident API 使用不可变 request-scoped binding 绑定 snapshot identity、队列/execute 准入和配置
派生视图；Worker 对缺失、不可读、digest 损坏、schema 不支持和 runtime-invalid 的 saved
revision 持久化可操作且脱敏的失败证据。独立复核的 11 项关键回归和 708 项完整离线
套件无失败，本 Task 范围内无 P0/P1 偏离。

Phase 22.3、Phase 22.4 与 Phase 22.5（A/B/C/D/E 及其全部 correction）的独立验收已全部通过。
Phase 22.5-E 的首个实现 checkpoint 曾被判定 **FIX REQUIRED**，该记录与被拒 SHA 保留不改写；
correction checkpoint `dce5c0ba53bb4fc91f18d1b5d6d56564cd3cfe62` 已于 2026-08-27 通过独立 High
re-review，同日 phase-level Final Closure Audit 判定 Phase 22.5 **PASS / CLOSED**。
Phase 22.6-A（含被拒 checkpoint `90ce13a6c6c39912dd389f71a1189314ff24eb5d` 与其保留记录）已于
2026-08-28 在 correction checkpoint `30af69ac82b30f8a45ad66afbd3c9747597c8fe7` 通过独立 High
re-review，判定 **PASS / CLOSED**。Phase 22.6-B 亦已于 2026-08-28 在
`5e2da5c634f1fa72a40e5f50b035260418fe1a37` 通过独立 High Review，判定 **PASS / CLOSED**。
下一正式 Task 是 **Phase 22.6-M — One Provable Per-Sample Destination Row Shape**；
Phase 22.6-A 至 22.6-L 已全部通过独立 High Review 判定 **PASS / CLOSED**（22.6-E、22.6-G、
22.6-H、22.6-L 各经其 F1 修正接受，被拒 checkpoint 与其 FIX REQUIRED 记录保留不改写；22.6-L 的接受
checkpoint 为 `b198c9662595c3e9c92d70602170561867763c10`，被拒 `74919a33ac5ec9cde5b104a591ef3fdfb25a1bf3`
于 2026-08-29 判 **FIX REQUIRED** 并保留不改写）。22.6-A 至
22.6-K 的全部 checkpoint 与审核记录已推送 `origin/main`（2026-08-29 第二次授权推送，`main` 与 `origin/main`
当时同为 `af9ca9a`；此后 `74919a3`、我的 22.6-L 审核记录 `cf99c6b`、22.6-L-F1 接受 checkpoint `b198c96` 与本轮审核记录尚未推送，需新的显式授权），Phase 22.6 的 phase-level
Final Closure Audit 仍未执行，推送本身不构成 Phase 关闭。不得借此提前开展 Provider
switching、通用 Task resume、兄弟项重放、
逐项 Processing Checkpoint 恢复或
更宽的自动化。Interval/Cron 仍只允许 scan/preview；
无人值守定时 `organize --execute` 继续不支持。
switching、通用 Task resume、兄弟项重放、
逐项 Processing Checkpoint 恢复或
更宽的自动化。Interval/Cron 仍只允许 scan/preview；
无人值守定时 `organize --execute` 继续不支持。

## 持续安全基线

- 默认 DryRun；真实变更必须显式授权。
- 不覆盖已存在目标，不静默删除源或未知文件。
- 只有 OrganizerExecutor 可以调用 Storage mutation。
- 同存储操作优先原生能力；跨存储 Move 必须 Copy→校验→Delete。
- 任何回退必须由策略显式配置，不得改变操作语义。
- 凭证仅来自环境或未来 Secret Store，不进入配置导出、日志和历史。
- RecognitionType C 复用 A 下游策略时仍必须保持 C。
