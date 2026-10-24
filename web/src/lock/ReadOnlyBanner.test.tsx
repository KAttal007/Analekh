import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, test } from "vitest";
import { ReadOnlyBanner, sinceText } from "./ReadOnlyBanner";

afterEach(cleanup);

// A moment on the viewer's own clock: the banner speaks local time, whatever the zone.
const local = (y: number, mo: number, d: number, h: number, mi: number) =>
  new Date(y, mo - 1, d, h, mi).toISOString();

test("today's lock shows the holder and the local time, HH:MM", () => {
  render(<ReadOnlyBanner holderName="Kaushal" takenAt={local(2026, 10, 24, 10, 42)} />);
  // The banner reads the real clock; only the time of day matters when the lock is from today.
  const text = screen.getByRole("status").textContent ?? "";
  expect(text).toMatch(/^In use by Kaushal since /);
});

test("times are padded to two digits and use the 24-hour clock", () => {
  const now = new Date(2026, 9, 24, 18, 0);
  expect(sinceText(local(2026, 10, 24, 9, 5), now)).toBe("09:05");
  expect(sinceText(local(2026, 10, 24, 14, 30), now)).toBe("14:30");
});

test("a lock from an earlier day also names the day", () => {
  const now = new Date(2026, 9, 24, 9, 0);
  expect(sinceText(local(2026, 10, 23, 17, 8), now)).toBe("23 Oct, 17:08");
});

test("the banner text is exactly the agreed copy", () => {
  const takenAt = new Date();
  takenAt.setHours(10, 42, 0, 0);
  render(<ReadOnlyBanner holderName="Kaushal" takenAt={takenAt.toISOString()} />);
  expect(screen.getByRole("status").textContent).toBe("In use by Kaushal since 10:42");
});

test("an action (an admin's release) sits inside the banner", () => {
  render(
    <ReadOnlyBanner
      holderName="Kaushal"
      takenAt={local(2026, 10, 24, 10, 42)}
      action={<button>Release lock</button>}
    />,
  );
  expect(screen.getByRole("button", { name: "Release lock" })).toBeTruthy();
});
