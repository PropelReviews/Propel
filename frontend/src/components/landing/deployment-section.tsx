import { ArrowRight, Check, Cloud, Server } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { CodeBlock } from "@/components/ui/code-block";
import { FeatureIcon } from "@/components/ui/feature-icon";
import { Section } from "@/components/ui/section";
import { SectionHeading } from "@/components/ui/section-heading";
import { appUrl, githubUrl } from "./links";

const selfHostedSnippet = `git clone https://github.com/PropelReviews/Propel
cd Propel
cp .env.example .env
docker-compose up`;

const selfHostedHighlights = [
  "No account required",
  "No API keys phoning home",
  "No telemetry unless you opt in",
];

export function DeploymentSection() {
  return (
    <Section id="deploy">
      <SectionHeading
        title="The same software, however you run it"
        description="Propel is the same open source software whether you run it yourself or we run it for you. Pick the option that fits your team."
      />

      <div className="mt-16 grid gap-6 lg:grid-cols-2">
        <Card className="flex flex-col">
          <CardHeader>
            <FeatureIcon icon={Cloud} className="mb-2" />
            <CardTitle className="text-xl">Propel Cloud</CardTitle>
            <CardDescription className="leading-relaxed">
              The managed version of Propel. We handle infrastructure, updates, and
              operations. You get the same metrics, the same SQL, and the same
              transparency without running anything yourself.
            </CardDescription>
          </CardHeader>
          <CardContent className="flex-1">
            <p className="text-muted-foreground text-sm">
              Best if you want Propel running quickly and do not want to operate the
              stack.
            </p>
          </CardContent>
          <CardFooter>
            <Button asChild>
              <a href={appUrl}>
                Get started
                <ArrowRight className="size-4" />
              </a>
            </Button>
          </CardFooter>
        </Card>

        <Card className="flex flex-col">
          <CardHeader>
            <FeatureIcon icon={Server} className="mb-2" />
            <CardTitle className="text-xl">Self-hosted</CardTitle>
            <CardDescription className="leading-relaxed">
              Run Propel entirely in your own infrastructure. Your data never leaves
              your environment, with full control over where it lives and who can access
              it.
            </CardDescription>
          </CardHeader>
          <CardContent className="flex-1 space-y-4">
            <CodeBlock code={selfHostedSnippet} />
            <ul className="text-muted-foreground space-y-2 text-sm">
              {selfHostedHighlights.map((highlight) => (
                <li key={highlight} className="flex items-center gap-2">
                  <Check className="size-4 shrink-0" />
                  {highlight}
                </li>
              ))}
            </ul>
          </CardContent>
          <CardFooter>
            <Button variant="outline" asChild>
              <a href={githubUrl} target="_blank" rel="noreferrer">
                Read the docs
              </a>
            </Button>
          </CardFooter>
        </Card>
      </div>
    </Section>
  );
}
