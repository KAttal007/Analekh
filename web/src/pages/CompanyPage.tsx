import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import ReactECharts from "echarts-for-react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { api, type CompanyDetail, type WatchlistEntry } from "../api/client";
import { Icon } from "../components/Icon";
import { QuarterRail } from "../components/QuarterRail";
import { RevisionTag } from "../components/RevisionTag";
import {
  Avatar,
  Badge,
  EmptyState,
  ErrorNote,
  Loading,
  PageHeader,
  SegmentThumb,
  StatusBadge,
} from "../components/ui";
import { companyQuery } from "../lib/preload";
import { crore, money, price, scaleFor, shortDate, signedPct, tone } from "../lib/format";
import { usePrefs } from "../lib/prefs";
import { useTheme } from "../lib/theme";

// "revenue" is resolved per results format on the server; these name what each format calls it.
const TOP_LINE: Record<string, { short: string; full: string }> = {
  banking: { short: "Interest earned", full: "interest earned" },
  insurance: { short: "Premium earned", full: "premium earned" },
  life_insurance: { short: "Net premium", full: "net premium income" },
};
const topLine = (taxonomy?: string | null) =>
  TOP_LINE[taxonomy ?? ""] ?? { short: "Revenue", full: "revenue from operations" };
const DAY_MS = 86_400_000;

// Filings carry year-to-date figures next to the quarter's; keep quarter-length durations only.
const isQuarter = (f: { period_start?: string | null; period_end: string }) => {
  if (!f.period_start) return false;
  const days = (Date.parse(f.period_end) - Date.parse(f.period_start)) / DAY_MS + 1;
  return days >= 80 && days <= 100;
};

// Source files for a filing, readable first: NSE's iXBRL web page, the results PDF, raw XBRL.
const LINK_KINDS = [
  ["ixbrl", "iXBRL"],
  ["pdf", "PDF"],
  ["xbrl", "XBRL"],
] as const;

type FilingLink = { kind: string; label: string; url: string };

const filingLinks = (f: { meta?: Record<string, unknown>; source_url?: string | null }) => {
  const stored = (f.meta?.links ?? {}) as Record<string, unknown>;
  const urls: Record<string, unknown> = { xbrl: f.source_url, ...stored };
  return LINK_KINDS.flatMap(([kind, label]): FilingLink[] => {
    const url = urls[kind];
    // Only web links: backfilled files carry "import:<name>", and nothing else is trusted.
    return typeof url === "string" && url.startsWith("https://") ? [{ kind, label, url }] : [];
  });
};

type Basis = "consolidated" | "standalone";
const BASES: { basis: Basis; label: string }[] = [
  { basis: "consolidated", label: "Consolidated" },
  { basis: "standalone", label: "Standalone" },
];

const cssVar = (name: string) =>
  getComputedStyle(document.documentElement).getPropertyValue(name).trim();

// Coverage levels (coverage.py), in plain words.
const COVERAGE = {
  universe: {
    label: "Listed only",
    tone: "neutral",
    hint: "In the company list. No results filings collected yet.",
  },
  numbers: {
    label: "Numbers collected",
    tone: "accent",
    hint: "Results filings collected, their XBRL figures extracted and validated.",
  },
  deep: {
    label: "Deep coverage",
    tone: "ok",
    hint: "On your watchlist: AI extraction from documents, model updates, reports and alerts.",
  },
} as const;

