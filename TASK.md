# NO ACTIVE IMPLEMENTATION TASK

[Slice52](SLICE.md) 已激活为 **ACTIVE**。下方为 **Task52.1 计划草案，等待产品实施授权**；
用户授权 A 代 B 的角色例外只限本次规划，后续 B 独立验收及 A 独立终审保持。
尚未修改产品代码、运行产品验收或取得 Task PASS。

Next Action: USER AUTHORIZES TASK52.1 IMPLEMENTATION

获实施授权后保留 Task ID／Base／Goal／Scope，移除本无活动实施声明，再按工作流实施；
本草案不自行授权实现、其他代理、推送或部署。最近接受基线仍为
[Slice51 固定关闭记录](https://github.com/kentinya/mediaflow/blob/c0a02875e53f249f1ac7d22b9b667c6a453c87b9/SLICE.md)，
原 Base `214b69b1e64b24fc22068c2e1760cd1b0c6ac787`、已审实现
`30c99f1bdcd9be2cb51ac82f78bc4b07eaea3113`、B Closure Packet
`e26b399c682e7c09f4e675b6ebe412f5adcf770a:TASK.md` 及全部旧接受身份／限制保持。
预存本地／私有文件不纳入提交。

## Planning Draft — Task52.1：探索页布局、详情滚动与有界浏览

Authority: committed [Slice52 Contract](SLICE.md) at
`c7913f6a751ee980db2b82ffaefec40d3d43528c`；
[Development Workflow](docs/development-workflow.md) 是生命周期／测试／Git 权威。
实施者读 [Developer experience](docs/agent-experience/developer-implementation-role.md)，
审查者读 [B experience](docs/agent-experience/task-planner-reviewer.md)。

```text
Task ID: 52.1
Task Type: SLICE
Parent Slice: 52
Status: PLANNED
Plan Authorization: DRAFT; IMPLEMENTATION NOT AUTHORIZED
Task Base: c7913f6a751ee980db2b82ffaefec40d3d43528c
Difficulty: Medium
Test Level: T3
Planner / Reviewer: A substituting for B (user-authorized planning only) / independent B
```

## Goal

完成“探索 → 浏览／筛选／名称搜索 → 浏览更多结果 → 详情完整阅读 → 原位置返回”的
同一旅程，覆盖 Slice52 **RO-1／RO-2、AC-1–4**，以及相关 AC-8 只读／鉴权不回归。
适用 `V2-EXPLORE-012–015`，完整旅程见
[Explore TARGET](docs/product-experience.md#target--slice52-experience-refinement-active) 和
[Explore CURRENT](docs/product-experience.md#current--v2-explore-homepage-slice51-pass--closed)。

进入后主内容仅一个“探索”标题，搜索、类型、筛选和海报整页协调；继续浏览不会持续
拉长文档。准确作品详情内部能滚到底，关闭／Escape／后退回原条件、浏览位置及焦点。
首读、翻页、选项、详情和图片各保留真实状态及原范围恢复；等待不冒充空态，失败不丢
同条件成功内容，旧上下文结果不能贴到新条件上。

### Actual gaps at Task Base

- `AppShell.tsx` 的 `mf-page-context` 与 `ExplorePage` h1 重复，该页还显示只读文件
  搜索占位。搜索沿用公共 `mf-field` 上下 margin，探索 flex 对齐没有抵消间距。
- `ExplorePage`／`explore-query.ts` 使用 infinite query，`flattenExplorePages` 合并全部
  已读页；浏览／搜索状态、滚动锚点和失败说明均按累加列表编写，不能只替换按钮。
- `ExploreDetailCard` 未接入已有 `mf-modal-body-scroll`，正文继承 `overflow: hidden`；
  图片／长简介超过可用卡高时不能读到底。
- 现有原生测试检查名称／属性／横向溢出和返回，但缺少正文真正滚到底及多次浏览后文档
  不累长的证据。现有原生海报夹具为1×1图片，不能单独支撑整页视觉判断。

## Implementation Scope

必需代码范围：`web/src/features/explore/`、`AppShell.tsx` 中仅限探索的标题／顶栏条件、
`styles.css` 中探索局部布局／滚动样式，以及直接受影响测试和本地 Explore harness／夹具。
复用现有 `ModalCardShell`、`useModalLayer`、滚动锁定／焦点、只读 API 和可信图片来源。

本 Task 选择**普通分页**：用现有单次最多20项的接口替换当前网格，提供上一页、下一页、
当前页和真实可浏览范围。紧凑页码按空间安排，不要求特定样式或新增页长设置；这是本
Task 的实现方案，不重新定义用户需求或 Slice 接受边界。

### Ordered implementation steps

1. **记录可见基线并统一整页布局。**
   用本地隔离夹具保存桌面和390px的同视口改前布局。仅在探索抑制重复定位行和只读文件
   搜索占位，保留侧栏、通知／身份操作。统一标题、搜索／提交、类型、常用／更多筛选、
   网格、结果导航及署名；用探索局部规则处理 margin、尺寸、换行和校验提示空间，不改
   所有页面的公共字段默认值。保持2:3海报、真实评分、缺图和长名可访问、窄屏两列。
   整页层级／密度／留白协调，不能只把输入框与按钮对齐就结束。

2. **替换累加状态，区分成功页与读取目标。**
   在 query／state／页面中使用完整条件＋类型＋关键词＋页的查询身份，只渲染当前成功
   页，移除累加展示及其专属文案／死依赖。保留原校验和后端 `applied` 条件说明；前后页
   及可浏览页数遵循真实总页数和 `pageLimit`，不把服务窗口外的结果冒充全部可访问，
   不自动读取所有后续页。复用现有五分钟闲置TTL及容量常量，为保留的列表页设置明确
   上限（本方案最多16页）；不能只限制条件数量，却在每个条件下累存全部访问页。
   options／detail 原有有界机制、鉴权隔离及401／断开清理保持，不新增缓存平台或
   持久浏览／凭据存储。

3. **完成条件切换、搜索往返和失败恢复。**
   新条件／类型／关键词从第1页开始；搜索内类型与原浏览锚点独立。捕获原条件、成功页、
   滚动与入口，退出搜索恢复；缓存已淘汰时重读同一目标页，等该页内容可用后合理恢复
   位置。同条件翻页等待时可保留成功页，明确实际显示页与目标页；失败留在成功页，
   仅显式重读失败目标，不虚增成功页码。换条件时旧内容不能冒充新结果，迟到响应不能
   夺回当前展示。结果集缩短／越界提供真实说明和回合法页动作；首次失败、真实空态、
   选项失败、403、上游凭据错误各自保留原恢复。新结果合理定位，导航可键盘完成。

4. **接入详情内部滚动并保护退出。**
   使用已有可滚动正文能力或等价探索局部样式，在可用卡高内容纳图片、长名称／简介、
   电影／剧集事实、署名和外链，标题／关闭清楚。加载、读取失败及缺图时仍可安全退出
   只读详情。沿用 `detail` 参数和准确作品身份；必要时使用现有路由局部滚动重置控制，
   不让背景回顶或宽度变化。关闭／Escape／后退恢复同一浏览页、位置与入口焦点；入口
   已消失时使用现有合理回焦目标。滚轮／触摸／键盘只滚卡内正文，锁定／滚动条占位
   准确释放。不改公共 Modal 生命周期、默认 `.mf-modal-body`／字段规则或整页动画机制。

5. **补齐测试与真实可见证据。**
   将旧“加载更多／累加页”断言改为新用户结果，保留原查询隔离、失败及返回的验证目的。
   增加翻页竞争、缓存淘汰返回及详情真正滚动等缺口。可扩展 `scripts/explore_harness.py`
   的本地虚构作品、长简介、分页／延迟／失败场景，保留真实 Python API／生产适配器链路、
   真实上游零页语义和副作用统计。用本地可辨识、具有实际比例的海报／背景夹具核对视觉，
   不联网抓真实TMDB／图片，也不读用户配置、数据库或媒体。普通多页和服务边界分别用
   有界场景验证，不以实际抓取500页为前提。保存同视口改后整页及详情滚动证据，检查
   实际操作；CSS数值、DOM形态或停稳截图不能单独证明美观／滚动／返回正确。必要用法
   说明只更新本 Task 事实，不提前宣称 Slice 交付，不改 Slice／Roadmap／Progress 或
   稳定要求的状态／边界。

## Acceptance Criteria

- [ ] **TAC-1 布局：** 探索主内容仅一个可见标题（正常侧栏入口保留），只显示可用作品
  搜索，输入／按钮对齐。桌面和390px的标题、工具区、筛选、网格、导航／署名在层级、
  密度、比例、留白和字体／色彩上协调，长文案／校验可用，无页面横向溢出。
- [ ] **TAC-2 浏览有界：** 浏览和搜索连续访问多页后只呈现当前成功页，文档长度及同时
  渲染条目不随访问量累增，仍可继续及返回先前页。前后页、真实末页／服务上限和总结果
  含义正确，无后续页自动请求或保留全部页的缓存堆积。
- [ ] **TAC-3 条件与往返：** 新条件／类型／关键词从起点开始，搜索不假装应用浏览专属
  条件；搜索内切类型不改原浏览锚点。详情／退出搜索恢复原条件、页、滚动及合法焦点，
  包括缓存淘汰后的原页重读；不新增刷新／重认证恢复会话承诺。
- [ ] **TAC-4 竞争／失败：** 目标页慢读或失败时实际显示页／目标页可辨，成功内容保留，
  只重读失败范围，不虚增成功位置。快切页／条件、迟到响应、结果集缩短／越界不串结果，
  不把未返回或读失败当真实空态。
- [ ] **TAC-5 详情：** 桌面、390px和代表性矮视口下，电影／剧集、长名称／简介、有无图片
  均可用滚轮／触摸／键盘真正读到正文末尾并操作外链，标题／关闭可达。慢读／失败可退；
  关闭／Escape／后退不改背景位置／宽度，锁定正确释放，重复打开不残留旧作品。
- [ ] **TAC-6 读取／安全：** 首读、选项、详情和图片的原失败／合法恢复可用；401／断开
  清理身份相关数据，403不冒充空态，上游凭据失败不清除合法API身份。正常布局差异、
  稳定占位及平顺替换允许；不为动画人为延迟／串行本可并行的请求，正常数据依赖、鉴权
  顺序与有限退避保持。
- [ ] **TAC-7 共享表面：** 探索同页筛选／分页／搜索／详情不重播整页入场。Shell其他页
  入口／搜索／身份操作及认证续转保持；复用共享弹卡而不改其生命周期，其他卡片的滚动／
  退出／焦点不因本 Task 失效。浏览／分页／详情零媒体Storage效果、零任务准入／配置
  发布／执行权限变更；图片来源／CSP／脱敏保持。

## Required Tests

遵循 [测试等级和分工](docs/development-workflow.md#6-test-levels)。以下为实施／验收计划，
本次规划没有运行这些产品测试；在实际候选代码和生产构建上，用本地隔离夹具记录结果。

### Developer — affected tests

仓库根目录：`python3 scripts/check_governance.py`、`git diff --check`。

`web/` 内：

```sh
npm run typecheck
npm run test -- run src/features/explore/ExplorePage.test.tsx src/entities/explore/explore.test.ts src/shared/api/explore-api.test.ts src/shared/ui/AppShell.test.tsx src/shared/ui/modal-card.test.tsx
npx eslint src/features/explore src/shared/ui/AppShell.tsx src/shared/ui/AppShell.test.tsx
npx prettier --check src/features/explore src/shared/ui/AppShell.tsx src/shared/ui/AppShell.test.tsx src/shared/ui/styles.css tests/e2e/explore.python.spec.ts
npm run build
npm run test:e2e -- --config=playwright.python.explore.config.ts tests/e2e/explore.python.spec.ts
```

新增 paging／query 测试须追加到同轮受影响命令；新增／改动文件追加相应 lint／格式检查。
覆盖成功、非法关键词／数值、页界限、读取竞争、失败保留、鉴权隔离、锚点恢复和真实滚动。
若调整 Python harness，追加根目录命令：

```sh
.venv/bin/ruff check scripts/explore_harness.py
.venv/bin/ruff format --check scripts/explore_harness.py
.venv/bin/python -m unittest discover -s tests -p 'test_explore*.py'
```

Developer 完成受影响验证及原生截图／滚动核对后交接，不承担全量Web／Python／E2E或发布矩阵。

### B — acceptance and regression

在精确 Task Base..candidate 上独立复现四个原问题及 TAC。重点实测第2页进详情再返回、
搜索内切类型再退出、目标页失败／迟到响应、缓存淘汰后原页恢复、长正文滚到底。
桌面、390px及矮视口核对同视口改前／改后整页及真实操作；不机械要求占位／几何变化为零，
也不把明显闪烁／布局突兀跳动当正常加载放行。

`web/` 内正常门禁和原生回归：

```sh
npm run typecheck
npm run lint
npm run format:check
npm run test -- run
npm run build
npm run test:e2e -- --config=playwright.python.explore.config.ts tests/e2e/explore.python.spec.ts
npm run test:e2e -- tests/e2e/page-transition.spec.ts tests/e2e/deep-link.spec.ts
```

仓库根目录：

```sh
python3 scripts/check_governance.py
.venv/bin/python -m unittest discover -s tests -p 'test_explore*.py'
git diff --check
```

全Web单元回归由 B 负责，依据是 AppShell 被所有页面共享，且本次涉及身份读取后的列表／
查询切换；原生范围限于 Explore 和共享导航／认证续转，不机械扩成全站E2E。
既有 page-transition 测试用于共享兼容性，不代表本 Task 已交付 RO-3 的全局体验改善。
按 [证据规则](docs/development-workflow.md#verifiable-evidence-and-reuse) 记录或复用 B 自己
匹配的运行，原失败／限制保留。T3不要求全Python／Docker／wheel／生产服务矩阵；若实际
触及 Active、mutation、权限、schema、并发或核心安全，先重评等级和范围。

## Non-goals

本 Task 不实施 RO-3 全主页面切换／加载接入重整或两种库刷新提示修正，不实施 RO-4
自动化“打开”链路退出；不规划下一 Task，不把本 Task PASS 当整个 Slice 完成。
不改全局动效、公共Modal生命周期／默认字段规则、库／任务／自动化业务、后端接口／
Provider语义／CSP／执行权限／schema／媒体引擎。不新增源、推荐、订阅、下载／播放、
页长设置、独立详情入口／持久会话，不清历史、不修无关基线、不作通用设计系统重构。
必要修正留在本 Task；若冻结表面确实阻碍目标，交 B 复核同一 Task 的范围与测试。

## Developer Completion Report

尚未实施。获授权后填写实际 checkpoint／READY FOR B REVIEW、行为与文件、受影响测试
真实结果、失败／风险和剩余工作；没有结果先不填 PASS 或产品测试计数。

## B Review Result

尚未独立审查；角色代行不包含验收。B 后续记录精确 Reviewed Base..Head、PASS／FIX REQUIRED、
实际验收／限制及整个 Slice 结果是否满足，不自行关闭 Slice。
