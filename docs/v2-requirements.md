# MediaFlow V2 Stable Requirements

This document is the stable V2 requirements layer for the active Operator Web migration. It
extends the frozen V1 requirements baseline without renumbering its `REQ-*` or `UX-*` entries.
Explicit user-approved V2 product amendments identify the baseline behavior they supersede for V2;
they preserve historical V1 meaning and all safety invariants. See `V2-AUTO-009` and the amendment
in [`requirements.md`](requirements.md). Slice-specific architecture and proof details
remain in [`SLICE.md`](../SLICE.md) and the architecture document; this file records only durable
product and authority boundaries.

## Current program boundary

[Release](release.md) owns release lines; [Roadmap](roadmap.md) priorities/status; [Progress](progress.md)
accepted closures and deferrals. [SLICE.md](../SLICE.md) and [TASK.md](../TASK.md) own current work.
CURRENT journeys/contracts live in Product Experience/Architecture; reference images are never
runtime authority. Accepted43–45 foundations remain; the accepted Slice46 amendments below define
changed CURRENT behavior. The accepted Task Center filter correction is reflected in
`V2-OPS-001/003`; the accepted Rules presentation correction is reflected in `V2-RULES-001`
and current page/journey documents. Accepted Automation presentation and execution-record
outcome corrections are reflected in `V2-AUTO-001/006/007` and the current journey/architecture.
Prior Slice acceptance remains unchanged; standalone review records are reachable through
[TASK.md](../TASK.md) and Git.

Slice47 is PASS / CLOSED after independent A Final Review on 2026-11-03. The Task-only
requirements below are CURRENT, superseding the affected Job-based foundation wording. Prior
acceptance facts remain in Git and Progress; no old-task/cross-version upgrade or V1 support is added.

## CURRENT — Slice52 experience refinement (Slice52 PASS / CLOSED)

