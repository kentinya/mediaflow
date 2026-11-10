# Slice 54 — 整理规则统一弹窗与可读性

```text
Slice ID: 54
Name: Organizing Rules Dialogs and Readability
Owner: A — Slice Owner / Architect / Final Reviewer
Status: READY FOR A REVIEW
Base SHA: e43a40674eb14aa12615a440a348fe675cd50c4e
Implementation Head: aef044e51dc91655372bf5fe39c6116da976c3b4
Working Branch: main
Development Authorization: TASK54.1 IMPLEMENTATION USER AUTHORIZED ON 2026-11-10
Risk: High
Accepted Test Level: T4
Next Action: A FINAL REVIEW OF ENTIRE SLICE BASE..IMPLEMENTATION HEAD
```

## Authority and accepted baseline

用户先授权只读调查：概览保留完整流程验证，其他规则表面只保留单项检查；七类添加
改为与自动化／文件页协调的居中弹窗。随后补充七类编辑也改为弹窗，并改善这些表单
内容的美观与可读性。2026-11-10 用户先授权 A 规划，合同提交于 022d7777；随后明确
“激活 Slice 并代替 B 规划第一个 Task”。本次将 Slice 激活并先提交合同，再由 A 按用户
授权代行 B 规划首个 Task。该角色例外仅限本次 Task 规划，不包含自审实现或代行最终
A 验收。用户随后明确“激活 Task”，正式授权 Task54.1 实施；原 Task ID／Base／Goal／Scope
保持，移除规划草案通知。Task54.1 经 Developer 实施与同一 Task 修正，现由 B 独立
复核 PASS；本 Slice 已提交 Closure Packet，等待 A 最终验收，尚未接受或关闭。

