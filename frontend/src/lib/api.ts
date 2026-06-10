import posthog from "posthog-js";

export const API_BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

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
  is_verified: boolean;
  created_at: string | null;
  github?: GitHubConnection;
};

export type LoginResult = {
  access_token: string;
  token_type: string;
};

/**
 * Error thrown by the API client. `code` is the backend's machine-readable
 * detail string (e.g. LOGIN_BAD_CREDENTIALS) when available; `message` is a
 * human-friendly string suitable for display.
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
  LOGIN_BAD_CREDENTIALS: "Incorrect email or password.",
  LOGIN_USER_NOT_VERIFIED: "Please verify your email before signing in.",
  REGISTER_USER_ALREADY_EXISTS: "An account with this email already exists.",
  REGISTER_INVALID_PASSWORD: "Password does not meet the requirements.",
  REGISTRATION_DISABLED: "Sign up is not available right now.",
  TOO_MANY_REQUESTS: "Too many attempts. Please wait a moment and try again.",
  WAITLIST_EMAIL_ALREADY_EXISTS: "You're already on the waitlist.",
};

/**
 * fastapi-users returns errors as `{ detail: "CODE" }` or, for password
 * validation, `{ detail: { code, reason } }`. Normalize both shapes into a
 * stable code + friendly message.
 */
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
export async function authedGet<T>(path: string, token: string): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: apiHeaders({ Authorization: `Bearer ${token}` }),
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
  token: string,
  payload?: unknown,
): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    method,
    headers: apiHeaders({
      Authorization: `Bearer ${token}`,
      ...(payload !== undefined ? { "Content-Type": "application/json" } : {}),
    }),
    body: payload !== undefined ? JSON.stringify(payload) : undefined,
  });
  const body = await parseJson(response);
  if (!response.ok) throw extractError(response.status, body);
  return body as T;
}

export async function register(input: {
  email: string;
  password: string;
  name?: string;
}): Promise<AuthUser> {
  const response = await fetch(`${API_BASE}/api/v1/auth/register`, {
    method: "POST",
    headers: apiHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({
      email: input.email,
      password: input.password,
      name: input.name || null,
    }),
  });

  const body = await parseJson(response);
  if (!response.ok) throw extractError(response.status, body);
  return body as AuthUser;
}

export async function login(input: {
  email: string;
  password: string;
}): Promise<LoginResult> {
  // fastapi-users login uses the OAuth2 password flow: form-urlencoded body
  // with `username` (not `email`) and `password`.
  const form = new URLSearchParams();
  form.set("username", input.email);
  form.set("password", input.password);

  const response = await fetch(`${API_BASE}/api/v1/auth/login`, {
    method: "POST",
    headers: apiHeaders({
      "Content-Type": "application/x-www-form-urlencoded",
    }),
    body: form.toString(),
  });

  const body = await parseJson(response);
  if (!response.ok) throw extractError(response.status, body);
  return body as LoginResult;
}

export type WaitlistEntry = {
  id: string;
  email: string;
  created_at: string;
};

/** Public landing-page waitlist signup (no auth). */
export async function joinWaitlist(input: { email: string }): Promise<WaitlistEntry> {
  const response = await fetch(`${API_BASE}/api/v1/waitlist`, {
    method: "POST",
    headers: apiHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({ email: input.email }),
  });

  const body = await parseJson(response);
  if (!response.ok) throw extractError(response.status, body);
  return body as WaitlistEntry;
}

export async function getMe(token: string): Promise<AuthUser> {
  const response = await fetch(`${API_BASE}/api/v1/auth/me`, {
    headers: apiHeaders({ Authorization: `Bearer ${token}` }),
  });

  const body = await parseJson(response);
  if (!response.ok) throw extractError(response.status, body);
  return body as AuthUser;
}

/**
 * Fetch the GitHub authorization URL for linking the signed-in user's account.
 * The caller redirects the browser to this URL; GitHub returns to the backend
 * callback, which bounces back to `/profile?github=connected`.
 */
export async function getGithubLinkUrl(token: string): Promise<string> {
  const { authorization_url } = await authedGet<{ authorization_url: string }>(
    "/api/v1/auth/github/link/authorize",
    token,
  );
  return authorization_url;
}

/**
 * Fetch the GitHub authorization URL to sign in / sign up with GitHub. No auth
 * required. The backend callback mints a session JWT and redirects to
 * `/auth/github/callback#access_token=...`, which the SPA consumes.
 */
export async function getGithubLoginUrl(): Promise<string> {
  const response = await fetch(`${API_BASE}/api/v1/auth/github/login/authorize`, {
    headers: apiHeaders(),
  });
  const body = await parseJson(response);
  if (!response.ok) throw extractError(response.status, body);
  return (body as { authorization_url: string }).authorization_url;
}

/**
 * Public GitHub App install URL for onboarding. Installing the app is all an
 * org needs — the backend auto-provisions the workspace and imports members.
 */
export async function getGithubAppInstallUrl(token: string): Promise<string> {
  const { install_url } = await authedGet<{ install_url: string }>(
    "/api/v1/connections/github/app",
    token,
  );
  return install_url;
}

export type InstallationSyncResult = {
  created: number;
  updated: number;
  revoked: number;
};

/** Ask the backend to reconcile connections with GitHub installations now. */
export async function syncGithubInstallations(
  token: string,
): Promise<InstallationSyncResult> {
  const response = await fetch(`${API_BASE}/api/v1/connections/github/sync`, {
    method: "POST",
    headers: apiHeaders({ Authorization: `Bearer ${token}` }),
  });
  const body = await parseJson(response);
  if (!response.ok) throw extractError(response.status, body);
  return body as InstallationSyncResult;
}
