import { afterEach, describe, expect, it, vi } from "vitest";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import {
  FILES_COLUMN_DEFAULT_WIDTH,
  FILES_COLUMN_MIN_WIDTH,
  FilesColumnResizeHandle,
  FilesDisplaySettings,
  filesSortLabel,
  nextFilesSort,
  sortFilesRows,
  useFilesColumnWidths,
  type FilesSortableRow,
} from "./files-browse-presentation";

afterEach(() => cleanup());

const ROWS: readonly FilesSortableRow[] = [
  {
    name: "Zeta Folder",
    path: "Zeta Folder",
    size: 0,
    isDirectory: true,
  },
  { name: "page-2.mkv", path: "page-2.mkv", size: 0, isDirectory: false },
  { name: "page-10.mkv", path: "page-10.mkv", size: 0, isDirectory: false },
  { name: "页.mkv", path: "页.mkv", size: 10, isDirectory: false },
  { name: " padded .mkv", path: " padded .mkv", size: 100, isDirectory: false },
  { name: "same.mkv", path: "same-a.mkv", size: 50, isDirectory: false },
  { name: "same.mkv", path: "same-b.mkv", size: 50, isDirectory: false },
  { name: "alpha.mkv", path: "alpha.mkv", size: 1024, isDirectory: false },
];

function pathsOf(rows: readonly FilesSortableRow[]): string[] {
  return rows.map((row) => row.path);
}

describe("Files current-page ordering", () => {
  it("keeps server order until a field is selected and never mutates the read rows", () => {
    expect(sortFilesRows(ROWS, null)).toBe(ROWS);
    const ascending = sortFilesRows(ROWS, { field: "name", direction: "asc" });
    expect(pathsOf(ROWS)).toEqual([
      "Zeta Folder",
      "page-2.mkv",
      "page-10.mkv",
      "页.mkv",
      " padded .mkv",
      "same-a.mkv",
      "same-b.mkv",
      "alpha.mkv",
    ]);
    expect(ascending).not.toBe(ROWS);
    expect(pathsOf(ascending)).not.toEqual(pathsOf(ROWS));
  });

  it("orders original names numerically, keeps boundary whitespace and stabilises equal names by exact path", () => {
    const ascending = sortFilesRows(ROWS, { field: "name", direction: "asc" });
    const paths = pathsOf(ascending);
    expect(paths.indexOf("page-2.mkv")).toBeLessThan(
      paths.indexOf("page-10.mkv"),
    );
    expect(paths.indexOf("same-a.mkv")).toBeLessThan(
      paths.indexOf("same-b.mkv"),
    );
    expect(ascending.map((row) => row.name)).toContain(" padded .mkv");
    expect(ascending.map((row) => row.name)).toContain("same.mkv");

    const descending = sortFilesRows(ROWS, {
      field: "name",
      direction: "desc",
    });
    const descendingPaths = pathsOf(descending);
    expect(descendingPaths.at(-1)).toBe(" padded .mkv");
    expect(descendingPaths.indexOf("same-a.mkv")).toBeLessThan(
      descendingPaths.indexOf("same-b.mkv"),
    );
  });

  it("sorts byte sizes with directories after real files in both directions", () => {
    const ascending = sortFilesRows(ROWS, { field: "size", direction: "asc" });
    expect(pathsOf(ascending).slice(0, 6)).toEqual([
      "page-10.mkv",
      "page-2.mkv",
      "页.mkv",
      "same-a.mkv",
      "same-b.mkv",
      " padded .mkv",
    ]);
    expect(pathsOf(ascending).at(-2)).toBe("alpha.mkv");
    expect(pathsOf(ascending).at(-1)).toBe("Zeta Folder");

    const descending = sortFilesRows(ROWS, {
      field: "size",
      direction: "desc",
    });
    expect(pathsOf(descending)[0]).toBe("alpha.mkv");
    expect(pathsOf(descending).at(-1)).toBe("Zeta Folder");
    // A zero-byte file is a real size, not an unavailable directory size.
    expect(pathsOf(descending).indexOf("page-2.mkv")).toBeGreaterThan(0);
    expect(pathsOf(descending).indexOf("page-2.mkv")).toBeLessThan(
      pathsOf(descending).length - 1,
    );
  });

  it("selects ascending first, reverses on the same field and labels the scope", () => {
    const first = nextFilesSort(null, "name");
    expect(first).toEqual({ field: "name", direction: "asc" });
    expect(filesSortLabel(first)).toBe("名称升序");
    const second = nextFilesSort(first, "name");
    expect(second).toEqual({ field: "name", direction: "desc" });
    expect(filesSortLabel(second)).toBe("名称降序");
    expect(nextFilesSort(second, "size")).toEqual({
      field: "size",
      direction: "asc",
    });
    expect(filesSortLabel(null)).toBe("默认顺序");
  });
});

