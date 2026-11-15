# Task PATCH-20261115-1 — 设置页可读性、去重与表单一致性修复

Next Action: B REVIEW；Developer 已在同一 Task 从网页完成精确草稿的发布前检查与 checked 激活，待 B 独立复核。

用户先要求只读调查，随后要求“规划一个独立修复 Task”，规划草案提交于
`9820cffa5dc4804634cc67ef96c3868aea75858e`。用户现明确“激活Task”，正式授权本 Task
实施；移除规划草案和无活动实施通知，保留原 Task ID、Base、Goal、Scope、Difficulty、
Test Level 及验收要求。激活检查点之后，Developer 已在
`d90b91bab8171c28b634b75ff15556b9b2115a11` 提交实现、测试与交接报告。
交接检查点为 `3186660167e82bf419051cdc8a072db4ed081604`；B 首次独立复核决定
FIX REQUIRED，修正保留同一 Task ID/Base/Goal/Scope。Developer 已在
`2ae26aec7f03b1bcce1fc2770837e26490bad80a` 提交两条阻塞的修正与回归；B 已核实修正，
并因 B-03 网页发布旅程未完成退回。Developer 已在
`6947b0f2f417aca68cf99c7634d288978386a0e2` 把精确草稿的只读检查接入设置页并改用网页旅程验证，
现交 READY FOR B REVIEW。未推送、发布或部署。

Authority: 用户授权的现有设置页独立修复范围；生命周期、角色与测试责任以
[Development Workflow](docs/development-workflow.md) §3.1/§5/§6 为准。
按 [Task 模板](Task/TEMPLATE.md) 规划；实施者须读
[Developer experience](docs/agent-experience/developer-implementation-role.md)，B 须读
[B experience](docs/agent-experience/task-planner-reviewer.md)。

```text
Task ID: PATCH-20261115-1
Task Type: STANDALONE MINOR BUG
Parent Slice: NONE
Status: READY FOR B REVIEW
Task Base: d5803682ac3e37cae6d46f3064c4cf252dc8aa30
Difficulty: High
Test Level: T4
Planner / Reviewer: B
Implementation Authorization: USER AUTHORIZED — 用户明确“激活Task”
```

### Goal and complete journey

用户从侧栏“系统设置”或业务页的配置恢复入口进入 `/ui-v2/configuration`，首先读懂
当前设置与是否生效，直接修改已有支持的设置；需要时进入高级配置和诊断，完成现有
草稿编辑、验证、显式激活、JSON 查看／导出或恢复，再准确返回来源页。
成功、未生效、需重启、尚未采用、权限拒绝、并发冲突和结果未知各自清楚，失败保留
可修正输入和真实耐久状态；不要求普通用户理解内部标识，也不丢失已有诊断与初始化能力。

