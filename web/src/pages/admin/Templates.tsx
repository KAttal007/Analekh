import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api, type Template } from "../../api/client";
import { Icon } from "../../components/Icon";
import { Badge, EmptyState, ErrorNote, Loading, PageHeader, StatusBadge } from "../../components/ui";

// Template onboarding (design doc 14): upload, review suggested mapping, test build, activate.
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
  const upload = useMutation({
    mutationFn: (form: FormData) => api.uploadTemplate(form),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["templates"] }),
  });
  const test = useMutation({ mutationFn: (t: Template) => api.testTemplate(t.id, symbol) });
  const activate = useMutation({
    mutationFn: (t: Template) => api.activateTemplate(t.id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["templates"] }),
  });

  return (
    <div className="page">
      <PageHeader title="Templates" subtitle="Your model layouts. Upload one, review how its rows map to reported figures, test-build it on a company, then activate it." />

      <form
        className="card"
        onSubmit={(e) => {
          e.preventDefault();
          upload.mutate(new FormData(e.currentTarget));
        }}
      >
        <div className="card-header">
          <h2>Upload a template</h2>
          <span className="muted">.xlsx or .xlsm · macros are never run</span>
        </div>
        <div className="card-body">
          <div className="form-grid">
            <label className="field">
              Workbook
              <input name="workbook" type="file" accept=".xlsx,.xlsm" required />
            </label>
            <label className="field">
              Template name
              <input name="name" placeholder="e.g. NBFC quarterly" required />
            </label>
            <label className="field">
              Sectors
              <input name="sectors" placeholder="Comma separated" required />
            </label>
            <label className="field field-inline">
              <input name="from_existing_model" type="checkbox" value="true" />
              From an existing model
            </label>
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

      <div className="card">
        <div className="card-header">
          <h2>Your templates</h2>
          <label className="field field-inline">
            Test company
            <input className="input-sm" placeholder="TICKER" value={symbol} onChange={(e) => setSymbol(e.target.value.toUpperCase())} />
          </label>
        </div>
        {isLoading ? (
          <div className="card-body">
            <Loading />
          </div>
        ) : isError ? (
          <div className="card-body">
            <ErrorNote error={error} />
          </div>
        ) : data.length === 0 ? (
          <div className="card-body">
            <EmptyState icon="layers" title="No templates yet">
              Upload a workbook above. Analekh reads its layout and suggests how each row maps to reported figures, for you to confirm.
            </EmptyState>
          </div>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Name</th>
                  <th className="num">Version</th>
                  <th>Sectors</th>
                  <th>Owner</th>
                  <th>Status</th>
                  <th>Mapped rows</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {data.map((t) => {
                  const rows = (t.mapping?.rows as { confidence: number }[] | undefined) ?? [];
                  const low = rows.filter((r) => r.confidence < 0.8).length;
                  return (
                    <tr key={t.id}>
                      <td>{t.name}</td>
                      <td className="num">{t.version}</td>
                      <td>{t.sectors.join(", ")}</td>
                      <td>{t.owner}</td>
                      <td>
                        <StatusBadge status={t.status} />
                      </td>
                      <td>
                        {rows.length} {low > 0 && <Badge tone="warn">{low} to review</Badge>}
                      </td>
                      <td>
                        <div className="cell-actions">
                          <button className="btn-sm" onClick={() => test.mutate(t)} disabled={!symbol} title={symbol ? `Test-build on ${symbol}` : "Enter a test company"}>
                            Test build
                          </button>
                          <button className="btn-sm btn-primary" onClick={() => activate.mutate(t)} disabled={t.status === "active"}>
                            Activate
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

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
