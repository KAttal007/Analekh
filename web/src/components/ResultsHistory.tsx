import { useLayoutEffect, useRef } from "react";
import type { Filing, History, HistoryLine } from "../api/client";
import { byQuarter, filedOn, filingLinks, isBlocked, isSuspect, periodKind, type QuarterFilings } from "../lib/filings";
import { longDate, plain, type Scale } from "../lib/format";
import { Icon } from "./Icon";
import { revisionLabel, revisionText, RevisionTag } from "./RevisionTag";
import { Badge, EmptyState, InfoTip, Popover, StatusBadge, TagTip } from "./ui";

// Results history (design doc 19.1): every stored quarter's lines, oldest on the left, in the

const BOLD = new Set(["revenue", "pat"]);

const SOURCE_TITLE = {
  reported: "As the company reports it in its investor presentation",
  calculated: "Worked out by Analekh from the filed accounts",
} as const;

const BLOCKED_NOTE = "A validation check failed on this filing. Its figures are shown as filed, but they won't " + "update a model without your review.";
const SUSPECT_NOTE =
  "Held back: its amounts look off by a power of ten against the company's other filings. " + "Left as filed and kept out of the figures until it is checked against the results PDF.";

function cell(line: HistoryLine, raw: string | null | undefined, scale: Scale): string {
  if (raw == null) return "–";
  if (line.kind === "pct") return `${Number(raw).toFixed(1)}%`;
  if (line.kind === "eps") return Number(raw).toFixed(2);
  return plain(raw, scale);
}

function SourceLinks({ f }: { f: Filing }) {
  const links = filingLinks(f);
  if (!links.length) return <span className="muted">No link from NSE</span>;
  return (
    <span className="file-links">
      {links.map((l) => (
        <a key={l.kind} href={l.url} target="_blank" rel="noopener noreferrer">
          {l.label}
        </a>
      ))}
    </span>
  );
}

function headMark(f: Filing): { label: string; tone: "error" | "warn" } | null {
  if (isBlocked(f)) return { label: "Blocked", tone: "error" };
  const rev = f.revision ? revisionLabel(f.revision) : null;
  return rev ? { label: rev, tone: "warn" } : null;
}

function FilingDetails({ label, end, qf }: { label: string; end: string; qf: QuarterFilings }) {
  const f = qf.current;
  const rev = f.revision && f.revision.status !== "original" ? f.revision : null;
  return (
    <>
      <p className="pop-title">
        {label} <span className="muted">· quarter ended {longDate(end)}</span>
      </p>
      <p className="pop-line">Filed {filedOn(f.filed_at)}</p>
      <p className="pop-line">
        <SourceLinks f={f} />
      </p>
      {isBlocked(f) && <p className="pop-note pop-note-error">{BLOCKED_NOTE}</p>}
      {rev && <p className="pop-note">{revisionText(rev, f.filed_at)}</p>}
      {qf.earlier.length > 0 && (
        <div className="pop-section">
          <p className="pop-sub">Earlier filings, no longer used</p>
          <ul className="pop-list">
            {qf.earlier.map((e) => (
              <li key={e.id}>
                <span>
                  {periodKind(e)}, filed {filedOn(e.filed_at)}
                </span>
                <SourceLinks f={e} />
              </li>
            ))}
          </ul>
        </div>
      )}
    </>
  );
}

function OtherFilings({ filings }: { filings: Filing[] }) {
  const n = filings.length;
  return (
    <details className="other-filings">
      <summary>
        <Icon name="chevronRight" size={14} />
        {n} more {n === 1 ? "filing" : "filings"}
        <span className="muted"> not in the table: older quarters and full-year filings</span>
      </summary>
      <ul className="other-list">
        {filings.map((f) => (
          <li key={f.id}>
            <span className="other-period">{f.period_end ? longDate(f.period_end) : "Period not read"}</span>
            <span className="muted">{periodKind(f)}</span>
            <span className="muted hide-sm">Filed {filedOn(f.filed_at)}</span>
            <span className="other-tags">
              {f.status !== "validated" && <StatusBadge status={f.status} />}
              {isBlocked(f) && <TagTip label="Blocked" tone="error" text={BLOCKED_NOTE} />}
              {isSuspect(f) && <TagTip label="Unit check" tone="warn" text={SUSPECT_NOTE} />}
              {f.revision && <RevisionTag rev={f.revision} filed={f.filed_at} />}
            </span>
            <SourceLinks f={f} />
          </li>
        ))}
      </ul>
    </details>
  );
}

