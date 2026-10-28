# 独立 Preview 产品退役 — Slice45（CURRENT / PASS / CLOSED）

本文件保留 Slice45 已验收的 CURRENT 退役合同；稳定要求为
[V2-OPS-013](v2-requirements.md)。完整 Contract 与验收证据见
`13ecfc0e75fc34ff0ae489e655124a178943cba4:SLICE.md`，当前状态见 [Progress](progress.md)。
后续受理/意图语义按已验收的 V2-OPS-014–017 与 V2-AUTO-010/011；下述现行说明合并这些
修订，不撤销独立 Preview 退役、共享分析和精确计划/权限边界。

## 1. 用户旅程

| 环节 | 必需结果 |
|---|---|
| 目标 | 保留共享完整分析/计划能力，通过各受支持入口的明确执行意图变更媒体 |
| 入口 | Files 手动整理、任务中心四类恢复、Automation 已保存定义；CLI `organize` 的不执行模式 |
| 状态 | 当前范围、配置、完整性、来源→目标、主文件/附件、就绪/未就绪、冲突和破坏性影响 |
| 动作 | Files/四类恢复分析后查看同页摘要、选择并明确确认；Automation 使用 checked Enabled 或显式运行一次意图，无第二次初始确认 |
| 成功 | 共享生产链产生精确固定计划，分析本身零媒体变更且不授予权限；执行受各入口的精确范围/意图/后端检查约束 |
| 失败 | 来源/计划/配置变化、缺 pin、范围不完整、Provider/Storage/权限问题逐项说明，保留其他项 |
| 恢复 | 在原界面修正并重新分析；需要新摘要/意图时明确展示，成功/未知效果不重放 |

规则对象测试、配置完整流程检查及整理执行前的内部校验继续有零变更分析和解释能力，
复用整理分析/计划服务，保留各自候选 Draft/Active、精确定义/范围、权限和配置发布边界。
分析本身不授予单次或无人值守执行权限；不要求操作者创建/管理独立 Preview Task。

## 2. 与 Scan 相同的首次部署退出方式

- 删除独立 Preview 的 V1/V2 页面/路由/导航/按钮/深链目标、API aliases/创建/查询/控制/
  导出入口、CLI 注册/帮助（含 `preview`、`batch preview`、`jobs submit preview`）。
- 删除独立 Preview Job/Task/command、通用和专用提交、定时配置/调度、Worker dispatch、
  retry/resume/continue、readiness/action 项及专用回调/运行装配、模型/仓储/schema/死代码。
  diagnostic、scheduled 或 definition-bound 的独立 Preview 也不作为保留例外。
- 旧 URL 在正常认证边界下走普通 not-found；旧命令/配置值走普通参数/不支持类型错误；
  共享支持类型校验在 Storage/Provider/工作准入/许可前停止。不保留退役页、410、专用错误/
  guard、隐藏别名或兼容执行器，不把旧 Preview 输入自动转成 Organize。
- 不建设旧 Preview 的停止/在途接管、升级迁移、历史页面/API/取消/导出、V1 parity 或数据
  转换/双写框架。不为开发 fixture 保留独立产品；不清空、drop 或重建现存运行库、媒体或 Git。
  新建受支持环境不创建独立 Preview 产品专用 schema；共享计划/任务存储正常重开和安全仍需验证。

## 3. 保留并统一的能力

`mediaflow organize` 不带 `--execute` 仍提供零媒体变更的完整分析/计划结果。
Web Files 整理/四类恢复的摘要明确复用 Organize DryRun 的共享应用层分析/计划链，
与 CLI 不执行模式共用应用行为，并保留各入口实际来源范围、固定配置与策略选择。
API 直接调用该应用服务，不启动 CLI 命令，不另建分析引擎或保留独立 Preview 服务生命周期。
Files/四类恢复流程为共享分析→持久完整固定计划→同页摘要→精确确认→重验计划/来源/
权限→现有 Worker/OrganizerExecutor 执行。Automation 的初始意图由 checked Enabled 或运行
一次命令提供，同样在后端完整分析/规划和安全校验后才可变更；业务阻塞使用四类恢复。
仅保存摘要文本不能作为执行依据；计划或来源实质变化须重新分析、更新摘要并重新确认。
共享 DryRun 遵循下方 analysis-only 规则，仅分析不创建正式执行待办或权限。
保留 Scanner/真实稳定观察、Parser/Recognition/Metadata/Naming/Classification/Planner、
主文件/附件计划和策略解释，以及精确来源、固定配置/计划、版本、许可、锁/fence、Result/审计。

