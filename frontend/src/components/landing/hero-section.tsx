import { ArrowRight } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Section } from "@/components/ui/section";
import { MetricBuilderDemo } from "@/features/metrics/builder/metric-builder-demo";
import { githubUrl } from "./links";
import { GithubIcon } from "./github-icon";

export function HeroSection() {
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
          Open source. Self-hostable.
        </Badge>

        <h1 className="text-4xl font-semibold tracking-tight text-balance sm:text-6xl">
          Metrics your team <span className="text-gradient-brand">actually wants.</span>
        </h1>

        <p className="text-muted-foreground mt-6 text-lg text-pretty sm:text-xl">
          Not a vendor's scorecard. Propel turns GitHub, Linear, and Cursor into metrics
          your team defines, reads, and trusts.
        </p>

        <div className="mt-10 flex flex-col items-center justify-center gap-3 sm:flex-row">
          <Button size="lg" asChild>
            <a href={githubUrl} target="_blank" rel="noreferrer">
              <GithubIcon className="size-4" />
              Star on GitHub
            </a>
          </Button>
          <Button size="lg" variant="outline" asChild>
            <a href="#define">
              Create a metric
              <ArrowRight className="size-4" />
            </a>
          </Button>
        </div>
      </div>

      <MetricBuilderDemo variant="hero" className="relative mx-auto mt-16 max-w-5xl" />
    </Section>
  );
}
