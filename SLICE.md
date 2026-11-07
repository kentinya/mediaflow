# Slice 51 — V2 探索首页替换 Dashboard

```text
Slice ID: 51
Name: V2 Explore Homepage Replacing Dashboard
Owner: A — Slice Owner / Architect / Final Reviewer
Status: ACTIVE
Base SHA: 214b69b1e64b24fc22068c2e1760cd1b0c6ac787
Implementation Head: NOT SET
Working Branch: main
Development Authorization: IMPLEMENTATION AUTHORIZED FOR ACTIVE TASK 51.2 ONLY
Risk: Medium
Final Test Level: T3
Next Action: DEVELOPER IMPLEMENTS TASK 51.2; B ACCEPTANCE PENDING
```

## Authority and accepted baseline

用户先要求只调查首页的美观、可读性和内容定位，随后要求改为类似 MoviePilot 的探索页，
明确“直接替换 Dashboard，不做跳转兼容”，最终授权按“浏览 → 筛选／搜索 → 查看详情 →
返回”的完整探索体验规划 Slice。此前仅授权 A 的范围与文档规划，未开始产品实施。
用户随后授权按范围复核结果收敛：取消详情独立深链／刷新重连恢复、无 Active 独立启动的
必需承诺，不锁定认证同源图片代理／缓存；测试按实际影响分级，必要安全边界保持。
用户进一步明确“Dashboard API／CLI 也删了，完全删除不做兼容”：本 Contract 将退出范围
扩大到 Dashboard 的全部运行入口和专属实现，替代先前保留统计 API／CLI 的边界。
用户于 2026-11-07 进一步明确“没问题就激活 Slice 并代替 B 规划第一个 Task”：
同一代理先以 A 身份提交 ACTIVE Contract，再按用户明确授权代替 B 规划首个 Task；这是
角色例外披露，不构成独立验收或 A Final Review。用户随后明确“激活 Task”，将已提交的
Task51.1 草案转为正式活动实施 Task。Task51.1 后经独立 B 验收 PASS，完整结论与限制见
`01f4e05d5cc03822d2e9ced3dfa91a2838990f62:TASK.md`。
用户本轮明确“激活Task”，授权实施已修订的 Task51.2：Dashboard API／CLI、专属后端与
消费者完整退出。B 按该明确指令仅同步授权／阶段事实，Required Outcomes、边界和测试
等级保持；这不是 A Final Review。本次只激活 Task51.2，尚未开始其 Developer 实施，
不推送或部署，不扩大 Slice／Task 边界。
生命周期、Git、测试和关闭规则统一遵循 [Development Workflow](docs/development-workflow.md)。

规划开始于 `main` / 上述 Base；治理检查 PASS，工作区和 Git 可写。预存的
`mediaflow/.DS_Store` 修改以及未跟踪的 `.DS_Store`、本地日志、`15`、`output/` 调查产物等
全部保留，不纳入 checkpoint；不读取或修改用户运行数据库、私有配置或生产媒体。
Base 固定为本 Slice 规划前的接受基线，后续规划／激活提交不重设 Base。

