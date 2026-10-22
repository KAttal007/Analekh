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

function AddUser({ onClose }: { onClose: () => void }) {
  const qc = useQueryClient();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<Role>("analyst");
  const add = useMutation({
    mutationFn: () =>
      api.createUser({
        name: name.trim(),
        email: email.trim(),
        role,
        password: password || undefined,
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["users"] });
      onClose();
    },
  });
  const submit = (e: FormEvent) => {
    e.preventDefault();
    add.mutate();
  };
  return (
    <aside className="admin-panel" role="dialog" aria-label="Add user">
      <form onSubmit={submit}>
        <h2>Add user</h2>
        <p className="muted">
          They sign in with the email and the first password you set here, and can change it any
          time with “Forgot password?”.
        </p>
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
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            maxLength={254}
            required
          />
        </label>
        <label className="field">
          First password
          <input
            type="password"
            autoComplete="new-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            maxLength={128}
          />
        </label>
        <fieldset className="admin-roles">
          <legend>Role</legend>
          {(["analyst", "admin"] as Role[]).map((r) => (
            <label key={r} className="field-inline">
              <input
                type="radio"
                name="role"
                checked={role === r}
                onChange={() => setRole(r)}
                aria-label={r === "admin" ? "Admin" : "Analyst"}
              />
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

function ResetPassword({ user, onClose }: { user: AdminUserRow; onClose: () => void }) {
  const [password, setPassword] = useState("");
  const reset = useMutation({
    mutationFn: () => api.resetUserPassword(user.id, password),
    onSuccess: onClose,
  });
  return (
    <aside className="admin-panel" role="dialog" aria-label="Reset password">
      <form
        onSubmit={(e) => {
          e.preventDefault();
          reset.mutate();
        }}
      >
        <h2>Reset password</h2>
        <p className="muted">
          Sets a new password for {user.name}, signs them out everywhere and clears any block.
        </p>
        {reset.isError && (
          <p className="error" role="alert">
            {reset.error.message}
          </p>
        )}
        <label className="field">
          New password
          <input
            type="password"
            autoComplete="new-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            maxLength={128}
            required
          />
        </label>
        <div className="admin-panel-actions">
          <button type="button" className="btn" onClick={onClose}>
            Cancel
          </button>
          <button type="submit" className="btn btn-primary" disabled={reset.isPending}>
            Set password
          </button>
        </div>
      </form>
    </aside>
  );
}

export function Users() {
  const qc = useQueryClient();
  const me = useMe().data;
  const users = useQuery({ queryKey: ["users"], queryFn: api.users });
  const [find, setFind] = useState("");
  const [adding, setAdding] = useState(false);
  const [resetting, setResetting] = useState<AdminUserRow | null>(null);
  const done = () => qc.invalidateQueries({ queryKey: ["users"] });
  const change = useMutation({
    mutationFn: ({ id, body }: { id: string; body: UserChange }) => api.updateUser(id, body),
    onSuccess: done,
  });
  const unblock = useMutation({ mutationFn: (id: string) => api.unblockUser(id), onSuccess: done });

  const q = find.trim().toLowerCase();
  const rows = (users.data ?? []).filter(
    (u) => !q || u.name.toLowerCase().includes(q) || u.email.toLowerCase().includes(q),
  );
  const failure = change.error ?? unblock.error;

  return (
    <div className="page">
      <PageHeader
        title="Users"
        subtitle="Who can sign in to Analekh, and what they can do. Only admins reach this area."
      />
      <div className="admin-bar">
        <input
          placeholder="Search name or email"
          aria-label="Search users"
          value={find}
          onChange={(e) => setFind(e.target.value)}
        />
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
                      <Badge tone={u.role === "admin" ? "accent" : "neutral"}>
                        {u.role === "admin" ? "Admin" : "Analyst"}
                      </Badge>
                    </td>
                    <td>{u.auth_kind === "password" ? "Password" : "Microsoft"}</td>
                    <td className="muted">{u.last_seen_at ? filedAt(u.last_seen_at) : "Never"}</td>
                    <td>
                      <Status u={u} />
                    </td>
                    <td>
                      <div className="admin-actions">
                        {u.is_active && u.blocked && (
                          <button
                            type="button"
                            className="btn btn-sm"
                            onClick={() => unblock.mutate(u.id)}
                          >
                            Unblock
                          </button>
                        )}
                        {u.is_active && u.auth_kind === "password" && (
                          <button
                            type="button"
                            className="btn btn-sm"
                            onClick={() => setResetting(u)}
                          >
                            Reset password
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
                        <button
                          type="button"
                          className="btn btn-sm"
                          onClick={() =>
                            change.mutate({ id: u.id, body: { is_active: !u.is_active } })
                          }
                        >
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
      {resetting && <ResetPassword user={resetting} onClose={() => setResetting(null)} />}
    </div>
  );
}
