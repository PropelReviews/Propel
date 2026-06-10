import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { ThemeProvider } from "./components/theme-provider";
import "./index.css";
import { AuthProvider } from "./providers/auth-provider";
import { PostHogProvider } from "./providers/posthog-provider";
import { TenantProvider } from "./providers/tenant-provider";
import { AppRoutes } from "./routes";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ThemeProvider>
      <PostHogProvider>
        <BrowserRouter>
          <AuthProvider>
            <TenantProvider>
              <AppRoutes />
            </TenantProvider>
          </AuthProvider>
        </BrowserRouter>
      </PostHogProvider>
    </ThemeProvider>
  </StrictMode>,
);
