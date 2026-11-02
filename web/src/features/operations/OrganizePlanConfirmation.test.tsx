/**
 * Slice 47 RO-6 journey proof: the prior-outcome warning inside the real plan
 * summary confirmation.
 *
 * These tests drive the real Run once plan-confirmation journey (the page that
 * renders the shared OrganizePlanConfirmation) with a stubbed API whose
 * payloads mirror the exact backend contract: when a selected source's
 * same-version latest formal organizing outcome is failed/partial, the server
 * projects a bounded `history` document into that item's plan and the
 * confirmation page shows it conspicuously before the ordinary selected
 * confirmation.  The assertions prove:
 *
 * - the warning is bound to the right file and says what the operator must
 *   check (source, target, Storage effects; unknown ≠ verified);
 * - the ordinary exact confirmation is the only confirm — no extra
 *   verification page, no routine checkbox, no history-only veto;
 * - a confirmation still submits exactly the reviewed selection for a normal
 *   execution;
 * - a file without applicable history shows no such warning.
 */

import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderApp } from "../../../tests/utils";
import { authStore } from "../../shared/api/auth-store";
import fixture from "../../entities/operations/__fixtures__/manual-operations.json";

type Json = Record<string, unknown>;

const documents = fixture as unknown as Record<string, Json>;
const TOKEN = "history-token";
const DISCOVERY_ID = "discovery-history";
const INTENT_ID = "intent-history";
const PREVIEW_ID = "preview-history";
const API_PATH = `/api/v1/operations/automation/run-once/${DISCOVERY_ID}`;

