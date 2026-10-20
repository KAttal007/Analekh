import { useLayoutEffect, useRef } from "react";
import type { History, HistoryLine } from "../api/client";
import type { Scale } from "../lib/format";
import { Icon } from "./Icon";
import { InfoTip } from "./ui";

// Results history (design doc 19.1): every stored quarter's lines, oldest on the left, in the
// company's own results format. One unit for the whole table, named in the header, so the cells
// hold plain numbers an analyst can read across.

const BOLD = new Set(["revenue", "pat"]);

/** 73,188 / 231.4 / −12.5 in the table's unit; one decimal below 1,000, as elsewhere. */
export function plain(raw: string | null | undefined, scale: Scale): string {
  if (raw == null || raw === "") return "–";
  const v = Number(raw) / scale.divisor;
  const digits = scale.short === "lakh" || Math.abs(v) < 1000 ? 1 : 0;
  const text = Math.abs(v).toLocaleString(scale.short === "mn" ? "en-US" : "en-IN", {
    maximumFractionDigits: digits,
    minimumFractionDigits: digits,
  });
  return `${v < 0 ? "−" : ""}${text}`;
}

function cell(line: HistoryLine, raw: string | null | undefined, scale: Scale): string {
  if (raw == null) return "–";
  if (line.kind === "pct") return `${Number(raw).toFixed(1)}%`;
  if (line.kind === "eps") return Number(raw).toFixed(2);
  return plain(raw, scale);
}

export function ResultsHistory({
  history,
  scale,
  excelUrl,
}: {
  history: History;
  scale: Scale;
  excelUrl: string;
}) {
  const basis = history.consolidated ? "consolidated" : "standalone";
  // Oldest on the left, as in a model, but opened at the newest quarters: the ones read first.
  const wrap = useRef<HTMLDivElement>(null);
  const newest = history.quarter_ends.at(-1);
  useLayoutEffect(() => {
    const el = wrap.current;
    if (el) el.scrollLeft = el.scrollWidth;
  }, [newest, basis]);
  return (
    <div className="card area-history">
      <div className="card-header">
        <h2>Results history</h2>
        <div className="actions">
          <span className="muted">
            ₹ {scale.long} · {basis} · {history.quarter_labels.length} quarters
          </span>
          <a className="btn btn-sm" href={excelUrl} download>
            <Icon name="download" size={13} /> Excel
          </a>
        </div>
      </div>
      {/* Quarters run across, so a long history scrolls inside the card, never the page; the
          line names stay pinned on the left. */}
      <div className="table-wrap history-table" ref={wrap}>
        <table>
          <thead>
            <tr>
              <th className="history-line">Line</th>
              {history.quarter_labels.map((q, i) => (
                <th
                  key={history.quarter_ends[i]}
                  className="num"
                  title={`Quarter ended ${history.quarter_ends[i]}`}
                >
                  {q}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {history.lines.map((line) => (
              <tr key={line.key} className={BOLD.has(line.key) ? "history-key" : undefined}>
                <th scope="row" className="history-line">
                  {line.label}
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
      </div>
    </div>
  );
}
