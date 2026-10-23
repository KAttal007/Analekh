import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { markWelcomed, resetWelcomed } from "./lib/welcome";
import { routes } from "./router";
import { ANALYST, mockApi } from "./test-utils";

beforeEach(() => resetWelcomed());
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

const WELCOME = {
  companies_in_scope: 1,
  filings_total: 1,
  reported: 1,
  quarter_label: "Q2 FY27",
  latest_filed_at: null,
};

function open(path: string, signedIn: boolean) {
  mockApi({
    "GET /api/auth/me": () => (signedIn ? { status: 200, body: ANALYST } : { status: 401 }),
    "GET /api/public/welcome": () => ({ status: 200, body: WELCOME }),
    "GET /api/public/auth-status": () => ({ status: 200, body: { auth_enabled: true } }),
    "GET /api/auth/password-rules": () => ({ status: 200, body: { rules: [], pattern: "" } }),
  });
  const router = createMemoryRouter(routes, { initialEntries: [path] });
  render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  return router;
}

test("opening Analekh signed out lands on the welcome page", async () => {
  const router = open("/", false);
  await waitFor(() => expect(router.state.location.pathname).toBe("/welcome"));
  expect(await screen.findByRole("button", { name: /open the results desk/i })).toBeTruthy();
});

test("opening Analekh with a live session goes straight to the home screen", async () => {
  const router = open("/", true);
  await screen.findByRole("heading", { name: /results desk/i }, { timeout: 3000 });
  expect(router.state.location.pathname).toBe("/");
});

test("after the welcome, the home address does not bring it back", async () => {
  markWelcomed();
  const router = open("/", false);
  await waitFor(() => expect(router.state.location.pathname).toBe("/login"));
});
