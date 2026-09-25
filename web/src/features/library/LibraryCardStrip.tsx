import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { Icon } from "../../shared/ui/Icons";
import type { IconName } from "../../shared/ui/Icons";

export interface LibrarySelectorItem {
  readonly id: string;
  readonly name: string | null;
  readonly rootPath: string;
  readonly enabled: boolean;
}

/**
 * The directly visible ResourceLibrary card strip.
 *
 * Complete cards fill the available width; one `更多` entry opens an anchored,
 * unclipped popover with the remaining libraries.  Selecting an overflow
 * library promotes it into the last visible card slot and returns the
 * previously promoted item to the searchable overflow list.
 */

const CARD_MIN_WIDTH = 232;
const CARD_GAP = 16;

function libraryLabel(library: LibrarySelectorItem): string {
  return library.name ?? library.id;
}

function useVisibleCardCount(): {
  readonly containerRef: React.RefObject<HTMLDivElement | null>;
  readonly visibleCount: number;
} {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [visibleCount, setVisibleCount] = useState(4);
  useLayoutEffect(() => {
    const element = containerRef.current;
    if (element === null) return undefined;
    const measure = () => {
      const width = element.clientWidth;
      if (width <= 0) return;
      const fitting = Math.floor(
        (width + CARD_GAP) / (CARD_MIN_WIDTH + CARD_GAP),
      );
      setVisibleCount(Math.max(1, Math.min(8, fitting)));
    };
    measure();
    // ResizeObserver keeps the strip responsive at runtime; environments
    // without it (older engines, jsdom) keep the default card budget.
    if (typeof ResizeObserver === "undefined") {
      window.addEventListener("resize", measure);
      return () => window.removeEventListener("resize", measure);
    }
    const observer = new ResizeObserver(measure);
    observer.observe(element);
    return () => observer.disconnect();
  }, []);
  return { containerRef, visibleCount };
}

function useDismiss(onDismiss: () => void): {
  readonly popoverRef: React.RefObject<HTMLDivElement | null>;
} {
  const popoverRef = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    const handleKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.stopPropagation();
        onDismiss();
      }
    };
    const handlePointer = (event: PointerEvent) => {
      const popover = popoverRef.current;
      const target = event.target;
      if (
        popover !== null &&
        target instanceof Node &&
        !popover.contains(target)
      ) {
        onDismiss();
      }
    };
    document.addEventListener("keydown", handleKey, true);
    document.addEventListener("pointerdown", handlePointer, true);
    return () => {
      document.removeEventListener("keydown", handleKey, true);
      document.removeEventListener("pointerdown", handlePointer, true);
    };
  }, [onDismiss]);
  return { popoverRef };
}

/**
 * The selected card's own `…` action menu.  Distinct from the terminal `更多`
 * overflow selector; opening it never changes the selected library.
 */
export function CardActionMenu({
  libraryId,
  libraryName,
  triggerLabel,
  onRemoveRequest,
  onEditRequest,
  editLabel = "编辑资源库",
  disabled,
  removeLabel = "删除资源库",
}: {
  readonly libraryId: string;
  readonly libraryName: string;
  readonly triggerLabel: string;
  readonly onRemoveRequest: (libraryId: string) => void;
  readonly onEditRequest?: (libraryId: string) => void;
  readonly editLabel?: string;
  readonly disabled?: boolean;
  readonly removeLabel?: string;
}) {
  const [open, setOpen] = useState(false);
  const triggerRef = useRef<HTMLButtonElement | null>(null);
  const { popoverRef } = useDismiss(() => setOpen(false));
  const close = () => {
    setOpen(false);
    triggerRef.current?.focus();
  };
  return (
    <div className="mf-card-menu-anchor">
      <button
        ref={triggerRef}
        type="button"
        className="mf-card-more"
        aria-label={triggerLabel}
        aria-haspopup="menu"
        aria-expanded={open}
        disabled={disabled}
        onClick={() => setOpen((current) => !current)}
      >
        <Icon name="more" />
      </button>
      {open && (
        <div
          ref={popoverRef}
          className="mf-card-menu"
          role="menu"
          aria-label={`资源库操作 ${libraryName}`}
        >
          {onEditRequest && (
            <button
              type="button"
              role="menuitem"
              className="mf-card-menu-item"
              onClick={() => {
                close();
                onEditRequest(libraryId);
              }}
            >
              <Icon name="settings" />
              {editLabel}
            </button>
          )}
          <button
            type="button"
            role="menuitem"
            className="mf-card-menu-item mf-card-menu-danger"
            onClick={() => {
              close();
              onRemoveRequest(libraryId);
            }}
          >
            <Icon name="trash" />
            {""}
            {removeLabel}
          </button>
        </div>
      )}
    </div>
  );
}

