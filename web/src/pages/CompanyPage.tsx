import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import ReactECharts from "echarts-for-react";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "../api/client";
import { Icon } from "../components/Icon";
import {
  Avatar,
  Badge,
  EmptyState,
  ErrorNote,
  Loading,
  PageHeader,
  StatusBadge,
} from "../components/ui";
import { useTheme } from "../lib/theme";

const REVENUE = "RevenueFromOperations";
const CRORE = 1e7;

const cssVar = (name: string) =>
  getComputedStyle(document.documentElement).getPropertyValue(name).trim();
const crore = (v: number) =>
  `₹${(v / CRORE).toLocaleString("en-IN", { maximumFractionDigits: 0 })} cr`;

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
  const company = useQuery({ queryKey: ["company", symbol], queryFn: () => api.company(symbol) });
  const filings = useQuery({ queryKey: ["filings", symbol], queryFn: () => api.filings(symbol) });
  const revenue = useQuery({
    queryKey: ["facts", symbol, REVENUE],
    queryFn: () => api.facts(symbol, REVENUE),
  });
  const watch = useMutation({
    mutationFn: async () => {
      if (company.data?.watched) await api.unwatch(symbol);
      else await api.watch(symbol);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["company", symbol] }),
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
    .filter((f) => f.period_start && f.consolidated)
    .sort((a, b) => a.period_end.localeCompare(b.period_end));
  const latest = quarters.at(-1);
  const previous = quarters.at(-2);
  const rows = filings.data ?? [];
  const coverage = COVERAGE[c.coverage_level as keyof typeof COVERAGE] ?? COVERAGE.universe;
  const qoq =
    latest && previous && Number(previous.value)
      ? (Number(latest.value) / Number(previous.value) - 1) * 100
      : null;

  return (
    <div className="page">
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
            {c.results_taxonomy && <Badge>{c.results_taxonomy}</Badge>}
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

      <div className="stat-grid">
        <div className="card card-hover stat">
          <span className="stat-icon">
            <Icon name="rupee" />
          </span>
          <div>
            <div className="stat-label">Revenue, latest quarter</div>
            <div className="stat-value">{latest ? crore(Number(latest.value ?? 0)) : "–"}</div>
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
            <div className="stat-note">Consolidated revenue from operations</div>
          </div>
        </div>
        <div className="card card-hover stat">
          <span className="stat-icon">
            <Icon name="file" />
          </span>
          <div>
            <div className="stat-label">Filings</div>
            <div className="stat-value">{rows.length}</div>
            <div className="stat-note">Results filings received</div>
          </div>
        </div>
        <div className="card card-hover stat">
          <span className="stat-icon">
            <Icon name="hash" />
          </span>
          <div>
            <div className="stat-label">Face value</div>
            <div className="stat-value">{c.face_value ? `₹${Number(c.face_value)}` : "–"}</div>
            <div className="stat-note">Per share</div>
          </div>
        </div>
      </div>

      <div className="card">
        <div className="card-header">
          <h2>Revenue by quarter</h2>
          <span className="muted">₹ crore · consolidated</span>
        </div>
        <div className="card-body">
          {quarters.length > 1 ? (
            <ReactECharts
              key={theme}
              style={{ height: 280 }}
              option={{
                grid: { left: 48, right: 16, top: 16, bottom: 32 },
                tooltip: {
                  trigger: "axis",
                  backgroundColor: cssVar("--surface"),
                  borderColor: cssVar("--border"),
                  textStyle: { color: cssVar("--text") },
                  axisPointer: { type: "shadow", shadowStyle: { color: cssVar("--accent-soft") } },
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
                    name: "Revenue",
                    type: "bar",
                    barMaxWidth: 36,
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
                    data: quarters.map((f) => Math.round(Number(f.value ?? 0) / CRORE)),
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

      <div className="card">
        <div className="card-header">
          <h2>Filings</h2>
          <span className="muted">{rows.length} received</span>
        </div>
        {rows.length ? (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Period end</th>
                  <th>Kind</th>
                  <th>Basis</th>
                  <th>Status</th>
                  <th>Checks</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((f) => (
                  <tr key={f.id}>
                    <td>{f.period_end ?? "-"}</td>
                    <td>{f.kind}</td>
                    <td>
                      {f.consolidated == null
                        ? "-"
                        : f.consolidated
                          ? "Consolidated"
                          : "Standalone"}
                    </td>
                    <td>
                      <StatusBadge status={f.status} />
                    </td>
                    <td>
                      {f.meta?.blocks_auto_apply ? (
                        <Badge tone="error">blocked</Badge>
                      ) : (
                        <Badge tone="ok">passed</Badge>
                      )}
                    </td>
                  </tr>
                ))}
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
  );
}
