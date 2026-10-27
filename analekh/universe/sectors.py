"""Sector classification (design doc 4.2).

EQUITY_L.csv has no sector column. Sources, highest precedence first (``companies.sector_source``):

1. ``user``: analyst's own value (``data/sector_map.csv`` today, company page later). Sector with
   no recorded source counts as user's.
2. ``nse_indices``: NSE's own taxonomy (22 current NSE Indices sectors), from Industry column of
   NSE Indices' constituent lists. Eleven lists (Total Market, SME Emerge, IPO, ...) cover every
   indexed company: ~1,430 (2026-10-16). Owner chose NSE's taxonomy over LSEG's 2026-10-16.
3. ``excel_stocks``: analyst's workbook converted with Excel's Stocks data type (LSEG industry
   groups), imported by ISIN; shown only where NSE has no sector, always kept in
   ``companies.sector_lseg``. Licensed to analyst for own research.

A source never replaces a higher one; same source refreshes its own values. Results taxonomy set
only from strong signals (bank index membership, or NSE sector naming banks, NBFCs or insurance);
else empty, so first parsed filing's schema reference decides (ingest/pipeline.py). Excel Stocks
sectors never set it: LSEG's "Banking Services" also holds NBFCs.

Companies in no index have no published NSE sector; NSE's per-company classification (quote data)
refused an honest request 2026-10-16.
"""

import csv
import io
from pathlib import Path

import structlog
from openpyxl import load_workbook
from sqlalchemy import select
from sqlalchemy.orm import Session

from analekh.db.models import Company
from analekh.ingest.http import PoliteClient

log = structlog.get_logger()

SECTOR_MAP = Path(__file__).parent / "data" / "sector_map.csv"

INDEX_BASE = "https://niftyindices.com/IndexConstituent/"
# Smallest set of NSE Indices lists covering every indexed company (worked out from all 116 lists,
# 2026-10-16): Total Market (Nifty 500 + Microcap 250), SME Emerge, IPO, WAVES, seven small lists
# each adding a few. File names checked on niftyindices.com.
SECTOR_LISTS = (
    "ind_niftytotalmarket_list.csv",
    "ind_niftysmelist.csv",
    "ind_niftyipo_list.csv",
    "ind_niftywaves_list.csv",
    "ind_niftysugarethanol_list.csv",
    "ind_niftysmallcap500_list.csv",
    "ind_niftymedialist.csv",
    "ind_nifty500multifactormqvlv50_list.csv",
    "ind_niftyhousingfinance_list.csv",
    "ind_niftymidsmallindiaconsumption_list.csv",
)
# NSE Indices' current sectors (classification structure revised 2022). A few stale lists still
# carry the old names in capitals ("PHARMA", "CONSUMER GOODS"): those are ignored.
NSE_SECTORS = frozenset(
    {
        "Automobile and Auto Components",
        "Capital Goods",
        "Chemicals",
        "Construction",
        "Construction Materials",
        "Consumer Durables",
        "Consumer Services",
        "Diversified",
        "Fast Moving Consumer Goods",
        "Financial Services",
        "Forest Materials",
        "Healthcare",
        "Information Technology",
        "Media Entertainment & Publication",
        "Metals & Mining",
        "Oil Gas & Consumable Fuels",
        "Power",
        "Realty",
        "Services",
        "Telecommunication",
        "Textiles",
        "Utilities",
    }
)
BANK_LISTS = ("ind_niftybanklist.csv", "ind_niftypsubanklist.csv", "ind_nifty_privatebanklist.csv")

Mapping = dict[str, tuple[str, str | None]]

RANK = {"user": 3, "nse_indices": 2, "excel_stocks": 1}


def load_sector_map(path: Path = SECTOR_MAP) -> Mapping:
    if not path.exists():
        return {}
    with path.open(newline="", encoding="utf-8") as fh:
        return {
            row["symbol"].strip().upper(): (
                row["sector"].strip(),
                (row.get("industry") or "").strip() or None,
            )
            for row in csv.DictReader(fh)
            if row.get("symbol") and row.get("sector")
        }


