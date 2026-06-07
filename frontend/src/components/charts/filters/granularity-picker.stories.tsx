import type { Meta, StoryObj } from "@storybook/react-vite";
import { useState } from "react";

import { GranularityPicker } from "./granularity-picker";
import type { Granularity } from "./types";

function Controlled() {
  const [granularity, setGranularity] = useState<Granularity>("weekly");
  return (
    <div className="flex flex-col gap-3">
      <GranularityPicker value={granularity} onValueChange={setGranularity} />
      <p className="text-muted-foreground text-sm">
        Selected: <code>{granularity}</code>
      </p>
    </div>
  );
}

function Restricted() {
  const [granularity, setGranularity] = useState<Granularity>("daily");
  return (
    <GranularityPicker
      value={granularity}
      onValueChange={setGranularity}
      options={["daily", "weekly"]}
    />
  );
}

const meta = {
  title: "Charts/Filters/GranularityPicker",
  component: Controlled,
} satisfies Meta<typeof Controlled>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = {};

export const RestrictedOptions: Story = {
  render: () => <Restricted />,
};
