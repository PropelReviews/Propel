import { ArrowRight } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Section } from "@/components/ui/section";
import { SectionHeading } from "@/components/ui/section-heading";

const pipeline = [
  { label: "Your tools", detail: "GitHub, Linear, Cursor" },
  { label: "Meltano", detail: "Extraction" },
  { label: "Postgres", detail: "Storage" },
  { label: "dbt", detail: "Transformations" },
  { label: "Propel", detail: "Dashboards + API" },
];

export function ArchitectureSection() {
  return (
    <Section id="architecture">
      <SectionHeading
        title="An open pipeline, end to end"
        description="Meltano extracts, Postgres stores, dbt transforms, and Propel presents. Each layer is either in our repository or a well-known open source project you can audit on your own."
      />

      <div className="mt-16 flex flex-col items-stretch gap-3 lg:flex-row lg:items-center lg:justify-center">
        {pipeline.map((stage, index) => (
          <div
            key={stage.label}
            className="flex flex-col lg:flex-row lg:items-center"
          >
            <Card className="flex-1 px-5 py-4 text-center lg:min-w-40">
              <div className="font-medium">{stage.label}</div>
              <div className="text-muted-foreground mt-1 text-sm">
                {stage.detail}
              </div>
            </Card>
            {index < pipeline.length - 1 && (
              <ArrowRight className="text-muted-foreground mx-auto my-2 size-4 rotate-90 lg:mx-2 lg:my-0 lg:rotate-0" />
            )}
          </div>
        ))}
      </div>
    </Section>
  );
}
