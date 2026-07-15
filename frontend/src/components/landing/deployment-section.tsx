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
import { useAuthFlag } from "@/hooks/use-auth-flag";
import { appUrl, githubUrl } from "./links";
import { WaitlistForm } from "./waitlist-form";

const selfHostedSnippet = `git clone https://github.com/PropelReviews/Propel
cd Propel
cp .env.example .env
docker-compose up`;

const selfHostedHighlights = [
  "No account required",
  "No keys phoning home",
  "No telemetry unless you opt in",
];

export function DeploymentSection() {
  const authEnabled = useAuthFlag();

  return (
    <Section id="deploy">
      <SectionHeading title="Same software, however you run it" />

      <div className="mt-16 grid gap-6 lg:grid-cols-2">
        <Card className="flex flex-col">
          <CardHeader>
            <FeatureIcon icon={Cloud} className="mb-2" />
            <CardTitle className="text-xl">Propel Cloud</CardTitle>
            <CardDescription className="leading-relaxed">
              Managed. Same metrics, same SQL, same transparency. Zero ops.
            </CardDescription>
          </CardHeader>
          <CardFooter className="mt-auto">
            {authEnabled ? (
              <Button asChild>
                <a href={appUrl}>
                  Try Propel Cloud
                  <ArrowRight className="size-4" />
                </a>
              </Button>
            ) : (
              <WaitlistForm variant="card" />
            )}
          </CardFooter>
        </Card>

        <Card className="flex flex-col">
          <CardHeader>
            <FeatureIcon icon={Server} className="mb-2" />
            <CardTitle className="text-xl">Self-hosted</CardTitle>
            <CardDescription className="leading-relaxed">
              Your infra. Your data never leaves.
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
