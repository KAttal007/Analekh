import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { api, type AdminUserRow, type UserChange } from "../../api/client";
import { Badge, ErrorNote, PageHeader, Skeleton } from "../../components/ui";
import { useMe } from "../../lib/auth";
import { filedAt } from "../../lib/format";

type Role = "admin" | "analyst";

const initials = (name: string) =>
  name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((w) => w[0].toUpperCase())
    .join("");

function Status({ u }: { u: AdminUserRow }) {
  if (!u.is_active) return <Badge>Disabled</Badge>;
  if (u.blocked) return <Badge tone="error">Blocked</Badge>;
  if (u.paused_until) return <Badge tone="warn">Paused until {filedAt(u.paused_until)}</Badge>;
  return <Badge tone="ok">Active</Badge>;
}

type MailState = AdminUserRow["first_password_mail"];

const MAIL_CHECK_MS = 1500;

function MailNote({ email, state, again }: { email: string; state: MailState; again: () => void }) {
  if (state !== "failed")
    return (
      <p className="muted" role="status">
        {state === "sent" ? `A first password has been emailed to ${email}. It works for 24 hours.` : `Emailing a first password to ${email}…`}
      </p>
    );
  return (
    <p className="error" role="alert">
      The welcome email was not sent.{" "}
      <button type="button" className="btn btn-sm" onClick={again}>
        Send again
      </button>
    </p>
  );
}

function AddUser({ onClose }: { onClose: () => void }) {
  const qc = useQueryClient();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<Role>("analyst");
  const refresh = () => void qc.invalidateQueries({ queryKey: ["users"] });
  const add = useMutation({
    mutationFn: () => api.createUser({ name: name.trim(), email: email.trim(), role }),
    onSuccess: refresh,
  });
  const again = useMutation({
    mutationFn: () => api.sendFirstPassword(add.data!.id),
    onSuccess: refresh,
  });
  const listed = useQuery({ queryKey: ["users"], queryFn: api.users, enabled: false }).data;
  const state: MailState = listed?.find((u) => u.id === add.data?.id)?.first_password_mail ?? again.data?.first_password_mail ?? add.data?.first_password_mail;
  const submit = (e: FormEvent) => {
    e.preventDefault();
    add.mutate();
  };
  if (add.data) {
    return (
      <aside className="admin-panel" role="dialog" aria-label="User added">
        <h2>User added</h2>
        <p>{add.data.name} can sign in once they have the first password.</p>
        {again.isError && (
          <p className="error" role="alert">
            {again.error.message}
          </p>
        )}
        <MailNote email={add.data.email} state={state} again={() => again.mutate()} />
        <div className="admin-panel-actions">
          <button type="button" className="btn btn-primary" onClick={onClose}>
            Done
          </button>
        </div>
      </aside>
    );
  }
  return (
    <aside className="admin-panel" role="dialog" aria-label="Add user">
      <form onSubmit={submit}>
        <h2>Add user</h2>
        <p className="muted">We email them a first password. They choose their own the first time they sign in.</p>
        {add.isError && (
          <p className="error" role="alert">
            {add.error.message}
          </p>
        )}
        <label className="field">
          Name
          <input value={name} onChange={(e) => setName(e.target.value)} maxLength={120} required />
        </label>
        <label className="field">
          Work email
          <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} maxLength={254} required />
        </label>
        <fieldset className="admin-roles">
          <legend>Role</legend>
          {(["analyst", "admin"] as Role[]).map((r) => (
            <label key={r} className="field-inline">
              <input type="radio" name="role" checked={role === r} onChange={() => setRole(r)} aria-label={r === "admin" ? "Admin" : "Analyst"} />
              {r === "admin" ? "Admin" : "Analyst"}
            </label>
          ))}
        </fieldset>
        <div className="admin-panel-actions">
          <button type="button" className="btn" onClick={onClose}>
            Cancel
          </button>
          <button type="submit" className="btn btn-primary" disabled={add.isPending}>
            Add user
          </button>
        </div>
      </form>
    </aside>
  );
}

function sendLabel(u: AdminUserRow) {
  return u.must_change_password ? "Send first password" : "Reset password";
}

function SendFirstPassword({ user, onClose }: { user: AdminUserRow; onClose: () => void }) {
  const qc = useQueryClient();
  const send = useMutation({
    mutationFn: () => api.sendFirstPassword(user.id),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["users"] });
      onClose();
    },
  });
  const label = sendLabel(user);
  return (
    <aside className="admin-panel" role="dialog" aria-label={label}>
      <h2>{user.must_change_password ? `Send ${user.name} a new first password?` : `Reset ${user.name}'s password?`}</h2>
      <p className="muted">
        Their current password stops working, they are signed out everywhere and any block is cleared. They get an email with a new first password and choose their own when they next sign in.
      </p>
      {send.isError && (
        <p className="error" role="alert">
          {send.error.message}
        </p>
      )}
      <div className="admin-panel-actions">
        <button type="button" className="btn" onClick={onClose}>
          Cancel
        </button>
        <button type="button" className="btn btn-primary" disabled={send.isPending} onClick={() => send.mutate()}>
          {label}
        </button>
      </div>
    </aside>
  );
}

