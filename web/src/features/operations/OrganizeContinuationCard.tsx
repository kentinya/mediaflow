/**
 * The Task Center host of one exact Files preparation continuation
 * (PATCH-20261113-3).
 *
 * The unified task center keeps its own list/detail background mounted and
 * opens one bounded card above it. The card is addressed only by the closed
 * `dialog=organize` marker plus the already-selected `run`; the preparation
 * identity always comes from that Task's backend projection, never from a
 * browser-supplied discovery/library value or from "the newest Task".
 *
 * Three presentations share the same host:
 * - a resolved durable association opens the existing shared
 *   `ManualOrganizeDialog` with all of its decision/analysis/confirmation and
 *   unknown-submission protections unchanged;
 * - an address without a selected Task, a Task without the exact association,
 *   or an unavailable/refused association read renders one bounded explanation
 *   and never creates, guesses or re-submits work.
 *
 * The active card is portaled to the document body so the task center's own
 * run-detail modal layer can suspend its keyboard/inert ownership below it
 * instead of fighting the topmost card's focus trap. Closing removes only the
 * marker; the background search, list position, detail tab and scroll stay
 * exactly as they were.
 */

import { createPortal } from "react-dom";
import type { ApiReadErrorCategory } from "../../shared/api/api-errors";
import { Button } from "../../shared/ui/Button";
import { StatusBanner } from "../../shared/ui/StatusBanner";
import {
  ModalCardShell,
  useModalCardExit,
  useModalLayer,
} from "../../shared/ui/modal-card";
import { ManualOrganizeDialog } from "./ManualOrganizeDialog";

export type OrganizeContinuationState =
  | { readonly kind: "ready"; readonly discoveryId: string }
  | { readonly kind: "missing-run" }
  | { readonly kind: "no-association" }
  | {
      readonly kind: "unavailable";
      readonly title: string;
      readonly nextAction: string | null;
      readonly category: ApiReadErrorCategory | null;
      readonly canRetry: boolean;
    };

export interface OrganizeContinuationHostProps {
  readonly state: OrganizeContinuationState;
  /** Focus target when the invoking continue link no longer exists. */
  readonly fallbackFocusId: string;
  readonly retrying: boolean;
  /** Remove only the hosted-card marker; keep the exact background context. */
  readonly onClose: () => void;
  /** Re-read the same selected Task overview; never a mutation. */
  readonly onRetry: () => void;
  /** Hand the exact returned Task to the center's existing selection. */
  readonly onHandoff: (taskId: string) => void;
}

export function OrganizeContinuationHost({
  state,
  fallbackFocusId,
  retrying,
  onClose,
  onRetry,
  onHandoff,
}: OrganizeContinuationHostProps) {
  // The card is a browser presentation only. The route never server-renders
  // this host, and the portal keeps it outside the suspended background layer.
  if (typeof document === "undefined") return null;
  return createPortal(
    state.kind === "ready" ? (
      <ManualOrganizeDialog
        // A different exact preparation is a different host: remounting never
        // carries one preparation's draft, request or unknown outcome into
        // another.
        key={state.discoveryId}
        session={{ phase: "admitted", discoveryId: state.discoveryId }}
        fallbackFocusId={fallbackFocusId}
        onClose={onClose}
        onHandoff={onHandoff}
      />
    ) : (
      <OrganizeContinuationUnavailable
        state={state}
        fallbackFocusId={fallbackFocusId}
        retrying={retrying}
        onClose={onClose}
        onRetry={onRetry}
      />
    ),
    document.body,
  );
}

/** One bounded explanation for a marker that cannot address real work. */
function OrganizeContinuationUnavailable({
  state,
  fallbackFocusId,
  retrying,
  onClose,
  onRetry,
}: {
  readonly state: Exclude<OrganizeContinuationState, { kind: "ready" }>;
  readonly fallbackFocusId: string;
  readonly retrying: boolean;
  readonly onClose: () => void;
  readonly onRetry: () => void;
}) {
  const exit = useModalCardExit();
  const layer = useModalLayer({
    onEscape: () => exit.beginClose(onClose),
    fallbackFocusId,
  });
  const canRetry = state.kind === "unavailable" && state.canRetry;
  const heading =
    state.kind === "missing-run"
      ? "继续整理地址缺少准确任务"
      : state.kind === "no-association"
        ? "这个任务没有关联的文件整理准备"
        : state.title;
  const explanation =
    state.kind === "missing-run"
      ? "这个地址没有指明要继续哪一次整理准备。未打开任何整理卡，也没有创建或修改任何整理工作。请在任务中心选择原任务后，再点击“继续整理”。"
      : state.kind === "no-association"
        ? "该任务没有持久关联的文件整理准备；未打开整理卡，也不会猜测最新任务或创建新的整理工作。请从资源库文件页重新发起整理；该任务的原流程与文件结果仍可在任务详情中查看。"
        : unavailableExplanation(state.category);
  return (
    <ModalCardShell
      layerRef={layer.layerRef}
      closing={exit.closing}
      busy={retrying}
      title="无法继续这次整理"
      titleId="mf-organize-continuation-unavailable-title"
      accessibleName="无法继续这次整理"
      description="这个整理入口只读取准确任务已持久关联的准备；它不会猜测或创建新的工作。"
      closeLabel="关闭整理提示"
      closeDisabled={exit.closing}
      onRequestClose={() => exit.beginClose(onClose)}
      size="detail"
      footer={
        <>
          <span className="mf-modal-footer-spacer" />
          {canRetry && (
            <Button
              type="button"
              variant="secondary"
              disabled={retrying}
              onClick={onRetry}
            >
              {retrying ? "正在重新读取..." : "重新读取任务"}
            </Button>
          )}
          <Button
            type="button"
            variant="secondary"
            disabled={exit.closing}
            onClick={() => exit.beginClose(onClose)}
          >
            关闭
          </Button>
        </>
      }
    >
      <StatusBanner
        variant={
          state.kind === "unavailable" &&
          (state.category === "unauthorized" || state.category === "forbidden")
            ? "warning"
            : "error"
        }
        title={heading}
      >
        <p role="status">{explanation}</p>
        {state.kind === "unavailable" && state.nextAction !== null && (
          <p>{state.nextAction}</p>
        )}
      </StatusBanner>
    </ModalCardShell>
  );
}

function unavailableExplanation(category: ApiReadErrorCategory | null): string {
  switch (category) {
    case "unauthorized":
      return "当前连接已被拒绝，因此没有读取整理准备，也没有创建工作。重新认证并回到这个地址后，会重新读取同一任务的关联。";
    case "forbidden":
      return "当前账号没有读取该任务整理的权限；未读取准备，也未创建工作。请使用有权限的账号，或返回任务中心。";
    default:
      return "读取这次整理的准备关联没有完成；未打开整理卡，也没有创建、分析或执行任何整理工作。可重新读取同一任务的关联。";
  }
}
