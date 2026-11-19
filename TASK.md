# Task PATCH-20261119-1 — 删除顶栏占位铃铛

用户于 2026-11-19 授权激活独立 Task，待 Developer 开始实施。[开发工作流](docs/development-workflow.md#31-independent-minor-bugs)

```text
Task ID: PATCH-20261119-1
Task Type: STANDALONE MINOR BUG
Parent Slice: NONE
Status: PLANNED
Task Base: dfb2388551d18fc8e751953532def26188b89941
Difficulty: Low
Test Level: T2
Planner / Reviewer: B
Implementation Authorization: USER AUTHORIZED ON 2026-11-19
```

### 目标与现状

用户在任一页面使用共享顶栏时，只看到可以操作的账户入口及适用的搜索框。当前的「通知」按钮
可以获得焦点，但点击无动作。需要管理 Webhook 或查看投递记录时，用户从侧栏「通知」进入
`/operations/notifications`，并在该页面处理投递失败与恢复。[共享顶栏](web/src/shared/ui/AppShell.tsx)

### 实施范围与步骤

1. 从共享顶栏删除铃铛按钮节点和专用 `bell` 类型与 SVG 分支。保留侧栏独立使用的
   `notification` 图标。铃铛直接删除，不做兼容，不隐藏，也不设置替代占位。
2. 删除 `.mf-notification-button` 专用规则和为铃铛预留的操作区宽度、间距及对应窄屏覆盖。
   保持账户控件靠右，保留已连接时的断开操作、未连接时的连接入口以及文件和存储页的搜索绑定。
3. 将 `AppShell.test.tsx`、`rules-readiness.spec.ts` 和 `rules_workspace_browser_proof.py`
   中共五处要求铃铛可见的断言改为检查顶栏节点数量为零。相关用例同时保留账户入口、搜索布局
   或工作区自身的断言。同步修订脚本描述及文档中的 `V2-EXPLORE-013`、探索和规则体验、
   规则顶栏架构说明及文件页顶栏描述。[V2 需求](docs/v2-requirements.md) ·
   [产品体验](docs/product-experience.md) · [架构](docs/architecture.md) ·
   [文件页视觉规范](docs/file-page-visual-spec.md)

### 验收标准

- [ ] 共享顶栏在连接前后、普通切页和刷新后均不存在铃铛按钮节点。DOM 检查包括隐藏节点，
  键盘导航直接到实际可用的控件。生产源码移除专用 `bell` 分支、铃铛 CSS 和占位尺寸。
- [ ] 在 1536px 和 390px 宽度下检查文件页与整理规则页。文件搜索可输入，账户控件可达并靠右，
  整理规则页保留其工作区搜索布局，顶栏无横向溢出。点击断开后回到连接入口。
- [ ] 从侧栏进入「通知」可读取 Webhook 定义和投递记录。通知页面与深链继续使用现有权限和恢复流程。
  当前规范和验证脚本均描述同一顶栏行为。

### Developer 受影响检查

- 在 `web/` 运行 `npm run typecheck` 和 `npm run test -- run src/shared/ui/AppShell.test.tsx`，
  验证图标类型以及探索、任务中心、整理规则中的共享顶栏。
- 在 `web/` 运行 `npm run build`，再运行
  `npm run test:e2e -- tests/e2e/rules-readiness.spec.ts -g 'Rules reference-aligned workspace presentation'`。
  在该组内覆盖两种宽度下的 DOM 缺席、文件搜索和账户控件，保留规则原有断言。
- 在仓库根目录运行
  `.venv/bin/ruff check scripts/rules_workspace_browser_proof.py` 和 `git diff --check`，
  并检查生产源码中 `mf-notification-button` 和 `"bell"` 的搜索结果为空。

### B 独立验收

- 在候选构建上独立复跑上述顶栏浏览器用例，核对桌面和窄屏、刷新与键盘顺序。
  在 `web/` 运行 `npm run test:e2e -- tests/e2e/notifications.spec.ts`，验证侧栏入口、深链重连、
  Webhook 与投递记录的现有旅程。
- 审查完整 Task Base 到候选的差异及当前规范，记录实际结果和 `PASS` 或 `FIX REQUIRED`。
  T2 验收覆盖共享顶栏与直接依赖它的 Web 旅程。

### 边界

修改范围限于共享顶栏及直接相关的样式、测试和当前规范。以现有账户和通知旅程作为回归验收。
