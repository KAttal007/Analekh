import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { Welcome } from "./Welcome";
import { hasWelcomed, resetWelcomed } from "../lib/welcome";

const ME = { id: "u1", name: "Kaushal", email: "k@firm.in", role: "analyst" };
let signedIn: boolean;

beforeEach(() => {
  resetWelcomed();
  signedIn = false;
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = String(input);
    const reply = (status: number, body: unknown) =>
      new Response(JSON.stringify(body), {
        status,
        headers: { "Content-Type": "application/json" },
      });
    if (url === "/api/auth/me")
      return signedIn ? reply(200, ME) : reply(401, { detail: "Sign in required." });
    if (url.startsWith("/api/public/welcome"))
      return reply(200, {
        companies_in_scope: 3,
        filings_total: 4,
        reported: 2,
        quarter_label: "Q2 FY27",
        latest_filed_at: null,
      });
    return reply(404, { detail: "no route" });
  });
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

function Where() {
  return <p data-testid="where">{useLocation().pathname}</p>;
}

function renderWelcome() {
  render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <MemoryRouter initialEntries={["/welcome"]}>
        <Where />
        <Routes>
          <Route path="/welcome" element={<Welcome />} />
          <Route path="*" element={<p>elsewhere</p>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const where = () => screen.getByTestId("where").textContent;

test("the counts come from the public endpoint, not the protected desk", async () => {
  renderWelcome();
  await waitFor(() => expect(screen.getByText("results filings")).toBeTruthy());
  const urls = vi.mocked(fetch).mock.calls.map((c) => String(c[0]));
  expect(urls).toContain("/api/public/welcome");
  expect(urls.some((u) => u.startsWith("/api/desk"))).toBe(false);
});

test("signed out, the way in reveals the sign-in screen", async () => {
  renderWelcome();
  // wait until the session check has answered (signed out)
  await waitFor(() =>
    expect(vi.mocked(fetch).mock.calls.some((c) => c[0] === "/api/auth/me")).toBe(true),
  );
  await new Promise((r) => setTimeout(r, 20));
  fireEvent.click(screen.getByRole("button", { name: /open the results desk/i }));
  await waitFor(() => expect(where()).toBe("/login"));
  expect(hasWelcomed()).toBe(true); // signing in must not send the visitor back to the welcome
});

test("already signed in, the way in opens the desk directly", async () => {
  signedIn = true;
  renderWelcome();
  await waitFor(() =>
    expect(vi.mocked(fetch).mock.calls.some((c) => c[0] === "/api/auth/me")).toBe(true),
  );
  await new Promise((r) => setTimeout(r, 20));
  fireEvent.click(screen.getByRole("button", { name: /open the results desk/i }));
  await waitFor(() => expect(where()).toBe("/"));
});

test("the unlock animation is tagged on the page for the transition styles", async () => {
  renderWelcome();
  await new Promise((r) => setTimeout(r, 20));
  fireEvent.click(screen.getByRole("button", { name: /open the results desk/i }));
  expect(document.documentElement.dataset.vt).toBe("reveal");
});

const settled = async () => {
  await waitFor(() =>
    expect(vi.mocked(fetch).mock.calls.some((c) => c[0] === "/api/auth/me")).toBe(true),
  );
  await new Promise((r) => setTimeout(r, 20));
};

test("Enter opens the way in", async () => {
  renderWelcome();
  await settled();
  fireEvent.keyDown(window, { key: "Enter" });
  await waitFor(() => expect(where()).toBe("/login"));
});

const drag = (from: number, to: number) => {
  const page = document.querySelector(".welcome")!;
  fireEvent.pointerDown(page, { pointerType: "mouse", button: 0, clientY: from });
  fireEvent.pointerMove(window, { pointerType: "mouse", clientY: to });
  fireEvent.pointerUp(window, { pointerType: "mouse", clientY: to });
  fireEvent.click(page);
};

test("a short mouse drag springs back; a long one opens the way in", async () => {
  renderWelcome();
  await settled();
  drag(600, 560);
  await new Promise((r) => setTimeout(r, 20));
  expect(where()).toBe("/welcome");
  drag(800, 100);
  await waitFor(() => expect(where()).toBe("/login"));
});
