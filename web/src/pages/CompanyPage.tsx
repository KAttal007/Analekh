import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import ReactECharts from "echarts-for-react";
import { useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { api, type CompanyDetail, type HistoryLine, type WatchlistEntry } from "../api/client";
import { Icon } from "../components/Icon";
import { QuarterRail } from "../components/QuarterRail";
import { ResultsHistory } from "../components/ResultsHistory";
import { Avatar, Badge, EmptyState, ErrorNote, Loading, PageHeader, Segmented } from "../components/ui";
import { companyQuery } from "../lib/preload";
import { crore, money, price, scaleFor, shortDate, signedPct, tone } from "../lib/format";
import { usePrefs } from "../lib/prefs";
import { useTheme } from "../lib/theme";
import { ReadOnlyBanner } from "../lock/ReadOnlyBanner";
import { lockedDetail } from "../lock/useModelLock";

const TOP_LINE: Record<string, { short: string; full: string }> = {
  banking: { short: "Interest earned", full: "interest earned" },
  insurance: { short: "Premium earned", full: "premium earned" },
  life_insurance: { short: "Net premium", full: "net premium income" },
};
const topLine = (taxonomy?: string | null) => TOP_LINE[taxonomy ?? ""] ?? { short: "Revenue", full: "revenue from operations" };

const CHART_KEYS = ["revenue", "pat", "ebitda_margin", "cpppm", "nim", "net_margin", "oplev"];
const CHART_LABEL: Record<string, string> = {
  pat: "Net profit",
  ebitda_margin: "EBITDA margin",
  cpppm: "Core pre-provision profit margin",
  oplev: "Operating leverage",
  nim: "Net interest margin",
  net_margin: "Net margin",
};
const INTEREST = "interest"; // the stacked yield / cost of borrowing / spread view
const INTEREST_LABEL = "Interest ratios";
const pctDigits = (key: string) => (key === "nim" ? 2 : 1);
const HISTORY_QUARTERS = 12;

type Basis = "consolidated" | "standalone";
const BASES: { basis: Basis; label: string }[] = [
  { basis: "consolidated", label: "Consolidated" },
  { basis: "standalone", label: "Standalone" },
];

const cssVar = (name: string) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

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
  const history = useQuery({
    queryKey: ["history", symbol, basis],
    queryFn: () => api.history(symbol, basis === "consolidated", HISTORY_QUARTERS),
    enabled: filings.isSuccess,
  });
  const [metric, setMetric] = useState("revenue");
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
      if (updated) qc.setQueryData(["company", symbol], updated);
      else {
        qc.setQueryData<CompanyDetail>(["company", symbol], (old) => (old ? { ...old, watched: false } : old));
        qc.setQueryData<WatchlistEntry[]>(["watchlist"], (old) => old?.filter((w) => w.symbol !== symbol));
      }
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
  const startLocked = lockedDetail(start.error);

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
  const scale = scaleFor(topValues);
  const chartLines = CHART_KEYS.map((k) => byKey.get(k)).filter((l): l is HistoryLine => l !== undefined);
  const margins = chartLines.filter((l) => l.key !== "revenue" && l.key !== "pat" && l.key !== "oplev");
  const choices = [...chartLines.filter((l) => l.key === "revenue" || l.key === "pat"), ...margins.slice(0, 1), ...chartLines.filter((l) => l.key === "oplev")];
  const ratios = {
    yield: byKey.get("yield"),
    cob: byKey.get("cob"),
    spread: byKey.get("spread"),
  };
  const hasRatios = !!(ratios.yield && ratios.cob && ratios.spread);
  const interestShown = hasRatios && metric === INTEREST;
  const shown = interestShown ? undefined : (choices.find((l) => l.key === metric) ?? choices[0]);
  const isPct = interestShown || shown?.kind === "pct";
  const digits = shown ? pctDigits(shown.key) : 2;
  const points = (shown?.values ?? []).map((v) => (v == null ? null : isPct ? Number(v) : Number((Number(v) / scale.divisor).toFixed(scale.digits))));
  const shownLabel = (l: HistoryLine) => (l.key === "revenue" ? topLine(c.results_taxonomy).short : (CHART_LABEL[l.key] ?? l.label));
  const chartTitle = interestShown ? INTEREST_LABEL : shown ? shownLabel(shown) : topLine(c.results_taxonomy).short;
  const chartOptions = [...choices.map((l) => ({ value: l.key, label: shownLabel(l) })), ...(hasRatios ? [{ value: INTEREST, label: INTEREST_LABEL }] : [])];
  const rows = allFilings.filter((f) => (basis === "consolidated") === (f.consolidated !== false));
  const coverage = COVERAGE[c.coverage_level as keyof typeof COVERAGE] ?? COVERAGE.universe;
  const qoq = latest?.value != null && previous != null && Number(previous) ? (Number(latest.value) / Number(previous) - 1) * 100 : null;

  return (
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
                <span title="Sectors come from NSE Indices' published lists (about 750 companies) or your own sector map.">Sector not mapped yet</span>
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
              <button className={c.watched ? "btn-on" : undefined} aria-pressed={c.watched} onClick={() => watch.mutate()} disabled={watch.isPending}>
                <Icon name="star" />
                {c.watched ? "Watching" : "Watch"}
              </button>
              <button
                onClick={() => analyse.mutate()}
                disabled={analyse.isPending || jobsDown}
                title={jobsDown ? (jobs.data?.detail ?? undefined) : "Collect history and read the documents in the background"}
                aria-describedby={jobsDown ? "analyse-note" : undefined}
              >
                <Icon name="play" />
                Analyse
              </button>
              <button className="btn-primary" onClick={() => start.mutate()} disabled={start.isPending}>
                Start coverage
              </button>
            </>
          }
        />
        {jobsDown && (
          <p id="analyse-note" className="muted action-note">
            Analyse runs as a background job, and the job queue isn't running on this machine yet (it comes with hosting). Watch and Start coverage work now.
          </p>
        )}
        {analyse.data && (
          <div className="alert alert-warn">
            <Icon name="clock" />
            <span>Analysis job {analyse.data.status}.</span>
          </div>
        )}
        {analyse.isError && <ErrorNote error={analyse.error} />}
        {startLocked ? <ReadOnlyBanner holderName={startLocked.holder_name} takenAt={startLocked.taken_at} /> : start.isError && <ErrorNote error={start.error} />}

        {allFilings.length > 0 && (
          <div className="basis-bar">
            <span className="muted">Figures</span>
            {filed.consolidated && filed.standalone ? (
              <Segmented label="Basis of figures" options={BASES.map((b) => ({ value: b.basis, label: b.label }))} value={basis} onChange={(b) => setParams({ basis: b }, { replace: true })} />
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
              <div className={qoq === null ? "stat-value" : `stat-value ${qoq < 0 ? "delta-down" : "delta-up"}`}>{signedPct(qoq, false)}</div>
              <div className="stat-note">
                {basis === "standalone" ? "Standalone" : "Consolidated"} {topLine(c.results_taxonomy).full}
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
                {quote.data?.change_pct != null && <span className={`stat-delta ${tone(quote.data.change_pct)}`}>{signedPct(quote.data.change_pct)}</span>}
              </div>
              <div className="stat-note">
                {quote.data ? `${shortDate(quote.data.trade_date)} close` : quote.isSuccess ? "No closing price loaded yet" : ""}
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
              <div className="stat-note" title="Closing price × shares in issue (paid-up equity capital ÷ face value, from the latest results filing)">
                {quote.data?.market_cap != null ? `At the ${shortDate(quote.data.trade_date)} close` : quote.data ? "No share count in its results filings yet" : ""}
              </div>
            </div>
          </div>
        </div>

        <div className="card area-chart">
          <div className="card-header">
            <h2>{chartTitle} by quarter</h2>
            <div className="actions">
              {chartOptions.length > 1 && <Segmented label="Chart shows" options={chartOptions} value={interestShown ? INTEREST : shown?.key} onChange={setMetric} />}
              <span className="muted">
                {isPct ? "%" : `₹ ${scale.long}`} · {basis}
              </span>
            </div>
          </div>
          <div className="card-body">
            {labels.length > 1 && interestShown ? (
              <div
                role="img"
                aria-label={`${INTEREST_LABEL} by quarter, ${labels[0]} to ${labels.at(-1)}: cost of borrowing with the spread stacked on it up to the yield; the same figures are in the results history table below`}
              >
                <InterestChart key={theme} labels={labels} yieldLine={ratios.yield!} cobLine={ratios.cob!} spreadLine={ratios.spread!} />
              </div>
            ) : labels.length > 1 && shown ? (
              <div role="img" aria-label={`${shownLabel(shown)} by quarter, ${labels[0]} to ${labels.at(-1)}; the same figures are in the results history table below`}>
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
                      formatter: (p: { name: string; value: number }) => `${p.name}<br/><b>${isPct ? `${p.value.toFixed(digits)}%` : `₹${p.value.toLocaleString("en-IN")} ${scale.short}`}</b>`,
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
                                ? `${p.value.toFixed(digits)}%`
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
                The chart fills in once two or more quarterly results have been collected for this company.
              </EmptyState>
            )}
          </div>
        </div>

        {/* The filings live in the history table now: each quarter's heading links to its
            filing, and filings without a column are listed under it. */}
        {h && (h.lines.length > 0 || rows.length > 0) && <ResultsHistory history={h} filings={rows} scale={scale} excelUrl={api.historyXlsxUrl(symbol, basis === "consolidated", HISTORY_QUARTERS)} />}
      </div>

      <QuarterRail symbol={symbol} consolidated={basis === "consolidated"} ready={filings.isSuccess} />
    </div>
  );
}

function InterestChart({ labels, yieldLine, cobLine, spreadLine }: { labels: string[]; yieldLine: HistoryLine; cobLine: HistoryLine; spreadLine: HistoryLine }) {
  const num = (v: string | null | undefined) => (v == null ? null : Number(v));
  const yields = yieldLine.values.map(num);
  const costs = cobLine.values.map(num);
  const spreads = spreadLine.values.map(num);
  const pct = (v: number | null) => (v == null ? "–" : `${v.toFixed(2)}%`);
  const tooltipRow = (label: string, v: number | null, color?: string) => `${label}: <b${color ? ` style="color:${color}"` : ""}>${pct(v)}</b>`;
  return (
    <ReactECharts
      style={{ height: 320 }}
      option={{
        media: [
          {
            query: { maxWidth: 520 },
            option: {
              grid: { left: 40, right: 8 },
              series: [
                { label: { show: false } },
                { label: { show: false } },
                {
                  symbolSize: [14, 2],
                  label: {
                    fontSize: 9,
                    formatter: (p: { value: number | null }) => (p.value == null ? "" : p.value.toFixed(1)),
                  },
                },
              ],
            },
          },
        ],
        grid: { left: 48, right: 16, top: 40, bottom: 56 },
        legend: {
          bottom: 0,
          textStyle: { color: cssVar("--text-2") },
          data: ["Cost of borrowing", "Spread", "Yield"],
        },
        tooltip: {
          trigger: "axis",
          axisPointer: { type: "shadow" },
          confine: true,
          backgroundColor: cssVar("--surface"),
          borderColor: cssVar("--border"),
          textStyle: { color: cssVar("--text") },
          formatter: (ps: { dataIndex: number; name: string }[]) => {
            const i = ps[0]?.dataIndex ?? 0;
            const s = spreads[i];
            if (yields[i] == null && costs[i] == null) return `${ps[0]?.name}<br/>Not yet: needs the next half-year's balance sheet`;
            return [ps[0]?.name, tooltipRow("Yield", yields[i]), tooltipRow("Cost of borrowing", costs[i]), tooltipRow("Spread", s, s != null && s < 0 ? cssVar("--negative") : undefined)].join(
              "<br/>",
            );
          },
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
          axisLabel: { color: cssVar("--text-2"), formatter: "{value}%" },
          splitLine: { lineStyle: { color: cssVar("--border") } },
        },
        series: [
          {
            name: "Cost of borrowing",
            type: "bar",
            stack: "yield",
            barMaxWidth: 36,
            cursor: "default",
            itemStyle: { color: cssVar("--border-strong") },
            label: {
              show: true,
              position: "inside",
              fontSize: 10,
              color: cssVar("--text"),
              formatter: (p: { value: number | null }) => (p.value == null ? "" : p.value.toFixed(2)),
            },
            data: costs,
          },
          {
            name: "Spread",
            type: "bar",
            stack: "yield",
            barMaxWidth: 36,
            cursor: "default",
            itemStyle: { color: cssVar("--accent"), borderRadius: [4, 4, 0, 0] },
            label: {
              show: true,
              position: "inside",
              fontSize: 10,
              color: cssVar("--on-accent"),
              formatter: (p: { value: number | null }) => (p.value == null ? "" : p.value.toFixed(2)),
            },
            data: spreads.map((s) => (s != null && s >= 0 ? s : null)),
          },
          {
            name: "Yield",
            type: "scatter",
            symbol: "rect",
            symbolSize: [30, 2],
            cursor: "default",
            itemStyle: { color: cssVar("--text") },
            label: {
              show: true,
              position: "top",
              fontSize: 10,
              color: cssVar("--text-2"),
              formatter: (p: { value: number | null }) => (p.value == null ? "" : `${p.value.toFixed(2)}%`),
            },
            labelLayout: { hideOverlap: true },
            data: yields,
            z: 3,
          },
        ],
      }}
    />
  );
}
