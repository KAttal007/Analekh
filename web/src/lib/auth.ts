import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { api, ApiError, type Me } from "../api/client";
import { clearFreed } from "../lock/freed";
import { forgetSignInLocks } from "../lock/signInMark";
import { resetWelcomed } from "./welcome";

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

const RETURN_KEY = "analekh.return-path";

export function rememberReturnPath(path: string): void {
  try {
    sessionStorage.setItem(RETURN_KEY, safeReturnPath(path));
  } catch { /* storage blocked: sign-in still works */ }
}

export function peekReturnPath(): string {
  try {
    return safeReturnPath(sessionStorage.getItem(RETURN_KEY));
  } catch {
    return "/";
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
  const navigate = useNavigate();
  return async (everywhere = false) => {
    try {
      await (everywhere ? api.logoutEverywhere() : api.logout());
    } catch (error) {
      if (!(error instanceof ApiError && error.status === 401)) throw error;
    }
    resetWelcomed();
    clearFreed();
    forgetSignInLocks();
    client.setQueryData(ME_KEY, null);
    client.removeQueries({ predicate: (q) => q.queryKey[0] !== ME_KEY[0] });
    navigate("/welcome", { replace: true });
  };
}
