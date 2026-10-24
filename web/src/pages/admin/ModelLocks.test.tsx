import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { Route, Routes } from "react-router-dom";
import { afterEach, expect, test, vi } from "vitest";
import { AdminLayout } from "../../AdminLayout";
import { ADMIN, ANALYST, mockApi, renderAt } from "../../test-utils";
import { ModelLocks } from "./ModelLocks";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

const lock = (over: object) => ({
  model_id: 1,
  holder_id: "u1",
  holder_name: "Kaushal Attal",
  activity: "update",
  taken_at: "2026-10-22T04:12:00Z",
  mine: false,
  job_running: false,
  model_name: "TCS model",
  company_symbol: "TCS",
  company_name: "Tata Consultancy Services Limited",
  ...over,
});
const LOCKS = [
  lock({ job_running: true }),
  lock({
    model_id: 2,
    holder_id: "u2",
    holder_name: "Arjun Shah",
    activity: "report",
    model_name: "ICICI Bank model",
    company_symbol: "ICICIBANK",
    company_name: "ICICI Bank Limited",
  }),
];
const rowOf = (text: string) => screen.getByText(text).closest("tr")!;

test("lists each lock with holder, model, activity, since and a running job", async () => {
  mockApi({
    "GET /api/auth/me": () => ({ status: 200, body: ADMIN }),
    "GET /api/admin/locks": () => ({ status: 200, body: LOCKS }),
  });
  renderAt(<ModelLocks />);
  await screen.findByText("Kaushal Attal");
  const tcs = rowOf("Kaushal Attal");
  expect(within(tcs).getByText("Tata Consultancy Services Limited")).toBeTruthy();
  expect(within(tcs).getByText(/TCS model/)).toBeTruthy();
  expect(within(tcs).getByText("Quarterly update")).toBeTruthy();
  expect(within(tcs).getByText(/22 Oct.*9:42/)).toBeTruthy(); // India time
  expect(within(tcs).getByText("Job running")).toBeTruthy();
  const icici = rowOf("Arjun Shah");
  expect(within(icici).getByText("Report")).toBeTruthy();
  expect(within(icici).queryByText("Job running")).toBeNull();
});

test("says so when no model is locked", async () => {
  mockApi({
    "GET /api/auth/me": () => ({ status: 200, body: ADMIN }),
    "GET /api/admin/locks": () => ({ status: 200, body: [] }),
  });
  renderAt(<ModelLocks />);
  expect(await screen.findByText("No one is working on a model right now.")).toBeTruthy();
  expect(screen.queryByRole("table")).toBeNull();
});

test("Release frees the model through the admin route, then the list is asked again", async () => {
  let released = false;
  const calls = mockApi({
    "GET /api/auth/me": () => ({ status: 200, body: ADMIN }),
    "GET /api/admin/locks": () => ({ status: 200, body: released ? [LOCKS[1]] : LOCKS }),
    "POST /api/admin/locks/1/release": () => {
      released = true;
      return { status: 204 };
    },
  });
  renderAt(<ModelLocks />);
  await screen.findByText("Kaushal Attal");
  fireEvent.click(within(rowOf("Kaushal Attal")).getByRole("button", { name: "Release" }));
  await waitFor(() => expect(screen.queryByText("Kaushal Attal")).toBeNull());
  expect(calls.filter((c) => c.method === "POST").map((c) => c.url)).toEqual([
    "/api/admin/locks/1/release",
  ]);
  expect(calls.filter((c) => c.url === "/api/admin/locks").length).toBe(2);
  expect(screen.getByText("Arjun Shah")).toBeTruthy();
});

test("a refused release is shown as the server says it", async () => {
  mockApi({
    "GET /api/auth/me": () => ({ status: 200, body: ADMIN }),
    "GET /api/admin/locks": () => ({ status: 200, body: LOCKS }),
    "POST /api/admin/locks/2/release": () => ({
      status: 404,
      body: { detail: "model not found" },
    }),
  });
  renderAt(<ModelLocks />);
  await screen.findByText("Arjun Shah");
  fireEvent.click(within(rowOf("Arjun Shah")).getByRole("button", { name: "Release" }));
  expect((await screen.findByRole("alert")).textContent).toContain("model not found");
});

const shell = (
  <Routes>
    <Route path="/admin" element={<AdminLayout />}>
      <Route path="locks" element={<ModelLocks />} />
    </Route>
    <Route path="*" element={<p>the desk</p>} />
  </Routes>
);

test("an analyst cannot reach the lock list", async () => {
  const calls = mockApi({
    "GET /api/auth/me": () => ({ status: 200, body: ANALYST }),
    "GET /api/admin/locks": () => ({ status: 403, body: { detail: "admins only" } }),
  });
  renderAt(shell, "/admin/locks");
  await screen.findByText("the desk");
  expect(screen.getByTestId("where").textContent).toBe("/");
  expect(calls.some((c) => c.url === "/api/admin/locks")).toBe(false);
});

test("the admin shell links to Model locks", async () => {
  mockApi({
    "GET /api/auth/me": () => ({ status: 200, body: ADMIN }),
    "GET /api/admin/locks": () => ({ status: 200, body: [] }),
  });
  renderAt(shell, "/admin/locks");
  await screen.findByText("No one is working on a model right now.");
  const nav = screen.getByRole("navigation", { name: "Admin" });
  expect(within(nav).getByRole("link", { name: "Model locks" })).toBeTruthy();
});
