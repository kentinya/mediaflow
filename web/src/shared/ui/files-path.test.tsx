/**
 * Focused proof for the shared Files path presentation (Task 44.5 / RO-5).
 *
 * jsdom applies no stylesheet, so these tests prove the behavior contract that
 * the shared component owns: the exact raw Storage value is rendered and
 * handed back unchanged, boundary whitespace stays distinguishable, every
 * ancestor and the root stay reachable, and the current segment is marked.
 * The real geometry is proven by the committed real-Python/Chromium proof and
 * the structural CSS guard.
 */

import { describe, expect, it, vi } from "vitest";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  within,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach } from "vitest";
import {
  FilesBreadcrumbs,
  IdentityLabel,
  identityAccessibleName,
} from "./files-path";

afterEach(() => {
  cleanup();
});

const CRUMBS = [
  { name: "root", path: "", isRoot: true },
  { name: "电影", path: "电影", isRoot: false },
  { name: "华语", path: "电影/华语", isRoot: false },
] as const;

function renderCrumbs(
  crumbs: readonly { name: string; path: string; isRoot: boolean }[] = CRUMBS,
  currentPath = "电影/华语",
) {
  const onOpenPath = vi.fn();
  const onReturnRoot = vi.fn();
  render(
    <FilesBreadcrumbs
      label="资源库面包屑"
      homeLabel="返回资源库根目录"
      crumbs={crumbs}
      currentPath={currentPath}
      onReturnRoot={onReturnRoot}
      onOpenPath={onOpenPath}
    />,
  );
  return { onOpenPath, onReturnRoot };
}

describe("exact Storage identity presentation", () => {
  it("renders an ordinary value character for character", () => {
    render(<IdentityLabel value="Breaking Bad" />);
    expect(screen.getByText("Breaking Bad")).toBeInTheDocument();
    expect(document.querySelector(".mf-ws-marker")).toBeNull();
  });

  it("marks boundary whitespace without rewriting the rendered value", () => {
    render(<IdentityLabel value="SSH " />);
    // The real characters, including the trailing space, are the value.
    expect(document.querySelector(".mf-ws-value")?.textContent).toBe("SSH ");
    expect(document.querySelector(".mf-ws-marker")?.textContent).toBe("␣");
    expect(
      document.querySelector(".mf-identity-label")?.getAttribute("title"),
    ).toBe("名称结尾包含空格");
  });

  it("keeps same-prefix siblings distinct in their accessible names", () => {
    expect(identityAccessibleName("SSH")).toBe("SSH");
    expect(identityAccessibleName("SSH ")).toBe("SSH （名称结尾包含空格）");
    expect(identityAccessibleName("SSH")).not.toBe(
      identityAccessibleName("SSH "),
    );
  });
});

describe("bounded Files breadcrumbs", () => {
  it("keeps the path region single-line and scrollable as its own track", () => {
    renderCrumbs();
    const nav = screen.getByRole("navigation", { name: "资源库面包屑" });
    const track = nav.querySelector(".mf-crumb-track");
    expect(track).not.toBeNull();
    // The track is a real list whose items are the ancestors.
    expect(within(track as HTMLElement).getAllByRole("listitem")).toHaveLength(
      2,
    );
  });

  it("keeps every ancestor and the root reachable with pointer and keyboard", async () => {
    const user = userEvent.setup();
    const { onOpenPath, onReturnRoot } = renderCrumbs();
    const nav = screen.getByRole("navigation", { name: "资源库面包屑" });

    const root = within(nav).getByRole("button", {
      name: "返回资源库根目录",
    });
    root.focus();
    expect(root).toHaveFocus();
    await user.keyboard("{Enter}");
    expect(onReturnRoot).toHaveBeenCalledTimes(1);

    const ancestor = within(nav).getByRole("button", { name: "电影" });
    await user.click(ancestor);
    expect(onOpenPath).toHaveBeenCalledWith("电影");
  });

  it("marks the current segment and keeps its exact raw path", async () => {
    const user = userEvent.setup();
    const { onOpenPath } = renderCrumbs();
    const nav = screen.getByRole("navigation", { name: "资源库面包屑" });
    const current = within(nav).getByRole("button", { name: "华语" });
    expect(current).toHaveAttribute("aria-current", "location");
    await user.click(current);
    // No trimming, normalization or abbreviation reaches navigation.
    expect(onOpenPath).toHaveBeenCalledWith("电影/华语");
  });

  it("discloses the complete exact name on hover and focus, including boundary whitespace", () => {
    const crumbs = [
      { name: "root", path: "", isRoot: true },
      { name: "SSH ", path: "SSH ", isRoot: false },
    ];
    renderCrumbs(crumbs, "SSH ");
    const nav = screen.getByRole("navigation", { name: "资源库面包屑" });
    const link = within(nav).getByRole("button", {
      name: "SSH （名称结尾包含空格）",
    });
    expect(link).toHaveAttribute("title", "SSH （名称结尾包含空格）");
    expect(link.querySelector(".mf-ws-value")?.textContent).toBe("SSH ");
  });

  it("renders one shared disclosure on hover and on keyboard focus", async () => {
    const user = userEvent.setup();
    renderCrumbs();
    const nav = screen.getByRole("navigation", { name: "资源库面包屑" });
    const ancestor = within(nav).getByRole("button", { name: "电影" });

    expect(screen.queryByTestId("crumb-disclosure")).toBeNull();
    await user.hover(ancestor);
    // The complete exact segment is disclosed, not the elided visible text.
    expect(screen.getByTestId("crumb-disclosure")).toHaveTextContent("电影");
    // The disclosure is portalled out of the bounded path region.
    expect(
      document.querySelector(".mf-breadcrumbs .mf-crumb-disclosure"),
    ).toBeNull();

    await user.unhover(ancestor);
    expect(screen.queryByTestId("crumb-disclosure")).toBeNull();

    // Keyboard focus discloses the same complete name.
    fireEvent.focus(ancestor);
    expect(screen.getByTestId("crumb-disclosure")).toHaveTextContent("电影");
    fireEvent.blur(ancestor);
    expect(screen.queryByTestId("crumb-disclosure")).toBeNull();
  });

  it("keeps same-visible-prefix siblings on their own exact paths", async () => {
    const user = userEvent.setup();
    const crumbs = [
      { name: "root", path: "", isRoot: true },
      { name: "SSH", path: "SSH", isRoot: false },
      { name: "SSH ", path: "SSH ", isRoot: false },
    ];
    const { onOpenPath } = renderCrumbs(crumbs, "SSH ");
    const nav = screen.getByRole("navigation", { name: "资源库面包屑" });
    await user.click(within(nav).getByRole("button", { name: "SSH" }));
    await user.click(
      within(nav).getByRole("button", { name: "SSH （名称结尾包含空格）" }),
    );
    expect(onOpenPath).toHaveBeenNthCalledWith(1, "SSH");
    expect(onOpenPath).toHaveBeenNthCalledWith(2, "SSH ");
  });
});
