import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api, type Filing } from "../api/client";
import { CompanySearch, type Suggestion } from "../components/CompanySearch";
import { Icon, type IconName } from "../components/Icon";
import { Badge, EmptyState, PageHeader, Segmented } from "../components/ui";
import { longDate } from "../lib/format";
import { IpoCoverage } from "./IpoCoverage";

// Reports (design doc 15, 17). The set-up is live: company, report type, quarter and the input
// checks read the real data. Writing the Word note and the PowerPoint is still being built, so

type Kind = "quarterly" | "initiating" | "ipo";

const SECTIONS: Record<Kind, { word: string[]; slides: string[] }> = {
  // The IPO tab has its own sections (IpoCoverage.tsx); these empty lists only keep the map total.
  ipo: { word: [], slides: [] },
  quarterly: {
    word: ["Results highlights", "Concall highlights", "Risks and future guidance", "Investment rationale"],
    slides: ["Results at a glance", "Segment and KPI update", "Concall takeaways", "Outlook and risks"],
  },
  initiating: {
    word: ["Investment summary", "MD&A and business", "Financial performance", "Sector performance", "Company outlook", "Strengths and risks", "Investment rationale"],
    slides: ["Investment summary", "Business model", "Financials", "Valuation context", "Risks"],
  },
};

type InputState = "ready" | "not-linked" | "coming";
const INPUT_ROWS: { key: string; label: string; icon: IconName; coming?: boolean }[] = [
  { key: "results", label: "Filed results", icon: "table" },
  { key: "comps", label: "Comps for the company and its peers", icon: "layers" },
  { key: "model", label: "Your Excel model and its rating", icon: "file" },
  { key: "concall", label: "Concall transcript", icon: "chat", coming: true },
  { key: "ppt", label: "Investor presentation", icon: "sliders", coming: true },
  { key: "mda", label: "Annual report MD&A", icon: "file", coming: true },
  { key: "template", label: "House template", icon: "layers", coming: true },
];

const TONE: Record<InputState, "ok" | "warn" | "neutral"> = {
  ready: "ok",
  "not-linked": "neutral",
  coming: "warn",
};
const TEXT: Record<InputState, string> = {
  ready: "Ready",
  "not-linked": "Not linked",
  coming: "Being built",
};

type Basis = "consolidated" | "standalone" | "both";
const BASIS_OPTIONS: { value: Basis; label: string }[] = [
  { value: "standalone", label: "Standalone" },
  { value: "consolidated", label: "Consolidated" },
  { value: "both", label: "Both" },
];

