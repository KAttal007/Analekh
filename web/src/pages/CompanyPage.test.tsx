import { cleanup, fireEvent, screen } from "@testing-library/react";
import { Route, Routes } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import { CompanyPage } from "./CompanyPage";
import { ANALYST, mockApi, renderAt } from "../test-utils";

vi.mock("echarts-for-react", () => ({ default: () => null }));

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

const TCS = {
  id: 10,
  nse_symbol: "TCS",
  isin: null,
  name: "Tata Consultancy Services",
  series: "EQ",
  listing_date: null,
  face_value: null,
  sector: null,
  industry: null,
  results_taxonomy: null,
  is_sme: false,
  is_active: true,
  refreshed_at: null,
  coverage_level: "universe",
  watched: false,
};

it("Start coverage on a model a colleague holds says who, instead of an error", async () => {
  const at = new Date();
  at.setHours(10, 42, 0, 0);
  mockApi({
    "GET /api/auth/me": () => ({ status: 200, body: ANALYST }),
    "GET /api/companies/TCS": () => ({ status: 200, body: TCS }),
    "GET /api/companies/TCS/filings": () => ({ status: 200, body: [] }),
    "POST /api/coverage": () => ({
      status: 423,
      body: {
        detail: {
          code: "model_locked",
          holder_name: "Kaushal",
          taken_at: at.toISOString(),
          activity: "update",
        },
      },
    }),
  });
  renderAt(
    <Routes>
      <Route path="/companies/:symbol" element={<CompanyPage />} />
    </Routes>,
    "/companies/TCS",
  );
  fireEvent.click(await screen.findByRole("button", { name: "Start coverage" }));
  expect(await screen.findByText("In use by Kaushal since 10:42")).toBeTruthy();
  expect(screen.queryByText(/model_locked/)).toBeNull();
});