function ResizeHarness() {
  const widths = useFilesColumnWidths(false);
  return (
    <div>
      <table>
        <thead>
          <tr>
            <th data-column-width="name">
              名称
              <FilesColumnResizeHandle
                column="name"
                width={widths.values.name}
                onWidthChange={widths.setColumnWidth}
                onReset={widths.resetWidths}
              />
            </th>
          </tr>
        </thead>
      </table>
      <output data-testid="name-width">{widths.values.name}</output>
      <output data-testid="resized">{String(widths.resized)}</output>
    </div>
  );
}

describe("Files column resizing", () => {
  it("resizes with the keyboard, clamps at the minimum and resets by double click", () => {
    render(<ResizeHarness />);
    const handle = screen.getByRole("separator", {
      name: "调整名称列宽",
    });
    expect(handle).toHaveAttribute(
      "aria-valuenow",
      String(FILES_COLUMN_DEFAULT_WIDTH.name),
    );

    fireEvent.keyDown(handle, { key: "ArrowRight" });
    expect(handle).toHaveAttribute(
      "aria-valuenow",
      String(FILES_COLUMN_DEFAULT_WIDTH.name + 16),
    );
    expect(screen.getByTestId("resized")).toHaveTextContent("true");

    fireEvent.keyDown(handle, { key: "ArrowLeft" });
    expect(handle).toHaveAttribute(
      "aria-valuenow",
      String(FILES_COLUMN_DEFAULT_WIDTH.name),
    );

    fireEvent.pointerDown(handle, {
      pointerId: 1,
      clientX: 100,
      button: 0,
    });
    expect(handle).toHaveClass("is-dragging");
    fireEvent.pointerMove(handle, { pointerId: 1, clientX: -1000 });
    fireEvent.pointerUp(handle, { pointerId: 1, clientX: -1000 });
    expect(handle).not.toHaveClass("is-dragging");
    expect(handle).toHaveAttribute(
      "aria-valuenow",
      String(FILES_COLUMN_MIN_WIDTH.name),
    );

    fireEvent.doubleClick(handle);
    expect(handle).toHaveAttribute(
      "aria-valuenow",
      String(FILES_COLUMN_DEFAULT_WIDTH.name),
    );
    expect(screen.getByTestId("resized")).toHaveTextContent("false");
  });

  it("keeps dragging outside the handle through pointer capture and stops on cancel, blur or pointer up", () => {
    render(<ResizeHarness />);
    const handle = screen.getByRole("separator", {
      name: "调整名称列宽",
    });

    fireEvent.pointerDown(handle, {
      pointerId: 7,
      clientX: 100,
      button: 0,
    });
    fireEvent.pointerMove(handle, { pointerId: 7, clientX: 140 });
    expect(handle).toHaveAttribute(
      "aria-valuenow",
      String(FILES_COLUMN_DEFAULT_WIDTH.name + 40),
    );

    // A move from another pointer cannot continue this drag.
    fireEvent.pointerMove(handle, { pointerId: 8, clientX: 500 });
    expect(handle).toHaveAttribute(
      "aria-valuenow",
      String(FILES_COLUMN_DEFAULT_WIDTH.name + 40),
    );

    fireEvent.pointerUp(handle, { pointerId: 7, clientX: 140 });
    fireEvent.pointerMove(handle, { pointerId: 7, clientX: 500 });
    expect(handle).toHaveAttribute(
      "aria-valuenow",
      String(FILES_COLUMN_DEFAULT_WIDTH.name + 40),
    );

    fireEvent.pointerDown(handle, {
      pointerId: 9,
      clientX: 200,
      button: 0,
    });
    fireEvent.pointerMove(handle, { pointerId: 9, clientX: 220 });
    fireEvent.pointerCancel(handle, { pointerId: 9, clientX: 220 });
    const afterCancel = handle.getAttribute("aria-valuenow");
    fireEvent.pointerMove(handle, { pointerId: 9, clientX: 400 });
    expect(handle).toHaveAttribute("aria-valuenow", afterCancel as string);

    fireEvent.pointerDown(handle, {
      pointerId: 10,
      clientX: 200,
      button: 0,
    });
    fireEvent.pointerMove(handle, { pointerId: 10, clientX: 210 });
    const beforeBlur = handle.getAttribute("aria-valuenow");
    fireEvent.blur(handle);
    fireEvent.pointerMove(handle, { pointerId: 10, clientX: 400 });
    expect(handle).toHaveAttribute("aria-valuenow", beforeBlur as string);
  });
});

