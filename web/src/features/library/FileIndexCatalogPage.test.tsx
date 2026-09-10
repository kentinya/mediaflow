import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState, type ComponentProps } from "react";
import type { FileIndexCatalogRecord } from "../../entities/library/file-index-catalog";
import type { SystemStatusModel } from "../../entities/library/system-status";
import type { FileIndexRead } from "../../shared/api/api-client";
import { renderWithProviders } from "../../../tests/utils";
import {
  emptyFileIndexSearch,
  type FileIndexCatalogSearchState,
} from "./file-index-query";
import { FileIndexCatalogView } from "./FileIndexCatalogPage";

const STATUS: SystemStatusModel = {
  authority: "MANAGED",
  configurationActive: true,
  configurationSnapshotId: "revision-1",
  storages: [
    { id: "storage-1", name: "Local media", type: "local", readOnly: true },
  ],
  resourceLibraries: [
    {
      id: "resources-1",
      storageId: "storage-1",
      name: "Incoming media",
      enabled: true,
    },
  ],
};

const RECORD: FileIndexCatalogRecord = {
  fileId: "file-1",
  storageId: "storage-1",
  resourceLibraryId: "resources-1",
  path: "Movies/Example.mkv",
  filename: "Example.mkv",
  extension: "mkv",
  size: 2 * 1024 * 1024,
  modifiedAt: "2026-08-22T12:00:00+00:00",
  updatedAt: "2026-08-22T12:01:00+00:00",
  firstSeenAt: "2026-08-22T11:00:00+00:00",
  lastSeenAt: "2026-08-22T12:01:00+00:00",
  stableSince: "2026-08-22T11:30:00+00:00",
  missingSince: null,
  scanStatus: "ready",
  change: "unchanged",
  occurrenceState: "verified",
  processingDisposition: "organized",
  identitySummary: {
    recognitionType: "Movie",
    provider: "tmdb",
    providerId: "101",
    title: "Example",
    year: 2026,
  },
};

const SECOND_RECORD: FileIndexCatalogRecord = {
  ...RECORD,
  fileId: "file-2",
  path: "Shows/Unverified.mkv",
  filename: "Unverified.mkv",
  updatedAt: "2026-08-22T11:59:00+00:00",
  occurrenceState: "unverified",
  processingDisposition: "attention",
  identitySummary: null,
};

const CATALOG: FileIndexRead = {
  ok: true,
  model: {
    items: [RECORD, SECOND_RECORD],
    limit: 50,
    hasNext: true,
    hasPrevious: false,
  },
};

function viewProps(
  overrides: Partial<ComponentProps<typeof FileIndexCatalogView>> = {},
) {
  const empty = emptyFileIndexSearch();
  return {
    status: STATUS,
    applied: empty,
    draft: empty,
    catalog: CATALOG,
    catalogPending: false,
    catalogFetching: false,
    onDraftChange: vi.fn(),
    onSubmit: vi.fn((event) => event.preventDefault()),
    onReset: vi.fn(),
    onResetPage: vi.fn(),
    onRetry: vi.fn(),
    onNavigate: vi.fn(),
    onRefresh: vi.fn(),
    onBack: vi.fn(),
    ...overrides,
  };
}

afterEach(() => {
  cleanup();
});

