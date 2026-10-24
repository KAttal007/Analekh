import { useMutation } from "@tanstack/react-query";
import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { useEffect } from "react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { ANALYST, type Handler, mockApi, renderAt } from "../test-utils";
import { resetChime } from "./chime";
import { IdleReminder } from "./IdleReminder";

// The idle threshold comes from the settings reply; here it is 60 ms so the tests run on real
// timers (React Query's fetches need them). Locks are asked for every 30 ms.
const IDLE_MINUTES = 0.001;
const SETTINGS = {
  bytes: 1,
  ceiling_bytes: 2,
  min_bytes: 1,
  updated_by: null,
  updated_at: null,
  lock_poll_seconds: 0.03,
  idle_reminder_minutes: IDLE_MINUTES,
};
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
const mine = (model_id: number, over: Record<string, unknown> = {}) => ({
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
const TCS = "You still have Tata Consultancy Services's model open. Close it if you are done.";

function routes(extra: Record<string, Handler> = {}) {
  return {
    "GET /api/auth/me": () => ({ status: 200, body: ANALYST }),
    "GET /api/settings/upload-limit": () => ({ status: 200, body: SETTINGS }),
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
    ...extra,
  };
}

let tones = 0;
class FakeAudioContext {
  state = "running";
  currentTime = 0;
  destination = {};
  resume() {
    return Promise.resolve();
  }
  createOscillator() {
    tones += 1;
    return {
      type: "sine",
      frequency: { value: 0, setValueAtTime: vi.fn() },
      connect: (n: unknown) => n,
      start: vi.fn(),
      stop: vi.fn(),
    };
  }
  createGain() {
    return {
      gain: { setValueAtTime: vi.fn(), exponentialRampToValueAtTime: vi.fn() },
      connect: (n: unknown) => n,
    };
  }
}
const reducedMotion = (on: boolean) =>
  vi.stubGlobal(
    "matchMedia",
    vi.fn((q: string) => ({
      matches: on && q.includes("prefers-reduced-motion: reduce"),
      media: q,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    })),
  );
const wait = (ms: number) => new Promise((r) => setTimeout(r, ms));

beforeEach(() => {
  held = [];
  tones = 0;
  resetChime();
  vi.stubGlobal("AudioContext", FakeAudioContext);
  reducedMotion(false);
});

afterEach(() => {
  cleanup();
  localStorage.clear();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

it("reminds an idle holder, naming the company, with a chime", async () => {
  held = [mine(1)];
  mockApi(routes());
  renderAt(<IdleReminder />);
  expect(await screen.findByText(TCS)).toBeTruthy();
  expect(screen.getByRole("button", { name: "Close" })).toBeTruthy();
  expect(screen.getByRole("button", { name: "Keep open" })).toBeTruthy();
  expect(tones).toBe(1);
});

it("chimes once per appearance, not on every poll", async () => {
  held = [mine(1)];
  mockApi(routes());
  renderAt(<IdleReminder />);
  await screen.findByText(TCS);
  await wait(200); // several polls while it is up
  expect(screen.getByText(TCS)).toBeTruthy();
  expect(tones).toBe(1);
});

it("no chime under reduced motion, but the reminder still shows", async () => {
  reducedMotion(true);
  held = [mine(1)];
  mockApi(routes());
  renderAt(<IdleReminder />);
  expect(await screen.findByText(TCS)).toBeTruthy();
  expect(tones).toBe(0);
});

it("no chime when the chime is off in Settings", async () => {
  localStorage.setItem("analekh.prefs", JSON.stringify({ chime: false }));
  held = [mine(1)];
  mockApi(routes());
  renderAt(<IdleReminder />);
  expect(await screen.findByText(TCS)).toBeTruthy();
  expect(tones).toBe(0);
});

it("does not show while the user keeps working", async () => {
  held = [mine(1)];
  mockApi(routes());
  renderAt(<IdleReminder />);
  for (let i = 0; i < 6; i += 1) {
    await wait(30);
    fireEvent.pointerDown(window);
  }
  expect(screen.queryByText(TCS)).toBeNull();
});

it("no locks: no reminder, however long the user is idle", async () => {
  const calls = mockApi(routes());
  renderAt(<IdleReminder />);
  await waitFor(() => expect(calls.some((c) => c.url.startsWith("/api/me/locks"))).toBe(true));
  await wait(200);
  expect(screen.queryByRole("region", { name: "Models still open" })).toBeNull();
  expect(tones).toBe(0);
});

it("does not show the reminder while a job is running, then shows it once it ends", async () => {
  held = [mine(1, { job_running: true })];
  mockApi(routes());
  renderAt(<IdleReminder />);
  await wait(250); // idle, polled several times
  expect(screen.queryByText(TCS)).toBeNull();
  expect(tones).toBe(0);
  held = [mine(1, { job_running: false })]; // the update finished; the lock is still the user's
  expect(await screen.findByText(TCS)).toBeTruthy();
  expect(tones).toBe(1);
});

it("one running job keeps the reminder away for every model", async () => {
  held = [mine(1), mine(2, { job_running: true })];
  mockApi(routes());
  renderAt(<IdleReminder />);
  await wait(250);
  expect(screen.queryByRole("region", { name: "Models still open" })).toBeNull();
});

/** Something the user started in this tab (a build, a finalize) that has not answered yet. */
function InFlight({ until }: { until: Promise<unknown> }) {
  const m = useMutation({ mutationFn: () => until });
  const { mutate } = m;
  useEffect(() => mutate(), [mutate]);
  return null;
}

it("does not show while a build or report runs in this tab, then shows when it ends", async () => {
  held = [mine(1)];
  mockApi(routes());
  let finish: (v: unknown) => void = () => undefined;
  const until = new Promise((r) => {
    finish = r;
  });
  renderAt(
    <>
      <InFlight until={until} />
      <IdleReminder />
    </>,
  );
  await wait(250);
  expect(screen.queryByText(TCS)).toBeNull();
  finish({});
  expect(await screen.findByText(TCS)).toBeTruthy();
});

it("Keep open hides it and starts the wait again", async () => {
  held = [mine(1)];
  const calls = mockApi(routes());
  renderAt(<IdleReminder />);
  fireEvent.click(await screen.findByRole("button", { name: "Keep open" }));
  expect(screen.queryByText(TCS)).toBeNull();
  expect(calls.some((c) => c.method === "POST")).toBe(false);
  // Idle again after another full wait: it comes back.
  expect(await screen.findByText(TCS)).toBeTruthy();
});

it("stays up when the user comes back, until answered", async () => {
  held = [mine(1)];
  mockApi(routes());
  renderAt(<IdleReminder />);
  await screen.findByText(TCS);
  fireEvent.keyDown(window, { key: "a" });
  await wait(100);
  expect(screen.getByText(TCS)).toBeTruthy();
});

it("Close gives the lock back and hides the reminder", async () => {
  held = [mine(1)];
  const calls = mockApi(routes());
  renderAt(<IdleReminder />);
  fireEvent.click(await screen.findByRole("button", { name: "Close" }));
  await waitFor(() =>
    expect(calls.some((c) => c.method === "POST" && c.url === "/api/models/1/lock/release")).toBe(
      true,
    ),
  );
  await waitFor(() => expect(screen.queryByText(TCS)).toBeNull());
  await wait(200); // idle again, nothing held: no reminder
  expect(screen.queryByRole("region", { name: "Models still open" })).toBeNull();
});

it("several models: one reminder lists each with its own Close, and one Keep open", async () => {
  held = [mine(1), mine(2)];
  const calls = mockApi(routes());
  renderAt(<IdleReminder />);
  const box = await screen.findByRole("region", { name: "Models still open" });
  expect(box.textContent).toContain("You still have 2 models open.");
  expect(box.textContent).toContain("Tata Consultancy Services");
  expect(box.textContent).toContain("Infosys");
  expect(screen.getAllByRole("button", { name: /^Close/ })).toHaveLength(2);
  expect(screen.getAllByRole("button", { name: "Keep open" })).toHaveLength(1);
  expect(tones).toBe(1);
  fireEvent.click(screen.getByRole("button", { name: "Close Infosys's model" }));
  await waitFor(() =>
    expect(calls.some((c) => c.method === "POST" && c.url === "/api/models/2/lock/release")).toBe(
      true,
    ),
  );
  // One left: the reminder now reads as for one model.
  expect(await screen.findByText(TCS)).toBeTruthy();
  expect(screen.queryByText(/Infosys/)).toBeNull();
});

it("a job that starts while it is up shows as running, and Close goes", async () => {
  held = [mine(1)];
  mockApi(routes());
  renderAt(<IdleReminder />);
  await screen.findByText(TCS);
  held = [mine(1, { job_running: true })]; // an update started from another tab
  const box = screen.getByRole("region", { name: "Models still open" });
  await waitFor(() => expect(box.textContent).toMatch(/running/i));
  expect(screen.queryByRole("button", { name: /^Close/ })).toBeNull();
  expect(box.textContent).not.toContain("Close it if you are done");
});

it("several models: a running one is listed without its Close", async () => {
  held = [mine(1), mine(2)];
  mockApi(routes());
  renderAt(<IdleReminder />);
  await screen.findByRole("region", { name: "Models still open" });
  held = [mine(1), mine(2, { job_running: true })];
  await waitFor(() =>
    expect(screen.queryByRole("button", { name: "Close Infosys's model" })).toBeNull(),
  );
  expect(
    screen.getByRole("button", { name: "Close Tata Consultancy Services's model" }),
  ).toBeTruthy();
});

it("never goes idle before the settings say how long to wait", async () => {
  held = [mine(1)];
  mockApi(routes({ "GET /api/settings/upload-limit": () => ({ status: 500, body: {} }) }));
  renderAt(<IdleReminder />);
  await wait(200);
  expect(screen.queryByRole("region", { name: "Models still open" })).toBeNull();
});
