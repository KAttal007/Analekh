import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { api, type UploadLimit } from "../../api/client";
import { ErrorNote, PageHeader, Skeleton } from "../../components/ui";
import { filedAt } from "../../lib/format";
import { Alerts, DataStatus } from "./statusPanels";

const MB = 1024 * 1024;

const mb = (bytes: number) => {
  const v = bytes / MB;
  return Number.isInteger(v) ? String(v) : v.toFixed(1);
};

function UploadLimitCard() {
  const qc = useQueryClient();
  const limit = useQuery({ queryKey: ["upload-limit"], queryFn: api.uploadLimit });
  const users = useQuery({ queryKey: ["users"], queryFn: api.users });
  const [draft, setDraft] = useState<string | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const save = useMutation({
    mutationFn: (bytes: number) => api.setUploadLimit(bytes),
    onSuccess: (fresh: UploadLimit) => {
      qc.setQueryData(["upload-limit"], fresh);
      setDraft(null);
      setProblem(null);
    },
    onError: (e) => setProblem(e.message),
  });
  const l = limit.data;
  const shown = draft ?? (l ? mb(l.bytes) : "");
  const who = l?.updated_by ? users.data?.find((u) => u.id === l.updated_by)?.name : null;

  const submit = (e: FormEvent) => {
    e.preventDefault();
    const n = Number(shown.trim());
    if (!shown.trim() || !Number.isFinite(n)) {
      setProblem("Enter a number of megabytes.");
      return;
    }
    setProblem(null);
    save.mutate(Math.round(n * MB));
  };

  return (
    <section className="card">
      <div className="card-header">
        <h2>Upload limit</h2>
      </div>
      <div className="card-body">
        {limit.isError ? (
          <ErrorNote error={limit.error} />
        ) : !l ? (
          <Skeleton height={80} />
        ) : (
          <form onSubmit={submit} noValidate>
            <p className="muted">The largest file anyone can upload: templates, models and anything added later. A change applies to new uploads only; files already stored stay.</p>
            <div className="admin-limit-row">
              <label className="field">
                Maximum file size
                <input inputMode="decimal" value={shown} onChange={(e) => setDraft(e.target.value)} />
              </label>
              <span className="muted">MB</span>
              <button type="submit" className="btn btn-primary" disabled={save.isPending}>
                Save
              </button>
              <button
                type="button"
                className="btn"
                disabled={draft === null}
                onClick={() => {
                  setDraft(null);
                  setProblem(null);
                }}
              >
                Cancel
              </button>
            </div>
            <p className="muted">
              Allowed range: {mb(l.min_bytes)} to {mb(l.ceiling_bytes)} MB. The server ceiling is {mb(l.ceiling_bytes)} MB.
            </p>
            {problem && (
              <p className="alert alert-error" role="alert">
                {problem}
              </p>
            )}
            <div className="admin-limit-meta muted">
              <span>
                Current limit: <b>{mb(l.bytes)} MB</b>
              </span>
              {l.updated_at && (
                <span>
                  Last changed by {who ?? "an admin"}, {filedAt(l.updated_at)}
                </span>
              )}
            </div>
          </form>
        )}
      </div>
    </section>
  );
}

export function AdminSettings() {
  return (
    <div className="page settings">
      <PageHeader title="Settings" subtitle="The upload limit, what the scheduled jobs last did, and where alerts go." />
      <UploadLimitCard />
      <DataStatus />
      <Alerts />
    </div>
  );
}
