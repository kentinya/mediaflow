# Task PATCH-20261114-3 — 通知页可读性、统一卡片与操作状态修复

Next Action: B 复核修正候选 `93996b68`，按原 T4 验收计划完成剩余并发、权限、视觉与全量门禁。

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
Implementation Head: 93996b687e4b39cba612141b6dfc804aecac0292
Evidence Head: 93996b687e4b39cba612141b6dfc804aecac0292
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

**Developer — new / changed / directly affected**

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

**B — independent acceptance / full regression**

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

### B Review Result — FIX REQUIRED（2026-11-14）

固定审查范围：`51480dc318837e4f1e4f9c60c17b8e708abb6409`..
`fd4856d1193ff9b8a76e5a4835a5eccc7ae8a7de`，共 18 个变更文件；产品实现
`83a104eeef60300ab67f7c5df7a45d0f02a2b971`，原生证明脚本在证据提交
`9329b1205cb3339fed7d73f3ec07f9f563793e02`。
已核对 `9329b120..fd4856d1` 仅改本文件，执行输入相同。分支 `main`，审查起始工作区／
暂存区干净，治理检查 PASS，工作区与 Git 可写。本次仅更新本 Task，不改产品实现。

**交付核对。** 六页已接入两张列表背景和统一卡片，中文状态、分组表单及较宽输入控件
已交付。B 独立从现有通知入口完成真实 Python API／临时 SQLite 旅程：只读浏览无配置写入
或测试发送；显式测试恰好发送一次；保存、检查、发布使 Active 版本 1→2，只改变所选
Webhook 地址；一条死信恢复为 pending，返回仍保留死信筛选，Tasks／Jobs 数量不变。
独立查看桌面卡片、390px 编辑和恢复后截图，确认标题、输入和固定底栏的呈现改善。
这些结果不代替下面两项未完成的恢复／效果要求，也不表示完整视觉矩阵或 T4 已通过。

**阻塞 1：版本冲突后，用户没有保留输入并重新读取的入口。**

真实操作：管理员甲乙分别从通知列表打开同一 Webhook 草稿；甲输入地址 A，乙输入
地址 B 并保存；甲点击“保存到草稿”，收到真实 HTTP 409。甲仍看到 A，但页面只说
“重新读取草稿后再提交”，卡片没有重新读取／刷新按钮，也没有“采用服务端值／保留
本地输入”的选择。甲再次保存仍收到 409；关闭卡片需要放弃输入。正常编辑旅程无法继续。

原因定位：`NotificationEditorPage.tsx` 保存失败分支（约第 285–297 行）只设置提示，
正常已加载卡片没有读取入口；现有 refetch 按钮仅出现在读取错误状态。查询不随窗口焦点
刷新，背景列表在卡片打开时不可操作；背景列表刷新也不读取该草稿。远端选择逻辑存在，
但用户无法通过这条失败旅程触发它。现有 `NotificationRouter.test.tsx` 的远端更新用例
直接调用 queryClient 失效查询，绕过了缺失的用户动作，不能证明此旅程可完成。
Base 原编辑页有常规 RefreshControl，本次卡片改造移除了正常读取入口。
本项阻塞 Implementation Scope 5 及并发／可修正输入验收。

**阻塞 2：死信恢复后，接收效果被显示成“尚未收到”。**

真实操作：用户从投递记录筛选死信，打开已有 HTTP 400 响应的一条记录，确认并点击
“重新入队死信投递”。命令成功后同一记录变为 pending，主内容的“已知接收效果”却说
“接收端尚未收到本投递”。此前的 HTTP 400 已证明发生过一次请求／响应；重新入队只说明
会再安排尝试，不能证明接收端从未收到或未处理。用户据此判断是否可能重复发送会被误导。

原因定位：新增 `notification-presentation.ts` 第 344–351 行只按 pending 状态生成
“尚未收到”的断言；`DeliveryDetailPage.tsx` 第 341 行把它作为主结论。恢复后尝试计数
重置为 0 也不能证明没有历史请求。Base 主内容显示服务端影响说明，本次新增中文映射
强化成了没有证据支持的结论。本项阻塞投递结果／已知效果准确性验收；不要求改变后端
恢复协议或新增历史 schema。

