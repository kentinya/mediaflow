# NO ACTIVE IMPLEMENTATION TASK

Task47.5 B Review: **PASS**。Next action: **SLICE READY FOR A REVIEW**；交 A 独立终审，未关闭 Slice。

# Task47.5 — PASS

B 独立审查完整 `75ddff55f8d5b2b1206c81804bfb5cbe9ed279a1..3cf1b6b4b59dbea0bbd2159c404e760f7bcd9417`，
原容量、旧批次收尾、提醒及自动历史准入并发问题均已通过。无剩余 P0/P1。
Slice47 的六项结果已重评完成，**SLICE READY FOR A REVIEW**，不再规划开发 Task。
A 的整个 Slice 终审及正式关闭尚待进行；B 没有关闭 Slice 或修改 A-owned 指针。
此前审查/返工详细记录留在 Git：`bb6c08aa:TASK.md`、`3cf1b6b4:TASK.md`；
Task47.4 的接受事实及原五项结果 packet 留在 `980ce42a:TASK.md`。下文保留本 Task 范围与验收。

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
Status: PASS
Task Base: 75ddff55f8d5b2b1206c81804bfb5cbe9ed279a1
Difficulty: High
Test Level: T4
Planner / Reviewer: B
Implementation authorization: USER-AUTHORIZED — IMPLEMENTED, B REVIEW PASS
```

## Planning preflight / workspace / role

- Repository `/Users/songzhidong/mediaflow`，branch `main`；原规划轮起始 HEAD
  `980ce42a977b5bc20cf8426dbaf5a232f46cf22b`，无预存 tracked 修改。预存未跟踪的 OS/log、
  `15`、参考图片及 `output/database-reference-2026-11-01/`、imagegen ZIP、
  `output/organize-flow-2026-11-01.html` 原样保留、未暂存。
- 同一 root agent 先履行 A 范围职责，提交 `75ddff55`，再履行 B 规划职责；公开此角色
  组合，但没有实施、自审 Task、A 终审或派生代理。提交后 governance PASS；工作区/Git 可写。
- Task Base 固定为已提交范围修订的完整 SHA。Slice 原 Base
  `5144ab1fc2344b06194969cc2c496835729664c0` 不变；Task47.4 接受事实不变。
- 本次 A 已先提交收窄范围的 `547570b778259a8b7d78c98fc0434acaa008e7cc`，governance
  PASS；B 据此修正同一个 Task 草案，保留 Task ID/Goal/Base 和 PLANNED 状态，无实施。
- 不访问用户数据库、媒体或私密配置。用户“不考虑旧任务/跨版本升级、V1 不受支持”
  继续有效；fresh 新数据与同版本 reopen/restart 安全仍必须完成。

## Goal / complete journey

同一来源版本最近一次正式整理结果为失败或部分失败：定时/运行一次不自动处理；
后来手动整理成功，就不再因更早失败排除，仍接受普通过滤/冲突规则。用户在资源库 Files
明确选中整理时，可以看到上次失败/已知部分效果/未知效果的明显提醒，按原摘要确认
后执行一次新的正常整理。只用现有 Task 引擎、计划、冲突策略和确认，不再找独立 CLI
失败重试，不建立远端核验或附件恢复系统。

- **入口：** Files 直接文件、文件夹、混合选择；已发布定义 due/Run once；保留正常
  CLI organize/batch 与受限 remote organizing 的既有权限/来源边界。
- **可见状态：** 自动排除有逐项原因/计数；手动原准备/摘要中有服务端生成的历史提醒，
  显示适用结果及可用的来源/目标/完成步骤/未知效果，复用现有摘要而非强制增加完整
  历史面板。普通提醒用简短人话；可用目标和已知影响放在现有条目详情，内部步骤代码、
  claim/lock/token 不成为必读内容或用户操作。未知不是“系统已核验”。
- **动作：** 用户核对实际文件效果后，仍使用原“确认整理 N 项”选中确认；无需新的
  核查页、例行 checkbox、token 或技术恢复按钮。已有目录、目标和复制残留走正常策略。
- **成功：** 新 Task 使用新请求准入时当前 Active 的不可变 pin 和当前已核对来源；
  只记录自己的效果；旧已记录结果、完成步骤、pin、未知证据和原 Automation 结果/时间
  不改写。必要的锁/claim/fence 与当前处理状态允许调整，不要求原 Task/item 所有字段不变。
- **失败/恢复：** 文件项尚在排队/处理且没有自己的终态结果时保留互斥。已记录 failed/
  partial 的文件项按历史处理，不能仅因父 Task 仍 running 或旧 unknown marker 再判为
  活动项；不要求用户或本 Task 证明远端已停止。有关来源/本次计划影响的实质变化、拒权、
  队满、响应丢失按既有精确读回/分析/确认处理，无关历史追加不增加确认步骤。

## Actual-code gap / affected seams

下列来自 Task Base 实际代码，是实现地图，不是要求逐文件拆 Task 或全面重构。

| 位置 | 当前缺口 / 本 Task 调整方向 |
|---|---|
| `domain/task_scheduling.py::TaskTrigger` / persisted display/admission context | 有 MANUAL/SCHEDULE/RUN_ONCE；origin 是服务端证据，不是浏览器可传的豁免。增加最小来源相关筛选语义，不能让 display 字符串授予执行权。 |
| `application/media_organizer.py::process_file/process_library`、`manual_task_engine.py`、`automation_definition_execution.py` | 共用引擎已存在，但没有统一“历史 failed/partial → 自动排除、手动提醒”的逐文件决定。目录 Task 建立时还没有完整文件清单，检查必须落到具体来源且先于该文件 Provider/执行。 |
| `sqlite_runtime.py::find_owned_source_work/_find_owned_source_work_locked`、`domain/task_persistence.py::SETTLED_ITEM_STATUSES` | 当前 FAILED 被当作已结束，PARTIAL 未被纳入；跨 Task 来源查询主要按状态，没有统一关联历史效果。不能只把 PARTIAL 加集合或只隐藏页面拒绝。 |
| `sqlite_runtime.py::list_results_for_source` / TaskItem、discovery source evidence | 现有查询是路径 + 最近有界结果，单独复用不能保证找到跨库真实路径/版本的最近正式结果。先在完整匹配总体确定最近一次，再限制显示；不是永久寻找任意一次失败。 |
| `media_discovery.py::_refuse_owned_sources/_owned_source_work` / atomic source reservation | Files 直接/展开/准备发布都做占用核对；要共享新判断，手动 partial/unknown 的旧占用不能在后续 finalize/confirm 又被当作永久 veto。 |
| `manual_organize_execution.py`、`task_runtime.py`、`task_scheduling.py` / SQLite admission、mutation marker、file_locks | 同步处理新手动意图、已知活动所有者、历史不确定证据和精确逐文件锁交接。保留同 Task 的旧项非重放与四类安全继续，不重写旧 Result 或用 task-wide 解锁释放兄弟项。 |
| `manual_organize_preview.py`、`interfaces/service_api.py`、`web/src/entities/operations/preview.ts/organize.ts`、`OrganizePlanConfirmation.tsx` | 现有计划摘要/typed boundary 可复用；补服务端历史提醒及摘要一致性，Files 准备和确认前都可发现，不另建页面。 |
| `final_cli.py`、`task_runtime.py::execution_retry_items` 与引用方 | 删除 retry-failed parser/help、原 pin bootstrap 分支、专属受理/renderer/helper；共享源码先核对真实调用再删。保持正常 organize/analysis、Task cancel、四类 continue/ignore/audit。 |

## Implementation Scope

1. **确定一个共享逐来源历史判断。**
   - 复用现有 TaskItem/Result/checkpoint/discovery source evidence 与 repository port，按
     Storage ID + canonical Storage-relative path + 可比较来源版本找最近一次正式整理
     结果；仅结果为 `failed/partial` 时触发本次排除/提醒。不是整个 Task aggregate；无 Result
     但有真实持久失败项的情况不能漏。exclude 当前新分析/尝试自身，不能自我拦截。
   - 使用同语义大小、修改时间、可用 Provider validator 等已有版本证据。跨库绑定不可
     直接比较 library-scoped digest；同名不同真实路径不混淆。真正替换的新版本不被
     永久路径黑名单拦住；缺失/不可比较版本按历史可能适用处理，不伪造“新文件”。
   - 在完整匹配总体里确定最近一次正式整理结果，再做有界展示。后来手动成功后，不再
     因更早失败排除；旧失败记录保留。以持久 attempt/admission 顺序及关系识别新工作，
     较早操作迟到的发布不能仅凭入库时间成为“最近一次”。历史读取失败给出有界拒绝/
     重读，不能当作无历史。浏览、Rules 测试、独立仅分析、未准入拒绝与本次历史排除
     不制造或覆盖正式整理结果。无全局目录/新队列。

2. **按后端来源接入准入与执行前复核。**

   | 来源 | 最近正式结果为 failed/partial 时的行为 |
   |---|---|
   | Scheduler interval/Cron/managed due | 同一版本逐项排除，包含零效果失败；不消耗该文件执行权，不查询其 Provider，不修改 Storage。 |
   | definition Run once | 用户已选择同定时排除；保持 disabled 可运行、原范围/上限、原一键执行及不推进 due。 |
   | Files 显式文件/文件夹/混合新整理 | 不因该历史排除；生成提醒并到达现有精确计划/选择确认。 |
   | 普通 CLI organize/batch | 保留既有来源/授权与默认分析、显式 --execute 语义；共享准入调整按原来源接入，不新增 CLI 历史提醒或交互要求。 |
   | 原 Task 四类继续 | 保持原 pin、决定→分析→摘要→明确确认；不是新的自动发现，不套“历史失败永不继续”。 |
   | 普通 remote organizing | 保留既有来源/权限/票据/范围契约及后端来源校验；不因本 Task 新增 remote 类别、提醒、同意参数或未展示 Web 提醒就拒绝的额外规则。 |

   - Files 直选、目录展开、definition pipeline 在同一具体来源判断上收敛，不只在页面或
     Task 创建时检查。准入与确认使用事务内新鲜历史/占用检查；Storage I/O 不放事务里。
   - 现有完整遍历、min(itemLimit,100)、深度/页数预算、过滤、附件与真实稳定性不变。
     排除不能把未完整遍历变成“前 N 个可以执行”，也不能污染主文件/附件身份。
   - 自动排除保留来源/原因/数量和实际 Task 结果。全排除是“因历史失败无本次可执行项”，
     不伪称新整理成功、健康空目录、扫描错误或新增四类待办；自由兄弟项正常处理。

3. **打通手动提醒 → 真正新整理，不只做展示。**
   - 后端投影适用的最近正式结果与可用目标/步骤/效果证据，进入既有 preparation/summary
     typed 数据，无须新建完整历史面板。显示如“该文件上次整理部分失败，目标
     可能已有文件，请核对后确认整理”；unknown 明确表示远端效果可能未确认。
   - 普通提醒不用 raw exception/secret；跨 principal 历史用于后端判断但遵守授权脱敏，
     不泄漏不可读任务身份/私有目标。页面显示或刷新只读，不自动搜索 Provider。
   - 提醒绑定当前 exact source/pin/plan/selected subset 和服务端历史依据，作为现有摘要
     一部分。涉及所选来源或本次文件影响的实质变化沿用既有摘要新鲜度规则；无关历史
     追加不令确认失效，不增加例行重分析/重确认。不执行未审阅的实质变化；
     不新增独立确认产品、例行 checkbox、客户端自报“安全”或 token 粘贴。
   - 以具体文件项而非父 Task 的汇总状态判断：未形成该文件终态结果的 queued/processing
     工作保留正常互斥；已有 failed/partial 结果的项按历史处理。父 Task 仍 running、
     历史 unknown/claim/marker 单独存在，均不得重新把它算成活动项并永久阻止新手动整理。
     这里不要求证明旧远端操作已停止。必要的旧应用所有者收束/fence、逐来源/目标锁交接、
     容量结算和新确认在现有 kernel/repository 中完成，原子地保留兄弟项及旧未知证据。
     不以效果未知“变成 none”或删除原结果来放行；不只检查来源就遗漏旧目标/附件锁。
     旧锁/claim/fence/当前处理状态允许按此目的调整，已记录结果与原运行事实保持不变。
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
     文档、历史说明和拒绝旧命令的 negative test 可以保留 retry-failed 字面量，验收检查
     活跃入口/执行能力退出，不要求全仓字符串零命中。原效果保护由真实新整理/旧项非重放
     断言覆盖，不能仅删测试；普通 CLI/remote 不新增本次未约定的产品规则。

5. **完成真实路径与可审查交接。**
   - 用临时 SQLite/LocalStorage 和 fake/local Provider 构造三类真实失败：目录成功后
     写入失败；目标父目录已存在时写入失败（failed + unknown）；COPY 已完成但 Move
     删源失败。通过 Files 当前 V2 API/Worker 实际重新整理到结果，保留旧证据。
   - 相同来源走 due/Run once 真实过滤，再经手动成功证明旧失败不再导致排除，自由兄弟项
     实际完成；过页历史、版本变化、并发手动重复确认、尚无终态的活动文件项、
     reopen/restart、拒权/队满/响应丢失都覆盖。
   - 只提交本 Task 必要改动，READY FOR B REVIEW，附实际受影响测试及限制；不开发后续
     Task、不关闭 Slice。B 完整验收后重新评估六项 RO/AC-1–25，再交 A。

## Acceptance Criteria

- [x] **AC-T1 / Slice AC-20：** due 和 Run once 对同版本 failed/partial 独立排除；零效果
  失败也排除；依据最近正式结果，后来手动成功解除早期失败造成的排除。自由兄弟项真实
  完成，完整范围/稳定性与排除记录/计数一致，全排除不假成功。
- [x] **AC-T2 / AC-21：** Files 直选、目录及混合选择都允许历史失败项进入新整理；真实
  部分目录、复制残留、failed+unknown/partial+unknown 均先显示清楚提醒，再经原摘要
  选中确认执行正常计划。没有额外核查页/例行 checkbox，也不只做到“可以打开摘要”。
- [x] **AC-T3 / AC-22：** 真实 canonical Storage/path/版本匹配不受最近32/100条历史截断；
  覆盖跨库绑定、同名异路径、新版本、未知版本、混合 Task、无 Result 持久失败、非整理
  仅分析和 failed→manual success。旧尝试迟到发布不能替代较新的正式尝试结果。
  读取失败不放行；新 Task 自己的分析失败不伪装成先前外部历史。
- [x] **AC-T4 / AC-23：** 尚无文件终态结果的排队/处理项保留互斥；已有 failed/partial
  结果的文件不因父 Task running/历史未知标记而被重新判为活动项。不要求远端停止证明。
  手动旧历史接管/确认、锁和容量原子核对，失效 app owner 后续状态写入及新步骤准入
  拒绝，不承诺停止已派发调用。兄弟项不被解锁。旧未知证据仍未知，且既有
  标记不会使已确认新手动工作永久无法执行。没有把 Web 确认说成远端已停止证明。
- [x] **AC-T5：** 新整理用新 pin，原已记录结果、完成步骤、Result/pin、未知证据和原
  Automation 结果/时间不改写；允许必要的锁/claim/fence/当前处理状态调整，不要求旧
  Task/item 每个字段不变。正常 Conflict/Hash/覆盖/清理、C→A identity、附件、RBAC/脱敏
  及四类同 Task 继续不退化。旧项/成功兄弟不被这次新请求作为恢复范围自动重放。
- [x] **AC-T6 / AC-24：** source/help/installed wheel/image 无活跃 retry-failed 或替代入口；
  旧命令在解析处拒绝且零效果；正常 CLI 分析/execute 和其他 Task 管理/四类继续保留。
  文档与 negative-test 字面量允许保留；普通 CLI/remote 原有来源/授权语义不变，
  不新增 CLI 历史提醒、remote 类别或未展示 Web 提醒的额外拒绝规则。
- [x] **AC-T7 / AC-25：** 真实 V2 浏览器桌面/窄屏，使用生产 build + real API/SQLite/
  Worker，证明提示→选中确认→实际效果、定时/运行一次排除、原历史不改写；重连/过期
  摘要/队满/拒权的状态与可操作下一步真实。B 完成适用 T4/原生/安装/容器/重启门禁。

## Required Tests

依 [workflow §6](docs/development-workflow.md#6-test-levels)。以下保留原实施/验收计划；实际执行、输入复用与结果见末尾 B Review Result。

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
分别验证入口规则：定时/运行一次按同一来源版本最近正式结果排除 failed/partial；
手动入口对包含未知效果的 failed/partial 文件，先展示 Web 提醒，再经正常选中确认
允许新整理，不能沿用“未知效果一律拒绝所有新 Task”的旧断言。原失败/未知效果记录
保留，旧文件项不自动重放；删除 CLI 不得丢掉这些区别的测试覆盖。

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
  必须包含同版本 failed→手动成功→定时/Run once 不再因早期失败排除的真实链路。
- 执行 [shared full gates](docs/development-workflow.md#shared-full-regression-commands)
  的适用 T4 Python/Web/full E2E/static/examples/wheel/installed/Docker/security 门禁，
  不复用改动前的 T4 PASS 代替本 Task 新执行输入。对未变输入的证据复用按 workflow。
- 在生产 build 上执行以下原生旅程（`web/`，每组独立产物目录/顺序运行，避免 harness
  与报告互相覆盖）：

  ```bash
  npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/organize-source-history.python.spec.ts
  npm run test:e2e -- --config=playwright.python.automation.config.ts tests/e2e/automation-lifecycle.python.spec.ts tests/e2e/automation-run-once.python.spec.ts
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

