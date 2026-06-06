import { ChartWidget } from "./chart-widget";
import { PropelAreaChart } from "./propel-area-chart";
import type { ChartPrimitiveProps, ChartWidgetProps } from "./types";

export type AreaChartWidgetProps = ChartWidgetProps & ChartPrimitiveProps;

/** A {@link PropelAreaChart} wrapped in a titled {@link ChartWidget} card. */
export function AreaChartWidget({
  title,
  description,
  footer,
  className,
  ...chartProps
}: AreaChartWidgetProps) {
  return (
    <ChartWidget
      title={title}
      description={description}
      footer={footer}
      className={className}
    >
      <PropelAreaChart {...chartProps} />
    </ChartWidget>
  );
}
