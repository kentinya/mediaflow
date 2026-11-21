/**
 * Browser account/session contract.
 *
 * The server owns the HttpOnly session cookie; JavaScript never receives,
 * stores or sends the session secret.  Each request only carries the cookie
 * already held by the browser, and every failure is normalized to a bounded,
 * secret-free code and operator next action.
 */

export interface AuthAccount {
  readonly principalId: string;
  readonly accountId: string;
  readonly username: string;
  readonly roles: readonly string[];
  readonly permissions: readonly string[];
}

export interface AuthStatus {
  readonly authenticated: boolean;
  readonly firstAdministratorRequired: boolean;
  readonly configurationRequired: boolean;
  readonly account: AuthAccount | null;
  readonly expiresAt: string | null;
  readonly absoluteExpiresAt: string | null;
}

export interface AuthErrorDetails {
  readonly durableState?: string;
  readonly retrySafe?: boolean;
  readonly nextAction?: string;
  readonly field?: string;
}

export class AuthApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: AuthErrorDetails;

  constructor(
    status: number,
    code: string,
    message: string,
    details: AuthErrorDetails,
  ) {
    super(message);
    this.name = "AuthApiError";
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

interface ErrorEnvelope {
  readonly error?: {
    readonly code?: unknown;
    readonly message?: unknown;
    readonly details?: AuthErrorDetails;
  };
}

async function readError(response: Response): Promise<AuthApiError> {
  let envelope: ErrorEnvelope = {};
  try {
    envelope = (await response.json()) as ErrorEnvelope;
  } catch {
    // A non-JSON failure is still bounded by its HTTP status.
  }
  const error = envelope.error;
  const code =
    typeof error?.code === "string" && error.code.length > 0
      ? error.code
      : "request_failed";
  const message =
    typeof error?.message === "string" && error.message.length > 0
      ? error.message
      : "The request could not be completed.";
  return new AuthApiError(response.status, code, message, error?.details ?? {});
}

async function request<T>(
  path: string,
  init: RequestInit,
  fetchImpl: typeof fetch,
): Promise<T> {
  let response: Response;
  try {
    response = await fetchImpl(path, {
      ...init,
      credentials: "same-origin",
      headers: {
        Accept: "application/json",
        ...(init.body === undefined
          ? {}
          : { "Content-Type": "application/json" }),
        ...init.headers,
      },
    });
  } catch {
    throw new AuthApiError(
      503,
      "service_unavailable",
      "MediaFlow could not be reached. Check that the service is running, then retry.",
      {
        durableState: "no account or session changed",
        retrySafe: true,
        nextAction: "check the service and retry the same form",
      },
    );
  }
  if (!response.ok) {
    throw await readError(response);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  try {
    return (await response.json()) as T;
  } catch {
    throw new AuthApiError(
      502,
      "malformed_response",
      "MediaFlow returned an unreadable response.",
      {
        durableState: "the outcome of the request is unknown",
        retrySafe: false,
        nextAction: "reload the page and check the current sign-in state",
      },
    );
  }
}

export function fetchAuthStatus(
  fetchImpl: typeof fetch = fetch,
): Promise<AuthStatus> {
  return request<AuthStatus>("/api/auth/status", { method: "GET" }, fetchImpl);
}

export function loginAccount(
  input: {
    readonly username: string;
    readonly password: string;
    readonly remember: boolean;
  },
  fetchImpl: typeof fetch = fetch,
): Promise<{ readonly account: AuthAccount }> {
  return request(
    "/api/auth/login",
    { method: "POST", body: JSON.stringify(input) },
    fetchImpl,
  );
}

export function bootstrapFirstAdministrator(
  input: {
    readonly code: string;
    readonly username: string;
    readonly password: string;
    readonly remember: boolean;
  },
  fetchImpl: typeof fetch = fetch,
): Promise<{ readonly account: AuthAccount }> {
  return request(
    "/api/auth/bootstrap",
    { method: "POST", body: JSON.stringify(input) },
    fetchImpl,
  );
}

export function resetPassword(
  input: { readonly code: string; readonly newPassword: string },
  fetchImpl: typeof fetch = fetch,
): Promise<{ readonly account: AuthAccount; readonly signedOut: true }> {
  return request(
    "/api/auth/reset",
    { method: "POST", body: JSON.stringify(input) },
    fetchImpl,
  );
}

export function logoutAccount(
  fetchImpl: typeof fetch = fetch,
): Promise<{ readonly signedOut: true }> {
  return request(
    "/api/auth/logout",
    { method: "POST", body: JSON.stringify({}) },
    fetchImpl,
  );
}

export function changePassword(
  input: {
    readonly currentPassword: string;
    readonly newPassword: string;
  },
  fetchImpl: typeof fetch = fetch,
): Promise<{ readonly passwordChanged: true; readonly signedOut: true }> {
  return request(
    "/api/auth/password",
    { method: "POST", body: JSON.stringify(input) },
    fetchImpl,
  );
}
