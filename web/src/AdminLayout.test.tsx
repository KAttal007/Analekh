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

test("the admin shell shows exactly Users, Templates, Settings and a way back", async () => {
  mockApi({ "GET /api/auth/me": () => ({ status: 200, body: ADMIN }) });
  renderAt(app, "/admin/users");
  await screen.findByText("users page");
  const nav = screen.getByRole("navigation", { name: "Admin" });
  const labels = Array.from(nav.querySelectorAll("a")).map((a) => a.textContent?.trim());
  expect(labels).toEqual(["Users", "Templates", "Settings", "← Back to Analekh"]);
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
