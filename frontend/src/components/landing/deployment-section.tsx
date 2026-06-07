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
        description="Identical open source software whether you run it or we do. Pick what fits your team."
      />

      <div className="mt-16 grid gap-6 lg:grid-cols-2">
        <Card className="flex flex-col">
          <CardHeader>
            <FeatureIcon icon={Cloud} className="mb-2" />
            <CardTitle className="text-xl">Propel Cloud</CardTitle>
            <CardDescription className="leading-relaxed">
              Our managed platform. Same metrics, same SQL, same transparency, without
              running anything yourself.
            </CardDescription>
          </CardHeader>
          <CardContent className="flex-1">
            <p className="text-muted-foreground text-sm">
              Best if you want Propel up quickly and don't want to operate the stack.
            </p>
          </CardContent>
          <CardFooter>
            <Button asChild>
              <a href={appUrl}>
                Try Propel Cloud
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
              Run the open source core in your own infrastructure. Your data never
              leaves your environment. Full control over where it lives and who can
              touch it.
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
