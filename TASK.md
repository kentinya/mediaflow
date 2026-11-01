# NO ACTIVE IMPLEMENTATION TASK

用户本轮只要求“合入当前 Slice，并规划 Task”。以下 Task47.5 为 **PLANNED 草案**，
不授权实施、派生代理、push、部署或 Slice 关闭。后续明确授权开发时原地激活，并核对
中间变更；不静默重定 Task Base。用户已选择：“运行一次”和定时一样排除历史
failed / partial，保留一键执行，不新增初始确认。

Task47.4 已由 B 审查 PASS，原范围
`383d8834787674675183f4b251d9dfd26a5dc511..dd3f1c25126cd574d8df293d0163131bc6cb9ad6`；
完整审查/原五项结果 Closure Packet 保留于
`980ce42a977b5bc20cf8426dbaf5a232f46cf22b:TASK.md`。本次新增 RO-6 后 Slice47 继续
ACTIVE，先前的 SLICE READY FOR A REVIEW 不覆盖新结果；没有 A Final Review 或关闭。

# Task 47.5 — 自动排除历史失败、手动提醒后新整理与 CLI 失败重试退出

Authority: committed [SLICE.md](SLICE.md) 的 2026-11-02 修订、RO-6 / AC-20–25；
[Development Workflow](docs/development-workflow.md) 管生命周期、测试和收尾。
[Requirements](docs/requirements.md)、[V2 Requirements](docs/v2-requirements.md) 的
`V2-TASK-008–010` 管本次规则；保留 `V2-TASK-001–007`、`V2-OPS-014–017`、
`V2-AUTO-010/011`、UX-002/003/004/006、REQ-SCAN-006、REQ-RECOVERY-006/009、
REQ-RESULT-* 与 REQ-SAFE-* 中未被明确修订的身份、授权、历史及安全义务。

```text
Task ID: 47.5
Task Type: SLICE
Parent Slice: 47
Status: PLANNED
Task Base: 75ddff55f8d5b2b1206c81804bfb5cbe9ed279a1
Difficulty: High
Test Level: T4
Planner / Reviewer: B
Implementation authorization: NOT GIVEN — PLANNING DRAFT ONLY
```

## Preflight / workspace / role

- Repository `/Users/songzhidong/mediaflow`，branch `main`；本轮开始 HEAD
  `980ce42a977b5bc20cf8426dbaf5a232f46cf22b`，无预存 tracked 修改。预存未跟踪的 OS/log、
  `15`、参考图片及 `output/database-reference-2026-11-01/`、imagegen ZIP、
  `output/organize-flow-2026-11-01.html` 原样保留、未暂存。
- 同一 root agent 先履行 A 范围职责，提交 `75ddff55`，再履行 B 规划职责；公开此角色
  组合，但没有实施、自审 Task、A 终审或派生代理。提交后 governance PASS；工作区/Git 可写。
- Task Base 固定为已提交范围修订的完整 SHA。Slice 原 Base
  `5144ab1fc2344b06194969cc2c496835729664c0` 不变；Task47.4 接受事实不变。
- 不访问用户数据库、媒体或私密配置。用户“不考虑旧任务/跨版本升级、V1 不受支持”
  继续有效；fresh 新数据与同版本 reopen/restart 安全仍必须完成。

## Goal / complete journey

同一个失败或部分失败的来源文件：以后定时/运行一次不自动处理；用户在资源库 Files
明确选中整理时，可以看到上次失败/已知部分效果/未知效果的明显提醒，按原摘要确认
后执行一次新的正常整理。只用现有 Task 引擎、计划、冲突策略和确认，不再找独立 CLI
失败重试，不建立远端核验或附件恢复系统。

- **入口：** Files 直接文件、文件夹、混合选择；已发布定义 due/Run once；保留正常
  CLI organize/batch 与受限 remote organizing 的既有权限/来源边界。
- **可见状态：** 自动排除有逐项原因/计数；手动原准备/摘要中有服务端生成的历史提醒，
  包含上次结果、原来源/目标、完成步骤和未知效果。未知不是“系统已核验”。
- **动作：** 用户核对实际文件效果后，仍使用原“确认整理 N 项”选中确认；无需新的
  核查页、例行 checkbox、token 或技术恢复按钮。已有目录、目标和复制残留走正常策略。
