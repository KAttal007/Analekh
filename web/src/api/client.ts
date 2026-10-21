// Typed API client. Types come from the FastAPI OpenAPI schema (pnpm api-types), so the
// front end and back end cannot drift (design doc Appendix G.5).
import type { components } from "./schema";

export type Schemas = components["schemas"];
export type SearchHit = Schemas["SearchHitOut"];
export type CompanyIndexEntry = Schemas["CompanyIndexEntry"];
export type CompanyDetail = Schemas["CompanyDetail"];
export type WatchlistEntry = Schemas["WatchlistEntryOut"];
export type Filing = Schemas["FilingOut"];
export type Fact = Schemas["FactOut"];
export type Glance = Schemas["GlanceOut"];
export type Desk = Schemas["DeskOut"];
export type DeskRow = Schemas["DeskRowOut"];
export type Price = Schemas["PriceOut"];
// GET /calendar (hand-typed until `pnpm api-types` is next run against the API).
export type CalendarKind = "results" | "meeting" | "concall";
export type CalendarEvent = {
  date: string;
  kind: CalendarKind;
  symbol: string;
  name: string;
  sector: string | null;
  purpose: string | null;
  watched: boolean;
  source_url: string | null;
  status: "scheduled" | "filed";
};
export type Calendar = {
  start: string;
  end: string;
  events: CalendarEvent[];
  unscheduled: { symbol: string; name: string; sector: string | null }[];
};
export type DeskSort = "filed" | "market_cap";
export type DeskQuery = {
  quarter_end?: string;
  sector?: string;
  watchlist?: boolean;
  days?: number;
  sort?: DeskSort;
  limit?: number;
  offset?: number;
};
export type GlanceLine = Schemas["GlanceLineOut"];
export type Revision = Schemas["RevisionOut"];
export type ChangeSet = Schemas["ChangeSetOut"];
export type ChangeItem = Schemas["ChangeItemOut"];
export type Template = Schemas["TemplateOut"];
export type Assumption = Schemas["AssumptionOut"];
export type ModelOut = Schemas["ModelOut"];
export type BuildOut = Schemas["BuildOut"];
export type PeerList = Schemas["PeerListOut"];
export type Peer = Schemas["PeerOut"];
export type CompsTable = Schemas["CompsTableOut"];
export type CompRow = Schemas["CompRowOut"];
export type Status = Schemas["StatusOut"];
export type JobRun = Schemas["JobRunOut"];
export type AlertChannels = Schemas["AlertChannelsOut"];
export type AlertTest = Schemas["AlertTestOut"];
export type AlertEntry = Schemas["AlertOut"];
export type History = Schemas["HistoryOut"];
export type HistoryLine = Schemas["HistoryLineOut"];

const BASE = "/api";
export const STALE_API =
  "The API server is running older code than this page: restart it to load the new features.";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

async function call<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> =
    init.body instanceof FormData ? {} : { "Content-Type": "application/json" };
  const res = await fetch(BASE + path, { headers, ...init });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      detail = (await res.json()).detail ?? detail;
    } catch {
      /* not JSON */
    }
    // FastAPI's bare "Not Found" means the route doesn't exist: the API process is older than
    // this page. Analekh's own 404s always say what is missing ("peer list not found").
    if (res.status === 404 && detail === "Not Found") {
      throw new ApiError(404, STALE_API);
    }
    throw new ApiError(res.status, typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return res.status === 204 ? (undefined as T) : ((await res.json()) as T);
}

const post = <T>(path: string, body?: unknown) =>
  call<T>(path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) });
const put = <T>(path: string, body: unknown) =>
  call<T>(path, { method: "PUT", body: JSON.stringify(body) });

