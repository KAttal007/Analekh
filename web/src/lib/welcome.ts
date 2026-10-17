// The welcome screen greets a visitor once per browser session: opening Analekh shows it, moving
// around inside the app does not. Session storage can be unavailable (private windows, blocked
// site data): the visitor then sees the welcome once per page load, never an error.

const KEY = "analekh.welcomed";

export function hasWelcomed(): boolean {
  try {
    return sessionStorage.getItem(KEY) === "1";
  } catch {
    return true; // storage blocked: don't stand between the visitor and the app
  }
}

export function markWelcomed(): void {
  try {
    sessionStorage.setItem(KEY, "1");
  } catch {
    /* storage unavailable: nothing to remember */
  }
}

/** Good morning / afternoon / evening, by the visitor's own clock. */
export function greeting(now = new Date()): string {
  const h = now.getHours();
  return h < 12 ? "Good morning" : h < 17 ? "Good afternoon" : "Good evening";
}
