import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { MetricSource } from "@/features/metrics/api/metric-definitions";

const STATUS_VARIANT: Record<
  string,
  "default" | "secondary" | "destructive" | "outline"
> = {
  active: "secondary",
  draft: "outline",
  deprecated: "outline",
  broken: "destructive",
  archived: "outline",
};

export function StatusChip({
  status,
  draftPending,
  className,
}: {
  status: string;
  draftPending?: boolean;
  className?: string;
}) {
  const label = status === "active" && draftPending ? "active · draft pending" : status;
  return (
    <Badge
      variant={STATUS_VARIANT[status] ?? "outline"}
      className={cn("font-mono text-[11px] tracking-wide uppercase", className)}
      data-testid="status-chip"
    >
      {label}
    </Badge>
  );
}

export function VisibilityBadge({
  visibility,
  className,
}: {
  visibility: string | null | undefined;
  className?: string;
}) {
  if (!visibility) return null;
  return (
    <Badge variant="outline" className={cn("capitalize", className)}>
      {visibility}
    </Badge>
  );
}

const SOURCE_LABEL: Record<MetricSource, string> = {
  standard: "Standard",
  standard_customized: "Standard · customized",
  custom: "Custom",
  variant: "Variant",
};

export function SourceBadge({
  source,
  extendsId,
  className,
}: {
  source: MetricSource;
  extendsId?: string | null;
  className?: string;
}) {
  const label =
    source === "variant" && extendsId
      ? `Variant of ${extendsId}`
      : SOURCE_LABEL[source];
  return (
    <Badge variant="secondary" className={cn(className)}>
      {label}
    </Badge>
  );
}

export function AdvancedBanner() {
  return (
    <div
      role="status"
      className="rounded-lg border border-amber-500/40 bg-amber-500/10 px-4 py-3 text-sm text-amber-200"
      data-testid="advanced-banner"
    >
      This metric uses raw SQL and can only be edited as YAML / via push. The structured
      builder is disabled to avoid partial edits that change semantics.
    </div>
  );
}