[Slice50 原 Contract / A review](https://github.com/kentinya/mediaflow/blob/214b69b1e64b24fc22068c2e1760cd1b0c6ac787/SLICE.md#final-validation-closure-packet-and-a-final-review)
保持 PASS / CLOSED，原 Base `6cd881f0311c9e53bfc6b0ab754bfbe9acefbfd0`、已审实现
`6b0927328a7bf0873faffce9cb38007fd4607764` 和全部延期不变。后续独立修正
`PATCH-20261107-1` 的 B PASS、已审范围与证据指针继续保留在 `TASK.md`。本 Slice 不重开旧工作。

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

定义见 [V2 Requirements TARGET](docs/v2-requirements.md#target--v2-explore-homepage-slice51)，
完整旅程见 [Product Experience TARGET](docs/product-experience.md#target--v2-explore-homepage-slice51)，
边界见 [Architecture TARGET](docs/architecture.md#target--v2-explore-homepage-slice51)。
本规划替换 V2 的 `REQ-WEB-002` 首页职责、原 Dashboard 无 Provider 读取约定，并退役运行中
Dashboard API／CLI；原 `V2-TASK-005/014` 等 Dashboard 消费者义务仅在这条退出垂直取消。
`REQ-WEB-001/005/006`、`REQ-API-002/003`、`REQ-META-001–004/009/010`、`UX-001–010`、
`REQ-SAFE-*`、`V2-UX-001–013` 及既有认证、处理流水线、任务／文件独立结果和非重放保持。
Task51.1 已获 B PASS；Slice 尚未整体接受，CURRENT／TARGET 的整体协调由 A 最终接受后完成。

## Initial investigation and evidence limit

以下为 Slice 规划基线调查；当前阶段和已完成 Task 见本页末及 `TASK.md`。

- 当前 `DashboardPage/View`、dashboard entity/query 和 Shell/Entry/Router 仍以旧统计页为
  默认，引用 `/dashboard`。调查看到英文统计卡、技术时间和类别码、已退役状态与旧列表链接。
  本地隔离 fake API 的统计跳转复现落到旧 Task 列表说明页；这不是本 Slice 修复验收。
- `MetadataProvider` / `TMDBProvider` 已支持搜索、详情、图片引用、超时、重试和缓存；尚无
  独立探索列表、面向浏览的分页／评分模型和作品详情 Web API，图片展示也需按实际方案接入。
  服务端 TMDB 凭据来自部署环境；现有图片路径字段不能直接成为可信 URL，现行 CSP 默认
  仅允许同源。这些事实要求接入可用链路，不构成必须新增认证图片代理的理由。
- 后端仍有 `/api/v1/dashboard`、`mediaflow dashboard --recent-limit`、CLI 分派／渲染、
  Dashboard domain/application 和 SQLite 专属聚合；API runtime binding 仍注入该服务及
  库计数。旧 `operator_ui.py` 仍调用 Dashboard，部分原生／打包／安全测试也把它当认证
  探针。全量退出需移除或改接这些消费者，不能只删 HTTP 分支后保留专属后端或悬空调用。
- 对照 [MoviePilot V2 探索入口](https://github.com/jxxghp/MoviePilot-Frontend/blob/19cead06f72c859732afdeccea7a37c0a770a947/src/pages/discover.vue)、
  [TMDB 筛选视图](https://github.com/jxxghp/MoviePilot-Frontend/blob/19cead06f72c859732afdeccea7a37c0a770a947/src/views/discover/TheMovieDbView.vue)
  与海报列表／详情源码；探索与推荐是不同入口。本 Slice 不引入多榜单推荐页。
- 接口依据为 TMDB 官方 [Movie Discover](https://developer.themoviedb.org/reference/discover-movie)、
  [TV Discover](https://developer.themoviedb.org/reference/discover-tv)、
  [Images](https://developer.themoviedb.org/docs/image-basics) 和
  [Attribution](https://developer.themoviedb.org/docs/faq)。引用是交互／接口依据，不是媒体样本。
  未部署或登录 MoviePilot 做验收；未调用用户凭据／真实 TMDB 验证本 Slice，不声称已实施。

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

激活后 B 规划连贯 Tasks，并负责验收和 Slice 最终验证：覆盖探索 Provider／API／Web 与
直接受影响的认证／默认导航／共享弹卡回归，完成相关静态检查、生产 Web 构建，以及真实
Python API＋本地假 TMDB／图片的桌面／390px 全旅程。按 AC 验证成功、无效输入、条件／
请求竞态、失败恢复、权限／脱敏、图片来源和零媒体变更。全量 Python／Web／E2E 只在
具体共享影响或 T4 重评需要时运行；安装包／Docker 门禁只按实际交付变更和工作流适用性
安排，不新增全发布矩阵，也不为未改动的处理引擎单独增加验收工程。
另按 AC-11 使用正常环境／合法身份及受支持接口对照，验证旧 API（含原查询参数／已注册
入口）的未知路由 404、CLI help 注销及旧命令（含原参数）的解析层拒绝。通过代码／引用
审查确认无专属服务残留，不以错误状态或字符串全清作为唯一证明；检查 API 构造／配置
绑定、其余 CLI 命令／共享统计和既有持久记录不回归。公共鉴权、审计、日志／初始化允许，
禁止的是旧请求额外触发的 Dashboard／外部 Provider／媒体／任务／配置业务效果。
对改接的认证／打包／安全探针运行其直接受影响检查，不删除原证明或改成自动联系 TMDB。
Developer 只运行当前 Task 新增／修改及直接受影响测试与静态检查，B 承担所需更广回归。
使用临时根、fake／mock 和本地服务，不依赖真实 TMDB、用户凭据或用户媒体。本次规划
修订只做治理、范围／链接和 `git diff --check`，不把未来功能／集成验收记为完成。

## Final validation, Closure Packet and A Final Review

Implementation Head: NOT SET（Slice 最终候选尚未提交）。Task51.1 已经独立 B 验收 PASS：
已审范围 `3c8053b06c218e76084ec1c06cf57f03259da84c..9efe8ccd480b257e12eee29b9b90075ee8f809f6`，
产品实现 `de86eab84e8627c0f656e51cea66e17e8ef1baf2`；原始失败、复现、证据及限制见
`01f4e05d5cc03822d2e9ced3dfa91a2838990f62:TASK.md`，不声称全仓测试通过。
RO-2／3／4 的 Task 范围已完成；RO-1 的 V2 首页已完成，Dashboard API／CLI／专属后端与
旧消费者退出由已激活的 Task51.2（PLANNED，Medium／T3）交付。该 Task 尚未开始实施。
全部结果仍需在最终候选重评；没有 Closure Packet 或 A Final Review，Slice51 保持 ACTIVE。
Slice50 的接受身份与全部延期保持；本次激活不转正 CURRENT 文档或关闭 Slice。
