import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { MetricCatalogEntity } from "@/features/metrics/api/metric-definitions";
import { summarizeFilters } from "@/features/metrics/builder/filter-summary";
import { NULL_OPS, opsForFieldType } from "@/features/metrics/catalogue/operators";

type Predicate = { field: string; op: string; value?: unknown };

export function FilterBuilder({
  entity,
  catalogEntities,
  filters,
  onChange,
  depth = 0,
}: {
  entity: string;
  catalogEntities: MetricCatalogEntity[];
  filters: unknown[];
  onChange: (next: unknown[]) => void;
  depth?: number;
}) {
  const ent = catalogEntities.find((e) => e.name === entity);
  const dimFields = (ent?.fields ?? []).filter(
    (f) => f.role === "dimension" || f.role === "event_time",
  );

  function updateAt(index: number, next: Predicate) {
    const copy = [...filters];
    copy[index] = next;
    onChange(copy);
  }

  function removeAt(index: number) {
    onChange(filters.filter((_, i) => i !== index));
  }

  function addPredicate() {
    const field = dimFields[0]?.name ?? "repo";
    onChange([...filters, { field, op: "eq", value: "" }]);
  }

  function addGroup() {
    if (depth >= 2) return;
    onChange([
      ...filters,
      { any_of: [{ field: dimFields[0]?.name ?? "repo", op: "eq", value: "" }] },
    ]);
  }

  return (
    <div className="space-y-3">
      {filters.map((raw, index) => {
        if (raw && typeof raw === "object" && ("any_of" in raw || "all_of" in raw)) {
          const group = raw as { any_of?: unknown[]; all_of?: unknown[] };
          const mode = group.any_of ? "any_of" : "all_of";
          const children = (group.any_of ?? group.all_of ?? []) as unknown[];
          return (
            <div key={index} className="border-border space-y-2 rounded-lg border p-3">
              <div className="flex items-center gap-2">
                <Select
                  value={mode}
                  onValueChange={(v) => {
                    const copy = [...filters];
                    copy[index] =
                      v === "any_of" ? { any_of: children } : { all_of: children };
                    onChange(copy);
                  }}
                >
                  <SelectTrigger className="w-28" aria-label="Group combinator">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all_of">AND</SelectItem>
                    <SelectItem value="any_of">OR</SelectItem>
                  </SelectContent>
                </Select>
                <Button size="sm" variant="ghost" onClick={() => removeAt(index)}>
                  Remove group
                </Button>
              </div>
              <FilterBuilder
                entity={entity}
                catalogEntities={catalogEntities}
                filters={children}
                depth={depth + 1}
                onChange={(next) => {
                  const copy = [...filters];
                  copy[index] = mode === "any_of" ? { any_of: next } : { all_of: next };
                  onChange(copy);
                }}
              />
            </div>
          );
        }

        const pred = (raw ?? {}) as Predicate;
        const fieldMeta = dimFields.find((f) => f.name === pred.field);
        const ops = opsForFieldType(fieldMeta?.type);
        const needsValue = !NULL_OPS.has(pred.op);

        return (
          <div
            key={index}
            className="flex flex-wrap items-center gap-2"
            data-testid="filter-row"
          >
            <Select
              value={pred.field}
              onValueChange={(field) =>
                updateAt(index, { ...pred, field, op: "eq", value: "" })
              }
            >
              <SelectTrigger className="w-40" aria-label="Filter field">
                <SelectValue placeholder="Field" />
              </SelectTrigger>
              <SelectContent>
                {dimFields.map((f) => (
                  <SelectItem key={f.name} value={f.name}>
                    {f.name}
                    {f.virtual ? " (mapped)" : ""}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select
              value={pred.op}
              onValueChange={(op) =>
                updateAt(index, {
                  ...pred,
                  op,
                  value: NULL_OPS.has(op) ? undefined : pred.value,
                })
              }
            >
              <SelectTrigger className="w-36" aria-label="Filter operator">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {ops.map((op) => (
                  <SelectItem key={op} value={op}>
                    {op}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {needsValue && fieldMeta?.type === "enum" && fieldMeta.values ? (
              <Select
                value={String(pred.value ?? "")}
                onValueChange={(value) => updateAt(index, { ...pred, value })}
              >
                <SelectTrigger className="w-40" aria-label="Filter value">
                  <SelectValue placeholder="Value" />
                </SelectTrigger>
                <SelectContent>
                  {fieldMeta.values.map((v) => (
                    <SelectItem key={v} value={v}>
                      {v}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            ) : needsValue && fieldMeta?.type === "boolean" ? (
              <Select
                value={String(pred.value ?? "true")}
                onValueChange={(value) =>
                  updateAt(index, { ...pred, value: value === "true" })
                }
              >
                <SelectTrigger className="w-28" aria-label="Boolean value">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="true">true</SelectItem>
                  <SelectItem value="false">false</SelectItem>
                </SelectContent>
              </Select>
            ) : needsValue ? (
              <Input
                className="w-40"
                value={String(pred.value ?? "")}
                onChange={(e) => updateAt(index, { ...pred, value: e.target.value })}
                aria-label="Filter value"
              />
            ) : null}
            <Button size="sm" variant="ghost" onClick={() => removeAt(index)}>
              Remove
            </Button>
          </div>
        );
      })}

      <div className="flex flex-wrap gap-2">
        <Button size="sm" variant="outline" onClick={addPredicate}>
          + Add condition
        </Button>
        {depth < 2 ? (
          <Button size="sm" variant="outline" onClick={addGroup}>
            + Add condition group
          </Button>
        ) : (
          <span className="text-muted-foreground text-xs">
            Max nesting reached — consider a variant or a mapping
          </span>
        )}
      </div>
      <p className="text-muted-foreground text-sm italic" data-testid="filter-summary">
        {summarizeFilters(filters)}
      </p>
    </div>
  );
}
