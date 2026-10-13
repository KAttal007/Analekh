import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useParams } from "react-router-dom";
import { api, type ChangeItem } from "../api/client";
import { Icon } from "../components/Icon";
import { ErrorNote, Loading, PageHeader, StatusBadge } from "../components/ui";

const KINDS = ["actual_write", "roll_forward", "label_shift", "assumption_suggestion"] as const;
const label = (k: string) => k.replaceAll("_", " ");

// Approval gate (design doc 16.4): nothing is written before every item has a decision.
export function ChangeSetReview() {
  const id = Number(useParams().id);
  const qc = useQueryClient();
  const [edits, setEdits] = useState<Record<number, string>>({});
  const cs = useQuery({ queryKey: ["change-set", id], queryFn: () => api.changeSet(id) });
  const refresh = (data: unknown) => qc.setQueryData(["change-set", id], data);
  const decide = useMutation({
    mutationFn: (body: Parameters<typeof api.decide>[1]) => api.decide(id, body),
    onSuccess: refresh,
  });
  const apply = useMutation({ mutationFn: () => api.apply(id) });

  if (cs.isError) return <ErrorNote error={cs.error} />;
  if (!cs.data) return <Loading />;
  const s = cs.data.summary ?? {};
  const items = cs.data.items;
  const pending = items.filter((i) => i.decision === "pending").length;
  const one = (i: ChangeItem, decision: "accepted" | "edited" | "skipped") =>
    decide.mutate({
      decisions: [
        { item_id: i.id, decision, final_value: decision === "edited" ? edits[i.id] : null },
      ],
      accept_kinds: [],
    });
  const stats = [
    ["Cell writes", s.writes],
    ["Dependent cells", s.dependents_affected],
    ["Roll-forwards", s.roll_forwards],
    ["Awaiting decision", pending],
  ] as const;

  return (
    <div className="page">
      <PageHeader
        title={`Change set ${id}`}
        badges={<StatusBadge status={cs.data.status} />}
        subtitle="Review each proposed change to the model. Nothing is written until every item has a decision and you apply them."
        actions={KINDS.map((k) => (
          <button
            key={k}
            className="btn-sm"
            onClick={() => decide.mutate({ decisions: [], accept_kinds: [k] })}
          >
            <Icon name="check" />
            Accept all {label(k)}
          </button>
        ))}
      />

      <div className="stat-grid">
        {stats.map(([name, value]) => (
          <div key={name} className="card stat">
            <div className="stat-label">{name}</div>
            <div className="stat-value">{String(value ?? 0)}</div>
          </div>
        ))}
      </div>

      {((s.warnings_detail as string[] | undefined) ?? []).map((w) => (
        <div key={w} className="alert alert-warn">
          <Icon name="alert" />
          <span>{w}</span>
        </div>
      ))}

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Kind</th>
              <th>Cell</th>
              <th>Old</th>
              <th>New</th>
              <th>Why / source</th>
              <th>Decision</th>
            </tr>
          </thead>
          <tbody>
            {items.map((i) => (
              <tr key={i.id}>
                <td>{label(i.kind)}</td>
                <td className="badge-mono">
                  {i.sheet}!{i.cell}
                </td>
                <td>
                  <code>{i.formula_before ?? i.old_value ?? ""}</code>
                </td>
                <td>
                  <code>{i.formula_after ?? i.new_value ?? ""}</code>
                </td>
                <td className="muted">
                  {i.rationale ?? (i.source_fact_id ? `fact ${i.source_fact_id}` : "")}
                </td>
                <td>
                  {i.decision === "pending" ? (
                    <div className="cell-actions">
                      <button className="btn-sm btn-primary" onClick={() => one(i, "accepted")}>
                        Accept
                      </button>
                      <input
                        className="input-sm"
                        placeholder="Edit value"
                        onChange={(e) => setEdits({ ...edits, [i.id]: e.target.value })}
                      />
                      <button
                        className="btn-sm"
                        onClick={() => one(i, "edited")}
                        disabled={!edits[i.id]}
                      >
                        Save
                      </button>
                      <button className="btn-sm btn-ghost" onClick={() => one(i, "skipped")}>
                        Skip
                      </button>
                    </div>
                  ) : (
                    <span className="cell-actions">
                      <StatusBadge status={i.decision} />
                      {i.final_value && <code>{i.final_value}</code>}
                    </span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="action-bar">
        <span className="muted">
          {pending
            ? `${pending} item${pending === 1 ? "" : "s"} still need a decision`
            : "All items decided"}
        </span>
        <button
          className="btn-primary"
          onClick={() => apply.mutate()}
          disabled={cs.data.status !== "approved" || apply.isPending}
        >
          Apply approved changes
        </button>
      </div>
      {apply.isError && <ErrorNote error={apply.error} />}
      {apply.data && <pre>{JSON.stringify(apply.data, null, 2)}</pre>}
    </div>
  );
}
