import { Link, NavLink, Outlet } from "react-router-dom";
import { CompanySearch } from "./components/CompanySearch";
import { Icon, type IconName } from "./components/Icon";

type NavItem = { to: string; label: string; icon: IconName; soon?: boolean };

// Sections from design doc 19.1. `soon` marks screens that arrive in Phases 4-5.
const GROUPS: { label: string; items: NavItem[] }[] = [
  {
    label: "Research",
    items: [
      { to: "/", label: "Home", icon: "home" },
      { to: "/watchlist", label: "Watchlist", icon: "star" },
    ],
  },
  {
    label: "Modelling",
    items: [
      { to: "/models", label: "Models", icon: "table" },
      { to: "/templates", label: "Templates", icon: "layers" },
    ],
  },
  {
    label: "Outputs",
    items: [
      { to: "/reports", label: "Reports", icon: "file", soon: true },
      { to: "/qa", label: "Q&A", icon: "chat", soon: true },
      { to: "/comps", label: "Comps", icon: "bars", soon: true },
    ],
  },
];
const SETTINGS: NavItem = { to: "/settings", label: "Settings", icon: "sliders", soon: true };

function Item({ item }: { item: NavItem }) {
  return (
    <NavLink to={item.to} end={item.to === "/"}>
      <Icon name={item.icon} />
      {item.label}
      {item.soon && <span className="badge soon">Soon</span>}
    </NavLink>
  );
}

export function Layout() {
  return (
    <div className="app">
      <aside className="sidebar">
        <Link to="/" className="brand">
          <span className="brand-mark">A</span>
          <span>
            <span className="brand-name">Analekh</span>
            <span className="brand-tagline">The analyst's record, kept for you.</span>
          </span>
        </Link>
        <nav className="nav" aria-label="Main">
          {GROUPS.map((g) => (
            <div key={g.label} className="nav">
              <div className="nav-group-label">{g.label}</div>
              {g.items.map((i) => (
                <Item key={i.to} item={i} />
              ))}
            </div>
          ))}
        </nav>
        <nav className="nav nav-bottom" aria-label="Settings">
          <Item item={SETTINGS} />
        </nav>
      </aside>
      <div className="workspace">
        <header className="topbar">
          <CompanySearch />
        </header>
        <main className="content">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
