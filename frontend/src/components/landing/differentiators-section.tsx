import { Code2, Eye, Pencil, ShieldCheck } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { CodeBlock } from "@/components/ui/code-block";
import { FeatureIcon } from "@/components/ui/feature-icon";
import { Section } from "@/components/ui/section";
import { SectionHeading } from "@/components/ui/section-heading";

type Differentiator = {
  icon: LucideIcon;
  title: string;
  description: string;
};

const differentiators: Differentiator[] = [
  {
    icon: ShieldCheck,
    title: "Open source core",
    description: "No proprietary engine scoring your team.",
  },
  {
    icon: Code2,
    title: "Open SQL",
    description: "Every number is a query you can read.",
  },
  {
    icon: Eye,
    title: "Traceable",
    description: "Dashboard → query → raw event.",
  },
  {
    icon: Pencil,
    title: "Changeable",
    description: "The measured can change how they're measured.",
  },
];

const traceSteps = [
  {
    label: "1. Number",
    body: "Cycle time: 2.4 days",
    kind: "metric" as const,
  },
  {
    label: "2. Definition",
    body: `metric: cycle_time
type: duration
primitive: pull_requests`,
    kind: "code" as const,
  },
  {
    label: "3. SQL",
    body: `SELECT avg(merged_at - opened_at)
FROM pull_requests
WHERE state = 'merged'`,
    kind: "code" as const,
  },
  {
    label: "4. Raw events",
    body: "pr#1842 opened → reviewed → merged",
    kind: "metric" as const,
  },
];

export function DifferentiatorsSection() {
  return (
    <Section id="transparency">
      <SectionHeading title="Don't trust it. Verify it." />

      <div className="mt-16 grid gap-6 sm:grid-cols-2">
        {differentiators.map((item) => (
          <Card key={item.title} className="gap-3 p-6">
            <FeatureIcon icon={item.icon} />
            <CardHeader className="p-0">
              <CardTitle className="text-lg">{item.title}</CardTitle>
              <CardDescription className="leading-relaxed">
                {item.description}
              </CardDescription>
            </CardHeader>
          </Card>
        ))}
      </div>

      <div className="mt-16">
        <p className="text-muted-foreground mb-6 text-center text-sm font-medium tracking-wide uppercase">
          Click to trace
        </p>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {traceSteps.map((step) => (
            <Card key={step.label} className="gap-3 p-5">
              <div className="text-primary text-xs font-semibold tracking-wide uppercase">
                {step.label}
              </div>
              {step.kind === "code" ? (
                <CodeBlock code={step.body} className="text-xs" />
              ) : (
                <p className="text-sm leading-relaxed font-medium">{step.body}</p>
              )}
            </Card>
          ))}
        </div>
      </div>
    </Section>
  );
}
