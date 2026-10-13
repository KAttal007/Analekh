import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, test, vi } from "vitest";
import { CompanySearch } from "./components/CompanySearch";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

const INDEX = [
  {
    id: 1,
    nse_symbol: "DEMOFIN",
    name: "Demo Finance Limited",
    isin: "INE000D01011",
    sector: "NBFC",
  },
];

// Answers /companies/index with INDEX and /companies/search with `searchHits`.
function mockApi(searchHits: unknown[] = []) {
  return vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = String(input);
    const body = url.startsWith("/api/companies/index") ? INDEX : searchHits;
    return new Response(JSON.stringify(body), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  });
}

function renderSearch() {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter>
        <CompanySearch />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return screen.getByLabelText("Search companies");
}

test("search suggests companies from the in-browser index", async () => {
  const fetch = mockApi();
  const input = renderSearch();
  await vi.waitFor(() =>
    expect(fetch).toHaveBeenCalledWith("/api/companies/index", expect.anything()),
  );
  fireEvent.change(input, { target: { value: "demo" } });
  expect(await screen.findByText("DEMOFIN")).toBeTruthy();
  expect(fetch.mock.calls.some(([u]) => String(u).includes("/companies/search"))).toBe(false);
});

test("falls back to the server's fuzzy search when nothing matches locally", async () => {
  const fetch = mockApi([
    {
      id: 2,
      nse_symbol: "RELIANCE",
      name: "Reliance Industries Limited",
      isin: null,
      sector: null,
      is_active: true,
      score: 0.4,
    },
  ]);
  const input = renderSearch();
  await vi.waitFor(() =>
    expect(fetch).toHaveBeenCalledWith("/api/companies/index", expect.anything()),
  );
  fireEvent.change(input, { target: { value: "relianse" } });
  expect(await screen.findByText("RELIANCE")).toBeTruthy();
  expect(fetch).toHaveBeenCalledWith(
    "/api/companies/search?q=relianse&limit=20&offset=0",
    expect.anything(),
  );
});