function jsonResponse(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

afterEach(() => {
  cleanup();
  authStore.clearToken();
  authStore.clearIntendedPath();
  vi.unstubAllGlobals();
});

function action(overrides: Json = {}): Json {
  return {
    available: false,
    method: "POST",
    path: null,
    reason: null,
    sideEffects: "none",
    durableOutcome: null,
    nextAction: null,
    ...overrides,
  };
}

/** The exact bounded Run once projection of a discovery that finished its walk. */
function runOnceDocument(overrides: Json = {}): Json {
  const value: Json = {
    journey: "automation-run-once",
    discoveryId: DISCOVERY_ID,
    definitionId: "nightly",
    definitionName: "Nightly",
    definitionFingerprint: "fingerprint",
    definitionOrigin: {
      origin: "definition-run-once",
      definitionId: "nightly",
      definitionName: "Nightly",
      definitionFingerprint: "fingerprint",
      configurationRevisionId: "revision-1",
      configurationRevisionVersion: 1,
      configurationRevisionDigest: "digest",
      resourceLibraryId: "library",
      sourceScope: "Movies",
      runMode: "automatic-organization",
      definitionItemLimit: 10,
      effectivePrimaryLimit: 10,
      admissionRequestId: null,
    },
    resourceLibraryId: "library",
    sourceScope: "Movies",
    runMode: "automatic-organization",
    definitionItemLimit: 10,
    effectivePrimaryLimit: 10,
    phase: "ready",
    status: "completed",
    version: 3,
    progress: {
      phase: "walking",
      activeCursor: null,
      activeCursorsSeen: [],
      activeDirectory: null,
      counters: {
        activeSeconds: 0.01,
        errorEntries: 0,
        excludedEntries: 0,
        pageFetches: 1,
        primarySources: 1,
        unstableEntries: 0,
        visitedDirectories: 1,
        visitedEntries: 2,
      },
      findings: [],
      reasons: [],
      refusalReasons: [],
      incompleteReason: "none",
      materialRefusal: null,
      message: "",
      pendingDirectories: [],
      pendingFiles: [],
      scopeEntries: [{ kind: "directory", path: "" }],
    },
    counts: {
      visitedEntries: 2,
      visitedDirectories: 1,
      pageFetches: 1,
      primarySources: 1,
      excludedEntries: 0,
      unstableEntries: 0,
      errorEntries: 0,
      activeSeconds: 0.01,
    },
    primarySourceCount: 1,
    intentId: null,
    previewId: null,
    frozen: false,
    frozenAt: null,
    zeroMutation: true,
    sideEffects: "none",
    admissionRequestId: null,
    nextAction: "finalize the completed discovery to review its exact Preview",
    actions: {
      pause: action(),
      cancel: action(),
      resume: action(),
      finalize: action(),
      narrowScope: action(),
      preview: action({ method: "GET" }),
    },
  };
  return { ...value, ...overrides };
}

/** The frozen Run once projection after its exact plan is durably linked. */
function frozenRunOnceDocument(previewId: string | null): Json {
  return runOnceDocument({
    phase: "frozen",
    intentId: INTENT_ID,
    previewId,
    frozen: true,
    frozenAt: "2026-10-21T23:47:21+00:00",
    version: 5,
    nextAction:
      "review the exact zero-mutation manual Preview of the frozen manifest, " +
      "then separately confirm execution",
    actions: {
      pause: action(),
      cancel: action(),
      resume: action(),
      finalize: action(),
      narrowScope: action(),
      preview: action({
        available: true,
        method: "GET",
        path:
          previewId === null
            ? null
            : `/api/v1/operations/organize/previews/${previewId}`,
        nextAction:
          "review the frozen manifest's exact plan summary in this Run once",
      }),
    },
  });
}

/** The contract Preview detail, retargeted to this journey's ids. */
function previewDocument(options: { readonly history?: Json }): Json {
  const value = JSON.parse(
    JSON.stringify(documents["organizePreviewDetail"]),
  ) as Json;
  value["previewId"] = PREVIEW_ID;
  value["intentId"] = INTENT_ID;
  value["executionCandidateItemIds"] = ["item-1"];
  const items = value["items"] as Json[];
  const first = items[0]!;
  first["itemId"] = "item-1";
  first["previewItemId"] = "pitem-1";
  const source = first["source"] as Json;
  source["filename"] = "One.2001.mkv";
  source["path"] = "Movies/One.2001.mkv";
  const selection = value["selection"] as Json;
  selection["selectedItemIds"] = ["item-1"];
  selection["unselectedItemIds"] = [];
  const actions = value["actions"] as Json;
  (actions["execute"] as Json)["available"] = true;
  (actions["execute"] as Json)["reason"] = null;
  (actions["execute"] as Json)["path"] =
    `/api/v1/operations/organize/previews/${PREVIEW_ID}/execute`;
  if (options.history !== undefined) {
    (first["plan"] as Json)["history"] = options.history;
  }
  return value;
}

function failedHistory(): Json {
  return {
    status: "failed",
    recordedAt: "2026-11-01T10:00:00+00:00",
    destinationStorageId: "target",
    destinationPath: "Movies/The Matrix (1999)/The Matrix (1999).mkv",
    completedOperations: ["copy_primary"],
    uncertainEffects: ["source_delete"],
    effectCertainty: "attempted_unverified",
    versionApplicable: true,
    warning:
      "上次整理失败；记录时间 2026-11-01T10:00:00+00:00；目标可能已有文件（Movies/The Matrix (1999)/The Matrix (1999).mkv）；已完成步骤：copy_primary；存在未确认效果（远端操作可能已发生，是否完成无法由本页证明）：source_delete；请核对来源、目标与存储实际效果后再确认本次整理",
  };
}

describe("organize plan confirmation history warning", () => {
  it("shows the prior-outcome warning for the right file before the ordinary confirmation", async () => {
    const user = userEvent.setup();
    let executeBody: Json | null = null;
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        if (url === "/api/v1/auth/principal") {
          return jsonResponse({ principal_id: "operator" });
        }
        if (url === API_PATH) {
          return jsonResponse(frozenRunOnceDocument(PREVIEW_ID));
        }
        if (url === `/api/v1/operations/organize/previews/${PREVIEW_ID}`) {
          return jsonResponse(previewDocument({ history: failedHistory() }));
        }
        if (
          url === `/api/v1/operations/organize/previews/${PREVIEW_ID}/execute`
        ) {
          executeBody = JSON.parse(String(init?.body ?? "{}")) as Json;
          return jsonResponse(
            {
              executionId: "exec-1",
              taskId: "task-1",
              status: "admitted",
              selectedItemCount: 1,
            },
            202,
          );
        }
        if (
          url.startsWith("/api/v1/operations/organize/executions?previewId=")
        ) {
          return jsonResponse({
            journey: "organize",
            items: [],
            limit: 100,
            total: 0,
            truncated: false,
          });
        }
        return jsonResponse({ error: { code: "not_found" } }, 404);
      }),
    );
    authStore.setToken(TOKEN);
    renderApp(`/ui-v2/operations/automation/run-once/${DISCOVERY_ID}`);

    await screen.findByRole("heading", { name: "本次运行计划的零变更摘要" });
    // The conspicuous aggregate banner names the affected file and the check
    // the operator must make; unknown effects are never presented as verified.
    await screen.findByText("部分文件上次整理未完全成功");
    // The affected file is named in the aggregate banner; its own bounded
    // warning text and the unknown-effect wording are visible.
    const banner = screen
      .getByText("部分文件上次整理未完全成功")
      .closest("section, div");
    expect(banner).not.toBeNull();
    expect(banner?.textContent ?? "").toContain("One.2001.mkv");
    expect(banner?.textContent ?? "").toContain("上次整理失败");
    await screen.findAllByText(/存在未确认效果/);
    await screen.findAllByText(
      /请核对来源、目标与存储实际效果后再确认本次整理/,
    );
    // No extra verification page or routine checkbox exists: the only confirm
    // remains the ordinary exact selection confirmation.
    expect(
      screen.queryByRole("checkbox", { name: /我已知晓|我已核对|历史已确认/ }),
    ).toBeNull();

    // The ordinary confirmation still binds to the reviewed selection and
    // executes the normal plan under its exact summary.
    const confirm = await screen.findByRole("button", {
      name: "确认整理本次运行 1 项",
    });
    await user.click(confirm);
    await waitFor(() => expect(executeBody).not.toBeNull());
    expect(executeBody?.["itemIds"]).toEqual(["item-1"]);
    expect(executeBody?.["confirmation"]).toBe(true);
  });

  it("says a possibly-applicable history honestly instead of claiming certainty", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url === "/api/v1/auth/principal") {
          return jsonResponse({ principal_id: "operator" });
        }
        if (url === API_PATH) {
          return jsonResponse(frozenRunOnceDocument(PREVIEW_ID));
        }
        if (url === `/api/v1/operations/organize/previews/${PREVIEW_ID}`) {
          return jsonResponse(
            previewDocument({
              history: {
                status: "partial",
                recordedAt: "2026-11-01T10:00:00+00:00",
                destinationStorageId: "target",
                destinationPath: "Movies/One (2001)/One (2001).mkv",
                completedOperations: [],
                uncertainEffects: [],
                effectCertainty: "partial_effects",
                versionApplicable: false,
                warning:
                  "上次整理部分成功；目标可能已有文件（Movies/One (2001)/One (2001).mkv）；来源版本与该记录不完全可比，此历史可能适用；请核对来源、目标与存储实际效果后再确认本次整理",
              },
            }),
          );
        }
        if (
          url.startsWith("/api/v1/operations/organize/executions?previewId=")
        ) {
          return jsonResponse({
            journey: "organize",
            items: [],
            limit: 100,
            total: 0,
            truncated: false,
          });
        }
        return jsonResponse({ error: { code: "not_found" } }, 404);
      }),
    );
    authStore.setToken(TOKEN);
    renderApp(`/ui-v2/operations/automation/run-once/${DISCOVERY_ID}`);

    await screen.findByRole("heading", { name: "本次运行计划的零变更摘要" });
    const partialBanner = (
      await screen.findByText("部分文件上次整理未完全成功")
    ).closest("section, div");
    expect(partialBanner?.textContent ?? "").toContain("One.2001.mkv");
    expect(partialBanner?.textContent ?? "").toContain("上次整理部分成功");
    // "可能适用" is honest: an incomparable version never claims certainty and
    // the page never says the system verified the target.
    await screen.findAllByText(/此历史可能适用/);
    expect(screen.queryByText(/系统已核验|已验证安全/)).toBeNull();
  });

  it("shows no history banner when the source has no applicable prior outcome", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url === "/api/v1/auth/principal") {
          return jsonResponse({ principal_id: "operator" });
        }
        if (url === API_PATH) {
          return jsonResponse(frozenRunOnceDocument(PREVIEW_ID));
        }
        if (url === `/api/v1/operations/organize/previews/${PREVIEW_ID}`) {
          return jsonResponse(previewDocument({ history: undefined }));
        }
        if (
          url.startsWith("/api/v1/operations/organize/executions?previewId=")
        ) {
          return jsonResponse({
            journey: "organize",
            items: [],
            limit: 100,
            total: 0,
            truncated: false,
          });
        }
        return jsonResponse({ error: { code: "not_found" } }, 404);
      }),
    );
    authStore.setToken(TOKEN);
    renderApp(`/ui-v2/operations/automation/run-once/${DISCOVERY_ID}`);

    await screen.findByRole("heading", { name: "本次运行计划的零变更摘要" });
    await screen.findByText("One.2001.mkv");
    expect(screen.queryByText("部分文件上次整理未完全成功")).toBeNull();
    expect(
      screen.queryByText(/该文件上次整理(失败|部分成功)，请核对后确认/),
    ).toBeNull();
    expect(screen.queryByText(/请核对来源、目标与存储实际效果/)).toBeNull();
  });
});
