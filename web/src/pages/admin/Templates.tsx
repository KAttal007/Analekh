import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api, type Template } from "../../api/client";
import { Icon } from "../../components/Icon";
import { Badge, EmptyState, ErrorNote, Loading, PageHeader, StatusBadge } from "../../components/ui";

type Kind = "excel_model" | "word_report" | "ppt_report";

const KINDS: { kind: Kind; title: string; accept: string; hint: string; empty: string }[] = [
  {
    kind: "excel_model",
    title: "Excel",
    accept: ".xlsx,.xlsm",
    hint: ".xlsx or .xlsm",
    empty: "Upload a workbook. Analekh reads its layout and suggests how each row maps to reported figures, for you to confirm.",
  },
  {
    kind: "word_report",
    title: "Word reports",
    accept: ".docx,.docm,.dotx,.dotm",
    hint: ".docx, .docm, .dotx or .dotm",
    empty: "Upload a Word report template for a sector. One template serves flash notes, notes and initiations.",
  },
  {
    kind: "ppt_report",
    title: "PowerPoint presentations",
    accept: ".pptx,.pptm,.potx,.potm",
    hint: ".pptx, .pptm, .potx or .potm",
    empty: "Upload a PowerPoint template for a sector.",
  },
];

// Template onboarding (design doc 14): upload, review suggested mapping, test build, activate.
// Word and PowerPoint templates are stored as they are for the report writer; only Excel is mapped and tested.
export function Templates() {
  const qc = useQueryClient();
  const {
    data = [],
    isLoading,
    isError,
    error,
  } = useQuery({
    queryKey: ["templates"],
    queryFn: api.templates,
  });
  const [symbol, setSymbol] = useState("");
  const [kind, setKind] = useState<Kind>("excel_model");
  const current = KINDS.find((k) => k.kind === kind) ?? KINDS[0];
  const refresh = () => qc.invalidateQueries({ queryKey: ["templates"] });
  const upload = useMutation({ mutationFn: (form: FormData) => api.uploadTemplate(form), onSuccess: refresh });
  const test = useMutation({ mutationFn: (t: Template) => api.testTemplate(t.id, symbol) });
  const activate = useMutation({ mutationFn: (t: Template) => api.activateTemplate(t.id), onSuccess: refresh });
  const toggle = useMutation({
    mutationFn: (t: Template) => (t.status === "disabled" ? api.enableTemplate(t.id) : api.disableTemplate(t.id)),
    onSuccess: refresh,
  });

  return (
    <div className="page">
      <PageHeader
        title="Templates"
        subtitle="Your Excel model layouts and your Word and PowerPoint report templates. Disable a template to stop new use; models already built from it keep working."
      />

      <form
        className="card"
        onSubmit={(e) => {
          e.preventDefault();
          upload.mutate(new FormData(e.currentTarget));
        }}
      >
        <div className="card-header">
          <h2>Upload a template</h2>
          <span className="muted">{current.hint} · macros are kept and never run</span>
        </div>
        <div className="card-body">
          <div className="form-grid">
            <label className="field">
              Kind
              <select name="kind" value={kind} onChange={(e) => setKind(e.target.value as Kind)}>
                {KINDS.map((k) => (
                  <option key={k.kind} value={k.kind}>
                    {k.title}
                  </option>
                ))}
              </select>
            </label>
            <label className="field">
              File
              <input key={kind} name="workbook" type="file" accept={current.accept} required />
            </label>
            <label className="field">
              Template name
              <input name="name" placeholder="e.g. NBFC quarterly" maxLength={120} required />
            </label>
            <label className="field">
              Sectors
              <input name="sectors" placeholder="Comma separated" maxLength={1000} required />
            </label>
            {kind === "excel_model" && (
              <label className="field field-inline">
                <input name="from_existing_model" type="checkbox" value="true" />
                From an existing model
              </label>
            )}
          </div>
          <div className="action-bar" style={{ marginTop: 16 }}>
            {upload.isError && <ErrorNote error={upload.error} />}
            <button className="btn-primary" type="submit" disabled={upload.isPending}>
              <Icon name="upload" />
              Upload
            </button>
          </div>
        </div>
      </form>

      <div className="template-columns">
        {KINDS.map((k) => {
          const items = data.filter((t) => t.kind === k.kind);
          return (
            <div className="card" key={k.kind}>
              <div className="card-header">
                <h2>{k.title}</h2>
                {k.kind === "excel_model" && (
                  <label className="field field-inline">
                    Test company
                    <input className="input-sm" placeholder="TICKER" value={symbol} onChange={(e) => setSymbol(e.target.value.toUpperCase())} />
                  </label>
                )}
              </div>
              {isLoading ? (
                <div className="card-body">
                  <Loading />
                </div>
              ) : isError ? (
                <div className="card-body">
                  <ErrorNote error={error} />
                </div>
              ) : items.length === 0 ? (
                <div className="card-body">
                  <EmptyState icon="layers" title="No templates yet">
                    {k.empty}
                  </EmptyState>
                </div>
              ) : (
                items.map((t) => {
                  const rows = (t.mapping?.rows as { confidence: number }[] | undefined) ?? [];
                  const low = rows.filter((r) => r.confidence < 0.8).length;
                  const macroType = /m$/.test(t.file_type);
                  return (
                    <div className={`template-item${t.status === "disabled" ? " is-disabled" : ""}`} key={t.id}>
                      <div className="template-name">
                        {t.name} <span className="muted">v{t.version}</span>
                      </div>
                      <div className="muted">{t.sectors.join(", ")}</div>
                      <div className="template-badges">
                        <StatusBadge status={t.status} />
                        <Badge>{t.file_type || "-"}</Badge>
                        {t.has_macros ? (
                          <Badge tone="ok">macros found</Badge>
                        ) : (
                          <Badge tone={macroType ? "warn" : "neutral"} title={macroType ? "This file type can hold macros but none were found" : undefined}>
                            no macros found
                          </Badge>
                        )}
                        {k.kind === "excel_model" && (
                          <span className="muted">
                            {rows.length} rows {low > 0 && <Badge tone="warn">{low} to review</Badge>}
                          </span>
                        )}
                      </div>
                      <div className="cell-actions">
                        {k.kind === "excel_model" && (
                          <>
                            <button className="btn-sm" onClick={() => test.mutate(t)} disabled={!symbol} title={symbol ? `Test-build on ${symbol}` : "Enter a test company"}>
                              Test build
                            </button>
                            <button className="btn-sm btn-primary" onClick={() => activate.mutate(t)} disabled={t.status !== "draft"}>
                              Activate
                            </button>
                          </>
                        )}
                        {t.status !== "draft" && (
                          <button className="btn-sm" onClick={() => toggle.mutate(t)} disabled={toggle.isPending}>
                            {t.status === "disabled" ? "Enable" : "Disable"}
                          </button>
                        )}
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          );
        })}
      </div>
      {toggle.isError && <ErrorNote error={toggle.error} />}
      {activate.isError && <ErrorNote error={activate.error} />}

      {test.data && (
        <div className="card">
          <div className="card-header">
            <h2>Test build result</h2>
          </div>
          <div className="card-body">
            <pre>{JSON.stringify(test.data, null, 2)}</pre>
          </div>
        </div>
      )}
      {test.isError && <ErrorNote error={test.error} />}
    </div>
  );
}
