# Task PATCH-20261114-3 — 通知页可读性、统一卡片与操作状态修复

Next Action: Developer 按本 Task 开始实施，完成受影响测试后提交 READY FOR B REVIEW。

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
Status: PLANNED
Task Base: 51480dc318837e4f1e4f9c60c17b8e708abb6409
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

尚未实施。后续按工作流提交连贯 checkpoint，记录 READY FOR B REVIEW、实际改动、
受影响测试及已知风险；全量与独立接受仍由 B 负责。

### B Review Result

尚未评审。B 在候选提交后记录固定 Base..Head、实际接受结果和
PASS／FIX REQUIRED；修正在本 Task 内。PASS 后恢复 NO ACTIVE IMPLEMENTATION TASK
及简短接受指针，不改变 Slice54 或大 Slice 关闭台账。

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
