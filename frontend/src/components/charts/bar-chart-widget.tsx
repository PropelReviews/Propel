import { ChartWidget } from "./chart-widget";
import { PropelBarChart } from "./propel-bar-chart";
import type { ChartPrimitiveProps, ChartWidgetProps } from "./types";

export type BarChartWidgetProps = ChartWidgetProps & ChartPrimitiveProps;

/** A {@link PropelBarChart} wrapped in a titled {@link ChartWidget} card. */
export function BarChartWidget({
  title,
  description,
  footer,
  className,
  ...chartProps
}: BarChartWidgetProps) {
  return (
    <ChartWidget
      title={title}
      description={description}
      footer={footer}
      className={className}
    >
      <PropelBarChart {...chartProps} />
    </ChartWidget>
  );
}
