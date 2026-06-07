import { useEffect } from "react";
import { usePostHog } from "posthog-js/react";
import { MarketingLayout } from "@/components/landing/marketing-layout";
import { HeroSection } from "@/components/landing/hero-section";
import { WhySection } from "@/components/landing/why-section";
import { AudiencesSection } from "@/components/landing/audiences-section";
import { DifferentiatorsSection } from "@/components/landing/differentiators-section";
import { MetricsSection } from "@/components/landing/metrics-section";
import { HowItWorksSection } from "@/components/landing/how-it-works-section";
import { DeploymentSection } from "@/components/landing/deployment-section";

export function LandingPage() {
  const posthog = usePostHog();

  useEffect(() => {
    posthog?.capture("landing_viewed");
  }, [posthog]);

  return (
    <MarketingLayout>
      <HeroSection />
      <WhySection />
      <AudiencesSection />
      <DifferentiatorsSection />
      <MetricsSection />
      <HowItWorksSection />
      <DeploymentSection />
    </MarketingLayout>
  );
}
