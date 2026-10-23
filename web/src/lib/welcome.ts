// The welcome screen is the landing page: every time Analekh is opened at its home address (a new
// tab, a reload, typing the address), signed in or not. Moving around inside the app does not bring
// it back, so this is remembered for the page's lifetime only.

let welcomed = false;

export function hasWelcomed(): boolean {
  return welcomed;
}

export function markWelcomed(): void {
  welcomed = true;
}

/** Tests only: a fresh page load. */
export function resetWelcomed(): void {
  welcomed = false;
}

/** Good morning / afternoon / evening, by the visitor's own clock. */
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
