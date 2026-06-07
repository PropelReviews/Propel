import { ChartWidget } from "./chart-widget";
import { PropelLineChart } from "./propel-line-chart";
import type { ChartPrimitiveProps, ChartWidgetProps } from "./types";

export type LineChartWidgetProps = ChartWidgetProps & ChartPrimitiveProps;

/** A {@link PropelLineChart} wrapped in a titled {@link ChartWidget} card. */
export function LineChartWidget({
  title,
  description,
  footer,
  className,
  ...chartProps
}: LineChartWidgetProps) {
  return (
    <ChartWidget
      title={title}
      description={description}
      footer={footer}
      className={className}
    >
      <PropelLineChart {...chartProps} />
    </ChartWidget>
  );
}
