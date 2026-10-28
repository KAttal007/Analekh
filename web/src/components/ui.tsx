import { type KeyboardEvent, type ReactNode, useEffect, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
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

const AVATAR_HUES = [212, 262, 190, 152, 28, 340, 232, 14];

export function Avatar({ symbol, name }: { symbol: string; name: string }) {
  const words = name
    .replace(/\b(limited|ltd\.?|the)\b/gi, "")
    .trim()
    .split(/\s+/);
  const initials = (words.length > 1 ? words[0][0] + words[1][0] : symbol.slice(0, 2)).toUpperCase();
  let h = 0;
  for (const ch of symbol) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
  const hue = AVATAR_HUES[h % AVATAR_HUES.length];
  return (
    <span className="avatar" aria-hidden="true" style={{ background: `linear-gradient(135deg, hsl(${hue} 70% 58%), hsl(${hue} 65% 44%))` }}>
      {initials}
    </span>
  );
}

export function EmptyState({ icon = "inbox", title, children, actions }: { icon?: IconName; title: string; children?: ReactNode; actions?: ReactNode }) {
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

export function Badge({ tone = "neutral", title, children }: { tone?: Tone; title?: string; children: ReactNode }) {
  return (
    <span className={tone === "neutral" ? "badge" : `badge badge-${tone}`} title={title}>
      {children}
    </span>
  );
}

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

export function Skeleton({ width = "100%", height = 14 }: { width?: number | string; height?: number }) {
  return <span className="skeleton" style={{ width, height }} />;
}

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

/** A badge that explains itself on hover, tap or focus. The note is placed against the window
 *  (below the badge, or above it near the bottom), so a table's scroll box or the edge of the
 *  screen never cuts it off; it closes on scroll rather than drifting away from its badge. */
export function TagTip({ label, tone, text }: { label: string; tone?: Tone; text: string }) {
  const button = useRef<HTMLButtonElement>(null);
  const [at, setAt] = useState<{ left: number; top: number; above: boolean } | null>(null);
  const show = () => {
    const r = button.current?.getBoundingClientRect();
    if (!r) return;
    const width = Math.min(300, window.innerWidth - 16);
    const above = window.innerHeight - r.bottom < 180 && r.top > 180;
    setAt({
      left: Math.max(8, Math.min(r.left, window.innerWidth - width - 8)),
      top: above ? r.top - 6 : r.bottom + 6,
      above,
    });
  };
  const hide = () => setAt(null);
  useEffect(() => {
    if (!at) return;
    window.addEventListener("scroll", hide, true);
    window.addEventListener("resize", hide);
    return () => {
      window.removeEventListener("scroll", hide, true);
      window.removeEventListener("resize", hide);
    };
  }, [at]);
  return (
    <span className="tag-tip" onMouseEnter={show} onMouseLeave={hide}>
      <button ref={button} type="button" className="info-tip-btn tag-tip-btn" aria-label={`${label}: ${text}`} onFocus={show} onBlur={hide} onKeyDown={(e) => e.key === "Escape" && hide()}>
        <Badge tone={tone}>{label}</Badge>
      </button>
      {/* In <body>: containers used for container queries would otherwise position it. */}
      {at &&
        createPortal(
          <span
            role="tooltip"
            className="tag-tip-bubble"
            style={{
              left: at.left,
              top: at.top,
              transform: at.above ? "translateY(-100%)" : undefined,
            }}
          >
            {text}
          </span>,
          document.body,
        )}
    </span>
  );
}

/** A button that opens a small panel on click, tap or Enter; the panel can hold links. Esc, a
 *  click elsewhere, scrolling or resizing closes it, and Esc puts focus back on the button. The
 *  panel is placed against the window like TagTip's note, so a scroll box never cuts it off;
 *  focus moves into it on open and Tab out of it closes it, so keyboard order still works. */
export function Popover({ label, children, className }: { label: string; children: ReactNode; className?: string }) {
  const button = useRef<HTMLButtonElement>(null);
  const panel = useRef<HTMLDivElement>(null);
  const [at, setAt] = useState<{ left: number; top: number; above: boolean } | null>(null);
  const close = (refocus: boolean) => {
    setAt(null);
    if (refocus) button.current?.focus();
  };
  const open = () => {
    const r = button.current?.getBoundingClientRect();
    if (!r) return;
    const width = Math.min(320, window.innerWidth - 16);
    const above = window.innerHeight - r.bottom < 240 && r.top > 240;
    setAt({
      left: Math.max(8, Math.min(r.right - width, window.innerWidth - width - 8)),
      top: above ? r.top - 6 : r.bottom + 6,
      above,
    });
  };
  useEffect(() => {
    if (!at) return;
    panel.current?.querySelector<HTMLElement>("a, button")?.focus();
    const away = (e: PointerEvent) => {
      const t = e.target as Node;
      if (!panel.current?.contains(t) && !button.current?.contains(t)) close(false);
    };
    const scrolled = (e: Event) => {
      if (!panel.current?.contains(e.target as Node)) close(false);
    };
    const resized = () => close(false);
    document.addEventListener("pointerdown", away);
    window.addEventListener("scroll", scrolled, true);
    window.addEventListener("resize", resized);
    return () => {
      document.removeEventListener("pointerdown", away);
      window.removeEventListener("scroll", scrolled, true);
      window.removeEventListener("resize", resized);
    };
  }, [at]);
  const onKey = (e: KeyboardEvent) => {
    if (e.key === "Escape") {
      e.stopPropagation();
      close(true);
    } else if (e.key === "Tab") {
      const items = panel.current?.querySelectorAll<HTMLElement>("a, button") ?? [];
      const last = items[items.length - 1];
      const first = items[0];
      if ((!e.shiftKey && document.activeElement === last) || (e.shiftKey && document.activeElement === first)) {
        close(true);
        if (e.shiftKey) e.preventDefault();
      }
    }
  };
  return (
    <>
      <button
        ref={button}
        type="button"
        className={`popover-btn${className ? ` ${className}` : ""}`}
        aria-label={label}
        aria-expanded={at !== null}
        aria-haspopup="dialog"
        onClick={() => (at ? close(false) : open())}
      >
        <Icon name="info" size={13} />
      </button>
      {at &&
        createPortal(
          <div
            ref={panel}
            role="dialog"
            aria-label={label}
            className="popover-panel"
            onKeyDown={onKey}
            style={{
              left: at.left,
              top: at.top,
              transform: at.above ? "translateY(-100%)" : undefined,
            }}
          >
            {children}
          </div>,
          document.body,
        )}
    </>
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

/** Put inside a `.segmented` group (or any row of buttons, with `selected` naming the chosen one):
 * one thumb behind the selected button that slides to the next choice with a little spring. It
 * follows the group's size without animating. */
export function SegmentThumb({ selected = '[aria-selected="true"]' }: { selected?: string }) {
  const ref = useRef<HTMLSpanElement>(null);
  useLayoutEffect(() => {
    const thumb = ref.current;
    const group = thumb?.parentElement;
    if (!thumb || !group) return;
    let placed = false;
    const place = (glide: boolean) => {
      const on = group.querySelector<HTMLElement>(selected);
      if (!on) {
        thumb.style.opacity = "0";
        return;
      }
      thumb.classList.toggle("no-glide", !glide || !placed);
      thumb.style.opacity = "1";
      thumb.style.width = `${on.offsetWidth}px`;
      thumb.style.height = `${on.offsetHeight}px`;
      thumb.style.transform = `translate(${on.offsetLeft}px, ${on.offsetTop}px)`;
      thumb.style.borderRadius = getComputedStyle(on).borderRadius;
      placed = true;
    };
    place(false);
    group.classList.add("has-thumb");
    const changed = new MutationObserver(() => place(true));
    changed.observe(group, {
      subtree: true,
      attributes: true,
      attributeFilter: ["aria-selected", "aria-pressed"],
    });
    const resized = new ResizeObserver(() => place(false));
    resized.observe(group);
    return () => {
      changed.disconnect();
      resized.disconnect();
      group.classList.remove("has-thumb");
    };
  }, [selected]);
  return <span className="segment-thumb" ref={ref} aria-hidden />;
}

/** A row of mutually exclusive choices with the sliding thumb. One place for the markup that six
 * screens had written out by hand (role="tablist" + SegmentThumb + one tab per option); it emits
 * exactly that markup, so the `.segmented` CSS and the thumb's observer see no difference.
 * `value` is the selected option's value, or undefined when none is selected. */
export function Segmented<T extends string>({
  label,
  options,
  value,
  onChange,
}: {
  label: string;
  options: readonly { value: T; label: ReactNode; title?: string }[];
  value: T | undefined;
  onChange: (value: T) => void;
}) {
  return (
    <div className="segmented" role="tablist" aria-label={label}>
      <SegmentThumb />
      {options.map((o) => (
        <button key={o.value} type="button" role="tab" title={o.title} aria-selected={value === o.value} onClick={() => onChange(o.value)}>
          {o.label}
        </button>
      ))}
    </div>
  );
}
