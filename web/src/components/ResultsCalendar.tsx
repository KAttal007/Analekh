import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api, type CalendarEvent, type CalendarKind } from "../api/client";
import {
  addDays,
  addMonths,
  dayLong,
  dayNumber,
  daysFrom,
  isWeekend,
  iso,
  monthGrid,
  monthLong,
  monthShort,
  rangeLabel,
  startOfWeek,
  weekdayShort,
} from "../lib/calendar";
import { Icon } from "./Icon";
import { Avatar, Badge, EmptyState, ErrorNote, Segmented, SegmentThumb, Skeleton } from "./ui";

// One calendar for the Results desk and the Watchlist: the same component, a different scope.
// `watchlistOnly` is the whole difference: on the desk it follows the "Watchlist only" switch,
// on the Watchlist it is always on.

type View = "day" | "week" | "month";
type KindFilter = "all" | CalendarKind;

const VIEWS = [
  { value: "day", label: "Day" },
  { value: "week", label: "Week" },
  { value: "month", label: "Month" },
] as const;

const KIND_LABEL: Record<CalendarKind, string> = {
  results: "Results",
  meeting: "Board meeting",
  concall: "Concall",
};
const KIND_TONE = { results: "accent", meeting: "neutral", concall: "ok" } as const;

const STRIP_BEFORE = 7; // days of history the day strip keeps
const STRIP_DAYS = 68; // and how many in all: a week back, the season ahead

const reducedMotion = () =>
  typeof window !== "undefined" &&
  !!window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

