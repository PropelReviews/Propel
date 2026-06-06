import { Activity, GitPullRequest, Timer, TrendingUp } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import {
  Card,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Section } from "@/components/ui/section";
import { SectionHeading } from "@/components/ui/section-heading";

type Metric = {
  icon: LucideIcon;
  title: string;
  description: string;
};

const metrics: Metric[] = [
  {
    icon: Timer,
    title: "Cycle time",
    description: "How long work takes from start to finish.",
  },
  {
    icon: TrendingUp,
    title: "Throughput",
    description: "How much work your team ships over time.",
  },
  {
    icon: GitPullRequest,
    title: "Review patterns",
    description: "How code review flows through your process.",
  },
  {
    icon: Activity,
    title: "Tooling activity",
    description: "Signals from the tools your team already uses.",
  },
];

export function MetricsSection() {
  return (
    <Section id="metrics">
      <SectionHeading
        title="What Propel measures"
        description="Propel pulls from your toolchain and surfaces engineering metrics. The exact set evolves with the project; what stays constant is that every one of them is inspectable."
      />

      <div className="mt-16 grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
        {metrics.map((metric) => (
          <Card key={metric.title} className="gap-3 p-6">
            <metric.icon className="text-muted-foreground size-5" />
            <CardHeader className="p-0">
              <CardTitle>{metric.title}</CardTitle>
              <CardDescription className="leading-relaxed">
                {metric.description}
              </CardDescription>
            </CardHeader>
          </Card>
        ))}
      </div>
    </Section>
  );
}