- **成功：** 新 Task 使用新请求准入时当前 Active 的不可变 pin 和当前已核对来源；
  只记录自己的真实效果，原 Task/Result/pin/原 Automation 时间与结果不改写。
- **失败/恢复：** 已知仍排队/执行的工作继续阻止并发；仅历史 partial/unknown 标记
  不构成永久手动拒绝。源/计划/历史发生变化、拒权、队满、响应丢失等按现有精确
  读回/重新分析/确认处理；旧在途远端调用的实际终止不由用户确认或系统提示证明。

## Actual-code gap / affected seams

下列来自 Task Base 实际代码，是实现地图，不是要求逐文件拆 Task 或全面重构。

| 位置 | 当前缺口 / 本 Task 调整方向 |
|---|---|
| `domain/task_scheduling.py::TaskTrigger` / persisted display/admission context | 有 MANUAL/SCHEDULE/RUN_ONCE；origin 是服务端证据，不是浏览器可传的豁免。增加最小来源相关筛选语义，不能让 display 字符串授予执行权。 |
| `application/media_organizer.py::process_file/process_library`、`manual_task_engine.py`、`automation_definition_execution.py` | 共用引擎已存在，但没有统一“历史 failed/partial → 自动排除、手动提醒”的逐文件决定。目录 Task 建立时还没有完整文件清单，检查必须落到具体来源且先于该文件 Provider/执行。 |
| `sqlite_runtime.py::find_owned_source_work/_find_owned_source_work_locked`、`domain/task_persistence.py::SETTLED_ITEM_STATUSES` | 当前 FAILED 被当作已结束，PARTIAL 未被纳入；跨 Task 来源查询主要按状态，没有统一关联历史效果。不能只把 PARTIAL 加集合或只隐藏页面拒绝。 |
| `sqlite_runtime.py::list_results_for_source` / TaskItem、discovery source evidence | 现有来源结果查询是路径 + 最近有界结果，单独复用无法覆盖跨库真实路径/版本和较老的匹配失败。需在准确历史总体上筛选，再限制对用户显示的信息。 |
| `media_discovery.py::_refuse_owned_sources/_owned_source_work` / atomic source reservation | Files 直接/展开/准备发布都做占用核对；要共享新判断，手动 partial/unknown 的旧占用不能在后续 finalize/confirm 又被当作永久 veto。 |
| `manual_organize_execution.py`、`task_runtime.py`、`task_scheduling.py` / SQLite admission、mutation marker、file_locks | 同步处理新手动意图、已知活动所有者、历史不确定证据和精确逐文件锁交接。保留同 Task 的旧项非重放与四类安全继续，不重写旧 Result 或用 task-wide 解锁释放兄弟项。 |
| `manual_organize_preview.py`、`interfaces/service_api.py`、`web/src/entities/operations/preview.ts/organize.ts`、`OrganizePlanConfirmation.tsx` | 现有计划摘要/typed boundary 可复用；补服务端历史提醒及摘要一致性，Files 准备和确认前都可发现，不另建页面。 |
| `final_cli.py`、`task_runtime.py::execution_retry_items` 与引用方 | 删除 retry-failed parser/help、原 pin bootstrap 分支、专属受理/renderer/helper；共享源码先核对真实调用再删。保持正常 organize/analysis、Task cancel、四类 continue/ignore/audit。 |

## Implementation Scope

1. **确定一个共享逐来源历史判断。**
   - 复用现有 TaskItem/Result/checkpoint/discovery source evidence 与 repository port，按
     Storage ID + canonical Storage-relative path + 可比较来源版本找正式整理的
     `failed/partial` 历史。失败/部分失败指文件项，不是整个 Task aggregate；无 Result
     但有真实持久失败项的情况不能漏。exclude 当前新分析/尝试自身，不能自我拦截。
   - 使用同语义大小、修改时间、可用 Provider validator 等已有版本证据。跨库绑定不可
     直接比较 library-scoped digest；同名不同真实路径不混淆。真正替换的新版本不被
     永久路径黑名单拦住；缺失/不可比较版本按历史可能适用处理，不伪造“新文件”。
   - 匹配完整历史总体后再做有界展示。更近的成功或其他结果不能掩盖仍适用的较早失败；
     历史读取失败给出有界拒绝/重读，不能当作无历史。浏览、Rules 测试、独立仅分析、
     未准入来源拒绝及本次“历史排除”不制造新的正式失败历史。无全局目录/新队列。

