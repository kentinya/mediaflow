import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
  type KeyboardEvent as ReactKeyboardEvent,
  type PointerEvent as ReactPointerEvent,
} from "react";

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
  if (sort === null) return "服务端默认顺序";
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
  const active = sort?.field === field;
  return (
    <button
      type="button"
      className={active ? "mf-sort-button is-active" : "mf-sort-button"}
      title={`按${label}排序（当前页）`}
      onClick={() => onSort(field)}
    >
      <span>{label}</span>
      <span className="mf-sort-indicator" aria-hidden="true">
        {active ? (sort.direction === "asc" ? "↑" : "↓") : "↕"}
      </span>
    </button>
  );
}

/** The visible scope and reset entries for current-page ordering. */
export function FilesSortScope({
  sort,
  onResetSort,
  onResetWidths,
}: {
  readonly sort: FilesSortState | null;
  readonly onResetSort: () => void;
  readonly onResetWidths?: () => void;
}) {
  return (
    <div className="mf-files-sortscope">
      <span className="mf-files-sortscope-label">
        当前页排序：{filesSortLabel(sort)}
      </span>
      <button
        type="button"
        className="mf-files-sortscope-reset"
        onClick={onResetSort}
        disabled={sort === null}
      >
        恢复默认顺序
      </button>
      {onResetWidths !== undefined && (
        <button
          type="button"
          className="mf-files-sortscope-reset"
          onClick={onResetWidths}
        >
          恢复默认列宽
        </button>
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
  readonly tableStyle: CSSProperties | undefined;
  readonly setColumnWidth: (column: FilesColumnKey, width: number) => void;
  readonly resetWidths: () => void;
}

export function useFilesColumnWidths(
  active: boolean,
): FilesColumnWidthsController {
  const tableRef = useRef<HTMLTableElement | null>(null);
  const [resized, setResized] = useState<FilesColumnWidths | null>(null);
  const [measured, setMeasured] = useState<FilesColumnWidths | null>(null);
  const measuredRef = useRef<FilesColumnWidths | null>(null);
  const resizedActive = resized !== null;

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
      setResized((current) => {
        const base =
          current ?? measuredRef.current ?? FILES_COLUMN_DEFAULT_WIDTH;
        if (current !== null && base[column] === clamped) return current;
        return { ...base, [column]: clamped };
      });
    },
    [],
  );

  const resetWidths = useCallback(() => setResized(null), []);

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
      minWidth: `${total}px`,
    } as CSSProperties;
  }, [resized]);

  return {
    tableRef,
    values,
    resized: resized !== null,
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

  useEffect(() => {
    return () => {
      dragRef.current = null;
    };
  }, []);

  const finishDrag = (element: HTMLSpanElement, pointerId: number) => {
    if (dragRef.current?.pointerId !== pointerId) return;
    dragRef.current = null;
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
      className="mf-col-resize"
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
