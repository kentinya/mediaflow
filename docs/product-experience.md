# MediaFlow Product Experience

This document owns operator journeys and completion semantics. Stable scope/IDs live in
[Requirements](requirements.md) and [V2 Requirements](v2-requirements.md); technical boundaries in
[Architecture](architecture.md). [Progress](progress.md) records accepted baselines and deferrals.
The committed [Slice](../SLICE.md) owns current scope. Accepted live-list/retirement and Automation
workspace/settings foundations remain; current journeys include the accepted46 entry, readability,
work-ownership and execution-intent amendments and subsequent accepted presentation/record-result
corrections. Original Slice acceptance identities remain in Progress and Git; [TASK.md](../TASK.md)
points to the current implementation state and immutable review packet.
Detailed superseded delivery notes are retained at
`865ebdce47b0b323064fd8e05fbfaa54546e6269:docs/product-experience.md`.

## Current journey boundary

Current journeys incorporate accepted Slice50 presentation/loading/stability amendments `V2-UX-005–013`,
Slice49 Automation amendments `V2-AUTO-013–015`, Slice48 flow/rate amendments `V2-TASK-012–014` /
`V2-AUTO-012`, Slice47 Task-only scheduling/settings/history `V2-TASK-001–011`, and retained Slice46 amendments: `V2-UX-004`, `V2-OPS-014–017`,
`V2-FILES-007` and `V2-AUTO-010/011`. Historical43/45/46 acceptance facts and original deferrals
remain in [Progress](progress.md) and their Git Contracts; they are not additional operator steps.
Files owns new manual selection and ordinary-file progress; Task Center owns admitted organizing
progress and four business recovery types; Automation owns saved-definition scheduled/one-run intent.

## TARGET — V2 Explore homepage (Slice51 PLANNED)

[Slice51](../SLICE.md) 仅授权规划，`V2-EXPLORE-001–011` 是 TARGET，尚未激活／交付。
以下旅程在接受后替换 V2 Dashboard 首页；当前根入口和无 Provider Dashboard 读取规则仍是
CURRENT。MoviePilot 的筛选式探索是交互参考，使用 MediaFlow 现有中文浅色 Shell／弹卡。

- **目标／入口：** 用户进入“探索”浏览电影／剧集或找指定作品。侧栏和默认认证后目的地
  为 `/ui-v2/explore`，其他合法深链仍回原目标。旧 Dashboard Web 页面与入口移除，旧路径
  使用普通未找到；无跳转、旧页面／别名／说明页兼容。复用现有 Provider 配置和就绪条件，
  缺配置说明实际恢复步骤；不专门建设无 Active／无库独立启动流程，自然可用不刻意禁用。
- **可见状态／浏览：** 默认热门电影，明确切换剧集。页面只有“探索”标题、作品名称搜索、
  紧凑筛选／更多筛选与海报网格；常用题材、原始语言直接可见，年份、最低评分、最低评分
  人数在扩展条件内。热度／评分／上映或首播日期排序用准确名称；评分优先有可见合理人数
  阈值。筛选作用于整个后端结果集，切换电影／剧集校正不适用题材。默认中文，原文／空项
  诚实回退，原始语言不当作国家，数据源日期不当作本地上映日期或最新一集播出时间。
- **搜索动作：** 输入作品名并显式提交，进入明确的搜索结果态。保留电影／剧集选择，
  只显示该搜索实际应用的条件；探索独有的排序、题材、语言和评分不能假装适用于搜索。
  清空／退出搜索回到原探索条件与上下文。空关键词或其他无效输入有可纠正反馈，禁止
  将搜索词解析为本地文件或自动作作品确认。
- **列表／分页：** 2:3 海报、片名、年份常显，评分明确是 TMDB 评分，无评分不显示假 0；
  长名称可完整获取。桌面自适应列数、390px 两列。点击“加载更多”追加下一有界页，按
  Provider＋作品类型＋ID 去重，说明已到末页；改变条件从新结果集首页开始。旧请求不能
  覆盖新条件，过期条件的数据不冒充新结果；不自动无界翻页，不把当前页数当全部数量。
- **详情动作：** 点击卡片在列表背景上打开稳定居中详情卡，窄屏适配可用高度，名称和
  关闭入口清楚。先看图片、中文名／原名、年份、TMDB 评分／人数、题材、简介及该类型
  可用基本信息，再通过准确外链看 TMDB 原页。详情用确切作品身份，不按名称猜匹配。
  无图片／简介等字段显示真实缺项，图片失败不阻止阅读或关闭。
- **成功／返回：** 关闭、Escape 和浏览器后退恢复原筛选／搜索、已加载页、滚动位置和
  卡片焦点。本次只要求页面内详情与返回，不增加独立详情链接／刷新重认证恢复该作品的
  义务；刷新／重认证按现有机制正常进入探索即可，自然恢复详情也可接受，不强制丢弃。
  其他既有页面的合法深链续转保持。
  同页筛选、搜索、分页、详情开关不重播整页切换；背景滚动和宽度稳定，尊重 reduced-motion。
- **失败／恢复：** 首次用等比例骨架，快速响应／有效缓存不强制动画。未返回和真实空态
  分开显示；各读取环节只覆盖实际可能的失败，不做全组合。元数据 API 的缺失详情、身份 401／403、
  Provider 未配置／凭据失效、网络超时、限流和畸形响应分别可辨；上游凭据错误不冒充
  MediaFlow 身份失效。公开海报覆盖缺图／网络／CSP 加载失败，采用认证图片接口才验证
  该接口的认证错误。首次失败重读当前条件，空结果清除条件；分页失败保留成功页，
  只重试该页；详情失败在卡内重读
  并可退回原列表。429 提示有限等待／重读，不无限请求。缺凭据指向部署配置／重启后重读，
  不误导为可在探索页填密钥；403 不当空态，401／断开清理身份相关读取状态，若使用图片
  对象 URL 则同时释放。图片显示可复用可信公开海报，不要求新增同源代理／缓存平台。
- **状态与效果：** 明确探索请求读取外部元数据／图片；显示来源与必要 TMDB 署名。凭据
  始终留在服务端。页面不显示缺乏可靠依据的“已入库／已订阅”，不扫描或改动媒体，不
  创建执行任务／权限，不提供订阅、下载或播放。任务中心／文件／自动化／通知保留原职责。

