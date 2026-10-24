import type { CompanyIndexEntry } from "../api/client";

// In-browser type-ahead over GET /companies/index. Mirrors analekh/universe/search.py tier for
// tier, so results match the API; the server stays the source of truth and handles typos.
//   100 exact ticker or ISIN · 80 ticker starts with · 60 name starts with
//   one character stops there; two or more add:
//   40 every word starts a word of the name · 30 ticker contains · 20 name contains

type Prepared = { entry: CompanyIndexEntry; name: string; symbol: string };
export type CompanyIndex = Prepared[];

export function prepareIndex(entries: CompanyIndexEntry[]): CompanyIndex {
  return entries.map((entry) => ({
    entry,
    name: entry.name.toLowerCase(),
    symbol: entry.nse_symbol.toUpperCase(),
  }));
}

const escape = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

export function searchIndex(index: CompanyIndex, raw: string): CompanyIndexEntry[] {
  const q = raw.split(/\s+/).filter(Boolean).join(" ");
  if (!q) return [];
  const lower = q.toLowerCase();
  const words = lower.split(" ");
  const sym = words.join("").toUpperCase(); // "hdfc amc" -> HDFCAMC
  const long = q.length > 1;
  // Postgres \m: a word starts after anything that is not a letter, digit or underscore.
  // Each word is escaped, so typed text is matched literally (no user-supplied pattern).
  // nosemgrep
  const starts = words.map((w) => new RegExp(`(?<![\\p{L}\\p{N}_])${escape(w)}`, "u"));

  const scored: { entry: CompanyIndexEntry; score: number }[] = [];
  for (const c of index) {
    let score = 0;
    if (c.symbol === sym || c.entry.isin === sym) score = 100;
    else if (c.symbol.startsWith(sym)) score = 80;
    else if (c.name.startsWith(lower)) score = 60;
    else if (long && starts.every((re) => re.test(c.name))) score = 40;
    else if (long && c.symbol.includes(sym)) score = 30;
    else if (long && c.name.includes(lower)) score = 20;
    if (score) scored.push({ entry: c.entry, score });
  }
  scored.sort(
    (a, b) =>
      b.score - a.score ||
      (a.entry.nse_symbol < b.entry.nse_symbol
        ? -1
        : a.entry.nse_symbol > b.entry.nse_symbol
          ? 1
          : 0),
  );
  return scored.map((s) => s.entry);
}
