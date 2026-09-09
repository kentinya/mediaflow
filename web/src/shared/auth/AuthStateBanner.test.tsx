import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { authStore } from "../api/auth-store";
import { renderWithProviders } from "../../../tests/utils";
import { AuthStateBanner, UnavailableBanner } from "./AuthStateBanner";

const TOKEN = "auth-banner-token";

afterEach(() => {
  cleanup();
  authStore.clearToken();
});

describe("AuthStateBanner", () => {
  it("renders the not-connected state with the V2 entry link", async () => {
    renderWithProviders(
      <AuthStateBanner
        variant="not-connected"
        title="Not connected"
        message="Enter an API principal token to view this area."
      />,
    );
    expect(
      await screen.findByRole("heading", { name: "Not connected" }),
    ).toBeVisible();
    expect(
      screen.getByRole("link", { name: "Go to the V2 entry" }),
    ).toBeVisible();
  });

  it("renders the unauthorized state with bounded recovery on 401", async () => {
    renderWithProviders(
      <AuthStateBanner
        variant="unauthorized"
        title="Not authorized"
        message="The API token was rejected. Enter a valid API principal token to continue."
      />,
    );
    expect(
      await screen.findByRole("heading", { name: "Not authorized" }),
    ).toBeVisible();
    expect(
      screen.getByRole("link", { name: "Enter an API principal token" }),
    ).toBeVisible();
  });

  it("renders the forbidden state with bounded recovery on 403", async () => {
    authStore.setToken(TOKEN);
    renderWithProviders(
      <AuthStateBanner
        variant="forbidden"
        title="Forbidden"
        message="The connected API principal does not have permission to view this area."
      />,
    );
    expect(
      await screen.findByRole("heading", { name: "Forbidden" }),
    ).toBeVisible();
    expect(
      screen.getByText(/does not have permission to view this area/),
    ).toBeVisible();
    expect(
      screen.getByRole("link", {
        name: "Connect a principal with read permission",
      }),
    ).toBeVisible();
    // The active principal is never rendered by the banner.
    expect(screen.queryByText(TOKEN)).toBeNull();
  });
});

describe("UnavailableBanner", () => {
  it("renders the unavailable state with an explicit refresh action", async () => {
    const onRetry = vi.fn();
    renderWithProviders(
      <UnavailableBanner onRetry={onRetry} retrying={false} />,
    );
    expect(
      await screen.findByRole("heading", { name: "Service unavailable" }),
    ).toBeVisible();
    expect(
      screen.getByText(/requested data could not be loaded right now/),
    ).toBeVisible();
    expect(screen.getByRole("button", { name: "Refresh" })).toBeVisible();
  });

  it("triggers only the bounded refresh when the operator retries", async () => {
    const onRetry = vi.fn();
    const user = userEvent.setup();
    renderWithProviders(
      <UnavailableBanner onRetry={onRetry} retrying={false} />,
    );
    await user.click(await screen.findByRole("button", { name: "Refresh" }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it("accepts context-specific title and description", async () => {
    const onRetry = vi.fn();
    renderWithProviders(
      <UnavailableBanner
        onRetry={onRetry}
        retrying={false}
        title="Dashboard unavailable"
        description="The MediaFlow API is currently unavailable. Check that the application is running, then refresh."
      />,
    );
    expect(
      await screen.findByRole("heading", { name: "Dashboard unavailable" }),
    ).toBeVisible();
    expect(screen.getByText(/currently unavailable/)).toBeVisible();
    expect(screen.getByRole("button", { name: "Refresh" })).toBeVisible();
  });
});