2. **按后端来源接入准入与执行前复核。**

   | 来源 | 历史 failed/partial 的行为 |
   |---|---|
   | Scheduler interval/Cron/managed due | 同一版本逐项排除，包含零效果失败；不消耗该文件执行权，不查询其 Provider，不修改 Storage。 |
   | definition Run once | 用户已选择同定时排除；保持 disabled 可运行、原范围/上限、原一键执行及不推进 due。 |
   | Files 显式文件/文件夹/混合新整理 | 不因该历史排除；生成提醒并到达现有精确计划/选择确认。 |
   | 明确 CLI organize/batch | 保留手动显式意图；输出逐项历史提醒，默认只分析，--execute 才执行合法新计划。 |
   | 原 Task 四类继续 | 保持原 pin、决定→分析→摘要→明确确认；不是新的自动发现，不套“历史失败永不继续”。 |
   | 无逐文件选择的 remote discovery | 保留原 remote 权限/票据/范围契约；不能信任输入 origin/skipHistory 等字段取得 Files 人工接管豁免。历史 partial/unknown 不走未展示提醒的静默放行旁路。 |

   - Files 直选、目录展开、definition pipeline 在同一具体来源判断上收敛，不只在页面或
     Task 创建时检查。准入与确认使用事务内新鲜历史/占用检查；Storage I/O 不放事务里。
   - 现有完整遍历、min(itemLimit,100)、深度/页数预算、过滤、附件与真实稳定性不变。
     排除不能把未完整遍历变成“前 N 个可以执行”，也不能污染主文件/附件身份。
   - 自动排除保留来源/原因/数量和实际 Task 结果。全排除是“因历史失败无本次可执行项”，
     不伪称新整理成功、健康空目录、扫描错误或新增四类待办；自由兄弟项正常处理。

3. **打通手动提醒 → 真正新整理，不只做展示。**
   - 后端投影旧 Task/item/Result 的有界历史、原目标、已完成步骤、效果确定性，进入既有
     preparation/summary typed 数据。对适用历史显示如“该文件上次整理部分失败，目标
     可能已有文件，请核对后确认整理”；unknown 明确表示远端效果可能未确认。
   - 普通提醒不用 raw exception/secret；跨 principal 历史用于后端判断但遵守授权脱敏，
     不泄漏不可读任务身份/私有目标。页面显示或刷新只读，不自动搜索 Provider。
   - 提醒绑定当前 exact source/pin/plan/selected subset 和服务端历史依据，作为现有摘要
     一部分。确认时历史或计划更新就重读/分析并展示当前摘要，不执行未审阅的变化；
     不新增独立确认产品、例行 checkbox、客户端自报“安全”或 token 粘贴。
   - 已知活动工作保持互斥；纯历史 partial/unknown、旧已停止阶段遗留的 claim/marker 不得
     让新手动整理永久停在不可执行。必要的旧应用所有者收束/fence、逐来源/目标锁交接、
     容量结算和新确认在现有 kernel/repository 中完成，原子地保留兄弟项及旧未知证据。
     不以效果未知“变成 none”或删除原结果来放行；不只检查来源就遗漏旧目标/附件锁。
   - 新请求获得自己的当前 pin/计划/单次授权；旧项不重启、不补发旧步骤、不续发已消费
     权限。即使允许用户核对后新整理，也不能允许已失效应用 owner 再启动后续文件调用。
     既已发出的远端调用不能被数据库 fence 撤销；此限制明显提示，但本 Task 不实现自动
     结束探测、线程接管/远程取消。用户明确核对后的新请求是此处的窄范围授权调整。
   - 已建合法目录复用；目标与复制残留走现有 Skip/Rename/许可 Overwrite/Manual 和
     Hash/capability/cleanup 规则，不自动删残留或强制覆盖。主文件成功附件失败仍人工
     按现有指导处理；不生成附件专用重试。

