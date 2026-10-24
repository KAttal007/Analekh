import { useEffect, useState } from "react";

// Display preferences (Settings): per-browser conveniences, stored in localStorage when it is
// available, like the theme. Every reader falls back to the defaults, so a private window or
// blocked storage shows the app exactly as before.

export type Units = "auto" | "crore" | "million";
export type BasisPref = "consolidated" | "standalone";
export type DeskSortPref = "filed" | "market_cap";
export type Prefs = {
  units: Units;
  basis: BasisPref;
  deskSort: DeskSortPref;
  /** A soft tone when a model a colleague held is free again (model locks). */
  chime: boolean;
};

export const DEFAULT_PREFS: Prefs = {
  units: "auto",
  basis: "consolidated",
  deskSort: "filed",
  chime: true,
};
const KEY = "analekh.prefs";
const EVENT = "analekh-prefs";

const UNITS: Units[] = ["auto", "crore", "million"];
const BASES: BasisPref[] = ["consolidated", "standalone"];
const SORTS: DeskSortPref[] = ["filed", "market_cap"];

export function readPrefs(): Prefs {
  try {
    const raw = JSON.parse(localStorage.getItem(KEY) ?? "{}") as Partial<Prefs>;
    // Each value is checked on its own: an old or hand-edited entry never breaks a page.
    return {
      units: UNITS.includes(raw.units as Units) ? (raw.units as Units) : DEFAULT_PREFS.units,
      basis: BASES.includes(raw.basis as BasisPref)
        ? (raw.basis as BasisPref)
        : DEFAULT_PREFS.basis,
      deskSort: SORTS.includes(raw.deskSort as DeskSortPref)
        ? (raw.deskSort as DeskSortPref)
        : DEFAULT_PREFS.deskSort,
      chime: typeof raw.chime === "boolean" ? raw.chime : DEFAULT_PREFS.chime,
    };
  } catch {
    return DEFAULT_PREFS;
  }
}

export function setPrefs(change: Partial<Prefs>): void {
  const next = { ...readPrefs(), ...change };
  try {
    localStorage.setItem(KEY, JSON.stringify(next));
  } catch {
    /* storage unavailable: nothing is kept */
  }
  window.dispatchEvent(new Event(EVENT));
}

/** The current preferences; re-renders when they change (in this tab or another). */
export function usePrefs(): Prefs {
  const [prefs, setState] = useState<Prefs>(readPrefs);
  useEffect(() => {
    const update = () => setState(readPrefs());
    const onStorage = (e: StorageEvent) => {
      if (e.key === KEY) update();
    };
    window.addEventListener(EVENT, update);
    window.addEventListener("storage", onStorage);
    return () => {
      window.removeEventListener(EVENT, update);
      window.removeEventListener("storage", onStorage);
    };
  }, []);
  return prefs;
}
