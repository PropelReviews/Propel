/** Operator compatibility matrix mirrored from propel_metrics.validate.semantic */

export const OPS_BY_TYPE: Record<string, string[]> = {
  string: [
    "eq",
    "neq",
    "in",
    "not_in",
    "contains",
    "not_contains",
    "starts_with",
    "ends_with",
    "is_null",
    "is_not_null",
  ],
  enum: ["eq", "neq", "in", "not_in", "is_null", "is_not_null"],
  integer: [
    "eq",
    "neq",
    "in",
    "not_in",
    "gt",
    "gte",
    "lt",
    "lte",
    "is_null",
    "is_not_null",
  ],
  float: [
    "eq",
    "neq",
    "in",
    "not_in",
    "gt",
    "gte",
    "lt",
    "lte",
    "is_null",
    "is_not_null",
  ],
  boolean: ["eq", "neq", "is_null", "is_not_null"],
  timestamp: ["is_null", "is_not_null"],
  "array<string>": ["contains", "not_contains", "is_null", "is_not_null"],
};

export const NULL_OPS = new Set(["is_null", "is_not_null"]);

export function opsForFieldType(type: string | undefined): string[] {
  if (!type) return OPS_BY_TYPE.string;
  return OPS_BY_TYPE[type] ?? OPS_BY_TYPE.string;
}
