import { describe, expect, it, vi } from "vitest";
import {
  AuthApiError,
  AuthUnknownOutcomeError,
  changePassword,
  fetchAuthStatus,
  loginAccount,
} from "./auth-api";

const LOGIN = {
  username: "admin",
  password: "correct-horse",
  remember: false,
};

function jsonResponse(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("auth API outcome classification", () => {
  it("reports a transport abort on a submitted form as unknown", async () => {
    const fetchMock = vi.fn(async () => {
      throw new Error("connection reset");
    });
    await expect(loginAccount(LOGIN, fetchMock)).rejects.toBeInstanceOf(
      AuthUnknownOutcomeError,
    );
    const error = await loginAccount(LOGIN, fetchMock).catch(
      (failure: unknown) => failure,
    );
    expect(error).toBeInstanceOf(AuthApiError);
    expect((error as AuthApiError).code).toBe("unknown_outcome");
    expect((error as AuthApiError).details.retrySafe).toBe(false);
    expect((error as AuthApiError).message).not.toContain(
      "could not be reached",
    );
  });

  it("treats an unstructured proxy timeout after submission as unknown", async () => {
    const fetchMock = vi.fn(
      async () =>
        new Response("<html>Gateway Timeout</html>", {
          status: 504,
          headers: { "Content-Type": "text/html" },
        }),
    );
    await expect(
      changePassword({ currentPassword: "old", newPassword: "new" }, fetchMock),
    ).rejects.toBeInstanceOf(AuthUnknownOutcomeError);
  });

  it("keeps an explicit rejection as the server's bounded error", async () => {
    const fetchMock = vi.fn(async () =>
      jsonResponse(
        {
          error: {
            code: "invalid_credentials",
            message: "The login name or password is incorrect.",
            details: {
              durableState: "no session was created",
              retrySafe: true,
              nextAction: "correct the account or password and try again",
            },
          },
        },
        401,
      ),
    );
    const error = await loginAccount(LOGIN, fetchMock).catch(
      (failure: unknown) => failure,
    );
    expect(error).toBeInstanceOf(AuthApiError);
    expect(error).not.toBeInstanceOf(AuthUnknownOutcomeError);
    expect((error as AuthApiError).code).toBe("invalid_credentials");
    expect((error as AuthApiError).details.retrySafe).toBe(true);
  });

  it("treats an unreadable success body after submission as unknown", async () => {
    const fetchMock = vi.fn(
      async () =>
        new Response("not-json", {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
    );
    await expect(
      changePassword({ currentPassword: "old", newPassword: "new" }, fetchMock),
    ).rejects.toBeInstanceOf(AuthUnknownOutcomeError);
  });

  it("keeps a failed status read a bounded availability failure", async () => {
    const fetchMock = vi.fn(async () => {
      throw new Error("connection reset");
    });
    const error = await fetchAuthStatus(fetchMock).catch(
      (failure: unknown) => failure,
    );
    expect(error).toBeInstanceOf(AuthApiError);
    expect(error).not.toBeInstanceOf(AuthUnknownOutcomeError);
    expect((error as AuthApiError).status).toBe(503);
    expect((error as AuthApiError).code).toBe("service_unavailable");
  });
});
