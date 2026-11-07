# Slice 51 — V2 探索首页替换 Dashboard

```text
Slice ID: 51
Name: V2 Explore Homepage Replacing Dashboard
Owner: A — Slice Owner / Architect / Final Reviewer
Status: PLANNED
Base SHA: 214b69b1e64b24fc22068c2e1760cd1b0c6ac787
Implementation Head: NOT SET
Working Branch: main
Development Authorization: PLANNING ONLY
Risk: Medium
Final Test Level: T3
Next Action: A ACTIVATES SLICE AFTER EXPLICIT AUTHORIZATION; THEN B PLANS THE FIRST TASK
```

## Authority and accepted baseline

用户先要求只调查首页的美观、可读性和内容定位，随后要求改为类似 MoviePilot 的探索页，
明确“直接替换 Dashboard，不做跳转兼容”，最终授权按“浏览 → 筛选／搜索 → 查看详情 →
返回”的完整探索体验规划 Slice。本次只授权 A 的范围与文档规划；不激活、不规划 B 的实施
Task、不修改产品代码、不推送或部署。`TASK.md` 保持 NO ACTIVE IMPLEMENTATION TASK。
用户随后授权按范围复核结果收敛：取消详情独立深链／刷新重连恢复、无 Active 独立启动的
必需承诺，不锁定认证同源图片代理／缓存；测试按实际影响分级，必要安全边界保持。
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
| RO-1 | 探索成为默认首页，旧 Dashboard Web 入口完整移除且无跳转兼容 | `V2-EXPLORE-001` |
| RO-2 | TMDB 电影／剧集的真实有界浏览、筛选、排序、搜索与分页 | `V2-EXPLORE-002–004` |
| RO-3 | 美观可读的海报网格、作品详情卡与准确返回 | `V2-EXPLORE-005/006` |
| RO-4 | 完整加载／空态／失败／恢复与安全的元数据、图片读取 | `V2-EXPLORE-007–010` |

