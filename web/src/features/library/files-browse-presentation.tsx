import {
  useCallback,
  useEffect,
  useId,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
  type KeyboardEvent as ReactKeyboardEvent,
  type PointerEvent as ReactPointerEvent,
} from "react";
import { createPortal } from "react-dom";
import { Icon } from "../../shared/ui/Icons";

/**
 * Presentation-only Files helpers shared by the ResourceLibrary and
 * MediaLibrary browse surfaces. They only order the rows already read and size
 * table columns in this browser session; no helper sorts a whole directory,
 * requests another page or changes an entry identity.
 */

export type FilesSortField = "name" | "size";
export type FilesSortDirection = "asc" | "desc";

export interface FilesSortState {
  readonly field: FilesSortField;
  readonly direction: FilesSortDirection;
}

export interface FilesSortableRow {
  readonly name: string;
  readonly path: string;
  readonly size: number;
  readonly isDirectory: boolean;
}

export type FilesColumnKey = "name" | "type" | "size" | "modified";

export type FilesColumnWidths = Readonly<Record<FilesColumnKey, number>>;

export const FILES_SELECTION_COLUMN_WIDTH = 34;

export const FILES_COLUMN_LABEL: Readonly<Record<FilesColumnKey, string>> = {
  name: "名称",
  type: "类型",
  size: "大小",
  modified: "修改时间",
};

/**
 * Fallback values are only used before the real header widths can be measured
 * (for example in jsdom or during the first paint). A browser replaces them
 * with the actual rendered widths, so the announced current value matches the
 * visible boundary.
 */
export const FILES_COLUMN_DEFAULT_WIDTH: FilesColumnWidths = {
  name: 420,
  type: 76,
  size: 92,
  modified: 128,
};

export const FILES_COLUMN_MIN_WIDTH: FilesColumnWidths = {
  name: 180,
  type: 64,
  size: 72,
  modified: 112,
};

const FILES_COLUMN_MAX_WIDTH: FilesColumnWidths = {
  name: 1200,
  type: 420,
  size: 420,
  modified: 640,
};

const COLUMN_WIDTH_STEP = 16;

const nameCollator = new Intl.Collator("zh-CN", {
  numeric: true,
  sensitivity: "variant",
});

/** A codepoint comparison, so equal visible names never swap on a re-render. */
function compareExactPath(
  left: FilesSortableRow,
  right: FilesSortableRow,
): number {
  if (left.path === right.path) return 0;
  return left.path < right.path ? -1 : 1;
}

function compareName(
  left: FilesSortableRow,
  right: FilesSortableRow,
  direction: FilesSortDirection,
): number {
  const byName = nameCollator.compare(left.name, right.name);
  if (byName === 0) return compareExactPath(left, right);
  return direction === "asc" ? byName : -byName;
}

function compareSize(
  left: FilesSortableRow,
  right: FilesSortableRow,
  direction: FilesSortDirection,
): number {
  // A directory size is not a known byte count. It stays after real files in
  // both directions and is never presented as zero bytes.
  if (left.isDirectory !== right.isDirectory) {
    return left.isDirectory ? 1 : -1;
  }
  if (left.isDirectory) return compareExactPath(left, right);
  const bytes = left.size - right.size;
  if (bytes !== 0) return direction === "asc" ? bytes : -bytes;
  return compareExactPath(left, right);
}

/** Order only the rows of the currently loaded page, leaving the input intact. */
export function sortFilesRows<T extends FilesSortableRow>(
  rows: readonly T[],
  sort: FilesSortState | null,
): readonly T[] {
  if (sort === null) return rows;
  return [...rows].sort((left, right) =>
    sort.field === "name"
      ? compareName(left, right, sort.direction)
      : compareSize(left, right, sort.direction),
  );
}

/** First selection of a field is ascending; a repeated selection reverses it. */
export function nextFilesSort(
  current: FilesSortState | null,
  field: FilesSortField,
): FilesSortState {
  if (current?.field !== field) return { field, direction: "asc" };
  return {
    field,
    direction: current.direction === "asc" ? "desc" : "asc",
  };
}

