import { afterEach, expect, it, vi } from "vitest";
import { cleanup, screen } from "@testing-library/react";
import { renderWithProviders } from "../../../tests/utils";
import { authStore } from "../../shared/api/auth-store";
import { ResidentServiceStatus } from "./ResidentServiceStatus";

afterEach(() => {
  cleanup();
  authStore.clearToken();
  vi.unstubAllGlobals();
});

it.each([
  "unconfigured",
  "configuration_unavailable",
  "database_unavailable",
  "schema_unsupported",
  "secret_unavailable",
])(
  "renders backend %s separately from infrastructure health without raw details",
  async (reason) => {
    authStore.setToken("fake-resident-status-token");
    const fetcher = vi.fn(
      async () =>
        new Response(
          JSON.stringify({
            infrastructure: {
              services: Object.fromEntries(
                ["api", "worker", "scheduler", "notification-worker"].map(
                  (service) => [
                    service,
                    {
                      ready: true,
                      condition: "ready",
                      waiting: true,
                      waitingReason: reason,
                      waitingDetail: "unsafe-canary",
                    },
                  ],
                ),
              ),
            },
          }),
        ),
    );
    vi.stubGlobal("fetch", fetcher);
    renderWithProviders(<ResidentServiceStatus />);
    expect(await screen.findByText("notification-worker")).toBeVisible();
    expect(screen.getByRole("link", { name: "前往系统设置" })).toBeVisible();
    expect(screen.queryByText(/unsafe-canary/)).not.toBeInTheDocument();
    expect(fetcher).toHaveBeenCalledWith(
      "/api/v1/management/readiness",
      expect.any(Object),
    );
  },
);

it("keeps database read failures visible and offers refresh", async () => {
  authStore.setToken("fake-resident-status-token");
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => new Response("{}", { status: 503 })),
  );
  renderWithProviders(<ResidentServiceStatus />);
  expect(await screen.findByText("服务状态暂不可用")).toBeVisible();
});
