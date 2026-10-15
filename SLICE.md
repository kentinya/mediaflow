# Slice 45 — V2 Task Center Redesign and Recovery Pages

```text
Slice ID: 45
Name: V2 Task Center Redesign and Recovery Pages
Owner: A — Slice Owner / Architect / Final Reviewer
Status: ACTIVE
Base SHA: a72252091d5d46edf3e2114b994036ae21b08e2e
Implementation Head: NOT SET
Working Branch: slice/45-scope-pending
Development Authorization: CONTRACT DEFINED; B TASK REQUIRED BEFORE IMPLEMENTATION
Risk: High
Final Test Level: T4
Next Action: B PLANS THE FIRST COHERENT IMPLEMENTATION TASK
```

## Authority and baseline

用户于 2026-10-15 指定 A 冻结 Slice43，并从已接受的 Slice44 基线预留 Slice45；随后确认
任务中心重构、独立 Scan 完整退役、整理内取消独立 Preview 页面、九个横向标签及跨任务
分类恢复列表，最终选择“同页先显示计划摘要，再确认执行”，并要求将最终方案写入文档。

本次检查点激活该完整 Contract，仅是范围与 TARGET 设计授权，不是实现、B PASS 或 A 交付验收。
B 仍须先定义合法 Task；本次不创建 Developer Task、不导入冻结代码、不推送。

不可变 Base 保持为 Slice44 closure `a72252091d5d46edf3e2114b994036ae21b08e2e`
（接受的 Implementation Head 为 `8be263ea778df08aa374e9433f138a218c1d4af9`）。
当前分支的 scope-pending 名称是保留的历史名称，不改变其现在的 ACTIVE Contract。
前期范围说明检查点保留在 Git，未发生产品实现。

## Suspended work preservation

- Slice43 original Base: `853973dbbf8289fa2ad40657033e94e870a690e4`.
- Latest executable candidate: `727317168cc62f859f19db1b54b8175cb08449de`.
- Latest Developer report checkpoint: `78ec108d4473e8c140174c1356d0e88a1ae42b34:TASK.md`.
- Exact pre-hold Contract and Task43.3 plan/B decision snapshot:
  `c539429c2c3aaeaab4842b87d3c858e77106fed1:SLICE.md` / `c539429c2c3aaeaab4842b87d3c858e77106fed1:TASK.md`.
- Frozen Contract checkpoint: `ed974e0df8b263f631bfe48b524da461013d8780`.
- Preservation branch: `frozen/slice-43-2026-10-15`.
- Slice43 status: PLANNED; Development Hold: FROZEN BY USER. Task43.1/43.2 are B PASS only;
  Task43.3 remains PLANNED / NOT STARTED and suspended in the exact snapshot.
- Inventory/statistics, consolidated history and actual engine-settings adoption remain incomplete.
  Slice43 has no final validation, Closure Packet or A PASS / CLOSED.

The same agent previously performed B review and is now explicitly authorized by the user for
A's hold/reservation action. No A final review of its own prior B decisions is performed here.
Git history and locally retained evidence remain available; nothing is pushed or claimed remotely
reachable. Resuming Slice43 requires explicit A reactivation and reassessment of intervening changes.

## User Goal

操作者在一个原生任务中心中发起并确认真实整理、跟踪各文件结果，通过问题类型直接找到
跨任务的待处理工作，并完成明确、低摩擦、安全的恢复，无需独立 Scan/Preview 页面、
CLI 回退或内部授权材料。统一创建、分析、执行、结果与恢复的完整用户旅程。

最终页面/旅程规范：[任务中心最终方案](docs/task-center-page-spec.md)。
九张参考图统一位于 `docs/pics/任务中心-标签名.png`，其结构、层级及风格适用；
样本名称、数量、时间和路径不构成运行数据或固定验收 fixture。

## Applicable Requirements

- V2-OPS-001–008 的既有统一工作、结果、权限及恢复基线，按 V2-OPS-009–012 的显式
  TARGET 产品修订实现新的入口、九标签、同页摘要与跨任务类型视图。
- V2-UX-001–003、V2-AUTH-001–003、V2-SAFE-001、V2-MIG-001–003。
- UX-001–010，REQ-GEN-*，REQ-ORG-*，REQ-RECOVERY-*，REQ-TASK-*，
  REQ-SAFE-*，REQ-RESULT-* 与适用的 Storage/Library/Recognition/Metadata 要求。
