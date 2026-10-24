import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { Route, Routes } from "react-router-dom";
import { afterEach, beforeAll, expect, test, vi } from "vitest";
import { AdminLayout } from "./AdminLayout";
import { RequireSignIn } from "./components/RequireSignIn";
import { Layout } from "./Layout";
import { ADMIN, ANALYST, mockApi, renderAt } from "./test-utils";

beforeAll(() => {
  // jsdom has no ResizeObserver; the sidebar highlight uses one.
  globalThis.ResizeObserver ??= class {
    observe() {}
    unobserve() {}
    disconnect() {}
  };
});
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

const app = (
  <Routes>
    <Route path="/admin" element={<AdminLayout />}>
      <Route path="users" element={<p>users page</p>} />
      <Route path="templates" element={<p>templates page</p>} />
      <Route path="settings" element={<p>settings page</p>} />
    </Route>
    <Route element={<Layout />}>
      <Route path="*" element={<p>the desk</p>} />
    </Route>
  </Routes>
);

const where = () => screen.getByTestId("where").textContent;

test("the admin shell shows exactly Users, Model locks, Templates, Settings and a way back", async () => {
  mockApi({ "GET /api/auth/me": () => ({ status: 200, body: ADMIN }) });
  renderAt(app, "/admin/users");
  await screen.findByText("users page");
  const nav = screen.getByRole("navigation", { name: "Admin" });
  const labels = Array.from(nav.querySelectorAll("a")).map((a) => a.textContent?.trim());
  expect(labels).toEqual(["Users", "Model locks", "Templates", "Settings", "← Back to Analekh"]);
});

test("an admin who still holds a model is reminded in the admin shell too", async () => {
  sessionStorage.clear();
  mockApi({
    "GET /api/auth/me": () => ({ status: 200, body: ADMIN }),
    "GET /api/me/locks": () => ({
      status: 200,
      body: [
        {
          model_id: 1,
          holder_id: ADMIN.id,
          holder_name: ADMIN.name,
          activity: "update",
          taken_at: "2026-10-24T10:42:00Z",
          mine: true,
          job_running: false,
        },
      ],
    }),
    "GET /api/models": () => ({
      status: 200,
      body: [{ id: 1, company_id: 10, template_id: null, name: "TCS model", origin: "built" }],
    }),
    "GET /api/companies/index": () => ({
      status: 200,
      body: [{ id: 10, nse_symbol: "TCS", name: "Tata Consultancy Services", isin: null }],
    }),
  });
  renderAt(app, "/admin/users");
  const box = await screen.findByRole("region", { name: "Models still open" });
  expect(box.textContent).toContain("You still have 1 model open");
  expect(box.textContent).toContain("Tata Consultancy Services");
  sessionStorage.clear();
});

test("an analyst opening an admin page is sent to the home page", async () => {
  mockApi({ "GET /api/auth/me": () => ({ status: 200, body: ANALYST }) });
  renderAt(app, "/admin/users");
  await waitFor(() => expect(where()).toBe("/"));
  expect(screen.queryByText("users page")).toBeNull();
});

test("the main nav has no Templates entry, and only admins see an Admin link", async () => {
  mockApi({ "GET /api/auth/me": () => ({ status: 200, body: ANALYST }) });
  renderAt(app, "/");
  await screen.findByText("the desk");
  expect(screen.queryByRole("link", { name: "Templates" })).toBeNull();
  expect(screen.queryByRole("link", { name: "Admin" })).toBeNull();
  cleanup();
  vi.restoreAllMocks();
  mockApi({ "GET /api/auth/me": () => ({ status: 200, body: ADMIN }) });
  renderAt(app, "/");
  await screen.findByRole("link", { name: "Admin" });
  expect(screen.queryByRole("link", { name: "Templates" })).toBeNull();
});

