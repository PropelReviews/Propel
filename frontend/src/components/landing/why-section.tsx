import { Section } from "@/components/ui/section";
import { SectionHeading } from "@/components/ui/section-heading";

export function WhySection() {
  return (
    <Section id="why">
      <div className="grid gap-12 lg:grid-cols-2 lg:gap-16">
        <SectionHeading
          align="left"
          title="Most analytics tools optimize for managers. Propel optimizes for engineers."
        />

        <div className="text-muted-foreground space-y-6 text-lg leading-relaxed">
          <p>
            Performance measurement only works when the people being measured
            trust it. That requires transparency at every layer: the source
            data, the transformation logic, and the final numbers on the
            dashboard.
          </p>
          <p>
            When any of that is hidden, metrics feel like surveillance. When all
            of it is visible, they become a shared basis for accountability.
          </p>
          <p className="text-foreground font-medium">
            Propel is built on that principle. Every metric is defined in open,
            readable SQL, and every step in the pipeline is open source.
          </p>
        </div>
      </div>
    </Section>
  );
}
