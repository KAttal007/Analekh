import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --- universe and coverage ------------------------------------------------------------------------


class CompanyIndexEntry(BaseModel):
    """One row of the in-browser search index (GET /companies/index)."""

    id: int
    nse_symbol: str
    name: str
    isin: str | None
    sector: str | None


class SearchHitOut(BaseModel):
    id: int
    nse_symbol: str
    name: str
    isin: str | None
    sector: str | None
    is_active: bool
    score: float


class CompanyOut(ORM):
    id: int
    nse_symbol: str
    isin: str | None
    name: str
    series: str | None
    listing_date: date | None
    face_value: Decimal | None
    sector: str | None
    industry: str | None
    results_taxonomy: str | None
    is_sme: bool
    is_active: bool
    refreshed_at: datetime | None


class CompanyDetail(CompanyOut):
    coverage_level: str  # universe | numbers | deep
    watched: bool


class WatchRequest(BaseModel):
    symbol: str
    settings: dict[str, Any] = Field(default_factory=dict)  # alerts, auto-analyse


class WatchlistEntryOut(BaseModel):
    symbol: str
    name: str
    added_at: datetime
    settings: dict[str, Any]
    last_filing: date | None
    validation_blocked: bool
    pending_change_sets: int
    # For watching day to day: the sector, the latest close and the latest quarter's growth, from
    # the same figures as the company page (glance.py).
    sector: str | None = None
    taxonomy: str = "indas"
    consolidated: bool | None = None
    price: Decimal | None = None
    change_pct: Decimal | None = None
    price_date: date | None = None
    market_cap: Decimal | None = None
    quarter_label: str | None = None
    revenue: Decimal | None = None
    revenue_yoy: Decimal | None = None
    pat: Decimal | None = None
    pat_yoy: Decimal | None = None


# --- filings, facts, KPIs -------------------------------------------------------------------------


class LineChangeOut(BaseModel):
    label: str
    kind: str  # inr, eps, pct
    old: Decimal | None
    new: Decimal | None
    change: Decimal | None  # % for amounts and EPS; basis points for ratios


class RevisionOut(BaseModel):
    """A quarter filed more than once on one basis: the newest filed is in use."""

    status: str  # original, revised, refiled
    replaces: datetime | None = None
    superseded_by: datetime | None = None
    changes: list[LineChangeOut] = []
    replaced_period: tuple[date, date] | None = None  # the replaced filing covered this instead


class FilingOut(ORM):
    id: int
    kind: str
    period_start: date | None
    period_end: date | None
    period_type: str | None
    consolidated: bool | None
    audited: bool | None
    source_url: str | None
    filed_at: datetime | None
    status: str
    meta: dict[str, Any]
    revision: RevisionOut | None = None  # only when the quarter was filed more than once


class DeskRowOut(BaseModel):
    symbol: str
    name: str
    sector: str | None
    taxonomy: str  # indas, banking, insurance, life_insurance: what "revenue" means for this row
    consolidated: bool
    filed_at: datetime | None
    revenue: Decimal | None
    revenue_yoy: Decimal | None  # % on the same quarter a year earlier
    pat: Decimal | None
    pat_yoy: Decimal | None
    ebitda_margin: Decimal | None  # %, Ind-AS only
    ebitda_margin_yoy: Decimal | None  # basis points
    blocked: bool  # a validation check blocks this filing
    yoy_note: str | None = None  # why the YoY columns are blank, for the dash's tooltip
    market_cap: Decimal | None = None  # rupees, at the latest stored close
    price_date: date | None = None


class SectorProgressOut(BaseModel):
    sector: str
    reported: int
    total: int
    median_revenue_yoy: Decimal | None
    median_pat_yoy: Decimal | None


class QuarterCountOut(BaseModel):
    quarter_end: date
    quarter_label: str
    reported: int


class CalendarEventOut(BaseModel):
    date: date
    kind: Literal["results", "meeting", "concall"]
    symbol: str
    name: str
    sector: str | None
    purpose: str | None
    watched: bool
    source_url: str | None
    status: Literal["scheduled", "filed"] = "scheduled"


class UnscheduledOut(BaseModel):
    symbol: str
    name: str
    sector: str | None


class CalendarOut(BaseModel):
    start: date
    end: date
    events: list[CalendarEventOut]
    # Watchlist companies with no results date announced in the window (a gap, not a mistake).
    unscheduled: list[UnscheduledOut]


class DeskOut(BaseModel):
    quarter_end: date | None
    quarter_label: str | None
    quarters: list[QuarterCountOut]
    companies_in_scope: int
    reported: int
    filings_total: int
    latest_filed_at: datetime | None
    rows: list[DeskRowOut]
    rows_total: int
    revenue_top: list[DeskRowOut]
    revenue_bottom: list[DeskRowOut]
    profit_top: list[DeskRowOut]
    profit_bottom: list[DeskRowOut]
    turned_profitable: list[DeskRowOut]
    turned_loss: list[DeskRowOut]
    sectors: list[SectorProgressOut]
    all_sectors: list[str] = []  # every sector in scope, for the filter