### Developer Guidance — 本 Task 内修正

1. **恢复可操作的读取旅程。** 在卡片中提供可见、键盘可达的现有对象读取动作，连接
   对应查询；优先修好上述编辑 409 旅程，并检查此次同样移除常规读取入口的定义、新建和
   投递详情，确保现有“重新读取”提示均有对应操作。读取本身不提交任何命令。
   甲的本地输入与旧基线须保留；读到乙的新版本后，复用已实现的明确选择，采用服务端值
   或保留本地输入，再由用户保存。不要用关闭重开／硬刷新丢输入来完成恢复。
2. **纠正接收效果表述。** pending 说明等待下一次尝试；不据此断言接收端从未收到。
   复用现有读回及命令结果表达已知事实和可能重复发送，保证主内容与恢复结果一致。
   同一处状态映射里的死信原因也应按现有真实失败原因说明，不能把所有死信说成次数用尽
   （现有 HTTP 4xx 可直接进入死信）。此处只改呈现，不改投递计数、Worker 或恢复协议。
3. **按实际用户动作补回归。** 编辑用例从甲本地修改、乙保存、甲 409 开始，通过卡片
   读取按钮走完两种选择；保留本地输入后保存成功并核对新版本与提交值，采用服务端值
   则核对表单与旧证据失效。不要再用测试内部 queryClient 调用代替用户读取入口。
   投递用例从真实 HTTP 400 死信确认恢复到 pending，核对主结论不再声称从未收到；
   恢复仅一次、原身份及返回筛选保持。先跑这些失败场景、新改和直接受影响测试；
   B 接手完整 T4，不把全量回归交给 Developer。

修正后仍需由 B 核对原四个交互问题、完整失败／未知／权限及视觉矩阵，并运行适用全量
门禁后才可 PASS。ID／Base／目标／非目标／Difficulty／T4 均保持；Slice54 为已关闭参考，
不是父 Slice，SLICE／Roadmap／Progress 原接受事实保持。

### B Actual Validation

以下均为 B 本轮实际执行，测试使用新生产资产和隔离数据；没有生产接收端或用户媒体：

```sh
# cwd web
npm run build
# PASS；index-TDkfNVo5.js / index-CT0fyh28.css；保留构建的 chunk 大小提示

# cwd repository
.venv/bin/python scripts/notifications_workspace_browser_proof.py --artifacts .git/validation-evidence/patch-20261114-3/b-native
# PASS：只读／一次测试／精确草稿发布／单条恢复／返回筛选旅程

.venv/bin/python .git/validation-evidence/patch-20261114-3/b-review/reproduce.py
# 复现完成：真实第二写者导致甲连续两次 409；卡片读取按钮 0、远端选择 0，输入 A 保留；
# 同一 HTTP 400 死信恢复后 pending，仍显示“接收端尚未收到”；显式测试请求 0。
```

证据保留于 `.git/validation-evidence/patch-20261114-3/b-native/` 和 `b-review/`，
后者含独立复现代码、JSON、冲突与恢复后截图。复现复用已交付脚本的临时 API 装配，
两个浏览器窗口分别通过 Connect、通知列表、查看定义、编辑草稿操作；未调用猜测入口、
未从浏览器注入查询状态、未修改生产代码。此脚本的“复现完成”表示问题被观察到，不是
产品验收通过。

本轮未运行全量 Python／Web／Node E2E、wheel／源码外安装、真实权限／丢响应矩阵及
1440×700／完整键盘／动效矩阵；按流程 §6 已证明阻塞后提前 FIX REQUIRED，剩余验收
保留给修正候选，不视为 Developer 缺少全量报告。Docker 广域发布矩阵因本 Task 未改
容器／部署路径不适用。构建和两项浏览执行合计少于 1 分钟，独立代码／文档审查与结果
核对超过 10 分钟，测试时间低于本轮总时间 50%；未通过重复测试填充时间。
`python3 scripts/check_governance.py`、`git diff --check` 均 PASS；本地 B 检查点仅含本文件。

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
