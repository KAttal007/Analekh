import { Link, Navigate, NavLink, Outlet } from "react-router-dom";
import { Loading } from "./components/ui";
import { useMe } from "./lib/auth";

const ITEMS = [
  { to: "/admin/users", label: "Users" },
  { to: "/admin/templates", label: "Templates" },
  { to: "/admin/settings", label: "Settings" },
];

/** The admin area's own shell: only Users, Templates and Settings, and a way back. A non-admin
 * is sent to the home page (the server answers 403 to them anyway). */
export function AdminLayout() {
  const me = useMe();
  if (me.isPending) return <Loading />;
  if (me.data?.role !== "admin") return <Navigate to="/" replace />;
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
      </aside>
      <div className="workspace">
        <main className="content admin-content">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