- REQ-SCAN-001 的独立手动扫描产品入口被当前 V2 修订取代；内部扫描、过滤、稳定性、
  SourceIdentity 及已有历史语义保留。通用 DryRun 和 Rules 测试不整体退役。
- Slice42 的“全局 Review 列表延期”不限制本次明确选择的跨任务分类列表；跨任务批量
  mutation 仍不在本 Slice。闭合 Slice 的交付事实和原有接受证据不重写。

## Required Outcomes

### RO-1 — 九标签原生任务中心与权威查询

提供同一横向导航行中的 `全部任务 / 进行中 / 需要处理 / 已结束 / 识别恢复 /
元数据恢复 / 分类恢复 / 冲突处理 / 失败恢复` 九个独立可深链列表，默认全宽清单无详情选中。
共享 Shell、来源/类型或状态/时间/文字筛选、有界分页、统计和可见活跃轮询。

后端基于完整授权总体与一致读口径决定列表、计数和当前问题；不能只过滤浏览器当前页。
任务数和文件数分开，重叠视角说明清楚，普通排队不自动算作需要人工处理。
历史名称/范围、进度、主文件/附件及未知数据真实可解释。Job/Task 仅按持久关联去重，
排队及 pre-Task 失败可见，旧诊断和普通文件维护/传输历史不丢失或改写为整理。

### RO-2 — 新建整理与同页计划摘要确认

新建仅提供真实整理，选择 Active ResourceLibrary 与有界目录/文件范围；Files 的单项、
多项及文件夹整理接入相同应用行为和返回上下文。普通操作者无需先跑 Scan 或切到独立 Preview。

显式准备操作复用真实有界发现/稳定性和完整分析链，长操作走持久任务与既有 Worker。
当前创建界面先显示计划摘要：来源、完整性、主文件/附件数、就绪和未就绪项、操作、
媒体库/目录、可展开逐项来源→目标、策略解释、冲突及覆盖/来源清理影响。
准备零 Storage mutation、无执行许可，不因预览准备制造正式执行阻塞待办。

用户检查后明确“确认整理 N 项”；仅精确确认的就绪子集取得执行许可，附件和破坏性
权限绑定实际计划。未选/未就绪项保留独立准备状态与补正入口，不隐藏、不自动执行。
完整性受实质边界影响时不得悄悄选择前 N 项执行。

原子准入、防重复、丢响应核对、固定配置和实时来源校验沿用现有权威。
计划或来源实质变化回到同页更新摘要，不执行未确认的新方案；合法固定历史快照不随
当前 Active 变化而改绑。确认后按原生入口跟踪真实 Worker/OrganizerExecutor 与独立结果。

### RO-3 — 五类跨任务恢复列表与任务内文件处理

五类恢复标签各自列出该类型尚需处理的任务，一行一个任务，展示对应问题、文件数和操作；
同任务可在多类型页出现，旧已解决阻塞不继续占用待处理清单。

行内操作进入该任务该类型的原生文件处理界面，识别、Metadata 候选/纠正、分类、冲突、
失败修复分别提供适合的输入和说明。仅使用后端当前允许的选择/动作。
保留现有任务内有界批量分析恢复及独立准入/拒绝结果，不新增跨任务批量执行。

安全分析可在保存后组合，但保存决定不取得 mutation 权限。恢复界面直接展示新计划摘要、
必要影响确认及明确继续；取消原来强制的独立 Preview 跳转，不要求操作者处理内部 DryRun Task。
成功、忽略和未知效果不被重新执行；配置修复与效果核查明确区别于可安全继续。
解除问题后按真实持久状态更新列表/计数，保留其他任务/文件、返回上下文与关联历史。

### RO-4 — 详情、协作控制、结果与异常连续性

原生详情提供阶段、逐文件与附件结果、源/目标、策略/失败解释、持久执行步骤、相关日志/审计、
恢复链及有界脱敏 JSON 导出，现有 Task/Job 深链仍可到达真实记录。
普通工作不依赖两套 Task/Job 管理入口或内部 UUID。

