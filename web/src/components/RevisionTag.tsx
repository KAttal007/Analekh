import type { Revision } from "../api/client";
import { filedAt, longDate, figure, scaleFor, signedBps, signedPct } from "../lib/format";
import { TagTip } from "./ui";

/** What the popup says about a quarter filed more than once. */
export function revisionText(rev: Revision, filed?: string | null): string {
  if (rev.status === "original") {
    return (
      `Superseded: replaced by the revised filing of ${filedAt(rev.superseded_by)}. ` +
      "Kept as history; its numbers are no longer used."
    );
  }
  const what = rev.status === "refiled" ? "Filed again" : "Revised filing";
  const head = `${what}${filed ? ` (${filedAt(filed)})` : ""}, replacing the one filed ${filedAt(rev.replaces)}.`;
  if (rev.replaced_period) {
    const [start, end] = rev.replaced_period;
    return `${head}\nThe earlier filing covered ${longDate(start)} to ${longDate(end)} only; this one adds the quarter's own figures.`;
  }
  if (!rev.changes?.length) return `${head}\nNo headline numbers changed.`;
  // One unit for the whole note: lakhs only when every amount in it is under Rs 10 crore.
  const scale = scaleFor(
    rev.changes.filter((c) => c.kind === "inr").flatMap((c) => [c.old, c.new]),
  );
  const lines = rev.changes.map((c) => {
    const delta =
      c.change == null
        ? ""
        : ` (${c.kind === "pct" ? signedBps(c.change, false) : signedPct(c.change, false)})`;
    return `${c.label}: ${figure(c.old, c.kind, scale)} → ${figure(c.new, c.kind, scale)}${delta}`;
  });
  return `${head}\nChanged:\n${lines.join("\n")}`;
}

/** The badge word for a filing's revision status, or null for an original still in use. */
export function revisionLabel(rev: Revision): string | null {
  if (rev.status === "original") return rev.superseded_by ? "Superseded" : null;
  return rev.status === "refiled" ? "Refiled" : rev.changes?.length ? "Restated" : "Revised";
}

/** "Revised" / "Superseded" badge with the details in a popup. */
export function RevisionTag({ rev, filed }: { rev: Revision; filed?: string | null }) {
  const label = revisionLabel(rev);
  if (!label) return null;
  return (
    <TagTip
      label={label}
      tone={rev.status === "original" ? undefined : "warn"}
      text={revisionText(rev, filed)}
    />
  );
}
