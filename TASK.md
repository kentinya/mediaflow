# Task47.5 — FIX REQUIRED

最新候选 `f3fcace35371bc7aa3f56ce6e5698261faab5e52` 的提醒数据和单文件交接已有修复证据。
B 撤回此前“失败且效果未知就必须继续占容量”的批量 P1 判断；原复现未证明仍有在途工作，
不能用该假设要求 Developer 返工。进一步实际验证发现相反问题：所有文件已结束，旧批次
仍占名额；此外，批次进行中接手已失败文件后，旧批次最终结算会误报技术失败。
这两项为已实测阻塞，见末尾容量核对及补充旅程。其余 T4 验收仍未完成。
Task ID、Goal、Base 和 Slice 边界不变；不授权派生代理、push、部署或 Slice 关闭。
用户已选择：“运行一次”和定时一样排除历史 failed / partial，保留一键执行，不新增初始确认。
本次规划一致性核对后按用户选择改为**同一来源版本最近一次正式整理结果**判断；后来手动整理
成功，不再因更早失败排除。普通 CLI/remote 不新增提醒或放行契约，Web 提醒要求保留。

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
Status: FIX REQUIRED
Task Base: 75ddff55f8d5b2b1206c81804bfb5cbe9ed279a1
Difficulty: High
Test Level: T4
Planner / Reviewer: B
Implementation authorization: USER-AUTHORIZED THIS ROUND — IMPLEMENTED, CANDIDATE SUBMITTED
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

- [ ] **AC-T1 / Slice AC-20：** due 和 Run once 对同版本 failed/partial 独立排除；零效果
  失败也排除；依据最近正式结果，后来手动成功解除早期失败造成的排除。自由兄弟项真实
  完成，完整范围/稳定性与排除记录/计数一致，全排除不假成功。
- [ ] **AC-T2 / AC-21：** Files 直选、目录及混合选择都允许历史失败项进入新整理；真实
  部分目录、复制残留、failed+unknown/partial+unknown 均先显示清楚提醒，再经原摘要
  选中确认执行正常计划。没有额外核查页/例行 checkbox，也不只做到“可以打开摘要”。
- [ ] **AC-T3 / AC-22：** 真实 canonical Storage/path/版本匹配不受最近32/100条历史截断；
  覆盖跨库绑定、同名异路径、新版本、未知版本、混合 Task、无 Result 持久失败、非整理
  仅分析和 failed→manual success。旧尝试迟到发布不能替代较新的正式尝试结果。
  读取失败不放行；新 Task 自己的分析失败不伪装成先前外部历史。
- [ ] **AC-T4 / AC-23：** 尚无文件终态结果的排队/处理项保留互斥；已有 failed/partial
  结果的文件不因父 Task running/历史未知标记而被重新判为活动项。不要求远端停止证明。
  手动旧历史接管/确认、锁和容量原子核对，失效 app owner 后续状态写入及新步骤准入
  拒绝，不承诺停止已派发调用。兄弟项不被解锁。旧未知证据仍未知，且既有
  标记不会使已确认新手动工作永久无法执行。没有把 Web 确认说成远端已停止证明。
- [ ] **AC-T5：** 新整理用新 pin，原已记录结果、完成步骤、Result/pin、未知证据和原
  Automation 结果/时间不改写；允许必要的锁/claim/fence/当前处理状态调整，不要求旧
  Task/item 每个字段不变。正常 Conflict/Hash/覆盖/清理、C→A identity、附件、RBAC/脱敏
  及四类同 Task 继续不退化。旧项/成功兄弟不被这次新请求作为恢复范围自动重放。
- [ ] **AC-T6 / AC-24：** source/help/installed wheel/image 无活跃 retry-failed 或替代入口；
  旧命令在解析处拒绝且零效果；正常 CLI 分析/execute 和其他 Task 管理/四类继续保留。
  文档与 negative-test 字面量允许保留；普通 CLI/remote 原有来源/授权语义不变，
  不新增 CLI 历史提醒、remote 类别或未展示 Web 提醒的额外拒绝规则。
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

## Developer Completion Report — FIX ROUND（候选 2）

按 B Review 的三项阻塞在同一 Task 内修复；Task ID/Goal/Base 与 Slice 边界不变，
未扩大范围。工作区 `main`，本轮起始 HEAD `76598900`（B 指导澄清提交），无预存 tracked
修改；预存未跟踪文件（OS/log、`15`、docs 图片、`output/*` 等）原样保留、未暂存。
未触碰用户数据库/媒体/私密配置；未 push、未部署、未自判 PASS。

