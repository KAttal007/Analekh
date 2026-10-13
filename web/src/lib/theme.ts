import { useEffect, useState } from "react";

// Light / dark / system theme. The choice is a per-browser convenience: stored in localStorage
// when available, applied as <html data-theme>; "system" removes the attribute so the
// prefers-color-scheme rules in styles.css apply. index.html applies it before first paint.

export type ThemeChoice = "light" | "dark" | "system";
const KEY = "analekh.theme";
const EVENT = "analekh-theme";

export function readTheme(): ThemeChoice {
  try {
    const v = localStorage.getItem(KEY);
    return v === "light" || v === "dark" ? v : "system";
  } catch {
    return "system";
  }
}

export function applyTheme(choice: ThemeChoice): void {
  const root = document.documentElement;
  if (choice === "system") root.removeAttribute("data-theme");
  else root.setAttribute("data-theme", choice);
}

export function setTheme(choice: ThemeChoice): void {
  try {
    if (choice === "system") localStorage.removeItem(KEY);
    else localStorage.setItem(KEY, choice);
  } catch {
    /* storage unavailable: the choice lasts for this page only */
  }
  applyTheme(choice);
  window.dispatchEvent(new Event(EVENT));
}

const systemDark = () => window.matchMedia?.("(prefers-color-scheme: dark)").matches ?? false;

/** The user's choice and the theme actually showing; re-renders when either changes. */
export function useTheme(): { choice: ThemeChoice; resolved: "light" | "dark" } {
  const [choice, setChoice] = useState<ThemeChoice>(readTheme);
  const [dark, setDark] = useState(systemDark);
  useEffect(() => {
    const onChoice = () => setChoice(readTheme());
    const mq = window.matchMedia?.("(prefers-color-scheme: dark)");
    const onSystem = () => setDark(systemDark());
    window.addEventListener(EVENT, onChoice);
    mq?.addEventListener("change", onSystem);
    return () => {
      window.removeEventListener(EVENT, onChoice);
      mq?.removeEventListener("change", onSystem);
    };
  }, []);
  return { choice, resolved: choice === "system" ? (dark ? "dark" : "light") : choice };
}
