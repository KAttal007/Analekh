import type { Filing } from "../api/client";

// Source links for a filing, readable first: NSE's iXBRL web page (the integrated filing) and the
// results PDF. The raw XBRL file is not shown to users (owner's rule, 2026-10-21).
const LINK_KINDS = [
  ["ixbrl", "iXBRL"],
  ["pdf", "PDF"],
] as const;

export type FilingLink = { kind: (typeof LINK_KINDS)[number][0]; label: string; url: string };

export function filingLinks(f: Pick<Filing, "meta">): FilingLink[] {
  const urls = ((f.meta ?? {}).links ?? {}) as Record<string, unknown>;
  return LINK_KINDS.flatMap(([kind, label]): FilingLink[] => {
    const url = urls[kind];
    // Only web links: backfilled files carry "import:<name>", and nothing else is trusted.
    return typeof url === "string" && url.startsWith("https://") ? [{ kind, label, url }] : [];
  });
}

/** A validation check failed: shown as filed, never applied to a model without review. */
export const isBlocked = (f: Pick<Filing, "meta">) => Boolean(f.meta?.blocks_auto_apply);

/** V11 held it back: amounts look a power of ten off, left as filed until checked. */
export const isSuspect = (f: Pick<Filing, "meta">) =>
  (f.meta?.scale as { status?: string } | undefined)?.status === "suspect";

const PERIOD_KIND: Record<string, string> = { Q: "Quarter", H: "Half year", Y: "Full year" };
export const periodKind = (f: Pick<Filing, "period_type">) =>
  PERIOD_KIND[f.period_type ?? ""] ?? "Results";

/** "12 Jan 2026, 6:43 pm" in IST: older filings need the year. */
export function filedOn(iso?: string | null): string {
  if (!iso) return "date not recorded";
  return new Date(iso).toLocaleString("en-IN", {
    timeZone: "Asia/Kolkata",
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

const newestFirst = (a: Filing, b: Filing) =>
  (b.filed_at ?? "").localeCompare(a.filed_at ?? "") || b.id - a.id;

export type QuarterFilings = { current: Filing; earlier: Filing[] };

/** The filing behind each history column and the ones it replaced, plus every filing that has
 *  no column (older quarters, full-year or half-year filings, filings without quarterly figures).
 *  The newest filed is the one in use, as on the server (the same order as `is_latest`); a
 *  quarterly filing wins over a full-year one ending the same day. */
export function byQuarter(
  filings: Filing[],
  ends: string[],
): { quarters: (QuarterFilings | null)[]; other: Filing[] } {
  const columns = new Set(ends);
  const quarters = ends.map((end) => {
    const group = filings.filter((f) => f.period_end === end).sort(newestFirst);
    if (!group.length) return null;
    const current = group.find((f) => f.period_type === "Q") ?? group[0];
    return { current, earlier: group.filter((f) => f !== current) };
  });
  const other = filings
    .filter((f) => !f.period_end || !columns.has(f.period_end))
    .sort((a, b) => (b.period_end ?? "").localeCompare(a.period_end ?? "") || newestFirst(a, b));
  return { quarters, other };
}
