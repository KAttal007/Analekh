import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { api } from "../api/client";
import { ErrorNote } from "../components/ui";
import { useMe } from "../lib/auth";
import { meLocksKey, useCompanyNames, useReleaseMine } from "./heldModels";
import { markShown, wasShown } from "./signInMark";

export { forgetSignInLocks } from "./signInMark";

/** Once after sign-in: the models this user still holds from before, each with a Close (or
 *  "Running", with no Close, while a job of theirs holds it). Not on every page change, and not
 *  after a reload in the same tab; sign-out arms it again. */
export function SignInLocks() {
  const me = useMe().data;
  if (!me) return null;
  return <ForUser key={me.id} userId={me.id} />;
}

function ForUser({ userId }: { userId: string }) {
  const [due] = useState(() => !wasShown(userId)); // read once, when the shell first appears
  const [dismissed, setDismissed] = useState(false);
  const locks = useQuery({ queryKey: meLocksKey, queryFn: api.meLocks, enabled: due });
  const names = useCompanyNames(due);
  const release = useReleaseMine();
  useEffect(() => {
    if (due && locks.isSuccess) markShown(userId); // answered: this sign-in has had its reminder
  }, [due, locks.isSuccess, userId]);

  const held = locks.data ?? [];
  if (!due || dismissed || held.length === 0 || !names.ready) return null;
  const closable = held.filter((l) => !l.job_running).length;
  return (
    <div className="lock-reminder" role="region" aria-label="Models still open" aria-live="polite">
      <p>
        {held.length === 1
          ? "You still have 1 model open."
          : `You still have ${held.length} models open.`}{" "}
        {closable === 0
          ? held.length === 1
            ? "Work is still running on it; it closes itself when done."
            : "Work is still running on them; they close themselves when done."
          : held.length === 1
            ? "Close it if you are done."
            : "Close any you are done with."}
      </p>
      <ul className="lock-reminder-list">
        {held.map((l) => {
          const name = names.name(l.model_id);
          return (
            <li key={l.model_id}>
              <span>{name}</span>
              {l.job_running ? (
                // A running job's lock is not the user's to give back: the job lets go itself.
                <span className="muted">Running</span>
              ) : (
                <button
                  type="button"
                  className="btn btn-sm"
                  aria-label={`Close ${name}'s model`}
                  disabled={release.isPending}
                  onClick={() => release.mutate(l.model_id)}
                >
                  Close
                </button>
              )}
            </li>
          );
        })}
      </ul>
      {release.isError && <ErrorNote error={release.error} />}
      <div className="lock-reminder-actions">
        <button type="button" className="btn btn-primary btn-sm" onClick={() => setDismissed(true)}>
          Keep open
        </button>
      </div>
    </div>
  );
}
