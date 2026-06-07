import type { Meta, StoryObj } from "@storybook/react-vite";
import { useState } from "react";

import { RelativeRangePicker } from "./relative-range-picker";
import type { RelativeRange } from "./types";

function Controlled() {
  const [range, setRange] = useState<RelativeRange>("quarter");
  return (
    <div className="flex flex-col gap-3">
      <RelativeRangePicker value={range} onValueChange={setRange} />
      <p className="text-muted-foreground text-sm">
        Selected: <code>{range}</code>
      </p>
    </div>
  );
}

const meta = {
  title: "Charts/Filters/RelativeRangePicker",
  component: Controlled,
} satisfies Meta<typeof Controlled>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = {};