## Developer guidance — 本轮已交付的修复边界

以下指导已由实现 `2332105ac46127ba572ada4b02f3e09f4b24e6d3` 完成，保留用于审查与维护，
不授权额外开发。

1. 自动历史检查放在真实最终逐文件准入 `begin_scheduled_item_with_ownership`：同一
   SQLite 写事务核对 claim、活动来源占用、最新适用正式结果并写本项。不能在服务先读
   历史、稍后单独取得来源。事务内不调用 Provider/Storage。
2. 最新 failed/partial 直接持久化 `history_excluded`；读失败持久化
   `history_unavailable`，不按无历史放行。两者没有 Provider/媒体效果/正式 Result。
   活动占用优先；成功历史或可证明替换的新版本按普通规则处理。
3. 只有 due/Run once 带自动排除标志。手动、普通 CLI/remote、同 Task 四类继续保留
   既有入口规则。容量按 Task 的机器工作计算；文件所有权另行核对，不能混为一个名额。
4. 并发复现的暂停点在最终准入事务之前：自动已开始，手动通过真实 Files 分析/摘要/
   确认后实际写入失败，再恢复自动。旧只读查询现已在事务内，不能阻塞它再等待另一
   写请求完成，并把测试自身的等待误判成产品故障。反向顺序验证自动已取得来源时
   手动被拒绝；兄弟项、历史、四类继续和容量结算必须保留。

