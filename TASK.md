# Task 51.1 — 探索完整旅程与 V2 首页切换

Authority: committed [SLICE.md](SLICE.md), activated by A at
`3c8053b06c218e76084ec1c06cf57f03259da84c`;
[Development Workflow](docs/development-workflow.md) and
[B experience](docs/agent-experience/task-planner-reviewer.md) govern planning/review.

```text
Task ID: 51.1
Task Type: SLICE
Parent Slice: 51
Status: PLANNED
Task Base: 3c8053b06c218e76084ec1c06cf57f03259da84c
Difficulty: High
Test Level: T3
Planner / Reviewer: B — user-authorized substitution for this plan; review pending
Implementation Authorization: AUTHORIZED — TASK 51.1 ONLY; USER ACTIVATION 2026-11-07
```

用户于 2026-11-07 明确“激活 Task”，将已提交的 Task51.1 草案转为正式活动实施 Task。
目标、范围、Task ID／Base、High／T3 及测试分工保持，实施授权仅限本 Task。
当前为 PLANNED，等待 Developer 开始后转 IN PROGRESS；本次只激活，尚未修改产品代码。
同一代理代替 B 规划的既有用户授权及角色例外继续披露，不构成 B 验收或 A Final Review。

## Accepted baseline

最近独立修正 **PATCH-20261107-1：B PASS（2026-11-07）**。

- 已审完整范围：`fcfc1d2070932e0aaf354d8cc3c3b83f4b67574c..67103db5c2ae4a1ae193dc3195d02c53490dcf44`。
- 最终源码 `0232364073401aebd126c2ed7f6e68d3ec31d85a`；最终测试补充
  `96fcbbd0017c919e0753e95a019776a5102a71b8`。
