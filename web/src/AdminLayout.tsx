import { useEffect } from "react";
import { Link, Navigate, NavLink, Outlet } from "react-router-dom";
import { SignOut } from "./Layout";
import { Loading } from "./components/ui";
import { useMe } from "./lib/auth";
import { unlockChimeOnGesture } from "./lock/chime";
import { IdleReminder } from "./lock/IdleReminder";
import { SignInLocks } from "./lock/SignInLocks";

const ITEMS = [
  { to: "/admin/users", label: "Users" },
  { to: "/admin/locks", label: "Model locks" },
  { to: "/admin/templates", label: "Templates" },
  { to: "/admin/settings", label: "Settings" },
];

/** The admin area's own shell: Users, Model locks, Templates and Settings, and a way back. A
 * non-admin is sent to the home page (the server answers 403 to them anyway). */
export function AdminLayout() {
  const me = useMe();
  if (me.isPending) return <Loading />;
  if (me.data?.role !== "admin") return <Navigate to="/" replace />;
  return <AdminShell />;
}

function AdminShell() {
  useEffect(() => unlockChimeOnGesture(), []);
  return (
    <div className="app admin">
      <aside className="sidebar">
        <Link to="/admin/users" className="brand" title="Analekh admin">
          <span className="brand-mark">A</span>
          <span className="brand-text">
            <span className="brand-name">Analekh</span>
          </span>
          <span className="admin-tag">Admin</span>
        </Link>
        <nav className="nav" aria-label="Admin">
          <div className="nav-group-label">Manage</div>
          {ITEMS.map((i) => (
            <NavLink key={i.to} to={i.to}>
              <span className="nav-label">{i.label}</span>
            </NavLink>
          ))}
          <Link to="/" className="admin-back">
            ← Back to Analekh
          </Link>
        </nav>
        <nav className="nav nav-bottom" aria-label="Account">
          <SignOut />
        </nav>
      </aside>
      <div className="workspace">
        <main className="content admin-content">
          <Outlet />
        </main>
        <div className="lock-corner">
          <SignInLocks />
          <IdleReminder />
        </div>
      </div>
    </div>
  );
}
