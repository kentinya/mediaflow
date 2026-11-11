# Task PATCH-20261112-1 — 整理窗口整体美化与保存分析入口统一

Authority: 用户明确要求删除“继续此条目的安全分析”，不是按状态隐藏，也不新增
“重新分析”替代按钮；已有“保存并重新分析”承接保存与必要的分析恢复。同时改善
整理窗口内部内容不协调、不美观及状态交接跳变的问题。依据
[Development Workflow §3.1](docs/development-workflow.md#31-independent-minor-bugs)
作为现有整理／恢复行为的独立修复，不重开已接受 Slice。
角色经验见 [B](docs/agent-experience/task-planner-reviewer.md) 与
[Developer](docs/agent-experience/developer-implementation-role.md)。

用户于 2026-11-12 明确“激活Task”，正式授权本 Task 实施。原规划检查点为
`3a4b70a78aa8b967503d5a1ad89bce2cd4ccc164`；本次仅激活，移除无活动实施及规划草案通知，
原 Task ID／Base／Goal／Scope、Medium / T3 和测试分工保持。该激活检查点未启动
Developer 或其他代理；本轮实施依据用户随后明确授权，不推送或部署。

```text
Task ID: PATCH-20261112-1
Task Type: STANDALONE MINOR BUG
Parent Slice: NONE
Status: READY FOR B REVIEW
Task Base: 32bb37262777ae945deb8af4a51d9109876ca804
Difficulty: Medium
Test Level: T3
Planner / Reviewer: B
Development Authorization: IMPLEMENTATION USER AUTHORIZED ON 2026-11-12
```

规划前与激活前治理检查均 PASS。工作区 `/Users/songzhidong/mediaflow`，分支 `main`，
规划时 HEAD 为上述 Base，激活前 HEAD 为上述规划检查点；暂存区／工作区干净，
Task 文件及 Git 可写。本次只修改根 `TASK.md`；Slice54 的原 Base／接受 Head／
PASS / CLOSED、Roadmap／Progress 保持。PATCH-20261111-2 的历史接受保持；
PATCH-20261111-5 已独立 B PASS，完整审查范围为
`436117e0588d30794dc3ee17d4fc1d0988a79442..408b5303cdabad202188ed252ceaa741159cdeaa`，
原结果／失败与证据保留于[固定 B 验收](https://github.com/kentinya/mediaflow/blob/eced270336a93e93c128fbf274eb0537effbaed2/TASK.md#b-final-review--patch-20261111-5-pass)。本 Task 依据
用户本轮明确收敛后的入口及窗口可读性要求修正，不把先前“异常时保留独立按钮”继续
当作验收标准。整体美化覆盖现有整理窗口，不新增产品能力、执行步骤或新的恢复模型。

## Goal

用户从资源库 Files 单项／批量／文件夹整理或任务中心的合法“继续整理”进入同一个
协调、可读的整理窗口，先看到当前文件与最需要完成的操作，再检查作品／来源→目标／
附件／危险影响，最后复核精确子集并明确确认。准备、等待、失败、只读历史等状态使用
同一视觉层级，保留准确上下文与可用的下一步，不靠堆叠重复提示或技术字段解释流程。

在该弹窗及任务中心共用的识别／元数据／分类／冲突处理内，用户选择
合法决定后，只使用一个“保存并重新分析”动作：保存未保存的决定，再请求零变更分析；
若决定已保存而分析明确未受理，则再次使用同一动作仅补做分析。成功进入精确方案，
按原入口明确确认执行；无需理解第二套“安全分析”步骤。

“继续此条目的安全分析”独立按钮及其紧邻说明在正常、中间、失败、刷新／重开状态下
彻底移除，不改名、不折叠、不搬到另一处；不新增独立“重新分析”按钮。必要的已保存／
分析未受理／等待中／未知／读取失败事实继续就近显示，原只读核对入口保留。

### Actual gap and applicable journey

- `TaskItemRecoveryPanel.saveDecision` 已串联 `/recovery/decision` 与 `/recovery/continue`。
  保存响应写入缓存后，决定表单会因 `decision=null` 消失；`continueAt` 成功只更新消息／
  失效读取，随后 `finishAction` 清除 busy，未把已受理的同 Task 分析纳入完整动作状态。
- `needsExplicitAnalysisAction` 仍渲染两个模式下的独立按钮；其排队判断只看
  `checkpoint.continuationStatus`。真实 Files 同 Task 分析走 `nativeAnalysis`／discovery，
  不生成旧式 `recovery_continuation`，故成功受理后仍可能满足 `retry` 显示条件。
- 本会话在 Base 的新构建＋真实 Python API／临时 SQLite／模拟 Provider 中复现：
  decision 返回 200、continue 返回 202 后，旧按钮仍可用，新计划发布后才消失。
  属于弹窗内错误中间态，不是另一个页面跳转。原相关单元 39/39 通过不能覆盖该缺口，
  因已有 queued/running 夹具使用带 `recovery_continuation` 的另一种状态。
- 现有队列拒绝测试明确期待独立按钮；仅删 JSX 会导致已保存决定没有后续动作。
  `ManualOrganizeDialog` 自有选择表单也会把原按钮文案切为“重新分析”，本 Task 的
  逐文件入口统一要求同一个“保存并重新分析”，不能留下该替代文案分支。
- `renderReview` 当前依次平铺作品匹配、来源到目标、操作及附件、当前问题，问题决定
  嵌在最下面。人工选作品前尚无目标方案，仍先显示多项“—”、重复的来源／操作及安全
  说明；1440×1000 实际窗口中候选操作排在首屏以下。`dt/dd` 逐项纵排、嵌套小标题／
  卡片／刷新和两个技术诊断入口缺少清晰层级。分析前后的候选卡、普通修正表单与提示
  替换还会改变正文高度和滚动位置。现有 CSS 多用所有 section 的统一下边框，无法区分
  当前主动作、方案信息与次要证据；需要内容结构与样式一起修正，不只调整颜色或留白。

需求映射：`REQ-RECOVERY-006/007/009`、`V2-OPS-007/008/016/018/019`、
`V2-TASK-003/014`、`V2-UX-001–004/011/013–015`。完整旅程为
[Manual organize 与逐项弹窗](docs/product-experience.md#manual-organize)、
[Tasks, results and per-item recovery](docs/product-experience.md#tasks-results-and-per-item-recovery)
及 [Task Center §4](docs/task-center-page-spec.md#4-四类恢复决定--分析--摘要确认--真实结果)。
遵循 [CURRENT organizer contract](docs/architecture.md#current--manual-organize-dialog-slice53-pass--closed)
及 Tasks recovery 契约；用户本轮要求收敛异常恢复入口，不取消必要分析或改变执行授权。

## Implementation Scope

主要表面：`ManualOrganizeDialog.tsx` 的完整窗口（准备／发现／分析、逐项复核、合法修正、
整批确认、失败／未知核对、原历史地址的只读态）、`TaskItemRecoveryPanel.tsx` 的
full／decision 模式、`task-item-recovery-session.tsx`、局部 `styles.css` 及直接相关查询／模型／测试。
沿用既有 API／同 Task 分析／精确摘要／请求核对；必要时组合既有 discovery、Task、
recovery 读取及已有响应字段，不创建第二个工作流或本地执行权威。

1. **先补真实缺口用例。** 模拟真实 native-analysis 响应及没有旧式续作记录的后续读取，
   有意延后 continue 响应、刷新读取和新计划发布。持续观察保存前至方案就绪的 DOM，
   证明正常成功以及各交接窗口均无独立按钮；不能仅对最终截图或最终文案断言。
2. **彻底移除独立呈现。** 删除 full／decision 两套独立安全分析按钮及其专属说明／
   空操作容器，清理仅服务该呈现的判断。逐文件决定与修正统一使用现有
   “保存并重新分析”（在途可显示“正在保存并重新分析…”），不新增第二按钮，不以
   改名、折叠或另一个区域保留等价独立入口。Metadata 搜索、忽略、刷新、摘要生成／
   确认与读取原状态是不同目的的既有操作，保持各自合法边界。
3. **让同一个动作处理实际阶段。** 把原决定表单的提交区与可消失的决定输入解耦：
   决定已保存不再有输入时，原位置仍能展示其保存／分析结果，并在后端允许且已证明
   分析未受理时使用同一“保存并重新分析”补做分析。未保存输入要先保存，保存失败
   不请求分析；已保存且未改的决定只使用当前合法 checkpoint 请求分析，不再 POST
   decision、不重新搜索 Provider，也不要求重选候选。不能靠重交已解决决定实现恢复。
4. **以真实工作状态保护再次操作。** 处理下表，尤其不能只用“曾点击／曾成功”的本地
   布尔值永久锁住，也不能仅看旧式续作字段或一次成功 GET 就解除未知请求限制。

   | 当前事实 | 同一动作与下一步 |
   |---|---|
   | 合法决定未保存 | 用户点击后保存一次，再请求一次分析；无效输入保留纠正，不调用分析 |
   | 保存明确失败 | 保留当前输入与失败原因；同一动作允许合法纠正后再提交 |
   | 决定已保存，分析明确被 queue_full／capacity_full 拒绝 | 显示“选择已保存、分析未受理、文件未修改”；再次点击同一动作仅请求分析 |
   | 分析请求在途、已受理、排队或运行 | 显示等待状态并阻止重复提交；包括 nativeAnalysis／旧式续作，等待真实新方案 |
   | 决定或分析响应未知 | 保持精确请求上下文与提交保护；用既有只读核对，不能自动重发或把旧 retry 当未受理证明 |
   | 已有当前可确认方案／已确认执行 | 进入原摘要／确认或结果；不提供无意义重复分析，不以旧缓存覆盖持久事实 |
   | 方案失效，后端明确允许重新分析 | 通过同一动作请求当前合法分析；已保存输入不重复写；不拿失效方案确认 |
   | 新四类阻塞／纯技术终态／未知文件效果 | 新阻塞显示自己的合法决定；技术终态及未知效果保持既有只读、非重放边界 |

5. **刷新／重开与兄弟隔离。** 复用当前主体／Task／item 的既有 session／durable 读取，
   关闭重开、翻页返回、类型筛选、刷新／重认证后重新辨明已保存与分析状态；读取不自动
   调用 continue／decision／Provider。无法证明状态时先保留读取与核对，不能伪造未受理
   或按最新 Task／其他文件判断。迟到响应不串项，不覆盖另一个文件草稿，不重放成功兄弟。
6. **直接消费者与交付协调。** 回归 Files 弹窗、任务详情和四类恢复（元数据含候选与
   修正）共用入口；默认 full 表单的旧“保存决策并继续安全分析”也归一为
   “保存并重新分析”。full 模式只改本入口及必要的状态呈现，任务中心整体详情不重设计。
   实施交付时仅同步 Product Experience／Task Center §4 中本窗口呈现与入口操作表述：
   说明主动作／方案／证据的层级、分析失败仍用同一动作恢复，不再暗示独立重试按钮；
   必要的 CURRENT 架构说明只协调前端读取／动作及窗口呈现关系，不改已接受引擎契约。
   规划与激活检查点只写 Task，这些同步随产品修复交付。
7. **整体重组整理窗口内容。** 参考现有 Files 新建／编辑库、Automation 新建／编辑卡片
   的字号、控件、间距、圆角、提示与按钮层级，复用 `modal-card.tsx`。具体结果如下：

   | 窗口区域／状态 | 必需呈现结果 |
   |---|---|
   | 固定标题与底栏 | 标题简洁，当前文件／第 i/N 个／业务状态有明确层级；翻页、关闭、整批复核／最终确认分组，桌面不拥挤，窄屏可换行且所有动作可达 |
   | 初始受理／发现／等待分析 | 紧凑显示真实阶段、必要进度／排除原因与当前下一步；外壳不从矮框突然撑大，不展示虚构的空方案 |
   | 需要人工决定 | 当前问题、必要的匹配信息和候选／修正表单优先可见；不先滚过尚未生成的目标、操作和空附件块。典型桌面双候选可见候选及保存动作；多候选／复杂输入在正文内自然滚动 |
   | 已有可读方案 | 作品身份紧凑、来源→目标关系清楚，操作及来源是否保留就近；避免作品／操作／来源的重复平铺。普通修正可按需展开，已采用作品与另行编辑意图区分，不丢当前输入 |
   | 附件与诊断 | 附件数量与重要警告先可见，展开可读每项准确来源／目标／操作。Provider/ID、精确策略／版本／原始依据等按目的集中诊断，避免两个同名无区分入口；不隐藏阻塞或危险影响 |
   | 保存／分析／失败交接 | 一个主要状态位置说明阶段、已保存内容与下一步，减少重复“不会执行”段落。保存区稳定，候选消失不会暴露旧入口；新方案出现不突然把当前文件或操作滚走 |
   | 整批复核 | 已选数量、每项来源／目标／操作、未纳入原因和必要危险授权有清楚主次；长路径可读，多项清单内部滚动；原精确子集与一次最终确认保持 |
   | 历史只读／不可读／未知 | 使用同一视觉体系，明确真实状态、已知效果与合法只读核对；不为对称布局增加不可用动作或重新赋予执行入口 |

   可合并／重排重复来源和操作字段，未生成的信息用一条准确状态说明替代成片“—”；
   不删除其后就绪方案的完整来源／目标，不把缺失数据伪造成空成功。技术 ID 可展开，
   作品标题／年份／类型、候选可区分信息、精确路径、失败原因及危险影响仍可查。
   不新增图片／外部请求或依靠海报装饰解决内容层级问题。
8. **只在整理窗口范围应用样式与交互。** 用明确的局部分区类组织样式，避免递归
   section／dt／dd 规则误伤状态横幅与嵌套表单。保留提示水平留白、背景位置／目录／
   选择、标题／底栏稳定、正文滚动、焦点／Escape／Tab／回焦、在途与未保存退出保护。
   状态切换按同一文件／草稿保持合理滚动，不强制每次归顶；不以固定遮盖、截断路径、
   隐藏错误或无法抵达的按钮换取“稳定”。若确需兼容扩展公共 modal，验证直接消费者，
   不顺带重做 Storage／Automation／库配置或任务中心详情的其他布局。

服务端权限、checkpoint/version/fence、原 pin、decision／continue endpoint、原子准入、
队列／Worker／执行引擎、Storage 语义与数据库 schema 不改。`retry` 是后端合法能力而非
必须单独呈现的按钮，不能从后端抹掉它。若现有读取确实不足、必须改变上述契约，
先交 B 评估 Task 范围／Test Level，不在本 Task 按纯 UI 修正静默扩张。

## Acceptance Criteria

- [ ] Files 弹窗与任务中心 full／decision 的识别、元数据候选／修正、分类、冲突中，
      独立“继续此条目的安全分析”按钮、紧邻专属说明及空动作区完全消失，正常／异常／
      中间态／重开均不出现；没有改名或新增独立“重新分析”替代入口。
- [ ] 同一条目只有一个保存分析入口，文案为“保存并重新分析”；一次合法选择只产生
      一次 decision 和一次 continue，进入新方案后使用原精确子集确认。所有读取／翻页
      不自动发命令，不新增逐文件执行确认。
- [ ] 原报告的真实 nativeAnalysis 路径中，保存后 continue 返回 202、GET 仍带 retry
      且 recovery_continuation 为空时，不闪旧入口、不误导再次提交；慢 Worker 下保持真实
      等待，直到计划发布或真实失败，不以延时隐藏或加快轮询掩盖错误。
- [ ] queue_full／capacity_full：已保存决定与输入事实可见，用户再次点同一按钮只补做
      分析；刷新／关闭重开仍可完成，不重复保存、不重新选作品／搜索、不自动重试。
- [ ] 保存失败、过期 checkpoint、权限拒绝、读取失败、未知 decision／continue 响应均
      有明确阶段、持久状态、已知效果与下一步；未知先核对，不能重复提交已受理分析。
      当前可确认／已确认摘要优先；失效方案不能确认，必要更新仍从同一动作完成。
- [ ] 文件 A/B、任务与主体的请求／草稿／读取隔离；翻页／筛选／关闭返回保护未保存输入，
      新问题可处理，成功／已受理／效果未知兄弟不重放。保存与分析零媒体变更，覆盖／
      清理仍需原精确摘要许可；纯技术历史不新增重试入口。
- [ ] 整理窗口整体达到上表结果：典型人工双候选在 1440×1000 中不需先翻过空方案即可
      看见候选及保存动作；就绪时能清楚对照作品、来源→目标、操作与附件。分区／字体／
      控件／状态／底栏协调，重复说明与重复业务字段收敛，完整必要证据仍可查看。
- [ ] 准备、慢读取、决定、保存／等待分析、新方案、失败／未知、整批确认、历史只读均
      使用同一视觉体系；外壳和固定动作稳定，正文切换不闪旧入口、不意外跳走当前操作。
      390px 与矮窗口内所有内容及操作可到达，无横向整页溢出、遮挡、截断关键路径或空块。
- [ ] 单项／批量／文件夹、Files 背景／任务继续／合法历史地址保持准确上下文、原选择／
      草稿与退出保护。Tab／Escape／回焦、背景不可交互／锁滚及 reduced-motion 可用。
      必要 CURRENT 旅程／呈现说明随修复协调，不提前把未实现的设计写成已接受能力。

## Required Tests

遵循 [Workflow §6](docs/development-workflow.md#6-test-levels)。T3 因本修复涉及共用前端
请求阶段与真实 API／Worker 状态交接，以及承载确认意图的整个窗口呈现；不改队列、
并发算法、持久化、权限或媒体变更边界。
Developer 负责下面受影响用例，B 独立审查完整 Base..candidate 并完成原生验收。
若实际实施触及上述冻结契约，先由 B 重新评估，必要时提升 T4 及其
[共享全量门禁](docs/development-workflow.md#shared-full-regression-commands)。

### Developer — affected tests

在既有测试补齐／调整断言，不删除原队列失败／未知恢复的行为覆盖：

- full／decision、四类及元数据两个分支的成功、无效输入、拒绝、重要边缘情况；
  nativeAnalysis 与旧式 continuation 两条路径均覆盖。
- 用可控 promise 及 DOM 变化观察覆盖保存→continue→读取→新摘要全阶段，特别是真实
  202 后仍 retry／无旧式续作的间隙；断言动作数量与实际 POST 序列，不能只查旧文案。
- 原失败测试改为同一“保存并重新分析”完成 queue_full 恢复，明确第二次仅 continue，
  decision 总数仍为 1；存储读回后重开也要覆盖，不只依赖局部 session。
- 未知 decision／continue 先核对，读回已受理不重发，读回明确未受理才可显式补做；
  读失败或模糊事实保持保护。不同 item／主体／新草稿及失效摘要不串请求。
- 直接受影响 E2E 的旧按钮／旧提交文案定位改为真实旅程，并补一次慢分析中间态证明。
- 窗口重排后保留当前文件、候选、完整路径、附件、错误／诊断、选择／危险许可及原一次
  确认断言；覆盖复杂内容／慢响应／多项与准确返回。视觉由原生浏览器验收，不为 CSS
  数值或实现 DOM 增加镜像测试；复用现有 modal 键盘／退出行为测试。

cwd `web/`：

```sh
npm run test -- run src/features/operations/TaskItemRecoveryPanel.test.tsx src/features/operations/ManualOrganizeDialog.test.tsx src/features/operations/RunDetailTabs.test.tsx src/features/operations/OrganizePlanConfirmation.test.tsx src/entities/operations/task-item-recovery.test.ts src/shared/ui/modal-card.test.tsx
npm run typecheck
npx eslint src/features/operations/TaskItemRecoveryPanel.tsx src/features/operations/TaskItemRecoveryPanel.test.tsx src/features/operations/task-item-recovery-session.tsx src/features/operations/ManualOrganizeDialog.tsx src/features/operations/ManualOrganizeDialog.test.tsx
npx prettier --check src/features/operations/TaskItemRecoveryPanel.tsx src/features/operations/TaskItemRecoveryPanel.test.tsx src/features/operations/task-item-recovery-session.tsx src/features/operations/ManualOrganizeDialog.tsx src/features/operations/ManualOrganizeDialog.test.tsx
npx prettier --check src/shared/ui/styles.css
```

新增／修改其他文件加入对应直接测试与 lint／format；变更 E2E／harness 时先
`npm run build`，运行本轮新改的原生用例。根目录执行 `python3 scripts/check_governance.py`
与 `git diff --check`。无需 Developer 全仓 Python／Web／E2E 或完整打包矩阵。

### B — acceptance and regression

审查完整固定 Base..candidate，先复现并验证真实同 Task/nativeAnalysis 缺口，再运行：

cwd `web/`：

```sh
npm run typecheck
npm run lint
npm run format:check
npm run build
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/manual-organize-dialog.python.spec.ts
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts --grep 'PATCH-20261111-2|PATCH-20261112-1|a brand-new ambiguous source|a selected execution never blocks|dated views and 21-file recovery'
```

另重跑上述受影响 Web 单元；所有本轮新增原生场景命名带 `PATCH-20261112-1`，保证
被验收命令选中。如修改其他原生 spec，精确运行其被改用例；不以全仓机械扫测代替关键证明。
使用新构建、真实 Python API、临时 SQLite／Local Storage 及模拟 Provider，至少证明：

1. Files 与 Task Center 四类从决定到当前摘要／显式确认，包含元数据候选与修正。
   暂停 Worker 观察已受理等待状态，DOM 观察覆盖瞬间，无旧按钮、无第二分析提交。
2. 真实队列容量拒绝，决定已保存后同一按钮恢复；关闭重开／刷新后仍成立；核对请求
   次数、固定主体／Task／item／pin，未重交 decision。用 harness 其他在途工作占满共享
   容量，不改生产容量逻辑或伪造产品读模型。
3. 已提交成功但响应丢失与明确拒绝分开，未知通过原状态核对；读失败不解锁、不重发，
   已有当前方案直接检查。至少一条真实受理后丢响应案例，不能全用静态 mock 替代。
4. 当前／失效／已确认方案、纯技术失败／未知效果、文件与 Task 切换和原草稿／准确交接
   的直接回归。没有执行确认前零媒体 mutation，之后原精确授权与兄弟非重放保持。
5. 使用同视口改前／改后及现有 Files／Automation 卡片参考，实际检查桌面 1440×1000、
   390×844、矮窗口 1280×650 的整体美化：双候选、元数据修正、长文件名／路径、附件／
   冲突警告、多项整批确认、空／读取失败、未知响应、慢分析、新方案及历史只读。
   验证首屏主动作与主次层级，实际滚动全部内容、键盘操作／回焦／退出保护，并观察
   中间态尺寸与滚动；不能只交最终成功截图。无遗留说明／空容器／横向溢出，危险许可
   完整可操作。保存截图、trace、命令与原始结果到
   `.git/validation-evidence/<candidate>/patch-20261112-1/`。

如修改公共 modal 实现／通用 CSS 选择器，除上述单元外，cwd `web/` 运行：

```sh
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/storage-dialog.python.spec.ts tests/e2e/automation-create-dialog.python.spec.ts
```

并用既有两种库新建／编辑旅程核对焦点、退出和背景稳定；如样式完全限定整理窗口，
上述其他业务原生矩阵不机械扩跑，但仍需取得现有卡片的视觉参考并记录依据。

根目录执行治理及 diff 检查，核对必要文档表述与所有改动消费者。本 Task 未触及 Python
执行／打包输入时，不要求全 Python、全 Web／E2E、wheel 或 Docker／生产外服矩阵；
B 如发现具体共享影响再追加所需检查并说明，不把全量门禁转交 Developer。

## Non-goals

- 任务中心整体详情／结果／文件证据、其他业务页及全站提示／主题／动效重设计；
  整理窗口以外的视觉美化。窗口内的整体美化与必要内容重排属于本 Task。
- 删除后端 continue／retry 能力、分析阶段或精确执行确认；新 endpoint、schema、队列、
  Provider、Storage、权限、自动重试、跨 Task 恢复、技术失败通用重放或历史转换。
- Files 尚无逐文件决定时的准备级“运行分析并生成计划摘要”、独立旧 intent 页面、
  元数据显式搜索及合法只读核对入口退役；动作退役仅针对上述共用逐文件决定入口，
  准备级状态／动作的必要美化仍在窗口范围内。
- 重开或关闭 Slice，修改 SLICE／Roadmap／Progress；推送或部署。激活检查点不自动
  开始 Developer 实施或启动其他代理；实施由用户后续授权。

## Developer Completion Report — Fix Round 2

READY FOR B REVIEW

- Prior B review range: `32bb37262777ae945deb8af4a51d9109876ca804..91fbffb381cc21a72ad730fd942f88623852498e`.
  This round addresses its two required fixes inside the same Task/Base; the old review detail
  remains reachable in Git and the Task ID/Goal/Scope are unchanged.
- Implementation checkpoint: `07e6d9aa642880eb2ffe591a7af8d12206eb3699` (Base
  `32bb37262777ae945deb8af4a51d9109876ca804`). This report travels in a separate Task-document
  checkpoint; the exact candidate Head is Git `HEAD` after that commit.
- Fix 1 — real analysis admission:
  - `GET /api/v1/tasks/{taskId}/items/{itemId}/recovery` now publishes one bounded,
    read-only `native_analysis` projection from the exact Task scheduling row: `task_id`,
    `item_id`, `readable`, `queue_state`, `machine_stage`. No endpoint, schema, admission,
    queue, Worker, permission or execution rule changed.
  - The panel no longer treats the overall Task `pending/running` status as analysis
    admission. A discovery-free kernel Task waits only for a queued/claimed `analysis`
    stage; human waiting, an explicit queue refusal and a settled Task are known
    non-admission. Files keeps its linked discovery as the exact stage. Read failure stays
    unknown and never re-enables an already accepted request.
  - Real Automatic Task regression added in `tests/test_v2_automation_run_once.py`: saved
    decision → real 409 `queue_full` (`decision_saved_analysis_not_queued`) → unchanged
    checkpoint/decision, `waiting_human` projection → release a real capacity-holding Task →
    the same action only `continue` → `queued/analysis`, zero media mutations. Browser unit
    coverage also reopens the panel with the overall flow still reading `running`, and proves
    only `continue` is posted (decision count stays 1 for that saved decision).
- Fix 2 — one status/handoff hierarchy in the organizer:
  - Removed the contradictory outer “先完成这个文件的选择” and duplicate native-failure
    instruction. The recovery panel is the single decision/waiting/refusal status; the
    dialog receives its one high-level state for nearby copy.
  - The ready page now shows adopted work, source → target, operation/source retention,
    attachment warning and selection before optional evidence. Ordinary identity correction
    is collapsed unless dirty or awaiting an analysis retry. The accepted-analysis success
    notice ends when the new exact plan arrives; refusals/errors stay beside the same action.
  - Metadata candidates moved into the existing diagnostics area; empty candidate/plan
    blocks and repeated source/operation copy were removed without hiding paths, errors or
    dangerous effects.
- Verification (actual):
  - cwd `web/`: affected unit command from Required Tests, including the changed entity
    test → **6 files / 88 tests passed**.
  - cwd `web/`: `npm run typecheck`, targeted `npx eslint`, targeted `npx prettier --check`
    → pass. `npm run build` → pass (existing bundle-size advisory only).
  - cwd repo: `.venv/bin/python -m unittest tests.test_v2_automation_run_once.RunOnceApiTests.test_recognition_decision_continues_analysis_summary_and_execution_on_one_task tests.test_v2_automation_run_once.RunOnceApiTests.test_full_queue_refusal_keeps_saved_decision_and_recovers_on_same_action tests.test_operations_task_center`
    → **28 tests passed**. `ruff check` and `ruff format --check` on the changed Python files
    → pass.
  - `python3 scripts/check_governance.py` → PASS; `git diff --check` → no output.
  - No real-browser visual matrix or full E2E was run by Developer; B owns that acceptance.
- Remaining risks: B must re-run the real Automatic Task conflict/capacity journey and the
  1440×1000 / 390×844 / 1280×650 visual/scroll/keyboard checks on this candidate. The
  native projection is a new response field; B should verify the real Python API response and
  all direct consumers. No push or deployment.