export function filesSortLabel(sort: FilesSortState | null): string {
  if (sort === null) return "默认顺序";
  const field = sort.field === "name" ? "名称" : "大小";
  return field + (sort.direction === "asc" ? "升序" : "降序");
}

export function FilesSortButton({
  field,
  label,
  sort,
  onSort,
}: {
  readonly field: FilesSortField;
  readonly label: string;
  readonly sort: FilesSortState | null;
  readonly onSort: (field: FilesSortField) => void;
}) {
  const active = sort !== null && sort.field === field;
  const indicator =
    active && sort.direction === "asc"
      ? "sort-asc"
      : active
        ? "sort-desc"
        : "sort";
  return (
    <button
      type="button"
      className={active ? "mf-sort-button is-active" : "mf-sort-button"}
      title={`按${label}排序（当前页）`}
      onClick={() => onSort(field)}
    >
      <span>{label}</span>
      <span className="mf-sort-indicator" aria-hidden="true">
        <Icon name={indicator} />
      </span>
    </button>
  );
}

/**
 * The compact toolbar status for current-page ordering and its display
 * settings menu. Sort and width recovery stay separate actions; the width
 * entry is absent for the grid, where no column geometry is on screen.
 */
export function FilesDisplaySettings({
  sort,
  onResetSort,
  onResetWidths,
  widthsResettable = false,
}: {
  readonly sort: FilesSortState | null;
  readonly onResetSort: () => void;
  readonly onResetWidths?: () => void;
  readonly widthsResettable?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [position, setPosition] = useState<{
    readonly top: number;
    readonly left: number;
  } | null>(null);
  const triggerRef = useRef<HTMLButtonElement | null>(null);
  const menuRef = useRef<HTMLDivElement | null>(null);
  const menuId = useId();
  const openedAtRef = useRef(0);

  const closeMenu = useCallback((restoreFocus: boolean) => {
    setOpen(false);
    setPosition(null);
    if (restoreFocus) triggerRef.current?.focus({ preventScroll: true });
  }, []);

  useLayoutEffect(() => {
    if (!open) return;
    // A focus scroll can already be queued before the menu opens; only a
    // viewport change after this measurement invalidates the anchor.
    openedAtRef.current = performance.now();
    const measure = () => {
      const trigger = triggerRef.current;
      const menu = menuRef.current;
      if (trigger === null) return;
      const anchor = trigger.getBoundingClientRect();
      const width = menu?.offsetWidth ?? 184;
      const height = menu?.offsetHeight ?? 84;
      let left = anchor.right - width;
      left = Math.max(8, Math.min(left, window.innerWidth - width - 8));
      let top = anchor.bottom + 6;
      if (top + height > window.innerHeight - 8) {
        top = anchor.top - height - 6;
      }
      top = Math.max(8, Math.min(top, window.innerHeight - height - 8));
      setPosition((current) =>
        current !== null && current.top === top && current.left === left
          ? current
          : { top, left },
      );
    };
    measure();
    // The first paint may not know the real box yet; measure it once more.
    const frame = window.requestAnimationFrame(measure);
    return () => window.cancelAnimationFrame(frame);
  }, [open]);

  useEffect(() => {
    // The first portal frame is hidden until the anchor has been measured; a
    // hidden element cannot take focus, so wait for the measured position.
    if (!open || position === null) return;
    const menu = menuRef.current;
    const enabledItems = () =>
      Array.from(
        menu?.querySelectorAll<HTMLButtonElement>(
          '[role="menuitem"]:not(:disabled)',
        ) ?? [],
      );
    // Let the initiating click/key event finish its own focus handling first,
    // then place focus on the first enabled action (or the menu itself).
    const frame = window.requestAnimationFrame(() => {
      const first = enabledItems()[0];
      if (first !== undefined) first.focus({ preventScroll: true });
      else menu?.focus({ preventScroll: true });
    });

    const handleKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        event.stopPropagation();
        closeMenu(true);
        return;
      }
      if (event.key === "Tab") {
        // Let Tab continue from the trigger instead of the portal's position.
        closeMenu(true);
        return;
      }
      if (
        event.key !== "ArrowDown" &&
        event.key !== "ArrowUp" &&
        event.key !== "Home" &&
        event.key !== "End"
      ) {
        return;
      }
      const items = enabledItems();
      if (items.length === 0) return;
      event.preventDefault();
      const current = items.indexOf(
        document.activeElement as HTMLButtonElement,
      );
      const next =
        event.key === "Home"
          ? 0
          : event.key === "End"
            ? items.length - 1
            : event.key === "ArrowDown"
              ? (current + 1 + items.length) % items.length
              : (current - 1 + items.length) % items.length;
      items[next]?.focus({ preventScroll: true });
    };
    const handlePointer = (event: PointerEvent) => {
      const target = event.target;
      if (
        target instanceof Node &&
        (menu?.contains(target) ||
          (triggerRef.current?.contains(target) ?? false))
      ) {
        return;
      }
      closeMenu(false);
    };
    const handleViewportChange = (event: Event) => {
      if (event.timeStamp < openedAtRef.current) return;
      if (event.target instanceof Node && menu?.contains(event.target)) return;
      const focusWasInMenu =
        menu !== null && menu.contains(document.activeElement);
      closeMenu(focusWasInMenu);
    };
    document.addEventListener("keydown", handleKey, true);
    document.addEventListener("pointerdown", handlePointer, true);
    window.addEventListener("scroll", handleViewportChange, true);
    window.addEventListener("resize", handleViewportChange);
    return () => {
      window.cancelAnimationFrame(frame);
      document.removeEventListener("keydown", handleKey, true);
      document.removeEventListener("pointerdown", handlePointer, true);
      window.removeEventListener("scroll", handleViewportChange, true);
      window.removeEventListener("resize", handleViewportChange);
    };
  }, [open, position, closeMenu]);

  const runAction = (action: () => void) => {
    closeMenu(true);
    action();
  };

  return (
    <div className="mf-files-display">
      <span className="mf-files-sort-status">
        当前页排序：{filesSortLabel(sort)}
      </span>
      <button
        ref={triggerRef}
        type="button"
        className="mf-files-display-trigger"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={open ? menuId : undefined}
        onClick={() => {
          if (open) closeMenu(false);
          else setOpen(true);
        }}
      >
        <Icon name="settings" />
        显示设置
      </button>
      {open &&
        createPortal(
          <div
            ref={menuRef}
            id={menuId}
            className="mf-card-menu mf-files-display-menu"
            role="menu"
            aria-label="显示设置"
            tabIndex={-1}
            style={{
              position: "fixed",
              top: position?.top ?? -9999,
              left: position?.left ?? -9999,
              right: "auto",
              visibility: position === null ? "hidden" : "visible",
            }}
          >
            <button
              type="button"
              role="menuitem"
              className="mf-card-menu-item"
              disabled={sort === null}
              onClick={() => runAction(onResetSort)}
            >
              恢复默认顺序
            </button>
            {onResetWidths !== undefined && (
              <button
                type="button"
                role="menuitem"
                className="mf-card-menu-item"
                disabled={!widthsResettable}
                onClick={() => runAction(onResetWidths)}
              >
                恢复默认列宽
              </button>
            )}
          </div>,
          document.body,
        )}
    </div>
  );
}

