import type { QueryClient } from "@tanstack/react-query";
import { api, type DeskQuery } from "../api/client";
import { addDays, daysFrom, iso, startOfWeek } from "./calendar";
import { readPrefs } from "./prefs";

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

// The home screen's queries (Results desk, its calendar strip, the search index), defined once so
// the screens and the sign-in prefetch share cache entries.

export const DESK_PAGE = 10;

export const deskQuery = (query: DeskQuery, page: number) => ({
  queryKey: ["desk", query, page] as const,
  queryFn: () => api.desk({ ...query, limit: DESK_PAGE, offset: (page - 1) * DESK_PAGE }),
});

/** The desk filters as the URL and the order preference give them. */
export const deskFilters = (params: URLSearchParams, sort: "filed" | "market_cap"): DeskQuery => ({
  quarter_end: params.get("quarter") ?? undefined,
  sector: params.get("sector") ?? undefined,
  watchlist: params.get("watchlist") === "1" || undefined,
  days: Number(params.get("days")) || undefined,
  sort: sort === "market_cap" ? "market_cap" : undefined,
});

const STRIP_BEFORE = 7; // days of history the calendar's day strip keeps
const STRIP_DAYS = 68; // and how many in all: a week back, the season ahead

export const dayStrip = (today: string) => daysFrom(addDays(today, -STRIP_BEFORE), STRIP_DAYS);

export const calendarQuery = (start: string, end: string, watchlistOnly: boolean) => ({
  queryKey: ["calendar", start, end, watchlistOnly] as const,
  queryFn: () => api.calendar(start, end, watchlistOnly),
  staleTime: 60_000,
});

/** The signed-out "Results this week" list on the login page. Shared with the welcome page,
 * which warms it so the list is already there when the login page opens. */
export const publicWeekQuery = () => {
  const monday = startOfWeek(iso(new Date()));
  const sunday = addDays(monday, 6);
  return {
    queryKey: ["public-calendar", monday] as const,
    queryFn: () => api.publicCalendar(monday, sunday),
    staleTime: 60_000,
    retry: false as const,
  };
};

export const companyIndexQuery = {
  queryKey: ["company-index"] as const,
  queryFn: api.companyIndex,
  staleTime: 10 * 60_000,
};

/** Loads what the home screen shows first, so it opens filled in (after sign-in). The search
 * index is left out: nothing on screen needs it, and preparing ~3,000 companies would hold up
 * the handoff animation. */
export function prefetchHome(client: QueryClient): Promise<unknown> {
  const strip = dayStrip(iso(new Date()));
  const desk = deskFilters(new URLSearchParams(), readPrefs().deskSort);
  return Promise.all([
    client.prefetchQuery(deskQuery(desk, 1)),
    client.prefetchQuery(calendarQuery(strip[0], strip[strip.length - 1], false)),
  ]);
}
