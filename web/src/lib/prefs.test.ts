import { afterEach, expect, test, vi } from "vitest";
import { crore, IN_CRORE, IN_LAKH, IN_MILLION, scaleFor } from "./format";
import { DEFAULT_PREFS, readPrefs, setPrefs } from "./prefs";

afterEach(() => {
  localStorage.clear();
  vi.restoreAllMocks();
});

test("defaults until something is chosen, and each value is checked on its own", () => {
  expect(readPrefs()).toEqual(DEFAULT_PREFS);
  localStorage.setItem("analekh.prefs", JSON.stringify({ units: "furlongs", basis: "standalone" }));
  expect(readPrefs()).toEqual({ ...DEFAULT_PREFS, basis: "standalone" });
  expect(DEFAULT_PREFS.chime).toBe(true); // the free-model chime is on until turned off
  localStorage.setItem("analekh.prefs", JSON.stringify({ chime: "loud" }));
  expect(readPrefs().chime).toBe(true);
  localStorage.setItem("analekh.prefs", "not json");
  expect(readPrefs()).toEqual(DEFAULT_PREFS);
});

test("a choice is kept and announced", () => {
  const heard = vi.fn();
  window.addEventListener("analekh-prefs", heard);
  setPrefs({ units: "million" });
  setPrefs({ deskSort: "market_cap" });
  expect(readPrefs()).toEqual({
    units: "million",
    basis: "consolidated",
    deskSort: "market_cap",
    chime: true,
  });
  setPrefs({ chime: false });
  expect(readPrefs().chime).toBe(false);
  expect(heard).toHaveBeenCalledTimes(3);
  window.removeEventListener("analekh-prefs", heard);
});

test("blocked storage falls back to the defaults instead of breaking the page", () => {
  vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
    throw new Error("SecurityError");
  });
  vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
    throw new Error("SecurityError");
  });
  expect(() => setPrefs({ units: "crore" })).not.toThrow();
  expect(readPrefs()).toEqual(DEFAULT_PREFS);
});

test("amounts follow the Amounts preference", () => {
  expect(scaleFor(["460000"])).toBe(IN_LAKH); // auto: a small company in lakh
  expect(scaleFor(["460000"], "crore")).toBe(IN_CRORE);
  expect(scaleFor(["10556573000"], "million")).toBe(IN_MILLION);
  expect(scaleFor(["abc", null])).toBe(IN_CRORE); // nothing usable: crore, never NaN lakh
  setPrefs({ units: "million" });
  expect(crore("16391169600000.00")).toBe("₹16,391,170 mn"); // grouped in thousands
  expect(crore("-3000000", "crore")).toBe("−₹0.3 cr");
});