class PriceOut(BaseModel):
    """Latest closing price from NSE's bhavcopy: end of day, not live."""

    trade_date: date
    close: Decimal | None
    prev_close: Decimal | None
    change_pct: Decimal | None  # % on the previous close
    open: Decimal | None
    high: Decimal | None
    low: Decimal | None
    volume: int | None
    market_cap: Decimal | None  # rupees; None when no results filing gives the share count


class GlanceLineOut(BaseModel):
    key: str
    label: str
    kind: Literal["inr", "eps", "pct"]  # rupees, rupees per share, percent
    value: Decimal | None
    qoq: Decimal | None  # % change on the previous quarter; basis points for "pct"
    yoy: Decimal | None  # same, against the same quarter a year earlier
    note: str | None = None  # how a derived line is computed


class GlanceOut(BaseModel):
    consolidated: bool
    taxonomy: str
    period_start: date | None
    period_end: date | None
    quarter_label: str | None
    previous_end: date | None
    year_ago_end: date | None
    previous_note: str | None = None  # why QoQ is blank on every line
    year_ago_note: str | None = None  # why YoY is blank on every line
    revision: RevisionOut | None = None  # the quarter's figures come from a revised filing
    lines: list[GlanceLineOut]


class FactOut(ORM):
    id: int
    filing_id: int
    element: str
    period_start: date | None
    period_end: date
    is_instant: bool
    consolidated: bool
    value: Decimal | None
    unit: str | None
    context_ref: str | None


class KpiOut(ORM):
    id: int
    filing_id: int
    name: str
    value: Decimal | None
    unit: str | None
    period_end: date | None
    page: int | None
    quote: str | None
    confidence: Decimal | None
    verified: bool


class JobOut(BaseModel):
    job_id: str
    status: str
    result: Any = None


# --- templates, coverage, models ------------------------------------------------------------------


class TemplateOut(ORM):
    id: int
    owner: str
    name: str
    sectors: list[str]
    version: int
    status: str
    is_default: bool
    mapping: dict[str, Any] | None
    structure: dict[str, Any] | None
    created_at: datetime


class TemplateTestRequest(BaseModel):
    symbol: str


class TemplateTestOut(ORM):
    id: int
    template_id: int
    company_id: int
    result: str
    issues: dict[str, Any] | None


class CoverageRequest(BaseModel):
    symbol: str
    template_id: int | None = None  # default: the sector's default template


class AssumptionOut(ORM):
    id: int
    driver: str
    period: str | None
    proposed_value: Decimal | None
    rationale: str | None
    citations: dict[str, Any] | None
    decision: str
    final_value: Decimal | None


class AssumptionDecision(BaseModel):
    id: int
    decision: Literal["accepted", "edited", "skipped"]
    final_value: Decimal | None = None


class AssumptionDecisions(BaseModel):
    decisions: list[AssumptionDecision] = Field(default_factory=list)
    accept_all: bool = False


class ModelOut(ORM):
    id: int
    company_id: int
    template_id: int | None
    name: str
    origin: str
    doc_tag: uuid.UUID
    file_path: str | None
    last_seen: datetime | None


class BuildOut(BaseModel):
    model: ModelOut
    build_status: str
    filled_cells: int
    blank_rows: list[str]
    assumptions: list[AssumptionOut]


class WorkbookHintsIn(BaseModel):
    path: str
    tag_model_id: str | None = None
    tag_symbol: str | None = None
    text: list[str] = Field(default_factory=list)
    modified: float | None = None
    fingerprint: str | None = None


class DiscoverRequest(BaseModel):
    workbooks: list[WorkbookHintsIn]


class LinkRequest(BaseModel):
    symbol: str
    workbook: WorkbookHintsIn
    mapping: dict[str, Any] | None = None


# --- change sets ----------------------------------------------------------------------------------


class ChangeItemOut(ORM):
    id: int
    kind: str
    sheet: str | None
    cell: str | None
    old_value: str | None
    new_value: str | None
    formula_before: str | None
    formula_after: str | None
    rationale: str | None
    source_fact_id: int | None
    decision: str
    final_value: str | None


class ChangeSetOut(ORM):
    id: int
    model_id: int
    base_version: int
    filing_id: int | None
    status: str
    summary: dict[str, Any] | None
    items: list[ChangeItemOut]


class Decision(BaseModel):
    item_id: int
    decision: Literal["accepted", "edited", "skipped"]
    final_value: str | None = None


class Decisions(BaseModel):
    decisions: list[Decision] = Field(default_factory=list)
    accept_kinds: list[str] = Field(default_factory=list)  # bulk accept per kind (16.4)


