/**
 * Structural regression for the Files toolbar/breadcrumb CSS (Task 44.5 RO-5).
 *
 * The reported defect was a layout relationship, not a missing declaration:
 * the toolbar wrapped its controls and the breadcrumbs themselves wrapped,
 * while a later `.mf-files-toolbar { height: 52px }` rule fixed the wrapper to
 * a single row.  A wrapped control row therefore extended below the reserved
 * toolbar space and into the entry viewport, and an overlong unbroken segment
 * could exceed the pane width.
 *
 * jsdom does not apply the stylesheet, so this guard checks the exact
 * relationships that caused the defect.  It is not a substitute for the real
 * measured geometry in the committed real-Python/Chromium proof.
 */

/// <reference types="node" />
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const css = readFileSync(
  resolve(dirname(fileURLToPath(import.meta.url)), "styles.css"),
  "utf8",
);

/** Every rule block whose selector list contains `needle`. */
function declarationsFor(needle: string): string[] {
  const blocks: string[] = [];
  const pattern = /([^{}]+)\{([^{}]*)\}/g;
  let match: RegExpExecArray | null;
  while ((match = pattern.exec(css)) !== null) {
    if (match[1].includes(needle)) blocks.push(match[2]);
  }
  return blocks;
}

describe("Files toolbar geometry CSS", () => {
  it("reserves the toolbar's actual rows instead of a fixed single row", () => {
    const toolbar = declarationsFor(".mf-files-toolbar").join("\n");
    expect(toolbar).toContain("min-height: 52px");
    // A fixed height would hide a deliberately wrapped control row.
    expect(toolbar).not.toMatch(/(^|\n)\s*height:\s*52px/);
  });

  it("keeps the bounded path region single-line and shrinkable", () => {
    const breadcrumbs = declarationsFor(".mf-files-page .mf-breadcrumbs").join(
      "\n",
    );
    expect(breadcrumbs).toContain("flex-wrap: nowrap");
    expect(breadcrumbs).toContain("min-width:");
    expect(breadcrumbs).toContain("overflow: hidden");
  });

  it("scrolls the combined path inside its own track", () => {
    const track = declarationsFor(".mf-crumb-track").join("\n");
    expect(track).toContain("overflow-x: auto");
    expect(track).toContain("white-space: nowrap");
    expect(track).toContain("min-width: 0");
  });

  it("elides one overlong segment without moving the controls", () => {
    // The segment cap lives on the list item so it can never exceed the
    // bounded region itself; the link elides inside that cap.
    const crumb = declarationsFor(".mf-crumb-track .mf-crumb").join("\n");
    expect(crumb).toContain("max-width: min(22ch, 100%)");
    const link = declarationsFor(".mf-crumb-link").join("\n");
    expect(link).toContain("text-overflow: ellipsis");
    expect(link).toContain("max-width: 100%");
    const controls = declarationsFor(
      ".mf-files-page .mf-toolbar-controls",
    ).join("\n");
    expect(controls).toContain("flex: 0 1 auto");
  });

  it("renders the complete-name disclosure above every clipping ancestor", () => {
    const disclosure = declarationsFor(".mf-crumb-disclosure").join("\n");
    expect(disclosure).toContain("position: fixed");
    expect(disclosure).toContain("white-space: pre-wrap");
    expect(disclosure).toContain("z-index: 60");
  });

  it("keeps the display settings in the toolbar and gives the header a quiet complete surface", () => {
    expect(css).not.toContain(".mf-files-sortscope");
    const display = declarationsFor(".mf-files-display").join("\n");
    expect(display).toContain("border: 1px solid #e3e9f1");
    expect(display).toContain("background: #f8fafc");
    expect(display).toContain("white-space: nowrap");
    const menu = declarationsFor(".mf-files-display-menu").join("\n");
    expect(menu).toContain("z-index: 80");
    expect(menu).toContain("min-width: 184px");
    const header = declarationsFor(".mf-files-table thead th").join("\n");
    expect(header).toContain("background: #f7f9fc");
    expect(header).toContain("border-bottom: 1px solid #dfe6f0");
  });

  it("reveals an inactive sort direction on hover or focus and keeps the active one visible", () => {
    const indicator = declarationsFor(".mf-sort-indicator").join("\n");
    expect(indicator).toContain("opacity: 0");
    const revealed = declarationsFor(".mf-sort-button:hover .mf-sort-indicator")
      .concat(
        declarationsFor(".mf-sort-button:focus-visible .mf-sort-indicator"),
      )
      .concat(declarationsFor(".mf-sort-button.is-active .mf-sort-indicator"))
      .join("\n");
    expect(revealed).toContain("opacity: 1");
  });

  it("keeps a subtle resize boundary that strengthens without shrinking its hit area", () => {
    const handle = declarationsFor(".mf-col-resize").join("\n");
    expect(handle).toContain("width: 8px");
    const boundary = declarationsFor(".mf-col-resize::after").join("\n");
    expect(boundary).toContain("border-left: 1px solid #d5dfec");
    expect(boundary).toContain("opacity: 0.75");
    const enhanced = declarationsFor(".mf-col-resize.is-dragging::after")
      .concat(declarationsFor(".mf-col-resize:hover::after"))
      .join("\n");
    expect(enhanced).toContain("border-left-color: var(--files-accent)");
    expect(enhanced).toContain("opacity: 1");
  });
});
