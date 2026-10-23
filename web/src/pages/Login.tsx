import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { api, ApiError } from "../api/client";
import { NewPasswordField, usePasswordRules } from "../components/PasswordRules";
import { dayNumber, daysFrom, iso, startOfWeek, weekdayShort } from "../lib/calendar";
import { ME_KEY, peekReturnPath, takeReturnPath, useMe } from "../lib/auth";
import { prefetchHome, publicWeekQuery } from "../lib/preload";
import { greeting, markWelcomed, tagTransition } from "../lib/welcome";

type Mode = "signin" | "request" | "confirm" | "first";

// After sign-in, the longest the handoff waits for the home screen's data before it plays anyway.
const HANDOFF_WAIT_MS = 800;

/** A wait of N seconds that counts down once a second. `start` begins it; `left` is 0 when idle. */
function useCountdown(): { left: number; start: (seconds: number) => void } {
  const [state, setState] = useState<{ until: number; now: number } | null>(null);
  const running = state !== null;
  useEffect(() => {
    if (!running) return;
    const timer = window.setInterval(
      () => setState((s) => (s ? { ...s, now: Date.now() } : s)),
      1000,
    );
    return () => window.clearInterval(timer);
  }, [running]);
  return {
    left: state ? Math.max(0, Math.ceil((state.until - state.now) / 1000)) : 0,
    start: (seconds) => setState({ until: Date.now() + seconds * 1000, now: Date.now() }),
  };
}

