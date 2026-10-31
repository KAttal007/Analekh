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
export type CalendarEvent = Schemas["CalendarEventOut"];
export type CalendarKind = CalendarEvent["kind"];
export type Calendar = Schemas["CalendarOut"];
export type Me = Schemas["MeOut"];
export type PublicWelcome = Schemas["WelcomeOut"];
export type PublicEvent = Schemas["PublicEventOut"];
export type PublicCalendar = Schemas["PublicCalendarOut"];
export type AdminUserRow = Schemas["UserOut"];
export type NewUser = Schemas["UserIn"];
export type PasswordRule = { id: string; label: string; pattern: string };
export type PasswordRules = {
  rules: PasswordRule[];
  combined: string;
  max_length: number;
  min_length: number;
};
export type UserChange = Schemas["UserPatch"];
export type UploadLimit = Schemas["UploadLimitOut"];
export type ApiToken = Schemas["TokenOut"];
export type ApiTokenCreated = Schemas["TokenCreated"];
/** 409 from sign-in at the session limit (SessionLimitOut): pick a device to sign out of. */
export type SessionDevice = { device_id: string; name: string | null; label: string | null; signed_in_at: string; last_seen_at: string };
/** The device this browser just signed in on (ThisDeviceOut); `name` is the user's own. */
export type ThisDevice = { device_id: string; name: string | null; label: string | null };
export type LoginOut = Me & { device: ThisDevice };
export type SessionLimit = { detail: string; limit: number; choice_token: string; devices: SessionDevice[] };
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
export type LockOut = Schemas["LockOut"];
export type AdminLockOut = Schemas["AdminLockOut"];
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
export const STALE_API = "The API server is running older code than this page: restart it to load the new features.";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public retryAfter?: number,
    public blocked = false,
    public sessionLimit?: SessionLimit,
  ) {
    super(message);
  }
}

let signedOutHandler: (() => void) | null = null;
export const onSignedOut = (handler: (() => void) | null) => {
  signedOutHandler = handler;
};

const CSRF = { "X-Analekh-CSRF": "1" };
const isRead = (method?: string) => ["GET", "HEAD"].includes((method ?? "GET").toUpperCase());

async function call<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    ...(init.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
    ...(isRead(init.method) ? {} : CSRF),
  };
  const res = await fetch(BASE + path, { headers, credentials: "same-origin", ...init });
  if (!res.ok) {
    let detail = res.statusText;
    let blocked = false;
    let sessionLimit: SessionLimit | undefined;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
      blocked = body.blocked === true;
      if (res.status === 409 && typeof body.choice_token === "string") sessionLimit = body as SessionLimit;
    } catch {
      /* body is not JSON: keep the default detail */
    }
    if (res.status === 401 && !path.startsWith("/auth/login") && path !== "/auth/first-password") {
      signedOutHandler?.();
    }
    const wait = Number(res.headers.get("Retry-After"));
    if (res.status === 404 && detail === "Not Found") {
      throw new ApiError(404, STALE_API);
    }
    throw new ApiError(res.status, typeof detail === "string" ? detail : JSON.stringify(detail), Number.isFinite(wait) && wait > 0 ? wait : undefined, blocked, sessionLimit);
  }
  return res.status === 204 ? (undefined as T) : ((await res.json()) as T);
}

const post = <T>(path: string, body?: unknown) => call<T>(path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) });
const patch = <T>(path: string, body: unknown) => call<T>(path, { method: "PATCH", body: JSON.stringify(body) });
const put = <T>(path: string, body: unknown) => call<T>(path, { method: "PUT", body: JSON.stringify(body) });

