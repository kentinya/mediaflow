import {
  cleanup,
  fireEvent,
  render,
  screen,
  act,
} from "@testing-library/react";
import { useRef } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  MODAL_CARD_EXIT_MS,
  ModalCardShell,
  useBodyScrollLock,
  useModalCardExit,
  useModalLayer,
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

function BackgroundShellHarness() {
  const layerRef = useRef<HTMLDivElement | null>(null);
  const onRequestClose = vi.fn();
  return (
    <ModalCardShell
      layerRef={layerRef}
      closing={false}
      busy={false}
      title="详情卡片"
      titleId="background-shell-title"
      description="装饰背景"
      closeLabel="关闭"
      closeDisabled={false}
      onRequestClose={onRequestClose}
      layerBackground={<div data-testid="layer-background" />}
    >
      <p>可读正文</p>
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

  it("keeps an optional decorative layer behind the ordinary card content", () => {
    render(<BackgroundShellHarness />);
    const card = screen.getByRole("dialog");
    const background = screen.getByTestId("layer-background");
    expect(card.firstElementChild).toBe(background);
    expect(screen.getByText("可读正文")).toBeVisible();
    expect(screen.getByRole("button", { name: "关闭" })).toBeEnabled();
  });
});

function StackedLayerHarness({
  active,
  onEscape,
}: {
  readonly active: boolean;
  readonly onEscape: () => void;
}) {
  const layer = useModalLayer({ onEscape, active });
  return (
    <div>
      <p>背景正文</p>
      <ModalCardShell
        layerRef={layer.layerRef}
        closing={false}
        busy={false}
        title="下层卡片"
        titleId="stacked-shell-title"
        description="可被上层挂起"
        closeLabel="关闭"
        closeDisabled={false}
        onRequestClose={() => undefined}
      >
        <p>下层正文</p>
      </ModalCardShell>
    </div>
  );
}

function ExitHarness({ onClose }: { readonly onClose: () => void }) {
  const exit = useModalCardExit();
  return (
    <button type="button" onClick={() => exit.beginClose(onClose)}>
      {exit.closing ? "closing" : "idle"}
    </button>
  );
}

describe("useModalLayer stacking", () => {
  beforeEach(() => {
    cleanup();
  });

  it("suspends a lower layer's keyboard trap and inertness under a stacked card", () => {
    const onEscape = vi.fn();
    render(<StackedLayerHarness active onEscape={onEscape} />);
    const background = screen.getByText("背景正文");
    // The active lower layer owns its background while it is topmost.
    expect(background.closest("[inert]")).not.toBeNull();
    fireEvent.keyDown(document, { key: "Escape" });
    expect(onEscape).toHaveBeenCalledTimes(1);
    cleanup();

    // A stacked card above it suspends that ownership, so Escape and the
    // background are handled only once, by the topmost card.
    render(<StackedLayerHarness active={false} onEscape={onEscape} />);
    const suspendedBackground = screen.getByText("背景正文");
    expect(suspendedBackground.closest("[inert]")).toBeNull();
    fireEvent.keyDown(document, { key: "Escape" });
    expect(onEscape).toHaveBeenCalledTimes(1);
  });
});

describe("useModalCardExit", () => {
  beforeEach(() => {
    cleanup();
  });

  it("hands control to the owner only after the coordinated exit and ignores re-entry", () => {
    vi.useFakeTimers();
    try {
      const onClose = vi.fn();
      render(<ExitHarness onClose={onClose} />);
      const trigger = screen.getByRole("button", { name: "idle" });
      fireEvent.click(trigger);
      expect(
        screen.getByRole("button", { name: "closing" }),
      ).toBeInTheDocument();
      // A second close gesture while the exit runs schedules no second
      // completion.
      fireEvent.click(screen.getByRole("button", { name: "closing" }));
      act(() => {
        vi.advanceTimersByTime(MODAL_CARD_EXIT_MS);
      });
      expect(onClose).toHaveBeenCalledTimes(1);
    } finally {
      vi.useRealTimers();
    }
  });

  it("closes immediately under reduced motion", () => {
    vi.stubGlobal(
      "matchMedia",
      vi.fn().mockReturnValue({ matches: true } as MediaQueryList),
    );
    try {
      const onClose = vi.fn();
      render(<ExitHarness onClose={onClose} />);
      fireEvent.click(screen.getByRole("button", { name: "idle" }));
      expect(onClose).toHaveBeenCalledTimes(1);
      expect(screen.getByRole("button", { name: "idle" })).toBeInTheDocument();
    } finally {
      vi.unstubAllGlobals();
    }
  });

  it("never completes after the owner unmounts mid-exit", () => {
    vi.useFakeTimers();
    try {
      const onClose = vi.fn();
      const { unmount } = render(<ExitHarness onClose={onClose} />);
      fireEvent.click(screen.getByRole("button", { name: "idle" }));
      unmount();
      act(() => {
        vi.advanceTimersByTime(MODAL_CARD_EXIT_MS * 2);
      });
      expect(onClose).not.toHaveBeenCalled();
    } finally {
      vi.useRealTimers();
    }
  });
});