export function ResultsCalendar({
  watchlistOnly = false,
  title = "Results calendar",
}: {
  watchlistOnly?: boolean;
  title?: string;
}) {
  const today = iso(new Date());
  const [view, setView] = useState<View>("day");
  const [selected, setSelected] = useState(today);
  const [kind, setKind] = useState<KindFilter>("all");

  const strip = useMemo(() => daysFrom(addDays(today, -STRIP_BEFORE), STRIP_DAYS), [today]);
  const range = useMemo(() => {
    if (view === "week") {
      const start = startOfWeek(selected);
      return { start, end: addDays(start, 6) };
    }
    if (view === "month") {
      const g = monthGrid(selected);
      return { start: g.start, end: g.end };
    }
    return { start: strip[0], end: strip[strip.length - 1] };
  }, [view, selected, strip]);

  const query = useQuery({
    queryKey: ["calendar", range.start, range.end, watchlistOnly],
    queryFn: () => api.calendar(range.start, range.end, watchlistOnly),
    placeholderData: keepPreviousData, // the old days stay up while the next range loads
    staleTime: 60_000,
  });
  const data = query.data;

  const counts = useMemo(() => {
    const c: Record<CalendarKind, number> = { results: 0, meeting: 0, concall: 0 };
    for (const e of data?.events ?? []) c[e.kind] += 1;
    return c;
  }, [data]);

  const byDay = useMemo(() => {
    const map = new Map<string, CalendarEvent[]>();
    for (const e of data?.events ?? []) {
      if (kind !== "all" && e.kind !== kind) continue;
      const list = map.get(e.date);
      if (list) list.push(e);
      else map.set(e.date, [e]);
    }
    return map;
  }, [data, kind]);

  const pick = (day: string) => setSelected(day);
  const inStrip = (day: string) => day >= strip[0] && day <= strip[strip.length - 1];
  const changeView = (next: View) => {
    setView(next);
    // The strip only reaches so far back and ahead; a day outside it falls back to today.
    if (next === "day" && !inStrip(selected)) setSelected(today);
  };
  const step = (dir: 1 | -1) => {
    if (view === "month") {
      const first = addMonths(selected, dir);
      setSelected(first.slice(0, 7) === today.slice(0, 7) ? today : first);
    } else {
      const next = addDays(selected, 7 * dir);
      setSelected(view === "day" && !inStrip(next) ? selected : next);
    }
  };
  const label = view === "week" ? rangeLabel(range.start, range.end) : monthLong(selected);

  const events = byDay.get(selected) ?? [];

  return (
    <section className="card cal" aria-label={title}>
      <div className="card-header cal-header">
        <h2 className="cal-title">
          <Icon name="calendar" size={16} />
          {title}
        </h2>
        <div className="cal-nav">
          <button
            type="button"
            className="icon-btn"
            aria-label={view === "month" ? "Previous month" : "Previous week"}
            onClick={() => step(-1)}
          >
            <Icon name="chevronLeft" />
          </button>
          <span className="cal-label" aria-live="polite">
            {label}
          </span>
          <button
            type="button"
            className="icon-btn"
            aria-label={view === "month" ? "Next month" : "Next week"}
            onClick={() => step(1)}
          >
            <Icon name="chevronRight" />
          </button>
          <button
            type="button"
            className="btn-sm"
            onClick={() => setSelected(today)}
            disabled={selected === today}
          >
            Today
          </button>
        </div>
        <Segmented
          label="Calendar view"
          options={VIEWS}
          value={view}
          onChange={(v) => changeView(v)}
        />
      </div>

      <div className="cal-kinds" role="group" aria-label="Show">
        <KindChip
          active={kind === "all"}
          onClick={() => setKind("all")}
          label="All"
          count={counts.results + counts.meeting + counts.concall}
        />
        <KindChip
          active={kind === "results"}
          onClick={() => setKind("results")}
          label="Results"
          count={counts.results}
        />
        <KindChip
          active={kind === "meeting"}
          onClick={() => setKind("meeting")}
          label="Board meetings"
          count={counts.meeting}
        />
        <KindChip
          active={kind === "concall"}
          onClick={() => setKind("concall")}
          label="Concalls"
          count={counts.concall}
          disabled={counts.concall === 0}
          title="Earnings-call dates are not collected yet"
        />
      </div>

      {query.isError ? (
        <div className="card-body">
          <ErrorNote error={query.error} />
        </div>
      ) : !data ? (
        <div className="card-body">
          <Skeleton height={64} />
        </div>
      ) : (
        <>
          {view === "day" && (
            <DayStrip days={strip} today={today} selected={selected} byDay={byDay} onPick={pick} />
          )}
          {view === "week" && (
            <WeekView
              days={daysFrom(range.start, 7)}
              today={today}
              selected={selected}
              byDay={byDay}
              onPick={pick}
            />
          )}
          {view === "month" && (
            <MonthView
              days={monthGrid(selected).days}
              month={selected.slice(0, 7)}
              today={today}
              selected={selected}
              byDay={byDay}
              onPick={pick}
            />
          )}

          <div className="cal-day-head">
            <h3>{dayLong(selected)}</h3>
            <span className="muted">
              {events.length
                ? `${events.length} ${events.length === 1 ? "company" : "companies"}${
                    watchlistOnly
                      ? ""
                      : `, ${events.filter((e) => e.watched).length} on your watchlist`
                  }`
                : "Nothing scheduled"}
            </span>
          </div>
          {/* Keyed by day: choosing another day crossfades the list (a click's answer). */}
          <div className="cal-list-wrap" key={selected}>
            {events.length ? (
              <ul className="cal-list">
                {events.map((e) => (
                  <EventRow key={`${e.symbol}-${e.kind}`} e={e} />
                ))}
              </ul>
            ) : (
              <EmptyState icon="calendar" title="No results scheduled for this day">
                {watchlistOnly
                  ? "None of your watchlist companies has announced a board meeting on this day."
                  : "No company has announced a board meeting for this day yet. Intimations arrive at least two working days ahead."}
              </EmptyState>
            )}
          </div>

          {watchlistOnly && data.unscheduled.length > 0 && (
            <div className="cal-unscheduled">
              <h3>Not yet announced</h3>
              <ul>
                {data.unscheduled.map((u) => (
                  <li key={u.symbol}>
                    <Link to={`/companies/${u.symbol}`} title={u.name}>
                      {u.symbol}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </>
      )}
    </section>
  );
}

function KindChip({
  active,
  onClick,
  label,
  count,
  disabled,
  title,
}: {
  active: boolean;
  onClick: () => void;
  label: string;
  count: number;
  disabled?: boolean;
  title?: string;
}) {
  return (
    <button
      type="button"
      className={active ? "cal-chip on" : "cal-chip"}
      aria-pressed={active}
      onClick={onClick}
      disabled={disabled}
      title={disabled ? title : undefined}
    >
      {label}
      <span className="cal-chip-n">{count}</span>
    </button>
  );
}

function EventRow({ e }: { e: CalendarEvent }) {
  return (
    <li className="cal-row">
      <Avatar symbol={e.symbol} name={e.name} />
      <Link to={`/companies/${e.symbol}`} className="cal-row-main">
        <span className="cal-row-name">
          {e.name}
          {e.watched && (
            <span className="cal-star" title="On your watchlist">
              <Icon name="star" size={12} />
            </span>
          )}
        </span>
        <span className="cal-row-meta">
          {e.symbol}
          {e.sector ? ` · ${e.sector}` : ""}
        </span>
      </Link>
      <Badge tone={e.status === "filed" ? "ok" : KIND_TONE[e.kind]} title={e.purpose ?? undefined}>
        {e.status === "filed" ? "Filed" : KIND_LABEL[e.kind]}
      </Badge>
      {e.source_url && (
        <a
          className="cal-source"
          href={e.source_url}
          target="_blank"
          rel="noreferrer"
          aria-label={`Intimation for ${e.name} (opens the NSE file)`}
          title="Open the intimation"
        >
          <Icon name="file" size={14} />
        </a>
      )}
    </li>
  );
}

type DayProps = {
  days: string[];
  today: string;
  selected: string;
  byDay: Map<string, CalendarEvent[]>;
  onPick: (day: string) => void;
};

/** A row of days that scrolls with momentum and snaps; the selected day is lit by a thumb that
 *  glides to it. Mouse users can drag it like a finger. */
function DayStrip({ days, today, selected, byDay, onPick }: DayProps) {
  const scroller = useRef<HTMLDivElement>(null);
  const drag = useRef<{ x: number; left: number; moved: boolean } | null>(null);
  const placed = useRef(false);

  // Keep the selected day centred: instantly the first time, smoothly after.
  useEffect(() => {
    const box = scroller.current;
    const tile = box?.querySelector<HTMLElement>('[aria-pressed="true"]');
    if (!box || !tile) return;
    const left = tile.offsetLeft - (box.clientWidth - tile.offsetWidth) / 2;
    box.scrollTo({
      left,
      behavior: placed.current && !reducedMotion() ? "smooth" : "auto",
    });
    placed.current = true;
  }, [selected]);

  const scrollBy = (dir: 1 | -1) =>
    scroller.current?.scrollBy({
      left: dir * scroller.current.clientWidth * 0.8,
      behavior: reducedMotion() ? "auto" : "smooth",
    });

  const onPointerDown = (ev: React.PointerEvent<HTMLDivElement>) => {
    if (ev.pointerType !== "mouse" || ev.button !== 0 || !scroller.current) return;
    const box = scroller.current;
    drag.current = { x: ev.clientX, left: box.scrollLeft, moved: false };
    const move = (m: PointerEvent) => {
      const d = drag.current;
      if (!d) return;
      const dx = m.clientX - d.x;
      if (Math.abs(dx) > 5 && !d.moved) {
        d.moved = true;
        box.classList.add("dragging"); // snapping off while it follows the pointer
      }
      if (d.moved) box.scrollLeft = d.left - dx;
    };
    const up = () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
      box.classList.remove("dragging");
      // The click that ends a drag must not pick a day; clear the flag after it has fired.
      window.setTimeout(() => (drag.current = null), 0);
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
  };

  const onKeyDown = (ev: React.KeyboardEvent) => {
    const i = days.indexOf(selected);
    const next =
      ev.key === "ArrowRight" ? days[i + 1] : ev.key === "ArrowLeft" ? days[i - 1] : undefined;
    if (!next) return;
    ev.preventDefault();
    onPick(next);
    requestAnimationFrame(() =>
      scroller.current?.querySelector<HTMLElement>('[aria-pressed="true"]')?.focus({
        preventScroll: true,
      }),
    );
  };

  return (
    <div className="cal-strip-wrap">
      <button
        type="button"
        className="icon-btn cal-edge cal-edge-l"
        aria-label="Scroll days back"
        onClick={() => scrollBy(-1)}
      >
        <Icon name="chevronLeft" />
      </button>
      <div
        className="cal-strip"
        ref={scroller}
        role="group"
        aria-label="Days"
        onPointerDown={onPointerDown}
        onKeyDown={onKeyDown}
      >
        <SegmentThumb selected='[aria-pressed="true"]' />
        {days.map((day) => {
          const n = byDay.get(day)?.length ?? 0;
          const mine = byDay.get(day)?.filter((e) => e.watched).length ?? 0;
          return (
            <button
              key={day}
              type="button"
              className="cal-day"
              data-weekend={isWeekend(day) || undefined}
              data-today={day === today || undefined}
              aria-pressed={day === selected}
              aria-current={day === today ? "date" : undefined}
              tabIndex={day === selected ? 0 : -1}
              aria-label={`${dayLong(day)}, ${n} ${n === 1 ? "company" : "companies"}`}
              onClick={() => {
                if (!drag.current?.moved) onPick(day);
              }}
            >
              <span className="cal-dow">{weekdayShort(day)}</span>
              <span className="cal-num">{dayNumber(day)}</span>
              <span className="cal-mon">{dayNumber(day) === "1" ? monthShort(day) : " "}</span>
              <span className="cal-count" data-empty={n === 0 || undefined}>
                {n || "·"}
                {mine > 0 && <i className="cal-mine" aria-hidden />}
              </span>
            </button>
          );
        })}
      </div>
      <button
        type="button"
        className="icon-btn cal-edge cal-edge-r"
        aria-label="Scroll days ahead"
        onClick={() => scrollBy(1)}
      >
        <Icon name="chevronRight" />
      </button>
    </div>
  );
}

/** Seven columns, each listing its companies; a short list shows every name, a long one a few
 *  and "+N more", which opens that day below. */
function WeekView({ days, today, selected, byDay, onPick }: DayProps) {
  return (
    <div className="cal-week">
      {days.map((day) => {
        const list = byDay.get(day) ?? [];
        return (
          <div
            key={day}
            className="cal-week-col"
            data-weekend={isWeekend(day) || undefined}
            data-selected={day === selected || undefined}
          >
            <button
              type="button"
              className="cal-week-head"
              data-today={day === today || undefined}
              aria-pressed={day === selected}
              onClick={() => onPick(day)}
            >
              <span className="cal-dow">{weekdayShort(day)}</span>
              <span className="cal-num">{dayNumber(day)}</span>
              <span className="cal-count" data-empty={list.length === 0 || undefined}>
                {list.length || "·"}
              </span>
            </button>
            <ul>
              {list.slice(0, 5).map((e) => (
                <li key={`${e.symbol}-${e.kind}`}>
                  <Link
                    to={`/companies/${e.symbol}`}
                    className="cal-pill"
                    data-kind={e.kind}
                    title={`${e.name} · ${e.status === "filed" ? "Results filed" : KIND_LABEL[e.kind]}`}
                  >
                    {e.watched && <i className="cal-mine" aria-hidden />}
                    {e.name.replace(/\b(limited|ltd\.?)$/i, "").trim()}
                  </Link>
                </li>
              ))}
              {list.length > 5 && (
                <li>
                  <button type="button" className="link-btn" onClick={() => onPick(day)}>
                    +{list.length - 5} more
                  </button>
                </li>
              )}
            </ul>
          </div>
        );
      })}
    </div>
  );
}

/** The month as a grid: a day's count, and its first names, at a glance. */
function MonthView({ days, month, today, selected, byDay, onPick }: DayProps & { month: string }) {
  return (
    <div className="cal-month" role="grid" aria-label={monthLong(selected)}>
      {days.slice(0, 7).map((d) => (
        <span key={d} className="cal-month-dow" role="columnheader">
          {weekdayShort(d)}
        </span>
      ))}
      {days.map((day) => {
        const list = byDay.get(day) ?? [];
        return (
          <button
            key={day}
            type="button"
            role="gridcell"
            className="cal-cell"
            data-outside={day.slice(0, 7) !== month || undefined}
            data-weekend={isWeekend(day) || undefined}
            data-today={day === today || undefined}
            aria-pressed={day === selected}
            aria-label={`${dayLong(day)}, ${list.length} ${list.length === 1 ? "company" : "companies"}`}
            onClick={() => onPick(day)}
          >
            <span className="cal-cell-top">
              <span className="cal-num">{dayNumber(day)}</span>
              {list.length > 0 && <span className="cal-count">{list.length}</span>}
            </span>
            <span className="cal-cell-names">
              {list.slice(0, 2).map((e) => (
                <span key={`${e.symbol}-${e.kind}`} data-kind={e.kind}>
                  {e.symbol}
                </span>
              ))}
              {list.length > 2 && <span className="muted">+{list.length - 2}</span>}
            </span>
          </button>
        );
      })}
    </div>
  );
}