[Slice52](https://github.com/kentinya/mediaflow/blob/19a458eb6c1a6afb8693d2757755487a58213a4f/SLICE.md#closure-packet-and-a-final-review) 于 2026-11-08 经独立 A 终审
**PASS / CLOSED**，真实 Base `9aa6054e0a2f624b9fb5c0e0fa8d70b232a6cfa8` 至实现
`f5409da41191c6e4bbf238bb7def601229fc59dc`。下表为 CURRENT，旧 Slice 接受身份保持。
`V2-EXPLORE-015` 以普通分页替换 `004/006` 中追加加载／返回已加载列表的表示；
`V2-AUTO-016` 取消旧 Web 定义详情／后继草稿编辑入口的保留义务。
九个主页面的完整切换与读取接入均已交付，两种库刷新提示包含在内。
其余查询、权限、执行和历史边界保持。

| ID | Requirement | Acceptance meaning |
|---|---|---|
| V2-EXPLORE-012 | 探索主内容不显示单独的页面标题，探索区域以可访问名称标识。 | 移除公共定位文字造成的重复“探索”、可见标题及其空占位；正常侧栏同名入口保留。区域可访问名称、搜索、空态／失败／分页焦点和详情退出兜底可用，不能以隐藏空白或不可见焦点代替修正。 |
| V2-EXPLORE-013 | 探索整页协调美观，搜索与相邻控件对齐。 | 以相同视口的改前／改后完整页面及实际浏览检查层级、密度、比例、留白和字体／色彩一致性；不能只修错位或证明不溢出。搜索、筛选和网格与文件、媒体库、规则、自动化、任务中心采用一致的内容边界；搜索输入与按钮实际对齐，不显示只读文件搜索占位，通知／身份操作保留。常用／扩展筛选清楚，桌面和390px合理换行，窄屏两列海报，校验／长文案可读。 |
| V2-EXPLORE-014 | 详情首屏可读，完整内容可滚动。 | 适配桌面、390px及矮视口；长名称／简介、有无图片、电影／剧集和加载／失败均可用。作品横幅只作卡片装饰背景，不占正文行；名称、关闭、评分／类型及简介开头在未滚动时可见，其余基本信息与外链可经卡内滚动抵达。滚轮／触摸／键盘能读到末尾，背景不滚；明暗／高反差图片、缺图／迟到不得降低文字可读性或移动正文起点。关闭／Escape／后退恢复条件、浏览位置、滚动、焦点及滚动条占位。 |
| V2-EXPLORE-015 | 浏览更多结果时页面长度保持可控。 | 文档长度／同时渲染条目不随访问量持续累积，后续结果和先前位置仍可访问，不靠截断结果解决超长页面。推荐复用现有单次至多20项API采用普通分页；界面页长／页码形式由B按用户结果确定，不是新增硬指标，不增加页长设置。条件变化回新结果集起点，退出搜索／详情恢复位置；迟到响应不串上下文，失败保留成功范围并仅重读失败请求，实际位置／目标范围／末页／服务上限真实，缓存有界且鉴权隔离。 |
| V2-UX-014 | 全部九个主页面切换舒缓，没有突兀闪烁和非预期抖动。 | 覆盖切页过渡、实际读取及内容接入的完整过程，不能只改Shell或只验两种库。时长／透明度／缓动为调校参数，不指定毫秒数；消除明显闪白、干扰阅读的明暗突变、布局突兀推挤／非预期来回位移、错属旧页残留及重复淡入造成的突兀变化。正常目标页布局／高度差异、稳定占位及平顺替换允许，不能仅凭发生过几何变化或出现过占位判失败。快切、前后退及认证续转归属正确；同页不重播，交互／读取不等动画；不得为动画人为延迟或串行本可并行的请求，正常数据依赖、鉴权顺序及有限限流退避保持，reduced-motion静态可用。 |
| V2-UX-015 | 全部主页面读取反馈与内容接入平顺。 | 按各页实际读取状态处理；快速响应／缓存避免加载提示或骨架突兀闪出又消失，确有等待时稳定反馈并平顺接入，必要请求／失败恢复保持。不以出现过加载反馈本身判失败。两种库切页进入不再短暂闪出“正在刷新当前目录”；后台重读、手动刷新及操作后更新不因瞬时插入／移除刷新行而突兀闪灭或挤动列表，仅移到固定位置后仍突兀闪现不算修复。真实空／失败／权限／无Active可辨，不串库／路径／页面；只作必要呈现修正，不重设计其他业务或强制统一骨架。 |
| V2-AUTO-016 | 旧“打开”Web功能及其专属链路退出。 | 删除列表“打开”，名称为普通文本；旧 definition／editor 页面、路由、导航身份、入口和专属客户端依赖退出，旧地址普通未找到，无别名／重定向。历史页面返回合法列表／记录。保留现有新建／编辑卡及深链、保存／启停、复制／运行一次、执行记录／Task、未知请求核对和共享管理API／CLI，不删除历史或扩展后端退役范围。 |

完整现行旅程见 [Product Experience CURRENT](product-experience.md#current--slice52-experience-refinement-slice52-pass--closed)，
技术边界见 [Architecture CURRENT](architecture.md#current--slice52-experience-refinement-slice52-pass--closed)。
首个 Task 由用户授权 A 代 B 规划，例外仅限规划；后续实施分别获授权，B 独立验收与
A 独立终审已完成。实际结果、非阻塞失败、复用和证据限制见 Contract／B Closure Packet。

## CURRENT — V2 Explore homepage (Slice51 PASS / CLOSED)

[Slice51](https://github.com/kentinya/mediaflow/blob/c0a02875e53f249f1ac7d22b9b667c6a453c87b9/SLICE.md) 于 2026-11-07 经独立 A Final Review **PASS / CLOSED**，原 Base
`214b69b1e64b24fc22068c2e1760cd1b0c6ac787` 至已审实现 `30c99f1bdcd9be2cb51ac82f78bc4b07eaea3113`；
更新后的 B Closure Packet 为 `e26b399c682e7c09f4e675b6ebe412f5adcf770a:TASK.md`。下列 `V2-EXPLORE-001–011` 全部为 CURRENT。
探索替换 V2 的 `REQ-WEB-002` 首页职责，明确探索请求可读取外部元数据／图片；其他页面的
无 Provider 副作用及全部媒体执行安全保持。用户明确授权 Dashboard Web／API／CLI 和专属
实现完整退出、无兼容，仅取消 `V2-TASK-005/014` 等在该垂直的 Dashboard 消费者义务。
共享统计／状态入口、耐久历史、冻结 V1 含义和旧 Slice 接受身份不变。

现行筛选呈现、来源入口及详情位置包含 2026-11-08 独立修正
[PATCH-20261108-1 的 B 验收](https://github.com/kentinya/mediaflow/blob/6220e369b4f8b7830a8a67ae9c8a6a3fd6e81134/TASK.md)；
页面标题删除、内容边界对齐及详情首屏阅读由同日
[PATCH-20261108-2 的 B 验收](https://github.com/kentinya/mediaflow/blob/2ed492b10a87e2d4a7de7279bb35fa740ba85d43/TASK.md)
确认，反映于 `V2-EXPLORE-012–014`。两次修正沿用既有 ID、查询及权限边界；
原 Slice51/52 Base、已审实现和关闭身份保持。

| ID | Requirement | Acceptance meaning |
|---|---|---|
| V2-EXPLORE-001 | 探索成为 V2 默认首页，旧 Dashboard Web 直接退出。 | 侧栏“探索”、默认认证续转和页头一致使用 `/ui-v2/explore`，其他合法深链保持。旧 `/dashboard` 普通未找到，无旧页、重定向、别名、退役说明或兼容解析。移除旧页专属前端依赖／请求，保留仍被其他页使用的共享组件；API／CLI 和专属后端全退出见 V2-EXPLORE-011。 |
| V2-EXPLORE-002 | 提供 TMDB 电影／剧集的真实有界探索。 | 默认热门电影，两类型身份／查询分离；中文展示并诚实回退，标明来源。复用现有部署 Provider 配置／就绪条件，不专门建设或验收无业务 Active／无库独立启动；自然可用不刻意禁用，配置不可用时明确原因和恢复。 |
| V2-EXPLORE-003 | 有准确的筛选和排序语义。 | 类型、排序、题材、原始语言采用左标签／右选项的单选标签行，评分行提供最低评分滑条与最低评分人数；年份保留在更多筛选。数值草稿与已应用条件可分辨，显式应用，评分可清除为不限且保留 0／小数语义。题材与作品类型匹配，语言不冒充产地。热度、评分、上映／首播日期排序真实作用于后端查询，评分排序默认最低人数 100 可见且可修改；非法参数安全拒绝。 |
| V2-EXPLORE-004 | 搜索、分页及结果归属完整。 | 显式提交名称进入独立搜索态，展示真实支持条件；不携带不受支持的探索过滤／排序或用单页假装全量筛选。退出恢复原探索。按 V2-EXPLORE-015 用普通分页替换当前页，范围有界、去重／末页明确，失败保留成功页；条件变化重置页，旧响应不能污染新类型／查询。 |
| V2-EXPLORE-005 | 海报网格可读、美观并可访问。 | 统一 2:3 海报，片名／年份始终可读，TMDB 评分与识别置信度分离，无评分不伪造 0。缺图占位，中文缺失诚实回退，长标题可完整获取；桌面自适应、390px 两列、键盘／reduced-motion 可用，首屏直接呈现内容。 |
| V2-EXPLORE-006 | 作品详情与返回形成完整旅程。 | 同一 Provider＋作品类型＋ID 在当前页面打开协调稳定的居中详情卡，含可用图片、名称／原名、年份、评分／人数、类型、简介和基本信息；末尾为紧凑 TMDB 图标＋“在 TMDB 查看”的准确作品外链。非顶部打开、加载／失败／重读及关闭／Escape／后退／前进期间背景保持原位，返回保留条件、当前成功页和合法焦点；不要求独立详情链接或刷新／重认证恢复该作品，其他既有页面的合法深链续转保持。 |
| V2-EXPLORE-007 | 各读取环节的适用失败可独立恢复。 | 仅覆盖所选读取链路实际可能的失败，不做环节与错误全组合。元数据 API 区分当前身份 401／403、Provider 配置／凭据失效、超时／429／5xx／畸形返回和真实空／缺失；上游凭据错误不清除有效 MediaFlow 身份。公开海报覆盖缺图／网络／CSP 加载失败，认证图片接口仅在采用时验证鉴权。重读失败范围、保留成功区域，无假空态或无限重试。 |
| V2-EXPLORE-008 | 外部元数据读取保持 Provider 分层和有界资源。 | 业务使用 Provider 抽象及内部浏览模型，复用部署凭据、HTTP 请求控制和缓存；不依赖 TMDB DTO，不把搜索词交 Parser，不改变整理策略／匹配分数。仅明确探索请求可调用 Provider；缓存／并发／分页／时间均有界，不新增账户、隐式 fallback 或持久媒体索引。 |
| V2-EXPLORE-009 | 图片来源可信、安全显示且缺图可恢复。 | 不锁定同源图片接口、代理或缓存，按实际依赖选最小实现；可受限加载 Provider 公开海报。精确限制可信来源和 CSP，密钥不进入浏览器／URL／cookie／持久存储。若新增服务端代理则验证来源、路径、重定向、私网拒绝、类型／大小／时间和现有权限；若使用缓存／对象 URL 则验证其边界与释放，不为未采用技术增加建设或验收要求。 |
| V2-EXPLORE-010 | 探索与媒体执行、拥有状态保持独立。 | 列表／搜索／详情／图片不读写媒体 Storage、不建 Task、不发布配置或授予执行权；不声称已入库／已订阅，不触发扫描／识别／整理／下载／播放／通知。其他任务、文件、自动化、设置及非重放语义保持。必要 TMDB 署名集中于侧栏“关于与鸣谢”静态卡，本地批准 Logo、完整声明及首页链接可达；不在探索底部或详情重复整块声明，卡片开关无 API／Provider 请求并保留原页位置与焦点。 |
| V2-EXPLORE-011 | Dashboard API／CLI 和专属实现完全退出，无兼容。 | 删除 `/api/v1/dashboard`、`mediaflow dashboard` 的注册／分派／参数／help／渲染、专属模型／服务／repository 聚合及 runtime 注入。正常配置和合法身份下以通用未知路由 404、CLI help 注销／解析层未知命令和代码引用清理共同证明退出，不以非 200／非零退出或全仓字符串消失代替。无别名、410／说明页、空成功、替代接口或兼容；旧请求不额外触发 Provider／媒体／任务／配置业务，公共解析／鉴权／审计／日志／初始化允许。清理全部旧消费者，包括 V1 窄耦合和探针；共享统计／组件与持久历史保留，不清库或新增迁移。 |

完整旅程见 [Product Experience CURRENT](product-experience.md#current--v2-explore-homepage-slice51-pass--closed)，
技术契约见 [Architecture CURRENT](architecture.md#current--v2-explore-homepage-slice51-pass--closed)。
新源、推荐榜单、订阅／收藏、资源站搜索／下载／播放、演员／相似作品、完整季集浏览及
本地拥有状态都不在首期。Dashboard API／CLI 及专属后端退出已经用户明确授权，不再保留；
V1 只清理 Dashboard 消费者，不新增 V1 探索或其他 V1 修复／重设计。
详情独立深链／刷新重连恢复及无 Active 独立启动不作本次交付要求。图片实现由 B 按实际
依赖选择；T3 集成验证与实际出现 T4 风险时的重评遵循 Contract 和工作流，安全不变量保持。
非必需能力不作反向失败断言：自然支持详情刷新恢复或无 Active 运行时不专门禁用，
也不新增其建设／支持承诺。T4 根据实际安全影响判定，不以图片代理模块的有无单独判级。

## CURRENT — V2 dialog, readability and navigation experience (Slice50 PASS / CLOSED)

用户原八项 `V2-UX-005–012` 与后续自动化新建/编辑稳定性补充 `V2-UX-013` 均已交付。
[Slice50](https://github.com/kentinya/mediaflow/blob/214b69b1e64b24fc22068c2e1760cd1b0c6ac787/SLICE.md) 于 2026-11-07 通过独立 A Final Review **PASS / CLOSED**：原 Base
`6cd881f0311c9e53bfc6b0ab754bfbe9acefbfd0`，已审实现 `6b0927328a7bf0873faffce9cb38007fd4607764`；
B 最终包 `60798c3e50fdc62a6d46b6ee439e2406751ecfd3:TASK.md`。下表全部为 CURRENT；现有自动化卡片是共同视觉/
交互基准，各领域保留自己的模型与命令。旧参考图和旧 Slice 原始验收保持历史事实。

| ID | Requirement | Acceptance meaning |
|---|---|---|
| V2-UX-005 | 用户第 1 项：任务中心点击任务名称，以弹出卡片打开任务详情。 | 原列表作为背景且不挤窄；遮罩、卡片层级和进出效果与自动化新建协调，详情按内容设计。既有任务深链、刷新/认证续转、返回及列表条件/页/滚动/焦点保留；打开/关闭不执行工作。 |
| V2-UX-006 | 用户第 2 项：任务详情人类可读、美观。 | 默认清楚呈现任务、流程状态、阶段/等待、进度、独立文件/附件结果和需处理项；来源/目标与现有动作易找。概览按流程状态→处理进度→文件结果分层，实际异常就近说明；可用取消在任务操作行，无可用操作时不显示空控制区。文件证据直接解释固定历史记录中的处理结果、来源/目标、识别/作品匹配、命名、分类及执行经过；技术标识/诊断可折叠，计划、日志/审计、导出和四类处理仍可达。长内容、窄屏、键盘、加载/错误可用；流程完成不冒充文件成功，不增通用技术失败恢复。 |
| V2-UX-007 | 用户第 3 项：存储查看、添加、编辑都使用与自动化新建/编辑一致的弹出卡片。 | 三个入口均在列表背景打开居中卡片；保留各 Provider 已有字段/值、引用/检查及可读失败。精确 Active、checked Save、权限、并发/未知发布核对、输入保留及关闭/返回语义不变；不把原抽屉几何或步骤当作必须照搬的布局。 |
| V2-UX-008 | 用户第 4 项：存储列表“更多”美观、操作可读。 | 菜单锚定正确行，边界/行距/图标文字和普通/危险操作层级清楚；复制、启停、只读检查、移除保留。悬浮/焦点/禁用/忙碌及窄屏/边缘不裁切或误操作；权限/确认不变，配置移除不等于物理文件删除。 |
| V2-UX-009 | 用户第 5 项：删除文件/媒体库页的页内左侧目录树。 | 两页均移除目录树及占位，文件区利用释放宽度；全局导航侧栏保留。现有文件夹、面包屑、上一级/根目录、精确路径、搜索、刷新、视图和分页完成浏览；不新增替代树，错误指引不引用已移除入口。 |
| V2-UX-010 | 用户第 6 项：改善文件/媒体库页编辑媒体库、删除媒体库的呈现。 | 两页库配置编辑/移除菜单及相应确认协调、清楚、美观，普通/危险操作可辨，覆盖编辑/删除媒体库。现有入口、权限、引用阻塞、取消/确认保留；移除配置保留物理文件，不变成条目 Delete 或强制修改引用。 |
| V2-UX-011 | 用户第 7 项：添加/编辑资源库、媒体库均为弹出卡片。 | 四个入口使用与自动化/存储协调的居中卡片，保留全部既有字段、准确回填、不可变编辑 ID、隐藏配置、checked Active Save、合法目录返回及禁用恢复。成功/无效输入/冲突/失败/未知状态真实，输入/核对保留；不创建/迁移/删除物理内容。 |
| V2-UX-012 | 用户第 8 项：各页面切换自然、美观，文件/媒体库未加载时以一致加载动画改善体验。 | 页面切换仅指现有 V2 左侧侧栏入口对应的主页面之间，覆盖全部现有侧栏主页面，按主页面身份判断；其他业务内容不重设计。同一主页面内的标签、详情子路由（含其深链）、切库/目录、开关弹卡及刷新/轮询不重播该整页动画，原有导航/返回/认证续转和合法局部动效保留，所选弹卡按各自要求协调进出。主页面切换无突兀挤压/闪白/旧页残留。两种库的库信息和目录读取按实际等待区域分阶段反馈、内容平顺接入；快速响应/有效缓存可直接显示内容，不强制占位播放或串行请求。未返回不能当空态，真实空/失败/权限/无 Active 可辨。保留同条件刷新内容，快速切库/路径不串响应，尊重 reduced-motion，不人为延时或重放命令。 |
| V2-UX-013 | 用户补充：自动化页新建与编辑弹卡打开稳定、不抖动。 | 两个入口均保留背景列表的滚动、宽度和合法上下文；叠层路由不默认回顶，滚动锁定保留实际滚动条占位并准确释放。权限/定义读取与完整表单使用协调的稳定卡片布局，不从矮空壳突然撑大重居中；不跳过真实读取、放宽提交权限或人为延时。覆盖打开中间帧、关闭/重开、页顶/已滚动、占位滚动条/无占位、慢权限/慢定义、失败/拒绝/缺失、桌面/窄屏和 reduced-motion；保留深链、认证续转、回焦、未保存/在途保护、精确保存和未知核对。仅停稳截图或标题 y 不能证明通过。 |

后续[独立可读性/导航修正](https://github.com/kentinya/mediaflow/blob/db54158dbb5ee9df3b67c26f38999ba87ea6281a/TASK.md)已由 B 验收，细化上述任务正文、文件证据及加载接入呈现；自动化页头常驻刷新已移除，
局部读取失败恢复、必要读取和操作后更新保留。稳定 ID、原 Slice 接受事实继续适用。

这组 CURRENT 要求替换原任务侧详情、Storage 右抽屉及 Files/MediaLibrary 目录树/添加编辑抽屉的
所选呈现约束；旧参考图/旧 Slice 原始验收保持历史事实。沿用 `V2-UX-001–004`、当前
五态 Task/文件结果分离、四类恢复、配置/执行权限和非重放，不新增引擎/状态/恢复或设置。
自动化新建/编辑补充仅修正共享卡片的布局稳定性，视觉基准与已有业务字段/命令保持。
完整 [CURRENT 旅程](product-experience.md#current--v2-dialog-readability-and-navigation-experience-slice50-pass--closed)
与 [CURRENT 架构](architecture.md#current--v2-dialog-readability-and-navigation-experience-slice50-pass--closed)
共同解释现行行为；更早的 CURRENT 业务/安全契约在不冲突的部分继续适用。

## Automation forms and direct Run once — CURRENT (Slice49 PASS / CLOSED)

[Slice49](https://github.com/kentinya/mediaflow/blob/6cd881f0311c9e53bfc6b0ab754bfbe9acefbfd0/SLICE.md) passed independent A Final Review on 2026-11-05, from original Base
`02fb77dd713bad4dd51c29b6cfc5556ddd6d5b4e` through implementation
`9d6b78147d90b950ed2333f9747facc77bf0391a`. Correct confined sources, direct list Run once,
shared creation/editing and optional enabled creation are CURRENT. The implementation uses one
atomic checked creation publication. `V2-AUTO-013` changes the V2 disabled-only **create** result of `V2-AUTO-002/010`
and the accepted creation-card journey; copy still starts disabled without inherited authority.
`V2-AUTO-014/015` refine the existing `V2-AUTO-001/002/004/011` experience without new execution
authority. Frozen V1 and all prior acceptance facts remain unchanged.

| ID | Requirement | Acceptance meaning |
|---|---|---|
| V2-AUTO-013 | Creation offers explicit optional enablement, and later enable/disable remains available. | The Chinese enable control defaults off; omitted create input remains disabled and invalid truthy values cannot enable. One form submission completes the selected result in normal success, using either atomic publication or safe composition of existing checked create/enable commands. Current configuration management/activation and scheduled execution permissions, exact scoped intent, audit and no unrelated Draft changes remain. After creation, the edit card supports explicit enable/disable regardless of the initial choice. Each rejected command preserves its prior Active; if composed steps create the definition but enablement fails/becomes unknown, show that real state, retain its ID and original intent, and reconcile the actual submitted step before further commands. No duplicate creation, blind unknown replay, silent downgrade or false full success. Copy stays disabled; publication itself admits no Task/Run once, and Scheduler follows the saved schedule. |
| V2-AUTO-014 | Ordinary creation and saved-definition editing share the same Chinese card and form interaction in the list context. | Share field presentation/validation, bounded directory browsing, interval units, daily/weekly time choices, advanced Cron/timezone, backend upcoming times, limits, enabled state, buttons, motion/reduced-motion, keyboard focus and narrow-screen layout. Editing preserves identity and exact saved values, including arbitrary legal Cron and fractional intervals; diagnostics are not ordinary operator chores. Remove edit Run once buttons; the editor retains enable/disable after creation. Ordinary deep links reach the same experience. Cancel/discard/save/error/unknown flows preserve input and valid list context; submitting prevents duplicates, own confirmed Save allows continued editing and peer changes require explicit reread. Existing copy/remove/read-only history and Draft-only truth retain their boundaries. |
| V2-AUTO-015 | The definition list directly admits one Run once from a single explicit click, with correct confined scope and in-context feedback. | Use the exact observed saved definition/principal/request/pin through existing Run once, not navigation to detail/edit, a picker or another initial confirmation; full backend analysis/planning/checks remain. Keep list context and per-definition busy/accepted/rejected/unknown feedback plus an exact-work readback link. Remove edit Run once; its already-submitted pending requests remain reconcilable in the list. Disabled definitions remain runnable with manual execution permission without enabling/advancing the schedule. Trusted source composition/consumption agree for whole-library/subdirectory and empty/nonempty nested roots. Unsafe scope/pin mismatch, or directory read failure preventing full enumeration/incomplete/overflow scope cannot become healthy empty or first-N execution. Individual file read/processing failures keep independent outcomes under V2-TASK-012–014. Retain stability, bounds, source ownership, authority, request deduplication, principal-scoped reconciliation after reload/reconnect, native four-type recovery and completed/uncertain non-replay. Admission is not file success. |

The accepted [standalone UI correction](https://github.com/kentinya/mediaflow/blob/8a37d1a17526347116df528dcba0467f0fdfe766/TASK.md) refines
`V2-AUTO-002/014`: Copy is adjacent to Edit in the list and completes there with the exact disabled
copy's edit entry. It uses the displayed saved source and matching publication baseline; stale views
are reread before a new explicit command. Each attempt has its own feedback; unknown outcomes retain
exact principal/source/baseline reconciliation, including legacy pending sessions and filtered-out
sources, without automatic resubmission. Create/edit share a compact accessible enable switch saved
through Create/Save; remove the separate lifecycle button group and extra list-background location
label. Reference-safe removal and existing permissions/publication semantics remain unchanged.

The [CURRENT journey](product-experience.md#current--automation-forms-and-direct-run-once-slice49-pass--closed)
and [CURRENT architecture](architecture.md#current--automation-forms-and-direct-run-once-slice49-pass--closed)
define the accepted behavior. Five-state flow, independent file outcomes and the due-plus-Run-once
rate under `V2-TASK-012–014` / `V2-AUTO-012` remain unchanged. Original acceptance facts and the
Contract's deferrals remain; this is development acceptance, not a release or deployment.

## Task flow status and Automation success rate — CURRENT (Slice48 PASS / CLOSED)

The user selected this amendment on 2026-11-03 and authorized the remaining Task48.2 on 2026-11-04.
[Slice48](https://github.com/kentinya/mediaflow/blob/02fb77dd713bad4dd51c29b6cfc5556ddd6d5b4e/SLICE.md) passed independent A Final Review on 2026-11-04, from original Base
`ba84272721961c970f1eb85d616a0d129523ab92` through implementation
`a80015e2f7d46e3ad1b8f7b14c453d1030e62104`, including the A48-01 correction.
These CURRENT requirements amend the V2 aggregate realization of
`REQ-TASK-002/003`, affected completed/recovered wording in `V2-OPS-016`, and the rate portion of
`V2-AUTO-005`. They also amend `V2-AUTO-006` so execution-record Task results/status filters use
the same Task flow state as Task Center, with file results independent. Original times, attempts,
file/effect history and all unchanged safety remain.

| ID | Requirement | Acceptance meaning |
|---|---|---|
| V2-TASK-012 | Task has five current flow states: pending, running, completed, failed and cancelled. | Flow state is independent of stage, waiting reason, queue eligibility, file/attachment/operation result and read availability. Partial-success and paused are not current Task states; Pause remains retired. Required human/machine work stays unfinished, with visible waiting. Missing/unreadable Task-state truth is unavailable, not a fabricated sixth status or a guessed valid state; missing file results remain independent. Shared Task consumers, including ordinary-file aggregates on both library kinds, use this vocabulary without replacing their per-operation results or queues. |
| V2-TASK-013 | Only failure of the Task flow itself makes the Task failed; ended file-processing technical failures count as completed. | Normal closure and ended file technical attempts yield completed regardless of failure/partial/skip/ignore/individual cancellation, unknown effects or missing formal file Results. Actual file results, effect verification and remote-stop proof are not completion gates. Keep known steps/failures and missing-result truth; do not invent success. Required human steps, genuine remaining machine work and a locally executing call remain unfinished; a stale marker from the ended failed attempt alone does not keep Task running. Incomplete scope/root discovery, broken required context/relations or fatal Task orchestration still fail the Task, never inferred merely from a file failure or absent Result. Persist Task closure under existing fences; absence of a file Result alone cannot retain an ended Task's ordinary queue slot, while live-effect protection and uncertain non-replay remain. Task-status publication failure preserves last durable truth. Explicit safe cancellation remains distinct. |
| V2-TASK-014 | All affected consumers distinguish flow completion, file outcomes and real recovery. | Task Center's eight views/counts/detail, Files local ordinary-operation status, API/CLI/log/export and existing Task-status consumers expose consistent flow state and independent processed/success/partial/failure counts. Completed means the flow ended, never all files succeeded or an uncertain effect was verified. Four-type waiting/decision/analysis/summary/explicit continuation remains in the same Task; completion alone neither clears a business problem nor proves recovery success. Legal explicit continuation may re-enter the current Task without replacing original outcomes/pins or creating generic technical/attachment retry. Latest formal file failure/partial still drives automatic history exclusion and new-manual warnings even when Task is completed. |
| V2-AUTO-012 | Automation success rate and execution-record Task results use Task flow outcomes. | The authorized cohort includes Scheduler due AND the Automation definition's Run once; Files/CLI manual organizing and ordinary file operations are excluded from numerator and denominator. Rate is completed/(completed+failed); cancelled and pending/running Tasks are excluded from numerator and denominator, and no completed/failed Tasks or unavailable evidence yields no percentage, including all-cancelled cohorts. Cancelled Tasks remain in records/admitted/all-ended counts, outside active counts; rate explanations/validation must distinguish the all-ended count from the rate denominator. Each original Task counts once through legal same-Task continuation. Remove successful-primary/all-file/attachment/effect-certainty/Result-presence predicates and frozen file-derived stage substitution. Task completed under V2-TASK-013 counts as success, including file technical failure with unknown effects or no formal Result. Records/status filters/counts/paging use the same current Task flow state as Task Center within their own authorized population; ten failed files can coexist with completed flow. Preserve original times/attempts/file effects, compact read-only records, truthful file/no-work/exclusion evidence, local-month/timezone and unavailable states. Missing file results are not missing Task truth. This amends V2-AUTO-006 result/filter meaning without new recovery controls or history rewriting. |

Fresh initialization/new work/same-version restart must preserve the new flow and independent
results. Old-task/status conversion, cross-version upgrade/rollback, data clearing and history
relabelling are not selected. The [CURRENT journey](product-experience.md#current--task-flow-status-and-automation-success-rate-slice48-pass--closed)
and [CURRENT architecture](architecture.md#current--task-flow-status-and-automation-success-rate-slice48-pass--closed)
define completion/failure boundaries; the committed Slice owns scope and proof.

## Unified Task scheduling and organizing — CURRENT (Slice47 PASS / CLOSED)

**2026-10-31 user amendment:** Organizing AND ordinary-file operations (including Copy/Move)
retire Pause and resume-from-pause across Web/API/CLI and live dedicated dispatch. This supersedes
REQ-TASK-004 / V2-OPS-007 and affected CURRENT/TARGET pause requirements. Cancellation remains
cooperative and preserves completed/uncertain effects. Four-type organizing decision/analysis/
summary/explicit continuation, human/stability waiting and fences remain. The user confirms no
currently paused organizing Tasks: do not build a pause migration, restoration or compatibility
executor. Existing history stays readable without deletion, false relabelling or automatic replay.
The retirement is accepted under Slice47 AC-19 / V2-TASK-007.

The user authorized removal of the independent Job system on 2026-10-30 and granted A scope
authority. [Slice47](https://github.com/kentinya/mediaflow/blob/ba84272721961c970f1eb85d616a0d129523ab92/SLICE.md) records implementation boundaries, persistence and final acceptance.
One organizing work is one Task, its TaskItems and corresponding Results. Automation Definitions
remain reusable configuration; occurrence records remain idempotency/history evidence, not work
queues. These requirements replace the V2 Job-object realization of `REQ-TASK-008`, Job-emitting
`REQ-SCHED-003`, Job-specific queue/readiness/settings terminology and Job/Task joining in affected
`V2-OPS-002–005/007/008/014/016/017` and `V2-AUTO-004–008/010/011`. Existing authority, UX and
data-preservation obligations remain. Old tasks/Job conversion and cross-version upgrades are excluded;
fresh initialization, new-work history and same-version reopen/restart remain required. This does not
exclude failed/partial history generated by supported work or immutable configuration readability.
V1 is unsupported; its frozen definition and prior accepted implementation facts remain historical.

| ID | Requirement | Acceptance meaning |
|---|---|---|
| V2-TASK-001 | One organizing Task owns admission, scheduling, processing and the complete work identity. | Manual, due and Run once each admit one pinned Task before business readiness. Task owns bounded queue eligibility, claim/heartbeat/staleness, cooperative controls and fenced publication. Per-source TaskItems retain their own stage/checkpoint/results; no independent Job or renamed competing queue/lifecycle remains. Human-waiting work is not repeatedly claimed or counted as new execution parallelism. |
| V2-TASK-002 | All organizing triggers use the same application engine and policy pipeline. | Inputs carry source intent, trigger, limits, immutable pin and applicable authority. Manual exact summary/selected confirmation, checked Enabled scheduled intent and explicit one-run intent retain their existing meanings. Scheduler atomically admits Task plus occurrence/due evidence without choosing policies or mutating Storage. Preserve configured filtering, attachments, bounds, real stability and Run once's existing ceiling; no independent grant or second initial Automation confirmation returns. |
| V2-TASK-003 | Recovery and continuation reuse the existing four business flows in the same organizing work. | Recognition, Metadata, Classification and Conflict keep existing decisions/checkpoints, source validation, analysis, exact summary and explicit continuation. Keep the Task identity and exact per-file source/version/pin lineage; internal TaskItem IDs may be reused or versioned with explicit durable links, preserved IDs/history, truthful counts and supported links. Only proven-safe remaining work runs through existing permitted boundaries. A dispatched mutation without durable outcome proof remains uncertain; timeout/lease expiry/restart or a missing Result never proves no effects. Preserve attempt/result identities and history inside supported same-version work. Save/analysis grants no effects; no successful/uncertain replay, consumed-authority renewal, fifth type, second recovery system or every-crash seamless-continuation promise. |
| V2-TASK-004 | Job removal preserves new-work data and execution evidence across same-version reopen/restart. | Fresh initialization → submit new work → same-version reopen/restart preserves Task/item/attempt relations, pre-start/active/waiting/terminal states, continuations, pins, requests, occurrences, authorization consumption, audit/logs and primary/attachment effects. Use exact durable links; no guessed merge, lost evidence, fabricated success or implicit replay. Initialization/reopen failures preserve existing durable state and do not present an incomplete database as ready; existing schema/claim fences remain. No old-task/Job conversion, cross-version upgrade/rollback or mixed-version writer interoperability is required. The exclusion permits no user-data clearing or retired-product restoration. |
| V2-TASK-005 | Operator and administrative capabilities consume Tasks without redundant Job surfaces. | Task Center keeps its eight organizing views/four-type union and consistent server paging/counts; Files keeps exact readback/confirmation and local ordinary work. Automation definitions and records/metrics, System Settings runtime fields, logs/export and readiness remain complete. Original execution outcomes/times stay distinct from later handling. Remove Job collections/submission/control/stale-requeue APIs/CLI/frontend; existing capabilities use safe Task equivalents. Retained links resolve read-only to proved same-version Task/history or bounded unavailable/denied evidence, never execution; no old-Job mapping layer is required. |
| V2-TASK-006 | The refactor completely removes the live Job model/schema/queue while preserving execution safety. | Fresh/same-version reopened runtime, source, installed package and container contain no redundant Job table/index/FK/domain/repository/dispatch or parallel writer. Immutable configuration remains readable without digest/pin rewriting or a Job executor. RBAC, explicit effect intent, immutable pins, source ownership/confinement, claim/lease/fences, zero-mutation analysis, C→A identity and OrganizerExecutor-only mutation remain; test real native journeys, fresh initialization and same-version restart, not only renamed models. Old-task and cross-version upgrade gates are excluded. |
| V2-TASK-007 | Retire Pause and resume-from-pause for organizing and ordinary-file operations under the user scope change. | No Web/API/CLI action or dedicated live dispatch remains; old commands are refused without effects. Keep safe cancellation, four-type organizing continuation and readable history. No dedicated paused-organizing migration/restoration system is required. |
| V2-TASK-011 | Three shared runtime settings live in System Settings; retire the unused stale-age parameter. | Use the existing System Settings page as the ordinary editor; remove Automation's settings tab/form and safely redirect its old links. Retain existing keys for shared organizing capacity 1–10000, shared Worker idle polling (including ordinary asynchronous file work), and Scheduler polling for due Automation definitions only. All organizing entrances and same-Task machine-work re-entry share atomic capacity/authority checks; ordinary copy/move/delete retain their existing admission rules. Three-field checked Save preserves unrelated Drafts/settings, explicit overrides, exact publication/adoption evidence and execution pins. Remove staleJobAgeSeconds from editable/effective/default contracts; existing immutable documents may retain it and remain readable with it ignored, without digest/pin rewriting. Field edits to the retired parameter fail with zero publication. Preserve current heartbeat, per-runner claim expiry/renewal and Provider/Storage call timeouts; add no no-progress observer, whole-Task timeout or automatic uncertain replay. Keep one engine/scheduling authority, source fences and backend-proven provenance; no new page/store/queue/parallelism. |

**2026-11-03 settings amendment:** the user selects System Settings for the remaining three
fields and deletes the stale-age parameter while retaining current judgments. `V2-TASK-011`
replaces the prior Automation-only boundary and intermediate four-field/no-progress-observer
plan, and amends `V2-AUTO-001/007/008` below. This is accepted CURRENT behavior; historical43 acceptance remains unchanged.

Each applicable scheduling bound counts a Task with pending machine work or an active
Worker stage once, including discovery/analysis/execution and machine-timed stability waiting.
Wholly human-waiting work with no queued/claimed machine work uses zero slots;
a cancellation request alone does not release a slot while work/a call remains active. Re-entry is
capacity-checked atomically. A queue-full refusal preserves an existing Task's waiting state,
choices/summary/results, consumes no authority and registers no automatic continuation; an explicit
later retry rechecks normal authority/freshness. A full due tick does not create an occurrence or
advance due state. Decision Save needs no slot; exact admitted duplicates reconcile without another
slot. One system allowance covers manual, due/Run once and same-Task machine-work re-entry;
ordinary asynchronous file work keeps its separate existing admission rules. Source ownership and uncertainty protections
survive slot release. Capacity is not Worker/thread parallelism. Job-named settings in historical
published snapshots must remain reproducible; adopt Task terminology/semantics through compatible parsing or explicit checked
successors, never by changing an old revision/digest. No unrelated ordinary-file queue, notification
delivery or supervision redesign is selected. Full outcomes/evidence are in the committed Contract.

## Source-dependent failed-history admission — CURRENT (Slice47)

Accepted user-authorized CURRENT behavior. `V2-TASK-008–010` supersede only the
affected history-refusal and standalone CLI retry realization in `V2-TASK-002/003/005/006`,
`V2-OPS-016/017`, `V2-AUTO-004`, `REQ-TASK-004`, `REQ-RECOVERY-006/008/009` and related
non-replay wording. Same-Task automatic/uncertain replay remains prohibited; this permits a new
explicitly warned manual organizing request without rewriting its predecessor's results or authority.

| ID | Requirement | Acceptance meaning |
|---|---|---|
| V2-TASK-008 | Definition-driven new organizing excludes versions whose latest formal organizing outcome is failed/partial. | Due and Run once find that latest applicable outcome from complete matching history by canonical Storage/path and comparable version, not enclosing Task outcome or a recent arbitrary page. Exclude failed/partial, including zero-effect failure; a later manual success removes this failure-based exclusion without deleting old records. Independent free sources still run. Durable reasons/counts preserve truthful no-work/skipped outcomes and complete traversal limits. Browsing, tests, analysis-only and exclusion records do not supersede formal outcomes; real replacement is new content. Other terminal states are not added to this exclusion. |
| V2-TASK-009 | New manual organizing admits failed/partial sources with a clear Web history warning and ordinary exact confirmation. | Files direct/folder/mixed selection includes partial/unknown effects without a permanent history-only veto. Show the applicable result and available effects/source/target before existing selected confirmation; no verification page or routine checkbox. Items still queued/processing without a terminal outcome retain normal mutual exclusion; an item already failed/partial is not reclassified active merely by parent Task running or an old unknown marker. User checks Storage and starts new work under current configuration and normal conflict/destructive rules. Necessary lock/claim/fence/current-state updates are allowed while recorded outcomes, Results, pins, steps, unknown evidence and original run times remain factual. No remote-completion proof/detector or attachment recovery is required. CLI/remote keep existing source/authority semantics; no new CLI warning or remote history-refusal rule is selected. |
| V2-TASK-010 | Remove the independent tasks retry-failed CLI entrance; use new organizing and existing four-type continuation. | Parser/help/dispatch/exclusive helper code and installed consumers no longer expose retry-failed or aliases. Old input fails normally before work/Provider/Storage/authority consumption. Keep scoped zero-mutation analysis, ordinary organize, shared ignore/audit, four-type decision→analysis→summary→confirmation and immutable original Results/pins/Automation records. No hidden fallback, second recovery system or automatic replay is introduced. |

Explicit user boundaries carried forward: no old-task/cross-version upgrade scope and no supported
V1 product. Fresh/new-work and same-version reopen/restart safety remain. [Slice47](https://github.com/kentinya/mediaflow/blob/ba84272721961c970f1eb85d616a0d129523ab92/SLICE.md)
RO-6/AC-20–25 own the proof boundaries; prior accepted implementation facts remain in Git.

## Slice46 authorized amendments — CURRENT

The following stable amendments select readable actions, organizing-only Task Center, earlier Files
manual admission, local ordinary-work feedback and enable-to-execute/real Run once. [Slice46](https://github.com/kentinya/mediaflow/blob/5144ab1fc2344b06194969cc2c496835729664c0/SLICE.md)
owns full scope/acceptance and retained stability behavior; Product Experience owns complete journeys.
A reviewed the full immutable Base..Implementation Head and closed Slice46 on 2026-10-29. Prior
independent-grant, all-folder-suffix and no-wait planning variants remain superseded; they are not
current behavior.

| ID | Requirement | Acceptance meaning |
|---|---|---|
| V2-UX-004 | Shared V2 actions are readable and usable throughout the light shell, especially Entry. | Primary/secondary/danger/link/icon and dialog actions preserve readable normal/hover/focus/busy/disabled states and keyboard names/focus. Enabled text meets AA contrast; directly related Entry field colors support the same readable journey. Existing auth, semantics and duplicate-submit guards remain; no new identity/theme product. |
| V2-OPS-014 | Task Center's eight views, counts, filters and selected detail concern admitted organizing work and its legitimate organizing continuations only. | Backend scopes the complete authorized population before grouping/counting/paging, preserving admission/pre-start organizing failures and one stable Task per work. Ordinary-file/notification/unrelated work and analysis-only preparation do not enter center lists/counts/recovery or legacy-list/deep-link loopholes. Remove global Worker/resident-status, discovery and manual-operation blocks and their exclusive landing reads; retain factual failure/readiness evidence and the four-type recovery selected by V2-OPS-016. |
| V2-OPS-015 | New file-selection-based manual organizing starts only from ResourceLibrary Files. | Remove center creation CTAs and independent source-selection flow. Explicit Files submission admits organizing work before business readiness under V2-OPS-017, with discovery/analysis, exact summary and separate selected execution confirmation inside the task. Exact task/preparation/unknown-request readback remains accessible after close/reload/reconnect from the Files submission and the admitted Task Center task detail. Existing prepared-work/task-recovery links retain exact context; generic creation URLs guide to Files without work. MediaLibrary is not a source; definition-bound Automation execution intent follows V2-AUTO-010/011 without a new generic file picker. |
| V2-OPS-016 | Task Center Attention and pending-task statistics cover only current Recognition, Metadata, Classification and Conflict problems; Failure Recovery is removed. | Keep All/Running/Attention/Ended and four type lists. Pending task total is the distinct union of the four types and their required human decision/analysis/confirmation steps; queued/running alone is not attention. Genuine resolution clears the exact problem; new business blockers change type, while solely technical failures leave attention. Under V2-TASK-012–014, recovered-completion display requires both durably completed Task flow and exact linked recovery proving every necessary file effect; a failed flow remains failed regardless of file success. Preserve original failed-attempt history. Other terminal failures appear only in All/Ended and factual detail/results/logs/export, with real status/reason/effects but no separate failure statistics or generic recovery guidance/actions, including old deep links. Provider/network faults are not Metadata decisions. Mixed tasks count only current four-type problems, without false success, history rewriting or completed/uncertain replay. Administrative API/CLI recovery and native Automation readiness/authorization remain outside this presentation change. |
| V2-OPS-017 | Explicit Files manual organizing admits a durable task before business-rule resolution, retaining folder media-type filtering and same-source unfinished-work/explicit-extension checks. | Single/multiple/folder/mixed selections do not require matching all rules, metadata/target/conflict readiness or an executable summary before admission. Direct files are not vetoed merely for an unlisted suffix. Folder/mixed-folder discovery retains configured primary-media extensions (default video) and existing attachment settings; default pictures/subtitles/NFO do not become independent primaries/Attention items, including when artwork is off. Unassociated files stay at source; other-same-stem settings and explicit extension customization remain, with no ad-content detector/deletion. Other automatic include/exclude/rule readiness cannot add manual vetoes. Backend verified source ownership is atomic across manual/Automation/continuation work, including queued/unresolved four-type recovery; filename or terminal history alone cannot prove a duplicate. Report duplicates/exclusions per item and preserve eligible siblings. Recognition/Metadata/Classification/Conflict problems arise inside the admitted task and complete their native recovery/counts under V2-OPS-016. Keep bounded/constrained sources, immutable pins, real stability before execution, full pipeline, exact in-task summary and explicit selected execution/destructive authority, capabilities/fences and completed/uncertain non-replay. Browsing/DryRun/analysis-only requests are not converted into manual organizing submissions and gain no execution authority. No forced default identity/target; Automation intent/Run once follows V2-AUTO-010/011 and retains its saved source filtering. |
| V2-AUTO-010 | Checked Enabled publication supplies scoped scheduled execution intent; independent unattended grants and mandatory grant pre-analysis are removed. | All supported enable/publication entry points validate execution/configuration permissions and audit the exact saved definition/source/scope/limits for enable/enabled-successor intent. Normal due execution needs no separate grant or per-run click; enabling starts no immediate run. Creation defaults disabled with explicit optional enablement under V2-AUTO-013; copy remains disabled. Disabled/removed definitions and live permission loss stop future admission and unperformed scheduled effects at safe boundaries; no rollback. Existing enabled definitions use these semantics without old grants or re-enabling; old grants/revocations cannot override Enabled. Retain pins, immutable admitted context, optimistic concurrency, plan/capability/source/effect checks, idempotency and independent outcomes. Explicit overwrite/Delete/cleanup intent remains required. Reads/analysis/unrelated publication never fabricate execute intent or replay history. |
| V2-AUTO-011 | Run once directly executes the saved Automation organizing definition once, admitting a task before business-rule readiness. | The explicit command binds current saved definition/principal/scope/pin and supplies one-run execution intent, without prior analysis/grant or a second initial summary/execute gate. Reuse the scheduled source scope/filtering, full pipeline and bounded complete enumeration; retain Run once's effective primary limit of min(definition itemLimit, 100) and existing traversal/evidence budgets. Ready items execute and four business blockers use native Task Center recovery/Attention/counts. Single-source ownership is atomic across manual/Run once/due/recovery work; unknown submissions reconcile exact identities. Disabled definitions can run once with execution permission without enabling or advancing the schedule. Empty/no-work, per-file instability failures, incomplete bounds and actual failures remain truthful; no first-N execution, forced identity/target, successful/uncertain replay or silent destructive escalation. Files manual summary/confirmation and four-type decision/analysis/explicit-continuation safety remain. One real run counts once; old analysis-only preparations are not auto-executed. |
| V2-FILES-007 | Ordinary-file progress, results and supported recovery belong to the originating ResourceLibrary/MediaLibrary file page. | Create/rename/edit/Copy/Move/Delete do not send normal progress/recovery to Task Center. 当前页面操作状态 sits immediately left of the corresponding 添加资源库 / 添加媒体库 button with the same style and opens a centered modal for bounded ordinary progress/results/existing permitted controls. Entries retain originating library/source context and never mix library kinds; empty/loading/read-error and accessible dismissal remain usable. The same entry reopens multiple relevant operations and durable per-item results after close/reload/reconnect/service restart, including supported pre-existing work; closing cancels/replays nothing. Preserve exact kind/principal/source/pin, unknown-admission reconciliation, existing safe controls and completed/uncertain non-replay; hiding work never removes Tasks/results/audit, adds retry/undo authority or requires a new global center. |

`V2-OPS-014–017` narrow the prior all-command discoverability of `V2-OPS-002`, the population of
`V2-OPS-001/003/009/012`, Task Center creation in `V2-OPS-006/010`, and the nine-view/general-failure
recovery and next-action realization of `V2-OPS-005/008/009/012`. The four selected business types
retain native recovery, exact plans and explicit authority; `V2-OPS-007/008/011–013` execution safety
and retirement boundaries remain. `V2-OPS-017` specifically supersedes Files manual task admission
only after ready-plan confirmation in `V2-OPS-006/010` and the CURRENT manual journey; task creation
now precedes business resolution, while exact planning/confirmation still precedes media mutation.
It also supersedes other automatic include/exclude/match filtering as deliberate manual entry vetoes;
configured folder media-type filtering, explicit extension exclusions, source safety/stability and
bounded traversal remain. A merely unlisted suffix remains admissible for direct-file intent, not
blanket folder enumeration. Definition-bound
Automation keeps saved source filtering; its intent/admission sequence is replaced by V2-AUTO-010/011.
For V2-OPS-017, admit outer folder work before traversal, then atomically check/reserve each
discovered source with its own item admission; full scope/bounds validation still precedes effects.
Do not restore pre-task full traversal or span Storage I/O with a database transaction. Under
V2-OPS-014/016, normal manual WaitingConfirm without four-type recovery lineage remains unfinished
in Running/All with exact summary/confirmation readback after refresh/restart, outside Attention and
pending-task counts. Necessary human confirmation within four-type recovery retains its lineage.
For other Task Center failures, this explicit user amendment replaces generic repair guidance with
factual read-only history, without removing durable evidence or administrative recovery capabilities.
`V2-FILES-007` changes ordinary recovery ownership without weakening
`V2-FILES-002/003`, `REQ-TASK-009/010`, RBAC, immutable pins, fences or durable results.

`V2-AUTO-010/011` supersede the separate grant/pre-analysis requirements and analysis-then-confirm
Run once in `V2-AUTO-002–004`, `V2-OPS-010/013`, and the V2 realization of `UX-006`,
`REQ-SCHED-006/007` and `REQ-SAFE-008`. Scoped explicit intent is now checked enable/enabled-successor
publication or the Run once command; independent revocation becomes scheduled disable/removal.
Exact backend plans and execution checks still precede mutation; four-type recovery retains explicit
safe continuation, and Files manual summary/confirmation remains. `V2-AUTO-005/006` counts/read-only
records apply to real executions with the four-type-only attention amendment. This does not authorize
a second execution engine, broad file authority, destructive defaults or historical work replay.

## Stable V2 requirements

| ID | Requirement | Acceptance meaning |
|---|---|---|
| V2-UX-001 | User experience is the primary product-design and acceptance criterion for V2 Operator Web journeys. | Normal operator journeys are Web-completable with task-oriented actions: no CLI fallback for an ordinary Web journey, no raw internal-token copy/paste as the final UX, no unnecessary implementation identifiers, and no repeated interaction without new human intent. |
| V2-UX-002 | Safety, authority and data-integrity controls must be delivered with the lowest practical operator friction. | Scope validation, capability checks, limits, authorization binding, short-lived/scoped execution authority where required and backend permission enforcement are automatically composed by the product wherever technically safe. Extra interaction occurs only at meaningful authority, ambiguity, uncertain-effect or irreversible/destructive boundaries. |
| V2-UX-003 | Implementation mechanisms must not define the operator journey. | Bearer tokens, execution tokens, revision IDs, locks, claims, checkpoints, grants or fencing mechanisms do not by themselves justify mandatory user exposure. They remain backend-authoritative and may be surfaced when useful for diagnosis/support, without weakening `V2-AUTH-*`, `V2-SAFE-*` or other authority requirements. |
| V2-WEB-001 | V2 Operator Web is a first-class product surface for the operator journeys selected by the active V2 program. | Required operator outcomes are delivered through a discoverable Web surface, not only through internal APIs or CLI commands. |
| V2-SETUP-001 | Native V2 Settings owns explicit first-Draft creation/resume and activation, reachable after authentication and from setup-required business pages. | Entry, refresh and reconnect restore existing state without creating another Draft; concurrent creation cannot duplicate setup roots. Viewer receives administrator guidance. Return refetches actual authority; broken prior Active is recovery, not first setup. |
| V2-SETUP-002 | First activation accepts a valid empty business baseline without mandatory media-business forms or generated policies. | An admin explicitly activates through normal validation and atomic runtime binding. Show `配置已激活，媒体业务尚未配置` and capability readiness; activation starts no media work or notification. Thereafter business pages retain exact Active-successor publication, applicable tests and their explicit authority boundaries. |
| V2-CONFIG-001 | Empty business families are valid configuration while populated objects retain structural and declared-dependency validation. | No Storage, libraries, Recognition types/rules/bindings, Metadata/Naming/Classification/Organize policies, Automation or Webhooks is required merely to activate. Malformed/dangling populated objects still fail; no development/default business objects fill gaps. Storage/strategy/destination evidence applies only to actual configured capabilities and enabled applicable bindings. |
| V2-CONFIG-002 | Settings shows labelled Active/Draft JSON and exports complete portable supported managed configuration without secret values or deployment authority. | Default to the exact runtime-consumed Active; no Active shows Draft/no-Draft, while corrupt Active remains explicit. Retain safe environment references, redact unsafe URL credentials, exclude database/principal/token startup authority, and bind validated imports to the receiving deployment. |
| V2-CONFIG-003 | Advanced Settings edits only backend-supported configuration absent from other management pages through the normal managed lifecycle. | Backend allowlists/schema reject arbitrary JSON fields, unknown/unconsumed settings and deployment database/identity changes. RBAC, audit, exact successor, validation and activation apply; deployment/restart-only values cannot be mislabelled as currently consumed. |
| V2-CONFIG-004 | Business readiness is command/scope-specific and separate from configuration validity or Active existence. | Incremental objects can publish while unrelated families remain empty. Missing/disabled/unavailable/unauthorized prerequisites have bounded reasons and recovery; missing media policies do not disable valid direct file operations. Admission/execution revalidate and preserve prior Active/input on failed publication. |
| V2-RULES-001 | V2 provides one discoverable organizing-rules workspace for the complete RecognitionType policy graph. | An administrator can manage Overview, type bindings, Recognition Types, Recognition Rules, Metadata Policies, Naming Policies, Classification Policies and Organize Policies through a native V2 journey. Each family opens as a complete full-width inventory with no editor/drawer selected; only an explicit `添加xx` action opens its create drawer, while existing Edit is an explicit full-page state. The workspace owns its content title/description and refresh, without a duplicate topbar search or normal sequence/Settings utility row. Overview has no inventory search; each family retains one local search/state filter, and successful refresh preserves current family, filters and unsaved input. Keep the eight category cards, seven inventory layouts, real overview counts, conditional gap/dependency guidance and explicit complete-flow check. Settings diagnostics and unavailable-configuration recovery remain available; exact Active, permissions and publication semantics are unchanged. Supplied references govern structure/style only; their example data is never runtime or acceptance authority. |
| V2-RULES-002 | Rule-workspace `保存` is one page-level command that automatically validates and activates the exact successor candidate. | Read/navigation creates no Draft. Explicit Save composes the focused candidate from the exact Active snapshot, runs whole-document validation and applicable checks, then atomically publishes Active. There is no ordinary separate Save-Draft/Validate/Activate step; stale/failed/unknown Save preserves or verifies durable state without automatic resubmission. |
| V2-RULES-003 | RecognitionType and RecognitionRule editing exposes the production condition and resolution semantics. | Typed nested AND/OR/NOT conditions, compatible field/operator/value controls, priority, score, stop-on-match, ambiguity and bounded evidence match the backend engine. Unsafe regex and invalid values fail; list order does not invent a first-match algorithm. |
| V2-RULES-004 | RecognitionTypePolicy binds one enabled RecognitionType to Metadata, Naming, Classification and Organize policies without changing recognition identity. | Duplicate enabled bindings and missing/disabled references fail. Downstream policy reuse remains legal and explainable; RecognitionType C remains C when it uses another type's naming, classification or organize policies. |
| V2-RULES-005 | Metadata, Naming, Classification and Organize policies have purpose-built typed Web editors over the shared managed configuration authority. | Forms expose current domain fields and compatibility without inventing Provider switching, fallback or execution authority. MetadataPolicy uses only query type (Movie/TV/Auto/None); legacy policy mediaType is ignored and omitted on Save. Candidate/result movie/TV types remain identity data; Auto permits both. Movie/TV templates remain distinct; classification selects MediaLibrary plus safe relative path; high-risk organize effects are explicit. |
| V2-RULES-006 | Rule and policy tests/previews are exact-revision, bounded, explainable and zero Storage mutation. | Recognition Strategy Test, Metadata test, Naming Preview, Classification Preview and Organize authority/whole-chain explanation identify the tested non-Active candidate, become stale after relevant edits, expose secret-free evidence and create no executable work or execution authority. Provider access occurs only through an explicit applicable test. |
| V2-RULES-007 | Object lifecycle, references and automatic Save/activation remain backend authoritative and consistent across Web/API/runtime consumers. | Create/copy/edit/enable-disable/reference-safe delete and page-level Save use audit, RBAC, optimistic concurrency, validation/applicable evidence and atomic activation shared services. Files Organize, Automation, API and CLI consume the same published semantics; the frontend never resolves or caches policy as authority. |
| V2-RULES-008 | Empty, partial, invalid and failed rule graphs provide actionable recovery. | Empty Active offers dependency guidance without generated defaults. Disabled/missing references, invalid conditions/templates/paths, Provider/secret failures, stale Save candidates, denied permission, malformed responses and automatic-activation failures state what is durable, whether Active changed and the explicit safe next action. |
| V2-RULES-009 | Each Rules editor's default offline test analyzes its current object and necessary inputs; complete-flow checks have a separate explicit entry. | RecognitionType definition is independent of rule conditions and downstream bindings; absent associated rules is inapplicable. A RecognitionRule test evaluates actual conditions and output type without resolving downstream policies, explains match/non-match with bounded condition evidence and never forces recognition. Binding/Metadata/Naming/Classification/Organize checks use only relevant dependencies. Local results, downstream readiness and full-flow outcomes remain distinct; synthetic identities are labelled and offline local tests call no Provider or Storage. Candidate/sample/context evidence stays exact and stale-aware; local passes cannot replace whole-graph publication, complete planning or execution authority. Existing complete Test Policy/DryRun remains available through native Web and shared backend behavior. Delivered within the accepted Slice 44 boundary. |
| V2-RUNTIME-001 | MediaFlow Worker starts and registers without Active and consumes later eligible work without restart. | Keep FileTransfer consumption resident; no valid authorized published context means no processing/mutation. Preserve supported command readiness, exact admitted pins, claims/leases/fences and per-item uncertainty recovery. Current Active governs new admission and does not replace older valid pins. |
| V2-RUNTIME-002 | Scheduler and Notification Worker remain resident through absent/empty/unavailable configuration and adopt current valid configuration without restart. | No eligible schedule means no Task admission; unavailable Active never uses cached schedules. No usable Webhook means no send or targetless claim; preserve target identity and delivery recovery without silent retargeting. Configuration read failures explain waiting while preserving process and durable state. |
| V2-STO-001 | Every provider-valid Storage root round-trips through typed Save, inventory, detail and Edit. | OpenList's empty root and `/` both represent its service root; render a clear provider-root label without dropping the row or rejecting the whole inventory. Existing saved empty-root entries remain readable. Other provider and Local confinement rules stay intact; failed list rendering never implies Save rollback or triggers automatic resubmission. |
| V2-AUTH-001 | During the current V2 program, the existing API-principal Bearer-token model and RBAC remain the identity/authentication and role/permission authorization boundary. | A scoped execution grant, execution unlock, step-up authorization or equivalent mutation-admission authority may be layered on top when required by an approved V2 journey, but it does not replace principal identity, authentication or RBAC. V2 does not silently introduce a new username/password identity system, OIDC integration, session or cookie authority. |
| V2-AUTH-002 | The API principal token remains memory-only in the browser during the current identity architecture. | The token is not persisted in `localStorage`, `sessionStorage`, IndexedDB, URLs/query strings or frontend-managed authentication cookies. |
| V2-AUTH-003 | Python remains the authoritative backend for domain behavior, execution authority and storage mutation. | Frontend code does not duplicate or move domain decisions, execution permission or Storage mutation out of the Python application; `OrganizerExecutor` remains the sole Storage mutator. |
| V2-MIG-001 | Existing `/api/v1/*` and shared application behavior remain authoritative during migration. | V2 UI and V1 UI use the same API semantics, validation, permissions, state transitions and safety gates. |
| V2-MIG-002 | V1 `/ui` and the V2 migration surface may coexist until parity and cutover acceptance. | The V1 UI remains available during migration, and a separate V2 entry is used until the approved cutover. |
| V2-SAFE-001 | Read-only V2 UI actions remain zero-side-effect. | A read, refresh or status view does not create Tasks, invoke a Provider or mutate Storage unless a later explicitly approved journey says otherwise. |
| V2-SHELL-001 | V2 uses one shared reference-aligned operator shell across all V2 routes. | The light left rail/top bar in `docs/pics/文件页.png` replaces the earlier dark horizontal shell; Files does not create a parallel navigation model, existing route/auth/deep-link semantics remain shared, and non-Files business journeys remain functional inside the new chrome. |
| V2-FILES-001 | Files is a live-Storage ResourceLibrary browser and a complete common file-management surface. | An authorized operator can Create Folder/Text File, Rename, Copy, Move, Delete, Edit an allowlisted bounded text file, Upload and Download eligible files/directories, with bounded multi-selection where meaningful, without entering the media-organize policy pipeline. |
| V2-FILES-002 | Direct file management is low friction but backend authoritative. | A direct command needs no Organize Preview, recognition/metadata/naming/classification stages or raw execution token; it still enforces RBAC, explicit destructive/overwrite intent, Active ResourceLibrary confinement, Storage capability, stale/conflict checks, audit and `OrganizerExecutor`-only mutation. |
| V2-FILES-003 | Direct file operations preserve truthful state and bounded recovery. | Known success refreshes from live Storage; invalid path/name/content, unsupported capability, conflict, stale source, root/unbounded directory scope, transfer/verification failure, denied permission or uncertain effect remains item-specific and is never silently overwritten/deleted or automatically replayed. Copy/Move source media byte totals are informational rather than admission limits; boundedness is enforced through selection, entry/depth/path and bounded control-plane evidence. |
| V2-FILES-004 | ResourceLibrary configuration can be edited from its selected Files card without exposing managed-lifecycle mechanics. | ID stays immutable; name, enabled state, Storage and source root are prefilled and saved through exact-Active optimistic concurrency, field-preserving merge, complete validation and checked atomic activation. Storage contents are never migrated by the edit, and failures retain the prior Active and correctable input. |
| V2-DEPLOY-001 | Production remains operable without a Node runtime server. | Node may build the frontend, while the existing Python/MediaFlow application serves the built static assets and API. |
| V2-DEPLOY-002 | Fresh Compose requires only management bootstrap, durable data and deployment-owned administrator credentials, with distinct process, infrastructure and work readiness. | No mandatory media mount; configured Local Storage still requires explicit mounts/permissions. Waiting for first configuration is normal resident state, not false Scheduler/notification readiness. DB/schema/heartbeat and Active/pin/secret failures are distinct, fail closed and retain safe recovery; health checks have no media/provider/delivery side effects. |
| V2-MIG-003 | Final V1 UI retirement requires explicit parity and cutover acceptance. | `/ui` is not removed merely because a V2 route or partial migration exists; parity, accessibility and migration evidence are required first. |

## MediaLibrary requirements — delivered baseline and editing

| ID | Requirement | Acceptance meaning |
|---|---|---|
| V2-MEDIALIB-001 | MediaLibrary file management browses the real contents of an Active destination library through its configured Storage and root. | Physical membership is live Storage truth, independent of FileIndex, metadata or prior organization. Exact relative paths, bounded navigation/search/paging and truthful refresh/recovery are required; page entry starts no processing. |
| V2-MEDIALIB-002 | MediaLibrary offers bounded common file maintenance without the media Organize journey. | Create Folder/Text, single Rename, Copy, Move, Delete and allowlisted text Edit share backend RBAC, kind-specific library confinement, capability/stale/conflict checks, explicit destructive intent, OrganizerExecutor mutation and durable per-item recovery. Equal IDs or reused evidence cannot exchange MediaLibrary and ResourceLibrary authority. |
| V2-MEDIALIB-003 | Adding/editing/removing MediaLibrary configuration is a complete Web/API journey using actual managed runtime authority. | Page-local create/edit Save validates and atomically activates a successor; edit keeps ID immutable, preserves unexposed fields and rejects stale writers. Failures preserve Active and correctable input. Disabled libraries have a Web re-enable path; Storage/root edits and reference-protected removal never move or delete physical files. |
| V2-MEDIALIB-004 | Files and MediaLibrary have distinct navigation identities while sharing suitable presentation and file-operation mechanisms. | Route changes preserve Files capabilities, Organize return context, authentication and other journeys. MediaLibrary follows its reference with type icons and without card statistics/placeholders, thumbnails or Organize actions; row sizes and bounded selection/operation summaries remain available. |

## Operations and Tasks requirements — delivered baseline (Slice 42 PASS / CLOSED)

These requirements extend the existing Operations foundation and are delivered within Slice 42's
accepted boundary. CURRENT behavior and explicit deferrals are documented in Architecture and
Product Experience. Task-linked recovery is delivered; cross-Task recovery lists were deferred by
that baseline and are delivered by the accepted Slice45 amendment below.
The stable IDs remain. V2-OPS-014–017 now supersede the affected all-command population, entry,
admission ordering and general-failure recovery. The rows below consolidate those accepted
amendments; prior wording and acceptance remain in Git.

| ID | Requirement | Acceptance meaning |
|---|---|---|
| V2-OPS-001 | One native V2 task center presents a reference-aligned inventory, summary, filters and selected-run detail/records. | Default entry has no open detail; selection/deep link opens it. The shared top search is absent; all eight views expose a compact creation-date group and clear, without a repeated current-view heading/description below the tabs. Native start/end dates have independent accessible names. Routine statistics explanations, the local-timezone label and timezone-help control/content are absent; actual population/deduplication and local-day filtering/display semantics remain unchanged. The filter/table boundaries align and controls wrap readably when space is limited. Manual refresh has Chinese busy feedback; background polling stays quiet and normal same-query refresh preserves visible content/context. Shared shell, narrow/keyboard use, bounded return context and existing Task links work without hard-coded reference data. |
| V2-OPS-002 | Unified runs preserve Task/item/Result distinctions and count one explicitly linked organizing run once. | Apply V2-OPS-014 before querying the complete population. Organizing queued/pre-start failures remain visible in their admitted Task; original occurrences/attempts and same-Task continuation retain durable history. Queue completion cannot overwrite Task outcome; ordinary work remains discoverable on its own library page under V2-FILES-007. |
| V2-OPS-003 | Search, status/kind/time filters, counts and paging are bounded and authoritative on the server. | Each of the eight views exposes only the local creation-date range and clear: without a selected range it reads that view’s complete authorized population; a selected range restricts it. Management API consumers retain their existing filters. Display/filter timezones agree and the end date includes the whole day. Cards and filtered totals use one authorized population and consistent read basis; cursors bind to query/authorization context. Attention is a labelled overlapping facet. No frontend page-only totals, fabricated pages or unavailable-as-zero. |
| V2-OPS-004 | Names/scopes and progress reflect durable historical evidence rather than current configuration or approximate UI inference. | Preserve admission/pinned context or label missing legacy evidence. Known item counts reconcile; unknown totals stay indeterminate; scan errors/attachment steps are separate; Preview, waiting, ignored and uncertain outcomes are not organize success. |
| V2-OPS-005 | Task detail connects per-item explanations, durable operation/results, relevant audit/logs and secret-free JSON export. | Source/target, recognition/policies, completed steps, failure/effect certainty and next action remain independently inspectable. Logs supplement results; records and exports are task-scoped and clearly bounded. |
| V2-OPS-006 | Manual organization starts from live ResourceLibrary Files and reaches exact planning, explicit selected execution and durable results. | V2-OPS-015/017 admit the task before business readiness; preserve exact Files scope/return context, no MediaLibrary organizing or index authority, and no stale/unknown automatic resubmission. |
| V2-OPS-007 | Cancellation and four-type continuation are backend-authoritative, cooperative and Web-completable. | Under V2-TASK-003/007, Pause/resume-from-pause is retired. Cancellation does not undo effects or interrupt in-flight calls. Four-type decision/analysis/summary/explicit confirmation re-enters the same Task with exact remaining safe scope, pins/fences, current capacity and authority; no CLI fallback, consumed-token reissue, withdrawn-intent/current-permission bypass or successful/uncertain replay. |
| V2-OPS-008 | Task-linked decisions and single/bounded failed-analysis recovery complete in native V2 with per-item safety. | Recognition, Metadata, Classification and conflict decisions use existing gates; saving decisions does not execute. Exact analysis/Preview and separate execution intent link back to the original item. Mixed selections preserve accepted/refused outcomes; uncertain mutation stays investigation-only and retired retry APIs stay retired. |

## Operations and Tasks redesign — CURRENT (Slice 45 PASS / CLOSED)

The user-approved 2026-10-15 amendment extends the accepted baseline and passed Slice45 final review.
The current eight-view/four-type journey and historical reference images are in
[task-center-page-spec.md](task-center-page-spec.md). V2-OPS-014–017 supersede the affected
nine-view/general-failure/creation/admission wording of the original accepted foundation;
the stable rows below now state the combined current meaning.
It supersedes the mandatory separate Preview-page realization of `V2-OPS-006/008` and the former
standalone Scan-entry obligation; exact zero-mutation plans, explicit execution authority and all
`V2-AUTH-*` / `V2-SAFE-*` requirements remain unchanged. The user-approved 2026-10-18 first-deployment
amendment treats Scan as never shipped, including definition-bound scan-only/scan-and-plan modes; no
retirement recognition, old-mode/V1 parity, migration or dedicated historical compatibility layer remains.
Ordinary not-found/argument/unsupported-type validation replaces special retirement errors. Supported-
work history, restart/recovery safety and frozen accepted facts remain intact. The FileIndex amendment below adds
complete retirement and CLI/Web live-list parity to the same Slice45. The subsequent user-approved
`V2-OPS-013` amendment also retires the standalone Preview product using the same first-deployment
absence standard. Shared zero-mutation analysis/immutable plans remain; earlier preservation of
diagnostic/scheduled Preview products and retired command-family discoverability is superseded.

| ID | Requirement | Acceptance meaning |
|---|---|---|
| V2-OPS-009 | Task Center provides eight sibling organizing list pages and native recovery by the four business types. | All/running/attention/ended and Recognition/Metadata/Classification/conflict share one horizontal navigation row. V2-OPS-014/016 define population and attention. Group one Task per type with affected-file counts; tasks may overlap types. Query/count/page over the authorized full population; reads/navigation have no work/Provider/Storage effects. |
| V2-OPS-010 | Files manual work and four-type recovery show an exact same-interface plan summary before explicit selected execution. | Task admission follows V2-OPS-017; mutation requires complete bounded discovery, real stability, production planning/attachments, source/target/operation/completeness, per-item reasons and destructive impacts. Confirmation atomically binds exact plan/source/pin/subset and permitted effects. Unselected/unready items remain independent; material incomplete bounds cannot execute a first-N prefix. Unknown submissions reconcile without replay. V2-AUTO-010/011 define Automation initial intent; no separate Preview product is offered. |
| V2-OPS-011 | Scan products are absent on first deployment; shared capabilities needed by supported work remain. | Remove standalone Web/API/CLI routes, aliases, registration/help, work-type/readiness/action entries, scheduling/execution/retry/continuation, exclusive models/services/repositories/schema and dead code. Remove definition-bound scan-only/scan-and-plan values/aliases/defaults and exclusive branches as the narrow Slice45 exception to the then-frozen Slice43. No retirement page/410/guidance/special guard, compatible executor, conversion, old-work settlement/takeover/migration, V1 parity or dedicated history/cancel/export remains. Old URLs/commands use ordinary not-found/argument errors under normal authentication; shared supported-type validation rejects before discovery/admission/authority. Never convert Scan into organization or grant implicit mutation authority by removing a default. Keep genuinely shared discovery/filtering/real elapsed stability/planning, zero-mutation analysis/Rules tests and all supported-work Results/pins/audit/permissions/restart/recovery/non-replay. Standalone diagnostic/scheduled Preview preservation is superseded by V2-OPS-013. No media/runtime/user-data clearing or Git-history rewrite is authorized. V2-FILES-005/006 remain a separate unit in the same Slice; other Slice43 workspace/Run once/metrics/settings work was outside45 acceptance and subsequently accepted in43, with the intent amendments in46. |
| V2-OPS-012 | Four business recovery lists lead to task/type-scoped processing with analysis, same-page summary and explicit continuation. | Recognition, Metadata candidate/correction, Classification and conflict use current legal choices/checkpoints. Save/analysis grants no effects; confirmation binds the exact eligible subset. V2-OPS-016 keeps required human lineage until real outcomes, preserves independent attempts/siblings, and leaves technical/uncertain history read-only. No separate Preview/operator-managed DryRun task, cross-Task bulk mutation or successful/uncertain replay. |
| V2-OPS-013 | The standalone Preview product is absent on first deployment; organizing owns shared zero-mutation analysis and exact plans. | Remove standalone Web/V1/API/CLI/alias/help, Task/command/scheduled/definition-bound dispatch/retry/continuation, exclusive models/repositories/schema/composition and dead code. Old inputs use ordinary authenticated not-found/argument/shared unsupported-type validation before discovery/Provider/admission/authority; no retirement page/410/guidance/special guard, hidden executor, automatic conversion to Organize, old-work settlement/takeover/migration/history/cancel/export or V1-parity layer. Organize without --execute, same-page creation/recovery summaries, Rules/configuration checks and Automation internal planning/permission checks reuse existing analysis/plan/Task/Worker capabilities with exact source/configuration/plan/version evidence. Separate analysis-only records findings/unready items without formal execution backlog or single/unattended authority; admitted Files/Run once tasks retain their real business findings under V2-OPS-017/V2-AUTO-011. Execution still requires exact authorized plans, pins/fences, revalidation and completed/uncertain non-replay. Preserve supported-work data/reopen/results/audit; do not clear media/runtime databases; this retirement requirement does not itself authorize unrelated Automation redesign; accepted Automation requirements define that boundary. |

For V2-OPS-012 as narrowed by V2-OPS-016, the four-type recovery journey must expose the failed
stage, source/target, completed steps,
effect certainty and permitted action per file/attachment. Repair dependencies or save a legal
decision, explicitly re-analyze the allowed scope, handle any new blocker, then review the in-context
summary and confirm the eligible selected subset. Admission/running is not resolution; membership
follows current durable problems, recovery attempts retain independent history, and a repeated
failure explains its new cause and next step. Dependency repair never silently repins old work to
new Active; unavailable pinned context refuses continuation with guidance. Unknown confirmation
responses reconcile the exact durable request; uncertain effects have evidence/investigation only,
and separate analysis-only findings are not fabricated execution failures. An explicitly admitted
Files/Run once Task owns its real analysis-stage business problems under V2-OPS-017/V2-AUTO-011.

## FileIndex retirement and shared live lists — CURRENT (Slice45 PASS / CLOSED)

The user-approved 2026-10-18 amendment adds complete FileIndex retirement to current Slice45.
It supersedes V1 global indexing, FileIndex catalog/detail/statistics, automatic result sync and
optional indexed Files feedback; it preserves supported Task/Result/pin/audit/permission/source
safety and actual internal stability. [The retirement design](file-index-retirement-spec.md)
defines the accepted CLI and end-to-end journey. Closure facts live in Progress and the Slice.

| ID | Requirement | Acceptance meaning |
|---|---|---|
| V2-FILES-005 | CLI `mediaflow files list`, ResourceLibrary Files and MediaLibrary browsing share library-scoped live Storage listing without recording a file catalog. | Resolve the same Active library kind/ID/root and bounded relative directory/cursor through shared application behavior. Preserve exact names, supported entry types, path confinement, kind-separated cursors, bounded/unknown totals and actionable errors. List/refresh/paging creates no file/observation records, Tasks/Results, execution authority, Provider/Hash calls or media mutations; it never falls back to an index. Explicit subsequent work retains its required durable records. |
| V2-FILES-006 | FileIndex fully exits the product and all runtime consumers under the prelaunch boundary. | Remove indexed CLI/API/UI/reprocess/statistics, global file-directory/occurrence/disposition persistence, repositories/stand-ins, dedicated schema, initialization, sync/repair paths and dead code. Fresh supported deployments and every supported CLI/API/Worker/discovery/organize/recovery/Automation foundation work without FileIndex; do not hide or rename it or substitute a no-op/global cache. Exact work-scoped source/plan/pin/stability/results, locks and completed/uncertain non-replay stay authoritative. No old FileIndex production migration, dual write, historical FileID/API or takeover compatibility is required; do not clear existing runtime data/media. Necessary shared dependency removal did not itself accept Automation business features; their delivery is recorded separately in Progress. |

## Automation workspace requirements — CURRENT (Slice 43 PASS / CLOSED)

Slice43 is PASS / CLOSED after A's review of original Base
`853973dbbf8289fa2ad40657033e94e870a690e4` through implementation
`97316131946bdecc483b684f6e6f6ecb98c5594d`; its Contract/review remain at
`e9f1a8dc607cfc6d5ea02141b058da8ce849cd70:SLICE.md`, with closure facts in [Progress](progress.md).
The hold Contract `ed974e0df8b263f631bfe48b524da461013d8780:SLICE.md` and branch
`frozen/slice-43-2026-10-15` remain historical, unchanged. This factual delivery update preserves
the stable IDs and the Contract's explicit deferrals and evidence limits. Accepted V2-AUTO-010/011
now replace the independent grant and initial analysis/confirmation ordering of V2-AUTO-002–004;
V2-OPS-016 limits Task Center recovery to four business types. Stable rows below incorporate
these accepted meanings; old43 grant/initial-confirmation prose remains historical in Git.

Scan/Preview/FileIndex removal is already accepted under45. Historical old-mode parity/inventory/
migration clauses are superseded by `V2-OPS-011` first-deployment absence. `V2-OPS-013` replaces the
independent Preview product form with shared exact organizing analysis/plan summaries, preserving
scoped authorization, checks, supported pins/results/audit and non-replay. Reactivation does not
restore retired entry points, schemas, executors or dedicated compatibility/history machinery.

The accepted `V2-TASK-011` amendment updates `V2-AUTO-001/007/008` below: three shared runtime
settings live in System Settings and the unused stale-age parameter is removed. `V2-AUTO-012`
updates flow/rate/record results; `V2-AUTO-013–015` update creation/editing/direct list Run once.
The stable rows incorporate these amendments; historical43 delivery/closure is unchanged.

| ID | Requirement | Acceptance meaning |
|---|---|---|
| V2-AUTO-001 | One native Automation workspace provides definition inventory and execution records in the shared shell; runtime settings move to System Settings under the accepted Slice47 amendment. | One Chinese content title and the remaining two tabs retain consistent controls, content boundaries and focus styling. Remove the settings tab/form and safely navigate old settings links to the existing System Settings page. Preserve authoritative metrics, unavailable/empty/denied/error guidance, real bounded server search/filter/sort/paging and responsive/keyboard/deep-link reachability. V2-AUTO-016 retires only the old definition/editor Web journey; names are plain text and current create/edit cards remain. The settings relocation is accepted under V2-TASK-011, without rewriting historical43 delivery. |
| V2-AUTO-002 | Definition lifecycle uses typed forms and one focused checked Save to publish the intended automatic-organization successor. | There is no mode selector or conversion action. Create/copy/edit/enable/disable/reference-safe remove retain whole-document validation, applicable evidence, RBAC, audit and optimistic concurrency without publishing sibling Draft edits. Published, enabled, authorized and running states remain distinct; copy starts disabled without authority and removal preserves history. |
| V2-AUTO-003 | Native V2 combines exact zero-mutation planning with explicit scoped scheduled execution intent. | V2-AUTO-010 supplies intent through checked Enabled/enabled-successor publication and withdraws it through disable/removal; no independent grant or mandatory pre-analysis. Analysis never grants permission. Due execution retains pinned scope, full per-item plans and current permission/capability/conflict/effect checks before mutation. |
| V2-AUTO-004 | Run once directly organizes one published definition’s bounded saved scope without changing its schedule. | Under V2-AUTO-011, one explicit command supplies current-principal one-run intent and admits the Task before readiness, with no file picker, prior grant/analysis or second initial confirmation. Complete enumeration within min(itemLimit,100), real stability and backend plans/checks precede effects; incomplete/overflow never executes first N. Empty alone is no-work. Four business blockers use explicit safe recovery; source ownership, exact request reconciliation, independent outcomes and successful/uncertain non-replay remain. Disabled definitions can run once without enabling. Old scan/plan definitions and analysis-only records acquire no execution authority. |
| V2-AUTO-005 | Cross-definition history and metrics use durable run links and truthful current or historical outcomes. | Task/execution count once; admission/pre-start failures remain visible, preparation/grant-preflight analysis, discovery alone and rejected admissions are not execution runs. Supported historical runs retain their admitted context/outcome and count once; retired Scan/Preview gain no dedicated history/migration/compatibility obligation under V2-OPS-011/013, and surviving records are never relabelled as organization. Under V2-AUTO-012, rate is completed/(completed+failed) for original due/definition Run once Tasks; cancelled and unfinished Tasks are excluded. Files/CLI manual and ordinary operations do not participate. File outcomes never gate Task-flow success; actual organizing success remains independent. Server-calculated windows/timezone/denominators, labelled no-work outcomes and missing-data states are truthful; historical context survives definition edits/removal. |
| V2-AUTO-006 | Automation execution records show the current Task flow result, original actual times, independent file outcomes, concise Chinese failure reason and next step. | Under V2-AUTO-012, records and Task Center use the same durable five-state Task flow. Server status filters/counts/paging agree before page limits; file/recovery proof never overrides failed flow or acknowledged cancellation. Completed flow can have failed/partial/skipped/ignored files, unknown effects or missing Results, with independent truthful file counts/causes/effects. Pending/running human waiting remains unfinished; unavailable Task evidence stays unavailable. Legal continuation can change current flow result/statistics without another run or rewriting original times/attempts/file effects. Rows retain one 查看详情/收起详情 button; details contain at most 执行结果和时间 / 失败原因 (failed only) / 下一步. Missing times are —; unreadable/truncated reasons and uncertain effects are explicit. No recovery tutorial, Task Center/definition navigation or recovery/execution controls. Reads are zero-write; refresh/filter/paging preserve exact scope and reject mismatched cursors. No second store/queue/engine or successful/uncertain replay. |
| V2-AUTO-007 | Under the accepted Slice47 amendment, System Settings uses a compact three-field form with shared managed authority and truthful meanings. | Capacity bounds queued/claimed executable organizing Tasks across all entrances, not parallelism or ordinary-file task count. Worker poll covers its shared idle work checks; Scheduler poll checks Automation due definitions only. Remove the stale-age parameter without adding observation/timeout behavior. Checked Save preserves unrelated Drafts/settings, uses backend bounds and distinguishes publication/adoption. Existing immutable documents stay readable with unchanged digest/pins. Concise meanings remain; no engine tutorial or new configuration store. |
| V2-AUTO-008 | Settings consumption is proved by the actual eligible runtime consumers. | Under V2-TASK-011, resident Worker/Scheduler adopt their respective shared-work/due-only polling changes at safe boundaries without routine restart, including idle/long-wait transitions. Fresh per-instance values/version distinguish published/adopted/pending/override/unavailable; API binding alone is insufficient. Shared capacity is proven at real organizing admission/re-entry. The retired stale-age field is not an effective/adopted setting. CLI overrides, existing heartbeat/lease/call-timeout judgments, fences and admitted pipeline pins remain authoritative. |
| V2-AUTO-009 | Automation supports automatic organization only; the other two modes are entirely removed. | Remove scan-only/scan-and-plan mode values/aliases/defaults, selectors and exclusive publication/scheduling/admission/execution/continuation branches across Web/API/CLI. The 2026-10-18 first-deployment amendment selects this removal in Slice45 under V2-OPS-011, with ordinary unsupported-value validation and no legacy-mode inventory/conversion/history/parity/retirement layer or compatible executor. Never reinterpret removed modes as organization or make default removal grant authority. Preserve supported-work intent/pins/results/audit and completed/uncertain non-replay, shared internal analysis, organizing DryRun and Rules/configuration checks under V2-OPS-013; no standalone Preview product remains. Automation workspace delivery was accepted separately in43 and amended in46, rather than by45 retirement acceptance; prior V1 acceptance stays historical. |

## Authority and evolution

The complete canonical V1 definition and stable IDs in [requirements.md](requirements.md) remain
the product baseline. V2 uses
operator goals and the UX requirements above to shape interaction while preserving every existing
correctness, security, authority and data-integrity invariant. Each active Slice contract may refine
its V2 surface and architecture within these boundaries, and a
future Slice may add stable requirements through an explicit A-owned documentation change. Task files
must not silently expand this V2 layer.

React, TypeScript, Vite, TanStack Router, TanStack Query, testing tools and the feature-first source
tree are adopted Slice 30 architecture decisions. They are intentionally not encoded as permanent
product requirements here; the Python runtime, authority, authentication, coexistence and cutover
boundaries are.

## UI-V2 Files Contract — 2026-09-14

The accepted baseline is consolidated in [Product Experience](product-experience.md#real-storage-files),
[Architecture](architecture.md#ui-v2-files-and-manual-organize-authority-update--2026-09-13) and
[the Files specification](file-page-visual-spec.md). ResourceLibrary/live Storage owns physical
entries, exact relative paths and server-derived SourceIdentity; browser FileID/fingerprints or
FileIndex membership never confer listing/organizing/execution authority. Same-kind bounded ordinary
commands keep capabilities, current evidence, explicit Delete/Replace/Save, independent outcomes and
OrganizerExecutor-only mutation; cross-Storage Move verifies before source removal. No direct browser
Upload/Download or arbitrary binary/media editing. Page-local library Save composes checked atomic
Active publication; failure preserves prior Active.

The current Files page displays no recognition/organize-status feedback. Original optional feedback,
result synchronization and index-compatibility allowances are superseded for the selected target by
`V2-FILES-005/006`, without claiming all runtime dependencies have exited. Until that outcome passes,
known sync failure remains independent and never permits replay. Exact accepted historical text is
retained at `865ebdce47b0b323064fd8e05fbfaa54546e6269:docs/v2-requirements.md`.

## UI-V2 Files Visual Contract — 2026-09-14

The immutable [`文件页.png`](pics/文件页.png), at 1536×1024, defines the replacement shared light shell
and Files composition. [Files specification](file-page-visual-spec.md) owns copy/fixture/layout and
visual acceptance; [MediaLibrary specification](media-library-page-visual-spec.md) owns its separate
page. Shared chrome does not create another authority or imply unrelated business-page redesign.

## TARGET — Manual organize dialog (Slice53 ACTIVE)

User-authorized 2026-11-09 Task activation; [Slice53](../SLICE.md) fixes the scope.
These requirements are not delivered CURRENT behavior. They refine `V2-OPS-010/012/017` presentation
and post-confirmation navigation, without changing early durable admission or execution authority.

| ID | Requirement | Acceptance meaning |
|---|---|---|
| V2-OPS-018 | ResourceLibrary Files manual single/batch/folder organizing uses a readable centered modal, one primary plus attachments per page, with per-item correction and one final subset confirmation. | Preserve Files background and existing library/Automation card conventions. Show real preparation, readable identity/source/target/operation/issues, and expandable exact diagnostics. Previous/Next only browse and preserve item drafts. Explicit Save and re-analyze saves the legal decision then generates the new exact plan, without execution. For 10 ambiguous files, make 10 candidate selections and 10 save/reanalysis actions, review all 10 and confirm once with 确认整理 10 项. Unready/readonly/admitted items remain independent; only the selected eligible exact subset may execute under existing overwrite/cleanup authority. Desktop/390px/short viewport, keyboard/focus/scroll/close, failures and exact-context reopen remain usable. |
| V2-OPS-019 | Proven manual execution admission closes the organizer and opens the exact returned Task using existing Task Center detail UI. | Show 正在提交… and prevent duplicate confirmation. Lost responses reconcile the original submission only; known admission takes the same exact-task handoff. Unavailable Task association/read preserves exact known context and reread, never guesses the newest Task or resubmits. Admission is not file success. Task Center task-detail layout/content/progress/results/recovery UI remains unchanged; existing continue/readonly links reopen the exact organizer context. Preserve pins, independent outcomes and completed/uncertain non-replay. |

No new Task engine/schema/permissions/Provider or Task Center redesign is authorized. Existing
CURRENT journeys remain authoritative until implementation and independent acceptance; the
[TARGET journey](product-experience.md#target--manual-organize-dialog-slice53-active) supplies the
complete operator sequence.