const clock = (seconds: number) =>
  `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;

// Companies listed under a date before "+N more".
const PER_DAY = 4;

/** The month the week is in, e.g. "October 2026", or "October – November 2026" when it crosses one. */
const weekMonths = (first: string, last: string): string => {
  const a = new Date(`${first}T00:00`);
  const b = new Date(`${last}T00:00`);
  const fmt = (d: Date, opts: Intl.DateTimeFormatOptions) => d.toLocaleDateString("en-IN", opts);
  if (a.getMonth() === b.getMonth()) return fmt(a, { month: "long", year: "numeric" });
  const from = fmt(a, { month: "long" });
  const to = fmt(b, { month: "long", year: "numeric" });
  return a.getFullYear() === b.getFullYear()
    ? `${from} – ${to}`
    : `${fmt(a, { month: "long", year: "numeric" })} – ${to}`;
};

/** Results this week, public: Monday to Sunday of the current week, a column per date with that
 * day's companies as bullets, and today highlighted. */
function WeekAhead() {
  const calendar = useQuery(publicWeekQuery());
  if (calendar.isPending) {
    // Holds the card's place while the list loads, so the page does not shift when it arrives.
    return <section className="login-week login-week-loading" aria-hidden />;
  }
  const events = (calendar.data?.events ?? []).filter((e) => e.kind === "results");
  if (events.length === 0) return null;
  const today = iso(new Date());
  const week = daysFrom(startOfWeek(today), 7);
  return (
    <section className="login-week" aria-label="Results this week">
      <h2>Results this week</h2>
      <p className="login-week-month">{weekMonths(week[0], week[6])}</p>
      <div className="login-week-cols">
        {week.map((date) => {
          const items = events.filter((e) => e.date === date);
          return (
            <div
              className={`login-week-day${date === today ? " is-today" : ""}`}
              key={date}
              aria-current={date === today ? "date" : undefined}
            >
              <time className="login-week-date" dateTime={date}>
                <span className="login-week-num">{dayNumber(date)}</span>
                <span className="login-week-mon">{weekdayShort(date)}</span>
              </time>
              <ul>
                {items.slice(0, PER_DAY).map((e) => (
                  <li key={`${e.date}-${e.symbol}`}>{e.name}</li>
                ))}
              </ul>
              {items.length > PER_DAY && (
                <span className="login-week-more">+{items.length - PER_DAY} more</span>
              )}
            </div>
          );
        })}
      </div>
    </section>
  );
}

function ConfirmField({
  value,
  onChange,
  maxLength,
}: {
  value: string;
  onChange: (value: string) => void;
  maxLength: number | undefined;
}) {
  return (
    <label className="field">
      Confirm new password
      <input
        type="password"
        name="confirm-password"
        autoComplete="new-password"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        maxLength={maxLength}
        required
      />
    </label>
  );
}

/** Sign-in, and the emailed-code password reset behind "Forgot password?". The password and the
 * code only ever leave in a POST body: nothing here puts them in an address, a title or storage. */
export function Login() {
  const navigate = useNavigate();
  const client = useQueryClient();
  const me = useMe();
  const [chosen, setMode] = useState<Mode>("signin");
  // A session that still holds the emailed first password can do nothing but choose a new one.
  const mode: Mode = me.data?.must_change_password ? "first" : chosen;
  const { maxLength, ready } = usePasswordRules();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [again, setAgain] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const { left, start: startWait } = useCountdown();
  const waiting = left > 0;

  // Signed in (just now, or already): go to the page that was asked for. The home screen's data
  // is loaded first (waiting at most HANDOFF_WAIT_MS), so it does not fill in and change size
  // during the short unlock animation.
  useEffect(() => {
    if (!me.data || me.data.must_change_password) return;
    let gone = false;
    const ready = peekReturnPath() === "/" ? prefetchHome(client) : Promise.resolve();
    const wait = new Promise((r) => window.setTimeout(r, HANDOFF_WAIT_MS));
    void Promise.race([ready, wait]).then(() => {
      if (gone) return;
      markWelcomed();
      tagTransition("enter"); // the desk settles in (a plain animation: the page stays clickable)
      navigate(takeReturnPath(), { replace: true });
    });
    return () => {
      gone = true;
    };
  }, [me.data, navigate, client]);

  const go = (next: Mode, message: string | null = null) => {
    setMode(next);
    setNewPassword("");
    setAgain("");
    setError(null);
    setNotice(message);
  };

  const fail = (e: unknown) => {
    setError(e instanceof Error ? e.message : "Something went wrong. Try again.");
    if (e instanceof ApiError && e.status === 429 && e.retryAfter) {
      startWait(e.retryAfter);
    }
  };

  const signIn = useMutation({
    mutationFn: () => api.login(email.trim(), password),
    onSuccess: (user) => client.setQueryData(ME_KEY, user),
    onError: (e) => {
      setPassword("");
      if (e instanceof ApiError && e.blocked) {
        go("request", e.message); // the account needs a new password: the code flow
      } else fail(e);
    },
  });
  const askCode = useMutation({
    mutationFn: () => api.requestReset(email.trim()),
    onSuccess: (r) => go("confirm", r.detail),
    onError: fail,
  });
  const setNew = useMutation({
    mutationFn: () => api.confirmReset(email.trim(), code.trim(), newPassword),
    onSuccess: () => {
      setCode("");
      setNewPassword("");
      setPassword("");
      go("signin", "Password changed. Sign in with the new password.");
    },
    onError: fail,
  });

  const setFirst = useMutation({
    mutationFn: () => api.firstPassword(password, newPassword),
    onSuccess: () => {
      // The server ended every session: nothing is signed in until the new password is used.
      setPassword("");
      client.setQueryData(ME_KEY, null);
      go("signin", "Password set. Sign in with your new password.");
    },
    onError: fail,
  });

  const submit = (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    if ((mode === "confirm" || mode === "first") && newPassword !== again) {
      setError("The two passwords do not match.");
      return;
    }
    if (mode === "signin") signIn.mutate();
    else if (mode === "request") askCode.mutate();
    else if (mode === "confirm") setNew.mutate();
    else setFirst.mutate();
  };
  const busy = signIn.isPending || askCode.isPending || setNew.isPending || setFirst.isPending;
  const needsRules = mode === "confirm" || mode === "first";

  return (
    <div className="login-screen">
      <div className="welcome-flow" aria-hidden>
        <span className="flow-a" />
        <span className="flow-b" />
        <span className="flow-c" />
      </div>
      <div className="login">
        <section className="login-intro">
          <span className="brand-mark welcome-mark" aria-hidden>
            A
          </span>
          <p className="welcome-greeting">{greeting()}</p>
          <p className="login-tagline">The analyst's record, kept for you.</p>
          <p className="welcome-lead">
            Quarterly results for every NSE-listed company, read from the filings themselves and
            checked before they reach you.
          </p>
          <WeekAhead />
        </section>
        <form className="login-card" onSubmit={submit} noValidate>
          <h1>
            {mode === "signin"
              ? "Sign in"
              : mode === "request"
                ? "Reset your password"
                : mode === "confirm"
                  ? "Enter your code"
                  : "Choose your password"}
          </h1>
          {notice && <p className="login-notice">{notice}</p>}
          {error && (
            <p className="error login-error" role="alert">
              {error}
            </p>
          )}

          {mode !== "first" && (
            <label className="field">
              Email
              <input
                type="email"
                name="email"
                autoComplete="username"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                maxLength={254}
                required
              />
            </label>
          )}

          {mode === "signin" && (
            <label className="field">
              Password
              <input
                type="password"
                name="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                maxLength={maxLength}
                required
              />
            </label>
          )}

          {mode === "first" && (
            <>
              <label className="field">
                First password
                <input
                  type="password"
                  name="first-password"
                  autoComplete="current-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  maxLength={maxLength}
                  required
                />
              </label>
              <NewPasswordField value={newPassword} onChange={setNewPassword} />
              <ConfirmField value={again} onChange={setAgain} maxLength={maxLength} />
            </>
          )}

          {mode === "confirm" && (
            <>
              <label className="field">
                Code
                <input
                  name="code"
                  inputMode="numeric"
                  autoComplete="one-time-code"
                  value={code}
                  onChange={(e) => setCode(e.target.value)}
                  maxLength={32}
                  required
                />
              </label>
              <NewPasswordField value={newPassword} onChange={setNewPassword} />
              <ConfirmField value={again} onChange={setAgain} maxLength={maxLength} />
            </>
          )}

          <button
            type="submit"
            className="btn btn-primary"
            disabled={busy || waiting || (needsRules && !ready)}
          >
            {waiting
              ? `Try again in ${clock(left)}`
              : mode === "signin"
                ? "Sign in"
                : mode === "request"
                  ? "Send code"
                  : mode === "confirm"
                    ? "Set new password"
                    : "Set password"}
          </button>

          {mode === "signin" ? (
            <>
              <button type="button" className="btn btn-ghost" disabled title="Coming soon">
                Sign in with Microsoft (soon)
              </button>
              <button type="button" className="login-link" onClick={() => go("request")}>
                Forgot password?
              </button>
            </>
          ) : mode === "first" ? (
            <button
              type="button"
              className="login-link"
              onClick={() => {
                setPassword("");
                // A session this limited holds nothing else, so only who-is-signed-in is reset.
                void api
                  .logout()
                  .catch(() => undefined)
                  .then(() => {
                    client.setQueryData(ME_KEY, null);
                    go("signin");
                  });
              }}
            >
              Sign out
            </button>
          ) : (
            <>
              {mode === "confirm" && (
                <button type="button" className="login-link" onClick={() => go("request")}>
                  Send a new code
                </button>
              )}
              <button type="button" className="login-link" onClick={() => go("signin")}>
                Back to sign in
              </button>
            </>
          )}
        </form>
      </div>
      <p className="welcome-foot">End-of-day data from NSE filings. No ratings or target prices.</p>
    </div>
  );
}
