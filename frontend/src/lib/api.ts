const API_BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export type AuthUser = {
  id: string;
  email: string;
  name: string | null;
  is_active: boolean;
  is_verified: boolean;
  created_at: string | null;
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

export async function register(input: {
  email: string;
  password: string;
  name?: string;
}): Promise<AuthUser> {
  const response = await fetch(`${API_BASE}/api/v1/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
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
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: form.toString(),
  });

  const body = await parseJson(response);
  if (!response.ok) throw extractError(response.status, body);
  return body as LoginResult;
}

export async function getMe(token: string): Promise<AuthUser> {
  const response = await fetch(`${API_BASE}/api/v1/auth/me`, {
    headers: { Authorization: `Bearer ${token}` },
  });

  const body = await parseJson(response);
  if (!response.ok) throw extractError(response.status, body);
  return body as AuthUser;
}
