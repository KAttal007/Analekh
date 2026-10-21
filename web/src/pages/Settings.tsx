import { useMutation, useQuery } from "@tanstack/react-query";
import { type ReactNode, useState } from "react";
import { api, type AlertTest, type JobRun, type Status } from "../api/client";
import { Icon, type IconName } from "../components/Icon";
import { Badge, ErrorNote, PageHeader, Segmented, Skeleton } from "../components/ui";
import { crore, filedAt, shortDate } from "../lib/format";
import { type Prefs, setPrefs, usePrefs } from "../lib/prefs";
import { setTheme, type ThemeChoice, useTheme } from "../lib/theme";

// Settings (design doc 19.1): what the scheduled jobs last did, where alerts go, and display
// preferences. NSE schedules are not editable here: they follow the owner's approvals (rule 1).

const STATUS_FRESH_MS = 30_000;

function bytes(n?: number | null): string {
  if (n == null) return "–";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let v = n;
  let i = 0;
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024;
    i += 1;
  }
  return `${v.toFixed(v < 10 && i > 0 ? 1 : 0)} ${units[i]}`;
}

const count = (n: number) => n.toLocaleString("en-IN");

function StatCard({
  icon,
  label,
  value,
  children,
}: {
  icon: IconName;
  label: string;
  value: ReactNode;
  children?: ReactNode;
}) {
  return (
    <div className="card stat settings-stat">
      <span className="stat-icon">
        <Icon name={icon} />
      </span>
      <div className="settings-stat-body">
        <div className="stat-label">{label}</div>
        <div className="stat-value">{value}</div>
        {children}
      </div>
    </div>
  );
}

/** "ok" -> what it did; "skipped" -> why; "error" -> the error. */
function runSummary(run: JobRun): string | null {
  const s = run.last_summary as Record<string, unknown>;
  if (run.last_status === "error") return `Failed: ${String(s.error ?? "unknown error")}`;
  if (run.last_status === "skipped") return String(s.skipped ?? "skipped");
  return null;
}

function Watcher({ w }: { w: Status["watcher"] }) {
  const ok = w.run.last_ok_summary as Record<string, unknown> | null | undefined;
  const found = typeof ok?.new === "number" ? ok.new : null;
  return (
    <StatCard
      icon="clock"
      label="Results watcher"
      value={w.in_season && w.season ? `In season · ${w.season.quarter_label}` : "Off season"}
    >
      {w.missed_start_at && (
        <Badge tone="warn" title="Nothing was recorded for this start">
          Missed the {filedAt(w.missed_start_at)} run: is the scheduler on?
        </Badge>
      )}
      {w.run.last_status === "error" && <Badge tone="error">{runSummary(w.run)}</Badge>}
      <div className="stat-note">{w.schedule}</div>
      <div className="stat-note">
        Last asked NSE:{" "}
        {w.run.last_ok_at ? (
          <>
            {filedAt(w.run.last_ok_at)}
            {found != null && ` · ${found} new filing${found === 1 ? "" : "s"}`}
          </>
        ) : (
          "not recorded yet"
        )}
      </div>
      {w.run.last_run_at && w.run.last_status === "skipped" && (
        <div className="stat-note">
          Last check {filedAt(w.run.last_run_at)}: {runSummary(w.run)}
        </div>
      )}
      <div className="stat-note">Next ask: {filedAt(w.next_ask_at)}</div>
      {!w.in_season && w.next_season && (
        <div className="stat-note">
          {w.next_season.quarter_label} season opens {shortDate(w.next_season.opens)}
        </div>
      )}
    </StatCard>
  );
}

