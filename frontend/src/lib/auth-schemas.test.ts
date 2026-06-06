import { describe, expect, it } from "vitest";

import { signInSchema, signUpSchema } from "./auth-schemas";

describe("signInSchema", () => {
  it("accepts a valid email and non-empty password", () => {
    expect(signInSchema.safeParse({ email: "a@b.com", password: "x" }).success).toBe(
      true,
    );
  });

  it("rejects an invalid email", () => {
    expect(
      signInSchema.safeParse({ email: "nope", password: "x" }).success,
    ).toBe(false);
  });

  it("rejects an empty password", () => {
    expect(
      signInSchema.safeParse({ email: "a@b.com", password: "" }).success,
    ).toBe(false);
  });
});

describe("signUpSchema", () => {
  it("accepts a valid signup with optional name omitted", () => {
    expect(
      signUpSchema.safeParse({ email: "a@b.com", password: "supersecret" }).success,
    ).toBe(true);
  });

  it("rejects a password shorter than 8 characters", () => {
    expect(
      signUpSchema.safeParse({ email: "a@b.com", password: "short" }).success,
    ).toBe(false);
  });
});
