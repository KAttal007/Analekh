import { act, cleanup, fireEvent, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { useIdle } from "./useIdle";

const T = 30 * 60_000; // any threshold works; the app reads it from the settings

beforeEach(() => {
  vi.useFakeTimers();
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

it("flips to idle after the threshold with no input", () => {
  const { result } = renderHook(() => useIdle(T));
  expect(result.current.idle).toBe(false);
  act(() => vi.advanceTimersByTime(T));
  expect(result.current.idle).toBe(true);
});

it("input just before the threshold starts the wait again", () => {
  const { result } = renderHook(() => useIdle(T));
  act(() => vi.advanceTimersByTime(T - 1));
  act(() => {
    fireEvent.keyDown(window, { key: "a" });
  });
  act(() => vi.advanceTimersByTime(1));
  expect(result.current.idle).toBe(false);
  act(() => vi.advanceTimersByTime(T - 2));
  expect(result.current.idle).toBe(false);
  act(() => vi.advanceTimersByTime(2));
  expect(result.current.idle).toBe(true);
});

it.each([
  ["pointerdown", () => fireEvent.pointerDown(window)],
  ["keydown", () => fireEvent.keyDown(window, { key: "x" })],
  ["wheel", () => fireEvent.wheel(window)],
  ["touchstart", () => fireEvent.touchStart(window)],
])("%s counts as activity and ends idle", (_name, input) => {
  const { result } = renderHook(() => useIdle(T));
  act(() => vi.advanceTimersByTime(T));
  expect(result.current.idle).toBe(true);
  act(() => {
    input();
  });
  expect(result.current.idle).toBe(false);
  act(() => vi.advanceTimersByTime(T));
  expect(result.current.idle).toBe(true);
});

it("pointer movement alone is not activity", () => {
  const { result } = renderHook(() => useIdle(T));
  act(() => vi.advanceTimersByTime(T - 1));
  act(() => {
    fireEvent.pointerMove(window);
  });
  act(() => vi.advanceTimersByTime(1));
  expect(result.current.idle).toBe(true);
});

it("reset() ends idle and starts the wait again", () => {
  const { result } = renderHook(() => useIdle(T));
  act(() => vi.advanceTimersByTime(T));
  act(() => result.current.reset());
  expect(result.current.idle).toBe(false);
  act(() => vi.advanceTimersByTime(T - 1));
  expect(result.current.idle).toBe(false);
  act(() => vi.advanceTimersByTime(1));
  expect(result.current.idle).toBe(true);
});

it("never goes idle while the threshold is unknown (0)", () => {
  const { result } = renderHook(() => useIdle(0));
  act(() => vi.advanceTimersByTime(24 * 60 * 60_000));
  expect(result.current.idle).toBe(false);
});

it("stops listening when unmounted", () => {
  const off = vi.spyOn(window, "removeEventListener");
  const { unmount } = renderHook(() => useIdle(T));
  unmount();
  const removed = off.mock.calls.map((c) => c[0]);
  expect(removed).toEqual(expect.arrayContaining(["pointerdown", "keydown", "wheel", "touchstart"]));
  off.mockRestore();
});
