# 发布与验证

`main` 是当前开发分支，软件版本见 [pyproject.toml](../pyproject.toml)。构建、打标、发布和部署由维护者分别执行。

## Current V2 validation boundary

当前公开入口为 Web `/` 和 API `/api/*`。当前支持全新初始化和同版本重开；启动只接受空库或本版本创建的数据库（包括本版本首次设置创建的仅配置库），其他版本创建的库在启动前拒绝并保留原文件，即使它只含当前编号的配置。需要旧数据的部署者用创建它的原版本处理原文件，本版本改用新的空数据目录；没有就地切换、降级或恢复入口。通用跨版本升级与回滚、混合版本写入和旧任务迁移均在支持范围之外。Slice 56 的入口切换验证早于本版本的 runtime schema 变化，其 Base 数据仍作为历史验证记录，但不被当前版本作为可启动数据接受。

- Slice 58 终审覆盖 Base `5b2e0de4ac1c9d79e3618cef82d420ae302401e7` 至实施 `5415534a38bb8e23ea64a7fd2929c9e6a59a2cad`。验证四个固定服务、首次设置与找回、停机 SQLite 恢复、原 Active 和任务固定快照的实际采用，以及通用 CLI 和配置 schema 11 切换退役。[验收记录](progress.md#prior-accepted-closure--slice-58)
- 当前 runtime schema 只接受空库或本版本创建的数据库；上一版本生成的库在启动前被拒绝，文件字节保持不变。仅配置库同样要求本版本的 store origin 标记；上一版本首次设置生成的仅配置库不会被启动流程补建 runtime，也不会被恢复或切换。
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

恢复只支持与备份同版本、同部署环境的数据库，并且总是发布到**新的**数据库文件。原数据库及其
`-wal`、`-shm`、`-journal` 文件保持原位，不删除、不改名；原备份保留到从恢复后的 API 读回并
核对完成。开始前停止 API、Worker、Scheduler、Notification Worker 和任何其他会打开该数据库的
MediaFlow 进程。恢复命令会取得独占租约；租约被占用时启动服务会在打开数据库前退出，空目标
保持为空。

校验输出分别报告 SQLite 完整性、本版本能否使用，以及不可使用时的具体原因。`Integrity: OK`
与 `Usable by this version: YES` 表示可恢复；`Integrity: OK` 与
`Usable by this version: NO` 表示文件完好但属于别的版本（例如配置 schema 11），本版本不能
恢复或启动它：保留原文件，用创建它的原版本处理，另用新的空数据目录初始化本版本。原库不可读
时 `verify` 在完整性阶段失败，按[原库不可读时](#原库不可读时从已保存的备份接续)处理。恢复
只接受 `Usable by this version: YES` 的同版本备份；不适用的备份被拒绝，目标保持不存在。若
恢复目标或它的任一旁路文件已存在，恢复也会拒绝且不修改文件；另选一个同一数据目录内的新文件名
并重新生成恢复用 bootstrap。

### 源码安装

在新的维护终端进入仓库根目录，沿用 README 启动该部署时创建的本地 `.venv`、
`MEDIAFLOW_CONFIG` 和 `MEDIAFLOW_DATA_DIR`。下面以 README 的默认路径为例；安装时用了其他
路径就替换为当时的实际值：

```bash
cd /path/to/mediaflow
export MEDIAFLOW_CONFIG="$PWD/config/mediaflow.json"
export MEDIAFLOW_DATA_DIR="$PWD/.mediaflow"
```

1. 记录原库摘要并确认当前版本能否启动它。`verify` 只读地检查数据库，不改写库内容；原库
   已损坏时保持原文件原样，改走下面的[原库不可读时](#原库不可读时从已保存的备份接续)。输出
   `Usable by this version: NO`（例如 `Reason` 指出配置 schema 11）时，文件虽完好但属于原
   版本：跳过恢复步骤，保留原文件并用创建它的原版本处理，本版本改用新的空数据目录。

   ```bash
   .venv/bin/python -m mediaflow.host_operations verify \
     "$MEDIAFLOW_DATA_DIR/mediaflow.sqlite3"
   ```

2. 生成并校验备份。备份已存在时不要覆盖，改用另一个新文件名；原库不可读时跳过这一步，
   直接走[原库不可读时](#原库不可读时从已保存的备份接续)：

   ```bash
   .venv/bin/python -m mediaflow.host_operations backup \
     --output "$MEDIAFLOW_DATA_DIR/runtime-backup.sqlite3"
   .venv/bin/python -m mediaflow.host_operations verify \
     "$MEDIAFLOW_DATA_DIR/runtime-backup.sqlite3"
   ```

3. 用现有 bootstrap 生成方法把恢复目标放到同一 `MEDIAFLOW_DATA_DIR` 中的新文件。不要复用原
   `config/mediaflow.json`，也不要预先创建目标或它的旁路文件：

   ```bash
   .venv/bin/python scripts/make_deployment_config.py \
     --output config/mediaflow.restore.json \
     --database-path "$MEDIAFLOW_DATA_DIR/mediaflow-restored.sqlite3"
   ```

4. 用新 bootstrap 执行恢复。恢复会再次校验原备份和暂存副本，并在发布前核对源摘要不变。
   显式恢复会把新目标登记为该部署的当前定位；原 Active、任务 pin 的内容、ID 和 digest 保持
   不变，之后必须继续用恢复 bootstrap 打开这个新文件：

   ```bash
   MEDIAFLOW_CONFIG="$PWD/config/mediaflow.restore.json" \
     .venv/bin/python -m mediaflow.host_operations restore \
     "$MEDIAFLOW_DATA_DIR/runtime-backup.sqlite3" --confirm-empty-destination
   ```

5. 核对原库未变化（第 1 步和第 5 步的 SHA-256 应相同），然后只启动 API：

   ```bash
   MEDIAFLOW_CONFIG="$PWD/config/mediaflow.json" \
     .venv/bin/python -m mediaflow.host_operations verify \
     "$MEDIAFLOW_DATA_DIR/mediaflow.sqlite3"

   MEDIAFLOW_CONFIG="$PWD/config/mediaflow.restore.json" \
   MEDIAFLOW_API_HOST=127.0.0.1 MEDIAFLOW_API_PORT=8787 \
     .venv/bin/python -m mediaflow.resident_entry api
   ```

6. 打开 `http://127.0.0.1:8787/`，用原管理员登录，核对账号、Active、任务、结果与审计；再
   打开原资源库 Files，确认读取的是原媒体根中的真实条目。若 Files 仍报配置不可用，保留原库
   与备份，核对 `MEDIAFLOW_CONFIG` 是否指向恢复 bootstrap、该 bootstrap 的 `databasePath`
   是否就是恢复目标，以及原 Local Storage 媒体根（源码部署中的绝对路径）是否仍可访问；
   核对完成前保持后台服务停用。

7. 核对通过后启用后台。本节开头 `export` 的 `MEDIAFLOW_CONFIG` 仍指向原 bootstrap，直接
   启动会让三个后台服务打开原库。先把部署变量固定到恢复 bootstrap（`MEDIAFLOW_DATA_DIR`
   仍是本节开头的原数据目录，变更的只是 bootstrap 文件），再在各自的终端启动三个后台
   服务：

   ```bash
   export MEDIAFLOW_CONFIG="$PWD/config/mediaflow.restore.json"
   export MEDIAFLOW_DATA_DIR="$PWD/.mediaflow"   # 与本节开头相同的原数据目录
   .venv/bin/python -m mediaflow.resident_entry worker
   .venv/bin/python -m mediaflow.resident_entry scheduler
   .venv/bin/python -m mediaflow.resident_entry notification-worker
   ```

   之后在本终端或新终端启动任何 MediaFlow 进程前，先执行上面两行 `export` 再启动。确认
   四个职责都打开恢复库：按[部署指引](deployment.md#health-and-readiness-signals)的认证
   只读请求 `GET /api/management/readiness`（或 Web 系统视图的同一信号），
   `infrastructure.services` 应同时显示 `api`、`worker`、`scheduler` 和
   `notification-worker` 在线。无法确认备份时点之后的实际文件效果或仍待处理的任务时，
   保持后台服务停用。

#### 原库不可读时，从已保存的备份接续

原库已损坏、`verify` 在完整性检查阶段失败时，跳过第 2 步，不要对原库再执行 `backup`，也不要
删除、改写或重命名原库及其旁路文件。`Usable by this version: NO` 的完好旧版本文件不属于
这一分支，按第 1 步改用原版本或新数据目录。从部署中已保存且此前校验通过的备份接续：

1. 记录原文件摘要，供恢复后核对原文件未变化。损坏的库无法通过 `verify`，但文件字节的
   SHA-256 仍可计算（macOS 用 `shasum -a 256`，Linux 用 `sha256sum`）：

   ```bash
   shasum -a 256 "$MEDIAFLOW_DATA_DIR/mediaflow.sqlite3"
   ```

2. 校验已保存的备份；`Integrity: OK` 与 `Usable by this version: YES` 才可作为恢复源。
   这份备份不可用时换用另一份此前校验通过的备份，没有可用备份就停止并保留现场：

   ```bash
   .venv/bin/python -m mediaflow.host_operations verify \
     "$MEDIAFLOW_DATA_DIR/runtime-backup.sqlite3"
   ```

3. 按第 3–4 步生成指向新目标的恢复 bootstrap 并执行恢复。目标文件名不得与原库或它的旁路
   文件相同。
4. 重新计算第 1 步的原文件摘要，确认原库未被改动。原库 `verify` 已知失败，不要重跑；
   直接执行第 5 步的恢复库 API 启动命令（跳过该步开头的原库 `verify`），再按第 6–7 步
   读回账号与任务，并固定恢复 bootstrap 启用后台：

   ```bash
   MEDIAFLOW_CONFIG="$PWD/config/mediaflow.restore.json" \
   MEDIAFLOW_API_HOST=127.0.0.1 MEDIAFLOW_API_PORT=8787 \
     .venv/bin/python -m mediaflow.resident_entry api
   ```

### Compose 部署

在 Compose 项目目录执行。默认 bootstrap 是 `config/mediaflow.json`，容器内数据库是
`/data/mediaflow.sqlite3`，停机和恢复都使用同一个 `mediaflow-data` 卷。下面的维护命令必须
沿用该部署启动时使用的 Compose 文件组合：没有媒体挂载的普通部署只用基础 Compose；配置了
Local Storage 的部署还要带上 `compose.media-mounts.yaml`，并保留原来的
`MEDIAFLOW_SOURCE_MEDIA_ROOT`、`MEDIAFLOW_TARGET_MEDIA_ROOT`（项目 `.env` 或当前终端）：

```bash
cd /path/to/mediaflow

# 普通部署（无媒体挂载）：
mediaflow_compose=(docker compose -f compose.yaml)
# 使用 media overlay 的部署改用下面这行：
# mediaflow_compose=(docker compose -f compose.yaml -f compose.media-mounts.yaml)

"${mediaflow_compose[@]}" stop
```

之后每一步都使用同一个 `mediaflow_compose` 数组；使用 overlay 时重启 API 和后台服务都会
重新获得原 `/media/incoming`（只读）与 `/media/organized`（读写）挂载。

1. 记录原库摘要并确认当前版本能否启动它；原库已损坏时保持卷内文件原样，改走下面的
   [原库不可读时](#原库不可读时从已保存的备份接续-1)。`Usable by this version: NO` 的完好
   旧版本文件同样跳过恢复：保留原文件并用创建它的原版本处理，本版本改用新的空数据目录。

   ```bash
   "${mediaflow_compose[@]}" run --rm --no-deps api host verify /data/mediaflow.sqlite3
   ```

2. 生成并校验备份。备份已存在时不要覆盖，改用另一个新文件名；原库不可读时跳过这一步，
   直接走[原库不可读时](#原库不可读时从已保存的备份接续-1)：

   ```bash
   "${mediaflow_compose[@]}" run --rm --no-deps api \
     host backup --output /data/runtime-backup.sqlite3
   "${mediaflow_compose[@]}" run --rm --no-deps api \
     host verify /data/runtime-backup.sqlite3
   ```

3. 在主机用现有 bootstrap 生成方法把恢复目标放到同一 `/data` 卷中的新文件。这里只使用
   `scripts/make_deployment_config.py`，不需要在主机安装 MediaFlow Python 包：

   ```bash
   python3 scripts/make_deployment_config.py \
     --output config/mediaflow.restore.json \
     --database-path /data/mediaflow-restored.sqlite3
   ```

4. 用 `MEDIAFLOW_CONFIG_FILE` 让恢复容器挂载新的 bootstrap。`mediaflow-data` 卷、原数据库和
   原备份都保留。显式恢复会把新目标登记为该部署的当前定位；原 Active、任务 pin 的内容、
   ID 和 digest 保持不变，服务必须用恢复 bootstrap 和原媒体挂载启动：

   ```bash
   MEDIAFLOW_CONFIG_FILE="$PWD/config/mediaflow.restore.json" \
     "${mediaflow_compose[@]}" run --rm --no-deps api \
     host restore /data/runtime-backup.sqlite3 --confirm-empty-destination
   ```

5. 核对原库摘要未变，然后仅启动 API。容器仍监听 8080，浏览器使用 Compose 项目配置的宿主端口：

   ```bash
   "${mediaflow_compose[@]}" run --rm --no-deps api host verify /data/mediaflow.sqlite3

   MEDIAFLOW_CONFIG_FILE="$PWD/config/mediaflow.restore.json" \
     "${mediaflow_compose[@]}" up -d --no-deps api
   "${mediaflow_compose[@]}" ps api
   ```

6. 打开 `http://127.0.0.1:${MEDIAFLOW_API_PORT:-8080}/`，用原管理员登录，核对账号、Active、
   任务、结果与审计；再打开原资源库 Files，确认读取的是真实媒体条目。使用媒体 overlay 时
   两处原挂载必须仍由 `mediaflow_compose` 带入。核对通过后，让后续 Compose 命令固定使用恢复后
   的 bootstrap 再启用其余服务：

   ```bash
   export MEDIAFLOW_CONFIG_FILE="$PWD/config/mediaflow.restore.json"
   "${mediaflow_compose[@]}" up -d
   ```

   要把恢复后的库作为该项目今后的数据源，把
   `MEDIAFLOW_CONFIG_FILE=./config/mediaflow.restore.json` 写入项目 `.env`，或在每个维护终端
   导出同一变量；否则不带该变量的 `up -d` 会重新挂载原 bootstrap 并打开原库。后台服务必须
   继续使用同一个 `mediaflow_compose` 组合和原媒体根；启用之前仍需核对备份时点之后的实际
   文件效果和待处理任务，无法确认时保持后台服务停用。

#### 原库不可读时，从已保存的备份接续

原库已损坏、`verify` 在完整性检查阶段失败时，跳过第 2 步，不要对原库再执行 `backup`，也不要
删除、改写或重命名卷内原库及其旁路文件。`Usable by this version: NO` 的完好旧版本文件不属于
这一分支，按第 1 步改用原版本或新数据目录。从已保存且此前校验通过的备份接续：

1. 把原库复制到主机上已被 Git 忽略的目录并记录摘要，供恢复后核对原文件未变化。不要把
   数据库复制到项目根目录等会被 Git 跟踪的位置（服务停止后 `compose cp` 仍可读取卷内
   文件；macOS 用 `shasum -a 256`，Linux 用 `sha256sum`）：

   ```bash
   mkdir -p .mediaflow
   "${mediaflow_compose[@]}" cp api:/data/mediaflow.sqlite3 \
     "$PWD/.mediaflow/mediaflow-original.sqlite3"
   shasum -a 256 "$PWD/.mediaflow/mediaflow-original.sqlite3"
   ```

2. 校验已保存的备份；`Integrity: OK` 与 `Usable by this version: YES` 才可作为恢复源。
   这份备份不可用时换用另一份此前校验通过的备份，没有可用备份就停止并保留现场：

   ```bash
   "${mediaflow_compose[@]}" run --rm --no-deps api host verify /data/runtime-backup.sqlite3
   ```

3. 按第 3–4 步生成指向新目标的恢复 bootstrap 并执行恢复。目标文件名不得与原库或它的旁路
   文件相同。
4. 重新计算第 1 步的原文件摘要，确认原库未被改动；再次校验备份并核对 `SHA-256` 与第 2 步
   相同。原库 `verify` 已知失败，不要重跑；直接执行第 5 步的 API 启动命令（跳过该步开头
   的原库 `verify`）：

   ```bash
   MEDIAFLOW_CONFIG_FILE="$PWD/config/mediaflow.restore.json" \
     "${mediaflow_compose[@]}" up -d --no-deps api
   "${mediaflow_compose[@]}" ps api
   ```

   然后按第 6 步读回账号与任务，并固定 `MEDIAFLOW_CONFIG_FILE`、同一个 `mediaflow_compose`
   组合和原媒体根启用其余服务。

POSIX 上，恢复命令必须取得独占租约。恢复后先检查原任务、逐项结果和源／目标状态，使用任务
已有的安全续作入口处理剩余工作。[备份与重启](deployment.md#backup-and-same-version-recovery)
