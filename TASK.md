# Task 58.2 — 通用 CLI 与配置 schema 11 退出

Next Action: DEVELOPER IMPLEMENTS THE A58-01 CORRECTION

[Slice 58 合同](SLICE.md#required-outcomes-and-surfaces) · [开发工作流](docs/development-workflow.md)

```text
Task ID: 58.2
Task Type: SLICE
Parent Slice: 58
Status: FIX REQUIRED
Task Base: 307eaaf8b006527a11fa2514de839a5528e6c202
Reviewed Head: 1a2383942aff3200f99c9c0560dec3e191ce611e
Difficulty: High
Test Level: T4
Planner / Reviewer: B
Implementation Authorization: ORIGINAL TASK 58.2 CORRECTION SCOPE — A58-01
```

## 目标与 B 复核

**FIX REQUIRED — A58-01（P1，RO-3 / AC-03）。** B 在原候选镜像用正式 Compose 和媒体 overlay
建立隔离实例。原资源库可打开。按发布指引停机、备份、校验并恢复到新文件，命令报告恢复成功，原库摘要一致。
仅启动恢复库 API 后，原会话可读到原 Active 记录，但 Files 返回 `503 configuration_unavailable`。
指引中的 Compose 命令丢掉了两处媒体挂载。带原 overlay 重启 API 后，两处挂载恢复，Files 仍返回
503（`runtime_invalid`）。原发布快照记录的是原库路径，共享加载器把它与恢复 bootstrap 的新路径直接比较。
[正式恢复入口](docs/release.md#offline-restore-procedure) · [共享加载器](mediaflow/infrastructure/runtime_configuration.py)

部署者应能按正式指引停机备份、校验并非覆盖恢复。恢复后先用原管理员登录，只开 API 核对 Active 已实际采用，
打开原资源库看到原文件，并在任务中心对照原任务、逐项结果和审计。核对备份时点之后的实际文件效果和待处理任务后，
用同一恢复配置及原挂载启用后台，按原任务入口继续符合条件的条目。若校验或发布拒绝，按现有提示保留原文件，
换用符合版本要求的备份或不存在的新目标。若恢复已发布但业务核对失败，保留原库与备份，按当前失败信号核对恢复
bootstrap 或原部署挂载，核对完成前保持后台停用。

## 本轮开发指导

1. **落实恢复库的部署定位。** 从 `host_operations.py` 的 `restore` 和 `SQLiteRestoreService` 跟到读取
   已发布快照的共用边界。由正式、显式的离线恢复建立新库的部署定位，复用现有租约、临时副本校验及非覆盖发布。
   恢复副本保留业务记录和原快照内容、ID、digest、Task pin。恢复 bootstrap 固定服务实际打开的 SQLite。
2. **让运行时和发布各走现有业务规则。** 从 `runtime_support.py`、`service_api.py` 和 `resident_entry.py`
   核对 Active 采用、就绪检查和历史 pin 消费，接通 Files 浏览、原任务分析与继续、Worker、Scheduler 和
   Notification Worker。原快照继续按发布状态、schema、完整性和 pin 读取。用 `configuration_snapshot.py`
   中的 `stage_successor_draft` 为常规 Save 候选带入当前部署定位，现有发布输入仍受 bootstrap 路径校验。
   在共用边界处理部署定位，沿用 `REQ-CONFIG-008` 对 Active 和历史 pin 的要求。
3. **修正操作指引。** 更新 `docs/release.md` 的源码及 Compose 步骤和相关部署指引。Compose 从停机到 API-only
   启动、后台启动沿用该部署的 Compose 文件组合和原媒体根。有挂载时给出含 `compose.media-mounts.yaml`
   的可执行命令，普通部署继续用基础 Compose。先核对认证后的管理就绪状态、Files 实际读取及原业务记录，
   再核对实际文件效果并启用后台。源码与 Compose 从已保存备份接续时沿用相同的 API-only 核对顺序。

## 验收

- [ ] 源码和正式 Compose 各自从已发布配置且有合法工作的隔离实例出发，按修正指引停机、备份、校验、恢复到
  不存在的新文件。先只启 API，用原管理员登录，核对 Active 的原 ID 和 digest、管理就绪状态、资源库 Files
  的真实条目及原任务、逐项结果和审计。Compose 媒体 overlay 的两处原挂载在启 API 及启后台时均有效。
- [ ] 对照备份时点后的媒体效果，再用恢复 bootstrap 启后台。在原 Task 显式选择符合条件的原条目，按现有页面
  分析、核对精确摘要并确认。保留原 Task、Item 和固定快照，其中旧 pin 能读取已被后续发布替换的快照。仅
  选定条目发生预期效果，已完成或效果不确定条目的历史结果和文件效果保持原样。
- [ ] 恢复发布、API 读取及分析阶段均为零媒体变更，原数据库及源备份各自的前后摘要一致。沿用缺少确认、目标已存在、
  目标旁路文件、租约冲突、损坏或不适用备份的真实入口与现有失败结果，核对原文件及目标状态。
- [ ] 恢复库的系统设置沿原权限及 checked publication 完成一次常规 Save。原 pin 可继续使用。原有错路径发布
  输入仍被拒绝，普通部署继续通过现有配置采用和快照完整性用例。

## 测试分工

### Developer — 受影响测试

在仓库根目录扩充现有恢复或配置集成用例，证明通过主机恢复入口切换数据库路径后，原发布快照可实际消费。复用
现有镜像和部署夹具沿正式命令核对带 overlay 的 API-only 启动及 Files 读取。运行受影响模块并记录结果及镜像标识。

```bash
python3 scripts/check_governance.py
PYTHONPATH=tests .venv/bin/python -m unittest \
  test_sqlite_restore test_sqlite_backup test_runtime_lease \
  test_configuration_snapshot test_resident_services test_container_deployment
git diff --check
```

### B — 独立验收和全量门禁

从原 Task Base 审查完整候选差异，先对照本轮真实 Compose 复现走修正后的源码与 Compose 指引，再做原 Task
的 Web/Worker 接续和文件效果核对。复用现有隔离夹具和正式命令。按 [T4 共享门禁](docs/development-workflow.md#6-test-levels)
覆盖精确候选，并在仓库根目录用该候选镜像执行现有 Compose 门禁。

```bash
.venv/bin/python scripts/docker_empty_baseline_smoke_test.py --image "$candidate_image"
.venv/bin/python scripts/docker_restart_fault_smoke_test.py --image "$candidate_image"
.venv/bin/python scripts/docker_release_security_smoke_test.py --image "$candidate_image"
```

同一候选用固定 Slice Base 建立并接续合法工作，按 AC-05 核对原任务、权限、pin 和逐项效果。按工作流核对可复用的
验收输入与相关失败，记录实际门禁结果。各测试轮次的测试耗时少于当轮总耗时的一半。

## Slice 结果重评

| 结果 | 当前结论 |
| --- | --- |
| RO-1 / AC-01 | 原候选四服务、空库和媒体挂载启动、整理与传输、调度与通知的验收证据保留。修正候选复验四服务采用配置。 |
| RO-2 / AC-02 | 原候选首次建号、忘记密码及权限的验收证据保留。修正候选复验既有账号与权限的同库连续性。 |
| RO-3 / AC-03 | **未达到。** 恢复后原 Active 无法用于实际文件读取。正式指引还需保留已配置的 Compose 媒体挂载。 |
| RO-4 / AC-04、AC-05 | 原候选旧 CLI 和 schema 11 退出及固定 Base 同库续作的证据保留。修正涉及共享 Active/pin 消费，精确候选复验同库接续。 |

本轮范围限于合同内的同版本停机恢复及实际继续使用。跨版本迁移、媒体备份、Web 备份管理和新的维护入口属于合同
延期范围。原 Task 的全部验收边界见 `32c269044ad14843d37f80f9b855e0b668062daa:TASK.md`。

B 核对了 `307eaaf8..1a238394` 和 `5b2e0de4..1a238394` 的范围及此前验收证据，确认候选至规划前 HEAD
`a75c6e9e50d09ff88339eb6a8e1917cf9182c5e1` 仅变更治理文档。规划开始时 `main` 工作区和暂存区干净，
仓库和 Git 可写。B 在镜像 `sha256:6aba5a154fcaaed5017067260c368b84fb9fbb8dbbb86514ce55da5402e724d8`
复现 A58-01。Compose 复跑耗时 44 秒。两次日志位于
`.git/validation-evidence/1a2383942aff3200f99c9c0560dec3e191ce611e/b-review-a58-01/`。
此前 Closure Packet 及其中记载的 4 个原生整理夹具失败保存在
`435a0b42904765820c85cc71cb904c14bf66f10e:TASK.md`。收到修正候选后，由 B 按本 Task 复验并更新 Closure Packet。
