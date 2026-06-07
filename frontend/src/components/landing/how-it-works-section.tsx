import { ArrowRight } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Section } from "@/components/ui/section";
import { SectionHeading } from "@/components/ui/section-heading";

const steps = [
  {
    label: "Connect your tools",
    detail: "Plug in GitHub, Linear, and Cursor.",
  },
  {
    label: "Propel does the rest",
    detail: "We turn the activity into insights.",
  },
  {
    label: "See how it is made",
    detail: "Every step is open source to inspect.",
  },
];

export function HowItWorksSection() {
  return (
    <Section id="how-it-works">
      <SectionHeading
        title="An open pipeline, end to end"
        description="Connect your tools and Propel turns the activity into insights. No internals to learn, and because it is all open source you can see exactly how every insight is made."
      />

      <div className="mt-16 flex flex-col items-stretch gap-3 lg:flex-row lg:items-center lg:justify-center">
        {steps.map((step, index) => (
          <div key={step.label} className="flex flex-col lg:flex-row lg:items-center">
            <Card className="flex-1 px-5 py-4 text-center lg:min-w-48">
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
