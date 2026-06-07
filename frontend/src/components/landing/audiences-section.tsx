import { Check } from "lucide-react";
import {
  Card,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Section } from "@/components/ui/section";
import { SectionHeading } from "@/components/ui/section-heading";

const developerBenefits = [
  {
    title: "Fairer reviews",
    detail: "Walk in with data you can inspect, not a manager's memory.",
  },
  {
    title: "A brag doc that fills itself",
    detail: "Real commits, reviews, and shipped work, collected as you go.",
  },
  {
    title: "Resume datapoints",
    detail: "Concrete signal about what you actually shipped.",
  },
  {
    title: "Metrics you can change",
    detail: "Every number about you is open SQL. Read it, question it, fix it.",
  },
];

const leaderBenefits = [
  "See where teams are stuck and what's slowing delivery",
  "Unblock people instead of measuring them from a distance",
  "Trust the rollup, because every number under it is inspectable",
];

export function AudiencesSection() {
  return (
    <Section id="for-teams">
      <SectionHeading
        title="Built for developers first"
        description="The work you already do, turned into evidence you own."
      />

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

      <p className="text-muted-foreground mt-6 text-center text-sm">
        Your record is yours. You see exactly how every number was made.
      </p>

      <div className="mt-24">
        <SectionHeading
          title="The same numbers, for leaders"
          description="Leaders work from the exact metrics developers see, not a separate hidden scorecard."
        />

        <div className="mx-auto mt-12 max-w-2xl">
          <Card className="gap-4 p-6">
            <ul className="space-y-3">
              {leaderBenefits.map((item) => (
                <li key={item} className="flex items-start gap-2.5">
                  <Check className="text-primary mt-0.5 size-4 shrink-0" />
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          </Card>

          <p className="text-muted-foreground mt-6 text-center text-sm">
            Defaults to aggregate signal. Drilling into one person is opt-in, never the
            default.
          </p>
        </div>
      </div>
    </Section>
  );
}
