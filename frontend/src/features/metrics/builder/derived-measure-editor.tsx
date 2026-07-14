import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  getMetricCatalog,
  listMetricDefinitions,
  type MetricCatalogEntity,
  type MetricCatalogItem,
} from "@/features/metrics/api/metric-definitions";
import { FilterBuilder } from "@/features/metrics/builder/filter-builder";
import { tryParseFormula } from "@/features/metrics/builder/formula-parser";

type Operand = {
  ref?: string;
  overrides?: { filters?: unknown[] };
};

/** Derived measure editor (ratio / formula) for M5.4. */
export function DerivedMeasureEditor({
  token,
  tenantId,
  measure,
  onChange,
}: {
  token: string;
  tenantId: string;
  measure: Record<string, unknown>;
  onChange: (next: Record<string, unknown>) => void;
}) {
  const [operands, setOperands] = useState<MetricCatalogItem[]>([]);
  const [entities, setEntities] = useState<MetricCatalogEntity[]>([]);
  const type = String(measure.type ?? "ratio");

  useEffect(() => {
    listMetricDefinitions(token, tenantId, { referencable: true })
      .then(setOperands)
      .catch(() => setOperands([]));
    getMetricCatalog(token, tenantId)
      .then((c) => setEntities(c.entities))
      .catch(() => setEntities([]));
  }, [token, tenantId]);

  if (type === "ratio") {
    const num = (measure.numerator ?? {}) as Operand;
    const den = (measure.denominator ?? {}) as Operand;
    return (
      <div className="space-y-3">
        <OperandCard
          label="Numerator"
          operand={num}
          options={operands}
          entities={entities}
          onChange={(next) =>
            onChange({
              type: "ratio",
              numerator: next,
              denominator: den,
              zero_denominator: measure.zero_denominator ?? null,
            })
          }
        />
        <OperandCard
          label="Denominator"
          operand={den}
          options={operands}
          entities={entities}
          onChange={(next) =>
            onChange({
              type: "ratio",
              numerator: num,
              denominator: next,
              zero_denominator: measure.zero_denominator ?? null,
            })
          }
        />
        <div>
          <Label>When denominator is zero</Label>
          <Select
            value={measure.zero_denominator == null ? "null" : "zero"}
            onValueChange={(v) =>
              onChange({
                ...measure,
                type: "ratio",
                zero_denominator: v === "null" ? null : "zero",
              })
            }
          >
            <SelectTrigger className="mt-1 w-72">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="null">
                Show no data (NULL) — weeks with no activity disappear
              </SelectItem>
              <SelectItem value="zero">Show 0%</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>
    );
  }

  // formula
  const inputs = (measure.inputs ?? {}) as Record<string, Operand>;
  const expression = String(measure.expression ?? "");
  const parse = tryParseFormula(expression || "a");
  const names = Object.keys(inputs);

  return (
    <div className="space-y-3">
      <div className="space-y-3">
        {names.map((name) => (
          <OperandCard
            key={name}
            label={`Input ${name}`}
            operand={inputs[name] ?? {}}
            options={operands}
            entities={entities}
            onChange={(next) =>
              onChange({
                type: "formula",
                inputs: { ...inputs, [name]: next },
                expression,
              })
            }
          />
        ))}
        <Button
          type="button"
          size="sm"
          variant="outline"
          onClick={() => {
            const nextName = String.fromCharCode(97 + names.length);
            onChange({
              type: "formula",
              inputs: { ...inputs, [nextName]: { ref: "" } },
              expression,
            });
          }}
        >
          + input
        </Button>
      </div>
      <div>
        <Label htmlFor="formula-expr">Expression</Label>
        <Input
          id="formula-expr"
          className="mt-1 font-mono"
          value={expression}
          onChange={(e) =>
            onChange({
              type: "formula",
              inputs,
              expression: e.target.value,
            })
          }
        />
        <p
          className={
            parse.ok
              ? "text-muted-foreground mt-1 text-xs"
              : "text-destructive mt-1 text-xs"
          }
        >
          {parse.ok ? "Expression parses." : parse.error}
        </p>
      </div>
    </div>
  );
}

function OperandCard({
  label,
  operand,
  options,
  entities,
  onChange,
}: {
  label: string;
  operand: Operand;
  options: MetricCatalogItem[];
  entities: MetricCatalogEntity[];
  onChange: (next: Operand) => void;
}) {
  const [showOverrides, setShowOverrides] = useState(
    Boolean(operand.overrides?.filters?.length),
  );
  const selected = options.find((o) => o.metric_id === operand.ref);
  const entity = selected?.entity ?? entities[0]?.name ?? "pull_request";

  return (
    <div className="border-border space-y-2 rounded-lg border p-3">
      <div className="flex flex-wrap items-end gap-3">
        <div className="min-w-48 flex-1">
          <Label>{label}</Label>
          <Select
            value={operand.ref ?? ""}
            onValueChange={(ref) => onChange({ ...operand, ref })}
          >
            <SelectTrigger className="mt-1">
              <SelectValue placeholder="Pick a metric" />
            </SelectTrigger>
            <SelectContent>
              {options.map((o) => (
                <SelectItem key={o.metric_id} value={o.metric_id}>
                  {o.name} ({o.metric_id})
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        {selected && (
          <p className="text-muted-foreground text-xs">
            {selected.entity ?? "—"} · {selected.visibility ?? "—"}
          </p>
        )}
      </div>
      <Button
        type="button"
        size="sm"
        variant="ghost"
        onClick={() => setShowOverrides((v) => !v)}
      >
        {showOverrides ? "Hide" : "Additional filters on this side"}
      </Button>
      {showOverrides && (
        <div className="bg-muted/30 space-y-2 rounded-md p-2">
          <p className="text-muted-foreground text-xs">
            Parent / inherited filters stay locked above — additions only narrow.
          </p>
          <FilterBuilder
            entity={entity}
            catalogEntities={entities}
            filters={
              Array.isArray(operand.overrides?.filters)
                ? operand.overrides!.filters!
                : []
            }
            onChange={(filters) =>
              onChange({
                ...operand,
                overrides: { filters },
              })
            }
          />
        </div>
      )}
    </div>
  );
}
