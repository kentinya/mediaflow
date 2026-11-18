# NO ACTIVE IMPLEMENTATION TASK

Task55.5：**B PASS**。固定审查范围
`8a9d2460d0fb4df1afee0e157af3736f136a64c8..63d87814bc61f5da8b6300c70e4f5d3b62110d15`；
完整报告与证据索引见 `git show 2e460b71735ac0284e58928c884baac9d3f46009:TASK.md`。
Slice55 仍为 ACTIVE。下文仅为规划草案，不授权实施。

## 草案：Task55.6 — 现有 V2 数据继续使用，Task 只走五态

依据已提交 [Slice55](SLICE.md) 的 RO-4 及 RO-2/3/5/6 中和 Task 状态、持久化直接相关的部分。
需求为 [V2-RETIRE-002–007/009–010](docs/v2-requirements.md#target--complete-v1-and-migration-residue-retirement-slice55-active)；
生命周期和测试分工遵循 [开发流程](docs/development-workflow.md)。

```text
Proposed Task ID: 55.6
Proposed Task Type: SLICE
Proposed Parent Slice: 55
Draft Status: PLANNED — NOT AUTHORIZED FOR IMPLEMENTATION
Proposed Task Base: 2e460b71735ac0284e58928c884baac9d3f46009
Difficulty: High
Test Level: T4
Planner / Reviewer: B
```

规划起点：`/Users/songzhidong/mediaflow`，`main`，HEAD 为上述提交，工作区及暂存干净，
治理检查通过。Slice Base 仍为 `2b2e7c1824fa5681864455714d0f97b26555c7dc`，它是证明原有 V2
数据继续使用的起点；Task Base 是本单元的代码比较起点。草案提交不重设任一 Base。

### Goal 与完整操作旅程

管理员已有 Active 配置，通过资源库 Files 提交整理。其中一个文件已完成，另一个等识别、
元数据、分类或冲突决定。安装候选并重启后，管理员从任务中心打开原 Task，看到原结果和仍
须处理的文件，不必重新配置或重发任务。保存决定后重新分析，核对精确摘要、明确确认，只让
Worker 处理选中的合法工作；也可用现有 Cancel 停止未执行部分。已完成或效果未知的文件不重做，
等待不显示成暂停，流程完成也不冒充每个文件成功。两种库的 Copy/Move/Delete 仍在来源页
显示各自结果。若部署指向原本不支持或损坏的库，启动说明读到了什么、原库未被改动，以及应
检查数据库路径或选择已验证的支持备份；已有的备份、校验和明确非覆盖恢复入口仍可用。

**现在的代码缺口：** `service_api.py` 仍分派 Task 的 `pause`/`resume` 并返回专用
`pause_retired`；`task_runtime.py`、`task_scheduling.py`、discovery 和普通文件 transfer
仍保留暂停路径，Web Task/run 读模型仍接收废弃的 aggregate 状态。CLI 的真实
`mediaflow upgrade --help` 仍列出 `check`、`rehearse`。两个 SQLite repository 启动时
仍混用新库建表、旧补列和历史回填；其中 scheduling 和首轮执行证据是当前必需结构，而
`manual_recovery_preparations` 旧 NOT NULL 列会阻挡当前 INSERT。这些不能按 helper 名称整段删除。

### 开发指导

1. **沿现行入口核对读写归属。** 从最小 bootstrap 启动 API/Worker/Scheduler/Notification，从
   Files、Task Center、Automation、现行 CLI 和数据库备份恢复入口追到读写结构。用 Slice Base
   的实际生产入口生成 V2 夹具，记下候选要保留的 ID、关系、原 digest、pins、请求和效果；
   用 Task Base 的派发与注册确定要退出的旧入口。已有库上的闲置旧表不等于正常 V2 数据不能用。
2. **一次收敛五态及其传输。** 删除 Task 和普通文件的暂停指令、状态、队列/transfer 转移、
   投影、CLI 字段及 Web 消费；注销实际注册的 Pause/resume 分派与审计分类，让旧请求走相同的
   未知路由。拆开 `PersistentTaskStatus` 与文件、附件、扫描/分析结果：删除旧 Task aggregate
   的 `paused`、`partial_success`，保留当前结果的部分成功、效果未知和缺 Result。移除旧
   `domain/tasks.py` 的 Task/ScanTask/阶段状态；`domain/scanner.py` 的现行扫描输出使用其
   实际需要的领域状态，不再代表另一套 Task 生命周期。保留安全取消、Worker claim/lease/fence、
   human/stability waiting、原 Task 的四类续作、Automation 统计与当前通知事实。
   `CANCEL_JOB/cancel_job` 和 `automation.maximumActiveJobs` 不改名。
3. **把新库建表与既有库读取分开。** 在 `sqlite_runtime.py` 和
   `sqlite_configuration_management.py` 直接定义完整当前表、列、索引和版本标记；包括 Task
   scheduling、首轮执行证据、当前来源证据、版本化摘要及 managed 发布权威。移除纯历史补列、
   回填、旧 lock owner 和旧恢复子 Task/remaining-scope 专属结构及读写。沿真实调用确认
   同 Task 摘要、请求、attempt 和结果仍完整；不清除来源归属证据或重算现有 checkpoint/pin。
   对真实 Base 形状只做采用当前行为所需的最小结构调整，例如保留能够原样读取和继续新建
   同 Task 摘要的结构；Base 已满足的列和索引不重写。必要调整置于同一事务，成功后才完成
   初始化；核对 API 与常驻服务同时打开时不会各自提交一半结构。在任何写入前分清新库、支持
   的 V2 库与原本不支持或畸形的库。现有 V2 库不为
   去掉闲置表而删除历史，不靠重设版本号或补授权来接续。
4. **退出旧工具并迁回当前断言。** 注销 `upgrade check/rehearse`，删除专属服务和只验证旧
   升级的脚本；同步 wheel smoke、release 验证、实际引用它们的 CI/部署说明。不改变
   `database backup/verify/restore`。把现有暂停、升级正向测试中仍有意义的断言接到当前
   取消、重启接管、来源变化和效果不重放旅程；只删除为已退役行为本身背书的断言。

### 验收

- [ ] **AC-1（Slice AC-02/06）：** 正常 Active 和合法身份下，已注册的旧 Pause/resume 返回
  普通 unknown route，旧 Upgrade 不在 CLI help 中且进入普通参数错误；无新请求、Task 或
  媒体效果。当前 Cancel、Task 继续与数据库备份入口仍可用。源码及安装包不含旧执行/升级工具。
- [ ] **AC-2（Slice AC-04/06/09/10）：** Files、due/Run once、同 Task 四类恢复及两种库
  普通操作使用五态；任务中心、来源页、API/CLI、日志、导出、通知和 Automation 记录/统计仍
  区分流程、等待原因、文件/附件结果与效果确定性。取消只在安全边界生效；已完成和未知效果
  不重放，权限、满额与 fence 等现有断言不变。
- [ ] **AC-3（Slice AC-05/08）：** 空目录的正式 bootstrap 初始化完整当前库，首次创建
  Draft 并激活后能够直接受理当前工作；新库无 Pause/旧恢复链等专属结构，不靠旧补列或回填
  才具备当前功能。同版本重开、四服务重启、在线备份/核验和显式非覆盖恢复通过。
- [ ] **AC-4（Slice AC-05/06/07）：** 候选打开 Slice Base 用真实入口形成的 V2 库，继续读取原
  Draft/Active、合法 Task 和结果/审计，并完成原待办或核对原未知请求；原 ID、关系、digest、
  pins 及已知/未知效果保持。至少覆盖人等、已受理未执行、已有成功或未知执行效果，以及
  有普通文件操作的库；不要求用户重配或重发。若存在实际结构调整，证明失败时原结构和记录
  不变；原本不支持、损坏或不支持的混合库在启动时报出真实情况，拒绝前后原文件、结构、行
  不变，且无业务执行。
- [ ] **AC-5（Slice AC-11/12 的本 Task 部分）：** 当前 wheel/源码外安装及候选 Docker 的
  启动、空库、重启和相关安全门禁通过。新库结构、实际注册、测试和发布清单相符。以当前
  入口验证保留行为，不用造一个没有注册的地址或只能经测试直接调用的方法证明产品问题。

### 测试

**Developer：** 只运行改动和直接受影响的测试。以下为已有入口，按实际修改的用例选取；
交接给出实际命令/结果，测试和构建累计时间须小于本轮用时的一半。

```sh
# 仓库根：五态、调度与 fence，配置初始化及备份恢复
.venv/bin/python -m unittest tests.test_task_flow_status tests.test_task_scheduling tests.test_task_scheduling_fencing
.venv/bin/python -m unittest tests.test_configuration_management tests.test_sqlite_backup tests.test_sqlite_restore
.venv/bin/python -m unittest tests.test_release_validation
git diff --check
# web/：Task/run 读模型、当前控制及真实浏览器五态/取消旅程
npm run test -- run src/entities/operations/task.test.ts src/entities/operations/run.test.ts src/features/operations/RunLifecycleControls.test.tsx
npm run typecheck
npm run build
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/task-flow.python.spec.ts
```

本轮修改的 Files、transfer、discovery、CLI/源库证明用例随改动运行；不把整套原生、全回归
或镜像矩阵转交 Developer。

**B：** 对冻结候选审查完整 Task Base..Head，先用现行入口证明 AC-1、Base 数据继续使用
及拒绝坏库，再跑 [共享 T4 门禁](docs/development-workflow.md#shared-full-regression-commands)。
原生覆盖 `task-flow.python.spec.ts`、`operations-inventory.python.spec.ts`、`direct-files.python.spec.ts`
与 `automation-run-once.python.spec.ts` 的相关旅程；使用各自隔离的实例及产物目录。用 Task55.5
的固定证据定位现成夹具，仅把它当作本候选复验起点。额外在已验证镜像上运行
`.venv/bin/python scripts/docker_empty_baseline_smoke_test.py --image <candidate-image>`、
`.venv/bin/python scripts/docker_restart_fault_smoke_test.py --image <candidate-image>`，并核对
两种库普通文件生命周期的实际效果。记录 SHA、运行结果和稳定证据位置；累计测试/构建时间
小于该轮总耗时的 50%，未运行的门禁不记为通过。

### 非目标与剩余 Slice 结果

不重做 Task55.1–55.5 已接受的入口、配置与确认功能。RO-1 已验收；RO-2 的剩余暂停/旧链、
RO-3 的旧模型、RO-4 的当前库/五态以及 RO-5/6 中对应消费者与制品归本 Task。Run once/Copy/
Settings 等纯迁移 session、无生产调用的旧全局批量审核及其他非状态协议残留不混入本单元，
待本 Task PASS 后重新核实；全 Slice 最终门禁、CURRENT 协调与 A 终审仍未完成。保留 Git 历史，
不做通用迁移器、部署/推送、运行用户库或新增开发过程工具。

### 交接状态

草案未激活，尚无 Developer 候选，无本 Task 的 PASS/FIX REQUIRED 结论；不改变 Slice、Roadmap
或 Progress。

规划检查：`python3 scripts/check_governance.py` 通过，`python3 -m unittest tests.test_governance`
20 项通过（6.5 秒），旧 CLI 入口确认仅运行 `mediaflow upgrade --help`。未运行产品 T4。