function LibraryCard({
  library,
  selected,
  onLibraryChange,
  onRemoveRequest,
  onEditRequest,
  editLabel,
  removalDisabled,
  iconName,
  actionLabel,
  removeLabel,
}: {
  readonly library: LibrarySelectorItem;
  readonly selected: boolean;
  readonly onLibraryChange: (id: string) => void;
  readonly onRemoveRequest: (libraryId: string) => void;
  readonly onEditRequest?: (libraryId: string) => void;
  readonly editLabel: string;
  readonly removalDisabled: boolean;
  readonly iconName: IconName;
  readonly actionLabel: string;
  readonly removeLabel: string;
}) {
  const label = libraryLabel(library);
  return (
    <div
      className={selected ? "mf-library-card is-selected" : "mf-library-card"}
    >
      {/* One semantic selection control owns the complete visible card
          geometry — padding, border, icon and label — so every non-menu point
          of the card selects this library exactly once.  The `…` action menu
          below is a non-nested sibling overlay with its own focus and event
          boundary and never switches libraries. */}
      <button
        type="button"
        className={
          selected
            ? "mf-library-card-select is-selected"
            : "mf-library-card-select"
        }
        aria-pressed={selected}
        onClick={() => onLibraryChange(library.id)}
      >
        <span className="mf-library-card-icon" aria-hidden="true">
          <Icon name={iconName} />
        </span>
        <span className="mf-library-card-name">{label}</span>
      </button>
      {selected && (
        <CardActionMenu
          libraryId={library.id}
          libraryName={label}
          triggerLabel={`${actionLabel}操作 ${label}`}
          onRemoveRequest={onRemoveRequest}
          onEditRequest={onEditRequest}
          editLabel={editLabel}
          disabled={removalDisabled}
          removeLabel={removeLabel}
        />
      )}
    </div>
  );
}