export function Users() {
  const qc = useQueryClient();
  const me = useMe().data;
  const users = useQuery({
    queryKey: ["users"],
    queryFn: api.users,
    refetchInterval: (q) => (q.state.data?.some((u) => u.first_password_mail === "sending") ? MAIL_CHECK_MS : false),
  });
  const [find, setFind] = useState("");
  const [adding, setAdding] = useState(false);
  const [sending, setSending] = useState<AdminUserRow | null>(null);
  const done = () => qc.invalidateQueries({ queryKey: ["users"] });
  const change = useMutation({
    mutationFn: ({ id, body }: { id: string; body: UserChange }) => api.updateUser(id, body),
    onSuccess: done,
  });
  const unblock = useMutation({ mutationFn: (id: string) => api.unblockUser(id), onSuccess: done });

  const q = find.trim().toLowerCase();
  const rows = (users.data ?? []).filter((u) => !q || u.name.toLowerCase().includes(q) || u.email.toLowerCase().includes(q));
  const failure = change.error ?? unblock.error;

  return (
    <div className="page">
      <PageHeader title="Users" subtitle="Who can sign in to Analekh, and what they can do. Only admins reach this area." />
      <div className="admin-bar">
        <input placeholder="Search name or email" aria-label="Search users" value={find} onChange={(e) => setFind(e.target.value)} />
        <span className="admin-spacer" />
        <button type="button" className="btn btn-primary" onClick={() => setAdding(true)}>
          Add user
        </button>
      </div>
      {failure && (
        <p className="error" role="alert">
          {failure.message}
        </p>
      )}
      {users.isError ? (
        <ErrorNote error={users.error} />
      ) : !users.data ? (
        <Skeleton height={200} />
      ) : (
        <div className="card">
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Role</th>
                  <th>Sign-in</th>
                  <th>Last seen</th>
                  <th>Status</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {rows.map((u) => (
                  <tr key={u.id} className={u.is_active ? undefined : "admin-dim"}>
                    <td>
                      <div className="admin-who">
                        <span className="admin-avatar" aria-hidden>
                          {initials(u.name)}
                        </span>
                        <div>
                          <div className="admin-name">{u.name}</div>
                          <div className="muted admin-email">{u.email}</div>
                        </div>
                      </div>
                    </td>
                    <td>
                      <Badge tone={u.role === "admin" ? "accent" : "neutral"}>{u.role === "admin" ? "Admin" : "Analyst"}</Badge>
                    </td>
                    <td>{u.auth_kind === "password" ? "Password" : "Microsoft"}</td>
                    <td className="muted">{u.last_seen_at ? filedAt(u.last_seen_at) : "Never"}</td>
                    <td>
                      <Status u={u} />
                      {u.is_active && u.must_change_password && <Badge tone="warn">Waiting for first sign-in</Badge>}
                      {u.first_password_mail === "sending" && <Badge>Emailing…</Badge>}
                      {u.first_password_mail === "failed" && <Badge tone="error">Email not sent</Badge>}
                    </td>
                    <td>
                      <div className="admin-actions">
                        {u.is_active && u.blocked && (
                          <button type="button" className="btn btn-sm" onClick={() => unblock.mutate(u.id)}>
                            Unblock
                          </button>
                        )}
                        {u.is_active && u.auth_kind === "password" && (
                          <button type="button" className="btn btn-sm" onClick={() => setSending(u)}>
                            {sendLabel(u)}
                          </button>
                        )}
                        {u.is_active && u.id !== me?.id && (
                          <button
                            type="button"
                            className="btn btn-sm"
                            onClick={() =>
                              change.mutate({
                                id: u.id,
                                body: { role: u.role === "admin" ? "analyst" : "admin" },
                              })
                            }
                          >
                            {u.role === "admin" ? "Make analyst" : "Make admin"}
                          </button>
                        )}
                        <button type="button" className="btn btn-sm" onClick={() => change.mutate({ id: u.id, body: { is_active: !u.is_active } })}>
                          {u.is_active ? "Disable" : "Enable"}
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
      <p className="muted admin-note">The last active admin cannot be disabled or demoted.</p>
      {adding && <AddUser onClose={() => setAdding(false)} />}
      {sending && <SendFirstPassword user={sending} onClose={() => setSending(null)} />}
    </div>
  );
}
