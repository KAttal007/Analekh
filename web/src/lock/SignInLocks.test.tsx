import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { Link, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { Layout } from "../Layout";
import { ANALYST, mockApi, renderAt } from "../test-utils";
import { forgetSignInLocks, SignInLocks } from "./SignInLocks";

const model = (id: number, company_id: number) => ({
  id,
  company_id,
  template_id: null,
  name: `Model ${id}`,
  origin: "linked",
  doc_tag: `5f0c6b8e-0000-4000-8000-00000000000${id}`,
  file_path: null,
  last_seen: null,
});
const INDEX = [
  { id: 10, nse_symbol: "TCS", name: "Tata Consultancy Services", isin: null, sector: null },
  { id: 20, nse_symbol: "INFY", name: "Infosys", isin: null, sector: null },
];
const mine = (model_id: number, over: { job_running?: boolean } = {}) => ({
  model_id,
  holder_id: ANALYST.id,
  holder_name: ANALYST.name,
  activity: "update",
  taken_at: "2026-10-24T10:42:00Z",
  mine: true,
  job_running: false,
  ...over,
});

let held: ReturnType<typeof mine>[] = [];
const routes = () => ({
  "GET /api/auth/me": () => ({ status: 200, body: ANALYST }),
  "GET /api/me/locks": () => ({ status: 200, body: held }),
  "GET /api/models": () => ({ status: 200, body: [model(1, 10), model(2, 20)] }),
  "GET /api/companies/index": () => ({ status: 200, body: INDEX }),
  "POST /api/models/1/lock/release": () => {
    held = held.filter((l) => l.model_id !== 1);
    return { status: 204 };
  },
  "POST /api/models/2/lock/release": () => {
    held = held.filter((l) => l.model_id !== 2);
    return { status: 204 };
  },
});

const wait = (ms: number) => new Promise((r) => setTimeout(r, ms));

beforeEach(() => {
  held = [];
  sessionStorage.clear();
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

it("sign-in lists each held model with a Close button", async () => {
  held = [mine(1), mine(2)];
  mockApi(routes());
  renderAt(<SignInLocks />);
  const box = await screen.findByRole("region", { name: "Models still open" });
  expect(box.textContent).toContain("You still have 2 models open");
  expect(box.textContent).toContain("Tata Consultancy Services");
  expect(box.textContent).toContain("Infosys");
  expect(
    screen.getByRole("button", { name: "Close Tata Consultancy Services's model" }),
  ).toBeTruthy();
  expect(screen.getByRole("button", { name: "Close Infosys's model" })).toBeTruthy();
});

it("says model, not models, for one", async () => {
  held = [mine(1)];
  mockApi(routes());
  renderAt(<SignInLocks />);
  const box = await screen.findByRole("region", { name: "Models still open" });
  expect(box.textContent).toContain("You still have 1 model open");
  expect(box.textContent).not.toContain("models open");
});

it("a model whose update job is running shows as running, with no Close", async () => {
  held = [mine(1, { job_running: true }), mine(2)];
  mockApi(routes());
  renderAt(<SignInLocks />);
  const box = await screen.findByRole("region", { name: "Models still open" });
  expect(box.textContent).toContain("Tata Consultancy Services");
  expect(box.textContent).toContain("Running");
  expect(
    screen.queryByRole("button", { name: "Close Tata Consultancy Services's model" }),
  ).toBeNull();
  expect(screen.getByRole("button", { name: "Close Infosys's model" })).toBeTruthy();
});

it("only running work: no invitation to close anything", async () => {
  held = [mine(1, { job_running: true })];
  mockApi(routes());
  renderAt(<SignInLocks />);
  const box = await screen.findByRole("region", { name: "Models still open" });
  expect(box.textContent).not.toContain("Close it if you are done");
  expect(screen.queryByRole("button", { name: /^Close/ })).toBeNull();
  expect(screen.getByRole("button", { name: "Keep open" })).toBeTruthy();
});

it("nothing held: nothing shown", async () => {
  const calls = mockApi(routes());
  renderAt(<SignInLocks />);
  await waitFor(() => expect(calls.some((c) => c.url.startsWith("/api/me/locks"))).toBe(true));
  await wait(50);
  expect(screen.queryByRole("region", { name: "Models still open" })).toBeNull();
});

it("Close gives that model back; the last one closes the reminder", async () => {
  held = [mine(1), mine(2)];
  const calls = mockApi(routes());
  renderAt(<SignInLocks />);
  fireEvent.click(await screen.findByRole("button", { name: "Close Infosys's model" }));
  await waitFor(() => expect(screen.queryByText(/Infosys/)).toBeNull());
  expect(calls.some((c) => c.method === "POST" && c.url === "/api/models/2/lock/release")).toBe(
    true,
  );
  expect(screen.getByRole("region", { name: "Models still open" }).textContent).toContain(
    "You still have 1 model open",
  );
  fireEvent.click(screen.getByRole("button", { name: "Close Tata Consultancy Services's model" }));
  await waitFor(() =>
    expect(screen.queryByRole("region", { name: "Models still open" })).toBeNull(),
  );
});

it("Keep open dismisses it without giving anything back", async () => {
  held = [mine(1)];
  const calls = mockApi(routes());
  renderAt(<SignInLocks />);
  fireEvent.click(await screen.findByRole("button", { name: "Keep open" }));
  expect(screen.queryByRole("region", { name: "Models still open" })).toBeNull();
  expect(calls.some((c) => c.method === "POST")).toBe(false);
});

it("shows once after sign-in, not again on moving between pages", async () => {
  held = [mine(1)];
  mockApi(routes());
  renderAt(
    <>
      <SignInLocks />
      <Link to="/models">Models</Link>
      <Routes>
        <Route path="/" element={<p>home</p>} />
        <Route path="/models" element={<p>models</p>} />
      </Routes>
    </>,
  );
  fireEvent.click(await screen.findByRole("button", { name: "Keep open" }));
  fireEvent.click(screen.getByRole("link", { name: "Models" }));
  await screen.findByText("models");
  await wait(50);
  expect(screen.queryByRole("region", { name: "Models still open" })).toBeNull();
});

it("not again when the shell is mounted again in the same session", async () => {
  held = [mine(1)];
  mockApi(routes());
  const first = renderAt(<SignInLocks />);
  await screen.findByRole("region", { name: "Models still open" });
  first.unmount();
  renderAt(<SignInLocks />);
  await wait(80);
  expect(screen.queryByRole("region", { name: "Models still open" })).toBeNull();
});

it("shows again after signing out and in", async () => {
  held = [mine(1)];
  mockApi(routes());
  const first = renderAt(<SignInLocks />);
  await screen.findByRole("region", { name: "Models still open" });
  first.unmount();
  forgetSignInLocks(); // what sign-out does
  renderAt(<SignInLocks />);
  expect(await screen.findByRole("region", { name: "Models still open" })).toBeTruthy();
});

it("the app shell shows it", async () => {
  held = [mine(1)];
  mockApi(routes());
  renderAt(
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<p>home</p>} />
      </Route>
    </Routes>,
  );
  const box = await screen.findByRole("region", { name: "Models still open" });
  expect(box.textContent).toContain("You still have 1 model open");
});
