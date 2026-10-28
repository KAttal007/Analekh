import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api, type CompRow, type CompsTable, type PeerList } from "../api/client";
import { CompanySearch } from "../components/CompanySearch";
import { Icon } from "../components/Icon";
import { EmptyState, ErrorNote, InfoTip, PageHeader, Segmented, SkeletonTable } from "../components/ui";
import { changeTitle, money, scaleFor, shortDate, signedPct, tone } from "../lib/format";

// Comps (design doc 18): a peer set, its valuation and growth on the latest close and the last

const MAX = 30; // the server's limit per table and per list
type Basis = "auto" | "consolidated" | "standalone";
const BASES: { basis: Basis; label: string; title: string }[] = [
  {
    basis: "auto",
    label: "Auto",
    title: "Consolidated where a company has four consolidated quarters, else standalone",
  },
  { basis: "consolidated", label: "Consolidated", title: "Consolidated first for everyone" },
  { basis: "standalone", label: "Standalone", title: "Standalone first for everyone" },
];
const AS_FLAG: Record<Basis, boolean | null> = {
  auto: null,
  consolidated: true,
  standalone: false,
};

function parseSymbols(raw: string | null): string[] {
  const out: string[] = [];
  for (const s of (raw ?? "").split(",")) {
    const symbol = s.trim().toUpperCase();
    if (symbol && !out.includes(symbol)) out.push(symbol);
  }
  return out.slice(0, MAX);
}

const multiple = (v?: string | null) => (v == null ? null : `${Number(v).toFixed(1)}x`);
const percent = (v?: string | null) => (v == null ? null : `${Number(v).toFixed(1)}%`);

function Blank({ why }: { why: string }) {
  return (
    <span className="muted" title={why}>
      {why.startsWith("Not meaningful") ? "n.m." : "–"}
    </span>
  );
}

function CompsGrid({ table, onRemove }: { table: CompsTable; onRemove: (symbol: string) => void }) {
  const rows = table.rows;
  const scale = scaleFor(rows.flatMap((r) => [r.market_cap, r.ttm_revenue]));
  const stat = (key: string, kind: "pct" | "x" | "chg") => {
    const s = table.stats[key];
    const show = (v?: string | null) => (v == null ? "–" : kind === "x" ? multiple(v) : kind === "pct" ? percent(v) : signedPct(v));
    return { median: show(s?.median), mean: show(s?.mean) };
  };
  const stats = {
    yoy: stat("revenue_yoy", "chg"),
    ebitda: stat("ebitda_margin", "pct"),
    net: stat("pat_margin", "pct"),
    pe: stat("pe", "x"),
    pb: stat("pb", "x"),
  };

  return (
    <div className="table-wrap comps-table">
      <table>
        <thead>
          <tr>
            <th>Company</th>
            <th className="num">Price</th>
            <th className="num">Mkt cap</th>
            <th className="num" title="Last four reported quarters, back to back">
              TTM revenue
            </th>
            <th className="num" title="Latest quarter's revenue on the same quarter a year earlier">
              Rev YoY
            </th>
            <th className="num c-margin" title="TTM; not shown for lenders and insurers">
              EBITDA margin
            </th>
            <th className="num c-margin" title="TTM net profit over TTM revenue">
              Net margin
            </th>
            <th className="num" title="Market cap over TTM net profit">
              P/E
            </th>
            <th className="num" title="Market cap over the latest balance sheet's equity">
              P/B
            </th>
            <th aria-label="Remove" />
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <Row key={r.symbol} r={r} scaleLabel={scale} onRemove={onRemove} />
          ))}
        </tbody>
        {rows.length > 1 && (
          <tfoot>
            {(["median", "mean"] as const).map((k) => (
              <tr key={k} className="comps-stat">
                <td className="comps-stat-label">{k === "median" ? "Median" : "Mean"}</td>
                <td className="c-empty" />
                <td className="c-empty" />
                <td className="c-empty" />
                <td className="num" data-label="rev YoY">
                  {stats.yoy[k]}
                </td>
                <td className="num c-margin" data-label="EBITDA margin">
                  {stats.ebitda[k]}
                </td>
                <td className="num c-margin" data-label="net margin">
                  {stats.net[k]}
                </td>
                <td className="num" data-label="P/E">
                  {stats.pe[k]}
                </td>
                <td className="num" data-label="P/B">
                  {stats.pb[k]}
                </td>
                <td className="c-empty" />
              </tr>
            ))}
          </tfoot>
        )}
      </table>
    </div>
  );
}

