import { Target, Unplug, ShieldCheck } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { FeatureIcon } from "@/components/ui/feature-icon";
import { Section } from "@/components/ui/section";
import { SectionHeading } from "@/components/ui/section-heading";

const developerBenefits = [
  {
    title: "Fairer reviews",
    detail: "Data you can inspect, not a manager's memory.",
  },
  {
    title: "A brag doc that fills itself",
    detail: "Your shipped work, collected as you go.",
  },
  {
    title: "Resume datapoints",
    detail: "Proof of what you actually built.",
  },
  {
    title: "Metrics you can change",
    detail: "Question any number, rewrite its definition.",
  },
];

type LeaderBenefit = {
  icon: LucideIcon;
  title: string;
  detail: string;
};

const leaderBenefits: LeaderBenefit[] = [
  {
    icon: Target,
    title: "Measure your strategy",
    detail: "Your goals aren't DORA's. Define metrics that match them.",
  },
  {
    icon: Unplug,
    title: "Unblock, don't surveil",
    detail: "See where teams are stuck, then help.",
  },
  {
    icon: ShieldCheck,
    title: "Trust the rollup",
    detail: "Every aggregate is inspectable underneath.",
  },
];

export function AudiencesSection() {
  return (
    <Section id="for-teams">
      <SectionHeading title="Built for developers first" />

      <div className="mt-12 grid gap-6 sm:grid-cols-2">
        {developerBenefits.map((benefit) => (
          <Card key={benefit.title} className="gap-2 p-6">
            <CardHeader className="p-0">
              <CardTitle className="text-lg">{benefit.title}</CardTitle>
              <CardDescription className="leading-relaxed">
                {benefit.detail}
              </CardDescription>
            </CardHeader>
          </Card>
        ))}
      </div>

      <p className="text-foreground mx-auto mt-8 max-w-2xl text-center text-base font-medium text-balance">
        Your record is yours.
      </p>

      <div className="mt-24">
        <SectionHeading title="Same numbers. No hidden scorecard." />

        <div className="mt-12 grid gap-6 lg:grid-cols-3">
          {leaderBenefits.map((benefit) => (
            <Card key={benefit.title} className="gap-3 p-6">
              <FeatureIcon icon={benefit.icon} />
              <CardHeader className="p-0">
                <CardTitle className="text-lg">{benefit.title}</CardTitle>
                <CardDescription className="leading-relaxed">
                  {benefit.detail}
                </CardDescription>
              </CardHeader>
            </Card>
          ))}
        </div>

        <p className="text-muted-foreground mx-auto mt-8 max-w-2xl text-center text-sm">
          Aggregate by default. Individual drill-down is opt-in, never automatic.
        </p>

        <blockquote className="border-primary/40 bg-primary/5 mx-auto mt-10 max-w-3xl rounded-xl border px-6 py-5 text-center text-base font-medium text-balance sm:text-lg">
          Metrics leaders need. Metrics developers want. Only in the open.
        </blockquote>
      </div>
    </Section>
  );
}
