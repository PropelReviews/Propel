import { ArrowRight, FileCode2, GitBranch, Pencil } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { FeatureIcon } from "@/components/ui/feature-icon";
import { Section } from "@/components/ui/section";
import { SectionHeading } from "@/components/ui/section-heading";
import { MetricBuilderDemo } from "@/features/metrics/builder/metric-builder-demo";

type SupportPoint = {
  icon: LucideIcon;
  title: string;
  description: string;
};

type GoalRow = {
  goal: string;
  metric: string;
};

const goalRows: GoalRow[] = [
  {
    goal: "Ship the platform migration",
    metric: "Migration PRs merged per week",
  },
  {
    goal: "Raise code quality",
    metric: "Rework rate on shipped work",
  },
  {
    goal: "Deeper reviews, not faster ones",
    metric: "Substantive comments per merged PR",
  },
];

const supportPoints: SupportPoint[] = [
  {
    icon: FileCode2,
    title: "Start with standards",
    description: "DORA and flow metrics, built in.",
  },
  {
    icon: Pencil,
    title: "Rewrite anything",
    description: "Every default is editable, none are hard-coded.",
  },
  {
    icon: GitBranch,
    title: "Versioned like code",
    description:
      "Every metric saves as a plain config file in your repo. Reviewable, diffable, traceable to SQL.",
  },
];

export function DefineSuccessSection() {
  return (
    <Section id="define">
      <SectionHeading
        title="Wanted metrics are self-defined"
        description="Every tool ships its own idea of a healthy team. Yours is different."
      />

      {/* Beat 1 — the why: this quarter's goals become this quarter's metrics. */}
      <div className="border-border/60 bg-card mx-auto mt-12 max-w-3xl overflow-hidden rounded-xl border shadow-sm">
        <div className="border-border/60 text-muted-foreground grid grid-cols-[1fr_auto_1fr] items-center gap-3 border-b px-5 py-3 text-xs font-medium tracking-wide uppercase">
          <span>This quarter's goal</span>
          <span aria-hidden className="w-4" />
          <span>The metric you'd build</span>
        </div>
        {goalRows.map((row) => (
          <div
            key={row.goal}
            className="border-border/60 grid grid-cols-[1fr_auto_1fr] items-center gap-3 border-b px-5 py-4 last:border-b-0"
          >
            <span className="text-sm font-medium">{row.goal}</span>
            <ArrowRight aria-hidden className="text-muted-foreground size-4" />
            <span className="text-primary font-mono text-sm">{row.metric}</span>
          </div>
        ))}
      </div>

      <p className="text-muted-foreground mx-auto mt-8 max-w-3xl text-center text-lg text-pretty">
        A metric is only wanted when it points at something your team is actually trying
        to do. Propel turns this quarter's goals into this quarter's metrics — and when
        your goals change, your metrics change with them.
      </p>

      {/* Beat 2 — the how: the wizard, right under the speed claim. */}
      <h3 className="mt-16 text-center text-2xl font-semibold tracking-tight text-balance">
        Build it in minutes. No query language required.
      </h3>

      <MetricBuilderDemo variant="full" className="mx-auto mt-8" />

      <div className="mt-12 grid gap-6 sm:grid-cols-3">
        {supportPoints.map((point) => (
          <Card key={point.title} className="gap-3 p-6">
            <FeatureIcon icon={point.icon} />
            <CardHeader className="p-0">
              <CardTitle className="text-lg">{point.title}</CardTitle>
              <CardDescription className="leading-relaxed">
                {point.description}
              </CardDescription>
            </CardHeader>
          </Card>
        ))}
      </div>
    </Section>
  );
}
