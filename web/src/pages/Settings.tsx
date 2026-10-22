import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type ReactNode, useState } from "react";
import { api, type ApiTokenCreated } from "../api/client";
import { ErrorNote, PageHeader, Segmented, Skeleton } from "../components/ui";
import { useMe, useSignInOff, useSignOut } from "../lib/auth";
import { crore, filedAt } from "../lib/format";
import { type Prefs, setPrefs, usePrefs } from "../lib/prefs";
import { setTheme, type ThemeChoice, useTheme } from "../lib/theme";

// Settings (design doc 19.1): display preferences and your own bridge token. What the scheduled
// jobs did, alerts, users, templates and the upload limit are in the admin area.

function Choice<T extends string>({
  label,
  hint,
  value,
  options,
  onChange,
}: {
  label: string;
  hint: ReactNode;
  value: T;
  options: { value: T; label: string }[];
  onChange: (v: T) => void;
}) {
  return (
    <li className="settings-row">
      <div className="settings-row-text">
        <strong>{label}</strong>
        <p className="muted">{hint}</p>
      </div>
      <Segmented label={label} options={options} value={value} onChange={onChange} />
    </li>
  );
}

const SAMPLE_CAP = "16391169600000"; // Reliance at the 16 Oct 2026 close

function Display() {
  const prefs = usePrefs();
  const { choice } = useTheme();
  const set =
    <K extends keyof Prefs>(key: K) =>
    (v: Prefs[K]) =>
      setPrefs({ [key]: v });
  return (
    <section className="card">
      <div className="card-header">
        <h2>Display</h2>
        <span className="muted">Saved in this browser</span>
      </div>
      <ul className="card-body settings-rows">
        <Choice<ThemeChoice>
          label="Theme"
          hint="System follows your device's light or dark setting."
          value={choice}
          options={[
            { value: "light", label: "Light" },
            { value: "dark", label: "Dark" },
            { value: "system", label: "System" },
          ]}
          onChange={setTheme}
        />
        <Choice
          label="Amounts"
          hint={
            <>
              Auto shows small companies in lakh and the rest in crore. Example:{" "}
              {crore(SAMPLE_CAP, prefs.units)}.
            </>
          }
          value={prefs.units}
          options={[
            { value: "auto", label: "Auto" },
            { value: "crore", label: "Crore" },
            { value: "million", label: "Million" },
          ]}
          onChange={set("units")}
        />
        <Choice
          label="Company page basis"
          hint="Which results a company page opens on when the company files both."
          value={prefs.basis}
          options={[
            { value: "consolidated", label: "Consolidated" },
            { value: "standalone", label: "Standalone" },
          ]}
          onChange={set("basis")}
        />
        <Choice
          label="Results desk order"
          hint="How the Home page lists the quarter's results."
          value={prefs.deskSort}
          options={[
            { value: "filed", label: "Newest filing" },
            { value: "market_cap", label: "Largest market cap" },
          ]}
          onChange={set("deskSort")}
        />
      </ul>
    </section>
  );
}

