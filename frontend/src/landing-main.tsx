import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { ThemeProvider } from "./components/theme-provider";
import "./index.css";
import { LandingRoutes } from "./landing-routes";
import { PostHogProvider } from "./providers/posthog-provider";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ThemeProvider>
      <PostHogProvider>
        <BrowserRouter>
          <LandingRoutes />
        </BrowserRouter>
      </PostHogProvider>
    </ThemeProvider>
  </StrictMode>,
);
