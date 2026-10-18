import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, screen, waitFor } from "@testing-library/react";
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

/** The real Preview document with one deterministic preview identity. */
function previewDocument(name: string, previewId: string): Json {
  const value = document(name);
  value["previewId"] = previewId;
  for (const item of value["items"] as Json[]) {
    item["previewId"] = previewId;
  }
  return value;
}

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
    // The unified run inventory landing composes a run-inventory read beside
    // the manual journeys; an empty inventory page keeps those tests focused
    // on the manual surfaces without pretending the endpoint is absent.
    if (call.url.startsWith("/api/v1/operations/runs")) {
      return jsonResponse(runInventoryPageDocument(), 200);
    }
    const response = respond(call);
    if (response !== undefined) {
      return response;
    }
    return jsonResponse({ error: { code: "not_found" } }, 404);
  });
  return { calls };
}

/** The bounded empty inventory page the landing reads first. */
function runInventoryPageDocument(): Json {
  return {
    items: [],
    limit: 20,
    status: null,
    command: null,
    q: null,
    from: null,
    to: null,
    attention: false,
    total: 0,
    truncated: false,
    status_counts: {},
    attention_count: 0,
    population:
      "unified job/task run inventory, deduplicated by explicit task linkage",
    sideEffects: "none",
    previous_cursor: null,
    next_cursor: null,
  };
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
        return jsonResponse(document("resourceLibrarySelected"));
      }
      return undefined;
    });
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/operations");

    await screen.findByRole("heading", { name: "手动操作" });
    // Before an exact scope is chosen, the discovery document advertises no
    // actionable Scan/Preview control.
    expect(screen.queryByRole("link", { name: "发起受限扫描" })).toBeNull();
    expect(screen.queryByRole("link", { name: "运行零变更预览" })).toBeNull();

    await user.selectOptions(
      await screen.findByLabelText("ResourceLibrary scope"),
      "library",
    );
    // The exact backend-advertised scope opens the Scan/Preview entries and
    // the matrix read carries the exact submitted scope.
    expect(screen.queryByRole("link", { name: "发起受限扫描" })).toBeNull();
    expect(
      await screen.findByRole("link", { name: "运行零变更预览" }),
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
      screen.getAllByText(
        "target:Movies/Movies/Anime/One (2001)/One (2001).mkv",
      ).length,
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
      "/ui-v2/operations/preview/new?scopeKind=file&relativePath=One.2001.mkv&resourceLibraryId=library",
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
        return jsonResponse(document("resourceLibrarySelected"));
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

  it("renders ResourceLibrary actions only when the backend advertises them", async () => {
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
      if (call.url.includes("/api/v1/operations/manual-actions")) {
        return jsonResponse(document("resourceLibrarySelected"));
      }
      return undefined;
    });
    authStore.setToken(TOKEN);
    renderApp(
      "/ui-v2/operations?scopeKind=resourceLibrary&resourceLibraryId=library",
    );

    // The Operations workspace owns the manual ResourceLibrary actions now
    // that the retired Library landing no longer exists.
    expect(screen.queryByRole("link", { name: "发起受限扫描" })).toBeNull();
    expect(
      await screen.findByRole("link", { name: "运行零变更预览" }),
    ).toBeVisible();
    expect(
      calls.some(
        (call) =>
          call.url.includes("scopeKind=resourceLibrary") &&
          call.url.includes("resourceLibraryId=library"),
      ),
    ).toBe(true);
  });

  it("shows the backend reason instead of an unadvertised ResourceLibrary action", async () => {
    const unavailable = document("actionMatrix");
    const actions = unavailable["actions"] as Json;
    (actions["preview"] as Json)["available"] = false;
    (actions["preview"] as Json)["reason"] =
      "the FileIndex source is not a verified ready current occurrence";
    recordingFetch((call) => {
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
      if (call.url.includes("/api/v1/operations/manual-actions")) {
        return jsonResponse(unavailable);
      }
      return undefined;
    });
    authStore.setToken(TOKEN);
    const user = userEvent.setup();
    renderApp("/ui-v2/operations");

    await screen.findByRole("heading", { name: "手动操作" });
    await user.selectOptions(
      await screen.findByLabelText("ResourceLibrary scope"),
      "library",
    );
    // The backend reason replaces the unadvertised control instead of a dead
    // button, and no Scan/Preview action is offered for this exact scope.
    expect(
      await screen.findByText(/此范围没有后端公告的手动操作/),
    ).toBeVisible();
    expect(screen.queryByRole("link", { name: "发起受限扫描" })).toBeNull();
    expect(screen.queryByRole("link", { name: "运行零变更预览" })).toBeNull();
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
      "/ui-v2/operations/preview/new?scopeKind=file&relativePath=One.2001.mkv&resourceLibraryId=library",
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
    renderApp("/ui-v2/operations/preview/new?scopeKind=file&fileId=file-1");

    await screen.findByRole("button", { name: "Connect" });
    expect(
      calls.filter((call) => call.url.includes("manual-actions")),
    ).toHaveLength(0);
    expect(authStore.getToken()).toBeNull();
  });
});