- [固定 B 验收报告](https://github.com/kentinya/mediaflow/blob/db54158dbb5ee9df3b67c26f38999ba87ea6281a/TASK.md)保留全部六项交付、52 条单元 / 24 条页面 / 15 条不同真实集成用例、原生交互、
  首次共享测试数据冲突与独立运行通过结果、未运行门禁和本地证据限制。
- Slice50 保持 PASS / CLOSED，原 Base/已接受 Head、Roadmap 关闭项和 Progress 接受账本不变。

## Goal

完成 Slice51 RO-2／RO-3／RO-4 和 RO-1 的 V2 Web 首页替换：连接后进入“探索”，从真实
TMDB 电影／剧集列表筛选或按名称搜索，加载更多，打开准确作品详情，再回到原列表位置。
加载、空态、配置或读取失败有明确状态与就近恢复。对应 `V2-EXPLORE-001–010`、
Slice AC-1–9 及 AC-10 的实际浏览器旅程；不把 API／CLI 退役未完成误报为 Slice 完成。

实际缺口：现有 `MetadataProvider` 搜索依赖 ParseResult，`TMDBProvider._search` 会合并
匹配候选页，评分模型用于匹配；不能直接充当探索分页／TMDB 评分。V2 Router／Entry／
导航仍默认 Dashboard，图片 CSP 仍为同源；没有探索 application/API 或列表／详情状态。

## Implementation Scope

1. **建立只读探索端口，复用现有 TMDB。** 在 `mediaflow/domain/explore.py` 定义内部查询、
   有界页、筛选选项、作品摘要／详情及 `ExploreProvider`；application service 放在
   `mediaflow/application/explore.py`。扩展现有 TMDB adapter 的可选浏览能力，复用它的
   client／transport 和部署 registry bootstrap；不要要求所有整理用 fake/provider 实现
   新浏览方法，也不强造 ParseResult／MediaIdentity、改 MetadataPolicy 或匹配分数。
   服务解析部署支持的 tmdb 并通过探索端口调用，API／业务不见 TMDB DTO。按需初始化，
   不因 Shell／状态读取而请求 Provider；不改 Active 初始化、权限模型或整理运行绑定。

2. **确定单一同源 API 契约。** 全部为 GET，鉴权后按现有 READ 权限检查，再进入探索
   application service；不新增 CLI 探索命令。统一 query 名与内部归一化响应如下：

   | Path | Query / result |
   |---|---|
   | `/api/v1/explore/options` | `mediaType`；返回该类型合法题材和原始语言选项（代码＋可读名称），中文优先、真实原文回退 |
   | `/api/v1/explore/browse` | `mediaType, genreId?, originalLanguage?, year?, minRating?, minVotes?, sort?, page?` |
   | `/api/v1/explore/search` | 仅 `mediaType, query, page?`；不接受探索专属排序／过滤参数 |
   | `/api/v1/explore/{mediaType}/{providerId}` | 精确 tmdb＋类型＋作品 ID 的详情，不按名称二次匹配 |

   browse 默认 movie、popular、page=1；options/search 的类型显式传入。`sort` 只支持
   popular／rating／date 三种降序，分别映射官方热度、评分、电影首次上映／剧集首播日期；
   年份用电影 `primary_release_year`／剧集 `first_air_date_year`，不混入地区上映口径。
   显式 `language=zh-CN` 读取，中文缺失取可用原名／原文，缺项据实显示。
   rating 排序未指定人数时默认 `minVotes=100` 并回显／显示；用户显式修改人数后按其值。
   搜索仅按作品名和类型提交，不声称支持年份等未选定搜索条件。

   后端拒绝未知、重复参数、非法枚举／组合和非有限数字。page 为整数 1–500；年份 1–9999；
   minRating 为有限数 0–10；minVotes 为整数 0–1,000,000,000；作品 ID 为正整数且不超过
   2,147,483,647；关键词 trim 后 1–200 个 Unicode 字符，拒绝控制字符。题材须属于当前
   类型，原始语言须来自支持的目录。响应回显实际 applied query、provider、类型、page、
   totalPages、totalResults、hasMore 和 items；真实总数与当前已加载数分开，超过服务页上限
   的结果清楚说明可浏览边界，不谎称数据源已无结果。详情含名称／原名、年份／源日期、
   voteAverage／voteCount、题材、简介、电影时长或剧集首播／季集数等可用基本信息，
   图片引用与准确 TMDB 外链；不要暴露 raw DTO、凭据或本地拥有状态。

3. **控制真实外部请求和恢复。** 对接 TMDB discover/movie、discover/tv、search/movie、
   search/tv、类型详情及题材／语言目录；不做逐条详情补全或隐藏自动翻页。列表／
   搜索主读取只取一页，详情只取一个作品；冷目录校验可额外读取题材／语言各一次，
   后续复用缓存，不能随作品数量增加请求。重试仍受现有 timeout／retry／429／并发控制。探索单响应至多 20 个作品，目录至多 300 个选项；畸形／超界页安全失败，
   不把坏数据变成空态。为探索读取落实 2 MiB 元数据响应上限，覆盖无 Content-Length 的
   超限响应；只作必要的共用 transport 扩展，保留原调用默认行为和脱敏。
   复用内存 TTL 缓存：探索缓存最多 256 项，列表／搜索 5 分钟、详情／目录 1 小时；
   可给现有 MetadataCache 增加可选容量边界，旧调用语义保持，不新建全局缓存平台。
   cache key 含来源实例／适用配置、操作、类型、locale、全部实际条件和页；先鉴权再命中。
   前端探索缓存非当前上下文最多保留 16 个、闲置最多 5 分钟，加载仅由用户显式触发，
   不无界预取。参数、来源变化和身份切换不能复用不匹配缓存。

   当前 MediaFlow 身份 401／403 与上游配置／凭据、超时、429、5xx、畸形数据、真实无结果／
   详情缺失分别归一化。上游 401／403 返回 Provider 错误类别及非当前身份的 HTTP 状态，
   不触发前端退出登录；不回传原异常／上游正文。错误说明失败环节、当前保留结果、零媒体
   效果和下一动作。缺凭据复用部署环境变量／重启指导，不能让用户在页面输入密钥。
   分页只重读失败页，详情失败在卡内重读，429 有限等待／重读，无后台请求风暴。

4. **直接加载受限公开海报，不建图片代理。** 使用固定
   `https://image.tmdb.org/t/p/`，只允许网格 w342、详情海报 w500、背景 w780；Provider
   图片引用必须为合法单段文件路径，拒绝完整 URL、协议相对 URL、穿越、编码分隔符、
   query／fragment 等，非法引用作为缺图占位。`img-src` 只在 V2 静态响应增加必要的
   TMDB 图片来源限制，其他 CSP／安全头及 V1 静态规则保持。图片不带 API Bearer／Provider
   token，不用 URL、cookie、localStorage 等存凭据，不新增同源接口、blob 或图片缓存。
   使用浏览器懒加载、等比例占位和可恢复失败状态；图坏了仍可读文字／打开详情。
   源 API、图片构造依据见官方 [Movie Discover](https://developer.themoviedb.org/reference/discover-movie)、
   [TV Discover](https://developer.themoviedb.org/reference/discover-tv)、
   [Movie Search](https://developer.themoviedb.org/reference/search-movie) 与
   [Image Basics](https://developer.themoviedb.org/docs/image-basics)。署名遵循 Slice 已引用的 TMDB 要求。

5. **交付完整 React 旅程。** 新增 `web/src/entities/explore/`、`features/explore/`，复用
   central API client／typed error、TanStack Query 和共享 modal-card／认证边界。页面以中文
   标题、作品名搜索、紧凑筛选／更多筛选和 2:3 海报网格为主体，默认热门电影；切类型时
   校正不适用题材。常用题材／原始语言直接可见，年份／最低评分／人数折叠；三类排序
   含义清楚。搜索显式提交，与浏览状态分开，退出搜索恢复之前的条件、已加载列表和位置。
   切新条件从第一页开始；key 含 Provider＋类型＋条件／关键词＋页，忽略过时响应。
   加载更多追加并按 Provider＋类型＋ID 去重，失败保留成功页；不以一页数量冒充总数。
   列表常显片名／年份／有依据的 TMDB 评分，未评分不能显示假 0；长名可完整获取。
   桌面自然排列约 6–8 列，390px 两列，无水平溢出；缺图／空字段不破坏布局。

   点击海报在列表背景上开居中详情卡；同 ID 不同类型必须读各自作品。使用页面内 history
   状态或等价的最小路由机制处理浏览器后退：关闭、Escape、后退保留条件、已加载页、
   滚动和入口焦点，开关不重播 Shell 主页面动画。保持背景滚动／宽度稳定、键盘焦点和
   reduced-motion。首次／分页／详情错误各自恢复；真实空态允许清除条件。断开／401／
   身份变化清理相关读取，403 不显示前一身份数据；不扩大刷新／重认证恢复详情的承诺。

6. **切换默认首页并退出旧 V2 Web 消费者。** `/ui-v2/explore` 接替 Dashboard 的侧栏、
   标题和首页身份；修改 Router、EntryPage、destination-model、未知路由返回、迁移页返回
   等全部 V2 默认／返回入口，其他合法深链续转保持。移除旧 Dashboard 页面／entity／
   query／客户端函数／专属错误和只服务该页的样式／测试／fixtures；保留共享 CountGrid、
   RefreshControl 和有效 `.mf-dashboard-*` 样式。旧 `/ui-v2/dashboard` 走普通 not-found，
   不增加重定向、别名或退役说明页；React not-found 与 Python SPA 的 HTML fallback 分层
   验证，不把静态 HTML 200 错当旧页面仍被支持。
   改接因默认首页变化而受影响的 auth／导航测试和全部共用连接 helper，不让其他页面测试
   依赖 TMDB 凭据；Node fake 只为探索用例提供有界新契约。旧 Dashboard 专属正向 Web
   用例退出，原认证／错误／深链安全证明改接新表面或已有零 Provider 读接口，不能删证据。
   原生证明新增独立 `scripts/explore_harness.py`、
   `web/playwright.python.explore.config.ts` 和 `web/tests/e2e/explore.python.spec.ts`；
   生产 Web 资产通过真实 MediaFlowApi／临时 SQLite、合法测试配置、生产 TMDB adapter＋
   注入的本地 fake transport 驱动，公开图片由本地 fixture 响应。不能拦截探索 JSON 来替代
   Python 链路，不能访问真实 TMDB／生产配置／用户媒体。测试目录隔离，普通 Node suite
   不误收集 Python 专属用例。必要操作说明只描述真实可用入口，Slice TARGET 保持待验收。

## Acceptance Criteria

- [ ] 认证默认到探索；其他合法目标优先。旧 Dashboard Web 为普通未找到，无兼容／旧请求；其他主页面正常，Python API／CLI 启动和静态资产服务保留。
- [ ] 电影／剧集、类型题材、语言、年份、评分／人数、排序真实到达 Provider，实际 applied 条件可见；搜索模式无假过滤，退出完整恢复浏览。
- [ ] 页与结果范围真实；分页保留／去重／末页／失败重读正确；快速切类型／条件／关键词／详情和断开后返回的旧响应均不能污染当前上下文。
- [ ] 桌面／390px 可读、美观、无溢出；无评分／缺图／长标题／中文缺项诚实呈现。居中详情字段和外链属于准确作品，关闭／Escape／后退恢复原列表、滚动和焦点，键盘与 reduced-motion 可用。
- [ ] 首次、分页、详情、公开图片各自覆盖实际适用失败和恢复；当前身份 401／403、上游凭据错误不混淆，不做错误类别全组合或把失败记成空态。
- [ ] 请求／响应／缓存有界；固定图片来源和精确 V2 CSP 可证，任意图片来源不被采用；凭据不出服务端。合法 READ 先于 Provider／缓存访问，未授权不能触发探索上游读取。
- [ ] 本地假上游＋真实 Python API＋生产资产完成桌面／390px 全旅程；证明零媒体 Storage 读取／变更、零新增 Task／执行权／配置发布。允许原有鉴权审计和启动初始化，不以数据库完全无写入作断言。
- [ ] 不改变整理匹配／MetadataPolicy、其他功能和历史记录；无 Active／无库及刷新详情的非必需场景不作预期失败断言。RO-1 的 Dashboard API／CLI／专属后端退出和 AC-11 明确仍待完成，不能声明 Slice PASS。

## Required Tests

本 Task 按只读 Provider／API／Web 集成定为 **T3**：复用既有 READ 权限及部署能力，
未修改权限语义、Active 发布、schema、媒体执行或并发 authority。新增外部读取与共享请求
边界须做下列安全回归；若实施实际改变这些高风险语义，先回 B 按工作流重评等级，不能
凭 T3 标签省略必要门禁。下列新增测试路径是交付文件名，未实现前不声称已运行。

### Developer — affected tests

在仓库根运行，新增 `tests/test_explore.py`（模型／adapter／有界请求／缓存）与
`tests/test_explore_api.py`（真实路由／权限／错误／零业务效果），并运行直接受影响模块：

```sh
python3 scripts/check_governance.py
.venv/bin/python -m unittest discover -s tests -p 'test_explore*.py'
.venv/bin/python -m unittest discover -s tests -p 'test_metadata.py'
.venv/bin/python -m unittest discover -s tests -p 'test_api_security.py'
.venv/bin/python -m unittest discover -s tests -p 'test_v2_ui.py'
.venv/bin/ruff format --check mediaflow/domain/explore.py mediaflow/application/explore.py mediaflow/application/metadata.py mediaflow/infrastructure/tmdb.py mediaflow/interfaces/service_api.py tests/test_explore.py tests/test_explore_api.py tests/test_metadata.py tests/test_v2_ui.py scripts/explore_harness.py
.venv/bin/ruff check mediaflow/domain/explore.py mediaflow/application/explore.py mediaflow/application/metadata.py mediaflow/infrastructure/tmdb.py mediaflow/interfaces/service_api.py tests/test_explore.py tests/test_explore_api.py tests/test_metadata.py tests/test_v2_ui.py scripts/explore_harness.py
git diff --check
```

上述 Ruff 清单覆盖本计划明确的 Python 文件；若实现增减了必要文件，同步补齐实际清单，
补跑实际改变的 bootstrap 等模块测试；不把全仓测试转交 Developer。覆盖成功、参数
边界／非法组合、跨类型同 ID、
真实空／缺失、坏 JSON／超大无长度响应、限流／超时／临时与永久上游错误、有限重试、
缓存过期／容量／隔离、无凭据脱敏、READ 拒绝和 spy 所见零媒体／工作效果。
共用 TMDBClient／Cache 变更必须由 `test_metadata.py` 证明旧整理调用行为保持。

在 `web/` 运行（先增加相应 Explore 文件）：

```sh
npm run typecheck
npm exec eslint -- src/entities/explore src/features/explore src/features/entry src/features/migration src/routes src/shared/api/api-client.ts src/shared/api/api-errors.ts src/shared/api/explore-api.test.ts src/shared/navigation/destination-model.ts src/shared/navigation/destination-model.test.ts src/shared/ui/AppShell.tsx src/shared/ui/AppShell.test.tsx tests/e2e/explore.python.spec.ts tests/e2e/deep-link.spec.ts tests/e2e/page-transition.spec.ts playwright.config.ts playwright.python.explore.config.ts tests/fake-server.mjs
npm exec prettier -- --check src/entities/explore src/features/explore src/features/entry src/features/migration src/routes src/shared/api/api-client.ts src/shared/api/api-errors.ts src/shared/api/explore-api.test.ts src/shared/navigation/destination-model.ts src/shared/navigation/destination-model.test.ts src/shared/ui/AppShell.tsx src/shared/ui/AppShell.test.tsx src/shared/ui/styles.css tests/e2e/explore.python.spec.ts tests/e2e/deep-link.spec.ts tests/e2e/page-transition.spec.ts playwright.config.ts playwright.python.explore.config.ts tests/fake-server.mjs
npm run test -- run src/entities/explore src/features/explore src/shared/api/explore-api.test.ts src/shared/api/api-client.test.ts src/shared/api/auth-store.test.ts src/shared/auth src/shared/navigation/destination-model.test.ts src/shared/ui/AppShell.test.tsx src/shared/ui/modal-card.test.tsx src/features/entry/EntryPage.test.tsx src/routes/router.test.tsx
npm run build
npm run test:e2e -- --config=playwright.python.explore.config.ts tests/e2e/explore.python.spec.ts
```

上述 Web 静态清单覆盖已知受影响入口和新增文件；若实际还改接了其他 helper／spec，
一并补入检查并在完成报告列明实际命令，不强制重格式化无关文件。
新建 `src/shared/api/explore-api.test.ts` 可测试 central client 的探索函数，无需为文件名
强拆请求基础设施。React 测试覆盖上下文、失序响应、分页独立恢复、评分／图片缺项和身份
清理；原生用例覆盖桌面／390px、后退／Escape／焦点／滚动和真实 CSP 下的图片。
Developer 另跑自己改动的既有 E2E 用例，使用其正确 Node／Python config，不跑无关全矩阵。

### B — acceptance and regression

B 对提交的精确 Task Base..candidate 审查上述断言与实际实现，重现关键场景并记录真实结果：

- 运行上述 Python 受影响测试和 Web 静态检查／生产 build；检查新增 client 边界没有改变其他接口错误语义。
- 在 `web/` 运行 `npm run test:e2e -- tests/e2e/deep-link.spec.ts tests/e2e/page-transition.spec.ts`，及本 Task 实际改接的其他 E2E 用例（按各自 config），验证默认连接、原有深链、九个主页面身份和共用 helper 没有悬空 Dashboard 依赖。若实际共享重构产生更广影响，再按证据扩大回归。
- 运行 `npm run test:e2e -- --config=playwright.python.explore.config.ts tests/e2e/explore.python.spec.ts`；观察真实页面的成功／空态／适用失败、搜索退出、多页后详情返回、快速切换与身份清理。检查请求记录证实 adapter 参数和零媒体／任务／配置效果。
- 检视桌面／390px、长名／缺图、详情、reduced-motion 截图和必要交互；截图／运行记录保存在稳定忽略证据目录，不能仅以 DOM／CSS 数值验收可读性。
- 检查合法 READ 与无权限对照、上游 401／403 不使当前身份退出、恶意图片引用／来源拒绝、CSP 其他指令保持、凭据不在响应／日志／DOM／URL／持久存储。图片不走认证 API，不追加未采用代理的测试矩阵。

T3 不默认跑全 Python／Web／E2E 或 Docker／安装包全发布矩阵；实际共享影响或交付路径
改变时由 B 补充相应门禁，达到 T4 时适用[共享全量门禁](docs/development-workflow.md#shared-full-regression-commands)。
PASS 后重新核对全部 Slice 结果；Dashboard API／CLI 和专属后端仍在，不能交 A 关闭。

## Non-goals

本 Task 不删除 Dashboard API／CLI、domain/application/repository 聚合／runtime 注入，
也不改接 V1 Dashboard 或仍使用旧后端的打包／安全探针；它们仍是本 ACTIVE Slice 必须
完成的退出范围，此处只是实施顺序，不是兼容承诺、延期出 Slice 或新 Task 计划。
不新增其他 Provider、推荐／收藏／订阅、下载／播放、拥有判断、详情深链恢复、专用无
Active 启动／初始化、图片代理／缓存平台、新设置／权限、schema 或核心处理改造。
不为非必需能力增加反向失败断言，不删除共享样式／统计／历史来追求 dashboard 字符串归零。

## Developer Completion Report

Task 已激活，尚未开始实施；没有实施 checkpoint 或受影响测试结果。Developer 完成后
按模板提交 READY FOR B REVIEW、实际变更／命令结果和剩余风险；B 验收待执行。

## B Review Result

尚未评审；Task 已按用户明确授权激活，当前没有 PASS／FIX REQUIRED、功能验收结果或
Slice Closure Packet。规划时的角色例外不构成验收授权或已完成独立审查。
