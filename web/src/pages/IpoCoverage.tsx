import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api, ApiError, type IpoDetail, type IpoDraft, type IpoFigure, type IpoIssueRow, type IpoSection } from "../api/client";
import { Badge, EmptyState } from "../components/ui";

// IPO coverage (plan Task 9). Figures come from SEBI offer documents (RHP, then Prospectus).
// Rating and rationale are analyst blanks: rendered, never filled by the AI.

const SECTION_TITLES: Record<string, string> = {
  mdna: "MD&A and financial performance",
  financial_performance: "Financial performance",
  sector_performance: "Sector performance",
  strengths_and_risks: "Strengths and risks",
  valuation: "Valuation context",
};
const SECTION_ORDER = Object.keys(SECTION_TITLES);
const MONEY_LINES = new Set(["eps_basic", "eps_diluted"]);
const LINE_LABELS: Record<string, string> = {
  revenue_from_operations: "Revenue from operations",
  other_income: "Other income",
  total_income: "Total income",
  total_expenses: "Total expenses",
  finance_costs: "Finance costs",
  depreciation: "Depreciation",
  profit_before_tax: "Profit before tax",
  tax_expense: "Tax expense",
  profit_after_tax: "Profit after tax",
  eps_basic: "EPS, basic (Rs per share)",
  eps_diluted: "EPS, diluted (Rs per share)",
  total_assets: "Total assets",
  total_equity: "Total equity",
  total_borrowings: "Total borrowings",
  cash_from_operations: "Cash from operations",
  cash_from_investing: "Cash from investing",
  cash_from_financing: "Cash from financing",
};

type Basis = "consolidated" | "standalone" | "both";

/** Crore for amounts, two decimals; EPS stays as printed. Display only: storage stays Decimal. */
function display(line: string, amount: string): string {
  if (MONEY_LINES.has(line)) return Number(amount).toFixed(2);
  return (Number(amount) / 1e7).toLocaleString("en-IN", { maximumFractionDigits: 2, minimumFractionDigits: 2 });
}

function periodColumns(figures: IpoFigure[]): { label: string; stub: boolean }[] {
  const seen = new Map<string, { label: string; stub: boolean }>();
  for (const f of figures) if (!seen.has(f.period_end)) seen.set(f.period_end, { label: f.period_label, stub: f.is_stub });
  return [...seen.keys()].sort().map((end) => seen.get(end)!);
}