## B Review Result — PASS

```text
Task: 47.5
Decision: PASS
Task Base: 75ddff55f8d5b2b1206c81804bfb5cbe9ed279a1
Reviewed Head: 3cf1b6b4b59dbea0bbd2159c404e760f7bcd9417
Latest executable checkpoint: 2332105ac46127ba572ada4b02f3e09f4b24e6d3
Branch: main
Blocking findings: NONE
Next action: SLICE READY FOR A REVIEW
```

独立核对完整 Base..Head 的 36 文件，结合前序 B 全范围审查逐项复核现存结果，并重新
审查本次 9 文件增量及实际调用者。`2332105a..3cf1b6b4` 仅为交接报告。B 本轮仅改
`TASK.md`；所有原有未跟踪 OS/log/图片/参考产物原样保留且未暂存。无产品或测试改写、
派生代理、push、用户服务部署、用户数据库/媒体/私密配置访问。

### 用户旅程与阻塞处置

- **自动先检查但尚未取得 A：** 手动可先进入。独立原始复现已改用真实准入前暂停点：
  Files 选 A → 分析 → 摘要 → 确认 → 实际 Storage.write 故障产生 PARTIAL/未知效果；
  自动恢复后持久化排除，零 Provider、零 Result、零目标文件。新回归还证明自由兄弟
  Two 正常 COPY，旧手动结果不变。历史读取故障同样不执行文件。
