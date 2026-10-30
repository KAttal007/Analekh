import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { Login } from "./Login";
import { iso } from "../lib/calendar";
import { RequireSignIn } from "../components/RequireSignIn";

type Reply = { status: number; body?: unknown; headers?: Record<string, string> };
let routes: Record<string, (init: RequestInit) => Reply>;
let calls: { url: string; init: RequestInit }[];

beforeEach(() => {
  calls = [];
  routes = {
    "GET /api/auth/me": () => ({ status: 401, body: { detail: "Sign in required." } }),
    "GET /api/public/calendar": () => ({ status: 200, body: { start: "", end: "", events: [] } }),
    "GET /api/auth/password-rules": () => ({ status: 200, body: RULES }),
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
  localStorage.clear();
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

const RULES = {
  rules: [
    { id: "length", label: "15 to 30 characters", pattern: String.raw`^[\s\S]{15,30}$` },
    { id: "digits", label: "At least 1 number", pattern: "^(?:[^0-9]*[0-9]){1}" },
  ],
  combined: "",
  max_length: 30,
  min_length: 15,
};
const NEW_PASSWORD = "A-brand-new-passw0rd";

const ME = { id: "u1", name: "Kaushal", email: "k@firm.in", role: "analyst" };
// a device already named, so sign-in goes straight on
const LOGIN = { ...ME, device: { device_id: "ab12cd34", name: "Office laptop", label: "Chrome on Windows" } };

function Where() {
  const loc = useLocation();
  return <p data-testid="where">{loc.pathname + loc.search}</p>;
}

function renderLogin(initial = "/login") {
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
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
  expect((await screen.findByRole("alert")).textContent).toContain("Email or password is incorrect.");
});

test("sign-in posts JSON with the CSRF header and never puts credentials in the address", async () => {
  routes["POST /api/auth/login"] = () => ({ status: 200, body: LOGIN });
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
  for (const call of push.mock.calls) expect(String(call[2] ?? "")).not.toMatch(/secret|password|@/);
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
  await screen.findByText("At least 1 number");
  fill("New password", "a brand new long password");
  fill("Confirm new password", "a brand new long password");
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
  fill("Confirm new password", "short");
  fireEvent.click(screen.getByRole("button", { name: "Set new password" }));
  expect((await screen.findByRole("alert")).textContent).toContain("Password must be at least 15 characters.");
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
  routes["POST /api/auth/login"] = () => ({ status: 200, body: LOGIN });
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
  const event = {
    date: iso(new Date()),
    kind: "results",
    symbol: "TCS",
    name: "Tata Consultancy Services",
  };
  routes["GET /api/public/calendar"] = () => ({ status: 200, body: { events: [event] } });
  renderLogin();
  expect(await screen.findByText("Tata Consultancy Services")).toBeTruthy();
});

const FLAGGED = { ...ME, must_change_password: true };

test("routes a flagged sign-in to the first-password step", async () => {
  routes["POST /api/auth/login"] = () => ({ status: 200, body: FLAGGED });
  routes["GET /api/auth/me"] = () => ({ status: 200, body: FLAGGED });
  renderLogin();
  fill("Email", "k@firm.in");
  fill("Password", "the-emailed-first-pw");
  fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
  expect(await screen.findByRole("heading", { name: "Choose your password" })).toBeTruthy();
  expect(screen.getByLabelText("First password")).toBeTruthy();
  expect(screen.getByLabelText("New password")).toBeTruthy();
  expect(screen.getByLabelText("Confirm new password")).toBeTruthy();
  expect(screen.queryByText("the desk")).toBeNull();
});

test("first password: sets the new one, then asks to sign in again", async () => {
  routes["GET /api/auth/me"] = () => ({ status: 200, body: FLAGGED });
  routes["POST /api/auth/first-password"] = () => ({ status: 204 });
  renderLogin();
  await screen.findByLabelText("First password");
  await screen.findByText("At least 1 number");
  fill("First password", "the-emailed-first-pw");
  fill("New password", NEW_PASSWORD);
  fill("Confirm new password", NEW_PASSWORD);
  fireEvent.click(screen.getByRole("button", { name: "Set password" }));
  expect(await screen.findByText("Password set. Sign in with your new password.")).toBeTruthy();
  const post = calls.find((c) => c.url === "/api/auth/first-password")!;
  expect(JSON.parse(String(post.init.body))).toEqual({
    current_password: "the-emailed-first-pw",
    new_password: NEW_PASSWORD,
  });
  expect(screen.getByRole("button", { name: "Sign in" })).toBeTruthy();
});

test("first password: two different new passwords are refused before sending", async () => {
  routes["GET /api/auth/me"] = () => ({ status: 200, body: FLAGGED });
  renderLogin();
  await screen.findByLabelText("First password");
  fill("First password", "the-emailed-first-pw");
  fill("New password", NEW_PASSWORD);
  fill("Confirm new password", NEW_PASSWORD + "x");
  fireEvent.click(screen.getByRole("button", { name: "Set password" }));
  expect((await screen.findByRole("alert")).textContent).toContain("The two passwords do not match.");
  expect(calls.some((c) => c.url === "/api/auth/first-password")).toBe(false);
});

test("first password: the server's message for missing rules is shown", async () => {
  routes["GET /api/auth/me"] = () => ({ status: 200, body: FLAGGED });
  routes["POST /api/auth/first-password"] = () => ({
    status: 400,
    body: { detail: "Password needs: At least 1 number.", missing: ["digits"] },
  });
  renderLogin();
  await screen.findByLabelText("First password");
  fill("First password", "the-emailed-first-pw");
  fill("New password", "short");
  fill("Confirm new password", "short");
  fireEvent.click(screen.getByRole("button", { name: "Set password" }));
  expect((await screen.findByRole("alert")).textContent).toContain("Password needs: At least 1 number.");
  expect(screen.getByRole("heading", { name: "Choose your password" })).toBeTruthy();
});

test("first password: Sign out ends the session and returns to sign-in", async () => {
  routes["GET /api/auth/me"] = () => ({ status: 200, body: FLAGGED });
  routes["POST /api/auth/logout"] = () => {
    routes["GET /api/auth/me"] = () => ({ status: 401, body: { detail: "Sign in required." } });
    return { status: 204 };
  };
  renderLogin();
  await screen.findByLabelText("First password");
  fireEvent.click(screen.getByRole("button", { name: "Sign out" }));
  expect(await screen.findByRole("heading", { name: "Sign in" })).toBeTruthy();
  expect(calls.some((c) => c.url === "/api/auth/logout")).toBe(true);
});

test("shows the server's expired message as given", async () => {
  const detail = "This first password has expired. Ask an admin to send a new one.";
  routes["POST /api/auth/login"] = () => ({ status: 401, body: { detail } });
  renderLogin();
  fill("Email", "k@firm.in");
  fill("Password", "the-emailed-first-pw");
  fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
  expect((await screen.findByRole("alert")).textContent).toBe(detail);
});

test("reset step uses the shared rules field", async () => {
  routes["POST /api/auth/reset/request"] = () => ({ status: 202, body: { detail: "sent" } });
  renderLogin();
  fireEvent.click(screen.getByRole("button", { name: "Forgot password?" }));
  fill("Email", "k@firm.in");
  fireEvent.click(screen.getByRole("button", { name: "Send code" }));
  expect(await screen.findByText("15 to 30 characters")).toBeTruthy();
  expect(screen.getByText("At least 1 number")).toBeTruthy();
  fill("New password", "abc1");
  expect(screen.getByText("At least 1 number").closest("li")!.getAttribute("data-met")).toBe("true");
});

test("refuses 31 characters with maxLength in the DOM", async () => {
  routes["POST /api/auth/reset/request"] = () => ({ status: 202, body: { detail: "sent" } });
  renderLogin();
  fireEvent.click(screen.getByRole("button", { name: "Forgot password?" }));
  fill("Email", "k@firm.in");
  fireEvent.click(screen.getByRole("button", { name: "Send code" }));
  await screen.findByText("15 to 30 characters");
  await waitFor(() => {
    for (const label of ["New password", "Confirm new password"]) expect((screen.getByLabelText(label) as HTMLInputElement).maxLength).toBe(30);
  });
});

test("after sign-in the desk's data is asked for before the page changes", async () => {
  routes["POST /api/auth/login"] = () => ({ status: 200, body: LOGIN });
  let deskAskedWhileOnLogin = false;
  routes["GET /api/desk"] = () => {
    deskAskedWhileOnLogin = screen.getByTestId("where").textContent === "/login";
    return { status: 200, body: { rows: [], rows_total: 0 } };
  };
  renderLogin();
  fill("Email", "k@firm.in");
  fill("Password", "a-long-secret-password");
  fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
  await waitFor(() => expect(screen.getByTestId("where").textContent).toBe("/"));
  expect(deskAskedWhileOnLogin).toBe(true);
  expect(document.documentElement.dataset.vt).toBe("enter");
});

test("signing in again after a session ran out re-arms the sign-in reminder", async () => {
  sessionStorage.setItem("analekh.signin-locks", ME.id);
  routes["POST /api/auth/login"] = () => ({ status: 200, body: LOGIN });
  renderLogin();
  fill("Email", "k@firm.in");
  fill("Password", "a-long-secret-password");
  fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
  await waitFor(() => expect(sessionStorage.getItem("analekh.signin-locks")).toBeNull());
});

test("a failed sign-in leaves the reminder's mark alone", async () => {
  sessionStorage.setItem("analekh.signin-locks", ME.id);
  routes["POST /api/auth/login"] = () => ({
    status: 401,
    body: { detail: "Email or password is incorrect." },
  });
  renderLogin();
  fill("Email", "k@firm.in");
  fill("Password", "nope");
  fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
  await screen.findByRole("alert");
  expect(sessionStorage.getItem("analekh.signin-locks")).toBe(ME.id);
});

function signInWith(body: unknown, status = 200) {
  routes["POST /api/auth/login"] = () => ({ status, body });
  renderLogin();
  fill("Email", "k@firm.in");
  fill("Password", "a-long-secret-password");
  fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
}

const UNNAMED = { ...ME, device: { device_id: "ab12cd34", name: null, label: "Chrome on Windows" } };

test("a new device is offered a name, ready to edit, and saving it goes on", async () => {
  routes["POST /api/auth/device-name"] = () => ({ status: 200, body: { ...UNNAMED.device, name: "Home PC" } });
  signInWith(UNNAMED);
  const input = (await screen.findByLabelText("Device name")) as HTMLInputElement;
  expect(input.value).toBe("Chrome on Windows");
  expect(screen.getByTestId("where").textContent).toBe("/login"); // held until named or skipped
  fill("Device name", "Home PC");
  fireEvent.click(button("Save name"));
  await waitFor(() => expect(screen.getByTestId("where").textContent).toBe("/"));
  const post = calls.find((c) => c.url === "/api/auth/device-name")!;
  expect(JSON.parse(String(post.init.body))).toEqual({ name: "Home PC" });
  expect(post.init.headers).toMatchObject({ "X-Analekh-CSRF": "1" });
});

test("skipping the name goes on and is not asked again on this browser", async () => {
  signInWith(UNNAMED);
  fireEvent.click(await screen.findByRole("button", { name: "Skip for now" }));
  await waitFor(() => expect(screen.getByTestId("where").textContent).toBe("/"));
  expect(localStorage.getItem("analekh.device-name-skipped")).toBe("ab12cd34");
  expect(calls.some((c) => c.url === "/api/auth/device-name")).toBe(false);
});

test("at the session limit the devices are listed and one can be signed out", async () => {
  const limit = {
    detail: "You are signed in on 3 devices, the most allowed. Sign out of one to sign in here.",
    limit: 3,
    choice_token: "choice-token",
    devices: [
      { device_id: "11aa22bb", name: "Office laptop", label: "Chrome on Windows", signed_in_at: "2026-10-30T04:00:00Z", last_seen_at: "2026-10-30T05:00:00Z" },
      { device_id: "33cc44dd", name: null, label: "Safari on iPhone", signed_in_at: "2026-10-29T04:00:00Z", last_seen_at: "2026-10-29T05:00:00Z" },
    ],
  };
  routes["POST /api/auth/login/replace"] = () => ({ status: 200, body: LOGIN });
  signInWith(limit, 409);
  expect(await screen.findByText("Office laptop")).toBeTruthy();
  expect(screen.getByText("Safari on iPhone")).toBeTruthy();
  expect(screen.getByText("11aa22bb")).toBeTruthy();
  fireEvent.click(screen.getAllByRole("button", { name: "Sign out of this device" })[1]);
  await waitFor(() => expect(screen.getByTestId("where").textContent).toBe("/"));
  const post = calls.find((c) => c.url === "/api/auth/login/replace")!;
  expect(JSON.parse(String(post.init.body))).toEqual({ choice_token: "choice-token", device_id: "33cc44dd" });
});
