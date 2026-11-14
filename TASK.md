# Task PATCH-20261114-3 — 通知页可读性、统一卡片与操作状态修复

Next Action: B 在固定候选复核投递恢复响应丢失时显示“恢复结果未知”且与正文一致，明确拒绝仍显示“恢复没有应用”，随后继续本轮剩余 T4 验收。

用户于 2026-11-14 在规划检查点 `a3418bd7df4ed939943c6f73e8abe90db03a4d6c`
后明确“激活Task”，本 Task 正式启用并授权实施。原 ID／Base／目标／范围／测试分工
保持；本激活检查点仅更新本文件，不改产品代码、现行产品文档、SLICE、Roadmap 或 Progress。
不包含委派、推送或部署授权。

Authority: 用户授权的现有通知页体验纠正；遵循
[Development Workflow](docs/development-workflow.md) §3.1、§5–8。B 规划并独立验收，
Developer 实施；Slice54 及原接受边界、SLICE／Roadmap／Progress 保持。

```text
Task ID: PATCH-20261114-3
Task Type: STANDALONE MINOR BUG
Parent Slice: NONE
Status: READY FOR B REVIEW
Task Base: 51480dc318837e4f1e4f9c60c17b8e708abb6409
Implementation Head: 07624ec95b948f211bd93ed77596ebdea7e9992f
Evidence Head: 07624ec95b948f211bd93ed77596ebdea7e9992f
Difficulty: High
Test Level: T4
Planner / Reviewer: B
Development Authorization: USER AUTHORIZED ON 2026-11-14
```

规划前分支 `main`，HEAD 为上述 Base，工作区及暂存区干净、工作区／Git 可写；
`python3 scripts/check_governance.py` PASS。本轮仅改 `TASK.md`，保留此前独立修复的
接受指针。若实施授权前出现独立产品变化，先由 B 重新核对兼容性和边界，不静默重设 Base。

激活前分支 `main`，HEAD 为上述规划检查点，工作区与暂存区干净；治理检查 PASS。
Base..规划检查点仅有 `TASK.md` 规划变更，没有独立产品变化；保留原始 Task Base。
当前 PLANNED 表示已授权、待 Developer 开始；实施开始时转为 IN PROGRESS。

### Goal and observed gap

用户从侧栏通知入口管理既有 HTTPS Webhook，能快速读懂是否生效／启用、接收地址、
事件和密钥引用就绪状态，在与自动化／规则协调的卡片内添加、查看、编辑并完成既有
草稿检查和发布；从投递记录理解独立结果、失败原因、已知影响及下一步，明确确认后
只恢复所选投递，再返回原列表。读取、失败、并发拒绝及不确定结果均可理解和安全恢复。

