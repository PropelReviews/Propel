/**
 * Corpus round-trip: load propel.* YAML fixtures through the document model
 * and assert normalize(emit(parse(yaml))) === normalize(parse(yaml)).
 *
 * Fixtures are inlined snapshots of shipped configs (kept in sync manually /
 * via CI script later). Advanced/sql configs are excluded.
 */
import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import {
  documentFromYaml,
  documentToYaml,
  normalizeForRoundTrip,
} from "@/features/metrics/document/yaml-io";
import { isAdvancedDocument } from "@/features/metrics/document/advanced";

const CONFIG_DIR = join(
  process.cwd(),
  "..",
  "transformation",
  "propel_metrics",
  "propel_metrics",
  "configs",
  "propel",
);

describe("propel.* corpus round-trip", () => {
  const files = readdirSync(CONFIG_DIR).filter((f) => f.endsWith(".yaml"));

  it("discovers shipped configs", () => {
    expect(files.length).toBeGreaterThan(0);
  });

  for (const file of files) {
    it(`round-trips ${file}`, () => {
      const yamlText = readFileSync(join(CONFIG_DIR, file), "utf8");
      const doc = documentFromYaml(yamlText);
      if (isAdvancedDocument(doc as never)) {
        return;
      }
      const emitted = documentToYaml(doc);
      const again = documentFromYaml(emitted);
      expect(normalizeForRoundTrip(again)).toEqual(normalizeForRoundTrip(doc));
    });
  }
});
