import { Code2, Eye, GitBranch, ShieldCheck } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
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
    icon: ShieldCheck,
    title: "Fully open source core",
    description:
      "Open source and self-hostable. No proprietary engine deciding how your team is scored.",
  },
  {
    icon: GitBranch,
    title: "Read the code yourself",
    description:
      "Disagree with a metric? Trace it, fix it, or open a pull request. The people being measured can change how they're measured.",
  },
  {
    icon: Code2,
    title: "Every metric is open SQL",
    description:
      "No black-box scores. Each number is a query you can open, review, and edit.",
  },
  {
    icon: Eye,
    title: "Traceable end to end",
    description:
      "Follow any number from the dashboard to the query that produced it, down to the raw event it came from.",
  },
];

export function DifferentiatorsSection() {
  return (
    <Section>
      <SectionHeading
        title="Transparency you can verify"
        description="If you want to know how a number was calculated, you can find out. Always."
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
