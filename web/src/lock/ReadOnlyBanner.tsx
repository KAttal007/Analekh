import type { ReactNode } from "react";
import { Icon } from "../components/Icon";

const two = (n: number) => String(n).padStart(2, "0");

/** When a lock was taken, on the viewer's clock: "10:42" today, "23 Oct, 17:08" before that. */
export function sinceText(iso: string, now = new Date()): string {
  const d = new Date(iso);
  const time = `${two(d.getHours())}:${two(d.getMinutes())}`;
  if (d.toDateString() === now.toDateString()) return time;
  const day = d.toLocaleDateString("en-GB", { day: "numeric", month: "short" });
  return `${day}, ${time}`;
}

/** A colleague is working on this model: the screen is read-only until they finish. Static (no
 *  entrance motion), so the regular lock checks never make it flicker. */
export function ReadOnlyBanner({
  holderName,
  takenAt,
  action,
}: {
  holderName: string;
  takenAt: string;
  /** An admin's Release lock button, beside the text. */
  action?: ReactNode;
}) {
  return (
    <div className="alert alert-warn lock-banner">
      <Icon name="clock" />
      <span role="status">
        In use by {holderName} since {sinceText(takenAt)}
      </span>
      {action && <span className="lock-banner-action">{action}</span>}
    </div>
  );
}
