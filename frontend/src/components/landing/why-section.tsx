import { Check, X } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Section } from "@/components/ui/section";
import { SectionHeading } from "@/components/ui/section-heading";

const mostTools = [
  "Definitions you didn't choose",
  "Numbers you can't see into",
  "Handed down from above",
  "So people distrust or game them",
];

const propel = [
  "Definitions your team writes",
  "Every number traceable to SQL",
  "Open source, self-hostable",
  "Disagree? Change it.",
];

export function WhySection() {
  return (
    <Section id="why">
      <SectionHeading title="Nobody wants imposed metrics" />

      <div className="mt-16 grid gap-6 lg:grid-cols-2">
        <Card className="gap-4 p-6">
          <div className="text-muted-foreground text-xs font-semibold tracking-wide uppercase">
            Most tools
          </div>
          <ul className="space-y-3">
            {mostTools.map((item) => (
              <li key={item} className="text-muted-foreground flex items-start gap-2.5">
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
        The only metrics people trust are the ones they chose.
      </p>
    </Section>
  );
}
