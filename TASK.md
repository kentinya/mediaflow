# Task 51.1 — 探索完整旅程与 V2 首页切换

Authority: committed [Slice51](SLICE.md) at
`58a748663b67180c103c37f65062dddd95ac5645`, including A51-01;
[Development Workflow](docs/development-workflow.md) governs the same-Task correction and test ownership.

```text
Task ID: 51.1
Task Type: SLICE
Parent Slice: 51
Status: READY FOR B REVIEW
Task Base: 3c8053b06c218e76084ec1c06cf57f03259da84c
Difficulty: High
Test Level: T3
Planner / Reviewer: User-authorized B substitution for this correction plan; independent B review pending
Implementation Authorization: AUTHORIZED — TASK 51.1 A51-01 CORRECTION; B REVIEW PENDING
```

用户本轮明确“代替 B 规划 Task”，授权同一代理在 A 退回后代替 B 补齐本 Task 修正计划。
这是规划角色例外，不构成独立 B 验收或修正后的 A Final Review；规划轮不启动
Developer 实施、不把状态改为 IN PROGRESS，也不以本计划批准候选。后续实施按用户指令
启动，B 独立验收，A 再审完整 Slice。原 ID／Task Base／Goal／Scope／High／T3 保持，不创建 Task51.3。
本次是在原 Task 内对 A51-01 给出具体修正指导，合法继续；原完整计划／验收／测试分工仍见
`9efe8ccd:TASK.md`，历史实现不重做。本轮具体工作以下列指导为准，未完成的 A 阻塞不重置。

## Goal and existing journey

