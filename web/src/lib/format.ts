import { readPrefs, type Units } from "./prefs";

export const CRORE = 1e7;
export const MILLION = 1e6;

/** ₹1,056 cr; one decimal below ₹1,000 crore, none above. In millions (₹10,560 mn) when the
 *  Amounts preference says so. */
export function crore(raw: string | number | null | undefined, units?: Units): string {
  return money(raw, (units ?? readPrefs().units) === "million" ? IN_MILLION : IN_CRORE);
}

export function price(raw: string | number | null | undefined): string {
  if (raw == null || raw === "") return "–";
  return `₹${Number(raw).toLocaleString("en-IN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

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

/** An amount in the scale's unit, grouped for reading: 73,188 / 231.4 / 4.6. One decimal below
 *  1,000 (and always for lakhs); millions are grouped in thousands (16,391,170), the rest the
 *  Indian way. The sign is returned apart so a caller can put a currency symbol after it. */
function amountText(raw: string | number, scale: Scale): { negative: boolean; text: string } {
  const v = Number(raw) / scale.divisor;
  const digits = scale.short === "lakh" || Math.abs(v) < 1000 ? 1 : 0;
  const text = Math.abs(v).toLocaleString(scale.short === "mn" ? "en-US" : "en-IN", {
    maximumFractionDigits: digits,
    minimumFractionDigits: digits,
  });
  return { negative: v < 0, text };
}

export function money(raw: string | number | null | undefined, scale: Scale): string {
  if (raw == null || raw === "") return "–";
  const { negative, text } = amountText(raw, scale);
  return `${negative ? "−" : ""}₹${text} ${scale.short}`; // −₹0.3 cr, not ₹-0.3 cr
}

export function plain(raw: string | number | null | undefined, scale: Scale): string {
  if (raw == null || raw === "") return "–";
  const { negative, text } = amountText(raw, scale);
  return `${negative ? "−" : ""}${text}`;
}

export function figure(raw: string | number | null | undefined, kind: string, scale: Scale): string {
  if (raw == null || raw === "") return "–";
  const v = Number(raw);
  if (kind === "pct") return `${v.toFixed(1)}%`;
  if (kind === "eps") return `${v < 0 ? "−" : ""}₹${Math.abs(v).toFixed(2)}`;
  return money(raw, scale);
}

const PCT_CAP = 1000; // growth of 10x or more: direction kept, size not
const BPS_CAP = 10_000; // a margin moving by over 100 percentage points: not meaningful

export function signedPct(raw: string | number | null | undefined, cap = true): string {
  if (raw == null || raw === "") return "–";
  const v = Number(raw);
  if (cap && Math.abs(v) >= PCT_CAP) return v > 0 ? ">+999%" : "<−999%";
  return `${v > 0 ? "+" : ""}${v.toFixed(1)}%`;
}

export function signedBps(raw: string | number | null | undefined, cap = true): string {
  if (raw == null || raw === "") return "–";
  const v = Number(raw);
  if (cap && Math.abs(v) >= BPS_CAP) return "n.m.";
  return `${v > 0 ? "+" : ""}${v.toFixed(0)} bps`;
}

export function changeTitle(raw: string | number | null | undefined, unit: "pct" | "bps"): string | undefined {
  if (raw == null || raw === "") return undefined;
  const v = Number(raw);
  const capped = unit === "pct" ? Math.abs(v) >= PCT_CAP : Math.abs(v) >= BPS_CAP;
  if (!capped) return undefined;
  const text = v.toLocaleString("en-IN", { maximumFractionDigits: unit === "pct" ? 1 : 0 });
  return `${v > 0 ? "+" : ""}${text}${unit === "pct" ? "%" : " bps"}: from a very small base`;
}

export function longDate(iso?: string | null): string {
  if (!iso) return "";
  return new Date(`${iso.slice(0, 10)}T00:00:00`).toLocaleDateString("en-IN", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

export function shortDate(iso?: string | null, today = new Date()): string {
  if (!iso) return "";
  const d = new Date(`${iso.slice(0, 10)}T00:00:00`);
  return d.toLocaleDateString("en-IN", {
    day: "numeric",
    month: "short",
    ...(d.getFullYear() === today.getFullYear() ? {} : { year: "numeric" }),
  });
}

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

export function tone(raw: string | number | null | undefined, risingIsBad = false): string {
  if (raw == null || raw === "") return "";
  const v = Number(raw);
  if (v === 0) return "";
  return v > 0 !== risingIsBad ? "delta-up" : "delta-down";
}
