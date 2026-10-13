import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "../api/client";
import { Icon } from "../components/Icon";
import { EmptyState, ErrorNote, Loading, PageHeader, StatusBadge } from "../components/ui";

// Proposed drivers for a new model, with rationale and citations (design doc 15.1 step 4).
export function AssumptionReview() {
  const id = Number(useParams().id);
  const qc = useQueryClient();
  const [edits, setEdits] = useState<Record<number, string>>({});
  const list = useQuery({ queryKey: ["assumptions", id], queryFn: () => api.assumptions(id) });
  const decide = useMutation({
    mutationFn: (body: Parameters<typeof api.decideAssumptions>[1]) =>
      api.decideAssumptions(id, body),
    onSuccess: (data) => qc.setQueryData(["assumptions", id], data),
  });
  const finalize = useMutation({ mutationFn: () => api.finalize(id) });

  if (list.isError) return <ErrorNote error={list.error} />;
  if (list.isLoading) return <Loading />;
  const rows = list.data ?? [];
  const pending = rows.filter((a) => a.decision === "pending").length;

  return (
    <div className="page">
      <PageHeader
        title={`Assumptions for model ${id}`}
        subtitle="Proposed drivers for the forecast, each with its reasoning. Accept or edit every one; the model is only built once checks pass."
        actions={
          <button
            onClick={() => decide.mutate({ decisions: [], accept_all: true })}
            disabled={!pending}
          >
            <Icon name="check" />
            Accept all
          </button>
        }
      />
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
                    {a.decision === "pending" ? (
                      <div className="cell-actions">
                        <button
                          className="btn-sm btn-primary"
                          onClick={() =>
                            decide.mutate({
                              decisions: [{ id: a.id, decision: "accepted" }],
                              accept_all: false,
                            })
                          }
                        >
                          Accept
                        </button>
                        <input
                          className="input-sm"
                          placeholder="Edit value"
                          onChange={(e) => setEdits({ ...edits, [a.id]: e.target.value })}
                        />
                        <button
                          className="btn-sm"
                          disabled={!edits[a.id]}
                          onClick={() =>
                            decide.mutate({
                              decisions: [
                                { id: a.id, decision: "edited", final_value: edits[a.id] },
                              ],
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
        <span className="muted">
          {pending ? `${pending} still to decide` : "All assumptions decided"}
        </span>
        <button
          className="btn-primary"
          onClick={() => finalize.mutate()}
          disabled={pending > 0 || rows.length === 0 || finalize.isPending}
        >
          Build model
        </button>
      </div>
      {finalize.isError && <ErrorNote error={finalize.error} />}
      {finalize.data && <pre>{JSON.stringify(finalize.data, null, 2)}</pre>}
    </div>
  );
}
