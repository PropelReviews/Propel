import { useCallback, useEffect, useMemo, useReducer, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { parse as parseYaml } from "yaml";

import { Button } from "@/components/ui/button";
import { CodeBlock } from "@/components/ui/code-block";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/providers/auth-provider";
import { useTenant } from "@/providers/tenant-provider";
import {
  activateMetricDefinition,
  classifyMetricDefinition,
  createMetricDefinition,
  getMetricCatalog,
  getMetricDefinition,
  putMetricDefinitionDraft,
  validateMetricDefinition,
  type MetricCatalogResponse,
} from "@/features/metrics/api/metric-definitions";
import { FilterBuilder } from "@/features/metrics/builder/filter-builder";
import { DerivedMeasureEditor } from "@/features/metrics/builder/derived-measure-editor";
import { AdvancedBanner } from "@/features/metrics/components/metric-badges";
import { ForkPrompt } from "@/features/metrics/catalog/customize-params-dialog";
import { isAdvancedDocument } from "@/features/metrics/document/advanced";
import {
  createDocumentState,
  documentReducer,
  emptyMetricDocument,
} from "@/features/metrics/document/store";
import { documentToYaml } from "@/features/metrics/document/yaml-io";
import { PreviewPanel } from "@/features/metrics/preview/preview-panel";

const MEASURE_TYPES = [
  "count",
  "count_distinct",
  "sum",
  "avg",
  "min",
  "max",
  "percentile",
  "interval",
  "ratio",
  "formula",
] as const;

const GRAINS = ["day", "week", "month", "quarter"] as const;

export function MetricBuilderPage({ mode }: { mode: "create" | "edit" }) {
  const { metricId: rawId } = useParams<{ metricId: string }>();
  const metricIdParam = rawId ? decodeURIComponent(rawId) : null;
  const [searchParams] = useSearchParams();
  const extendsParent = searchParams.get("extends");
  const presetId = searchParams.get("id");
  const { token } = useAuth();
  const { tenant } = useTenant();
  const navigate = useNavigate();

  const [state, dispatch] = useReducer(documentReducer, undefined, () =>
    createDocumentState(
      emptyMetricDocument(tenant ? `${tenant.slug}.new_metric` : "org.new_metric"),
    ),
  );
  const [catalog, setCatalog] = useState<MetricCatalogResponse | null>(null);
  const [yamlMode, setYamlMode] = useState(false);
  const [yamlText, setYamlText] = useState("");
  const [yamlError, setYamlError] = useState<string | null>(null);
  const [storeVersion, setStoreVersion] = useState<number | null>(null);
  const [storeRevision, setStoreRevision] = useState<number | null>(null);
  const [saveState, setSaveState] = useState<string>("");
  const [validateErrors, setValidateErrors] = useState<
    Array<{ code?: string; path?: string; message?: string }>
  >([]);
  const [activateMsg, setActivateMsg] = useState<string | null>(null);
  const [loading, setLoading] = useState(mode === "edit");
  const [loadError, setLoadError] = useState<string | null>(null);

  const doc = state.doc;
  const meta = (doc.metadata ?? {}) as Record<string, unknown>;
  const spec = (doc.spec ?? {}) as Record<string, unknown>;
  const measure = (spec.measure ?? {}) as Record<string, unknown>;
  const time = (spec.time ?? {}) as Record<string, unknown>;
  const advanced = isAdvancedDocument(doc as never);

  useEffect(() => {
    if (!token || !tenant) return;
    getMetricCatalog(token, tenant.id)
      .then(setCatalog)
      .catch(() => setCatalog(null));
  }, [token, tenant]);

  useEffect(() => {
    if (mode !== "edit" || !token || !tenant || !metricIdParam) return;
    let cancelled = false;
    setLoading(true);
    getMetricDefinition(token, tenant.id, metricIdParam)
      .then((detail) => {
        if (cancelled) return;
        const parsed = parseYaml(detail.yaml);
        if (parsed && typeof parsed === "object") {
          dispatch({
            type: "load",
            doc: parsed as Record<string, unknown>,
          });
        }
        setStoreVersion(detail.version);
        setStoreRevision(detail.revision);
        setLoading(false);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setLoadError(err instanceof ApiError ? err.message : "Failed to load");
        setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [mode, token, tenant, metricIdParam]);

  // Prefill variant from ?extends=
  useEffect(() => {
    if (mode !== "create" || !extendsParent || !tenant) return;
    const id =
      presetId ??
      `${tenant.slug}.${extendsParent.split(".").slice(1).join("_")}_variant`;
    dispatch({
      type: "load",
      doc: {
        apiVersion: "propel/v1",
        kind: "Metric",
        metadata: {
          id,
          name: `Variant of ${extendsParent}`,
          description: "",
          tags: [],
          status: "draft",
          version: 1,
        },
        spec: {
          extends: extendsParent,
          overrides: {
            filters: [],
          },
          visibility: "team",
        },
      },
    });
  }, [mode, extendsParent, presetId, tenant]);

  // Create mode: bind tenant slug into id once
  useEffect(() => {
    if (mode !== "create" || !tenant || extendsParent) return;
    const id = String(meta.id ?? "");
    if (!id.startsWith(`${tenant.slug}.`)) {
      dispatch({
        type: "patch",
        patch: {
          op: "set",
          path: ["metadata", "id"],
          value: `${tenant.slug}.new_metric`,
        },
      });
    }
  }, [mode, tenant, extendsParent]); // eslint-disable-line react-hooks/exhaustive-deps

  const setMeta = (key: string, value: unknown) =>
    dispatch({ type: "patch", patch: { op: "set", path: ["metadata", key], value } });
  const setSpec = (key: string, value: unknown) =>
    dispatch({ type: "patch", patch: { op: "set", path: ["spec", key], value } });

  const runValidate = useCallback(async () => {
    if (!token || !tenant) return;
    try {
      const res = await validateMetricDefinition(token, tenant.id, documentToYaml(doc));
      setValidateErrors(
        (res.errors as Array<{ code?: string; path?: string; message?: string }>) ?? [],
      );
    } catch {
      /* ignore transient */
    }
  }, [token, tenant, doc]);

  useEffect(() => {
    if (advanced || yamlMode) return;
    const t = window.setTimeout(() => void runValidate(), 500);
    return () => window.clearTimeout(t);
  }, [doc, advanced, yamlMode, runValidate]);

  const autosave = useCallback(async () => {
    if (!token || !tenant || advanced) return;
    const yaml = documentToYaml(doc);
    setSaveState("Saving…");
    try {
      if (storeVersion == null) {
        const created = await createMetricDefinition(token, tenant.id, yaml);
        setStoreVersion(created.version);
        setStoreRevision(created.revision);
      } else {
        const updated = await putMetricDefinitionDraft(token, tenant.id, {
          yaml,
          expected_version: storeVersion,
          expected_revision: storeRevision,
        });
        setStoreVersion(updated.version);
        setStoreRevision(updated.revision);
      }
      setSaveState("Saved draft");
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setSaveState("Conflict — reload the metric and try again");
      } else {
        setSaveState(err instanceof ApiError ? err.message : "Save failed");
      }
    }
  }, [token, tenant, doc, advanced, storeVersion, storeRevision]);

  useEffect(() => {
    if (mode === "create" && storeVersion == null) return; // wait for explicit first save / activate
    if (advanced || yamlMode) return;
    const t = window.setTimeout(() => void autosave(), 800);
    return () => window.clearTimeout(t);
  }, [doc]); // eslint-disable-line react-hooks/exhaustive-deps

  async function onActivate() {
    if (!token || !tenant) return;
    setActivateMsg(null);
    const yaml = documentToYaml(doc);
    try {
      if (storeVersion == null) {
        const created = await createMetricDefinition(token, tenant.id, yaml);
        setStoreVersion(created.version);
        setStoreRevision(created.revision);
      } else {
        await putMetricDefinitionDraft(token, tenant.id, {
          yaml,
          expected_version: storeVersion,
          expected_revision: storeRevision,
        });
      }
      const classification = await classifyMetricDefinition(token, tenant.id, {
        yaml,
      });
      const mid = String(meta.id);
      await activateMetricDefinition(token, tenant.id, mid, {
        version: classification.next_version,
      });
      setActivateMsg(
        classification.kind === "semantic"
          ? `Activated as version ${classification.next_version} (semantic change — history recompute).`
          : `Activated (display/revision change).`,
      );
      navigate(`/metrics/${encodeURIComponent(mid)}`);
    } catch (err) {
      setActivateMsg(err instanceof ApiError ? err.message : "Activate failed");
    }
  }

  function enterYaml() {
    setYamlText(documentToYaml(doc));
    setYamlError(null);
    setYamlMode(true);
  }

  function leaveYaml() {
    try {
      const parsed = parseYaml(yamlText);
      if (!parsed || typeof parsed !== "object") {
        setYamlError("YAML root must be a mapping");
        return;
      }
      dispatch({ type: "load", doc: parsed as Record<string, unknown> });
      setYamlMode(false);
      setYamlError(null);
    } catch (err) {
      setYamlError(err instanceof Error ? err.message : "Invalid YAML");
    }
  }

  const entity = String(spec.entity ?? "pull_request");
  const entities = catalog?.entities ?? [];
  const entityMeta = entities.find((e) => e.name === entity);
  const eventTimeFields = (entityMeta?.fields ?? []).filter(
    (f) => f.role === "event_time",
  );
  const measureFields = (entityMeta?.fields ?? []).filter(
    (f) => f.role === "measure" || f.role === "key" || f.role === "dimension",
  );
  const dimFields = (entityMeta?.fields ?? []).filter((f) => f.role === "dimension");

  const grains = useMemo(
    () => (Array.isArray(time.grains) ? (time.grains as string[]) : []),
    [time.grains],
  );

  if (loading) {
    return (
      <main className="mx-auto max-w-3xl px-6 py-12">
        <Skeleton className="h-40 w-full" />
      </main>
    );
  }

  if (loadError) {
    return (
      <main className="mx-auto max-w-3xl px-6 py-12">
        <p role="alert" className="text-destructive text-sm">
          {loadError}
        </p>
      </main>
    );
  }

  if (advanced) {
    return (
      <main className="mx-auto max-w-3xl space-y-4 px-6 py-12">
        <AdvancedBanner />
        <CodeBlock code={documentToYaml(doc)} />
        <Button asChild variant="outline">
          <Link to="/metrics">Back</Link>
        </Button>
      </main>
    );
  }

  // Fork prompt when trying to edit a standard propel.* metric in the builder
  if (mode === "edit" && metricIdParam?.startsWith("propel.") && tenant) {
    return (
      <main className="mx-auto max-w-2xl space-y-4 px-6 py-12">
        <h1 className="text-2xl font-semibold">Edit standard metric</h1>
        <ForkPrompt metricId={metricIdParam} orgSlug={tenant.slug} />
        <Button asChild variant="outline">
          <Link to={`/metrics/${encodeURIComponent(metricIdParam)}`}>
            Back to detail
          </Link>
        </Button>
      </main>
    );
  }

  return (
    <main className="bg-background mx-auto min-h-svh max-w-6xl px-6 py-12">
      <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_320px]">
        <div className="space-y-10">
          <header className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <h1 className="text-3xl font-semibold tracking-tight">
                {mode === "create" ? "New metric" : "Edit metric"}
              </h1>
              <p className="text-muted-foreground mt-1 text-sm">
                Structured editor over a <code>propel/v1</code> document.
                {saveState && (
                  <span className="text-muted-foreground ml-2">· {saveState}</span>
                )}
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button
                size="sm"
                variant="outline"
                onClick={() => dispatch({ type: "undo" })}
              >
                Undo
              </Button>
              {yamlMode ? (
                <Button size="sm" variant="outline" onClick={leaveYaml}>
                  Form mode
                </Button>
              ) : (
                <Button size="sm" variant="outline" onClick={enterYaml}>
                  View as YAML
                </Button>
              )}
              <Button
                size="sm"
                analyticsName="metric_activate"
                onClick={() => void onActivate()}
              >
                Activate
              </Button>
            </div>
          </header>

          {activateMsg && (
            <p role="status" className="text-sm">
              {activateMsg}
            </p>
          )}

          {validateErrors.length > 0 && (
            <ul
              role="alert"
              className="border-destructive/40 bg-destructive/5 text-destructive space-y-1 rounded-lg border p-3 text-sm"
            >
              {validateErrors.map((e, i) => (
                <li key={`${e.path}-${i}`}>
                  [{e.code}] {e.path}: {e.message}
                </li>
              ))}
            </ul>
          )}

          {yamlMode ? (
            <div className="space-y-2">
              <textarea
                className="border-input bg-background min-h-96 w-full rounded-lg border p-3 font-mono text-sm"
                value={yamlText}
                onChange={(e) => setYamlText(e.target.value)}
                aria-label="Metric YAML"
              />
              {yamlError && (
                <p role="alert" className="text-destructive text-sm">
                  {yamlError}
                </p>
              )}
            </div>
          ) : (
            <>
              <section className="space-y-3">
                <h2 className="text-lg font-medium">① What kind of metric?</h2>
                <div className="grid gap-3 sm:grid-cols-3">
                  <KindCard
                    title="Measure events"
                    body="Count, interval, or aggregate over an entity."
                    active={
                      !extendsParent &&
                      measure.type !== "ratio" &&
                      measure.type !== "formula"
                    }
                    onClick={() => setSpec("measure", { type: "count" })}
                  />
                  <KindCard
                    title="Combine metrics"
                    body="Ratio or formula over referencable metrics."
                    active={measure.type === "ratio" || measure.type === "formula"}
                    onClick={() =>
                      setSpec("measure", {
                        type: "ratio",
                        numerator: { ref: "" },
                        denominator: { ref: "" },
                        zero_denominator: null,
                      })
                    }
                  />
                  <KindCard
                    title="Variant"
                    body={
                      extendsParent
                        ? `Extends ${extendsParent}`
                        : "Extend an existing metric from the catalog."
                    }
                    active={Boolean(extendsParent)}
                  />
                </div>
                {extendsParent && (
                  <p className="text-muted-foreground text-sm">
                    Locked fields (entity, time.field, measure type) inherit from the
                    parent. Add filters below to narrow — never widen.
                  </p>
                )}
              </section>

              <section className="space-y-3">
                <h2 className="text-lg font-medium">② Basics</h2>
                <div className="grid gap-3 sm:grid-cols-2">
                  <div>
                    <Label htmlFor="metric-name">Name</Label>
                    <Input
                      id="metric-name"
                      value={String(meta.name ?? "")}
                      onChange={(e) => setMeta("name", e.target.value)}
                    />
                  </div>
                  <div>
                    <Label htmlFor="metric-id">Id</Label>
                    <Input
                      id="metric-id"
                      className="font-mono"
                      value={String(meta.id ?? "")}
                      disabled={mode === "edit"}
                      onChange={(e) => setMeta("id", e.target.value)}
                    />
                  </div>
                </div>
                <div>
                  <Label htmlFor="metric-desc">Description</Label>
                  <textarea
                    id="metric-desc"
                    className="border-input bg-background mt-1 min-h-20 w-full rounded-lg border p-2 text-sm"
                    value={String(meta.description ?? "")}
                    onChange={(e) => setMeta("description", e.target.value)}
                  />
                </div>
              </section>

              <section className="space-y-3">
                <h2 className="text-lg font-medium">③ Data</h2>
                <div className="grid gap-3 sm:grid-cols-2">
                  {entities.map((ent) => (
                    <button
                      key={ent.name}
                      type="button"
                      className={
                        entity === ent.name
                          ? "border-primary bg-primary/5 rounded-lg border p-3 text-left"
                          : "border-border hover:bg-muted/40 rounded-lg border p-3 text-left"
                      }
                      onClick={() => setSpec("entity", ent.name)}
                    >
                      <div className="font-medium">{ent.name}</div>
                      <div className="text-muted-foreground text-xs">{ent.grain}</div>
                    </button>
                  ))}
                </div>
                <div>
                  <Label>Measure type</Label>
                  <Select
                    value={String(measure.type ?? "count")}
                    onValueChange={(type) => setSpec("measure", { type })}
                  >
                    <SelectTrigger className="mt-1 w-56">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {MEASURE_TYPES.map((t) => (
                        <SelectItem key={t} value={t}>
                          {t}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                {(measure.type === "ratio" || measure.type === "formula") &&
                  token &&
                  tenant && (
                    <DerivedMeasureEditor
                      token={token}
                      tenantId={tenant.id}
                      measure={measure}
                      onChange={(next) => setSpec("measure", next)}
                    />
                  )}
                {(measure.type === "sum" ||
                  measure.type === "avg" ||
                  measure.type === "min" ||
                  measure.type === "max" ||
                  measure.type === "percentile" ||
                  measure.type === "count_distinct") && (
                  <div>
                    <Label>Field</Label>
                    <Select
                      value={String(measure.field ?? "")}
                      onValueChange={(field) =>
                        setSpec("measure", { ...measure, field })
                      }
                    >
                      <SelectTrigger className="mt-1 w-56">
                        <SelectValue placeholder="Pick field" />
                      </SelectTrigger>
                      <SelectContent>
                        {measureFields.map((f) => (
                          <SelectItem key={f.name} value={f.name}>
                            {f.name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                )}
                {measure.type === "interval" && (
                  <div className="grid gap-3 sm:grid-cols-2">
                    <div>
                      <Label>From</Label>
                      <Select
                        value={String(measure.from ?? "")}
                        onValueChange={(from) =>
                          setSpec("measure", { ...measure, type: "interval", from })
                        }
                      >
                        <SelectTrigger className="mt-1">
                          <SelectValue placeholder="from" />
                        </SelectTrigger>
                        <SelectContent>
                          {eventTimeFields.map((f) => (
                            <SelectItem key={f.name} value={f.name}>
                              {f.name}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                    <div>
                      <Label>To</Label>
                      <Select
                        value={String(measure.to ?? "")}
                        onValueChange={(to) =>
                          setSpec("measure", {
                            ...measure,
                            type: "interval",
                            to,
                            agg: measure.agg ?? "median",
                          })
                        }
                      >
                        <SelectTrigger className="mt-1">
                          <SelectValue placeholder="to" />
                        </SelectTrigger>
                        <SelectContent>
                          {eventTimeFields.map((f) => (
                            <SelectItem key={f.name} value={f.name}>
                              {f.name}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                  </div>
                )}
              </section>

              <section className="space-y-3">
                <h2 className="text-lg font-medium">④ Filters</h2>
                <FilterBuilder
                  entity={entity}
                  catalogEntities={entities}
                  filters={
                    Array.isArray(spec.filters) ? (spec.filters as unknown[]) : []
                  }
                  onChange={(filters) => setSpec("filters", filters)}
                />
              </section>

              <section className="space-y-3">
                <h2 className="text-lg font-medium">⑤ Time</h2>
                <div>
                  <Label>Event time field</Label>
                  <Select
                    value={String(time.field ?? "")}
                    onValueChange={(field) => setSpec("time", { ...time, field })}
                  >
                    <SelectTrigger className="mt-1 w-56">
                      <SelectValue placeholder="field" />
                    </SelectTrigger>
                    <SelectContent>
                      {eventTimeFields.map((f) => (
                        <SelectItem key={f.name} value={f.name}>
                          {f.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="flex flex-wrap gap-3">
                  {GRAINS.map((g) => {
                    const checked = grains.includes(g);
                    return (
                      <label key={g} className="flex items-center gap-2 text-sm">
                        <input
                          type="checkbox"
                          checked={checked}
                          onChange={() => {
                            const next = checked
                              ? grains.filter((x) => x !== g)
                              : [...grains, g];
                            setSpec("time", { ...time, grains: next });
                          }}
                        />
                        {g}
                      </label>
                    );
                  })}
                </div>
              </section>

              <section className="space-y-3">
                <h2 className="text-lg font-medium">⑥ Dimensions</h2>
                <div className="flex flex-wrap gap-3">
                  {dimFields.map((f) => {
                    const dims = Array.isArray(spec.dimensions)
                      ? (spec.dimensions as string[])
                      : [];
                    const checked = dims.includes(f.name);
                    return (
                      <label key={f.name} className="flex items-center gap-2 text-sm">
                        <input
                          type="checkbox"
                          checked={checked}
                          onChange={() => {
                            const next = checked
                              ? dims.filter((x) => x !== f.name)
                              : [...dims, f.name];
                            setSpec("dimensions", next);
                          }}
                        />
                        {f.name}
                        {f.person ? " (person)" : ""}
                        {f.cardinality_estimate != null
                          ? ` · ~${f.cardinality_estimate}`
                          : ""}
                      </label>
                    );
                  })}
                </div>
              </section>

              <section className="space-y-3">
                <h2 className="text-lg font-medium">⑦ Display & visibility</h2>
                <div className="grid gap-3 sm:grid-cols-3">
                  {(
                    [
                      [
                        "ic",
                        "IC",
                        "Surfaced to each individual about their own work; appears in team/org rollups only if the individual opts in.",
                      ],
                      [
                        "team",
                        "Team",
                        "Visible to the team. Person-dimension breakdowns still respect opt-in.",
                      ],
                      [
                        "org",
                        "Org",
                        "Visible across the organization. Prefer IC for person-level flow metrics.",
                      ],
                    ] as const
                  ).map(([value, title, copy]) => (
                    <button
                      key={value}
                      type="button"
                      className={
                        spec.visibility === value
                          ? "border-primary bg-primary/5 rounded-lg border p-3 text-left"
                          : "border-border hover:bg-muted/40 rounded-lg border p-3 text-left"
                      }
                      onClick={() => setSpec("visibility", value)}
                    >
                      <div className="font-medium">{title}</div>
                      <div className="text-muted-foreground mt-1 text-xs">{copy}</div>
                    </button>
                  ))}
                </div>
                {Array.isArray(spec.dimensions) &&
                  (spec.dimensions as string[]).some((d) =>
                    dimFields.find((f) => f.name === d && f.person),
                  ) &&
                  spec.visibility !== "ic" && (
                    <p
                      role="status"
                      className="rounded-lg border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-sm text-amber-100"
                    >
                      This metric breaks down by individual and is visible beyond the
                      individual. Propel&apos;s default is IC visibility for
                      person-level metrics.
                    </p>
                  )}
              </section>
            </>
          )}
        </div>
        {token && tenant && (
          <PreviewPanel token={token} tenantId={tenant.id} doc={doc} />
        )}
      </div>
    </main>
  );
}

function KindCard({
  title,
  body,
  active,
  disabled,
  onClick,
}: {
  title: string;
  body: string;
  active?: boolean;
  disabled?: boolean;
  onClick?: () => void;
}) {
  const className = disabled
    ? "border-border text-muted-foreground rounded-lg border p-3 opacity-60"
    : active
      ? "border-primary bg-primary/5 rounded-lg border p-3 text-left"
      : "border-border hover:bg-muted/40 rounded-lg border p-3 text-left";
  if (disabled || !onClick) {
    return (
      <div className={className}>
        <div className="font-medium">{title}</div>
        <div className="text-muted-foreground mt-1 text-xs">{body}</div>
      </div>
    );
  }
  return (
    <button type="button" className={className} onClick={onClick}>
      <div className="font-medium">{title}</div>
      <div className="text-muted-foreground mt-1 text-xs">{body}</div>
    </button>
  );
}