- **自动已取得 A 并开始处理：** 实际暂停在 Provider 调用，Files 再选 A 返回 409
  `source_already_organizing`，未新建第二个 Task；自动随后只执行一次并释放容量。
  自动因历史排除 A 不取得其执行权，后续手动仍可看到提醒、正常确认并新整理。
- **批量容量与旧批次收尾：** 10 成功、8 成功 2 零效果失败、8 成功 1 部分成功/未知
  1 失败，运行时各占 1、全部结束各占 0。旧批次 A 失败、B 仍真实写入时，手动新整理
  A 成功；B 的占用/边界保持，B 成功后原批次诚实为部分成功并占 0，旧 A 结果未改写。
- **单文件与四类人工决定：** 单文件失败/部分成功可经新手动摘要和确认完成；已有目录
  写失败及 COPY 后删除源失败的残留均经过真实 MOVE 旅程，后者走正常冲突 Rename。
  Recognition、Metadata、Classification、Conflict 的决定→分析→摘要→明确继续在原
  Task 完成。全部等待人工时机器名额为 0，但待决定/正在处理的文件仍保留来源互斥。
- **提醒与实际效果：** 桌面及 390px 窄屏展示失败文件、旧目标/未知效果和原确认按钮；
  未新增核查页或必选知晓框。浏览器确认后真实 MOVE，旧未知记录仍未知。
  定时/Run once 按最新适用结果排除，后来手动成功解除早期失败排除；不是永久路径黑名单。

