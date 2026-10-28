import { describe, expect, it } from "vitest";
import type { Filing } from "../api/client";
import { byQuarter, filingLinks, isBlocked, isSuspect } from "./filings";

let next = 1;
const filing = (over: Partial<Filing>): Filing => ({
  id: next++,
  kind: "results_xbrl",
  period_start: null,
  period_end: "2026-09-30",
  period_type: "Q",
  consolidated: true,
  audited: null,
  source_url: null,
  filed_at: "2026-10-08T10:00:00Z",
  status: "validated",
  meta: {},
  revision: null,
  ...over,
});

describe("filingLinks", () => {
  it("keeps iXBRL and PDF web links, drops raw XBRL and imported files", () => {
    const f = filing({
      source_url: "https://nsearchives.nseindia.com/x.xml",
      meta: {
        links: {
          xbrl: "https://nsearchives.nseindia.com/x.xml",
          pdf: "import:file.pdf",
          ixbrl: "https://www.nseindia.com/ixbrl/1",
        },
      },
    });
    expect(filingLinks(f)).toEqual([{ kind: "ixbrl", label: "iXBRL", url: "https://www.nseindia.com/ixbrl/1" }]);
  });
});

describe("byQuarter", () => {
  it("uses the newest filing per quarter and lists what it replaced", () => {
    const old = filing({ filed_at: "2026-10-08T10:00:00Z" });
    const revised = filing({ filed_at: "2026-10-20T10:00:00Z" });
    const { quarters, other } = byQuarter([old, revised], ["2026-09-30"]);
    expect(quarters[0]?.current).toBe(revised);
    expect(quarters[0]?.earlier).toEqual([old]);
    expect(other).toEqual([]);
  });

  it("prefers the quarterly filing over a full-year one ending the same day", () => {
    const year = filing({
      period_end: "2026-03-31",
      period_type: "Y",
      filed_at: "2026-05-01T00:00:00Z",
    });
    const quarter = filing({ period_end: "2026-03-31", filed_at: "2026-04-20T00:00:00Z" });
    const { quarters } = byQuarter([year, quarter], ["2026-03-31"]);
    expect(quarters[0]?.current).toBe(quarter);
    expect(quarters[0]?.earlier).toEqual([year]);
  });

  it("puts filings without a column in other, newest period first", () => {
    const older = filing({ period_end: "2023-06-30" });
    const unread = filing({ period_end: null });
    const shown = filing({});
    const { quarters, other } = byQuarter([older, unread, shown], ["2026-09-30", "2026-12-31"]);
    expect(quarters[0]?.current).toBe(shown);
    expect(quarters[1]).toBeNull();
    expect(other).toEqual([older, unread]);
  });
});

describe("flags", () => {
  it("reads blocked and suspect from the slim meta", () => {
    expect(isBlocked(filing({ meta: { blocks_auto_apply: true } }))).toBe(true);
    expect(isBlocked(filing({}))).toBe(false);
    expect(isSuspect(filing({ meta: { scale: { status: "suspect", power: 2 } } }))).toBe(true);
    expect(isSuspect(filing({ meta: { scale: { status: "corrected" } } }))).toBe(false);
  });
});