适用要求：`REQ-NOTIFY-001/002`、`V2-UX-001–004`；完整既有旅程见
[Operations administration](docs/product-experience.md#operations-administration)，
运行边界见 [Notifications and operational logging](docs/architecture.md#notifications-and-operational-logging)。
自动化／规则卡片仅作为现有视觉与交互参考，不将其领域协议移植到通知。

调查使用 Base 源码的新构建、隔离 Node 假 API，实际查看六个现有页面及桌面／390px，
并对照自动化卡片；未使用生产凭据、接收端或用户媒体。这些是调查结果，尚非真实后端验收：

- 六页以 `mf-dashboard`／`mf-count-section`、原生 `dl` 和表单控件拼接；常用输入约
  153×21px，URL／环境变量名显示不全。状态徽标缺少本页适用样式，正文、说明、状态、
  技术字段混排；英文主文案、原始事件／租约／时间值和大段安全机制说明难以扫读。
- 添加／定义详情／编辑／投递详情分别跳整页，与已接受的居中卡片和原列表返回不协调。
- `NotificationListPage` 的添加链接仅设 `aria-disabled`；无可编辑草稿时仍呈蓝色且
  鼠标可进入无法提交、却可填写的表单。
- `NotificationEditorPage.updateForm` 只更新本地输入；修改地址后旧测试成功仍显示。
  测试／验证／发布绑定已保存 Draft，未清楚区分其与屏幕上未保存输入；返回详情再编辑
  会丢输入，没有明确放弃确认。
- `DeliveryDetailPage` 的固定返回链接丢失列表状态筛选；筛选死信→详情→返回变为全部。

### Implementation Scope

边界为六个现有通知表面：`NotificationListPage`、`NotificationNewPage`、
`NotificationDetailPage`、`NotificationEditorPage`、`DeliveryListPage`、
`DeliveryDetailPage`，及其必要路由／查询状态、只读投影适配、通知专属样式和测试。
公共 modal、按钮、Shell 仅作本 Task 必需的兼容复用／局部接入，禁止全站重设计。

1. **先固定可复现行为与参考。** 为四个已复现交互问题补回归；保留同视口基线，
   核对真实 API 的 actions、Draft／Active、投递状态及精确版本约束。以自动化／规则的
   页面边界、标题、控件、按钮层次、卡片和留白为参考，形成通知专属组件／样式，
   不复制整套自动化或规则业务代码。
2. **整理两张主列表和内容层次。** 配置列表优先显示 Webhook、接收地址、可读事件、
   已生效／仅草稿、启用状态和密钥引用就绪；投递列表优先显示事件、结果、尝试次数、
   可读时间、失败摘要及查看动作。配置与投递入口清楚，不混为媒体任务结果。常见状态、
   事件、单位和动作使用中文，技术 ID／修订／版本／租约等保留诊断入口；未知值如实回退。
   长 URL／名称／错误可读，合法原始标识和安全证据保持可查；不显示密钥、payload 或原始异常。
3. **统一卡片与表单。** 添加、定义详情、编辑在通知配置列表背景打开协调居中卡片；
   投递详情／恢复在投递列表背景打开同体系卡片。复用 `shared/ui/modal-card.tsx`。
   基本地址／密钥引用、事件与启用、超时与重试合理分组，控件尺寸／开关／标签／帮助／
   行内错误统一；高级参数保持可达、值完整，不靠删除字段或默认授权简化。
   结果先显示结论、原因、已知影响和下一步，诊断折叠；未触碰空表单不铺满错误清单。
   头部／关闭／底栏稳定可达，正文内部滚动，慢读／错误／就绪不突然撑高重居中。
4. **修复编辑和命令状态。** 无可编辑草稿时不提供可执行的添加表单，显示直接、合法的
   下一步；既有“创建后继草稿”仍由明确动作发起。区分“未保存修改／已保存草稿／
   已检查／已发布”，保留现有保存草稿、检查、发布及显式测试协议，不合并成新的发布命令。
   测试明确说明会向接收端发送一次签名请求。未保存输入不得被当作已保存测试／验证／
   发布对象；有未保存修改时，引导先保存或明确放弃后再操作已保存版本。
   输入或相关版本变化时旧测试／验证结论失效，发布确认同步失效；迟到响应不覆盖新上下文。
   未保存退出统一提供继续编辑／明确放弃，继续后地址与输入不变；在途动作阻止重复提交和
   冲突退出，刷新卸载有适当保护。已保存草稿重开从耐久状态读取，本地输入按身份、动作和
   Webhook 隔离，刷新／重新认证不串对象、不自动提交，不持久化凭据或密钥值。
5. **修复返回、并发和失败。** 保留全部现有合法通知路径、对象身份和深链；直接进入／
   刷新／重新认证打开同一卡片并有准确列表背景和默认返回去向，不留下第二套整页表单。
   普通打开／关闭、前后退保留来源列表筛选、分页、滚动和焦点；投递恢复后仍回原筛选。
   返回状态只接受同源受支持通知路径及合法条件。并发拒绝保留可修正输入与旧 Active，
   重新读取时明确采用服务端值或保留本地输入，不静默将旧输入配到新版本提交。
   保存／发布／恢复成功后读取失败仍保留已知命令结果；响应丢失说明可能已生效或已发送，
   只能依据现有可靠读回核对，不能证明则保持未知；不得自动重发或误报未发布／未投递。
   测试未知需提示核对接收端，再次测试必须是新的明确意图。
6. **完成定向回归和交接。** 更新中英文呈现断言及原生浏览证明，保留既有协议／权限／
   绑定／不重放断言。只协调实际受影响的当前通知操作说明，不预写完成事实，不改
   SLICE／Roadmap／Progress 或已接受 Slice 的身份。Developer 冻结连贯候选交 B 独立验收。

既有后端业务保持：一个 Webhook 的 checked activation 不得夹带兄弟定义或其他配置变化；
测试绑定精确已保存修订／版本；失败投递按后端 actions、原身份和状态／时间 fence 独立恢复，
重复投递风险和明确确认保留。已完成媒体效果、通知重试／退避／租约／死信、权限、审计、
脱敏、HMAC 及 Worker 运行协议不变。若发现必须改变这些边界，先交 B 重新评估，不借本 Task 扩展。

### Acceptance Criteria

- [ ] 六页的中文文案、标题／内容边界、状态、控件、按钮和信息密度与现有系统协调；
  添加／查看／编辑及投递详情使用上述卡片，长地址与引用可读，事件、就绪和实际结果一眼可辨。
  技术诊断可查；实际失败、未知、已保存／已生效不因美化而混淆。
- [ ] 桌面 1440×1000、390×844 和矮窗口 1440×700 的完整页面与卡片对照通过；
  主动作和退出稳定可达，长文本／全部字段可操作；实际加载中间态、错误、重试读取、空态、
  正常／hover／focus／disabled／busy、键盘 Tab／Escape／回焦和 reduced-motion 均检查。
- [ ] 无草稿／无权限／草稿不可编辑时，鼠标和键盘不能绕过不可用入口继续填写无效表单，
  原链接直达提供准确解释及合法下一步；打开、关闭和刷新零配置写入、零测试发送、零媒体变更。
- [ ] 添加／编辑／复制／启停仍完整可用，保存草稿与发布生效明确区分；读回真实 Active。
  测试仅经显式操作发送一次、绑定当前已保存上下文；编辑、版本改变或对象切换后旧证据／
  确认失效；未保存当前值不能借旧成功继续发布，迟到响应不串上下文。
- [ ] 所有退出方式共同遵守未保存／在途保护；继续编辑保留输入和准确地址，明确放弃才丢弃。
  已保存草稿重开可读回。普通往返和深链／刷新／重认证准确打开对象，不自动重提命令。
- [ ] 投递筛选（含死信）、分页和原列表返回保持；结果、失败原因、已知接收效果、是否会再发
  及下一步清楚。过期租约／死信只恢复所选记录，显式确认与可能重复发送提示保留；
  已完成或自动重试记录不虚构人工恢复动作，不改变媒体结果。
- [ ] 无效字段、缺失密钥引用、测试失败、401／403、读取失败、真实并发 409，以及命令已完成
  但响应丢失均有准确反馈和恢复；旧 Active／成功兄弟／已知效果保留，未知不冒充失败，
  不自动重放、不重新绑定接收目标、不携带其他定义发布，完整绑定／脱敏断言保持。
- [ ] 公共 modal／Shell／按钮直接消费者回归通过，既有通知 API／领域／持久化协议不变；
  B 完成固定 Base..candidate 审查、真实 Python 原生旅程及适用 T4 门禁后才可 PASS。

### Required Tests

遵循 [测试分工](docs/development-workflow.md#6-test-levels)。下列未来命令是实施／验收计划，
规划／激活轮未执行产品测试。新脚本及必要新测试只服务本 Task，不建设通用新测试平台。

### Developer — affected tests

在 `web/`：

```sh
npm run test -- run src/entities/operations/notification.test.ts src/features/operations/NotificationRouter.test.tsx src/routes/router.test.tsx src/shared/ui/modal-card.test.tsx src/shared/ui/AppShell.test.tsx
npm run typecheck
npm run lint
npm run format:check
npm run build
npm run test:e2e -- tests/e2e/notifications.spec.ts --output=test-results/patch-20261114-3-developer-node
```

将新增通知组件／状态测试文件显式加入上述定向 Vitest 命令；改到公共组件时补跑其实际
直接消费者（自动化、规则、Storage／库配置）对应测试，不用全 Web／E2E 套件代替定向覆盖。
必测四个复现、输入／读取基线配对、未保存操作与证据失效、旧响应、在途／未知非重放、
安全返回、无权限及所有状态分支，禁止为通过界面改造删除原有协议断言。

新增 `scripts/notifications_workspace_browser_proof.py`，沿用现有浏览证明模式，提供
`--artifacts` 参数；使用新生产资产、真实 Python API／临时 SQLite、可记录的假 Webhook
transport 和临时根。通过既有通知入口验证卡片、编辑／返回、真实 Draft 保存／发布、测试
及单条恢复；证明读取无写入，明确命令次数和准确身份。Developer 跑新证明及直接影响检查：

```sh
.venv/bin/python scripts/notifications_workspace_browser_proof.py --artifacts .git/validation-evidence/patch-20261114-3/developer-native
.venv/bin/ruff check scripts/notifications_workspace_browser_proof.py
.venv/bin/ruff format --check scripts/notifications_workspace_browser_proof.py
python3 scripts/check_governance.py
git diff --check
```

若修改既有 Python 测试／夹具，另跑对应测试与该次变更文件检查。Developer 不运行 B 的
全量 Python／Web／E2E 和发布矩阵；受影响结果齐全即可交接。

### B — independent acceptance / full regression

- 在固定候选先审完整 Base..Head、复现四个问题已纠正，独立查看同视口完整改前／改后及
  自动化参考；验收矩阵覆盖长地址／名称／全部事件、空／慢读／失败、390px／矮窗口、
  键盘／动效、深链／历史／刷新／重认证、明确放弃与在途保护，不能只凭尺寸或截图数量 PASS。
- 用上述原生证明在 B 的独立产物目录运行：

  ```sh
  .venv/bin/python scripts/notifications_workspace_browser_proof.py --artifacts .git/validation-evidence/patch-20261114-3/b-native
  ```

  B 补足真实第二写者 409、已完成命令丢响应后的核对、错误对象／版本响应、真实权限边界、
  切换对象／修改输入时迟到结果，以及恢复后原过滤列表的完整旅程。真实 Python 验证成功
  发布仅含所选 Webhook；记录 API 请求、配置版本／审计、transport 调用和投递状态，
  使用有界脱敏证据，不能用 Node 假 API 冒充真实后端验收。
- 按 [共享全量门禁](docs/development-workflow.md#shared-full-regression-commands) 执行适用
  T4 全量 Python／Web／Node E2E、质量、新构建／wheel 与源码外安装 smoke；验证
  `tests/test_v2_notification_operations.py`、`tests/test_notification_delivery_management.py`、
  `tests/test_notifications.py` 的精确修订、兄弟定义拒绝、发送／恢复及同版本重开行为
  （已在匹配全量中运行无需再机械重复）。公共消费者原生回归按实际影响选择。
  本 Task 不改容器／部署路径时 Docker 广域矩阵不适用，B 记录依据；不以生产服务作门槛。
- Node 与 Python 浏览器使用不同产物目录。保留首次失败、skip、未运行与环境限制；
  不删除断言、不加自动重试掩盖失败，按工作流保留实际命令／结果和候选／资产身份。

### Non-goals

不新增通知渠道、订阅／站内消息产品、事件类型、模板、批量命令、搜索／统计后端、
删除定义能力、发送／恢复协议、schema、权限、配置发布或幂等协议，不新增一键自动发布、
自动测试／自动重发、跨投递恢复、通用回滚、持久化任意本地表单的独立草稿产品。
不重设计全站 Shell／主题、任务中心、自动化、规则或文件；不改 Worker／签名／退避／
租约／媒体效果，不扩展 V1，不接生产服务、不推送／发布／部署，不开启后续 Task 或 Slice。

### Developer Completion Report

已实施并冻结候选，状态 READY FOR B REVIEW（2026-11-14）。本 TASK 报告提交仅含文档；实现提交
`83a104eeef60300ab67f7c5df7a45d0f02a2b971`，证据提交
`9329b1205cb3339fed7d73f3ec07f9f563793e02`；Base 保持
`51480dc318837e4f1e4f9c60c17b8e708abb6409`。本轮未改 Python 生产代码、
API／领域／持久化协议、SLICE、Roadmap 或 Progress，也未推送、发布或部署。

实际改动：

- 六页统一为通知专属页面和公共 `ModalCardShell` 卡片：定义列表与投递列表作为持久
  背景，添加／定义详情／编辑／投递详情作为背景上的卡片；列表筛选、分页、滚动和焦点
  在卡片往返中保留。新增必要嵌套路由，直接进入／刷新／重新认证仍打开同一卡片。
- 列表、定义、草稿、投递改用中文状态、事件、动作、单位和失败摘要；长地址、长名称、
  原始事件／修订／版本／租约／响应证据放入可展开诊断。密钥值、payload、签名头、
原始异常不进入界面。
- 添加／编辑表单按基本设置、事件与启用、超时与重试分组；无可编辑草稿时不渲染可填写
  表单，提供创建后继草稿或准确权限／草稿解释；空表单只在触碰或提交后显示行内错误。
- 草稿编辑区分已保存草稿、未保存修改、已检查、已发布；测试／检查／发布绑定精确已保存
  版本，输入、状态或版本变化使旧证据和发布确认失效，迟到响应不覆盖新上下文。远端版本
  变化提供采用服务端值／保留本地输入再保存的明确选择，不静默重绑。
- 关闭、Escape、遮罩、浏览器后退共用继续编辑／明确放弃决定；在途命令阻止重复提交和
  冲突退出，硬刷新／卸载有未保存或在途保护；成功命令后的已知结果在读回失败时保留。
- 传输丢失、5xx 和不可解析的 2xx 命令结果标为“结果未知”，提示可能已执行并只依据
  持久读回核对，不自动重发、不误报未发布／未投递。测试未知额外提示先核对接收端。
- 投递恢复保留精确交付身份与观察到的状态／时间 fence、显式确认和至少一次提示；只恢复
  所选记录，返回原投递筛选。公共 modal 对 body 的焦点回退修正为按声明 fallback 聚焦，
  通知背景 wrapper 保持 `inert`。

验证（Developer 实际执行）：

```sh
python3 scripts/check_governance.py
# PASS

cd web
npm run test -- run src/entities/operations/notification.test.ts   src/features/operations/notification-presentation.test.ts   src/features/operations/NotificationRouter.test.tsx   src/routes/router.test.tsx src/shared/ui/modal-card.test.tsx   src/shared/ui/AppShell.test.tsx src/shared/navigation/destination-model.test.ts
# 7 files, 172 tests passed

npm run typecheck && npm run lint && npm run format:check && npm run build
# PASS；生产资产已重建

npm run test:e2e -- tests/e2e/notifications.spec.ts   --output=test-results/patch-20261114-3-developer-node
# 12 passed
```

真实 Python 原生证明（新生产资产、真实 API、临时 SQLite／根、可记录假 Webhook
transport）：

```sh
.venv/bin/python scripts/notifications_workspace_browser_proof.py   --artifacts .git/validation-evidence/patch-20261114-3/developer-native
.venv/bin/ruff check scripts/notifications_workspace_browser_proof.py
.venv/bin/ruff format --check scripts/notifications_workspace_browser_proof.py
git diff --check
```

结果：PASS。Read-only 列表／详情／投递浏览未改变 Active、未发送测试、未创建投递；
显式签名测试恰好 1 次 transport 请求；Draft 保存／检查／发布后 Active 版本 1→2，
Webhook 身份集合不变且只有所选 URL 变成已编辑值；不相关配置区段未变；投递保持 1 行，
单条恢复后 dead-letter→pending；Tasks／Jobs 行数未变。证据目录（未提交）：
`.git/validation-evidence/patch-20261114-3/developer-native/`，含 `evidence.json` 和
桌面／390px 截图。

未运行／交由 B：T4 全量 Python／Web／Node E2E、共享全量门禁、真实第二写者 409 与
权限边界、真实 API 下的迟到响应／切换对象、1440×700 窗口矩阵、wheel／Docker 适用门禁
（本 Task 未改容器／部署路径）。Developer 未将定向结果冒充全量通过。

已知风险：原生证明只覆盖一个 Active Webhook 与一条死信投递；B 需补真实权限、第二写者、
并发／响应丢失和多卡片直接深链旅程。共享 `useModalLayer` 的 body 焦点回退改动已由
modal／Shell 测试覆盖，B 仍应核对其直接消费者。

### Previous B Review

首轮审查 `51480dc3..fd4856d1` 为 FIX REQUIRED：卡片缺少冲突后的读取入口，死信
恢复后的 pending 被误述为接收端尚未收到。完整复现、原因与开发指导保留于
`d09842de5b3bff61d09725fb0554d431d90488da:TASK.md`；下述修正报告和当前 B 复核
继续使用同一 Task ID／Base／验收，不重设边界。

### Developer Completion Report — FIX ROUND（2026-11-14）

Status READY FOR B REVIEW。实现提交 `93996b687e4b39cba612141b6dfc804aecac0292`，包含
源码、测试、Node E2E 与原生证明脚本；本报告提交仅改 `TASK.md`。Task Base 保持
`51480dc318837e4f1e4f9c60c17b8e708abb6409`。本轮未改 Python 生产代码、API／领域／
持久化协议、SLICE、Roadmap 或 Progress，未推送、发布或部署。

修复：

- 编辑卡片在正常表单和无草稿状态都提供可见、键盘可达的“读取最新草稿”，连接现有
  Draft 查询。读取只发 GET，不提交保存、检查、测试或发布。真实 409 失败后，用户可直接
  读取最新版本，看到既有的“采用服务端值／保留本地输入并重新保存”；保留输入会以读到
  的版本重存并核对提交值，采用服务端值会更新表单并清除旧检查、测试和发布确认证据。
  删除了以测试内部 `queryClient` 失效查询代替用户读取入口的旧用例。
- 定义详情、新建和投递详情补回正常状态的“读取最新定义／草稿状态／投递”入口；无草稿的
  新建与编辑状态也可读取最新状态，既有读取失败／降级提示的重试入口保留。
- pending 的已知接收效果不再断言接收端从未收到，改为“当前没有已确认的发送结果”，并
  明确“此前是否已有请求到达接收端，不能仅由当前状态证明”；待投递主结论显示等待下一次
  尝试。死信说明改用真实 `failureCategory`（HTTP 400、传输失败、配置缺失等），不再把
  所有死信说成尝试次数用尽。恢复命令结果保留，读回 pending 与至少一次／可能重复提示一致。
- 公共 modal、Shell、按钮和媒体结果未改；未新增通知协议、重试、租约或恢复行为。

验证（Developer 实际执行）：

```sh
cd web
npm run test -- run src/entities/operations/notification.test.ts \
  src/features/operations/notification-presentation.test.ts \
  src/features/operations/NotificationRouter.test.tsx \
  src/routes/router.test.tsx src/shared/ui/modal-card.test.tsx \
  src/shared/ui/AppShell.test.tsx src/shared/navigation/destination-model.test.ts
# 7 files, 174 tests passed

npm run typecheck && npm run lint && npm run format:check && npm run build
# PASS；生产资产 index-B0R4k6Jb.css / index-C944Junr.js；保留 chunk 体积提示

npm run test:e2e -- tests/e2e/notifications.spec.ts \
  --output=test-results/patch-20261114-3-developer-fix-node-r3
# 12 passed
```

首个 Node E2E 轮次在新增“读取最新定义”步骤后以 11/12 失败：对“密钥引用：已就绪”的
断言同时匹配背景列表与卡片，属于 strict-mode 重复匹配，不是产品失败。将断言限定到
`dialog` 后重跑通过；保留该首次失败记录。最终资产重建后再次 12/12 通过。

```sh
.venv/bin/python scripts/notifications_workspace_browser_proof.py \
  --artifacts .git/validation-evidence/patch-20261114-3/developer-fix/native-r2
.venv/bin/ruff check scripts/notifications_workspace_browser_proof.py
.venv/bin/ruff format --check scripts/notifications_workspace_browser_proof.py
python3 scripts/check_governance.py
git diff --check
```

原生证明 PASS，证据目录（未提交）：
`.git/validation-evidence/patch-20261114-3/developer-fix/native-r2/`。只读定义／投递
读取（含新增读取入口）未改变 Active、未发送测试、未改变投递；显式签名测试恰 1 次
transport 请求；保存、检查、发布后 Active 1→2 且只改变所选 Webhook；一条 HTTP 400 死信
恢复为 pending，界面显示“当前没有已确认的发送结果”，不再出现“接收端尚未收到”；
Tasks／Jobs 行数未变。`ruff`、治理检查与 `git diff --check` 均 PASS。

未运行／交 B：T4 全量 Python／Web／Node E2E、真实第二写者 409、真实权限边界、命令丢响应
核对、1440×700／390px 完整视觉与键盘矩阵、wheel／Docker 适用门禁。Vitest 的 409 旅程
使用两个连续真实 HTTP 响应和一个 API 写者状态变化，不是生产环境第二浏览器；B 仍需按原
计划用真实 Python API 复核。已知风险：新增读取入口在窄窗口的最终排版与焦点顺序仅由
Node E2E／原生证明的点击路径覆盖，完整视觉矩阵保留给 B。

本轮定向 Vitest、构建、Node E2E 与原生证明合计约 3 分钟；实现、差异审查与结果核对占
主要时间，测试时间低于本轮总时间 30%。

### Previous B Review — 修正候选

`51480dc3..6db78cba` 为 FIX REQUIRED：其他管理员发布后，读取最新草稿会丢弃本地
未保存输入。完整旅程、原因、指导与验证保留于
`5f781ddccd5abb68412d896d2a1577d528d9ef96:TASK.md`。下述 Developer 报告与当前 B
复核接续该检查点；此前接受身份与原 Task Base 不变。

### Developer Completion Report — FIX ROUND 2（2026-11-14）

Status READY FOR B REVIEW。实现提交 `ed8b7f4f2872c14488544fbfdc8164ba150ab752`；
本报告提交仅改 `TASK.md`。Task Base 保持
`51480dc318837e4f1e4f9c60c17b8e708abb6409`。本轮未改 Python 生产代码、API／领域／
持久化协议、SLICE、Roadmap 或 Progress，未推送、发布或部署。

修复：

- 读取到“没有打开的草稿”且存在未保存本地输入时，不再清除表单和原始基线。卡片保留
  输入，显示“草稿已不再打开，本地输入已保留”、原草稿版本、已生效配置可能已变化，
  并提供显式“创建后继草稿”和“放弃本地输入”。读取只发 GET；旧保存提示、检查／测试
  证据和发布确认失效。该状态隐藏保存、检查、测试和发布段，按 Enter 也不能沿用旧修订
  提交。创建后继草稿后，新修订作为显式选择出现；只有“保留本地输入并重新保存”才把后续
  保存绑定到新 revision／version，“采用服务端值”才替换本地输入。卡片正文回到顶部，
  说明与选择不会被旧滚动位置遮住。
- 读取到不同草稿修订且存在本地输入时同样保留输入，显示“读取到另一个草稿修订”的采用／
  保留选择，不静默替换。同修订版本变化的并发选择保持原行为。无草稿且无本地输入时仍显示
  原“没有可编辑草稿”说明，不渲染可填写表单。
- 原生浏览证明增加真实第二写者：通过真实 Python API 保存、检查并发布浏览器正在编辑的
  同一草稿；浏览器点击既有“读取最新草稿”后本地输入保留，再通过既有“创建后继草稿”、
  “保留本地输入并重新保存”完成保存／检查／发布，最终 Active 只包含浏览器保留的地址。
  证据记录 `crossPublishedReadPreserved: true` 和
  `finalActiveWebhookUrl: https://example.invalid/hooks/proof-edited`。

新增或加强的定向回归（均通过既有按钮完成，不调用内部 `queryClient`）：

- 乙发布后甲读取：本地地址保留、GET 增加、零 PUT、零 successor、零测试；创建后继草稿后
  明确保留本地输入，保存请求绑定新修订 `revision-draft-2`、版本 `1` 和本地地址。
- 读取到乙已创建的另一草稿修订：本地输入保留，明确采用服务端值后才替换，且没有写请求。
- 乙发布后读取、关闭提示继续编辑、再显式放弃：输入移除并回到无草稿说明，零写请求。

验证（Developer 实际执行）：

```sh
cd web
npm run test -- run src/entities/operations/notification.test.ts \
  src/features/operations/notification-presentation.test.ts \
  src/features/operations/NotificationRouter.test.tsx \
  src/routes/router.test.tsx src/shared/ui/modal-card.test.tsx \
  src/shared/ui/AppShell.test.tsx src/shared/navigation/destination-model.test.ts
# 7 files, 177 tests passed

npm run typecheck && npm run lint && npm run format:check
# PASS

npm run build
# PASS；index-R_L0IApw.js / index-B0R4k6Jb.css；保留既有 chunk 体积提示

npm run test:e2e -- tests/e2e/notifications.spec.ts \
  --output=test-results/patch-20261114-3-developer-fix-node-r4
# 12 passed
```

真实 Python 原生证明：

```sh
.venv/bin/python scripts/notifications_workspace_browser_proof.py \
  --artifacts .git/validation-evidence/patch-20261114-3/developer-fix-r2/native-r3
.venv/bin/ruff check scripts/notifications_workspace_browser_proof.py
.venv/bin/ruff format --check scripts/notifications_workspace_browser_proof.py
python3 scripts/check_governance.py
git diff --check
```

结果：PASS。只读浏览未改变 Active、未发送测试、未创建投递；显式签名测试恰 1 次
transport 请求；第二写者发布后浏览器读取仍保留本地输入；后继草稿由既有 UI 动作创建，
保留输入后保存／检查／发布，最终 Active 地址为浏览器保留值；只有所选 Webhook 改变，
兄弟身份集合、无关配置区段、Tasks／Jobs 行数不变；一条死信恢复为 pending。证据目录
（未提交）：`.git/validation-evidence/patch-20261114-3/developer-fix-r2/native-r3/`，
含 `evidence.json` 和保留输入、快照与投递截图。

保留的首次失败：新增第二写者浏览器步骤后首次原生证明因背景列表与卡片存在同名
“创建后继草稿”触发 Playwright strict-mode 重复匹配，限定到 `dialog` 后通过，不是产品
失败。首次把正文滚动写为 `scrollTo` 的 7 文件定向测试有 2 个新增用例在 jsdom 报
`formScrollRef.current.scrollTo is not a function`，改为设置 `scrollTop` 后重跑全通过；
该失败记录保留。首张保留输入截图因旧滚动位置未显示说明，已增加回到卡片正文顶部并重新
截图核对。

未运行／交 B：真实双浏览器第二写者 409、权限边界、迟到响应／切换对象、1440×700 与
390px 完整视觉／键盘矩阵、T4 全量 Python／Web／Node E2E、wheel／Docker 适用门禁。
原生证明的“第二写者”使用真实 Python API 同进程写入，不是两个独立浏览器；B 仍需按原
计划复核。定向 Vitest、Node E2E、原生证明与静态检查累计约半分钟，实现、差异审查与证据
核对占主要时间，测试时间低于本轮总时间 30%。

### Previous B Review — FIX ROUND 2

`51480dc3..bdb65246` 为 FIX REQUIRED：编辑保存成功响应覆盖随后输入的内容，只读用户
从已有草稿深链仍可编辑并提交。完整复现、原因、指导与验证保留于
`ca37a043:TASK.md`。下述 Developer 报告与当前复核接续该检查点；原 ID／Base 不变。

### Developer Completion Report — FIX ROUND 3（2026-11-14）

Status READY FOR B REVIEW。最终实现提交
`42fbe6c4bafbf880a99c59fd743b71090dc8bb1e`（主体 `925b45efec1868cd726fa7e56f5c7cbda24b5ca8`
加上保存完成时同步读取最新输入的修正）；本报告提交仅改 `TASK.md`。Task Base 保持
`51480dc318837e4f1e4f9c60c17b8e708abb6409`。本轮未改 Python 生产代码、API／领域／
持久化协议、SLICE、Roadmap 或 Progress，未推送、发布或部署。

修复：

- 保存成功不再把表单重置为请求时的值。成功回调把已确认提交的 A 与返回版本设为已保存
  基线；若保存期间表单已继续输入 B，则保留 B 和“有未保存修改”，成功提示明确说明保存的是
  提交时内容、B 尚未写入。自动读回与手动“读取最新草稿”都保留 B；检查、测试、发布继续
  只针对已保存版本，禁用并显示原因；只有再次明确保存才以新版本写入 B。输入变更同时同步
  更新保存回调读取的 ref，避免迟到的成功响应早于下一次渲染 effect 时恢复旧值。没有增加
  自动保存、本地持久化或后端协议。
- 编辑卡片现在遵循服务端 `actions.save.available`。草稿存在但不可保存时，不渲染可填写
  表单、保存、检查、测试或发布控件；显示权限原因、持久草稿只读摘要，以及“查看定义”
  “返回通知列表”“读取最新草稿”。真实保存返回 403 时立即隐藏表单并给出权限原因和
  联系管理员／重新读取的下一步，不再解释为表单或版本过期；读取只用于核对服务端动作，
  不自动重试保存。
- 原生浏览证明增加真实 `READ` principal：在同一已打开草稿上，通过既有编辑地址重新认证
  进入卡片，核对无保存／测试控件、无填写表单，并证明草稿修订与版本未变；随后可进入
  只读定义。

验证（Developer 实际执行）：

```sh
cd web
npm run test -- run src/entities/operations/notification.test.ts \
  src/features/operations/notification-presentation.test.ts \
  src/features/operations/NotificationRouter.test.tsx \
  src/routes/router.test.tsx src/shared/ui/modal-card.test.tsx \
  src/shared/ui/AppShell.test.tsx src/shared/navigation/destination-model.test.ts
# 7 files, 180 tests passed

npm run typecheck && npm run lint && npm run format:check
# PASS

npm run build
# PASS；index-DJ7-SHRm.js / index-B0R4k6Jb.css；保留既有 chunk 体积提示

npm run test:e2e -- tests/e2e/notifications.spec.ts \
  --output=test-results/patch-20261114-3-developer-fix-node-r6
# 12 passed
```

真实 Python 原生证明：

```sh
.venv/bin/python scripts/notifications_workspace_browser_proof.py \
  --artifacts .git/validation-evidence/patch-20261114-3/developer-fix-r3/native-r6
.venv/bin/ruff check scripts/notifications_workspace_browser_proof.py
.venv/bin/ruff format --check scripts/notifications_workspace_browser_proof.py
python3 scripts/check_governance.py
git diff --check
```

结果：PASS。Active 版本 1→2；显式签名测试恰 1 次 transport 请求；只读定义／投递读取未
改变 Active、未发送测试、未创建投递；`READ` 深链未改变打开的草稿修订／版本，卡片无保存
或测试控件；第二写者发布后浏览器保留本地输入并可通过既有后继草稿选择完成发布；最终
Active 地址为浏览器保留值；无关配置区段、Webhook 身份集合、Tasks／Jobs 行数未变；一条
死信恢复为 pending。证据目录（未提交）：
`.git/validation-evidence/patch-20261114-3/developer-fix-r3/native-r6/`。

保留的首次失败：新增只读 Vitest 首次运行时测试本身漏了 `connect()`，页面停在读取态；
补齐连接后通过，不是产品失败。原生证明首次给只读浏览器补深链时未定义 `webhookId`；第二次
在管理员创建草稿之前运行，读到的是“没有可编辑的草稿”而非草稿只读分支；改为在管理员已
打开草稿的阶段用第二页面验证 `READ` 深链后通过。首跑结果不作为通过证据。

未运行／交 B：T4 全量 Python／Web／Node E2E、真实第二写者 409、真实权限 403 边界、命令
响应丢失核对、1440×700／390px 完整视觉与键盘矩阵、wheel／Docker 适用门禁。原生证明的
只读账号使用真实 Python API 与真实路由，但不是独立服务进程；B 仍需按原计划复核并发、
权限和迟到响应旅程。定向 Vitest、构建、Node E2E、原生证明与静态检查合计约 3 分钟，
实现、差异审查和证据核对占主要时间，测试时间低于本轮总时间 30%。

### Earlier B review

上一轮 FIX REQUIRED 的完整旅程、原因及原失败日志见 `09e9d3de:TASK.md`。
本轮独立复核已确认其中新建／发布期间输入丢失和通知页面过渡断言问题纠正；
原 Task ID、Base、范围和 T4 分工不变。

### Developer Completion Report — FIX ROUND 4（2026-11-15）

Status READY FOR B REVIEW。实现提交
`4edb1526cc418ab5bbeb0ca96323f0584d0b5091`；本报告提交仅改 `TASK.md`。Task Base 保持
`51480dc318837e4f1e4f9c60c17b8e708abb6409`。本轮未改 Python 生产代码、公共 modal、
API／领域／持久化协议、SLICE、Roadmap 或 Progress，未推送、发布或部署。

修复：

- 新建并保存到草稿现在在请求在途时禁用整张可编辑表单：标识符、HTTPS 地址、密钥引用、
  订阅事件、启用开关、超时、尝试次数及两个重试间隔。成功仍只按真实结果进入新定义详情，
  失败后恢复可编辑并保留原输入；底部按钮忙碌状态与既有退出保护不变。
- 发布已检查草稿同样在请求在途时禁用全部可编辑字段；成功仍进入已生效定义详情，失败
  恢复编辑并保留原值。没有新增自动保存、自动重试、协议字段或本地草稿。
- 编辑卡片普通“保存到草稿”未加字段锁，继续保留上轮已通过的“处理期间可继续输入、
  成功后标为未保存修改”的行为；既有回归仍通过。
- `web/tests/e2e/page-transition.spec.ts` 的通知目的地改用当前标题“通知”，等待标识改用
  “正在读取通知定义”；九页顺序、单次过渡、Shell 几何、溢出和等待态断言未改。

验证（Developer 实际执行）：

```sh
cd web
npm run test -- run src/entities/operations/notification.test.ts \
  src/features/operations/notification-presentation.test.ts \
  src/features/operations/NotificationRouter.test.tsx \
  src/routes/router.test.tsx src/shared/ui/modal-card.test.tsx \
  src/shared/ui/AppShell.test.tsx src/shared/navigation/destination-model.test.ts
# 7 files, 183 tests passed

npm run typecheck && npm run lint && npm run format:check
# PASS

npm run build
# PASS；index-C9lHThdg.js / index-B0R4k6Jb.css；保留既有 chunk 体积提示

npm run test:e2e -- tests/e2e/notifications.spec.ts \
  tests/e2e/page-transition.spec.ts \
  --output=test-results/patch-20261114-3-developer-fix-r4
# 22 passed（通知 12、页面过渡 10），49.0 秒
```

新增／修改的定向回归覆盖：延迟真实新建成功响应期间标识符、地址、密钥引用、事件、启用
和数值字段均不可编辑且输入不变，成功后进入详情并显示提交地址，恰一次创建、无 PUT／测试；
新建 409 失败后字段解锁且原输入保留；延迟发布成功期间字段不可编辑，成功后详情显示提交值，
恰一次发布、无额外保存或测试；发布 409 失败后字段解锁、原值保留且不自动重放。普通保存
期间继续输入的既有用例保持通过。所有旅程均从既有按钮进入，未调用内部查询或构造旁路入口。

真实 Python 原生证明（新生产资产、真实 API、临时 SQLite／根、可记录假 Webhook
transport）：

```sh
.venv/bin/python scripts/notifications_workspace_browser_proof.py \
  --artifacts .git/validation-evidence/patch-20261114-3/developer-fix-r4/native
.venv/bin/ruff check scripts/notifications_workspace_browser_proof.py
.venv/bin/ruff format --check scripts/notifications_workspace_browser_proof.py
python3 scripts/check_governance.py
git diff --check
```

结果：PASS。Active 版本 1→2；显式签名测试恰 1 次 transport 请求；只读定义／投递读取未
改变 Active、未发送测试、未创建投递；`READ` 深链未改变打开的草稿修订／版本；第二写者
发布后浏览器保留本地输入；最终 Active 地址为浏览器保留值；Webhook 身份集合、无关配置
区段、Tasks／Jobs 行数未变；一条死信恢复为 pending。证据目录（未提交）：
`.git/validation-evidence/patch-20261114-3/developer-fix-r4/native/`，含 `evidence.json`
和六张桌面／390px 截图。`ruff`、治理检查与 `git diff --check` 均 PASS。

未运行／交 B：T4 全量 Python／Web／Node E2E、真实第二写者 409、真实权限 403 边界、
命令响应丢失核对、1440×700／390px 完整视觉与键盘矩阵、wheel／Docker 适用门禁。
原生证明继续使用同进程第二写者，未制造两个独立浏览器进程的并发；在途字段锁定由
Vitest 的延迟真实 `fetch` 响应和既有按钮旅程覆盖，B 仍应在真实浏览器保存／发布窗口内
输入确认字段不变。已知风险：本轮没有改变创建／发布协议或读回逻辑，若 B 在真实 API
发现并发读回与成功跳转交互问题，应按原 Task 边界复核，不视为本修正已覆盖。

本轮定向 Vitest、构建、Node E2E、原生证明与静态检查合计约 2 分钟；实现、差异审查与
证据核对占主要时间，测试时间低于本轮总时间 30%。

### B Review Result — FIX REQUIRED（2026-11-15，本轮）

B 独立审查完整范围：
`51480dc318837e4f1e4f9c60c17b8e708abb6409..48e9d2769abd96cbc06c37139cf67cb33c00b428`。
产品候选为 `4edb1526cc418ab5bbeb0ca96323f0584d0b5091`；其到交接 Head 仅改 TASK.md，
执行输入一致。分支 main，开始时工作区／暂存区干净、治理检查 PASS。本轮仅维护 TASK.md。

**尚余一个 P1 阻塞：未知的恢复结果被标题断言为没有应用。**

用户从通知 → 查看投递记录 → 死信筛选 → 查看投递，勾选确认并点击重新入队。
真实 Python API 已返回 200、SQLite 已把所选记录改为 pending，但该成功响应在返回浏览器时
丢失。卡片此时以红色标题“恢复没有应用”给出确定结论，正文却说明“命令结果未知：所选
投递可能已经恢复为待投递”。同一结果相互矛盾，用户无法直接判断应相信哪个结论；这不是
后端恢复失败。点击读取最新投递后能确认待投递，整个过程只发送一次恢复命令、没有自动重放。
本 Task 明确要求实际失败与未知不混淆，因此该可见结果仍不满足验收。

根因：`DeliveryDetailPage.tsx:511` 对所有 error 字符串固定使用“恢复没有应用”，包括
`isUnknownCommandResult` 分支。引入提交 `83a104eeef60300ab67f7c5df7a45d0f02a2b971`
（2026-11-14 12:52 +08）；本轮候选仍保留。可读证据在本机
`.git/validation-evidence/patch-20261114-3/b-round5/recovery-unknown.json`、
`recovery-unknown-390.png`、`recovery-unknown.log`。该证明从既有页面／按钮进入，
在真实恢复完成后只丢弃响应；没有伪造入口或恢复返回值。

**给 Developer 的修复指导与验收：**

1. 只协调恢复结果的标题、正文和呈现：未知结果明确显示“恢复结果未知”或等义结论，
   已确定拒绝仍明确显示没有应用及原因。沿用现有错误分支和读回入口，不改恢复协议。
2. 保留“可能已执行 → 读取持久状态核对”的下一步，保留显式确认、精确投递身份／fence，
   读回 pending 后不再提供死信恢复；不得为修正文案重新发送命令。
3. 在已有 unknown recovery 回归中断言用户实际可见标题与正文一致；保留 409 拒绝、
   已知成功后读取失败、一次命令和原死信筛选返回断言。无需新增通用证明平台。
4. Developer 跑 NotificationRouter 定向 Vitest、通知 Node E2E，以及受影响类型／lint／格式／
   构建检查后提交同一 Task。B 复核真实“已完成后丢响应 → 未知 → 读回待投递”旅程，
   并依工作流匹配最终候选的 T4 证据。原 ID／Base／范围／High／T4 不变。

**本轮已独立通过的交付：**

- 新建保存与发布真实请求在途时全部字段禁用，提交值不变，各恰一次命令，成功后进入正确
  定义；普通保存仍允许继续输入，迟到成功保留新值为未保存修改。双浏览器真实 409、
  第二写者发布、读取后明确保留／采用服务端值、退出继续编辑及再次保存均正常。
- 原生证明通过：Active 1→2，仅所选 Webhook 变化；READ 深链无可填写表单、无保存／测试；
  只读访问不写配置、不发测试；一次签名测试恰一次 transport、零新投递；所选死信恢复 pending。
- 真实已完成保存／发布／签名测试丢响应后提示未知，显式读回核对，不自动重放；发布后的
  精确地址经“读取最新定义”与 Active 核对。已知恢复成功后 GET 失败仍保留已知成功、标识
  旧读取，显式重试恢复为 pending；返回保持原死信筛选。
- 以 Base 新构建和候选新构建对照六页的 1440×1000、390×844、1440×700 实际截图，并对照
  自动化页面。字段／事件分组、可读 URL、状态和诊断层次较 Base 改善，卡片头尾操作区与
  内部滚动可用。真实创建 64 字符标识、360 字符地址、全部四事件后能查看和编辑，窄屏无
  页面横向溢出。键盘操作投递筛选／确认／恢复、Tab 限于卡片、Escape、继续编辑／明确放弃
  和 reduced-motion 通过。读取与状态分支同时由全量 Web／Node 回归覆盖。

**实际门禁与限制：**

证据根目录 `.git/validation-evidence/patch-20261114-3/b-round5/`（本机忽略产物，未提交）：

- `.venv/bin/python -m unittest discover -s tests`：2692 项，2684 通过、7 skipped、1 文档格式
  失败，306.599 秒；原日志 `python-full.log` 保留。失败是 B 规划中的测试分工使用粗体标题，
  未满足仓库文档消费者要求。B 本轮改成标准三级标题，未改测试或产品；随后
  `.venv/bin/python -m unittest discover -s tests -p test_release_security.py`：8 项通过
  （`python-task-doc-rerun.log`）。未将首次全量冒充全绿，产品执行输入未因该文档修正变化。
- `web/`：`npm run test -- run` 100 文件／1601 项通过；
  `npm run test:e2e -- --output=test-results/patch-20261114-3-b-round5-node` 274 项通过；
  typecheck、lint、format:check、build 均通过。新资产
  `index-C9lHThdg.js`／`index-B0R4k6Jb.css`；既有 chunk 体积提示保留。
- 原生脚本 `scripts/notifications_workspace_browser_proof.py --artifacts .../b-round5/native`
  通过；B 独立补充证明为 `create_pending.py`、`publish_pending.py`、`reproduce.py`、
  `remaining.py`、`recovery_unknown.py`、`long_visual.py`，结果／截图保留同目录。
  补充脚本首次运行的定位器严格匹配、PUT 拦截方法、已关闭草稿预期、显式读取及重试按钮
  定位问题已修正后通过，所有原失败日志保留；未修改产品以迁就脚本。
- ruff 格式（385 文件）、ruff check、compileall、pip check、两个示例 config validate、
  禁用依赖检索（无 FFmpeg／FFprobe，exit 1）通过；wheel 构建和源码外安装 smoke 通过。
  精确 wheel：`mediaflow-2.0.0.dev0-py3-none-any.whl`，SHA-256
  `0a7b00e78ed17a26d61fa03f0631b3b15c75b4d8a863ceae7f35e656ac2f238d`。
- Docker 广域矩阵不适用：未改容器／部署路径；未使用生产接收端、凭据或用户媒体。
  本轮按并行执行的实际经过时间计，测试低于审查总时间 50%。

结论为 FIX REQUIRED，仅上述恢复未知结果的确定性标题阻塞。没有后端重放或越权证据，
不新增功能／防御性机制或后续 Task。Slice54 保持 PASS / CLOSED，SLICE／Roadmap／Progress
未变，无推送、发布或部署。治理检查与 `git diff --check` 在本轮检查点前通过。

### Developer Completion Report — FIX ROUND 5（2026-11-15）

Status READY FOR B REVIEW。实现提交
`07624ec95b948f211bd93ed77596ebdea7e9992f`；本报告提交仅改 `TASK.md`。Task Base 保持
`51480dc318837e4f1e4f9c60c17b8e708abb6409`。本轮未改 Python 生产代码、恢复协议、API／
领域／持久化、公共 modal、SLICE／Roadmap／Progress，未推送、发布或部署。

修复：

- `DeliveryDetailPage` 的恢复错误状态改为同时保存文案与“是否未知”。传输丢失、5xx 和
  不可解析的 2xx 结果继续走既有 `isUnknownCommandResult` 分支，但标题显示
  “恢复结果未知”，使用 warning 呈现；正文保留“命令结果未知：所选投递可能已经恢复为
  待投递……请重新读取当前持久状态核对；系统不会自动重试或重复提交”。同一卡片不再同时
  出现“恢复没有应用”。
- 409 与其他确定拒绝继续显示“恢复没有应用”，正文保留“没有应用恢复”或
  “恢复动作没有执行（code）”的明确原因，并指引读取当前状态后再决定。
- 恢复协议、精确投递身份与观察到的状态／时间 fence、显式确认、至少一次提示、读回
  pending 后不再提供死信恢复以及原投递筛选返回均未改；没有新增自动读回、重发或后端字段。

回归（均从既有投递详情卡片和按钮进入）：

- 既有 unknown recovery 用例改为定位异常 banner 的二级标题，断言标题为“恢复结果未知”、
  同一 banner 正文包含“可能已经恢复为待投递”和“重新读取当前持久状态核对”，且同一
  banner 与页面都不含“恢复没有应用”；仍断言读取到的投递保持死信且恢复命令只发送一次。
- 既有 409 用例断言标题“恢复没有应用”和“因此没有应用恢复”正文，页面不出现
  “恢复结果未知”，仍断言恢复命令只发送一次。
- 既有已知成功后读取失败、恢复命令一次、原死信筛选返回断言保持不变并继续通过。

验证（Developer 实际执行）：

```sh
cd web
npm run test -- run src/features/operations/NotificationRouter.test.tsx
# 1 file, 43 tests passed，5.40s

npm run typecheck && npm run lint && npm run format:check
# PASS

npm run build
# PASS；index-xYA76ha9.js / index-B0R4k6Jb.css；保留既有 chunk 体积提示

npm run test:e2e -- tests/e2e/notifications.spec.ts \
  --output=test-results/patch-20261114-3-developer-fix-r5
# 12 passed，10.2s
```

```sh
python3 scripts/check_governance.py
# PASS
git diff --check
# 无输出
```

未运行／交 B：真实 Python API 下“恢复已应用但响应丢失 → 未知 → 读取最新投递确认
pending”的完整旅程、真实权限与并发门禁、T4 全量 Python／Web／Node E2E、wheel／Docker
适用门禁。本轮的 unknown Vitest 使用既有网络失败分支和固定死信详情，不冒充真实第二写者；
Node E2E 覆盖已知恢复成功与陈旧恢复拒绝，未覆盖未知恢复，B 仍应按原计划复核。

已知风险：未知结果的提示仍保留在卡片内，直到用户开始新的明确操作；读取最新投递确认
pending 后，状态和恢复入口按持久值更新，但标题不会自动改成“已恢复”。这不影响本轮要求的
“未知不冒充失败、确定拒绝明确没有应用”，B 应核对读回后的实际呈现。

本轮定向 Vitest、构建、Node E2E 与静态检查合计约 30 秒；实现、差异审查与证据核对占
主要时间，测试时间低于本轮总时间 30%。

## Latest accepted Task — PATCH-20261114-2

```text
Task Type: STANDALONE MINOR BUG
Parent Slice: NONE
Decision: B PASS — 2026-11-14
Task Base: 4107c299d8f99b817fcd3cbdffa274de1f5598ea
Implementation Head: 6a358085d1fc622c0257c545d83be41539d38620
Reviewed Handoff Head: a98403804f23a47d4bac771def3fc5f07234fcde
Acceptance checkpoint: 7ffe380669e50c46da15982a86e14e54228a38d8
```

两页排序状态与恢复入口收敛到工具栏显示设置，表头／排序／调宽反馈协调；原当前页
排序、精确选择、列宽边界和读取恢复保持。完整 Base..Head 审查、开发指导、验收旅程、
实际测试与原失败记录见
[固定 B 验收](https://github.com/kentinya/mediaflow/blob/7ffe380669e50c46da15982a86e14e54228a38d8/TASK.md#patch-20261114-2--b-pass)。
原规划／激活分别见 `d3d984a5:TASK.md`／`b1fa0905:TASK.md`，Developer 交接见
`a9840380:TASK.md`。

B 独立验证：受影响 Vitest 112 项、Node E2E 71 项、真实 Python 活列表 6 项，以及类型／
lint／格式／新构建、两页四视口前后对照、键盘、真实长名称、读取中间态／错误恢复、
reduced-motion 和重载默认状态通过。首轮 Node／Python E2E 共用输出目录造成一次 trace
归档失败，原日志保留；Node 使用独立目录完整重跑通过。详细命令、产物身份、提示、
未运行／不适用项及本轮测试时间分配见固定验收。

本机证据：`.git/validation-evidence/6a358085d1fc622c0257c545d83be41539d38620/patch-20261114-2-b/`。
依 [Development Workflow](docs/development-workflow.md) §3.1 保留本指针，详细历史留于 Git；
现行行为见 [文件浏览旅程](docs/product-experience.md#browse-feedback-selection-and-table-controls)。
Slice54 保持原 PASS / CLOSED，SLICE／Roadmap／Progress 未变；本次为开发验收，未发布或部署。

上一独立修复 PATCH-20261114-1 的接受身份与证据继续见
[固定 B 验收](https://github.com/kentinya/mediaflow/blob/280fc5fdedaf8c079dee52480e1eb4d3bf26449a/TASK.md#patch-20261114-1--b-pass)。
