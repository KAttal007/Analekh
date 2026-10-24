// The sign-in reminder shows once per sign-in in a tab: this mark (the user's id, never a
// credential) says it has. Sign-out removes it, so the next sign-in is reminded again.
const KEY = "analekh.signin-locks";

/** Whether this user has had the sign-in reminder since signing in (in this tab). */
export function wasShown(userId: string): boolean {
  try {
    return sessionStorage.getItem(KEY) === userId;
  } catch {
    return false; // storage unavailable: remind on each load of the app instead
  }
}

export function markShown(userId: string): void {
  try {
    sessionStorage.setItem(KEY, userId);
  } catch {
    /* storage unavailable: see wasShown */
  }
}

export function forgetSignInLocks(): void {
  try {
    sessionStorage.removeItem(KEY);
  } catch {
    /* storage unavailable: nothing was kept */
  }
}
