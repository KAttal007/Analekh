"""Validation rules V1-V11 (design doc 8.2).

Each rule returns RuleResult. Rule that cannot run because an element is not tagged returns
``skip``; nothing inferred. ``block`` failure stops auto-apply of filing's change set.
"""

import math
import statistics
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import date
from decimal import Decimal
from typing import Any, Literal

from analekh.xbrl.elements import candidates
from analekh.xbrl.parser import ParsedFact, ParsedFiling, period_type

Status = Literal["pass", "fail", "skip"]
Action = Literal["block", "flag", "warn", "highlight", "label", "info"]

RESULTS_DEADLINE_DAYS = 45
ANNUAL_RESULTS_DEADLINE_DAYS = 60
XBRL_GRACE_DAYS = 1
SWING_THRESHOLD = Decimal("0.5")
RELATIVE_TOLERANCE = Decimal("0.0005")


@dataclass(frozen=True)
class RuleResult:
    rule: str
    status: Status
    action: Action
    message: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class HistoryFact:
    """A latest fact already stored for this company and basis, from an earlier filing."""

    element: str
    period_start: date | None
    period_end: date
    value: Decimal
    filing_id: int


@dataclass(frozen=True)
class KpiValue:
    logical: str  # logical name from analekh.xbrl.elements, e.g. "revenue"
    period_end: date
    value: Decimal  # in full INR, same scale as XBRL


@dataclass
class ValidationContext:
    filing: ParsedFiling
    taxonomy: str = "indas"
    filed_at: date | None = None
    history: list[HistoryFact] = field(default_factory=list)
    kpis: list[KpiValue] = field(default_factory=list)
    # for V11.
    other_basis: list[HistoryFact] = field(default_factory=list)

    @property
    def period_end(self) -> date | None:
        """Declared reporting period wins over context dates (V6)."""
        if self.filing.declared_end:
            return self.filing.declared_end
        ends = [f.period_end for f in self.filing.facts if not f.is_instant]
        return max(ends) if ends else None

    def fact(self, logical: str, *, quarter: bool = True, instant: bool = False) -> ParsedFact | None:
        end = self.period_end
        for element in candidates(logical, self.taxonomy):
            for f in self.filing.facts:
                if f.element != element or f.dimensions or f.period_end != end:
                    continue
                if instant and f.is_instant:
                    return f
                if not instant and not f.is_instant:
                    is_q = period_type(f.period_start, f.period_end) == "Q"
                    if is_q == quarter:
                        return f
        return None


@dataclass
class ValidationReport:
    results: list[RuleResult]
    # V11's correction of the filing's rupee amounts (e.g. 100 when tagged 100 times too small),
    scale: Decimal | None = None
    filing: ParsedFiling | None = field(default=None, compare=False, repr=False)

    @property
    def blocks_auto_apply(self) -> bool:
        return any(r.status == "fail" and r.action == "block" for r in self.results)

    @property
    def failures(self) -> list[RuleResult]:
        return [r for r in self.results if r.status == "fail"]

    def as_dict(self) -> dict[str, Any]:
        return {
            "blocks_auto_apply": self.blocks_auto_apply,
            "results": [r.__dict__ | {"details": _jsonable(r.details)} for r in self.results],
        }


def tolerance(*facts: ParsedFact) -> Decimal:
    """Rounding allowance: half a unit of each term's stated precision, or 0.05% of the largest."""
    allowance = sum(
        (Decimal(10) ** (-f.decimals) / 2 for f in facts if f.decimals is not None),
        Decimal(0),
    )
    largest = max((abs(f.value) for f in facts), default=Decimal(0))
    return max(allowance, largest * RELATIVE_TOLERANCE, Decimal(1))


def _identity(
    rule: str,
    action: Action,
    label: str,
    lhs: list[ParsedFact | None],
    rhs: ParsedFact | None,
    signs: list[int] | None = None,
) -> RuleResult:
    if rhs is None or any(f is None for f in lhs):
        return RuleResult(rule, "skip", action, f"{label}: element not tagged")
    terms = [f for f in lhs if f is not None]
    signs = signs or [1] * len(terms)
    computed = sum((s * f.value for s, f in zip(signs, terms, strict=True)), Decimal(0))
    diff = computed - rhs.value
    tol = tolerance(*terms, rhs)
    details = {"computed": computed, "reported": rhs.value, "diff": diff, "tolerance": tol}
    if abs(diff) <= tol:
        return RuleResult(rule, "pass", action, label, details)
    return RuleResult(rule, "fail", action, f"{label}: off by {diff}", details)


