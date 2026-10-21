import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router-dom";
import { api, type WatchlistEntry } from "../api/client";
import { ResultsCalendar } from "../components/ResultsCalendar";
import {
  BasisCell,
  BasisHeader,
  MarketCapCell,
  ProfitCell,
  ResultColumns,
  RevenueCell,
  YoyCell,
} from "../components/ResultCells";
import { Badge, EmptyState, Loading, MissingTip, PageHeader } from "../components/ui";
import { price, scaleFor, shortDate, signedPct, tone } from "../lib/format";

// The Watchlist (design doc 19.1): the companies under deep coverage, as a day-to-day view: the
// latest close, the latest quarter's growth, and anything that needs the analyst's attention
// (a blocked filing, change sets waiting for review). Same table and phone cards as the desk.

function link(w: WatchlistEntry) {
  const basis =
    w.consolidated == null ? "" : `?basis=${w.consolidated ? "consolidated" : "standalone"}`;
  return `/companies/${w.symbol}${basis}`;
}

function Row({ w }: { w: WatchlistEntry }) {
  const navigate = useNavigate();
  const scale = scaleFor([w.revenue]);
  return (
    <tr className="desk-row" onClick={() => navigate(link(w))}>
      <td className="d-co">
        <Link className="desk-company" to={link(w)} onClick={(e) => e.stopPropagation()}>
          {w.name}
        </Link>
        <span className="desk-ticker">
          <span className="badge-mono">{w.symbol}</span>
          {w.sector && <> · {w.sector}</>}
          {w.quarter_label && <> · {w.quarter_label}</>}
        </span>
        {w.validation_blocked && (
          <Badge tone="error" title="A validation check blocked the latest filing">
            blocked
          </Badge>
        )}
        {w.pending_change_sets > 0 && (
          <Badge tone="warn" title="Model updates waiting for your review">
            {w.pending_change_sets} to review
          </Badge>
        )}
      </td>
      <td
        className="num desk-filed d-filed"
        data-label="Price"
        title={w.price_date ? `${shortDate(w.price_date)} close` : undefined}
      >
        {w.price == null ? (
          <MissingTip text="No closing price loaded yet" />
        ) : (
          <>
            {price(w.price)}
            {w.change_pct != null && (
              <>
                {" "}
                <span className={`desk-sub ${tone(w.change_pct)}`}>{signedPct(w.change_pct)}</span>
              </>
            )}
          </>
        )}
      </td>
      <MarketCapCell value={w.market_cap} missing={<span className="muted">–</span>} />
      <RevenueCell value={w.revenue} taxonomy={w.taxonomy} scale={scale} />
      <YoyCell value={w.revenue_yoy} of="revenue" missing={<span className="muted">–</span>} />
      <ProfitCell value={w.pat} scale={scale} />
      <YoyCell value={w.pat_yoy} of="profit" missing={<span className="muted">–</span>} />
      <BasisCell consolidated={w.consolidated} />
    </tr>
  );
}

export function Watchlist() {
  const { data = [], isLoading } = useQuery({ queryKey: ["watchlist"], queryFn: api.watchlist });
  const newest = data
    .map((w) => w.price_date)
    .filter(Boolean)
    .sort()
    .at(-1);
  return (
    <div className="page">
      <PageHeader
        title="Watchlist"
        badges={data.length > 0 && <Badge>{data.length}</Badge>}
        subtitle="Companies under deep coverage: new results are extracted, validated and turned into change sets for your models."
      />
      {isLoading ? (
        <Loading />
      ) : data.length === 0 ? (
        <EmptyState
          icon="star"
          title="Nothing on your watchlist yet"
          actions={
            <Link className="btn btn-primary" to="/">
              Browse this season's results
            </Link>
          }
        >
          Search for a company above, open it, and press Watch. Its results are then collected and
          checked as soon as NSE publishes them.
        </EmptyState>
      ) : (
        <section className="card desk-main">
          <div className="table-wrap desk-table">
            <table>
              <thead>
                <tr>
                  <th>Company</th>
                  <th className="num">Price</th>
                  <ResultColumns />
                  <BasisHeader />
                </tr>
              </thead>
              <tbody>
                {data.map((w) => (
                  <Row key={w.symbol} w={w} />
                ))}
              </tbody>
            </table>
          </div>
          <p className="rail-foot">
            Latest quarter on record for each company
            {newest ? `; prices at the ${shortDate(newest)} close` : ""}. Growth is on the same
            quarter a year earlier.
          </p>
        </section>
      )}
      {data.length > 0 && <ResultsCalendar watchlistOnly title="Upcoming for your watchlist" />}
    </div>
  );
}
