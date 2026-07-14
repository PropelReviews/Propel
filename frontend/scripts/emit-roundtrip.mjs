#!/usr/bin/env node
/**
 * Emit canonical JSON for a metric YAML file (same normalize pipeline as the UI).
 * Usage: node frontend/scripts/emit-roundtrip.mjs <path-to.yaml>
 */
import { readFileSync } from "node:fs";
import { parse as parseYaml, stringify as stringifyYaml } from "yaml";

function canonicalize(value) {
  if (Array.isArray(value)) return value.map(canonicalize);
  if (value && typeof value === "object") {
    const out = {};
    for (const key of Object.keys(value).sort()) {
      out[key] = canonicalize(value[key]);
    }
    return out;
  }
  return value;
}

function normalizeForRoundTrip(doc) {
  const copy = structuredClone(doc);
  const meta = { ...(copy.metadata ?? {}) };
  delete meta.version;
  delete meta.status;
  copy.metadata = meta;
  return canonicalize(copy);
}

const path = process.argv[2];
if (!path) {
  console.error("usage: emit-roundtrip.mjs <yaml>");
  process.exit(2);
}
const yamlText = readFileSync(path, "utf8");
const doc = parseYaml(yamlText);
if (!doc || typeof doc !== "object") {
  console.error("invalid yaml root");
  process.exit(1);
}
const emitted = stringifyYaml(doc, { lineWidth: 100 });
const again = parseYaml(emitted);
const a = JSON.stringify(normalizeForRoundTrip(doc));
const b = JSON.stringify(normalizeForRoundTrip(again));
if (a !== b) {
  console.error("ROUNDTRIP_MISMATCH", path);
  process.exit(1);
}
process.stdout.write(a);
