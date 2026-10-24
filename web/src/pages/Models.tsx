import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type RefObject, useEffect, useId, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useNavigate } from "react-router-dom";
import { api, type Filing, type ModelOut } from "../api/client";
import { Badge, EmptyState, ErrorNote, Loading, PageHeader } from "../components/ui";
import { isBlocked } from "../lib/filings";
import { companyIndexQuery } from "../lib/preload";
import { LockNotice, useIsAdmin } from "../lock/LockNotice";
import { lockedDetail, useLockPollMs, useModelLock } from "../lock/useModelLock";

/** The filing an update reads: the newest results filing. When that one is blocked (its numbers
 *  wait to be checked), the update stops there rather than quietly drafting from an older
 *  quarter. */
function newestFiling(filings: Filing[]): Filing {
  const newest = filings
    .filter((f) => f.kind === "results_xbrl" && f.period_end)
    .sort(
      (a, b) =>
        (b.period_end ?? "").localeCompare(a.period_end ?? "") ||
        (b.filed_at ?? "").localeCompare(a.filed_at ?? ""),
    )[0];
  if (!newest) throw new Error("No filed results to update from yet.");
  if (isBlocked(newest)) throw new BlockedFiling(newest.period_end ?? "");
  return newest;
}

/** The newest results are blocked: Update stops and says so in a pop-up. */
class BlockedFiling extends Error {
  constructor(readonly periodEnd: string) {
    super(`The newest results (period ending ${periodEnd}) are blocked.`);
  }
}

/** A modal pop-up for an Update that cannot go ahead because the newest results are blocked.
 *  Focus moves to OK; OK or Escape closes it and gives focus back to `returnTo`, where focus was
 *  when Update was pressed (read then: the pending Update is disabled, so by the time the pop-up
 *  opens focus has fallen to the page), or to `fallback` when that is gone or disabled. */
function BlockedDialog({
  periodEnd,
  onClose,
  returnTo,
  fallback,
}: {
  periodEnd: string;
  onClose: () => void;
  returnTo: RefObject<HTMLElement | null>;
  fallback: RefObject<HTMLButtonElement | null>;
}) {
  const ok = useRef<HTMLButtonElement>(null);
  const id = useId();
  useEffect(() => {
    const back = returnTo.current; // set when Update was pressed, before this opened
    const update = fallback.current;
    ok.current?.focus();
    return () => {
      const usable =
        back !== null && back !== document.body && back.isConnected && !back.matches(":disabled");
      (usable ? back : update)?.focus();
    };
  }, [returnTo, fallback]);
  return createPortal(
    // The backdrop never takes focus: the dialog's keys (Escape, the Tab trap) keep working.
    <div className="modal-backdrop" onMouseDown={(e) => e.preventDefault()}>
      <div
        className="modal"
        role="alertdialog"
        aria-modal="true"
        aria-labelledby={`${id}-title`}
        aria-describedby={`${id}-text`}
        onKeyDown={(e) => {
          if (e.key === "Escape") {
            e.stopPropagation();
            onClose();
          } else if (e.key === "Tab") {
            e.preventDefault(); // OK is the only control: keep focus inside
            ok.current?.focus();
          }
        }}
      >
        <h2 id={`${id}-title`}>Newest results are blocked</h2>
        <p id={`${id}-text`}>
          The newest results (period ending {periodEnd}) are blocked until their numbers are
          checked, so nothing was drafted. You can still update the model by hand.
        </p>
        <div className="modal-actions">
          <button ref={ok} type="button" className="btn btn-primary" onClick={onClose}>
            OK
          </button>
        </div>
      </div>
    </div>,
    document.body,
  );
}

