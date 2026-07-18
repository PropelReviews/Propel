import type { ReactNode } from "react";
import { Navigate, Route, Routes } from "react-router-dom";

import { useLandingBlogFlag } from "@/hooks/use-landing-blog-flag";
import { useLandingCareersFlag } from "@/hooks/use-landing-careers-flag";
import { BlogIndexPage } from "@/pages/landing/blog/BlogIndexPage";
import { BlogPostPage } from "@/pages/landing/blog/BlogPostPage";
import { CareersPage } from "@/pages/landing/CareersPage";
import { LandingPage } from "@/pages/landing/LandingPage";

function RequireLandingBlogFlag({ children }: { children: ReactNode }) {
  const blogEnabled = useLandingBlogFlag();
  if (!blogEnabled) return <Navigate to="/" replace />;
  return children;
}

function RequireLandingCareersFlag({ children }: { children: ReactNode }) {
  const careersEnabled = useLandingCareersFlag();
  if (!careersEnabled) return <Navigate to="/" replace />;
  return children;
}

export function LandingRoutes() {
  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route
        path="/blog"
        element={
          <RequireLandingBlogFlag>
            <BlogIndexPage />
          </RequireLandingBlogFlag>
        }
      />
      <Route
        path="/blog/:slug"
        element={
          <RequireLandingBlogFlag>
            <BlogPostPage />
          </RequireLandingBlogFlag>
        }
      />
      <Route
        path="/careers"
        element={
          <RequireLandingCareersFlag>
            <CareersPage />
          </RequireLandingCareersFlag>
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
