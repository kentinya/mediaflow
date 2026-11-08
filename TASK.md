# Task PATCH-20261108-1 — 探索筛选、来源呈现与详情背景位置修正

**已激活，待 Developer 开始实施。** 用户于 2026-11-08 明确要求“激活Task吧”，
本 Task 从规划草案提升为活动实施 Task，保留原 ID、Base、范围、验收和测试分工。
本轮仅激活并 checkpoint；Developer 开工时将状态改为 IN PROGRESS。

Authority: 用户于 2026-11-08 提出的四项探索体验问题、“规划一个Task吧”及“激活Task吧”；
[Development Workflow](docs/development-workflow.md#31-independent-minor-bugs) §3.1、§5–8。
参考已接受 Slice51/52，不以它们作为父 Slice，不修改其 Base、已审 Head、关闭记录、
Roadmap 或 Progress。B 负责本 Task 规划及后续独立验收，Developer 不自审。

```text
Task ID: PATCH-20261108-1
Task Type: STANDALONE MINOR BUG
Parent Slice: NONE
Status: PLANNED
Task Base: aa752cc3bc194707808a1af79afd8978ce4aef44
Difficulty: Medium
Test Level: T3
Planner / Reviewer: B
Implementation Authorization: USER-AUTHORIZED TASK ACTIVATION — READY FOR DEVELOPER
Next Action: DEVELOPER IMPLEMENTS THIS TASK
```

## Goal

完成同一条现有旅程的四项有界修正：用户进入探索，直接按 MoviePilot 式标签行筛选或提交
作品名搜索；在列表中下部打开准确作品时背景保持原位，详情末尾只有紧凑的 TMDB 图标与
“在 TMDB 查看”外链；关闭后继续原位置浏览。探索列表底部不再出现整块署名横栏。
必要完整署名集中可达，搜索、分页、失败恢复和媒体零副作用语义保持。

适用现行要求：`V2-EXPLORE-002–010/012–015`，尤其整页布局、准确详情返回、来源与必要
署名；`V2-UX-014/015` 的同页弹卡不重播整页过渡和真实读取反馈保持。完整旅程见
[Product Experience](docs/product-experience.md#current--v2-explore-homepage-slice51-pass--closed)，
技术边界见 [Architecture](docs/architecture.md#current--v2-explore-homepage-slice51-pass--closed)。
本次只修正现有呈现与滚动行为，不新增元数据来源、过滤维度或媒体操作能力。

### Observed gaps and references

| 用户问题                                            | 当前代码及已确认原因                                                                                                                                                                                                                                      |
| --------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1. 详情底部不清晰、不好看，只留 TMDB 图标和查看入口 | `ExploreDetailCard.tsx` 将中文说明、`ExploreAttribution compact`、独立外链分开；`compact` 仍输出英文声明，外链类没有专用样式。                                                                                                                            |
| 2. 顶部排版和样式与 MoviePilot 一致                 | `ExplorePage.tsx` 使用搜索、两端分布的类型按钮、下拉筛选和扩展表单；`styles.css` 的 `justify-content: space-between` 拉大两端距离。MoviePilot 使用左侧标签、右侧标签组的多行结构和评分滑条。                                                              |
| 3. 删除列表底部整块 TMDB 横栏                       | `ExplorePage.tsx` 末尾直接挂载 `ExploreAttribution`，与详情重复展示。                                                                                                                                                                                     |
| 4. 打开详情时背景跳到顶部                           | `openDetail` 修改 `detail` 查询参数，未禁用导航默认滚动重置；当前安装的路由代码会执行 `scrollTo({top: 0, left: 0})`。隔离真实 Python 夹具和当前源码生产构建中，1440×900 从 694px 跳到 0，390px 宽也复现。现有详情背景测试从顶部打开，未覆盖非零滚动位置。 |

布局参考固定为已核对的
[MoviePilot TheMovieDbView.vue](https://github.com/jxxghp/MoviePilot-Frontend/blob/19cead06f72c859732afdeccea7a37c0a770a947/src/views/discover/TheMovieDbView.vue)，
调查时 v2/v3 对应文件相同；采用其行结构、标签选中态、密度和对齐，不引入 Vue/Vuetify。
[TMDB 官方署名说明](https://developer.themoviedb.org/docs/faq)要求在关于／鸣谢类区域展示
批准 Logo 和指定声明，并不要求在每个列表／详情重复。现有应用没有此独立展示入口。
调查复现不是修复验收，Developer/B 必须在各自候选上完成指定验证。

### Complete journey

- **目标／入口：** 从现有探索入口浏览电影／剧集；单一“探索”标题下保留紧凑的作品名
  搜索和提交按钮。常用筛选按类型、排序、题材、原始语言、评分逐行呈现。
- **可见状态／动作：** 左侧标签统一对齐，右侧紧凑标签组清楚标出当前单选值；类型不再
  孤立在最右侧。题材／语言保留“全部”，来自当前 API 选项；长选项行可在自身区域横向
  浏览，键盘可达，不撑宽整页。评分行采用滑条与最低评分人数输入；年份保留更多筛选。
  数值沿用显式“应用筛选”，草稿与真正已应用条件可分辨，清除条件恢复现有默认值。
- **搜索／成功：** 搜索态只展示当前类型与关键词及实际支持的操作；浏览筛选不伪装为
  已用于搜索。退出搜索恢复原条件、成功页、位置和焦点；普通分页继续替换当前网格。
- **详情／返回：** 点击当前可见作品原位打开详情。加载、成功、缺项、失败和重读期间，
  背景均保持打开前的可见位置，正文独立滚动。末尾显示一条紧凑外链操作：TMDB 小图标＋
  “在 TMDB 查看 ↗”，同一点击区域打开当前准确作品；去掉该处重复的中文和英文说明。
  关闭、Escape、浏览器后退／前进保持当前列表归属、背景位置与合法焦点，不先跳顶再恢复。
- **集中署名：** 侧栏底部提供轻量“关于与鸣谢”入口，打开复用共享弹层的静态小卡。
  展示 MediaFlow 名称、批准的本地 TMDB Logo、指定英文声明和 TMDB 首页链接；可用简短
  中文说明解释数据来源。该卡不读取配置／Provider，不创建新路由、账户菜单或设置表单。
  桌面／窄屏都可发现、阅读、关闭并返回原位置；不依赖元数据或筛选选项读取成功。
- **失败／恢复：** 筛选选项加载／失败有原有重读入口，可用列表保持可读；类型切换不
  沿用非法题材。无效数值保留输入并给出就近纠正，不提交非法条件。首次失败、真实空态、
  分页失败、详情失败各自保留原恢复入口；迟到响应不覆盖新条件、抢搜索焦点或移动背景。

## Implementation Scope

1. **先保留改前参照并补回归入口。** 使用隔离夹具和相同桌面／390px视口保存整页、详情
   末尾的改前截图；增加从列表中下部点击可见海报的真实浏览器回归，打开前必须断言
   `scrollY > 0`。记录点击前后背景中同一可见海报的几何位置，不能只断言关闭后的数值。
2. **重排现有探索控件。** 在 `ExplorePage.tsx` 与探索局部样式中实现上述 MoviePilot 式
   标签行、选中态和评分行，复用既有筛选、搜索、数值校验与 query key。评分支持现有合法
   小数并可清空为不限，保留未指定值与显式 0 的语义；评分排序默认人数仍是现有 100，
   不照搬参考项目的 10。不新增升序排序、多选、平台／地区／关键词过滤或硬编码语言全集。
   年份、清除条件和真实已应用摘要保持可达，避免重复显示同一个评分输入。
3. **统一详情外链与署名位置。** 修改 `ExploreDetailCard.tsx` 的末尾操作，复用
   `web/public/tmdb-logo.svg`，保持比例、准确作品 URL、新标签页安全属性及键盘焦点。
   删除探索页末尾横栏的渲染与专属废弃样式，不能仅用 CSS 隐藏。将署名内容／静态展示
   放到小型 `features/about` 模块或适合的共享模块，`AppShell.tsx` 只增加侧栏入口与弹卡
   挂载；Shell 不反向依赖 Explore 特性，不改 `AuthControls` 的断开行为。保持
   `V2-EXPLORE-010` 的可见来源与必要署名，不删除声明或远程加载 Logo。
4. **修正详情导航滚动。** 优先在探索详情导航显式使用 `resetScroll: false`，核对普通
   打开、无来源的关闭分支以及 popstate／前进后退。若仍需局部位置保存，绑定本次详情／
   列表上下文，退出或切页后清理，不能用延时回滚掩盖跳动。不得全局关闭页面导航滚动、
   修改共享历史机制或改变分页／退出搜索的合法定位。除有实测必要，不修改共享滚动锁。
5. **同步直接消费者与验证。** 更新 Explore 单元和真实 Python 浏览器测试的控件入口，
   将旧“两处必须显示声明”的断言迁为集中署名入口可见、可读、可关闭；保留图片 CSP、
   准确作品、独立失败恢复和零副作用断言。为静态署名卡、Shell入口和非顶部详情补必要
   自动化及视觉检查，删除只服务旧布局的实现，不做无关清理。

预期受影响文件为 Explore 页面／详情／署名组件、探索样式、`AppShell`、小型静态
关于模块、对应单元／E2E测试及必要的本地夹具；不改产品 Python、API、Provider、schema、
配置发布、权限或媒体执行。若实测需要超出此范围，先交 B 重评范围及 Test Level。
实现仅必要同步当前用户说明，不追改旧 Slice 关闭事实；本轮激活只写 `TASK.md`。

## Acceptance Criteria

- [ ] 四项作为同一个完整浏览旅程交付：整页布局与 MoviePilot 参考的标签行、选中态、
      对齐、密度协调，类型不再远离筛选区；截图必须包含标题、搜索、全部筛选、网格和
      分页，不以“没有溢出”或某个 CSS 数值代替整体视觉判断。
- [ ] 桌面和390px完整旅程可用，窄屏保留两列海报，长语言／题材选项、校验提示、更多
      筛选不撑宽页面或遮挡操作。鼠标、触摸、键盘可选取及清空合法条件，选中态可访问。
- [ ] 原三种排序、按作品类型匹配的题材、原始语言、年份、最低评分／人数继续作用于
      后端完整结果集；默认、空值、0、小数和非法输入语义准确。快速切类型／条件及迟到
      响应不串范围，已应用摘要来自真实返回；搜索与浏览独立，退出和分页恢复保持。
- [ ] 详情末尾只有紧凑的小 TMDB 图标和“在 TMDB 查看”外链操作，无重复中文解释、英文
      声明或默认紫色下划线呈现；电影／剧集链接准确，访问后的样式与整体一致。
- [ ] 探索页底部整块署名横栏及其占位退出；从侧栏可打开关于与鸣谢卡，完整指定声明、
      批准的本地 Logo 和首页链接可见可操作，来源不会被描述为本地已拥有。卡片开关零
      API／Provider请求，不改变原页条件／滚动，不触发主页面过渡或断开身份。
- [ ] 在浏览／搜索结果的非零滚动位置，从列表中部及底部打开不同电影／剧集，加载、
      成功／失败、重读、正文滚动、关闭／Escape／后退／前进全程不发生背景回顶或横向
      位移。逐帧／连续位置观测证明没有“先跳再恢复”，而非只比较最后状态；关闭焦点
      回到合法入口，离开探索后不被迟到回调拉回。
- [ ] 长简介、缺图、矮视口仍能读到详情末尾并操作外链；滚轮／触摸／Tab不滚动背景，
      滚动锁、滚动条占位、弹层关闭和 reduced-motion 行为保持。失败不清空成功列表或
      伪造空结果，既有身份、Provider失败和重读语义保持。
- [ ] 探索读取和集中署名不访问媒体 Storage、不创建 Task／Result／授权／配置，CSP和
      认证隔离不放宽；常规跨主页面导航、其他弹卡及搜索／分页合法定位无回归。

## Required Tests

遵循 [测试等级及分工](docs/development-workflow.md#6-test-levels)。T3 依据是现有
Router／Query／真实 API 读取、静态署名入口及共享 Shell 呈现的集成；没有 T4 边界变更。
测试使用已有 Node／真实 Python 本地夹具、临时数据库及假 Provider／图片，不接触用户
配置、运行数据库、凭据、生产媒体或真实 TMDB。新增本 Task 浏览器用例名带
`PATCH-20261108-1`，方便 Developer 只运行本轮新增回归。

### Developer — affected tests

仓库根运行：

```sh
python3 scripts/check_governance.py
git diff --check
```

`web/` 运行：

```sh
npm run test -- run src/features/explore src/features/about src/shared/ui/AppShell.test.tsx src/shared/ui/modal-card.test.tsx src/routes/router.test.tsx
npm exec -- eslint src/features/explore src/features/about src/shared/ui/AppShell.tsx src/shared/ui/AppShell.test.tsx tests/e2e/explore.python.spec.ts
npm exec -- prettier --check src/features/explore src/features/about src/shared/ui/AppShell.tsx src/shared/ui/AppShell.test.tsx src/shared/ui/styles.css tests/e2e/explore.python.spec.ts
npm run typecheck
npm run build
npm run test:e2e -- --config=playwright.python.explore.config.ts tests/e2e/explore.python.spec.ts --grep 'PATCH-20261108-1'
```

新增静态卡测试使用 `src/features/about/`；如最小实现采用共享模块，替换为其真实测试
路径并在交接记录。若另有直接受影响文件，将其加入上方定向 lint／format 命令；ESLint
只检查受支持的源码／测试文件，CSS 使用 Prettier，不给 Developer 全仓格式／全套测试任务。
覆盖选项单选／清除、合法及非法数值、搜索分离、类型／迟到响应冲突、失败恢复、署名
入口、准确外链与非顶部打开／关闭／历史返回；真实浏览器新增用例同时包含桌面、390px、
矮视口与 reduced-motion 的必要组合，不要求错误与视口全笛卡尔积。
若修改共享滚动锁／弹卡，追加该变更直接影响的其他弹卡用例，由 B 按实测确定范围。
受影响测试完成即提交 coherent checkpoint 为 READY FOR B REVIEW，不等待 B 全量验收。

### B — acceptance and full regression

独立审查整个 Task Base..候选，重现原回顶触发，再检查四项完整旅程。`web/` 运行：

```sh
npm run typecheck
npm run lint
npm run format:check
npm run test -- run
npm run build
npm run test:e2e -- --config=playwright.python.explore.config.ts tests/e2e/explore.python.spec.ts
npm run test:e2e -- tests/e2e/page-transition.spec.ts tests/e2e/deep-link.spec.ts
```

完整 Web 单元回归由 B 承担：新增 Shell 全局入口和署名组件迁移会影响所有 `renderApp`
消费者；真实 Python Explore 覆盖查询参数、CSP、默认人数和零副作用；九主页面过渡与
深链套件核对共享 Shell、同页弹卡和历史／认证续转，不能全局禁用导航行为来修复详情。
本 Task 不涉及产品 Python／打包／Storage／权限，不要求全 Python、wheel、Docker或
生产发布矩阵。根目录另跑治理及 `git diff --check`。

B 检查相同视口、相同夹具的改前／改后完整页面和详情末尾，验证与固定 MoviePilot参考
的可见对应关系；检查非顶部点击至弹卡关闭的中间帧／背景锚点，包含慢读取和历史返回，
不以最终截图或从0打开证明不跳顶。验证关于卡和缺项／失败下的完整可达性。保存实际
命令／结果／失败／跳过及截图、位置数据至工作流指定的稳定忽略证据目录；不将临时
调查产物当作最终验收。既有失败须在固定 Base 复现并保留事实，不能删断言或加重试掩盖。

## Non-goals

- 不重开／关闭 Slice51/52，不创建新 Slice，不更新 Roadmap／Progress 或规划第二个 Task。
- 不新增来源、升序等额外排序、多选、平台／地区／推荐、订阅／下载／播放、本地拥有状态。
- 不建设完整关于／账户管理页面、设置体系、独立详情深链或刷新／重认证持久会话。
- 不更改 API／Provider／缓存容量／分页契约、权限、Active、schema、Storage或任务引擎；
  不为滚动修正全局重构 Router／Shell／弹层，不改其他页面业务和主题。
- 不读取／修改私有配置和用户运行数据，不推送、发布、部署或更改 Git 历史。

## Workspace and activation checks

规划基线为 `main` / `aa752cc3bc194707808a1af79afd8978ce4aef44`，暂存区为空；规划前治理
检查 PASS。预存已跟踪修改仅 `mediaflow/.DS_Store`；未跟踪系统元数据、调查脚本、日志、
`15` 及既有 `output/` 材料全部保留，不读取或纳入本 Task checkpoint。本次只修改
`TASK.md`；Task Base 不随规划／激活提交后移。

激活起点为 `main` / `4d974355827132121cec51a140b4dcc853411cb5`，即已提交的规划草案；
激活前治理检查 PASS，暂存区为空，预存 dirty／未跟踪文件保持。本轮只激活 Task，
未开始产品实施；文档／治理检查不构成产品测试或验收 PASS。

## Developer Completion Report

未开始；Task 已激活，下一步由 Developer 按本 Task 实施。后续按模板记录候选 SHA、
实际受影响测试／风险和 READY FOR B REVIEW，不在本次激活填入实施或验证结论。

## B Review Result

NOT REVIEWED — 本次只激活；产品验收与修复验证均待实施候选提交后独立完成。
