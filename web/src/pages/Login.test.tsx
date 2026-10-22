import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { Login } from "./Login";
import { RequireSignIn } from "../components/RequireSignIn";

type Reply = { status: number; body?: unknown; headers?: Record<string, string> };
let routes: Record<string, (init: RequestInit) => Reply>;
let calls: { url: string; init: RequestInit }[];

beforeEach(() => {
  calls = [];
  routes = {
    "GET /api/auth/me": () => ({ status: 401, body: { detail: "Sign in required." } }),
    "GET /api/public/calendar": () => ({ status: 200, body: { start: "", end: "", events: [] } }),
  };
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init = {}) => {
    const url = String(input);
    calls.push({ url, init });
    const key = `${(init.method ?? "GET").toUpperCase()} ${url.split("?")[0]}`;
    const reply = routes[key]?.(init) ?? { status: 404, body: { detail: `no route ${key}` } };
    return new Response(reply.status === 204 ? null : JSON.stringify(reply.body ?? {}), {
      status: reply.status,
      headers: { "Content-Type": "application/json", ...reply.headers },
    });
  });
  sessionStorage.clear();
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

const ME = { id: "u1", name: "Kaushal", email: "k@firm.in", role: "analyst" };

function Where() {
  const loc = useLocation();
  return <p data-testid="where">{loc.pathname + loc.search}</p>;
}

