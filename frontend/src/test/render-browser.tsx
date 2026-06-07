import type { ReactNode } from "react";
import { createRoot } from "react-dom/client";

export interface RenderResult {
  container: HTMLElement;
  unmount: () => void;
}

/**
 * Minimal React mount helper for Vitest browser tests. Renders `ui` into a
 * sized, detached container appended to the document so layout-dependent
 * components (charts) measure a real box.
 */
export function renderInDom(ui: ReactNode): RenderResult {
  const container = document.createElement("div");
  container.style.width = "640px";
  document.body.appendChild(container);

  const root = createRoot(container);
  root.render(ui);

  return {
    container,
    unmount() {
      root.unmount();
      container.remove();
    },
  };
}

/**
 * Polls `predicate` until it returns true or the timeout elapses. Use this
 * instead of a fixed delay: React 19's concurrent render plus Recharts'
 * measure-then-render means content can appear a few frames after mount.
 */
export async function waitFor(
  predicate: () => boolean,
  { timeout = 5000, interval = 25 }: { timeout?: number; interval?: number } = {},
): Promise<void> {
  const start = Date.now();
  while (!predicate()) {
    if (Date.now() - start > timeout) {
      throw new Error("waitFor: condition not met before timeout");
    }
    await new Promise((resolve) => setTimeout(resolve, interval));
  }
}