class SyncRequest(BaseModel):
    filing_id: int


# --- outputs --------------------------------------------------------------------------------------


class ReportRequest(BaseModel):
    symbol: str
    kind: Literal["flash", "digest", "red_flags", "note", "initiation"]
    period_end: date
    model_id: int | None = None


class QaRequest(BaseModel):
    symbol: str
    question: str


class CompsRequest(BaseModel):
    symbols: list[str] = Field(default_factory=list)
    peer_list: str | None = None
    # One basis for every company; None picks per company (consolidated when it has four
    # consolidated quarters, else standalone) and the export's Basis column shows which.
    consolidated: bool | None = None


# --- comps (design doc 18) ------------------------------------------------------------------------


class PeerListIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    symbols: list[str] = Field(default_factory=list, max_length=30)


class PeerListUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    symbols: list[str] | None = Field(default=None, max_length=30)


class PeerListOut(ORM):
    id: int
    name: str
    symbols: list[str]


class PeerOut(BaseModel):
    symbol: str
    name: str
    sector: str | None
    market_cap: Decimal | None


class CompRowOut(BaseModel):
    symbol: str
    name: str
    sector: str | None
    taxonomy: str
    consolidated: bool | None  # the basis the row's figures were looked up on
    price: Decimal | None
    price_date: date | None
    market_cap: Decimal | None
    ttm_revenue: Decimal | None  # last four back-to-back quarters
    ttm_ebitda: Decimal | None  # Ind-AS, non-financial companies only
    ttm_pat: Decimal | None
    revenue_yoy: Decimal | None  # latest quarter on a year earlier, %
    ebitda_margin: Decimal | None  # TTM, %
    pat_margin: Decimal | None
    pe: Decimal | None
    pb: Decimal | None
    book_value: Decimal | None
    book_value_at: date | None
    ev: Decimal | None  # None until balance-sheet debt and cash are sourced
    ev_ebitda: Decimal | None
    quarter_end: date | None
    quarter_label: str | None
    notes: list[str]


class CompStatOut(BaseModel):
    median: Decimal | None
    mean: Decimal | None


class CompsTableOut(BaseModel):
    rows: list[CompRowOut]
    stats: dict[str, CompStatOut]
    missing: list[str]  # symbols not in the universe (delisted or renamed since the list was saved)
    as_of: date | None  # the latest close in the table


# --- system: data status and alerts (Settings) --------------------------------------------------


class JobRunOut(BaseModel):
    last_run_at: datetime | None = None
    last_status: str | None = None  # ok, skipped, error
    last_summary: dict[str, Any] = Field(default_factory=dict)
    last_ok_at: datetime | None = None
    last_ok_summary: dict[str, Any] | None = None


class SeasonOut(BaseModel):
    quarter_end: date
    quarter_label: str
    opens: date
    closes: date


class WatcherStatusOut(BaseModel):
    run: JobRunOut
    in_season: bool
    season: SeasonOut | None  # the season under way
    next_season: SeasonOut | None  # outside a season: when the next one opens
    schedule: str
    next_ask_at: datetime
    # No run recorded since the last scheduled start: the scheduler is off or the machine slept.
    missed_start_at: datetime | None


class PricesStatusOut(BaseModel):
    run: JobRunOut
    latest_day: date | None
    expected_day: date  # the latest trading day whose file should exist (holidays have none)
    priced: int
    with_market_cap: int


class DataCountsOut(BaseModel):
    companies: int
    with_sector: int
    with_results: int
    filings: int
    values_estimate: int  # stored XBRL values, from the planner's row estimate
    latest_filed_at: datetime | None
    database_bytes: int | None


class StatusOut(BaseModel):
    version: str
    checked_at: datetime
    watcher: WatcherStatusOut
    prices: PricesStatusOut
    data: DataCountsOut
    ai_configured: bool  # an Anthropic API key is set (never the key itself)


class AlertChannelsOut(BaseModel):
    telegram: bool
    email: bool
    email_to: str | None  # masked: k•••@gmail.com


class AlertTestIn(BaseModel):
    channel: Literal["telegram", "email"]


class AlertTestOut(BaseModel):
    ok: bool
    detail: str


class AlertOut(BaseModel):
    id: int
    kind: str | None
    symbol: str | None
    text: str | None
    channel: str | None  # telegram, email, or none (not delivered)
    sent_at: datetime | None


# --- results history and the job queue ------------------------------------------------------------


class HistoryLineOut(BaseModel):
    key: str
    label: str
    kind: Literal["inr", "eps", "pct"]
    values: list[Decimal | None]  # one per quarter, oldest first
    note: str | None = None


class HistoryOut(BaseModel):
    consolidated: bool
    taxonomy: str
    quarter_ends: list[date]
    quarter_labels: list[str]
    lines: list[HistoryLineOut]


class JobsAvailableOut(BaseModel):
    available: bool
    detail: str | None = None
