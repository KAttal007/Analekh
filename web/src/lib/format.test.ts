import { expect, test } from "vitest";
import { IN_CRORE, IN_LAKH, changeTitle, money, scaleFor, signedBps, signedPct } from "./format";

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
