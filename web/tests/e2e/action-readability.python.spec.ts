/**
 * Readable V2 actions and login (Slice 46, Task 46.1 RO-1 / AC-1).
 *
 * Run under `playwright.python.config.ts` after `npm run build`:
 *
 *   npm run test:e2e -- --config=playwright.python.config.ts \
 *     tests/e2e/action-readability.python.spec.ts
 *
 * Every assertion here reads the **rendered** state from the real production
 * bundle served by the isolated real-Python harness: computed colors are
 * composited through the whole ancestor chain (so a transparent button on a
 * tinted row resolves to the surface actually painted), and the effective
 * opacity of the element plus its ancestors is part of the measured result.
 * Source-only hex/selector checks cannot prove any of that, so this spec
 * measures contrast, focus visibility and busy/disabled truth directly.
 *
 * Screenshots are written under `test-results/action-readability/` (an ignored
 * test-output path); no binary evidence is committed.
 */

import { expect, test, type Page, type Locator } from "@playwright/test";
import { mkdirSync, writeFileSync } from "node:fs";

const ADMIN_TOKEN = "harness-admin-token";
const READONLY_TOKEN = "harness-viewer-token";
const BASE = "http://127.0.0.1:4183";
const OUTPUT = "test-results/action-readability";
const MIN_CONTRAST = 4.5;
const MIN_LARGE_CONTRAST = 3;

/** Runs in the page: composite the real painted colors and measure contrast. */
const MEASURE = `
  (element) => {
    const numbers = (value) => {
      const parts = (value || "").match(/[\\d.]+/g);
      return parts ? parts.map(Number) : [];
    };
    const toRgba = (value) => {
      const parts = numbers(value);
      if (parts.length < 3) return null;
      return {
        r: parts[0],
        g: parts[1],
        b: parts[2],
        a: parts.length > 3 ? parts[3] : 1,
      };
    };
    const over = (front, back) => {
      const a = front.a + back.a * (1 - front.a);
      if (a === 0) return { r: 0, g: 0, b: 0, a: 0 };
      return {
        r: (front.r * front.a + back.r * back.a * (1 - front.a)) / a,
        g: (front.g * front.a + back.g * back.a * (1 - front.a)) / a,
        b: (front.b * front.a + back.b * back.a * (1 - front.a)) / a,
        a,
      };
    };
    const computed = window.getComputedStyle(element);
    let visible = toRgba(computed.color);
    let backdrop = { r: 0, g: 0, b: 0, a: 0 };
    let node = element;
    let opacity = 1;
    while (node) {
      const style = window.getComputedStyle(node);
      const background = toRgba(style.backgroundColor);
      // Opacity composites a whole element subtree onto its parent: apply it
      // to both pixels (text and adjacent background), before the parent fill.
      visible = over(visible, background);
      backdrop = over(backdrop, background);
      const alpha = Number(style.opacity);
      visible.a *= alpha;
      backdrop.a *= alpha;
      opacity *= alpha;
      node = node.parentElement;
    }
    const canvas = { r: 255, g: 255, b: 255, a: 1 };
    visible = over(visible, canvas);
    backdrop = over(backdrop, canvas);
    const channel = (value) => {
      const s = value / 255;
      return s <= 0.03928 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
    };
    const luminance = (c) =>
      0.2126 * channel(c.r) + 0.7152 * channel(c.g) + 0.0722 * channel(c.b);
    const lighter = Math.max(luminance(visible), luminance(backdrop));
    const darker = Math.min(luminance(visible), luminance(backdrop));
    const fontSize = Number.parseFloat(computed.fontSize);
    const fontWeight = Number(computed.fontWeight) || 400;
    const rect = element.getBoundingClientRect();
    return {
      contrast: Math.round(((lighter + 0.05) / (darker + 0.05)) * 100) / 100,
      largeText: fontSize >= 24 || (fontSize >= 18.66 && fontWeight >= 700),
      color: computed.color,
      backdrop:
        'rgb(' + Math.round(backdrop.r) + ',' + Math.round(backdrop.g) +
        ',' + Math.round(backdrop.b) + ')',
      opacity: Math.round(opacity * 100) / 100,
      outlineStyle: computed.outlineStyle,
      outlineWidth: computed.outlineWidth,
      outlineColor: computed.outlineColor,
      disabled: element.disabled === true,
      ariaBusy: element.getAttribute("aria-busy"),
      width: Math.round(rect.width),
      height: Math.round(rect.height),
      text: (element.textContent || "").trim().slice(0, 40),
    };
  }
`;