function Row({ r, scaleLabel, onRemove }: { r: CompRow; scaleLabel: ReturnType<typeof scaleFor>; onRemove: (symbol: string) => void }) {
  const basis = r.consolidated == null ? null : r.consolidated ? "consolidated" : "standalone";
  const negativeBook = r.book_value != null && Number(r.book_value) <= 0;
  const loss = r.ttm_pat != null && Number(r.ttm_pat) <= 0;
  return (
    <tr>
      <td className="c-co">
        <Link className="desk-company" to={`/companies/${r.symbol}${basis ? `?basis=${basis}` : ""}`}>
          {r.name}
        </Link>
        <span className="desk-ticker">
          <span className="badge-mono">{r.symbol}</span>
          {basis && (
            <>
              {" · "}
              <span title={`${basis} figures`}>{basis === "consolidated" ? "C" : "S"}</span>
            </>
          )}
          {r.quarter_label && <> · to {r.quarter_label}</>}
          {r.notes.length > 0 && <InfoTip text={r.notes.join("; ")} />}
        </span>
      </td>
      <td className="num" data-label="Price" title={r.price_date ? `${shortDate(r.price_date)} close` : undefined}>
        {r.price == null ? <Blank why="No closing price loaded" /> : `₹${Number(r.price).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`}
      </td>
      <td className="num" data-label="Mkt cap">
        {r.market_cap == null ? <Blank why="No share count in its results filings" /> : money(r.market_cap, scaleLabel)}
      </td>
      <td className="num" data-label="TTM revenue">
        {r.ttm_revenue == null ? <Blank why="Fewer than four back-to-back quarters on record" /> : money(r.ttm_revenue, scaleLabel)}
      </td>
      <td className={`num ${tone(r.revenue_yoy)}`} data-label="Rev YoY" title={changeTitle(r.revenue_yoy, "pct")}>
        {r.revenue_yoy == null ? <Blank why="No year-ago quarter on record" /> : signedPct(r.revenue_yoy)}
      </td>
      <td className="num c-margin" data-label="EBITDA margin">
        {percent(r.ebitda_margin) ?? (
          <Blank
            why={r.taxonomy !== "indas" || r.ttm_revenue != null ? "EBITDA isn't meaningful for lenders and insurers, or a quarter lacks a line" : "Fewer than four back-to-back quarters on record"}
          />
        )}
      </td>
      <td className="num c-margin" data-label="Net margin">
        {percent(r.pat_margin) ?? <Blank why="Needs TTM revenue and net profit" />}
      </td>
      <td className="num" data-label="P/E">
        {multiple(r.pe) ?? <Blank why={loss ? "Not meaningful: a loss over the last four quarters" : "Needs market cap and TTM profit"} />}
      </td>
      <td className="num" data-label="P/B" title={r.book_value_at ? `Equity at ${shortDate(r.book_value_at)}` : undefined}>
        {multiple(r.pb) ?? (
          <Blank
            why={
              negativeBook
                ? "Not meaningful: negative equity"
                : r.taxonomy === "insurance" || r.taxonomy === "life_insurance"
                  ? "Book value isn't mapped for insurers yet"
                  : "Needs market cap and a balance sheet"
            }
          />
        )}
      </td>
      <td className="c-remove">
        <button type="button" className="btn-ghost btn-sm icon-btn" aria-label={`Remove ${r.name}`} title="Remove from this comparison" onClick={() => onRemove(r.symbol)}>
          <Icon name="x" size={14} />
        </button>
      </td>
    </tr>
  );
}

function Suggestions({ first, have, onAdd }: { first: string; have: string[]; onAdd: (s: string) => void }) {
  const peers = useQuery({ queryKey: ["peers", first], queryFn: () => api.peers(first, 12) });
  const fresh = (peers.data ?? []).filter((p) => !have.includes(p.symbol)).slice(0, 8);
  if (peers.isLoading) return null;
  if (!peers.data?.length) return <p className="comps-hint muted">No suggestions for {first}: it has no sector on record, or no peers with a market cap.</p>;
  if (!fresh.length) return null;
  return (
    <div className="comps-suggest">
      <span className="muted">Same sector, similar size:</span>
      {fresh.map((p) => (
        <button key={p.symbol} type="button" className="chip chip-add" disabled={have.length >= MAX} title={p.name} onClick={() => onAdd(p.symbol)}>
          <Icon name="plus" size={12} />
          {p.symbol}
        </button>
      ))}
    </div>
  );
}

