import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { authStore } from "../../shared/api/auth-store";
import { renderApp } from "../../../tests/utils";
import fixture from "../../entities/operations/__fixtures__/manual-operations.json";

/**
 * Component/router proof for the manual Scan/Preview journey.
 *
 * Every API payload below is the exact document the real Python API returns
 * (captured into the checked-in fixture and re-proved by
 * `tests/test_manual_operations_contract.py`), so these tests exercise the real
 * route tree, the real query/mutation boundaries and the real normalizers
 * together instead of a hand-written approximation of the contract.
 */

type Json = Record<string, unknown>;

const documents = fixture as unknown as Record<string, Json>;
const TOKEN = "manual-operations-token";

function document(name: string): Json {
  return JSON.parse(JSON.stringify(documents[name])) as Json;
}

/** The real Scan detail document with one deterministic task identity. */
function scanDocument(name: string, taskId: string): Json {
  const value = document(name);
  value["taskId"] = taskId;
  const actions = value["actions"] as Json;
  (actions["cancel"] as Json)["path"] =
    `/api/v1/operations/scans/${taskId}/cancel`;
  return value;
}

/** The real Preview document with one deterministic preview identity. */
function previewDocument(name: string, previewId: string): Json {
  const value = document(name);
  value["previewId"] = previewId;
  for (const item of value["items"] as Json[]) {
    item["previewId"] = previewId;
  }
  return value;
}

const SYSTEM_STATUS = {
  system: {
    configuration_valid: true,
    configuration_authority: "MANAGED",
    configuration_snapshot_id: "snap-1",
  },
  storages: { total: 1, truncated: false, items: [] },
  resource_libraries: {
    total: 1,
    truncated: false,
    items: [
      {
        id: "library",
        storage_id: "source",
        name: "Library",
        enabled: true,
      },
    ],
  },
};

