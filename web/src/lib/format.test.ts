import { expect, test } from "vitest";
import {
  IN_CRORE,
  IN_LAKH,
  changeTitle,
  crore,
  money,
  price,
  scaleFor,
  shortDate,
  signedBps,
  signedPct,
} from "./format";

test("companies under ₹10 crore are shown in lakhs, larger ones in crore", () => {
  // Agri-Tech's quarters: ₹3.4 to ₹20.5 lakh of revenue.
  expect(scaleFor(["342000", "2050000", "460000"])).toBe(IN_LAKH);
  expect(scaleFor(["99999999"])).toBe(IN_LAKH); // just under 1,000 lakh
  expect(scaleFor(["100000000"])).toBe(IN_CRORE); // ₹10 crore
  expect(scaleFor(["10556573000"])).toBe(IN_CRORE); // Tata Elxsi
  expect(scaleFor([null, undefined, ""])).toBe(IN_CRORE);
});

test("money keeps the unit, one decimal in lakhs and small crore, and a leading minus", () => {
  expect(money("460000", IN_LAKH)).toBe("₹4.6 lakh");
  expect(money("-3002000", IN_LAKH)).toBe("−₹30.0 lakh");
  expect(money("2314065000", IN_CRORE)).toBe("₹231.4 cr");
  expect(money("10556573000", IN_CRORE)).toBe("₹1,056 cr");
  expect(money(null, IN_CRORE)).toBe("–");
});

test("changes from a tiny base are capped, with the exact figure for the tooltip", () => {
  // Agri-Tech, Q2 FY27: EBITDA margin -58,307 bps QoQ, profit -1,345.6% YoY.
  expect(signedBps("-58307")).toBe("n.m.");
  expect(changeTitle("-58307", "bps")).toBe("-58,307 bps: from a very small base");
  expect(signedPct("-1345.6")).toBe("<−999%");
  expect(signedPct("2400")).toBe(">+999%");
  expect(signedBps("86")).toBe("+86 bps");
  expect(signedPct("15")).toBe("+15.0%");
  expect(changeTitle("15", "pct")).toBeUndefined();
});

test("share prices keep two decimals; market caps read in crore with Indian grouping", () => {
  expect(price("1211.2000")).toBe("₹1,211.20"); // Reliance, 16 Oct 2026
  expect(price("48.5")).toBe("₹48.50");
  expect(price(null)).toBe("–");
  expect(crore("16391169600000.00")).toBe("₹16,39,117 cr");
});

test("a trading day drops the year only when it is this year's", () => {
  const today = new Date("2026-10-17T12:00:00");
  expect(shortDate("2026-10-16", today)).toBe("16 Oct");
  expect(shortDate("2025-12-31", today)).toBe("31 Dec 2025");
});