def _with_optional(
    ctx: ValidationContext,
    required: list[tuple[str, int]],
    optional: list[tuple[str, int, str]],
) -> tuple[list[ParsedFact | None], list[int], str]:
    """Terms for an identity: required logical names, plus those optional ones the filing tags
    (a bank's provisions, an insurer's investment income). Returns facts, signs and the label's
    extra wording."""
    facts: list[ParsedFact | None] = [ctx.fact(name) for name, _ in required]
    signs = [sign for _, sign in required]
    words = ""
    for name, sign, label in optional:
        fact = ctx.fact(name)
        if fact is not None:
            facts.append(fact)
            signs.append(sign)
            words += f" {'+' if sign > 0 else '-'} {label}"
    return facts, signs, words


def v1_total_income(ctx: ValidationContext) -> RuleResult:
    facts, signs, words = _with_optional(
        ctx,
        [("revenue", 1), ("other_income", 1)],
        [
            ("investment_income", 1, "investment income"),  # insurers
            ("transfer_from_shareholders", 1, "transfer from shareholders"),  # life insurers
        ],
    )
    return _identity(
        "V1",
        "block",
        f"Revenue + other income{words} = total income",
        facts,
        ctx.fact("total_income"),
        signs,
    )


def v2_pbt(ctx: ValidationContext) -> RuleResult:
    if ctx.taxonomy == "life_insurance":
        return _identity(
            "V2",
            "block",
            "Shareholders' account income - expenses = PBT",
            [ctx.fact("shareholders_income"), ctx.fact("shareholders_expenses")],
            ctx.fact("pbt"),
            [1, -1],
        )
    facts, signs, words = _with_optional(
        ctx,
        [("total_income", 1), ("total_expenses", -1)],
        [
            ("provisions", -1, "provisions"),
            ("exceptional_items", 1, "exceptional items"),
            ("extraordinary_items", 1, "extraordinary items"),  # Ind-AS, tagged with its sign
            ("shareholders_investment_income", 1, "shareholders' investment income"),
            ("shareholders_other_income", 1, "shareholders' other income"),
            ("non_operating_expenses", -1, "non-operating expenses"),
            ("transfer_to_reserves", -1, "transfer to reserves"),  # reinsurers
        ],
    )
    return _identity(
        "V2",
        "block",
        f"Total income - total expenses{words} = PBT",
        facts,
        ctx.fact("pbt"),
        signs,
    )


def v3_pat(ctx: ValidationContext) -> RuleResult:
    pat = ctx.fact("pat_continuing") or ctx.fact("pat")
    return _identity("V3", "flag", "PBT - tax = PAT", [ctx.fact("pbt"), ctx.fact("tax")], pat, [1, -1])


def v4_balance_sheet(ctx: ValidationContext) -> RuleResult:
    assets = ctx.fact("total_assets", instant=True)
    eq_li = ctx.fact("equity_and_liabilities", instant=True)
    if eq_li is not None:
        return _identity("V4", "block", "Assets = equity + liabilities", [eq_li], assets)
    return _identity(
        "V4",
        "block",
        "Assets = equity + liabilities",
        [ctx.fact("total_equity", instant=True), ctx.fact("total_liabilities", instant=True)],
        assets,
    )


