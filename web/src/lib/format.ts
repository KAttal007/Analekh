// Number and date formats shared by the results screens. Values arrive from the API as decimal
// strings in rupees; display is in crore (1 crore = 10 million), Indian digit grouping, IST.
// The Amounts preference (Settings) can switch large amounts to millions instead.

import { readPrefs, type Units } from "./prefs";

export const CRORE = 1e7;
export const MILLION = 1e6;

/** ₹1,056 cr; one decimal below ₹1,000 crore, none above. In millions (₹10,560 mn) when the
 *  Amounts preference says so. */
export function crore(raw: string | number | null | undefined, units?: Units): string {
  if (raw == null || raw === "") return "–";
  const inMillions = (units ?? readPrefs().units) === "million";
  const v = Number(raw) / (inMillions ? MILLION : CRORE);
  const digits = Math.abs(v) < 1000 ? 1 : 0;
  // Millions are grouped in thousands (16,391,170 mn); lakh and crore the Indian way.
  const text = Math.abs(v).toLocaleString(inMillions ? "en-US" : "en-IN", {
    maximumFractionDigits: digits,
    minimumFractionDigits: digits,
  });
  return `${v < 0 ? "−" : ""}₹${text} ${inMillions ? "mn" : "cr"}`; // −₹0.3 cr, not ₹-0.3 cr
}

/** ₹1,211.20: a share price, always two decimals. */
export function price(raw: string | number | null | undefined): string {
  if (raw == null || raw === "") return "–";
  return `₹${Number(raw).toLocaleString("en-IN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

// Small companies are shown in lakhs (1 lakh = 100,000): below ₹10 crore (1,000 lakh) a crore
// scale rounds them to nothing (Agri-Tech: ₹4.6 lakh of revenue read "₹0 cr").
export const LAKH = 1e5;
export const LAKH_BELOW = 10 * CRORE;
export type Scale = { divisor: number; short: string; long: string; digits: number };
export const IN_CRORE: Scale = { divisor: CRORE, short: "cr", long: "crore", digits: 0 };
export const IN_LAKH: Scale = { divisor: LAKH, short: "lakh", long: "lakh", digits: 1 };
export const IN_MILLION: Scale = { divisor: MILLION, short: "mn", long: "million", digits: 0 };

/** One unit for a whole view. By default lakhs when the largest value is under ₹10 crore, else
 *  crore; the Amounts preference can fix crore or millions instead. */
export function scaleFor(values: (string | number | null | undefined)[], units?: Units): Scale {
  const chosen = units ?? readPrefs().units;
  if (chosen === "million") return IN_MILLION;
  if (chosen === "crore") return IN_CRORE;
  const nums = values
    .filter((v) => v != null && v !== "")
    .map((v) => Math.abs(Number(v)))
    .filter(Number.isFinite);
  return nums.length && Math.max(...nums) < LAKH_BELOW ? IN_LAKH : IN_CRORE;
}

/** ₹4.6 lakh / ₹231.4 cr / ₹1,056 cr / −₹0.3 cr, in the given unit. */
export function money(raw: string | number | null | undefined, scale: Scale): string {
  if (raw == null || raw === "") return "–";
  const v = Number(raw) / scale.divisor;
  const digits = scale === IN_LAKH || Math.abs(v) < 1000 ? 1 : 0;
  const text = Math.abs(v).toLocaleString(scale === IN_MILLION ? "en-US" : "en-IN", {
    maximumFractionDigits: digits,
    minimumFractionDigits: digits,
  });
  return `${v < 0 ? "−" : ""}₹${text} ${scale.short}`;
}

// Changes this large only come from a near-zero base (Agri-Tech: revenue of ₹4.6 lakh moved
// its EBITDA margin by -58,307 bps). They are capped for display, with the exact figure in
// changeTitle() for a tooltip, and so stay inside their table cells.
const PCT_CAP = 1000; // growth of 10x or more: direction kept, size not
const BPS_CAP = 10_000; // a margin moving by over 100 percentage points: not meaningful

/** +15.0%, or >+999% / <−999% beyond ten times. */
export function signedPct(raw: string | number | null | undefined, cap = true): string {
  if (raw == null || raw === "") return "–";
  const v = Number(raw);
  if (cap && Math.abs(v) >= PCT_CAP) return v > 0 ? ">+999%" : "<−999%";
  return `${v > 0 ? "+" : ""}${v.toFixed(1)}%`;
}

/** +86 bps, or n.m. beyond 10,000 bps. */
export function signedBps(raw: string | number | null | undefined, cap = true): string {
  if (raw == null || raw === "") return "–";
  const v = Number(raw);
  if (cap && Math.abs(v) >= BPS_CAP) return "n.m.";
  return `${v > 0 ? "+" : ""}${v.toFixed(0)} bps`;
}

/** The exact change, for a tooltip when the displayed one is capped; undefined otherwise. */
export function changeTitle(
  raw: string | number | null | undefined,
  unit: "pct" | "bps",
): string | undefined {
  if (raw == null || raw === "") return undefined;
  const v = Number(raw);
  const capped = unit === "pct" ? Math.abs(v) >= PCT_CAP : Math.abs(v) >= BPS_CAP;
  if (!capped) return undefined;
  const text = v.toLocaleString("en-IN", { maximumFractionDigits: unit === "pct" ? 1 : 0 });
  return `${v > 0 ? "+" : ""}${text}${unit === "pct" ? "%" : " bps"}: from a very small base`;
}

/** 30 Sept 2026 */
export function longDate(iso?: string | null): string {
  if (!iso) return "";
  return new Date(`${iso.slice(0, 10)}T00:00:00`).toLocaleDateString("en-IN", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

/** 16 Oct: a trading day in the current year, with the year otherwise. */
export function shortDate(iso?: string | null, today = new Date()): string {
  if (!iso) return "";
  const d = new Date(`${iso.slice(0, 10)}T00:00:00`);
  return d.toLocaleDateString("en-IN", {
    day: "numeric",
    month: "short",
    ...(d.getFullYear() === today.getFullYear() ? {} : { year: "numeric" }),
  });
}

/** 13 Oct, 9:42 pm, in India time whatever the viewer's clock says. */
export function filedAt(iso?: string | null): string {
  if (!iso) return "–";
  return new Date(iso).toLocaleString("en-IN", {
    timeZone: "Asia/Kolkata",
    day: "numeric",
    month: "short",
    hour: "numeric",
    minute: "2-digit",
  });
}

/** Colour class for a change: green when it's good news, red when bad, none when flat. */
export function tone(raw: string | number | null | undefined, risingIsBad = false): string {
  if (raw == null || raw === "") return "";
  const v = Number(raw);
  if (v === 0) return "";
  return v > 0 !== risingIsBad ? "delta-up" : "delta-down";
}
