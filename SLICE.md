# Slice 58 — 通用 CLI 彻底退役

```text
Slice ID: 58
Name: Complete Retirement of the General CLI
Owner: A — Slice Owner / Architect / Final Reviewer
Status: PLANNED
Base SHA: 5b2e0de4ac1c9d79e3618cef82d420ae302401e7
Implementation Head: NOT SET
Working Branch: main
Development Authorization: PLANNING ONLY
Risk: High
Target Test Level: T4
Next Action: USER ACTIVATES SLICE / B THEN PLANS THE FIRST TASK
```

## 授权与基线

用户授权 A 规划通用 CLI 的彻底退役，无兼容。部署与恢复只保留四组能力：四个服务的启动、
首次管理员设置、忘记密码、停机数据库备份恢复。备份范围限 MediaFlow 的 SQLite 数据库。
用户确认当前库内没有已受理的 CLI 任务，CLI 专属任务续作随入口退出。
本合同处于规划状态，激活、Task 规划和验收按工作流进行。[Development Workflow](docs/development-workflow.md)

规划前 `main` 位于上述 Base，治理检查通过，工作区和暂存区干净，仓库文档和 Git 可写。
Slice 57 已关闭，固定终审保留原范围、证据及限制。
[Slice 57 A Final Review](https://github.com/kentinya/mediaflow/blob/f3b52c7ff188c502ef711fbc354ca40d90d5ac9e/SLICE.md#a-final-review--pass--closed)

## 用户目标与适用要求

部署者用正式制品启动实例，用主机权限办理首次设置和忘记密码，在停机维护时备份或恢复
数据库。管理员从根地址进入 Web 完成日常工作，集成继续使用现有 `/api/*` 和分权限令牌。
切换后可在任务中心查看受支持库内由现行 Web、API 或自动化受理的任务，并继续适用的操作。

Base 的 Compose 四服务经容器预检后执行 `mediaflow`。`final_cli.py` 同时承载服务装配和
旧命令分派，Web 的文件发现、整理分析和文件传输也依赖这些 Worker 装配。此次切换按调用
路径提取四服务和现行业务使用的装配及共享逻辑，删除旧命令及其专属执行路径。
[容器入口](mediaflow/container_entrypoint.py) · [当前 Worker 和 API 装配](mediaflow/final_cli.py)

合同验收后，更新 `V2-RETIRE-002/009`、`V2-FILES-005`、`V2-TASK-005/014` 等现行
要求的 CLI 实现，以及 Direct configuration publication 的 schema 11 切换例外。
`V2-AUTH-004/005/007–009`、`V2-DEPLOY-001/002`、`V2-ROUTE-001/002/004`、
`REQ-CONFIG-004/008`、`REQ-API-002` 和现行安全要求继续约束保留的能力。按本合同的
受支持数据库范围落实 `V2-RETIRE-005`。冻结 V1 及已验收 Slice 的历史事实保留原义。
[Requirements](docs/requirements.md) · [V2 Requirements](docs/v2-requirements.md) ·
[Product Experience](docs/product-experience.md) · [Architecture](docs/architecture.md)

## Required Outcomes and Surfaces

### RO-1 — 四个服务从独立于通用 CLI 的入口启动

- 正式 Compose 和源码外安装能按各自固定职责启动 API、Worker、Scheduler 和
  Notification Worker。保留单镜像四服务、非 root 用户、最小 bootstrap、持久卷和可选媒体
  挂载。启动入口直接装配各服务并复用适用的配置和存储预检、数据库租约、心跳与退出处理。
- 部署者从 Compose 状态、`/health` 和现有就绪入口区分进程在线、等待管理员、等待 Active 和
  可处理工作。启动失败指出所属阶段、受影响服务及可执行的下一步。修复配置、挂载或权限
  后按新入口启动相应服务，已受理工作的原上下文继续有效。
- 保留服务启动所需的部署配置生成、环境装配和健康探针。启动选择限四个服务职责，删除旧
  命令分派、任意可执行文件转发及 `MEDIAFLOW_COMMAND` 覆盖。`run-next`、`tick` 等原一次性
  业务调度命令退出。

### RO-2 — 首次设置和忘记密码保留主机授权

- 空实例的 Web 根页给出与正式制品一致的主机侧指引。部署者用主机权限对指定实例领取短期
  一次性设置码，在 Web 创建唯一管理员，再进入系统设置初始化业务配置。失效时可重新
  领取，提交回包丢失时可在原页核对设置状态，并根据状态继续设置或登录。
- 忘记密码时，未登录页面给出新主机入口的指引。部署者为同一实例的管理员领取重置码，
  用户在 Web 重置并重新登录。失效或提交结果未确认时，保留现有找回路径和状态核对。
- 两种签发复用现有实例、用途和账户约束、有效期、事务消费、审计及会话撤销。码明文只在
  授权的主机调用中一次性显示，日志和审计脱敏。公开 HTTP 保留现有消费与状态接口，
  签发权限留在主机侧。日常登录、改密、退出和令牌权限沿用现行契约。

### RO-3 — 停机备份、校验和非覆盖恢复

- 部署者停止四个服务，在相同部署环境中通过专用主机入口生成并校验 SQLite 快照。成功
  输出备份位置、schema 与摘要。目标已存在、备份无效或写入失败时，说明操作结果和
  可安全执行的下一步，保留原库和已有备份。
- 恢复使用现行适用性规则可启动的同版本备份。校验区分文件完整性与目标版本能否使用。
  恢复前确认四服务已停止，保留源备份和原数据库，通过独占租约、显式确认和临时文件
  校验后发布到不存在的数据库目标，目标旁路文件也必须不存在。失败时保护原文件。
- 恢复后先单独启动 API，核对已恢复的账号、Active、任务、结果与审计。启用后台前，部署者
  核对备份时点之后的实际文件效果与仍待处理的任务。无法确认时保持相关后台执行停用。
  恢复本身零媒体操作，备份与恢复只覆盖 SQLite 持久状态。

### RO-4 — 旧 CLI 和 schema 11 切换完全退出

- 删除 `mediaflow` console script、`mediaflow.cli`、`mediaflow.final_cli`、旧解析器和专属
  命令实现。旧拼写、别名、帮助、转发层、导入兼容和开关一并退出。主机一次性入口只支持
  设置码签发、重置码签发、数据库备份、校验和恢复。具体调用方式由实现按本合同交付。
- 旧业务命令整体退出，包括配置校验与发布、分析、直接及全资源库批量整理、任务命令与
  单项／批量忽略、Storage 检查与文件列表、通知运维、日志与安全审计，以及手动日志清理。
  删除 CLI 专属的任务受理、执行和续作分支，包括 `direct-organize`。Web、现有 API 和
  自动化沿用当前业务旅程、共享 Task 内核及权限。
- 配置 schema 11 全面退出启动、采用和恢复范围。删除 `config retire-unpublished` 及专属
  切换机制。正式启动、探针和主机操作在写入前拒绝此类库，保留原文件，并指向用原版本
  处理旧库或用新数据目录初始化。支持空库和符合当前适用性规则的库，
  Base 的当前格式为配置 schema 12、运行库 schema 60。
- 源码、wheel、镜像、Compose、README、部署和发布指引、CI、冒烟及浏览器测试脚手架统一
  切到新入口。样例配置继续通过现行校验行为验证。仍有效的安全及业务断言转接到保留的
  正式链路。历史验收、测试退役断言和 Git 记录可引用旧命令。

## 架构、安全与交付边界

- 服务启动、主机发码及离线数据库操作复用现有运行时、账号、预检和持久化逻辑。启动层
  负责装配，业务裁决继续由共享应用服务承担。生产 API 继续服务 Web 根地址和
  `/api/*`，既有认证、RBAC 和脚本令牌权限继续生效。媒体修改沿用 OrganizerExecutor、
  显式授权、作用域限制和执行 fence。
- 当前受支持的 Base 库原样重开。保留已发布配置、账号、令牌、Task、Item、请求、结果和
  审计的身份、关系、原摘要和固定快照。合法 Web、API 和自动化工作保持适用的同 Task
  安全续作，已完成或效果不确定的操作禁止自动重放。
  CLI 退役本身无需改写正式记录或提高当前 schema。
- 本 Slice 的范围限于入口切换及其专属实现、数据适用性和交付清理。媒体备份、旧库迁移和
  跨版本恢复、Web 备份管理与新认证机制不在范围内。

## Acceptance Criteria

- [ ] **AC-01 / RO-1。** 用候选镜像及正式 Compose 从无媒体挂载、空库启动四服务，
  核对进程和就绪状态、系统设置初始化与重启。用隔离媒体挂载核对 Web 文件夹准备到
  同任务的精确确认、普通文件传输、Automation 到期与 Run once、Webhook 投递。
  验证失败预检和恢复，分析阶段零媒体变更，Worker/Scheduler 在原授权边界内工作。
- [ ] **AC-02 / RO-2。** 使用正式镜像的新主机入口和生产浏览器页面完成首次设置及未登录
  找回，核对过期、错用途、重复／并发消费、丢回包后的状态核对、会话撤销及脱敏。
  同时验证现有 Web 登录与 API 令牌权限，HTTP 无签发权限。
- [ ] **AC-03 / RO-3。** 在有管理员、Active、任务及审计的隔离实例，停机备份、校验、恢复，
  先从 API／Web 核对备份时点的记录，再按指引启动后台。核对损坏及不适用的备份、
  无确认、租约被占用、目标已有文件或旁路文件、发布冲突的保护行为。比较媒体根、
  源备份与应保留的原文件，核对零媒体效果和非覆盖。
- [ ] **AC-04 / RO-4。** 检查源码和构建清单，验证源码外安装和候选镜像中旧二进制、
  可导入旧模块和旧分派全部消失。用正规配置尝试旧调用及任意分派，确认零新任务、
  配置发布、Provider 调用和媒体效果。用临时 schema 11 测试库验证启动、发码及恢复路径
  在写入前拒绝，失败提示对应正确去向，原文件摘要保持一致。
- [ ] **AC-05 / RO-4。** 用 Base 的现行 Web/API 和自动化在隔离的当前格式库建立合法任务，
  覆盖已有完成结果和仍可安全续作的工作。候选重新打开同一库，通过正式 Web/Worker
  核对原任务、审计、结果、来源和 pin，并在明确选择后续作合法条目。核对原 ID、配置摘要、
  逐项效果与已完成／不确定项零重放，以及管理员和脚本令牌的原权限。

## Final validation and closure

本 Slice 采用 T4。B 按工作流提交精确候选的全量、安全、原生浏览器、wheel 和真实 Compose
结果，在 CI、样例校验与冒烟迁移到正式入口后完成门禁。A 核对完整 Base..Implementation Head
和独立验收证据，关闭时同步现行要求、旅程、架构和交付指引。
[测试等级与验收分工](docs/development-workflow.md#6-test-levels)
