import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { filedAt } from "../lib/format";
import { useMe } from "../lib/auth";
import { greeting, markWelcomed, tagTransition } from "../lib/welcome";

// The welcome screen is Analekh's lock screen: the page follows a scroll or swipe up, with some
// resistance, springs back when let go early, and opens the app past a threshold or on a click.
const COMMIT = 0.55; // share of the way (0..1) past which letting go opens the app
const REACH = 320; // px of scroll or swipe that take the page most of the way
const WHEEL_IDLE = 160; // ms without wheel movement that count as letting go

const reducedMotion = () =>
  typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

/** Counts up to `target` once it is known: quick at first, settling at the end. */
function useCountUp(target: number | undefined, ms = 900): number {
  const [value, setValue] = useState(0);
  const still = reducedMotion();
  useEffect(() => {
    if (target === undefined || still) return;
    let frame = 0;
    const start = performance.now();
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / ms);
      setValue(Math.round(target * (1 - (1 - t) ** 3)));
      if (t < 1) frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [target, ms, still]);
  return still ? (target ?? 0) : value; // reduced motion: the number, at once
}

function Stat({ value, label }: { value: number | undefined; label: string }) {
  const shown = useCountUp(value);
  return (
    <div className="welcome-stat">
      <span className="welcome-stat-value">
        {value === undefined ? "–" : shown.toLocaleString("en-IN")}
      </span>
      <span className="welcome-stat-label">{label}</span>
    </div>
  );
}

/** The first screen of a visit: what Analekh is, live numbers, and the way in. */
export function Welcome() {
  const navigate = useNavigate();
  const root = useRef<HTMLDivElement>(null);
  const enter = useRef<HTMLButtonElement>(null);
  const opened = useRef(false);
  const desk = useQuery({
    queryKey: ["public-welcome"],
    queryFn: api.publicWelcome,
    retry: false,
  });
  const d = desk.data;
  // Signed in (or sign-in switched off in development): the way in opens the desk. Otherwise it
  // brings up the sign-in screen. Read through a ref, because the gesture listeners are set up once.
  const me = useMe();
  const signedIn = useRef(false);
  useEffect(() => {
    signedIn.current = !!me.data;
  }, [me.data]);

  const open = () => {
    if (opened.current) return;
    opened.current = true;
    markWelcomed();
    // Gives this one transition its own choreography (styles.css): the page lifts away from
    // wherever the gesture left it; the desk settles in with the mark flying into the sidebar, or
    // the sign-in screen rises into place.
    tagTransition(signedIn.current ? "welcome" : "reveal");
    navigate(signedIn.current ? "/" : "/login", { viewTransition: true });
  };

  useEffect(() => {
    enter.current?.focus({ preventScroll: true });
    const el = root.current;
    if (!el) return;
    const still = reducedMotion();
    let distance = 0;
    let idle = 0;
    let touchY: number | null = null;
    let frame = 0;

    // Rubber band: the page moves freely at first and stiffens towards the end.
    const progress = () => 1 - Math.exp(-Math.max(0, distance) / REACH);
    const paint = () => {
      frame = 0;
      el.style.setProperty("--p", still ? "0" : progress().toFixed(4));
    };
    const follow = () => {
      el.classList.remove("springing");
      if (!frame) frame = requestAnimationFrame(paint);
    };
    const release = () => {
      if (progress() >= COMMIT) return open();
      distance = 0;
      el.classList.add("springing"); // back into place with a little overshoot
      paint();
    };

    const onWheel = (e: WheelEvent) => {
      distance += e.deltaY;
      follow();
      if (progress() >= 0.92) return open();
      window.clearTimeout(idle);
      idle = window.setTimeout(release, WHEEL_IDLE);
    };
    const onTouchStart = (e: TouchEvent) => {
      touchY = e.touches[0].clientY;
    };
    const onTouchMove = (e: TouchEvent) => {
      if (touchY === null) return;
      distance = (touchY - e.touches[0].clientY) * 1.4;
      follow();
    };
    const onTouchEnd = () => {
      touchY = null;
      release();
    };
    const onKey = (e: KeyboardEvent) => {
      if (["ArrowDown", "PageDown", " "].includes(e.key)) {
        e.preventDefault();
        open();
      }
    };
    // The light leans towards the pointer.
    const onPointer = (e: PointerEvent) => {
      if (still) return;
      el.style.setProperty("--mx", (e.clientX / window.innerWidth - 0.5).toFixed(3));
      el.style.setProperty("--my", (e.clientY / window.innerHeight - 0.5).toFixed(3));
    };

    el.addEventListener("wheel", onWheel, { passive: true });
    el.addEventListener("touchstart", onTouchStart, { passive: true });
    el.addEventListener("touchmove", onTouchMove, { passive: true });
    el.addEventListener("touchend", onTouchEnd);
    el.addEventListener("pointermove", onPointer);
    window.addEventListener("keydown", onKey);
    return () => {
      el.removeEventListener("wheel", onWheel);
      el.removeEventListener("touchstart", onTouchStart);
      el.removeEventListener("touchmove", onTouchMove);
      el.removeEventListener("touchend", onTouchEnd);
      el.removeEventListener("pointermove", onPointer);
      window.removeEventListener("keydown", onKey);
      window.clearTimeout(idle);
      cancelAnimationFrame(frame);
    };
    // open() only reads refs and stable router state; listeners are set up once.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    // A click anywhere opens the app, like tapping a lock screen; the button is the way in for
    // keyboards and screen readers.
    <div className="welcome" ref={root} onClick={open}>
      <div className="welcome-flow" aria-hidden>
        <span className="flow-a" />
        <span className="flow-b" />
        <span className="flow-c" />
      </div>
      <div className="welcome-inner">
        <span className="brand-mark welcome-mark">A</span>
        <p className="welcome-greeting">{greeting()}</p>
        <h1 className="welcome-title">The analyst's record, kept for you.</h1>
        <p className="welcome-lead">
          Quarterly results for every NSE-listed company, read from the filings themselves and
          checked before they reach you.
        </p>

        {!desk.isError && (
          <div className="welcome-stats" aria-live="polite">
            <Stat value={d?.companies_in_scope} label="companies tracked" />
            <Stat value={d?.filings_total} label="results filings" />
            <Stat
              value={d?.reported}
              label={d?.quarter_label ? `reported for ${d.quarter_label}` : "reported this quarter"}
            />
          </div>
        )}
        <p className="welcome-fresh">
          {d?.latest_filed_at ? `Latest filing collected ${filedAt(d.latest_filed_at)}` : " "}
        </p>

        <button ref={enter} type="button" className="btn-primary welcome-enter" onClick={open}>
          Open the results desk
          <span className="welcome-arrow" aria-hidden>
            →
          </span>
        </button>
      </div>

      <div className="welcome-hint" aria-hidden>
        <span className="welcome-chevron" />
        Scroll, swipe up or tap to enter
      </div>
      <p className="welcome-foot">End-of-day data from NSE filings. No ratings or target prices.</p>
    </div>
  );
}
