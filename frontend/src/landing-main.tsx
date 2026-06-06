import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { ThemeProvider } from "./components/theme-provider";
import "./index.css";
import { PostHogProvider } from "./providers/posthog-provider";
import { LandingPage } from "./pages/landing/LandingPage";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ThemeProvider>
      <PostHogProvider>
        <LandingPage />
      </PostHogProvider>
    </ThemeProvider>
  </StrictMode>,
);