**Changes（对应 B 修复指导 1–3）**

1. **历史事实读取（阻塞 2）**：`sqlite_runtime.py` 重写
   `latest_organize_source_outcome`：
   - Result 关联改走真实持久边界：`LEFT JOIN manual_execution_items mei ON
     mei.task_item_id = i.item_id`，`r.result_id = COALESCE(mei.result_id,
     i.item_id || ':' || i.attempts)`——手动 UUID Result 与自动/CLI/继续
     `item:attempts` Result 各按其真实写法命中，无 Result 的持久失败项仍回退
     item 行；目标/完成步骤/效果确定性/未知证据按 Result 优先读取（COALESCE）。
   - 状态大小写统一为小写（手动 `PARTIAL` → `partial`），排除/提醒判断
     不再漏判。
   - `LIMIT 400` 撤销：新共享迭代器 `_iter_organize_source_outcome_rows_locked`
     以 keyset 分批（每批 400）按 admission/attempt 顺序读取**完整匹配总体**，
     最新可适用行胜出；迟到发布不冒充最新尝试的语义不变。
2. **真实 API → 页面（阻塞 1）**：`operations_lifecycle.py::_bounded_preview_plan`
   新增 `history` 投影与 `_bounded_preview_history`（字段级边界与脱敏：status/
   recordedAt/destinationStorageId/destinationPath/completedOperations/
   uncertainEffects/effectCertainty/versionApplicable/warning），不透传 raw plan。
   真实 Preview GET 现已携带 history，现有 Web typed normalizer
   （`preview.ts::normalizeHistory`）与 `OrganizePlanConfirmation.tsx` banner 直接
   消费，无需前端改动；无新增核查页/例行 checkbox。
3. **逐文件交接与容量结算（阻塞 3）**：
   - 新增迁移列 `task_items.superseded_by_task_id`（additive，fresh 与同版本
     reopen 均安全；`_TASK_ITEM_UPSERT` 不触碰该列）。
   - `admit_manual_execution` 确认事务内新增：被替代源守卫（adopted Task 的
     已交接来源以 `source_superseded` 拒绝）+ 每个确认项的
     `_hand_off_superseded_source_owner_locked`——在同版本最近正式结果为
     failed/partial、旧 owner 为未完成 kernel Task 时：标记旧 item（guarded
     UPDATE，不覆盖已有标记）、仅当变异边界属于被交接项时收束该边界（其他项的
     未验证边界绝不触碰）、无剩余机器工作且无待处理控制时释放名额
     （全部 settled → SETTLED，含诚实聚合修正；仅剩人工决定 → WAITING_HUMAN），
     仍有机器工作则保留原 claim 与 1 个名额。排程/处理中且无终态的来源完全不触碰，
     file_locks 互斥保持原样。
   - `_require_scheduled_item_locked`：已交接 item 的 START/PROGRESS/OUTCOME
     发布一律拒绝（旧 owner 不能再启动后续步骤或改写旧结果）；旧 Result/pin/
     完成步骤/unknown 证据与原 Automation 时间不改写。
   - 公开包装 `hand_off_superseded_source_owner`（独立事务）供仓库级旅程复用。

**Developer affected tests（实际命令与结果）**

- `python -m unittest tests.test_organize_source_history`：18 tests OK（新增：
  手动 UUID Result 完整证据读取 + 大小写统一；>400 行完整总体跨批找到最新可适用；
  手动 Result 越批；真实 Files→引擎旅程两例——单文件 uncertain 失败后新整理
  交接：旧 Task SETTLED、旧 claim 心跳 REJECTED、容量 0、旧 Result/证据逐字段
  不变、标记=新 Task；批 [One,Two] One 失败 Two 未完成：交接后旧 Task 保留
  名额与有效心跳、One 迟到发布被拒（"handed off"）、新 Task 完成、旧 Result 不变）。
  失败注入位于真实 Storage.write/`_ExplodingExecutor` 边界，非手填状态。
- `ManualHistoryWarningJourneyTests` 新增真实 Preview GET 断言（阻塞 1 的 API
  级回归；经突变校验确认真实执行）。
