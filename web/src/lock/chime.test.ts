import { fireEvent } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { playChime, resetChime, unlockChimeOnGesture } from "./chime";

// jsdom has no Web Audio: a small fake records what the chime builds.
const made = { contexts: 0, oscillators: 0, frequencies: [] as number[] };
class FakeAudioContext {
  state = "running";
  currentTime = 0;
  destination = {};
  constructor() {
    made.contexts += 1;
  }
  resume() {
    return Promise.resolve();
  }
  createOscillator() {
    made.oscillators += 1;
    const osc = {
      type: "sine",
      frequency: {
        set value(v: number) {
          made.frequencies.push(v);
        },
        setValueAtTime: (v: number) => made.frequencies.push(v),
      },
      connect: (n: unknown) => n,
      start: vi.fn(),
      stop: vi.fn(),
    };
    return osc;
  }
  createGain() {
    return {
      gain: {
        setValueAtTime: vi.fn(),
        exponentialRampToValueAtTime: vi.fn(),
        linearRampToValueAtTime: vi.fn(),
      },
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
  made.contexts = 0;
  made.oscillators = 0;
  made.frequencies = [];
  resetChime();
  vi.stubGlobal("AudioContext", FakeAudioContext);
  reducedMotion(false);
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

it("plays a 660 Hz tone when enabled", () => {
  playChime(true);
  expect(made.oscillators).toBe(1);
  expect(made.frequencies).toContain(660);
});

it("plays no chime when disabled", () => {
  playChime(false);
  expect(made.contexts).toBe(0);
  expect(made.oscillators).toBe(0);
});

it("plays no chime under reduced motion", () => {
  reducedMotion(true);
  playChime(true);
  expect(made.contexts).toBe(0);
  expect(made.oscillators).toBe(0);
});

it("never throws when the browser has no Web Audio", () => {
  vi.stubGlobal("AudioContext", undefined);
  expect(() => playChime(true)).not.toThrow();
});

it("never throws when the browser refuses an AudioContext", () => {
  vi.stubGlobal(
    "AudioContext",
    vi.fn(() => {
      throw new Error("NotAllowedError");
    }),
  );
  expect(() => playChime(true)).not.toThrow();
});

it("reuses one AudioContext and chimes at most once a second", () => {
  vi.useFakeTimers();
  playChime(true);
  playChime(true); // a second model freed in the same moment: no second chime
  expect(made.oscillators).toBe(1);
  vi.advanceTimersByTime(1001);
  playChime(true);
  expect(made.oscillators).toBe(2);
  expect(made.contexts).toBe(1);
});

it("wakes the shared AudioContext on the first gesture, so a later unprompted chime plays", () => {
  const resumed = vi.fn(() => Promise.resolve());
  class Suspended extends FakeAudioContext {
    state = "suspended";
    resume = resumed;
  }
  vi.stubGlobal("AudioContext", Suspended);
  const stop = unlockChimeOnGesture();
  expect(made.contexts).toBe(0); // nothing before the user does anything
  fireEvent.pointerDown(window);
  expect(made.contexts).toBe(1);
  expect(resumed).toHaveBeenCalledTimes(1);
  playChime(true); // later, with no gesture: the same, woken context
  expect(made.contexts).toBe(1);
  expect(made.oscillators).toBe(1);
  stop();
});

it("a key press also wakes it, and a stopped listener does nothing", () => {
  const stop = unlockChimeOnGesture();
  stop();
  fireEvent.keyDown(window, { key: "a" });
  expect(made.contexts).toBe(0);
  const again = unlockChimeOnGesture();
  fireEvent.keyDown(window, { key: "a" });
  expect(made.contexts).toBe(1);
  again();
});

it("waking never throws when the browser refuses an AudioContext", () => {
  vi.stubGlobal(
    "AudioContext",
    vi.fn(() => {
      throw new Error("NotAllowedError");
    }),
  );
  const stop = unlockChimeOnGesture();
  expect(() => fireEvent.pointerDown(window)).not.toThrow();
  stop();
});