/** Tokens for the Excel bridge and the Office add-in: made here, shown once, revocable. */
function BridgeTokens() {
  const qc = useQueryClient();
  const tokens = useQuery({ queryKey: ["tokens"], queryFn: api.tokens });
  const [name, setName] = useState("");
  const [fresh, setFresh] = useState<ApiTokenCreated | null>(null);
  const create = useMutation({
    mutationFn: () => api.createToken(name.trim()),
    onSuccess: (t) => {
      setFresh(t);
      setName("");
      void qc.invalidateQueries({ queryKey: ["tokens"] });
    },
  });
  const revoke = useMutation({
    mutationFn: (id: number) => api.revokeToken(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["tokens"] }),
  });
  return (
    <section className="card">
      <div className="card-header">
        <h2>Excel bridge token</h2>
        <span className="muted">For the bridge on your computer and the Excel add-in</span>
      </div>
      <div className="card-body settings-tokens">
        <p className="muted">
          A token lets the bridge act as you without your password. It is shown once, when you
          create it. Revoke it here at any time.
        </p>
        <form
          className="settings-token-form"
          onSubmit={(e) => {
            e.preventDefault();
            if (name.trim()) create.mutate();
          }}
        >
          <label className="field">
            Token name
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              maxLength={80}
              placeholder="Office laptop"
            />
          </label>
          <button type="submit" className="btn" disabled={!name.trim() || create.isPending}>
            Create token
          </button>
        </form>
        {create.isError && (
          <p className="error" role="alert">
            {create.error.message}
          </p>
        )}
        {fresh && (
          <div className="token-fresh" role="status">
            <p>
              <strong>{fresh.name}</strong>: copy this token now. It is shown only once.
            </p>
            <code className="token-value">{fresh.token}</code>
            <div className="token-actions">
              <button
                type="button"
                className="btn btn-sm"
                onClick={() => void navigator.clipboard?.writeText(fresh.token)}
              >
                Copy
              </button>
              <button type="button" className="btn btn-sm" onClick={() => setFresh(null)}>
                Done
              </button>
            </div>
          </div>
        )}
        {tokens.isError ? (
          <ErrorNote error={tokens.error} />
        ) : !tokens.data ? (
          <Skeleton height={40} />
        ) : tokens.data.length ? (
          <ul className="settings-rows">
            {tokens.data.map((t) => (
              <li key={t.id} className="settings-row">
                <div className="settings-row-text">
                  <strong>{t.name}</strong>
                  <p className="muted">Created {filedAt(t.created_at)}</p>
                </div>
                <button
                  type="button"
                  className="btn btn-sm"
                  aria-label={`Revoke ${t.name}`}
                  disabled={revoke.isPending}
                  onClick={() => revoke.mutate(t.id)}
                >
                  Revoke
                </button>
              </li>
            ))}
          </ul>
        ) : (
          <p className="muted">No tokens yet.</p>
        )}
      </div>
    </section>
  );
}

function Account() {
  const me = useMe().data;
  const signOut = useSignOut();
  const signInOff = useSignInOff();
  const offHint = signInOff ? "Sign-in is off in development" : undefined;
  const [confirming, setConfirming] = useState(false);
  if (!me) return null;
  return (
    <section className="card">
      <div className="card-header">
        <h2>Account</h2>
      </div>
      <div className="card-body settings-row">
        <div className="settings-row-text">
          <strong>{me.name}</strong>
          <p className="muted">
            {me.email} · {me.role === "admin" ? "Admin" : "Analyst"}
          </p>
        </div>
        <button
          type="button"
          className="btn btn-sm"
          disabled={signInOff}
          title={offHint}
          onClick={() => void signOut()}
        >
          Sign out
        </button>
      </div>
      <div className="card-body settings-row">
        <div className="settings-row-text">
          <strong>Sign out everywhere</strong>
          <p className="muted">
            {confirming
              ? "This ends your sessions in every browser and revokes your Excel bridge tokens. You will need to sign in again and make new tokens."
              : "For a lost laptop or a shared computer: ends every session and revokes your bridge tokens."}
          </p>
        </div>
        {confirming ? (
          <div className="settings-actions">
            <button type="button" className="btn btn-sm" onClick={() => setConfirming(false)}>
              Cancel
            </button>
            <button
              type="button"
              className="btn btn-sm btn-danger"
              onClick={() => void signOut(true)}
            >
              Sign out everywhere
            </button>
          </div>
        ) : (
          <button
            type="button"
            className="btn btn-sm"
            disabled={signInOff}
            title={offHint}
            onClick={() => setConfirming(true)}
          >
            Sign out everywhere
          </button>
        )}
      </div>
    </section>
  );
}

export function Settings() {
  return (
    <div className="page settings">
      <PageHeader
        title="Settings"
        subtitle="How figures are shown, and the token your Excel bridge uses to sign in."
      />
      <Account />
      <Display />
      <BridgeTokens />
    </div>
  );
}
