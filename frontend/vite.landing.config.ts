import path from "path";
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig, loadEnv, type Plugin } from "vite";

// The entry is landing.html, but Vite's dev/preview servers serve the root
// index.html (the app) for "/". This middleware rewrites "/" to landing.html so
// the dev server (and `preview`) serve the landing page at the root, matching
// the production CloudFront default_root_object.
function serveLandingAtRoot(): Plugin {
  const rewrite = (req: { url?: string }) => {
    if (req.url === "/" || req.url === "/index.html") {
      req.url = "/landing.html";
    }
  };
  return {
    name: "serve-landing-at-root",
    configureServer(server) {
      server.middlewares.use((req, _res, next) => {
        rewrite(req);
        next();
      });
    },
    configurePreviewServer(server) {
      server.middlewares.use((req, _res, next) => {
        rewrite(req);
        next();
      });
    },
  };
}

// Standalone build for the marketing landing site served on the apex/www
// domains (propel.ninja, www.propel.ninja, and the beta equivalents). It shares
// the app's design system but ships as its own bundle so the dashboard build at
// app.* stays untouched. Output goes to dist-landing/.
export default defineConfig(({ mode }) => {
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
        env.VITE_POSTHOG_HOST ?? env.POSTHOG_HOST ?? "https://metrics.propelreview.com",
      ),
      "import.meta.env.VITE_POSTHOG_UI_HOST": JSON.stringify(
        env.VITE_POSTHOG_UI_HOST ?? env.POSTHOG_UI_HOST ?? "https://us.posthog.com",
      ),
      // Where the "Open app" / "Get started" CTAs point. The deploy script sets
      // this per environment (e.g. https://app.beta.propel.ninja).
      "import.meta.env.VITE_APP_URL": JSON.stringify(
        env.VITE_APP_URL ?? "https://app.propel.ninja",
      ),
      // Backend API base URL for the waitlist signup. The deploy script sets
      // this per environment (e.g. https://api.beta.propel.ninja); defaults to
      // the local dev API.
      "import.meta.env.VITE_API_URL": JSON.stringify(
        env.VITE_API_URL ?? "http://localhost:8000",
      ),
      // Public GitHub repository used by the self-hosted CTAs.
      "import.meta.env.VITE_GITHUB_URL": JSON.stringify(
        env.VITE_GITHUB_URL ?? "https://github.com/PropelReviews/Propel",
      ),
    },
    plugins: [react(), tailwindcss(), serveLandingAtRoot()],
    resolve: {
      alias: {
        "@": path.resolve(__dirname, "./src"),
      },
    },
    // Separate dependency cache so running the landing dev server alongside the
    // app dev server (default node_modules/.vite) doesn't clash.
    cacheDir: path.resolve(__dirname, "node_modules/.vite-landing"),
    build: {
      outDir: "dist-landing",
      rollupOptions: {
        input: path.resolve(__dirname, "landing.html"),
      },
    },
    server: {
      host: "0.0.0.0",
      port: 5174,
      allowedHosts: ["frontend-landing", "localhost", "127.0.0.1"],
      hmr: {
        host: "localhost",
        port: 5174,
        clientPort: 5174,
      },
      watch: {
        usePolling: true,
        interval: 1000,
        ignored: [
          "**/node_modules/**",
          "**/.git/**",
          "**/dist/**",
          "**/dist-landing/**",
          "**/__screenshots__/**",
          "**/storybook-static/**",
        ],
      },
    },
  };
});
