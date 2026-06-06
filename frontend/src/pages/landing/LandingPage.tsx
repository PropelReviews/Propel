import { useEffect } from "react";
import { usePostHog } from "posthog-js/react";
import { MarketingLayout } from "@/components/landing/marketing-layout";
import { HeroSection } from "@/components/landing/hero-section";
import { WhySection } from "@/components/landing/why-section";
import { DifferentiatorsSection } from "@/components/landing/differentiators-section";
import { MetricsSection } from "@/components/landing/metrics-section";
import { ArchitectureSection } from "@/components/landing/architecture-section";
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
      <DifferentiatorsSection />
      <MetricsSection />
      <ArchitectureSection />
      <DeploymentSection />
    </MarketingLayout>
  );
}
