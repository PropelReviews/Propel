/**
 * Document store: JSON-path patches over a Metric document.
 * Single source of truth for the builder (M5 principle #1).
 */

export type JsonPath = Array<string | number>;

export type DocumentPatch =
  | { op: "set"; path: JsonPath; value: unknown }
  | { op: "remove"; path: JsonPath }
  | { op: "replace_root"; value: Record<string, unknown> };

export type DocumentState = {
  doc: Record<string, unknown>;
  past: Record<string, unknown>[];
  future: Record<string, unknown>[];
};

function clone<T>(value: T): T {
  return structuredClone(value);
}

function getAt(root: unknown, path: JsonPath): unknown {
  let cur: unknown = root;
  for (const key of path) {
    if (cur == null || typeof cur !== "object") return undefined;
    cur = (cur as Record<string | number, unknown>)[key as never];
  }
  return cur;
}

function setAt(
  root: Record<string, unknown>,
  path: JsonPath,
  value: unknown,
): Record<string, unknown> {
  if (path.length === 0) {
    if (value && typeof value === "object" && !Array.isArray(value)) {
      return clone(value as Record<string, unknown>);
    }
    throw new Error("replace_root required for non-object root");
  }
  const out = clone(root);
  let cur: Record<string | number, unknown> = out;
  for (let i = 0; i < path.length - 1; i++) {
    const key = path[i]!;
    const next = cur[key as never];
    if (next == null || typeof next !== "object") {
      const nextKey = path[i + 1];
      cur[key as never] = typeof nextKey === "number" ? [] : {};
    } else {
      cur[key as never] = clone(next as object);
    }
    cur = cur[key as never] as Record<string | number, unknown>;
  }
  const last = path[path.length - 1]!;
  cur[last as never] = value;
  return out;
}

function removeAt(
  root: Record<string, unknown>,
  path: JsonPath,
): Record<string, unknown> {
  if (path.length === 0) return {};
  const out = clone(root);
  let cur: Record<string | number, unknown> = out;
  for (let i = 0; i < path.length - 1; i++) {
    const key = path[i]!;
    const next = cur[key as never];
    if (next == null || typeof next !== "object") return out;
    cur[key as never] = clone(next as object);
    cur = cur[key as never] as Record<string | number, unknown>;
  }
  const last = path[path.length - 1]!;
  if (Array.isArray(cur)) {
    cur.splice(Number(last), 1);
  } else {
    delete cur[last as never];
  }
  return out;
}

export function applyPatch(
  doc: Record<string, unknown>,
  patch: DocumentPatch,
): Record<string, unknown> {
  if (patch.op === "replace_root") return clone(patch.value);
  if (patch.op === "set") return setAt(doc, patch.path, patch.value);
  return removeAt(doc, patch.path);
}

export type DocumentAction =
  | { type: "patch"; patch: DocumentPatch }
  | { type: "undo" }
  | { type: "redo" }
  | { type: "load"; doc: Record<string, unknown> };

export function createDocumentState(
  doc: Record<string, unknown> = emptyMetricDocument("org.metric"),
): DocumentState {
  return { doc: clone(doc), past: [], future: [] };
}

export function documentReducer(
  state: DocumentState,
  action: DocumentAction,
): DocumentState {
  switch (action.type) {
    case "load":
      return { doc: clone(action.doc), past: [], future: [] };
    case "patch": {
      const next = applyPatch(state.doc, action.patch);
      return {
        doc: next,
        past: [...state.past, state.doc].slice(-100),
        future: [],
      };
    }
    case "undo": {
      if (state.past.length === 0) return state;
      const previous = state.past[state.past.length - 1]!;
      return {
        doc: previous,
        past: state.past.slice(0, -1),
        future: [state.doc, ...state.future],
      };
    }
    case "redo": {
      if (state.future.length === 0) return state;
      const [next, ...rest] = state.future;
      return {
        doc: next!,
        past: [...state.past, state.doc],
        future: rest,
      };
    }
    default:
      return state;
  }
}

export function emptyMetricDocument(
  metricId: string,
  name = "New metric",
): Record<string, unknown> {
  return {
    apiVersion: "propel/v1",
    kind: "Metric",
    metadata: {
      id: metricId,
      name,
      description: "",
      tags: [],
      status: "draft",
      version: 1,
    },
    spec: {
      entity: "pull_request",
      measure: { type: "count" },
      filters: [],
      time: { field: "merged_at", grains: ["week"] },
      dimensions: [],
      display: {
        unit: "count",
        format: "integer",
        direction: "neutral",
      },
      visibility: "team",
    },
  };
}

export function getPath(doc: Record<string, unknown>, path: JsonPath): unknown {
  return getAt(doc, path);
}

/** Canonical JSON for round-trip equality (sorted object keys). */
export function canonicalize(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(canonicalize);
  if (value && typeof value === "object") {
    const out: Record<string, unknown> = {};
    for (const key of Object.keys(value as object).sort()) {
      out[key] = canonicalize((value as Record<string, unknown>)[key]);
    }
    return out;
  }
  return value;
}
