import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { Route, Routes } from "react-router-dom";
import { Models } from "../pages/Models";
import { ADMIN, ANALYST, type Handler, mockApi, renderAt } from "../test-utils";
import { resetChime } from "./chime";
import { clearFreed } from "./freed";
import { LockToast, LockToasts } from "./LockToast";
import { useModelLock } from "./useModelLock";

/** Each model's lock answer, changed by the test as colleagues come and go. */
const locks: Record<number, unknown> = {};

// Web Audio is faked: each tone is one oscillator.
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

beforeEach(() => {
  tones = 0;
  for (const k of Object.keys(locks)) delete locks[Number(k)];
  resetChime();
  vi.stubGlobal("AudioContext", FakeAudioContext);
  reducedMotion(false);
});

afterEach(() => {
  cleanup();
  clearFreed();
  localStorage.clear();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

const TCS_TEXT = "Tata Consultancy Services's model is free. You can open it for editing.";
const INFY_TEXT = "Infosys's model is free. You can open it for editing.";
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
const lockOf = (model_id: number, over: Record<string, unknown> = {}) => ({
  model_id,
  holder_id: "u2",
  holder_name: "Rhea",
  activity: "update",
  taken_at: "2026-10-24T10:42:00Z",
  mine: false,
  ...over,
});

function routes(extra: Record<string, Handler> = {}) {
  return {
    "GET /api/auth/me": () => ({ status: 200, body: ANALYST }),
    "GET /api/models": () => ({ status: 200, body: [model(1, 10), model(2, 20)] }),
    "GET /api/companies/index": () => ({ status: 200, body: INDEX }),
    "GET /api/models/1/lock": () => ({ status: 200, body: locks[1] ?? null }),
    "GET /api/models/2/lock": () => ({ status: 200, body: locks[2] ?? null }),
    ...extra,
  };
}

/** A page that watches one model's lock, as Models and Assumptions do. */
function Watch({ id }: { id: number }) {
  const gate = useModelLock(id, 25, { freedTo: `/models/${id}/assumptions` });
  return <p data-testid={`lock-${id}`}>{gate.held ? "held" : gate.loaded ? "free" : "..."}</p>;
}
const shows = async (id: number, state: "held" | "free") => waitFor(() => expect(screen.getByTestId(`lock-${id}`).textContent).toBe(state));
const settle = () => new Promise((r) => setTimeout(r, 80)); // a few polls

it("the toast names the company and opens the model when clicked", () => {
  const onOpen = vi.fn();
  render(<LockToast companyName="Tata Consultancy Services" modelId={1} onOpen={onOpen} />);
  fireEvent.click(screen.getByRole("button", { name: TCS_TEXT }));
  expect(onOpen).toHaveBeenCalledTimes(1);
});

it("shows the free toast, with a chime, to a colleague who saw the model held", async () => {
  locks[1] = lockOf(1);
  mockApi(routes());
  renderAt(
    <>
      <Watch id={1} />
      <LockToasts />
    </>,
  );
  await shows(1, "held");
  expect(screen.queryByText(TCS_TEXT)).toBeNull();
  locks[1] = null;
  expect(await screen.findByText(TCS_TEXT)).toBeTruthy();
  expect(tones).toBe(1);
  // It stays until dismissed.
  await settle();
  expect(screen.getByText(TCS_TEXT)).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Dismiss" }));
  expect(screen.queryByText(TCS_TEXT)).toBeNull();
});

it("never tells a viewer who only ever saw the model free", async () => {
  locks[1] = null;
  mockApi(routes());
  renderAt(
    <>
      <Watch id={1} />
      <LockToasts />
    </>,
  );
  await shows(1, "free");
  await settle();
  expect(screen.queryByText(/is free/)).toBeNull();
  expect(tones).toBe(0);
});

it("my own lock given back is not news to me", async () => {
  locks[1] = null;
  mockApi(routes());
  renderAt(
    <>
      <Watch id={1} />
      <LockToasts />
    </>,
  );
  await shows(1, "free");
  locks[1] = lockOf(1, { mine: true, holder_name: "Kaushal Attal" });
  await settle();
  locks[1] = null;
  await settle();
  expect(screen.queryByText(/is free/)).toBeNull();
});

it("a model taken after the page opened and then given back is announced", async () => {
  locks[1] = null;
  mockApi(routes());
  renderAt(
    <>
      <Watch id={1} />
      <LockToasts />
    </>,
  );
  await shows(1, "free");
  locks[1] = lockOf(1);
  await shows(1, "held");
  locks[1] = null;
  expect(await screen.findByText(TCS_TEXT)).toBeTruthy();
});

it("a lock passed from one colleague to another is not free", async () => {
  locks[1] = lockOf(1, { holder_id: "u2", holder_name: "Rhea" });
  mockApi(routes());
  renderAt(
    <>
      <Watch id={1} />
      <LockToasts />
    </>,
  );
  await shows(1, "held");
  locks[1] = lockOf(1, { holder_id: "u3", holder_name: "Arjun" });
  await settle();
  expect(screen.getByTestId("lock-1").textContent).toBe("held");
  expect(screen.queryByText(/is free/)).toBeNull();
  expect(tones).toBe(0);
});

it("under reduced motion the toast shows but no chime plays", async () => {
  reducedMotion(true);
  locks[1] = lockOf(1);
  mockApi(routes());
  renderAt(
    <>
      <Watch id={1} />
      <LockToasts />
    </>,
  );
  await shows(1, "held");
  locks[1] = null;
  expect(await screen.findByText(TCS_TEXT)).toBeTruthy();
  expect(tones).toBe(0);
});

it("with the chime turned off in Settings the toast shows but no chime plays", async () => {
  localStorage.setItem("analekh.prefs", JSON.stringify({ chime: false }));
  locks[1] = lockOf(1);
  mockApi(routes());
  renderAt(
    <>
      <Watch id={1} />
      <LockToasts />
    </>,
  );
  await shows(1, "held");
  locks[1] = null;
  expect(await screen.findByText(TCS_TEXT)).toBeTruthy();
  expect(tones).toBe(0);
});

it("a browser that refuses audio still gets the toast", async () => {
  vi.stubGlobal(
    "AudioContext",
    vi.fn(() => {
      throw new Error("NotAllowedError");
    }),
  );
  locks[1] = lockOf(1);
  mockApi(routes());
  renderAt(
    <>
      <Watch id={1} />
      <LockToasts />
    </>,
  );
  await shows(1, "held");
  locks[1] = null;
  expect(await screen.findByText(TCS_TEXT)).toBeTruthy();
});

it("two models freed together: two toasts, one chime", async () => {
  locks[1] = lockOf(1);
  locks[2] = lockOf(2);
  mockApi(routes());
  renderAt(
    <>
      <Watch id={1} />
      <Watch id={2} />
      <LockToasts />
    </>,
  );
  await shows(1, "held");
  await shows(2, "held");
  locks[1] = null;
  locks[2] = null;
  expect(await screen.findByText(TCS_TEXT)).toBeTruthy();
  expect(await screen.findByText(INFY_TEXT)).toBeTruthy();
  expect(tones).toBe(1);
});

it("clicking the toast opens that model and clears the toast", async () => {
  locks[1] = lockOf(1);
  mockApi(routes());
  renderAt(
    <>
      <Watch id={1} />
      <LockToasts />
    </>,
    "/somewhere",
  );
  await shows(1, "held");
  locks[1] = null;
  fireEvent.click(await screen.findByRole("button", { name: TCS_TEXT }));
  expect(screen.getByTestId("where").textContent).toBe("/models/1/assumptions");
  expect(screen.queryByText(TCS_TEXT)).toBeNull();
});

it("on the Models page the freed model's buttons come back with the toast", async () => {
  locks[1] = lockOf(1);
  mockApi(
    routes({
      "GET /api/models": () => ({ status: 200, body: [model(1, 10)] }),
      "GET /api/settings/upload-limit": () => ({
        status: 200,
        body: {
          bytes: 1,
          ceiling_bytes: 2,
          min_bytes: 1,
          updated_by: null,
          updated_at: null,
          lock_poll_seconds: 1,
        },
      }),
    }),
  );
  renderAt(
    <>
      <Routes>
        <Route path="/models" element={<Models />} />
      </Routes>
      <LockToasts />
    </>,
    "/models",
  );
  await screen.findByText(/In use by Rhea/);
  locks[1] = null;
  const toast = await screen.findByRole("button", { name: TCS_TEXT }, { timeout: 3000 });
  fireEvent.click(toast);
  expect(screen.getByTestId("where").textContent).toBe("/models");
  const update = screen.getByRole("button", { name: /update/i }) as HTMLButtonElement;
  expect(update.disabled).toBe(false);
});

it("an admin who releases the lock is not told it is free", async () => {
  locks[1] = lockOf(1);
  mockApi(
    routes({
      "GET /api/auth/me": () => ({ status: 200, body: ADMIN }),
      "GET /api/models": () => ({ status: 200, body: [model(1, 10)] }),
      "POST /api/admin/locks/1/release": () => {
        locks[1] = null;
        return { status: 204 };
      },
    }),
  );
  renderAt(
    <>
      <Models />
      <LockToasts />
    </>,
  );
  fireEvent.click(await screen.findByRole("button", { name: "Release lock" }));
  await waitFor(() => expect(screen.queryByText(/In use by/)).toBeNull());
  await settle();
  expect(screen.queryByText(/is free/)).toBeNull();
  expect(tones).toBe(0);
});
