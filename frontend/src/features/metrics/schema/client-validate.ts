/**
 * Tier-1 client validation: JSON Schema (ajv) + cheap semantic mirrors.
 * Server :validate always wins on disagreement.
 */

import Ajv2020, { type ErrorObject } from "ajv/dist/2020.js";
import addFormats from "ajv-formats";

import metricSchema from "@/features/metrics/schema/generated/metric.schema.json";
import { opsForFieldType, NULL_OPS } from "@/features/metrics/catalogue/operators";

export type ClientValidationIssue = {
  code: string;
  path: string;
  message: string;
  source: "schema" | "semantic";
};

const ajv = new Ajv2020({
  allErrors: true,
  strict: false,
  validateSchema: false,
});
addFormats(ajv);

const validateMetric = ajv.compile(metricSchema as object);

function schemaPath(err: ErrorObject): string {
  const base = err.instancePath || "";
  if (err.params && typeof err.params === "object" && "missingProperty" in err.params) {
    const missing = String((err.params as { missingProperty: string }).missingProperty);
    return (
      `${base}/${missing}`
        .replace(/\/+/g, ".")
        .replace(/^\./, "$.")
        .replace(/\//g, ".") || "$"
    );
  }
  return (base || "$").replace(/\//g, ".") || "$";
}

/** Map common JSON paths to builder section ids for inline surfacing. */
export const pathToField: Record<string, string> = {
  "$.metadata.name": "basics.name",
  "$.metadata.id": "basics.id",
  "$.metadata.description": "basics.description",
  "$.spec.entity": "data.entity",
  "$.spec.measure": "data.measure",
  "$.spec.filters": "filters",
  "$.spec.time": "time",
  "$.spec.dimensions": "dimensions",
  "$.spec.visibility": "visibility",
  "$.spec.display": "display",
};

export function fieldForPath(path: string): string | null {
  if (pathToField[path]) return pathToField[path];
  for (const [prefix, field] of Object.entries(pathToField)) {
    if (path.startsWith(prefix)) return field;
  }
  if (path.startsWith("$.spec.filters")) return "filters";
  if (path.startsWith("$.spec.measure")) return "data.measure";
  return null;
}

export function validateMetricDocument(
  doc: Record<string, unknown>,
  catalog?: {
    entities: Array<{
      name: string;
      fields: Array<{ name: string; type: string; role: string }>;
    }>;
  },
): ClientValidationIssue[] {
  const issues: ClientValidationIssue[] = [];
  const ok = validateMetric(doc);
  if (!ok && validateMetric.errors) {
    for (const err of validateMetric.errors) {
      issues.push({
        code: "E_SCHEMA",
        path: schemaPath(err),
        message: err.message ?? "schema validation failed",
        source: "schema",
      });
    }
  }

  // Cheap semantic mirrors (must never contradict server — only false-negative OK).
  const spec = (doc.spec ?? {}) as Record<string, unknown>;
  const entity = String(spec.entity ?? "");
  const filters = Array.isArray(spec.filters) ? spec.filters : [];
  if (catalog && entity) {
    const ent = catalog.entities.find((e) => e.name === entity);
    const fieldType = (name: string) => ent?.fields.find((f) => f.name === name)?.type;

    const walk = (node: unknown, path: string, depth: number) => {
      if (depth > 3) {
        issues.push({
          code: "E_FILTER_DEPTH",
          path,
          message: "filter nesting exceeds max depth 3",
          source: "semantic",
        });
        return;
      }
      if (!node || typeof node !== "object") return;
      const obj = node as Record<string, unknown>;
      if ("any_of" in obj && Array.isArray(obj.any_of)) {
        obj.any_of.forEach((c, i) => walk(c, `${path}.any_of[${i}]`, depth + 1));
        return;
      }
      if ("all_of" in obj && Array.isArray(obj.all_of)) {
        obj.all_of.forEach((c, i) => walk(c, `${path}.all_of[${i}]`, depth + 1));
        return;
      }
      if ("not" in obj) {
        walk(obj.not, `${path}.not`, depth + 1);
        return;
      }
      if ("sql" in obj) return;
      if ("field" in obj && "op" in obj) {
        const f = String(obj.field);
        const op = String(obj.op);
        const t = fieldType(f);
        if (t) {
          const allowed = opsForFieldType(t);
          if (!allowed.includes(op)) {
            issues.push({
              code: "E_OP_TYPE",
              path,
              message: `op ${op} incompatible with field type ${t}`,
              source: "semantic",
            });
          }
        }
        if (!NULL_OPS.has(op) && !("value" in obj)) {
          issues.push({
            code: "E_VALUE_TYPE",
            path,
            message: `op ${op} requires a value`,
            source: "semantic",
          });
        }
      }
    };
    filters.forEach((f, i) => walk(f, `$.spec.filters[${i}]`, 1));
  }

  return issues;
}