/** POST that answers with a file: saved by the browser under `filename`. */
async function download(path: string, body: unknown, filename: string): Promise<void> {
  const res = await fetch(BASE + path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new ApiError(res.status, res.statusText);
  const url = URL.createObjectURL(await res.blob());
  const a = Object.assign(document.createElement("a"), { href: url, download: filename });
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export const api = {
  companyIndex: () => call<CompanyIndexEntry[]>("/companies/index"),
  search: (q: string, offset = 0, limit = 20) =>
    call<SearchHit[]>(
      `/companies/search?q=${encodeURIComponent(q)}&limit=${limit}&offset=${offset}`,
    ),
  company: (symbol: string) => call<CompanyDetail>(`/companies/${symbol}`),
  filings: (symbol: string) => call<Filing[]>(`/companies/${symbol}/filings`),
  facts: (symbol: string, elements: string) =>
    call<Fact[]>(`/companies/${symbol}/facts?elements=${encodeURIComponent(elements)}`),
  desk: (q: DeskQuery) => {
    const params = new URLSearchParams();
    for (const [k, v] of Object.entries(q))
      if (v !== undefined && v !== "") params.set(k, String(v));
    return call<Desk>(`/desk?${params}`);
  },
  calendar: (start: string, end: string, watchlist: boolean) =>
    call<Calendar>(`/calendar?start=${start}&end=${end}&watchlist=${watchlist}`),
  // Latest close from NSE's bhavcopy (end of day); null before the first load.
  price: (symbol: string) => call<Price | null>(`/companies/${symbol}/price`),
  // Every stored quarter's P&L lines, oldest first; the chart and the history table share it.
  history: (symbol: string, consolidated: boolean, quarters = 12) =>
    call<History>(`/companies/${symbol}/history?consolidated=${consolidated}&quarters=${quarters}`),
  historyXlsxUrl: (symbol: string, consolidated: boolean, quarters = 12) =>
    `${BASE}/companies/${symbol}/history.xlsx?consolidated=${consolidated}&quarters=${quarters}`,
  // Whether Analyse and Refresh can be queued (the job queue comes with hosting).
  jobsAvailable: () => call<Schemas["JobsAvailableOut"]>("/system/jobs"),
  glance: (symbol: string, consolidated: boolean) =>
    call<Glance>(`/companies/${symbol}/glance?consolidated=${consolidated}`),
  // By logical name (e.g. "revenue"), resolved for the company's results format on the server.
  logicalFacts: (symbol: string, logical: string, consolidated?: boolean) =>
    call<Fact[]>(
      `/companies/${symbol}/facts?logical=${encodeURIComponent(logical)}` +
        (consolidated === undefined ? "" : `&consolidated=${consolidated}`),
    ),
  watchlist: () => call<WatchlistEntry[]>("/watchlist"),
  watch: (symbol: string) => post<CompanyDetail>("/watchlist", { symbol }),
  unwatch: (symbol: string) => call<void>(`/watchlist/${symbol}`, { method: "DELETE" }),
  analyse: (symbol: string) => post<Schemas["JobOut"]>(`/companies/${symbol}/analyse`),
  refresh: (symbol: string) => post<Schemas["JobOut"]>(`/companies/${symbol}/refresh`),
  startCoverage: (symbol: string, templateId?: number) =>
    post<BuildOut>("/coverage", { symbol, template_id: templateId ?? null }),
  assumptions: (modelId: number) => call<Assumption[]>(`/models/${modelId}/assumptions`),
  decideAssumptions: (modelId: number, body: Schemas["AssumptionDecisions"]) =>
    post<Assumption[]>(`/models/${modelId}/assumptions/decisions`, body),
  finalize: (modelId: number) => post<Record<string, unknown>>(`/models/${modelId}/finalize`),
  models: () => call<ModelOut[]>("/models"),
  changeSet: (id: number) => call<ChangeSet>(`/change-sets/${id}`),
  decide: (id: number, body: Schemas["Decisions"]) =>
    post<ChangeSet>(`/change-sets/${id}/decisions`, body),
  apply: (id: number) => post<Record<string, unknown>>(`/change-sets/${id}/apply`),
  templates: () => call<Template[]>("/templates"),
  uploadTemplate: (form: FormData) => call<Template>("/templates", { method: "POST", body: form }),
  testTemplate: (id: number, symbol: string) =>
    post<Schemas["TemplateTestOut"]>(`/templates/${id}/test`, { symbol }),
  activateTemplate: (id: number) => post<Template>(`/templates/${id}/activate`),
  // Comps (design doc 18)
  peerLists: () => call<PeerList[]>("/peer-lists"),
  createPeerList: (name: string, symbols: string[]) =>
    post<PeerList>("/peer-lists", { name, symbols }),
  updatePeerList: (id: number, body: { name?: string; symbols?: string[] }) =>
    put<PeerList>(`/peer-lists/${id}`, body),
  deletePeerList: (id: number) => call<void>(`/peer-lists/${id}`, { method: "DELETE" }),
  peers: (symbol: string, limit = 8) => call<Peer[]>(`/companies/${symbol}/peers?limit=${limit}`),
  compsTable: (symbols: string[], consolidated: boolean | null) =>
    post<CompsTable>("/comps/table", { symbols, consolidated }),
  compsXlsx: (symbols: string[], consolidated: boolean | null) =>
    download("/comps", { symbols, consolidated }, "comps.xlsx"),
  // Settings: what the scheduled jobs did, and the alert channels
  status: () => call<Status>("/status"),
  alertChannels: () => call<AlertChannels>("/alerts/channels"),
  testAlert: (channel: "telegram" | "email") => post<AlertTest>("/alerts/test", { channel }),
  alerts: (limit = 20) => call<AlertEntry[]>(`/alerts?limit=${limit}`),
};