/** Grid selection parity with the table's select-all checkbox. */
export function FilesGridSelectAll({
  allChecked,
  onToggleAll,
}: {
  readonly allChecked: boolean;
  readonly onToggleAll: () => void;
}) {
  return (
    <div className="mf-grid-selection-bar">
      <label className="mf-grid-select-all">
        <input
          type="checkbox"
          aria-label="选择全部"
          checked={allChecked}
          onChange={onToggleAll}
        />
        <span>全选当前页</span>
      </label>
    </div>
  );
}

function clampColumnWidth(column: FilesColumnKey, value: number): number {
  return Math.round(
    Math.min(
      FILES_COLUMN_MAX_WIDTH[column],
      Math.max(FILES_COLUMN_MIN_WIDTH[column], value),
    ),
  );
}

function widthsEqual(
  left: FilesColumnWidths,
  right: FilesColumnWidths,
): boolean {
  return (
    left.name === right.name &&
    left.type === right.type &&
    left.size === right.size &&
    left.modified === right.modified
  );
}

export interface FilesColumnWidthsController {
  readonly tableRef: React.RefObject<HTMLTableElement | null>;
  readonly values: FilesColumnWidths;
  readonly resized: boolean;
  /** Exact session widths; null keeps the default CSS table layout. */
  readonly resizedWidths: FilesColumnWidths | null;
  readonly tableStyle: CSSProperties | undefined;
  readonly setColumnWidth: (column: FilesColumnKey, width: number) => void;
  readonly resetWidths: () => void;
}