4. **删除独立 CLI retry-failed，保持共享行为。**
   - 从 parser/help/dispatch、专属 snapshot bootstrap、_admit_cli_retry_task、专属输出与
     无其他消费者的 helper 中退出。普通 argparse 拒绝旧命令，零新 Task/请求登记/
     Provider/Storage/执行权消费；无 alias、隐藏分支或自动转换成 organize。
   - 核对并保留四类继续、ignore、cancel、只读 Task/result/export、正常 organize/batch
     和仅分析。source/wheel/container 的实际入口一致，更新当前 V2 管理文档与测试消费者。
     旧测试中用于 retry-failed 的效果保护改由真实新整理/旧项非重放断言覆盖，不能仅删测试。

5. **完成真实路径与可审查交接。**
   - 用临时 SQLite/LocalStorage 和 fake/local Provider 构造三类真实失败：目录成功后
     写入失败；目标父目录已存在时写入失败（failed + unknown）；COPY 已完成但 Move
     删源失败。通过 Files 当前 V2 API/Worker 实际重新整理到结果，保留旧证据。
   - 相同来源走 due/Run once 真实过滤，自由兄弟项实际完成；过页历史、版本变化、并发
     手动重复确认、已知活动所有者、reopen/restart、拒权/队满/响应丢失都覆盖。
   - 只提交本 Task 必要改动，READY FOR B REVIEW，附实际受影响测试及限制；不开发后续
     Task、不关闭 Slice。B 完整验收后重新评估六项 RO/AC-1–25，再交 A。

## Acceptance Criteria

- [ ] **AC-T1 / Slice AC-20：** due 和 Run once 对同版本 failed/partial 独立排除；零效果
  失败也排除，自由兄弟项真实完成，完整范围/稳定性与排除记录/计数一致，全排除不假成功。
- [ ] **AC-T2 / AC-21：** Files 直选、目录及混合选择都允许历史失败项进入新整理；真实
  部分目录、复制残留、failed+unknown/partial+unknown 均先显示清楚提醒，再经原摘要
  选中确认执行正常计划。没有额外核查页/例行 checkbox，也不只做到“可以打开摘要”。
- [ ] **AC-T3 / AC-22：** 真实 canonical Storage/path/版本匹配不受最近32/100条历史截断；
  覆盖跨库绑定、同名异路径、新版本、未知版本、混合 Task、无 Result 持久失败和非整理
  仅分析。读取失败不放行；新 Task 自己的分析失败不伪装成先前外部历史。
- [ ] **AC-T4 / AC-23：** 有效活动所有者仍阻止并发；手动旧历史接管/确认、锁和容量
  原子核对，旧 app owner 后续写/调用拒绝，兄弟项不被解锁。旧未知证据仍未知，且既有
  标记不会使已确认新手动工作永久无法执行。没有把 Web 确认说成远端已停止证明。
- [ ] **AC-T5：** 新整理用新 pin，原 Task/item/Result/原 pin/原 Automation 结果和时间
  不变；正常 Conflict/Hash/覆盖/清理、C→A identity、附件、RBAC/脱敏及四类同 Task
  继续不退化。旧项/成功兄弟不被这次新请求作为恢复范围自动重放。
- [ ] **AC-T6 / AC-24：** source/help/installed wheel/image 无 retry-failed 或替代别名；
  旧命令在解析处拒绝且零效果；正常 CLI 分析/execute 和其他 Task 管理/四类继续保留。
  remote 不能伪造 origin 取得未展示提示的 manual 例外。
- [ ] **AC-T7 / AC-25：** 真实 V2 浏览器桌面/窄屏，使用生产 build + real API/SQLite/
  Worker，证明提示→选中确认→实际效果、定时/运行一次排除、原历史不改写；重连/过期
  摘要/队满/拒权的状态与可操作下一步真实。B 完成适用 T4/原生/安装/容器/重启门禁。

## Required Tests