type Measured = {
  readonly contrast: number;
  readonly largeText: boolean;
  readonly color: string;
  readonly backdrop: string;
  readonly opacity: number;
  readonly outlineStyle: string;
  readonly outlineWidth: string;
  readonly outlineColor: string;
  readonly disabled: boolean;
  readonly ariaBusy: string | null;
  readonly width: number;
  readonly height: number;
  readonly text: string;
};

async function measure(page: Page, selector: string): Promise<Measured> {
  return (await page
    .locator(selector)
    .first()
    .evaluate(
      new Function(`return (${MEASURE})(arguments[0]);`) as never,
    )) as Measured;
}

/** Assert one measured action is readable for its own text size. */
const readings: { label: string; measured: Measured }[] = [];

function expectReadable(label: string, measured: Measured): void {
  readings.push({ label, measured });
  const floor = measured.largeText ? MIN_LARGE_CONTRAST : MIN_CONTRAST;
  expect(
    measured.contrast,
    `${label} rendered ${measured.contrast}:1 (${measured.color} on ${measured.backdrop}, effective opacity ${measured.opacity}); needs ${floor}:1`,
  ).toBeGreaterThanOrEqual(floor);
}

/** Exercise existing controls without dispatching clicks or submitting work. */
async function expectActionStates(
  action: Locator,
  label: string,
): Promise<void> {
  const read = async (state: string) => {
    const measured = (await action.evaluate(
      new Function(`return (${MEASURE})(arguments[0]);`) as never,
    )) as Measured;
    expectReadable(`${label} · ${state}`, measured);
    return measured;
  };
  await expect(action).toBeVisible();
  await action.page().mouse.move(0, 0);
  await action.evaluate((element) => (element as HTMLElement).blur());
  await read("normal");
  await action.hover();
  await read("hover");
  if (await action.isEnabled()) {
    await action.page().mouse.move(0, 0);
    await action.page().keyboard.press("Tab");
    await action.focus();
    const focused = await read("keyboard focus");
    expect(focused.outlineStyle).not.toBe("none");
    expect(Number.parseFloat(focused.outlineWidth)).toBeGreaterThanOrEqual(2);
    await action.evaluate((element) => (element as HTMLElement).blur());
  }
}

/** Every visible action on the surface, measured where it is really painted. */
async function expectSurfaceReadable(
  page: Page,
  surface: string,
): Promise<number> {
  const selector =
    'button:visible, a.mf-button:visible, [role="menuitem"]:visible';
  // The modal owns interaction while open; its backdrop dims/inerts the page.
  // Measure the reachable dialog rather than controls behind a sibling overlay.
  const dialog = page.getByRole("dialog");
  const actions =
    (await dialog.count()) > 0
      ? dialog.locator(selector)
      : page.locator(selector);
  const total = await actions.count();
  expect(total, `${surface} exposes no actions to measure`).toBeGreaterThan(0);
  for (let index = 0; index < total; index += 1) {
    const action = actions.nth(index);
    const name =
      (await action.getAttribute("aria-label")) ??
      (await action.textContent()) ??
      "(icon action)";
    const measured = (await action.evaluate(
      new Function(`return (${MEASURE})(arguments[0]);`) as never,
    )) as Measured;
    expectReadable(`${surface} · ${name.trim().slice(0, 30)}`, measured);
    expect(
      measured.width + measured.height,
      `${surface} · "${name.trim().slice(0, 30)}" has no painted box`,
    ).toBeGreaterThan(0);
  }
  return total;
}

async function connect(page: Page, token = ADMIN_TOKEN): Promise<void> {
  await page.getByLabel("API token").fill(token);
  await page.getByRole("button", { name: "Connect", exact: true }).click();
}

/**
 * Focus one real control the way a keyboard operator reaches it. The shared
 * `:focus-visible` ring only paints under keyboard modality, so a real key
 * event is part of arriving at the state being measured.
 */
async function focusByKeyboard(
  page: Page,
  selector: string,
): Promise<Measured> {
  const target = page.locator(selector).first();
  await page.keyboard.press("Tab");
  await target.focus();
  return (await target.evaluate(
    new Function(`return (${MEASURE})(arguments[0]);`) as never,
  )) as Measured;
}

async function openSurface(page: Page, path: string): Promise<void> {
  await page.goto(`/ui-v2${path}`);
  if ((await page.getByLabel("API token").count()) > 0) {
    await connect(page);
  }
  await expect(page.locator("#main-content")).toBeVisible();
  // Let the surface's own authorized reads settle before measuring actions.
  await page.waitForTimeout(400);
}

