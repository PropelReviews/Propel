import { afterEach, describe, expect, it, vi } from "vitest";

import { renderInDom, waitFor, type RenderResult } from "@/test/render-browser";

import { WaitlistForm } from "./waitlist-form";

const CONFIRMATION = "You're on the list";

type RecordedCall = {
  method: string;
  path: string;
  body?: unknown;
};

/**
 * Stubs `globalThis.fetch` with a single canned response matching the shape
 * `joinWaitlist` consumes (it reads the body via `response.text()`). Returns
 * the recorded calls for asserting outgoing requests.
 */
function mockFetch(response: { status: number; body: unknown }): {
  calls: RecordedCall[];
} {
  const calls: RecordedCall[] = [];

  vi.stubGlobal(
    "fetch",
    (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
      const href =
        typeof input === "string"
          ? input
          : input instanceof URL
            ? input.href
            : input.url;
      const path = new URL(href, "http://localhost:8000").pathname;
      const method = (init?.method ?? "GET").toUpperCase();
      const body =
        typeof init?.body === "string" ? (JSON.parse(init.body) as unknown) : undefined;
      calls.push({ method, path, body });

      return Promise.resolve({
        ok: response.status >= 200 && response.status < 300,
        status: response.status,
        text: async () => JSON.stringify(response.body),
      } as Response);
    },
  );

  return { calls };
}

/**
 * Sets an input's value through the native prototype setter so React's value
 * tracker registers the change, then dispatches an `input` event for
 * react-hook-form's onChange subscription.
 */
function typeInto(input: HTMLInputElement, value: string) {
  const setter = Object.getOwnPropertyDescriptor(
    HTMLInputElement.prototype,
    "value",
  )!.set!;
  setter.call(input, value);
  input.dispatchEvent(new Event("input", { bubbles: true }));
}

let result: RenderResult | undefined;

afterEach(() => {
  result?.unmount();
  result = undefined;
  vi.unstubAllGlobals();
});

async function mountForm(): Promise<HTMLElement> {
  result = renderInDom(<WaitlistForm />);
  const { container } = result;
  await waitFor(() => container.querySelector("input[type=email]") !== null);
  return container;
}

async function submitEmail(container: HTMLElement, email: string) {
  const input = container.querySelector<HTMLInputElement>("input[type=email]")!;
  typeInto(input, email);
  container.querySelector<HTMLButtonElement>("button[type=submit]")!.click();
}

describe("WaitlistForm", () => {
  it("shows the confirmation and POSTs the email on success", async () => {
    const { calls } = mockFetch({
      status: 201,
      body: { id: "1", email: "a@b.com", created_at: "2026-06-10T00:00:00Z" },
    });
    const container = await mountForm();

    await submitEmail(container, "a@b.com");

    await waitFor(() => container.textContent!.includes(CONFIRMATION));
    expect(calls).toEqual([
      { method: "POST", path: "/api/v1/waitlist", body: { email: "a@b.com" } },
    ]);
    expect(container.querySelector("form")).toBeNull();
  });

  it("treats WAITLIST_EMAIL_ALREADY_EXISTS as success", async () => {
    mockFetch({
      status: 409,
      body: { detail: "WAITLIST_EMAIL_ALREADY_EXISTS" },
    });
    const container = await mountForm();

    await submitEmail(container, "a@b.com");

    await waitFor(() => container.textContent!.includes(CONFIRMATION));
    expect(container.querySelector("[role=alert]")).toBeNull();
  });

  it("shows the friendly rate-limit error on 429", async () => {
    mockFetch({ status: 429, body: { detail: "TOO_MANY_REQUESTS" } });
    const container = await mountForm();

    await submitEmail(container, "a@b.com");

    await waitFor(() => container.querySelector("[role=alert]") !== null);
    expect(container.querySelector("[role=alert]")!.textContent).toBe(
      "Too many attempts. Please wait a moment and try again.",
    );
    expect(container.textContent).not.toContain(CONFIRMATION);
  });

  it("shows the zod validation message for an invalid email", async () => {
    const { calls } = mockFetch({ status: 201, body: {} });
    const container = await mountForm();

    await submitEmail(container, "not-an-email");

    await waitFor(() => container.querySelector("[role=alert]") !== null);
    expect(container.querySelector("[role=alert]")!.textContent).toBe(
      "Enter a valid email address.",
    );
    expect(calls).toEqual([]);
  });
});
