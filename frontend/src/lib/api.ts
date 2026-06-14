import posthog from "posthog-js";

export const API_BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

const fetchCredentials: RequestCredentials = "include";

/** Headers that link backend OTLP logs to PostHog person + session replay. */
function posthogLogHeaders(): Record<string, string> {
  if (!posthog.__loaded) return {};
  const headers: Record<string, string> = {};
  const distinctId = posthog.get_distinct_id();
  const sessionId = posthog.get_session_id();
  if (distinctId) headers["X-PostHog-Distinct-Id"] = distinctId;
  if (sessionId) headers["X-PostHog-Session-Id"] = sessionId;
  return headers;
}

function apiHeaders(extra: Record<string, string> = {}): Record<string, string> {
  return { ...posthogLogHeaders(), ...extra };
}

export type GitHubConnection = {
  connected: boolean;
  account_id: string | null;
  account_email: string | null;
  login: string | null;
};

export type AuthUser = {
  id: string;
  email: string;
  name: string | null;
  is_active: boolean;
  email_verified: boolean;
  created_at: string | null;
  github?: GitHubConnection;
};

/**
 * Error thrown by the API client. `code` is the backend's machine-readable
 * detail string when available; `message` is a human-friendly string.
 */
export class ApiError extends Error {
  code: string | null;
  status: number;

  constructor(message: string, status: number, code: string | null = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

const FRIENDLY_MESSAGES: Record<string, string> = {
  OIDC_NOT_CONFIGURED: "Sign-in is not configured yet.",
  TOO_MANY_REQUESTS: "Too many attempts. Please wait a moment and try again.",
  WAITLIST_EMAIL_ALREADY_EXISTS: "You're already on the waitlist.",
};

function extractError(status: number, body: unknown): ApiError {
  let code: string | null = null;
  let reason: string | null = null;

  if (body && typeof body === "object" && "detail" in body) {
    const detail = (body as { detail: unknown }).detail;
    if (typeof detail === "string") {
      code = detail;
    } else if (detail && typeof detail === "object") {
      const d = detail as { code?: unknown; reason?: unknown };
      if (typeof d.code === "string") code = d.code;
      if (typeof d.reason === "string") reason = d.reason;
    }
  }

  const message =
    (code && FRIENDLY_MESSAGES[code]) ??
    reason ??
    "Something went wrong. Please try again.";

  return new ApiError(message, status, code);
}

async function parseJson(response: Response): Promise<unknown> {
  const text = await response.text();
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}

/** Authenticated GET that returns parsed JSON or throws `ApiError`. */
export async function authedGet<T>(path: string, _token?: string): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    credentials: fetchCredentials,
    headers: apiHeaders(),
  });
  const body = await parseJson(response);
  if (!response.ok) throw extractError(response.status, body);
  return body as T;
}

/**
 * Authenticated request with a JSON body (POST/PATCH/PUT/DELETE). Returns
 * parsed JSON (null for 204) or throws `ApiError`.
 */
export async function authedRequest<T>(
  method: "POST" | "PATCH" | "PUT" | "DELETE",
  path: string,
  _token?: string,
  payload?: unknown,
): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    method,
    credentials: fetchCredentials,
    headers: apiHeaders({
      ...(payload !== undefined ? { "Content-Type": "application/json" } : {}),
    }),
    body: payload !== undefined ? JSON.stringify(payload) : undefined,
  });
  const body = await parseJson(response);
  if (!response.ok) throw extractError(response.status, body);
  return body as T;
}

/** Redirect the browser to Zitadel hosted login (Auth Code + PKCE via BFF). */
export function redirectToLogin(): void {
  window.location.href = `${API_BASE}/api/v1/auth/login`;
}

/** Redirect through the BFF logout endpoint (clears session + Zitadel). */
export function redirectToLogout(): void {
  window.location.href = `${API_BASE}/api/v1/auth/logout`;
}

export async function joinWaitlist(input: { email: string }): Promise<{
  id: string;
  email: string;
  created_at: string;
}> {
  const response = await fetch(`${API_BASE}/api/v1/waitlist`, {
    method: "POST",
    headers: apiHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({ email: input.email }),
  });

  const body = await parseJson(response);
  if (!response.ok) throw extractError(response.status, body);
  return body as { id: string; email: string; created_at: string };
}

export async function getMe(): Promise<AuthUser> {
  const response = await fetch(`${API_BASE}/api/v1/auth/me`, {
    credentials: fetchCredentials,
    headers: apiHeaders(),
  });

  const body = await parseJson(response);
  if (!response.ok) throw extractError(response.status, body);
  return body as AuthUser;
}

export async function getGithubLinkUrl(): Promise<string> {
  const { authorization_url } = await authedGet<{ authorization_url: string }>(
    "/api/v1/auth/github/link/authorize",
  );
  return authorization_url;
}

export async function getGithubAppInstallUrl(): Promise<string> {
  const { install_url } = await authedGet<{ install_url: string }>(
    "/api/v1/connections/github/app",
  );
  return install_url;
}

export type LinearConnection = {
  connected: boolean;
  workspace_name: string | null;
};

export async function getLinearConnection(tenantId: string): Promise<LinearConnection> {
  return authedGet<LinearConnection>(`/api/v1/tenants/${tenantId}/connections/linear`);
}

export async function getLinearAuthorizeUrl(tenantId: string): Promise<string> {
  const { authorization_url } = await authedGet<{ authorization_url: string }>(
    `/api/v1/tenants/${tenantId}/connections/linear/authorize`,
  );
  return authorization_url;
}

export type InstallationSyncResult = {
  created: number;
  updated: number;
  revoked: number;
};

export async function syncGithubInstallations(): Promise<InstallationSyncResult> {
  const response = await fetch(`${API_BASE}/api/v1/connections/github/sync`, {
    method: "POST",
    credentials: fetchCredentials,
    headers: apiHeaders(),
  });
  const body = await parseJson(response);
  if (!response.ok) throw extractError(response.status, body);
  return body as InstallationSyncResult;
}