- `python -m unittest tests.test_organize_preparation tests.test_manual_task_engine
  tests.test_manual_organize_execution tests.test_task_scheduling
  tests.test_task_scheduling_fencing tests.test_task_retry
  tests.test_automation_entrance_recovery`：167 tests OK。
- `tests.test_automation_run_once tests.test_automation_task_admission
  tests.test_task_source_ownership_race tests.test_preview_retirement`：73 OK；
  `tests.test_operations_task_center tests.test_operations_run_detail_log_isolation
  tests.test_operations_run_detail_plan_evidence tests.test_v2_automation_operations`：
  58 OK；`tests.test_task_persistence tests.test_workflow_retry
  tests.test_manual_ignore tests.test_manual_ignore_batch
  tests.test_processing_recovery_admission tests.test_manual_operations_contract`：
  55 OK；`tests.test_direct_file_operations tests.test_batch_cli
  tests.test_conflict_resolution`：74 OK；`tests.test_manual_operations
  tests.test_media_discovery tests.test_task_scope`：185 OK。
- `python -m unittest discover -s tests`：**2518 tests OK（skipped=7，既有 skip）**。
- `ruff check .` / `ruff format --check .` PASS；`compileall` PASS；
  `scripts/check_governance.py` PASS；`git diff --check` PASS；
  `rg -n -i 'ffprobe|ffmpeg' mediaflow pyproject.toml` 无匹配（exit 1）。
- Web（cwd `web/`）：`npm run typecheck`、`lint`、`format:check` PASS
  （prettier 对既有 `OrganizePlanConfirmation.test.tsx` 的格式修正 3 行）；
  `npm run test -- run` 88 文件 / 1267 tests PASS；`npm run build` PASS。
- 契约夹具按测试官方路径再生
  （`MEDIAFLOW_UPDATE_FIXTURES=1`）：`manual-operations.json` 仅新增两处
  `"history": null` 字段（真实 API 投影的体现）。

**Deviations / remaining risks（如实披露）**

1. 批量场景中 Two 为"排队机器工作"（PROCESSING、无自身终态）时的**最终收束**
   走既有中断执行恢复路径（reconcile/租约接管），属既有机制；本 Task 只断言
   交接不触碰其边界且名额保留（B 验收表第 2 行要求），未新增恢复能力。
2. 浏览器级旅程（桌面/窄屏截图，AC-T7）未由 Developer 执行，与上轮相同留给
   B 的验收门禁；Web 组件测试经既有 typed normalizer 消费真实 API 形状。
3. 文档协调（requirements/architecture/product-experience 的 CURRENT 描述、
   RO-6 交付标记）仍留待 Slice 收尾核对，未改 A-owned 文档。
4. 交接目标的版本可比性沿用与历史判定/占用边界同一证据链；无可比版本时按
   "可能适用"处理（保守，不伪造新文件）。

## B Review Result

**当前状态：FIX REQUIRED。此前“过早释放名额”的 P1 仍撤回；本轮实际证明“全部结束后未释放名额”，需按下述准确方向修复。**

候选：`f3fcace35371bc7aa3f56ce6e5698261faab5e52`；审查范围仍为
`75ddff55f8d5b2b1206c81804bfb5cbe9ed279a1..f3fcace35371bc7aa3f56ce6e5698261faab5e52`。
本次仅纠正 B 的判断，不改变候选代码、原 Task/合同、安全规则或旧接受事实，不宣告 PASS。

### 最新容量核对：批次全部结束后仍可能占一个名额（P1）

用户明确的口径：一个 Task 最多占一份容量；成功 8/失败 2 全部结束应占 0，成功 2/失败
5/进行中 3 应占 1，全成功占 0，成功 8/部分成功 2 全部结束也应占 0。历史未知效果本身
不等于当前还有工作。此规则与保留真实在途调用、逐文件结果和非重放要求同时成立。

本轮从 `main` / `373705e00ba7159ca12b4a171ff2fe0589d21ff6` 开始，无预存 tracked 修改，
预存 untracked 保留未暂存。产品代码仍为 f3fcace3。通过已有 Run once API → definition
pipeline → Worker / SQLite / LocalStorage，使用 10 个临时文件与 SyntheticMetadataProvider，
实际执行结果如下（未手填 Task/Result）：

| 实际旅程 | 未结束文件数 | Worker 调用返回后的实际容量 |
|---|---:|---:|
| 10 个全部成功 | 0 | 0，符合 |
| 8 成功、2 个在效果发生前失败 | 0 | 0，符合 |
| 8 成功、目标写入故障造成 1 partial/unknown、随后 1 failed/none | 0 | **1，不符合** |

