import { ArrowRight } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Section } from "@/components/ui/section";
import { appUrl, githubUrl } from "./links";
import { GithubIcon } from "./github-icon";

export function HeroSection() {
  return (
    <Section
      bordered={false}
      className="relative overflow-hidden"
      containerClassName="py-24 sm:py-32"
    >
      <div className="mx-auto max-w-3xl text-center">
        <Badge variant="outline" className="mb-6 gap-2">
          <span className="bg-primary size-1.5 rounded-full" />
          Open source. Trust first.
        </Badge>

        <h1 className="text-balance text-4xl font-semibold tracking-tight sm:text-6xl">
          Developer analytics your team can actually trust
        </h1>

        <p className="text-muted-foreground mt-6 text-pretty text-lg sm:text-xl">
          Propel connects to GitHub, Linear, and Cursor and turns raw
          engineering activity into metrics your team can inspect, question, and
          own. Every number is open, readable SQL.
        </p>

        <div className="mt-10 flex flex-col items-center justify-center gap-3 sm:flex-row">
          <Button size="lg" asChild>
            <a href={appUrl}>
              Get started
              <ArrowRight className="size-4" />
            </a>
          </Button>
          <Button size="lg" variant="outline" asChild>
            <a href={githubUrl} target="_blank" rel="noreferrer">
              <GithubIcon className="size-4" />
              View on GitHub
            </a>
          </Button>
        </div>

        <p className="text-muted-foreground mt-6 text-sm">
          Self-host in minutes or use Propel Cloud. No telemetry unless you opt
          in.
        </p>
      </div>
    </Section>
  );
}
