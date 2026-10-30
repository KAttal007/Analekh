import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { api, ApiError, type LoginOut, type Me, type SessionLimit } from "../api/client";
import { NewPasswordField, usePasswordRules } from "../components/PasswordRules";
import { dayNumber, daysFrom, iso, startOfWeek, weekdayShort } from "../lib/calendar";
import { ME_KEY, peekReturnPath, takeReturnPath, useMe } from "../lib/auth";
import { prefetchHome, publicWeekQuery } from "../lib/preload";
import { greeting, markWelcomed, tagTransition } from "../lib/welcome";
import { forgetSignInLocks } from "../lock/signInMark";

type Mode = "signin" | "request" | "confirm" | "first" | "devices" | "name";

const HANDOFF_WAIT_MS = 800;
const NAME_MAX = 40; // device_name_max_length on the server, which checks it again
// The device id the person chose not to name, so the suggestion is not repeated on that browser.
const SKIPPED_KEY = "analekh.device-name-skipped";

function useCountdown(): { left: number; start: (seconds: number) => void } {
  const [state, setState] = useState<{ until: number; now: number } | null>(null);
  const running = state !== null;
  useEffect(() => {
    if (!running) return;
    const timer = window.setInterval(() => setState((s) => (s ? { ...s, now: Date.now() } : s)), 1000);
    return () => window.clearInterval(timer);
  }, [running]);
  return {
    left: state ? Math.max(0, Math.ceil((state.until - state.now) / 1000)) : 0,
    start: (seconds) => setState({ until: Date.now() + seconds * 1000, now: Date.now() }),
  };
}

const when = (stamp: string) => new Date(stamp).toLocaleString("en-IN", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });

/** At the session limit: the live devices, each with a button that signs it out and this one in. */
function DeviceChoice({ held, busy, onPick }: { held: SessionLimit; busy: boolean; onPick: (deviceId: string) => void }) {
  return (
    <ul className="login-devices">
      {held.devices.map((d) => (
        <li key={d.device_id}>
          <span className="login-device-name">{d.name ?? d.label ?? "Unknown device"}</span>
          <span className="login-device-meta">
            {d.name && d.label ? `${d.label} · ` : ""}Device ID <code>{d.device_id}</code> · signed in {when(d.signed_in_at)} · last active {when(d.last_seen_at)}
          </span>
          <button type="button" className="btn btn-ghost" disabled={busy} onClick={() => onPick(d.device_id)}>
            Sign out of this device
          </button>
        </li>
      ))}
    </ul>
  );
}

