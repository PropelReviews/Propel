import { ArrowRight } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Section } from "@/components/ui/section";
import { useAuthFlag } from "@/hooks/use-auth-flag";
import { appUrl, githubUrl } from "./links";
import { GithubIcon } from "./github-icon";
import { WaitlistForm } from "./waitlist-form";

export function HeroSection() {
  const authEnabled = useAuthFlag();

  return (
    <Section
      bordered={false}
      className="relative overflow-hidden"
      containerClassName="py-24 sm:py-32"
    >
      {/* Brand-gradient glow behind the hero copy. */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-x-0 -top-40 mx-auto h-96 max-w-3xl rounded-full bg-[radial-gradient(ellipse_at_center,color-mix(in_oklab,var(--color-brand-blue)_25%,transparent),color-mix(in_oklab,var(--color-brand-cyan)_10%,transparent)_55%,transparent_75%)] blur-3xl"
      />

      <div className="relative mx-auto max-w-3xl text-center">
        <Badge variant="outline" className="mb-6 gap-2">
          <span className="bg-primary size-1.5 rounded-full" />
          Fully open source. Self-hostable.
        </Badge>

        <h1 className="text-4xl font-semibold tracking-tight text-balance sm:text-6xl">
          <span className="text-gradient-brand">Transparent analytics</span> for
          engineering teams
        </h1>

        <p className="text-muted-foreground mt-6 text-lg text-pretty sm:text-xl">
          Your work in GitHub, Linear, and Cursor, turned into metrics you can read,
          trace, and trust. Built first for the developers doing the work, open to
          everyone who depends on it.
        </p>

        <div className="mt-10 flex flex-col items-center justify-center gap-3 sm:flex-row">
          <Button size="lg" variant="outline" asChild>
            <a href={githubUrl} target="_blank" rel="noreferrer">
              <GithubIcon className="size-4" />
              Read the code
            </a>
          </Button>
          {authEnabled ? (
            <Button size="lg" asChild>
              <a href={appUrl}>
                Try Propel Cloud
                <ArrowRight className="size-4" />
              </a>
            </Button>
          ) : (
            <WaitlistForm variant="inline" />
          )}
        </div>
      </div>
    </Section>
  );
}