export function Reports() {
  const [params, setParams] = useSearchParams();
  const symbol = params.get("company") ?? "";
  const requested = params.get("kind");
  const kind: Kind = requested === "initiating" || requested === "ipo" ? requested : "quarterly";
  const asked = params.get("basis");
  const chosenBasis: Basis | null = asked === "standalone" || asked === "consolidated" || asked === "both" ? asked : null;
  const quarter = params.get("quarter");
  const set = (changes: Record<string, string | null>, replace = true) =>
    setParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        for (const [k, v] of Object.entries(changes)) {
          if (v === null || v === "") next.delete(k);
          else next.set(k, v);
        }
        return next;
      },
      { replace },
    );

  const filings = useQuery({
    queryKey: ["filings", symbol],
    queryFn: () => api.filings(symbol),
    enabled: !!symbol,
  });
  const company = useQuery({
    queryKey: ["company", symbol],
    queryFn: () => api.company(symbol),
    enabled: !!symbol,
  });
  const peerLists = useQuery({
    queryKey: ["peer-lists"],
    queryFn: api.peerLists,
    enabled: !!symbol,
  });
  const models = useQuery({ queryKey: ["models"], queryFn: api.models, enabled: !!symbol });
  const dated = (filings.data ?? []).filter((f: Filing) => f.period_end);
  const files = {
    consolidated: dated.some((f) => f.consolidated !== false),
    standalone: dated.some((f) => f.consolidated === false),
  };
  const offered = BASIS_OPTIONS.filter((o) => (o.value === "both" ? files.consolidated && files.standalone : files[o.value]));
  const basis: Basis | null = offered.some((o) => o.value === chosenBasis) ? chosenBasis : (offered[0]?.value ?? null);
  const wantCons = basis === "consolidated" || basis === "both";
  const wantStand = basis === "standalone" || basis === "both";
  const consHistory = useQuery({
    queryKey: ["history", symbol, "consolidated", 12],
    queryFn: () => api.history(symbol, true, 12),
    enabled: !!symbol && wantCons,
  });
  const standHistory = useQuery({
    queryKey: ["history", symbol, "standalone", 12],
    queryFn: () => api.history(symbol, false, 12),
    enabled: !!symbol && wantStand,
  });

  const companyId = company.data?.id;
  const states: Record<string, InputState> = {
    results: basis ? "ready" : "not-linked",
    comps: peerLists.data?.some((l) => l.symbols.includes(symbol)) ? "ready" : "not-linked",
    model: models.data?.some((m) => m.company_id === companyId) ? "ready" : "not-linked",
  };
  const byEnd = new Map<string, string>();
  for (const h of [wantCons && consHistory.data, wantStand && standHistory.data]) {
    if (h) h.quarter_ends.forEach((end, i) => byEnd.set(end, h.quarter_labels[i]));
  }
  const ends = [...byEnd.keys()].sort().reverse();
  const pickedEnd = quarter && byEnd.has(quarter) ? quarter : (ends[0] ?? null);
  const [active, setActive] = useState(0);
  const [wordActive, setWordActive] = useState(0);
  const slides = SECTIONS[kind].slides;
  const cur = Math.min(active, slides.length - 1);
  const sections = SECTIONS[kind].word;
  const wcur = Math.min(wordActive, sections.length - 1);
  const readyCount = INPUT_ROWS.filter((r) => states[r.key] === "ready").length;

  if (kind === "ipo") {
    // IPO coverage has its own inputs (SEBI offer documents), so the company and quarter cards
    // do not apply. Hooks above run for every kind; this early return only changes the layout.
    return (
      <div className="page">
        <PageHeader title="Reports" subtitle="Report types: quarterly update, initiating coverage, IPO coverage." />
        <div className="field">
          Report
          <Segmented<Kind>
            label="Report type"
            options={[
              { value: "quarterly", label: "Quarterly update" },
              { value: "initiating", label: "Initiating coverage" },
              { value: "ipo", label: "IPO coverage" },
            ]}
            value={kind}
            onChange={(v) => set({ kind: v === "quarterly" ? null : v }, false)}
          />
        </div>
        <IpoCoverage />
      </div>
    );
  }

  return (
    <div className="page">
      <PageHeader
        title="Reports"
        badges={<Badge tone="warn">Being built</Badge>}
        subtitle="Draft a Word note and a PowerPoint from a company's filed numbers, its comps and its documents. Every figure in a draft is sourced; you approve it before it leaves your desk."
      />

      <div className="reports-grid">
        <section className="card">
          <div className="card-header">
            <h2>New report</h2>
          </div>
          <div className="card-body reports-form">
            <label className="field">
              Company
              {symbol ? (
                <div className="report-pick">
                  <span className="badge-mono">{symbol}</span>
                  <span>{company.data?.name ?? "Loading…"}</span>
                  <button type="button" className="btn-sm" onClick={() => set({ company: null, basis: null, quarter: null })}>
                    Change
                  </button>
                </div>
              ) : (
                <CompanySearch
                  onPick={(h: Suggestion) => set({ company: h.nse_symbol, basis: null, quarter: null }, false)}
                  shortcut
                  label="Company for the report"
                  placeholder="Search a company by name or ticker"
                />
              )}
            </label>

            <div className="field">
              Report
              <Segmented<Kind>
                label="Report type"
                options={[
                  { value: "quarterly", label: "Quarterly update" },
                  { value: "initiating", label: "Initiating coverage" },
                  { value: "ipo", label: "IPO coverage" },
                ]}
                value={kind}
                onChange={(v) => set({ kind: v === "quarterly" ? null : v }, false)}
              />
              <span className="muted reports-hint">{kind === "quarterly" ? "A short update on one quarter, for the desk." : "A full note on the company, with its valuation context."}</span>
            </div>

            <div className="field">
              Figures
              {offered.length > 1 ? (
                <Segmented<Basis> label="Basis of figures" options={offered} value={basis ?? offered[0].value} onChange={(v) => set({ basis: v }, false)} />
              ) : (
                <span>
                  <Badge>
                    {basis === "consolidated" ? "Consolidated only" : basis === "standalone" ? "Standalone only" : symbol && filings.isSuccess ? "No filed results" : "Pick a company first"}
                  </Badge>
                </span>
              )}
              <span className="muted reports-hint">
                {basis === "both" ? "Consolidated and standalone figures side by side." : offered.length === 1 ? "The only basis this company files." : "The basis every figure in the drafts uses."}
              </span>
            </div>

            <label className="field">
              Quarter
              <select value={pickedEnd ?? ""} onChange={(e) => set({ quarter: e.target.value }, false)} disabled={!ends.length}>
                {ends.length ? (
                  ends.map((end) => (
                    <option key={end} value={end}>
                      {byEnd.get(end)}
                    </option>
                  ))
                ) : (
                  <option value="">{symbol ? "No quarters yet" : "Pick a company first"}</option>
                )}
              </select>
              {pickedEnd && <span className="muted reports-hint">Quarter ended {longDate(pickedEnd)}</span>}
            </label>

            <div className="reports-actions">
              <button type="button" className="btn-primary" disabled aria-describedby="gen-note">
                <Icon name="play" />
                Generate drafts
              </button>
              <span id="gen-note" className="muted reports-hint">
                Drafting is being built. The inputs below are what it will read.
              </span>
            </div>
          </div>
        </section>

        <section className="card">
          <div className="card-header">
            <h2>Inputs</h2>
            <span className="muted">{symbol ? `${readyCount} of ${INPUT_ROWS.length} ready` : "Pick a company first"}</span>
          </div>
          <ul className="report-inputs">
            {INPUT_ROWS.map((r) => {
              const state: InputState | null = r.coming ? "coming" : symbol ? (states[r.key] ?? "not-linked") : null;
              return (
                <li key={r.key}>
                  <Icon name={r.icon} />
                  <span>{r.label}</span>
                  {state ? (
                    <Badge tone={TONE[state]}>
                      {state === "coming" && <span className="pulse-dot" aria-hidden="true" />}
                      {TEXT[state]}
                    </Badge>
                  ) : (
                    <span className="muted">–</span>
                  )}
                </li>
              );
            })}
          </ul>
        </section>
      </div>

      <div className="reports-grid">
        <section className="card">
          <div className="card-header">
            <h2>Word note</h2>
            <span className="muted">{kind === "quarterly" ? "Quarterly update" : "Initiating coverage"}</span>
          </div>
          <div className="slide-deck">
            <div className="slide-main" aria-live="polite">
              <div className="doc-page" data-layout={wcur % 3}>
                <span className="doc-kicker">{kind === "quarterly" ? "Quarterly update" : "Initiating coverage"}</span>
                <span className="doc-heading">{sections[wcur]}</span>
                <span className="pulse-bar" aria-hidden="true" />
                <span className="pulse-bar" aria-hidden="true" />
                <span className="pulse-bar short" aria-hidden="true" />
                <div className="doc-body">
                  <div className="doc-table" aria-hidden="true">
                    {[0, 1, 2].map((i) => (
                      <span key={i} className="pulse-bar" />
                    ))}
                  </div>
                  <span className="pulse-bar" aria-hidden="true" />
                </div>
                <span className="slide-source">
                  Section {wcur + 1} of {sections.length}
                </span>
              </div>
            </div>
            <ol className="slide-list">
              {sections.map((sec, i) => (
                <li key={sec}>
                  <button type="button" className="slide-item" aria-pressed={i === wcur} onClick={() => setWordActive(i)}>
                    <span className="slide-item-no">{i + 1}</span>
                    {sec}
                  </button>
                </li>
              ))}
            </ol>
          </div>
        </section>

        <section className="card">
          <div className="card-header">
            <h2>PowerPoint</h2>
            <span className="muted">Dense IB style, {SECTIONS[kind].slides.length} slides</span>
          </div>
          <div className="slide-deck">
            <div className="slide-main" aria-live="polite">
              <div className="slide-page" data-layout={cur % 3}>
                <div className="slide-page-head">
                  <span className="slide-page-title">{slides[cur]}</span>
                  <span className="slide-no">
                    {cur + 1} / {slides.length}
                  </span>
                </div>
                <span className="pulse-bar wide" aria-hidden="true" />
                <div className="slide-page-body">
                  <div className="wf-chart" aria-hidden="true">
                    {[55, 70, 48, 82, 64, 90].map((h, i) => (
                      <span key={i} style={{ height: `${h}%` }} />
                    ))}
                  </div>
                  <div className="wf-table" aria-hidden="true">
                    {[0, 1, 2, 3, 4].map((i) => (
                      <span key={i} className="pulse-bar" />
                    ))}
                  </div>
                </div>
                <span className="slide-source">Source: company filings, your model</span>
              </div>
            </div>
            <ol className="slide-list">
              {slides.map((s, i) => (
                <li key={s}>
                  <button type="button" className="slide-item" aria-pressed={i === cur} onClick={() => setActive(i)}>
                    <span className="slide-item-no">{i + 1}</span>
                    {s}
                  </button>
                </li>
              ))}
            </ol>
          </div>
        </section>
      </div>

      <section className="card">
        <div className="card-header">
          <h2>Recent reports</h2>
        </div>
        <EmptyState icon="file" title="No reports yet">
          Drafts you generate will be listed here, with their sources and approval status.
        </EmptyState>
      </section>
    </div>
  );
}
