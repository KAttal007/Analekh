import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../../api/client";
import { Badge, ErrorNote, PageHeader, Skeleton } from "../../components/ui";
import { filedAt } from "../../lib/format";

const ACTIVITY: Record<string, string> = {
  update: "Quarterly update",
  build: "Build",
  report: "Report",
};

export const adminLocksKey = ["admin-locks"] as const;

/** Every model someone is working on, with a Release for each: an admin frees a model a
 *  colleague left open (the holder is named in the audit log). */
export function ModelLocks() {
  const qc = useQueryClient();
  const locks = useQuery({ queryKey: adminLocksKey, queryFn: api.adminLocks });
  const release = useMutation({
    mutationFn: (modelId: number) => api.adminReleaseLock(modelId),
    onSettled: () => qc.invalidateQueries({ queryKey: adminLocksKey }),
  });

  return (
    <div className="page">
      <PageHeader
        title="Model locks"
        subtitle="Who is working on which model. Release frees a model someone left open, and the audit log names whose it was."
      />
      {release.isError && (
        <p className="error" role="alert">
          {release.error.message}
        </p>
      )}
      {locks.isError ? (
        <ErrorNote error={locks.error} />
      ) : !locks.data ? (
        <Skeleton height={160} />
      ) : locks.data.length === 0 ? (
        <p className="muted">No one is working on a model right now.</p>
      ) : (
        <div className="card">
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Held by</th>
                  <th>Company and model</th>
                  <th>Doing</th>
                  <th>Since</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {locks.data.map((l) => (
                  <tr key={l.model_id}>
                    <td>
                      <div className="admin-name">{l.holder_name || "Unknown user"}</div>
                      {l.mine && <div className="muted">You</div>}
                    </td>
                    <td>
                      <div className="admin-name">{l.company_name}</div>
                      <div className="muted">
                        {l.company_symbol} · {l.model_name}
                      </div>
                    </td>
                    <td>
                      {ACTIVITY[l.activity] ?? l.activity}
                      {l.job_running && (
                        <>
                          {" "}
                          <Badge tone="warn">Job running</Badge>
                        </>
                      )}
                    </td>
                    <td className="muted">{filedAt(l.taken_at)}</td>
                    <td>
                      <div className="admin-actions">
                        <button
                          type="button"
                          className="btn btn-sm"
                          disabled={release.isPending}
                          onClick={() => release.mutate(l.model_id)}
                        >
                          Release
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
      <p className="muted admin-note">
        Releasing does not stop a running quarterly update job; it only lets someone else start on
        the model.
      </p>
    </div>
  );
}
