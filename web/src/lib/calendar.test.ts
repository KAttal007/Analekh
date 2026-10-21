import { describe, expect, it } from "vitest";
import { addDays, addMonths, isWeekend, monthGrid, startOfWeek } from "./calendar";

describe("calendar dates", () => {
  it("adds days across month and year ends", () => {
    expect(addDays("2026-10-31", 1)).toBe("2026-11-01");
    expect(addDays("2026-01-01", -1)).toBe("2025-12-31");
  });
  it("adds months without overflowing short months", () => {
    expect(addMonths("2026-01-31", 1)).toBe("2026-02-01");
    expect(addMonths("2026-12-15", 1)).toBe("2027-01-01");
  });
  it("starts weeks on Monday", () => {
    expect(startOfWeek("2026-10-21")).toBe("2026-10-19"); // a Wednesday
    expect(startOfWeek("2026-10-25")).toBe("2026-10-19"); // the Sunday before the next Monday
    expect(startOfWeek("2026-10-19")).toBe("2026-10-19");
  });
  it("knows weekends", () => {
    expect(isWeekend("2026-10-24")).toBe(true);
    expect(isWeekend("2026-10-23")).toBe(false);
  });
  it("lays a month out in whole weeks", () => {
    const g = monthGrid("2026-10-21");
    expect(g.start).toBe("2026-09-28");
    expect(g.end).toBe("2026-11-01");
    expect(g.days.length % 7).toBe(0);
    expect(g.days[0]).toBe(g.start);
    expect(g.days.at(-1)).toBe(g.end);
  });
});
