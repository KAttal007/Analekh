import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import ReactECharts from "echarts-for-react";
import { useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { api, type CompanyDetail, type HistoryLine, type WatchlistEntry } from "../api/client";
import { Icon } from "../components/Icon";
import { QuarterRail } from "../components/QuarterRail";
import { ResultsHistory } from "../components/ResultsHistory";
import { RevisionTag } from "../components/RevisionTag";
import {
  Avatar,
  Badge,
  EmptyState,
  ErrorNote,
  Loading,
  PageHeader,
  Segmented,
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

// What the chart can show: the top line, profit, then the first margin the company's format has
// (a bank's net interest income instead, since EBITDA means nothing for a lender).
const CHART_KEYS = ["revenue", "pat", "ebitda_margin", "nii", "net_margin"];
const CHART_LABEL: Record<string, string> = {
  pat: "Net profit",
  ebitda_margin: "EBITDA margin",
  nii: "Net interest income",
  net_margin: "Net margin",
};
const HISTORY_QUARTERS = 12;

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
  // The chart, the tiles and the history table share one request: the same quarters, lines and
  // exclusions as the latest-quarter column.
  const history = useQuery({
    queryKey: ["history", symbol, basis],
    queryFn: () => api.history(symbol, basis === "consolidated", HISTORY_QUARTERS),
    enabled: filings.isSuccess,
  });
  const [metric, setMetric] = useState("revenue");
  // Analyse queues a background job: say so up front when the queue isn't running.
  const jobs = useQuery({
    queryKey: ["jobs-available"],
    queryFn: api.jobsAvailable,
    staleTime: 60_000,
  });
  const jobsDown = jobs.data?.available === false;
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
  const h = history.data;
  const labels = h?.quarter_labels ?? [];
  const byKey = new Map((h?.lines ?? []).map((l) => [l.key, l]));
  const topValues = byKey.get("revenue")?.values ?? [];
  let lastAt = topValues.length - 1;
  while (lastAt >= 0 && topValues[lastAt] == null) lastAt -= 1;
  const latest = lastAt >= 0 ? { value: topValues[lastAt], label: labels[lastAt] } : undefined;
  const previous = lastAt > 0 ? topValues[lastAt - 1] : undefined;
  // One unit for the chart, the tiles and the table, from the largest quarter shown.
  const scale = scaleFor(topValues);
  const chartLines = CHART_KEYS.map((k) => byKey.get(k)).filter(
    (l): l is HistoryLine => l !== undefined,
  );
  const choices = [
    ...chartLines.filter((l) => l.key === "revenue" || l.key === "pat"),
    ...chartLines.filter((l) => l.key !== "revenue" && l.key !== "pat").slice(0, 1),
  ];
  const shown = choices.find((l) => l.key === metric) ?? choices[0];
  const isPct = shown?.kind === "pct";
  const points = (shown?.values ?? []).map((v) =>
    v == null
      ? null
      : isPct
        ? Number(v)
        : Number((Number(v) / scale.divisor).toFixed(scale.digits)),
  );
  const shownLabel = (l: HistoryLine) =>
    l.key === "revenue" ? topLine(c.results_taxonomy).short : (CHART_LABEL[l.key] ?? l.label);
  const rows = allFilings.filter((f) => (basis === "consolidated") === (f.consolidated !== false));
  const coverage = COVERAGE[c.coverage_level as keyof typeof COVERAGE] ?? COVERAGE.universe;
  const qoq =
    latest?.value != null && previous != null && Number(previous)
      ? (Number(latest.value) / Number(previous) - 1) * 100
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
              <button
                onClick={() => analyse.mutate()}
                disabled={analyse.isPending || jobsDown}
                title={
                  jobsDown
                    ? (jobs.data?.detail ?? undefined)
                    : "Collect history and read the documents in the background"
                }
                aria-describedby={jobsDown ? "analyse-note" : undefined}
              >
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
        {jobsDown && (
          <p id="analyse-note" className="muted action-note">
            Analyse runs as a background job, and the job queue isn't running on this machine yet
            (it comes with hosting). Watch and Start coverage work now.
          </p>
        )}
        {analyse.data && (
          <div className="alert alert-warn">
            <Icon name="clock" />
            <span>Analysis job {analyse.data.status}.</span>
          </div>
        )}
        {analyse.isError && <ErrorNote error={analyse.error} />}
        {start.isError && <ErrorNote error={start.error} />}

        {allFilings.length > 0 && (
          <div className="basis-bar">
            <span className="muted">Figures</span>
            {filed.consolidated && filed.standalone ? (
              <Segmented
                label="Basis of figures"
                options={BASES.map((b) => ({ value: b.basis, label: b.label }))}
                value={basis}
                onChange={(b) => setParams({ basis: b }, { replace: true })}
              />
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
              <div className="stat-note">{latest ? latest.label : "No results loaded yet"}</div>
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
                {signedPct(qoq, false)}
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
            <h2>{shown ? shownLabel(shown) : topLine(c.results_taxonomy).short} by quarter</h2>
            <div className="actions">
              {choices.length > 1 && (
                <Segmented
                  label="Chart shows"
                  options={choices.map((l) => ({ value: l.key, label: shownLabel(l) }))}
                  value={shown?.key}
                  onChange={setMetric}
                />
              )}
              <span className="muted">
                {isPct ? "%" : `₹ ${scale.long}`} · {basis}
              </span>
            </div>
          </div>
          <div className="card-body">
            {labels.length > 1 && shown ? (
              <div
                role="img"
                aria-label={`${shownLabel(shown)} by quarter, ${labels[0]} to ${labels.at(-1)}; the same figures are in the results history table below`}
              >
                <ReactECharts
                  key={`${theme}-${shown.key}`}
                  style={{ height: 320 }}
                  option={{
                    grid: { left: 48, right: 16, top: 40, bottom: 32 },
                    tooltip: {
                      trigger: "item",
                      position: "top", // above the bar, clear of the bar and the axis labels
                      confine: true, // and inside the chart, never over the card header
                      backgroundColor: cssVar("--surface"),
                      borderColor: cssVar("--border"),
                      textStyle: { color: cssVar("--text") },
                      formatter: (p: { name: string; value: number }) =>
                        `${p.name}<br/><b>${
                          isPct
                            ? `${p.value.toFixed(1)}%`
                            : `₹${p.value.toLocaleString("en-IN")} ${scale.short}`
                        }</b>`,
                    },
                    animationDuration: 600,
                    animationEasing: "cubicOut",
                    textStyle: { fontFamily: "inherit", color: cssVar("--text-2") },
                    xAxis: {
                      type: "category",
                      data: labels,
                      axisLine: { lineStyle: { color: cssVar("--border-strong") } },
                      axisLabel: { color: cssVar("--text-2") },
                    },
                    yAxis: {
                      type: "value",
                      axisLabel: {
                        color: cssVar("--text-2"),
                        formatter: isPct ? "{value}%" : undefined,
                      },
                      splitLine: { lineStyle: { color: cssVar("--border") } },
                    },
                    series: [
                      {
                        name: shownLabel(shown),
                        type: "bar",
                        barMaxWidth: 36,
                        cursor: "default",
                        // The value on each bar, as design doc 19.1 asks; on a narrow screen the
                        // labels that would collide are dropped (the tooltip still has them).
                        labelLayout: { hideOverlap: true },
                        label: {
                          show: true,
                          position: "top",
                          fontSize: 10,
                          color: cssVar("--text-2"),
                          formatter: (p: { value: number | null }) =>
                            p.value == null
                              ? ""
                              : isPct
                                ? `${p.value.toFixed(1)}%`
                                : p.value.toLocaleString("en-IN", {
                                    maximumFractionDigits: scale.digits,
                                  }),
                        },
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
                        data: points,
                      },
                    ],
                  }}
                />
              </div>
            ) : history.isLoading || filings.isLoading ? (
              <div className="chart-placeholder" />
            ) : (
              <EmptyState icon="bars" title="No quarterly figures yet">
                The chart fills in once two or more quarterly results have been collected for this
                company.
              </EmptyState>
            )}
          </div>
        </div>

        {h && h.lines.length > 0 && (
          <ResultsHistory
            history={h}
            scale={scale}
            excelUrl={api.historyXlsxUrl(symbol, basis === "consolidated", HISTORY_QUARTERS)}
          />
        )}

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
