import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { Button, buttonVariants } from "@/components/ui/button";
import { useAuthFlag } from "@/hooks/use-auth-flag";
import { useLandingBlogFlag } from "@/hooks/use-landing-blog-flag";
import { useLandingCareersFlag } from "@/hooks/use-landing-careers-flag";
import { cn } from "@/lib/utils";
import { appUrl, githubUrl } from "./links";
import { GithubIcon } from "./github-icon";
import { Footer } from "./footer";

const sectionNavLinks = [
  { href: "/#why", label: "Why Propel" },
  { href: "/#define", label: "Define" },
  { href: "/#for-teams", label: "For teams" },
  { href: "/#transparency", label: "Transparency" },
  { href: "/#deploy", label: "Deploy" },
];

export function MarketingLayout({ children }: { children: ReactNode }) {
  const authEnabled = useAuthFlag();
  const blogEnabled = useLandingBlogFlag();
  const careersEnabled = useLandingCareersFlag();

  return (
    <div className="bg-background text-foreground flex min-h-svh flex-col">
      <header className="border-border/60 bg-background/80 sticky top-0 z-50 border-b backdrop-blur">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-6">
          <Link to="/" className="flex items-center gap-2">
            <img src="/favicon.svg" alt="" className="size-7" />
            <span className="text-gradient-brand text-lg font-semibold tracking-tight">
              Propel
            </span>
          </Link>

          <nav className="hidden items-center gap-1 md:flex">
            {sectionNavLinks.map((link) => (
              <a
                key={link.href}
                href={link.href}
                className={cn(
                  buttonVariants({ variant: "ghost", size: "sm" }),
                  "text-muted-foreground",
                )}
              >
                {link.label}
              </a>
            ))}
            {blogEnabled && (
              <Link
                to="/blog"
                className={cn(
                  buttonVariants({ variant: "ghost", size: "sm" }),
                  "text-muted-foreground",
                )}
              >
                Blog
              </Link>
            )}
            {careersEnabled && (
              <Link
                to="/careers"
                className={cn(
                  buttonVariants({ variant: "ghost", size: "sm" }),
                  "text-muted-foreground",
                )}
              >
                Careers
              </Link>
            )}
          </nav>

          <div className="flex items-center gap-2">
            <Button variant="ghost" size="sm" asChild>
              <a href={githubUrl} target="_blank" rel="noreferrer">
                <GithubIcon className="size-4" />
                GitHub
              </a>
            </Button>
            {authEnabled && (
              <Button size="sm" asChild>
                <a href={appUrl}>Open app</a>
              </Button>
            )}
          </div>
        </div>
      </header>

      <main id="top" className="flex-1">
        {children}
      </main>

      <Footer />
    </div>
  );
}
