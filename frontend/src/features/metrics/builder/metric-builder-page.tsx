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
  createMetricDefinition,
  getMetricCatalog,
  getMetricDefinition,
  putMetricDefinitionDraft,
  validateMetricDefinition,
  type MetricCatalogResponse,
} from "@/features/metrics/api/metric-definitions";
import { MetricYamlEditor } from "@/features/metrics/builder/metric-yaml-editor";
import { ActivateReviewSheet } from "@/features/metrics/builder/activate-sheet";
import { DerivedMeasureEditor } from "@/features/metrics/builder/derived-measure-editor";
import {
  COMBINE_TEMPLATE_ID,
  METRIC_TEMPLATES,
  matchTemplate,
  type MetricTemplate,
} from "@/features/metrics/builder/metric-templates";
import { AdvancedBanner } from "@/features/metrics/components/metric-badges";
import { ForkPrompt } from "@/features/metrics/catalog/customize-params-dialog";
import { isAdvancedDocument } from "@/features/metrics/document/advanced";
import {
  createDocumentState,
  documentReducer,
  emptyMetricDocument,
} from "@/features/metrics/document/store";
import { documentToYaml } from "@/features/metrics/document/yaml-io";
import {
  fieldForPath,
  validateMetricDocument,
} from "@/features/metrics/schema/client-validate";
import { messageForCode } from "@/features/metrics/schema/error-messages";
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