function Prices({ p }: { p: Status["prices"] }) {
  const why = runSummary(p.run);
  // NSE publishes no file on a market holiday: the job says so for that day, which isn't a fault.
  const summary = p.run.last_summary as Record<string, unknown>;
  const noFile =
    p.run.last_status === "skipped" &&
    summary.day === p.expected_day &&
    String(summary.skipped ?? "").startsWith("no file");
  const behind = (!p.latest_day || p.latest_day < p.expected_day) && !noFile;
  return (
    <StatCard
      icon="rupee"
      label="Closing prices"
      value={p.latest_day ? `${shortDate(p.latest_day)} close` : "None loaded"}
    >
      {behind && (
        <Badge tone="warn" title={why ?? undefined}>
          {shortDate(p.expected_day)} close not loaded yet
        </Badge>
      )}
      {noFile && (
        <div className="stat-note">
          No file for {shortDate(p.expected_day)}: a market holiday, or not published yet
        </div>
      )}
      <div className="stat-note">
        {count(p.priced)} companies · {count(p.with_market_cap)} with a market cap
      </div>
      {p.run.last_run_at && (
        <div className="stat-note">
          Last run {filedAt(p.run.last_run_at)}
          {why && `: ${why}`}
        </div>
      )}
      <div className="stat-note">Weekdays after 19:00 IST; one file per trading day</div>
    </StatCard>
  );
}

function DataStatus() {
  const status = useQuery({
    queryKey: ["status"],
    queryFn: api.status,
    staleTime: STATUS_FRESH_MS,
  });
  const s = status.data;
  return (
    <section className="card">
      <div className="card-header">
        <h2>Data status</h2>
        <div className="actions">
          {s && <span className="muted settings-checked">checked {filedAt(s.checked_at)}</span>}
          <button
            type="button"
            className="btn-sm"
            disabled={status.isFetching}
            onClick={() => void status.refetch()}
          >
            Refresh
          </button>
        </div>
      </div>
      <div className="card-body">
        {status.isError ? (
          <ErrorNote error={status.error} />
        ) : !s ? (
          <div className="stat-grid">
            {[0, 1, 2, 3].map((i) => (
              <Skeleton key={i} height={120} />
            ))}
          </div>
        ) : (
          <div className="stat-grid settings-stats">
            <Watcher w={s.watcher} />
            <Prices p={s.prices} />
            <StatCard icon="database" label="Stored" value={`${count(s.data.companies)} companies`}>
              <div className="stat-note">
                {count(s.data.with_sector)} with a sector · {count(s.data.with_results)} with
                results
              </div>
              <div className="stat-note">
                {count(s.data.filings)} filings · about {count(s.data.values_estimate)} values
              </div>
              {s.data.latest_filed_at && (
                <div className="stat-note">Latest filing {filedAt(s.data.latest_filed_at)}</div>
              )}
              <div className="stat-note">
                Database {bytes(s.data.database_bytes)} · Analekh v{s.version}
              </div>
            </StatCard>
            <StatCard icon="chat" label="AI" value={s.ai_configured ? "Key set" : "No key"}>
              <div className="stat-note">
                The Anthropic API key, for document AI and reports (Phase 3). It stays in .env
                (ANTHROPIC_API_KEY) and never passes through this page.
              </div>
            </StatCard>
          </div>
        )}
      </div>
    </section>
  );
}

function ChannelRow({
  channel,
  label,
  ready,
  detail,
}: {
  channel: "telegram" | "email";
  label: string;
  ready: boolean;
  detail?: string | null;
}) {
  const [result, setResult] = useState<AlertTest | null>(null);
  const test = useMutation({
    mutationFn: () => api.testAlert(channel),
    onMutate: () => setResult(null),
    onSuccess: setResult,
    onError: (e) => setResult({ ok: false, detail: e instanceof Error ? e.message : String(e) }),
  });
  return (
    <li className="settings-row">
      <div className="settings-row-text">
        <strong>{label}</strong>{" "}
        {ready ? <Badge tone="ok">Set up</Badge> : <Badge>Not set up</Badge>}
        <p className="muted">
          {ready
            ? (detail ?? "Ready")
            : channel === "telegram"
              ? "Add TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID to .env and restart the API."
              : "Add SMTP_URL and ALERT_EMAIL_TO to .env and restart the API."}
        </p>
        {result && (
          <p className={result.ok ? "delta-up" : "delta-down"} role="status">
            {result.detail}
          </p>
        )}
      </div>
      <button
        type="button"
        className="btn-sm"
        disabled={!ready || test.isPending}
        onClick={() => test.mutate()}
      >
        {test.isPending ? "Sending…" : "Send test"}
      </button>
    </li>
  );
}

