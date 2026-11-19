# Slice 56 — V2 正式入口与 API 去版本前缀

```text
Slice ID: 56
Name: Canonical Web and API Routes
Owner: A — Slice Owner / Architect / Final Reviewer
Status: PLANNED
Base SHA: 33c70735e0a8f45426dde614587ea3d43af94e9b
Implementation Head: NOT SET
Working Branch: main
Development Authorization: PLANNING ONLY
Risk: High
Target Test Level: T4
Next Action: USER ACTIVATES SLICE / B THEN PLANS THE FIRST TASK
```

## 授权与基线

用户以文件页 `/resourcelib/files` 和 `/api/v1/tasks → /api/tasks` 为例，先授权调查，
随后要求规划 Slice。本合同将两个示例应用到全部当前 Web 和 API 路由。本轮交付规划文档
及本地检查点。激活、Task 规划、实施及发布依照仓库工作流。[Development Workflow](docs/development-workflow.md)

规划前治理检查通过。仓库位于 main，HEAD 为上述 Base，暂存区及工作区干净，文档和 Git 可写。
Base 是产品实施前的基线，规划／激活检查点沿用该 Base。介入的产品变更由 A 审核范围和集成。
Slice 55 仍为 PASS / CLOSED，原 Base、实施 Head、最终审查及验证限制可查阅
[固定终审](https://github.com/kentinya/mediaflow/blob/f1a0b10e29ec6fdbdad67fd97345065113f45626/SLICE.md#a-final-review--pass--closed)
与 [Progress](docs/progress.md)。

## 目标与调查基线

用户从服务根地址进入，连接后进入探索，也可用 `/resourcelib/files` 打开文件页。
打开带资源库和目录参数的文件链接、重连或刷新后，用户看到原目录及适用的操作。
切换前已有的任务可通过新地址继续查看，恢复时核对原请求及可执行范围。外部客户端可用
`GET /api/tasks` 查询任务，也可通过新地址调用现有详情、取消和逐项恢复接口。

部署的匿名 GET 验证了旧文件页及构建的 JS/CSS 返回 200，新文件页返回 404，旧任务 API
返回 401、新任务 API 返回 404。本机开发端口连接被拒绝。用 Base 源码、临时 SQLite 和测试
身份验证了 `/api/v1/tasks`、`/api/v1/operations/tasks` 返回 200，`/api/tasks`、
`/api/v2/tasks` 返回 404。静态入口和 API 安全测试共通过 24 项。这些是规划基线，
候选产物须依下方标准验收。

Slice 55 的 `V2-RETIRE-001/006/008/009/010` 和 `V2-MIG-001/002` 定义当前基线。
本 Slice 通过 [V2-ROUTE-001–004](docs/v2-requirements.md#target--canonical-web-and-api-routes-slice56-planned)
调整 V2 的公开路径，涵盖 `REQ-WEB-001/003/004/005`、`REQ-API-001–003` 的传输入口。
旅程与服务分界见 [Product Experience](docs/product-experience.md#target--canonical-entry-journey-slice56-planned)
和 [Architecture](docs/architecture.md#target--root-web-and-unversioned-api-slice56-planned)。

## Required Outcomes and Surfaces

### RO-1 — Web 从根路径提供当前全部旅程

- `/` 作为现有连接入口，连接后进入 `/explore`。保留现有九个主页面和相关深链的后缀，
  包括 `/resourcelib/files`、`/medialib/files`、`/operations?run=<Task>&dialog=organize`、
  `/rules/edit/<family>/<id>`、自动化 lifecycle、通知及设置。首页、菜单、后端跳转指引、
  静态资源、前端校验与浏览器地址使用同一正式路径。
- 直达、导航、刷新和重认证沿用当前查询语义及权限边界。可恢复原资源库／媒体库、目录、
  有效分页和弹窗来源。规则 Edit 的合法带点 ID 仍可直达，缺失静态资源按普通 404 处理。
- 由 Python 同源提供构建产物，应用现有安全头和方法限制，构建产物缺失时返回普通错误。
  `/health`、API 和静态资源分别分派。API 按路径段识别并统一返回 JSON 错误，
  SPA 回退限于 Web 导航。

### RO-2 — 当前 API 统一使用 `/api/*`

- 全部当前 API 移除路径中的 `v1` 段。端点后缀、方法、请求结构、响应投影、错误和分页遵循
  当前契约，响应内用于继续操作的路径值随正式地址更新。`/api/tasks`、
  `/api/operations/tasks` 和 `/api/operations/runs` 各自沿用其职责及字段投影。
  请求和响应字段名、配置键、权限名及业务数据版本沿用当前契约。
- 分发、认证、RBAC、Active 检查、错误分类、安全审计与只读审计例外覆盖新路径。新审计
  使用新路由模板，仍按现行规则隐藏受保护的标识和秘密。Web 客户端和后端生成的设置指引、
  checkpoint、取消、恢复、配置发布、包交换、自动化及通知操作链接均使用正式地址。
- 规划采用直接切换。退役的 `/ui-v2`、子路由及资源遵循普通未知路由结果，允许现有认证
  边界下的通用 not-found。`/api/v1`、`/api/v2` 及其子路由返回普通 JSON 404。
  旧前缀的请求在未知路由处理结束，业务变更为零。Slice 55 已退役的业务入口在新前缀下同样拒绝。

### RO-3 — 切换前的有效工作可以继续

- 用户继续使用 Base 建立的有效配置、Draft／Active、任务、请求、结果和审计。保留 ID、
  原快照 digest／pins、任务状态、证据和效果。用既有对象身份生成新的可操作链接，历史审计
  原样呈现当时的路由。已有配置和运行库可以原地打开，验收使用隔离实例建立及重开可复核的副本。
- 用户在新地址核对受支持的原请求，包括已提交但响应丢失的场景。回读仍基于原请求身份和权限，
  由用户显式触发合法继续。读取、换地址或重启均不得重复受理或重放已完成／不确定的效果。
  原 Task 内四类恢复、普通文件页内进度和结果、失败与可采取的下一步保持可用。

### RO-4 — 源码、产物和随仓消费者一起切换

- Vite 开发代理、测试假服务及匹配表达式、Playwright、部署 smoke、CI、样例命令和运维
  指引都随正式路径切换。候选镜像中的 Python 与 Web 资源来自同一候选，验证构建的资源、
  wheel／源码外安装及生产 Compose 入口。记录仓库内受影响的调用方，提供维护方可以执行的
  外部脚本换址指引。外部接入范围目前未确认，现场接入方核对与切换属于部署授权。
- 当前 README、部署指引、要求、旅程与架构按验收结果更新。冻结的 V1 基线、Git 历史、
  历史审计、历史关闭与旧路径负向测试保留其原始含义。

## 交付边界

工作限于当前 V2 的 HTTP 路径和随仓消费者。沿用现有应用服务、前端页面、任务引擎、
配置格式、数据结构和部署拓扑。发布版本号、标签、容器发布、实机部署及第三方接入方改造
另行授权。稳定 V2 继续使用从本 Slice Base 验证，历史版本的通用迁移在范围外。
原认证、RBAC、同源安全、Storage 约束、读取零业务变更、精确确认、原子发布、作用域和
审计、Worker claim／fence、独立结果与不确定效果保护均为验收义务。

## Acceptance Criteria

- [ ] AC-01 / RO-1 验证真实构建与浏览器中的根入口、九个主页面及关键深链，包含两种库、
  设置、Task card、Rules Edit、自动化与通知。两种库验证带参数直达、刷新／重连及原来源返回。
  带点合法规则 ID 和直接加载的生产静态资源可用。未知资源、非法资源路径、API 及健康检查
  得到对应分派，按现行规则保留安全头和静态读取隔离。
- [ ] AC-02 / RO-2 用认证客户端覆盖新路径下的公共 API 路由族，重点核对任务三种投影、
  认证 401、权限 403、查询校验、分页及只读审计。验证实际返回的操作链接能在原权限下
  到达对应动作，新的审计模板分类正确且保持脱敏。旧 API 用有效身份仍返回 JSON 404，
  包含有写语义的方法且无业务效果。旧 Web 实际呈现未知路由或其通用认证边界。
  核对旧入口没有重定向目标、旧页面和旧资源均不可达，已退役业务能力仍拒绝。
- [ ] AC-03 / RO-3 由 Base 真实代码在隔离库创建合法配置、任务、请求、结果及审计。
  验证候选重开该库并重启后，读回原数据、生成对应操作链接，在权限范围内取消任务和执行
  逐项恢复。四类恢复均验证新入口及原权限。模拟既有请求响应丢失，从新地址只读核对原请求，
  验证无重复 Task、无重复已完成／未知效果，且历史审计原值可读。同时用空实例验证首次设置
  及合法业务操作。
- [ ] AC-04 / RO-4 确认随仓开发、假服务、发布验证和当前指引均使用正式地址，
  扫描普通字符串和路径匹配表达式。全量 Python/Web 回归、真实浏览器、源码外安装、
  候选 Docker 的空实例／发布安全／重启证明达到 T4。以真实产物验证 API、页面、静态资源
  和 `/health` 的一致性，冷启动与重开使用隔离配置和数据。所需结果由 B 写入 Closure Packet，
  由 A 按工作流核对。

## Closure Packet and A Final Review

待候选实现、B 验收与 A 终审。