/** Derive the local (org-scoped) identifier part from a display name. */
function slugifyMetricName(name: string): string {
  const slug = name
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^[_0-9]+/, "")
    .replace(/_+$/, "")
    .slice(0, 63);
  return /^[a-z][a-z0-9_]{1,62}$/.test(slug) ? slug : "new_metric";
}

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
  const [activateOpen, setActivateOpen] = useState(false);
  const [yamlReformatWarn, setYamlReformatWarn] = useState(false);
  const [parentVisibility, setParentVisibility] = useState<string | null>(null);
  const [loading, setLoading] = useState(mode === "edit");
  const [loadError, setLoadError] = useState<string | null>(null);

  const doc = state.doc;
  const meta = (doc.metadata ?? {}) as Record<string, unknown>;
  const spec = (doc.spec ?? {}) as Record<string, unknown>;
  const measure = (spec.measure ?? {}) as Record<string, unknown>;
  const time = (spec.time ?? {}) as Record<string, unknown>;
  const advanced = isAdvancedDocument(doc as never);
  const clientIssues = useMemo(
    () =>
      advanced || yamlMode
        ? []
        : validateMetricDocument(
            doc,
            catalog
              ? {
                  entities: catalog.entities.map((e) => ({
                    name: e.name,
                    fields: e.fields.map((f) => ({
                      name: f.name,
                      type: f.type,
                      role: f.role,
                    })),
                  })),
                }
              : undefined,
          ),
    [doc, advanced, yamlMode, catalog],
  );

  useEffect(() => {
    if (!token || !tenant) return;
    getMetricCatalog(token, tenant.id)
      .then(setCatalog)
      .catch(() => setCatalog(null));
  }, [token, tenant]);

  useEffect(() => {
    if (mode !== "edit" || !token || !tenant || !metricIdParam) return;
    let cancelled = false;
    void (async () => {
      await Promise.resolve();
      if (cancelled) return;
      setLoading(true);
      try {
        const detail = await getMetricDefinition(token, tenant.id, metricIdParam);
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
      } catch (err: unknown) {
        if (cancelled) return;
        setLoadError(err instanceof ApiError ? err.message : "Failed to load");
        setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [mode, token, tenant, metricIdParam]);

  // Prefill variant from ?extends=
  useEffect(() => {
    if (mode !== "create" || !extendsParent || !tenant || !token) return;
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
    getMetricDefinition(token, tenant.id, extendsParent)
      .then((parent) => {
        const resolved = parent.resolved_json as {
          spec?: { visibility?: string };
        } | null;
        const vis =
          resolved?.spec?.visibility ??
          (parseYaml(parent.yaml) as { spec?: { visibility?: string } })?.spec
            ?.visibility ??
          "org";
        setParentVisibility(String(vis));
        dispatch({
          type: "patch",
          patch: { op: "set", path: ["spec", "visibility"], value: vis },
        });
      })
      .catch(() => setParentVisibility("org"));
  }, [mode, extendsParent, presetId, tenant, token]);

  // Create mode: bind tenant slug into id once, preserving the local part.
  useEffect(() => {
    if (mode !== "create" || !tenant || extendsParent) return;
    const id = String(meta.id ?? "");
    if (!id.startsWith(`${tenant.slug}.`)) {
      const local = id.split(".").slice(1).join(".") || "new_metric";
      dispatch({
        type: "patch",
        patch: {
          op: "set",
          path: ["metadata", "id"],
          value: `${tenant.slug}.${local}`,
        },
      });
    }
  }, [mode, tenant, extendsParent]); // eslint-disable-line react-hooks/exhaustive-deps

  const setMeta = (key: string, value: unknown) =>
    dispatch({ type: "patch", patch: { op: "set", path: ["metadata", key], value } });
  const setSpec = (key: string, value: unknown) =>
    dispatch({ type: "patch", patch: { op: "set", path: ["spec", key], value } });

  // The identifier is always `{org slug}.{local part}`. The namespace is fixed
  // to the tenant, and the local part is derived from the name until the
  // first save pins it (draft rows are stored under the id).
  const idIsDerivable = mode === "create" && storeVersion == null && !extendsParent;
  // Until the tenant resolves, keep whatever namespace the doc already has;
  // the bind effect above rewrites it to the tenant slug once known.
  const idNamespace = tenant?.slug ?? (String(meta.id ?? "").split(".")[0] || "org");

  const onNameChange = (name: string) => {
    if (!idIsDerivable) {
      setMeta("name", name);
      return;
    }
    dispatch({
      type: "patch",
      patch: {
        op: "set",
        path: [],
        value: {
          ...doc,
          metadata: {
            ...meta,
            name,
            id: `${idNamespace}.${slugifyMetricName(name)}`,
          },
        },
      },
    });
  };

  /** Apply a core-metric template in a single undo step. */
  function applyTemplate(template: MetricTemplate) {
    const currentName = String(meta.name ?? "");
    const currentDesc = String(meta.description ?? "");
    const nameIsDefault =
      currentName === "" ||
      currentName === "New metric" ||
      METRIC_TEMPLATES.some((t) => t.defaultName === currentName);
    const descIsDefault =
      currentDesc === "" || METRIC_TEMPLATES.some((t) => t.description === currentDesc);
    const nextName = nameIsDefault ? template.defaultName : currentName;
    const nextMeta = {
      ...meta,
      ...(nameIsDefault ? { name: template.defaultName } : {}),
      ...(descIsDefault ? { description: template.description } : {}),
      ...(idIsDerivable ? { id: `${idNamespace}.${slugifyMetricName(nextName)}` } : {}),
    };
    dispatch({
      type: "patch",
      patch: {
        op: "set",
        path: [],
        value: {
          ...doc,
          metadata: nextMeta,
          spec: {
            ...spec,
            entity: template.spec.entity,
            measure: structuredClone(template.spec.measure),
            filters: structuredClone(template.spec.filters),
            time: structuredClone(template.spec.time),
            display: structuredClone(template.spec.display),
          },
        },
      },
    });
  }

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
  }, [doc, advanced, yamlMode, runValidate, catalog]);

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
    setActivateMsg(null);
    setActivateOpen(true);
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
      const parsedDoc = parsed as Record<string, unknown>;
      const parsedMeta = (parsedDoc.metadata ?? {}) as Record<string, unknown>;
      // The identifier is immutable: pin it in edit mode and keep the
      // namespace inside this org in create mode.
      let nextId = String(parsedMeta.id ?? "");
      if (mode === "edit" && metricIdParam) {
        nextId = metricIdParam;
      } else if (tenant && !nextId.startsWith(`${tenant.slug}.`)) {
        const local = nextId.split(".").slice(1).join(".") || nextId || "new_metric";
        nextId = `${tenant.slug}.${local}`;
      }
      dispatch({
        type: "load",
        doc: { ...parsedDoc, metadata: { ...parsedMeta, id: nextId } },
      });
      setYamlMode(false);
      setYamlError(null);
    } catch (err) {
      setYamlError(err instanceof Error ? err.message : "Invalid YAML");
    }
  }

  const entity = String(spec.entity ?? "pull_request");
  const entities = catalog?.entities ?? [];
  const entityMeta = entities.find((e) => e.name === entity);
  const activeTemplateId = matchTemplate(spec);
  const availableEntities = new Set(entities.map((e) => e.name));
  const eventTimeFields = (entityMeta?.fields ?? []).filter(
    (f) => f.role === "event_time",
  );
  const measureFields = (entityMeta?.fields ?? []).filter(
    (f) => f.role === "measure" || f.role === "key" || f.role === "dimension",
  );
  const dimFields = (entityMeta?.fields ?? []).filter((f) => f.role === "dimension");

  const grains = Array.isArray(time.grains) ? (time.grains as string[]) : [];

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
                Pick a core metric, adjust the basics, then save &amp; publish.
                {storeVersion != null && (
                  <span className="text-muted-foreground ml-2">· v{storeVersion}</span>
                )}
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
                Save &amp; publish
              </Button>
            </div>
          </header>

          {activateMsg && (
            <p role="status" className="text-sm">
              {activateMsg}
            </p>
          )}

          {(clientIssues.length > 0 || validateErrors.length > 0) && (
            <ul
              role="alert"
              className="border-destructive/40 bg-destructive/5 text-destructive space-y-1 rounded-lg border p-3 text-sm"
            >
              {clientIssues.map((e, i) => (
                <li key={`c-${e.path}-${i}`}>
                  [{e.code}] {e.path}: {messageForCode(e.code, e.message)}
                  {fieldForPath(e.path) ? (
                    <span className="text-muted-foreground">
                      {" "}
                      → {fieldForPath(e.path)}
                    </span>
                  ) : null}
                </li>
              ))}
              {validateErrors.map((e, i) => (
                <li key={`s-${e.path}-${i}`}>
                  [{e.code}] {e.path}:{" "}
                  {messageForCode(String(e.code ?? ""), e.message ?? "")}
                </li>
              ))}
            </ul>
          )}

          {yamlMode ? (
            <div className="space-y-2">
              {yamlReformatWarn && (
                <p role="status" className="text-sm text-amber-200">
                  This edit will reformat the YAML (structural change).
                </p>
              )}
              <MetricYamlEditor
                value={yamlText}
                onChange={(v) => {
                  setYamlText(v);
                  setYamlReformatWarn(true);
                }}
              />
              {yamlError && (
                <p role="alert" className="text-destructive text-sm">
                  {yamlError}
                </p>
              )}
            </div>
          ) : (
            <>
              {!extendsParent && (
                <section className="space-y-3">
                  <h2 className="text-lg font-medium">① Choose a core metric</h2>
                  <p className="text-muted-foreground text-sm">
                    Start from a proven metric — everything can be fine-tuned under
                    Advanced below.
                  </p>
                  <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                    {METRIC_TEMPLATES.map((template) => {
                      const unavailable =
                        catalog != null && !availableEntities.has(template.spec.entity);
                      return (
                        <KindCard
                          key={template.id}
                          title={template.title}
                          body={
                            unavailable
                              ? `Needs the ${template.spec.entity} entity, which isn't in your catalog yet.`
                              : template.description
                          }
                          active={activeTemplateId === template.id}
                          disabled={unavailable}
                          onClick={
                            unavailable ? undefined : () => applyTemplate(template)
                          }
                        />
                      );
                    })}
                    <KindCard
                      title="Combine metrics"
                      body="Ratio or formula over existing metrics."
                      active={activeTemplateId === COMBINE_TEMPLATE_ID}
                      onClick={() =>
                        setSpec("measure", {
                          type: "ratio",
                          numerator: { ref: "" },
                          denominator: { ref: "" },
                          zero_denominator: null,
                        })
                      }
                    />
                  </div>
                  {activeTemplateId === null && (
                    <p className="text-muted-foreground text-sm">
                      Custom definition — the details live under Advanced below.
                    </p>
                  )}
                  {activeTemplateId === COMBINE_TEMPLATE_ID && token && tenant && (
                    <DerivedMeasureEditor
                      token={token}
                      tenantId={tenant.id}
                      measure={measure}
                      onChange={(next) => setSpec("measure", next)}
                    />
                  )}
                </section>
              )}

              {extendsParent && (
                <section className="border-border space-y-2 rounded-lg border border-dashed p-4">
                  <h2 className="text-lg font-medium">Variant of {extendsParent}</h2>
                  <ul className="text-muted-foreground space-y-1 text-sm">
                    <li>
                      🔒 Entity / measure type / time.field — locked (not overridable)
                    </li>
                    <li>
                      ⤴ Grains, dimensions, display, visibility — inherited; override
                      below
                    </li>
                  </ul>
                </section>
              )}

              <section className="space-y-3">
                <h2 className="text-lg font-medium">② Basics</h2>
                <div className="grid gap-3 sm:grid-cols-2">
                  <div>
                    <Label htmlFor="metric-name">Name</Label>
                    <Input
                      id="metric-name"
                      value={String(meta.name ?? "")}
                      onChange={(e) => onNameChange(e.target.value)}
                    />
                  </div>
                  <div>
                    <Label>Identifier</Label>
                    <p
                      className="text-muted-foreground mt-2.5 font-mono text-sm"
                      data-testid="metric-id-display"
                    >
                      {String(meta.id ?? "")
                        .split(".")
                        .slice(1)
                        .join(".") || String(meta.id ?? "")}
                    </p>
                    <p className="text-muted-foreground mt-1 text-xs">
                      {idIsDerivable
                        ? "Set automatically from the name."
                        : "Identifiers can't be changed."}
                    </p>
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

              <section className="space-y-4">
                <h2 className="text-lg font-medium">③ Time</h2>
                <div className="space-y-1">
                  <Label>Date used on the chart</Label>
                  <p className="text-muted-foreground text-xs">
                    Each {entity.replace(/_/g, " ")} lands in a time bucket based on
                    this date.
                  </p>
                  <Select
                    value={String(time.field ?? "")}
                    onValueChange={(field) => setSpec("time", { ...time, field })}
                  >
                    <SelectTrigger className="mt-1 w-56">
                      <SelectValue placeholder="Pick a date field" />
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
                <div className="space-y-1">
                  <Label>Chart by</Label>
                  <p className="text-muted-foreground text-xs">
                    Choose which time buckets this metric can be viewed at.
                  </p>
                  <div className="flex flex-wrap gap-2 pt-1">
                    {GRAINS.map((g) => {
                      const checked = grains.includes(g);
                      return (
                        <button
                          key={g}
                          type="button"
                          aria-pressed={checked}
                          className={
                            checked
                              ? "border-primary bg-primary/5 text-foreground rounded-full border px-3 py-1 text-sm"
                              : "border-border text-muted-foreground hover:bg-muted/40 rounded-full border px-3 py-1 text-sm"
                          }
                          onClick={() => {
                            const next = checked
                              ? grains.filter((x) => x !== g)
                              : [...grains, g];
                            setSpec("time", { ...time, grains: next });
                          }}
                        >
                          {g.charAt(0).toUpperCase() + g.slice(1)}
                        </button>
                      );
                    })}
                  </div>
                </div>
              </section>

              <section className="space-y-3">
                <h2 className="text-lg font-medium">④ Visibility</h2>
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
                  )
                    .filter(([value]) => {
                      if (!parentVisibility) return true;
                      const rank: Record<string, number> = {
                        ic: 0,
                        team: 1,
                        org: 2,
                      };
                      return (rank[value] ?? 0) <= (rank[parentVisibility] ?? 2);
                    })
                    .map(([value, title, copy]) => (
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

              <details className="border-border rounded-lg border">
                <summary className="hover:bg-muted/40 cursor-pointer rounded-lg px-4 py-3 font-medium">
                  Advanced — measure, dimensions, display
                </summary>
                <div className="space-y-8 px-4 pt-2 pb-4">
                  <div className="space-y-3">
                    <h3 className="text-sm font-medium">Data</h3>
                    {!extendsParent && (
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
                            <div className="text-muted-foreground text-xs">
                              {ent.grain}
                            </div>
                          </button>
                        ))}
                      </div>
                    )}
                    {extendsParent ? (
                      <p className="text-muted-foreground text-sm">
                        Entity and measure type are locked from the parent.
                      </p>
                    ) : (
                      <>
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
                                  setSpec("measure", {
                                    ...measure,
                                    type: "interval",
                                    from,
                                  })
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
                      </>
                    )}
                  </div>

                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <Label>Rolling windows</Label>
                      <Button
                        size="sm"
                        variant="outline"
                        type="button"
                        onClick={() => {
                          const windows = Array.isArray(time.windows)
                            ? [...(time.windows as object[])]
                            : [];
                          windows.push({ days: 30, step: "day" });
                          setSpec("time", { ...time, windows });
                        }}
                      >
                        + Add rolling window
                      </Button>
                    </div>
                    {(Array.isArray(time.windows)
                      ? (time.windows as Array<{ days?: number; step?: string }>)
                      : []
                    ).map((w, i) => (
                      <div
                        key={i}
                        className="flex flex-wrap items-center gap-2 text-sm"
                      >
                        <span>Trailing</span>
                        <Input
                          type="number"
                          className="w-20"
                          value={w.days ?? 30}
                          onChange={(e) => {
                            const windows = [
                              ...(time.windows as Array<{
                                days?: number;
                                step?: string;
                              }>),
                            ];
                            windows[i] = {
                              ...windows[i],
                              days: Number(e.target.value),
                            };
                            setSpec("time", { ...time, windows });
                          }}
                        />
                        <span>days, computed</span>
                        <Select
                          value={w.step ?? "day"}
                          onValueChange={(step) => {
                            const windows = [
                              ...(time.windows as Array<{
                                days?: number;
                                step?: string;
                              }>),
                            ];
                            windows[i] = { ...windows[i], step };
                            setSpec("time", { ...time, windows });
                          }}
                        >
                          <SelectTrigger className="w-28">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="day">daily</SelectItem>
                            <SelectItem value="week">weekly</SelectItem>
                          </SelectContent>
                        </Select>
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => {
                            const windows = (time.windows as object[]).filter(
                              (_, j) => j !== i,
                            );
                            setSpec("time", { ...time, windows });
                          }}
                        >
                          Remove
                        </Button>
                      </div>
                    ))}
                    {Array.isArray(time.windows) &&
                      (time.windows as unknown[]).length > 0 &&
                      Array.isArray(spec.dimensions) &&
                      (spec.dimensions as string[]).length > 2 && (
                        <p className="text-xs text-amber-200">
                          Cost hint: many windows × dimensions can be expensive to
                          compile.
                        </p>
                      )}
                  </div>

                  <div className="space-y-3">
                    <h3 className="text-sm font-medium">Dimensions</h3>
                    <div className="flex flex-wrap gap-3">
                      {dimFields.map((f) => {
                        const dims = Array.isArray(spec.dimensions)
                          ? (spec.dimensions as string[])
                          : [];
                        const checked = dims.includes(f.name);
                        return (
                          <label
                            key={f.name}
                            className="flex items-center gap-2 text-sm"
                          >
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
                  </div>

                  <div className="space-y-3">
                    <h3 className="text-sm font-medium">Display</h3>
                    <div className="grid gap-3 sm:grid-cols-3">
                      <div>
                        <Label>Unit</Label>
                        <Input
                          className="mt-1"
                          value={String(
                            ((spec.display as Record<string, unknown>) ?? {}).unit ??
                              "",
                          )}
                          onChange={(e) =>
                            setSpec("display", {
                              ...((spec.display as object) ?? {}),
                              unit: e.target.value,
                            })
                          }
                        />
                      </div>
                      <div>
                        <Label>Format</Label>
                        <Select
                          value={String(
                            ((spec.display as Record<string, unknown>) ?? {}).format ??
                              "integer",
                          )}
                          onValueChange={(format) =>
                            setSpec("display", {
                              ...((spec.display as object) ?? {}),
                              format,
                            })
                          }
                        >
                          <SelectTrigger className="mt-1">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            {(
                              [
                                "integer",
                                "decimal_1dp",
                                "decimal_2dp",
                                "percent_1dp",
                                "humanize_duration",
                              ] as const
                            ).map((f) => (
                              <SelectItem key={f} value={f}>
                                {f}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>
                      <div>
                        <Label>Direction</Label>
                        <Select
                          value={String(
                            ((spec.display as Record<string, unknown>) ?? {})
                              .direction ?? "neutral",
                          )}
                          onValueChange={(direction) =>
                            setSpec("display", {
                              ...((spec.display as object) ?? {}),
                              direction,
                            })
                          }
                        >
                          <SelectTrigger className="mt-1">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="higher_is_better">
                              higher is better
                            </SelectItem>
                            <SelectItem value="lower_is_better">
                              lower is better
                            </SelectItem>
                            <SelectItem value="neutral">neutral</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                    </div>
                  </div>
                </div>
              </details>
            </>
          )}
        </div>
        {token && tenant && (
          <PreviewPanel token={token} tenantId={tenant.id} doc={doc} />
        )}
      </div>
      {token && tenant && (
        <ActivateReviewSheet
          open={activateOpen}
          onOpenChange={setActivateOpen}
          token={token}
          tenantId={tenant.id}
          doc={doc}
          storeVersion={storeVersion}
          storeRevision={storeRevision}
          onStoreMeta={(version, revision) => {
            setStoreVersion(version);
            setStoreRevision(revision);
          }}
          onActivated={(mid) => {
            setActivateMsg("Activated.");
            navigate(`/metrics/${encodeURIComponent(mid)}`);
          }}
        />
      )}
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
