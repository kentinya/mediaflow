/**
 * Structural regression for the Rules form CSS (Task 44.4 correction round 1).
 *
 * The rendered switch and the required-label markers were broken by two
 * selector conflicts rather than by missing declarations:
 *
 * 1. `.mf-rules-field input[type="checkbox"]` (0,2,1) out-specified
 *    `.mf-rules-switch input` (0,1,1), so the real 44x24 track was resized to
 *    1.15rem while its 18px thumb stayed translated 20px — visually a dot with
 *    the state text underneath.
 * 2. `.mf-rules-section-body label:not(.mf-rules-flag)` (0,3,2) out-specified
 *    `.mf-rules-field > label` (0,1,2) and forced `display: grid` onto the
 *    switch label and the inline required label, splitting the `*` onto its own
 *    row.
 *
 * jsdom does not apply the stylesheet, so this checks the exact selector
 * relationships that caused the defect. It is a structural guard, not a
 * substitute for the real-browser dimension assertions in
 * `scripts/rules_workspace_browser_proof.py`.
 */

/// <reference types="node" />
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

// Vitest disables CSS processing, so the guard reads the exact stylesheet
// source from disk rather than a processed module.
const css = readFileSync(
  resolve(dirname(fileURLToPath(import.meta.url)), "styles.css"),
  "utf8",
);

/** Specificity of one simple selector: [ids, classes/attrs/pseudo-classes, types]. */
function specificity(selector: string): [number, number, number] {
  const ids = (selector.match(/#[\w-]+/g) ?? []).length;
  const classes =
    (selector.match(/\.[\w-]+/g) ?? []).length +
    (selector.match(/\[[^\]]+\]/g) ?? []).length +
    (selector.match(/:(?!:)[\w-]+/g) ?? []).length;
  const types =
    (selector.match(/(^|[\s>+~,])([a-z][\w-]*)/g) ?? []).length +
    (selector.match(/::[\w-]+/g) ?? []).length;
  return [ids, classes, types];
}

function compare(
  a: [number, number, number],
  b: [number, number, number],
): number {
  for (let index = 0; index < 3; index += 1) {
    if (a[index] !== b[index]) return a[index] - b[index];
  }
  return 0;
}

/** Every rule block whose selector list contains `needle`. */
function declarationsFor(needle: string): string[] {
  const blocks: string[] = [];
  const pattern = /([^{}]+)\{([^{}]*)\}/g;
  let match: RegExpExecArray | null;
  while ((match = pattern.exec(css)) !== null) {
    const selectors = match[1];
    if (selectors.includes(needle)) blocks.push(match[2]);
  }
  return blocks;
}

describe("Rules form switch CSS", () => {
  it("keeps the real switch track larger than the base checkbox rule", () => {
    const base = '.mf-rules-field input[type="checkbox"]';
    const scoped = ".mf-rules-field .mf-rules-switch input";
    const baseIndex = css.indexOf(base);
    const scopedIndex = css.indexOf(scoped);
    expect(baseIndex).toBeGreaterThan(-1);
    expect(scopedIndex).toBeGreaterThan(-1);
    // The scoped rule must exist and must not lose on specificity, or the
    // track silently shrinks back to the checkbox default.
    expect(
      compare(specificity(scoped), specificity(base)),
    ).toBeGreaterThanOrEqual(0);
    const scopedDeclarations = declarationsFor(scoped).join("\n");
    expect(scopedDeclarations).toContain("width: 44px");
    expect(scopedDeclarations).toContain("height: 24px");
    expect(scopedDeclarations).toContain("padding: 0");
  });

  it("keeps the switch track and thumb geometrically consistent", () => {
    const track = declarationsFor(".mf-rules-switch input").join("\n");
    const thumb = declarationsFor(".mf-rules-switch input::after").join("\n");
    const checked = declarationsFor(
      ".mf-rules-switch input:checked::after",
    ).join("\n");
    expect(track).toContain("width: 44px");
    expect(track).toContain("height: 24px");
    expect(thumb).toContain("width: 18px");
    // 3px inset + 18px thumb + 20px travel + 3px inset = 44px track, so the
    // checked thumb stays inside the track in both states.
    expect(checked).toContain("translateX(20px)");
  });
});

describe("Rules section label CSS", () => {
  it("does not force the grid layout onto the inline switch or field labels", () => {
    // The section-wide label selector must exclude the switch and the
    // Field-owned label, otherwise its grid display out-specifies their own
    // layout and the state text / required marker drops onto a second row.
    const sectionSelectors = css
      .match(/([^{}]*\.mf-rules-section-body[^{}]*)\{/g)
      ?.join("\n");
    expect(sectionSelectors).toBeDefined();
    expect(sectionSelectors).toContain(":not(.mf-rules-switch)");
    expect(sectionSelectors).toContain(":not(.mf-rules-field-label)");
  });

  it("keeps the required marker inline with its own field label", () => {
    const label = declarationsFor(".mf-rules-field > label").join("\n");
    expect(label).toContain("display: block");
    const marker = css.includes(
      '.mf-rules-field > label[data-required="true"]::after',
    );
    expect(marker).toBe(true);
  });
});
