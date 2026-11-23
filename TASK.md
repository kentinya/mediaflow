# NO ACTIVE IMPLEMENTATION TASK

Next Action: A REVIEWS SLICE 58

Task 58.2 **PASS**。Slice 58 **READY FOR A REVIEW**。

## B 复核与 Slice 58 交接

```text
Slice: 58 — 通用 CLI 彻底退役
Task Reviewed: 307eaaf8b006527a11fa2514de839a5528e6c202..5415534a38bb8e23ea64a7fd2929c9e6a59a2cad
Slice Base: 5b2e0de4ac1c9d79e3618cef82d420ae302401e7
Implementation Head: 5415534a38bb8e23ea64a7fd2929c9e6a59a2cad
Tasks completed: 58.1, 58.2
Required Outcomes and Surfaces: COMPLETE
Decision: SLICE READY FOR A REVIEW
```

B 从干净的 `main` 复核完整 Task 和 Slice 差异。候选之后的 Developer 交接 `76016def` 只更新
`TASK.md`。历次复现、修正指导及 Developer 结果保存在该提交。

### 合同结果

- **AC-01 / RO-1。** 正式 Compose 从空库和媒体挂载两种部署启动四个职责。空库在生产 Web 初始化，
  Scheduler 采用配置并触发工作，受控接收端收到签名 Webhook。媒体挂载中，整理分析阶段零文件效果，
  显式确认后在同一 Task 完成一份原字节 COPY，两种库的普通复制通过。配置改地址后，旧投递在恢复
  原地址时才继续。已有取消回归验证任务取消仅生成一条通知，源文件仍可读。
- **AC-02 / RO-2。** 候选镜像用主机签发设置码并建立管理员。固定 Base 的原管理员和只读令牌权限
  经候选同库重开、恢复再验证。合用 58.1 的正式镜像首页建号、忘记密码和旧会话撤销证据。
- **AC-03 / RO-3。** 源码和正式 Compose 均先停机、备份、校验，恢复到新路径，再从现用库备份，
  恢复到已腾空的旧路径。只启 API，原会话读回相同的 Active ID、digest 和 Files 条目。Compose
  保持两处媒体挂载，Rules 对同一离线样例生成同一计划。归档的原库、现用库、源备份摘要和媒体效果
  核对通过。Python 全量与源码外 wheel 覆盖恢复权限、租约、备份适用性、非覆盖与失败原子性。
- **AC-04 / RO-4。** 源码、清单、wheel 和候选镜像均已移除旧 CLI 入口。固定 Base 场景的旧调用
  被拒绝，任务数和媒体效果保持一致。镜像在四服务启动、探针、主机发码与恢复入口拒绝 schema 11，
  原库、备份摘要一致。旧通知浏览器脚本已移除。现行浏览器从管理员会话进入通知列表，筛选并确认
  重排一条死信，正式 API 读回原投递 ID、事件、Webhook 标识与待投递状态。
- **AC-05 / RO-4。** 固定 Slice Base 用正式 Compose 创建 Automation Run once 的完成结果、
  Files 的不确定写入及等待识别的任务。候选重开原库并在离线恢复后读回原账号、权限、Task、Item、
  请求、审计和 pin。发布新 Active 后，管理员从原 Task 保存识别决定、查看零变更摘要，明确确认
  一个条目。常驻 Worker 按原 pin 只处理选定条目，已完成及效果不确定的条目未重放。

### 门禁、证据和限制

- Python 全量 2328 项，2321 通过、7 跳过。治理、Ruff、编译、依赖、样例与禁用依赖检查通过。
  Web 类型、Lint、格式、构建、1642 项单测和 289 项默认 Chromium 用例通过。真实账号用例
  覆盖首次建号、重置、会话撤销及提交回包丢失后的状态核对。
- 候选 Compose 空库、媒体挂载、重启故障、发布安全、schema 11 拒绝、二次恢复及 Base 延续验证
  通过。精确 wheel 在源码外安装并通过冒烟。镜像
  `sha256:b620c763162eb9d6912602669282bdc7aeb5b9d125361b5223a9948a257d9a28`，
  wheel SHA-256 `defb3ab85509efa274686486efb15ec7eef642ecdc0c8761a4f77a3254b893ce`。
- 真实 Python 浏览器通知及取消组 3 项、Task Center 接续组 4 项通过。此前 4 个原生整理夹具
  失败记录保留在原验收包。首项 trace 中，夹具在 Execute 响应仍进行时驱动单步 Worker，结果为
  无可领取任务，后续用例读到前一个任务的结果。本轮以通过的现行候选 Compose 和真实原 Task
  旅程验证对应合同结果。
- 本轮日志、制品标识和截图见
  `.git/validation-evidence/5415534a38bb8e23ea64a7fd2929c9e6a59a2cad/b-review/`。
  58.1 正式根页建号、忘记密码、隔离库恢复证据在
  `.git/validation-evidence/c0315d8795fb042448fdc22f1e05b1fb43fcb29f/b-review/`。
  原生整理夹具完整结果在
  `.git/validation-evidence/32c269044ad14843d37f80f9b855e0b668062daa/b-review/`。

跨版本迁移、媒体备份、Web 备份管理和新认证机制沿用合同延期边界。A 按完整 Slice 范围复审，
关闭时同步现行 V2 要求、产品旅程、架构、发布指引和接受账本。
