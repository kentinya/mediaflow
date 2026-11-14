/**
 * Shared Notification card lifecycle.
 *
 * Every Notification surface opens one card over its own list. The card uses
 * the shared `ModalCardShell` presentation (V2-UX-007) and adds only the
 * Notification-specific leaving rules:
 *
 * - Escape, the close control, the backdrop and browser back share one guard;
 * - an in-flight command refuses every conflicting exit;
 * - unsaved input offers an explicit continue/discard choice instead of a
 *   second gesture;
 * - a hard reload is protected while input or a command is still open;
 * - a deliberate navigation after a known command result bypasses the guard.
 */

import { useEffect, useRef, useState, type ReactNode } from "react";
import { useBlocker } from "@tanstack/react-router";
import { Button } from "../../shared/ui/Button";
import {
  ModalCardShell,
  useModalCardExit,
  useModalLayer,
} from "../../shared/ui/modal-card";
import { StatusBanner } from "../../shared/ui/StatusBanner";

export const NOTIFICATION_DISCARD_CONTINUE_ID =
  "notification-card-discard-continue";

export interface NotificationCardGuardOptions {
  /** A command is in flight; no exit may abandon or repeat it. */
  readonly busy: boolean;
  /** The card currently owns input that differs from its saved baseline. */
  readonly dirty: boolean;
  /** The final navigation for a legal close/discard. */
  readonly onClose: () => void;
  /** Clear page-owned input after the operator explicitly discards it. */
  readonly onDiscard: () => void;
  readonly firstFieldId: string;
  readonly fallbackFocusId?: string;
}

export type NotificationLeavePromptMode = "busy" | "discard" | "clean";

export interface NotificationCardGuard {
  readonly layerRef: ReturnType<typeof useModalLayer>["layerRef"];
  readonly closing: boolean;
  readonly discardPromptOpen: boolean;
  readonly promptMode: NotificationLeavePromptMode;
  readonly attemptClose: () => void;
  readonly commitDiscard: () => void;
  readonly cancelDiscard: () => void;
  /**
   * Run a deliberate navigation after a known command result. The guard is
   * bypassed once; the resulting destination owns its own card/read state.
   */
  readonly guardNavigation: (navigate: () => void) => void;
}

export function useNotificationCardGuard(
  options: NotificationCardGuardOptions,
): NotificationCardGuard {
  const { busy, dirty, onClose, onDiscard } = options;
  const stateRef = useRef({ busy, dirty });
  useEffect(() => {
    stateRef.current = { busy, dirty };
  }, [busy, dirty]);
  const bypassRef = useRef(false);
  const [discardArmed, setDiscardArmed] = useState(false);
  const { closing, beginClose } = useModalCardExit();

  const blocker = useBlocker({
    shouldBlockFn: () =>
      !bypassRef.current && (stateRef.current.busy || stateRef.current.dirty),
    withResolver: true,
  });
  const blockerStatus = blocker.status;

  const commitClose = () => {
    if (stateRef.current.busy) return;
    setDiscardArmed(false);
    onDiscard();
    bypassRef.current = true;
    if (blockerStatus === "blocked") {
      const proceed = blocker.proceed;
      beginClose(() => proceed());
      return;
    }
    beginClose(onClose);
  };

  const attemptClose = () => {
    if (stateRef.current.busy || closing) return;
    if (discardArmed) {
      cancelDiscard();
      return;
    }
    if (blockerStatus === "blocked" || stateRef.current.dirty) {
      setDiscardArmed(true);
      return;
    }
    commitClose();
  };

  const cancelDiscard = () => {
    setDiscardArmed(false);
    if (blockerStatus === "blocked") blocker.reset();
    window.requestAnimationFrame(() => {
      document.getElementById(options.firstFieldId)?.focus();
    });
  };

  const guardNavigation = (navigate: () => void) => {
    bypassRef.current = true;
    navigate();
  };

  const { layerRef } = useModalLayer({
    onEscape: () => attemptClose(),
    escapeDisabled: () => stateRef.current.busy,
    fallbackFocusId: options.fallbackFocusId,
  });

  const promptOpen = discardArmed || blockerStatus === "blocked";
  const promptMode: NotificationLeavePromptMode = busy
    ? "busy"
    : dirty
      ? "discard"
      : "clean";

  useEffect(() => {
    if (!promptOpen) return;
    const timer = window.requestAnimationFrame(() => {
      document.getElementById(NOTIFICATION_DISCARD_CONTINUE_ID)?.focus();
    });
    return () => window.cancelAnimationFrame(timer);
  }, [promptOpen]);

  useEffect(() => {
    if (!busy && !dirty) return;
    const handleBeforeUnload = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => window.removeEventListener("beforeunload", handleBeforeUnload);
  }, [busy, dirty]);

  return {
    layerRef,
    closing,
    discardPromptOpen: promptOpen,
    promptMode,
    attemptClose,
    commitDiscard: commitClose,
    cancelDiscard,
    guardNavigation,
  };
}

