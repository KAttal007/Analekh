import { useQuery } from "@tanstack/react-query";
import { api, type GlanceLine } from "../api/client";
import { changeTitle, money, scaleFor, signedBps, signedPct, type Scale } from "../lib/format";
import { Badge, InfoTip, MissingTip, Skeleton } from "./ui";

// Lines where a rise is a cost going up: their changes are coloured the other way round.
const COSTS = new Set([
  "depreciation",
  "finance_costs",
  "tax",
  "interest_expended",
  "operating_expenses",
  "provisions",
  "expense_ratio", // a life insurer's expenses of management: lower is better
]);

const fmtDate = (iso?: string | null) =>
  iso
    ? new Date(`${iso}T00:00:00`).toLocaleDateString("en-IN", {
        day: "numeric",
        month: "short",
        year: "numeric",
      })
    : "";

function value(line: GlanceLine, scale: Scale): string {
  if (line.value == null) return "–";
  const v = Number(line.value);
  if (line.kind === "pct") return `${v.toFixed(1)}%`;
  if (line.kind === "eps") return `${v < 0 ? "−" : ""}₹${Math.abs(v).toFixed(2)}`;
  return money(line.value, scale);
}

function Change({
  line,
  which,
  missing,
}: {
  line: GlanceLine;
  which: "qoq" | "yoy";
  missing?: string | null; // why the comparison quarter has no figures
}) {
  const raw = line[which];
  if (raw == null) return <MissingTip text={missing} />;
  const v = Number(raw);
  const good = COSTS.has(line.key) ? v < 0 : v > 0;
  const tone = v === 0 || line.key === "exceptional_items" ? "" : good ? "delta-up" : "delta-down";
  const unit = line.kind === "pct" ? "bps" : "pct"; // margins move in basis points
  // Full figures here (the notes moved behind an icon, so the columns have room); the tooltip
  // still says when a change comes from a very small base.
  return (
    <span className={tone} title={changeTitle(raw, unit)}>
      {unit === "bps" ? signedBps(raw, false) : signedPct(raw, false)}
    </span>
  );
}

/** Right-hand column of the company page: the latest quarter's P&L at a glance, and the
 *  earnings-call highlights (generated once per quarter, when the call is processed). */
export function QuarterRail({
  symbol,
  consolidated,
  ready,
}: {
  symbol: string;
  consolidated: boolean;
  ready: boolean;
}) {
  const glance = useQuery({
    queryKey: ["glance", symbol, consolidated],
    queryFn: () => api.glance(symbol, consolidated),
    enabled: ready,
  });
  const g = glance.data;
  // Lakhs for small companies, from the top line, so every line in the box shares one unit.
  const scale = scaleFor([g?.lines.find((l) => l.key === "revenue")?.value]);

  return (
    <aside className="rail" aria-label="Latest quarter">
      <section className="card rail-card">
        <div className="card-header">
          <h2>Latest quarter</h2>
          {g?.quarter_label && <Badge tone="accent">{g.quarter_label}</Badge>}
        </div>
        {!g ? (
          <div className="card-body">
            <Skeleton height={180} />
          </div>
        ) : g.lines.length === 0 ? (
          <div className="card-body muted">No quarterly results on this basis yet.</div>
        ) : (
          <>
            <p className="rail-sub">
              Quarter ended {fmtDate(g.period_end)} ·{" "}
              {g.consolidated ? "consolidated" : "standalone"}
            </p>
            <table className="glance">
              <thead>
                <tr>
                  <th />
                  <th className="num">Value</th>
                  <th
                    className="num"
                    title={`Against the quarter ended ${fmtDate(g.previous_end)}`}
                  >
                    QoQ
                  </th>
                  <th
                    className="num"
                    title={`Against the quarter ended ${fmtDate(g.year_ago_end)}`}
                  >
                    YoY
                  </th>
                </tr>
              </thead>
              <tbody>
                {g.lines.map((line) => (
                  <tr key={line.key} className={line.kind === "pct" ? "glance-ratio" : undefined}>
                    <th scope="row">
                      {line.label}
                      {line.note && <InfoTip text={line.note} />}
                    </th>
                    <td className="num">{value(line, scale)}</td>
                    <td className="num">
                      <Change line={line} which="qoq" missing={g.previous_note} />
                    </td>
                    <td className="num">
                      <Change line={line} which="yoy" missing={g.year_ago_note} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="rail-foot">
              From the filed XBRL. QoQ against {fmtDate(g.previous_end)}, YoY against{" "}
              {fmtDate(g.year_ago_end)}; margins change in basis points (100 bps = 1%).
            </p>
          </>
        )}
      </section>

      <section className="card rail-card rail-grow">
        <div className="card-header">
          <h2>Call highlights</h2>
          <Badge>Not generated yet</Badge>
        </div>
        <div className="card-body rail-empty">
          <p>
            Notes from the earnings call: management's commentary, guidance and the analysts'
            questions, each with a quote and a timestamp you can check.
          </p>
          <p className="muted">
            They are written once per quarter, when the call's recording or transcript has been
            processed, and every number in them is checked against the filing.
          </p>
        </div>
      </section>
    </aside>
  );
}
