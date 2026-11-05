/**
 * The shared Automation definition card container.
 *
 * Creation and saved-definition editing open the same card over the Automation
 * list: one layer, backdrop, Chinese header, exit animation, discard choice,
 * focus trap and route/browser-back protection (V2-AUTO-013/014, Slice49
 * RO-3). The shell owns no form model and no command; each entry supplies its
 * own fields, submit path and command outcomes. Leaving is blocked only while
 * an in-flight command or unsaved input would be silently abandoned; a
 * submitted-but-unconfirmed command stays reconcilable after a deliberate
 * leave and reopen.
 */

import {
  useEffect,
  useRef,
  useState,
  type ReactNode,
  type RefObject,
} from "react";
import { useBlocker } from "@tanstack/react-router";
import { Button } from "../../shared/ui/Button";

export const AUTOMATION_CARD_EXIT_MS = 160;

export function prefersReducedMotion(): boolean {
  return (
    typeof window !== "undefined" &&
    typeof window.matchMedia === "function" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches
  );
}

export interface AutomationCardExitOptions {
  readonly onClose: () => void;
  /**
   * Whether leaving now would abandon an in-flight command or unsaved input.
   * Read through the freshest closure on every render, so the newest dialog
   * state decides.
   */
  readonly shouldBlockLeave: () => boolean;
  /** Whether a command is currently in flight; commits wait for its outcome. */
  readonly isSubmitting: () => boolean;
  /**
   * Whether there is unsaved input to discard. A retained unknown command is
   * deliberately not input: its owner may leave and reopen to reconcile.
   */
  readonly hasUnsavedInput: () => boolean;
  /** The operator committed the discard choice: clear dialog-owned input. */
  readonly onDiscardCommitted?: () => void;
  /** The field focus returns to when the discard choice is cancelled. */
  readonly firstFieldId: string;
  readonly discardContinueId: string;
  /** Where focus returns when the original invoker is gone (list entry). */
  readonly focusReturnId: string;
}

export interface AutomationCardExit {
  readonly layerRef: RefObject<HTMLDivElement | null>;
  readonly closing: boolean;
  readonly discardPromptOpen: boolean;
  /** The route/browser-back blocker is currently holding a navigation. */
  readonly routeBlocked: boolean;
  readonly attemptClose: () => void;
  readonly commitClose: () => void;
  readonly cancelDiscard: () => void;
  readonly beginExit: (after: (() => void) | null) => void;
  /**
   * Clear an in-progress exit when the same card instance continues with a
   * new route context (a Copy navigation keeps the card mounted): the exit
   * animation belongs to the abandoned context, never to the next one.
   */
  readonly resetExit: () => void;
  /** Release a route-level block together with the command's real outcome. */
  readonly releaseBlockedNavigation: () => void;
  readonly bypassBlockerRef: RefObject<boolean>;
}

/**
 * Exit, discard-choice and navigation protection shared by both card entries.
 * The blocked route/browser-back navigation shows the same pinned decision as
 * the close button; a confirmed outcome releases the block with the result.
 */
