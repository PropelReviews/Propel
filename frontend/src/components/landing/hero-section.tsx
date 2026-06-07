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
          Fully open source. Self-hostable.
        </Badge>

        <h1 className="text-4xl font-semibold tracking-tight text-balance sm:text-6xl">
          Transparent analytics for engineering teams
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
          <Button size="lg" asChild>
            <a href={appUrl}>
              Try Propel Cloud
              <ArrowRight className="size-4" />
            </a>
          </Button>
        </div>
      </div>
    </Section>
  );
}
