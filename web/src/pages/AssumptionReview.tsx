import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useParams } from "react-router-dom";
import { api, ApiError } from "../api/client";
import { Icon } from "../components/Icon";
import { EmptyState, ErrorNote, Loading, PageHeader, StatusBadge } from "../components/ui";
import { LockNotice, useIsAdmin } from "../lock/LockNotice";
import { lockedDetail, useLockPollMs, useModelLock } from "../lock/useModelLock";

// Proposed drivers for a new model, with rationale and citations (design doc 15.1 step 4).
export function AssumptionReview() {
  const id = Number(useParams().id);
  const qc = useQueryClient();
  const [edits, setEdits] = useState<Record<number, string>>({});
  const gate = useModelLock(id, useLockPollMs(), {
    freedTo: `/models/${id}/assumptions`,
    refreshOnFree: [["assumptions", id]],
  });
  const isAdmin = useIsAdmin();
  const onLocked = (e: unknown) => {
    const detail = lockedDetail(e);
    if (detail) gate.heldBy(detail);
  };
  const list = useQuery({ queryKey: ["assumptions", id], queryFn: () => api.assumptions(id) });
  const decide = useMutation({
    mutationFn: (body: Parameters<typeof api.decideAssumptions>[1]) => api.decideAssumptions(id, body),
    onSuccess: (data) => qc.setQueryData(["assumptions", id], data),
    onError: (e) => {
      onLocked(e);
      if (e instanceof ApiError && e.status === 409) void qc.invalidateQueries({ queryKey: ["assumptions", id] });
    },
  });
  const finalize = useMutation({ mutationFn: () => api.finalize(id), onError: onLocked });

  if (list.isError) return <ErrorNote error={list.error} />;
  if (list.isLoading) return <Loading />;
  const rows = list.data ?? [];
  const pending = rows.filter((a) => a.decision === "pending").length;
  const off = gate.held; // read-only: a colleague holds the model
  const hidden = off && isAdmin; // an admin frees the model rather than working on it
  const failed = (m: typeof finalize | typeof decide) => m.isError && !lockedDetail(m.error);

  return (
    <div className="page">
      <PageHeader
        title={`Assumptions for model ${id}`}
        subtitle="Proposed drivers for the forecast, each with its reasoning. Accept or edit every one; the model is only built once checks pass."
        actions={
          !hidden && (
            <button onClick={() => decide.mutate({ decisions: [], accept_all: true })} disabled={!pending || off}>
              <Icon name="check" />
              Accept all
            </button>
          )
        }
      />
      <LockNotice modelId={id} gate={gate} />
      {failed(decide) && <ErrorNote error={decide.error} />}
      {rows.length === 0 ? (
        <EmptyState icon="sliders" title="No assumptions proposed">
          Assumptions are proposed when coverage starts from a template.
        </EmptyState>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Driver</th>
                <th className="num">Proposed</th>
                <th>Rationale</th>
                <th>Decision</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((a) => (
                <tr key={a.id}>
                  <td>{a.driver}</td>
                  <td className="num">{a.proposed_value}</td>
                  <td className="muted">{a.rationale}</td>
                  <td>
                    {a.decision === "pending" && hidden ? (
                      <StatusBadge status={a.decision} />
                    ) : a.decision === "pending" ? (
                      <div className="cell-actions">
                        <button
                          className="btn-sm btn-primary"
                          disabled={off}
                          onClick={() =>
                            decide.mutate({
                              decisions: [{ id: a.id, decision: "accepted" }],
                              accept_all: false,
                            })
                          }
                        >
                          Accept
                        </button>
                        <input className="input-sm" placeholder="Edit value" disabled={off} onChange={(e) => setEdits({ ...edits, [a.id]: e.target.value })} />
                        <button
                          className="btn-sm"
                          disabled={!edits[a.id] || off}
                          onClick={() =>
                            decide.mutate({
                              decisions: [{ id: a.id, decision: "edited", final_value: edits[a.id] }],
                              accept_all: false,
                            })
                          }
                        >
                          Save
                        </button>
                      </div>
                    ) : (
                      <span className="cell-actions">
                        <StatusBadge status={a.decision} />
                        {a.final_value && <code>{a.final_value}</code>}
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <div className="action-bar">
        <span className="muted">{pending ? `${pending} still to decide` : "All assumptions decided"}</span>
        {!hidden && (
          <button className="btn-primary" onClick={() => finalize.mutate()} disabled={pending > 0 || rows.length === 0 || finalize.isPending || off}>
            Build model
          </button>
        )}
      </div>
      {failed(finalize) && <ErrorNote error={finalize.error} />}
      {finalize.data && <pre>{JSON.stringify(finalize.data, null, 2)}</pre>}
    </div>
  );
}
