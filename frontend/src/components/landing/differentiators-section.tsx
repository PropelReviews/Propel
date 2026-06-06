import { Code2, Eye, GitBranch, ShieldCheck } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import {
  Card,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { FeatureIcon } from "@/components/ui/feature-icon";
import { Section } from "@/components/ui/section";
import { SectionHeading } from "@/components/ui/section-heading";

type Differentiator = {
  icon: LucideIcon;
  title: string;
  description: string;
};

const differentiators: Differentiator[] = [
  {
    icon: Code2,
    title: "Every metric is open SQL",
    description:
      "No black-box scores. Each number is defined in readable SQL you can open, review, and change.",
  },
  {
    icon: Eye,
    title: "Traceable end to end",
    description:
      "Follow any number from the dashboard to the query that produced it, down to the raw event it came from.",
  },
  {
    icon: GitBranch,
    title: "Open source pipeline",
    description:
      "Extraction, storage, and transformation are open source or well-known tools you can audit yourself.",
  },
  {
    icon: ShieldCheck,
    title: "Built trust first",
    description:
      "Metrics become a shared basis for accountability instead of surveillance, because nothing is hidden.",
  },
];

export function DifferentiatorsSection() {
  return (
    <Section>
      <SectionHeading
        title="Why Propel is different"
        description="If you want to know how a number was calculated, you can find out."
      />

      <div className="mt-16 grid gap-6 sm:grid-cols-2">
        {differentiators.map((item) => (
          <Card key={item.title} className="gap-3 p-6">
            <FeatureIcon icon={item.icon} />
            <CardHeader className="p-0">
              <CardTitle className="text-lg">{item.title}</CardTitle>
              <CardDescription className="leading-relaxed">
                {item.description}
              </CardDescription>
            </CardHeader>
          </Card>
        ))}
      </div>
    </Section>
  );
}