Slice53 已于 2026-11-10 **PASS / CLOSED**，原 Base、接受实现、A53-01 原退回／修正、
验证限制及 B 转任 A 的用户授权例外均保留于
[固定关闭记录](https://github.com/kentinya/mediaflow/blob/8bc3ef905a76b96ef8ec327154b92e9b9972ea05/SLICE.md#closure-packet-and-a-final-review)。
本 Slice 不重开 Slice41／44／50／53；当前接受基线为
`e43a40674eb14aa12615a440a348fe675cd50c4e`。Base 固定，后续纯规划／激活提交不重设；
若实现前出现独立产品变更，A 应先明确基线／范围的合法处理，不能静默重定 Base。
生命周期以 [Development Workflow](docs/development-workflow.md) 为唯一依据。

规划前治理检查 PASS；工作区 `/Users/songzhidong/mediaflow`，分支 `main`，HEAD 如上，
暂存区为空，工作区／Git 可写。预存 `mediaflow/.DS_Store` 修改及未跟踪系统元数据、
`.explore_adapter_block.py`、日志、`15` 和 `output/` 调查材料原样保留，不进入本检查点。
调查检查七类共用表单／测试／编辑路由；使用已有构建和隔离 Node 假服务实际查看命名、
分类添加界面。假服务清单对象的编辑投影缺失不能当成产品缺陷；该调查不等于当前源码
构建或真实 Python 编辑旅程验收。未读取运行数据库、私有配置、凭据或用户媒体。

## User goal and requirement mapping

用户从整理规则的任一分类清单添加、复制或编辑对象，在原列表背景上的协调弹窗内
理解并修改规则、显式运行当前对象测试、一次保存发布，返回原清单确认真实结果。
表单按业务目的组织，关键设置、测试结论与纠正动作清晰；完整流程只在概览检查。

| Required Outcome | 完整旅程 | 需求 |
|---|---|---|
| RO-1 七类统一弹窗 | 列表／空态添加、复制、编辑及准确旧编辑链接 → 稳定卡片 → 保存或安全关闭 → 原清单 | TARGET `V2-RULES-010`；`V2-RULES-001/002/007/008`、`V2-UX-001–003/011/013–015` |
| RO-2 内容可读与协调 | 七类设置／内部规则／单项测试 → 有层级的输入和结果 → 直接纠正 → 精确重测／保存 | TARGET `V2-RULES-011`；`V2-RULES-003–009` |
| RO-3 完整流程入口收敛 | 概览完整图检查；其余表单仅当前对象检查 → 各自结论／失效／恢复 | TARGET `V2-RULES-012`；`V2-RULES-006/009` |

本合同是 **TARGET / ACTIVE**，未交付、不改称 CURRENT。见
[V2 TARGET](docs/v2-requirements.md#target--organizing-rules-dialogs-and-readability-slice54-active)、
[完整 TARGET 旅程](docs/product-experience.md#target--organizing-rules-dialogs-and-readability-slice54-active) 和
[架构 TARGET](docs/architecture.md#target--organizing-rules-dialogs-and-readability-slice54-active)。
接受后替换既有 Rules Add／Copy 抽屉、独立整页 Edit 及编辑器内完整链路预览的呈现约定；
当前发布、安全、识别身份、局部分析和共享完整规划的业务语义保持。

## Required outcomes and surfaces

### RO-1 — 七类添加／复制／编辑统一弹窗

覆盖类型策略、识别类型、识别规则、元数据策略、命名规则、分类规则、整理策略。
顶部与空列表添加、每行复制／编辑使用同一视觉体系；不同对象不串输入、权限、响应或
测试证据。默认仍是八区导航和完整清单，不自动选中或弹出表单。

以现有自动化新建／编辑及文件页库配置卡片为视觉基准，优先复用业务无关公共 modal。
圆角、遮罩、阴影、标题、按钮、间距、开关动效协调；按规则复杂度安排内容，不复制
自动化字段或库配置步骤。标题显示动作、类别和可读名称；精确 ID 保持可查且编辑不可改。
正文内部滚动，标题／关闭／底栏稳定可达；读取权限和对象、失败与就绪不从矮壳突然撑大
重新居中。背景位置／宽度稳定，原分类、搜索、状态筛选和滚动保留。

现有 `/ui-v2/rules/edit/{family}/{objectId}` 的合法链接、刷新、前后退和重认证仍准确
打开同一对象的弹窗；直接进入时提供对应分类清单作为背景及默认关闭去向。不保留
第二套独立整页编辑体验，不以改 ID 或返回错误分类作兼容。合法特殊字符 ID 仍可用。

保存期间所有退出途径共同保护在途命令并阻止重复提交；未保存关闭／返回提供清楚的
继续编辑／明确放弃选择。Escape、Tab、回焦、背景不可交互／锁滚、窄屏和 reduced-motion
可用。不能用两次关闭手势代替明确放弃决定。表单输入按类别／对象隔离并保持已有
刷新／重认证恢复能力；不保存凭据或将草稿显示为 Active。

一次明确保存仍校验并原子发布完整后继。成功读回／更新清单并回到原清单，显示真实
保存结果；后续清单读取失败不能抹掉已知发布或自动重提。校验、引用、权限、并发拒绝
保留旧 Active 与可修正输入；未知保存说明可能已发布、保留核对入口，不能因关闭／
重开或换对象自动重发、借新弹窗误报未保存，核对前不提供无保护的重复提交。

### RO-2 — 七类设置与单项测试内容可读

设置与单项测试在卡内有明确分区／切换，保留当前输入、样本和证据；不再把所有配置、
长篇说明、全部样本和历史结果平铺成一条长表单。简单类型不强塞复杂步骤；复杂条件
必须能在卡内完成，不借可读性删除已有字段、隐藏生效设置或生成业务默认值。

| 类别 | 必需内容结果 |
|---|---|
| 识别类型 | 基本定义、说明与启用状态紧凑清晰；无需下游绑定即可检查定义，关联规则试识别保持可选。 |
| 识别规则 | 清楚呈现“哪些条件 → 哪个识别类型”；优先级／分数／停止匹配解释就近，AND／OR／NOT 层级与条件操作可读。 |
| 类型策略 | 类型与四个下游策略关联一眼可辨，名称优先、ID 可查；缺失／禁用／重复启用引用能定位纠正，复用不改类型。 |
| 元数据策略 | 服务／查询、语言／地区、候选接受阈值与高级请求限制合理分组；单位、范围和凭据状态清楚，不展示密钥。 |
| 命名规则 | 电影／剧集模板分明，变量帮助集中可查，不在每字段重复整串；长模板可读可编辑，真实单项渲染能对照目录／文件名与缺失原因。 |
| 分类规则 | 内部规则清单与当前规则编辑层级明确，条件、优先级、目标媒体库和相对路径可读；复杂表格不依赖整页横向溢出，内部“完成”与最终“保存”意图区分。 |
| 整理策略 | 操作／冲突、附件、重复检测及回滚／清理分组，枚举有可懂中文、数值有单位；覆盖／删除等实际危险影响就近明确，不默认授权或承诺万能回滚。 |

统一表单标签、控件、帮助、错误、按钮和结果样式，包含当前缺少配套 CSS 的
`RulesObjectTestPanel` 及分类内部动作。单项测试保留必要样本，按当前类型／用途组织，
显示真实作用域；默认先看结论、实际输出、失败原因和下一步。技术 family、修订／版本、
原始类别、调用统计及完整 JSON 放入诊断展开，不作为普通操作前置条件。不能用隐藏
真实阻塞、截断关键路径、删除证据或一律绿色成功来美化。样本、输入、Active／对象
变化后证据失效，迟到响应不覆盖新上下文；失败与未知保持可辨。

### RO-3 — 仅概览保留完整流程检查

概览保留显式 `完整流程检查`，基于读取到的精确 Active 完整图，保留真实竞争、策略
解析、合成身份标记、必要只读目标检查及单独实时元数据意图。
七类添加／复制／编辑全部移除 `完整链路预览（既有能力）` 及其完整链路表单／按钮，
不是折叠隐藏。各对象只提供自身及必要依赖的单项测试，不增加旁路完整流程入口。

单项结果不能宣称全图就绪、发布成功或执行授权；如需全流程，清楚引导到概览并说明
它检查已发布 Active，尚未保存的候选不会被偷偷代入。保存仍独立校验完整后继及适用
发布证据，不能因删检查 UI 而降低检查；共享后端分析／DryRun／配置／自动化预检和
既有 API 语义保留，本 Slice 不做完整测试后端退役。

必需表面：Rules 清单入口／空态／路由、七类表单与嵌套条件／分类内部规则、局部测试
输入／结果／诊断、概览检查分界、必要公共 modal、直接受影响测试和交付时文档协调。
清单只做支持弹窗返回与正确状态所需调整；八区导航、表格整体与概览布局不另行重设计。

## Safety invariants and explicit deferrals

- 后端 RBAC、精确 Active 基线、并发拒绝、完整后继检查、原子激活、引用保护、隐藏配置
  保留和审计脱敏不变。草稿／局部成功不是 Active；未知保存先核对，不自动重放。
- 打开、编辑、切换、关闭、刷新不发布／创建可执行 Task／访问 Provider。显式离线局部
  测试零 Provider／媒体 Storage I/O；实时元数据需明确意图，完整检查只做既有有界只读观察。
- RecognitionType C 使用 A 命名／分类后仍为 C，保留自动化测试；Naming／Classification
  不突变 Storage，只有 OrganizerExecutor 可按原明确授权变更媒体。
- 新建分类保持 MediaLibrary＋安全 path；旧 library/path 只可明确转换，历史 pins 不重写。
  保留真实规则竞争、模板、Provider 抽象及附件／冲突／高风险权限语义，不做前端第二引擎。
- 公共组件仅作必要兼容扩展，自动化、Files／MediaLibrary、存储与任务详情／恢复消费者
  保持已接受行为；尤其不改 Slice53 的原请求核对、逐文件整理与准确 Task 交接。

延期：新规则字段／条件／算法、Provider／Storage 操作、schema、权限／配置发布协议、
队列／执行引擎／恢复模型、全站主题或动效设置、规则批量修改／导入导出／版本差异／
回滚产品、V1 切换／UI 改造、完整测试 API／后端退役、概览／清单整体重设计、其他页面
业务改造、生产服务／用户媒体验证、推送、发布及部署。不得借可读性改写枚举值或危险默认。

## Acceptance and final validation

1. 七类的添加（含空态）、复制、编辑均为协调居中弹窗；列表保留，保存回到准确分类并
   展示真实结果。七类现有字段、嵌套编辑、状态能力、值回填和不可变 ID 均完整。
2. 旧编辑链接与特殊 ID 的直达／刷新／重认证及浏览器前后退进入准确弹窗；普通打开关闭
   保留分类／筛选／滚动／焦点，不触发整页切换动画、不意外丢稿或串对象。
3. 七类设置与单项测试按 RO-2 可读；桌面同视口改前／改后及自动化／库配置参考对照，
   390px 窄屏与矮窗口中，复杂条件、多条分类规则、长模板／名称／路径和错误结果可操作。
   检查真实中间过程：慢权限／对象读取、就绪、错误、开关动效及 reduced-motion。
4. 明确测试只提交当前候选及必要样本；局部成功／非匹配／不适用／阻塞／失败真实，编辑
   后证据失效、迟到结果不串项，实时 Provider 不自动调用；完整证据仍可查看。
5. 完整流程只在概览可操作；添加／复制／编辑没有旧链路区域或按钮。概览精确 Active
   全图结果、保存全图校验和共享 API／后端能力保持。
6. 一次保存成功、无效输入、缺失／禁用引用、权限拒绝、并发发布、读取失败及未知保存
   的完整恢复旅程；所有退出方式遵守在途／未保存保护，已发布／未知命令不自动重发。
7. 公共 modal、自动化／两种库／存储／任务详情及 Slice53 交接的直接影响回归；C→A
   仍为 C、零媒体变更、审计脱敏、pins／fences 和已完成／不确定效果非重放保持。

T4 因七类表单直接承载 Active 配置发布、危险策略输入和未知保存／导航状态交接而选择，
不是要求新后端能力。Developer 负责新改及直接受影响测试；B 负责固定 Base..candidate
审查、七类真实 Python／API／临时 SQLite 的完整旅程、实际视觉／键盘验收和适用
[共享全量门禁](docs/development-workflow.md#shared-full-regression-commands)，包括精确新构建／
安装 smoke。外部 Provider 用本地假服务，Storage 用临时根；生产服务不是必需验收环境。
无容器执行路径变更时 Docker 广域矩阵不适用，B 说明依据并保留失败／跳过／未运行限制。
首个 Task 由 A 按本次明确授权代行 B 规划，依据实际代码组织连贯行为，不按七类、字段或纯技术层机械拆分。

## Closure Packet and A Final Review

~~~text
Slice: 54
Base SHA: e43a40674eb14aa12615a440a348fe675cd50c4e
Implementation Head: aef044e51dc91655372bf5fe39c6116da976c3b4
Last Product Checkpoint: 2aedd74e1085aa42c96fe7b438ee3ffc606572d7
Required Outcomes and Surfaces: COMPLETE
Tasks completed: Task54.1 — B PASS (High / T4)
Decision: SLICE READY FOR A REVIEW
A Final Review: PENDING
~~~

### Outcome / Surface coverage

| Required Outcome | B 的完整结果核对 |
|---|---|
| RO-1 | 七类 Add／Copy／Edit 共 21 个真实入口共用清单背景上的居中卡片；旧链接／特殊 ID、刷新／重认证、草稿模式隔离、Back／继续、退出与在途保护、准确发布及未知核对完成。搜索 `Normal`→编辑→取消时页头／导航／表格全程 y=78／158／375，七类返回及 390px 已滚动背景保持 |
| RO-2 | 七类设置与单项测试的内容矩阵完整；名称／ID、条件与输出、四策略引用、Metadata 分组、模板帮助、分类内部编辑及操作／附件／高风险权限保持。桌面、390px、矮窗口的复杂条件、模板／路径、多条分类规则、错误与慢读取／失败恢复可读可操作；局部结论／输出／原因／下一步与诊断分层 |
| RO-3 | 三模式移除表单完整链路区域与动作；概览保持显式精确 Active 完整检查，未保存候选只做局部分析，保存仍校验完整后继。共享 preview／Python 能力保留，无旁路入口 |

固定 Task 审查范围为 `6351b60433f0e79dac6f5f7150884a1fecb0da43` 到上述 Head；B 已重评
全部 Slice 结果与表面，不再规划 Task。最后产品检查点后的提交仅为交接文字。
详细验收、命令与原始失败说明见 [B final Task review](TASK.md#b-final-task-review)。

### Final tests and safety evidence

本机证据根目录 `.git/validation-evidence/aef044e5/task54-1-b/`：Python 2678 tests OK
（7 个既有外部服务／endurance skip），Web 99 文件／1516 项、Node E2E 268 项 PASS；
新生产资产、类型／lint／format、受版本控制 Python 的 Ruff、compileall、配置验证、
新 wheel 与源码外安装 smoke PASS。根 Ruff 扫到预存未跟踪调查文件的语法失败保留。

Rules 主原生、analysis／identity／classification 三项原生证明与补充恢复／视觉矩阵
通过；七类局部分析零 Provider／媒体 Storage 读取，C 使用 A 命名／分类仍为 C。
真实 409 后采用／复核所用对象、基线与分析一致；真实发布后丢响应保留原请求，
刷新后没有第二次 PUT。打开／测试不创建执行工作，已接受的领域与权限语义保持。

共享消费者：自动化最终 35 项、存储 8 项、整理／Task 交接 10 项、包含两种库实际保存
的原生用例 1 项 PASS；两种库取消返回背景稳定且参考旅程零写。自动化首次运行有
1 项因连续复制时清单尚未读完而没有发出第二次请求，原失败／trace、单项诊断及
最终完整结果全部保留，详见 Task。未通过修改用例或重试配置掩盖原失败。

### Known non-blocking issues / explicit deferrals

无剩余 Task 或 Slice 结果阻塞。上述自动化用例的读取就绪时序作为非阻塞验证记录
保留。外部服务／endurance 未运行；无 Docker／依赖／容器路径变更，广域 Docker
矩阵不适用。本机证据未声明为远程 CI，原合同的延期及既有接受边界保持。

### Documentation reconciliation needed / A handoff

A 审查完整 `Base SHA..Implementation Head` 并作最终决定；本包不宣告 Slice PASS／CLOSED。
A 接受后一次协调 Requirements、V2 Requirements、Product Experience、Architecture、
`docs/configuration.md` 的抽屉／整页／旧表单完整预览 CURRENT／TARGET 措辞，以及
Roadmap／Progress／根 Task 的关闭事实。B 本次不更新 Roadmap／Progress 或提前转换
TARGET；保留 Slice41／44／50／53 的接受身份、原证据与延期。

可复用经验候选：列表内弹窗路由复用后，同时核对 Shell 的搜索／位置行与原背景；
新卡片自己的几何稳定并不能证明背景稳定。A 收尾时按各角色经验规则决定是否合并。
