# Slice 52 — 探索、页面切换与自动化入口体验修整

```text
Slice ID: 52
Name: Explore, Navigation and Automation Entry Experience
Owner: A — Slice Owner / Architect / Final Reviewer
Status: PLANNED
Base SHA: 9aa6054e0a2f624b9fb5c0e0fa8d70b232a6cfa8
Implementation Head: NOT SET
Working Branch: main
Development Authorization: PLANNING ONLY; IMPLEMENTATION NOT AUTHORIZED
Risk: Medium
Planned Test Level: T3; reassess if implementation changes T4 boundaries
Next Action: USER AUTHORIZES SLICE ACTIVATION; THEN B PLANS THE FIRST TASK
```

## Authority and accepted baseline

用户于 2026-11-07 提出探索页四项、页面切换两项、自动化页一项体验问题，先授权只读调查，
随后明确要求“开始规划 Slice”。本 checkpoint 只确定用户结果、边界和验收；不激活 Slice、
不代 B 编写实施 Task、不修改产品代码，也不授权推送、发布或部署。

Base 固定为调查及规划前的接受基线 `9aa6054e0a2f624b9fb5c0e0fa8d70b232a6cfa8`；
后续规划／激活提交不重设 Base。Slice51 原 Base、已审实现、终审及全部限制保留于
[固定关闭记录](https://github.com/kentinya/mediaflow/blob/c0a02875e53f249f1ac7d22b9b667c6a453c87b9/SLICE.md)，
Slice50 和其他已关闭 Slice／独立修正的身份、延期与历史同样保留，不重开或追改旧验收。
生命周期和测试分工统一遵循 [Development Workflow](docs/development-workflow.md)。

规划前治理检查 PASS；工作区和 Git 可写，暂存区为空。分支为 main，HEAD 即上述 Base。
预存已跟踪变更仅 `mediaflow/.DS_Store`；另有未跟踪系统元数据、调查脚本、日志、`15`、
`output/` 下既有材料及 `testdata/`／`web/` 元数据，全部保留且不纳入 checkpoint。
不读取用户运行数据库、私有配置、凭据或媒体作为例行验证材料。

## User goal and requirement mapping

用户进入探索后直接看到协调的作品搜索、筛选和海报；按页浏览不会持续拉长页面，详情可
完整阅读并准确返回。切换侧栏主页面舒缓、稳定，文件／媒体库读取不闪现挤压内容的提示。
自动化列表保留现有有效管理入口，退出与编辑卡重复的旧“打开”功能。

| Required Outcome | 用户原问题 | 稳定 TARGET 需求 |
|---|---|---|
| RO-1 探索布局与完整详情 | 探索 1 双标题；2 不协调／搜索错位；3 详情不全／不能滚动 | `V2-EXPLORE-012–014` |
| RO-2 固定页长浏览与返回 | 探索 4 加载更多使页面过长 | `V2-EXPLORE-015` |
| RO-3 舒缓切页与稳定读取 | 切页 1 动画太快／闪烁抖动；2 两种库短暂刷新提示 | `V2-UX-014/015` |
| RO-4 自动化旧打开功能退出 | 自动化 1 删除“打开”按钮及连带功能 | `V2-AUTO-016` |

稳定定义见 [V2 TARGET](docs/v2-requirements.md#target--slice52-experience-refinement-planned)，
完整旅程见 [Product Experience TARGET](docs/product-experience.md#target--slice52-experience-refinement-planned)，
组件边界见 [Architecture TARGET](docs/architecture.md#target--slice52-experience-refinement-planned)。
本规划拟替换 `V2-EXPLORE-004/006` 中追加加载及“已加载列表”的返回表示，细化
`V2-EXPLORE-005/006`、`V2-UX-012`，并取消 `V2-AUTO-001/014` 等对旧 Web 定义详情／
后继草稿编辑入口的保留义务；CURRENT 在实现和独立验收前仍为既有接受基线。
其余 `REQ-WEB-*`、`UX-*`、`REQ-SAFE-*`、Explore 真实查询／来源／错误边界和自动化
checked publication／执行记录／非重放语义保持，不扩大 V1、API／CLI 产品退役范围。

## Investigation and evidence limits

代码调查基于 Base；现有页面核对了重复可见标题和追加列表。下列是定位及规划依据，
不是已完成修复或原生验收证明：

- `AppShell.tsx` 输出 `mf-page-context`，探索页另有 h1，形成重复“探索”。
- 搜索沿用 `mf-field` 上下16px margin，flex底部对齐未消除间距；探索顶部还显示只读
  文件搜索占位，工具区、类型与筛选缺少统一布局。
- `ExploreDetailCard` 未接入可滚动正文，公共 `mf-modal-body` 为 `overflow: hidden`；
  图片／长简介超过可用卡高时缺少滚动区。
- `explore-query.ts` 使用 infinite query，页面合并全部已读页；每次20项、上限500页
  不能避免当前文档增长。现有 API 已支持按页读取，无需新增接口。
- Shell 从0.2透明度用200ms恢复，两种库内容另有170ms淡入，叠加存在闪烁风险。
  最终节奏仍须检查真实中间过程，不能以 CSS 时长证明通过。
- 两种库将 `isFetching` 直接渲染为正文刷新提示，缓存重读也会插入／移除该行。
- `AutomationInventory` 的名称及“打开”都走旧 definition 路由，关联 editor 后继草稿
  编辑／复制；`AutomationOccurrencesPage` 也有旧详情返回链接。不能只隐藏按钮。
  相关管理 API 具有共享用途，不能机械删除。

## RO-1 — Coordinated Explore layout and readable detail

探索主内容区只有一个“探索”标题，公共定位文字不再重复占位；侧栏同名入口保留。
作品搜索、提交按钮、电影／剧集选择构成协调工具区，常用筛选紧随其后，更多筛选折叠。
探索不显示不可输入的文件搜索占位，通知和身份操作保留。统一控件高度、间距和对齐；
校验提示出现后仍可读可操作。桌面自然分列，390px保留两列海报且工具区合理换行，
无水平页面溢出、遮挡或大幅留白形成的碎片布局。统一2:3海报、片名／年份／真实评分、
缺图和长名可访问、TMDB署名及现有浅色视觉保持。

点击准确作品后，居中卡片适配桌面、窄屏和较矮视口。标题／关闭入口清楚稳定，正文能
通过滚轮、触摸及键盘读到最后一项和 TMDB 外链；滚动详情不带动背景。图片、长简介、
长名称、电影／剧集、加载／缺项／读取失败均有可用布局和原有恢复路径。关闭、Escape、
浏览器后退恢复条件、作品页、滚动与入口焦点，锁定／滚动条占位准确释放。共享弹卡只作
必要呈现调整；存储、库、任务与自动化卡片不得因此裁切或抖动。

## RO-2 — Fixed-page browse/search without accumulated document height

浏览和搜索统一采用每页最多20项的普通分页；上一页／下一页、当前页和紧凑页码导航可用。
翻页替换当前网格，不将所有访问页累计到 DOM，不自动预取所有后续页。保留 Provider＋
作品类型＋ID 身份及当前页去重。可访问范围遵循现有服务上限；总结果数不冒充全部可访问，
末页／服务窗口边界真实，页码控件本身不能无限铺开。

切类型、提交新关键词或改变浏览条件从第1页开始。退出搜索恢复原浏览条件、页与位置；
详情开关不改当前页。成功翻页定位到新结果区合理起点，鼠标／键盘仍可继续浏览。
快速翻页、切条件和迟到响应不能串页／类型；页码、已应用条件和可见结果始终一致。
读取目标页可保留同条件成功页，但须说明实际显示页及正在读取的目标页。失败不追加、
不虚增当前页、不清空成功结果，只显式重试该目标页；首次失败、真实空态、越界／结果集
变化和身份／Provider错误继续提供原范围恢复。保留有界缓存和鉴权隔离，不新增持久列表、
独立详情深链或刷新／重认证恢复作品义务。

## RO-3 — Comfortable main-page transitions and stable library reads

覆盖全部九个现有侧栏主页面。过渡比当前200ms更舒缓，以约350ms为调校起点；结合
透明度落差、缓动和真实中间帧决定最终效果，不能仅加长时长而保留明显闪灭。共享页头／
导航及内容宽度稳定，不叠加整页与内容区重复淡入，不残留旧页或闪白。快速切换、前后退
及认证续转保持 URL／内容归属，交互和真实读取无需等动画。同主页面标签、页码、条件、
库／路径和弹卡开关不重播整页过渡，既有弹卡动效保留；reduced-motion静态可用。
不新增动效设置，不为动画延时请求或串行读取。

文件和媒体库页区分首次库信息、首次目录读取和同条件后台刷新。实际等待区域保留协调
占位，有效缓存和快速返回直接呈现。已有内容后台重读、手动刷新或命令后更新均不插入
挤动列表的短暂提示行；必要忙碌反馈放在稳定区域并保持可访问。慢读取仍可辨，真实空态、
无 Active、权限、失败和安全重读入口保持。不以禁用必要请求、沿用旧权限、错属目录或
无限骨架掩盖问题；普通操作、配置卡片和整理任务的进度／独立结果、恢复与命令生命周期
保持原归属。

## RO-4 — Retire Automation's old Open journey

任务列表移除“打开”，名称成为普通可读文本；保留“编辑／复制／运行一次”及原权限和
独立反馈。新建／编辑使用现有中文卡片和有效 lifecycle 深链，启停随创建／保存生效；
执行记录及准确 Task 查看／四类恢复继续可达。

退出旧 Web `operations/automation/definition/$definitionId` 及连带
`operations/automation/editor/$definitionId` 页面、路由、导航身份、入口和专属依赖。
旧地址普通未找到，不保留别名、重定向或退役说明页。旧详情专属后继 Draft 编辑／复制
控件不迁入新卡片。清理仅服务该链路的客户端查询／模型／样式／夹具及测试；历史页面
返回链接回到合法自动化列表／执行记录，不删除历史页或制造另一“打开”。

按实际消费者保留共享管理 API、通用配置 Draft、API／CLI、历史查询和权限模型；本次
不扩大为自动化后端接口全面退役。禁止删除 Definition／Task／Result／审计／运行记录，
不重写配置，不丢失已有未知创建／保存／复制／运行一次请求的核对上下文。

## Required surfaces and safety boundaries

必需表面为 Explore 页面／分页状态／详情卡、Shell 主页面过渡、两种库读取呈现、
Automation 列表和旧 Web 路由依赖、直接受影响测试及交付时必要的现行文档协调。
复用现有只读页接口、Provider／图片／CSP边界和配置／执行命令，只作实际所需的共享调整。

- 探索浏览／翻页／详情和纯页面切换不准入工作、不发布配置、不新增媒体 Storage读取／变更；
  文件／媒体库仍执行原有有界只读目录查询，不因切页额外触发 Provider 或媒体执行。
- 后端仍决定权限、Active、命令与效果；不为快显跳过鉴权、放松检查或自动重发。
- 保留 immutable pins、confinement、并发 fencing、审计脱敏及未知效果不重放；已有工作
  按原合法 pin 继续。五态流程／独立文件结果不变；C 使用 A 命名／分类后仍是 C。
- 禁止 FFmpeg／FFprobe 依赖。新测试使用临时／本地夹具和假 Provider／Storage。

明确延期：新源、推荐／订阅／下载／播放、独立详情深链或持久会话恢复、无 Active专用启动、
全站视觉重设计／主题设置、其他页面业务改造、自动化 API／CLI全面退出、新命令／schema／
权限／队列／恢复引擎、历史清理／旧任务转换／跨版本升级、生产外部服务／用户媒体／
发布和部署。所有既有未变延期保持，不以新规划改写旧关闭事实。

## Acceptance and final validation

| AC | 必需可见结果／证据 |
|---|---|
| AC-1 | 探索主内容仅一个可见标题；作品搜索与按钮实际对齐，类型／常用／扩展筛选协调；桌面和390px无横向溢出，校验／长文案不破坏布局。不能只数 heading 忽略重复普通文字。 |
| AC-2 | 桌面、390px和矮视口，电影／剧集、长名称／简介、有无图片均能真正滚到详情末尾并操作外链；标题／关闭可达，背景不滚；关闭／Escape／后退恢复页、位置、焦点。 |
| AC-3 | 浏览／搜索连续访问多页后只渲染当前页至多20项，文档不随访问页数累长；上一页／下一页／页码、末页／服务上限、条件重置、退出搜索与详情返回正确。 |
| AC-4 | 快速翻页／切条件、迟到响应、失败页重读、真实空态和结果集缩短／越界保持页码／条件／内容归属；不丢成功页，不伪造空态或新页成功。 |
| AC-5 | 九页正常／快速切换、前后退及认证续转过程舒缓，无闪白、几何跳动、旧页残留或叠加淡入；同页交互不重播；reduced-motion静态可用。检查中间帧／交互，CSS数值或停稳截图不能单独证明通过。 |
| AC-6 | 两种库冷读、缓存返回、快速／慢读、手动刷新和操作后更新有真实反馈；刷新提示不再短暂占位挤动列表；空／权限／失败可辨，跨库／路径不串数据。 |
| AC-7 | 列表无“打开”及名称旧入口；旧 definition／editor 普通未找到，无悬空消费者／专属实现；有效新建／编辑深链、保存／启停、复制／运行一次、记录／Task链接与未知核对保持。 |
| AC-8 | 探索／导航零业务变更；鉴权隔离、checked Active、pins／fences、任务／文件结果分离和非重放无回归；不删除运行历史或误删共享后端能力。 |

计划等级 T3：Router／Query／共享弹层／真实 API 读取的集成与原生可见旅程。B 在激活后
按实际依赖规划 Task 和具体命令；Developer 只跑新改及直接受影响测试。B 承担对应验收
及 Slice-final覆盖，按工作流选择真实 Python／本地 Provider夹具的探索浏览器旅程、
九页切换／两种库读取、自动化原生旅程及受影响 Web 门禁；共享 Shell／弹层的回归范围
须有实际影响依据。若触及权限、Active发布、mutation、schema、并发或核心安全，先重评
T4，不将其藏在视觉调整中，也不预先要求无关全发布矩阵。

## Closure Packet and A Final Review

尚无实施 Task、实现 checkpoint、产品验收或关闭结论。规划校验只证明文档／治理一致，
不证明七项体验已修复。后续 B 提交精确 Base..Implementation Head 的 Closure Packet；
A 独立审查本合同全部结果和表面后才能宣布 PASS / CLOSED。