Dashboard API／CLI 也按用户明确要求完全退出：正常配置／合法身份下旧接口返回通用未知
路由 404，旧命令在解析层按未知命令拒绝；不能把无权限或配置失败当作退出证据。
无别名、跳转、退役说明或空成功。公共解析／鉴权／审计／日志和初始化保留，旧请求不
额外触发 Provider、媒体操作、任务或配置变更。删除专属后端及所有旧消费者；
现存 V1 界面的 Dashboard 按钮／默认调用只作必要断接，不提供 V1 探索。测试／操作说明
不再要求使用旧接口或命令。任务中心／自动化／通知／系统状态仍提供各自已有信息，
耐久任务／结果／审计历史保留，不因删除面板清除记录或新增替代统计平台。
新数据源、推荐榜单、个人清单、演员／相似作品和完整季集浏览不在本 Slice。后端与图片边界见
[Architecture TARGET](architecture.md#target--v2-explore-homepage-slice51-planned)。

## CURRENT — V2 dialog, readability and navigation experience (Slice50 PASS / CLOSED)

[Slice50](https://github.com/kentinya/mediaflow/blob/214b69b1e64b24fc22068c2e1760cd1b0c6ac787/SLICE.md) 于 2026-11-07 经独立 A Final Review **PASS / CLOSED**，原 Base
`6cd881f0311c9e53bfc6b0ab754bfbe9acefbfd0`，已审实现 `6b0927328a7bf0873faffce9cb38007fd4607764`。
原八项 `V2-UX-005–012` 和自动化新建/编辑补充 `V2-UX-013` 全部接受，以下完整旅程为 CURRENT。
它们替换原任务侧详情、所选存储/库抽屉与两页目录树；旧图片/历史接受事实保留，更早 CURRENT
中的业务、权限、独立结果与非重放规则继续适用。

后续[独立可读性/导航修正](https://github.com/kentinya/mediaflow/blob/db54158dbb5ee9df3b67c26f38999ba87ea6281a/TASK.md)已于 2026-11-07 经 B 验收 PASS，下列旅程包含该修正的现行呈现。原 Slice 接受身份保留。

**任务中心详情（用户 1、2）：**

- 目标/入口：在任务中心点击任务名称，查看该任务并完成已有允许的操作；既有精确任务
  链接、刷新/认证续转仍到达同一上下文。
- 可见状态/动作：列表作为背景打开居中详情卡，不挤窄列表。效果与自动化新建卡片协调，
  内容按详情设计。先呈现任务名称、流程状态、阶段/等待、进度、独立文件/附件结果与需
  处理项，再按层级查看来源/目标、条目、记录和诊断；技术标识可折叠，证据不能丢失。
  概览按“流程状态→处理进度→文件结果”阅读，实际失败/未知/未记录结果就近说明。
  可用取消放在任务操作行，已结束且无操作时不显示空控制区。
  点击文件的“查看证据”，先看处理结果、来源/目标，再看从该文件固定历史计划捕获的
  识别/作品匹配、命名和分类依据及存储步骤；成功文件直接显示完成事实。原始状态、策略 ID、
  拒绝码和计划/日志/审计进入可展开诊断，任务级 JSON 导出及四类决定→分析→精确摘要→
  明确继续仍可达。
- 成功/退出：人能够区分“流程已完成；部分文件失败”和文件全部成功。长名称/路径和多
  条目在桌面/窄屏可读，键盘与必要操作可用；关闭/返回恢复原合法视图、时间筛选、页、
  滚动和入口焦点。开关卡片不执行或取消工作。
- 失败/恢复：加载、缺失、无权限、读失败各自可辨；失败阶段、真实文件结果/未知效果及
  原有合法下一步保留。技术终结失败保持事实查看，不新加通用重试。未决命令仍核对原请求，
  不因关闭/重开丢失，也不借新卡片自动重发。

**存储卡片与更多菜单（用户 3、4）：**

- 目标/入口：从存储列表查看、添加、编辑，或打开某行“更多”。三个查看/表单入口均打开
  列表背景上的居中卡片，与自动化新建/编辑卡片视觉、进出效果一致。
- 可见状态/动作：查看清晰展示状态/位置、能力、引用与检查；添加/编辑保留各 Provider
  已有字段和值，按卡片安排分组/步骤。“更多”锚定当前行，图标/文字、行距、边界与普通/
  危险操作清楚；复制、启停、只读检查、移除的入口/权限/确认不变。
- 成功/退出：保存仍通过现有 checked publication，读回真实状态后返回原列表；关闭/取消
  恢复焦点，未保存输入和在途提交按已有规则保护。菜单与卡片在窄屏/键盘下可用。
- 失败/恢复：字段校验/引用/权限/并发拒绝保留输入与旧 Active，并给出现有合法纠正；未知
  发布先核对原命令。查看/检查/开关菜单不变更媒体，不新增发布步骤或重复确认。

**两种库布局与配置卡片（用户 5、6、7）：**

- 目标/入口：从文件或媒体库页浏览目录，通过库菜单编辑/移除配置，或添加库。两页删除
  页内左侧目录树及其空白占位；应用全局侧栏保留。
- 可见状态/动作：文件区利用释放宽度，原有文件夹、面包屑、上一级/根目录、搜索、视图、
  选择、刷新/分页完成浏览。编辑/移除菜单和确认呈现清楚美观，包含用户点名的媒体库操作，
  危险动作可辨；移除配置明确保留物理文件。添加/编辑两种库四个入口全部使用协调弹卡，
  保留既有字段、精确回填、编辑 ID 不变及隐藏配置。
- 成功/退出：一次界面 Save 仍发布真实 Active；名称编辑保留合法目录，Storage/根变更回到
  正确根，禁用仍可经现有配置入口恢复。原有配置移除确认/引用保护保留；关闭/返回不丢失
  合法浏览上下文、不取消或重放工作。
- 失败/恢复：无效/重复输入、并发冲突、保存失败/未知、引用阻塞保持真实状态/输入和现有
  安全下一步。路径错误指引使用仍存在的导航，不再要求目录树。普通操作状态与资源库整理
  保持原归属，资源库/媒体库身份与结果不混用，配置操作不迁移或删除内容。

**侧栏主页面切换与一致加载（用户 8）：**

- 目标/入口：点击现有 V2 左侧侧栏“首页”“文件”“媒体库”等入口，在其对应主页面之间
  切换；覆盖全部现有侧栏主页面，其他业务内容不重设计。按主页面身份判断切换，同一主
  页面内的标签、详情子路由（含其深链）、切库/目录及开关弹卡不重播这项整页动画；既有
  前后退/认证续转和合法局部动效保留，弹卡按各自要求进出。
  文件/媒体库首次库信息和选库后的目录读取分别适用以下加载体验。
- 可见状态/动作：主页面切换自然协调，导航/页头稳定，不出现突兀挤压、闪白、叠影或
  快速切换旧页残留。两种库都区分库信息加载与目录读取，以协调的占位/加载动画反馈，真实
  内容就绪后平顺接入；仅未就绪区域需要占位，快速响应/有效缓存直接显示，不强制播放各
  阶段或为动画串行请求。减少动态效果偏好下提供清楚静态反馈。
- 成功：用户无需等待假动画完成才能操作；正常同条件刷新保留内容，轮询/筛选不反复播放
  整页入场。新库/路径不显示错属旧响应，既有筛选/返回/焦点和认证边界保留。
- 失败/恢复：尚未返回不能显示“未添加库/空目录”。真实空态、无 Active、权限拒绝与读取
  失败独立可辨并保留既有纠正/安全只读刷新，不能无限动画掩盖。动画/导航不提交或重放命令。

**自动化新建/编辑弹卡稳定性（用户补充）：**

- 目标/入口：从自动化列表点击“新建自动化任务”或任一已保存定义的“编辑”；两个入口
  均在原背景上稳定打开卡片，覆盖页顶和已滚动列表。原有深链、刷新/认证续转仍进入正确
  新建/编辑上下文，保留合法默认列表返回。
- 可见状态/动作：背景不回顶、不因滚动条隐藏改变宽度；权限和编辑定义读取在与完整表单
  协调的稳定布局中反馈，避免矮空壳突然撑大重新居中。标题、关闭及主操作位置稳定，正文
  长内容内部滚动；表单仍须等真实权限/精确配置就绪，不能用旧缓存提前允许提交。
- 成功/退出：打开到就绪以及关闭/回退均自然，筛选、页、滚动与焦点保留；滚动锁定/占位
  正确释放，重复打开或换定义不残留旧上下文。未保存选择、在途保护及原有保存/启停语义保留。
- 失败/恢复：慢权限/慢定义、读取失败、拒绝或缺失均有稳定可辨状态和原有下一步，不无限
  加载或自动重试。关闭/重开保留既有未知发布核对，不重发命令。reduced-motion 下同样稳定，
  不靠延长动画或先跳动再滚回掩盖问题；验收检查实际中间过程。

共同视觉以现有自动化卡片为基准，按详情、表单、配置移除确认分别安排内容；不要求复制
自动化字段、旧抽屉几何、固定时长或像素坐标，也不新增主题/动效设置。上述调整保留完整
已有权限、配置、Task/文件结果和非重放规则；原八项与自动化新建/编辑补充均需真实可见交互验收。

## CURRENT — Automation forms and direct Run once (Slice49 PASS / CLOSED)

[Slice49](https://github.com/kentinya/mediaflow/blob/6cd881f0311c9e53bfc6b0ab754bfbe9acefbfd0/SLICE.md) passed independent A Final Review on 2026-11-05 through implementation
`9d6b78147d90b950ed2333f9747facc77bf0391a`, preserving original Base
`02fb77dd713bad4dd51c29b6cfc5556ddd6d5b4e`. `V2-AUTO-013–015` and these journeys are CURRENT;
they replace the earlier disabled-only create outcome while preserving copy's disabled state.
Original Slice43/46 acceptance and all unchanged deferrals remain historical facts. The accepted
[standalone UI correction](https://github.com/kentinya/mediaflow/blob/8a37d1a17526347116df528dcba0467f0fdfe766/TASK.md) updates the current entries and feedback below;
it does not replace Slice49's acceptance or introduce another lifecycle command.

- **Goal/entry:** from `自动化 → 任务列表`, create or edit an automatic-organization definition
  in one familiar card, explicitly choose whether its schedule is enabled, copy a saved definition
  from the list, or click a saved row's `运行一次` to immediately submit one real organizing Task. Available row actions appear as `打开 / 编辑 / 复制 / 运行一次` under backend
  authority. Opening, browsing and closing do no work. The list, create/legacy-create and edit routes
  share one background without an extra location label or its layout shift.
- **Create state/action:** `新建自动化任务` opens the current list's Chinese card. Name, library,
  whole-library/subdirectory browser, interval value/unit, daily/weekly times, advanced Cron/timezone,
  backend upcoming times and limit retain the accepted interaction. The compact `启用定时计划`
  switch defaults off. On desktop it shares the item-limit control row, with its label alongside
  and help below; narrow screens stack the fields without page overflow. An explicit selection changes the primary action to communicate `创建并启用`. The note explains
  that enabling schedules future runs; it is distinct from `运行一次`. Missing enable permission
  explains that limit while allowing disabled creation when the operator has configuration rights.
- **Create success/failure/recovery:** one form submission completes the selected create/enable result
  in the normal success path through one atomic checked publication.
  Feedback reads `已创建，未启用` or `已创建并启用` from durable truth, refreshes the list and returns
  to its exact context. Publishing itself does not admit a Task; the Scheduler later follows the saved
  plan and live authority. Each rejected command preserves its prior Active state and correctable input.
  There is no separate create-success/enable-failure intermediate state in this implementation.
  Unknown responses retain the original enable choice and command's principal/candidate/base across
  reopen/reload. Reconcile that exact publication first. A proved historical publication is distinguished
  from the current saved definition when a peer later modifies/removes it or current state is unreadable;
  reconciliation never creates again or reapplies enablement.
- **Edit state/action:** a row's `编辑` or a supported saved-definition edit deep link opens the same
  card with exact saved values and the current enable state. Preserve arbitrary legal Cron and
  fractional intervals without converting them to convenience defaults. The ID is immutable and
  internal publication details do not occupy ordinary fields or introductory tutorials. One `保存`
  publishes only that intended successor under existing configuration and execution permissions.
  After creation the operator can explicitly enable or disable the saved definition here, regardless
  of the initial choice. The edit card/page has no `运行一次` button; use the list for that action.
  Enable/disable uses the shared form switch and takes effect only on Save; the separate lifecycle
  heading and immediate toggle/copy/refresh group are absent. Reference-safe removal retains its
  separate impact evidence, explicit confirmation and authority.
- **Edit success/failure/recovery:** preserve the creation card's grouping, controls, animations,
  reduced-motion, keyboard and narrow-screen behavior. Success returns to the original list with
  current readback. Reopening that definition permits another edit/enable change against the confirmed publication.
  A late response never erases later input. Peer changes retain input and require explicit reread;
  an unknown edit retains its exact submitted candidate for `核对本次发布`, without reposting.
- **Exit and return:** unchanged input closes directly; unsaved changes expose visible continue/discard
  choices. During submission, repeated commands and accidental departure are prevented. An ended
  unknown response can leave/reopen with the retained reconciliation context. Cancel/discard/success
  preserve valid list filters, page, scroll and entry focus; filtered-out successes are explained.
  Ordinary deep-link/reload/login continuations reach the same form with a safe default list return.
- **Copy state/action:** click `复制` beside the saved row's `编辑`; it copies saved source values,
  independently of unsaved editor input. Stay on the list and retain filters, page, scroll and focus.
  Show busy feedback for that source; each explicit new attempt replaces its previous result.
- **Copy success/failure/recovery:** show the actual new disabled copy and an `编辑副本` entry;
  explain when filters/paging hide it. The copy has a new ID and no inherited execution authority;
  the source is unchanged and no Task/media work starts. Permission/read/validation refusal gives
  its cause and next action. A stale conflict refreshes both list and configuration authority;
  a row and authority from different saved versions cannot be submitted together. Reread and show
  current values, then await another explicit click. Lost/5xx/malformed responses retain the original
  principal/source/publication baseline and offer `核对复制结果`, including after reload or when the
  source is filtered away. Reconcile only that command; never repost automatically or show an earlier
  success as its result. Retained legacy edit-copy sessions remain reconcilable here. Incomplete
  evidence stays unknown; only complete proof of non-publication releases the repeat block.
- **Run once state/action:** click the saved row's `运行一次` once. The row becomes busy in place;
  no prerequisite navigation, picker, manual analysis or second initial confirmation is required;
  backend analysis, planning and safety checks still run. Bind the exact observed published definition
  and current-principal execution intent. Disabled definitions
  can run once without enabling or changing due state; unsaved editor values are not executed.
- **Run once success/failure/recovery:** accepted feedback keeps the list in place and identifies the
  original Task via an explicit readback link, without claiming file success or forcing navigation.
  Double clicks cannot duplicate work. Permission/queue/stale-definition refusals offer bounded
  correction and a deliberate new command after reread. Lost/5xx/malformed responses retain the
  principal/definition/request across reload/reconnect and offer exact reconciliation in the list;
  a missing lookup is not permission to replay. Other rows keep independent feedback. Pending requests
  previously submitted from the edit page remain reconcilable from the list after its button is removed.
- **Scope and result:** whole-library/subdirectory sources work for Storage root and nonempty/nested
  ResourceLibrary roots, including Chinese names/spaces. Internal path composition cannot reject a
  valid whole-library source or blame the operator. Healthy empty completion says no work. A missing
  root or directory read failure preventing complete enumeration, or an incomplete/overflowing scope,
  remains Task failure. An individual file read/processing technical failure retains its failed file
  outcome; an ended flow can complete when no work, human decision or real live call remains.
  Real stability, full pipeline, limits, source ownership and non-replay remain.
  Task Center owns the existing four-type recovery;
  flow status, file effects, original records and success-rate meanings remain unchanged.

## CURRENT — Task flow status and Automation success rate (Slice48 PASS / CLOSED)

The user selected `V2-TASK-012–014` / `V2-AUTO-012` on 2026-11-03.
[Slice48](https://github.com/kentinya/mediaflow/blob/02fb77dd713bad4dd51c29b6cfc5556ddd6d5b4e/SLICE.md) passed independent A Final Review on 2026-11-04 through implementation
`a80015e2f7d46e3ad1b8f7b14c453d1030e62104`. These journeys supersede the affected earlier
aggregate, recovery-display, metric and execution-record meanings; original acceptance facts remain in Git.

- **Goal/entry:** organize from the existing ResourceLibrary Files/manual API/CLI, due Automation
  or saved-definition Run once, then distinguish whether the Task flow finished from what happened
  to each file. Existing manual initial confirmation, Automation intent and four-type continuation
  remain; ordinary-file operations stay on their originating library page.
- **Visible state:** five Task states are 待处理/pending, 进行中/running, 流程已完成/completed,
  流程失败/failed and 已取消/cancelled. Scanning/analysis/execution and stability/human waiting remain
  visible stages/reasons. Current Task badges/filters do not offer paused or partial_success;
  unavailable evidence is shown as unavailable, without guessing an outcome.
- **Action:** inspect independent file results, causes, completed steps and uncertain effects;
  use existing backend-permitted cancel or four-type decision → analysis → exact summary → explicit
  continuation. Saving/reading does not execute. Required waiting keeps the flow unfinished, and
  only explicit legal continuation can re-enter a terminal Task with its existing identity/pin.
- **Success:** a normally closed flow displays “流程已完成；成功 7、部分成功 2、失败 1”.
  File-processing attempts ended by technical failure also close as completed, including timeout,
  interrupted file work, unknown effects and no formal file Result. Do not wait to establish actual
  file results before this technical closure. Show “流程已完成；文件处理发生技术失败，实际结果未记录/效果未知”
  where applicable; retain known failures/steps without inventing file success or empty work.
  All skipped/ignored/individually cancelled, healthy empty and complete history exclusions can also
  close normally. Required human decisions, genuine remaining machine work and a locally executing
  call stay unfinished. An old processing marker left by the ended technical failure alone does not
  keep Task running. Task-level flow failure/cancellation remains distinct; Task closure itself must
  be saved. The [Slice48 scenario table](https://github.com/kentinya/mediaflow/blob/02fb77dd713bad4dd51c29b6cfc5556ddd6d5b4e/SLICE.md#场景与统计口径--slice48-current) defines each case.
- **Failure:** Task scope enumeration/root failure, unusable required execution context/relations or
  orchestration error preventing normal completion shows a Task flow failure with bounded stage,
  durable state, known effects and the existing allowed next action. A safely isolated file error
  does not fail the Task. Incomplete/overflowed traversal cannot be shown as healthy empty or
  first-N success. No/stale Worker and lease/claim loss alone do not assert terminal failure.
- **Recovery/cancellation:** existing four business flows and actual recovery-success evidence
  remain separate from flow completion. Unresolved human work is not completed; successful or
  uncertain effects cannot replay. Cancel is acknowledged only at a safe boundary; a request or
  file-level cancellation does not itself make the Task cancelled. Ended file technical attempts can
  close without a formal Result; preserve known evidence, absent-result warnings and non-replay.
  Task-status read/publication failures preserve last durable truth. No new generic retry, remote-stop
  verification gate, pause restoration or universal rollback.
- **Automation success rate:** in the existing local-month Automation cohort, each admitted due/Run
  once Task counts once. Run once means the Automation definition button; manual Files/CLI organizing
  and ordinary Copy/Move/Delete do not enter this statistic. The rate is
  completed/(completed+failed); cancelled and pending/running human waiting are excluded from both
  numerator and denominator. No completed/failed Tasks or unavailable data shows no rate, even if
  every run was cancelled. Cancelled runs remain in records and execution/ended counts, outside
  active counts; the displayed rate explanation uses its own completed-plus-failed denominator.
  A completed Task counts even if every file failed/was partial/skipped/ignored, effects are unknown,
  formal file results are absent, or the scope was healthy empty/history-excluded. File outcomes and
  Result presence never gate this metric. Legal continuation may change that Task's current
  lifecycle-based rate contribution without creating a second run. Unknown metrics offer existing
  refresh/read recovery, never fabricated 0% or 100%.
- **Execution records:** 自动化 → 执行记录 → 查看详情 shows the same current Task flow result as
  Task Center. For a normally completed Task with ten failed files, both show “流程已完成” plus
  “文件失败 10 个”; the success rate counts that Task as successful. File failures do not relabel
  the Task's execution result as failed. Status filters/counts/paging follow Task flow state over the
  authorized population; required human waiting stays unfinished, and actual Task-level flow failure
  stays failed regardless of file mix. Original execution times, attempts and file/effect history
  remain factual when legal continuation changes the current Task status. Records stay compact and
  read-only with no new execution/recovery control. All-failed is not empty/no-work or successful
  media organization. This CURRENT amendment changes the result/filter meaning of `V2-AUTO-006`.
- **Other surfaces:** Files local ordinary-operation status, Task Center, Dashboard, API/CLI,
  export/logs and existing Task-status notifications distinguish flow state from per-file effects,
  without adding a page or control. Ordinary Copy/Move/Delete already have Tasks and use the same
  technical-failure completion rule on their originating library page. The operation still shows
  failure/partial/unknown/missing results; Task completed alone cannot say the file was copied,
  moved or deleted successfully. Known successful or uncertain operations are never replayed.

Fresh/new-work/same-version restart retains the same Task and independent results. The source-history
gate still uses actual latest formal file failure/partial even inside a completed Task; a new manual
request keeps its warning/normal confirmation. Old-task/status conversion and cross-version upgrade
remain excluded. This accepted amendment changes flow aggregate/rate and execution-record Task result/filter
meaning while preserving recorded file facts and safety.

## CURRENT — One organizing Task across triggers and recovery (Slice47 PASS / CLOSED)

**2026-10-31 user amendment:** Organizing AND ordinary-file operations (including Copy/Move)
retire Pause and resume-from-pause across Web/API/CLI and live dedicated dispatch. This supersedes
REQ-TASK-004 / V2-OPS-007 and affected CURRENT/TARGET pause requirements. Cancellation remains
cooperative and preserves completed/uncertain effects. Four-type organizing decision/analysis/
summary/explicit continuation, human/stability waiting and fences remain. The user confirms no
currently paused organizing Tasks: do not build a pause migration, restoration or compatibility
executor. Existing history stays readable without deletion, false relabelling or automatic replay.
This retirement passed Slice47 AC-19 / V2-TASK-007 acceptance.

The user-authorized `V2-TASK-001–011` refactor passed independent A Final Review on 2026-11-03.
[Slice47](https://github.com/kentinya/mediaflow/blob/ba84272721961c970f1eb85d616a0d129523ab92/SLICE.md) records the original Base and accepted Head. The journeys below preserve
entry-specific intent, bounded scope, failure/recovery and original execution-record semantics
through one Task identity; historical Job-based acceptance remains in Git.

- **Goal/entry:** organize live ResourceLibrary selections from Files, let an enabled saved
  Automation definition run when due, or explicitly Run once on its saved scope. These entrances
  admit the same kind of durable organizing Task before rule/metadata/target/conflict readiness.
  Disabled Run once stays schedule-independent; browsing/analysis creates no execution authority.
- **System runtime settings — 2026-11-03 user amendment (`V2-TASK-011`):** open `系统设置`
  → inspect the three published runtime values and their scope → edit and Save → distinguish this
  publication from actual consumer adoption/pending/override. Automation keeps definitions and
  records; its old settings links navigate here, without a second ordinary form. Invalid/stale/denied
  Save preserves Active/input; unknown publication is reconciled before another submission.
  Save 1025/10000 → Files selection → task admission → exact summary → normal confirmation → actual
  result works without lowering the legal value or routine restart. With capacity 1 occupied by
  either manual or automatic organizing, a distinct new organizing request explains the full system
  queue; after safe release, explicitly retry it or let due work reach its next normal check.
  Same-Task re-entry preserves choices/results/authority if full. No source-label bypass or extra
  routine confirmation is added. Ordinary asynchronous copy/move/delete keep their own admission
  rules and local state, while sharing the Worker's idle cadence. Scheduler cadence only affects
  when Automation due definitions are checked; it does not control manual/Run once submissions,
  individual task duration or definition schedules. Publication/heartbeats are not business polls.
  Users no longer see or set “失效判定时间”; no replacement no-progress prompt or total-runtime
  timeout is added. Current heartbeat, lease/renewal and individual call timeouts still apply, with
  the same safe controls and uncertain-effect non-replay. Existing snapshots containing the old key
  remain readable without changing their identity or requiring manual cleanup. This replaces the
  prior Automation-only scope and intermediate four-setting plan, not historical acceptance.
- **Visible state:** the exact Task shows queued/discovery/analysis/waiting/execution stage,
  independent files, bounded explanations, real completed/partial/uncertain effects and current
  allowed actions. Queued and pre-start failures are Task evidence rather than a separate Job to
  locate. Close/reload/reconnect/restart finds that same work; unknown responses reconcile the exact
  request instead of submitting another. No queue token/claim/revision becomes an operator chore.
- **Action and success:** manual work reviews its exact in-task summary and explicitly confirms
  selected items/effects. Due work uses configured rules and valid checked Enabled intent without
  a per-run click; Run once's command supplies this run's intent without a second initial
  confirmation. The shared engine validates each real plan/source/capability/permission before
  OrganizerExecutor runs. Per-file Results/attachment effects remain durable; empty no-work,
  policy skip, unstable/unreadable/incomplete scope and real success remain distinct.
- **Failure and recovery:** Recognition, Metadata, Classification and Conflict keep their native
  decision → analysis → exact summary → explicit continuation. Recovery stays in the same newly
  admitted Task, with each file's source/version, decisions, attempts and results traceable through
  durable relations. Internal item IDs may change without losing history/links or duplicating files.
  Other siblings and original attempt evidence remain preserved.
  Save/analysis never executes media. Technical failures remain factual All/Ended history under
  the existing V2 restriction; uncertain effects remain inspection-only. No fifth flow, generic
  retry promise, successful-sibling replay or implicit authority refresh is introduced.
- **Controls:** cancellation and four-type continuation remain cooperative and backend-authoritative.
  A request is distinct from its acknowledgement and cannot interrupt an in-flight call or undo
  completed effects. A Task wholly waiting for a human uses no queue slot when no
  machine work remains; it keeps identity/source ownership without being repeatedly claimed. A cancellation
  request still in progress keeps its slot until the active call/work reaches a safe boundary. When
  continuation/confirmation is refused because the queue is full, the Task stays waiting with
  choices/summary/results retained and no authority consumed. It explains the refusal; the operator
  can explicitly retry later with normal checks. Saving a decision needs no queue slot. Worker
  unavailability has truthful task-local readiness; no global monitoring block returns.
- **Interrupted work:** after restart, continue only the remaining work that existing supported
  rules and durable evidence prove safe. If a copy/move or other mutation was sent but its outcome
  was not recorded reliably, preserve that step as uncertain for factual inspection and prevent
  replay. A timeout, expired claim or missing result does not mean the operation never happened.
  No promise of seamless automatic continuation at every interruption or new recovery flow is added.
- **History and same-version restart:** Automation records use the current durable Task flow result
  under Slice48, with concise failure/next step and server flow-state filtering. Later legal recovery
  can change that Task result without rewriting original execution times/attempts/file effects or
  counting another original run. Existing Task/Result/attempt/decision/audit/log
  identities and new-work history survive same-version reopen/restart, including pre-start failures
  and four-type continuation. Retained links resolve read-only into proved same-version Task/history
  or explain unavailability/denial; they never start work or require an old-Job mapping layer.
  Restart grants no new authority and never automatically replays an uncertain file operation.
- **Existing surfaces:** Task Center retains eight organizing views and the four-type Attention
  union; Files retains initial confirmation and exact task/preparation readback. Both library
  kinds keep ordinary-operation progress/recovery locally. Automation keeps definition lifecycle,
  records/metrics; System Settings owns the three runtime fields. Dashboard, scoped logs/export, API/CLI and health retain
  their capabilities through Tasks. No Job management page/API/CLI command remains. Capacity is
  bounded queued/claimed executable work, not new parallelism; immutable old configurations and
  explicit runtime overrides retain their meaning.

The supported persistence journey is fresh initialization → submit new work → same-version
reopen/restart → inspect results or safely continue. Old-task migration/import/takeover and
cross-version upgrade/rollback are excluded, as is V1 support. Failed/partial history from supported
work and existing immutable configuration readability remain required. Full boundaries and evidence
requirements live in the Contract/Architecture; no history clearing, new recovery system or arbitrary
historical Reprocess is selected.

## CURRENT — New organizing after failed/partial history (Slice47)

The accepted `V2-TASK-008–010` extension uses the ordinary Files and Automation entrances.

- **Goal/entry:** use normal ResourceLibrary Files 整理 for a failed/partial file. Definition
  due/Run once excludes a version only while its latest formal organizing outcome is failed/partial;
  later manual success removes that failure-based exclusion, with ordinary filters/conflicts still
  applied. Check each concrete file in shared admission, including selected-directory expansion.
- **Visible state:** automatic work records excluded files/reasons and free siblings truthfully.
  Files preparation/summary visibly identifies each affected file's applicable outcome and available
  target/steps/unknown effects, with bounded readable evidence and a clear reminder to
  check source/target/Storage before re-organizing. Read/refresh creates no work or Provider call.
- **Action:** user checks actual effects and uses the existing selected plan confirmation. No new
  verification page, routine extra checkbox, terminal-failure center or CLI retry command is needed.
  Existing directories and target/remnant files follow normal conflict policy; explicit overwrite
  and source-cleanup authority remain separate. A new request uses current configuration and
  reviewed live source evidence; same-Task four-type continuation retains its legitimate old pin.
- **Success:** new work records its own effects; old outcomes/Results/pins/steps/unknown evidence
  and original Automation result/time remain factual. Necessary lock/claim/fence/current handling
  changes are permitted. Same request readback does not duplicate work.
- **Failure/recovery:** a file still queued/processing without its own terminal outcome retains
  normal ownership. A failed/partial file is not blocked solely because its parent Task is running
  or an old unknown marker remains. No remote-stop proof is required. Backend handoff fences any
  superseded application owner and preserves siblings; confirmation cannot prove or stop an already sent
  remote Storage call. Explain that limitation without claiming automated verification. New conflicts,
  source/plan changes, denied authority or queue-full retain normal explicit correction/readback.

CLI `tasks retry-failed` is removed, including its analysis-only form; ordinary `organize` analysis
and explicit execution remain. Normal CLI/remote source and authorization behavior is retained,
without new CLI warnings or a new remote history gate; the required conspicuous warning is in Web
Files. Unrelated history appends do not by themselves require an extra confirmation. Source identity
is canonical Storage/path plus comparable version, not a pathname blacklist or a new FileIndex.
Only latest failed/partial outcomes cause exclusion; an earlier failure is not permanent after success.

## Readable actions and Entry

Open Entry or a V2 page/dialog → distinguish text, availability and focus → submit the permitted
action → read success or bounded failure/recovery. Shared primary/secondary/danger/link/icon actions
and directly related Entry fields stay legible in normal, hover, focus, selected, busy and disabled
states. Enabled text meets AA contrast; keyboard names/focus and duplicate-submit guards remain.
Authentication continuation and memory-only credentials are unchanged; reconnect never replays a
command. This is the shared light theme, without a new identity or theme-customization product.

## Product Experience Priority

Choose the most direct complete Web journey that preserves correctness, security and data integrity.
Automate determinable scope/capability/permission/freshness checks; interrupt for meaningful intent,
authority escalation, ambiguity, conflict, uncertain effects or irreversible/destructive scope.
Internal tokens/grants/revisions/claims/fences remain backend mechanisms, not ordinary user chores.
CLI supports administration, automation and diagnosis; it cannot complete a required ordinary Web flow.

## Product completion contract

Every capability completes **goal → entry → visible state → action → success → failure → recovery**.
API and Web share application behavior. Active is the actual immutable runtime snapshot; admitted
work retains its legitimate pin. Analysis/Preview has zero media mutation and no execution authority.
Only OrganizerExecutor mutates Storage after explicit effect permission. No silent overwrite/delete,
link fallback, unsafe path, secret leakage, successful-sibling replay or automatic uncertain replay.

Show bounded decision explanations. On failure identify item/stage, durable state, known effects,
safe repeatability and the legal next action. Retry alone is not recovery. Unknown submission outcomes
are reconciled from durable identity before another explicit attempt; reads never replay work.

## Configuration lifecycle

- **Goal/entry:** change runtime behavior through Settings/Configuration or focused business forms.
- **State:** JSON_BOOTSTRAP versus MANAGED authority; Draft/Validated/Active/Superseded, exact version/
  digest, references, validation/current evidence and capability readiness. Unsaved input is not Active.
- **Action:** explicitly create/resume a Draft or successor, edit typed objects, inspect impact,
  validate/test and checked-activate. Advanced whole-document JSON/import/export is a labelled support
  path; imports create inactive Drafts. Business-page Save bundles shared validation and activation.
- **Success:** one immutable candidate becomes runtime Active atomically; old work keeps its pin.
  Publication starts no media Task, scheduled occurrence, notification or Storage mutation.
- **Failure/recovery:** stale/concurrent or invalid reference/evidence/runtime, denied permission or
  unknown Save is actionable. Known rejection preserves prior Active and correctable input. Refresh
  stale authority, repair named blockers, rerun relevant checks; verify unknown publication before
  resubmitting. Corrupt Active stays explicit, never silently falls back to Draft/cache/JSON.

[Configuration](configuration.md) owns exact fields, lifecycle APIs, secret references and checked
publication. Reference-safe removal preserves media, Results and historical snapshots; it cannot
silently publish unrelated Draft changes.

## First-time setup

- **Goal/entry:** authenticate a management-only installation and open `系统设置`
  (`/ui-v2/configuration`) or a setup-required page. Viewers get read state and admin guidance.
- **State/action:** distinguish no Draft, resumable Draft, empty Active and broken prior Active.
  Explicitly create the first Draft, inspect/export labelled JSON and activate empty or populated
  configuration. No mandatory media forms or generated Storage/type/policy defaults.
- **Success:** show `配置已激活，媒体业务尚未配置` for empty Active. Validate populated objects and
  their declared references; require applicable library/Storage/recognition/destination evidence,
  without blocking unrelated empty families. Browsing/transfer need not require the media pipeline.
- **Failure/recovery:** retain saved Draft and input across reload/reconnect without duplicate
  initialization. Fix named mount/secret/reference/schema/permission blockers. Broken prior Active
  uses recovery, not automatic first setup. Return to the allowlisted originating page and refetch.

JSON defaults to actual Active; before activation label Draft/no-Draft. Portable exports retain safe
environment references and supported managed fields, excluding database/principal/token deployment
authority and unsafe URL credentials. Advanced edits are backend schema/field-allowlisted; restart-
only settings are never presented as already consumed.

Fresh Compose needs no media mount. Local roots must be explicit paths visible to the running
container/UID/GID; host `/`, Docker socket and arbitrary unmapped paths are unsupported. Correct a
missing/denied root by fixing the mount/ownership or Draft path, then retry the bounded read/check.
V1's complete-configuration setup remains a compatibility path, not the native empty-first requirement.

## Storage management and root recovery

- **Goal/entry:** inspect or maintain configured locations through `存储管理` (`/ui-v2/storage`).
- **State/action:** real provider/identity/root, enabled/read-only/readiness and library references;
  typed add/edit/copy/enable/disable/reference-safe removal, or explicit Connection/Read check.
  No secrets/private host paths or mutation-based capability probes.
- **Success:** checked successor publication or bounded read evidence; supported transfers keep their
  own library-kind/pin. No media work from configuration management.
- **Failure/recovery:** name unavailable root/provider, stale Active, blocked reference, missing setup,
  schema/secret/permission issues and the correction/refresh/setup action. Preserve prior Active.
  Worker waiting leads to readiness diagnosis, not request resubmission or unsafe replay.

OpenList `rootPath` may be empty or `/`: display `提供商根目录` and preserve the exact provider-valid
value through Save, inventory, detail and Edit. Other providers retain their own rules. A failed
list read after Save is a read/presentation failure, not proof of rollback: verify durable state,
never automatically Add again, reset the database or move media. Existing saved values remain readable.

## Recognition and rules

- **Goal/entry:** manage the RecognitionRule→RecognitionType→four-policy graph at `/ui-v2/rules`,
  or inspect recognition/metadata decisions from an explicit test, Preview or Task recovery.
- **State:** actual Active, object identity/enabled state/references/readiness and separate unsaved
  candidate. Overview, bindings, types, rules and Metadata/Naming/Classification/Organize inventories
  open full-width without a selected editor. Add/Copy opens a drawer; Edit is a full-page route.
- **Presentation:** the workspace content header contains one `整理规则` title, a short description
  and `刷新`, following the Task Center header hierarchy. The shared topbar keeps account/notification
  controls. The eight category cards and seven inventory layouts retain their design. Overview
  shows Chinese relationship labels, real total/enabled counts, conditional gaps/dependency guidance
  and the separate complete-flow check at the bottom; it has no inventory search. Each family keeps
  one local search and its existing state filter.
- **Action:** typed lifecycle/reference impact, exact object test or policy preview and one `保存`.
  Search/filter/navigation/refresh are read-only and create no Draft, Provider call or work. A
  successful refresh retains the current family, keyword, state filter and unsaved input; changing
  family clears the keyword. Busy refresh is visibly unavailable. Forms retain correctable
  tab-scoped input, not credentials or publication authority.
- **Success:** focused whole-graph checked publication becomes Active for every consumer. Real rule
  priority/score/ambiguity/stop-on-match remains authoritative; one enabled binding per type. C keeps
  C under A Naming/Classification/Organize reuse. Save starts no work or execution authority.
- **Failure/recovery:** show incompatible condition/operator, unsafe regex/template/path, duplicate
  binding, missing/disabled reference, denied/stale/invalid response or Provider/test failure on the
  affected object. Preserve input/Active; refresh stale authority, inspect/repoint references and
  rerun necessary evidence. An unknown Save needs state verification before another submission.
  Authentication/read failures use the shared boundary without presenting stale data as refreshed
  or resubmitting commands. No Active remains distinct from an empty Active graph and offers Settings
  recovery with the originating family preserved. The normal workspace omits the sequence/Settings
  utility row; Settings retains version/digest diagnostics and ordinary sidebar access.

Reference images define hierarchy/style, not real names, counts, conditions or backend algorithms.
TMDB remains the configured Provider abstraction; no implicit fallback or V1 Provider switching.
Production identity selection explains parser/rule/policy/candidate score; unrecognized/ambiguous/
below-threshold/credential/timeout/malformed evidence cannot fabricate an identity.

### Object-scoped tests and complete-flow checks

`测试与预览` tests the edited candidate and relevant inputs; `完整流程检查` is a separate Rules
Overview action using the exact complete graph. Local success does not imply production competition,
whole-flow readiness, publication or execution permission. Save still validates its whole successor.

| Edited object | Local test and visible outcome |
|---|---|
| RecognitionType | Validate identity/name/description/enabled state without binding/sample. Optional associated-rule tests report real output; no rules shows `类型定义有效；暂无关联规则可供试识别`. Never force that type or resolve unrelated policies. |
| RecognitionRule | Parse the submitted synthetic path and show bounded condition/group expected/actual/truth for this rule alone. Missing downstream bindings cannot turn a real local match into failure. Exact context stays visible; library selection never silently prepends a root. |
| Binding | Check type, uniqueness and four references. |
| Metadata | Offline configuration validity is distinct from credential/live identity; live testing is separate explicit intent and applies the configured policy. |
| Naming | Typed identity/episode/tag sample renders the actual Movie/TV template family without other policies. |
| Classification | Test its rules and MediaLibrary/safe path without Naming or Storage probes. |
| Organize | Explain own effects, permissions and capabilities; destination/conflict/execution readiness stays `未检查` until contextual complete-flow analysis. |

Non-match/not-applicable/disabled are honest outcomes. Show only applicable fields and named input/
reference corrections, never raw PolicyResolutionError. Offline local tests call no Provider or media
Storage and create no executable work. Evidence binds non-Active candidate/purpose/sample/context and
goes stale after relevant edits. Full-flow analysis retains real competition/policy resolution and
planning, labels synthetic identity, exposes missing stages and uses bounded read-only destination
checks; explicit live Metadata is separate.

### Naming and classification destination

Inspect policy IDs, rendered names/directory, MediaLibrary/path, operation/capability/conflict and
destructive effects before authorizing media work. Unsafe/missing/stale policy or destination fails
the affected action; correct the named reference and rerun the exact preview. No silent fallback.

New Classification rules use MediaLibrary plus safe `path`: root + path + Naming directory/filename,
without a library name/ID prefix. Labelled legacy `library/path` preserves old semantics until explicit
checked conversion with destination-impact acknowledgement. Preserve path; do not silently add a
legacy label. Old snapshots/Previews/Tasks/grants retain their original meaning; failed conversion
keeps prior Active and correctable input.

## Real Storage Files

- **Goal/entry:** browse physical sources at `文件` (`/ui-v2/resourcelib/files`), Dashboard or a
  ResourceLibrary link; MediaLibrary has the separate destination journey below.
- **State:** enabled ResourceLibrary cards, exact relative root/breadcrumb, bounded deterministic live
  entries/list/grid, paging, selection and meaningful capability/error state. No FileIndex membership,
  FileID/occurrence/fingerprint authority, recognition-result or organize-status feedback.
- **Action:** navigate/refresh/select a bounded file/folder scope, use ordinary maintenance or explicitly
  submit organization into its durable task. Viewing is a bounded read, never recursive discovery,
  Provider lookup or work.
- **Success:** exact names/paths survive normalization, hover/focus, breadcrumbs and long-name toolbar
  reflow. Boundary whitespace is visibly/assistively distinguished; shortening never changes identity.
  Refresh reconciles live entries/selection and removes vanished entries without losing a
  still-valid selected library/path.
- **Failure/recovery:** explain missing/denied root, timeout/provider, invalid/stale cursor/path,
  capability/conflict or escape. Correct binding/path or retry the bounded read; absent paths never
  trigger alternate trimmed-path guesses. Preserve read-failure state when the current directory vanished.

Library cards show icon/name/selection/menu, no Storage/root/count/capacity. Selected context shows
enabled state and exact configured path only, not a repeated name. Disabled libraries are hidden
truthfully with an existing Web re-enable path. The immutable visual references and responsive/
keyboard states are in [Files specification](file-page-visual-spec.md) and
[MediaLibrary specification](media-library-page-visual-spec.md).

### Common file maintenance

Use toolbar/selection bar or an accessible entry context menu to create folder/text, rename one
entry, Copy/Move/Delete or edit allowlisted bounded text. Folders open on left click; no inline Open
button. No browser Upload/Download, arbitrary binary/media editing, host paths, root delete or
unbounded recursion. These commands do not run media recognition/metadata/naming/planning/Preview or
require raw execution tokens; backend confinement, capabilities, authority and audit still apply.

Show exact source/destination/library kind, operation, current evidence, bounded impact, per-item
progress/conflict/partial effects and explicit Delete/Replace/Save intent. Transfer byte totals are
impact/progress, not an admission ceiling; selection/entry/depth/path/manifest/control projections
remain bounded. Cross-Storage Move explicitly Copy→digest-verify→Delete-source; failed verification
preserves source. Same-Storage requires advertised native capability and no silent fallback.

Rename/Delete use kind/library/Storage/root/pin/path/type/size/mtime evidence without reading media
bytes; provider fingerprints are optional but remain binding once observed. Text Edit binds its own
loaded-content digest. External replacement/check-to-write windows remain provider observation
limits. Delete asks once after current bounded scope/impact. Long/batch commands persist independent
Task/results and cooperative controls; unknown admission is read back by exact request. Correct a
name/destination, refresh/reopen changed input or explicitly continue only known-safe remaining work.
Uncertain effects are investigated; result persistence or display failure never replays a mutation.

“当前页面操作状态” sits immediately left of 添加资源库 / 添加媒体库 with the same button style.
It opens a centered modal for that library kind/source's multiple ordinary operations, progress,
independent item results and existing backend-permitted controls/recovery. Close/reload/reconnect/
service restart can reopen durable work; browser memory or one overwritable hint is not the only
index. Hints remain principal-isolated and non-authoritative. Missing/removed/pin-restricted history
explains its restriction instead of rebinding to current Active. Empty/loading/read-error states and
keyboard dismissal stay usable; closing neither cancels nor replays. Unknown effects stay inspection-
only, success refreshes live Storage without discarding unaffected selection/siblings, and no global
ordinary-operation center or new retry/undo authority is introduced.

### Library Add/Edit/removal

Add ResourceLibrary from `+ 添加资源库`; edit either library kind through its selected-card menu.
The three-step centered card is `基本信息 → 存储位置 → 确认`, opened only by explicit intent. Edit loads exact
Active, keeps ID read-only and allows name/enabled/Storage/kind-relative root while preserving hidden
configuration. One Save/`保存并激活` composes shared structural/reference/applicable checks and atomic
runtime publication; no ordinary Draft/Validate/Activate ceremony.

Success makes an enabled library selectable. Storage/root changes return to that root; a name-only
edit preserves a valid directory. Disabled results remain labelled/recoverable. Changes are
configuration-only and never create/move/migrate/delete physical contents. Reference-protected
removal differs from Delete of interior entries. Invalid/duplicate/stale input, failed checks,
persistence or activation/runtime errors preserve prior Active and correctable fields; refresh
stale authority and explicitly resubmit only after unknown outcomes have been verified.

## CURRENT — MediaLibrary files and separate ResourceLibrary navigation

- **Goal/entry:** maintain destination files at `媒体库` (`/ui-v2/medialib/files`). Old `/ui-v2/library`
  and `/ui-v2/library/files` provide explicit recovery links without automatic work or redirect.
- **State/action:** the shared cards/exact breadcrumbs/list-grid/selection/paging, without a page-local directory tree, ordinary
  maintenance and Add/Edit/removal above. No library-card statistics/placeholders/thumbnails or
  thumbnail collection. Per-file size, selected count/known size and bounded impact remain visible.
- **Success:** live entries are independent of prior organization/index membership, and enabled Save
  publishes actual Active. Copy/Move uses MediaLibrary endpoints for both sides on same/across Storage;
  equal IDs never exchange ResourceLibrary/MediaLibrary scope or evidence.
- **Failure/recovery:** missing Active/library, unavailable root, denied/unsupported action, conflict,
  stale input, partial or unknown effect stays per-item. Use Web configuration/re-enable, choose another
  library/root, refresh/revalidate or inspect durable Task/results. No replay on refresh/reconnect.

No MediaLibrary Organize/Scan/Preview, general cross-kind direct transfer, browser Upload/Download or
arbitrary media edit. Source Files retains its separate organization and return context.

## CURRENT — Live lists without FileIndex

CLI `mediaflow files list`, ResourceLibrary Files and MediaLibrary share the same bounded live
Storage browse. Select exactly one library kind/ID and relative directory; preserve exact names,
kind-bound pagination and unknown totals. Missing Active/library, confinement, stale cursor,
permission and Storage failures explain the next safe read/configuration action, never an empty
index fallback. Listing creates no catalog/observation/work/result/authority or Provider/Hash/media
effects and does not initialize or upgrade a database.

FileIndex products, global catalogs, repositories, schema and sync/reprocess/repair dependencies
are removed. Old indexed inputs provide library-browse/Task Center guidance without a compatibility
engine. Explicit organizing/maintenance/recovery retains work-scoped source evidence, plans, pins,
results and audit; no existing runtime data or media is cleared.

## Manual organize

- **Goal/entry:** explicitly organize selected live ResourceLibrary files or bounded folders from
  Files only. Task Center continues existing admitted work. MediaLibrary is not a source, and
  indexed paths provide no admission.
- **State/action:** exact source identities, durable intent, allowed recognition/metadata/classification
  choices, zero-mutation plan/attachments/conflicts/capabilities/effects and selected items. The
  Files command admits its durable pinned task before business readiness; rule/metadata/target/
  conflict resolution then happens inside that work. Review
  the plan and separately confirm exact execution plus any permitted overwrite/source cleanup.
- **Success:** server-held short-lived single-use authority binds authenticated principal, immutable
  plan/configuration/item subset/effect scope; atomic execution admission consumes it inside the
  already admitted organizing work.
  Worker rechecks reviewed Storage/path/fingerprint directly and OrganizerExecutor executes only that
  scope. No CLI issuance, raw token transfer or FileIndex re-resolution for normal V2 work.
- **Failure/recovery:** source/plan change, stale permission/pin, conflict, capability or pre-mutation/
  partial/unknown effect explains durable state per item. Re-analyze the legal scope and obtain fresh
  intent when necessary; completed/ignored/uncertain siblings are not re-executed.

V1's explicit one-shot token remains an administration/API-automation/support mechanism, never a
replacement for the normal V2 journey. Source preparation cannot accept browser-provided raw Storage
paths, fingerprints, occurrences or IDs as execution authority. In-context summary/confirmation
belongs to the admitted task and its exact preparation; no independent Preview product remains.
Files keeps bounded task/preparation history and exact unknown-request reconciliation after close/
reload/reconnect, without the former center discovery list or guessed request/library. Generic new
URLs guide to Files without work; valid prepared-work links keep their legitimate exact context.
Browsing/separate analysis creates no organizing task or execute intent; admission/decision Save
does not authorize media effects. Four business blockers stay native to the admitted task.

### CURRENT — Bounded folder organization with safe discovery restart

Explicit Files-originated discovery inside the admitted task shows pinned scope, progress/exclusions,
real stability waiting and read errors before freezing sources for exact planning/confirmation.
At most 100 selected scopes and 100 primaries; confinement, pinned depth/budgets and real stability
apply to direct and walked files. Direct file business checks are same-source unfinished work and
explicit extension exclusion; a merely unlisted suffix or automatic include/rule miss cannot veto it.
Selected folders retain configured primary-media extensions, defaulting to video, and existing
attachment settings: pictures/subtitles/NFO are not standalone primaries/problems, artwork-off does
not promote them, other-same-stem remains effective, and unassociated files stay at source.
The folder task exists before traversal; concrete discovered sources are atomically reserved at
item admission across manual/Automation/continuation work. Equal names are not source identity,
eligible siblings remain independent and a finished history row is not a perpetual entry lock.
Matching enabled trailers attach to the retained main even in explicit mixed selection. Exact legal
long names survive handoff; first stat/old mtime/lost observation is not a stable-size interval.

Cancellation is cooperative; Pause/resume-from-pause is retired. If safe unfrozen continuation cannot be proved, retain
stage/findings/zero media effects, settle/fence the old attempt and offer visibly distinct explicit
new discovery. No automatic restart on read. Unknown admission recovers the proved original request
or stays unresolved with native inspection, never another root/pin or a guessed newer attempt.

Read errors preserve unaffected findings for an explicitly reviewed known subset. Material bounds
cannot expose an executable first-N prefix. Repeated/concurrent Freeze converges on one linked intent.
Seamless continuation across every old duplicate, activation/crash/control combination remains
explicitly deferred; exact pins, source checks, independent results and non-replay are mandatory.
Discovery controls/progress/readiness and return-to-Files remain in the exact admitted task/
preparation context, with no global discovery block.

## Tasks, results and per-item recovery

Use All/Running/Attention/Ended plus Recognition/Metadata/Classification/Conflict over the same
backend-authorized organizing population, before counts/paging/options/detail. Ordinary-file,
notification and separate analysis-only work stay outside; no center new-task picker/global Worker/
discovery/manual-operation blocks or their exclusive landing reads remain. Normal manual initial
WaitingConfirm stays unfinished in Running/All with exact summary access, outside Attention.
Attention/pending tasks are the distinct four-type union; type/file counts stay distinct. Required
human decision→analysis→summary/confirmation steps retain their four-type lineage, while plain
queued/running follow-ups do not invent a human blocker. Real resolution clears the problem; a new
business blocker changes type, a solely technical follow-up failure becomes factual All/Ended history.
Only a durably completed Task plus verified exact linked success for every necessary item permits
recovered display, without rewriting attempts or double-counting recovery. A failed Task stays failed
even if every file succeeded. Mixed technical/ignored/uncertain siblings
never become all-success just because the business problems cleared. Provider transport failures are
not Metadata decisions, and other terminal failures have no separate failure statistics or generic
center recovery guidance/actions. Administrative API/CLI recovery remains outside this V2 UX.

- **Goal/entry:** find one admitted run from Task Center, Files, Dashboard, Automation or a Task
  deep link, then understand and safely resolve its actual files. Default list has no open detail.
- **State:** All eight views expose only creation-date range selection and clear; clearing restores
  the current view's complete authorized population. This applies to the page-level task list;
  detail and problem-handling inputs retain their own scope. Time, valid paging and counts use
  the complete server-authorized population, alongside historical name/scope/trigger;
  queue/Task stage/item outcome/problem/effect certainty are distinct. One admitted Task counts once across its durable discovery/analysis/execution links;
  admission/pre-start failures and original occurrences/attempts remain visible.
  Task and file counts differ; attention overlaps and ordinary queued state is not a human blocker.
- **Action:** inspect detail, source/target/policies, completed primary/attachment steps, relevant
  audit/logs and bounded secret-free JSON; use backend-advertised cancel or four-type continuation or enter the
  current task/type's recognition, Metadata, classification or conflict handling. Other technical/
  uncertain failures remain factual read-only All/Ended history, with no generic center recovery.
- **Success:** durable per-file Results and linked recovery attempts survive reload/reconnect/restart.
  File or recovery success cannot overwrite Task flow failure or unavailable state. Current Active cannot rename
  historical work or substitute its legitimate pinned context; unavailable totals never become zero.
- **Failure/recovery:** show missing/stale Worker, pin/dependency, denied/stale decision, source change,
  known partial or uncertain effects as factual history. Four-type decisions and supported live
  controls retain legal next actions; no generic terminal-failure recovery is added. Keep input and
  successful siblings. Controls
  distinguish request from acknowledged effect; they do not interrupt an in-flight call or roll back.

Continue rechecks exact remaining safe scope, current authority and fences; consumed one-shot
permission is not reissued and withdrawn scheduled intent is not bypassed. Recognition selection/
ignore, persisted Metadata candidate/correction/ignore,
classification and conflict use backend-offered legal inputs. Saving is non-executing. Bounded single/
batch failed-analysis recovery keeps independent admitted/refused items and linked original history.
Repair dependencies or save a legal decision, explicitly re-analyze, handle any new blocker, inspect
new summary/remaining steps and confirm the eligible subset. Admission/running is not resolution;
repeated failure supplies its new cause. Original pin unavailable means refusal/recovery guidance,
not silent repinning or arbitrary historical Reprocess. Unknown effects offer evidence/source-target
inspection/log-export only, never retry/force-replay/automatic rollback.

Primary verified success remains complete despite attachment failure/unexecuted/conflict warnings.
Retain each attachment's cause/source/target/completed steps and guidance from actual fixed
OrganizePolicy; human movement is only a policy-permitted example. Warnings remain visible, no
attachment-only automatic recovery or main-file replay. Preparation-only unready findings stay in
preparation and do not fabricate execution recovery work.

## Scheduled unattended organization

- **Goal/entry:** save bounded ResourceLibrary/scope/schedule intent in Automation, review its source,
  limits and policy effects, then explicitly enable or save an enabled successor.
- **State/action:** create defaults disabled with explicit optional enablement; copy stays disabled. Checked publication validates current execution and
  configuration permissions. Enabled supplies scheduled intent without an independent grant or
  mandatory pre-analysis. Enablement creates no immediate work; due occurrences need no per-run click.
- **Success:** Scheduler admits one immutable pinned Task; Worker/TaskItem/Result and OrganizerExecutor
  perform full planning/source/capability/conflict/authority checks and preserve independent results.
- **Failure/recovery:** disable/removal/current permission loss stops future admission and remaining
  scheduled effects at safe boundaries, with no rollback or historical replay. Four business problems
  use Task Center decision→analysis→summary→explicit continuation; other failures retain truthful history.
  Healthy empty is no-work; unstable/unreadable/incomplete is never fabricated empty success.

Run once is a separate explicit execution of the saved scope, even while disabled, without changing
its schedule or requiring another initial confirmation. Full bounded traversal and real stability
precede effects. Old grants/revocations and analysis records remain history; they cannot override
Enabled or execute an old preparation. Only automatic organization remains; Scan/Preview/FileIndex
products remain absent. Run once retains min(definition itemLimit,100) and complete traversal budgets.
Both automatic entries retain real age/size stability: age uses the larger configured minimum-age/
modified threshold; nonzero stable-size requires unchanged observations separated by real elapsed
duration, never old-mtime inference. If no files are ready and unstable candidates
remain, perform at most one wait/re-scan when the shortest remaining interval is in (0,60] seconds.
Ready siblings proceed without waiting; longer intervals do not synchronously wait. Remaining unstable
files retain independent failures outside Attention; a normally closed Task flow is completed. Later
normal runs use normal scope/checks; no failed-item selection or cross-run observation mechanism.

### CURRENT — Complete native Automation workspace (accepted43, amended46)

Slice47 replaces the former settings tab/four-field form with three System Settings fields.
Historical43/46 acceptance remains unchanged. Current settings follow accepted47, flow/results and
rate follow accepted48, and creation/editing/list Run once follow accepted49 above.

- **Entry/state:** shared-shell `自动化` opens the real definition inventory; name/打开/direct links
  read saved definitions before/after enablement, including truthful disabled/unavailable states.
  Malformed/denied/not-found/read errors remain bounded; no grant-eligibility dependency returns.
  Inventory provides `任务列表 / 执行记录`, population metrics,
  source/scope/schedule/timezone/limit, next/latest outcome and distinct
  published/enabled/execution-readiness states. No editor opens automatically or sample data appears.
  One Chinese content title, flat tabs and readable controls align with Task Center/Files on desktop
  and narrow screens. Routine statistics/tutorial paragraphs are omitted; unavailable metrics retain
  their correction guidance, and wide tables scroll inside the workspace rather than the page.
  The standing header refresh button is removed. Failed list/record reads keep their local reload
  action; successful create/edit/copy and other existing commands read back the current list. Opening
  the create card still reads its required authority/definition without changing a header button.
- **Create:** `自动化 → 新建自动化任务` opens one Chinese card over the current list; the creation
  deep links reach the same experience. Enter a name, choose a ResourceLibrary and its whole scope
  or a bounded subdirectory, then set the interval/daily/weekly/advanced Cron schedule and item limit.
  Internal ID is generated automatically. Cron timezone and backend-calculated upcoming times are
  explicit; preview writes nothing and supplies no execution authority. The default `创建任务` publishes
  a disabled definition; explicitly selecting enablement changes the action to `创建并启用` and publishes
  the enabled definition atomically with checked scheduled intent. Neither starts immediate work.
  The limit bounds the complete source scope; overflow requires narrowing, never automatic batching
  or first-N execution.
- **Create feedback/return:** unchanged input closes directly; edited input offers visible
  `继续填写 / 放弃修改`. Cancellation, discard and success preserve the list's filters, page, scroll
  and entry focus. Success refreshes authoritative rows/statistics and explains when the new row is
  outside the current results. While submitting, `创建中…` blocks duplicate creation, premature
  reconciliation and accidental navigation. Rejection preserves correctable input; a peer conflict
  requires an explicit recheck before a new create. An unknown response retains the original
  principal/ID/candidate/base identity across close/reopen/reload and offers only `核对本次创建`,
  never an automatic repost or a replacement ID. Failures and exit choices stay visible in the card,
  with field correction and keyboard focus; narrow screens and reduced motion retain the journey.
- **Configure/authorize:** New defaults disabled and can explicitly enable under `V2-AUTO-013`;
  copy starts disabled without inherited authority. Ordinary editing opens the same Chinese card over
  the list with exact saved values and returns there on Save. One focused checked Save
  publishes only the intended definition. Checked enable/enabled-successor Save supplies scoped
  scheduled intent with current execution permission and audit; there is no independent grant or
  mandatory grant analysis. Confirmed Save reconciles the same editor's values/publication identity
  so another Enabled edit/Save works, preserving later typing. Peer conflicts preserve input. Unknown
  edit or a retained earlier toggle uses “核对本次发布” to read exact
  principal/action/candidate/base/activation evidence without reposting; unknown Run once reconciles only its own principal/request identity.
- **Scheduled success:** each valid due occurrence creates one linked pinned run and executes through
  the existing Worker/OrganizerExecutor without another per-run click, with independent item results.
- **Run once:** click the saved row's `运行一次` directly in the list, retaining row feedback and an
  explicit exact-Task link. The edit card has no Run once button. The published definition's saved scope
  supplies a complete bounded manifest without asking the user to pick files again. One explicit
  command admits the organizing Task before readiness and executes ready items without a second initial confirmation. Four-type
  recovery still needs explicit continuation; no schedule advancement or old grant consumption.
  Overflow/incomplete scope refuses execution and explains narrowing/re-analysis, not first-N success.
- **Execution records:** 自动化 → 执行记录 → 查看详情 reads only this execution. Compact rows
  show its current Task flow result, original actual local start/end times, independent file counts and a single
  查看详情 / 收起详情 button. Details contain at most 执行结果和时间 / 失败原因 (failed only) /
  下一步, in concise ordinary Chinese. Missing times are `—`, never creation/update times.
  The record uses the same durable five-state flow as Task Center: normal closure is 已完成 even
  with failed/partial/skipped/ignored files, unknown effects or missing Results. Actual Task flow
  failure is 失败 and acknowledged cancellation is 已取消; file success cannot override either.
  A proven healthy empty scope is independently labelled no work. Pending/running and required
  waiting remain unfinished; a cancellation request is not an acknowledgement. Unavailable Task
  truth remains unavailable, unreadable/truncated reasons are explicit, and uncertain
  effects say to check first and not repeat. Cancelling one admitted run through Task Center's
  existing controls is distinct from disabling an Automation definition.
- **Result/reason/next step:** success says this run needs no repair, not that the source was fully
  exhausted. Unfinished work says to wait; policy skip identifies the relevant files/settings;
  cancellation says this run was cancelled and completed operations remain. Errors identify what
  to check; correcting configuration is not recovery of the old Task and never promises auto-retry.
  No recovery tutorial, Task Center/definition links or
  local decisions/execution controls appear in records. Those workspaces retain their independent
  entries and responsibilities. Legal continuation changes current flow result and statistics without
  adding a run or rewriting original times/attempts/file effects.
- **Read/failure recovery:** the same Task-flow outcome filter is applied server-side to the
  whole authorized population before count/paging. Definition/trigger/time filters, clear, refresh,
  forward/backward paging and reconnect preserve exact conditions; stale/invalid filters/cursors
  are bounded read refusals. A failed read offers refresh and filtered reads can clear conditions.
  Expanding/collapsing and reads create no work or Provider/Storage effects. Pre-Task failures and
  unknown handoff remain truthful; missing Task linkage never authorizes replay. Raw API outcomes,
  independent recovery evidence, latest outcomes and metrics retain their own existing semantics.
- **Read/save safety:** stale/failed Save retains Active/input; reads/refresh/paging create no work or
  Provider/media effects. Preparation-only findings remain distinct from execution failures.
- **Settings:** open System Settings for the one compact three-field form and checked Save. Capacity
  counts queued/claimed organizing Tasks across all triggers; wholly human-waiting work uses zero.
  It is not thread/file parallelism. Worker/Scheduler polling is adopted by the actual resident
  consumers without routine restart, with published/adopted/pending/override/unavailable readback
  and concrete repair guidance. The retired stale-age key has no runtime meaning; immutable
  documents containing it remain readable. Current heartbeat/lease/call-timeout judgments remain.
  Each fresh live instance must prove its own adoption. Stopped/expired predecessors remain folded
  diagnostic history with a bounded display and real total; they neither veto nor prove current
  adoption. A healthy replacement restores completion, while missing services, unreadable evidence
  and any real live pending/overridden replica still refuse collective success.

## Operations administration

Configuration/Settings manages exact Active/successor and reference-safe object lifecycle; versioned
secret-free configuration/result exchange stays explicit. Notifications manages Webhook definition/
events/secret references, exact test, enable state, deliveries, leases/dead letters and recovery.
Actions share RBAC/audit/validation and preserve prior Active/correctable input on failed Save.

Delivery failure never changes media results. Retry/requeue is scoped to the delivery, with bounded
safe backoff and durable target identity; missing/changed target waits/refuses rather than silent
retargeting. Correct endpoint/secret/configuration then explicitly use its permitted recovery.
Payloads/secrets/raw exception details are not read-projection fields. Settings target publication
must not be confused with a resident consumer's actual adopted value.

## Docker self-hosted operation

Start/inspect/restart/backup and same-version recovery from [Deployment](deployment.md); verified non-overwriting
offline restore is in [Release](release.md#offline-restore-procedure). Four independent services,
local `/data`, explicit Local media mounts and non-root permissions retain process isolation.
TLS/certificates/proxy/public exposure and environment-secret injection are deployment-owned.

Worker/Scheduler/Notification Worker start and wait without Active/media mounts, then adopt eligible
configuration without routine restart. Scheduler never uses stale configuration; Notification Worker
never burns targetless claims or retargets durable deliveries. Older intact work pins remain usable
independently of new-admission Active; broken pins fail before mutation. Process liveness, DB/schema/
registration/heartbeat and command/pin readiness are separate; no-Active waiting is not a dead process.
Recoverable DB/config faults retain processes/work with bounded reasons. No API process supervision.
Adding mounts may recreate containers; publication alone does not. Schema/mount/permission/secret/
schema-readiness failures preserve durable work/backup and never replay uncertain media.
Old-task/Job conversion and cross-version upgrade/rollback remain outside current support.

## V2 Operator Web migration

The shared responsive light shell provides persistent navigation, identity/connection controls,
safe deep links and bounded return context. Root opens Overview/Dashboard. Memory-only token auth
continues supported routes; reconnect never replays work. A 401 clears rejected authority/query state;
a 403 retains identity and offers legal navigation. Disconnect clears token/cache/intended route.
Show loading/empty/success/transport/malformed/unauthorized/forbidden/unavailable/not-found distinctly.
Dashboard/refresh/list/navigation are read-only, with no Provider/work/mutation. The
[Slice51 TARGET](#target--v2-explore-homepage-slice51-planned) separately plans the future V2 homepage
replacement and explicit external metadata/artwork reads; it is not CURRENT. No independent Node
production service, replacement identity model or implicit V1 cutover is introduced.

### Task Center integration

[Tasks, results and per-item recovery](#tasks-results-and-per-item-recovery) owns the organizing
journey; [Task Center specification](task-center-page-spec.md) owns eight-view interactions, exact
summary/confirmation and native four-type forms. Supported same-version Task links resolve into that
exact organizing context or the proven ordinary-operation library page; missing/denied/unavailable
identity stays a bounded read-only explanation, with no generic failure recovery or guessed work.

The center has one page title, with content boundaries and spacing coordinated with MediaLibrary.
The shared shell keyword input is not shown there. The selected tab supplies current-view context;
no duplicate view heading or generic description appears between the tabs and filters. All eight
views share a compact 创建日期 group with independently named native 开始日期/结束日期 controls,
apply either or both sides without a search submission, and clear back to the current view’s
complete authorized population. The toolbar's low-emphasis 清除 appears when a date is set;
existing empty/read-error recovery entries remain available in their applicable states.
The summary's routine population/pagination/deduplication explanation is omitted, as are the 本地时区
label and 时区说明 control/content. Local-calendar filtering, full end-day inclusion, explicit
list/detail time offsets and authoritative statistics/deduplication retain their existing behavior.
Filters and table align, and controls wrap without clipped text or page overflow when narrow or
when the selected detail reduces available space. Manual refresh shows 刷新 / 刷新中… without layout
jumps; background polling updates quietly. Normal same-query refresh preserves
visible lists/details and valid context; real changes and read/permission failures remain visible.
Management-API consumers outside that control keep their existing filter semantics.
Long names/scopes retain readable status/progress columns and complete mouse/keyboard-accessible
identity. Using the shared Files sidebar entry opens ordinary ResourceLibrary browsing without a
task-center return button, including when leaving a Files visit that already carried one. Explicit
task/preparation/organizing links retain their own exact return context through reconnect; ordinary
page navigation does not start a new organizing journey or discard durable work.

### CURRENT — FileIndex 退出与 CLI/两种库页实时列表（Slice45）

[FileIndex retirement design](file-index-retirement-spec.md) and `V2-FILES-005/006` define the complete
CLI/ResourceLibrary/MediaLibrary same-library live list journey and removal of all global-index
products/consumers/schema/sync/repair/stand-ins. Browse/refresh/page creates no catalog/observations/
work/authority, Provider/Hash or media effects; explicit work retains exact evidence/results/audit.
Old indexed inputs offer library browsing/Task Center guidance, no compatibility engine or data clear.
No-index real stability→summary→confirmation→execution→recovery/reopen is covered by acceptance.

### CURRENT — 独立 Preview 首次部署退出与分析统一（Slice45）

[Preview 退役设计](preview-retirement-spec.md)、`V2-OPS-013` 和 RO-8 将独立 Preview 产品按
Scan 相同的首次部署标准移除：独立 V1/V2 页面、CLI/API、Job/Task/定时/Worker/继续路径、
专用持久化和运行装配均不存在。旧输入普通 not-found/参数/不支持类型错误，无退役页/410/
提示/兼容执行器或自动转成整理；不建设旧 Preview 停止/接管、迁移、历史或 V1 parity 服务。

操作者在整理创建/Files 或原任务恢复界面显式分析，直接检查当前计划摘要和逐项原因，选择
合法就绪子集后明确确认。CLI organize 不带 --execute 继续显示完整零媒体变更分析。
独立分析的未就绪或冲突留在准备上下文，不产生正式执行待办或权限；明确 Files 整理或
Automation Run once 已受理的任务则在四类原生恢复中补充决定、重新分析并明确继续。
来源/计划变化需更新摘要和意图，成功/未知效果不得重放。

Rules、配置检查和整理执行前的内部校验复用共享分析/精确计划，并保持原候选配置/定义/
权限边界；无需用户管理独立 Preview Task。支持工作的计划/pin/结果/审计和正常重启恢复
保留，不清空媒体/运行库。Automation 的现行工作区、Enabled/运行一次行为按上文，
不由退役要求另行产生权限或功能范围。
这是整 Slice 验收后的 CURRENT；没有把 Task45.4 Scan PASS 代替 Preview 退役验收。

## V1 and post-V1 boundary

V1 `/ui` and shared API authority remain until explicit cutover/parity acceptance. Current delivered
workspaces do not include cross-Task bulk mutation, arbitrary historical Reprocess, universal rollback,
automatic uncertain replay, Provider switching/new production Providers, built-in users/session/OIDC,
general Secret Store or specialized email/chat/media-server channels. Selected45 cross-Task problem
lists supersede earlier deferral of those lists only. Active/frozen scope and earlier accepted
exceptions are authoritative in Slice/Progress; documentation consolidation does not extend them.
