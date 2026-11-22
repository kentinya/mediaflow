# Task PATCH-20261122-2 — 简化设置和通知页面

```text
Task ID: PATCH-20261122-2
Task Type: STANDALONE MINOR BUG
Parent Slice: NONE
Status: FIX REQUIRED
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

## B 复核

```text
Reviewed: 9027e0a0384bae8c28971d24e5dd666604e5a6f9..a915f6465e28777bb5f7d09048440da326d7919a
Decision: FIX REQUIRED
Authorized bug acceptance complete: NO
Next: SAME TASK FIX LOOP
```

- 桌面和 390px 首屏可达主要入口。设置分区切换保留输入且零业务写入。设置及通知 Chromium 16 项、真实 Python 设置 Chromium 10 项，以及规则页进入设置完成初始化并返回的 Chromium 1 项通过。生产构建和 TypeScript 检查通过，构建提示有大包。
- **P1 · 新建 Webhook 被拒后无法在原表单重新读取配置。** 在 390px 从「通知 → 新建 Webhook」填写并通过签名测试。另一会话从「系统设置 → 常规设置 → 日志」保存后，原表单的保存被服务端拒绝，提示重新读取。表单保留了输入，但没有读取入口，直接重测也被拒绝。候选提交删掉了原卡片内的「读取最新配置状态」。
- 本机日志和截图保存在 `.git/validation-evidence/a915f6465e28777bb5f7d09048440da326d7919a/b-review/`。首跑并发复现使用了错误的侧栏定位并超时，修正后 `webhook-conflict-repro.log` 记录两次 HTTP 409 和卡片读取入口断言失败。

## Developer 修复指导

1. 在 `NotificationNewPage.tsx` 的已知版本冲突提示旁提供「读取最新配置」，复用当前 Webhook 列表查询。保留标识符、地址、密钥引用、事件和高级字段。提示说明这次未创建，以及读取后需重新测试。
2. 冲突后清除旧签名测试结论。读回最新配置后，允许用户显式重测。签名测试通过后才开放保存。使用原有读取失败提示和原请求核对路径。
3. 在 `web/tests/e2e/operations-inventory.python.spec.ts` 用两个真实浏览器会话走上述旅程。断言首次保存未创建定义，重新读取只发 GET，表单输入保留。用户再次测试、保存后打开刚创建的定义，列表只有一条该定义。用测试名称 `recovers a concurrent Webhook creation conflict`，在 `web/` 跑 `npm run test:e2e -- --config playwright.python.config.ts operations-inventory.python.spec.ts --grep 'recovers a concurrent Webhook creation conflict|a new Notification publication reconciles'`、`npm run test:e2e -- notifications.spec.ts` 和 `npm run typecheck`。运行 Chromium 前构建生产产物。

B 在修正候选独立复核新增并发旅程，并重跑本 Task 的两组指定 Chromium 验收。
