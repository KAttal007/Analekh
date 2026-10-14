import type { ReactNode } from "react";
import { Icon, type IconName } from "./Icon";

export function PageHeader({
  title,
  subtitle,
  badges,
  meta,
  actions,
  leading,
}: {
  title: ReactNode;
  subtitle?: ReactNode;
  badges?: ReactNode;
  meta?: ReactNode;
  actions?: ReactNode;
  leading?: ReactNode;
}) {
  return (
    <div className="page-header">
      <div className="page-heading">
        {leading}
        <div>
          <div className="page-title">
            <h1>{title}</h1>
            {badges}
          </div>
          {subtitle && <p className="page-subtitle">{subtitle}</p>}
          {meta && <div className="meta">{meta}</div>}
        </div>
      </div>
      {actions && <div className="actions">{actions}</div>}
    </div>
  );
}

// Initials on a colour picked from the ticker, so each company keeps the same colour.
const AVATAR_HUES = [212, 262, 190, 152, 28, 340, 232, 14];

export function Avatar({ symbol, name }: { symbol: string; name: string }) {
  const words = name
    .replace(/\b(limited|ltd\.?|the)\b/gi, "")
    .trim()
    .split(/\s+/);
  const initials = (
    words.length > 1 ? words[0][0] + words[1][0] : symbol.slice(0, 2)
  ).toUpperCase();
  let h = 0;
  for (const ch of symbol) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
  const hue = AVATAR_HUES[h % AVATAR_HUES.length];
  return (
    <span
      className="avatar"
      aria-hidden="true"
      style={{ background: `linear-gradient(135deg, hsl(${hue} 70% 58%), hsl(${hue} 65% 44%))` }}
    >
      {initials}
    </span>
  );
}

export function EmptyState({
  icon = "inbox",
  title,
  children,
  actions,
}: {
  icon?: IconName;
  title: string;
  children?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <div className="empty">
      <div className="empty-icon">
        <Icon name={icon} size={20} />
      </div>
      <div className="empty-title">{title}</div>
      {children && <p>{children}</p>}
      {actions && <div className="actions">{actions}</div>}
    </div>
  );
}

export type Tone = "neutral" | "accent" | "ok" | "warn" | "error";

export function Badge({
  tone = "neutral",
  title,
  children,
}: {
  tone?: Tone;
  title?: string;
  children: ReactNode;
}) {
  return (
    <span className={tone === "neutral" ? "badge" : `badge badge-${tone}`} title={title}>
      {children}
    </span>
  );
}

// Maps the status words the API uses to a badge colour.
const TONES: Record<string, Tone> = {
  active: "ok",
  accepted: "ok",
  applied: "ok",
  approved: "ok",
  edited: "accent",
  validated: "ok",
  ok: "ok",
  pending: "warn",
  draft: "warn",
  testing: "warn",
  blocked: "error",
  failed: "error",
  rejected: "error",
  skipped: "neutral",
};

export function StatusBadge({ status }: { status: string | null | undefined }) {
  if (!status) return <span className="muted">-</span>;
  return <Badge tone={TONES[status] ?? "neutral"}>{status.replaceAll("_", " ")}</Badge>;
}

export function Skeleton({
  width = "100%",
  height = 14,
}: {
  width?: number | string;
  height?: number;
}) {
  return <span className="skeleton" style={{ width, height }} />;
}

/** Placeholder while a screen loads: a heading, a row of figure tiles and a table. */
export function Loading({ rows = 6 }: { rows?: number }) {
  return (
    <div className="skeleton-stack" role="status" aria-label="Loading">
      <Skeleton width="38%" height={22} />
      <Skeleton width="22%" />
      <SkeletonTable rows={rows} />
    </div>
  );
}

export function SkeletonTable({ rows = 6 }: { rows?: number }) {
  return (
    <div className="card card-body skeleton-stack">
      {Array.from({ length: rows }, (_, i) => (
        <Skeleton key={i} width={`${92 - ((i * 13) % 30)}%`} />
      ))}
    </div>
  );
}

export function ErrorNote({ error }: { error: unknown }) {
  return (
    <div className="alert alert-error" role="alert">
      <Icon name="alert" />
      <span>{error instanceof Error ? error.message : String(error)}</span>
    </div>
  );
}

/** An ⓘ beside a label: its note shows on hover, on tap (the button takes focus) and to screen
 *  readers, instead of taking a line of the table. */
export function InfoTip({ text }: { text: string }) {
  return (
    <span className="info-tip">
      <button type="button" className="info-tip-btn" aria-label={text}>
        <Icon name="info" size={13} />
      </button>
      <span role="tooltip" className="info-tip-bubble">
        {text}
      </span>
    </span>
  );
}

/** A dash for a missing figure that says why, the same way as InfoTip (hover, tap, screen
 *  readers). The note opens leftwards: these sit in right-aligned number columns. */
export function MissingTip({ text }: { text?: string | null }) {
  if (!text) return <span className="muted">–</span>;
  return (
    <span className="info-tip info-tip-end">
      <button type="button" className="info-tip-btn missing-tip-btn" aria-label={text}>
        –
      </button>
      <span role="tooltip" className="info-tip-bubble">
        {text}
      </span>
    </span>
  );
}