def v5_quarter_vs_ytd(ctx: ValidationContext) -> RuleResult:
    """Quarter = YTD - prior YTD of the same fiscal year, for revenue and PAT."""
    checked: list[dict[str, Any]] = []
    for logical in ("revenue", "pat"):
        q, ytd = ctx.fact(logical), ctx.fact(logical, quarter=False)
        if q is None or ytd is None or q.period_start is None or q.period_start == ytd.period_start:
            continue
        names = candidates(logical, ctx.taxonomy)
        prior = next(
            (h for h in ctx.history if h.element in names and h.period_start == ytd.period_start and q.period_start is not None and (q.period_start - h.period_end).days == 1),
            None,
        )
        if prior is None:
            continue
        derived = ytd.value - prior.value
        diff = derived - q.value
        ok = abs(diff) <= tolerance(q, ytd)
        checked.append({"logical": logical, "derived": derived, "reported": q.value, "diff": diff, "ok": ok})
    if not checked:
        return RuleResult("V5", "skip", "flag", "Quarter vs YTD: no prior YTD in history")
    bad = [c for c in checked if not c["ok"]]
    status: Status = "fail" if bad else "pass"
    return RuleResult("V5", status, "flag", "Quarter = YTD - prior YTD", {"checks": checked})


def v6_declared_period(ctx: ValidationContext) -> RuleResult:
    declared = ctx.filing.declared_end
    if declared is None:
        return RuleResult("V6", "skip", "warn", "No declared reporting period in filing")
    ends = sorted({f.period_end for f in ctx.filing.facts if not f.is_instant})
    if not ends or ends[-1] == declared:
        return RuleResult("V6", "pass", "warn", "Context dates agree with declared period")
    return RuleResult(
        "V6",
        "fail",
        "warn",
        f"Latest context end {ends[-1]} != declared {declared}; using declared",
        {"declared_end": declared, "context_end": ends[-1]},
    )


def v7_swing(ctx: ValidationContext) -> RuleResult:
    swings: list[dict[str, Any]] = []
    for logical in ("revenue", "pat"):
        q = ctx.fact(logical)
        if q is None or q.period_start is None:
            continue
        names = candidates(logical, ctx.taxonomy)
        prev = next(
            (h for h in ctx.history if h.element in names and h.period_start is not None and period_type(h.period_start, h.period_end) == "Q" and (q.period_start - h.period_end).days == 1),
            None,
        )
        if prev is None or prev.value == 0:
            continue
        change = (q.value - prev.value) / abs(prev.value)
        if abs(change) > SWING_THRESHOLD:
            swings.append({"logical": logical, "previous": prev.value, "current": q.value, "change": change})
    if swings:
        return RuleResult("V7", "fail", "highlight", "QoQ change above 50%", {"swings": swings})
    return RuleResult("V7", "pass", "highlight", "No QoQ swing above 50%")


def is_year_end(ctx: ValidationContext) -> bool:
    """The filing closes a financial year: a full-year duration ends on the period end, or the
    period ends on 31 March (the financial year under the Companies Act)."""
    end = ctx.period_end
    if end is None:
        return False
    if (end.month, end.day) == (3, 31):
        return True
    return any(f.period_end == end and period_type(f.period_start, f.period_end) == "FY" for f in ctx.filing.facts if not f.is_instant)


def v8_late_filing(ctx: ValidationContext) -> RuleResult:
    """Filed after SEBI's results deadline (LODR 33(3)): 45 days, or 60 for the year end."""
    end = ctx.period_end
    if ctx.filed_at is None or end is None:
        return RuleResult("V8", "skip", "label", "Filing date unknown")
    deadline = ANNUAL_RESULTS_DEADLINE_DAYS if is_year_end(ctx) else RESULTS_DEADLINE_DAYS
    lag = (ctx.filed_at - end).days
    details = {"lag_days": lag, "deadline_days": deadline}
    if lag > deadline + XBRL_GRACE_DAYS:
        return RuleResult(
            "V8",
            "fail",
            "label",
            f"Filed {lag} days after period end, past SEBI's {deadline}-day deadline (late)",
            details,
        )
    return RuleResult(
        "V8",
        "pass",
        "label",
        f"Filed {lag} days after period end, within SEBI's {deadline}-day deadline",
        details,
    )


def v9_restatement(ctx: ValidationContext) -> RuleResult:
    """Same period already stored from another filing with different values."""
    stored = {(h.element, h.period_start, h.period_end): h for h in ctx.history}
    diffs = []
    for f in ctx.filing.facts:
        if f.dimensions:
            continue
        h = stored.get((f.element, f.period_start, f.period_end))
        if h is not None and abs(h.value - f.value) > tolerance(f):
            diffs.append(
                {
                    "element": f.element,
                    "period_end": f.period_end,
                    "old": h.value,
                    "new": f.value,
                    "old_filing_id": h.filing_id,
                }
            )
    if diffs:
        return RuleResult("V9", "fail", "info", f"Restatement: {len(diffs)} values changed", {"diffs": diffs})
    return RuleResult("V9", "pass", "info", "No restated values")


