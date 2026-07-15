import { ArrowRight } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Section } from "@/components/ui/section";
import { SectionHeading } from "@/components/ui/section-heading";

const steps = [
  {
    label: "Connect",
    detail: "GitHub, Linear, Cursor. Open connector model.",
  },
  {
    label: "Compute",
    detail: "Activity becomes primitives, primitives become your metrics.",
  },
  {
    label: "Inspect",
    detail: "Every step is open source.",
  },
];

export function HowItWorksSection() {
  return (
    <Section id="how-it-works">
      <SectionHeading title="Connect. Compute. Inspect." />

      <div className="mt-16 flex flex-col items-stretch gap-3 lg:flex-row lg:items-center lg:justify-center">
        {steps.map((step, index) => (
          <div key={step.label} className="flex flex-col lg:flex-row lg:items-center">
            <Card className="flex-1 px-5 py-4 text-center lg:max-w-xs lg:min-w-48">
              <div className="font-medium">{step.label}</div>
              <div className="text-muted-foreground mt-1 text-sm">{step.detail}</div>
            </Card>
            {index < steps.length - 1 && (
              <ArrowRight className="text-muted-foreground mx-auto my-2 size-4 rotate-90 lg:mx-2 lg:my-0 lg:rotate-0" />
            )}
          </div>
        ))}
      </div>
    </Section>
  );
}
