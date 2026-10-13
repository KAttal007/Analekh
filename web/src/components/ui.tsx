import type { ReactNode } from "react";
import { Icon, type IconName } from "./Icon";

export function PageHeader({
  title,
  subtitle,
  badges,
  meta,
  actions,
}: {
  title: ReactNode;
  subtitle?: ReactNode;
  badges?: ReactNode;
  meta?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <div className="page-header">
      <div>
        <div className="page-title">
          <h1>{title}</h1>
          {badges}
        </div>
        {subtitle && <p className="page-subtitle">{subtitle}</p>}
        {meta && <div className="meta">{meta}</div>}
      </div>
      {actions && <div className="actions">{actions}</div>}
    </div>
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

export function Loading() {
  return <p className="loading">Loading…</p>;
}

export function ErrorNote({ error }: { error: unknown }) {
  return (
    <div className="alert alert-error" role="alert">
      <Icon name="alert" />
      <span>{error instanceof Error ? error.message : String(error)}</span>
    </div>
  );
}
