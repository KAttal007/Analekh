import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router-dom";
import { api, type WatchlistEntry } from "../api/client";
import { Badge, EmptyState, Loading, MissingTip, PageHeader } from "../components/ui";
import {
  changeTitle,
  crore,
  money,
  price,
  scaleFor,
  shortDate,
  signedPct,
  tone,
} from "../lib/format";

// The Watchlist (design doc 19.1): the companies under deep coverage, as a day-to-day view: the
// latest close, the latest quarter's growth, and anything that needs the analyst's attention
// (a blocked filing, change sets waiting for review). Same table and phone cards as the desk.

const TOP_LINE: Record<string, string> = {
  banking: "int.",
  insurance: "prem.",
  life_insurance: "prem.",
};

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
      <td className="num d-mcap" data-label="Mkt cap">
        {w.market_cap == null ? <span className="muted">–</span> : crore(w.market_cap)}
      </td>
      <td className="num d-rev" data-label="Revenue">
        {money(w.revenue, scale)}
        {TOP_LINE[w.taxonomy] && <span className="desk-tag">{TOP_LINE[w.taxonomy]}</span>}
      </td>
      <td className={`num d-revy ${tone(w.revenue_yoy)}`} title={changeTitle(w.revenue_yoy, "pct")}>
        {w.revenue_yoy == null ? <span className="muted">–</span> : signedPct(w.revenue_yoy)}
      </td>
      <td className="num d-pat" data-label="Net profit">
        {money(w.pat, scale)}
      </td>
      <td className={`num d-paty ${tone(w.pat_yoy)}`} title={changeTitle(w.pat_yoy, "pct")}>
        {w.pat_yoy == null ? <span className="muted">–</span> : signedPct(w.pat_yoy)}
      </td>
      <td className="d-basis">
        {w.consolidated != null && <span className="desk-basis">{w.consolidated ? "C" : "S"}</span>}
      </td>
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
                  <th className="num d-mcap">Market cap</th>
                  <th className="num">Revenue</th>
                  <th className="num" title="Latest quarter on the same quarter a year earlier">
                    YoY
                  </th>
                  <th className="num">Net profit</th>
                  <th className="num">YoY</th>
                  <th className="d-basis" title="C = consolidated, S = standalone">
                    Basis
                  </th>
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
    </div>
  );
}
