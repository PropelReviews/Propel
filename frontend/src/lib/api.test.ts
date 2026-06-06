import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, getMe, login, register } from "./api";

type FetchInit = {
  method?: string;
  headers: Record<string, string>;
  body: string;
};

function mockFetch(response: { ok: boolean; status: number; body: unknown }) {
  const fetchMock = vi.fn(async (_url: string, _init: FetchInit) => ({
    ok: response.ok,
    status: response.status,
    text: async () => (response.body === null ? "" : JSON.stringify(response.body)),
  }));
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function lastFetchInit(
  fetchMock: ReturnType<typeof vi.fn>,
): FetchInit {
  const init = fetchMock.mock.calls[fetchMock.mock.calls.length - 1]?.[1];
  expect(init).toBeDefined();
  return init as FetchInit;
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("register", () => {
  it("POSTs JSON to /api/v1/auth/register", async () => {
    const fetchMock = mockFetch({
      ok: true,
      status: 201,
      body: { id: "1", email: "a@b.com", name: null },
    });

    await register({ email: "a@b.com", password: "supersecret", name: "Ada" });

    const [url] = fetchMock.mock.calls[0]!;
    const init = lastFetchInit(fetchMock);
    expect(url).toContain("/api/v1/auth/register");
    expect(init.method).toBe("POST");
    expect(init.headers["Content-Type"]).toBe("application/json");
    expect(JSON.parse(init.body)).toEqual({
      email: "a@b.com",
      password: "supersecret",
      name: "Ada",
    });
  });

  it("maps REGISTER_USER_ALREADY_EXISTS to a friendly message", async () => {
    mockFetch({
      ok: false,
      status: 400,
      body: { detail: "REGISTER_USER_ALREADY_EXISTS" },
    });

    await expect(
      register({ email: "a@b.com", password: "supersecret" }),
    ).rejects.toMatchObject({
      code: "REGISTER_USER_ALREADY_EXISTS",
      message: "An account with this email already exists.",
    });
  });
});

describe("login", () => {
  it("POSTs form-urlencoded with username (not email)", async () => {
    const fetchMock = mockFetch({
      ok: true,
      status: 200,
      body: { access_token: "tok", token_type: "bearer" },
    });

    const result = await login({ email: "a@b.com", password: "pw" });

    const [url] = fetchMock.mock.calls[0]!;
    const init = lastFetchInit(fetchMock);
    expect(url).toContain("/api/v1/auth/login");
    expect(init.headers["Content-Type"]).toBe("application/x-www-form-urlencoded");
    const params = new URLSearchParams(init.body);
    expect(params.get("username")).toBe("a@b.com");
    expect(params.get("password")).toBe("pw");
    expect(result.access_token).toBe("tok");
  });

  it("maps LOGIN_BAD_CREDENTIALS to a friendly message", async () => {
    mockFetch({
      ok: false,
      status: 400,
      body: { detail: "LOGIN_BAD_CREDENTIALS" },
    });

    await expect(login({ email: "a@b.com", password: "x" })).rejects.toMatchObject({
      code: "LOGIN_BAD_CREDENTIALS",
      message: "Incorrect email or password.",
    });
  });
});

describe("getMe", () => {
  it("sends the bearer token and throws ApiError on 401", async () => {
    const fetchMock = mockFetch({ ok: false, status: 401, body: null });

    const error = await getMe("tok").catch((e) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).status).toBe(401);

    const init = lastFetchInit(fetchMock);
    expect(init.headers.Authorization).toBe("Bearer tok");
  });
});