const clock = (seconds: number) => `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;

const PER_DAY = 4;

const weekMonths = (first: string, last: string): string => {
  const a = new Date(`${first}T00:00`);
  const b = new Date(`${last}T00:00`);
  const fmt = (d: Date, opts: Intl.DateTimeFormatOptions) => d.toLocaleDateString("en-IN", opts);
  if (a.getMonth() === b.getMonth()) return fmt(a, { month: "long", year: "numeric" });
  const from = fmt(a, { month: "long" });
  const to = fmt(b, { month: "long", year: "numeric" });
  return a.getFullYear() === b.getFullYear() ? `${from} – ${to}` : `${fmt(a, { month: "long", year: "numeric" })} – ${to}`;
};

/** Results this week, public: Monday to Sunday of the current week, a column per date with that
 * day's companies as bullets, and today highlighted. */
function WeekAhead() {
  const calendar = useQuery(publicWeekQuery());
  if (calendar.isPending) {
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
            <div className={`login-week-day${date === today ? " is-today" : ""}`} key={date} aria-current={date === today ? "date" : undefined}>
              <time className="login-week-date" dateTime={date}>
                <span className="login-week-num">{dayNumber(date)}</span>
                <span className="login-week-mon">{weekdayShort(date)}</span>
              </time>
              <ul>
                {items.slice(0, PER_DAY).map((e) => (
                  <li key={`${e.date}-${e.symbol}`}>{e.name}</li>
                ))}
              </ul>
              {items.length > PER_DAY && <span className="login-week-more">+{items.length - PER_DAY} more</span>}
            </div>
          );
        })}
      </div>
    </section>
  );
}

function ConfirmField({ value, onChange, maxLength }: { value: string; onChange: (value: string) => void; maxLength: number | undefined }) {
  return (
    <label className="field">
      Confirm new password
      <input type="password" name="confirm-password" autoComplete="new-password" value={value} onChange={(e) => onChange(e.target.value)} maxLength={maxLength} required />
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
  const mode: Mode = me.data?.must_change_password ? "first" : chosen;
  const { maxLength, ready } = usePasswordRules();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [again, setAgain] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [held, setHeld] = useState<SessionLimit | null>(null);
  const [pending, setPending] = useState<LoginOut | null>(null); // signed in, offered a name first
  const [deviceName, setDeviceName] = useState("");
  const { left, start: startWait } = useCountdown();
  const waiting = left > 0;

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
    if (next !== "devices") setHeld(null);
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

  const finish = (result: LoginOut) => {
    const user: Me = { id: result.id, name: result.name, email: result.email, role: result.role, must_change_password: result.must_change_password };
    setHeld(null);
    setPending(null);
    forgetSignInLocks();
    client.setQueryData<Me>(ME_KEY, user);
  };
  // A device with no name yet: suggest one (the browser label, ready to edit) before going on.
  const signedIn = (result: LoginOut) => {
    const { device } = result;
    if (result.must_change_password || device.name || localStorage.getItem(SKIPPED_KEY) === device.device_id) {
      finish(result);
      return;
    }
    setPending(result);
    setDeviceName(device.label ?? "");
    go("name", "Give this device a name so you can tell it apart from your others, for example \u201cOffice laptop\u201d.");
  };
  const skipName = () => {
    if (!pending) return;
    localStorage.setItem(SKIPPED_KEY, pending.device.device_id);
    finish(pending);
  };
  const atLimit = (e: unknown): boolean => {
    if (!(e instanceof ApiError) || !e.sessionLimit) return false;
    setHeld(e.sessionLimit);
    setMode("devices");
    setError(null);
    setNotice(e.sessionLimit.detail);
    return true;
  };

  const signIn = useMutation({
    mutationFn: () => api.login(email.trim(), password),
    onSuccess: signedIn,
    onError: (e) => {
      setPassword("");
      if (atLimit(e)) return;
      if (e instanceof ApiError && e.blocked) {
        go("request", e.message); // the account needs a new password: the code flow
      } else fail(e);
    },
  });
  const replace = useMutation({
    mutationFn: (deviceId: string) => api.replaceSession(held?.choice_token ?? "", deviceId),
    onSuccess: signedIn,
    onError: (e) => {
      if (atLimit(e)) return; // the device had already gone and the list is still full
      if (e instanceof ApiError && e.status === 401) go("signin", e.message);
      else fail(e);
    },
  });
  const saveName = useMutation({
    mutationFn: () => api.nameDevice(deviceName),
    onSuccess: () => {
      if (pending) finish(pending);
    },
    onError: fail,
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
    if (mode === "devices") return; // each device row has its own button
    if (mode === "name") {
      saveName.mutate();
      return;
    }
    if (mode === "signin") signIn.mutate();
    else if (mode === "request") askCode.mutate();
    else if (mode === "confirm") setNew.mutate();
    else setFirst.mutate();
  };
  const busy = saveName.isPending || replace.isPending || signIn.isPending || askCode.isPending || setNew.isPending || setFirst.isPending;
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
          <p className="welcome-lead">Quarterly results for every NSE-listed company, read from the filings themselves and checked before they reach you.</p>
          <WeekAhead />
        </section>
        <form className="login-card" onSubmit={submit} noValidate>
          <h1>
            {mode === "signin"
              ? "Sign in"
              : mode === "devices"
                ? "Too many devices"
                : mode === "name"
                  ? "Name this device"
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

          {mode === "devices" && held && <DeviceChoice held={held} busy={busy} onPick={(id) => replace.mutate(id)} />}

          {mode === "name" && (
            <label className="field">
              Device name
              <input name="device-name" autoComplete="off" value={deviceName} onChange={(e) => setDeviceName(e.target.value)} maxLength={NAME_MAX} autoFocus />
            </label>
          )}

          {mode !== "first" && mode !== "devices" && mode !== "name" && (
            <label className="field">
              Email
              <input type="email" name="email" autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} maxLength={254} required />
            </label>
          )}

          {mode === "signin" && (
            <label className="field">
              Password
              <input type="password" name="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} maxLength={maxLength} required />
            </label>
          )}

          {mode === "first" && (
            <>
              <label className="field">
                First password
                <input type="password" name="first-password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} maxLength={maxLength} required />
              </label>
              <NewPasswordField value={newPassword} onChange={setNewPassword} />
              <ConfirmField value={again} onChange={setAgain} maxLength={maxLength} />
            </>
          )}

          {mode === "confirm" && (
            <>
              <label className="field">
                Code
                <input name="code" inputMode="numeric" autoComplete="one-time-code" value={code} onChange={(e) => setCode(e.target.value)} maxLength={32} required />
              </label>
              <NewPasswordField value={newPassword} onChange={setNewPassword} />
              <ConfirmField value={again} onChange={setAgain} maxLength={maxLength} />
            </>
          )}

          {mode !== "devices" && (
            <button type="submit" className="btn btn-primary" disabled={busy || waiting || (needsRules && !ready)}>
              {waiting
                ? `Try again in ${clock(left)}`
                : mode === "signin"
                  ? "Sign in"
                  : mode === "request"
                    ? "Send code"
                    : mode === "confirm"
                      ? "Set new password"
                      : mode === "name"
                        ? "Save name"
                        : "Set password"}
            </button>
          )}

          {mode === "signin" ? (
            <>
              <button type="button" className="btn btn-ghost" disabled title="Coming soon">
                Sign in with Microsoft (soon)
              </button>
              <button type="button" className="login-link" onClick={() => go("request")}>
                Forgot password?
              </button>
            </>
          ) : mode === "name" ? (
            <button type="button" className="login-link" disabled={busy} onClick={skipName}>
              Skip for now
            </button>
          ) : mode === "first" ? (
            <button
              type="button"
              className="login-link"
              onClick={() => {
                setPassword("");
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
