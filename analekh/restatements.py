"""Revised results: which filing of a quarter is in use, what it replaced, what changed.

A company can file a quarter more than once on one basis: a revision correcting numbers, or the
quarter's own figures after results covering a half-year only (Canara Robeco AMC, March 2026).
Newest filed is in use (``ingest.pipeline.refresh_latest``); others kept as history. NSE's flag
("Original" / "Revision") stored when filing came from integrated-filing list; older rows labelled
by filing order (``infer_revision_flags``).
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from analekh.db.models import Company, Fact, Filing
from analekh.glance import AS_FRACTION, HUNDRED, LINES, Kind, change
from analekh.xbrl.elements import candidates
from analekh.xbrl.parser import period_type

Status = Literal["original", "revised", "refiled"]


@dataclass
class LineChange:
    label: str
    kind: Kind
    old: Decimal | None
    new: Decimal | None
    change: Decimal | None  # % for amounts and EPS; basis points for ratios


@dataclass
class Revision:
    status: Status
    replaces: datetime | None = None  # filing time of the filing this one replaced
    superseded_by: datetime | None = None  # filing time of the one that replaced this one
    changes: list[LineChange] = field(default_factory=list)  # headline lines that moved
    # Set when the replaced filing had no figures for the quarter itself (a half-year filing).
    replaced_period: tuple[date, date] | None = None


def _when(f: Filing) -> tuple:
    return (f.filed_at is not None, f.filed_at or datetime.min, f.id)


def _groups(filings: list[Filing]) -> list[list[Filing]]:
    """Results filings of one quarter on one basis, oldest filed first."""
    by: dict[tuple, list[Filing]] = {}
    for f in filings:
        if f.kind == "results_xbrl" and f.period_end is not None:
            by.setdefault((bool(f.consolidated), f.period_end), []).append(f)
    return [sorted(g, key=_when) for g in by.values()]


def _quarter_values(
    session: Session, filing_ids: list[int], taxonomy: str, end: date
) -> dict[int, dict[str, Decimal]]:
    """{filing id: {logical: value}} for the quarter ending ``end``, headline lines only."""
    names = [n for n, _, _ in LINES.get(taxonomy, LINES["indas"]) if not n.startswith("=")]
    order = {n: candidates(n, taxonomy) for n in names}
    elements = {e for c in order.values() for e in c}
    rows = session.scalars(
        select(Fact).where(
            Fact.filing_id.in_(filing_ids),
            Fact.element.in_(elements),
            Fact.dimensions == {},
            Fact.is_instant.is_(False),
            Fact.period_end == end,
        )
    )
    found: dict[int, dict[str, tuple[int, Decimal]]] = {}
    for f in rows:
        if f.value is None or period_type(f.period_start, f.period_end) != "Q":
            continue
        for name, cands in order.items():
            if f.element in cands:
                rank = cands.index(f.element)
                have = found.setdefault(f.filing_id, {}).get(name)
                if have is None or rank < have[0]:
                    value = f.value * HUNDRED if name in AS_FRACTION else f.value
                    found[f.filing_id][name] = (rank, value)
    return {fid: {n: v for n, (_, v) in vals.items()} for fid, vals in found.items()}


def _change(old: Decimal, new: Decimal, kind: Kind) -> Decimal | None:
    return change(new, old, kind)  # the same maths as the company page's QoQ / YoY


def revisions(session: Session, company: Company, filings: list[Filing]) -> dict[int, Revision]:
    """Revision status of each filing that shares its quarter and basis with another; filings
    alone in their quarter are left out (nothing to say)."""
    taxonomy = company.results_taxonomy or "indas"
    labels = {n: (label, kind) for n, label, kind in LINES.get(taxonomy, LINES["indas"])}
    out: dict[int, Revision] = {}
    for group in _groups(filings):
        if len(group) < 2:
            continue
        end = group[0].period_end
        if end is None:  # _groups keeps filings with a period end only
            raise ValueError(f"filing {group[0].id} has no period end")
        values = _quarter_values(session, [f.id for f in group], taxonomy, end)
        for i, f in enumerate(group):
            flag = (f.meta or {}).get("revision")
            if i == 0:
                status: Status = "original"
            elif flag == "Original":  # NSE lists it as a first filing: not a correction
                status = "refiled"
            else:
                status = "revised"
            rev = Revision(status=status)
            if i + 1 < len(group):
                rev.superseded_by = group[i + 1].filed_at
            if i > 0:
                prev = group[i - 1]
                rev.replaces = prev.filed_at
                old, new = values.get(prev.id, {}), values.get(f.id, {})
                if not old and prev.period_start and prev.period_start != f.period_start:
                    rev.replaced_period = (prev.period_start, end)
                for name, (label, kind) in labels.items():
                    a, b = old.get(name), new.get(name)
                    if a is None or b is None or a == b:
                        continue
                    rev.changes.append(LineChange(label, kind, a, b, _change(a, b, kind)))
            out[f.id] = rev
    return out


def infer_revision_flags(session: Session, company_id: int) -> int:
    """Label stored filings that predate NSE's flag being kept: the first filed of a quarter and
    basis is the original, later ones revisions (marked as inferred). Returns filings labelled."""
    filings = list(
        session.scalars(
            select(Filing).where(Filing.company_id == company_id, Filing.kind == "results_xbrl")
        )
    )
    labelled = 0
    for group in _groups(filings):
        for i, f in enumerate(group):
            if (f.meta or {}).get("revision"):
                continue
            f.meta = {
                **(f.meta or {}),
                "revision": "Original" if i == 0 else "Revision",
                "revision_inferred": True,
            }
            labelled += 1
    return labelled
