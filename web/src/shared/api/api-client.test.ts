import { afterEach, describe, expect, it, vi } from "vitest";
import { dashboardUrl, fetchDashboard } from "./api-client";
import { DashboardApiError } from "./api-errors";
import { dashboardModel, dashboardPayload } from "../../../tests/fixtures";

const TOKEN = "memory-only-token-value";

function jsonResponse(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function stubFetch(
  implementation: () => Promise<Response>,
): ReturnType<typeof vi.fn> {
  const fetchMock = vi.fn(implementation);
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("fetchDashboard", () => {
  it("sends one bounded GET with the Bearer token from memory", async () => {
    const fetchMock = stubFetch(async () => jsonResponse(dashboardPayload));
    const model = await fetchDashboard(TOKEN);
    expect(model).toEqual(dashboardModel);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [input, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(input).toBe(dashboardUrl());
    expect(input).toBe("/api/v1/dashboard?recentLimit=10");
    expect(init.method).toBe("GET");
    const headers = init.headers as Record<string, string>;
    expect(headers.Authorization).toBe(`Bearer ${TOKEN}`);
    expect(headers.Accept).toBe("application/json");
  });

  it("omits the Authorization header when not connected", async () => {
    const fetchMock = stubFetch(async () => jsonResponse(dashboardPayload));
    await fetchDashboard(null);
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(init.headers as Record<string, string>).toEqual({
      Accept: "application/json",
    });
  });

  it.each([
    [401, "unauthorized"],
    [403, "forbidden"],
    [500, "unavailable"],
    [503, "unavailable"],
    [400, "rejected"],
    [404, "rejected"],
  ] as const)("maps HTTP %i to the %s category", async (status, category) => {
    stubFetch(async () =>
      jsonResponse({ error: { code: "x", message: "y" } }, status),
    );
    await expect(fetchDashboard(TOKEN)).rejects.toMatchObject({
      name: "DashboardApiError",
      category,
    });
  });

  it("maps transport failure to the unavailable category", async () => {
    stubFetch(async () => {
      throw new TypeError("network down");
    });
    await expect(fetchDashboard(TOKEN)).rejects.toMatchObject({
      category: "unavailable",
    });
  });

  it("maps non-JSON success responses to the malformed category", async () => {
    stubFetch(
      async () => new Response("<html>not json</html>", { status: 200 }),
    );
    await expect(fetchDashboard(TOKEN)).rejects.toMatchObject({
      category: "malformed",
    });
  });

  it("maps shape violations to the malformed category", async () => {
    stubFetch(async () => jsonResponse({ hello: "world" }));
    await expect(fetchDashboard(TOKEN)).rejects.toMatchObject({
      category: "malformed",
    });
  });

  it("keeps every error message bounded and free of token material", async () => {
    const cases: Array<() => Promise<unknown>> = [
      () => {
        stubFetch(async () => jsonResponse({}, 401));
        return fetchDashboard(TOKEN);
      },
      () => {
        stubFetch(async () => jsonResponse({}, 403));
        return fetchDashboard(TOKEN);
      },
      () => {
        stubFetch(async () => {
          throw new TypeError("network down");
        });
        return fetchDashboard(TOKEN);
      },
      () => {
        stubFetch(async () => new Response("not json", { status: 200 }));
        return fetchDashboard(TOKEN);
      },
    ];
    for (const run of cases) {
      const error = await run().catch((caught: unknown) => caught);
      expect(error).toBeInstanceOf(DashboardApiError);
      expect((error as Error).message).not.toContain(TOKEN);
      expect((error as Error).message.length).toBeLessThan(200);
    }
  });
});