def save_sector_map(mapping: Mapping, path: Path = SECTOR_MAP) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        out = csv.writer(fh)
        out.writerow(["symbol", "sector", "industry"])
        for symbol in sorted(mapping):
            sector, industry = mapping[symbol]
            out.writerow([symbol, sector, industry or ""])


def import_sector_worksheet(
    session: Session, path: Path, map_path: Path = SECTOR_MAP
) -> dict[str, int]:
    """The analyst's sectors from a worksheet (Symbol, Sector and Confirmed columns): rows
    confirmed with "Yes" and naming one of NSE's sectors are merged into the curated map and
    applied as the user's own, which no other source replaces. Nothing is downloaded."""
    ws = load_workbook(path, data_only=True, read_only=True).worksheets[0]
    rows = ws.iter_rows(values_only=True)
    header = [" ".join(str(h or "").split()).lower() for h in next(rows)]
    missing = {"symbol", "sector", "confirmed"} - set(header)
    if missing:
        raise ValueError(f"{path.name}: needs Symbol, Sector and Confirmed columns, found {header}")
    i_symbol, i_sector, i_ok = (header.index(c) for c in ("symbol", "sector", "confirmed"))
    confirmed: Mapping = {}
    counts = {"rows": 0, "confirmed": 0, "not_an_nse_sector": 0}
    for row in rows:
        symbol = str(row[i_symbol] or "").strip().upper()
        if not symbol:
            continue
        counts["rows"] += 1
        if str(row[i_ok] or "").strip().lower() != "yes":
            continue
        counts["confirmed"] += 1
        sector = str(row[i_sector] or "").strip()
        if sector not in NSE_SECTORS:
            counts["not_an_nse_sector"] += 1
            continue
        confirmed[symbol] = (sector, None)
    curated = load_sector_map(map_path) | confirmed
    save_sector_map(curated, map_path)
    counts["updated"] = apply_sectors(session, confirmed, source="user")
    return counts


def parse_constituents(data: bytes) -> Mapping:
    """Symbol -> (sector, None) from a constituent list.

    Columns: Company Name, Industry, Symbol, Series, ISIN Code (seen 2026-10-16); matched by name,
    ignoring case and spacing, so column order doesn't matter.
    """
    out: Mapping = {}
    for raw in csv.DictReader(io.StringIO(data.decode("utf-8-sig", errors="replace"))):
        row = {" ".join((k or "").split()).lower(): (v or "").strip() for k, v in raw.items()}
        symbol, industry = row.get("symbol", "").upper(), row.get("industry", "")
        if symbol and industry in NSE_SECTORS:  # old pre-2022 labels are left out
            out[symbol] = (industry, None)
    return out


def fetch_index_sectors(client: PoliteClient | None = None) -> tuple[Mapping, set[str], int]:
    """Download published lists: (symbol -> sector, bank symbols, lists fetched).

    List that fails to download is logged and skipped: one renamed file doesn't stop the others.
    """
    client = client or PoliteClient()
    mapping: Mapping = {}
    banks: set[str] = set()
    fetched = 0
    for name in SECTOR_LISTS + BANK_LISTS:
        try:
            rows = parse_constituents(client.get(INDEX_BASE + name).content)
        except Exception as exc:  # noqa: BLE001 - one missing list should not stop the rest
            log.warning("index_list_unavailable", list=name, error=str(exc))
            continue
        if not rows:  # a wrong name gets the site's HTML page with status 200, not a 404
            log.warning("index_list_unavailable", list=name, error="no rows (not a CSV?)")
            continue
        fetched += 1
        for symbol, value in rows.items():
            mapping.setdefault(symbol, value)
        if name in BANK_LISTS:
            banks |= rows.keys()
    return mapping, banks, fetched