依 [workflow §6](docs/development-workflow.md#6-test-levels)。以下命令为实施后的计划，
**本轮没有运行这些产品测试或声称通过**。新模块名是本 Task 的预期测试文件。

### Developer — affected tests

根目录：

```bash
.venv/bin/python -m unittest tests.test_organize_source_history tests.test_organize_preparation tests.test_manual_task_engine tests.test_manual_organize_execution tests.test_task_scheduling tests.test_task_scheduling_fencing tests.test_task_retry tests.test_automation_entrance_recovery
.venv/bin/ruff check <本Task新增或修改的Python文件>
.venv/bin/ruff format --check <本Task新增或修改的Python文件>
.venv/bin/python scripts/check_governance.py
git diff --check
```

`tests/test_organize_source_history.py` 为本 Task 新的临时 DB/Storage 成功、无效输入、
冲突、故障及边界测试；其余是直接受影响的真实准入、手动执行、claim/fence、CLI 与
自动入口。复制/删除实际故障从 Executor/Storage 注入，不能全用手填状态或假前端。
明确验证未知状态原来存在的跨新 Task 放行缺口，不因删除 CLI 而失去安全证据。

`web/`：

```bash
npm run test -- run src/entities/operations/organize.test.ts src/entities/operations/preview.test.ts src/features/operations/OrganizePlanConfirmation.test.tsx
npm run typecheck
npm run build
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/organize-source-history.python.spec.ts
```

新增 `OrganizePlanConfirmation.test.tsx` 与 `organize-source-history.python.spec.ts`，
使用现有生产摘要和真实 Python harness，覆盖提示对正确来源可见、unknown 文案、无
额外 chore、选择确认绑定/拒绝重读、真实文件效果及自动排除。补足实际受影响的 unit/
原生测试，不把全部 Web/Python/E2E 交给 Developer。若只复用旧测试模块，交接说明
等价覆盖位置并保留相同有意义断言，不要求为命名再造一套 harness。

### B — acceptance and full regression

- 独立审查整个 Task Base..candidate；实际复现 AC-T1–7，重点对比 due/Run once 与
  Files 对同一来源的不同结果、旧 partial/unknown app-owner 的交接和历史完整性。
- 执行 [shared full gates](docs/development-workflow.md#shared-full-regression-commands)
  的适用 T4 Python/Web/full E2E/static/examples/wheel/installed/Docker/security 门禁，
  不复用改动前的 T4 PASS 代替本 Task 新执行输入。对未变输入的证据复用按 workflow。
- 在生产 build 上执行以下原生旅程（`web/`，每组独立产物目录/顺序运行，避免 harness
  与报告互相覆盖）：

  ```bash
  npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/organize-source-history.python.spec.ts
  npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/automation-lifecycle.python.spec.ts tests/e2e/automation-run-once.python.spec.ts
  npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-task-center-visual.python.spec.ts
  ```

- 人工检查实际桌面与窄屏截图/交互：失败项提醒明显、长路径有界、可见旧目标/未知效果，
  普通确认可达，不新增 Failure Recovery、核查页或 Routine checkbox；读/刷新零效果。
- clean wheel/source-external CLI 验证 retry-failed 普通参数拒绝与正常 organize；隔离
  Docker 验证 fresh、同版本 Worker/Scheduler restart、源历史排除/手动新整理、权限、
  原结果/未知证据及旧 owner fencing。只用临时媒体与 fake/local Provider；不读用户库。
- 无旧任务、跨版本升级或 V1 产品门禁；不要求真实远程复制终止/取消能力或完整外部
  endurance 环境。既有外部环境 skip 和任何 unavailable 门禁如实记录；不放宽断言。
- PASS 后对扩大后的整个 Slice RO-1–6/AC-1–25 重评并提交新的 Closure Packet，旧
  Task47.4 packet 是基线而非新增行为的接受证明；不得代 A 终审或关闭。

## Non-goals

远程操作完成探测/操作 ID 查询/取消、SMB 线程管理重构、Storage/Provider 新能力、
“系统核验安全后解锁”新产品；附件专用恢复、自动删残留、历史步骤恢复/全局 reprocess、
跨 Task 批量恢复/通用回滚；额外历史清理/全局 FileIndex/并行引擎；把所有历史状态都
扩成自动排除、改变 Run once 初次一键意图；旧 Task/跨版本升级/V1 支持；更改权限、
源边界、稳定性/完整遍历或静默覆盖/删除；恢复 Pause/resume/retry-request/Job。

## Developer Completion Report

待明确实施授权并完成后填写：完整 checkpoint、READY FOR B REVIEW、实际受影响测试、
剩余问题/限制。当前仅 PLANNED 草案，无实施、产品测试或已交付声明。

## B Review Result

尚未提交实施候选，未审查、未验收。范围规划不是 Task PASS，也不是 Slice Final Review。
