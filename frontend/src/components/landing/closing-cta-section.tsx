import { ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Section } from "@/components/ui/section";
import { useAuthFlag } from "@/hooks/use-auth-flag";
import { appUrl, githubUrl } from "./links";
import { GithubIcon } from "./github-icon";
import { WaitlistForm } from "./waitlist-form";

export function ClosingCtaSection() {
  const authEnabled = useAuthFlag();

  return (
    <Section id="get-started" bordered={false} containerClassName="py-24 sm:py-28">
      <div className="mx-auto max-w-2xl text-center">
        <h2 className="text-3xl font-semibold tracking-tight text-balance sm:text-5xl">
          Measure what you mean.
        </h2>
        <p className="text-muted-foreground mt-6 text-lg text-pretty">
          Clone it. Run it. Read every line.
        </p>

        <div className="mt-10 flex flex-col items-center justify-center gap-3 sm:flex-row">
          <Button size="lg" asChild>
            <a href={githubUrl} target="_blank" rel="noreferrer">
              <GithubIcon className="size-4" />
              Get started on GitHub
            </a>
          </Button>
          {authEnabled ? (
            <Button size="lg" variant="outline" asChild>
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
