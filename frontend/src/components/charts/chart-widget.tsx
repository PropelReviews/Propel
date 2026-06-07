import type { ReactNode } from "react";

import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { cn } from "@/lib/utils";

import type { ChartWidgetProps } from "./types";

/**
 * Titled card shell for a chart. Wrap any chart primitive to get a consistent
 * header, optional description, and footer:
 *
 * ```tsx
 * <ChartWidget title="Cycle time" description="Median hours to merge">
 *   <PropelLineChart data={...} series={...} />
 * </ChartWidget>
 * ```
 */
export function ChartWidget({
  title,
  description,
  footer,
  className,
  children,
}: ChartWidgetProps & { children: ReactNode }) {
  return (
    <Card data-slot="chart-widget" className={cn("gap-0", className)}>
      <CardHeader className="pb-4">
        <CardTitle>{title}</CardTitle>
        {description ? <CardDescription>{description}</CardDescription> : null}
      </CardHeader>
      <CardContent>{children}</CardContent>
      {footer ? (
        <CardFooter className="text-muted-foreground mt-4 text-xs">
          {footer}
        </CardFooter>
      ) : null}
    </Card>
  );
}