本 Task 修正既有表面和行为缺陷，不增加配置能力或改动配置权威。相关已接受 Slice
40/41/43/47/50/52/54 只作引用；SLICE、Roadmap、Progress 及其接受身份保持。
适用 `V2-UX-001–003/014/015`、`V2-SETUP-001/002`、`V2-CONFIG-001–004`、
`V2-TASK-011`、`V2-AUTO-007/008`、`V2-RULES-001`、`REQ-CONFIG-005/011`、
`REQ-WEB-006`；完整旅程见 [配置生命周期与首次设置](docs/product-experience.md#configuration-lifecycle)、
[运行设置与采用](docs/product-experience.md#current--complete-native-automation-workspace-accepted43-amended46)。
既有契约见 [Configuration guide](docs/configuration.md)、
[System runtime settings](docs/architecture.md#system-runtime-settings--user-amendment-2026-11-03)、
[Empty business runtime](docs/architecture.md#current--empty-business-runtime-and-resident-configuration-lifecycle)。

### Baseline and actual gaps

规划前 `python3 scripts/check_governance.py` PASS。仓库 `/Users/songzhidong/mediaflow`，
分支 main，HEAD 为 Task Base；暂存区与工作区干净，TASK.md 与 Git 可写。
已读取当前治理、模板、B 经验、HEAD:SLICE、Task、Roadmap/Progress 和适用旅程／契约。
既有 Slice54 为 PASS / CLOSED，无活动实施 Task；符合独立修复路径。

激活前 HEAD 为 `9820cffa5dc4804634cc67ef96c3868aea75858e`，分支仍为 main，
暂存区与工作区干净，治理检查 PASS；未出现介入产品变更，Task Base 保持不变。
本次独立 Task 不修改 SLICE、Roadmap、Progress 或已接受 Slice 的关闭事实。

调查通过浏览器只读观察现有部署的设置／规则／自动化／通知页，并核对当前源码。
没有保存、验证、激活或写入部署；未核对部署构建与 HEAD 身份，未完成窄屏、故障注入或
产品验收。以下源码定位和可见问题是实施基线，部署观察不能替代后续精确候选验收：

| 缺口 | 根因／源码定位 |
|---|---|
| 首屏连续出现 Configuration、系统设置、配置生命周期；英文、UUID 与机制说明先于可编辑设置 | `ConfigurationPage.tsx` 页头及 Authority/revision/Next action 平铺；Shell 仍加位置行与只读文件搜索 |
| 留白、刷新位置、相邻面板间距及满宽普通按钮与其他页不协调 | `mf-page`/`mf-page-header` 没有对应 CSS，通用 `mf-panel` 的纵向 flex 拉伸直接子按钮；高级 select/input 未接入表单样式 |
| 重复规则概览、正常采用状态占据大量空间 | `RuleReadinessPanel` 再列七类数量／启用数／缺口；运行表单整体采用结论后又铺三张正常状态卡 |
| 高级字段入口藏在查看 JSON／恢复草稿之后，字段路径＋通用值输入缺乏业务分组 | `settingFields` 丢弃后端 section 分组，所有类型使用同一个文本 input；高级编辑没有独立可发现入口 |
| 布尔值空白，非法输入可能被静默改写 | `text()` 不接受 boolean；保存使用字符串等于 true，其余全部变 false；整数 parseInt、数字 Number 会截断或把空白转零 |
| 有 Active 时默认仍选草稿，空 JSON 区先出现并可见验证／激活按钮 | selected 回退 setupDraft，json 初值为空，尚未 inspect 就渲染修订区和操作 |
| 状态、刷新与保存反馈难以读懂或彼此不同步 | 配置状态与运行参数分别读取／刷新，通用成功也显示“需要继续处理”；version 与 sequence 未明确区分 |

三项运行参数在自动化页已无第二份编辑器，不属于待删除重复；通知轮询／租约也不是
Webhook 定义／投递记录的重复。仅修设置页过量展示，保留它们现有管理归属。

### Implementation Scope and ordered steps

1. **建立页面层级。** 默认主视图只有一个中文“系统设置”内容标题、简短说明、协调的
   页面刷新和紧凑配置状态摘要，随后直接呈现三项运行设置。提供清晰的“高级配置”和
   “诊断”次级区域／切换，沿用当前路由与 allowlisted 返回上下文，不新建设置中心。
   进入、切换、刷新、返回和重连只读取；无 Active 时就近显示明确初始化或恢复操作，
   无草稿／已有草稿／合法空 Active／损坏 Active／只读账号保持可辨。
2. **统一视觉与去重。** 以当前规则页、自动化和通知页的标题、内容边界、字体、字段、
   间距、按钮和状态反馈为基准。移除设置页重复位置行与无功能的文件搜索占位；Shell
   修改仅限识别此表面，其他页面布局不变。普通按钮按内容布局，不由面板拉成整行；
   表单宽度、分组留白和窄屏堆叠协调。规则七类计数／启用数／完整缺口移入诊断，
   日常视图不再复刻规则概览；保留精确规则族链接、不可用／混合快照原因与原来源返回。
   命令能力明细保留在诊断；移除已退出的独立预览展示项，不改共享分析／就绪计算。
   正常采用情况优先给整体结论，实例／各项证据可展开；待采用、覆盖、缺服务或读失败
   就近显示具体下一步，不折叠成成功。内部 ID、digest、authority、技术原因码仅诊断可查。
3. **修复配置查看与初始化。** 有健康 Active 时，JSON 查看默认读取精确 Active；存在
   草稿不自动改选它。无 Active 时可恢复已有草稿或明确创建首个草稿，读取不得创建。
   损坏 Active 明示恢复，不拿草稿替代。未加载／读失败／无内容各有状态，不能把空白框
   当配置，也不能在缺少精确修订／版本证据时启用发布。修订选择、编辑、验证和激活
   始终绑定同一对象；显示可读的“生效配置／草稿”，明确配置序号与草稿编辑版本。
   JSON 和脱敏配置包各自标注内容与来源，保留现有导出能力和包格式，操作结果可理解。
4. **高级设置改为有类型的分组表单。** 高级入口不依赖先打开 JSON。保留现有后端
   allowlist、section、字段值与生效边界，按语言／时区、路径、日志、重试、通知运行、
   远程执行组织已支持字段；不硬填默认值，不展示不可编辑的部署数据库定位。
   布尔使用开关／复选框，枚举使用合法选项，整数／小数严格校验有限值与已有范围，
   字符串／路径使用对应字段；单位和热生效／需重启说明就近显示。
   布尔 false/true/未配置必须可辨；非法布尔文本、整数小数、空白数字、NaN/Infinity、
   尾随字符不能被转换成另一合法值再提交。后端仍为最终校验权威。
   每组“保存到草稿”只提交该组实际修改字段，复用现有 settings edits API：从 Active
   明确保存时创建精确后继，已有草稿编辑绑定所选版本；不隐式采用其他人的打开草稿。
   多组输入切换保留；成功只确认已提交快照，未提交／在途后输入仍属未保存。
5. **保留两种既有发布语义并修正反馈。** 三项运行参数继续通过现有 focused API 一次
   保存发布，不重增草稿／验证／激活步骤，也不在高级表单重复编辑这三项或退休字段。
   高级设置保存仍只是草稿；同一区域明确显示后续“验证草稿”“激活配置”和当前验证
   是否有效，激活只针对精确已验证版本；不新增自动整份发布或悄悄发布其他草稿改动。
   已有启用库时，同一高级区域须能通过已有只读检查能力完成该精确草稿适用的检查与
   checked 发布；缺项提示必须有可执行的网页操作，不能由用户或测试脚本手工调用 API
   补齐。这是原完整设置旅程的实现指导，不改变检查规则或增加新的配置能力。
   保存成功、草稿成功、生效成功和已发布但采用未完成分别反馈；两组读取在相关成功后
   更新实际权威，页面刷新覆盖当前所显示状态，刷新不清除输入或重播命令。
   已知拒绝说明阶段／旧 Active／草稿状态／修正动作；未知写入不声称未保存、不自动
   重发，在核实失败或仍未知时保持阻止再次写入，保留现有请求核对和身份隔离。
   异步读取／保存／验证的迟到结果不能跨修订、组、身份或新输入覆盖；在途操作有
   防重复提交与离开保护，明确放弃输入与继续编辑可用，不要求用户操作内部令牌。
6. **完成受影响验证并交接。** 改写旧英文标题／控件选择器时保留原业务断言；补充
   下列回归与真实旅程。产品实现仅限设置页组件、必要表单模型／API 适配、精准 Shell
   样式及受影响测试／隔离 harness。现有后端契约若不足，不自行加 endpoint/store 或
   改发布语义，交 B 重新核对边界。经 B PASS 后才按现有事实最小核对操作说明；
   规划阶段不修改需求、架构、旅程、SLICE、Roadmap 或 Progress。

### Acceptance Criteria

- [ ] 正常已配置进入时，主内容只有一个“系统设置”标题；紧凑状态后直接找到运行设置，
      无重复英文位置行、只读文件搜索、UUID 墙、规则七类清单或大面积正常采用卡片。
- [ ] 标题／刷新／按钮／分组字段与现有页面协调；桌面 1440×900、窄屏 390×844、
      矮视口 1280×600 同视口改前改后截图及实际操作通过。长名称、长值、展开诊断和
      多条错误可读，无页面横向溢出、遮挡、突兀撑高／反复淡入；仅“不溢出”不算美观通过。
- [ ] 高级字段完整、中文、分组、有类型与单位；所有现有允许值保留，boolean 两值正确
      显示／往返；整数小数／空白／尾随字符／非有限值拒绝且不发送改写后的值。
- [ ] 有 Active 默认查看其精确 JSON；草稿明确选择才打开，读取失败无旧对象冒充，
      JSON／配置包来源与种类清楚，脱敏和部署权威排除保持。
- [ ] 三项运行设置一次保存只发布原三项实际修改；高级每组保存仅修改所选草稿／精确
      后继的本组改动，仍待验证和显式激活。无关设置、其他打开草稿和工作 pins 不变。
- [ ] 已配置启用库的实例，修改日志保留天数后，仅用本页操作即可完成精确草稿的适用
      检查与 checked 激活；检查失败能在网页纠正／重查，保留草稿与旧生效配置。原生
      验收不得通过测试脚本直接调用检查 API，代替缺失的用户操作。
- [ ] 空基线创建／恢复／验证／激活 Web 可完成；Viewer、缺权限、已有损坏 Active 和
      setup-required 返回保持准确；无后台隐式建草稿、媒体 Task、通知或 Storage 写入。
- [ ] 发布目标与实际采用分别真实；正常整体结论、活实例 pending/override/missing、
      有界历史／不可用和热生效／需重启可辨。刷新／后续读取失败不抹掉已知成功。
- [ ] 校验失败、401/403、409、持久化／运行时准备失败、请求前拒绝、实际写成功后丢
      响应均保留正确状态与输入；未知结果先只读核对，不把核对失败当允许重提。
      三项设置表单与其他管理员改动保持原冲突合并语义。
- [ ] 切组／切修订／后台刷新／保存期间输入、迟到响应、返回／重认证不串内容、不丢
      未提交输入、不重复写；未保存离开有明确决定，在途提交保护有效。
- [ ] 诊断仍有精确版本、命令就绪、七类规则计数／缺口／混合快照及实例证据；来源规则
      族、Storage 等合法返回准确且返回后读取实际权威。键盘、焦点、展开控件与
      reduced-motion 可用；规则／自动化／通知／两种库页面无共享样式或入口回归。

### Required Tests

遵循 [测试责任](docs/development-workflow.md#6-test-levels)。本规划文档的实际检查不等于
下列产品门禁通过；Developer 只负责受影响计划，B 独立审查完整 Base..候选并完成 T4。

#### Developer — affected tests

仓库根目录：

```sh
python3 scripts/check_governance.py
.venv/bin/python -m unittest discover -s tests -p 'test_system_settings_management.py'
.venv/bin/python -m unittest discover -s tests -p 'test_configuration_status.py'
.venv/bin/python -m unittest discover -s tests -p 'test_v2_settings_rule_readiness.py'
.venv/bin/python -m unittest discover -s tests -p 'test_automation_settings_management.py'
.venv/bin/python -m unittest discover -s tests -p 'test_configuration_package_exchange.py'
git diff --check
```

Web 目录：新增 `configuration-settings.spec.ts` 覆盖页面分区、typed forms、读取及发布
状态／失败／返回；扩展 `ConfigurationPage.test.tsx`，表单模型拆出时同步补其输入边界
测试；不测试 CSS 数值代替可见验收。现有选择器按新中文操作更新，业务断言不得删减。

```sh
npm run test -- run src/features/configuration src/features/operations/AutomationSettingsPage.test.tsx src/features/operations/automation-settings-recovery.test.ts src/features/operations/automation-settings-session.test.ts src/entities/operations/automation-settings.test.ts src/shared/navigation/settings-return.test.ts src/shared/ui/AppShell.test.tsx src/routes/router.test.tsx
npm run typecheck
npm run lint
npm run format:check
npm run build
npm run test:e2e -- tests/e2e/configuration-settings.spec.ts tests/e2e/rules-readiness.spec.ts tests/e2e/page-transition.spec.ts --output=test-results/patch-20261115-1-affected-node
npm run test:e2e -- --config=playwright.python.automation.config.ts tests/e2e/automation-settings.python.spec.ts --output=test-results/patch-20261115-1-affected-python
```

真实 Python spec 复用隔离 API/SQLite 和真实常驻消费者，增加高级类型保存草稿→验证→
显式激活、两个浏览器并发、实际写完成后丢响应与只读核对；测试不得把假返回当采用。
首次设置／Storage 返回复用并更新旧文案选择器后运行：
`.venv/bin/python scripts/storage_settings_browser_proof.py`（仓库根目录）。
仅测试本 Task 影响的真实旅程，不要求 Developer 运行其余完整原生矩阵或全量套件。

#### B — acceptance and full regression

先对精确候选复现布尔双值／数字严格校验、Active 默认读取、首次空基线、并发与未知
写入恢复；原生证据必须来自候选新构建、临时配置／SQLite／Local 根，不访问用户运行
数据库、生产媒体或外部服务。独立核对所有验收项与截图，不能只接受 Developer 标签。

运行 [shared full gates](docs/development-workflow.md#shared-full-regression-commands) 的
完整 Python/Web/Node E2E、质量、示例、构建／wheel／安装门禁及本 Task 适用安全验证；
另运行上述真实设置／首次设置旅程和 `test_automation_settings_resident.py`，证明发布与
实际采用、进程等待／恢复、原 pins、零媒体变更、无关草稿不被发布与未知不重放。
Python/Node 并行时分开产物目录；保存候选 SHA、命令、结果／跳过、原失败、截图及
构建／wheel 身份到稳定忽略证据目录，不上传秘密，不把此前部署观察作当前验收。
不改 Docker／部署边界则无需新增该类实现；已有门禁适用性与未执行限制由 B 明示。

### Non-goals

- 新设置、新配置中心／数据存储／通用表单平台、任意 JSON 编辑或新导入旅程。
- 合并／替换 focused 与 generic API，改变草稿／显式激活权威、schema、RBAC、审计、
  原子发布、消费者采用判定或退休字段行为；不新增自动重试／自动发布／隐式业务默认值。
- 重设计规则／自动化／通知／存储／库页面，搬迁其对象管理、删除诊断能力或重开已关闭 Slice。
- 更改常驻调度／队列／超时、媒体处理、Storage 操作、C→A 识别身份或历史 pins。
- 使用生产配置／秘密／媒体作验收，推送、发布、部署、分派其他代理或自审通过。

### Developer Completion Report

Status: READY FOR B REVIEW
Task Base: `d5803682ac3e37cae6d46f3064c4cf252dc8aa30`
Original implementation: `d90b91bab8171c28b634b75ff15556b9b2115a11`
Fix implementation checkpoint: `2ae26aec7f03b1bcce1fc2770837e26490bad80a`
Handoff checkpoint: 本 `TASK.md` 提交（仅文档；实现为上列 SHA）

#### 实际变更

- **页面层级与去重。** 默认主视图只保留一个中文“系统设置”标题、简短说明、页面刷新和
  紧凑配置状态摘要；随后直接是“系统运行设置”。高级配置与诊断作为次级区域；诊断
  折叠保留命令就绪、七类规则计数／缺口／混合快照、精确版本／摘要、消费证据。
  移除 Shell 在设置表面上的只读文件搜索和重复位置行；其他页面仍走原 Shell 分支。
- **视觉与布局。** 设置页使用与规则／自动化／通知页协调的标题、卡片、间距、字段和
  状态样式；普通按钮按内容布局；桌面、窄屏和矮视口下分组字段、工具栏和 JSON 区域
  堆叠，无页面横向溢出。运行采用证据收拢为一个紧凑区域，服务实例按行展开，不再
  在正常结论后铺三张状态卡。
- **配置查看与初始化。** 有健康 Active 时默认读取并展示其精确 JSON；草稿只在操作者
  明确选择时读取。无 Active 时提供明确的恢复草稿或创建首个草稿操作；损坏 Active
  只显示恢复状态，不用草稿替代。JSON 与脱敏配置包分开展示内容、来源和版本；
  读取失败、空内容和未加载分别可辨，不把旧内容当当前结果。
- **高级设置有类型分组。** 按后端 section 组织语言／时区、路径、日志、重试、通知
  运行、远程执行；保留 allowlist、边界值和生效边界，排除 focused 三项运行参数与
  部署数据库定位。布尔提供开启／关闭／未配置，枚举使用合法选项，整数／小数严格
  拒绝空白、尾随字符、NaN/Infinity、越界和非法枚举；非法输入不发送。
- **按组保存与两种发布语义。** 每组保存只提交本组实际修改；从 Active 保存创建精确
  后继，从草稿保存绑定所选修订的当前编辑版本；其他组、其他打开草稿和未提交输入
  不被提交。三项运行参数继续使用原有 focused checked Save 一次发布。高级草稿保存
  后仍须验证并显式激活；激活恢复原 `checked: true` 边界，只发布精确已验证版本，
  由后端重新核对适用 Storage 检查、识别策略测试和目标预检；拒绝时不发布并保留
  草稿与旧 Active。
- **按组放弃只影响本组。** “放弃本组修改”只把当前组字段恢复为编辑会话的比较值，
  保留其他组输入、初始比较值和原编辑权威；切回其他组仍可准确保存其实际修改。
- **失败、并发与输入保留。** 已知拒绝、旧 Active／草稿、未知写入、在途命令、迟到
  响应和离开均有明确状态；未知写入先只读核实，不自动重发。checked 激活被发布前
  检查拒绝时显示“发布前检查未满足”、后端返回的具体缺项／下一步，并保留精确草稿、
  验证状态与旧 Active；不自动重发或改走兼容激活。保存期间仍可编辑其他输入，迟到
  响应只确认已提交快照；未提交／在途输入保留为未保存。未保存输入或未知写入按
  principal 存入 sessionStorage，显式断开／身份切换由共享 cleaner 清除，重认证或重载
  可恢复；不存凭据、令牌或发布授权。
- **验证与交接。** 更新设置页、自动化采用区、Rules 就绪和页面过渡的既有选择器与
  fake／真实 Python 测试；新增 typed form 模型、session 保留、Node 设置旅程及真实
  Python 高级设置旅程。本轮新增双组放弃回归（Vitest + Node E2E）、checked 激活
  blocker 回归和真实 Python“缺检查被拒→满足现有检查→checked 激活”旅程；fake 按
  真实接口拒绝未 checked 的激活请求。

#### 实际验证（最终候选 `2ae26aec`）

- 根目录：`python3 scripts/check_governance.py` PASS；`git diff --check` 通过；
  `ruff format --check`／`ruff check` 覆盖改动的 `storage_settings_browser_proof.py` 通过。
- Python 受影响单测：`test_system_settings_management.py` 24、`test_configuration_status.py` 6、
  `test_v2_settings_rule_readiness.py` 11、`test_automation_settings_management.py` 56、
  `test_configuration_package_exchange.py` 13，全部通过（110 项）。
- Web 质量：`npm run typecheck`、`npm run lint`、`npm run format:check`、`npm run build`
  通过；构建产物为 `index-EfCqwWlB.js`、`index-DsUx6wXB.css`。Task 指定的 affected
  Vitest 127 项通过（10 文件）；其中 configuration + AutomationSettingsPage 子集 69 项。
- Node E2E（构建产物 + 隔离 fake）：`configuration-settings.spec.ts`
  `rules-readiness.spec.ts` `page-transition.spec.ts` 共 34 项通过（新增双组放弃旅程；
  fake 拒绝未 checked 的激活，并断言激活请求体为 `{expectedVersion, checked:true}`）。
- 真实 Python／API／SQLite：`automation-settings.python.spec.ts` 18 项通过，含更新后的
  高级 typed Save→验证→缺检查被拒→为精确修订满足真实只读 Storage 检查／识别策略
  测试／目标预检→页面 checked 激活成功；另含双浏览器同草稿并发、写成功后丢响应
  只读核对。
- `scripts/storage_settings_browser_proof.py` PASS：首次空基线创建／恢复／验证／
  checked 激活返回 Storage（已断言激活请求 `checked:true`），且无 token／sessionStorage
  泄漏。
- 本轮测试及构建命令累计约 4–5 分钟，低于本轮开发总时间（约 25 分钟）的 30%；
  其中一次真实 Python 用例失败是测试辅助读取了错误的 detail 字段，修正测试后全量
  通过，无产品失败。未运行全量 Python/Web/Node 门禁，T4 全量归 B。

#### 已知风险与限制

- **产品缺口（交 B 判定）。** V2 设置页没有运行精确修订 Storage check／识别策略
  测试／目标预检的界面；在带启用库的实例里，高级草稿会按原权威被 checked 激活
  拒绝。页面已显示具体缺项和后端下一步并保留草稿／旧 Active；真实 Python 用例用
  现有公开只读检查 API 为该精确修订满足检查后，页面 checked 激活成功。首次空基线
  无适用检查，Web 可完成。本 Task 未新增检查执行 UI、endpoint/store 或降低检查；
  是否另开独立 Task 补齐该缺口由 B 核对决定。
- 被拒提示中的“具体缺项”沿用后端 bounded `nextAction`（英文、可能含 Storage ID），
  以保持精确；请 B 核对这是否满足普通操作员可读性，或需另定中文映射。
- 未保存输入／未知写入使用 principal-scoped sessionStorage 保留；需 B 核对
  401／403、同 principal 重认证、显式断开、身份切换和浏览器持久化泄漏。
- Node fake 已按真实公开形状实现设置投影、草稿生命周期和 checked 拒绝，但不模拟
  Storage／规则检查证据；真实发布证据来自真实 Python／API／SQLite 旅程。T4 全量、
  真实视觉验收、完整 RBAC／并发矩阵和可能的既有失败由 B 独立执行。
- 本轮未修改需求、架构、旅程、SLICE、Roadmap 或 Progress；未推送、发布或部署。

### B Review Result

```text
Reviewed Base: d5803682ac3e37cae6d46f3064c4cf252dc8aa30
Reviewed Head: 4fa38c9ecc7dfff3f44dcb7e4002e3b2fae84c69
Implementation Head: 2ae26aec7f03b1bcce1fc2770837e26490bad80a
Decision: FIX REQUIRED
Authorized bug acceptance complete: NO
Next: SAME TASK FIX LOOP
```

B 已审查完整 Base..候选的 17 文件变更，并逐项复查上次候选后的 8 文件修正。
实现之后的 `63bf6e3e`／`4fa38c9e` 只有 Task 交接／测试结果文档变化。
工作区 main、复核前干净，治理检查 PASS；独立修复没有 Parent Slice，不改变
SLICE54、Roadmap、Progress 或已接受结果。本次仍只修改 Task 审查与开发指导。

#### 上轮阻塞的实际复核

- **B-01 的绕过检查问题已修复。** helper 恢复固定 checked:true，页面激活走原检查
  边界；B 从真实 Python 设置页保存日志草稿、验证并激活，观察到 checked:true 和
  缺检查时的 409，未再走兼容发布。空业务首次设置／checked 激活／返回 Storage
  的真实旅程也通过。普通高级设置的成功／恢复仍有下列 B-03，不能据此接受整个 Task。
- **B-02 已修复。** B 从页面修改时区→切日志修改保留天数→放弃日志组→返回时区组，
  Europe/Berlin 仍保留；随后单独保存时区，实际 edits 只有 timezone，日志组已恢复。
  没有整份重建表单或丢掉另一组输入。原失败与首次 FIX 记录见 `bc508559:TASK.md`。

#### B-03 — 已配置实例的高级设置发布缺少网页完成入口（P1）

**实际旅程：** 在已有启用资源库／媒体库的真实隔离实例中，打开系统设置→日志，
把保留天数 30 改为 31→保存到草稿→验证草稿→激活配置。后端正确拒绝缺少当前草稿
的 Storage 检查，返回 409；页面显示英文“run the read-only Storage check ...”，
却没有运行此修订检查的按钮、链接或其他完成动作。再次验证／激活不能补齐检查，
本次日志设置无法在当前 V2 网页完成生效。

B 的本页实际请求中，三类检查请求数为 0；高级区域只有验证、激活、分组、保存、
重读和导出等操作。源码检索也确认 V2 没有接入精确草稿的 storage-check／
recognition-strategy-test／destination-precheck。旧 V1 和后端存在相关能力，不是
本页可执行的恢复入口。

当前真实 Python 用例在 `automation-settings.python.spec.ts:1481` 直接通过
`runExactRevisionChecks(request, ...)` 调用这些 API，随后才再次点击页面激活。
这证明后端能力可用，不证明操作者能完成网页旅程。Developer 已披露缺口，B 确认
它属于本 Task 已要求的“高级设置编辑→验证／检查→显式激活→失败恢复”，不能另开
Task 延后，也不能降为仅提示／诊断问题后接受。保留 checked 边界的修正正确，不回退。

#### Developer 开发指导（同一 Task）

1. 在当前高级设置区域接入已有的精确草稿只读检查和发布能力，使操作者从本页能
   完成适用检查后 checked 激活。按已有后端规则判断适用项、绑定所选修订与精确版本，
   能自动确定的内容由产品完成；确需样本／选择时提供业务输入，不要求复制修订、
   digest 或自己调用 API。复用已有服务／公开接口，不建新检查平台、设置库或 endpoint。
2. 将真实返回的检查缺项、进行中、通过、失败与下一步整理为中文可读结果，提供实际
   检查／纠正／重查操作。检查失败保留草稿与旧生效配置；再次编辑后使用新版本的
   适用证据，最后仍调用原 checked 激活。不要跳过检查，也不让用户陷入反复验证／
   激活同一份缺证据草稿的循环；三项运行参数的一次保存发布路径保持。
3. 修改现有真实 Python 高级设置旅程：移除代替用户完成检查的测试侧
   `runExactRevisionChecks` 调用，从真实网页执行新接入的操作，一直到新日志值真实
   生效。测试只观察／控制既有隔离依赖，不在 UI 之外补证据。覆盖正常带启用库、实际
   检查失败后网页恢复、无适用检查的空基线；继续保留 B-02 双组放弃和输入隔离回归。
4. 运行 Task 的新／改变／直接受影响验证，记录实际结果并交 READY FOR B REVIEW。
   完整 T4 仍由 B 负责。本轮开发／复核测试时间小于各自总时间的 50%；不改 Task
   Base，不新拆 Task，不降低验收，不开发无关过程工具。

#### 本轮实际验证与限制

- `python3 scripts/check_governance.py` PASS；完整 Base..Head `git diff --check` 通过。
- `npm --prefix web run build` 通过，产物 `index-EfCqwWlB.js`／`index-DsUx6wXB.css`。
  实际复现使用新构建和现有临时 Node fixture／真实 Python API／SQLite harness。
- 从已有页面完成 B-02 双组修改、单组放弃、另一组单独保存：通过；请求 edits
  为 `[{fieldPath: timezone, value: Europe/Berlin}]`（JSON 原值见证据）。
- 从真实 Python 设置页完成日志保存→验证→激活：checked:true、409 缺检查；页面
  没有检查执行入口，确认 B-03。没有用直接 API 检查补救并冒充网页成功。
- `.venv/bin/python scripts/storage_settings_browser_proof.py` 通过：首次空基线的
  创建／恢复／验证／checked 激活／返回以及健康 Active 文件浏览保持。
- 已查看带实际错误与全部高级操作的新构建截图；本轮没有据 fixture 中缺 Worker／
  Scheduler 的状态扩展产品问题。存在明确 Task 阻塞，按流程先退回，T4 全量与完整
  视觉／原生／安装矩阵待修正候选，不以 Developer 127 项等通过标签代替独立接受。
- 本轮测试与构建命令累计约 5.2 秒，低于本轮超过 4 分钟复核时间的 50%。原日志、
  请求与操作清单、截图、trace 和资产 digest 存于本机忽略目录
  `.git/validation-evidence/patch-20261115-1/b-round2/`；未上传远程 CI。

---

### Developer Completion Report — B-03 修正

```text
Status: READY FOR B REVIEW
Task Base: d5803682ac3e37cae6d46f3064c4cf252dc8aa30
B-03 fix implementation: 6947b0f2f417aca68cf99c7634d288978386a0e2
Handoff checkpoint: 本 `TASK.md` 提交（仅文档；实现为上列 SHA）
```

#### 实际变更

- **发布前检查模型。** 新增 `configuration-checks.ts`，从该修订的同一对象投影确定
  checked 激活实际要求的检查：被资源库／媒体库引用且启用的存储；存在启用资源库时的
  识别策略测试；以及按后端同一规则（媒体库＋启用识别类型策略＋启用命名／整理策略＋
  分类规则显式引用媒体库）判断的目标预检。禁用存储不要求、引用缺失按需纠正；未识别
  的失败类别不猜成通过。每项给出中文状态、结论与下一步，并将后端原文收在诊断折叠内。
- **网页完成入口。** 高级配置内新增“发布前检查”区域：存储逐项运行只读检查；识别
  策略测试使用所选启用资源库与合成文件名；目标预检使用所选识别类型与示例片名／
  媒体类型／年份／题材／国家／扩展名。所有动作自动绑定所选草稿的当前编辑版本与摘要，
  不需要操作者复制修订、digest 或调用 API；示例输入在前端严格校验，非法值不发送。
  策略测试在草稿验证前禁用并说明原因。
- **真实状态与恢复。** 每次运行后重新读取该修订对象／证据；读取失败时禁用运行且不以
  上次结果判断当前状态。检查被拒／版本变化／权限／不可用分别说明，未执行时不声称已
  变更配置。checked 激活被拒时用同一读取列出来自页面的未通过项（中文），保留草稿与
  旧 Active；无适用检查的空基线明确显示“该草稿没有适用检查”，checked 激活照旧可用。
- **接口适配。** 仅接入已有公开的精确修订 Storage check、识别策略测试、目标预检与
  修订对象投影读取；只读检查按只读语义处理结果未知（不会误报为未知配置写入），未新增
  endpoint、store、schema 或检查规则。
- **测试更新。** 新增检查模型 Vitest 13 项与页面 3 项旅程（逐项检查后激活、目标预检
  真实失败→改正示例重跑、空基线无适用检查）；Node fake 增加 checked 夹具与证据门禁，
  新增浏览器发布旅程；真实 Python 旅程删除测试侧 `runExactRevisionChecks`，改为从网页
  完成 3 个存储检查、策略测试、目标预检（先以 tv 示例真实失败并保留草稿／旧 Active，
  再改回 movie 重跑）直到 checked 激活；首次设置脚本断言空基线无适用检查。

#### 实际验证（实现 `6947b0f2`，最终构建 `index-BikKo9f0.js`／`index-Cvv7FA31.css`）

- 根目录：`python3 scripts/check_governance.py` PASS；`git diff --check` 通过；
  `ruff format/check` 覆盖改动的 `storage_settings_browser_proof.py` 通过。
- Web 质量：`npm run typecheck`、`npm run lint`、`npm run format:check`、`npm run build` 通过。
- Task 指定 affected Vitest 143 项通过（11 文件）；其中 configuration 目录 55 项
  （新增模型 13 项、页面 33 项）。
- Node E2E：`configuration-settings.spec.ts` 12 项通过（含新增 checked 夹具旅程）；
  `rules-readiness.spec.ts`＋`page-transition.spec.ts` 23 项通过，合计 35 项。
- 真实 Python／API／SQLite：`automation-settings.python.spec.ts` 18 项通过；修改后的
  高级设置旅程从页面完成日志草稿→验证→3 个真实存储检查→策略测试→目标预检失败→
  改正重跑→checked 激活，激活请求体为 `{expectedVersion, checked:true}`，所有 6 次
  检查请求绑定同一修订版本／摘要。
- `.venv/bin/python scripts/storage_settings_browser_proof.py` PASS：空基线明确无适用
  检查，创建／恢复／验证／checked 激活／返回 Storage 保持。
- 本轮测试与构建命令累计约 5–6 分钟，低于本轮约 50 分钟总时间的 30%；未运行 T4
  全量 Python/Web/原生门禁，由 B 执行。

#### 已知风险与限制

- 适用性判断是后端 checked 激活规则的前端镜像（存储引用、启用资源库、目标策略链）；
  后端仍是唯一发布权威，后续后端规则变化需同步该模型。目标预检一次一个示例（后端
  支持 1–8 个），未提供批量示例。
- 策略合成文件名与目标示例输入不随刷新／重认证保留（设置字段草稿保留不变）；如 B
  认为示例输入也须跨刷新保留，需在同一 Task 扩展会话结构。
- 当本地未发现阻断项而后端仍拒绝时，提示会附带后端英文 `nextAction`；正常缺项时以
  中文列表为主，后端原文仅在各项诊断折叠中。
- Node fake 的 checked 夹具只产生通过证据；目标失败与纠正由 Vitest 与真实 Python
  旅程覆盖。未做桌面／窄屏视觉复核，T4 全量与视觉验收归 B。

---

## Latest accepted Task — PATCH-20261114-3

```text
Task Type: STANDALONE MINOR BUG
Parent Slice: NONE
Decision: B PASS — 2026-11-15
Task Base: 51480dc318837e4f1e4f9c60c17b8e708abb6409
Implementation Head: 07624ec95b948f211bd93ed77596ebdea7e9992f
Reviewed Handoff Head: 6c4b9a5d390ffc5d1f54537966d4d9f99599a3ad
Acceptance checkpoint: 4134ea8f6be6ac2de920d25eda56d77fcf800526
```

通知六页的可读性、中文状态、居中卡片和表单交互已统一；草稿／生效、未保存输入、
在途命令、读取恢复和原投递筛选返回准确。真实恢复已完成但响应丢失时显示“恢复结果
未知”，读取后显示待投递；真实 409 拒绝仍显示“恢复没有应用”，都只有一次恢复命令。

B 独立审查完整 Base..交接 Head，全部验收项通过、无剩余阻塞。T4：Python 2692 项
（2685 通过、7 可选外部／耐久测试跳过）、Web 100 文件／1601 项、Node E2E 274 项通过；
真实 Python API／SQLite／Worker 旅程、双浏览器并发、权限变化、丢响应读取核对、在途
输入、三视口视觉／键盘及构建安装门禁通过。

完整规划／开发指导、审查、命令、截图／资产／wheel 身份、原失败和适用限制见
[固定 B 验收](https://github.com/kentinya/mediaflow/blob/4134ea8f6be6ac2de920d25eda56d77fcf800526/TASK.md#patch-20261114-3--b-pass)。
最终 Developer 交接见 `6c4b9a5d:TASK.md`，上一轮 FIX REQUIRED 见 `409ac88f:TASK.md`。
本机忽略证据：`.git/validation-evidence/patch-20261114-3/b-round6/`，未上传远程 CI。

依据 [Development Workflow](docs/development-workflow.md) §3.1 恢复本指针，详细历史留于 Git。
收尾文档消费者 8 项、治理检查和 `git diff --check` 通过。
Slice54 保持原 PASS / CLOSED，SLICE／Roadmap／Progress 未变；未推送、发布或部署。

## Previously accepted Task — PATCH-20261114-2

```text
Task Type: STANDALONE MINOR BUG
Parent Slice: NONE
Decision: B PASS — 2026-11-14
Task Base: 4107c299d8f99b817fcd3cbdffa274de1f5598ea
Implementation Head: 6a358085d1fc622c0257c545d83be41539d38620
Reviewed Handoff Head: a98403804f23a47d4bac771def3fc5f07234fcde
Acceptance checkpoint: 7ffe380669e50c46da15982a86e14e54228a38d8
```

两页排序状态与恢复入口收敛到工具栏显示设置，表头／排序／调宽反馈协调；原当前页
排序、精确选择、列宽边界和读取恢复保持。完整 Base..Head 审查、开发指导、验收旅程、
实际测试与原失败记录见
[固定 B 验收](https://github.com/kentinya/mediaflow/blob/7ffe380669e50c46da15982a86e14e54228a38d8/TASK.md#patch-20261114-2--b-pass)。
原规划／激活分别见 `d3d984a5:TASK.md`／`b1fa0905:TASK.md`，Developer 交接见
`a9840380:TASK.md`。

B 独立验证：受影响 Vitest 112 项、Node E2E 71 项、真实 Python 活列表 6 项，以及类型／
lint／格式／新构建、两页四视口前后对照、键盘、真实长名称、读取中间态／错误恢复、
reduced-motion 和重载默认状态通过。首轮 Node／Python E2E 共用输出目录造成一次 trace
归档失败，原日志保留；Node 使用独立目录完整重跑通过。详细命令、产物身份、提示、
未运行／不适用项及本轮测试时间分配见固定验收。

本机证据：`.git/validation-evidence/6a358085d1fc622c0257c545d83be41539d38620/patch-20261114-2-b/`。
依 [Development Workflow](docs/development-workflow.md) §3.1 保留本指针，详细历史留于 Git；
现行行为见 [文件浏览旅程](docs/product-experience.md#browse-feedback-selection-and-table-controls)。
Slice54 保持原 PASS / CLOSED，SLICE／Roadmap／Progress 未变；本次为开发验收，未发布或部署。

上一独立修复 PATCH-20261114-1 的接受身份与证据继续见
[固定 B 验收](https://github.com/kentinya/mediaflow/blob/280fc5fdedaf8c079dee52480e1eb4d3bf26449a/TASK.md#patch-20261114-1--b-pass)。
