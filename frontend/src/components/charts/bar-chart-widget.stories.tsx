import type { Meta, StoryObj } from "@storybook/react-vite";

import { BarChartWidget } from "./bar-chart-widget";
import { formatCount } from "./formatters";

const data = [
  { category: "Platform", opened: 38, merged: 34 },
  { category: "Growth", opened: 29, merged: 25 },
  { category: "Payments", opened: 22, merged: 21 },
  { category: "Mobile", opened: 31, merged: 27 },
  { category: "Data", opened: 18, merged: 16 },
];

const meta = {
  title: "Charts/BarChartWidget",
  component: BarChartWidget,
  decorators: [
    (Story) => (
      <div className="max-w-xl">
        <Story />
      </div>
    ),
  ],
} satisfies Meta<typeof BarChartWidget>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = {
  args: {
    title: "PR activity by team",
    description: "Opened vs. merged in the current cycle",
    data,
    series: [
      { key: "opened", label: "Opened" },
      { key: "merged", label: "Merged" },
    ],
    xKey: "category",
    valueFormatter: formatCount,
  },
};

export const SingleSeries: Story = {
  args: {
    title: "PRs merged by team",
    data: data.map((d) => ({ category: d.category, merged: d.merged })),
    series: [{ key: "merged", label: "Merged" }],
    xKey: "category",
    valueFormatter: formatCount,
  },
};

export const Empty: Story = {
  args: {
    title: "PR activity by team",
    description: "No activity in the selected range",
    data: [],
    series: [{ key: "merged", label: "Merged" }],
    xKey: "category",
    emptyMessage: "No team activity yet",
  },
};
