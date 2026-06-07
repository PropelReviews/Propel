import type { Meta, StoryObj } from "@storybook/react-vite";

import { formatCount, formatDuration, formatWeekLabel } from "./formatters";
import { LineChartWidget } from "./line-chart-widget";

const data = [
  { date: "2026-03-16", median: 32.4, p90: 58.1 },
  { date: "2026-03-23", median: 29.1, p90: 52.3 },
  { date: "2026-03-30", median: 30.8, p90: 49.7 },
  { date: "2026-04-06", median: 27.5, p90: 44.2 },
  { date: "2026-04-13", median: 25.9, p90: 41.8 },
  { date: "2026-04-20", median: 23.1, p90: 38.4 },
  { date: "2026-04-27", median: 21.8, p90: 35.1 },
  { date: "2026-05-04", median: 19.4, p90: 31.9 },
];

const meta = {
  title: "Charts/LineChartWidget",
  component: LineChartWidget,
  decorators: [
    (Story) => (
      <div className="max-w-xl">
        <Story />
      </div>
    ),
  ],
} satisfies Meta<typeof LineChartWidget>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = {
  args: {
    title: "Cycle time trend",
    description: "Median hours from first commit to merge",
    footer: "Last 8 weeks",
    data,
    series: [{ key: "median", label: "Median hours" }],
    xFormatter: formatWeekLabel,
    valueFormatter: formatDuration,
  },
};

export const MultiSeries: Story = {
  args: {
    title: "Cycle time distribution",
    description: "Median and 90th percentile",
    data,
    series: [
      { key: "median", label: "Median" },
      { key: "p90", label: "P90" },
    ],
    xFormatter: formatWeekLabel,
    valueFormatter: formatDuration,
  },
};

export const Empty: Story = {
  args: {
    title: "Cycle time trend",
    description: "No data for the selected range",
    data: [],
    series: [{ key: "median", label: "Median hours" }],
    emptyMessage: "No cycle time data yet",
  },
};

export const Loading: Story = {
  args: {
    title: "Cycle time trend",
    description: "Loading…",
    data: [],
    series: [{ key: "median", label: "Median hours" }],
    isLoading: true,
  },
};

export const Throughput: Story = {
  args: {
    title: "Throughput",
    description: "Pull requests merged per week",
    data: data.map((d) => ({ date: d.date, value: Math.round(d.median * 2) })),
    series: [{ key: "value", label: "PRs merged" }],
    xFormatter: formatWeekLabel,
    valueFormatter: formatCount,
  },
};