def v10_kpi_conflict(ctx: ValidationContext) -> RuleResult:
    conflicts = []
    for k in ctx.kpis:
        for element in candidates(k.logical, ctx.taxonomy):
            f = ctx.filing.get(element, end=k.period_end)
            if f is not None and abs(f.value - k.value) > tolerance(f):
                conflicts.append({"logical": k.logical, "xbrl": f.value, "ai": k.value})
                break
    if not ctx.kpis:
        return RuleResult("V10", "skip", "flag", "No AI-extracted values to compare")
    if conflicts:
        return RuleResult(
            "V10",
            "fail",
            "flag",
            "AI value conflicts with XBRL; XBRL wins",
            {"conflicts": conflicts},
        )
    return RuleResult("V10", "pass", "flag", "AI values agree with XBRL")


# V11: amounts tagged in wrong unit. Filer entering lakh as rupees, or crore as lakh, files every
# rupee amount 100, 1,000, 1 lakh or 1 crore times off; statement still adds up, V1-V3 pass (Metro
# bad quarter can't move it). Both agree on same power of ten: amounts corrected (rule 5 holds:
SCALE_POWERS = range(2, 8)  # 100 to 1 crore
SCALE_SLACK = 0.3  # log10 distance from an exact power: within a factor of 2 either way
SCALE_MIN_BASE = Decimal(10_000_000)  # Rs 1 crore: below it, ratios of tiny figures are noise
SCALE_NEIGHBOURS = 4  # nearest other quarters compared (two each side when there are)
SCALE_MIN_NEIGHBOURS = 3
MONETARY_UNITS = frozenset({"INR"})


def _power(ratio: Decimal) -> int | None:
    """k when ratio is within SCALE_SLACK of 10**k for a unit-slip power, else None."""
    if ratio <= 0:
        return None
    lg = math.log10(float(ratio))
    k = round(lg)
    return k if abs(k) in SCALE_POWERS and abs(lg - k) <= SCALE_SLACK else None


def scaled_decimals(decimals: int | None, factor: Decimal) -> int | None:
    """The XBRL precision that goes with an amount multiplied by factor (a power of ten):
    Metro's crore figures read as lakh carried decimals -3 (Rs 1,000); times 100 they are
    precise to Rs 1 lakh, -5, as its correct standalone filing says."""
    if decimals is None or factor == 1:
        return decimals
    return decimals - round(math.log10(float(factor)))


def rescaled(filing: ParsedFiling, factor: Decimal) -> ParsedFiling:
    """The filing with its rupee amounts (and their precision) multiplied by factor; everything
    else as filed."""
    return replace(
        filing,
        facts=[replace(f, value=f.value * factor, decimals=scaled_decimals(f.decimals, factor)) if f.unit in MONETARY_UNITS else f for f in filing.facts],
    )


def _quarters(facts: list[HistoryFact], names: tuple[str, ...]) -> dict[date, Decimal]:
    """{period_end: value} for quarter-length facts of the first candidate element present."""
    out: dict[date, Decimal] = {}
    for name in names:
        for h in facts:
            if h.element == name and h.period_start is not None and period_type(h.period_start, h.period_end) == "Q":
                out.setdefault(h.period_end, h.value)
        if out:
            return out
    return out


def _typical(own: dict[date, Decimal], end: date) -> Decimal | None:
    """Median of the nearest other quarters within 400 days, when there are enough and it is
    large enough to compare against."""
    near = sorted((e for e in own if e != end), key=lambda e: abs((e - end).days))
    near = [e for e in near if abs((e - end).days) <= 400][:SCALE_NEIGHBOURS]
    if len(near) < SCALE_MIN_NEIGHBOURS:
        return None
    typical = statistics.median(own[e] for e in near)
    return typical if typical >= SCALE_MIN_BASE else None