async function download(path: string, body: unknown, filename: string): Promise<void> {
  const res = await fetch(BASE + path, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...CSRF },
    credentials: "same-origin",
    body: JSON.stringify(body),
  });
  if (res.status === 401) signedOutHandler?.();
  if (!res.ok) throw new ApiError(res.status, res.statusText);
  const url = URL.createObjectURL(await res.blob());
  const a = Object.assign(document.createElement("a"), { href: url, download: filename });
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export const api = {
  login: (email: string, password: string) => post<LoginOut>("/auth/login", { email, password }),
  replaceSession: (choiceToken: string, deviceId: string) => post<LoginOut>("/auth/login/replace", { choice_token: choiceToken, device_id: deviceId }),
  nameDevice: (name: string) => post<ThisDevice>("/auth/device-name", { name }),
  logout: () => post<void>("/auth/logout"),
  logoutEverywhere: () => post<void>("/auth/logout-everywhere"),
  me: () => call<Me>("/auth/me"),
  requestReset: (email: string) => post<{ detail: string }>("/auth/reset/request", { email }),
  confirmReset: (email: string, code: string, newPassword: string) => post<void>("/auth/reset/confirm", { email, code, new_password: newPassword }),
  passwordRules: () => call<PasswordRules>("/auth/password-rules"),
  firstPassword: (current: string, next: string) => post<void>("/auth/first-password", { current_password: current, new_password: next }),
  users: () => call<AdminUserRow[]>("/users"),
  createUser: (body: NewUser) => post<AdminUserRow>("/users", body),
  updateUser: (id: string, body: UserChange) => patch<AdminUserRow>(`/users/${id}`, body),
  sendFirstPassword: (id: string) => post<AdminUserRow>(`/users/${id}/send-first-password`),
  unblockUser: (id: string) => post<void>(`/users/${id}/unblock`),
  uploadLimit: () => call<UploadLimit>("/settings/upload-limit"),
  setUploadLimit: (bytes: number) => put<UploadLimit>("/settings/upload-limit", { bytes }),
  tokens: () => call<ApiToken[]>("/auth/tokens"),
  createToken: (name: string) => post<ApiTokenCreated>("/auth/tokens", { name }),
  revokeToken: (id: number) => call<void>(`/auth/tokens/${id}`, { method: "DELETE" }),
  publicAuthStatus: () => call<{ auth_enabled: boolean }>("/public/auth-status"),
  publicWelcome: () => call<PublicWelcome>("/public/welcome"),
  publicCalendar: (start: string, end: string) => call<PublicCalendar>(`/public/calendar?start=${start}&end=${end}&kind=results`),
  companyIndex: () => call<CompanyIndexEntry[]>("/companies/index"),
  search: (q: string, offset = 0, limit = 20) => call<SearchHit[]>(`/companies/search?q=${encodeURIComponent(q)}&limit=${limit}&offset=${offset}`),
  company: (symbol: string) => call<CompanyDetail>(`/companies/${symbol}`),
  filings: (symbol: string) => call<Filing[]>(`/companies/${symbol}/filings`),
  facts: (symbol: string, elements: string) => call<Fact[]>(`/companies/${symbol}/facts?elements=${encodeURIComponent(elements)}`),
  desk: (q: DeskQuery) => {
    const params = new URLSearchParams();
    for (const [k, v] of Object.entries(q)) if (v !== undefined && v !== "") params.set(k, String(v));
    return call<Desk>(`/desk?${params}`);
  },
  calendar: (start: string, end: string, watchlist: boolean) => call<Calendar>(`/calendar?start=${start}&end=${end}&watchlist=${watchlist}`),
  price: (symbol: string) => call<Price | null>(`/companies/${symbol}/price`),
  history: (symbol: string, consolidated: boolean, quarters = 12) => call<History>(`/companies/${symbol}/history?consolidated=${consolidated}&quarters=${quarters}`),
  historyXlsxUrl: (symbol: string, consolidated: boolean, quarters = 12) => `${BASE}/companies/${symbol}/history.xlsx?consolidated=${consolidated}&quarters=${quarters}`,
  jobsAvailable: () => call<Schemas["JobsAvailableOut"]>("/system/jobs"),
  glance: (symbol: string, consolidated: boolean) => call<Glance>(`/companies/${symbol}/glance?consolidated=${consolidated}`),
  logicalFacts: (symbol: string, logical: string, consolidated?: boolean) =>
    call<Fact[]>(`/companies/${symbol}/facts?logical=${encodeURIComponent(logical)}` + (consolidated === undefined ? "" : `&consolidated=${consolidated}`)),
  watchlist: () => call<WatchlistEntry[]>("/watchlist"),
  watch: (symbol: string) => post<CompanyDetail>("/watchlist", { symbol }),
  unwatch: (symbol: string) => call<void>(`/watchlist/${symbol}`, { method: "DELETE" }),
  analyse: (symbol: string) => post<Schemas["JobOut"]>(`/companies/${symbol}/analyse`),
  refresh: (symbol: string) => post<Schemas["JobOut"]>(`/companies/${symbol}/refresh`),
  startCoverage: (symbol: string, templateId?: number) => post<BuildOut>("/coverage", { symbol, template_id: templateId ?? null }),
  assumptions: (modelId: number) => call<Assumption[]>(`/models/${modelId}/assumptions`),
  decideAssumptions: (modelId: number, body: Schemas["AssumptionDecisions"]) => post<Assumption[]>(`/models/${modelId}/assumptions/decisions`, body),
  finalize: (modelId: number) => post<Record<string, unknown>>(`/models/${modelId}/finalize`),
  models: () => call<ModelOut[]>("/models"),
  syncModel: (modelId: number, filingId: number) => post<Schemas["JobOut"]>(`/models/${modelId}/sync`, { filing_id: filingId }),
  modelLock: (modelId: number) => call<LockOut | null>(`/models/${modelId}/lock`),
  adminReleaseLock: (modelId: number) => post<void>(`/admin/locks/${modelId}/release`),
  adminLocks: () => call<AdminLockOut[]>("/admin/locks"),
  meLocks: () => call<LockOut[]>("/me/locks"),
  releaseLock: (modelId: number) => post<void>(`/models/${modelId}/lock/release`),
  changeSet: (id: number) => call<ChangeSet>(`/change-sets/${id}`),
  decide: (id: number, body: Schemas["Decisions"]) => post<ChangeSet>(`/change-sets/${id}/decisions`, body),
  apply: (id: number) => post<Record<string, unknown>>(`/change-sets/${id}/apply`),
  templates: () => call<Template[]>("/templates"),
  uploadTemplate: (form: FormData) => call<Template>("/templates", { method: "POST", body: form }),
  testTemplate: (id: number, symbol: string) => post<Schemas["TemplateTestOut"]>(`/templates/${id}/test`, { symbol }),
  activateTemplate: (id: number) => post<Template>(`/templates/${id}/activate`),
  disableTemplate: (id: number) => post<Template>(`/templates/${id}/disable`),
  enableTemplate: (id: number) => post<Template>(`/templates/${id}/enable`),
  // Comps (design doc 18)
  peerLists: () => call<PeerList[]>("/peer-lists"),
  createPeerList: (name: string, symbols: string[]) => post<PeerList>("/peer-lists", { name, symbols }),
  updatePeerList: (id: number, body: { name?: string; symbols?: string[] }) => put<PeerList>(`/peer-lists/${id}`, body),
  deletePeerList: (id: number) => call<void>(`/peer-lists/${id}`, { method: "DELETE" }),
  peers: (symbol: string, limit = 8) => call<Peer[]>(`/companies/${symbol}/peers?limit=${limit}`),
  compsTable: (symbols: string[], consolidated: boolean | null) => post<CompsTable>("/comps/table", { symbols, consolidated }),
  compsXlsx: (symbols: string[], consolidated: boolean | null) => download("/comps", { symbols, consolidated }, "comps.xlsx"),
  status: () => call<Status>("/status"),
  alertChannels: () => call<AlertChannels>("/alerts/channels"),
  testAlert: (channel: "telegram" | "email") => post<AlertTest>("/alerts/test", { channel }),
  alerts: (limit = 20) => call<AlertEntry[]>(`/alerts?limit=${limit}`),
  ipoIssues: () => call<IpoIssueRow[]>("/ipo/issues"),
  ipoIssue: (id: number) => call<IpoDetail>(`/ipo/issues/${id}`),
  ipoCoverage: (id: number) => call<IpoDraft>(`/ipo/issues/${id}/coverage`),
  generateIpoCoverage: (id: number) => post<IpoDraft>(`/ipo/issues/${id}/coverage`),
  setIpoSymbol: (id: number, symbol: string) => post<{ id: number; symbol: string | null; company_id: number | null }>(`/ipo/issues/${id}/symbol`, { symbol }),
};

// IPO coverage (plan Task 8). The routes return plain dicts, so these are written by hand.
export type IpoStage = "rhp" | "prospectus";
export type IpoIssueRow = {
  id: number;
  name: string;
  stages: IpoStage[];
  current_stage: IpoStage | null;
  status: string;
  filed_on: string | null;
  company_symbol: string | null;
};
export type IpoFigure = {
  period_label: string;
  period_end: string;
  is_stub: boolean;
  line: string;
  amount: string;
  unit: string;
  page: number;
  flagged: boolean;
};
export type IpoRestatement = { basis: string; period_end: string; line: string; old: string; new: string };
export type IpoDetail = {
  id: number;
  name: string;
  current_stage: IpoStage | null;
  financials: { consolidated: IpoFigure[]; standalone: IpoFigure[] };
  restatements: IpoRestatement[];
  terms: Record<string, unknown> | null;
};
export type IpoSection = { key: string; text: string; blocked: boolean; unmatched: string[]; style_issues: string[] };
export type IpoDraft = {
  draft_id: number;
  stage: IpoStage | null;
  sections: Partial<Record<string, IpoSection>>;
  rating: string;
  rationale: string;
};
