import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { useRef } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  ModalCardShell,
  useBodyScrollLock,
  type ModalCardShellProps,
} from "./modal-card";

function LockedSurface() {
  useBodyScrollLock();
  return <p>locked</p>;
}

function OverlaySurface() {
  useBodyScrollLock();
  return <p>overlay</p>;
}

function setScrollbarGutter(pixels: number) {
  Object.defineProperty(document.documentElement, "clientWidth", {
    configurable: true,
    get: () => window.innerWidth - pixels,
  });
}

describe("useBodyScrollLock", () => {
  beforeEach(() => {
    cleanup();
    document.body.removeAttribute("style");
  });

  it("reserves the measured viewport scrollbar gutter and restores it exactly", () => {
    document.body.style.overflow = "visible";
    document.body.style.paddingRight = "3px";
    setScrollbarGutter(15);
    const { unmount } = render(<LockedSurface />);
    expect(screen.getByText("locked")).toBeVisible();
    // 3px pre-existing padding + the 15px viewport gutter, applied once.
    expect(document.body.style.overflow).toBe("hidden");
    expect(document.body.style.paddingRight).toBe("18px");
    unmount();
    expect(document.body.style.overflow).toBe("visible");
    expect(document.body.style.paddingRight).toBe("3px");
  });

  it("adds no padding when the viewport has an overlay scrollbar", () => {
    setScrollbarGutter(0);
    const { unmount } = render(<LockedSurface />);
    expect(document.body.style.overflow).toBe("hidden");
    expect(document.body.style.paddingRight).toBe("");
    unmount();
    expect(document.body.style.overflow).toBe("");
  });

  it("compensates once for nested layers and releases only on the last unmount", () => {
    setScrollbarGutter(12);
    const first = render(
      <div>
        <LockedSurface />
      </div>,
    );
    const second = render(<OverlaySurface />);
    expect(document.body.style.paddingRight).toBe("12px");
    first.unmount();
    // The outer layer is still open; a second compensation or a premature
    // release would move the background.
    expect(document.body.style.overflow).toBe("hidden");
    expect(document.body.style.paddingRight).toBe("12px");
    second.unmount();
    expect(document.body.style.overflow).toBe("");
    expect(document.body.style.paddingRight).toBe("");
  });

  it("measures the gutter without changing ordinary page scroll behavior", () => {
    setScrollbarGutter(9);
    const getComputed = vi.spyOn(window, "getComputedStyle");
    const { unmount } = render(<LockedSurface />);
    expect(document.body.style.overflow).toBe("hidden");
    expect(getComputed).not.toHaveBeenCalled();
    unmount();
    expect(document.body.style.overflow).toBe("");
  });
});

function ShellHarness(
  props: Pick<ModalCardShellProps, "closeDisabled" | "onRequestClose">,
) {
  const layerRef = useRef<HTMLDivElement | null>(null);
  return (
    <ModalCardShell
      layerRef={layerRef}
      closing={false}
      busy={!props.closeDisabled}
      title="存储卡片"
      titleId="shell-title"
      description="共享呈现"
      closeLabel="关闭"
      closeDisabled={props.closeDisabled}
      onRequestClose={props.onRequestClose}
    >
      <p>卡片正文</p>
    </ModalCardShell>
  );
}

function layerAndBackdrop() {
  const card = screen.getByRole("dialog");
  const layer = card.closest(".mf-modal-layer");
  if (!(layer instanceof HTMLElement)) throw new Error("modal layer missing");
  const backdrop = layer.querySelector(".mf-modal-backdrop");
  if (!(backdrop instanceof HTMLElement)) throw new Error("backdrop missing");
  return { layer, backdrop };
}

describe("ModalCardShell close permission", () => {
  beforeEach(cleanup);

  it("closes from the backdrop, layer edge and close button when allowed", () => {
    const onRequestClose = vi.fn();
    render(
      <ShellHarness closeDisabled={false} onRequestClose={onRequestClose} />,
    );
    const { layer, backdrop } = layerAndBackdrop();
    fireEvent.mouseDown(backdrop);
    fireEvent.mouseDown(layer);
    fireEvent.click(screen.getByRole("button", { name: "关闭" }));
    expect(onRequestClose).toHaveBeenCalledTimes(3);
  });

  it("refuses backdrop and layer-edge dismissal while the owner disables exit", () => {
    const onRequestClose = vi.fn();
    render(<ShellHarness closeDisabled onRequestClose={onRequestClose} />);
    const { layer, backdrop } = layerAndBackdrop();
    fireEvent.mouseDown(backdrop);
    fireEvent.mouseDown(layer);
    expect(onRequestClose).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "关闭" })).toBeDisabled();
  });
});
