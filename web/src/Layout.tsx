import { useLayoutEffect, useRef, useState } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import { CompanySearch } from "./components/CompanySearch";
import { Icon, type IconName } from "./components/Icon";
import { SegmentThumb } from "./components/ui";
import { useMe, useSignInOff, useSignOut } from "./lib/auth";
import { setTheme, type ThemeChoice, useTheme } from "./lib/theme";

type NavItem = { to: string; label: string; icon: IconName; soon?: boolean };

// Sections from design doc 19.1. `soon` marks screens that arrive in Phase 4.
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
    items: [{ to: "/models", label: "Models", icon: "table" }],
  },
  {
    label: "Outputs",
    items: [
      { to: "/reports", label: "Reports", icon: "file" },
      { to: "/qa", label: "Q&A", icon: "chat", soon: true },
      { to: "/comps", label: "Comps", icon: "bars" },
    ],
  },
];
// Screens without the top search bar: those with their own company picker (Reports, Comps), and
// those that are not about one company (Models, which gets its own search; Templates; Settings).
const NO_SEARCH_BAR = new Set(["/reports", "/comps", "/models", "/settings"]);
const SETTINGS: NavItem = { to: "/settings", label: "Settings", icon: "sliders" };
const ADMIN: NavItem = { to: "/admin/users", label: "Admin", icon: "layers" };

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
      <SegmentThumb selected='[aria-pressed="true"]' />
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

/** One highlight behind the active tab that glides to the next tab instead of jumping. It follows
 * the sidebar's size without animating (collapsing, a phone's sideways scroll), and only glides
 * when the tab changes. */
function useNavHighlight(pathname: string, collapsed: boolean) {
  const aside = useRef<HTMLElement>(null);
  const highlight = useRef<HTMLSpanElement>(null);
  const shownFor = useRef<string | null>(null); // the path the highlight is on

  useLayoutEffect(() => {
    const side = aside.current;
    const mark = highlight.current;
    if (!side || !mark) return;
    const place = (glide: boolean) => {
      const link = side.querySelector<HTMLElement>("nav a.active");
      if (!link) {
        mark.style.opacity = "0";
        return;
      }
      const s = side.getBoundingClientRect();
      const l = link.getBoundingClientRect();
      mark.dataset.motion = glide ? "glide" : "instant";
      mark.style.opacity = "1";
      mark.style.width = `${l.width}px`;
      mark.style.height = `${l.height}px`;
      mark.style.transform = `translate(${l.left - s.left + side.scrollLeft}px, ${
        l.top - s.top + side.scrollTop
      }px)`;
    };
    // Glide only to a new tab; collapsing or expanding moves it with the sidebar.
    place(shownFor.current !== null && shownFor.current !== pathname);
    shownFor.current = pathname;
    // The sidebar resizing (collapsing, the window) moves the highlight with it, without
    // gliding. The first report comes straight after observing and is no resize: skip it, or it
    // would cut the glide short.
    let first = true;
    const resized = new ResizeObserver(() => {
      if (first) first = false;
      else place(false);
    });
    resized.observe(side);
    return () => resized.disconnect();
  }, [pathname, collapsed]);

  // A faint light follows the pointer across the sidebar, as on the welcome screen.
  useLayoutEffect(() => {
    const side = aside.current;
    if (!side) return;
    let frame = 0;
    const onMove = (e: PointerEvent) => {
      if (frame) return;
      frame = requestAnimationFrame(() => {
        frame = 0;
        const s = side.getBoundingClientRect();
        side.style.setProperty("--gx", `${e.clientX - s.left + side.scrollLeft}px`);
        side.style.setProperty("--gy", `${e.clientY - s.top + side.scrollTop}px`);
      });
    };
    side.addEventListener("pointermove", onMove);
    return () => {
      side.removeEventListener("pointermove", onMove);
      cancelAnimationFrame(frame);
    };
  }, []);

  return { aside, highlight };
}

function SignOut() {
  const me = useMe().data;
  const signOut = useSignOut();
  const signInOff = useSignInOff();
  if (!me) return null;
  return (
    <div className="signed-in">
      <span className="signed-in-name" title={me.email}>
        {me.name}
      </span>
      {!signInOff && (
        <button type="button" className="btn btn-ghost btn-sm" onClick={() => void signOut()}>
          Sign out
        </button>
      )}
    </div>
  );
}

export function Layout() {
  const { pathname } = useLocation();
  const isAdmin = useMe().data?.role === "admin";
  const [collapsed, setCollapsed] = useState(readCollapsed);
  const { aside, highlight } = useNavHighlight(pathname, collapsed);
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
      <aside className="sidebar" ref={aside}>
        <span className="sidebar-glow" aria-hidden />
        <span className="nav-highlight" ref={highlight} aria-hidden />
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
          {isAdmin && <Item item={ADMIN} />}
          <SignOut />
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
        {/* No top search bar where a page has its own company picker (two searches that do
            different things confuse; "/" reaches the picker) or is not about one company. */}
        {!NO_SEARCH_BAR.has(pathname) && (
          <header className="topbar">
            <CompanySearch />
          </header>
        )}
        {/* Screens and their figures appear at once: motion is for what you click (the sliding
            tab highlight, switches), never for the data (owner's choice, 2026-10-17). */}
        <main className="content">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