function SavedLists({ lists, current, onOpen }: { lists: PeerList[]; current: number | null; onOpen: (l: PeerList) => void }) {
  if (!lists.length) return <p className="card-body muted">No saved lists yet. Build a comparison and save it.</p>;
  return (
    <ul className="comps-lists">
      {lists.map((l) => (
        <li key={l.id}>
          <button type="button" className="comps-list-btn" aria-current={l.id === current ? "true" : undefined} onClick={() => onOpen(l)}>
            <span className="comps-list-name">{l.name}</span>
            <span className="muted">{l.symbols.length}</span>
          </button>
        </li>
      ))}
    </ul>
  );
}

export function Comps() {
  const qc = useQueryClient();
  const [params, setParams] = useSearchParams();
  const symbols = parseSymbols(params.get("c"));
  const asked = params.get("basis");
  const basis: Basis = asked === "consolidated" || asked === "standalone" ? asked : "auto";
  const listId = Number(params.get("list")) || null;
  const [name, setName] = useState("");
  const [exportError, setExportError] = useState<unknown>(null);

  const update = (change: { c?: string[]; basis?: Basis; list?: number | null }) => {
    const next = new URLSearchParams(params);
    if (change.c) {
      if (change.c.length) next.set("c", change.c.join(","));
      else next.delete("c");
    }
    if (change.basis) {
      if (change.basis === "auto") next.delete("basis");
      else next.set("basis", change.basis);
    }
    if (change.list !== undefined) {
      if (change.list) next.set("list", String(change.list));
      else next.delete("list");
    }
    setParams(next, { replace: true });
  };
  const add = (symbol: string) => {
    if (!symbols.includes(symbol) && symbols.length < MAX) update({ c: [...symbols, symbol] });
  };
  const remove = (symbol: string) => update({ c: symbols.filter((s) => s !== symbol) });

  const lists = useQuery({ queryKey: ["peer-lists"], queryFn: api.peerLists });
  const current = lists.data?.find((l) => l.id === listId) ?? null;
  const changed = current != null && current.symbols.join(",") !== symbols.join(",");

  const table = useQuery({
    queryKey: ["comps", symbols, basis],
    queryFn: () => api.compsTable(symbols, AS_FLAG[basis]),
    enabled: symbols.length > 0,
    placeholderData: keepPreviousData, // the last table stays up while the next one loads
  });

  const saveNew = useMutation({
    mutationFn: (listName: string) => api.createPeerList(listName, symbols),
    onSuccess: (made) => {
      qc.setQueryData<PeerList[]>(["peer-lists"], (old) => [...(old ?? []), made].sort((a, b) => a.name.localeCompare(b.name)));
      setName("");
      update({ list: made.id });
    },
  });
  const saveChanges = useMutation({
    mutationFn: () => api.updatePeerList(listId as number, { symbols }),
    onSuccess: (saved) => qc.setQueryData<PeerList[]>(["peer-lists"], (old) => (old ?? []).map((l) => (l.id === saved.id ? saved : l))),
  });
  const dropList = useMutation({
    mutationFn: (id: number) => api.deletePeerList(id),
    onSuccess: (_, id) => {
      qc.setQueryData<PeerList[]>(["peer-lists"], (old) => (old ?? []).filter((l) => l.id !== id));
      update({ list: null });
    },
  });
  const exporting = useMutation({
    mutationFn: () => api.compsXlsx(symbols, AS_FLAG[basis]),
    onMutate: () => setExportError(null),
    onError: (e) => setExportError(e),
  });

  const submitName = (e: FormEvent) => {
    e.preventDefault();
    const clean = name.trim();
    if (clean && symbols.length) saveNew.mutate(clean);
  };
  const saveError = saveNew.error ?? saveChanges.error ?? dropList.error;
  const data = table.data;

  return (
    <div className="page comps">
      <PageHeader title="Comps" subtitle="Valuation and growth across a peer set: the latest close and the last four reported quarters." />
      <div className="comps-grid">
        <section className="card comps-side">
          <div className="card-header">
            <h2>Peer lists</h2>
            {(symbols.length > 0 || listId) && (
              <button type="button" className="btn-sm" onClick={() => setParams({}, { replace: true })} title="Start an empty comparison">
                <Icon name="plus" size={13} /> New
              </button>
            )}
          </div>
          {lists.isError ? (
            <div className="card-body">
              <ErrorNote error={lists.error} />
            </div>
          ) : (
            <SavedLists lists={lists.data ?? []} current={listId} onOpen={(l) => setParams({ list: String(l.id), ...(l.symbols.length ? { c: l.symbols.join(",") } : {}) }, { replace: true })} />
          )}
        </section>

        <div className="comps-main">
          <section className="card">
            <div className="card-header">
              <h2>{current ? current.name : "Companies"}</h2>
              <span className="muted">
                {symbols.length} of {MAX}
              </span>
            </div>
            <div className="card-body comps-build">
              {symbols.length > 0 && (
                <ul className="chips" aria-label="Companies in this comparison">
                  {symbols.map((s) => (
                    <li key={s} className="chip">
                      <span className="badge-mono">{s}</span>
                      <button type="button" className="chip-x" aria-label={`Remove ${s}`} onClick={() => remove(s)}>
                        <Icon name="x" size={12} />
                      </button>
                    </li>
                  ))}
                </ul>
              )}
              {symbols.length < MAX ? (
                <CompanySearch onPick={(hit) => add(hit.nse_symbol)} placeholder="Add a company by name or ticker" label="Add a company" exclude={symbols} shortcut />
              ) : (
                <p className="comps-hint muted">A comparison holds up to {MAX} companies.</p>
              )}
              {symbols.length > 0 && <Suggestions first={symbols[0]} have={symbols} onAdd={add} />}
              {symbols.length > 0 && (
                <div className="comps-save">
                  {current && (
                    <>
                      <button type="button" className="btn-primary btn-sm" disabled={!changed || saveChanges.isPending} onClick={() => saveChanges.mutate()}>
                        {changed ? "Save changes" : "Saved"}
                      </button>
                      <button
                        type="button"
                        className="btn-sm btn-ghost"
                        disabled={dropList.isPending}
                        onClick={() => {
                          if (window.confirm(`Delete the list "${current.name}"?`)) dropList.mutate(current.id);
                        }}
                      >
                        Delete list
                      </button>
                    </>
                  )}
                  <form className="comps-name" onSubmit={submitName}>
                    <input aria-label="Name for a new list" placeholder={current ? "Save a copy as…" : "Name this list"} value={name} maxLength={80} onChange={(e) => setName(e.target.value)} />
                    <button type="submit" className="btn-sm" disabled={!name.trim() || saveNew.isPending}>
                      Save as list
                    </button>
                  </form>
                </div>
              )}
              {saveError != null && <ErrorNote error={saveError} />}
            </div>
          </section>

          <section className="card comps-result">
            <div className="card-header">
              <h2>Comparison</h2>
              <div className="comps-tools">
                <Segmented label="Basis" options={BASES.map((b) => ({ value: b.basis, label: b.label, title: b.title }))} value={basis} onChange={(b) => update({ basis: b })} />
                <button type="button" className="btn-sm" disabled={!data?.rows.length || exporting.isPending} onClick={() => exporting.mutate()}>
                  <Icon name="download" size={13} /> Excel
                </button>
              </div>
            </div>
            {exportError != null && (
              <div className="card-body">
                <ErrorNote error={exportError} />
              </div>
            )}
            {!symbols.length ? (
              <div className="card-body">
                <EmptyState icon="bars" title="Start a comparison">
                  Add companies with the box above, or open a saved list. Suggestions from the same sector appear once you add the first one.
                </EmptyState>
              </div>
            ) : table.isError ? (
              <div className="card-body">
                <ErrorNote error={table.error} />
              </div>
            ) : !data ? (
              <SkeletonTable rows={Math.min(symbols.length, 6) + 1} />
            ) : (
              <>
                {data.missing.length > 0 && (
                  <div className="card-body">
                    <div className="alert alert-warn" role="status">
                      <Icon name="alert" />
                      <span>
                        Not in the NSE universe any more (delisted or renamed?): {data.missing.join(", ")}.{" "}
                        <button type="button" className="link-btn" onClick={() => update({ c: symbols.filter((s) => !data.missing.includes(s)) })}>
                          Remove {data.missing.length > 1 ? "them" : "it"}
                        </button>
                      </span>
                    </div>
                  </div>
                )}
                {data.rows.length > 0 && <CompsGrid table={data} onRemove={remove} />}
                <p className="rail-foot comps-foot">
                  {data.as_of && <>Prices at the {shortDate(data.as_of)} close. </>}
                  TTM is the last four reported quarters, back to back; C and S mark consolidated and standalone figures. P/B uses the latest balance sheet's equity. EV/EBITDA arrives once
                  balance-sheet debt and cash are sourced.
                </p>
              </>
            )}
          </section>
        </div>
      </div>
    </div>
  );
}
