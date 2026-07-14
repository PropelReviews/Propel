/** English summary for filter trees (catalog tooltips + builder readback). */

export type FilterNode =
  | { field: string; op: string; value?: unknown }
  | { any_of: FilterNode[] }
  | { all_of: FilterNode[] }
  | { not: FilterNode }
  | { sql: string };

function fmtValue(value: unknown): string {
  if (Array.isArray(value)) return value.map(fmtValue).join(", ");
  if (typeof value === "string") return `\`${value}\``;
  if (value === null || value === undefined) return "null";
  return String(value);
}

function summarizeNode(node: FilterNode): string {
  if ("sql" in node) return `(raw SQL)`;
  if ("not" in node) return `not (${summarizeNode(node.not)})`;
  if ("any_of" in node) {
    return node.any_of.map(summarizeNode).join(" or ");
  }
  if ("all_of" in node) {
    return node.all_of.map(summarizeNode).join(" and ");
  }
  const { field, op, value } = node;
  switch (op) {
    case "eq":
      return `${field} = ${fmtValue(value)}`;
    case "neq":
      return `${field} ≠ ${fmtValue(value)}`;
    case "in":
      return `${field} in [${fmtValue(value)}]`;
    case "not_in":
      return `${field} not in [${fmtValue(value)}]`;
    case "contains":
      return `${field} contains ${fmtValue(value)}`;
    case "not_contains":
      return `${field} does not contain ${fmtValue(value)}`;
    case "starts_with":
      return `${field} starts with ${fmtValue(value)}`;
    case "ends_with":
      return `${field} ends with ${fmtValue(value)}`;
    case "gt":
      return `${field} > ${fmtValue(value)}`;
    case "gte":
      return `${field} ≥ ${fmtValue(value)}`;
    case "lt":
      return `${field} < ${fmtValue(value)}`;
    case "lte":
      return `${field} ≤ ${fmtValue(value)}`;
    case "is_null":
      return `${field} is null`;
    case "is_not_null":
      return `${field} is not null`;
    default:
      return `${field} ${op} ${fmtValue(value)}`;
  }
}

export function summarizeFilters(filters: unknown): string {
  if (!Array.isArray(filters) || filters.length === 0) {
    return "No filters";
  }
  try {
    return filters.map((f) => summarizeNode(f as FilterNode)).join(" and ");
  } catch {
    return "Filters (unreadable)";
  }
}