describe("FileIndexCatalogView", () => {
  it("renders bounded discovery, occurrence, processing and identity groups", async () => {
    renderWithProviders(<FileIndexCatalogView {...viewProps()} />);

    expect(
      await screen.findByRole("heading", { name: "FileIndex catalog" }),
    ).toBeVisible();
    expect(screen.getAllByText("Discovery and stability")).not.toHaveLength(0);
    expect(screen.getAllByText("Current occurrence")).not.toHaveLength(0);
    expect(screen.getAllByText("Processing disposition")).not.toHaveLength(0);
    expect(screen.getAllByText("Identity summary")).not.toHaveLength(0);
    expect(
      screen.getByText("Verified for this indexed occurrence"),
    ).toBeVisible();
    expect(screen.getByText("Example")).toBeVisible();
    expect(screen.getAllByText("2.0 MB")).not.toHaveLength(0);
    expect(
      screen.getByText(
        "Identity is unavailable in this bounded catalog result.",
      ),
    ).toBeVisible();
    expect(screen.queryByText(/fingerprint/i)).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /reprocess/i }),
    ).not.toBeInTheDocument();
  });

  it("keeps draft filters separate from submitted filters and resets both", async () => {
    const user = userEvent.setup();
    function Harness() {
      const [draft, setDraft] = useState<FileIndexCatalogSearchState>(
        emptyFileIndexSearch(),
      );
      const [applied, setApplied] = useState<FileIndexCatalogSearchState>(
        emptyFileIndexSearch(),
      );
      return (
        <FileIndexCatalogView
          {...viewProps({
            applied,
            draft,
            onDraftChange: (key, value) =>
              setDraft((current) => ({ ...current, [key]: value })),
            onSubmit: (event) => {
              event.preventDefault();
              setApplied({ ...draft });
            },
            onReset: () => {
              const empty = emptyFileIndexSearch();
              setDraft(empty);
              setApplied(empty);
            },
          })}
        />
      );
    }

    renderWithProviders(<Harness />);
    const query = await screen.findByLabelText("Path or filename");
    await user.type(query, "Example");
    expect(screen.getByText("Draft changes not submitted")).toBeVisible();
    expect(
      screen.getByText("None — showing the bounded catalog."),
    ).toBeVisible();

    await user.click(screen.getByRole("button", { name: "Apply filters" }));
    expect(
      screen.queryByText("Draft changes not submitted"),
    ).not.toBeInTheDocument();
    expect(screen.getByText(/Path or filename:/)).toBeVisible();

    await user.click(screen.getByRole("button", { name: "Reset filters" }));
    expect(query).toHaveValue("");
    expect(
      screen.getByText("None — showing the bounded catalog."),
    ).toBeVisible();
  });

  it("pages with updatedAt/fileId cursors while preserving submitted filters", async () => {
    const user = userEvent.setup();
    const applied = {
      ...emptyFileIndexSearch(),
      processingDisposition: "organized",
    };
    const onNavigate = vi.fn();
    renderWithProviders(
      <FileIndexCatalogView
        {...viewProps({ applied, draft: applied, onNavigate })}
      />,
    );

    await user.click(await screen.findByRole("button", { name: "Next page" }));
    expect(onNavigate).toHaveBeenCalledWith({
      ...applied,
      after: SECOND_RECORD.updatedAt,
      before: null,
      cursorFileId: SECOND_RECORD.fileId,
    });
  });

  it("pages backward to adjacent records while preserving submitted filters", async () => {
    const user = userEvent.setup();
    const applied = {
      ...emptyFileIndexSearch(),
      processingDisposition: "organized",
      before: "2026-08-22T12:02:00+00:00",
      cursorFileId: "cursor",
    };
    const onNavigate = vi.fn();
    renderWithProviders(
      <FileIndexCatalogView
        {...viewProps({
          applied,
          draft: applied,
          onNavigate,
          catalog: {
            ok: true,
            model: {
              items: [SECOND_RECORD, RECORD],
              limit: 50,
              hasNext: true,
              hasPrevious: true,
            },
          },
        })}
      />,
    );

    await user.click(
      await screen.findByRole("button", { name: "Previous page" }),
    );
    expect(onNavigate).toHaveBeenCalledWith({
      ...applied,
      after: null,
      before: SECOND_RECORD.updatedAt,
      cursorFileId: SECOND_RECORD.fileId,
    });
  });

  it("presents bounded failure recovery and keeps the read path explicit", async () => {
    const user = userEvent.setup();
    const onReset = vi.fn();
    const onResetPage = vi.fn();
    const onBack = vi.fn();
    const onRetry = vi.fn();
    const failure: FileIndexRead = {
      ok: false,
      failure: {
        kind: "invalid_cursor",
        title: "Page continuation no longer valid",
        nextAction: "Return to the first page and page forward again.",
      },
    };
    renderWithProviders(
      <FileIndexCatalogView
        {...viewProps({
          catalog: failure,
          onReset,
          onResetPage,
          onBack,
          onRetry,
        })}
      />,
    );

    expect(
      await screen.findByRole("heading", {
        name: "Page continuation no longer valid",
      }),
    ).toBeVisible();
    expect(screen.getByText(/No work or mutation was started/)).toBeVisible();
    await user.click(
      screen.getByRole("button", { name: "Return to first page" }),
    );
    await user.click(screen.getByRole("button", { name: "Back to Library" }));
    expect(onReset).not.toHaveBeenCalled();
    expect(onResetPage).toHaveBeenCalledTimes(1);
    expect(onBack).toHaveBeenCalledTimes(1);
    expect(onRetry).not.toHaveBeenCalled();
  });

  it("distinguishes filtered empty results from an unfiltered empty catalog", async () => {
    const user = userEvent.setup();
    const emptyCatalog: FileIndexRead = {
      ok: true,
      model: { items: [], limit: 50, hasNext: false, hasPrevious: false },
    };
    const applied = {
      ...emptyFileIndexSearch(),
      processingDisposition: "failed",
    };
    const onReset = vi.fn();
    renderWithProviders(
      <FileIndexCatalogView
        {...viewProps({
          catalog: emptyCatalog,
          applied,
          draft: applied,
          onReset,
        })}
      />,
    );

    expect(
      await screen.findByRole("heading", {
        name: "No FileIndex records match",
      }),
    ).toBeVisible();
    expect(
      screen.getByText(/returned no record for the submitted filters/),
    ).toBeVisible();
    await user.click(
      screen.getByRole("button", { name: "Reset filters and page" }),
    );
    expect(onReset).toHaveBeenCalledTimes(1);

    cleanup();
    renderWithProviders(
      <FileIndexCatalogView {...viewProps({ catalog: emptyCatalog })} />,
    );
    expect(
      await screen.findByRole("heading", { name: "FileIndex is empty" }),
    ).toBeVisible();
  });

  it("does not present a FileIndex scope without Active managed authority", async () => {
    renderWithProviders(
      <FileIndexCatalogView
        {...viewProps({
          status: { ...STATUS, configurationActive: false },
          catalog: undefined,
        })}
      />,
    );

    expect(
      await screen.findByRole("heading", { name: "No Active runtime" }),
    ).toBeVisible();
    expect(
      screen.queryByRole("heading", { name: "Search and filters" }),
    ).not.toBeInTheDocument();
  });
});
