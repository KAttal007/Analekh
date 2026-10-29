import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";
import { mockApi, renderAt } from "../test-utils";
import { IpoCoverage } from "./IpoCoverage";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

const figure = (basis: string, end: string, label: string, line: string, amount: string, stub = false) => ({
  basis,
  period_end: end,
  period_label: label,
  is_stub: stub,
  line,
  amount,
  unit: "INR",
  page: 40,
  flagged: false,
});

const issue = (over: Record<string, unknown> = {}) => ({
  id: 7,
  name: "Jio Platforms Limited",
  stages: ["rhp", "prospectus"],
  current_stage: "prospectus",
  status: "extracted",
  filed_on: "2026-10-26",
  company_symbol: null,
  ...over,
});

const detail = (overrides: Record<string, unknown> = {}) => ({
  id: 7,
  name: "Jio Platforms Limited",
  current_stage: "prospectus",
  financials: {
    consolidated: [
      figure("consolidated", "2024-03-31", "FY24", "revenue_from_operations", "10000000000"),
      figure("consolidated", "2025-03-31", "FY25", "revenue_from_operations", "12000000000"),
      figure("consolidated", "2026-03-31", "FY26", "revenue_from_operations", "15000000000"),
      figure("consolidated", "2026-06-30", "Apr-Jun 26", "revenue_from_operations", "4000000000", true),
    ],
    standalone: [figure("standalone", "2026-03-31", "FY26", "revenue_from_operations", "9000000000")],
  },
  restatements: [],
  terms: null,
  ...overrides,
});

const draft = (overrides: Record<string, unknown> = {}) => ({
  draft_id: 3,
  stage: "rhp",
  sections: {
    mdna: { key: "mdna", text: "Revenue grew steadily.", blocked: false, unmatched: [], style_issues: [] },
    valuation: { key: "valuation", text: "Multiple of 999 times.", blocked: true, unmatched: ["999"], style_issues: [] },
  },
  rating: "[Analyst to set rating]",
  rationale: "[Analyst rationale]",
  ...overrides,
});

describe("IPO coverage tab", () => {
  test("shows the three years and the stub for both bases", async () => {
    mockApi({
      "GET /api/ipo/issues": () => ({ status: 200, body: [issue()] }),
      "GET /api/ipo/issues/7": () => ({ status: 200, body: detail() }),
      "GET /api/ipo/issues/7/coverage": () => ({ status: 404, body: { detail: "no coverage draft yet" } }),
    });
    renderAt(<IpoCoverage />);
    await screen.findByRole("heading", { name: "Consolidated" });
    expect(screen.getByRole("heading", { name: "Standalone" })).toBeTruthy();
    const cons = document.querySelector(".ipo-table-wrap") as HTMLElement;
    expect(within(cons).getByText("FY24")).toBeTruthy();
    expect(within(cons).getByText("FY25")).toBeTruthy();
    expect(within(cons).getByText("FY26")).toBeTruthy();
    expect(within(cons).getByText("stub")).toBeTruthy();
    expect(within(cons).getByText("1,000.00")).toBeTruthy();
  });

  test("generate is enabled for an RHP-only issue and the draft names its stage", async () => {
    mockApi({
      "GET /api/ipo/issues": () => ({ status: 200, body: [issue({ current_stage: "rhp", stages: ["rhp"] })] }),
      "GET /api/ipo/issues/7": () => ({ status: 200, body: detail({ current_stage: "rhp" }) }),
      "GET /api/ipo/issues/7/coverage": () => ({ status: 404, body: { detail: "no coverage draft yet" } }),
      "POST /api/ipo/issues/7/coverage": () => ({ status: 200, body: draft() }),
    });
    renderAt(<IpoCoverage />);
    const button = await screen.findByRole("button", { name: "Generate coverage" });
    await waitFor(() => expect((button as HTMLButtonElement).disabled).toBe(false));
    fireEvent.click(button);
    expect(await screen.findByText("Drafted from the RHP.")).toBeTruthy();
  });

  test("a blocked section shows its unmatched numbers and is never shown as clean", async () => {
    mockApi({
      "GET /api/ipo/issues": () => ({ status: 200, body: [issue()] }),
      "GET /api/ipo/issues/7": () => ({ status: 200, body: detail() }),
      "GET /api/ipo/issues/7/coverage": () => ({ status: 200, body: draft() }),
    });
    renderAt(<IpoCoverage />);
    expect(await screen.findByText("Blocked: unmatched numbers")).toBeTruthy();
    expect(screen.getByText(/Numbers not found in the document or in calc: 999/)).toBeTruthy();
    expect(screen.getAllByText("Blocked: unmatched numbers")).toHaveLength(1);
  });

  test("the rating and rationale are marked blanks for the analyst", async () => {
    mockApi({
      "GET /api/ipo/issues": () => ({ status: 200, body: [issue()] }),
      "GET /api/ipo/issues/7": () => ({ status: 200, body: detail() }),
      "GET /api/ipo/issues/7/coverage": () => ({ status: 200, body: draft() }),
    });
    renderAt(<IpoCoverage />);
    expect((await screen.findByTestId("rating")).textContent).toContain("[Analyst to set rating]");
    expect(screen.getByTestId("rationale").textContent).toContain("[Analyst rationale]");
  });

  test("generate waits when no document has been read yet", async () => {
    mockApi({
      "GET /api/ipo/issues": () => ({ status: 200, body: [issue({ current_stage: null, stages: [] })] }),
      "GET /api/ipo/issues/7": () => ({ status: 200, body: detail({ current_stage: null, financials: { consolidated: [], standalone: [] } }) }),
      "GET /api/ipo/issues/7/coverage": () => ({ status: 404, body: { detail: "no coverage draft yet" } }),
    });
    renderAt(<IpoCoverage />);
    expect(await screen.findByText(/Waits for an offer document to be read/)).toBeTruthy();
    expect((screen.getByRole("button", { name: "Generate coverage" }) as HTMLButtonElement).disabled).toBe(true);
  });
});

describe("Reports page kinds", () => {
  test("?kind=ipo selects the IPO tab; the other kinds are unchanged", async () => {
    const { Reports } = await import("./Reports");
    mockApi({ "GET /api/ipo/issues": () => ({ status: 200, body: [] }) });
    renderAt(<Reports />, "/reports?kind=ipo");
    expect(await screen.findByText("No IPO offer documents yet")).toBeTruthy();
    expect(screen.queryByText("New report")).toBeNull();
    cleanup();
    vi.restoreAllMocks();
    mockApi({});
    renderAt(<Reports />, "/reports?kind=initiating");
    expect(await screen.findByText("New report")).toBeTruthy();
    expect(screen.queryByText("No IPO offer documents yet")).toBeNull();
  });
});
