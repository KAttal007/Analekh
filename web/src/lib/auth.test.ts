import { describe, expect, it } from "vitest";
import { safeReturnPath } from "./auth";

describe("safeReturnPath", () => {
  it("keeps an in-app path", () => {
    expect(safeReturnPath("/companies/TCS")).toBe("/companies/TCS");
    expect(safeReturnPath("/models?x=1")).toBe("/models?x=1");
  });

  it.each(["//evil.com", "https://evil.com", "javascript:alert(1)", "", null, "relative/path"])(
    "sends %j back to the home page",
    (raw) => {
      expect(safeReturnPath(raw)).toBe("/");
    },
  );
});