export function ResultsHistory({
  history,
  filings,
  scale,
  excelUrl,
}: {
  history: History;
  filings: Filing[]; // this basis only
  scale: Scale;
  excelUrl: string;
}) {
  const basis = history.consolidated ? "consolidated" : "standalone";
  const wrap = useRef<HTMLDivElement>(null);
  const newest = history.quarter_ends.at(-1);
  useLayoutEffect(() => {
    const el = wrap.current;
    if (el) el.scrollLeft = el.scrollWidth;
  }, [newest, basis]);
  const { quarters, other } = byQuarter(filings, history.quarter_ends);
  const hasTable = history.lines.length > 0;
  return (
    <div className="card area-history">
      <div className="card-header">
        <h2>Results history</h2>
        {hasTable && (
          <div className="actions">
            <span className="muted">
              ₹ {scale.long} · {basis} · {history.quarter_labels.length} quarters
            </span>
            <a className="btn btn-sm" href={excelUrl} download>
              <Icon name="download" size={13} /> Excel
            </a>
          </div>
        )}
      </div>
      {hasTable ? (
        /* Quarters run across, so a long history scrolls inside the card, never the page; the
           line names stay pinned on the left. Focusable so the keyboard can scroll it too. */
        <div className="table-wrap history-table" ref={wrap} tabIndex={0} role="region" aria-label="Results history, quarters scroll sideways">
          <table>
            <caption className="sr-only">
              Quarterly results, {basis}, in ₹ {scale.long}. Each quarter links to its filing on NSE.
            </caption>
            <thead>
              <tr>
                <th className="history-line" scope="col">
                  Line
                </th>
                {history.quarter_labels.map((q, i) => {
                  const end = history.quarter_ends[i];
                  const qf = quarters[i];
                  const ixbrl = qf && filingLinks(qf.current).find((l) => l.kind === "ixbrl");
                  const mark = qf && headMark(qf.current);
                  return (
                    <th key={end} className="num history-q" scope="col">
                      {/* Row 1 is only the label, so the column is as wide as its numbers;
                          tools (and any added later) go in row 2, a status word in row 3. */}
                      <span className="hq-label" title={`Quarter ended ${longDate(end)}`}>
                        {q}
                      </span>
                      <span className="hq">
                        {ixbrl && (
                          <a
                            className="hq-btn"
                            href={ixbrl.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            aria-label={`Open the ${q} filing on NSE (opens in a new tab)`}
                            title="Open the filing on NSE"
                          >
                            <Icon name="external" size={12} />
                          </a>
                        )}
                        {qf && (
                          <Popover label={`${q} filing details`} className="hq-btn">
                            <FilingDetails label={q} end={end} qf={qf} />
                          </Popover>
                        )}
                      </span>
                      {mark && (
                        <span className="hq-mark">
                          <Badge tone={mark.tone}>{mark.label}</Badge>
                        </span>
                      )}
                    </th>
                  );
                })}
              </tr>
            </thead>
            <tbody>
              {history.lines.map((line) => (
                <tr key={line.key} className={BOLD.has(line.key) ? "history-key" : undefined}>
                  <th scope="row" className="history-line">
                    {line.label}
                    {line.source && (
                      <Badge tone={line.source === "reported" ? "accent" : "neutral"} title={SOURCE_TITLE[line.source]}>
                        {line.source === "reported" ? "Reported" : "Calculated"}
                      </Badge>
                    )}
                    {line.note && <InfoTip text={line.note} />}
                  </th>
                  {line.values.map((v, i) => (
                    <td key={history.quarter_ends[i]} className="num">
                      {cell(line, v, scale)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
          {history.lines.some((l) => l.source) && (
            <p className="history-legend muted">
              <Badge tone="accent">Reported</Badge> as published by the company in its investor presentation. <Badge>Calculated</Badge> worked out by Analekh from the filed accounts. The two can
              differ, because companies define margin and funding differently; the calculated rows reconcile with each other (spread = yield minus cost of borrowing).
            </p>
          )}
        </div>
      ) : (
        <div className="card-body">
          <EmptyState icon="file" title="No quarterly figures yet">
            {filings.length
              ? "None of this company's filings carry quarterly figures that passed the checks; they are listed below."
              : "Results filings appear here as NSE publishes them. Watch this company to collect and validate them automatically."}
          </EmptyState>
        </div>
      )}
      {other.length > 0 && <OtherFilings filings={other} />}
    </div>
  );
}
