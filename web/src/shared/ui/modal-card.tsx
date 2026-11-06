/**
 * Feature-independent modal presentation used by the V2 Storage cards
 * (V2-UX-007, Slice50 RO-2).
 *
 * The Automation create/edit card is the visual baseline. This module keeps
 * the reusable, business-free pieces: viewport scroll locking with a stable
 * scrollbar gutter, background inertness, a keyboard focus trap, focus return
 * and the centered card/backdrop/header shell. It owns no form model, no
 * command and no Storage or Automation business rule.
 */

import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type ReactNode,
  type RefObject,
} from "react";

let bodyLockCount = 0;
let savedBodyStyle: {
  readonly overflow: string;
  readonly paddingRight: string;
} | null = null;

/**
 * Lock background scrolling once per active layer stack.
 *
 * Removing the viewport scrollbar normally widens the page by its width. The
 * lock reserves the measured gutter instead, so the list behind the card does
 * not reflow horizontally. A nested layer only increments a counter: the
 * gutter is measured once and restored once, never compensated twice. An
 * overlay-style scrollbar measures zero and receives no padding.
 */
export function useBodyScrollLock(): void {
  useEffect(() => {
    if (typeof document === "undefined" || typeof window === "undefined") {
      return;
    }
    const body = document.body;
    if (bodyLockCount === 0) {
      // Depending on the shell's overflow propagation the classic scrollbar
      // may live on the document element or on <body>. Measure both positive
      // differences; an overlay scrollbar yields zero and receives no padding.
      // A zero-width body (for example a DOM test environment) is ignored.
      const htmlGutter =
        window.innerWidth - document.documentElement.clientWidth;
      const bodyGutter =
        document.body.clientWidth > 0
          ? window.innerWidth - document.body.clientWidth
          : 0;
      const scrollbarWidth = Math.max(0, htmlGutter, bodyGutter);
      const inlinePadding = Number.parseFloat(body.style.paddingRight) || 0;
      savedBodyStyle = {
        overflow: body.style.overflow,
        paddingRight: body.style.paddingRight,
      };
      body.style.overflow = "hidden";
      if (scrollbarWidth > 0) {
        body.style.paddingRight = `${inlinePadding + scrollbarWidth}px`;
      }
    }
    bodyLockCount += 1;
    let released = false;
    return () => {
      if (released) return;
      released = true;
      bodyLockCount = Math.max(0, bodyLockCount - 1);
      if (bodyLockCount === 0 && savedBodyStyle !== null) {
        body.style.overflow = savedBodyStyle.overflow;
        body.style.paddingRight = savedBodyStyle.paddingRight;
        savedBodyStyle = null;
      }
    };
  }, []);
}

/**
 * Coordinated exit duration for the shared card/backdrop exit CSS below
 * (`.mf-modal-layer-exiting`), matching the Automation baseline's 160ms.
 */
export const MODAL_CARD_EXIT_MS = 160;

function prefersReducedMotion(): boolean {
  return (
    typeof window !== "undefined" &&
    typeof window.matchMedia === "function" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches
  );
}

export interface ModalCardExit {
  /** True between a close request and the coordinated exit finishing. */
  readonly closing: boolean;
  /**
   * Begin the shared card/backdrop exit; `close` runs when it finishes
   * (immediately under reduced motion). A request while an exit is already
   * running is ignored, so repeated close gestures cannot schedule a second
   * completion.
   */
  readonly beginClose: (close: () => void) => void;
}

/**
 * The shared exit lifecycle for owners of one modal card.
 *
 * A legal close request first plays the shared exit presentation and only
 * then hands control back to the owner, whose state change unmounts the card
 * and releases the layer's scroll lock, inert background and focus return.
 * The pending timer never outlives the owner: unmounting clears it, so a
 * navigation away mid-exit cannot fire the completion into a dead component.
 */
export function useModalCardExit(): ModalCardExit {
  const [closing, setClosing] = useState(false);
  const closingRef = useRef(false);
  const timerRef = useRef<number | null>(null);
  useEffect(
    () => () => {
      if (timerRef.current !== null) window.clearTimeout(timerRef.current);
    },
    [],
  );
  const beginClose = useCallback((close: () => void) => {
    if (closingRef.current) return;
    closingRef.current = true;
    setClosing(true);
    const finish = () => {
      timerRef.current = null;
      closingRef.current = false;
      setClosing(false);
      close();
    };
    if (prefersReducedMotion()) {
      finish();
      return;
    }
    timerRef.current = window.setTimeout(finish, MODAL_CARD_EXIT_MS);
  }, []);
  return { closing, beginClose };
}

export interface ModalLayerOptions {
  /** Escape asks the owner to close; owners apply their own in-flight rules. */
  readonly onEscape: () => void;
  /** The owner's freshest "a command is in flight" decision. */
  readonly escapeDisabled?: () => boolean;
  /** Focus target when the invoking control no longer exists. */
  readonly fallbackFocusId?: string;
}

export interface ModalLayer {
  readonly layerRef: RefObject<HTMLDivElement | null>;
}

/**
 * The shared keyboard/focus/background lifecycle of one modal layer.
 *
 * - Tab stays inside the visible card.
 * - Escape is delegated to the owner, which may refuse while saving.
 * - The sibling page surface is inert while the card is open.
 * - Focus returns to the invoker (or the declared fallback) with
 *   `preventScroll`, so closing never moves the preserved background.
 */
