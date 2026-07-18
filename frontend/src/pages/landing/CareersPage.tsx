import { Button } from "@/components/ui/button";
import { MarketingLayout } from "@/components/landing/marketing-layout";
import { Section } from "@/components/ui/section";
import { SectionHeading } from "@/components/ui/section-heading";

const CAREERS_EMAIL = "sam@propel.ninja";
const CAREERS_MAILTO = `mailto:${CAREERS_EMAIL}`;

export function CareersPage() {
  return (
    <MarketingLayout>
      <Section bordered={false} containerClassName="py-16 sm:py-24">
        <div className="mx-auto max-w-2xl">
          <SectionHeading
            align="left"
            title="Careers"
            description="We're a small team building transparent engineering analytics. If that sounds like your kind of work, we'd love to hear from you."
          />
          <p className="text-muted-foreground mt-8 text-base leading-relaxed">
            There isn&apos;t a formal openings board yet — reach out directly and tell
            us what you&apos;re interested in building.
          </p>
          <div className="mt-10">
            <Button asChild size="lg" analyticsName="careers_email">
              <a href={CAREERS_MAILTO}>Email {CAREERS_EMAIL}</a>
            </Button>
            <p className="text-muted-foreground mt-4 text-sm">
              Or write to{" "}
              <a
                href={CAREERS_MAILTO}
                className="text-foreground underline underline-offset-4"
              >
                {CAREERS_EMAIL}
              </a>
            </p>
          </div>
        </div>
      </Section>
    </MarketingLayout>
  );
}