test("the sidebar Sign out button is hidden when sign-in is off, shown when on", async () => {
  mockApi({
    "GET /api/auth/me": () => ({ status: 200, body: ANALYST }),
    "GET /api/public/auth-status": () => ({ status: 200, body: { auth_enabled: false } }),
  });
  renderAt(app, "/");
  await screen.findByText("the desk");
  await waitFor(() => expect(screen.queryByRole("button", { name: "Sign out" })).toBeNull());
  cleanup();
  vi.restoreAllMocks();
  mockApi({
    "GET /api/auth/me": () => ({ status: 200, body: ANALYST }),
    "GET /api/public/auth-status": () => ({ status: 200, body: { auth_enabled: true } }),
  });
  renderAt(app, "/");
  await screen.findByRole("button", { name: "Sign out" });
});

test("Sign out shows the sign-in page at once, with no other click", async () => {
  let signedIn = true;
  mockApi({
    "GET /api/auth/me": () => (signedIn ? { status: 200, body: ANALYST } : { status: 401 }),
    "GET /api/public/auth-status": () => ({ status: 200, body: { auth_enabled: true } }),
    "POST /api/auth/logout": () => {
      signedIn = false;
      return { status: 204 };
    },
  });
  renderAt(
    <Routes>
      <Route path="/login" element={<p>sign-in page</p>} />
      <Route element={<RequireSignIn />}>
        <Route element={<Layout />}>
          <Route path="*" element={<p>the desk</p>} />
        </Route>
      </Route>
    </Routes>,
    "/",
  );
  fireEvent.click(await screen.findByRole("button", { name: "Sign out" }));
  await screen.findByText("sign-in page");
});

function signOutApp() {
  return (
    <Routes>
      <Route path="/welcome" element={<p>welcome page</p>} />
      <Route element={<RequireSignIn />}>
        <Route element={<Layout />}>
          <Route path="*" element={<p>the desk</p>} />
        </Route>
      </Route>
    </Routes>
  );
}

test("Sign out waits for the server's reply, then goes to the welcome page", async () => {
  mockApi({
    "GET /api/auth/me": () => ({ status: 200, body: ANALYST }),
    "GET /api/public/auth-status": () => ({ status: 200, body: { auth_enabled: true } }),
    "POST /api/auth/logout": () => ({ status: 204 }),
  });
  // Hold back only the sign-out reply until the test lets it through.
  const spy = vi.mocked(globalThis.fetch);
  const real = spy.getMockImplementation()!;
  let release: () => void = () => {};
  const gate = new Promise<void>((resolve) => (release = resolve));
  spy.mockImplementation(async (input, init) => {
    if (String(input).endsWith("/auth/logout")) await gate;
    return real(input, init);
  });
  renderAt(signOutApp(), "/");
  fireEvent.click(await screen.findByRole("button", { name: "Sign out" }));
  await new Promise((r) => setTimeout(r, 100));
  expect(screen.queryByText("welcome page")).toBeNull();
  release();
  await screen.findByText("welcome page");
});

test("a failed sign-out stays put and says so", async () => {
  mockApi({
    "GET /api/auth/me": () => ({ status: 200, body: ANALYST }),
    "GET /api/public/auth-status": () => ({ status: 200, body: { auth_enabled: true } }),
    "POST /api/auth/logout": () => ({ status: 500, body: { detail: "Server error" } }),
  });
  renderAt(signOutApp(), "/");
  fireEvent.click(await screen.findByRole("button", { name: "Sign out" }));
  await screen.findByRole("alert");
  expect(screen.queryByText("welcome page")).toBeNull();
  expect(screen.getByText("the desk")).toBeTruthy();
});

test("the admin sidebar has Sign out too", async () => {
  mockApi({
    "GET /api/auth/me": () => ({ status: 200, body: ADMIN }),
    "GET /api/public/auth-status": () => ({ status: 200, body: { auth_enabled: true } }),
  });
  renderAt(app, "/admin/users");
  await screen.findByText("users page");
  expect(
    within(screen.getByRole("navigation", { name: "Account" })).getByRole("button", {
      name: "Sign out",
    }),
  ).toBeTruthy();
});