### B 实际验收与证据

本轮本地 ignored 证据根：
`.git/validation-evidence/3cf1b6b4b59dbea0bbd2159c404e760f7bcd9417/b-review/`。
日志、命令、截图、artifact/source proof 与耗时保留于此，不宣称远程可访问。

| 验证 | 实际结果及证据 |
|---|---|
| 完整 Python | **2530 tests OK，7 skipped，285.921s**；`python-full.log`。包括新并发事务、来源版本/完整历史、队满/claim/fence、C→A identity、权限及不确定效果保护。 |
| 关键真实旅程 | 19 项专项通过；独立 `admission_history_race.py`、`automatic-owner-probe.py`、容量/活跃兄弟/残留探针均通过，对应 `*-race.log`、`automatic-owner.log`、`capacity.log`、`live-sibling.log`、`residual.log`。 |
| 原生浏览器 | 源历史 1、Automation lifecycle/Run once 17、Task Center 八视图/摘要 2；另窄屏 1、桌面截图 1，全部通过。使用生产 build、真实 API/SQLite/Worker 和临时 Storage。`native-e2e.log`、`automation-native.log`、`task-center-correct.log`、`narrow.log`、`desktop.log`。 |
| 人工视觉 | 实看 `desktop-summary.png`、`narrow-summary.png`、`narrow-confirm.png`：提醒可见、长路径换行、确认可达，无横向溢出或新增例行操作。窄屏仅按实际菜单/更多资源库入口调整证据副本，保留原断言。 |
| Python 质量/示例 | governance、Ruff format/check、compileall、pip check、两份公开示例 validate、完整范围 whitespace 通过；生产代码/pyproject 无 FFmpeg/FFprobe。`quality.log/json`。 |
| Web 全量复用 | 复用 B 对 `3fb10500` 的 **88 files / 1267 unit passed、253 fake E2E passed**，及 typecheck/lint/format/build。`web-reuse-diff.txt` 证明 Web 源码/测试/锁文件/配置、浏览器 harness、pyproject 均未变；依赖未重装、原 build 未替换。Python 执行输入已变化的 native、安装/容器与完整 Python 均在本候选重跑。旧原始日志在上一候选同名 `b-review/`。 |
| clean installed wheel | 从 `git archive 3cf1b6b4` 干净上下文重建；169 个 Python 模块与当前源码逐字节一致，无多余/缺失模块。wheel smoke、源码目录外安装后 6 项真实执行/四类继续/单文件交接通过；旧 retry-failed 在解析处 exit 2，help 不含该入口，正常 organize 保留。`wheel-clean-build.log`、`wheel-clean-smoke.log`、`installed-clean.log`、`artifact-source-proof.json`。 |
| Docker fresh/security | **PASS**，53.4s，实际四服务、手动整理、RBAC/non-root/秘密扫描；`docker-security.log`。脚本从 committed context 构建。 |
| Docker 同版本 restart/fault | **PASS**，102.2s，实际调度/COPY、各服务重启、幂等、旧 owner 拒写、原记录/不确定效果不重放；`docker-restart.log`。最终 image `sha256:d6f8d4fcd8ae47fd692bfb85d3880b8f9fe41f9ebc8f24dd7795dbac45193e08`。 |
| image CLI 退出 | 直接调用 image 内已安装 CLI，retry-failed exit 2，help 无入口，普通 organize help 正常；`image-retired-cli.log`。正式容器启动预检另由安全门禁覆盖。 |

