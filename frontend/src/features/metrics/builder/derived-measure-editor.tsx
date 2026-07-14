import { useEffect, useState } from "react";

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
  listMetricDefinitions,
  type MetricCatalogItem,
} from "@/features/metrics/api/metric-definitions";
import { tryParseFormula } from "@/features/metrics/builder/formula-parser";

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
  const type = String(measure.type ?? "ratio");

  useEffect(() => {
    listMetricDefinitions(token, tenantId, { referencable: true })
      .then(setOperands)
      .catch(() => setOperands([]));
  }, [token, tenantId]);

  if (type === "ratio") {
    const num = (measure.numerator ?? {}) as { ref?: string };
    const den = (measure.denominator ?? {}) as { ref?: string };
    return (
      <div className="space-y-3">
        <OperandSelect
          label="Numerator"
          value={num.ref ?? ""}
          options={operands}
          onChange={(ref) =>
            onChange({
              type: "ratio",
              numerator: { ref },
              denominator: den,
              zero_denominator: measure.zero_denominator ?? null,
            })
          }
        />
        <OperandSelect
          label="Denominator"
          value={den.ref ?? ""}
          options={operands}
          onChange={(ref) =>
            onChange({
              type: "ratio",
              numerator: num,
              denominator: { ref },
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
  const inputs = (measure.inputs ?? {}) as Record<string, { ref?: string }>;
  const expression = String(measure.expression ?? "");
  const parse = tryParseFormula(expression || "a");
  const names = Object.keys(inputs);

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-2">
        {names.map((name) => (
          <span
            key={name}
            className="bg-muted inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs"
          >
            <span className="font-mono font-medium">{name}</span>
            <select
              className="bg-background max-w-40 truncate rounded border text-xs"
              value={inputs[name]?.ref ?? ""}
              onChange={(e) => {
                onChange({
                  type: "formula",
                  inputs: {
                    ...inputs,
                    [name]: { ref: e.target.value },
                  },
                  expression,
                });
              }}
              aria-label={`Input ${name}`}
            >
              <option value="">Pick metric…</option>
              {operands.map((o) => (
                <option key={o.metric_id} value={o.metric_id}>
                  {o.name}
                </option>
              ))}
            </select>
          </span>
        ))}
        <button
          type="button"
          className="text-muted-foreground text-xs underline"
          onClick={() => {
            const nextName = String.fromCharCode(97 + names.length); // a, b, c…
            onChange({
              type: "formula",
              inputs: { ...inputs, [nextName]: { ref: "" } },
              expression,
            });
          }}
        >
          + input
        </button>
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

function OperandSelect({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: MetricCatalogItem[];
  onChange: (ref: string) => void;
}) {
  return (
    <div>
      <Label>{label}</Label>
      <Select value={value} onValueChange={onChange}>
        <SelectTrigger className="mt-1">
          <SelectValue placeholder="Pick a metric" />
        </SelectTrigger>
        <SelectContent>
          {options.map((o) => (
            <SelectItem key={o.metric_id} value={o.metric_id}>
              {o.name}{" "}
              <span className="text-muted-foreground font-mono text-xs">
                ({o.metric_id})
              </span>
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}