export interface NotificationDiscardPromptProps {
  readonly mode: NotificationLeavePromptMode;
  readonly onContinue: () => void;
  readonly onDiscard: () => void;
}

/** The one explicit continue/discard decision shared by every exit path. */
export function NotificationDiscardPrompt({
  mode,
  onContinue,
  onDiscard,
}: NotificationDiscardPromptProps) {
  const busy = mode === "busy";
  const clean = mode === "clean";
  return (
    <div
      className="mf-notification-discard"
      role="alertdialog"
      aria-labelledby="notification-discard-question"
      aria-describedby="notification-discard-detail"
    >
      <p id="notification-discard-question">
        {busy ? "当前操作仍在进行" : clean ? "操作已经完成" : "有未保存的修改"}
      </p>
      <p id="notification-discard-detail">
        {busy
          ? "在操作完成前不能离开。请等待结果；结果会保留在卡片中。"
          : clean
            ? "没有未保存的输入。可以离开，也可以继续查看当前卡片。"
            : "离开会丢弃本次尚未保存的输入。已经保存到草稿的内容不受影响。"}
      </p>
      <div className="mf-actions">
        <Button
          type="button"
          variant="secondary"
          id={NOTIFICATION_DISCARD_CONTINUE_ID}
          onClick={onContinue}
        >
          {busy ? "继续等待" : clean ? "继续查看" : "继续编辑"}
        </Button>
        <Button
          type="button"
          variant="secondary"
          disabled={busy}
          onClick={onDiscard}
        >
          {clean ? "离开" : "放弃并离开"}
        </Button>
      </div>
    </div>
  );
}

export interface NotificationCardProps {
  readonly layerRef: ReturnType<typeof useModalLayer>["layerRef"];
  readonly closing: boolean;
  readonly busy: boolean;
  readonly title: string;
  readonly titleId: string;
  readonly description: ReactNode;
  readonly closeDisabled: boolean;
  readonly onRequestClose: () => void;
  readonly size?: "form" | "detail";
  readonly footer?: ReactNode;
  readonly children: ReactNode;
}

/** One card shell for the six Notification surfaces. */
export function NotificationCard({
  layerRef,
  closing,
  busy,
  title,
  titleId,
  description,
  closeDisabled,
  onRequestClose,
  size = "detail",
  footer,
  children,
}: NotificationCardProps) {
  return (
    <ModalCardShell
      layerRef={layerRef}
      closing={closing}
      busy={busy}
      title={title}
      titleId={titleId}
      description={description}
      closeLabel="关闭通知卡片"
      closeDisabled={closeDisabled}
      onRequestClose={onRequestClose}
      size={size}
      bodyClassName="mf-notification-card-body"
      footer={footer}
    >
      {children}
    </ModalCardShell>
  );
}

/** The stable inside-card status state used while a read or command runs. */
export function NotificationCardStatus({
  variant = "info",
  title,
  children,
}: {
  readonly variant?: "info" | "error" | "success" | "warning";
  readonly title: string;
  readonly children: ReactNode;
}) {
  return (
    <div className="mf-notification-card-status">
      <StatusBanner variant={variant} title={title}>
        {children}
      </StatusBanner>
    </div>
  );
}

/**
 * Retain the last successful read while a later refresh fails.
 *
 * The API returns a bounded read-failure document for a 5xx/transport
 * problem. Replacing a card that just completed a known command with a bare
 * failure would erase that command result, so the card keeps the last
 * successfully read durable snapshot and labels it as stale until the read
 * recovers. The retained snapshot is never presented as current truth.
 */
export function useLastSuccessfulRead<T>(value: T | null): T | null {
  const ref = useRef<T | null>(null);
  useEffect(() => {
    if (value !== null) ref.current = value;
  }, [value]);
  // Reading the latest successful snapshot is the hook's presentation
  // contract; the ref is written in an effect, never during render.
  // eslint-disable-next-line react-hooks/refs
  return value ?? ref.current;
}
