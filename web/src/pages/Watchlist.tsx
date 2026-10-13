import { useQuery } from "@tanstack/react-query";
import { AllCommunityModule, type ColDef, ModuleRegistry, themeQuartz } from "ag-grid-community";
import { AgGridReact } from "ag-grid-react";
import { Link } from "react-router-dom";
import { api, type WatchlistEntry } from "../api/client";
import { Badge, EmptyState, Loading, PageHeader } from "../components/ui";

ModuleRegistry.registerModules([AllCommunityModule]);

// AG Grid's Quartz theme, driven by the app's colour tokens so it follows light and dark mode.
const gridTheme = themeQuartz.withParams({
  fontFamily: "inherit",
  fontSize: 13,
  backgroundColor: "var(--surface)",
  foregroundColor: "var(--text)",
  headerBackgroundColor: "var(--surface-2)",
  headerTextColor: "var(--muted)",
  borderColor: "var(--border)",
  accentColor: "var(--accent)",
  rowHoverColor: "var(--surface-2)",
  wrapperBorderRadius: 8,
  spacing: 6,
});

const columns: ColDef<WatchlistEntry>[] = [
  {
    field: "symbol",
    width: 140,
    cellRenderer: (p: { value: string }) => <Link to={`/companies/${p.value}`}>{p.value}</Link>,
  },
  { field: "name", flex: 1, minWidth: 220 },
  { field: "last_filing", headerName: "Last filing", width: 140 },
  {
    field: "validation_blocked",
    headerName: "Validation",
    width: 130,
    cellRenderer: (p: { value: boolean }) =>
      p.value ? <Badge tone="error">blocked</Badge> : <Badge tone="ok">passed</Badge>,
  },
  {
    field: "pending_change_sets",
    headerName: "Pending change sets",
    width: 170,
    type: "rightAligned",
  },
];

export function Watchlist() {
  const { data = [], isLoading } = useQuery({ queryKey: ["watchlist"], queryFn: api.watchlist });
  return (
    <div className="page">
      <PageHeader
        title="Watchlist"
        badges={data.length > 0 && <Badge>{data.length}</Badge>}
        subtitle="Companies under deep coverage: new results are extracted, validated and turned into change sets for your models."
      />
      {isLoading ? (
        <Loading />
      ) : data.length === 0 ? (
        <EmptyState icon="star" title="Nothing on your watchlist yet">
          Search for a company above, open it, and press Watch. Its results are then collected and
          checked as soon as NSE publishes them.
        </EmptyState>
      ) : (
        <AgGridReact theme={gridTheme} rowData={data} columnDefs={columns} domLayout="autoHeight" />
      )}
    </div>
  );
}
