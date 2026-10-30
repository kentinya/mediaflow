# Task PATCH-20261030-4 — 自动化工作区视觉与信息层级修正

Authority: 用户 2026-10-30 在只读调查后明确授权删除说明、统一控件及跨页风格、
精简执行记录/全局设置，并按任务中心和文件页统一左上角标题。
生命周期遵循 [Development Workflow](docs/development-workflow.md#31-independent-minor-bugs)。

```text
Task ID: PATCH-20261030-4
Task Type: STANDALONE MINOR BUG
Parent Slice: NONE
Status: READY FOR B REVIEW
Task Base: 62beb31fdefe738c4fc90d2229bf3051fe3ec931
Difficulty: Medium
Test Level: T2
Planner / Reviewer: B
```

## Goal

修正现有自动化页首屏被说明占据、控件样式脱节、重复中英文标题、执行记录行过长和
四字段设置冗长的问题。沿用任务列表/执行记录/全局设置入口、真实数据、查询、保存与
失败恢复行为，仅调整展示；不重开 Slice46。

## Implementation Scope

1. 删除统计说明、使用说明、引擎介绍、调度/时区教程与 JSON 示例。统计保持服务端
   口径及缺失状态；状态、失败原因、效果与明确下一步不能随说明删除而丢失。
2. 自动化主工作区仅一个中文标题，内容边界、标题、卡片、标签页、表单与按钮协调
   任务中心/文件页。样式限定自动化，共享 Shell 仅改重复标题条件。
3. 记录列表显示简短时间、状态、条目与主要查看入口；完整时间/失败阶段/逐项效果/
   后续处理放入可展开详情；保持只读、精确路由及原列表返回上下文。
4. 设置四字段紧凑排列，保留字段含义/后端约束、已发布与已采用区别；实例诊断折叠，
   异常状态保持可见。保存/并发/未知结果核对机制原样保留。

## Acceptance Criteria

- [x] 三个分区无长篇统计/教程说明，仅一个主内容标题，首屏可达主要内容。
- [x] 桌面与窄屏控件、标签页、标题协调其他页，无页面横向溢出；焦点可见。
- [x] 记录紧凑，可展开完整证据，正确进入对应任务/定义；无新执行或恢复命令。
- [x] 设置字段、保存/只读/冲突/失败/未知提交与真实消费状态保持可用。
- [x] 无 API、权限、统计口径、调度/执行、数据模型、Slice/Roadmap/Progress 修改。

## Required Tests

Developer（受影响范围；cwd `web/`）：
- `npm run test -- run src/features/operations/AutomationRouter.test.tsx src/features/operations/AutomationWorkspaceReadModel.test.tsx src/features/operations/AutomationSettingsPage.test.tsx src/shared/ui/AppShell.test.tsx`。
- `npm run typecheck`、`npm run lint`、修改文件 Prettier、`npm run build`。
- Node 隔离 API 的 `automation.spec.ts` 和本 Task 桌面/窄屏布局用例；实际查看截图。
- `python3 scripts/check_governance.py`、`git diff --check`。

B 独立验收候选 Base..Head：上述功能/布局与相关 Settings 恢复测试，真实 Python
`automation-workspace.python.spec.ts` / `automation-settings.python.spec.ts` 相关旅程；
核对 Shell 标题不影响 Files/任务中心、记录展开证据与安全入口。无全仓回归要求。

## Non-goals

不改后端文案/历史授权语义，不新增自动化能力、不改变业务流程；不改其他页设计，
不部署、不推送、不自审 PASS。

## Workspace

`main`，初始 HEAD 为 Task Base；无已跟踪文件修改。预存未跟踪日志、DS_Store、`15`、
参考图与 imagegen zip 原样保留；初始清单在本机
`.git/validation-evidence/PATCH-20261030-4/baseline.txt`。

## Developer Completion Report

Status: READY FOR B REVIEW。实现 checkpoint 见本 Task 后续提交的精确 SHA。

- 已删除长说明/教程/JSON 示例和重复英文主标题；共享任务中心标题边界/标签页样式。
  控件使用现有浅色主题，桌面五列、窄屏两列筛选；记录时间本地化且精确值保留。
- 记录默认仅显示摘要，独立展开完整结果/时间/失败/效果/后续处理；路由入口不变且无
  新执行命令。四字段设置双列展示，保留后端范围、发布/采用区分及全部保存核对机制。
- 组件/路由/Shell/Settings 受影响回归 **62/62**；Node 假 API 浏览器功能与布局
  **15/15**，最后 CSS/截图调整后的桌面/390px 布局复查 **2/2**。新用例检查只读展开、
  收起、焦点、无页面横向溢出、记录行高度及完整失败证据，已人工查看六张最终截图。
- `npm run typecheck`、`npm run lint`、修改文件 Prettier、`npm run build`、governance、
  `git diff --check` 通过；构建仍报告 bundle 大小提示，无构建错误。
- 首轮组件 5 项失败：旧入口/旧展开状态断言不符，另有指标不可用下一步遗漏及采用
  状态重复；已恢复动态失败提示、去重并按真实展开入口验证完整证据。首轮浏览器另有
  JSON ESM 导入及展开后 locator 名称变化；均已修正，不添加重试/放宽超时。
- 本机原始日志：`.git/validation-evidence/PATCH-20261030-4/` 的 `components.log`、
  `browser.log`、`layout-final.log`、`lint.log`、`build.log`；最终六张截图在其 `screenshots/`。
- 证据限 Chromium、1536/390px 与隔离 Node API；真实 Python 验收按计划交 B，未宣称
  全仓/容器/外部服务通过。无部署/推送；预存未跟踪文件未包含在提交中。独立 B 审查待办。
