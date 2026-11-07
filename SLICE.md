# Slice 51 — V2 探索首页替换 Dashboard

```text
Slice ID: 51
Name: V2 Explore Homepage Replacing Dashboard
Owner: A — Slice Owner / Architect / Final Reviewer
Status: PASS / CLOSED
Base SHA: 214b69b1e64b24fc22068c2e1760cd1b0c6ac787
Implementation Head: 30c99f1bdcd9be2cb51ac82f78bc4b07eaea3113
Working Branch: main
Development Authorization: COMPLETE; NO ACTIVE IMPLEMENTATION TASK
Risk: Medium
Final Test Level: T3
Next Action: A SELECTS THE NEXT LARGE SLICE
```

## Authority and accepted baseline

用户授权以“浏览 → 筛选／搜索 → 详情 → 返回”完整探索替换首页，并完全退出 Dashboard
Web／API／CLI 和专属实现、无兼容。详情独立深链／刷新重连恢复、专用无 Active 启动不在
必需交付范围；图片交付按实际依赖选择，T3 及触发 T4 风险时的重评边界不变。

原始 Base 固定为 `214b69b1e64b24fc22068c2e1760cd1b0c6ac787`，即规划前接受基线；
规划／激活／修正与文档治理不重设 Base。Slice50、独立修正 `PATCH-20261107-1` 和更早接受
身份／延期保持，原事实见 `214b69b1:SLICE.md`／`214b69b1:TASK.md`，不重开旧工作。