clean wheel SHA-256：`e4b200a9dc15bef6d54ac99b9bc3dc1d7f3c24cd00218e090fe8e81ce54652f6`。
7 项 skip 是未配置专用 SMB/S3/OpenList/耐久环境；这些适配器未改，没有调用真实用户端点。
旧任务/跨版本升级及 V1 产品功能依用户明确边界不纳入，不声称已验证。

**证据设置问题已由 B 处理，不作为 Developer 返工：** 首次 Task Center 命令误用了不存在
的 spec 文件名，保留 `task-center-native.log`，改用实际现有 spec 后 2 项通过。首次本地
wheel 混入预存 `build/lib` 的退役模块，保留 `wheel-worktree-cache-contaminated/`；最终只
接受上述干净 committed archive 的 wheel，重新完成 smoke/installed。上一轮全 fake 与
native spec 默认路由配置问题仍有原始日志，分别使用对应配置覆盖，不删断言/加重试。

测试耗时按并行区间合并：全部本轮日志区间 302.8s，
另为人工图评和短检查预留 30s，总测试上界 332.8s；记录时保守总用时
685.7s，占比上界 48.5%，小于 50%。开始时间还晚于初始合同/代码核对，
未以空等补时，其他时间用于完整范围复核、构建污染处置、结果重评与交接；见 `timing.json`。

