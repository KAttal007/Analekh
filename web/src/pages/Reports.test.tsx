import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { Reports } from "./Reports";
import { ANALYST, mockApi, renderAt } from "../test-utils";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

function show(threads: unknown[] = []) {
  return mockApi({
    "GET /api/auth/me": () => ({ status: 200, body: ANALYST }),
    "GET /api/companies/TCS": () => ({ status: 200, body: { id: 10, nse_symbol: "TCS", name: "TCS Limited" } }),
    "GET /api/companies/TCS/filings": () => ({ status: 200, body: [{ id: 1, period_end: "2026-09-30", consolidated: false }] }),
    "GET /api/companies/TCS/history": () => ({ status: 200, body: { consolidated: false, taxonomy: "x", quarter_ends: ["2026-09-30"], quarter_labels: ["Q2 FY27"], lines: [] } }),
    "GET /api/peer-lists": () => ({ status: 200, body: [] }),
    "GET /api/models": () => ({ status: 200, body: [] }),
    "GET /api/threads": () => ({ status: 200, body: threads }),
    "POST /api/threads": () => ({ status: 200, body: { thread_id: 9, job_id: "j" } }),
  });
}

it("the format is chosen first and starting a report opens its thread", async () => {
  const calls = show();
  renderAt(<Reports />, "/reports?company=TCS&format=ppt");
  const go = await screen.findByRole("button", { name: "Draft the presentation" });
  await waitFor(() => expect((go as HTMLButtonElement).disabled).toBe(false));
  fireEvent.click(go);
  await waitFor(() => expect(screen.getByTestId("where").textContent).toBe("/reports/9"));
  expect(calls.find((c) => c.method === "POST")!.body).toMatchObject({ symbol: "TCS", report_type: "quarterly", format: "ppt", basis: "standalone", quarter_end: "2026-09-30" });
});

it("an initiating report without the analyst's model cannot start, and says why", async () => {
  show();
  renderAt(<Reports />, "/reports?company=TCS&kind=initiating");
  expect(await screen.findByText(/needs your Excel model/)).toBeTruthy();
  expect((screen.getByRole("button", { name: "Draft the Word report" }) as HTMLButtonElement).disabled).toBe(true);
});

it("your reports are listed with their status", async () => {
  show([{ id: 4, symbol: "INFY", company_name: "Infosys", report_type: "initiating", format: "word", quarter_end: null, status: "approved", busy: false, updated_at: "" }]);
  renderAt(<Reports />, "/reports");
  const row = await screen.findByRole("link", { name: /INFY/ });
  expect(row.getAttribute("href")).toBe("/reports/4");
  expect(screen.getByText("Approved")).toBeTruthy();
});
