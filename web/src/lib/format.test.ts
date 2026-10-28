import { expect, test } from "vitest";
import { IN_CRORE, IN_LAKH, IN_MILLION, changeTitle, crore, figure, money, plain, price, scaleFor, shortDate, signedBps, signedPct } from "./format";

test("companies under ₹10 crore are shown in lakhs, larger ones in crore", () => {
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

test("crore() is money() in crore or millions, whatever the amount", () => {
  for (const raw of ["0", "460000", "-3002000", "2314065000", "10556573000", "16391169600000", "-512000000"]) {
    expect(crore(raw, "crore")).toBe(money(raw, IN_CRORE));
    expect(crore(raw, "auto")).toBe(money(raw, IN_CRORE));
    expect(crore(raw, "million")).toBe(money(raw, IN_MILLION));
  }
  expect(crore("16391169600000", "million")).toBe("₹16,391,170 mn"); // grouped in thousands
  expect(crore(null, "crore")).toBe("–");
  expect(crore("", "crore")).toBe("–");
});

test("plain() is the table cell: the amount alone, same rounding as money()", () => {
  expect(plain("731880000000", IN_CRORE)).toBe("73,188");
  expect(plain("2314065000", IN_CRORE)).toBe("231.4");
  expect(plain("-125000000", IN_CRORE)).toBe("−12.5");
  expect(plain("460000", IN_LAKH)).toBe("4.6");
  expect(plain("16391169600000", IN_MILLION)).toBe("16,391,170");
  expect(plain(null, IN_CRORE)).toBe("–");
});

test("figure() formats a results line by its kind", () => {
  expect(figure("25.74", "pct", IN_CRORE)).toBe("25.7%");
  expect(figure("38.37", "eps", IN_CRORE)).toBe("₹38.37");
  expect(figure("-2.5", "eps", IN_CRORE)).toBe("−₹2.50");
  expect(figure("731880000000", "inr", IN_CRORE)).toBe("₹73,188 cr");
  expect(figure(null, "inr", IN_CRORE)).toBe("–");
  expect(figure("", "pct", IN_CRORE)).toBe("–");
});

test("signedPct(x, false) is the uncapped change used for quarter on quarter", () => {
  expect(signedPct(1.3, false)).toBe("+1.3%");
  expect(signedPct(-14.7, false)).toBe("-14.7%");
  expect(signedBps(-86)).toBe("-86 bps");
  expect(signedBps(0)).toBe("0 bps");
  expect(signedPct(1500, false)).toBe("+1500.0%"); // not capped
  expect(signedPct(null, false)).toBe("–");
});
