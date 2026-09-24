import {
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { createPortal } from "react-dom";

/**
 * The page-level row action menu.
 *
 * The menu renders through a portal above every overflow-clipped table cell
 * and scrolling ancestor, anchored to the exact invoking button rectangle.  It
 * prefers opening below the row, flips above near the viewport bottom and
 * clamps horizontally.  It closes on Escape, outside pointer down and on any
 * scroll or resize outside the menu itself, so it can never visually refer to
 * the wrong row, and it restores focus to the invoking control on dismissal.
 */
export function RowActionMenu({
  path,
  label,
  onClose,
  anchorPoint,
  children,
}: {
  readonly path: string;
  readonly label: string;
  readonly onClose: () => void;
  /** Optional pointer location for context-menu invocation. */
  readonly anchorPoint?: { readonly x: number; readonly y: number };
  readonly children: ReactNode;
}) {
  const menuRef = useRef<HTMLDivElement | null>(null);
  const [position, setPosition] = useState<{
    readonly top: number;
    readonly left: number;
  } | null>(null);
  const triggerSelector = `[data-row-menu="${CSS.escape(path)}"]`;

  const measure = () => {
    const trigger = document.querySelector(triggerSelector);
    const rect =
      trigger instanceof Element ? trigger.getBoundingClientRect() : null;
    const menu = menuRef.current;
    const width = menu?.offsetWidth ?? 176;
    const height = menu?.offsetHeight ?? 120;
    let left = anchorPoint?.x ?? (rect?.right ?? 8) - width;
    left = Math.max(8, Math.min(left, window.innerWidth - width - 8));
    let top = anchorPoint?.y ?? (rect?.bottom ?? 8) + 6;
    if (top + height > window.innerHeight - 8) {
      top = (anchorPoint?.y ?? rect?.top ?? 8) - height - 6;
    }
    top = Math.max(8, Math.min(top, window.innerHeight - height - 8));
    setPosition({ top, left });
  };

  useLayoutEffect(() => {
    measure();
    // The menu has no size on the very first paint; measure once more after it
    // mounts so flipping and clamping use the real box.
    const frame = window.requestAnimationFrame(measure);
    return () => window.cancelAnimationFrame(frame);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [path, anchorPoint]);

  useEffect(() => {
    const menu = menuRef.current;
    const focusFirst = () => {
      const first =
        menuRef.current?.querySelector<HTMLElement>('[role="menuitem"]');
      first?.focus();
    };
    const handleKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.stopPropagation();
        onClose();
      } else if (event.key === "ArrowDown" || event.key === "ArrowUp") {
        const items = Array.from(
          menuRef.current?.querySelectorAll<HTMLElement>('[role="menuitem"]') ??
            [],
        );
        if (items.length === 0) return;
        event.preventDefault();
        const current = items.indexOf(document.activeElement as HTMLElement);
        const next =
          event.key === "ArrowDown"
            ? (current + 1 + items.length) % items.length
            : (current - 1 + items.length) % items.length;
        items[next]?.focus();
      }
    };
    const handlePointer = (event: PointerEvent) => {
      const target = event.target;
      if (
        target instanceof Element &&
        target.closest(".mf-row-menu-portal, .mf-row-more") === null
      ) {
        onClose();
      }
    };
    const handleViewportChange = (event: Event) => {
      // Scrolling inside the menu keeps it; any other scroll (the Files pane,
      // the page or the table viewport) closes it so the menu can never
      // anchor to a row that has moved away.
      if (
        event.target instanceof Element &&
        menu !== null &&
        menu.contains(event.target)
      ) {
        return;
      }
      onClose();
    };
    document.addEventListener("keydown", handleKey, true);
    document.addEventListener("pointerdown", handlePointer, true);
    window.addEventListener("scroll", handleViewportChange, true);
    window.addEventListener("resize", handleViewportChange);
    focusFirst();
    return () => {
      document.removeEventListener("keydown", handleKey, true);
      document.removeEventListener("pointerdown", handlePointer, true);
      window.removeEventListener("scroll", handleViewportChange, true);
      window.removeEventListener("resize", handleViewportChange);
      // Restore focus to the exact invoking control when dismissal leaves
      // focus nowhere useful (Escape, outside click or scroll dismissal).
      const trigger = document.querySelector(triggerSelector);
      const active = document.activeElement;
      if (
        trigger instanceof HTMLElement &&
        (active === null ||
          active === document.body ||
          (menu !== null && menu.contains(active)))
      ) {
        trigger.focus();
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [onClose, path]);

  return createPortal(
    <div
      ref={menuRef}
      className="mf-card-menu mf-row-menu-portal"
      role="menu"
      aria-label={label}
      style={{
        position: "fixed",
        top: position?.top ?? -9999,
        left: position?.left ?? -9999,
        right: "auto",
        visibility: position === null ? "hidden" : "visible",
      }}
    >
      {children}
    </div>,
    document.body,
  );
}