定义见 [V2 Requirements TARGET](docs/v2-requirements.md#target--v2-explore-homepage-slice51-planned)，
完整旅程见 [Product Experience TARGET](docs/product-experience.md#target--v2-explore-homepage-slice51-planned)，
边界见 [Architecture TARGET](docs/architecture.md#target--v2-explore-homepage-slice51-planned)。
本规划仅对 V2 的 `REQ-WEB-002` 首页职责和原 Dashboard 无 Provider 读取约定定义未来替换；
`REQ-WEB-001/005/006`、`REQ-API-002/003`、`REQ-META-001–004/009/010`、`UX-001–010`、
`REQ-SAFE-*`、`V2-UX-001–013` 及既有认证、处理流水线、任务／文件独立结果和非重放保持。
所有 TARGET 均未交付，CURRENT Dashboard 事实在接受前保留。

## Investigation and evidence limit

- 当前 `DashboardPage/View`、dashboard entity/query 和 Shell/Entry/Router 仍以旧统计页为
  默认，引用 `/dashboard`。调查看到英文统计卡、技术时间和类别码、已退役状态与旧列表链接。
  本地隔离 fake API 的统计跳转复现落到旧 Task 列表说明页；这不是本 Slice 修复验收。
- `MetadataProvider` / `TMDBProvider` 已支持搜索、详情、图片引用、超时、重试和缓存；尚无
  独立探索列表、面向浏览的分页／评分模型和作品详情 Web API，图片展示也需按实际方案接入。
  服务端 TMDB 凭据来自部署环境；现有图片路径字段不能直接成为可信 URL，现行 CSP 默认
  仅允许同源。这些事实要求接入可用链路，不构成必须新增认证图片代理的理由。
- 对照 [MoviePilot V2 探索入口](https://github.com/jxxghp/MoviePilot-Frontend/blob/19cead06f72c859732afdeccea7a37c0a770a947/src/pages/discover.vue)、
  [TMDB 筛选视图](https://github.com/jxxghp/MoviePilot-Frontend/blob/19cead06f72c859732afdeccea7a37c0a770a947/src/views/discover/TheMovieDbView.vue)
  与海报列表／详情源码；探索与推荐是不同入口。本 Slice 不引入多榜单推荐页。
- 接口依据为 TMDB 官方 [Movie Discover](https://developer.themoviedb.org/reference/discover-movie)、
  [TV Discover](https://developer.themoviedb.org/reference/discover-tv)、
  [Images](https://developer.themoviedb.org/docs/image-basics) 和
  [Attribution](https://developer.themoviedb.org/docs/faq)。引用是交互／接口依据，不是媒体样本。
  未部署或登录 MoviePilot 做验收；未调用用户凭据／真实 TMDB 验证本 Slice，不声称已实施。

## RO-1 — Default entry and direct Web replacement

新增 `/ui-v2/explore`，侧栏显示“探索”，浏览器标题和内容页头一致。`/ui-v2/` 仍通过现有
认证入口，正常连接后的默认目的地改为探索；访问其他合法深链时仍续转原目的地。
更新全部 V2 默认／返回入口、Shell 页面身份与相关认证测试，不能遗漏旧默认路径。

移除旧 Dashboard 页面、专属 entity/query/API 客户端调用与只服务该页的样式／测试／fixture
分支；共享 CountGrid、RefreshControl、其他页面沿用的 CSS 等按实际引用保留，不机械清除。
旧 `/ui-v2/dashboard` 使用普通未找到行为；不保留旧页、重定向、别名、退役说明页或兼容
参数解析，也不在未找到页面推荐旧入口。探索不得继续请求旧 dashboard 数据作为首页内容。

本 Slice 的退出范围为 V2 Web。现有独立 Dashboard 统计 API／CLI、后台统计服务及 V1
历史界面不纳入删除或修复；保留它们不构成旧 V2 页面兼容，也不借此保留旧前端入口。
原九个侧栏主页面中的首页身份由探索接替；其他页面业务及已接受切换／弹卡行为保持。

## RO-2 — Browse, filter, search and bounded paging

首期数据源为现有部署支持的 TMDB，无其他源、切换器占位或隐式 fallback。默认电影、
热度降序；电影／剧集分别查询。文案默认中文，中文缺失时保留 Provider 原名／可用简介，
真实缺项清楚显示；标明 TMDB 来源和必要署名。复用现有部署 Provider 配置和就绪条件；
缺配置时给出实际可用的恢复入口，不新建探索专用初始化流程，也不承诺无业务 Active／
无库时独立运行，不为此改造服务启动或配置绑定链路。

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
刷新或重认证后按现有机制回到探索列表，其他已支持页面的合法深链续转保持，不跳旧页。
开关详情、切条件／搜索、分页和刷新属于同一主页面，不重播整个 Shell 主页面切换动画。

## RO-4 — Read states, recovery and external-read safety

加载用等比例海报／稳定详情骨架，有效缓存可直接呈现，不人为等待。首次请求未完成、
真实无结果、图片缺失、分页结束、详情缺失、401、403、无凭据／凭据失效、超时、429、
Provider 不可用及畸形返回分别可辨。当前条件失败不能显示成旧条件的新结果或无结果。

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

明确不含：豆瓣／Bangumi／AniList 等新源、推荐榜单／个性化／轮播、订阅／收藏／想看、
资源站点搜索／下载／播放、演员或相似作品扩展旅程、完整季集浏览、“已入库／缺集”判断、
本地文件匹配或从海报直接整理、全库媒体数／FileIndex 恢复、新账户／权限模型、凭据编辑器／
Secret Store、全局代理管理、任务队列／引擎／schema 重设计、V1 改造、旧 Dashboard API／CLI
退役及独立统计问题修复、生产连接／部署验收。详情独立深链与刷新／重认证恢复详情、
无业务 Active／无库的独立启动支持也不在本次必需交付中。保留其他 Slice 的所有延期。

## Acceptance and final validation

| AC | Required evidence |
|---|---|
| AC-1 | 认证默认和所有 V2 首页／返回链接进入探索；合法其他深链续转保持；旧 dashboard 普通未找到且无重定向／别名／说明页；旧前端专属代码和请求退出，共享组件正常。 |
| AC-2 | 电影／剧集、类型题材、语言、年份、评分／人数与三类排序有真实后端参数／结果，非法组合安全拒绝；日期／评分含义准确。 |
| AC-3 | 搜索提交、类型、清空／退出与原探索上下文完整；无探索专属参数假搜索或页内全量假筛选。 |
| AC-4 | 下一页／去重／末页／分页失败／有界资源可证；快速类型／条件／关键词／作品变化不串响应，跨类型同 ID 独立。 |
| AC-5 | 桌面与 390px 海报、长标题、缺图／无评分、中文回退、骨架、键盘和 reduced-motion 可用，无溢出或首屏被无关信息占满。 |
| AC-6 | 页面内打开准确作品详情，字段／来源外链真实；卡片关闭／Escape／后退恢复条件、已加载列表、滚动和焦点；不要求独立详情入口及刷新／重认证恢复该作品。 |
| AC-7 | 首次／分页／详情／图片各自加载、空／缺失、401／403、配置／凭据错误、超时／429／5xx／畸形返回及对应安全恢复覆盖；失败不伪装为无结果，成功区域保留。 |
| AC-8 | 元数据 API 复用后端认证，参数／Provider 请求有界，图片来源可信、CSP 精确、密钥不泄露；代理／缓存／对象 URL 仅按实际采用方案验证其边界，不要求建设未采用的路径。 |
| AC-9 | 在现有合法配置／就绪条件下探索可用，缺配置有准确恢复；不新增独立启动／初始化流程，无 Storage／Task／执行／发布副作用，不影响既有配置／整理／任务语义。 |
| AC-10 | 生产构建资产通过真实 Python API＋本地假 TMDB 及图片响应的桌面／窄屏完整旅程；CURRENT／TARGET 与操作说明在接受后准确对齐，原接受身份保持。 |

Final Test Level **T3 — INTEGRATION**：按复用现有认证／配置和请求控制、只读探索 API／Web
及可信公开海报展示评估跨层集成风险；不再用预选图片代理作为整套 T4 的依据。此处不是
安全豁免：若实际方案引入新的服务端图片代理、改变权限／凭据隔离、Active、schema、核心
流水线／并发执行安全等 T4 风险，B 必须在实施前按工作流重评并提高相应 Task／Slice 等级，
不能沿用 T3 绕过必需安全验证；改变本 Contract 边界仍须 A checkpoint。

激活后 B 规划连贯 Tasks，并负责验收和 Slice 最终验证：覆盖探索 Provider／API／Web 与
直接受影响的认证／默认导航／共享弹卡回归，完成相关静态检查、生产 Web 构建，以及真实
Python API＋本地假 TMDB／图片的桌面／390px 全旅程。按 AC 验证成功、无效输入、条件／
请求竞态、失败恢复、权限／脱敏、图片来源和零媒体变更。全量 Python／Web／E2E 只在
具体共享影响或 T4 重评需要时运行；安装包／Docker 门禁只按实际交付变更和工作流适用性
安排，不新增全发布矩阵，也不为未改动的处理引擎单独增加验收工程。
Developer 只运行当前 Task 新增／修改及直接受影响测试与静态检查，B 承担所需更广回归。
使用临时根、fake／mock 和本地服务，不依赖真实 TMDB、用户凭据或用户媒体。本次规划
修订只做治理、范围／链接和 `git diff --check`，不把未来功能／集成验收记为完成。

## Final validation, Closure Packet and A Final Review

Implementation Head: NOT SET。没有产品实施、B Task 验收、Closure Packet 或 A Final Review；
AC-1–10 均待验收，当前不是 PASS。A 已完成的仅是本 PLANNED Contract 和 TARGET 文档范围
规划。下一步须先明确授权激活，再由 B 规划首个 Task；不得从本规划自动开始实现。
