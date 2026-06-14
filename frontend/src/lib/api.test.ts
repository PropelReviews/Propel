import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, getMe, joinWaitlist } from "./api";

describe("api client", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("joinWaitlist posts JSON and returns the entry", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 201,
      text: async () =>
        JSON.stringify({
          id: "w1",
          email: "a@b.com",
          created_at: "2026-01-01T00:00:00Z",
        }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await joinWaitlist({ email: "a@b.com" });
    expect(result.email).toBe("a@b.com");
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/api/v1/waitlist"),
      expect.objectContaining({ method: "POST", credentials: "include" }),
    );
  });

  it("getMe uses session cookies and throws ApiError on 401", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 401,
      text: async () => JSON.stringify({ detail: "Not authenticated" }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const error = await getMe().catch((e) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).status).toBe(401);
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/api/v1/auth/me"),
      expect.objectContaining({ credentials: "include" }),
    );
  });
});