角色例外仅为用户授权的规划代行：A 代 B 规划首个 Task，以及 A51-01 退回后代 B 补齐修正
计划（`3c8053b0:SLICE.md`、`df5816ae:TASK.md`、`aa35bacf:TASK.md`）。Task51.1／51.2
及修正均另经 B 独立验收，A 最终独立审查原始完整范围；规划代行不构成自验收。
详细授权／调查／失败修正和终审报告见[不可变关闭记录](https://github.com/kentinya/mediaflow/blob/c0a02875e53f249f1ac7d22b9b667c6a453c87b9/SLICE.md#final-validation-closure-packet-and-a-final-review)；
生命周期、Git、测试与关闭规则统一由 [Development Workflow](docs/development-workflow.md) 管理。

没有活动实施 Task；下一大 Slice 另由 A 选择。预存本地／私有文件保持未纳入提交，不读取
用户运行数据库、私有配置或媒体做例行治理；Git 同步按用户授权，不等同发布或部署。

## User goal and requirement mapping

用户进入应用即能以中文浏览电影／剧集海报，按条件找作品或按名称搜索，打开作品详情后
回到原列表位置。参考 MoviePilot 的筛选式探索构成，使用现有 MediaFlow 浅色 Shell 和弹卡
语言；旧 Dashboard 页面、统计模块和 Web 路由直接退出，不另建统计首页或旧入口兼容层。

| Required Outcome | 用户结果 | 稳定需求 |
|---|---|---|
| RO-1 | 探索成为默认首页，Dashboard Web／API／CLI 和专属实现完整退出且无兼容 | `V2-EXPLORE-001/011` |
| RO-2 | TMDB 电影／剧集的真实有界浏览、筛选、排序、搜索与分页 | `V2-EXPLORE-002–004` |
| RO-3 | 美观可读的海报网格、作品详情卡与准确返回 | `V2-EXPLORE-005/006` |
| RO-4 | 完整加载／空态／失败／恢复与安全的元数据、图片读取 | `V2-EXPLORE-007–010` |

定义见 [V2 Requirements CURRENT](docs/v2-requirements.md#current--v2-explore-homepage-slice51-pass--closed)，
完整旅程见 [Product Experience CURRENT](docs/product-experience.md#current--v2-explore-homepage-slice51-pass--closed)，
边界见 [Architecture CURRENT](docs/architecture.md#current--v2-explore-homepage-slice51-pass--closed)。
本规划替换 V2 的 `REQ-WEB-002` 首页职责、原 Dashboard 无 Provider 读取约定，并退役运行中
Dashboard API／CLI；原 `V2-TASK-005/014` 等 Dashboard 消费者义务仅在这条退出垂直取消。
`REQ-WEB-001/005/006`、`REQ-API-002/003`、`REQ-META-001–004/009/010`、`UX-001–010`、
`REQ-SAFE-*`、`V2-UX-001–013` 及既有认证、处理流水线、任务／文件独立结果和非重放保持。
Task51.1／51.2 的原 B PASS、A 首次退回和修正证据保持可追溯；本次 A 终审为 PASS / CLOSED，
需求／旅程／架构和操作指引在同一关闭 checkpoint 协调为 CURRENT，冻结历史身份不变。

## Planning references

规划期现有入口调查、MoviePilot 交互源码、TMDB 官方接口依据及其证据限制保留于
[关闭记录的原调查段落](https://github.com/kentinya/mediaflow/blob/c0a02875e53f249f1ac7d22b9b667c6a453c87b9/SLICE.md#initial-investigation-and-evidence-limit)。
该调查描述实施前基线；当前生产边界见 [Architecture](docs/architecture.md#current--v2-explore-homepage-slice51-pass--closed)，
不将旧 Dashboard／探针接线或“尚未实施”的调查措辞视为现行行为。

## RO-1 — Default entry and complete Dashboard retirement

新增 `/ui-v2/explore`，侧栏显示“探索”，浏览器标题和内容页头一致。`/ui-v2/` 仍通过现有
认证入口，正常连接后的默认目的地改为探索；访问其他合法深链时仍续转原目的地。
更新全部 V2 默认／返回入口、Shell 页面身份与相关认证测试，不能遗漏旧默认路径。

移除旧 Dashboard 页面、专属 entity/query/API 客户端调用与只服务该页的样式／测试／fixture
分支；共享 CountGrid、RefreshControl、其他页面沿用的 CSS 等按实际引用保留，不机械清除。
旧 `/ui-v2/dashboard` 使用普通未找到行为；不保留旧页、重定向、别名、退役说明页或兼容
参数解析，也不在未找到页面推荐旧入口。探索不得继续请求旧 dashboard 数据作为首页内容。

同时移除 `GET /api/v1/dashboard` 及其专属参数解析、注册／路由和审计分类分支，移除
`mediaflow dashboard` 的 CLI 注册、分派、参数、help 与输出渲染，不新增替代统计端点或
命令别名。旧 API 按正常未知路由规则处理，旧命令按正常未知命令／参数错误处理；无
重定向、410／退役说明、空成功响应、适配器或其他兼容层。不保留 Dashboard 专用参数
解释／校验；通用 HTTP／CLI 参数处理、鉴权、审计、日志和既有公共服务初始化仍正常。
旧请求不得执行 Dashboard 专属逻辑，也不得额外联系 Provider、操作媒体 Storage、准入
任务或变更配置；验证以该请求触发的业务效果为界，不禁止进程启动时已有的公共初始化。

删除仅服务 Dashboard 的 domain model／protocol、application service、repository 聚合
方法、runtime binding／构造注入／库计数参数、导入和死代码。按实际引用保留共享能力：
任务中心／自动化／通知／系统状态的统计与只读查询、共享组件和 generic 审计仍正常。
不把专属统计服务换名保留，也不删除 Task／Result／review／notification 表、记录或既有
审计历史，不新增 schema 清理、数据迁移、运行数据删除或跨版本兼容工程。

清理所有可达 Dashboard 消费者，包括现存 V1 `operator_ui.py` 的按钮／默认 view／渲染和
API 调用；这是移除悬空依赖的窄耦合例外，不新增 V1 探索或重设计／恢复其余 V1 功能。
移除专属正向测试／fixture；把共用认证、启动、生产资产／安装包／安全检查中的 Dashboard
探针改接实际受支持且零工作／零 Provider 的读接口，保留原验证目的。必要操作说明改用
探索或现有对应页面，旧命令／接口不再作为支持入口；历史文档／Git 接受事实不抹除。

原九个侧栏主页面中的首页身份由探索接替；其他页面业务及已接受切换／弹卡行为保持。

## RO-2 — Browse, filter, search and bounded paging

首期数据源为现有部署支持的 TMDB，无其他源、切换器占位或隐式 fallback。默认电影、
热度降序；电影／剧集分别查询。文案默认中文，中文缺失时保留 Provider 原名／可用简介，
真实缺项清楚显示；标明 TMDB 来源和必要署名。复用现有部署 Provider 配置和就绪条件；
缺配置时给出实际可用的恢复入口，不专门建设探索初始化或无业务 Active／无库独立运行
模式；若复用现有机制自然可用，不刻意禁用，也不把它升级为额外支持／验收承诺。

- 常用筛选：作品类型、该类型合法的题材、原始语言；更多筛选含年份、最低评分、最低评分
  人数。原始语言不伪装为国家／地区。年份按电影首次上映年、剧集首次播出年定义。
- 排序：热度优先、评分优先、上映／首播日期排序。默认最高评分排序必须有可见的合理
  最低评分人数阈值；日期是数据源提供的日期，不声称全部是本地上映日期或最新一集日期。
- 关键词显式提交进入搜索态，电影／剧集类型继续明确。搜索不把探索的排序、题材、语言、
  最低评分伪装为受支持的全文搜索过滤，也不在一页结果上制造全量过滤。搜索态清楚展示
  已应用条件；退出搜索恢复之前的探索条件／列表上下文。
- 条件变化从新结果集第一页开始，先前响应不能覆盖新条件；影片／剧集同 ID 不混用。
  “加载更多”每次读取下一有界页；保留已加载条目，跨页按 Provider＋作品类型＋ID 去重，
  明确末页与分页失败，不无界自动翻页、不把一页数量当作全量数量。

后端验证允许字段、枚举、年份、评分／人数、关键词和页范围；参数无效时安全拒绝并给
可纠正反馈。具体限值和默认阈值由 B 在 Task 中确定，不要求新增持久设置或 UI 技术参数。
浏览和搜索使用独立在线查询模型，不把关键词当文件名送 Parser，也不自动识别／确认作品。

## RO-3 — Poster grid, details and return

页面以“探索”标题、作品搜索、紧凑筛选与海报网格构成。2:3 海报统一尺寸，始终显示片名、
年份与有依据的 TMDB 评分；评分缺失／无有效评分不显示虚构 0 分。长片名可读且完整名称
可通过键盘／鼠标获取。桌面按宽度自然排列，通常约 6–8 列，390px 窄屏两列；常用条件
直接可用，扩展条件折叠。无大幅轮播横幅、统计卡墙或多层数据源导航占据首屏。

点击海报打开列表背景上的居中详情卡，沿用已有弹卡／滚动锁定／焦点和 reduced-motion
规则，窄屏适配可用高度。展示真实背景图／海报、名称／原名、年份、TMDB 评分／人数、
类型、简介和该类型可用的基本信息，以及正确作品的 TMDB 外链。列表与详情用相同不可变
Provider＋作品类型＋ID；不凭名称猜详情，不把外部信息当本地已拥有／已识别证据。

关闭、Escape 和浏览器后退回到原筛选／搜索、已加载页、滚动和入口焦点。本次只要求
页面内打开详情与返回；不新增独立详情链接或刷新／重认证后恢复该作品的交付要求。
刷新或重认证后按现有机制正常进入探索即可；自然恢复详情也可接受，不要求保持或强制
丢弃详情。其他已支持页面的合法深链续转保持，不跳旧页。
开关详情、切条件／搜索、分页和刷新属于同一主页面，不重播整个 Shell 主页面切换动画。

## RO-4 — Read states, recovery and external-read safety

加载用等比例海报／稳定详情骨架，有效缓存可直接呈现，不人为等待。按实际读取环节覆盖
其可能发生的失败，不把首次／分页／详情／图片与全部错误类别做笛卡尔积。元数据读取的
未完成、真实空／缺失、API 身份 401／403、Provider 配置／凭据错误、超时、429、服务
不可用及畸形返回应按适用入口可辨；公开海报覆盖缺图、网络／CSP 加载失败和占位恢复，
只有实际采用认证图片接口时才覆盖该接口的认证失败。Provider 上游凭据失效不冒充当前
MediaFlow 身份失效。当前条件失败不能显示成旧条件的新结果或无结果。

首次失败重试原读取；分页失败保留列表，只重试失败页；详情失败在卡内重新读取且列表
仍可返回；图片失败显示占位且文字／详情不失效。429 尊重有限退避，不无限轮询或自动
请求风暴。缺凭据说明部署所需的环境变量及重启／重读步骤，不让用户在探索页填或复制密钥。
断开／401 清理身份相关读取状态；若使用图片对象 URL，同时释放这些对象。403 不冒充
空态，也不沿用上一身份的可读结果；公开 Provider 海报不混入本地文件或私有媒体证据。

新增外部读取仅属于明确的探索列表／搜索／详情／图片请求；其他 Shell 导航、状态检查和
库列表不因此调用 Provider。复用部署凭据、Metadata Provider 端口、HTTP 客户端、受限
并发、超时、重试／缓存能力；业务层不依赖 TMDB DTO，探索不更改整理 MetadataPolicy。
图片以来源可信、密钥不泄露、CSP 精确允许和缺图可恢复为结果要求，不强制新增认证同源
图片接口、代理或缓存。B 在 Task 中按实际依赖选择最小实现，可以受限加载 Provider 的
公开海报，也可在确有需要时采用同源交付；不得把元数据凭据放到浏览器、URL、cookie 或
持久存储，不接受任意图片 URL／任意代理地址，也不广泛放开 CSP。
若新增服务端图片代理，必须约束来源／路径／尺寸、重定向、响应类型、大小和时间，拒绝
私网／本机目标、路径穿越和凭据注入；受保护的接口仍按现有后端权限鉴权，不借图片加载
绕权。若使用缓存或对象 URL，则落实相应容量／TTL／权限边界和释放；不新建媒体索引或
触碰用户媒体。上述按实际方案验证，不为未采用的技术路径增加建设和测试要求。

本旅程零媒体 Storage 读取／变更、零 Task／执行 authority／配置发布；不启动 Worker、
扫描、识别、整理或通知。保留原流水线、精确 Active／pins、RBAC、审计脱敏、来源 confinement、
C 使用 A 的 Naming／Classification 仍为 C，以及成功／未知效果不重放。

## Required surfaces, boundaries and explicit deferrals

必需表面：React 路由／认证默认／Shell 导航、探索列表／筛选／搜索／分页、作品详情与返回、
Python 探索 application/API、Provider 抽象扩展／TMDB adapter、安全可用的图片展示、必要
请求控制／CSP、直接受影响测试与操作说明。复用现有配置、缓存与组件，只按实际依赖改
共享结构，不重构整个设计系统，不把具体图片交付技术写成额外必建平台。
Dashboard 全垂直退出所需的 CLI、Python domain/application/repository/runtime 接线、旧
消费者及测试／探针／操作说明清理也属必需表面；具体依赖清单由 B 按实际代码制定。

明确不含：豆瓣／Bangumi／AniList 等新源、推荐榜单／个性化／轮播、订阅／收藏／想看、
资源站点搜索／下载／播放、演员或相似作品扩展旅程、完整季集浏览、“已入库／缺集”判断、
本地文件匹配或从海报直接整理、全库媒体数／FileIndex 恢复、新账户／权限模型、凭据编辑器／
Secret Store、全局代理管理、任务队列／引擎／schema 重设计、除 Dashboard 消费者断接之外的
V1 改造、独立统计问题修复、生产连接／部署验收。详情独立深链与刷新／重认证恢复详情、
无业务 Active／无库的独立启动支持也不在本次必需交付中。保留其他 Slice 的所有延期。
这里的非必需能力表示不专门建设或追加验收义务；复用现有机制自然具备时无需禁用，
不能反向要求“刷新必须丢详情”或“无 Active 必须失败”，也不由此扩大正式交付范围。

## Acceptance and final validation

| AC | Required evidence |
|---|---|
| AC-1 | 认证默认和所有 V2 首页／返回链接进入探索；合法其他深链续转保持；旧 dashboard 普通未找到且无重定向／别名／说明页；旧前端专属代码和请求退出，共享组件正常。 |
| AC-2 | 电影／剧集、类型题材、语言、年份、评分／人数与三类排序有真实后端参数／结果，非法组合安全拒绝；日期／评分含义准确。 |
| AC-3 | 搜索提交、类型、清空／退出与原探索上下文完整；无探索专属参数假搜索或页内全量假筛选。 |
| AC-4 | 下一页／去重／末页／分页失败／有界资源可证；快速类型／条件／关键词／作品变化不串响应，跨类型同 ID 独立。 |
| AC-5 | 桌面与 390px 海报、长标题、缺图／无评分、中文回退、骨架、键盘和 reduced-motion 可用，无溢出或首屏被无关信息占满。 |
| AC-6 | 页面内打开准确作品详情，字段／来源外链真实；卡片关闭／Escape／后退恢复条件、已加载列表、滚动和焦点；不要求独立详情入口及刷新／重认证恢复该作品。 |
| AC-7 | 各读取环节覆盖其实际适用的加载／失败和独立恢复，不做错误类别全组合。元数据 API 的身份 401／403 与上游配置／凭据、超时／429／5xx／畸形返回区分；公开海报验证缺图／加载失败，认证图片接口仅在采用时验证鉴权。失败不冒充空态，成功区域保留。 |
| AC-8 | 元数据 API 复用后端认证，参数／Provider 请求有界，图片来源可信、CSP 精确、密钥不泄露；代理／缓存／对象 URL 仅按实际采用方案验证其边界，不要求建设未采用的路径。 |
| AC-9 | 在现有合法配置／就绪条件下探索可用，缺配置有准确恢复；无需建设专用启动／初始化流程，不操作媒体 Storage、不准入 Task、不授予执行权或发布配置，不影响既有配置／整理／任务语义。自然可用的非必需场景不作预期失败断言。 |
| AC-10 | 生产构建资产通过真实 Python API＋本地假 TMDB 及图片响应的桌面／窄屏完整旅程；CURRENT／TARGET 与操作说明在接受后准确对齐，原接受身份保持。 |
| AC-11 | 在合法 READ 身份、正常配置且受支持对照读取成功的环境中，旧 API 返回通用未知路由 404；CLI 顶层 help 无 Dashboard 命令，旧命令在解析层按未知命令拒绝，不能用权限／配置失败或泛化的“非 200／非零退出”代替。结合代码／引用检查证明专属实现、接线和消费者清除；不要求共享 CSS、历史记录和负向测试中的 dashboard 字符串消失。无兼容或请求触发的额外媒体／业务变更，公共处理与原测试目的、共享统计／历史保持。 |

Final Test Level **T3 — INTEGRATION**：按复用现有认证／配置和请求控制、只读探索 API／Web
及可信公开海报展示评估跨层集成风险；不再用预选图片代理作为整套 T4 的依据。此处不是
安全豁免：B 根据实际网络访问、权限／凭据隔离、Active、schema、核心流水线／并发执行
安全等影响判级；达到工作流 T4 风险时，必须在实施前提高相应 Task／Slice 等级并执行其
门禁。图片代理模块的存在与否不能单独决定升级或降级，也不能沿用 T3 绕过必需安全验证；
改变本 Contract 边界仍须 A checkpoint。
Dashboard 退出增加 CLI 分派、API 绑定／库计数注入、专属 repository 读取和旧消费者的
直接受影响回归，不授权改变权限语义、schema、Task／Result 或核心执行路径来方便删除。

验收覆盖探索 Provider／API／Web、直接受影响认证／导航／共享弹卡、真实 Python＋本地
上游的桌面／390px 完整旅程，以及旧 API／CLI 退出与共享读取／历史保留。全仓和发布矩阵
仅按工作流及实际交付影响适用；没有新增全发布承诺。具体实际执行、未运行门禁和复用
限制见下方终审结论及固定报告。后续本范围若产生产品变化，仍按工作流重新评估风险和验收。

## Final validation, Closure Packet and A Final Review

```text
A Final Review: 2026-11-07
Reviewed Base: 214b69b1e64b24fc22068c2e1760cd1b0c6ac787
Reviewed Implementation Head: 30c99f1bdcd9be2cb51ac82f78bc4b07eaea3113
B Closure Packet: e26b399c682e7c09f4e675b6ebe412f5adcf770a:TASK.md
Decision: PASS / CLOSED
A51-01: RESOLVED
Required Outcomes / Surfaces / AC-1–11: COMPLETE
Next: A SELECTS THE NEXT LARGE SLICE
```

A 审查原始完整 99 文件范围，接受 RO-1–4、全部必需表面及 AC-1–11；无剩余阻塞。
探索默认入口／有界浏览与搜索／详情和准确返回／独立读取恢复已交付；Dashboard 全垂直
退出无兼容，共享读取与耐久历史保持。A51-01 的合法零页空结果在原 Task51.1 内修正，
生产 adapter 仅对零结果且空数组归一化，畸形响应仍失败；已从现有页面入口通过整条链路。
没有新 schema、媒体访问／执行权限或核心流水线变化。

| 证据 | 已接受结果及限制 |
|---|---|
| A 独立验证 | 159 Python／142 Web／11 真实 Python 浏览器用例全部通过；含桌面／390px 空结果恢复、分页／详情／返回与零业务效果。产物摘要与 B 匹配；当前网格／空态和同产物稳定详情截图已检视。 |
| B 更新后的最终包 | `e26b399c:TASK.md`：159 Python／67 Web／11 原生与适用静态／构建检查通过；原 Task51.2 的 309 Python、10 原生、共享绑定／历史、V1／探针及干净源码隔离安装证据保留。 |
| 原失败／复用限制 | A 首次退回 `58a74866:SLICE.md` 和 B 原报告 `01f4e05d:TASK.md`／`ab3edf8d:TASK.md` 保留。旧断言／共享夹具／Base 对照、动画中间帧、缺依赖／构建 backend、旧 staging 污染包拒绝和探针抽取失败均未抹除或改写为全仓全绿。 |
| 未验证范围 | 未声称全仓套件、当前 wheel smoke、Docker 发布矩阵、真实 TMDB／用户媒体、生产部署、旧任务迁移或跨版本验证通过。Python adapter 变更后不将旧 wheel 当当前新包证明；本地图片夹具不证明真实海报美术。 |

完整已审范围、精确命令／cwd／结果、历史失败和证据复用理由见
[不可变 A 终审／关闭记录](https://github.com/kentinya/mediaflow/blob/c0a02875e53f249f1ac7d22b9b667c6a453c87b9/SLICE.md#final-validation-closure-packet-and-a-final-review)及其中 B packet。
本机原始材料在 `.git/validation-evidence/30c99f1b/a51-final/` 和各 B 目录，仅本机可用，
不承诺随 GitHub 同步。所有原 Contract 延期、以前接受身份和验证限制继续适用。
本次仅整理现行文档与历史指针，未改变上述验收或实施产品；CURRENT 定义和操作指引保持，
Git 同步不构成发布／部署。