export function Models() {
  const {
    data = [],
    isLoading,
    isError,
    error,
  } = useQuery({
    queryKey: ["models"],
    queryFn: api.models,
  });
  const pollMs = useLockPollMs();
  // The company behind each model, for its filings and its Reports link.
  const index = useQuery(companyIndexQuery);
  const symbols = new Map((index.data ?? []).map((c) => [c.id, c.nse_symbol]));
  return (
    <div className="page">
      <PageHeader
        title="Models"
        badges={data.length > 0 && <Badge>{data.length}</Badge>}
        subtitle="Models built here, and models the Excel bridge found in your watched folders."
      />
      {isLoading ? (
        <Loading />
      ) : isError ? (
        <ErrorNote error={error} />
      ) : data.length === 0 ? (
        <EmptyState icon="table" title="No models yet">
          Open a company and press Start coverage to build one from a template, or run the Excel
          bridge's <code>scan</code> to link the models you already keep.
        </EmptyState>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Name</th>
                <th>Origin</th>
                <th>File</th>
                <th>Last seen</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {data.map((m) => (
                <ModelRow key={m.id} model={m} symbol={symbols.get(m.company_id)} pollMs={pollMs} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

/** One model, with its update, build and report actions. While a colleague holds the model the
 *  actions are off and a banner says who since when; an admin gets Release lock instead. */
function ModelRow({
  model: m,
  symbol,
  pollMs,
}: {
  model: ModelOut;
  symbol: string | undefined;
  pollMs: number;
}) {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const gate = useModelLock(m.id, pollMs, { freedTo: "/models" });
  const isAdmin = useIsAdmin();
  const update = useMutation({
    mutationFn: async () => {
      const company =
        symbol ??
        (await qc.fetchQuery(companyIndexQuery)).find((c) => c.id === m.company_id)?.nse_symbol;
      if (!company) throw new Error("This model's company is not in the universe.");
      const filings = await qc.fetchQuery({
        queryKey: ["filings", company],
        queryFn: () => api.filings(company),
      });
      return api.syncModel(m.id, newestFiling(filings).id);
    },
    onSuccess: gate.refresh,
    onError: (e) => {
      const detail = lockedDetail(e);
      if (detail) gate.heldBy(detail);
      if (e instanceof BlockedFiling) setBlocked(e.periodEnd);
    },
  });
  const [blocked, setBlocked] = useState<string | null>(null); // the pop-up's period end
  const updateButton = useRef<HTMLButtonElement>(null);
  const focusAtUpdate = useRef<HTMLElement | null>(null); // where the pop-up gives focus back
  const off = gate.held;
  const why = off && gate.lock ? `In use by ${gate.lock.holder_name}` : undefined;
  const failed =
    update.isError && !lockedDetail(update.error) && !(update.error instanceof BlockedFiling);
  return (
    <>
      {blocked !== null && (
        <BlockedDialog
          periodEnd={blocked}
          onClose={() => setBlocked(null)}
          returnTo={focusAtUpdate}
          fallback={updateButton}
        />
      )}
      <tr>
        <td>{m.name}</td>
        <td>
          <Badge tone={m.origin === "built" ? "accent" : "neutral"}>{m.origin}</Badge>
        </td>
        <td className="muted">{m.file_path ?? "-"}</td>
        <td>{m.last_seen ?? "-"}</td>
        <td className="num">
          {!(off && isAdmin) && (
            <span className="cell-actions model-actions">
              <button
                ref={updateButton}
                type="button"
                className="btn-sm"
                onClick={() => {
                  focusAtUpdate.current = document.activeElement as HTMLElement | null;
                  update.mutate();
                }}
                disabled={off || update.isPending}
                title={why ?? "Draft a change set from the newest filing"}
              >
                Update
              </button>
              <button
                type="button"
                className="btn-sm"
                onClick={() => navigate(`/models/${m.id}/assumptions`)}
                disabled={off}
                title={why ?? "Review the assumptions and build the model"}
              >
                Build
              </button>
              <button
                type="button"
                className="btn-sm"
                onClick={() => navigate(symbol ? `/reports?company=${symbol}` : "/reports")}
                disabled={off}
                title={why ?? "Draft a report from this model"}
              >
                Report
              </button>
            </span>
          )}
        </td>
      </tr>
      {(off || failed || update.isSuccess) && (
        <tr className="model-lock-row">
          <td colSpan={5}>
            <LockNotice modelId={m.id} gate={gate} />
            {failed && <ErrorNote error={update.error} />}
            {update.isSuccess && !off && (
              <span className="muted">Update queued: the change set will be ready to review.</span>
            )}
          </td>
        </tr>
      )}
    </>
  );
}