整理内部计划记录承载摘要/确认使用的固定计划、附件和恢复关联，复用现有持久 Task/Worker。
内部 `manual_previews` 名称及整理计划 API 不代表独立产品；没有可独立创建/调度/续跑的
Preview 生命周期，也没有另一套分析队列/执行引擎。
对象局部试算方法或历史结果中的 Preview 字样不等于可运行产品，不要求全仓字符串零匹配。

独立 CLI `preview` 已删除，不执行的 `organize` 和后台整理分析共用生产分析/计划路径。
独立 analysis-only 发现只留 findings/未就绪，不产生正式执行待办，不自动执行或授予权限。
明确 Files 整理/Automation 运行一次已受理的 Task 则拥有其发现/分析和真实四类问题；
阶段是分析不代表它退回独立准备，决定保存/分析完成也不代表有权执行恢复。
不得仅将 `preview` 映射到 `organize`，也不得把分析失败/取消或 DryRun 改写成整理成功。

## 4. 当前消费者与运行边界

Files 整理、四类恢复、Rules/配置检查和 Automation 内部规划复用共享生产分析与
固定计划服务，保持各入口原 scope/pin/策略/权限；Web 不通过 CLI 绕行。长分析使用既有
discovery Worker，完整计划原子发布后才生成摘要，已生效的取消不接受迟到的新计划。
原来源重验、精确许可、成功兄弟项及未知效果非重放保持。

Web/API/CLI/Job/调度/dispatch/继续的独立产品及专用模型/仓储/schema/装配已退出。
fixture 使用受支持准入、实际 Worker 或明确的投影 Task/Result，不通过放开权限、删除安全
断言或恢复退役执行器满足验收。支持的共享 Automation 授权/执行仍需明确许可；
Automation 的验收状态见 [Progress](progress.md)，当前授权修订见 [SLICE.md](../SLICE.md)。

## 5. 验收边界

- V1/V2/CLI/API/Job/定时/Worker/重试/继续均无独立 Preview 可运行入口；旧输入普通报错，
  Storage/Provider/Task/Job/执行权限/媒体变更为零，不自动转为整理，也无退役提示/兼容层。
- 临时真实 Storage 与假 Provider 通过整理准备完成完整生产分析、附件/冲突解释和同页摘要；
  Files/四类恢复未确认零媒体变更；独立分析无执行许可/正式待办。明确受理的 Task 保留
  真实问题；Automation 的执行意图与初始确认按上述已接受修订。CLI 不执行模式保持零变更。
- 精确子集确认、来源/计划实质变化、丢响应/重复准入、合法旧 pin、成功/未知效果和混合逐项
  恢复均保持安全；同版本工作重开/重启正常，未知效果只核查。
- Rules、配置检查和 Automation 的共享分析/授权校验在无独立 Preview 装配时实际可用；
  不把定时 Preview 转成自动整理或因删除模式/默认值而产生权限。
- fresh schema、wheel/实际安装消费者、生产 Docker/常驻 Worker 和 served assets 无独立
  产品，真实整理分析→确认→执行→结果可运行；不要求旧 Preview 生产迁移/历史/V1 parity 矩阵。
- Developer 跑新增/修改与直接受影响检查；B 按 workflow 负责 T4 全量/原生/安全/产物验收。
  本文状态依据整 Slice 的实际验收及产物身份更新，原始证据与复用/跳过说明见 Closure Packet。
