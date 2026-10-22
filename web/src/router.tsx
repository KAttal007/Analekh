import { lazy, Suspense, type ReactNode } from "react";
import { createBrowserRouter, Navigate } from "react-router-dom";
import { AdminLayout } from "./AdminLayout";
import { Layout } from "./Layout";
import { RequireSignIn } from "./components/RequireSignIn";
import { Loading } from "./components/ui";
import { loadCompanyPage } from "./lib/preload";
import { hasWelcomed } from "./lib/welcome";
import { Login } from "./pages/Login";
import { Placeholder } from "./pages/Placeholder";
import { SearchPage } from "./pages/SearchPage";
import { Welcome } from "./pages/Welcome";

// Heavy screens (AG Grid, ECharts) load on demand.
const Watchlist = lazy(() => import("./pages/Watchlist").then((m) => ({ default: m.Watchlist })));
const CompanyPage = lazy(() => loadCompanyPage().then((m) => ({ default: m.CompanyPage })));
const ChangeSetReview = lazy(() =>
  import("./pages/ChangeSetReview").then((m) => ({ default: m.ChangeSetReview })),
);
const AssumptionReview = lazy(() =>
  import("./pages/AssumptionReview").then((m) => ({ default: m.AssumptionReview })),
);
const Models = lazy(() => import("./pages/Models").then((m) => ({ default: m.Models })));
const Templates = lazy(() =>
  import("./pages/admin/Templates").then((m) => ({ default: m.Templates })),
);
const Users = lazy(() => import("./pages/admin/Users").then((m) => ({ default: m.Users })));
const AdminSettings = lazy(() =>
  import("./pages/admin/AdminSettings").then((m) => ({ default: m.AdminSettings })),
);
const Comps = lazy(() => import("./pages/Comps").then((m) => ({ default: m.Comps })));
const Settings = lazy(() => import("./pages/Settings").then((m) => ({ default: m.Settings })));
const Reports = lazy(() => import("./pages/Reports").then((m) => ({ default: m.Reports })));

const page = (el: ReactNode) => <Suspense fallback={<Loading />}>{el}</Suspense>;

// Opening Analekh at its home page greets the visitor first, once per browser session. A link to
// anything else (a company, a change set) goes straight there.
function Home() {
  return hasWelcomed() ? <SearchPage /> : <Navigate to="/welcome" replace />;
}

// Screens from design doc 19.1. Reports and Q&A land in Phase 4.
export const router = createBrowserRouter([
  { path: "/welcome", element: <Welcome /> },
  { path: "/login", element: <Login /> },
  {
    path: "/",
    element: <RequireSignIn />,
    children: [
      {
        element: <Layout />,
        children: [
          { index: true, element: <Home /> },
          { path: "watchlist", element: page(<Watchlist />) },
          { path: "companies/:symbol", element: page(<CompanyPage />) },
          { path: "change-sets/:id", element: page(<ChangeSetReview />) },
          { path: "models", element: page(<Models />) },
          { path: "models/:id/assumptions", element: page(<AssumptionReview />) },
          { path: "templates", element: <Navigate to="/admin/templates" replace /> },
          { path: "reports", element: page(<Reports />) },
          { path: "qa", element: <Placeholder title="Q&A" phase={4} /> },
          { path: "comps", element: page(<Comps />) },
          { path: "settings", element: page(<Settings />) },
        ],
      },
      {
        path: "admin",
        element: <AdminLayout />,
        children: [
          { index: true, element: <Navigate to="users" replace /> },
          { path: "users", element: page(<Users />) },
          { path: "templates", element: page(<Templates />) },
          { path: "settings", element: page(<AdminSettings />) },
        ],
      },
    ],
  },
]);
