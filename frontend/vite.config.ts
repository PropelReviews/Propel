import path from "path";
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig, loadEnv } from "vite";

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
        env.VITE_POSTHOG_KEY ?? env.POSTHOG_API_KEY ?? "",
      ),
      "import.meta.env.VITE_POSTHOG_HOST": JSON.stringify(
        env.VITE_POSTHOG_HOST ?? env.POSTHOG_HOST ?? "https://us.i.posthog.com",
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
