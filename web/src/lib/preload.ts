import { api } from "../api/client";

// Code-split screens that the search box can warm up before the user picks a result.
// The router lazy-loads the same imports, so a preloaded chunk is reused, not fetched twice.
export const loadCompanyPage = () => import("../pages/CompanyPage");

// The company header query, shared by the company page and the search box's prefetch so both
// use the same cache entry. Prefetched data stays fresh briefly, so opening the page doesn't
// refetch what was fetched a moment ago.
export const companyQuery = (symbol: string) => ({
  queryKey: ["company", symbol] as const,
  queryFn: () => api.company(symbol),
  staleTime: 30_000,
});
