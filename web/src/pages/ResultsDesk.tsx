import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { api, type Desk, type DeskQuery, type DeskRow, type DeskSort } from "../api/client";
import {
  BasisCell,
  BasisHeader,
  MarketCapCell,
  ProfitCell,
  ResultColumns,
  RevenueCell,
  YoyCell,
} from "../components/ResultCells";
import { Badge, EmptyState, ErrorNote, MissingTip, Segmented, Skeleton } from "../components/ui";
import {
  changeTitle,
  crore,
  filedAt,
  scaleFor,
  shortDate,
  signedBps,
  signedPct,
  tone,
} from "../lib/format";
import { ResultsCalendar } from "../components/ResultsCalendar";
import { usePrefs } from "../lib/prefs";

const PAGE = 10;
const PERIODS = [
  { days: 1, label: "Today" },
  { days: 3, label: "3 days" },
  { days: 7, label: "7 days" },
  { days: 0, label: "Season" },
] as const;
const SORTS: { sort: DeskSort; label: string }[] = [
  { sort: "filed", label: "Newest filing first" },
  { sort: "market_cap", label: "Largest market cap first" },
];

function basisLink(r: DeskRow) {
  return `/companies/${r.symbol}?basis=${r.consolidated ? "consolidated" : "standalone"}`;
}

function Coverage({ d }: { d: Desk }) {
  return (
    <p className="desk-coverage">
      {d.quarter_label} season · <strong>{d.reported.toLocaleString("en-IN")}</strong> of{" "}
      {d.companies_in_scope.toLocaleString("en-IN")} companies reported ·{" "}
      {d.filings_total.toLocaleString("en-IN")} filings collected
      {d.latest_filed_at && <> · latest filing {filedAt(d.latest_filed_at)}</>}
    </p>
  );
}

