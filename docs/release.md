# 发布与验证

`main` 是当前开发分支，软件版本见 [pyproject.toml](../pyproject.toml)。构建、打标、发布和部署由维护者分别执行。

## Current V2 validation boundary

当前公开入口为 Web `/` 和 API `/api/*`。当前支持全新初始化和同版本重开；启动只接受空库或本版本创建的数据库（包括本版本配置命令创建的仅配置库），其他版本创建的库在启动前拒绝并保留原文件，即使它只含当前编号的配置，部署者应使用新的空数据目录。通用跨版本升级与回滚、混合版本写入和旧任务迁移均在支持范围之外。Slice 56 的入口切换验证早于本版本的 runtime schema 变化，其 Base 数据仍作为历史验证记录，但不被当前版本作为可启动数据接受。

- Slice 57 终审覆盖 Base `ad7f29a1cc6d73ce17106b513f4b763cfd0c22ab` 至实施 `5d2f215fb7afaceeae677877fdb4990fc6815077`。验证了空库设置、管理员会话及恢复、令牌轮换、计划停用和同版本四服务重启。[验收记录](progress.md#latest-accepted-closure--slice57)
- 当前 runtime schema 只接受空库或本版本创建的数据库；上一版本生成的库在启动前被拒绝，文件字节保持不变。仅配置库同样要求本版本的 store origin 标记；上一版本配置命令生成的仅配置库不会被启动流程补建 runtime。
- 更早的结果、适用范围和测试限制可从验收账本和固定文档版本查阅。[验收账本](progress.md#closure-ledger) · [既往验证记录](https://github.com/kentinya/mediaflow/blob/a9f3022ab061c8379adfeda7d464498345e13000/docs/release.md#earlier-v2-validation)

## Quality gate

以拟发布的精确源码和制品为准。通过工作流规定的 Python、Web、真实浏览器、打包和安全检查，保留镜像及 wheel 标识。[测试等级与门禁](development-workflow.md#6-test-levels)

```bash
release_dir=$(mktemp -d /tmp/mediaflow-release.XXXXXX)
python -m pip wheel . --no-deps -w "$release_dir"
python scripts/wheel_smoke_test.py "$release_dir"/mediaflow-*.whl
python scripts/docker_empty_baseline_smoke_test.py
python scripts/docker_restart_fault_smoke_test.py
python scripts/docker_release_security_smoke_test.py
```

wheel 检查在源码外安装并使用隔离数据库。Compose 验证使用临时媒体和数据卷，并从容器内的主机命令签发一次性设置码创建首位管理员后再核对会话。Docker 不可用时记为跳过，所需门禁须在具备条件的环境中补齐。发布前核对版本、适用支持范围和 CI 结果，检查制品内的文件清单。

部署验证使用目标版本配置并核对运行库 schema 和就绪状态。日期、包版本和 schema 各自独立，schema 以实际安装制品为准。[任务库 schema](../mediaflow/infrastructure/sqlite_runtime.py) · [配置库 schema](../mediaflow/infrastructure/sqlite_configuration_management.py) · [配置文档校验](../mediaflow/application/configuration_snapshot.py)

外部存储验收按服务、驱动及场景认定。提交记录中的 Local、Samba、OpenList Local 驱动和 MinIO 结果适用于所测环境。AWS/R2、其他 OpenList 驱动、远端原子性、长时间运行及断电场景需要对应证据。[存储验收](storage-acceptance.md)

## CI boundary

CI 使用只读仓库权限，运行 Python 质量与测试以及 wheel 检查。网络存储和 TMDB 测试按各自条件执行，发布由维护者确认。[GitHub Actions](../.github/workflows/quality.yml)

## Offline restore procedure

1. 停止全部 API、Worker、Scheduler、Notification Worker 及其他连接该数据库的 MediaFlow 命令。
2. 用 `mediaflow database verify BACKUP` 验证备份。另存原数据库及其 `-wal`、`-shm`、`-journal` 文件，保留原制品。
3. 确认目标和对应的旁路文件不存在，执行 `mediaflow database restore BACKUP --confirm-empty-destination`。
4. 核对恢复路径，使用创建备份的同版本制品启动一个进程验证后，再启动其余服务。

POSIX 上，恢复命令必须取得独占租约。该检查限于参与租约的进程，起步时仍需停机。恢复后先检查原任务、逐项结果和源／目标状态，使用任务已有的安全续作入口处理剩余工作。[备份与重启](deployment.md#backup-and-same-version-recovery)
