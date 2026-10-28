import { useIsMutating, useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { api } from "../api/client";
import { ErrorNote } from "../components/ui";
import { readPrefs } from "../lib/prefs";
import { playChime } from "./chime";
import { meLocksKey, useCompanyNames, useReleaseMine } from "./heldModels";
import { useIdle } from "./useIdle";
import { useLockPollMs } from "./useModelLock";

/** A tab left without input for the configured time (settings: idle_reminder_minutes), while
 *  its user holds a model, asks them to close it so colleagues can work on it. With the
 *  free-model chime it is the only attention the app asks for unprompted, so it appears at once,
 *  chimes once, and stays until answered: Close gives the model back, Keep open waits again.
 *
 *  Never while something of the user's is still running: an update job on one of their models,
 *  or a build or other action started in this tab that has not answered yet. */
export function IdleReminder() {
  const settings = useQuery({
    queryKey: ["upload-limit"],
    queryFn: api.uploadLimit,
    staleTime: Infinity,
  });
  const minutes = settings.data?.idle_reminder_minutes ?? 0;
  const { idle, reset } = useIdle(minutes > 0 ? minutes * 60_000 : 0);
  const pollMs = useLockPollMs();
  const busy = useIsMutating() > 0;
  const [open, setOpen] = useState(false);

  // Asked only while idle or showing, and again every poll: a job ending, or the user closing
  // the model in another tab, changes the answer.
  const watching = idle || open;
  const locks = useQuery({
    queryKey: meLocksKey,
    queryFn: api.meLocks,
    enabled: watching,
    staleTime: 0,
    refetchInterval: watching && pollMs > 0 ? pollMs : false,
    refetchIntervalInBackground: true, // an idle tab is often a hidden one
  });
  const names = useCompanyNames(watching);
  const release = useReleaseMine();
  const held = locks.data ?? [];
  const settled = locks.isSuccess && !locks.isFetching; // a current answer, not a cached one
  const running = busy || held.some((l) => l.job_running);

  if (!open && idle && settled && held.length > 0 && !running && names.ready) setOpen(true);
  if (open && settled && held.length === 0) setOpen(false);

  useEffect(() => {
    if (open) playChime(readPrefs().chime); // once per appearance
  }, [open]);

  if (!open || held.length === 0) return null;
  const keepOpen = () => {
    setOpen(false);
    reset();
  };
  const one = held.length === 1 ? held[0] : null;
  return (
    <div className="lock-reminder" role="region" aria-label="Models still open" aria-live="polite">
      {one ? (
        <p>
          You still have {names.name(one.model_id)}'s model open. {one.job_running ? "Work is still running on it; it closes itself when done." : "Close it if you are done."}
        </p>
      ) : (
        <>
          <p>You still have {held.length} models open. Close any you are done with.</p>
          <ul className="lock-reminder-list">
            {held.map((l) => {
              const name = names.name(l.model_id);
              return (
                <li key={l.model_id}>
                  <span>{name}</span>
                  {l.job_running ? (
                    // A job started while this was up: the job lets go itself, so no Close.
                    <span className="muted">Running</span>
                  ) : (
                    <button type="button" className="btn btn-sm" aria-label={`Close ${name}'s model`} disabled={release.isPending} onClick={() => release.mutate(l.model_id)}>
                      Close
                    </button>
                  )}
                </li>
              );
            })}
          </ul>
        </>
      )}
      {release.isError && <ErrorNote error={release.error} />}
      <div className="lock-reminder-actions">
        {one && !one.job_running && (
          <button type="button" className="btn btn-sm" disabled={release.isPending} onClick={() => release.mutate(one.model_id)}>
            Close
          </button>
        )}
        <button type="button" className="btn btn-primary btn-sm" onClick={keepOpen}>
          Keep open
        </button>
      </div>
    </div>
  );
}