export function LibraryCardStrip({
  libraries,
  selectedLibraryId,
  rootPath,
  onLibraryChange,
  onRemoveRequest,
  onEditRequest,
  editLabel,
  removalBusy,
  iconName,
  actionLabel,
  removeLabel,
}: {
  readonly libraries: readonly LibrarySelectorItem[];
  readonly selectedLibraryId: string;
  readonly rootPath: string;
  readonly onLibraryChange: (id: string) => void;
  readonly onRemoveRequest: (libraryId: string) => void;
  readonly onEditRequest?: (libraryId: string) => void;
  readonly editLabel?: string;
  readonly removalBusy: boolean;
  readonly iconName?: IconName;
  readonly actionLabel?: string;
  readonly removeLabel?: string;
}) {
  const cardIcon = iconName ?? "folder";
  const menuLabel = actionLabel ?? "资源库";
  const menuRemoveLabel = removeLabel ?? "删除资源库";
  const menuEditLabel = editLabel ?? "编辑资源库";
  const { containerRef, visibleCount } = useVisibleCardCount();
  const [moreOpen, setMoreOpen] = useState(false);
  const [overflowQuery, setOverflowQuery] = useState("");
  const moreTriggerRef = useRef<HTMLButtonElement | null>(null);
  const { popoverRef } = useDismiss(() => setMoreOpen(false));
  const overflowMode = libraries.length > visibleCount;
  const cardSlots = overflowMode
    ? Math.max(1, visibleCount - 1)
    : libraries.length;
  const selectedInOverflow =
    overflowMode &&
    cardSlots > 0 &&
    !libraries
      .slice(0, cardSlots - 1)
      .some((library) => library.id === selectedLibraryId);
  const visibleLibraries = overflowMode
    ? [
        ...libraries.slice(0, Math.max(0, cardSlots - 1)),
        ...(selectedInOverflow
          ? [
              libraries.find((library) => library.id === selectedLibraryId) ??
                libraries[cardSlots - 1],
            ]
          : [libraries[cardSlots - 1]]),
      ].filter(
        (library): library is LibrarySelectorItem => library !== undefined,
      )
    : libraries;
  const overflowLibraries = overflowMode
    ? libraries.filter(
        (library) =>
          !visibleLibraries.some((visible) => visible.id === library.id),
      )
    : [];
  const needle = overflowQuery.trim().toLowerCase();
  const filteredOverflow = overflowLibraries.filter(
    (library) =>
      needle === "" ||
      libraryLabel(library).toLowerCase().includes(needle) ||
      library.id.toLowerCase().includes(needle),
  );
  const closeMore = () => {
    setMoreOpen(false);
    setOverflowQuery("");
    moreTriggerRef.current?.focus();
  };
  return (
    <div className="mf-library-strip-block">
      <div className="mf-library-strip" ref={containerRef}>
        {visibleLibraries.map((library) => (
          <LibraryCard
            key={library.id}
            library={library}
            selected={library.id === selectedLibraryId}
            onLibraryChange={(id) => {
              onLibraryChange(id);
              closeMore();
            }}
            onRemoveRequest={onRemoveRequest}
            onEditRequest={onEditRequest}
            editLabel={menuEditLabel}
            removalDisabled={removalBusy}
            iconName={cardIcon}
            actionLabel={menuLabel}
            removeLabel={menuRemoveLabel}
          />
        ))}
        {overflowMode && (
          <div className="mf-library-more-anchor">
            <button
              ref={moreTriggerRef}
              type="button"
              className={
                moreOpen
                  ? "mf-library-card mf-more-card is-open"
                  : "mf-library-card mf-more-card"
              }
              aria-haspopup="dialog"
              aria-expanded={moreOpen}
              aria-label="更多资源库"
              onClick={() => setMoreOpen((current) => !current)}
            >
              <span className="mf-library-card-icon" aria-hidden="true">
                <Icon name={cardIcon} />
              </span>
              <span className="mf-library-card-name">更多</span>
              <span className="mf-library-card-more" aria-hidden="true">
                <Icon name="more" />
              </span>
            </button>
            {moreOpen && (
              <div
                ref={popoverRef}
                className="mf-library-more-popover"
                role="dialog"
                aria-label="更多资源库"
              >
                <h3>更多资源库</h3>
                <div className="mf-more-search">
                  <Icon name="search" />
                  <input
                    type="search"
                    placeholder="搜索资源库"
                    aria-label="搜索资源库"
                    value={overflowQuery}
                    onChange={(event) => setOverflowQuery(event.target.value)}
                  />
                </div>
                <ul className="mf-more-list">
                  {filteredOverflow.map((library) => (
                    <li key={library.id}>
                      <button
                        type="button"
                        className={
                          library.id === selectedLibraryId
                            ? "mf-more-item is-selected"
                            : "mf-more-item"
                        }
                        onClick={() => {
                          onLibraryChange(library.id);
                          closeMore();
                        }}
                      >
                        <span className="mf-more-item-icon" aria-hidden="true">
                          <Icon name="folder" />
                        </span>
                        {libraryLabel(library)}
                      </button>
                    </li>
                  ))}
                  {filteredOverflow.length === 0 && (
                    <li className="mf-more-empty">没有匹配的资源库。</li>
                  )}
                </ul>
              </div>
            )}
          </div>
        )}
      </div>
      <p className="mf-library-root-summary">
        <span className="mf-library-enabled">已启用</span>
        <span>路径: {rootPath === "" ? "/" : "/" + rootPath}</span>
      </p>
    </div>
  );
}
