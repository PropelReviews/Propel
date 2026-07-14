import type { Meta, StoryObj } from "@storybook/react-vite";

import { FilterBuilder } from "@/features/metrics/builder/filter-builder";
import {
  StatusChip,
  VisibilityBadge,
  SourceBadge,
  AdvancedBanner,
} from "@/features/metrics/components/metric-badges";
import { useState } from "react";

const ENTITIES = [
  {
    name: "pull_request",
    grain: "one row per PR",
    dbt_model: "pull_request",
    fields: [
      {
        name: "state",
        type: "enum",
        role: "dimension",
        values: ["open", "merged", "closed"],
        nullable: null,
        cardinality_estimate: 3,
        person: false,
        virtual: false,
        mapping_id: null,
      },
      {
        name: "repo",
        type: "string",
        role: "dimension",
        values: null,
        nullable: null,
        cardinality_estimate: 200,
        person: false,
        virtual: false,
        mapping_id: null,
      },
      {
        name: "author_id",
        type: "string",
        role: "dimension",
        values: null,
        nullable: null,
        cardinality_estimate: 2000,
        person: true,
        virtual: false,
        mapping_id: null,
      },
    ],
  },
];

function FilterDemo() {
  const [filters, setFilters] = useState<unknown[]>([
    { field: "state", op: "eq", value: "merged" },
  ]);
  return (
    <FilterBuilder
      entity="pull_request"
      catalogEntities={ENTITIES}
      filters={filters}
      onChange={setFilters}
    />
  );
}

const meta = {
  title: "Metrics/Builder",
  parameters: { layout: "padded" },
} satisfies Meta;

export default meta;

type Story = StoryObj;

export const FilterBuilderDefault: Story = {
  render: () => <FilterDemo />,
};

export const Badges: Story = {
  render: () => (
    <div className="flex flex-wrap gap-2">
      <StatusChip status="active" />
      <StatusChip status="active" draftPending />
      <StatusChip status="broken" />
      <VisibilityBadge visibility="ic" />
      <SourceBadge source="standard_customized" />
      <SourceBadge source="variant" extendsId="propel.merged_prs" />
    </div>
  ),
};

export const AdvancedReadOnly: Story = {
  render: () => <AdvancedBanner />,
};
