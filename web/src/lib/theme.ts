import { useEffect, useState } from "react";

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
  } catch { /* storage blocked: theme applies for this page only */ }
  applyTheme(choice);
  window.dispatchEvent(new Event(EVENT));
}

const systemDark = () => window.matchMedia?.("(prefers-color-scheme: dark)").matches ?? false;

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
