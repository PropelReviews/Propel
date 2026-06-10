import path from "path";
import tailwindcss from "@tailwindcss/vite";
import { playwright } from "@vitest/browser-playwright";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// Two test projects:
//  - `unit`: fast node tests (e.g. static-markup component checks, lib logic).
//  - `browser`: real-DOM tests for charts, which need layout + SVG to render.
//    These live in `*.browser.test.tsx` files and run in headless Chromium.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  // The image ships a root-owned `node_modules/.vite`, so the dev user can't
  // write the dep-optimizer cache there. Redirect it to a writable location.
  cacheDir: path.resolve(__dirname, ".vitest-cache"),
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  // Pre-bundle everything the browser tests import so the dep optimizer
  // commits once at startup. Late discovery would re-optimize mid-run, which
  // both duplicates React (broken hooks) and fails on filesystems where a
  // directory rename can't replace files Chromium holds open (9p/drvfs).
  optimizeDeps: {
    include: [
      "react",
      "react-dom/client",
      "react-router-dom",
      "radix-ui",
      "posthog-js",
      "posthog-js/react",
      "recharts",
      "lucide-react",
      "class-variance-authority",
      "clsx",
      "tailwind-merge",
    ],
  },
  test: {
    projects: [
      {
        extends: true,
        test: {
          name: "unit",
          environment: "node",
          include: ["src/**/*.test.{ts,tsx}"],
          exclude: ["src/**/*.browser.test.{ts,tsx}"],
        },
      },
      {
        extends: true,
        test: {
          name: "browser",
          include: ["src/**/*.browser.test.{ts,tsx}"],
          setupFiles: ["./vitest.setup.browser.ts"],
          browser: {
            enabled: true,
            provider: playwright(),
            headless: true,
            instances: [{ browser: "chromium" }],
          },
        },
      },
    ],
  },
});