第三种所有 Storage 调用和本轮 runner 均已返回，无 pending/processing 文件项；原 Task
仍 running、调度仍 claimed，未知效果记录继续存在。此时正确行为是保留失败/partial/
unknown 历史并结束本批次执行占位，不要求先重新整理任意文件才能释放容量。

因此不能回答“现在已经完全按四种规则实现”。本轮没有构造出恰好 8 成功/2 partial，
也没有把“3 个进行中”的计数表当作已执行测试；但第三种真实反例足以证明全部结束后
不占位的规则尚未完全实现。各次真实文件写入期间均实测占 1，不按 10 个文件占 10 份。

**根因与范围：** `manual_task_engine.py::_settle_automatic` 在 runner 返回后仍仅凭
`mutation_in_flight` 标记直接返回，未区分该标记代表已经结束后的未知效果历史，还是实际
尚未结束的调用；容量查询只按 queued/claimed 计数，因而已终态的文件仍把整批留在 claimed。
这与此前已撤回的“释放得太早”方向相反，不能恢复旧建议或要求 unknown 永久占位。

**Developer 修复指导（仍在同一 Task）：**

1. 在共享引擎/kernel 的合法结算边界区分真实在途/待执行工作和已终态的效果未知历史。
   当前调用已返回、文件项全部终态、无其他机器工作时，应更新诚实 Task 聚合并释放该 Task
   的执行名额、收束旧执行资格；真正仍在执行的调用或剩余机器工作继续占一份。避免只改
   容量 SQL 忽略 claimed Task、仅靠超时认定结束，或仅按页面状态跳过实际安全边界。
2. 原 Result、partial/unknown、完成步骤、配置 pin 及 Automation 原执行结果/时间保持事实；
   不把 unknown 改成 none，不重放旧文件/成功兄弟。定时同版本失败排除及 Files 警告后新
   整理仍按本 Task 规则执行，不能要求手动重新整理来清理已结束批次的占位。
3. 复用本轮 probe 和既有 fixture，将实际反例纳入受影响测试；同时覆盖普通失败释放、全
   成功释放、批量仍有真实进行中工作占一份、全部 terminal partial 释放。手动及定时/
   Run once 共用结算行为一并核对；真实仍未返回的调用不得被误释放。Developer 运行新增/
   修改与直接受影响测试，B 负责剩余原 T4 门禁。
4. 简短提醒的原交付要求继续有效；此修复不增加核查页、用户技术操作或新的恢复系统。

证据：本机 `.git/validation-evidence/373705e00ba7159ca12b4a171ff2fe0589d21ff6/capacity-current/`
的 `probe.py` / `probe.log`。3 个真实旅程合计运行不足 1 秒；治理预检和 `git diff --check`
通过，未执行全量/浏览器/包装门禁，测试时间低于本轮总用时 50%。Task 保持原 ID/Base，
本轮只提交 Task 复核结果及开发指导，不实施产品，不改 A-owned 合同或 Slice 状态。

### 补充旅程：旧批次运行中重新整理失败文件、单文件与四类决定

本轮起始 `main` / `1b33f1936e8f2c933faf3a762f3589916a2baba4`；无预存 tracked 修改，
预存 untracked 保留。候选产品代码不变；仅补充 B 证据与同 Task 修复指导。

**旧批次仍在执行时重新整理失败文件：前半程通过，旧批次结算失败（第二项 P1）。**

从现有 Run once API 建立含 A/B 的旧批次；A 在 Provider 阶段真实失败、无媒体效果；
B 的真实 LocalStorage 写入用 Event 暂停，使 B 的调用确实仍在执行。此时通过第二个
已注册 Worker 消费现有 Files 请求，用户选择 A → 失败提醒 → 普通确认 → 新 A COPY
实际成功。未手填 Task/Result，不用 PROCESSING 字段假设一个调用仍在运行。

实测过程：旧 A failed、B processing，旧批次占 1；新 A 确认后总计 2；新 A 成功后总计
1，B 的在途边界保留，旧 A Result 原样不变。这段符合逐文件接手要求。

