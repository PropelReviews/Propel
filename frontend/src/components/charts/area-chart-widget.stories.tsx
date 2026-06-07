import type { Meta, StoryObj } from "@storybook/react-vite";

import { AreaChartWidget } from "./area-chart-widget";
import { formatCount, formatWeekLabel } from "./formatters";

const data = [
  { date: "2026-03-16", value: 12 },
  { date: "2026-03-23", value: 14 },
  { date: "2026-03-30", value: 11 },
  { date: "2026-04-06", value: 18 },
  { date: "2026-04-13", value: 21 },
  { date: "2026-04-20", value: 19 },
  { date: "2026-04-27", value: 24 },
  { date: "2026-05-04", value: 28 },
];

const meta = {
  title: "Charts/AreaChartWidget",
  component: AreaChartWidget,
  decorators: [
    (Story) => (
      <div className="max-w-xl">
        <Story />
      </div>
    ),
  ],
} satisfies Meta<typeof AreaChartWidget>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = {
  args: {
    title: "Deploys",
    description: "Production deploys per week",
    footer: "Last 8 weeks",
    data,
    series: [{ key: "value", label: "Deploys" }],
    xFormatter: formatWeekLabel,
    valueFormatter: formatCount,
  },
};

export const Stacked: Story = {
  args: {
    title: "Deploys by environment",
    data: data.map((d) => ({
      date: d.date,
      staging: d.value,
      production: Math.round(d.value * 0.6),
    })),
    series: [
      { key: "staging", label: "Staging" },
      { key: "production", label: "Production" },
    ],
    xFormatter: formatWeekLabel,
    valueFormatter: formatCount,
  },
};
