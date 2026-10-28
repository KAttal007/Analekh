import { QueryClient, QueryClientProvider, useQuery } from "@tanstack/react-query";
import { act, cleanup, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, expect, test, vi } from "vitest";
import { mockApi } from "../test-utils";
import { lockedDetail, useModelLock } from "./useModelLock";
import { ApiError } from "../api/client";

let visibility: DocumentVisibilityState = "visible";
Object.defineProperty(document, "visibilityState", {
  configurable: true,
  get: () => visibility,
});
const setVisibility = (state: DocumentVisibilityState) => {
  visibility = state;
  document.dispatchEvent(new Event("visibilitychange", { bubbles: true }));
};

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  visibility = "visible";
});

// Like the app: data stays fresh for five minutes. The lock must not.
function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: 5 * 60_000 } },
  });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

const HELD = {
  model_id: 1,
  holder_id: "u2",
  holder_name: "Kaushal",
  activity: "update",
  taken_at: "2026-10-24T10:42:00Z",
  mine: false,
};
const lockCalls = (calls: { url: string }[]) => calls.filter((c) => c.url === "/api/models/1/lock").length;

test("a free model has no lock and is not mine", async () => {
  mockApi({ "GET /api/models/1/lock": () => ({ status: 200, body: null }) });
  const { result } = renderHook(() => useModelLock(1, 0), { wrapper });
  await waitFor(() => expect(result.current.loaded).toBe(true));
  expect(result.current.lock).toBeNull();
  expect(result.current.mine).toBe(false);
});

test("a colleague's lock is reported, and is not mine", async () => {
  mockApi({ "GET /api/models/1/lock": () => ({ status: 200, body: HELD }) });
  const { result } = renderHook(() => useModelLock(1, 0), { wrapper });
  await waitFor(() => expect(result.current.lock?.holder_name).toBe("Kaushal"));
  expect(result.current.mine).toBe(false);
});

test("my own lock is mine", async () => {
  mockApi({ "GET /api/models/1/lock": () => ({ status: 200, body: { ...HELD, mine: true } }) });
  const { result } = renderHook(() => useModelLock(1, 0), { wrapper });
  await waitFor(() => expect(result.current.mine).toBe(true));
});

test("polls every pollMs, and a lock given back shows as free", async () => {
  let body: unknown = HELD;
  const calls = mockApi({ "GET /api/models/1/lock": () => ({ status: 200, body }) });
  const { result } = renderHook(() => useModelLock(1, 40), { wrapper });
  await waitFor(() => expect(result.current.lock).not.toBeNull());
  body = null;
  await waitFor(() => expect(result.current.lock).toBeNull());
  expect(lockCalls(calls)).toBeGreaterThanOrEqual(2);
});

test("with nothing to wait for, polling stops while the page is hidden and resumes on return", async () => {
  for (const body of [null, { ...HELD, mine: true }]) {
    const calls = mockApi({ "GET /api/models/1/lock": () => ({ status: 200, body }) });
    const { result, unmount } = renderHook(() => useModelLock(1, 30), { wrapper });
    await waitFor(() => expect(result.current.loaded).toBe(true));
    act(() => setVisibility("hidden"));
    await new Promise((r) => setTimeout(r, 40)); // a poll already under way may still land
    const before = lockCalls(calls);
    await new Promise((r) => setTimeout(r, 150));
    expect(lockCalls(calls)).toBe(before);
    act(() => setVisibility("visible"));
    await waitFor(() => expect(lockCalls(calls)).toBeGreaterThan(before));
    unmount();
    vi.restoreAllMocks();
  }
});

test("waiting on a colleague, a hidden tab keeps polling and hears the model is free", async () => {
  let body: unknown = HELD;
  const calls = mockApi({ "GET /api/models/1/lock": () => ({ status: 200, body }) });
  const { result } = renderHook(() => useModelLock(1, 30), { wrapper });
  await waitFor(() => expect(result.current.held).toBe(true));
  act(() => setVisibility("hidden"));
  const before = lockCalls(calls);
  await waitFor(() => expect(lockCalls(calls)).toBeGreaterThan(before + 1));
  body = null;
  await waitFor(() => expect(result.current.held).toBe(false));
  expect(visibility).toBe("hidden");
});

test("when a colleague's lock ends, the page's data is reloaded before it shows as free", async () => {
  let body: unknown = HELD;
  let rows = "before";
  let reload: () => void = () => {};
  mockApi({
    "GET /api/models/1/lock": () => ({ status: 200, body }),
  });
  const { result } = renderHook(
    () => {
      const gate = useModelLock(1, 30, { refreshOnFree: [["rows", 1]] });
      const data = useQuery({
        queryKey: ["rows", 1],
        queryFn: () => (rows === "before" ? Promise.resolve(rows) : new Promise<string>((ok) => (reload = () => ok(rows)))),
      });
      return { gate, data: data.data };
    },
    { wrapper },
  );
  await waitFor(() => expect(result.current.data).toBe("before"));
  await waitFor(() => expect(result.current.gate.held).toBe(true));
  rows = "after"; // a colleague's work changed the rows; the next read waits until let go
  body = null;
  await new Promise((r) => setTimeout(r, 120)); // several polls see it free...
  expect(result.current.gate.held).toBe(true); // ...but it stays read-only while the rows reload
  act(() => reload());
  await waitFor(() => expect(result.current.gate.held).toBe(false));
  expect(result.current.data).toBe("after");
});

test("refresh asks again at once", async () => {
  const calls = mockApi({ "GET /api/models/1/lock": () => ({ status: 200, body: null }) });
  const { result } = renderHook(() => useModelLock(1, 0), { wrapper });
  await waitFor(() => expect(result.current.loaded).toBe(true));
  act(() => result.current.refresh());
  await waitFor(() => expect(lockCalls(calls)).toBe(2));
});

test("heldBy shows a 423's holder at once, then checks with the server", async () => {
  // The server's second answer waits until the test lets it go, so the 423's holder is seen first.
  let answer: (r: Response) => void = () => {};
  const asks = vi
    .spyOn(globalThis, "fetch")
    .mockResolvedValueOnce(new Response("null", { status: 200 }))
    .mockImplementationOnce(() => new Promise<Response>((ok) => (answer = ok)));
  const { result } = renderHook(() => useModelLock(1, 0), { wrapper });
  await waitFor(() => expect(result.current.loaded).toBe(true));
  act(() =>
    result.current.heldBy({
      code: "model_locked",
      holder_name: "Kaushal",
      taken_at: HELD.taken_at,
      activity: "report",
    }),
  );
  await waitFor(() => expect(result.current.lock?.activity).toBe("report"));
  expect(result.current.mine).toBe(false);
  expect(result.current.held).toBe(true);
  expect(asks).toHaveBeenCalledTimes(2); // ...and the server is asked again
  answer(new Response(JSON.stringify(HELD), { status: 200 }));
  await waitFor(() => expect(result.current.lock?.activity).toBe("update"));
});

test("lockedDetail reads a 423 and nothing else", () => {
  const detail = { code: "model_locked", holder_name: "Kaushal", taken_at: "x", activity: "build" };
  expect(lockedDetail(new ApiError(423, JSON.stringify(detail)))).toEqual(detail);
  expect(lockedDetail(new ApiError(409, JSON.stringify(detail)))).toBeNull();
  expect(lockedDetail(new ApiError(423, "not json"))).toBeNull();
  expect(lockedDetail(new Error("boom"))).toBeNull();
});
