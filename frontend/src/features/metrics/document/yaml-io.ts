import { parse as parseYaml, stringify as stringifyYaml } from "yaml";

import { canonicalize } from "@/features/metrics/document/store";

export function documentFromYaml(yamlText: string): Record<string, unknown> {
  const doc = parseYaml(yamlText);
  if (!doc || typeof doc !== "object" || Array.isArray(doc)) {
    throw new Error("YAML root must be a mapping");
  }
  return doc as Record<string, unknown>;
}

export function documentToYaml(doc: Record<string, unknown>): string {
  return stringifyYaml(doc, { lineWidth: 100 });
}

/** Normalize for round-trip compare (drop store-owned metadata noise). */
export function normalizeForRoundTrip(
  doc: Record<string, unknown>,
): Record<string, unknown> {
  const copy = structuredClone(doc);
  const meta = (copy.metadata ?? {}) as Record<string, unknown>;
  delete meta.version;
  delete meta.status;
  copy.metadata = meta;
  return canonicalize(copy) as Record<string, unknown>;
}