describe("Files display settings", () => {
  it("shows the current-page scope and disables default recovery entries", () => {
    render(
      <FilesDisplaySettings
        sort={null}
        onResetSort={() => {}}
        onResetWidths={() => {}}
        widthsResettable={false}
      />,
    );

    expect(screen.getByText("当前页排序：默认顺序")).toBeVisible();
    const trigger = screen.getByRole("button", { name: "显示设置" });
    expect(trigger).toHaveAttribute("aria-haspopup", "menu");
    fireEvent.click(trigger);
    expect(trigger).toHaveAttribute("aria-expanded", "true");
    expect(trigger).toHaveAttribute("aria-controls");
    expect(
      screen.getByRole("menuitem", { name: "恢复默认顺序" }),
    ).toBeDisabled();
    expect(
      screen.getByRole("menuitem", { name: "恢复默认列宽" }),
    ).toBeDisabled();
  });

  it("runs each recovery independently, navigates by keyboard and restores focus on Escape", async () => {
    const onResetSort = vi.fn();
    const onResetWidths = vi.fn();
    render(
      <FilesDisplaySettings
        sort={{ field: "name", direction: "asc" }}
        onResetSort={onResetSort}
        onResetWidths={onResetWidths}
        widthsResettable
      />,
    );

    expect(screen.getByText("当前页排序：名称升序")).toBeVisible();
    const trigger = screen.getByRole("button", { name: "显示设置" });
    fireEvent.click(trigger);
    const order = screen.getByRole("menuitem", { name: "恢复默认顺序" });
    const widths = screen.getByRole("menuitem", { name: "恢复默认列宽" });
    expect(order).toBeEnabled();
    expect(widths).toBeEnabled();
    await waitFor(() => expect(order).toHaveFocus());

    fireEvent.keyDown(document, { key: "ArrowDown" });
    expect(widths).toHaveFocus();
    fireEvent.keyDown(document, { key: "ArrowUp" });
    expect(order).toHaveFocus();

    fireEvent.click(order);
    expect(onResetSort).toHaveBeenCalledTimes(1);
    expect(onResetWidths).not.toHaveBeenCalled();
    expect(screen.queryByRole("menu")).toBeNull();
    expect(trigger).toHaveFocus();

    fireEvent.click(trigger);
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("menu")).toBeNull();
    expect(trigger).toHaveFocus();
  });

  it("closes on an outside pointer and keeps the readable status", () => {
    render(
      <FilesDisplaySettings
        sort={{ field: "size", direction: "desc" }}
        onResetSort={() => {}}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "显示设置" }));
    expect(screen.getByRole("menu")).toBeVisible();
    expect(screen.queryByRole("menuitem", { name: "恢复默认列宽" })).toBeNull();
    fireEvent.pointerDown(document.body);
    expect(screen.queryByRole("menu")).toBeNull();
    expect(screen.getByText("当前页排序：大小降序")).toBeVisible();
  });
});
