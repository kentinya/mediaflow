/**
 * Task Center original-submission reconciliation.
 *
 * The card is rendered from the Task's own durable acceptance projection; the
 * explicit action performs one bounded GET against the existing admission
 * reconciliation boundary. No test invents a route: the same URL and identity
 * are what the production component sends.
 */

import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "../../../tests/utils";
import { authStore } from "../../shared/api/auth-store";
import type { RunManualOrganizeSubmission } from "../../entities/operations/run";
import { OrganizeSubmissionVerification } from "./OrganizeSubmissionVerification";

function jsonResponse(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function submission(
  overrides: Partial<RunManualOrganizeSubmission> = {},
): RunManualOrganizeSubmission {
  return {
    executionId: "execution-1",
    previewId: "preview-1",
    intentVersion: 3,
    selectedItemIds: ["item-1"],
    status: "completed",
    createdAt: "2026-08-30T12:00:00+00:00",
    allowOverwrite: false,
    allowSourceCleanup: true,
    items: [
      {
        itemId: "item-1",
        taskItemId: "task-item-1",
        status: "success",
        resultId: "result-1",
        sourcePath: "Dialog/DialogUnknown.2021.mkv",
        checkpointPath: "/api/tasks/task-1/items/task-item-1",
      },
    ],
    ...overrides,
  };
}

function admissionOutcome(overrides: Record<string, unknown> = {}) {
  return {
    outcome: "known",
    reason: null,
    executionId: "execution-1",
    taskId: "task-1",
    status: "completed",
    selectedItemIds: ["item-1"],
    completedItemCount: 1,
    failedItemCount: 0,
    sideEffects: "none",
    nextAction: "open the unified Operations run for this admitted work",
    ...overrides,
  };
}

afterEach(() => {
  cleanup();
  authStore.clearToken();
  vi.unstubAllGlobals();
});

describe("OrganizeSubmissionVerification", () => {
  it("reconciles the exact original acceptance with one bounded read", async () => {
    authStore.setToken("token");
    const requests: Array<{ readonly url: string; readonly method: string }> =
      [];
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        requests.push({
          url: String(input),
          method: init?.method ?? "GET",
        });
        return jsonResponse(admissionOutcome());
      },
    );
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    renderWithProviders(
      <OrganizeSubmissionVerification
        taskId="task-1"
        submissions={[submission()]}
      />,
    );

    const card = await screen.findByRole("region", { name: "原整理提交" });
    expect(card).toHaveTextContent("DialogUnknown.2021.mkv");
    expect(card).toHaveTextContent("摘要版本");
    expect(card).toHaveTextContent("3");
    expect(card).toHaveTextContent("不允许覆盖现有目标；允许清理空来源目录");
    expect(requests).toHaveLength(0);

    await user.click(
      await screen.findByRole("button", { name: "核对提交结果" }),
    );

    await waitFor(() => expect(requests).toHaveLength(1));
    const url = new URL(requests[0]?.url ?? "", "http://localhost");
    expect(requests[0]?.method).toBe("GET");
    expect(url.pathname).toBe(
      "/api/operations/organize/previews/preview-1/admission",
    );
    expect(url.searchParams.get("itemIds")).toBe("item-1");
    expect(url.searchParams.get("expectedIntentVersion")).toBe("3");
    expect(url.searchParams.get("allowOverwrite")).toBe("false");
    expect(url.searchParams.get("allowSourceCleanup")).toBe("true");
    expect(await screen.findByText(/并指向本任务/)).toBeVisible();
    expect(screen.getByText(/成功 1 项，失败 0 项/)).toBeVisible();
    expect(requests).toHaveLength(1);
  });

  it("keeps every acceptance separately reconcilable by its own original request", async () => {
    authStore.setToken("token");
    const requests: Array<{ readonly url: string; readonly method: string }> =
      [];
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = new URL(String(input), "http://localhost");
        requests.push({ url: String(input), method: init?.method ?? "GET" });
        const preview = url.pathname.split("/").at(-2);
        return jsonResponse(
          admissionOutcome({
            executionId:
              preview === "preview-2" ? "execution-2" : "execution-1",
            selectedItemIds: [preview === "preview-2" ? "item-2" : "item-1"],
          }),
        );
      },
    );
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    renderWithProviders(
      <OrganizeSubmissionVerification
        taskId="task-1"
        submissions={[
          submission(),
          submission({
            executionId: "execution-2",
            previewId: "preview-2",
            intentVersion: 4,
            selectedItemIds: ["item-2"],
            createdAt: "2026-08-30T12:05:00+00:00",
            items: [
              {
                itemId: "item-2",
                taskItemId: "task-item-2",
                status: "admitted",
                resultId: null,
                sourcePath: "Dialog/DialogReopen.2029.mkv",
                checkpointPath: "/api/tasks/task-1/items/task-item-2",
              },
            ],
          }),
        ]}
      />,
    );

    const card = await screen.findByRole("region", { name: "原整理提交" });
    expect(card).toHaveTextContent("2 次已受理的精确整理提交");
    const first = within(card).getByRole("article", { name: "第 1 次提交" });
    const second = within(card).getByRole("article", { name: "第 2 次提交" });
    expect(first).toHaveTextContent("DialogUnknown.2021.mkv");
    expect(second).toHaveTextContent("DialogReopen.2029.mkv");
    expect(second).toHaveTextContent("preview-2");
    expect(second).toHaveTextContent("4");
    expect(requests).toHaveLength(0);

    await user.click(
      within(second).getByRole("button", { name: "核对提交结果" }),
    );

    await waitFor(() => expect(requests).toHaveLength(1));
    const url = new URL(requests[0]?.url ?? "", "http://localhost");
    expect(requests[0]?.method).toBe("GET");
    expect(url.pathname).toBe(
      "/api/operations/organize/previews/preview-2/admission",
    );
    expect(url.searchParams.get("itemIds")).toBe("item-2");
    expect(url.searchParams.get("expectedIntentVersion")).toBe("4");
    expect(url.searchParams.get("allowOverwrite")).toBe("false");
    expect(url.searchParams.get("allowSourceCleanup")).toBe("true");
    expect(await within(second).findByText(/并指向本任务/)).toBeVisible();
    // The first acceptance keeps its own state and sends no read.
    expect(requests).toHaveLength(1);
  });

  it("reports a non-equivalent durable record without guessing or replaying", async () => {
    authStore.setToken("token");
    const fetchMock = vi.fn(async () =>
      jsonResponse(
        admissionOutcome({
          outcome: "not_equivalent",
          reason: "selection_or_binding_mismatch",
          taskId: "task-9",
          completedItemCount: 0,
          failedItemCount: 0,
        }),
      ),
    );
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    renderWithProviders(
      <OrganizeSubmissionVerification
        taskId="task-1"
        submissions={[submission()]}
      />,
    );

    await user.click(
      await screen.findByRole("button", { name: "核对提交结果" }),
    );

    expect(
      await screen.findByText(/存在不属于这次原提交选择的持久受理记录/),
    ).toBeVisible();
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(screen.queryByText(/持久受理记录确认这次原提交已受理/)).toBeNull();
  });

  it("keeps the original acceptance visible when the bounded read fails and can retry", async () => {
    authStore.setToken("token");
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        jsonResponse({ code: "internal_error", message: "unavailable" }, 503),
      )
      .mockResolvedValueOnce(jsonResponse(admissionOutcome()));
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    renderWithProviders(
      <OrganizeSubmissionVerification
        taskId="task-1"
        submissions={[submission()]}
      />,
    );

    await user.click(
      await screen.findByRole("button", { name: "核对提交结果" }),
    );

    expect(await screen.findByText("核对读取未完成")).toBeVisible();
    expect(screen.getByText(/原提交记录和当前任务状态保持不变/)).toBeVisible();
    expect(screen.getByText("DialogUnknown.2021.mkv")).toBeVisible();
    expect(fetchMock).toHaveBeenCalledTimes(1);

    await user.click(
      await screen.findByRole("button", { name: "重新核对提交结果" }),
    );

    expect(await screen.findByText(/并指向本任务/)).toBeVisible();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("does not keep a previous success when the next reconciliation read fails", async () => {
    authStore.setToken("token");
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(admissionOutcome()))
      .mockResolvedValueOnce(
        jsonResponse({ code: "internal_error", message: "unavailable" }, 503),
      );
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    renderWithProviders(
      <OrganizeSubmissionVerification
        taskId="task-1"
        submissions={[submission()]}
      />,
    );

    await user.click(
      await screen.findByRole("button", { name: "核对提交结果" }),
    );
    expect(await screen.findByText(/并指向本任务/)).toBeVisible();

    await user.click(screen.getByRole("button", { name: "核对提交结果" }));

    expect(await screen.findByText("核对读取未完成")).toBeVisible();
    expect(screen.queryByText(/并指向本任务/)).toBeNull();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("does not claim the current Task when the durable answer names another Task", async () => {
    authStore.setToken("token");
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        jsonResponse(
          admissionOutcome({ taskId: "task-9", executionId: "execution-9" }),
        ),
      ),
    );
    const user = userEvent.setup();
    renderWithProviders(
      <OrganizeSubmissionVerification
        taskId="task-1"
        submissions={[submission()]}
      />,
    );

    await user.click(
      await screen.findByRole("button", { name: "核对提交结果" }),
    );

    expect(
      await screen.findByRole("heading", { name: "核对结果指向另一个任务" }),
    ).toBeVisible();
    expect(screen.getByText(/对应任务 task-9/)).toBeVisible();
    expect(screen.queryByText(/并指向本任务/)).toBeNull();
  });
});
