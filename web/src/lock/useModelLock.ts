import { type QueryKey, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useRef } from "react";
import { api, ApiError, type LockOut } from "../api/client";
import { announceFreed } from "./freed";

export type { LockOut };

/** What a 423 from a start action (update, build, report) says about the colleague in the way. */
export type LockedDetail = {
  code: "model_locked";
  holder_name: string;
  taken_at: string;
  activity: string;
};

export const lockKey = (modelId: number) => ["model-lock", modelId] as const;

/** The holder named by a 423 "model_locked" reply, or null for any other error. */
export function lockedDetail(error: unknown): LockedDetail | null {
  if (!(error instanceof ApiError) || error.status !== 423) return null;
  try {
    const detail = JSON.parse(error.message) as Partial<LockedDetail>;
    return detail?.code === "model_locked" ? (detail as LockedDetail) : null;
  } catch {
    return null;
  }
}

/** How often to ask, from the server's settings (lock_poll_seconds); 0 until they are known. */
export function useLockPollMs(): number {
  const settings = useQuery({
    queryKey: ["upload-limit"],
    queryFn: api.uploadLimit,
    staleTime: Infinity,
  });
  const seconds = settings.data?.lock_poll_seconds;
  return seconds && seconds > 0 ? seconds * 1000 : 0;
}

/** Who holds a model's lock, asked again every `pollMs` (0: once). A hidden tab stops asking
 *  unless a colleague holds the model: someone waiting for it in another tab must still hear it
 *  is free. Coming back asks at once. Earlier answers stay on screen while a new one is fetched,
 *  so nothing flickers between checks.
 *
 *  With `freedTo`, a viewer who saw a colleague hold the model on this page is told when it is
 *  free (a toast that opens `freedTo`, and the chime). Nobody else is: not a viewer who only saw
 *  it free, not one whose own lock ended, and not when it passes from one colleague to another.
 *
 *  With `refreshOnFree`, the page's own queries are reloaded when a colleague's lock ends, and
 *  the page stays read-only (`held`) until they have: the colleague's work changed the model, so
 *  buttons must not come back on rows read before it. */
export function useModelLock(modelId: number, pollMs: number, opts: { freedTo?: string; refreshOnFree?: readonly QueryKey[] } = {}) {
  const qc = useQueryClient();
  // Waiting on a colleague: the answer last seen (this render) names someone else.
  const seen = qc.getQueryData<LockOut | null>(lockKey(modelId));
  const waiting = seen != null && !seen.mine;
  const { freedTo, refreshOnFree } = opts;
  const query = useQuery({
    queryKey: lockKey(modelId),
    queryFn: async () => {
      const before = qc.getQueryData<LockOut | null>(lockKey(modelId));
      const now = await api.modelLock(modelId);
      if (before && !before.mine && now === null && refreshOnFree?.length) {
        // The colleague let go: reload the page's data first, so "free" (and the buttons) only
        // arrive with rows that include their work.
        await Promise.allSettled(refreshOnFree.map((queryKey) => qc.invalidateQueries({ queryKey })));
      }
      return now;
    },
    enabled: Number.isFinite(modelId),
    staleTime: 0, // the app keeps data for minutes; a lock must be current
    refetchInterval: pollMs > 0 ? pollMs : false,
    refetchIntervalInBackground: waiting,
    refetchOnWindowFocus: true,
  });
  const lock = query.data ?? null;
  const sawHeld = useRef(false); // a colleague held it while this page was open
  const quiet = useRef(false); // this viewer (an admin) is releasing it: no news for them
  useEffect(() => {
    if (!query.isSuccess) return;
    if (lock && !lock.mine) {
      sawHeld.current = true;
    } else if (lock) {
      sawHeld.current = false; // now mine: its end is not news
    } else {
      if (sawHeld.current && !quiet.current && freedTo !== undefined) {
        announceFreed({ modelId, to: freedTo });
      }
      sawHeld.current = false;
      quiet.current = false;
    }
  }, [query.isSuccess, lock, modelId, freedTo]);
  const refresh = useCallback(() => {
    void qc.invalidateQueries({ queryKey: lockKey(modelId) });
  }, [qc, modelId]);
  /** A start action answered 423: show the holder at once, then ask the server. */
  const heldBy = useCallback(
    (detail: LockedDetail) => {
      const held: LockOut = {
        model_id: modelId,
        holder_id: "",
        holder_name: detail.holder_name,
        activity: detail.activity,
        taken_at: detail.taken_at,
        mine: false,
        job_running: false,
      };
      qc.setQueryData<LockOut | null>(lockKey(modelId), () => held);
      refresh();
    },
    [qc, modelId, refresh],
  );
  /** An admin's Release lock: on (before the call) or off again (it failed). */
  const releasing = useCallback((on: boolean) => {
    quiet.current = on;
  }, []);
  return {
    lock,
    mine: lock?.mine ?? false,
    /** Someone else holds it: this screen is read-only. */
    held: lock !== null && !lock.mine,
    loaded: query.isSuccess,
    refresh,
    heldBy,
    releasing,
  };
}
