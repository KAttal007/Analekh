let welcomed = false;

export function hasWelcomed(): boolean {
  return welcomed;
}

export function markWelcomed(): void {
  welcomed = true;
}

export function resetWelcomed(): void {
  welcomed = false;
}

export function greeting(now = new Date()): string {
  const h = now.getHours();
  return h < 12 ? "Good morning" : h < 17 ? "Good afternoon" : "Good evening";
}

/** Names the next route change for the transition styles (styles.css): "reveal" brings the sign-in
 * screen up from the welcome page; "welcome" unlocks into the desk; "enter" is the short unlock
 * from sign-in into the desk. Cleared once it has played. */
export function tagTransition(kind: "reveal" | "welcome" | "enter"): void {
  document.documentElement.dataset.vt = kind;
  window.setTimeout(() => delete document.documentElement.dataset.vt, 1400);
}