test.describe("readable V2 actions", () => {
  test.beforeEach(() => {
    readings.length = 0;
  });
  test.afterEach(async ({ page }, testInfo) => {
    const path = `${OUTPUT}/${testInfo.title.replace(/[^a-z0-9]+/gi, "-")}.json`;
    writeFileSync(path, JSON.stringify({ url: page.url(), readings }, null, 2));
    await testInfo.attach("rendered-action-states", {
      path,
      contentType: "application/json",
    });
  });
  test.beforeAll(() => {
    mkdirSync(OUTPUT, { recursive: true });
  });

  test("Entry field, Connect and validation states are readable and bounded", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1536, height: 1024 });
    await page.goto("/ui-v2/");

    // The token field and its label are part of the same login journey.
    const field = await measure(page, "#api-token");
    expectReadable("Entry token field value", field);

    const fieldLabel = await measure(page, "label[for='api-token']");
    expectReadable("Entry token field label", fieldLabel);

    const connectAction = await measure(
      page,
      "form.mf-entry button[type='submit']",
    );
    expectReadable("Entry Connect", connectAction);
    expect(connectAction.disabled).toBe(false);
    await page.screenshot({ path: `${OUTPUT}/entry-desktop.png` });
    await expectActionStates(
      page.getByRole("button", { name: "Connect", exact: true }),
      "Entry Connect",
    );
    // Entry has no placeholder or asynchronous submitting state in production.
    await expect(page.getByLabel("API token")).not.toHaveAttribute(
      "placeholder",
    );
    await page.setViewportSize({ width: 390, height: 844 });
    await expectActionStates(
      page.getByRole("button", { name: "Connect", exact: true }),
      "Entry narrow Connect",
    );
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    await page.screenshot({ path: `${OUTPUT}/entry-narrow.png` });
    await page.setViewportSize({ width: 1536, height: 1024 });

    // Invalid input is rejected by the real form; the alert stays readable.
    await page.getByRole("button", { name: "Connect", exact: true }).click();
    const alert = page.getByRole("alert");
    await expect(alert).toBeVisible();
    await expect(alert).toContainText("Enter an API principal token");
    await expect(page.getByLabel("API token")).toBeVisible();
    const alertTitle = await alert
      .locator("h2")
      .first()
      .evaluate(new Function(`return (${MEASURE})(arguments[0]);`) as never);
    expectReadable("Entry validation alert", alertTitle as Measured);
    await page.screenshot({ path: `${OUTPUT}/entry-invalid.png` });

    // A valid temporary token connects and continues to the recorded route.
    await page.goto("/ui-v2/operations");
    await expect(page.getByLabel("API token")).toBeVisible();
    await connect(page);
    await expect(page).toHaveURL(/\/ui-v2\/operations$/);
    // The credential is memory only: no browser storage carries it.
    const storage = await page.evaluate(() => ({
      local: JSON.stringify(window.localStorage),
      session: JSON.stringify(window.sessionStorage),
      cookies: document.cookie,
      url: window.location.href,
    }));
    expect(storage.local).not.toContain(ADMIN_TOKEN);
    expect(storage.session).not.toContain(ADMIN_TOKEN);
    expect(storage.cookies).not.toContain(ADMIN_TOKEN);
    expect(storage.url).not.toContain(ADMIN_TOKEN);

    // Connected/disconnect actions on the Entry surface are readable too. The
    // post-connect continuation already left the root form behind, so the
    // connected state is reached the way an operator returns to it.
    await page.goBack();
    await expect(
      page.getByRole("heading", { name: "Connected" }),
    ).toBeVisible();
    await expectSurfaceReadable(page, "Entry connected");
    const disconnect = await measure(
      page,
      ".mf-status-success .mf-button-secondary",
    );
    expectReadable("Entry Disconnect", disconnect);
    await page.screenshot({ path: `${OUTPUT}/entry-connected.png` });

    // Disconnect returns to the readable entry form without a stale route.
    await page
      .locator(".mf-status-success")
      .getByRole("button", { name: "Disconnect", exact: true })
      .click();
    await expect(page.getByLabel("API token")).toBeVisible();
    const afterDisconnect = await measure(page, "#api-token");
    expectReadable("Entry field after disconnect", afterDisconnect);
  });

  test("Entry and representative business/dialog actions are readable at desktop and narrow widths", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1536, height: 1024 });
    await page.goto("/ui-v2/");
    await connect(page);
    await expect(page.locator("#main-content")).toBeVisible();

    const surfaces: readonly { label: string; path: string }[] = [
      { label: "Dashboard", path: "/dashboard" },
      {
        label: "ResourceLibrary Files",
        path: "/resourcelib/files?resourceLibraryId=source",
      },
      {
        label: "MediaLibrary Files",
        path: "/medialib/files?mediaLibraryId=movies",
      },
      { label: "Storage", path: "/storage" },
      { label: "Rules", path: "/rules" },
      { label: "Automation", path: "/operations/automation" },
      {
        label: "Automation settings",
        path: "/operations/automation?tab=settings",
      },
      { label: "Automation create", path: "/operations/automation/lifecycle" },
      {
        label: "Automation edit",
        path: "/operations/automation/lifecycle/harness-scheduled",
      },
      { label: "Task Center", path: "/operations" },
      { label: "Settings", path: "/configuration" },
    ];
    const counts: Record<string, number> = {};
    for (const surface of surfaces) {
      await openSurface(page, surface.path);
      if (
        surface.label === "Automation create" ||
        surface.label === "Automation edit"
      ) {
        await expect(
          page.getByRole("heading", {
            name:
              surface.label === "Automation create"
                ? "Create Automation definition"
                : "Edit Automation definition",
            exact: true,
          }),
        ).toBeVisible();
      }
      counts[surface.label] = await expectSurfaceReadable(page, surface.label);
      for (const variant of [".mf-button-primary", ".mf-button-secondary"]) {
        const action = page
          .locator(`${variant}:visible:not(:disabled)`)
          .first();
        if (await action.count())
          await expectActionStates(action, `${surface.label} ${variant}`);
      }
      await page.screenshot({
        path: `${OUTPUT}/${surface.label.replace(/\W+/g, "-").toLowerCase()}-desktop.png`,
      });
    }
    // The measurement really covered the named surfaces, not an empty page.
    expect(counts["ResourceLibrary Files"]).toBeGreaterThan(10);
    expect(counts["MediaLibrary Files"]).toBeGreaterThan(10);
    expect(counts["Task Center"]).toBeGreaterThan(10);
    expect(counts.Storage).toBeGreaterThan(3);
    expect(counts.Rules).toBeGreaterThan(3);

    // Both library kinds' primary/secondary/danger dialog actions.
    for (const kind of ["resource", "media"] as const) {
      await openSurface(
        page,
        kind === "resource"
          ? "/resourcelib/files?resourceLibraryId=source"
          : "/medialib/files?mediaLibraryId=movies",
      );
      const dialog = page.getByRole("dialog");
      const createFolder = page.getByRole("button", {
        name: "新建文件夹",
        exact: true,
      });
      await expect(createFolder).toBeVisible();
      const command = await measure(
        page,
        ".mf-files-page .mf-files-toolbar .mf-button",
      );
      expectReadable(`${kind} toolbar command`, command);
      await createFolder.click();
      await expect(dialog).toBeVisible();
      const dialogTitle = (
        (await dialog.getAttribute("aria-label")) ?? ""
      ).trim();
      expect(dialogTitle.length).toBeGreaterThan(0);
      for (const selector of [
        ".mf-dialog-footer .mf-button-primary",
        ".mf-dialog-footer .mf-button-secondary",
        ".mf-dialog-close",
      ]) {
        const action = await measure(page, selector);
        expectReadable(`${kind} dialog ${selector}`, action);
      }
      const dialogField = await measure(page, ".mf-dialog-body input");
      expectReadable(`${kind} dialog name field`, dialogField);
      await page.screenshot({
        path: `${OUTPUT}/${kind}-dialog-desktop.png`,
      });
      await page.keyboard.press("Escape");
      await expect(dialog).toHaveCount(0);
    }

    // A real danger action: the MediaLibrary delete confirmation.
    await openSurface(page, "/medialib/files?mediaLibraryId=movies");
    const tile = page.getByLabel(/^文件条目 /).first();
    await tile.focus();
    await page.keyboard.press("Shift+F10");
    const menu = page.getByRole("menu");
    await expect(menu).toBeVisible();
    await expectSurfaceReadable(page, "Files row action menu");
    await menu.getByRole("menuitem", { name: "删除" }).click();
    const confirmation = page.getByRole("dialog", { name: "删除确认" });
    await expect(confirmation).toBeVisible();
    const danger = await measure(page, ".mf-dialog-footer .mf-button-danger");
    expectReadable("MediaLibrary delete confirmation danger action", danger);
    expect(danger.color).not.toBe(danger.backdrop);
    await page.screenshot({ path: `${OUTPUT}/medialibrary-delete-danger.png` });
    await confirmation
      .getByRole("button", { name: "取消", exact: true })
      .click();
    await expect(confirmation).toHaveCount(0);

    // Narrow viewport: labels stay readable and no action is clipped.
    await page.setViewportSize({ width: 390, height: 844 });
    await openSurface(page, "/resourcelib/files?resourceLibraryId=source");
    const narrowCount = await expectSurfaceReadable(
      page,
      "ResourceLibrary Files (narrow)",
    );
    expect(narrowCount).toBeGreaterThan(10);
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth + 1,
    );
    expect(overflow, "narrow Files must not clip action labels").toBe(true);
    await page.screenshot({ path: `${OUTPUT}/files-narrow.png` });

    await page.getByRole("button", { name: "新建文件夹", exact: true }).click();
    await expect(page.getByRole("dialog")).toBeVisible();
    const narrowPrimary = await measure(
      page,
      ".mf-dialog-footer .mf-button-primary",
    );
    expectReadable("narrow dialog primary action", narrowPrimary);
    const narrowBackdrop = narrowPrimary.backdrop;
    expect(narrowBackdrop.length).toBeGreaterThan(0);
    await page.screenshot({ path: `${OUTPUT}/files-dialog-narrow.png` });
  });

  test("both library kinds expose readable Rename, text, Delete and transfer dialogs without submitting", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1536, height: 1024 });
    const writes: string[] = [];
    page.on("request", (request) => {
      if (request.url().includes("/api/") && request.method() !== "GET")
        writes.push(request.url());
    });
    for (const kind of ["resource", "media"] as const) {
      await openSurface(
        page,
        kind === "resource"
          ? "/resourcelib/files?resourceLibraryId=source&path=Live"
          : "/medialib/files?mediaLibraryId=movies&path=Live",
      );
      await page.getByRole("button", { name: "网格视图", exact: true }).click();
      const tile = page.getByLabel("文件条目 Beta.txt", { exact: true });
      await expect(tile).toBeVisible();
      for (const [command, title] of [
        ["重命名", "重命名"],
        ["编辑", "编辑文本 — Beta.txt"],
        ["删除", "删除确认"],
        ["复制", "复制到…"],
        ["移动", "移动到…"],
      ]) {
        let releaseImpact: (() => void) | undefined;
        const impactPattern = `**/api/v1/${kind === "resource" ? "resource-libraries/source" : "media-libraries/movies"}/files/delete-impact*`;
        if (command === "删除") {
          const held = new Promise<void>((resolve) => {
            releaseImpact = resolve;
          });
          await page.route(impactPattern, async (route) => {
            await held;
            await route.continue();
          });
        }
        await tile.focus();
        await page.keyboard.press("Shift+F10");
        await page
          .getByRole("menu")
          .getByRole("menuitem", { name: command, exact: true })
          .click();
        const dialog = page.getByRole("dialog", { name: title, exact: true });
        await expect(dialog).toBeVisible();
        if (command === "编辑")
          await expect(dialog.getByRole("textbox")).toHaveValue(
            "live beta text",
          );
        if (command === "删除") {
          const danger = dialog.getByRole("button", {
            name: "删除",
            exact: true,
          });
          await expect(danger).toBeDisabled();
          expectReadable(
            `${kind} disabled danger while impact read is held`,
            await measure(page, ".mf-dialog-footer .mf-button-danger"),
          );
          releaseImpact?.();
          await expect(danger).toBeEnabled();
          await page.unroute(impactPattern);
          const cancel = await measure(
            page,
            ".mf-dialog-footer .mf-button-secondary",
          );
          const destructive = await measure(
            page,
            ".mf-dialog-footer .mf-button-danger",
          );
          expect(
            destructive.backdrop,
            `${kind} Delete must differ from Cancel`,
          ).not.toBe(cancel.backdrop);
          expect(destructive.color).not.toBe(cancel.color);
        }
        await expectSurfaceReadable(page, `${kind} ${title}`);
        for (const action of await dialog
          .locator(".mf-dialog-footer button, .mf-dialog-close")
          .all()) {
          await expectActionStates(
            action,
            `${kind} ${title} ${await action.textContent()}`,
          );
        }
        await page.screenshot({
          path: `${OUTPUT}/${kind}-${command}-dialog.png`,
        });
        await page.keyboard.press("Escape");
        await expect(dialog).toHaveCount(0);
      }
    }
    expect(
      writes,
      "opening, hover, focus and dismissal must not submit commands",
    ).toEqual([]);
  });

  test("primary, secondary and danger stay distinguishable with visible focus", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1536, height: 1024 });
    await page.goto("/ui-v2/resourcelib/files?resourceLibraryId=source");
    await connect(page);
    await expect(page.locator("#main-content")).toBeVisible();
    await page.waitForTimeout(400);

    for (const selector of [
      ".mf-view-toggle.is-active",
      ".mf-library-card-select.is-selected",
      "#primary-navigation a.is-active",
    ]) {
      await expectActionStates(
        page.locator(selector).first(),
        `selected ${selector}`,
      );
    }

    // The three kinds of action must not collapse onto one background.
    const primary = await measure(page, ".mf-files-page .mf-button-primary");
    const secondary = await measure(
      page,
      ".mf-files-page .mf-files-toolbar .mf-button-secondary",
    );
    expectReadable("Files primary", primary);
    expectReadable("Files secondary", secondary);
    expect(primary.backdrop).not.toBe(secondary.backdrop);

    // Keyboard focus keeps a visible ring on buttons and button-styled links.
    const focusRing = async (selector: string, label: string) => {
      const measured = await focusByKeyboard(page, selector);
      expect(
        measured.outlineStyle !== "none" &&
          Number.parseFloat(measured.outlineWidth) >= 2,
        `${label} exposes no visible focus ring (${measured.outlineStyle} ${measured.outlineWidth})`,
      ).toBe(true);
      expect(measured.outlineColor.length).toBeGreaterThan(0);
      expect(
        await page
          .locator(selector)
          .first()
          .evaluate((element) => element === document.activeElement),
      ).toBe(true);
    };
    await focusRing(
      ".mf-files-page .mf-button-primary",
      "Files primary button",
    );
    await focusRing(
      ".mf-files-page .mf-files-toolbar .mf-button-secondary",
      "Files secondary button",
    );
    await focusRing("#primary-navigation a", "button-styled navigation link");

    // A button-styled link keeps its own reading of the primary palette.
    await openSurface(page, "/operations/automation");
    const linkPrimary = await measure(page, "a.mf-button-primary");
    expectReadable("Automation primary link action", linkPrimary);
    expect(linkPrimary.text.length).toBeGreaterThan(0);
  });

  test("disabled and busy actions stay legible, unavailable and single-shot", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1536, height: 1024 });
    await page.goto("/ui-v2/resourcelib/files?resourceLibraryId=source");
    await connect(page);
    await expect(page.locator("#main-content")).toBeVisible();
    await page.waitForTimeout(400);

    // Real disabled controls: the batch footer with no selection, and the
    // pagination edge on a single page.
    const footerDisabled = await measure(
      page,
      ".mf-files-footer .mf-button:disabled",
    );
    expectReadable("disabled batch action", footerDisabled);
    expect(footerDisabled.disabled).toBe(true);
    expect(footerDisabled.opacity).toBeGreaterThanOrEqual(0.5);
    const pageDisabled = await measure(
      page,
      ".mf-files-pagination .mf-page-button:disabled",
    );
    expectReadable("disabled pagination action", pageDisabled);
    expect(pageDisabled.disabled).toBe(true);
    // Disabled is visibly different from the enabled palette.
    const enabledSecondary = await measure(
      page,
      ".mf-files-toolbar .mf-button-secondary:not(:disabled)",
    );
    expect(pageDisabled.backdrop).not.toBe(enabledSecondary.backdrop);
    await page.screenshot({ path: `${OUTPUT}/files-disabled.png` });

    // In-flight submit: hold the real command response, then confirm the
    // submit control reports busy, is disabled and cannot submit twice.
    let submissions = 0;
    const hold: { release: (() => void) | undefined } = { release: undefined };
    const held = new Promise<void>((resolve) => {
      hold.release = resolve;
    });
    await page.route(
      "**/api/v1/resource-libraries/*/files/commands",
      async (route) => {
        submissions += 1;
        await held;
        await route.continue();
      },
    );

    await page.getByRole("button", { name: "新建文件夹", exact: true }).click();
    const dialog = page.getByRole("dialog");
    await expect(dialog).toBeVisible();
    await dialog.getByLabel("名称").fill("Readability-Held-Folder");
    await dialog.getByRole("button", { name: "创建", exact: true }).click();
    await expect
      .poll(() => submissions, { message: "the held command was submitted" })
      .toBe(1);
    const submitControl = page.locator(".mf-dialog-footer .mf-button-primary");
    await expect(submitControl).toHaveAttribute("aria-busy", "true");
    await expect(submitControl).toBeDisabled();
    const busy = await measure(page, ".mf-dialog-footer .mf-button-primary");
    expect(busy.ariaBusy).toBe("true");
    expect(busy.disabled).toBe(true);
    expect(busy.text).toContain("提交中");
    expectReadable("busy submit label", busy);
    // A second activation cannot reach the backend while busy.
    await page
      .locator(".mf-dialog-footer .mf-button-primary")
      .dispatchEvent("click");
    await page.keyboard.press("Enter");
    expect(submissions).toBe(1);
    await page.screenshot({ path: `${OUTPUT}/files-submitting.png` });

    hold.release?.();
    await expect(dialog).toHaveCount(0);
    expect(submissions).toBe(1);
    await page.unroute("**/api/v1/resource-libraries/*/files/commands");

    // A read-only principal keeps its permission guards: no new command
    // authority appears merely because actions became readable.
    await page.goto("/ui-v2/resourcelib/files?resourceLibraryId=source");
    await connect(page, READONLY_TOKEN);
    await page.waitForTimeout(600);
    // This principal can read, but the actual command endpoint refuses it.
    // Enter through the same visible create-folder action as the admin.
    await page.getByRole("button", { name: "新建文件夹", exact: true }).click();
    const deniedDialog = page.getByRole("dialog");
    await deniedDialog.getByLabel("名称").fill("Viewer-Must-Not-Create");
    const refused = page.waitForResponse(
      (response) =>
        response.request().method() === "POST" &&
        response.url().includes("/files/commands"),
    );
    await deniedDialog
      .getByRole("button", { name: "创建", exact: true })
      .click();
    expect((await refused).status()).toBe(403);
    await expect(deniedDialog.getByRole("alert")).toBeVisible();
    await expectSurfaceReadable(page, "actual permission refusal");
    const body = (await page.textContent("body")) ?? "";
    expect(body).not.toContain(ADMIN_TOKEN);
    expect(body).not.toContain(READONLY_TOKEN);
  });

  test("read-back failures keep the palette readable and never replay work", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1536, height: 1024 });
    await page.goto("/ui-v2/operations");
    await connect(page);
    await expect(page.locator("#main-content")).toBeVisible();
    await page.waitForTimeout(400);

    // Bounded read failure on the real route: the shell's factual error state
    // and its retry affordance stay readable.
    await page.route("**/api/v1/operations/runs*", async (route) =>
      route.fulfill({
        status: 503,
        contentType: "application/json",
        body: JSON.stringify({ error: { code: "service_unavailable" } }),
      }),
    );
    await page.goto("/ui-v2/operations?view=ended");
    await connect(page);
    await expect(
      page.getByRole("heading", { name: /unavailable/i }).first(),
    ).toBeVisible();
    await expectSurfaceReadable(page, "Task Center read failure");
    await page.screenshot({ path: `${OUTPUT}/task-center-read-failure.png` });
    await page.unroute("**/api/v1/operations/runs*");

    // The same entry re-reads the real surface; no work was replayed.
    await page.goto(`${BASE}/ui-v2/operations`);
    await connect(page);
    await expect(
      page.getByRole("heading", { name: "任务中心", exact: true }),
    ).toBeVisible();
    await expectSurfaceReadable(page, "Task Center after read failure");
  });

  test("a disabled shared secondary action stays visibly unavailable through the real Settings export", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1536, height: 1024 });
    await page.goto("/ui-v2/configuration");
    await connect(page);
    await expect(page.locator("#main-content")).toBeVisible();
    await page.waitForTimeout(400);

    // The shared secondary palette has the same specificity as the shared
    // disabled palette, so a plain `.mf-button-secondary` consumer could keep
    // the enabled white surface with `cursor: default` as its only unavailable
    // cue. Measure that real cascade on two different consumers.
    //
    // 1. A statically disabled shared secondary action: the Automation
    //    definition inventory's first-page boundary.
    await openSurface(page, "/operations/automation");
    const inventoryBack = page
      .getByRole("button", { name: "上一页", exact: true })
      .first();
    await expect(inventoryBack).toBeDisabled();
    const inventoryDisabled = (await inventoryBack.evaluate(
      new Function(`return (${MEASURE})(arguments[0]);`) as never,
    )) as Measured;
    expectReadable("Automation inventory disabled 上一页", inventoryDisabled);
    expect(inventoryDisabled.disabled).toBe(true);
    expect(inventoryDisabled.opacity).toBeGreaterThanOrEqual(0.5);

    // 2. A shared secondary action disabled by a real in-flight command: the
    //    Settings configuration-package export. Open its panel the way an
    //    operator does, hold the real GET, then continue it.
    await openSurface(page, "/configuration");
    await page
      .getByRole("button", { name: "查看 Active JSON", exact: true })
      .click();
    const exportAction = page.getByRole("button", {
      name: "导出脱敏配置包",
      exact: true,
    });
    await expect(exportAction).toBeEnabled();
    // Read the enabled palette in the same unhovered, unfocused condition the
    // disabled reading is compared against.
    await page.mouse.move(0, 0);
    await exportAction.evaluate((element) => (element as HTMLElement).blur());
    const enabledExport = (await exportAction.evaluate(
      new Function(`return (${MEASURE})(arguments[0]);`) as never,
    )) as Measured;
    expectReadable("Settings export enabled", enabledExport);
    expect(enabledExport.disabled).toBe(false);
    await exportAction.scrollIntoViewIfNeeded();
    await page.screenshot({ path: `${OUTPUT}/settings-export-enabled.png` });

    let exportRequests = 0;
    const hold: { release: (() => void) | undefined } = { release: undefined };
    const held = new Promise<void>((resolve) => {
      hold.release = resolve;
    });
    const exportPattern =
      "**/api/v1/configuration/packages/export/configuration*";
    await page.route(exportPattern, async (route) => {
      exportRequests += 1;
      await held;
      await route.continue();
    });
    await exportAction.click();
    await expect
      .poll(() => exportRequests, { message: "the held export was requested" })
      .toBe(1);
    await expect(exportAction).toBeDisabled();
    const disabledExport = (await exportAction.evaluate(
      new Function(`return (${MEASURE})(arguments[0]);`) as never,
    )) as Measured;
    expectReadable("Settings export disabled while held", disabledExport);
    expect(disabledExport.disabled).toBe(true);
    expect(disabledExport.text).toBe(enabledExport.text);
    // Disabled must be visible without relying on the pointer cursor alone.
    expect(
      disabledExport.backdrop,
      `disabled export backdrop ${disabledExport.backdrop} must differ from the enabled ${enabledExport.backdrop}`,
    ).not.toBe(enabledExport.backdrop);
    expect(disabledExport.color).not.toBe(enabledExport.color);
    await exportAction.scrollIntoViewIfNeeded();
    // Hovering an unavailable control must not paint a hover state either.
    await exportAction.hover();
    const hoveredDisabled = (await exportAction.evaluate(
      new Function(`return (${MEASURE})(arguments[0]);`) as never,
    )) as Measured;
    expectReadable("Settings export hovered while held", hoveredDisabled);
    expect(hoveredDisabled.backdrop).toBe(disabledExport.backdrop);
    expect(hoveredDisabled.color).toBe(disabledExport.color);
    await page.mouse.move(0, 0);
    await page.screenshot({ path: `${OUTPUT}/settings-export-disabled.png` });

    // No second command path while the export is in flight.
    await exportAction.dispatchEvent("click");
    await page.keyboard.press("Enter");
    expect(exportRequests).toBe(1);

    // Continuing the real response restores availability and renders the
    // authoritative package; nothing was replayed.
    hold.release?.();
    await expect(exportAction).toBeEnabled();
    await page.unroute(exportPattern);
    expect(exportRequests).toBe(1);
    const restoredExport = (await exportAction.evaluate(
      new Function(`return (${MEASURE})(arguments[0]);`) as never,
    )) as Measured;
    expectReadable("Settings export restored", restoredExport);
    expect(restoredExport.disabled).toBe(false);
    await expect(page.getByLabel("配置 JSON")).toContainText(
      "mediaflow.configuration.v1",
    );
    await expectSurfaceReadable(page, "Settings after export readback");

    // 3. A primary variant disabled by an unfinished real read: the Rules
    //    drawer's Save stays unavailable until its own form authority arrives.
    //    It must not keep the enabled blue fill while it cannot be used.
    let authorityReads = 0;
    const authorityHold: { release: (() => void) | undefined } = {
      release: undefined,
    };
    const authorityHeld = new Promise<void>((resolve) => {
      authorityHold.release = resolve;
    });
    const authorityPattern = "**/api/v1/operations/rules/form-authority";
    await openSurface(page, "/rules?section=classificationPolicies");
    await page.route(authorityPattern, async (route) => {
      authorityReads += 1;
      await authorityHeld;
      await route.continue();
    });
    await page
      .getByRole("button", { name: "添加分类规则", exact: true })
      .first()
      .click();
    const drawer = page.getByRole("dialog", { name: "添加分类规则" });
    await expect(drawer).toBeVisible();
    const drawerSave = drawer
      .locator(".mf-rules-drawer-actions .mf-button-primary")
      .first();
    await expect(drawerSave).toBeDisabled();
    await expect
      .poll(() => authorityReads, { message: "the authority read was issued" })
      .toBe(1);
    const pendingSave = (await drawerSave.evaluate(
      new Function(`return (${MEASURE})(arguments[0]);`) as never,
    )) as Measured;
    expectReadable(
      "Rules drawer Save while its authority read is held",
      pendingSave,
    );
    expect(pendingSave.disabled).toBe(true);
    expect(pendingSave.text).toBe("保存");
    // The enabled primary fill is the accent blue; the unavailable one is not.
    expect(pendingSave.backdrop).not.toBe("rgb(18,104,245)");
    await page.screenshot({ path: `${OUTPUT}/rules-drawer-save-pending.png` });

    // The real authority arrives: the same control becomes usable again.
    authorityHold.release?.();
    await expect(drawerSave).toBeEnabled();
    await page.unroute(authorityPattern);
    expect(authorityReads).toBe(1);
    const readySave = (await drawerSave.evaluate(
      new Function(`return (${MEASURE})(arguments[0]);`) as never,
    )) as Measured;
    expectReadable("Rules drawer Save after its authority read", readySave);
    expect(readySave.disabled).toBe(false);
    expect(readySave.backdrop).not.toBe(pendingSave.backdrop);
    await page.screenshot({ path: `${OUTPUT}/rules-drawer-save-ready.png` });
  });
});
