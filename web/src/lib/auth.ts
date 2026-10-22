import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, ApiError, type Me } from "../api/client";

export type { Me };

/** The page to return to after sign-in. Only an in-app path is accepted: one that starts with a
 * single `/` (not `//host`, not `/\\host`, not a URL or `javascript:`), and never the sign-in page
 * itself. Anything else goes to the home page. */
export function safeReturnPath(raw: string | null | undefined): string {
  if (!raw || !raw.startsWith("/") || raw.startsWith("//") || raw.startsWith("/\\")) return "/";
  for (const ch of raw) if (ch.charCodeAt(0) < 32) return "/"; // no control characters
  if (raw === "/login" || raw.startsWith("/login?") || raw.startsWith("/login/")) return "/";
  return raw;
}

// The path only (never a credential) is kept for the tab's lifetime, so an expired session lands
// back where the user was after signing in again.
const RETURN_KEY = "analekh.return-path";

export function rememberReturnPath(path: string): void {
  try {
    sessionStorage.setItem(RETURN_KEY, safeReturnPath(path));
  } catch {
    /* storage unavailable: sign-in returns to the home page */
  }
}

export function takeReturnPath(): string {
  try {
    const path = sessionStorage.getItem(RETURN_KEY);
    sessionStorage.removeItem(RETURN_KEY);
    return safeReturnPath(path);
  } catch {
    return "/";
  }
}

export const ME_KEY = ["me"] as const;

/** Who is signed in: the user, or null when nobody is (a 401 is an answer here, not an error). */
export function useMe() {
  return useQuery<Me | null>({
    queryKey: ME_KEY,
    queryFn: async () => {
      try {
        return await api.me();
      } catch (error) {
        if (error instanceof ApiError && error.status === 401) return null;
        throw error;
      }
    },
    staleTime: Infinity, // changes only by signing in or out, or a 401 elsewhere
    retry: false,
  });
}

/** Whether sign-in is on. False only when the API says so (ENV=dev without AUTH_ENABLED): there
 * is nothing to sign out of. While unknown, or if the check fails, sign-out stays available. */
export function useSignInOff(): boolean {
  const status = useQuery({
    queryKey: ["auth-status"],
    queryFn: api.publicAuthStatus,
    staleTime: Infinity,
    retry: false,
  });
  return status.data?.auth_enabled === false;
}

/** Ends the session on the server, then clears everything this page holds from it.
 * `everywhere` also ends every other session of this user and revokes their bridge tokens. */
export function useSignOut() {
  const client = useQueryClient();
  return async (everywhere = false) => {
    try {
      await (everywhere ? api.logoutEverywhere() : api.logout());
    } finally {
      client.clear(); // nothing from this session stays in the page
      client.setQueryData(ME_KEY, null);
    }
  };
}
