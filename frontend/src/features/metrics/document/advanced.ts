/** Detect advanced / raw-SQL documents that must render read-only. */
export function isAdvancedDocument(doc: {
  metadata?: { advanced?: boolean };
  spec?: {
    measure?: { type?: string; sql?: string };
    filters?: unknown[];
  };
}): boolean {
  if (doc.metadata?.advanced) return true;
  if (doc.spec?.measure?.type === "sql") return true;
  if (typeof doc.spec?.measure?.sql === "string") return true;
  return filtersContainSql(doc.spec?.filters);
}

function filtersContainSql(filters: unknown): boolean {
  if (!Array.isArray(filters)) {
    if (filters && typeof filters === "object" && "sql" in filters) return true;
    if (filters && typeof filters === "object") {
      const obj = filters as Record<string, unknown>;
      if ("any_of" in obj) return filtersContainSql(obj.any_of);
      if ("all_of" in obj) return filtersContainSql(obj.all_of);
      if ("not" in obj) return filtersContainSql(obj.not);
    }
    return false;
  }
  return filters.some((f) => filtersContainSql(f));
}

export function parseYamlLoose(yamlText: string): Record<string, unknown> | null {
  // Lightweight scan for advanced/sql markers when full YAML parse isn't needed.
  try {
    if (/^\s*advanced:\s*true\s*$/m.test(yamlText))
      return { metadata: { advanced: true } };
    if (/type:\s*sql\b/.test(yamlText) || /\bsql:\s*[|>]/.test(yamlText)) {
      return { metadata: {}, spec: { measure: { type: "sql" } } };
    }
    return {};
  } catch {
    return null;
  }
}
