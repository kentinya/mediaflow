# Task 58.2 — 通用 CLI 与配置 schema 11 退出

Next Action: B PLANS THE A58-01 CORRECTION

```text
Task ID: 58.2
Task Type: SLICE
Parent Slice: 58
Status: FIX REQUIRED
Task Base: 307eaaf8b006527a11fa2514de839a5528e6c202
Difficulty: High
Test Level: T4
Implementation Authorization: ORIGINAL TASK SCOPE; B CORRECTION PLAN PENDING
```

## A 终审退回

**A58-01（P1，RO-3 / AC-03）。** 按发布指引将同版本 SQLite 备份恢复到新文件，原账号和原配置
记录可读，但资源库 Files 返回 `503 configuration_unavailable`。恢复后的 bootstrap 数据库定位与
原快照中的定位不一致。原 Compose 指引中的启动命令还会丢掉部署原有媒体挂载。
[复现、证据及通过条件](SLICE.md#a-final-review--fix-required)

B 在原目标、范围和 T4 下规划修正，独立验证新候选并重交 Slice 58 Closure Packet。原计划与
验收范围见 `32c269044ad14843d37f80f9b855e0b668062daa:TASK.md`；B 对原候选的 PASS 与最终
验收包见 `435a0b42904765820c85cc71cb904c14bf66f10e:TASK.md`。
