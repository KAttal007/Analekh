import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, ApiError, type ChangeItem } from "../api/client";
import { Icon } from "../components/Icon";
import { ErrorNote, Loading, PageHeader, StatusBadge } from "../components/ui";
import { LockNotice, useIsAdmin } from "../lock/LockNotice";
import { lockedDetail, useLockPollMs, useModelLock } from "../lock/useModelLock";

const KINDS = ["actual_write", "roll_forward", "label_shift", "assumption_suggestion"] as const;
const label = (k: string) => k.replaceAll("_", " ");

const KNOWN_CODES = ["change_set_stale", "recalc_unavailable", "recalc_cannot_compute"];

/** The code and message of a 409, 422 or 503 reply the server wrote for the analyst, or null for any
 *  other error. */
function knownReply(e: unknown): { code: string; message: string } | null {
  if (!(e instanceof ApiError && (e.status === 409 || e.status === 422 || e.status === 503))) return null;
  try {
    const detail = JSON.parse(e.message) as { code?: string; message?: string };
    if (!detail?.code || !detail.message || !KNOWN_CODES.includes(detail.code)) return null;
    return { code: detail.code, message: detail.message };
  } catch {
    return null; // a plain-text 409, such as "decide every item first"
  }
}

const staleMessage = (e: unknown) => {
  const reply = knownReply(e);
  return reply?.code === "change_set_stale" ? reply.message : null;
};

/** The message of a 503 "recalc_unavailable" reply (the recalculation service is down) or a 422
 *  "recalc_cannot_compute" reply (the model uses functions it cannot run), or null. */
const unavailableMessage = (e: unknown) => {
  const reply = knownReply(e);
  return reply?.code === "recalc_unavailable" || reply?.code === "recalc_cannot_compute" ? reply.message : null;
};

// Approval gate (design doc 16.4): nothing is written before every item has a decision.
export function ChangeSetReview() {
  const id = Number(useParams().id);
  const qc = useQueryClient();
  const [edits, setEdits] = useState<Record<number, string>>({});
  const cs = useQuery({ queryKey: ["change-set", id], queryFn: () => api.changeSet(id) });
  const modelId = cs.data?.model_id ?? Number.NaN;
  const gate = useModelLock(modelId, useLockPollMs(), {
    freedTo: `/change-sets/${id}`,
    refreshOnFree: [["change-set", id]],
  });
  const isAdmin = useIsAdmin();
  const onLocked = (e: unknown) => {
    const detail = lockedDetail(e);
    if (detail) gate.heldBy(detail);
  };
  const refresh = (data: unknown) => qc.setQueryData(["change-set", id], data);
  const decide = useMutation({
    mutationFn: (body: Parameters<typeof api.decide>[1]) => api.decide(id, body),
    onSuccess: refresh,
    onError: (e) => {
      onLocked(e);
      if (e instanceof ApiError && e.status === 409) void qc.invalidateQueries({ queryKey: ["change-set", id] });
    },
  });
  const [stale, setStale] = useState<string | null>(null);
  const apply = useMutation({
    mutationFn: () => api.apply(id),
    onError: (e) => {
      onLocked(e);
      const message = staleMessage(e);
      if (message) setStale(message);
    },
  });

  if (cs.isError) return <ErrorNote error={cs.error} />;
  if (!cs.data) return <Loading />;
  const off = gate.held; // read-only: a colleague holds the model
  const hidden = off && isAdmin; // an admin frees the model rather than working on it
  const failed = (m: typeof apply | typeof decide) => m.isError && !lockedDetail(m.error) && !knownReply(m.error);
  const unavailable = apply.isError ? unavailableMessage(apply.error) : null;
  const s = cs.data.summary ?? {};
  const items = cs.data.items;
  const pending = items.filter((i) => i.decision === "pending").length;
  const one = (i: ChangeItem, decision: "accepted" | "edited" | "skipped") =>
    decide.mutate({
      decisions: [{ item_id: i.id, decision, final_value: decision === "edited" ? edits[i.id] : null }],
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
        actions={
          !hidden &&
          KINDS.map((k) => (
            <button key={k} className="btn-sm" disabled={off} onClick={() => decide.mutate({ decisions: [], accept_kinds: [k] })}>
              <Icon name="check" />
              Accept all {label(k)}
            </button>
          ))
        }
      />
      <LockNotice modelId={cs.data.model_id} gate={gate} />
      {failed(decide) && <ErrorNote error={decide.error} />}

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
                <td className="muted">{i.rationale ?? (i.source_fact_id ? `fact ${i.source_fact_id}` : "")}</td>
                <td>
                  {i.decision === "pending" && hidden ? (
                    <StatusBadge status={i.decision} />
                  ) : i.decision === "pending" ? (
                    <div className="cell-actions">
                      <button className="btn-sm btn-primary" disabled={off} onClick={() => one(i, "accepted")}>
                        Accept
                      </button>
                      <input className="input-sm" placeholder="Edit value" disabled={off} onChange={(e) => setEdits({ ...edits, [i.id]: e.target.value })} />
                      <button className="btn-sm" onClick={() => one(i, "edited")} disabled={!edits[i.id] || off}>
                        Save
                      </button>
                      <button className="btn-sm btn-ghost" disabled={off} onClick={() => one(i, "skipped")}>
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
        <span className="muted">{pending ? `${pending} item${pending === 1 ? "" : "s"} still need a decision` : "All items decided"}</span>
        {!hidden && (
          <button className="btn-primary" onClick={() => apply.mutate()} disabled={cs.data.status !== "approved" || apply.isPending || off || stale !== null}>
            Apply approved changes
          </button>
        )}
      </div>
      {stale !== null && (
        <div className="alert alert-warn" role="alert">
          <Icon name="alert" />
          <span>{stale}</span>
          <Link className="btn btn-sm" to="/models">
            Back to models
          </Link>
        </div>
      )}
      {unavailable !== null && (
        <div className="alert alert-warn" role="alert">
          <Icon name="alert" />
          <span>{unavailable}</span>
        </div>
      )}
      {failed(apply) && <ErrorNote error={apply.error} />}
      {apply.data && <pre>{JSON.stringify(apply.data, null, 2)}</pre>}
    </div>
  );
}
