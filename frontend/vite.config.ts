import { readFileSync } from "fs";
import path from "path";
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig, loadEnv } from "vite";

const pkg = JSON.parse(
  readFileSync(path.resolve(__dirname, "package.json"), "utf-8"),
) as { version?: string };

export default defineConfig(({ mode }) => {
  // Read env from the repo root (single shared .env for host dev) and from the
  // frontend dir (.env.local works inside the Docker container via bind mount,
  // no container rebuild needed). Local values win.
  const rootEnv = loadEnv(mode, path.resolve(__dirname, ".."), "");
  const localEnv = loadEnv(mode, __dirname, "");
  const env = { ...rootEnv, ...localEnv };

  return {
    envDir: path.resolve(__dirname, ".."),
    define: {
      "import.meta.env.VITE_POSTHOG_KEY": JSON.stringify(
        env.VITE_POSTHOG_KEY ?? env.POSTHOG_TOKEN ?? "",
      ),
      "import.meta.env.VITE_POSTHOG_HOST": JSON.stringify(
        env.VITE_POSTHOG_HOST ?? env.POSTHOG_HOST ?? "https://us.i.posthog.com",
      ),
      // Backend API base URL. The deploy script sets this per environment
      // (e.g. https://api.beta.propel.ninja); defaults to the local dev API.
      "import.meta.env.VITE_API_URL": JSON.stringify(
        env.VITE_API_URL ?? "http://localhost:8000",
      ),
      // Build-time metadata registered as PostHog super properties so every
      // event is attributable to an environment, app version, and commit.
      "import.meta.env.VITE_APP_ENV": JSON.stringify(
        env.VITE_APP_ENV ?? mode,
      ),
      "import.meta.env.VITE_APP_VERSION": JSON.stringify(
        env.VITE_APP_VERSION ?? pkg.version ?? "0.0.0",
      ),
      "import.meta.env.VITE_GIT_SHA": JSON.stringify(
        env.VITE_GIT_SHA ?? env.GITHUB_SHA ?? "dev",
      ),
    },
    plugins: [react(), tailwindcss()],
    resolve: {
      alias: {
        "@": path.resolve(__dirname, "./src"),
      },
    },
    server: {
      host: "0.0.0.0",
      port: 5173,
      watch: {
        // Bind mounts from the dev container may not propagate inotify events.
        usePolling: true,
      },
    },
  };
});