function ResultsTable({ rows }: { rows: DeskRow[] }) {
  const navigate = useNavigate();
  return (
    <div className="table-wrap desk-table">
      <table>
        <thead>
          <tr>
            <th>Company</th>
            <th>Filed</th>
            <ResultColumns />
            <th
              className="num d-ebitda"
              title="EBITDA margin; change in basis points on a year ago"
            >
              EBITDA margin
            </th>
            <BasisHeader />
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.symbol} className="desk-row" onClick={() => navigate(basisLink(r))}>
              <td className="d-co">
                <Link
                  to={basisLink(r)}
                  className="desk-company"
                  onClick={(e) => e.stopPropagation()}
                >
                  {r.name}
                </Link>
                <span className="desk-ticker">
                  <span className="badge-mono">{r.symbol}</span>
                  {r.sector && <> · {r.sector}</>}
                </span>
                {r.blocked && (
                  <Badge tone="error" title="A validation check blocked this filing">
                    blocked
                  </Badge>
                )}
              </td>
              <td className="desk-filed d-filed" data-label="Filed">
                {filedAt(r.filed_at)}
              </td>
              <MarketCapCell
                value={r.market_cap}
                title={r.price_date ? `At the ${shortDate(r.price_date)} close` : undefined}
                missing={
                  <MissingTip
                    text={
                      r.price_date
                        ? "No share count in its results filings yet"
                        : "No closing price loaded yet"
                    }
                  />
                }
              />
              <RevenueCell value={r.revenue} taxonomy={r.taxonomy} scale={scaleFor([r.revenue])} />
              <YoyCell
                value={r.revenue_yoy}
                of="revenue"
                missing={<MissingTip text={r.yoy_note} />}
              />
              <ProfitCell value={r.pat} scale={scaleFor([r.revenue])} />
              <YoyCell value={r.pat_yoy} of="profit" missing={<MissingTip text={r.yoy_note} />} />
              <td className="num d-ebitda">
                {r.ebitda_margin == null ? (
                  <span className="muted">–</span>
                ) : (
                  <>
                    {Number(r.ebitda_margin).toFixed(1)}%{" "}
                    <span
                      className={`desk-sub ${
                        signedBps(r.ebitda_margin_yoy) === "n.m."
                          ? "muted"
                          : tone(r.ebitda_margin_yoy)
                      }`}
                      title={changeTitle(r.ebitda_margin_yoy, "bps")}
                    >
                      {r.ebitda_margin_yoy == null ? (
                        <MissingTip text={r.yoy_note} />
                      ) : (
                        signedBps(r.ebitda_margin_yoy)
                      )}
                    </span>
                  </>
                )}
              </td>
              <BasisCell consolidated={r.consolidated} />
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function MoverList({
  title,
  rows,
  metric,
}: {
  title: string;
  rows: DeskRow[];
  metric: "rev" | "pat";
}) {
  if (!rows.length) return null;
  return (
    <div className="mover-group">
      <h3>{title}</h3>
      <ol>
        {rows.map((r) => {
          const change = metric === "rev" ? r.revenue_yoy : r.pat_yoy;
          const figure = metric === "rev" ? r.revenue : r.pat;
          return (
            <li key={r.symbol}>
              <Link to={basisLink(r)}>{r.name}</Link>
              <span className="muted mover-figure">{crore(figure)}</span>
              <span className={`num ${tone(change)}`}>
                {change == null ? "" : signedPct(change)}
              </span>
            </li>
          );
        })}
      </ol>
    </div>
  );
}

function Movers({ d }: { d: Desk }) {
  const [metric, setMetric] = useState<"rev" | "pat">("rev");
  const empty =
    metric === "rev"
      ? !d.revenue_top.length
      : !d.profit_top.length && !d.turned_profitable.length && !d.turned_loss.length;
  return (
    <section className="card">
      <div className="card-header">
        <h2>Movers, year on year</h2>
        <Segmented
          label="Movers by"
          options={[
            { value: "rev", label: "Revenue" },
            { value: "pat", label: "Profit" },
          ]}
          value={metric}
          onChange={setMetric}
        />
      </div>
      <div className="card-body movers desk-scroll">
        {empty ? (
          <p className="muted">Not enough results yet for this quarter.</p>
        ) : metric === "rev" ? (
          <>
            <MoverList title="Fastest growth" rows={d.revenue_top} metric="rev" />
            <MoverList title="Slowest growth" rows={d.revenue_bottom} metric="rev" />
          </>
        ) : (
          <>
            <MoverList title="Fastest growth" rows={d.profit_top} metric="pat" />
            <MoverList title="Slowest growth" rows={d.profit_bottom} metric="pat" />
            <MoverList title="Turned profitable" rows={d.turned_profitable} metric="pat" />
            <MoverList title="Turned to a loss" rows={d.turned_loss} metric="pat" />
          </>
        )}
      </div>
      <p className="rail-foot">
        Companies with at least ₹50 cr of quarterly revenue. Profit growth needs a year-ago profit
        of at least 2% of revenue; sign changes are listed on their own.
      </p>
    </section>
  );
}

function Sectors({ d, onPick }: { d: Desk; onPick: (sector: string) => void }) {
  return (
    <section className="card">
      <div className="card-header">
        <h2>By sector</h2>
        <span
          className="muted"
          title="Medians over companies with at least ₹50 cr of quarterly revenue"
        >
          reported · median YoY
        </span>
      </div>
      {d.sectors.length ? (
        <ul className="sector-list desk-scroll">
          {d.sectors.map((s) => (
            <li key={s.sector}>
              <button type="button" className="sector-row" onClick={() => onPick(s.sector)}>
                <span className="sector-name">{s.sector}</span>
                <span className="muted">
                  {s.reported}/{s.total}
                </span>
                <span className="sector-bar" aria-hidden>
                  <span
                    style={{ width: `${Math.min(100, (100 * s.reported) / (s.total || 1))}%` }}
                  />
                </span>
                <span className="sector-medians">
                  <span className={tone(s.median_revenue_yoy)}>
                    rev {signedPct(s.median_revenue_yoy)}
                  </span>
                  <span className={tone(s.median_pat_yoy)}>
                    profit {signedPct(s.median_pat_yoy)}
                  </span>
                </span>
              </button>
            </li>
          ))}
        </ul>
      ) : (
        <div className="card-body muted">No sectors have reported yet.</div>
      )}
    </section>
  );
}

/** Home: the results season at a glance. Filters live in the URL so a view can be shared. */
export function ResultsDesk() {
  const [params, setParams] = useSearchParams();
  // The order follows the URL, else the Results desk order preference (Settings).
  const { deskSort } = usePrefs();
  const askedSort = params.get("sort");
  const sort: DeskSort = askedSort === "market_cap" || askedSort === "filed" ? askedSort : deskSort;
  const query: DeskQuery = {
    quarter_end: params.get("quarter") ?? undefined,
    sector: params.get("sector") ?? undefined,
    watchlist: params.get("watchlist") === "1" || undefined,
    days: Number(params.get("days")) || undefined,
    sort: sort === "market_cap" ? "market_cap" : undefined,
  };
  const page = Math.max(1, Number(params.get("page")) || 1);
  const set = (key: string, value: string | null) => {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    if (key !== "page") next.delete("page"); // a new filter starts again at page 1
    setParams(next, { replace: true });
  };

  const desk = useQuery({
    queryKey: ["desk", query, page],
    queryFn: () => api.desk({ ...query, limit: PAGE, offset: (page - 1) * PAGE }),
    placeholderData: keepPreviousData, // the old page stays up while the next one loads
  });
  if (desk.isError) return <ErrorNote error={desk.error} />;
  const first = desk.data;
  const rows = first?.rows ?? [];
  const pages = first ? Math.max(1, Math.ceil(first.rows_total / PAGE)) : 1;

  return (
    <div className="desk">
      <header className="desk-header">
        <div>
          <h1>Results desk</h1>
          {first ? <Coverage d={first} /> : <Skeleton width="60%" />}
        </div>
        <div className="desk-filters">
          <select
            aria-label="Quarter"
            value={query.quarter_end ?? ""}
            onChange={(e) => set("quarter", e.target.value || null)}
          >
            <option value="">Latest quarter</option>
            {first?.quarters.map((q) => (
              <option key={q.quarter_end} value={q.quarter_end}>
                {q.quarter_label} · {q.reported} reported
              </option>
            ))}
          </select>
          <select
            aria-label="Sector"
            value={query.sector ?? ""}
            onChange={(e) => set("sector", e.target.value || null)}
          >
            <option value="">All sectors</option>
            {(first?.all_sectors ?? []).map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
          <label className="field-inline desk-watch">
            <input
              type="checkbox"
              checked={!!query.watchlist}
              onChange={(e) => set("watchlist", e.target.checked ? "1" : null)}
            />
            Watchlist only
          </label>
        </div>
      </header>

      <div className="desk-grid">
        <section className="card desk-main">
          <div className="card-header">
            <h2>Latest results</h2>
            <select
              className="desk-sort"
              aria-label="Sort results"
              value={sort}
              onChange={(e) => set("sort", e.target.value === deskSort ? null : e.target.value)}
            >
              {SORTS.map((s) => (
                <option key={s.sort} value={s.sort}>
                  {s.label}
                </option>
              ))}
            </select>
            <Segmented
              label="Filed within"
              options={PERIODS.map((p) => ({ value: String(p.days), label: p.label }))}
              value={String(query.days ?? 0)}
              onChange={(days) => set("days", days === "0" ? null : days)}
            />
          </div>
          {!first ? (
            <div className="card-body">
              <Skeleton height={240} />
            </div>
          ) : rows.length ? (
            <>
              <ResultsTable rows={rows} />
              <nav className="desk-more" aria-label="Results pages">
                <span className="muted">
                  {(page - 1) * PAGE + 1}–{(page - 1) * PAGE + rows.length} of{" "}
                  {first.rows_total.toLocaleString("en-IN")}
                </span>
                {pages > 1 && (
                  <span className="pager">
                    <button
                      type="button"
                      onClick={() => set("page", page > 2 ? String(page - 1) : null)}
                      disabled={page <= 1 || desk.isFetching}
                      aria-label="Previous page"
                    >
                      ‹ Prev
                    </button>
                    <span className="muted">
                      Page {page} of {pages}
                    </span>
                    <button
                      type="button"
                      onClick={() => set("page", String(page + 1))}
                      disabled={page >= pages || desk.isFetching}
                      aria-label="Next page"
                    >
                      Next ›
                    </button>
                  </span>
                )}
              </nav>
            </>
          ) : (
            <div className="card-body">
              {first.rows_total > 0 ? (
                <EmptyState icon="file" title={`Page ${page} is past the end`}>
                  This view has {first.rows_total.toLocaleString("en-IN")} results.{" "}
                  <button type="button" className="link-btn" onClick={() => set("page", null)}>
                    Go to the first page
                  </button>
                </EmptyState>
              ) : (
                <EmptyState icon="file" title="No results in this view">
                  Nothing filed {query.days ? `in the last ${query.days} day(s)` : "this quarter"}
                  {query.sector ? ` in ${query.sector}` : ""}
                  {query.watchlist ? " on your watchlist" : ""}. Try a longer period or another
                  quarter.
                </EmptyState>
              )}
            </div>
          )}
        </section>

        <aside className="desk-side">
          {first && <Movers d={first} />}
          {first && <Sectors d={first} onPick={(s) => set("sector", s)} />}
        </aside>
      </div>

      {/* Follows the "Watchlist only" switch above; the Watchlist screen shows the same
          calendar, always limited to its companies. */}
      <ResultsCalendar watchlistOnly={!!query.watchlist} />
    </div>
  );
}
