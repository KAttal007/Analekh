import { useState } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import { CompanySearch } from "./components/CompanySearch";
import { Icon, type IconName } from "./components/Icon";
import { setTheme, type ThemeChoice, useTheme } from "./lib/theme";

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

const THEMES: { choice: ThemeChoice; icon: IconName; label: string }[] = [
  { choice: "light", icon: "sun", label: "Light theme" },
  { choice: "dark", icon: "moon", label: "Dark theme" },
  { choice: "system", icon: "monitor", label: "Match system theme" },
];

const COLLAPSED_KEY = "analekh.sidebar-collapsed";
const readCollapsed = () => {
  try {
    return localStorage.getItem(COLLAPSED_KEY) === "1";
  } catch {
    return false;
  }
};

function Item({ item }: { item: NavItem }) {
  return (
    <NavLink to={item.to} end={item.to === "/"} title={item.label} aria-label={item.label}>
      <Icon name={item.icon} />
      <span className="nav-label">{item.label}</span>
      {item.soon && <span className="badge soon">Soon</span>}
    </NavLink>
  );
}

function ThemeSwitch() {
  const { choice } = useTheme();
  return (
    <div className="theme-switch" role="group" aria-label="Theme">
      {THEMES.map((t) => (
        <button
          key={t.choice}
          type="button"
          title={t.label}
          aria-label={t.label}
          aria-pressed={choice === t.choice}
          onClick={() => setTheme(t.choice)}
        >
          <Icon name={t.icon} size={14} />
        </button>
      ))}
    </div>
  );
}

export function Layout() {
  const { pathname } = useLocation();
  const [collapsed, setCollapsed] = useState(readCollapsed);
  const toggle = () => {
    setCollapsed((c) => {
      try {
        localStorage.setItem(COLLAPSED_KEY, c ? "0" : "1");
      } catch {
        /* storage unavailable: the choice lasts for this page only */
      }
      return !c;
    });
  };

  return (
    <div className={collapsed ? "app collapsed" : "app"}>
      <aside className="sidebar">
        <Link to="/" className="brand" title="Analekh">
          <span className="brand-mark">A</span>
          <span className="brand-text">
            <span className="brand-name">Analekh</span>
            <span className="brand-tagline">The analyst's record, kept for you.</span>
          </span>
        </Link>
        <nav className="nav" aria-label="Main">
          {GROUPS.map((g) => (
            <div key={g.label} className="nav nav-group">
              <div className="nav-group-label">{g.label}</div>
              {g.items.map((i) => (
                <Item key={i.to} item={i} />
              ))}
            </div>
          ))}
        </nav>
        <nav className="nav nav-bottom" aria-label="Settings">
          <Item item={SETTINGS} />
          <div className="sidebar-tools">
            <ThemeSwitch />
            <button
              type="button"
              className="icon-btn collapse-btn"
              title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
              aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
              aria-expanded={!collapsed}
              onClick={toggle}
            >
              <Icon name="panel" />
            </button>
          </div>
        </nav>
      </aside>
      <div className="workspace">
        <header className="topbar">
          <CompanySearch />
        </header>
        {/* Keyed by path so each screen's sections fade in when it opens. */}
        <main className="content page-enter" key={pathname}>
          <Outlet />
        </main>
      </div>
    </div>
  );
}