function renderLogin(initial = "/login") {
  render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <MemoryRouter initialEntries={[initial]}>
        <Where />
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route element={<RequireSignIn />}>
            <Route path="*" element={<p>the desk</p>} />
          </Route>
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const button = (name: string | RegExp) => screen.getByRole("button", { name }) as HTMLButtonElement;

function fill(label: string | RegExp, value: string) {
  fireEvent.change(screen.getByLabelText(label), { target: { value } });
}

test("the Microsoft button is shown but disabled", () => {
  renderLogin();
  expect(button(/microsoft/i).disabled).toBe(true);
});

test("wrong credentials show only the server's one sentence", async () => {
  routes["POST /api/auth/login"] = () => ({
    status: 401,
    body: { detail: "Email or password is incorrect." },
  });
  renderLogin();
  fill("Email", "k@firm.in");
  fill("Password", "nope");
  fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
  expect((await screen.findByRole("alert")).textContent).toContain(
    "Email or password is incorrect.",
  );
});

test("sign-in posts JSON with the CSRF header and never puts credentials in the address", async () => {
  routes["POST /api/auth/login"] = () => ({ status: 200, body: ME });
  const push = vi.spyOn(window.history, "pushState");
  renderLogin();
  fill("Email", "k@firm.in");
  fill("Password", "a-long-secret-password");
  fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
  await waitFor(() => expect(screen.getByTestId("where").textContent).toMatch(/^\/$/));
  const post = calls.find((c) => c.url === "/api/auth/login")!;
  expect(JSON.parse(String(post.init.body))).toEqual({
    email: "k@firm.in",
    password: "a-long-secret-password",
  });
  expect(post.init.headers).toMatchObject({ "X-Analekh-CSRF": "1" });
  expect(post.init.credentials).toBe("same-origin");
  for (const call of push.mock.calls)
    expect(String(call[2] ?? "")).not.toMatch(/secret|password|@/);
  expect(window.location.href).not.toMatch(/secret|password|@/);
});

test("a 429 says how long to wait and holds the button until then", async () => {
  routes["POST /api/auth/login"] = () => ({
    status: 429,
    body: { detail: "Too many attempts. Try again in 5 minute(s)." },
    headers: { "Retry-After": "300" },
  });
  renderLogin();
  fill("Email", "k@firm.in");
  fill("Password", "x");
  fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
  expect((await screen.findByRole("alert")).textContent).toContain("Too many attempts");
  expect(button(/try again in/i).disabled).toBe(true);
});

test("a blocked account is sent to the reset-code flow", async () => {
  routes["POST /api/auth/login"] = () => ({
    status: 403,
    body: { detail: "Reset your password to continue.", blocked: true },
  });
  renderLogin();
  fill("Email", "k@firm.in");
  fill("Password", "x");
  fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
  expect(await screen.findByRole("button", { name: "Send code" })).toBeTruthy();
  expect((screen.getByLabelText("Email") as HTMLInputElement).value).toBe("k@firm.in");
});

test("reset: ask for a code, then set a new password with it", async () => {
  routes["POST /api/auth/reset/request"] = () => ({
    status: 202,
    body: { detail: "If that account exists, a code has been sent." },
  });
  routes["POST /api/auth/reset/confirm"] = () => ({ status: 204 });
  renderLogin();
  fireEvent.click(screen.getByRole("button", { name: "Forgot password?" }));
  fill("Email", "k@firm.in");
  fireEvent.click(screen.getByRole("button", { name: "Send code" }));
  expect(await screen.findByText(/if that account exists/i)).toBeTruthy();
  fill("Code", "123456");
  fill("New password", "a brand new long password");
  fireEvent.click(screen.getByRole("button", { name: "Set new password" }));
  expect(await screen.findByText(/password changed/i)).toBeTruthy();
  const confirm = calls.find((c) => c.url === "/api/auth/reset/confirm")!;
  expect(JSON.parse(String(confirm.init.body))).toEqual({
    email: "k@firm.in",
    code: "123456",
    new_password: "a brand new long password",
  });
  expect(screen.getByRole("button", { name: "Sign in" })).toBeTruthy();
});

test("reset: the server's reason is shown for a short password or a bad code", async () => {
  routes["POST /api/auth/reset/request"] = () => ({ status: 202, body: { detail: "ok" } });
  routes["POST /api/auth/reset/confirm"] = () => ({
    status: 400,
    body: { detail: "Password must be at least 15 characters." },
  });
  renderLogin();
  fireEvent.click(screen.getByRole("button", { name: "Forgot password?" }));
  fill("Email", "k@firm.in");
  fireEvent.click(screen.getByRole("button", { name: "Send code" }));
  await screen.findByLabelText("Code");
  fill("Code", "123456");
  fill("New password", "short");
  fireEvent.click(screen.getByRole("button", { name: "Set new password" }));
  expect((await screen.findByRole("alert")).textContent).toContain(
    "Password must be at least 15 characters.",
  );
});

test("reset: when email is not set up the page says so", async () => {
  routes["POST /api/auth/reset/request"] = () => ({
    status: 503,
    body: { detail: "Email is not set up. Contact the admin team." },
  });
  renderLogin();
  fireEvent.click(screen.getByRole("button", { name: "Forgot password?" }));
  fill("Email", "k@firm.in");
  fireEvent.click(screen.getByRole("button", { name: "Send code" }));
  expect((await screen.findByRole("alert")).textContent).toContain("Email is not set up");
});

test("signed out, a protected page remembers its path and sign-in returns to it", async () => {
  routes["GET /api/auth/me"] = () => ({ status: 401, body: { detail: "Sign in required." } });
  routes["POST /api/auth/login"] = () => ({ status: 200, body: ME });
  renderLogin("/companies/TCS");
  await waitFor(() => expect(screen.getByTestId("where").textContent).toContain("/login"));
  expect(sessionStorage.getItem("analekh.return-path")).toBe("/companies/TCS");
  fill("Email", "k@firm.in");
  fill("Password", "a-long-secret-password");
  fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
  await waitFor(() => expect(screen.getByTestId("where").textContent).toContain("/companies/TCS"));
  expect(screen.getByText("the desk")).toBeTruthy();
});

test("signed in, the protected page opens and the sign-in page leaves", async () => {
  routes["GET /api/auth/me"] = () => ({ status: 200, body: ME });
  renderLogin("/models");
  expect(await screen.findByText("the desk")).toBeTruthy();
});

test("the public calendar is listed beside the form when there is something this week", async () => {
  routes["GET /api/public/calendar"] = () => ({
    status: 200,
    body: {
      start: "",
      end: "",
      events: [
        {
          date: "2026-10-23",
          kind: "results",
          symbol: "TCS",
          name: "Tata Consultancy Services",
          sector: "IT",
          purpose: null,
          source_url: null,
          status: "scheduled",
          revised: false,
        },
      ],
    },
  });
  renderLogin();
  expect(await screen.findByText("Tata Consultancy Services")).toBeTruthy();
});
