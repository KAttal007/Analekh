import { expect, test } from "vitest";
import { revisionText } from "./RevisionTag";

test("a restated quarter lists what changed, old to new", () => {
  const text = revisionText(
    {
      status: "revised",
      replaces: "2026-11-10T12:00:00Z",
      superseded_by: null,
      changes: [
        { label: "Revenue", kind: "inr", old: "1000000000", new: "1010000000", change: "1.0" },
        { label: "EBITDA margin", kind: "pct", old: "20.0", new: "19.5", change: "-50" },
      ],
      replaced_period: null,
    },
    "2026-11-20T12:00:00Z",
  );
  expect(text).toContain("Revised filing");
  expect(text).toContain("Revenue: ₹100.0 cr → ₹101.0 cr (+1.0%)");
  expect(text).toContain("EBITDA margin: 20.0% → 19.5% (-50 bps)");
});

test("a revision after half-year results says it adds the quarter", () => {
  const text = revisionText({
    status: "revised",
    replaces: "2026-04-27T15:56:11Z",
    superseded_by: null,
    changes: [],
    replaced_period: ["2025-10-01", "2026-03-31"],
  });
  expect(text).toContain("adds the quarter's own figures");
});

test("the replaced filing says it is history", () => {
  const text = revisionText({
    status: "original",
    replaces: null,
    superseded_by: "2026-05-01T14:47:20Z",
    changes: [],
    replaced_period: null,
  });
  expect(text).toMatch(/^Superseded/);
});