def v11_scale(ctx: ValidationContext) -> tuple[RuleResult, Decimal | None]:
    """V11: amounts in the wrong unit. Returns the result and the correction factor, if any."""
    logical = "revenue" if ctx.fact("revenue") is not None else "total_income"
    q = ctx.fact(logical)
    if q is None or q.period_start is None or q.value <= 0:
        return RuleResult("V11", "skip", "block", "Unit check: no quarterly top line"), None
    names = candidates(logical, ctx.taxonomy)
    consolidated = ctx.filing.consolidated
    details: dict[str, Any] = {"line": logical, "value": q.value}

    k_basis = None
    other = _quarters(ctx.other_basis, names).get(q.period_end)
    if other is not None and other >= SCALE_MIN_BASE:
        ratio = q.value / other
        details["other_basis"] = {"value": other, "ratio": ratio}
        k = _power(ratio)
        if k is not None and ((consolidated is not False and k < 0) or (consolidated is False and k > 0)):
            k_basis = k

    k_hist = None
    typical = _typical(_quarters(ctx.history, names), q.period_end)
    if typical is not None:
        details["neighbours"] = {"median": typical}
        k_hist = _power(q.value / typical)
        if k_hist is None:
            return RuleResult("V11", "pass", "block", "Amounts in line with past quarters", details), None

    if k_hist is not None and other is not None and other >= SCALE_MIN_BASE and k_basis is None:
        lg = abs(math.log10(float(q.value / other)))
        other_typical = _typical(_quarters(ctx.other_basis, names), q.period_end)
        if other_typical is not None:
            details["other_basis"]["neighbours_median"] = other_typical
        if (
            lg > 1 - SCALE_SLACK
            and other_typical is not None
            and typical is not None
            and _power(other / other_typical) is None
            and _power(q.value / other) == k_hist
            and abs(math.log10(float(typical / other_typical))) <= 1 - SCALE_SLACK
        ):
            k_basis = k_hist
        elif lg <= 1 - SCALE_SLACK and other_typical is not None:
            k_other = _power(other / other_typical)
            if k_other is None:
                return RuleResult(
                    "V11",
                    "pass",
                    "block",
                    "A real change: the other basis reports the same quarter and is in line with its own past quarters",
                    details,
                ), None
            if k_other == k_hist:
                k_basis = k_hist  # both bases slipped together: corrected below

    if k_basis is not None and k_hist == k_basis:
        factor = Decimal(10) ** -k_basis
        size = f"{Decimal(10) ** abs(k_basis):,f}".split(".")[0]
        way = "small" if k_basis < 0 else "large"
        details |= {"status": "corrected", "factor": factor}
        return (
            RuleResult(
                "V11",
                "fail",
                "flag",
                f"Amounts tagged {size} times too {way}; corrected (other basis and past quarters agree)",
                details,
            ),
            factor,
        )
    k = k_hist if k_hist is not None else k_basis
    if k is not None:
        size = f"{Decimal(10) ** abs(k):,f}".split(".")[0]
        details |= {"status": "suspect", "power": k}
        return (
            RuleResult(
                "V11",
                "fail",
                "block",
                f"Amounts look about {size} times off the company's other figures; check the PDF",
                details,
            ),
            None,
        )
    return RuleResult("V11", "pass", "block", "No sign of amounts in the wrong unit", details), None


RULES: list[Callable[[ValidationContext], RuleResult]] = [
    v1_total_income,
    v2_pbt,
    v3_pat,
    v4_balance_sheet,
    v5_quarter_vs_ytd,
    v6_declared_period,
    v7_swing,
    v8_late_filing,
    v9_restatement,
    v10_kpi_conflict,
]


def validate(ctx: ValidationContext) -> ValidationReport:
    """V11 first: when it corrects the amounts, V1-V10 judge the corrected filing."""
    unit_check, factor = v11_scale(ctx)
    if factor is not None:
        ctx = replace(ctx, filing=rescaled(ctx.filing, factor))
    return ValidationReport([rule(ctx) for rule in RULES] + [unit_check], factor, ctx.filing)


def _jsonable(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_jsonable(v) for v in value]
    return value