function FinancialsTable({ title, figures }: { title: string; figures: IpoFigure[] }) {
  const columns = periodColumns(figures);
  const lines = [...new Set(figures.map((f) => f.line))].sort((a, b) => Object.keys(LINE_LABELS).indexOf(a) - Object.keys(LINE_LABELS).indexOf(b));
  if (!figures.length) return <p className="muted">No {title.toLowerCase()} figures in this document.</p>;
  return (
    <div className="ipo-table-wrap">
      <h3>{title}</h3>
      <table className="ipo-table">
        <thead>
          <tr>
            <th>Line</th>
            {columns.map((c) => (
              <th key={c.label}>
                {c.label}
                {c.stub ? <Badge>stub</Badge> : null}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {lines.map((line) => (
            <tr key={line}>
              <th scope="row">{LINE_LABELS[line] ?? line}</th>
              {columns.map((c) => {
                const cell = figures.find((f) => f.line === line && f.period_label === c.label);
                return <td key={c.label}>{cell ? display(line, cell.amount) : "-"}</td>;
              })}
            </tr>
          ))}
        </tbody>
      </table>
      <p className="muted">Amounts in rupees crore; EPS in rupees per share.</p>
    </div>
  );
}

function SectionCard({ sectionKey, section }: { sectionKey: string; section: IpoSection }) {
  return (
    <article className="ipo-section">
      <h3>
        {SECTION_TITLES[sectionKey]}
        {section.blocked ? <Badge tone="error">Blocked: unmatched numbers</Badge> : null}
        {section.style_issues.length ? <Badge tone="warn">Check dashes</Badge> : null}
      </h3>
      {section.blocked ? (
        <>
          <p>Numbers not found in the document or in calc: {section.unmatched.join(", ") || "none listed"}</p>
          <pre className="ipo-draft-text">{section.text}</pre>
        </>
      ) : (
        <p className="ipo-draft-text">{section.text}</p>
      )}
    </article>
  );
}

function Draft({ draft }: { draft: IpoDraft }) {
  return (
    <section className="ipo-draft" aria-label="Draft">
      <p className="muted">Drafted from the {draft.stage === "prospectus" ? "Prospectus" : "RHP"}.</p>
      {SECTION_ORDER.map((key) => {
        const section = draft.sections[key];
        return section ? <SectionCard key={key} sectionKey={key} section={section} /> : null;
      })}
      <div className="ipo-blank" data-testid="rating">
        <strong>Rating:</strong> <span className="ipo-placeholder">{draft.rating}</span>
      </div>
      <div className="ipo-blank" data-testid="rationale">
        <strong>Rationale:</strong> <span className="ipo-placeholder">{draft.rationale}</span>
      </div>
    </section>
  );
}

function Financials({ detail, basis }: { detail: IpoDetail; basis: Basis }) {
  const showCons = basis === "consolidated" || basis === "both";
  const showStand = basis === "standalone" || basis === "both";
  return (
    <>
      {showCons ? <FinancialsTable title="Consolidated" figures={detail.financials.consolidated} /> : null}
      {showStand ? <FinancialsTable title="Standalone" figures={detail.financials.standalone} /> : null}
      {detail.restatements.length ? (
        <section className="ipo-restatements">
          <h3>Restated since the RHP</h3>
          <ul>
            {detail.restatements.map((r) => (
              <li key={`${r.basis}-${r.period_end}-${r.line}`}>
                {r.basis}, {r.period_end}, {LINE_LABELS[r.line] ?? r.line}: {display(r.line, r.old)} to {display(r.line, r.new)}
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </>
  );
}

export function IpoCoverage() {
  const qc = useQueryClient();
  const [picked, setPicked] = useState<number | null>(null);
  const [basisChoice, setBasisChoice] = useState<Basis | null>(null);
  const [symbolDraft, setSymbolDraft] = useState("");
  const [genError, setGenError] = useState<string | null>(null);

  const issues = useQuery({ queryKey: ["ipo-issues"], queryFn: api.ipoIssues });
  const selected: IpoIssueRow | undefined = (issues.data ?? []).find((i) => i.id === picked) ?? issues.data?.[0];
  const detail = useQuery({
    queryKey: ["ipo-issue", selected?.id],
    queryFn: () => api.ipoIssue(selected!.id),
    enabled: !!selected,
  });
  const coverage = useQuery({
    queryKey: ["ipo-coverage", selected?.id],
    enabled: !!selected,
    queryFn: async () => {
      try {
        return await api.ipoCoverage(selected!.id);
      } catch (err) {
        if (err instanceof ApiError && err.status === 404) return null;
        throw err;
      }
    },
  });
  const generate = useMutation({
    mutationFn: () => api.generateIpoCoverage(selected!.id),
    onSuccess: (draft) => {
      setGenError(null);
      qc.setQueryData(["ipo-coverage", selected!.id], draft);
    },
    onError: (err) => setGenError(err instanceof Error ? err.message : "Could not generate the draft."),
  });
  const saveSymbol = useMutation({
    mutationFn: () => api.setIpoSymbol(selected!.id, symbolDraft.trim()),
    onSuccess: () => {
      setSymbolDraft("");
      void qc.invalidateQueries({ queryKey: ["ipo-issues"] });
    },
  });

  if (issues.isPending) return <p className="muted">Loading IPOs…</p>;
  if (!issues.data?.length) {
    return <EmptyState title="No IPO offer documents yet">SEBI's RHP and Prospectus lists are read once a day.</EmptyState>;
  }

  const hasBoth = !!detail.data && detail.data.financials.consolidated.length > 0 && detail.data.financials.standalone.length > 0;
  const basis: Basis = basisChoice ?? (hasBoth ? "both" : detail.data?.financials.standalone.length ? "standalone" : "consolidated");
  const canGenerate = !!selected?.current_stage;
  const draft = generate.data ?? coverage.data ?? null;

  return (
    <div className="ipo">
      <label className="field">
        IPO
        <select value={selected?.id ?? ""} onChange={(e) => setPicked(Number(e.target.value))}>
          {issues.data.map((i) => (
            <option key={i.id} value={i.id}>
              {i.name}
              {i.current_stage ? ` (${i.current_stage === "prospectus" ? "Prospectus" : "RHP"})` : ""}
            </option>
          ))}
        </select>
      </label>

      {selected ? (
        <p className="muted">
          NSE symbol: {selected.company_symbol ?? "not yet assigned"}.
          <label>
            {" "}
            <input value={symbolDraft} onChange={(e) => setSymbolDraft(e.target.value)} placeholder="e.g. JIOFIN" aria-label="NSE symbol" />
          </label>{" "}
          <button type="button" className="btn-sm" disabled={!symbolDraft.trim() || saveSymbol.isPending} onClick={() => saveSymbol.mutate()}>
            Save symbol
          </button>
        </p>
      ) : null}

      {detail.data ? (
        <>
          <label className="field">
            Figures
            <select value={basis} onChange={(e) => setBasisChoice(e.target.value as Basis)} aria-label="Basis of figures">
              {hasBoth ? <option value="both">Both</option> : null}
              <option value="consolidated">Consolidated</option>
              <option value="standalone">Standalone</option>
            </select>
          </label>
          <Financials detail={detail.data} basis={basis} />
        </>
      ) : null}

      <div className="ipo-generate">
        <button type="button" className="btn" disabled={!canGenerate || generate.isPending} onClick={() => generate.mutate()}>
          Generate coverage
        </button>
        {!canGenerate ? <span className="muted"> Waits for an offer document to be read.</span> : null}
        {genError ? <p role="alert">{genError}</p> : null}
      </div>

      {draft ? <Draft draft={draft} /> : null}
    </div>
  );
}