export function useModalLayer(options: ModalLayerOptions): ModalLayer {
  const layerRef = useRef<HTMLDivElement | null>(null);
  const invokerRef = useRef<Element | null>(
    typeof document === "undefined" ? null : document.activeElement,
  );
  const escapeRef = useRef(options.onEscape);
  const escapeDisabledRef = useRef(options.escapeDisabled);
  useEffect(() => {
    escapeRef.current = options.onEscape;
    escapeDisabledRef.current = options.escapeDisabled;
  });

  useBodyScrollLock();

  useEffect(() => {
    const layer = layerRef.current;
    const focusables = () =>
      Array.from(
        layer?.querySelectorAll<HTMLElement>(
          'button:not(:disabled), [href], input:not(:disabled), select:not(:disabled), textarea:not(:disabled), summary, [tabindex]:not([tabindex="-1"])',
        ) ?? [],
      ).filter((element) => element.offsetParent !== null);
    const handleKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        if (escapeDisabledRef.current?.() === true) return;
        event.preventDefault();
        event.stopPropagation();
        escapeRef.current();
        return;
      }
      if (event.key !== "Tab") return;
      const items = focusables();
      if (items.length === 0) {
        event.preventDefault();
        return;
      }
      const first = items[0];
      const last = items[items.length - 1];
      const active = document.activeElement;
      if (event.shiftKey && (active === first || !layer?.contains(active))) {
        event.preventDefault();
        last.focus();
        return;
      }
      if (!event.shiftKey && (active === last || !layer?.contains(active))) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", handleKey, true);
    return () => document.removeEventListener("keydown", handleKey, true);
  }, []);

  useEffect(() => {
    const layer = layerRef.current;
    const parent = layer?.parentElement;
    if (!layer || !parent) {
      return;
    }
    const siblings = Array.from(parent.children).filter(
      (child): child is HTMLElement =>
        child !== layer && child instanceof HTMLElement,
    );
    const previous = siblings.map((child) => child.hasAttribute("inert"));
    for (const sibling of siblings) sibling.setAttribute("inert", "");
    return () => {
      siblings.forEach((sibling, index) => {
        if (!previous[index]) sibling.removeAttribute("inert");
      });
    };
  }, []);

  useEffect(
    () => () => {
      const invoker = invokerRef.current;
      if (invoker instanceof HTMLElement && document.contains(invoker)) {
        invoker.focus({ preventScroll: true });
        return;
      }
      if (options.fallbackFocusId !== undefined) {
        document
          .getElementById(options.fallbackFocusId)
          ?.focus({ preventScroll: true });
      }
    },
    // The layer's own mount/unmount is the focus-return lifetime.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [],
  );

  return { layerRef };
}

export interface ModalCardShellProps {
  readonly layerRef: RefObject<HTMLDivElement | null>;
  readonly closing: boolean;
  readonly busy: boolean;
  readonly title: string;
  readonly titleId: string;
  /** Stable accessible name when the visible heading alone is ambiguous. */
  readonly accessibleName?: string;
  readonly description: ReactNode;
  readonly closeLabel: string;
  readonly closeDisabled: boolean;
  readonly onRequestClose: () => void;
  /** `form` matches the Automation create/edit geometry; `detail` is calmer. */
  readonly size?: "form" | "detail";
  readonly cardClassName?: string;
  readonly bodyClassName?: string;
  readonly children: ReactNode;
  readonly footer?: ReactNode;
}

/** The centered backdrop, dialog card, header and scrollable body. */
export function ModalCardShell({
  layerRef,
  closing,
  busy,
  title,
  titleId,
  accessibleName,
  description,
  closeLabel,
  closeDisabled,
  onRequestClose,
  size = "form",
  cardClassName,
  bodyClassName,
  children,
  footer,
}: ModalCardShellProps) {
  return (
    <div
      ref={layerRef}
      className={
        closing ? "mf-modal-layer mf-modal-layer-exiting" : "mf-modal-layer"
      }
      onMouseDown={(event) => {
        // The owner decides whether leaving is allowed right now (for example
        // a Storage command already in flight). Backdrop and layer-edge
        // dismissal obey that same permission as the close button.
        if (closeDisabled) return;
        if (event.target === event.currentTarget) onRequestClose();
      }}
      data-modal-card="true"
    >
      <div
        className="mf-modal-backdrop"
        aria-hidden="true"
        onMouseDown={(event) => {
          event.stopPropagation();
          if (closeDisabled) return;
          onRequestClose();
        }}
      />
      <section
        className={[
          "mf-modal-card",
          size === "detail" ? "mf-modal-card-detail" : "",
          cardClassName ?? "",
        ]
          .filter((value) => value !== "")
          .join(" ")}
        role="dialog"
        aria-modal="true"
        aria-label={accessibleName}
        aria-labelledby={accessibleName === undefined ? titleId : undefined}
        aria-busy={busy}
      >
        <header className="mf-modal-header">
          <div>
            <h2 id={titleId}>{title}</h2>
            <p>{description}</p>
          </div>
          <button
            type="button"
            className="mf-modal-close"
            aria-label={closeLabel}
            disabled={closeDisabled}
            onClick={() => {
              if (closeDisabled) return;
              onRequestClose();
            }}
          >
            ×
          </button>
        </header>
        <div
          className={
            bodyClassName === undefined
              ? "mf-modal-body"
              : `mf-modal-body ${bodyClassName}`
          }
        >
          {children}
        </div>
        {footer !== undefined && (
          <footer className="mf-modal-footer">{footer}</footer>
        )}
      </section>
    </div>
  );
}
