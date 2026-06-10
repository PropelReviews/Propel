import { useEffect, type ReactNode } from "react";
import type { Meta, StoryObj } from "@storybook/react-vite";

import { WaitlistForm } from "./waitlist-form";

const originalFetch = window.fetch.bind(window);

/**
 * Intercepts the waitlist POST so submitting the form in Storybook shows the
 * real submitting → success (or error) flow without a backend.
 */
function WaitlistFetchStub({
  status,
  children,
}: {
  status: number;
  children: ReactNode;
}) {
  useEffect(() => {
    window.fetch = async (input, init) => {
      const url =
        typeof input === "string"
          ? input
          : input instanceof URL
            ? input.toString()
            : input.url;
      if (url.endsWith("/api/v1/waitlist") && init?.method === "POST") {
        // Brief delay so the "Joining..." submitting state is visible.
        await new Promise((resolve) => setTimeout(resolve, 600));
        const { email } = JSON.parse(String(init.body)) as { email: string };
        const body =
          status < 400
            ? {
                id: "5f0c4b1e-9a2d-4a7e-8a51-2f3f7f1c9d10",
                email,
                created_at: new Date().toISOString(),
              }
            : { detail: { code: "INTERNAL_ERROR", reason: "Server error." } };
        return new Response(JSON.stringify(body), {
          status,
          headers: { "Content-Type": "application/json" },
        });
      }
      return originalFetch(input, init);
    };
    return () => {
      window.fetch = originalFetch;
    };
  }, [status]);

  return children;
}

const meta = {
  title: "Landing/WaitlistForm",
  component: WaitlistForm,
  tags: ["autodocs"],
  argTypes: {
    variant: {
      control: "select",
      options: ["inline", "card"],
    },
  },
} satisfies Meta<typeof WaitlistForm>;

export default meta;
type Story = StoryObj<typeof meta>;

/**
 * Hero variant: caps its own width at max-w-md. Submit a valid email to see
 * the centered confirmation message.
 */
export const Inline: Story = {
  args: { variant: "inline" },
  decorators: [
    (Story) => (
      <WaitlistFetchStub status={201}>
        <div className="flex w-2xl max-w-full justify-center">
          <Story />
        </div>
      </WaitlistFetchStub>
    ),
  ],
};

/**
 * Card variant: stretches to fill its container, e.g. a pricing card footer.
 */
export const Card: Story = {
  args: { variant: "card" },
  decorators: [
    (Story) => (
      <WaitlistFetchStub status={201}>
        <div className="border-border bg-card w-sm max-w-full rounded-xl border p-6">
          <p className="text-card-foreground mb-1 text-sm font-medium">Propel Cloud</p>
          <p className="text-muted-foreground mb-4 text-sm">
            Hosted analytics for your whole org.
          </p>
          <Story />
        </div>
      </WaitlistFetchStub>
    ),
  ],
};

/**
 * Submitting any email surfaces the server error below the input. Invalid
 * emails show the client-side zod validation error without hitting fetch.
 */
export const ServerError: Story = {
  args: { variant: "inline" },
  decorators: [
    (Story) => (
      <WaitlistFetchStub status={500}>
        <Story />
      </WaitlistFetchStub>
    ),
  ],
};