function jsonResponse(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function stubFetch(
  implementation: (
    input: RequestInfo | URL,
    init?: RequestInit,
  ) => Promise<Response>,
): ReturnType<typeof vi.fn> {
  const fetchMock = vi.fn(implementation);
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

interface Call {
  readonly url: string;
  readonly method: string;
  readonly body: unknown;
}

function recordingFetch(respond: (call: Call) => Response | undefined): {
  calls: Call[];
} {
  const calls: Call[] = [];
  stubFetch(async (input, init) => {
    const call: Call = {
      url: String(input),
      method: init?.method ?? "GET",
      body:
        typeof init?.body === "string"
          ? (JSON.parse(init.body) as unknown)
          : null,
    };
    calls.push(call);
    const response = respond(call);
    if (response !== undefined) {
      return response;
    }
    return jsonResponse({ error: { code: "not_found" } }, 404);
  });
  return { calls };
}

afterEach(() => {
  cleanup();
  authStore.clearToken();
  authStore.clearIntendedPath();
  vi.unstubAllGlobals();
});

describe("Operations manual Scan/Preview journeys", () => {
  it("offers no manual action until an exact ResourceLibrary is chosen", async () => {
    const user = userEvent.setup();
    const { calls } = recordingFetch((call) => {
      if (call.url === "/api/v1/operations/workers/readiness") {
        return jsonResponse({
          ready: true,
          condition: "ready",
          category: null,
          durableState: "a Worker is registered",
          sideEffects: "none",
          retrySafe: true,
          nextAction: null,
          activeWorkersCount: 1,
          activeSnapshotId: "snap-1",
        });
      }
      if (call.url === "/api/v1/operations/manual-actions") {
        return jsonResponse(document("resourceLibraryDiscovery"));
      }
      if (call.url.includes("resourceLibraryId=library")) {
        return jsonResponse(document("actionMatrix"));
      }
      return undefined;
    });
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/operations");

    await screen.findByRole("heading", { name: "Manual operations" });
    expect(
      screen.queryByRole("link", { name: "Start bounded Scan" }),
    ).toBeNull();
    expect(
      screen.queryByRole("link", { name: "Run zero-mutation Preview" }),
    ).toBeNull();

    await user.selectOptions(
      await screen.findByLabelText("ResourceLibrary scope"),
      "library",
    );
    expect(
      await screen.findByRole("link", { name: "Start bounded Scan" }),
    ).toBeVisible();
    expect(
      screen.getByRole("link", { name: "Run zero-mutation Preview" }),
    ).toBeVisible();
    await waitFor(() =>
      expect(
        calls.some(
          (call) =>
            call.url.includes("scopeKind=resourceLibrary") &&
            call.url.includes("resourceLibraryId=library"),
        ),
      ).toBe(true),
    );
  });

  it("submits one exact bounded Scan body with the operator's mode and never replays it", async () => {
    const user = userEvent.setup();
    const { calls } = recordingFetch((call) => {
      if (call.url.includes("/api/v1/operations/manual-actions?")) {
        return jsonResponse(document("actionMatrix"));
      }
      if (call.url === "/api/v1/operations/scans" && call.method === "POST") {
        return jsonResponse(scanDocument("scanAdmission", "scan-1"), 202);
      }
      if (call.url.startsWith("/api/v1/operations/scans/")) {
        return jsonResponse(scanDocument("scanDetail", "scan-1"));
      }
      return undefined;
    });
    authStore.setToken(TOKEN);
    renderApp(
      "/ui-v2/operations/scan/new?scopeKind=file&fileId=file-1&resourceLibraryId=library",
    );

    await screen.findByRole("heading", { name: "Start bounded Scan" });
    await user.selectOptions(
      await screen.findByLabelText("Scan mode"),
      "incremental",
    );

    const submit = await screen.findByRole("button", {
      name: "Submit bounded Scan",
    });
    await waitFor(() => expect(submit).toBeEnabled());
    await user.click(submit);

    expect(await screen.findByText("Scan admitted successfully")).toBeVisible();
    await screen.findByRole(
      "heading",
      { name: "Scan scan-1" },
      { timeout: 3000 },
    );
    const submitted = calls.filter(
      (call) => call.url === "/api/v1/operations/scans",
    );
    expect(submitted).toHaveLength(1);
    expect(submitted[0]?.method).toBe("POST");
    expect(submitted[0]?.body).toEqual({
      scopeKind: "file",
      fileId: "file-1",
      resourceLibraryId: "library",
      mode: "incremental",
    });
  });

  it("activates the Scan submission from the keyboard and offers no action for an invalid scope", async () => {
    const user = userEvent.setup();
    const { calls } = recordingFetch((call) => {
      if (call.url.includes("/api/v1/operations/manual-actions")) {
        return jsonResponse(document("actionMatrix"));
      }
      if (call.url === "/api/v1/operations/scans" && call.method === "POST") {
        return jsonResponse(scanDocument("scanAdmission", "scan-1"), 202);
      }
      if (call.url.startsWith("/api/v1/operations/scans/")) {
        return jsonResponse(scanDocument("scanDetail", "scan-1"));
      }
      return undefined;
    });
    authStore.setToken(TOKEN);
    const { queryClient } = renderApp(
      "/ui-v2/operations/scan/new?scopeKind=file&fileId=file-1&resourceLibraryId=library",
    );

    const submit = await screen.findByRole("button", {
      name: "Submit bounded Scan",
    });
    await waitFor(() => expect(submit).toBeEnabled());
    submit.focus();
    expect(submit).toHaveFocus();
    await user.keyboard("{Enter}");
    await screen.findByRole(
      "heading",
      { name: "Scan scan-1" },
      { timeout: 3000 },
    );
    expect(
      calls.filter((call) => call.url === "/api/v1/operations/scans"),
    ).toHaveLength(1);

    queryClient.clear();
    renderApp("/ui-v2/operations/scan/new?scopeKind=bucket");
    await screen.findByRole("heading", { name: "Start bounded Scan" });
    expect(
      await screen.findByRole("heading", { name: "Invalid scope" }),
    ).toBeVisible();
    expect(
      screen.getByRole("button", { name: "Submit bounded Scan" }),
    ).toBeDisabled();
  });

  it("renders the durable Scan detail actions, paging and the exact backend-advertised control", async () => {
    const user = userEvent.setup();
    // The real paged document: page one of a 2-item ResourceLibrary Scan
    // (the fixture canonicalizes the page-window source label because which
    // sibling lands on page one is not part of the API contract).
    const paged = scanDocument("scanLibraryDetail", "scan-1");
    for (const item of paged["items"] as Json[]) {
      item["sourcePath"] = "Two.2002.mkv";
    }
    // Its real next page, as the backend would return it for that cursor.
    const pageTwo = scanDocument("scanLibraryDetail", "scan-1");
    pageTwo["items"] = [
      {
        ...((
          scanDocument("scanDetail", "scan-1")["items"] as Json[]
        )[0] as Json),
        itemId: "item-2",
        sourcePath: "One.2001.mkv",
      },
    ];
    pageTwo["nextItemCursor"] = null;
    pageTwo["itemsTruncated"] = false;
    const cursors: (string | null)[] = [];
    recordingFetch((call) => {
      if (!call.url.startsWith("/api/v1/operations/scans/scan-1")) {
        return undefined;
      }
      const cursorMatch = /itemCursor=([^&]+)/.exec(call.url);
      cursors.push(cursorMatch ? decodeURIComponent(cursorMatch[1]!) : null);
      return jsonResponse(cursorMatch ? pageTwo : paged);
    });
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/operations/scan/scan-1");

    await screen.findByRole("heading", { name: "Scan scan-1" });
    expect(screen.getByText("Two.2002.mkv", { exact: false })).toBeVisible();
    // The paged ResourceLibrary Scan advertises its next page and no
    // cancellation control for its terminal state.
    expect(
      screen.getByRole("button", { name: "Previous items" }),
    ).toBeDisabled();
    expect(screen.queryByRole("button", { name: "Request cancel" })).toBeNull();
    expect(
      screen.getByText(/Cancellation is not available for this Scan/),
    ).toBeVisible();

    const next = screen.getByRole("button", { name: "Next items" });
    expect(next).toBeEnabled();
    await user.click(next);
    expect(
      await screen.findByText("One.2001.mkv", { exact: false }),
    ).toBeVisible();
    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: "Previous items" }),
      ).toBeEnabled(),
    );
    expect(cursors.some((cursor) => cursor !== null)).toBe(true);

    await user.click(screen.getByRole("button", { name: "Previous items" }));
    expect(
      await screen.findByText("Two.2002.mkv", { exact: false }),
    ).toBeVisible();
  });

  it("submits exactly one cooperative Scan cancellation and keeps the durable outcome", async () => {
    const user = userEvent.setup();
    const running = scanDocument("scanAdmission", "scan-1");
    const cancelled = scanDocument("scanDetail", "scan-1");
    cancelled["status"] = "cancelled";
    cancelled["cancellationRequested"] = true;
    ((cancelled["actions"] as Json)["cancel"] as Json)["available"] = false;
    let cancellationRequested = false;
    const { calls } = recordingFetch((call) => {
      if (call.url === "/api/v1/operations/scans/scan-1/cancel") {
        cancellationRequested = true;
        return jsonResponse(cancelled);
      }
      if (call.url.startsWith("/api/v1/operations/scans/scan-1")) {
        return jsonResponse(cancellationRequested ? cancelled : running);
      }
      return undefined;
    });
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/operations/scan/scan-1");

    await screen.findByRole("heading", { name: "Scan scan-1" });
    const cancel = await screen.findByRole("button", {
      name: "Request cancel",
    });
    await user.click(cancel);

    await screen.findByText("Cancel requested");
    await waitFor(() =>
      expect(
        screen.queryByRole("button", { name: "Request cancel" }),
      ).toBeNull(),
    );
    const posted = calls.filter((call) =>
      call.url.endsWith("/api/v1/operations/scans/scan-1/cancel"),
    );
    expect(posted).toHaveLength(1);
    expect(posted[0]?.method).toBe("POST");
    expect(posted[0]?.body).toBeNull();
  });

  it("does not render a Scan cancel control when the backend denies this principal", async () => {
    const readOnly = scanDocument("scanAdmission", "scan-1");
    const actions = readOnly["actions"] as Json;
    const cancel = actions["cancel"] as Json;
    cancel["available"] = false;
    cancel["unavailableReason"] =
      "the connected API principal does not hold the cancel_job permission required for this control";
    recordingFetch((call) =>
      call.url.startsWith("/api/v1/operations/scans/scan-1")
        ? jsonResponse(readOnly)
        : undefined,
    );
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/operations/scan/scan-1");

    await screen.findByRole("heading", { name: "Scan scan-1" });
    expect(screen.queryByRole("button", { name: "Request cancel" })).toBeNull();
    expect(screen.getByText(/cancel_job permission required/)).toBeVisible();
  });

  it("renders the persisted Preview findings without fabricating absent ones", async () => {
    recordingFetch((call) =>
      call.url.startsWith("/api/v1/operations/previews/preview-e2e-001")
        ? jsonResponse(previewDocument("previewDetail", "preview-e2e-001"))
        : undefined,
    );
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/operations/preview/preview-e2e-001");

    await screen.findByRole("heading", {
      name: "Preview preview-e2e-001",
    });
    expect(screen.getAllByText("Zero-mutation").length).toBeGreaterThan(0);
    expect(screen.getByRole("cell", { name: "One" })).toBeVisible();
    expect(
      screen.getAllByText("target:Anime/One (2001)/One (2001).mkv").length,
    ).toBeGreaterThan(0);
    expect(
      screen.getByRole("heading", { name: "Findings for One" }),
    ).toBeVisible();
    expect(screen.getByText("RecognitionType policy")).toBeVisible();
    expect(screen.getByText("type-A")).toBeVisible();
    expect(screen.getByText("Title candidate")).toBeVisible();
    expect(screen.getAllByText("Episodes").length).toBeGreaterThan(0);
    expect(screen.getByText("Version / release group")).toBeVisible();
    expect(screen.getAllByText(/confidence high/).length).toBeGreaterThan(0);
    expect(screen.getByText(/Japanese Animation/)).toBeVisible();
    expect(screen.getByText(/manual-preview/)).toBeVisible();
    expect(screen.getAllByText("Warnings").length).toBeGreaterThan(0);
    expect(screen.getByText(/1 candidate\(s\)/)).toBeVisible();
    expect(screen.getAllByText("Matched by").length).toBeGreaterThan(0);
    expect(screen.getAllByText("candidate_matcher").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Countries").length).toBeGreaterThan(0);
    expect(screen.getAllByText("JP").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Genres").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Animation").length).toBeGreaterThan(0);
    expect(
      screen.getByText(/Candidate reached automatic threshold/),
    ).toBeVisible();
    expect(screen.getByText(/exact title yes/)).toBeVisible();
    expect(screen.getByText(/exact year yes/)).toBeVisible();
    expect(screen.getByText("Directory segments")).toBeVisible();
    expect(screen.getByText("Sanitization changes")).toBeVisible();
    expect(screen.getByText("RecognitionType / policy")).toBeVisible();
    expect(screen.getAllByText(/One \(2001\)\.mkv/).length).toBeGreaterThan(0);
    expect(
      screen.getByText("No sidecar attachment was planned for this item."),
    ).toBeVisible();
    expect(
      screen.getByText("No conflict was recorded for this item."),
    ).toBeVisible();
    expect(screen.getByText("No warning was recorded.")).toBeVisible();
  });

  it("shows each absent persisted finding instead of inventing a value", async () => {
    const absent = previewDocument("previewDetail", "preview-empty-findings");
    const item = (absent["items"] as Json[])[0]!;
    const plan = item["plan"] as Json;
    plan["mediaIdentity"] = null;
    plan["policies"] = null;
    plan["analysis"] = {
      parse: null,
      recognition: null,
      metadata: null,
      naming: null,
      classification: null,
    };
    recordingFetch((call) =>
      call.url.startsWith("/api/v1/operations/previews/preview-empty-findings")
        ? jsonResponse(absent)
        : undefined,
    );
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/operations/preview/preview-empty-findings");

    await screen.findByRole("heading", {
      name: "Preview preview-empty-findings",
    });
    expect(screen.getByText("No policy mapping was recorded.")).toBeVisible();
    expect(screen.getByText("No media identity was recorded.")).toBeVisible();
    expect(screen.getByText("No parse finding was recorded.")).toBeVisible();
    expect(
      screen.getByText("No recognition finding was recorded."),
    ).toBeVisible();
    expect(screen.getByText("No metadata finding was recorded.")).toBeVisible();
    expect(screen.getByText("No naming finding was recorded.")).toBeVisible();
    expect(
      screen.getByText("No classification finding was recorded."),
    ).toBeVisible();
    expect(screen.queryByText("candidate_matcher")).toBeNull();
    expect(screen.queryByText("Japanese Animation")).toBeNull();
  });

  it("fails closed before a hostile action-matrix source can reach the DOM", async () => {
    const hostile = document("actionMatrix");
    hostile["source"] = {
      digest: "a".repeat(64),
      extension: "mkv",
      fileId: "file-1",
      filename: "Bearer hidden-token.mkv",
      occurrenceState: "verified",
      path: "/private/media/Bearer hidden-token.mkv",
      resourceLibraryId: "library",
      scanStatus: "ready",
      sizeBytes: 12,
      storageId: "local",
    };
    recordingFetch((call) =>
      call.url.includes("/api/v1/operations/manual-actions")
        ? jsonResponse(hostile)
        : undefined,
    );
    authStore.setToken(TOKEN);
    renderApp(
      "/ui-v2/operations/scan/new?scopeKind=file&fileId=file-1&resourceLibraryId=library",
    );

    await screen.findByRole("heading", { name: "Action matrix unavailable" });
    const rendered = globalThis.document.body.textContent ?? "";
    expect(rendered).not.toContain("hidden-token");
    expect(rendered).not.toContain("/private/");
    expect(rendered).not.toContain("a".repeat(64));
    expect(
      screen.queryByRole("button", { name: "Submit bounded Scan" }),
    ).toBeNull();
  });

  it("submits one exact bounded Preview body and lands on the durable detail", async () => {
    const user = userEvent.setup();
    const { calls } = recordingFetch((call) => {
      if (call.url.includes("/api/v1/operations/manual-actions")) {
        return jsonResponse(document("actionMatrix"));
      }
      if (
        call.url === "/api/v1/operations/previews" &&
        call.method === "POST"
      ) {
        return jsonResponse(
          previewDocument("previewAdmission", "preview-e2e-001"),
          201,
        );
      }
      if (call.url.startsWith("/api/v1/operations/previews/")) {
        return jsonResponse(
          previewDocument("previewDetail", "preview-e2e-001"),
        );
      }
      return undefined;
    });
    authStore.setToken(TOKEN);
    renderApp(
      "/ui-v2/operations/preview/new?scopeKind=file&relativePath=Movies%2FOne.mkv&resourceLibraryId=library",
    );

    await screen.findByRole("heading", { name: "Run zero-mutation Preview" });
    const submit = await screen.findByRole("button", {
      name: "Submit zero-mutation Preview",
    });
    await waitFor(() => expect(submit).toBeEnabled());
    await user.click(submit);

    expect(
      await screen.findByText("Preview admitted successfully"),
    ).toBeVisible();
    await screen.findByRole(
      "heading",
      { name: "Preview preview-e2e-001" },
      { timeout: 3000 },
    );
    const posted = calls.filter(
      (call) => call.url === "/api/v1/operations/previews",
    );
    expect(posted).toHaveLength(1);
    expect(posted[0]?.body).toEqual({
      scopeKind: "file",
      relativePath: "Movies/One.mkv",
      resourceLibraryId: "library",
    });
  });

  it("renders Library ResourceLibrary actions only when the backend advertises them", async () => {
    const { calls } = recordingFetch((call) => {
      if (call.url === "/api/v1/system/status") {
        return jsonResponse(SYSTEM_STATUS);
      }
      if (call.url.includes("/api/v1/operations/manual-actions")) {
        return jsonResponse(document("actionMatrix"));
      }
      return undefined;
    });
    const user = userEvent.setup();
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/library");

    await screen.findByRole("heading", { name: "Library" });
    await user.click(
      screen.getByRole("button", { name: "Show ResourceLibrary actions" }),
    );
    expect(
      await screen.findByRole("link", { name: "Start bounded Scan" }),
    ).toBeVisible();
    expect(
      screen.getByRole("link", { name: "Run zero-mutation Preview" }),
    ).toBeVisible();
    expect(
      calls.some(
        (call) =>
          call.url.includes("scopeKind=resourceLibrary") &&
          call.url.includes("resourceLibraryId=library"),
      ),
    ).toBe(true);
  });

  it("shows the backend reason instead of an unadvertised Library action", async () => {
    const unavailable = document("actionMatrix");
    const actions = unavailable["actions"] as Json;
    (actions["scan"] as Json)["available"] = false;
    (actions["scan"] as Json)["reason"] =
      "the FileIndex source is not a verified ready current occurrence";
    (actions["preview"] as Json)["available"] = false;
    (actions["preview"] as Json)["reason"] =
      "the FileIndex source is not a verified ready current occurrence";
    recordingFetch((call) => {
      if (call.url === "/api/v1/system/status") {
        return jsonResponse(SYSTEM_STATUS);
      }
      if (call.url.includes("/api/v1/operations/manual-actions")) {
        return jsonResponse(unavailable);
      }
      return undefined;
    });
    const user = userEvent.setup();
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/library");

    await screen.findByRole("heading", { name: "Library" });
    await user.click(
      screen.getByRole("button", { name: "Show ResourceLibrary actions" }),
    );
    const section = (
      await screen.findByRole("heading", { name: "ResourceLibrary actions" })
    ).closest("section");
    expect(section).not.toBeNull();
    const scope = within(section as HTMLElement);
    await waitFor(() =>
      expect(
        scope.queryByRole("link", { name: "Start bounded Scan" }),
      ).toBeNull(),
    );
    expect(
      scope.getByText(
        /Scan unavailable: the FileIndex source is not a verified/,
      ),
    ).toBeVisible();
    expect(
      scope.queryByRole("link", { name: "Run zero-mutation Preview" }),
    ).toBeNull();
  });

  it("keeps the shell recovery path when the action matrix is unavailable", async () => {
    recordingFetch((call) => {
      if (call.url.includes("/api/v1/operations/manual-actions")) {
        return jsonResponse({ error: { code: "service_unavailable" } }, 503);
      }
      return undefined;
    });
    authStore.setToken(TOKEN);
    renderApp(
      "/ui-v2/operations/scan/new?scopeKind=file&fileId=file-1&resourceLibraryId=library",
    );

    await screen.findByRole("heading", { name: "Operations unavailable" });
    expect(
      screen.queryByRole("button", { name: "Submit bounded Scan" }),
    ).toBeNull();
    expect(
      screen.getByRole("link", { name: "Back to Operations" }),
    ).toBeVisible();
  });

  it("does not request manual actions before a principal is connected", async () => {
    const { calls } = recordingFetch(() => undefined);
    renderApp("/ui-v2/operations/scan/new?scopeKind=file&fileId=file-1");

    await screen.findByRole("button", { name: "Connect" });
    expect(
      calls.filter((call) => call.url.includes("manual-actions")),
    ).toHaveLength(0);
    expect(authStore.getToken()).toBeNull();
  });
});
