import type { Meta, StoryObj } from "@storybook/react-vite";

import { formatCount, formatWeekLabel } from "./formatters";
import { PropelLineChart } from "./propel-line-chart";

const data = [
  { date: "2026-04-06", value: 51 },
  { date: "2026-04-13", value: 47 },
  { date: "2026-04-20", value: 53 },
  { date: "2026-04-27", value: 58 },
  { date: "2026-05-04", value: 61 },
  { date: "2026-05-11", value: 55 },
];

const meta = {
  title: "Charts/PropelLineChart",
  component: PropelLineChart,
  decorators: [
    (Story) => (
      <div className="max-w-md rounded-xl border p-6">
        <Story />
      </div>
    ),
  ],
} satisfies Meta<typeof PropelLineChart>;

export default meta;
type Story = StoryObj<typeof meta>;

export const BarePrimitive: Story = {
  args: {
    data,
    series: [{ key: "value", label: "PRs merged" }],
    xFormatter: formatWeekLabel,
    valueFormatter: formatCount,
    height: 200,
  },
};

export const Empty: Story = {
  args: {
    data: [],
    series: [{ key: "value", label: "PRs merged" }],
    emptyMessage: "No data",
    height: 200,
  },
};

export const Loading: Story = {
  args: {
    data: [],
    series: [{ key: "value", label: "PRs merged" }],
    isLoading: true,
    height: 200,
  },
};