export function CompanyPage() {
  const { symbol = "" } = useParams();
  const qc = useQueryClient();
  const navigate = useNavigate();
  const { resolved: theme } = useTheme(); // chart colours follow the theme
  const company = useQuery(companyQuery(symbol));
  const filings = useQuery({ queryKey: ["filings", symbol], queryFn: () => api.filings(symbol) });
  // Many companies file both standalone and consolidated results: every figure on the page
  // follows one basis at a time, consolidated first when the company files it (or standalone
  // first, by the Company page basis preference in Settings).
  // Kept in the URL (?basis=standalone): the view can be shared and survives leaving the page.
  const { basis: preferred } = usePrefs();
  const [params, setParams] = useSearchParams();
  const asked = params.get("basis");
  const chosen: Basis | null = asked === "consolidated" || asked === "standalone" ? asked : null;
  const allFilings = filings.data ?? [];
  const filed = {
    consolidated: allFilings.some((f) => f.consolidated === true),
    standalone: allFilings.some((f) => f.consolidated === false),
  };
  const wanted: Basis = chosen ?? preferred;
  const basis: Basis = filed[wanted] ? wanted : filed.consolidated ? "consolidated" : "standalone";
  const revenue = useQuery({
    queryKey: ["facts", symbol, "revenue", basis],
    queryFn: () => api.logicalFacts(symbol, "revenue", basis === "consolidated"),
    enabled: filings.isSuccess,
  });
  const quote = useQuery({ queryKey: ["price", symbol], queryFn: () => api.price(symbol) });
  const watch = useMutation({
    mutationFn: async () => {
      if (company.data?.watched) {
        await api.unwatch(symbol);
        return null;
      }
      return api.watch(symbol); // the company as it now stands: watched, deep coverage
    },
    onSuccess: (updated) => {
      // The button flips as soon as the server answers: with the company as it now stands after
      // a watch, or (an unwatch returns nothing) by marking it unwatched here, so removing never
      // waits for a second request.
      if (updated) qc.setQueryData(["company", symbol], updated);
      else {
        qc.setQueryData<CompanyDetail>(["company", symbol], (old) =>
          old ? { ...old, watched: false } : old,
        );
        qc.setQueryData<WatchlistEntry[]>(["watchlist"], (old) =>
          old?.filter((w) => w.symbol !== symbol),
        );
      }
      // Everything that shows the watchlist, which the browser otherwise keeps for 5 minutes:
      // the company itself (its coverage level), the Watchlist page and the desk's "Watchlist
      // only" view. The Watchlist is fetched now, not on the next visit, so opening it never
      // shows the list from before the change.
      qc.invalidateQueries({ queryKey: ["company", symbol] });
      qc.invalidateQueries({ queryKey: ["watchlist"], refetchType: "all" });
      qc.invalidateQueries({ queryKey: ["desk"] });
    },
  });
  const analyse = useMutation({ mutationFn: () => api.analyse(symbol) });
  const start = useMutation({
    mutationFn: () => api.startCoverage(symbol),
    onSuccess: (b) => navigate(`/models/${b.model.id}/assumptions`),
  });

  if (company.isError) return <ErrorNote error={company.error} />;
  if (!company.data) return <Loading />;
  const c = company.data;
  const quarters = (revenue.data ?? [])
    .filter(isQuarter)
    .sort((a, b) => a.period_end.localeCompare(b.period_end));
  const latest = quarters.at(-1);
  const previous = quarters.at(-2);
  // One unit for the chart and the revenue tile, from the largest quarter shown.
  const scale = scaleFor(quarters.map((f) => Number(f.value ?? 0)));
  const rows = allFilings.filter((f) => (basis === "consolidated") === (f.consolidated !== false));
  const coverage = COVERAGE[c.coverage_level as keyof typeof COVERAGE] ?? COVERAGE.universe;
  const qoq =
    latest && previous && Number(previous.value)
      ? (Number(latest.value) / Number(previous.value) - 1) * 100
      : null;

  return (
    // Wide screens: everything in a main column, the latest quarter in a column on the right that
    // starts at the top of the page, so it fills the window exactly. Narrow screens: the main
    // column dissolves (display: contents) and the quarter slots in after the figure tiles.
    <div className="company-page">
      <div className="company-main">
        <PageHeader
          leading={<Avatar symbol={c.nse_symbol} name={c.name} />}
          title={c.name}
          badges={
            <>
              <Badge tone="accent">
                <span className="badge-mono">{c.nse_symbol}</span>
              </Badge>
              {c.series && <Badge>{c.series}</Badge>}
              {c.is_sme && <Badge tone="warn">SME</Badge>}
              {!c.is_active && <Badge tone="error">Inactive</Badge>}
            </>
          }
          meta={
            <>
              {c.sector ? (
                <span>{c.industry ? `${c.sector} · ${c.industry}` : c.sector}</span>
              ) : (
                <span title="Sectors come from NSE Indices' published lists (about 750 companies) or your own sector map.">
                  Sector not mapped yet
                </span>
              )}
              <span>·</span>
              <Badge tone={coverage.tone} title={coverage.hint}>
                {coverage.label}
              </Badge>
              {c.results_taxonomy && <Badge>{c.results_taxonomy.replace("_", " ")}</Badge>}
              {c.isin && <span className="badge-mono">{c.isin}</span>}
              {c.listing_date && <span>Listed {c.listing_date}</span>}
            </>
          }
          actions={
            <>
              <button
                className={c.watched ? "btn-on" : undefined}
                aria-pressed={c.watched}
                onClick={() => watch.mutate()}
                disabled={watch.isPending}
              >
                <Icon name="star" />
                {c.watched ? "Watching" : "Watch"}
              </button>
              <button onClick={() => analyse.mutate()} disabled={analyse.isPending}>
                <Icon name="play" />
                Analyse
              </button>
              <button
                className="btn-primary"
                onClick={() => start.mutate()}
                disabled={start.isPending}
              >
                Start coverage
              </button>
            </>
          }
        />
        {analyse.data && (
          <div className="alert alert-warn">
            <Icon name="clock" />
            <span>Analysis job {analyse.data.status}.</span>
          </div>
        )}
        {start.isError && <ErrorNote error={start.error} />}

        {allFilings.length > 0 && (
          <div className="basis-bar">
            <span className="muted">Figures</span>
            {filed.consolidated && filed.standalone ? (
              <div className="segmented" role="tablist" aria-label="Basis of figures">
                <SegmentThumb />
                {BASES.map((b) => (
                  <button
                    key={b.basis}
                    type="button"
                    role="tab"
                    aria-selected={basis === b.basis}
                    onClick={() => setParams({ basis: b.basis }, { replace: true })}
                  >
                    {b.label}
                  </button>
                ))}
              </div>
            ) : (
              <Badge>{basis === "consolidated" ? "Consolidated only" : "Standalone only"}</Badge>
            )}
          </div>
        )}

        <div className="stat-grid area-stats">
          <div className="card card-hover stat">
            <span className="stat-icon">
              <Icon name="rupee" />
            </span>
            <div>
              <div className="stat-label">{topLine(c.results_taxonomy).short}, latest quarter</div>
              <div className="stat-value">{latest ? money(latest.value, scale) : "–"}</div>
              <div className="stat-note">
                {latest ? `Quarter ended ${latest.period_end}` : "No results loaded yet"}
              </div>
            </div>
          </div>
          <div className="card card-hover stat">
            <span className="stat-icon">
              <Icon name={qoq !== null && qoq < 0 ? "trendDown" : "trendUp"} />
            </span>
            <div>
              <div className="stat-label">Quarter on quarter</div>
              <div
                className={
                  qoq === null ? "stat-value" : `stat-value ${qoq < 0 ? "delta-down" : "delta-up"}`
                }
              >
                {qoq === null ? "–" : `${qoq > 0 ? "+" : ""}${qoq.toFixed(1)}%`}
              </div>
              <div className="stat-note">
                {basis === "standalone" ? "Standalone" : "Consolidated"}{" "}
                {topLine(c.results_taxonomy).full}
              </div>
            </div>
          </div>
          {/* End-of-day prices from NSE's bhavcopy, loaded after each close: never live. */}
          <div className="card card-hover stat">
            <span className="stat-icon">
              <Icon name="hash" />
            </span>
            <div>
              <div className="stat-label">Share price</div>
              <div className="stat-value">
                {quote.data ? price(quote.data.close) : "–"}
                {quote.data?.change_pct != null && (
                  <span className={`stat-delta ${tone(quote.data.change_pct)}`}>
                    {signedPct(quote.data.change_pct)}
                  </span>
                )}
              </div>
              <div className="stat-note">
                {quote.data
                  ? `${shortDate(quote.data.trade_date)} close`
                  : quote.isSuccess
                    ? "No closing price loaded yet"
                    : ""}
                {c.face_value ? ` · FV ₹${Number(c.face_value)}` : ""}
              </div>
            </div>
          </div>
          <div className="card card-hover stat">
            <span className="stat-icon">
              <Icon name="layers" />
            </span>
            <div>
              <div className="stat-label">Market cap</div>
              <div className="stat-value">{crore(quote.data?.market_cap)}</div>
              <div
                className="stat-note"
                title="Closing price × shares in issue (paid-up equity capital ÷ face value, from the latest results filing)"
              >
                {quote.data?.market_cap != null
                  ? `At the ${shortDate(quote.data.trade_date)} close`
                  : quote.data
                    ? "No share count in its results filings yet"
                    : ""}
              </div>
            </div>
          </div>
        </div>

        <div className="card area-chart">
          <div className="card-header">
            <h2>{topLine(c.results_taxonomy).short} by quarter</h2>
            <span className="muted">
              ₹ {scale.long} · {basis}
            </span>
          </div>
          <div className="card-body">
            {quarters.length > 1 ? (
              <ReactECharts
                key={theme}
                style={{ height: 320 }}
                option={{
                  // Headroom above the plot: the hover popup fits over even the tallest bar.
                  grid: { left: 48, right: 16, top: 64, bottom: 32 },
                  // Hovering a bar shows its value; no band across the column (an opaque axis
                  // shadow painted over the bar in dark mode).
                  tooltip: {
                    trigger: "item",
                    position: "top", // above the bar, clear of the bar and the axis labels
                    confine: true, // and inside the chart, never over the card header
                    backgroundColor: cssVar("--surface"),
                    borderColor: cssVar("--border"),
                    textStyle: { color: cssVar("--text") },
                    formatter: (p: { name: string; value: number }) =>
                      `Quarter ended ${p.name}<br/><b>₹${p.value.toLocaleString("en-IN")} ${scale.short}</b>`,
                  },
                  animationDuration: 600,
                  animationEasing: "cubicOut",
                  textStyle: { fontFamily: "inherit", color: cssVar("--muted") },
                  xAxis: {
                    type: "category",
                    data: quarters.map((f) => f.period_end),
                    axisLine: { lineStyle: { color: cssVar("--border-strong") } },
                  },
                  yAxis: {
                    type: "value",
                    splitLine: { lineStyle: { color: cssVar("--border") } },
                  },
                  series: [
                    {
                      name: topLine(c.results_taxonomy).short,
                      type: "bar",
                      barMaxWidth: 36,
                      cursor: "default",
                      emphasis: { focus: "none", itemStyle: { color: cssVar("--accent-hover") } },
                      itemStyle: {
                        borderRadius: [4, 4, 0, 0],
                        color: {
                          type: "linear",
                          x: 0,
                          y: 0,
                          x2: 0,
                          y2: 1,
                          colorStops: [
                            { offset: 0, color: cssVar("--accent-2") },
                            { offset: 1, color: cssVar("--accent") },
                          ],
                        },
                      },
                      data: quarters.map((f) => {
                        const v = Number(f.value ?? 0) / scale.divisor;
                        return Number(v.toFixed(scale.digits)); // lakhs keep one decimal
                      }),
                    },
                  ],
                }}
              />
            ) : (
              <EmptyState icon="bars" title="No quarterly figures yet">
                The chart fills in once two or more quarterly results have been collected for this
                company.
              </EmptyState>
            )}
          </div>
        </div>

        <div className="card area-filings">
          <div className="card-header">
            <h2>Filings</h2>
            <span className="muted">
              {rows.length} {basis} received
            </span>
          </div>
          {rows.length ? (
            // About ten filings in view, older ones scroll inside the box (history runs to 28
            // quarters); the column headings stay put.
            <div className="table-wrap filings-scroll">
              <table>
                <thead>
                  <tr>
                    <th>Period end</th>
                    <th className="hide-sm">Kind</th>
                    <th className="hide-sm">Status</th>
                    <th>Checks</th>
                    <th>Files</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((f) => {
                    const links = filingLinks(f);
                    const main = links[0];
                    return (
                      <tr key={f.id}>
                        <td>
                          {main ? (
                            <a
                              href={main.url}
                              target="_blank"
                              rel="noopener noreferrer"
                              title={`Open the ${main.label} filing on NSE`}
                            >
                              {f.period_end ?? "-"}
                            </a>
                          ) : (
                            (f.period_end ?? "-")
                          )}
                          {f.revision && (
                            <>
                              {" "}
                              <RevisionTag rev={f.revision} filed={f.filed_at} />
                            </>
                          )}
                        </td>
                        <td className="hide-sm">{f.kind}</td>
                        <td className="hide-sm">
                          <StatusBadge status={f.status} />
                        </td>
                        <td>
                          {f.meta?.blocks_auto_apply ? (
                            <Badge tone="error">blocked</Badge>
                          ) : (
                            <Badge tone="ok">passed</Badge>
                          )}
                        </td>
                        <td className="file-links">
                          {links.length
                            ? links.map((l) => (
                                <a
                                  key={l.kind}
                                  href={l.url}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                >
                                  {l.label}
                                </a>
                              ))
                            : "-"}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="card-body">
              <EmptyState icon="file" title="No filings received yet">
                Results filings appear here as NSE publishes them in its results feed. Watch this
                company to collect and validate them automatically.
              </EmptyState>
            </div>
          )}
        </div>
      </div>

      <QuarterRail
        symbol={symbol}
        consolidated={basis === "consolidated"}
        ready={filings.isSuccess}
      />
    </div>
  );
}
