import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import { ThemeProvider } from "./components/theme-provider";
import "./index.css";
import { PostHogProvider } from "./providers/posthog-provider";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ThemeProvider>
      <PostHogProvider>
        <App />
      </PostHogProvider>
    </ThemeProvider>
  </StrictMode>,
);