def taxonomy_for_sector(sector: str | None, industry: str | None = None) -> str:
    """Initial guess; the first parsed filing's schema reference confirms it."""
    text = f"{sector or ''} {industry or ''}".lower()
    if "insurance" in text:
        return "life_insurance" if "life" in text else "insurance"
    if "nbfc" in text or "non banking" in text or "non-banking" in text:
        return "nbfc"
    if "bank" in text:
        return "banking"
    return "indas"


def _rank(company: Company) -> int:
    if company.sector is None:
        return 0
    return RANK.get(company.sector_source or "user", 0)


def apply_sectors(
    session: Session,
    mapping: Mapping | None = None,
    banks: set[str] | frozenset[str] = frozenset(),
    source: str = "user",
    set_taxonomy: bool = True,
) -> int:
    """Write sector/industry where map knows the symbol, unless a higher source set it.

    Returns number of companies whose sector changed. Sets results_taxonomy only on a strong signal
    (see module docstring).
    """
    mapping = load_sector_map() if mapping is None else mapping
    symbols = set(mapping) | set(banks)
    if not symbols:
        return 0
    n = 0
    for company in session.scalars(select(Company).where(Company.nse_symbol.in_(symbols))):
        if company.nse_symbol in mapping and RANK[source] >= _rank(company):
            value = mapping[company.nse_symbol]
            if (company.sector, company.industry) != value:
                n += 1
            company.sector, company.industry = value
            company.sector_source = source
        if set_taxonomy and company.results_taxonomy is None:
            if company.nse_symbol in banks:
                company.results_taxonomy = "banking"
            elif (guess := taxonomy_for_sector(company.sector, company.industry)) != "indas":
                company.results_taxonomy = guess
    return n


def refresh_sectors(session: Session, client: PoliteClient | None = None) -> dict[str, int]:
    """Curated overrides first, then the published index lists."""
    curated = apply_sectors(session)
    mapping, banks, fetched = fetch_index_sectors(client)
    from_lists = apply_sectors(session, mapping, banks, source="nse_indices")
    return {
        "lists_fetched": fetched,
        "lists_total": len(SECTOR_LISTS + BANK_LISTS),
        "companies_listed": len(mapping),
        "banks": len(banks),
        "updated_curated": curated,
        "updated_from_lists": from_lists,
    }


def import_stocks_workbook(session: Session, path: Path) -> dict[str, int]:
    """Sectors from workbook converted with Excel's Stocks data type, matched by ISIN.

    Needs "Sector" column (cached field value) and "ISIN No" (or "ISIN") column; others ignored.
    Formula errors and blanks skipped.
    """
    ws = load_workbook(path, data_only=True, read_only=True).worksheets[0]
    rows = ws.iter_rows(values_only=True)
    header = [" ".join(str(h or "").split()).lower() for h in next(rows)]
    if "sector" not in header or not ({"isin no", "isin"} & set(header)):
        raise ValueError(f"{path.name}: needs Sector and ISIN No columns, found {header}")
    i_sector = header.index("sector")
    i_isin = header.index("isin no" if "isin no" in header else "isin")
    by_isin: dict[str, str] = {}
    total = 0
    for row in rows:
        total += 1
        isin, sector = str(row[i_isin] or "").strip(), str(row[i_sector] or "").strip()
        if isin.startswith("IN") and sector and not sector.startswith("#"):
            by_isin[isin] = sector
    companies = session.scalars(select(Company).where(Company.isin.in_(by_isin))).all()
    for c in companies:  # kept whatever is shown: NSE's sector wins where it has one
        if c.isin:
            c.sector_lseg = by_isin[c.isin]
    mapping: Mapping = {c.nse_symbol: (by_isin[c.isin], None) for c in companies if c.isin}
    updated = apply_sectors(session, mapping, source="excel_stocks", set_taxonomy=False)
    return {
        "rows": total,
        "with_sector": len(by_isin),
        "matched": len(mapping),
        "updated": updated,
    }