后端决定各工作类型的暂停/取消/继续可用性，区分请求和确认生效；不声称在途效果回滚。
继续重验剩余范围和真实许可，必要摘要/重新授权在当前界面完成。
Worker 不可用、固定上下文缺失、权限不足、过期输入、未知响应与不确定效果均有行动指引。
持久状态经刷新/重连/重启可追溯，已完成与不确定 mutation 不自动重放。

### RO-5 — 独立 Scan 完整退役与依赖收敛

移除独立 Scan 的 Web 页面/按钮、API/CLI 准入与创建/执行/重试/继续分支，以及仅供该产品
使用的运行编排和死代码；隐藏、改名或保留兼容执行器不满足要求。退役请求明确拒绝并给出
原生整理/历史查看指引，不能自动转成真实整理或通过其他入口绕过。

保留整理/组织共用的 Scanner、Storage 发现、过滤、临时文件排除、稳定性与历史读取。
当前依赖“先手动 Scan”的稳定性/恢复指引必须转为原工作流内部有界观察，不降低检测要求。
旧未完成独立扫描安全停止/取消且保留历史，不删除媒体、记录或旧固定快照。
定义绑定的 Automation 模式退役归冻结 Slice43；不借本 Outcome 实现其完整工作区。

### RO-6 — 统一架构、验证与文档真实性

Web/API/Worker 使用同一应用行为、权限、固定来源/计划和恢复服务；不建立第二套任务、
队列、配置或恢复引擎。必要持久化变更保留原版本、结果、历史模式和来源身份。
任务运行状态、文件处置、待处理问题与效果确定性分开表达。

九页面、创建→摘要→确认→执行、各类恢复及退役/历史路径通过自动化和原生浏览器验证。
CURRENT 文档只在实际验收后更新；本次文档和图仍是 TARGET，不宣称实现。

## Required Surfaces

| Surface | 必需结果 |
|---|---|
| S-1 任务中心九标签 | 独立可达、原生查询/统计/筛选/分页，默认无选中详情 |
| S-2 创建与 Files 接入 | 有界真实来源选择、同页摘要与明确确认、正确返回 |
| S-3 识别/元数据/分类恢复 | 跨任务类型列表及任务内专用文件处理 |
| S-4 冲突/失败恢复 | 独立影响、许可与安全范围；效果未知只核查 |
| S-5 详情/记录/导出/控制 | 真实结果、历史链与后端允许的协作动作 |
| S-6 API/Worker/Persistence | 与 Web 同权威，耐久准入、固定上下文、去重和非重放 |
| S-7 Scan 退役及历史兼容 | Web/API/CLI 不再独立创建或运行，旧证据可读 |

## Product Experience / UX Constraints

完整 goal→entry→state→action→success→failure→recovery 见
[最终页面规范](docs/task-center-page-spec.md)第 3–5 节。
入口自然、中文业务名称优先、只为实际意图/权限升级/歧义/未知效果/破坏性影响增加确认。
九类页面不靠抽屉中的嵌套通用字段替代，关键状态不以原始异常或 token 呈现。
窄屏、键盘、深链、返回、空态、无权限、不可用及过期输入均能完成同样的用户结果。

## Safety Invariants

1. Scan/Discovery、Parse、Recognition、Metadata、Naming、Classification、Planner 和摘要分析
   全部零 Storage mutation；读取/刷新/切换标签不创建工作或调用 Provider。
2. OrganizerExecutor-only mutation，Storage confinement/capabilities、无静默 fallback、
   明确许可的覆盖/删除/来源清理、审计/脱敏、RBAC 不变。
3. ResourceLibrary→实时 Storage 是 Files 来源权威；MediaLibrary 非整理源；FileIndex 不变成
   物理源路径/执行权威，结果同步失败不引发重放。
4. 不可变配置与精确来源/计划/选择绑定、乐观并发、claim/lease/fence 和原子准入保留；
   当前 Active 不替代合法旧 pin，已消费/撤销许可不因 Continue 重新获得。
5. 逐项状态独立；成功、忽略及不确定 effects 不自动重试；未知提交先查持久状态。
6. RecognitionType C 复用 A 策略后仍是 C；Provider 接口、secret-free 解释和无 FFprobe 不变。
7. 保留无关用户脏文件、参考图删除意图、私有 ignored 配置及不可变已审历史。