/**
 * The pages keep sort and explicit widths above the directory read so a
 * loading/failure branch that unmounts the browse body cannot erase them. The
 * hook still owns the table DOM and its measurements on the browse side.
 */
export interface FilesColumnWidthsControl {
  readonly resized: FilesColumnWidths | null;
  readonly onResizedChange: (widths: FilesColumnWidths | null) => void;
}

/**
 * Column geometry is exact once the operator sets widths: the table is as wide
 * as its five columns, so the browser cannot redistribute leftover space into
 * a column the handle says it resized. Leftover container space stays outside
 * the table. The default layout still fills the pane.
 */
export function FilesTableColumnGroup({
  widths,
}: {
  readonly widths: FilesColumnWidths;
}) {
  return (
    <colgroup>
      <col style={{ width: FILES_SELECTION_COLUMN_WIDTH }} />
      <col style={{ width: widths.name }} />
      <col style={{ width: widths.type }} />
      <col style={{ width: widths.size }} />
      <col style={{ width: widths.modified }} />
    </colgroup>
  );
}

export function useFilesColumnWidths(
  active: boolean,
  control?: FilesColumnWidthsControl,
): FilesColumnWidthsController {
  const tableRef = useRef<HTMLTableElement | null>(null);
  const [internalResized, setInternalResized] =
    useState<FilesColumnWidths | null>(null);
  const [measured, setMeasured] = useState<FilesColumnWidths | null>(null);
  const measuredRef = useRef<FilesColumnWidths | null>(null);
  const resized = control === undefined ? internalResized : control.resized;
  const resizedActive = resized !== null;
  const applyResized = useCallback(
    (next: FilesColumnWidths | null) => {
      if (control === undefined) setInternalResized(next);
      else control.onResizedChange(next);
    },
    [control],
  );

  useLayoutEffect(() => {
    if (!active) return;
    const table = tableRef.current;
    if (table === null) return;
    const measure = () => {
      const next: Record<FilesColumnKey, number> = {
        ...FILES_COLUMN_DEFAULT_WIDTH,
      };
      table
        .querySelectorAll<HTMLTableCellElement>("th[data-column-width]")
        .forEach((cell) => {
          const column = cell.dataset.columnWidth as FilesColumnKey | undefined;
          if (column === undefined) return;
          const width = cell.getBoundingClientRect().width;
          if (Number.isFinite(width) && width > 0) {
            next[column] = Math.round(width);
          }
        });
      measuredRef.current = next;
      setMeasured((current) =>
        current !== null && widthsEqual(current, next) ? current : next,
      );
    };
    measure();
    if (typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(measure);
    observer.observe(table);
    return () => observer.disconnect();
  }, [active, resizedActive]);

  const setColumnWidth = useCallback(
    (column: FilesColumnKey, width: number) => {
      const clamped = clampColumnWidth(column, width);
      const base = resized ?? measuredRef.current ?? FILES_COLUMN_DEFAULT_WIDTH;
      if (resized !== null && base[column] === clamped) return;
      const next = { ...base, [column]: clamped };
      if (control === undefined) setInternalResized(next);
      else control.onResizedChange(next);
    },
    [control, resized],
  );

  const resetWidths = useCallback(() => applyResized(null), [applyResized]);

  const values = resized ?? measured ?? FILES_COLUMN_DEFAULT_WIDTH;
  const tableStyle = useMemo<CSSProperties | undefined>(() => {
    if (resized === null) return undefined;
    const total =
      FILES_SELECTION_COLUMN_WIDTH +
      resized.name +
      resized.type +
      resized.size +
      resized.modified;
    return {
      "--mf-col-name-width": `${resized.name}px`,
      "--mf-col-type-width": `${resized.type}px`,
      "--mf-col-size-width": `${resized.size}px`,
      "--mf-col-modified-width": `${resized.modified}px`,
      width: `${total}px`,
      minWidth: `${total}px`,
    } as CSSProperties;
  }, [resized]);

  return {
    tableRef,
    values,
    resized: resized !== null,
    resizedWidths: resized,
    tableStyle,
    setColumnWidth,
    resetWidths,
  };
}

/**
 * A focusable vertical separator on a column boundary. Pointer capture keeps a
 * drag alive outside the handle; cancel, blur, lost capture and unmount all
 * stop it without affecting sorting, selection or navigation.
 */
export function FilesColumnResizeHandle({
  column,
  width,
  onWidthChange,
  onReset,
}: {
  readonly column: FilesColumnKey;
  readonly width: number;
  readonly onWidthChange: (column: FilesColumnKey, width: number) => void;
  readonly onReset: () => void;
}) {
  const dragRef = useRef<{
    readonly pointerId: number;
    readonly startX: number;
    readonly startWidth: number;
  } | null>(null);
  const [dragging, setDragging] = useState(false);

  useEffect(() => {
    return () => {
      dragRef.current = null;
    };
  }, []);

  const finishDrag = (element: HTMLSpanElement, pointerId: number) => {
    if (dragRef.current?.pointerId !== pointerId) return;
    dragRef.current = null;
    setDragging(false);
    if (
      typeof element.hasPointerCapture === "function" &&
      element.hasPointerCapture(pointerId) &&
      typeof element.releasePointerCapture === "function"
    ) {
      element.releasePointerCapture(pointerId);
    }
  };

  const handlePointerDown = (event: ReactPointerEvent<HTMLSpanElement>) => {
    if (event.button !== 0) return;
    event.preventDefault();
    event.stopPropagation();
    dragRef.current = {
      pointerId: event.pointerId,
      startX: event.clientX,
      startWidth: width,
    };
    setDragging(true);
    event.currentTarget.focus();
    if (typeof event.currentTarget.setPointerCapture === "function") {
      event.currentTarget.setPointerCapture(event.pointerId);
    }
  };

  const handlePointerMove = (event: ReactPointerEvent<HTMLSpanElement>) => {
    const drag = dragRef.current;
    if (drag === null || drag.pointerId !== event.pointerId) return;
    event.preventDefault();
    event.stopPropagation();
    onWidthChange(column, drag.startWidth + (event.clientX - drag.startX));
  };

  const handlePointerEnd = (event: ReactPointerEvent<HTMLSpanElement>) => {
    finishDrag(event.currentTarget, event.pointerId);
  };

  const handleKeyDown = (event: ReactKeyboardEvent<HTMLSpanElement>) => {
    if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
    event.preventDefault();
    event.stopPropagation();
    const delta =
      event.key === "ArrowRight" ? COLUMN_WIDTH_STEP : -COLUMN_WIDTH_STEP;
    onWidthChange(column, width + delta);
  };

  const label = FILES_COLUMN_LABEL[column];
  return (
    <span
      role="separator"
      aria-orientation="vertical"
      aria-label={`调整${label}列宽`}
      aria-valuemin={FILES_COLUMN_MIN_WIDTH[column]}
      aria-valuemax={FILES_COLUMN_MAX_WIDTH[column]}
      aria-valuenow={width}
      aria-valuetext={`${label}列 ${width} 像素`}
      className={dragging ? "mf-col-resize is-dragging" : "mf-col-resize"}
      data-column-resize={column}
      tabIndex={0}
      onPointerDown={handlePointerDown}
      onPointerMove={handlePointerMove}
      onPointerUp={handlePointerEnd}
      onPointerCancel={handlePointerEnd}
      onKeyDown={handleKeyDown}
      onLostPointerCapture={(event) =>
        finishDrag(event.currentTarget, event.pointerId)
      }
      onBlur={(event) => {
        const drag = dragRef.current;
        if (drag !== null) finishDrag(event.currentTarget, drag.pointerId);
      }}
      onDoubleClick={(event) => {
        event.preventDefault();
        event.stopPropagation();
        onReset();
      }}
      onClick={(event) => event.stopPropagation()}
    />
  );
}
