# Task PATCH-20261122-2 — 简化设置和通知页面

```text
Task ID: PATCH-20261122-2
Task Type: STANDALONE MINOR BUG
Parent Slice: NONE
Status: PLANNED
Task Base: 9027e0a0384bae8c28971d24e5dd666604e5a6f9
Difficulty: Medium
Test Level: T3
Planner / Reviewer: B
```

## 目标

从系统设置直接找到要改的内容，从通知直接新建 Webhook 或查看投递记录。在 390px 实测中，设置的常用入口要划过状态卡和运行证据才能到达，通知的主要操作位于技术摘要之后，新建时测试又排在填写之前。

## 范围

1. 设置按用途选择内容，删去常驻状态卡、重复说明和字段旁的冗余文字。首次设置、故障恢复和实际采用异常就近显示。
2. 通知沿用现有工作区的标题和分区样式。定义和投递使用同一页面框架，去掉重复标签和发布说明。表单按填写、测试、保存排列。
3. 使用现有 API、权限、路由和写入流程。保留未提交输入、原请求核对、令牌明文一次性展示、Webhook 测试和逐条投递恢复。

## 验收与测试

- 桌面和 390px 首屏可直接选择设置区域、新建 Webhook 或打开投递。读取和切换分区零业务写入，返回原设置分区可继续编辑。
- 设置真实的生效、失败与后续动作可辨，首次初始化和完整替换可达。令牌和通知现有签发、保存、测试及投递的结果和错误继续有对应处理。
- Developer 在 `web/` 运行受影响 Vitest、TypeScript 类型检查、生产构建及设置和通知 Chromium 回归，并核对桌面和窄屏。
- B 独立审查完整差异，在 `web/` 运行 `npm run test:e2e -- configuration-settings.spec.ts notifications.spec.ts`，以及 `npm run test:e2e -- --config playwright.python.config.ts configuration-settings.python.spec.ts`，核对初始化、运行设置、令牌及发布恢复。核对两页的首屏、真实分区切换和零业务写入。
