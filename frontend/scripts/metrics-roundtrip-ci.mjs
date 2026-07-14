#!/usr/bin/env node
/**
 * CI: round-trip every non-advanced propel.* YAML through the UI emit pipeline.
 */
import { readdirSync, readFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";

const __dirname = dirname(fileURLToPath(import.meta.url));
const configs = join(
  __dirname,
  "../../transformation/propel_metrics/propel_metrics/configs/propel",
);
const emit = join(__dirname, "emit-roundtrip.mjs");

function isAdvanced(yamlText) {
  return (
    /^\s*advanced:\s*true\s*$/m.test(yamlText) ||
    /type:\s*sql\b/.test(yamlText) ||
    /\bsql:\s*[|>]/.test(yamlText)
  );
}

let failures = 0;
let checked = 0;
for (const file of readdirSync(configs).filter((f) => f.endsWith(".yaml"))) {
  const path = join(configs, file);
  const text = readFileSync(path, "utf8");
  if (isAdvanced(text)) {
    console.log("skip advanced", file);
    continue;
  }
  checked += 1;
  const proc = spawnSync(process.execPath, [emit, path], { encoding: "utf8" });
  if (proc.status !== 0) {
    console.error("FAIL", file, proc.stderr);
    failures += 1;
  } else {
    console.log("ok", file);
  }
}
console.log(`checked=${checked} failures=${failures}`);
process.exit(failures ? 1 : 0);
