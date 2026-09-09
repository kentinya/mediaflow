import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient } from "@tanstack/react-query";
import { authStore } from "../api/auth-store";
import { ApiReadError, DashboardApiError } from "../api/api-errors";
import { renderWithProviders } from "../../../tests/utils";
import {
  AuthorizedReadBoundary,
  type AuthorizedReadQuery,
} from "./AuthorizedReadBoundary";

const TOKEN = "read-boundary-token";

function makeQuery<T>(fields: {
  readonly data?: T;
  readonly isPending?: boolean;
  readonly isError?: boolean;
  readonly error?: unknown;
  readonly isFetching?: boolean;
  readonly refetch?: () => Promise<unknown>;
}): AuthorizedReadQuery<T> {
  return {
    data: fields.data,
    isPending: fields.isPending ?? false,
    isError: fields.isError ?? false,
    error: fields.error,
    isFetching: fields.isFetching ?? false,
    refetch: fields.refetch ?? (async () => undefined),
  };
}

afterEach(() => {
  cleanup();
  authStore.clearToken();
  authStore.clearIntendedPath();
  vi.unstubAllGlobals();
});

describe("AuthorizedReadBoundary", () => {
  it("renders the shared not-connected state and never mounts feature content", async () => {
    const renderContent = vi.fn(() => <p>feature content</p>);
    renderWithProviders(
      <AuthorizedReadBoundary query={makeQuery({})}>
        {renderContent}
      </AuthorizedReadBoundary>,
    );
    expect(
      await screen.findByRole("heading", { name: "Not connected" }),
    ).toBeVisible();
    expect(
      screen.getByRole("link", { name: "Go to the V2 entry" }),
    ).toBeVisible();
    expect(renderContent).not.toHaveBeenCalled();
  });

  it("clears the rejected authority and authenticated cache on 401 without replay", async () => {
    const refetch = vi.fn(async () => undefined);
    const renderContent = vi.fn(() => <p>feature content</p>);
    const queryClient = new QueryClient();
    queryClient.setQueryData(["feature", "read"], { cached: true });
    authStore.setToken(TOKEN);

    const { queryClient: renderedClient } = renderWithProviders(
      <AuthorizedReadBoundary
        query={makeQuery({
          isError: true,
          error: new DashboardApiError("unauthorized"),
          refetch,
        })}
      >
        {renderContent}
      </AuthorizedReadBoundary>,
      queryClient,
    );

    expect(
      await screen.findByRole("heading", { name: "Not authorized" }),
    ).toBeVisible();
    expect(authStore.getToken()).toBeNull();
    expect(authStore.isRejected()).toBe(true);
    // The authenticated cache was cleared, not left behind.
    expect(renderedClient.getQueryData(["feature", "read"])).toBeUndefined();
    // No automatic replay of the rejected request and no feature content.
    expect(refetch).not.toHaveBeenCalled();
    expect(renderContent).not.toHaveBeenCalled();
  });

  it("keeps the authenticated principal and renders a distinct state on 403", async () => {
    const renderContent = vi.fn(() => <p>feature content</p>);
    authStore.setToken(TOKEN);
    renderWithProviders(
      <AuthorizedReadBoundary
        query={makeQuery({
          isError: true,
          error: new DashboardApiError("forbidden"),
        })}
      >
        {renderContent}
      </AuthorizedReadBoundary>,
    );
    expect(
      await screen.findByRole("heading", { name: "Forbidden" }),
    ).toBeVisible();
    expect(
      screen.getByText(/does not have permission to view this area/),
    ).toBeVisible();
    expect(
      screen.queryByRole("heading", { name: "Not authorized" }),
    ).toBeNull();
    // A 403 is a permission failure: the principal stays authenticated.
    expect(authStore.getToken()).toBe(TOKEN);
    expect(authStore.isRejected()).toBe(false);
    expect(renderContent).not.toHaveBeenCalled();
  });

  it("offers an explicit bounded retry for unavailable reads", async () => {
    const refetch = vi.fn(async () => undefined);
    const user = userEvent.setup();
    authStore.setToken(TOKEN);
    renderWithProviders(
      <AuthorizedReadBoundary
        query={makeQuery({
          isError: true,
          error: new DashboardApiError("unavailable"),
          refetch,
        })}
        unavailableTitle="Feature unavailable"
      >
        {() => <p>feature content</p>}
      </AuthorizedReadBoundary>,
    );
    expect(
      await screen.findByRole("heading", { name: "Feature unavailable" }),
    ).toBeVisible();
    expect(screen.getByText(/currently unavailable/)).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Refresh" }));
    expect(refetch).toHaveBeenCalledTimes(1);
  });

  it("hands ready data and a bounded refresh to feature content", async () => {
    const refetch = vi.fn(async () => undefined);
    const user = userEvent.setup();
    authStore.setToken(TOKEN);
    renderWithProviders(
      <AuthorizedReadBoundary
        query={makeQuery<{ count: number }>({
          data: { count: 3 },
          refetch,
        })}
      >
        {({ data, refresh }) => (
          <div>
            <p>feature count {data?.count}</p>
            <button type="button" onClick={refresh}>
              Refresh data
            </button>
          </div>
        )}
      </AuthorizedReadBoundary>,
    );
    expect(await screen.findByText("feature count 3")).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Refresh data" }));
    expect(refetch).toHaveBeenCalledTimes(1);
  });
  it("applies the same 401-clearing lifecycle to a non-Dashboard read error", async () => {
    // A later product feature that throws the plain feature-neutral ApiReadError
    // (not DashboardApiError) must inherit the shared authority/cache transition.
    const refetch = vi.fn(async () => undefined);
    const queryClient = new QueryClient();
    queryClient.setQueryData(["feature", "read"], { cached: true });
    authStore.setToken(TOKEN);

    const { queryClient: renderedClient } = renderWithProviders(
      <AuthorizedReadBoundary
        query={makeQuery({
          isError: true,
          error: new ApiReadError("unauthorized"),
          refetch,
        })}
      >
        {() => <p>feature content</p>}
      </AuthorizedReadBoundary>,
      queryClient,
    );

    expect(
      await screen.findByRole("heading", { name: "Not authorized" }),
    ).toBeVisible();
    expect(authStore.getToken()).toBeNull();
    expect(authStore.isRejected()).toBe(true);
    expect(renderedClient.getQueryData(["feature", "read"])).toBeUndefined();
    expect(refetch).not.toHaveBeenCalled();
  });

  it("retains a still-authenticated principal on a non-Dashboard 403", async () => {
    const queryClient = new QueryClient();
    authStore.setToken(TOKEN);
    renderWithProviders(
      <AuthorizedReadBoundary
        query={makeQuery({
          isError: true,
          error: new ApiReadError("forbidden"),
        })}
      >
        {() => <p>feature content</p>}
      </AuthorizedReadBoundary>,
      queryClient,
    );
    expect(
      await screen.findByRole("heading", { name: "Forbidden" }),
    ).toBeVisible();
    expect(
      screen.queryByRole("heading", { name: "Not authorized" }),
    ).toBeNull();
    expect(authStore.getToken()).toBe(TOKEN);
    expect(authStore.isRejected()).toBe(false);
  });

  it("offers a bounded retry for a non-Dashboard unavailable read", async () => {
    const refetch = vi.fn(async () => undefined);
    const user = userEvent.setup();
    authStore.setToken(TOKEN);
    renderWithProviders(
      <AuthorizedReadBoundary
        query={makeQuery({
          isError: true,
          error: new ApiReadError("unavailable"),
          refetch,
        })}
      >
        {() => <p>feature content</p>}
      </AuthorizedReadBoundary>,
    );
    expect(
      await screen.findByRole("heading", { name: "Service unavailable" }),
    ).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Refresh" }));
    expect(refetch).toHaveBeenCalledTimes(1);
  });
});
