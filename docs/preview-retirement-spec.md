# 独立 Preview 产品退役 — Slice45（TARGET）

用户要求将独立 Preview 完整退役加入当前 Slice，退役方式与 Scan 相同。
[SLICE.md](../SLICE.md) RO-8 与 [V2-OPS-013](v2-requirements.md) 是范围和稳定验收 authority。
本设计尚未实现或验收；现有 Task45.4 Scan PASS 不覆盖此新增结果。

## 1. 用户旅程

| 环节 | 必需结果 |
|---|---|
| 目标 | 在整理或恢复界面了解计划和影响，明确确认后才变更媒体 |
| 入口 | 任务中心/Files 的整理准备、任务内恢复；CLI `organize` 的不执行模式 |
| 状态 | 当前范围、配置、完整性、来源→目标、主文件/附件、就绪/未就绪、冲突和破坏性影响 |
| 动作 | 显式分析/重新检查、查看同页摘要、选择合法就绪项、明确确认执行 |
| 成功 | 共享生产策略/计划链生成精确摘要；准备零媒体变更、零执行权限；只执行确认的固定计划/范围 |
| 失败 | 来源/计划/配置变化、缺 pin、范围不完整、Provider/Storage/权限问题逐项说明，保留其他项 |
| 恢复 | 在原界面修正并重新分析；需要新摘要/意图时明确展示，成功/未知效果不重放 |

规则对象测试、配置完整流程检查及 Automation 授权前校验继续有原本的零变更分析和解释能力，
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
Web 整理和恢复继续同页分析→摘要→精确确认→现有 Worker/OrganizerExecutor。
保留 Scanner/真实稳定观察、Parser/Recognition/Metadata/Naming/Classification/Planner、
主文件/附件计划和策略解释，以及精确来源、固定配置/计划、版本、许可、锁/fence、Result/审计。

当前内部 Preview 记录有一部分承载已被摘要/确认使用的固定计划、附件和恢复关联。
按真实职责把这些收敛到整理自己的分析/计划数据和现有持久 Task/Worker；不能简单删表丢失
计划，也不能只改名后继续保留可独立创建/调度/续跑的 Preview 产品或另建分析队列/执行引擎。
对象局部试算方法或历史结果中的 Preview 字样不等于可运行产品，不要求全仓字符串零匹配。

直接 CLI `preview` 和不执行的 `organize` 当前共用大部分处理路径；后台 Preview 另有
analysis-only 分支。合并时必须保留：分析发现只留 findings/未就绪，不产生正式执行的
WAITING_CONFIRM/Review/Conflict/Recovery 待办，不自动执行、不授予权限。
不得仅将 `preview` 映射到 `organize`，也不得把分析失败/取消或 DryRun 改写成整理成功。

## 4. 实际依赖和简单实施顺序

以下是同一完整退出目标的步骤，具体 Task 由 B 在已提交 Contract 内规划：

1. 沿实际调用列清单：`final_cli.py` 的命令/Job/schedule/continuation 与
   `_analysis_only_preview`；`service_api.py` 的独立 Preview 和整理摘要接口；V2 router 的
   PreviewNew/Detail、OrganizePreview、AutomationPreview 及 V1 UI；区分独立产品与共享分析。
2. 找到需要承接的消费者：新建整理/Files、五类恢复、Rules/配置检查、Automation 授权前校验、
   Worker 与安装/容器 harness。先将它们接入既有整理分析/固定计划服务，保留原 scope/pin/权限。
3. 将内部计划数据、版本和确认/恢复关联收敛到真实整理职责，保留原子发布、来源再验和有效
   许可绑定；长分析复用现有 Task/Worker。不得用新 Active 替换旧合法 pin。
4. 删除独立入口/类型/调度/dispatch/继续路径；清理专属服务/模型/仓储/schema/装配和无消费者
   代码。普通不支持类型错误要在发现/Provider/准入前发生，不新增 Preview 识别兼容层。
5. 去掉页面/DTO/导航/指标中的独立 Preview 产品；原配置/Rules/授权校验仍能解释并完成其
   用户结果。只清理必要 Automation 耦合，不展开冻结 Slice43 的页面/Run once/指标/设置重设计。
6. 把依赖独立 Preview 播种的测试、安装/镜像/Worker fixture 改为合法整理分析或显式 Task/计划。
   原分析零变更、权限分离、pin/来源变化、冲突/未就绪和非重放断言必须有等义覆盖。

## 5. 验收边界

- V1/V2/CLI/API/Job/定时/Worker/重试/继续均无独立 Preview 可运行入口；旧输入普通报错，
  Storage/Provider/Task/Job/执行权限/媒体变更为零，不自动转为整理，也无退役提示/兼容层。
- 临时真实 Storage 与假 Provider 通过整理准备完成完整生产分析、附件/冲突解释和同页摘要；
  未确认零媒体变更/零执行许可，未就绪不制造正式执行待办。CLI 不执行模式保持同义结果。
- 精确子集确认、来源/计划实质变化、丢响应/重复准入、合法旧 pin、成功/未知效果和混合逐项
  恢复均保持安全；同版本工作重开/重启正常，未知效果只核查。
- Rules、配置检查和 Automation 的共享分析/授权校验在无独立 Preview 装配时实际可用；
  不把定时 Preview 转成自动整理或因删除模式/默认值而产生权限。
- fresh schema、wheel/实际安装消费者、生产 Docker/常驻 Worker 和 served assets 无独立
  产品，真实整理分析→确认→执行→结果可运行；不要求旧 Preview 生产迁移/历史/V1 parity 矩阵。
- Developer 跑新增/修改与直接受影响检查；B 按 workflow 负责 T4 全量/原生/安全/产物验收。
  本次范围文档仅做治理/文档检查，不借文档变更宣称实现、T4 或 Slice 关闭。
