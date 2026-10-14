"""Sector classification (design doc 4.2).

EQUITY_L.csv has no sector column. Sectors come from these sources, highest precedence first
(``companies.sector_source``):

1. ``user``: the analyst's own value (``data/sector_map.csv`` today, the company page later).
   A sector with no recorded source is treated as the user's.
2. ``excel_stocks``: an analyst's workbook converted with Excel's Stocks data type (LSEG
   industry groups), imported by ISIN. Licensed to the analyst for their own research.
3. ``nse_indices``: NSE Indices' published constituent lists (Nifty 500 + Microcap 250, about
   750 companies), whose Industry column becomes the sector.

A source never replaces a higher one; the same source refreshes its own values. The results
taxonomy is only set from strong signals (bank index membership, or an NSE sector naming banks,
NBFCs or insurance); otherwise it stays empty so the first parsed filing's schema reference
decides (ingest/pipeline.py). Excel Stocks sectors never set it: LSEG's "Banking Services" also
holds NBFCs.

Open question 28.4: companies outside the ~750 have no published sector yet.
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
# verify: file names on niftyindices.com (unreachable when this was written, 2026-10-13).
BROAD_LISTS = ("ind_nifty500list.csv", "ind_niftymicrocap250_list.csv")
BANK_LISTS = ("ind_niftybanklist.csv", "ind_niftypsubanklist.csv", "ind_niftyprivatebanklist.csv")

Mapping = dict[str, tuple[str, str | None]]

RANK = {"user": 3, "excel_stocks": 2, "nse_indices": 1}


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


def parse_constituents(data: bytes) -> Mapping:
    """Symbol -> (sector, None) from a constituent list.

    verify: columns are Company Name, Industry, Symbol, Series, ISIN Code; matched by name,
    ignoring case and spacing, so column order does not matter.
    """
    out: Mapping = {}
    for raw in csv.DictReader(io.StringIO(data.decode("utf-8-sig", errors="replace"))):
        row = {" ".join((k or "").split()).lower(): (v or "").strip() for k, v in raw.items()}
        symbol, industry = row.get("symbol", "").upper(), row.get("industry", "")
        if symbol and industry:
            out[symbol] = (industry, None)
    return out


def fetch_index_sectors(client: PoliteClient | None = None) -> tuple[Mapping, set[str], int]:
    """Download the published lists: (symbol -> sector, bank symbols, lists fetched).

    A list that fails to download is logged and skipped, so one renamed file does not stop the
    others."""
    client = client or PoliteClient()
    mapping: Mapping = {}
    banks: set[str] = set()
    fetched = 0
    for name in BROAD_LISTS + BANK_LISTS:
        try:
            rows = parse_constituents(client.get(INDEX_BASE + name).content)
        except Exception as exc:  # noqa: BLE001 - one missing list should not stop the rest
            log.warning("index_list_unavailable", list=name, error=str(exc))
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
    """Write sector/industry where the map knows the symbol, unless a higher source set it.

    Returns the number of companies whose sector changed. Sets results_taxonomy only on a
    strong signal (see module docstring)."""
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
        "lists_total": len(BROAD_LISTS + BANK_LISTS),
        "companies_listed": len(mapping),
        "banks": len(banks),
        "updated_curated": curated,
        "updated_from_lists": from_lists,
    }


def import_stocks_workbook(session: Session, path: Path) -> dict[str, int]:
    """Sectors from a workbook converted with Excel's Stocks data type, matched by ISIN.

    Needs a "Sector" column holding the cached field value and an "ISIN No" (or "ISIN")
    column; other columns are ignored. Formula errors and blanks are skipped."""
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
    mapping: Mapping = {c.nse_symbol: (by_isin[c.isin], None) for c in companies if c.isin}
    updated = apply_sectors(session, mapping, source="excel_stocks", set_taxonomy=False)
    return {
        "rows": total,
        "with_sector": len(by_isin),
        "matched": len(mapping),
        "updated": updated,
    }
