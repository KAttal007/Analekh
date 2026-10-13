import { expect, test } from "vitest";
import type { CompanyIndexEntry } from "../api/client";
import { prepareIndex, searchIndex } from "./companySearch";

// Same SYNTHETIC companies and expectations as tests/test_universe.py, so the in-browser search
// and the API rank alike.
const rows: [string, string, string][] = [
  ["TCS", "Tazza Consultancy Services Limited", "INE000T01011"],
  ["TCIEXP", "TCI Express Limited", "INE000T01022"],
  ["TIGER", "Tiger Foods Limited", "INE000T01033"],
  ["MATCHBX", "Matchbox Industries Limited", "INE000M01044"],
  ["OTCX", "Orion Trading Company Limited", "INE000O01055"],
  ["ATLAS", "Atlas Tyres Limited", "INE000A01066"],
  ["ZEDMO", "Zed Motors Limited", "INE000Z01011"],
  ["ZEDPV", "Zed Motors Passenger Vehicles Limited", "INE000Z01022"],
  ["QUICKMOT", "Quick Motors Ltd", "INE000Q01033"],
  ["ZEDAMC", "Zed Asset Management Company Limited", "INE000Z01044"],
];
const index = prepareIndex(
  rows.map(([nse_symbol, name, isin], i): CompanyIndexEntry => ({
    id: i + 1,
    nse_symbol,
    name,
    isin,
    sector: null,
  })),
);
const symbols = (q: string) => searchIndex(index, q).map((c) => c.nse_symbol);

test("one character matches the start of a ticker or name", () => {
  expect(symbols("T")).toEqual(["TCIEXP", "TCS", "TIGER"]);
});

test("two or more characters match anywhere, closest first", () => {
  expect(symbols("TC")).toEqual(["TCIEXP", "TCS", "MATCHBX", "OTCX"]);
  expect(symbols("tcs")).toEqual(["TCS"]);
});

test("words match word starts in any order", () => {
  expect(symbols("zed pass")).toEqual(["ZEDPV"]);
  expect(symbols("passenger zed")).toEqual(["ZEDPV"]);
  expect(symbols("zed motors")).toEqual(["ZEDMO", "ZEDPV"]); // not Quick Motors
  expect(symbols("  zed   pass ")).toEqual(["ZEDPV"]);
});

test("words joined as a ticker, ISIN, and special characters", () => {
  expect(symbols("zed amc")[0]).toBe("ZEDAMC");
  expect(symbols("INE000A01066")).toEqual(["ATLAS"]);
  expect(symbols("zed (pass")).toEqual([]);
  expect(symbols("")).toEqual([]);
});
