/**
 * Shared Files-workspace path presentation (Task 44.5 / Slice 44 RO-5).
 *
 * ResourceLibrary Files and MediaLibrary Files render the same path/control
 * composition, so the bounded breadcrumb region and the exact-identity label
 * live here once.  The components are presentation only: they never trim,
 * normalize or abbreviate the Storage value they are given, and every
 * navigation callback receives the exact raw relative path.
 */

import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Icon } from "./Icons";

/** The stable id of the one disclosure element the path region can show. */
const DISCLOSURE_ID = "mf-crumb-disclosure";

/** The visible marker that makes one invisible boundary space unambiguous. */
export const EDGE_WHITESPACE_MARK = "␣";

export interface EdgeWhitespace {
  readonly leading: boolean;
  readonly trailing: boolean;
  /** A boundary description the operator and assistive technology can read. */
  readonly description: string;
}

/**
 * Does this exact Storage-relative value carry whitespace that changes its
 * identity?  Leading/trailing space is the invisible case the operator cannot
 * see but the Storage provider resolves literally: `SSH ` and `SSH` are two
 * different directories.
 */
export function hasEdgeWhitespace(value: string): boolean {
  return value !== value.trim();
}

/**
 * The boundary whitespace of one exact Storage identity, or `null` for an
 * ordinary value.  The accessible name computation collapses and trims raw
 * whitespace, so a trailing space inside a visible label or `aria-label`
 * cannot by itself tell an assistive-technology user which of two Storage
 * entries is meant; this description is what makes it unambiguous.
 */
export function readEdgeWhitespace(value: string): EdgeWhitespace | null {
  if (!hasEdgeWhitespace(value)) return null;
  const leading = value.length > value.trimStart().length;
  const trailing = value.length > value.trimEnd().length;
  const description =
    leading && trailing
      ? "开头和结尾包含空格"
      : leading
        ? "开头包含空格"
        : "结尾包含空格";
  return { leading, trailing, description };
}

/**
 * An accessible name for one exact Storage identity.  An ordinary value is
 * returned unchanged, so existing names and labels are unaffected; only a
 * value whose real characters carry boundary whitespace gains the explicit
 * description.
 */
export function identityAccessibleName(value: string): string {
  const whitespace = readEdgeWhitespace(value);
  return whitespace === null
    ? value
    : `${value}（名称${whitespace.description}）`;
}

/**
 * The exact Storage identity of one Files entry, presented unambiguously.
 *
 * The server value is rendered character for character, so the label still
 * corresponds to the path that will actually be requested.  Only when it
 * begins or ends with whitespace does the presentation add a visible boundary
 * marker and an explicit assistive description; an ordinary name renders
 * exactly as before.
 */
export function IdentityLabel({ value }: { readonly value: string }) {
  const whitespace = readEdgeWhitespace(value);
  if (whitespace === null) return <>{value}</>;
  return (
    <span
      className="mf-identity-label"
      data-edge-whitespace={
        whitespace.leading && whitespace.trailing
          ? "both"
          : whitespace.leading
            ? "leading"
            : "trailing"
      }
      title={`名称${whitespace.description}`}
    >
      {whitespace.leading && (
        <span className="mf-ws-marker" aria-hidden="true">
          {EDGE_WHITESPACE_MARK}
        </span>
      )}
      <span className="mf-ws-value">{value}</span>
      {whitespace.trailing && (
        <span className="mf-ws-marker" aria-hidden="true">
          {EDGE_WHITESPACE_MARK}
        </span>
      )}
      <span className="mf-visually-hidden">
        {`（名称${whitespace.description}）`}
      </span>
    </span>
  );
}

/** One measured placement of the complete-name disclosure. */
export interface DisclosurePlacement {
  /** False when the anchor itself is outside the visible viewport. */
  readonly visible: boolean;
  readonly top: number;
  readonly left: number;
  readonly maxWidth: number;
}

const DISCLOSURE_GAP = 6;
const DISCLOSURE_MARGIN = 8;
const DISCLOSURE_MAX_WIDTH = 520;
const DISCLOSURE_MIN_WIDTH = 160;