释放 Event 让 B 真正写完后，B Result 记录 success，旧 A Result 仍 failed，旧批次却在
正常汇总结算时抛出 TaskSchedulingError，最终被异常处理标为 failed，error 为
`manual Task engine could not advance this stage (TaskSchedulingError)`。正确应按旧批次
自己的 A failed / B success 汇总为 partial_success；新 A 的独立成功不改写旧 A。
最后容量为 0，**本次问题不是名额卡住或提前释放**，没有复现文件重复执行/丢失。

定位：`_settle_automatic` 把旧批次全部 item 传给结算；
`SQLiteTaskRepository.release_scheduled_claim` 在 PROGRESS 阶段重新发布这些 item；
`_require_scheduled_item_locked` 对已被新 A 接手的旧 A 一律拒绝，连本次只想读取旧终态来
汇总批次的结算也拒绝。该 guard 是 f3fcace3 的新接入，阻止旧 A 实际重启/改写仍必须保留。

Developer 指导：在现有结算事务中分开“读取旧终态参加批次汇总”和“再次发布旧 item”。
旧 A 的事实可以参与汇总，结算不应向已交接 item 重发 PROGRESS/OUTCOME 写入；不得
通过删除 superseded 标记、放宽旧 owner 启动/结果发布或覆盖旧结果来修复。补完整并行
回归：A 原失败 → B 真实仍在写 → 新 A 成功 → B 写完 → 旧批次诚实 partial_success，
无技术收尾错误，最终名额 0。原手动批次也按同一共享结算边界补直接受影响覆盖；本轮
新增并行探测的原批次入口是 Run once，不能据此宣称手动/due 的全部矩阵已通过。

**单文件与四类决定的针对性复验：9 tests OK，1.367 秒。**

- 单文件：`SupersededSingleFileOwnerHandoffTests` 与
  `ManualTaskDiscoveryTests.test_confirmation_adopts_the_same_task_and_executes`，覆盖正常
  Files 确认到结果、真实失败后提醒/再次确认/实际 COPY、旧 Result 保留、旧资格拒绝及
  新工作完成后的容量释放。失败后尚未重新整理就占位的问题仍按上一节修复。
- 批量阶段性检查：`SupersededOwnerWithRemainingWorkTests` 通过，但它未跑完旧兄弟项，
  不能替代上面新增的真实在途调用和旧批次最终结算；其阶段性通过与新 P1 不矛盾。
- 识别/元数据：`ManualTaskDiscoveryTests` 的 partial_recognition、
  task_center_continue、native_metadata_candidate 三项真实 API/Worker 旅程通过，覆盖
  保存决定 → 分析 → 精确摘要 → 选中确认 → 同 Task 实际结果及兄弟项独立处理。
- 分类/冲突：`RunOnceApiTests.test_recognition_decision_reaching_classification_stays_a_business_problem`
  与 `test_conflict_recovery_keeps_the_original_automation_record` 通过，完成各自决定到真实
  整理结果，保留原执行记录；队满时保留已保存决定与等待状态的测试也通过。
- 以上是现有 Python API/SQLite/Worker/LocalStorage 旅程，不是生产浏览器桌面/窄屏验收，
  不把 9 项通过等同于全部四类入口/并发/重启矩阵均完成。

本机证据：`.git/validation-evidence/1b33f1936e8f2c933faf3a762f3589916a2baba4/scenario-review/`
的 `journeys.log`、`live_sibling_probe.py`、`live_sibling.log`。独立旧批次最终状态断言
`partial_success != failed` 失败。所有产品测试与并行复现合计不足 10 秒，低于本轮总用时
50%；Task 保持 FIX REQUIRED，在同一 Task 修上述两个产品缺口，不新增 Task/执行系统。

### 判断纠正：失败历史与当前仍在执行是两件事

用户指出“A 已经失败，为什么还要占任务”。B 回查现有证据后纠正：

- 原 Run once 复现中，A 的 Storage.write 已抛错返回，并形成 partial/未知效果 Result；
  B 随后 failed、效果为 none，原 runner 已返回。没有证明还有实际在途调用或合法待执行
  工作。历史效果未知或旧 `mutation_in_flight` 标记单独存在，不能代替这项证明。
- 用户后来只重新整理 B，B 实际成功，旧批次 settled、容量为 0，是观察事实。此前私有
  probe 强制断言“容量必须为 1”，依赖未经证明的占位前提；该断言失败不能据此定性为
  产品容量回归、A 的安全保护被破坏或多放了执行任务。