export function useAutomationCardExit(
  options: AutomationCardExitOptions,
): AutomationCardExit {
  const { onClose, shouldBlockLeave, hasUnsavedInput, isSubmitting } = options;
  const layerRef = useRef<HTMLDivElement | null>(null);
  const invokerRef = useRef<Element | null>(
    typeof document === "undefined" ? null : document.activeElement,
  );
  const bypassBlockerRef = useRef(false);
  const blockersResetRef = useRef<(() => void) | null>(null);
  const discardReturnFocusRef = useRef<HTMLElement | null>(null);
  const lastFieldFocusRef = useRef<HTMLElement | null>(null);
  const exitTimerRef = useRef<number | null>(null);
  const [closing, setClosing] = useState(false);
  const [discardArmed, setDiscardArmed] = useState(false);

  const blocker = useBlocker({
    shouldBlockFn: () => !bypassBlockerRef.current && shouldBlockLeave(),
    withResolver: true,
  });
  useEffect(() => {
    blockersResetRef.current =
      blocker.status === "blocked" ? blocker.reset : null;
  }, [blocker]);

  const beginExit = (after: (() => void) | null) => {
    if (closing) return;
    setClosing(true);
    const finish = () => {
      if (after !== null) after();
      else onClose();
    };
    if (prefersReducedMotion()) {
      finish();
      return;
    }
    exitTimerRef.current = window.setTimeout(finish, AUTOMATION_CARD_EXIT_MS);
  };

  const commitClose = () => {
    if (isSubmitting()) return;
    setDiscardArmed(false);
    options.onDiscardCommitted?.();
    discardReturnFocusRef.current = null;
    bypassBlockerRef.current = true;
    if (blocker.status === "blocked") {
      const proceed = blocker.proceed;
      beginExit(() => proceed());
      return;
    }
    beginExit(onClose);
  };

  const attemptClose = () => {
    if (isSubmitting() || closing) return;
    if (discardArmed) {
      // A second close gesture while the choice is open keeps the input and
      // returns to the field the operator was editing.
      cancelDiscard();
      return;
    }
    if (blocker.status === "blocked") {
      setDiscardArmed(true);
      return;
    }
    if (hasUnsavedInput()) {
      setDiscardArmed(true);
      return;
    }
    commitClose();
  };
  const attemptCloseRef = useRef(attemptClose);
  useEffect(() => {
    attemptCloseRef.current = attemptClose;
  });

  function releaseBlockedNavigation() {
    const reset = blockersResetRef.current;
    blockersResetRef.current = null;
    if (reset !== null) reset();
  }

  function cancelDiscard() {
    setDiscardArmed(false);
    if (blocker.status === "blocked") blocker.reset();
    const previous = discardReturnFocusRef.current;
    discardReturnFocusRef.current = null;
    window.requestAnimationFrame(() => {
      if (previous !== null && document.contains(previous)) {
        previous.focus();
        return;
      }
      document.getElementById(options.firstFieldId)?.focus();
    });
  }

  const discardPromptOpen =
    !isSubmitting() && (discardArmed || blocker.status === "blocked");

  // The discard choice is always visible and focusable: it is rendered above
  // the scrolling fields, the safe "keep editing" action receives focus, and
  // cancelling restores the exact field the operator was editing.
  useEffect(() => {
    if (!discardPromptOpen) return;
    const active = document.activeElement;
    // Prefer the last field the operator edited, so both the close button and
    // a backdrop click return to the same input rather than a dismissed button.
    discardReturnFocusRef.current =
      lastFieldFocusRef.current ??
      (active instanceof HTMLElement && active !== document.body
        ? active
        : null);
    const timer = window.requestAnimationFrame(() => {
      document.getElementById(options.discardContinueId)?.focus();
    });
    return () => window.cancelAnimationFrame(timer);
  }, [discardPromptOpen, options.discardContinueId]);

  // Escape, Tab trapping and the first focus belong to the card. The invoker
  // is captured at mount; focus returns to it when the card unmounts, or to
  // the fallback list entry after a route-level open/close.
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
        event.preventDefault();
        event.stopPropagation();
        attemptCloseRef.current();
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
    const handleFocusIn = (event: FocusEvent) => {
      const target = event.target;
      if (
        target instanceof HTMLElement &&
        ["INPUT", "SELECT", "TEXTAREA"].includes(target.tagName)
      ) {
        lastFieldFocusRef.current = target;
      }
    };
    layer?.addEventListener("focusin", handleFocusIn);
    return () => {
      document.removeEventListener("keydown", handleKey, true);
      layer?.removeEventListener("focusin", handleFocusIn);
    };
  }, []);

  // The card owns the viewport while open: background scrolling and
  // interaction stop, and the sibling list surface is inert. Cleanup restores
  // exactly the previous state so an interrupted close cannot leave a lock.
  useEffect(() => {
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = previousOverflow;
    };
  }, []);

  useEffect(() => {
    const layer = layerRef.current;
    const parent = layer?.parentElement;
    if (layer === null || parent === null || parent === undefined) return;
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
      if (exitTimerRef.current !== null) {
        window.clearTimeout(exitTimerRef.current);
      }
      const invoker = invokerRef.current;
      if (invoker instanceof HTMLElement && document.contains(invoker)) {
        invoker.focus();
      } else {
        window.setTimeout(() => {
          document.getElementById(options.focusReturnId)?.focus();
        }, 0);
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [],
  );

  const resetExit = () => {
    if (exitTimerRef.current !== null) {
      window.clearTimeout(exitTimerRef.current);
      exitTimerRef.current = null;
    }
    setClosing(false);
    setDiscardArmed(false);
  };

  return {
    layerRef,
    closing,
    discardPromptOpen,
    routeBlocked: blocker.status === "blocked",
    attemptClose,
    commitClose,
    cancelDiscard,
    beginExit,
    resetExit,
    releaseBlockedNavigation,
    bypassBlockerRef,
  };
}

export interface AutomationCardShellProps {
  readonly layerRef: RefObject<HTMLDivElement | null>;
  readonly closing: boolean;
  readonly busy: boolean;
  readonly title: string;
  readonly titleId: string;
  readonly description: string;
  readonly closeLabel: string;
  readonly closeDisabled: boolean;
  readonly onRequestClose: () => void;
  readonly children: ReactNode;
}

/** The card layer, backdrop, dialog section and Chinese header. */
export function AutomationCardShell({
  layerRef,
  closing,
  busy,
  title,
  titleId,
  description,
  closeLabel,
  closeDisabled,
  onRequestClose,
  children,
}: AutomationCardShellProps) {
  return (
    <div
      ref={layerRef}
      className={
        closing
          ? "mf-automation-create-layer mf-automation-create-layer-exiting"
          : "mf-automation-create-layer"
      }
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onRequestClose();
      }}
      data-automation-create-dialog="true"
    >
      <div
        className="mf-automation-create-backdrop"
        aria-hidden="true"
        onMouseDown={(event) => {
          event.stopPropagation();
          onRequestClose();
        }}
      />
      <section
        className="mf-automation-create-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-busy={busy}
      >
        <header className="mf-automation-create-header">
          <div>
            <h2 id={titleId}>{title}</h2>
            <p>{description}</p>
          </div>
          <button
            type="button"
            className="mf-automation-create-close"
            aria-label={closeLabel}
            disabled={closeDisabled}
            onClick={onRequestClose}
          >
            ×
          </button>
        </header>
        <div className="mf-automation-create-body">{children}</div>
      </section>
    </div>
  );
}

export interface AutomationCardDiscardPromptProps {
  readonly questionId: string;
  readonly detailId: string;
  readonly continueId: string;
  readonly question: string;
  readonly detail: string;
  readonly continueLabel?: string;
  readonly discardLabel?: string;
  readonly onContinue: () => void;
  readonly onDiscard: () => void;
}

/** The pinned continue-edit/discard decision shown above the fields. */
export function AutomationCardDiscardPrompt({
  questionId,
  detailId,
  continueId,
  question,
  detail,
  continueLabel = "继续填写",
  discardLabel = "放弃修改",
  onContinue,
  onDiscard,
}: AutomationCardDiscardPromptProps) {
  return (
    <div
      className="mf-automation-create-discard"
      role="alertdialog"
      aria-labelledby={questionId}
      aria-describedby={detailId}
    >
      <p id={questionId}>{question}</p>
      <p className="mf-automation-create-hint" id={detailId}>
        {detail}
      </p>
      <div className="mf-actions">
        <Button
          type="button"
          variant="secondary"
          id={continueId}
          onClick={onContinue}
        >
          {continueLabel}
        </Button>
        <Button type="button" onClick={onDiscard}>
          {discardLabel}
        </Button>
      </div>
    </div>
  );
}
