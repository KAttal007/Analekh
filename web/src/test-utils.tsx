import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import type { ReactElement } from "react";
import { MemoryRouter, useLocation } from "react-router-dom";
import { vi } from "vitest";

// jsdom has no ResizeObserver; the segmented switches and the sidebar highlight use one.
globalThis.ResizeObserver ??= class {
  observe() {}
  unobserve() {}
  disconnect() {}
};

export type Reply = { status: number; body?: unknown; headers?: Record<string, string> };
export type Handler = (init: RequestInit, url: string) => Reply;
export type Call = { url: string; method: string; body: unknown; init: RequestInit };

/** Answers fetch from a table keyed "METHOD /api/path" (query string ignored). Anything not in
 * the table is a 404, so a test notices a call it did not expect. */
export function mockApi(routes: Record<string, Handler>) {
  const calls: Call[] = [];
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init = {}) => {
    const url = String(input);
    const method = (init.method ?? "GET").toUpperCase();
    let body: unknown;
    try {
      body = init.body ? JSON.parse(String(init.body)) : undefined;
    } catch {
      body = init.body;
    }
    calls.push({ url, method, body, init });
    const reply = routes[`${method} ${url.split("?")[0]}`]?.(init, url) ?? {
      status: 404,
      body: { detail: `no route ${method} ${url}` },
    };
    // An explicit null body is the JSON `null` (e.g. a free model's lock); no body is `{}`.
    const json = JSON.stringify(reply.body === undefined ? {} : reply.body);
    return new Response(reply.status === 204 ? null : json, {
      status: reply.status,
      headers: { "Content-Type": "application/json", ...reply.headers },
    });
  });
  return calls;
}

export function Where() {
  const loc = useLocation();
  return <p data-testid="where">{loc.pathname + loc.search}</p>;
}

export function renderAt(ui: ReactElement, initial = "/") {
  return render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <MemoryRouter initialEntries={[initial]}>
        <Where />
        {ui}
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

export const ADMIN = { id: "a1", name: "Rhea Mehta", email: "rhea@firm.in", role: "admin" };
export const ANALYST = {
  id: "u1",
  name: "Kaushal Attal",
  email: "kaushal@firm.in",
  role: "analyst",
};