原目标仍为 Slice51 RO-2／RO-3／RO-4 和 RO-1 的 V2 Web 首页替换：浏览 → 筛选／搜索 →
准确详情 → 返回，加载、真实空态及失败分别可见且可恢复。
本轮只完成 **A51-01：合法零结果经过生产 TMDB adapter／API 后呈现真实空态并可恢复**。
对应 `V2-EXPLORE-002/004/007/008/010`、Slice RO-2／4、AC-3／4／7／9／10；
[完整旅程](docs/product-experience.md#target--v2-explore-homepage-slice51)及
[Provider／API 边界](docs/architecture.md#target--v2-explore-homepage-slice51)保持。

| 现有入口／动作 | 修正后可见结果和恢复 |
|---|---|
| `/ui-v2/` 连接 → 探索 → 选择合法但无匹配的筛选，例如本地夹具的韩语 | 请求成功，显示“没有符合条件的作品”，没有读取失败、海报或加载更多；清除条件恢复真实非空列表 |
| 作品名搜索提交无匹配关键词 → 切电影／剧集 | 两类型均为正常搜索空态，明确当前类型与关键词；修改关键词后仍可搜索到作品 |
| 从已有筛选／已加载列表进入空搜索 → 退出搜索 | 恢复原浏览类型、条件、已加载页及位置，不把空搜索混成旧条件结果 |
| 真正的畸形上游／网络／凭据失败 → 原有读取恢复 | 仍显示相应失败，保留已成功区域和原恢复入口；不得把所有异常吞成空结果 |

零结果是一次成功的外部只读查询，不创建 Task、执行权限、Draft／Active 或媒体效果。
请求页仍为 1–500；数据源总页数为 0 与用户请求第 0 页是不同含义。

## Actual gap and preserved evidence

本轮从 `main` / `58a748663b67180c103c37f65062dddd95ac5645` 开始，治理检查 PASS，
工作区与 Git 可写。`git diff d91a9dd2 HEAD -- mediaflow scripts tests web` 为空，A 所审的
产品、测试与 harness 未变。已核对原 A 浏览器复现的请求／响应、零 Storage 调用及业务表
计数保持；复用其实际发现，不新造产品入口，不联系真实 TMDB 或用户媒体。
本机证据：`.git/validation-evidence/d91a9dd2/a51-final/` 的
`empty-journey-details.json`／`upstream-empty-pages.jsonl`／`tmdb-schema-note.json`；
它们是本机契约驱动的假上游证据，不承诺远程可访问。

修正前 `TMDBProvider.browse/search` 共用 `_explore_page`，在进入内部模型前拒绝
`total_pages < 1`。内部 `ExplorePage`、API `totalPages` 和前端 normalizer 均沿用至少
一个展示页的约定；现有 UI 已支持 `totalResults=0 / items=[] / hasMore=false` 的正常空态。
`scripts/explore_harness.py::_list_payload` 却用 `max(1, …)` 生成上游总页数，adapter
空页用例也写成 1；`test_explore_api.py` 的原 API double 直接生成内部页，不经过 TMDB
归一化。因此需要在上游边界修正并贯通验证，不能只给内部空页再添一个相同断言。

## Implementation Scope and ordered correction guidance

1. **先固定失败输入。** 在 `tests/test_explore.py` 扩展现有 route-aware transport／provider
   用例：对 browse/search × movie/tv 使用成功的上游
   `{"page":1,"total_pages":0,"total_results":0,"results":[]}`，通过公开 Provider
   方法触发归一化，修正前应复现失败。保留已有总页数为 1 的空页兼容用例；不调用
   `_explore_page` 来代替真实 adapter 入口。补充零页但有结果／条目、负数、布尔和错误
   类型等非法分页数据，证明修正没有扩大为任意畸形响应容忍；不用扩大到所有字段组合。

2. **只在 TMDB 边界归一合法空页。** 修改 `mediaflow/infrastructure/tmdb.py::_explore_page`：
   先保持对结果数组、整数总页／总数及 bool 的校验；仅当 `total_pages == 0`、
   `total_results == 0` 且原 `results` 数组为空时，归一到现有内部 `total_pages=1`。
   零页却带正总数或非空条目仍报 `MALFORMED_RESPONSE`；负数／类型错误仍失败。
   非空页、正总页数、请求页、上限、applied 条件、去重／末页和缓存规则保持。
   在归一化处写清“数据源零页 → 内部可展示的空窗口”的含义；不伪造总结果数或可翻页性。
   保留 `ExplorePage`／API／前端的现有内部契约，不需要放宽 domain 或前端模型；
   不修改共享 transport、错误映射、READ、配置绑定或整理用 Metadata 调用路径。

3. **补通生产 adapter → API。** 在 `tests/test_explore_api.py` 增加生产 `TMDBProvider`／
   `TMDBClient`（本地假 transport）接入现有 `MediaFlowApi` 的用例，复用真实 request helper、
   临时 SQLite 和合法 READ 身份。分别请求现有 browse/search 入口并检查 movie/tv：
   HTTP 200，`totalPages=1, totalResults=0, items=[], hasMore=false`，请求页／类型和
   搜索或筛选 applied 值正确，无错误 envelope；重复读取与现有有界缓存语义一致。
   对代表性非法上游总数通过同一 API 检查 `502 / provider_malformed`，非法请求页仍是
   400 且不触发 Provider。已有身份／零业务效果断言保留，不以业务库完全零写入否定正常审计。

4. **修正上游夹具并覆盖已有页面恢复。** 修改 `scripts/explore_harness.py::_list_payload`，
   空结果真实生成 0 总页，非空页仍按实际数量计算，不能在假上游提前归一成内部 1。
   保持本地 `httpx.MockTransport`、生产 adapter／API、图片拦截和临时数据库结构。
   在 `web/tests/e2e/explore.python.spec.ts` 复用并加强现有空筛选和搜索态退出旅程，
   补一条命名含 `zero-page` 的正常 UI 操作用例，覆盖电影／剧集无匹配搜索、改词得到
   非空结果、清除筛选／退出搜索恢复。响应监听检查真实 API 的 200 与内部空页字段，
   结合 harness 上游记录或 API adapter 用例证明上游为 0；不得拦截探索 JSON 假装通过。
   复用零 Storage 调用和耐久业务表计数对照，确认没有工作／配置效果；原凭据／限流／
   失败恢复与独立分页用例保持。桌面／390px 在同一有界旅程中核对空态、按钮及恢复。

5. **提交同一 Task 修正候选。** 只改上述 adapter、harness、直接测试和必要就地说明；
   运行下方 Developer 计划，检查完整差异、未跟踪私有文件和范围，提交实际 checkpoint，
   更新本页完成报告为 READY FOR B REVIEW。报告具体归一化规则、失败分支及实际命令／
   结果，保留 A51-01 与旧 B/A 结论指针；不自行 PASS 或关闭 Slice。

## Acceptance Criteria

- [ ] A51-01 原正常入口不再显示读取失败：合法零页空筛选、电影／剧集空搜索通过生产 adapter／API 显示真实空态。
- [ ] 上游 0 仅在零总数＋空条目时归一为内部 1；API 总结果为 0、无条目且不可加载更多。原内部 1 页空态和非空分页／末页保持。
- [ ] 当前类型、关键词／筛选归属准确；修改关键词、清除条件、退出搜索能回到相应真实内容，原浏览条件／已加载列表／返回上下文保持。
- [ ] 负数／bool／错误类型、零页有结果等畸形返回仍为真实失败；非法请求页仍被拒绝，原权限／上游凭据／网络失败与空态不混淆。
- [ ] 上游 fixture 确实生成零总页，API 用例经过生产 TMDB adapter；真实 Python＋生产 Web＋本地上游验证不拦截探索 JSON，桌面／390px 空态及恢复可用。
- [ ] 零 Storage 调用、零新增业务 Task／执行权／配置发布；原请求限制、缓存、认证、脱敏和整理路径不改。Dashboard 退出与 Task51.2 已交付行为保持。
- [ ] 原 Task Base、Slice Base 和历史身份不变；B 独立接受新候选后重评全部 Slice 结果并交最终包，A 决定最终关闭。

## Required Tests

测试归属遵循 [workflow §6](docs/development-workflow.md#6-test-levels)。High／T3 是原 Task
等级，不因本轮修正集中而降级；只读上游归一化不改变权限、Active、schema 或媒体执行。
实际若出现这些高风险影响，先回 B 重评，不沿用 T3 绕过门禁。

### Developer — affected tests

根目录，覆盖新回归、非法／不一致分页、真实 API、原 Metadata 调用和读取安全：

```sh
python3 scripts/check_governance.py
.venv/bin/python -m unittest discover -s tests -p 'test_explore*.py'
.venv/bin/python -m unittest discover -s tests -p 'test_metadata.py'
.venv/bin/python -m unittest discover -s tests -p 'test_api_security.py'
.venv/bin/ruff check mediaflow/infrastructure/tmdb.py scripts/explore_harness.py tests/test_explore.py tests/test_explore_api.py
.venv/bin/ruff format --check mediaflow/infrastructure/tmdb.py scripts/explore_harness.py tests/test_explore.py tests/test_explore_api.py
git diff --check
```

`web/` 中构建生产资产，再只跑本轮新增与空上游直接影响的原生用例；新用例名含
`zero-page`，其余 grep 项对应当前已存在的完整用例名，不得因未匹配新用例而假通过：

```sh
npm run build
npm exec prettier -- --check tests/e2e/explore.python.spec.ts
npm exec eslint -- tests/e2e/explore.python.spec.ts
npm run test:e2e -- --config=playwright.python.explore.config.ts tests/e2e/explore.python.spec.ts --grep 'zero-page|desktop: browse|search with its own type'
```

交接注明实际收集的新／旧用例和数量；若改动额外直接受影响文件，补跑它们的相关检查。
不要求 Developer 跑全仓 Python／Web／E2E、安装包或发布矩阵，不写全量证据 dossier。

### B — independent acceptance and Slice final

B 独立检查原 Task Base..新候选的完整差异，并特别核对本次相对
`d91a9dd2fd5833a5977a319e90d0283b05625e9a` 的修正范围。先核对生产 adapter 的零页成功
及畸形失败，再运行下列当前候选验收；修正引入的执行输入不能只复用原 PASS 标签。

根目录，除上述直接 Python／Ruff 外，读取身份／静态资源／旧入口退出仍正常：

```sh
.venv/bin/python -m unittest discover -s tests -p 'test_api_credentials.py'
.venv/bin/python -m unittest discover -s tests -p 'test_v2_ui.py'
.venv/bin/python -m unittest discover -s tests -p 'test_dashboard.py'
.venv/bin/python -m unittest discover -s tests -p 'test_operator_ui.py'
```

`web/` 中运行原探索前端契约、类型／条件归属／独立恢复回归，并在真实 Python 链路运行
完整探索 spec，覆盖本轮零页、非空多页／末页／返回及原失败恢复。T3 选这几个直接边界，
不新增全仓／全发布矩阵；同一候选一次完整探索 spec 已含 Developer grep，无需再重复 grep。

```sh
npm run typecheck
npm run test -- run src/entities/explore/explore.test.ts src/features/explore/ExplorePage.test.tsx src/shared/api/explore-api.test.ts
npm run build
npm run test:e2e -- --config=playwright.python.explore.config.ts tests/e2e/explore.python.spec.ts
```

B 从现有页面亲自核对零结果到恢复的请求／可见状态，检视桌面／390px 当前截图，确认
harness 发出的是真实零页且没有媒体／工作效果；这些若已由当前 spec 完整证明，不再
另造一套同义脚本。若因改动新增其他集成影响，再针对该事实补充检查。

B 重评原 Slice AC-1–11／全部 Required Surfaces。未变的导航／详情／图片、Dashboard
删除实现与既有共享读取／历史等可引用原报告中对应不变输入的证据，并明确比较范围、
依赖／配置／资产身份和原始失败／限制。本轮 Python adapter 与 harness 的新输入必须
重验；旧 wheel／生产构建证据只属于原产物，不宣称新候选已通过未运行的安装包或发布
门禁。若实际交付变化触发新包装／T4 门禁，按工作流重评并由 B 执行。
保留 `01f4e05d:TASK.md`／`ab3edf8d:TASK.md` 的原失败、Base 对照、共享夹具／定位、
可选 skip 及未运行项；保存精确 candidate、命令／cwd／实际结果和稳定本机或 CI 日志。

A51-01 及全部必需结果满足后停止规划，重交 **SLICE READY FOR A REVIEW** 的更新包，
包含原 Slice Base、新 Implementation Head、逐项结果、当前验证／合法复用和文档协调项。
B 不自行修改 A 的 Contract／Roadmap／Progress 或宣告 Slice CLOSED；若仍失败则本 Task
FIX REQUIRED，不为测试数量、可选证明或 P2 整理创建下一 Task。

## Non-goals

新增探索功能或 API、改前端展示／权限模型、放宽任意畸形上游、改变内部分页契约、
重设计缓存／请求控制／详情／搜索状态、重新实施 Task51.2、修复其他页面或旧测试维护项、
新 Provider／schema／队列／引擎、真实 TMDB／用户媒体／私有运行库验收、推送／部署。
全部原 Slice 延期保持；本轮不改 A 文件或转正 CURRENT，也不使用计划文档宣称修正已交付。

## Preserved checkpoints

- Task51.1 原已审范围：`3c8053b06c218e76084ec1c06cf57f03259da84c..9efe8ccd480b257e12eee29b9b90075ee8f809f6`；
  产品实现 `de86eab84e8627c0f656e51cea66e17e8ef1baf2`，原 B 报告 `01f4e05d:TASK.md`。
- Task51.2 原 B PASS：`01f4e05d5cc03822d2e9ced3dfa91a2838990f62..d91a9dd2fd5833a5977a319e90d0283b05625e9a`；
  完整报告及原 Closure Packet：`ab3edf8d3973012b2fb4f7152a18b90a0bf6e3f8:TASK.md`。
- A 已审 Slice 范围：`214b69b1e64b24fc22068c2e1760cd1b0c6ac787..d91a9dd2fd5833a5977a319e90d0283b05625e9a`；
  A FIX REQUIRED：`58a74866:SLICE.md`。旧 COMPLETE／READY 是 B 当时结论，已被 A51-01
  退回，不能作为当前 Slice 接受证据；Slice50／PATCH-20261107-1 及更早身份／延期保持。

## Developer Completion Report

```text
Implementation checkpoint: f31c47f0ef9fff65b5685ef194ead52a69e20ab1
Task Base unchanged: 3c8053b06c218e76084ec1c06cf57f03259da84c
Scope: A51-01 only; Dashboard retirement, Slice docs and other pages untouched
Status after this report: READY FOR B REVIEW (Developer 不自签 PASS)
```

### 本轮修改行为(源码身份)

1. **TMDB adapter 边界** `mediaflow/infrastructure/tmdb.py::_explore_page`：
   保留 results 数组、整数总页／总数及 bool 校验。仅当上游
   `total_pages=0`、`total_results=0` 且 `results=[]` 时，把“数据源零页”
   归一为既有内部可展示空窗口 `total_pages=1`；`total_results` 仍为 0、
   items 为空、不可翻页，不伪造总数。零页但正总数或带条目、负数、bool、
   错误类型仍抛 `MALFORMED_RESPONSE`；正总页／非空页、请求页、缓存与
   整理用 Metadata 路径未改。
2. **Harness 上游真值** `scripts/explore_harness.py`：`_list_payload` 不再用
   `max(1, …)`，空结果真实生成 `total_pages=0`，非空页按实际数量计算；
   `/__harness__/stats` 新增 `upstreamListPages` 记录每条 discover/search
   假上游回答的 `page/totalPages/totalResults`，供浏览器用例核对归一化前真值。
3. **真实 adapter → API 测试** `tests/test_explore_api.py`：新增生产
   `TMDBProvider`／`TMDBClient`／`HttpxTransport`（本地 MockTransport）接入
   现有 `MediaFlowApi` 的用例。browse 电影／剧集（含题材、语言、年份、评分、
   人数与排序）和 search 电影／剧集均为 HTTP 200、`totalPages=1`、
   `totalResults=0`、`items=[]`、`hasMore=false`、applied 准确；重复请求
   命中既有有界缓存。代表性非法上游总数经同一 API 为 502
   `provider_malformed`；非法请求页仍为 400 且未触发 Provider。
4. **真实 Python + 生产 Web 浏览器用例** `web/tests/e2e/explore.python.spec.ts`：
   新增 `zero-page: empty filters and searches recover in place at desktop and 390px`。
   从正常连接入口以 `fr` 原始语言触发真实空筛选，清除后恢复非空列表；以
   不存在关键词分别搜索电影／剧集，两类型均是 200 空态而非读取失败；390px
   检查空态、恢复按钮与无横向溢出；改词“北岸”得到真实剧集结果；退出搜索
   恢复原电影浏览条件与列表。响应监听断言真实 API 空页字段与无错误 envelope，
   harness `upstreamListPages` 断言对应上游确为 0 页，改词后有非空页；同时
   复核零 Storage 调用与耐久业务表计数不变。未拦截探索 JSON，仅按既有方式
   本地拦截海报图片。
5. **Adapter 直接测试** `tests/test_explore.py`：新增公开 `browse/search` ×
   电影／剧集零页成功用例，以及零页正总数／带条目、负数、bool、错误类型、
   负总数仍失败的边界用例；原 `total_pages=1` 空页兼容用例保留。先以修正前
   代码运行零页成功用例，得到 4 errors（browse/search × 电影／剧集均以
   `MALFORMED_RESPONSE` 失败），再加归一化修正转绿。

### 本轮实际执行命令与结果

仓库根（cwd=/Users/songzhidong/mediaflow）：

| 命令 | 实际结果 |
|---|---|
| `python3 scripts/check_governance.py` | PASS |
| `.venv/bin/python -m unittest discover -s tests -p 'test_explore*.py'` | 46 tests OK |
| `.venv/bin/python -m unittest discover -s tests -p 'test_metadata.py'` | 36 tests OK |
| `.venv/bin/python -m unittest discover -s tests -p 'test_api_security.py'` | 13 tests OK |
| `ruff check` + `ruff format --check`（TASK 指定 4 个 Python 文件） | 全过 |
| `git diff --check` | 干净 |

`web/`：

| 命令 | 实际结果 |
|---|---|
| `npm run build` | 成功（生产资产，163ms） |
| `npm exec prettier -- --check tests/e2e/explore.python.spec.ts` | 通过 |
| `npm exec eslint -- tests/e2e/explore.python.spec.ts` | 通过 |
| `npm run test:e2e -- --config=playwright.python.explore.config.ts tests/e2e/explore.python.spec.ts --grep 'zero-page\|desktop: browse\|search with its own type'` | 3 passed（desktop 1.5s；search anchor 0.6s；zero-page 0.5s） |

本地校验时还以临时数据库手动启动 harness，确认 `browse?originalLanguage=fr`
与 `search?mediaType=tv&query=no such work` 均返回内部空页，且
`upstreamListPages` 记录对应 `totalPages=0`；该临时进程已结束，不构成新的
验收证据来源。测试／构建类命令累计约 2–3 分钟，低于本轮总时长 30%。

### 剩余风险 / B 待执行

- 按 Developer 分工只跑直接受影响 Python 用例、构建、静态检查和指定 E2E
  grep；未运行全量 Python／Web 单测／完整 E2E spec。B 仍须按 TASK 的独立验收
  计划跑完整探索 spec、前端契约／类型测试及读取身份／旧入口回归，并亲自核对
  桌面／390px 当前截图。
- 归一化仅在 TMDB 边界、且只接受“零总页＋零总数＋空 results”；B 应重点复核
  零页带结果／正总数仍 502、非法请求页仍 400 且无 Provider 调用，以及原
  `total_pages=1` 空页和非空分页／末页未变。
- 本轮未改 domain／API／前端内部至少一页契约、权限、schema、Active、配置发布、
  Storage 或整理调用；未推送、未发布、未自行 PASS。
- 工作区起点 `main`/HEAD `aa35bacf`；预存 `mediaflow/.DS_Store` 修改与全部
  未跟踪 `.DS_Store`、日志、`.explore_adapter_block.py`、`15`、`output/` 等产物
  原样保留，未纳入 checkpoint；私有配置未读取／修改。

## B Review Result

```text
Reviewed: correction candidate NOT SUBMITTED
Decision: FIX REQUIRED — A51-01 remains open
Acceptance runs: PENDING; this checkpoint only checks governance, plan references/scope and whitespace
Task blockers: A51-01
Slice Required Outcomes / Surfaces all satisfied: NO
Next: DEVELOPER CORRECTION AFTER IMPLEMENTATION INSTRUCTION → INDEPENDENT B REVIEW → RENEWED SLICE CLOSURE PACKET
```

预存 `mediaflow/.DS_Store` 修改，以及各 `.DS_Store`、本地日志、`.explore_adapter_block.py`、
`15`、`output/` 等未跟踪产物全部保留，不纳入本 checkpoint；不读取用户运行库／私有配置。
