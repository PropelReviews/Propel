import type { Meta, StoryObj } from "@storybook/react-vite";

import { MetricCard } from "./metric-card";

const sparkline = [
  { value: 32 },
  { value: 29 },
  { value: 30 },
  { value: 27 },
  { value: 25 },
  { value: 23 },
  { value: 21 },
  { value: 18 },
];

const meta = {
  title: "Charts/MetricCard",
  component: MetricCard,
  decorators: [
    (Story) => (
      <div className="max-w-xs">
        <Story />
      </div>
    ),
  ],
} satisfies Meta<typeof MetricCard>;

export default meta;
type Story = StoryObj<typeof meta>;

export const WithSparkline: Story = {
  args: {
    label: "Median cycle time",
    value: "18.4h",
    delta: -12.3,
    higherIsBetter: false,
    sparklineData: sparkline,
  },
};

export const PositiveDelta: Story = {
  args: {
    label: "PRs merged",
    value: "72",
    delta: 8.1,
    higherIsBetter: true,
  },
};

export const NegativeDelta: Story = {
  args: {
    label: "Review coverage",
    value: "82%",
    delta: -4.5,
    higherIsBetter: true,
  },
};

export const NoDelta: Story = {
  args: {
    label: "Open PRs",
    value: "14",
    description: "Awaiting review",
  },
};
