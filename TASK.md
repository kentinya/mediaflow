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

## Developer 修正交接 — P1 并发 Webhook 创建冲突

```text
Candidate: 1374f356a30dd094c44476f591cc46f643aa908d
Fix range: 9b5ac2ee91a43f1ef3a51067e87250582c5fefd9..1374f356a30dd094c44476f591cc46f643aa908d
Task range: 9027e0a0384bae8c28971d24e5dd666604e5a6f9..1374f356a30dd094c44476f591cc46f643aa908d
```

- 已知版本冲突时保留全部未提交输入，清除旧签名测试结论，停止保存与重测。错误提示说明本次未创建，
  并在原位置提供「读取最新配置」。读取复用当前 Webhook 列表查询，只做有界 GET；成功后显示最新版本并
  要求重新测试，测试成功后才重新开放保存。读取失败继续使用原「最新读取失败」提示和重试入口，表单
  与已知命令结果不被替换。未知回包的原请求核对路径未改动。
- 新增 `recovers a concurrent Webhook creation conflict`：两个真实浏览器会话，第一会话填写并测试，
  第二会话从「系统设置 → 常规设置 → 日志」保存新的保留值。第一会话保存收到真实 409，服务端未创建
  定义，标识符、地址、密钥引用与高级字段保留；读取最新配置只发 GET；重新测试后保存并打开新定义，
  列表和 API 都只有一条该定义。
- 实际执行（`web/`，候选 `1374f356a30dd094c44476f591cc46f643aa908d`）：
  - `npm run typecheck` → PASS。
  - `npm run build` → PASS；310 modules，产物 `index-BFSWBVEx.js` 1,582.41 kB（既有大包提示）。
  - `npm run test:e2e -- --config playwright.python.config.ts operations-inventory.python.spec.ts --grep 'recovers a concurrent Webhook creation conflict|a new Notification publication reconciles'` → 2 passed。
  - `npm run test:e2e -- notifications.spec.ts` → 11 passed。
  - `npm run test -- run src/features/operations/NotificationRouter.test.tsx` → 8 passed（仅既有 jsdom `scrollTo` 提示）。
  - `npx prettier --check` 两个改动文件、`npm run lint -- --quiet`、`git diff --check` → PASS。
- 剩余风险：Developer 未运行全量 Python/Web/E2E 与打包矩阵，按 Task 由 B 执行；未发现本修正范围内的
  已知未覆盖入口。新增旅程依赖计数器在隔离 harness 内的当前日志保留值，取相邻合法值完成真实发布。

## B 复审

```text
Reviewed: 9027e0a0384bae8c28971d24e5dd666604e5a6f9..5be5ce847c30a2d2aca767d858763b83f807ef76
Decision: FIX REQUIRED
Authorized bug acceptance complete: NO
Next: SAME TASK FIX LOOP
```

- 保存冲突已能在原卡片恢复。真实 Python Chromium 复验了读取、重测和单次成功创建，也通过了回包丢失后的原请求核对。桌面与 390px 设置、通知及规则初始化 Chromium 18 项、真实设置 Chromium 10 项、Webhook Chromium 2 项通过。生产构建和类型检查通过。
- **P1 · 签名测试遭遇配置版本变化时，原表单缺少读取入口。** 在 390px 从「通知 → 新建 Webhook」填写表单。另一会话从「系统设置 → 常规设置 → 日志」保存后，原表单第一次发送签名测试收到 HTTP 409。页面把变化归因于表单，提示重试。再按一次仍收到 409，表单中没有读取入口，保存保持不可用。`NotificationNewPage.tsx` 目前只在保存冲突时显示恢复入口。复现日志与截图见 `.git/validation-evidence/5be5ce847c30a2d2aca767d858763b83f807ef76/b-review/` 的 `test-conflict.log` 和 `test-conflict-results/`。

## Developer 修复指导 · 签名测试阶段

1. 新建卡收到签名测试的 `configuration_version_conflict` 时，说明生效配置已更新、本次测试请求未发往接收方。复用原卡片已有的「读取最新配置」动作。保留已填字段。读取成功后，用户显式重测并在测试通过后保存。
2. 在 `operations-inventory.python.spec.ts` 的双会话旅程中覆盖两种顺序。第二会话在第一次签名测试前保存，以及在签名测试通过后、创建前保存。两条旅程都能在卡片内读取，读取只发 GET，完成后各有一条新定义。保留原请求核对用例。测试名称沿用 `recovers a concurrent Webhook creation conflict`，执行上一轮修复指导中的命令。

B 在新候选上复验两种顺序并重跑指定验收。
