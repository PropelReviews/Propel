import { Check, X } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Section } from "@/components/ui/section";
import { SectionHeading } from "@/components/ui/section-heading";

const blackBox = [
  "Numbers generated where you can't see",
  "Scored by logic you can't read",
  "Handed down to the people they describe",
  "So people distrust it, dispute it, or game it",
];

const propel = [
  "Fully open source and self-hostable",
  "Every metric is readable SQL",
  "Trace any number to the raw event",
  "Disagree? Fix it and open a pull request",
];

export function WhySection() {
  return (
    <Section id="why">
      <SectionHeading
        title="Analytics shouldn't feel like surveillance"
        description="When the pipeline is hidden, every metric feels like something being done to you. Propel is the opposite, by design."
      />

      <div className="mt-16 grid gap-6 lg:grid-cols-2">
        <Card className="gap-4 p-6">
          <div className="text-muted-foreground text-xs font-semibold tracking-wide uppercase">
            Most engineering analytics
          </div>
          <ul className="space-y-3">
            {blackBox.map((item) => (
              <li
                key={item}
                className="text-muted-foreground flex items-start gap-2.5"
              >
                <X className="mt-0.5 size-4 shrink-0" />
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </Card>

        <Card className="border-primary/30 gap-4 p-6">
          <div className="text-primary text-xs font-semibold tracking-wide uppercase">
            Propel
          </div>
          <ul className="space-y-3">
            {propel.map((item) => (
              <li key={item} className="flex items-start gap-2.5">
                <Check className="text-primary mt-0.5 size-4 shrink-0" />
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </Card>
      </div>

      <p className="text-foreground mx-auto mt-10 max-w-2xl text-center text-lg font-medium text-balance">
        Open measurement isn't a feature. It's the only kind developers will actually
        trust.
      </p>
    </Section>
  );
}
