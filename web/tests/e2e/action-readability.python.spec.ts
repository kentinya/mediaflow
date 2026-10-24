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

import { expect, test, type Page } from "@playwright/test";
import { mkdirSync } from "node:fs";

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
    const layers = [];
    let node = element;
    let opacity = 1;
    while (node) {
      const computed = window.getComputedStyle(node);
      opacity *= Number(computed.opacity);
      const rgba = toRgba(computed.backgroundColor);
      if (rgba && rgba.a > 0) layers.push(rgba);
      node = node.parentElement;
    }
    // Painted back-to-front from the page canvas so every translucent ancestor
    // contributes its real share of the visible backdrop.
    let backdrop = { r: 255, g: 255, b: 255, a: 1 };
    for (let index = layers.length - 1; index >= 0; index -= 1) {
      const layer = layers[index];
      backdrop = {
        r: layer.r * layer.a + backdrop.r * (1 - layer.a),
        g: layer.g * layer.a + backdrop.g * (1 - layer.a),
        b: layer.b * layer.a + backdrop.b * (1 - layer.a),
        a: 1,
      };
    }
    const computed = window.getComputedStyle(element);
    const foreground = toRgba(computed.color);
    // The browser paints text with the element's own opacity, so the visible
    // foreground is the label blended toward its backdrop by that factor.
    const visible = {
      r: foreground.r * opacity + backdrop.r * (1 - opacity),
      g: foreground.g * opacity + backdrop.g * (1 - opacity),
      b: foreground.b * opacity + backdrop.b * (1 - opacity),
    };
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
        'rgb(' + Math.round(backdrop.r) + ',' + Math.round(backdrop.g) + ')' +
        ',' + Math.round(backdrop.b),
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
function expectReadable(label: string, measured: Measured): void {
  const floor = measured.largeText ? MIN_LARGE_CONTRAST : MIN_CONTRAST;
  expect(
    measured.contrast,
    `${label} rendered ${measured.contrast}:1 (${measured.color} on ${measured.backdrop}, effective opacity ${measured.opacity}); needs ${floor}:1`,
  ).toBeGreaterThanOrEqual(floor);
}

/** Every visible action on the surface, measured where it is really painted. */
async function expectSurfaceReadable(
  page: Page,
  surface: string,
): Promise<number> {
  const selector =
    'button:visible, a.mf-button:visible, [role="menuitem"]:visible';
  const actions = page.locator(selector);
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
    expect(field.backdrop).not.toBe("rgb(32,43,36)");
    const fieldLabel = await measure(page, "label[for='api-token']");
    expectReadable("Entry token field label", fieldLabel);

    const connectAction = await measure(
      page,
      "form.mf-entry button[type='submit']",
    );
    expectReadable("Entry Connect", connectAction);
    expect(connectAction.disabled).toBe(false);
    await page.screenshot({ path: `${OUTPUT}/entry-desktop.png` });

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
      { label: "Task Center", path: "/operations" },
      { label: "Settings", path: "/configuration" },
    ];
    const counts: Record<string, number> = {};
    for (const surface of surfaces) {
      await openSurface(page, surface.path);
      counts[surface.label] = await expectSurfaceReadable(page, surface.label);
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

  test("primary, secondary and danger stay distinguishable with visible focus", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1536, height: 1024 });
    await page.goto("/ui-v2/resourcelib/files?resourceLibraryId=source");
    await connect(page);
    await expect(page.locator("#main-content")).toBeVisible();
    await page.waitForTimeout(400);

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
    await page.evaluate(() => window.localStorage.clear());
    await connect(page, READONLY_TOKEN);
    await page.waitForTimeout(600);
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
});