## Entire Slice reassessment / Closure Packet for A

```text
Slice: 47 — Unified Task scheduling and organizing execution
Slice Base: 5144ab1fc2344b06194969cc2c496835729664c0
Implementation Head: 3cf1b6b4b59dbea0bbd2159c404e760f7bcd9417
Required Outcomes and Surfaces: COMPLETE under explicit user amendments
Tasks completed: 47.1–47.4 accepted baseline; 47.5 PASS
Blocking findings: NONE
Decision: SLICE READY FOR A REVIEW — no next implementation Task
```

| 全部结果/验收 | 重评 |
|---|---|
| RO-1 / AC-1–3 | 完成：唯一 Task、各入口共享单 Task 容量、机器工作与人工等待区分、原子准入/领取、控制与安全释放。新真实混合批次补足结束占 0 及活跃兄弟占 1。 |
| RO-2 / AC-4–6 | 完成：Files/due/Run once/正常 CLI/remote 共用引擎；保留初始意图、精确确认、过滤/附件/完整遍历/稳定性及上限。本轮不恢复退役 retry-failed。 |
| RO-3 / AC-7–8 | 完成：四类在同 Task 决定/分析/摘要/确认、合法 pin、独立兄弟结果、已完成/不确定旧尝试不重放；实际 installed、完整回归与容器重启保留证据。 |
| RO-4 / AC-9–12 | 完成适用范围：Task47.4 的 Job 退出/fresh/同版本持久性接受事实保留，当前全量及干净 wheel/image/restart 复核无退化。旧任务/跨版本迁移按用户排除，不作已通过声明。 |
| RO-5 / AC-13–19 | 完成：八视图/Attention、Files/Automation 原记录/设置、Dashboard、通知/日志/导出/API/CLI/健康及 Pause 退出沿用接受基线，并由当前 full/native/release 复核。AC-18 的 A 独立整 Slice 终审仍待进行，B 不代签关闭。 |
| RO-6 / AC-20–25 | 完成：最新同版本历史、自动原子排除/自由兄弟/无工作真相、手动可见提醒与新效果、历史不改写、来源互斥/接管、CLI 退役及真实桌面/窄屏/installed/container 证明。 |

**Documentation Reconciliation Needed：** A 终审通过后协调 SLICE 的 Implementation Head/
最终状态、Roadmap/Progress 仍显示 PLANNED 的陈旧 Task 指针，以及 requirements/
Product Experience/Architecture 的 CURRENT/TARGET。原 Task47.4 packet 的已退役 CLI
描述由本 Task 的明确修订取代，不改写旧接受历史。B 不修改这些 A-owned 关闭文档。

**Known non-blocking issues / explicitly deferred：** 上述可选真实远端/耐久环境未运行；
默认 E2E 配置路由和旧安装恢复脚本引用的证据维护问题不新增开发 Task。没有新功能延期，
没有远端停止证明、通用恢复、旧版本升级或 V1 承诺。

**Stop rule：** 不再规划 Task；交 A 按完整 Slice Base..Implementation Head 独立终审。