## Explicitly Deferred

- 冻结 Slice43 的页面、定义绑定模式退役、Run once、指标与实际全局设置消费；不得导入其未接受实现。
- 整体 DryRun 退役、Rules 测试删除、其他诊断命令或 Provider/身份/配置体系重设计。
- 跨任务批量 mutation、批量覆盖、历史删除/保留策略、任意旧结果 Reprocess、通用回滚、
  不确定 mutation 自动重放、V1 UI 全面退役。
- 新 Storage/Metadata Provider、Upload/Download、MediaLibrary Organize、新调度/并行执行引擎。
- 超出现有有界发现/主文件限制、自动拆大批、保证所有旧 discovery 异常无缝续跑。
- 已闭合 Slice 的非阻塞清理和无关页面重构；后续未确认产品点不自动进入本 Slice。

## Slice Acceptance Criteria

- AC-1：九个标签和列表真实可达；查询覆盖完整授权总体，任务/文件数、重叠视图和多页筛选一致；
  不可用不显示零，历史名称/身份不因当前配置变化而改写。
- AC-2：单项、多项、文件夹新建整理在同页完成摘要与精确子集确认，未确认零媒体变更；
  附件、未就绪、边界不完整和破坏性影响均清楚，准入/响应丢失不重复执行。
- AC-3：每类恢复从跨任务列表到任务内文件处理、同页新摘要及确认继续完整可用；
  多问题/多任务互不覆盖，解除和新阻塞正确反映，原始历史和成功兄弟项保留。
- AC-4：详情、记录、导出、可用控制、Worker 等待与重连/重启恢复真实；
  原 Task/Job 深链可诊断，主旅程不回退 CLI/V1 或独立 Preview。
- AC-5：独立 Scan 在 Web/API/CLI/非定义绑定执行路径完整退役，旧入口不暗中执行；
  内部整理发现/稳定性和旧历史可用，不再提示先跑已删除功能。
- AC-6：架构与全部安全不变量通过验证，C→A 策略身份回归通过；
  文档/视觉状态、CURRENT/TARGET、受测候选与证据真实一致，未完成项不冒充交付。

## Final Validation Expectations

Final Test Level 为 T4；本次激活文档只执行治理/链接/图片完整性/范围/私有文件和 whitespace 检查。
实现候选按 workflow 分阶段验证，B 在各 Task 给出精确命令、风险与独立关键复现，最终至少覆盖：

- 全 Python regression：`python -m unittest discover -s tests`；
  quality 中适用的 `ruff format --check .`、`ruff check .`、
  `python -m compileall -q mediaflow tests scripts`、依赖/示例配置及禁止依赖审计。
- Web typecheck/lint/format、完整 unit/component tests 与 production build；
  实际构建产物上的原生九页面视觉、窄屏/键盘/深链/重连、各恢复及完整创建确认旅程。
- Real-Python API/SQLite/Worker 浏览器证明：跨页全总体计数、混合类型/逐项解除、准入去重、
  来源变化、未知提交核对、配置 pin、协作控制、恢复与不确定 effects 非重放。
- 实际 mutation 使用临时 Local / fake / local-server Storage、假 Provider，检查操作及权限；
  不接生产媒体/外部生产服务，分析段以 mutation/Provider 计数等证明其边界。
- 涉及 schema 时验证真实旧版本迁移/重开及失败原子性；涉及安装、生产产物/Worker 装配时验证
  wheel/Docker 内同一确认/恢复路径及常驻消费，不以 mock 替代实际边界。
- 对 9 张实际截图及布局作视觉检查；例图数量不当作测试常量，缺失外部门禁明确披露。

证据保存和复用按 workflow，完整 source SHA、实际命令、配置/依赖、结果计数及原始日志位于
耐久证据索引；文档/报告 successor 只在明确证明 executable inputs 不变时复用。
B 在满足全部 Required Outcomes 后提交一个 Closure Packet，停止继续生成微型 Task。

## Closure Packet

Not submitted. No implementation Task or final executable validation exists.

## A Final Review

Reviewed Range: NOT REVIEWED
Decision: NOT REVIEWED
P0/P1 Blockers: NOT ASSESSED
Closure Reconciliation: NOT PERFORMED
