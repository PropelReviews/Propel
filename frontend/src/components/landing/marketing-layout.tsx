import type { ReactNode } from "react";
import { Button, buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { appUrl, githubUrl } from "./links";
import { GithubIcon } from "./github-icon";
import { Footer } from "./footer";

const navLinks = [
  { href: "#why", label: "Why Propel" },
  { href: "#metrics", label: "Metrics" },
  { href: "#architecture", label: "How it works" },
  { href: "#deploy", label: "Deploy" },
];

export function MarketingLayout({ children }: { children: ReactNode }) {
  return (
    <div className="bg-background text-foreground flex min-h-svh flex-col">
      <header className="border-border/60 bg-background/80 sticky top-0 z-50 border-b backdrop-blur">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-6">
          <a href="#top" className="text-lg font-semibold tracking-tight">
            Propel
          </a>

          <nav className="hidden items-center gap-1 md:flex">
            {navLinks.map((link) => (
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
          </nav>

          <div className="flex items-center gap-2">
            <Button variant="ghost" size="sm" asChild>
              <a href={githubUrl} target="_blank" rel="noreferrer">
                <GithubIcon className="size-4" />
                GitHub
              </a>
            </Button>
            <Button size="sm" asChild>
              <a href={appUrl}>Open app</a>
            </Button>
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