- **撤回 `2dce1ae3:TASK.md` 中的唯一 P1 及据此要求保留旧 claim/名额的修复步骤。**
  不要求 Developer 为满足这个断言增加永久占位、恢复旧 claim、阻止新整理或改写生产行为。
  原 probe、失败日志和 Git 历史全部保留，标明是 B 预期依据不足，不删除或伪装为通过。

用户旅程应按真实工作判断：一批 A 失败、B 成功、C 仍在执行，C 的合法工作和必要容量应
保留；若整批都已结束、没有需保留的在途/待执行工作，保留 A 的失败及未知效果历史并不
要求永久占用执行名额。A 的同版本失败仍按定时/Run once 历史规则排除；用户手动选择 A
时仍走提醒与正常确认。不得把“效果未知”改写成“已验证无效果”，也不得自动重放 A。

这不是放宽真实在途调用、剩余机器工作、逐文件锁或旧 owner fencing 的安全义务。当前
未证明这些义务在该复现中受到破坏；后续应由正常入口的真实在途/剩余工作旅程验收。

### 已取得的候选证据与待验收项

| 项目 | 已取得的结果 / 限制 |
|---|---|
| 提醒传输与真实 Result | 真实 Preview GET 已含 history；UUID Result 的目标、完成步骤与未知效果可读。 |
| 单文件交接 | 实际失败 → Files 再次确认 → 新 COPY 成功；旧 heartbeat 拒绝，容量为 0。 |
| 聚焦测试 | B 执行 `tests.test_organize_source_history`，18 tests OK，2.723 秒；不等同于完整验收。 |
| 批量/定时 | Run once 故障后从 Files 重新整理 A 或 B 均实际成功；“只整理 B 后必须占 1 名额”的旧判据撤回，不能据此给 PASS 或 FIX REQUIRED。 |
| 简短提醒 | 用户已明确的简化尚未落实：当前文案仍有内部步骤代码和多处长文重复。保留原交付要求，普通提醒简短、确有 unknown 再说明，详情保留有用事实，不新增操作步骤。 |
| 完整验收 | 生产浏览器桌面/窄屏、其他适用 T4/Web/包装/Docker/restart/security 验收仍待 B 完成；不能用 Developer 的全量报告代替最终判断。 |

证据在本机 `.git/validation-evidence/f3fcace35371bc7aa3f56ce6e5698261faab5e52/b-review/`：
`manual.log`、`focused.log`、`automatic_probe.py`、`automatic.log`、`sibling-unknown.log`。
其中 sibling-unknown 的 exit 1 记录保留，**其容量=1 的预期已撤回**；不声称远端可访问。

### 后续开发指导与 B 验收边界

1. 撤回项不产生新的实现任务；Developer 不应照旧结论为已失败、无实际剩余工作的文件
   保留名额。保持已有结果、未知证据、非重放和已实现的逐文件交接。
2. 落实用户已确认的简短提醒：普通提醒说明上次整理未完成及核对来源/目标；未知效果
   才补一句。原始 CREATE_DIRECTORY / mutation_outcome 等代码无需作为普通必读文案，
   可用目标和已知影响放现有详情，以人话表达；不加核查页、checkbox 或令牌操作。
3. B 后续从已有入口完成批量中真实剩余工作/在途调用、失败历史与执行资格分离、拒权/
   队满/并发确认、同版本 reopen 等原计划验收；区分实际在途工作与纯历史 unknown，
   不把私有 probe 的内部 marker/计数预期当作新增产品要求。原 T4 门禁与测试时间小于
   本轮总用时 50% 的要求继续有效。

### 工作区与 Slice 状态

本次纠正开始于 `main` / `2dce1ae33de525695f4ad3ccae7311a07ddc143e`，无预存 tracked
修改，预存未跟踪 OS/log、图片、`15` 和 output 产物全部保留未暂存。仅更新 TASK.md，
治理预检 PASS；未改产品、未运行新产品测试，既有观察与原始日志不变。

RO-1–5 原接受事实保留；本候选的 RO-6 和整体回归尚未最终验收。没有基于当前复现证明
“过早释放”的容量回归，原阻塞不恢复；最新真实反例见上方“最新容量核对”。Slice 保持
ACTIVE，Task 因全部结束后仍占位而为 FIX REQUIRED，
不关闭 Slice、不创建后续 Task、不提交 READY FOR A REVIEW packet。