/**
 * Place the complete-name disclosure against its anchor using the element's
 * real rendered height.
 *
 * The height matters: a legal Storage segment can be up to 255 bytes, so its
 * wrapped disclosure is many lines tall.  A fixed reserve would push the
 * distinguishing suffix of a long name below the viewport bottom and hide
 * exactly the characters the disclosure exists to reveal.  The disclosure is
 * therefore preferred below its anchor, flipped above when it does not fit
 * there, and finally clamped inside the viewport.  A zero height (jsdom, or
 * before the first measurement) keeps the plain below-the-anchor placement.
 */
export function placeDisclosure(
  anchor: {
    readonly top: number;
    readonly bottom: number;
    readonly left: number;
  },
  renderedHeight: number,
  viewport: { readonly width: number; readonly height: number },
): DisclosurePlacement {
  const maxWidth = Math.max(
    DISCLOSURE_MIN_WIDTH,
    Math.min(DISCLOSURE_MAX_WIDTH, viewport.width - 2 * DISCLOSURE_MARGIN),
  );
  const left = Math.max(
    DISCLOSURE_MARGIN,
    Math.min(anchor.left, viewport.width - maxWidth - DISCLOSURE_MARGIN),
  );
  // The anchor can scroll out of the visible pane; a fixed disclosure
  // pointing at nothing is worse than none, so hide it instead.
  if (anchor.bottom < 0 || anchor.top > viewport.height) {
    return { visible: false, top: 0, left, maxWidth };
  }
  let top = anchor.bottom + DISCLOSURE_GAP;
  if (renderedHeight > 0) {
    if (top + renderedHeight > viewport.height - DISCLOSURE_MARGIN) {
      top = anchor.top - DISCLOSURE_GAP - renderedHeight;
    }
    const lowest = Math.max(
      DISCLOSURE_MARGIN,
      viewport.height - renderedHeight - DISCLOSURE_MARGIN,
    );
    top = Math.max(DISCLOSURE_MARGIN, Math.min(top, lowest));
  }
  return { visible: true, top, left, maxWidth };
}

function samePlacement(
  first: DisclosurePlacement,
  second: DisclosurePlacement,
): boolean {
  return (
    first.visible === second.visible &&
    first.top === second.top &&
    first.left === second.left &&
    first.maxWidth === second.maxWidth
  );
}

/**
 * The complete exact name of one breadcrumb segment, disclosed on hover and on
 * keyboard focus.
 *
 * The native `title` alone is not a usable keyboard disclosure (it is not
 * focusable, not always shown on focus and can be clipped by the bounded path
 * region), so this renders one shared portal element above every clipping
 * ancestor.  It is presentational: assistive technology reads the link's own
 * explicit accessible name, which already carries the exact value and its
 * boundary-whitespace description.
 */
function CrumbDisclosure({
  anchor,
  value,
}: {
  readonly anchor: HTMLElement;
  readonly value: string;
}) {
  const nodeRef = useRef<HTMLDivElement | null>(null);
  const [position, setPosition] = useState<DisclosurePlacement | null>(null);

  useLayoutEffect(() => {
    const node = nodeRef.current;
    const measure = () => {
      const rect = anchor.getBoundingClientRect();
      // The real rendered height of this exact value, not a fixed reserve.
      // jsdom reports zero, which keeps the plain below-the-anchor placement.
      const renderedHeight = node === null ? 0 : node.offsetHeight;
      const next = placeDisclosure(
        { top: rect.top, bottom: rect.bottom, left: rect.left },
        renderedHeight,
        { width: window.innerWidth, height: window.innerHeight },
      );
      setPosition((previous) =>
        previous !== null && samePlacement(previous, next) ? previous : next,
      );
    };
    measure();
    // Re-measure when the disclosure's own box changes: the first pass applies
    // the viewport-aware max width, which can change how many lines the value
    // wraps to, and that height is what the vertical decision needs.
    const observer =
      typeof ResizeObserver === "undefined"
        ? null
        : new ResizeObserver(() => measure());
    if (observer !== null && node !== null) observer.observe(node);
    // The disclosure follows its anchor rather than dismissing on scroll:
    // focusing or hovering an elided segment legitimately scrolls it into
    // view, and that must not hide the name being disclosed.
    window.addEventListener("resize", measure);
    window.addEventListener("scroll", measure, true);
    return () => {
      observer?.disconnect();
      window.removeEventListener("resize", measure);
      window.removeEventListener("scroll", measure, true);
    };
  }, [anchor, value]);

  return createPortal(
    <div
      ref={nodeRef}
      id={DISCLOSURE_ID}
      className="mf-crumb-disclosure"
      data-testid="crumb-disclosure"
      role="presentation"
      style={{
        top: position?.top ?? -9999,
        left: position?.left ?? -9999,
        maxWidth: position?.maxWidth ?? DISCLOSURE_MAX_WIDTH,
        visibility:
          position === null || !position.visible ? "hidden" : "visible",
      }}
    >
      {value}
    </div>,
    document.body,
  );
}