function Alerts() {
  const channels = useQuery({ queryKey: ["alert-channels"], queryFn: api.alertChannels });
  const recent = useQuery({ queryKey: ["alerts"], queryFn: () => api.alerts(20) });
  const c = channels.data;
  return (
    <section className="card">
      <div className="card-header">
        <h2>Alerts</h2>
        <span className="muted">Watchlist companies: results filed, red flags</span>
      </div>
      <div className="card-body settings-alerts">
        {channels.isError ? (
          <ErrorNote error={channels.error} />
        ) : !c ? (
          <Skeleton height={60} />
        ) : (
          <ul className="settings-rows">
            <ChannelRow channel="telegram" label="Telegram" ready={c.telegram} />
            <ChannelRow
              channel="email"
              label="Email"
              ready={c.email}
              detail={c.email_to ? `To ${c.email_to}` : null}
            />
          </ul>
        )}
        <h3 className="settings-sub">Recent alerts</h3>
        {recent.isError ? (
          <ErrorNote error={recent.error} />
        ) : !recent.data ? (
          <Skeleton height={40} />
        ) : recent.data.length ? (
          <ul className="settings-alert-list">
            {recent.data.map((a) => (
              <li key={a.id}>
                <span className="badge-mono">{a.symbol ?? "–"}</span>
                <span className="settings-alert-text">{a.text ?? a.kind}</span>
                <span className="muted">
                  {a.channel && a.channel !== "none" ? a.channel : "not delivered"}
                  {a.sent_at && ` · ${filedAt(a.sent_at)}`}
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="muted">No alerts yet.</p>
        )}
      </div>
    </section>
  );
}

function Choice<T extends string>({
  label,
  hint,
  value,
  options,
  onChange,
}: {
  label: string;
  hint: ReactNode;
  value: T;
  options: { value: T; label: string }[];
  onChange: (v: T) => void;
}) {
  return (
    <li className="settings-row">
      <div className="settings-row-text">
        <strong>{label}</strong>
        <p className="muted">{hint}</p>
      </div>
      <Segmented label={label} options={options} value={value} onChange={onChange} />
    </li>
  );
}

const SAMPLE_CAP = "16391169600000"; // Reliance at the 16 Oct 2026 close

function Display() {
  const prefs = usePrefs();
  const { choice } = useTheme();
  const set =
    <K extends keyof Prefs>(key: K) =>
    (v: Prefs[K]) =>
      setPrefs({ [key]: v });
  return (
    <section className="card">
      <div className="card-header">
        <h2>Display</h2>
        <span className="muted">Saved in this browser</span>
      </div>
      <ul className="card-body settings-rows">
        <Choice<ThemeChoice>
          label="Theme"
          hint="System follows your device's light or dark setting."
          value={choice}
          options={[
            { value: "light", label: "Light" },
            { value: "dark", label: "Dark" },
            { value: "system", label: "System" },
          ]}
          onChange={setTheme}
        />
        <Choice
          label="Amounts"
          hint={
            <>
              Auto shows small companies in lakh and the rest in crore. Example:{" "}
              {crore(SAMPLE_CAP, prefs.units)}.
            </>
          }
          value={prefs.units}
          options={[
            { value: "auto", label: "Auto" },
            { value: "crore", label: "Crore" },
            { value: "million", label: "Million" },
          ]}
          onChange={set("units")}
        />
        <Choice
          label="Company page basis"
          hint="Which results a company page opens on when the company files both."
          value={prefs.basis}
          options={[
            { value: "consolidated", label: "Consolidated" },
            { value: "standalone", label: "Standalone" },
          ]}
          onChange={set("basis")}
        />
        <Choice
          label="Results desk order"
          hint="How the Home page lists the quarter's results."
          value={prefs.deskSort}
          options={[
            { value: "filed", label: "Newest filing" },
            { value: "market_cap", label: "Largest market cap" },
          ]}
          onChange={set("deskSort")}
        />
      </ul>
    </section>
  );
}

export function Settings() {
  return (
    <div className="page settings">
      <PageHeader
        title="Settings"
        subtitle="What the scheduled jobs last did, where alerts go, and how figures are shown."
      />
      <DataStatus />
      <Alerts />
      <Display />
    </div>
  );
}