export interface FilesPathCrumb {
  readonly name: string;
  readonly path: string;
  readonly isRoot: boolean;
}

/**
 * The bounded single-line breadcrumb region of one Files workspace.
 *
 * The root control is always reachable.  Every non-root ancestor keeps its own
 * exact relative path and is reachable with pointer and keyboard; the current
 * segment is marked and brought into view after navigation without scrolling
 * the page.  The combined path scrolls inside this region only, so path
 * overflow can never push the toolbar controls or widen the page.
 *
 * `title` discloses the complete exact name on pointer hover, while the
 * explicit accessible name (which preserves boundary-whitespace
 * disambiguation) discloses it on keyboard focus.  Neither ever substitutes a
 * trimmed or abbreviated value for the path handed back to `onOpenPath`.
 */
export function FilesBreadcrumbs({
  label,
  homeLabel,
  crumbs,
  currentPath,
  onReturnRoot,
  onOpenPath,
}: {
  readonly label: string;
  readonly homeLabel: string;
  readonly crumbs: readonly FilesPathCrumb[];
  readonly currentPath: string;
  readonly onReturnRoot: () => void;
  readonly onOpenPath: (path: string) => void;
}) {
  const trackRef = useRef<HTMLOListElement | null>(null);
  const currentRef = useRef<HTMLLIElement | null>(null);
  const [disclosed, setDisclosed] = useState<{
    readonly anchor: HTMLElement;
    readonly value: string;
  } | null>(null);

  useEffect(() => {
    const track = trackRef.current;
    const current = currentRef.current;
    if (track === null || current === null) return;
    // Reveal the current segment with the smallest local scroll; the page and
    // the pane never move.  jsdom reports zero geometry, which is a no-op.
    const overflow =
      current.offsetLeft + current.offsetWidth - track.clientWidth;
    track.scrollLeft = Math.max(0, overflow);
  }, [currentPath, crumbs]);

  const disclosure =
    disclosed === null ? null : (
      <CrumbDisclosure anchor={disclosed.anchor} value={disclosed.value} />
    );

  return (
    <nav aria-label={label} className="mf-breadcrumbs">
      {disclosure}
      <button
        type="button"
        className="mf-crumb-home"
        aria-label={homeLabel}
        title={homeLabel}
        onClick={onReturnRoot}
      >
        <Icon name="home" />
      </button>
      <ol className="mf-crumb-track" ref={trackRef}>
        {crumbs.map((crumb) =>
          crumb.isRoot ? null : (
            <li
              key={crumb.path}
              className="mf-crumb"
              ref={crumb.path === currentPath ? currentRef : undefined}
            >
              <span className="mf-crumb-separator" aria-hidden="true">
                /
              </span>
              <button
                type="button"
                className={
                  crumb.path === currentPath
                    ? "mf-link-button mf-crumb-link is-current"
                    : "mf-link-button mf-crumb-link"
                }
                aria-current={
                  crumb.path === currentPath ? "location" : undefined
                }
                aria-label={identityAccessibleName(crumb.name)}
                title={identityAccessibleName(crumb.name)}
                onPointerEnter={(event) =>
                  setDisclosed({
                    anchor: event.currentTarget,
                    value: crumb.name,
                  })
                }
                onPointerLeave={() => setDisclosed(null)}
                onFocus={(event) =>
                  setDisclosed({
                    anchor: event.currentTarget,
                    value: crumb.name,
                  })
                }
                onBlur={() => setDisclosed(null)}
                onClick={() => onOpenPath(crumb.path)}
              >
                <IdentityLabel value={crumb.name} />
              </button>
            </li>
          ),
        )}
      </ol>
    </nav>
  );
}
