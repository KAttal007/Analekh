"""Reads NIM, cost of funds, cost of deposits and yields from a lender's investor presentation.

No LLM: sentence, table, chart, KPI-card and combo-chart layers over the PDF's text and drawings.
Rules baked in:
- Only single quarters are kept. Half-year (H1/H2), 9M, cumulative, YTD and full-year columns are
  rejected, never averaged or stored.
- Quarter labels in any notation resolve to a quarter-end date (Indian fiscal year, April to March).
- Metric: 'Net Interest Margin' or 'NIM'. Risk adjusted, core, excluding, forecasts: rejected.
"""

import re
from calendar import monthrange
from datetime import date
from pathlib import Path
from typing import Any

import pdfplumber
import pymupdf

from analekh.decks import entities as ENTITY

# ---------------------------------------------------------------- quarter labels
NON_QUARTER = re.compile(
    r"\bcumulative\b|\bytd\b|year[\s-]*to[\s-]*date|\bhalf[\s-]*year|\bsix\s+months|\bnine\s+months|"
    r"\b(?:h[12]|[12]h)\s*[-'\s]*(?:fy)?\s*\d{2,4}|\b[369]m\s*[-'\s]*(?:fy)?\s*\d{2,4}|\bh[12]\b|"
    r"\bfull[\s-]*year\b|\bannual\b|\byear\s+ended\b|\bhy\s*[12]\b|\b[12]\s*hy\b|\bh[12]\s*fy|"
    r"\bas\s+(?:on|of|at)\b|\bactuals?\b|\bguidance\b|\boutlook\b|\btarget\b|"  # point-in-time or forward-looking, not a quarter
    r"\byearly\b|\byear[\s-]*wise\b|\(\s*[369]\s*m\s*\)",  # 'Key business ratios – yearly trends', '(6 M)'
    re.I,
)
YEAR = r"(\d{4}\s*-\s*\d{2,4}|\d{2,4})"
FQ_A = re.compile(r"\b([1-4])\s*q\s*[-'\s]*(?:fy)?\s*[-'\s]*" + YEAR, re.I)  # 2QFY27, 2Q27
FQ_B = re.compile(r"\bq\s*([1-4])\s*[-'\s]*(?:fy)?\s*[-'\s]*" + YEAR, re.I)  # Q2FY27, Q2 FY27, Q2-2027, Q2 26-27
MONTH_Y = re.compile(r"\b(mar|jun|sep|sept|dec)[a-z]*\.?\s*[-'/\s]?\s*(\d{4}|\d{2})\b", re.I)  # Sep'26, Sep-26, September 2026
DMY = re.compile(r"\b(30|31)\s*[./-]\s*(03|06|09|12|3|6|9)\s*[./-]\s*(\d{4}|\d{2})\b")
MONTH_NUM = {"mar": 3, "jun": 6, "sep": 9, "sept": 9, "dec": 12}
FY_QUARTER_END = {1: (6, -1), 2: (9, -1), 3: (12, -1), 4: (3, 0)}  # (month, year offset from the FY end year)


def _year(raw: str) -> int | None:
    raw = raw.replace(" ", "")
    if "-" in raw:  # 2026-27 -> fiscal year ending 2027
        raw = raw.split("-")[1]
    y = int(raw)
    y = 2000 + y if y < 100 else y
    return y if 2015 <= y <= 2029 else None


def _qend(year: int, month: int) -> date:
    return date(year, month, monthrange(year, month)[1])


MDY = re.compile(r"\b(mar|jun|sep|sept|dec)[a-z]*\.?\s*(30|31)(?:st|th)?,?\s+(\d{4})\b", re.I)  # September 30, 2026
FY_FIRST = re.compile(r"\bfy\s*'?\s*(\d{4}\s*-\s*\d{2,4}|\d{2,4})\s*[-'\s]*q\s*([1-4])\b", re.I)
BARE_Q = re.compile(r"\b(?:q\s*([1-4])|([1-4])\s*q)\b", re.I)  # 'Q2' with no year: needs the deck's fiscal year
CONTEXT_FY: int | None = None  # the deck's fiscal year (end year), set per deck by run()
COVERAGE_FROM = date(2022, 6, 30)  # FY23 Q1: the first quarter we show
DECK_Q: date | None = None  # the deck's quarter (most common label on its first pages), set per deck by run()


def parse_period(text: str, fy_hint: int | None = None) -> tuple[str, date | None]:
    """('Q', quarter_end) for one quarter, ('other', None) for half-year/cumulative/annual, ('none', None).
    A bare 'Q2' resolves only with the deck's fiscal year (fy_hint or CONTEXT_FY); without one it is 'none'."""
    t = re.sub(r"\s+", " ", (text or "").replace("\n", " ").replace("’", "'").replace("‘", "'").replace("`", "'")).strip()
    if NON_QUARTER.search(t):
        return "other", None
    for pat in (FQ_B, FQ_A):
        m = pat.search(t)
        if m:
            fy = _year(m.group(2))
            if fy:
                month, off = FY_QUARTER_END[int(m.group(1))]
                return "Q", _qend(fy + off, month)
    m = MDY.search(t)
    if m:
        y = _year(m.group(3))
        if y:
            return "Q", _qend(y, MONTH_NUM[m.group(1).lower()])
    for m in MONTH_Y.finditer(t):  # first match with a valid year: 'Sep 30, 2026' must not read 30 as the year
        y = _year(m.group(2))
        if y:
            return "Q", _qend(y, MONTH_NUM[m.group(1).lower()])
    m = DMY.search(t)
    if m:
        y = _year(m.group(3))
        if y:
            return "Q", _qend(y, int(m.group(2)))
    m = FY_FIRST.search(t)  # 'FY27 Q2', 'FY 2026-27 Q2'
    if m:
        fy = _year(m.group(1))
        if fy:
            month, off = FY_QUARTER_END[int(m.group(2))]
            return "Q", _qend(fy + off, month)
    fy = fy_hint or CONTEXT_FY
    m = BARE_Q.search(t)
    if m and re.search(r"\b(?:19|20)\d{2}\b|\b\d{2}\b", t):
        return "none", None  # a year-like number sits beside the bare quarter: never guess the deck's year over it
    if m and fy:
        month, off = FY_QUARTER_END[int(m.group(1) or m.group(2))]
        return "Q", _qend(fy + off, month)
    return "none", None


def deck_context(texts: list[str]) -> tuple[int | None, date | None]:
    """The deck's fiscal year and quarter: the most common full quarter label on its first pages."""
    from collections import Counter

    qs: Counter = Counter()
    for t in texts:
        for pat in (FQ_B, FQ_A):
            for m in pat.finditer(t):
                kind, qe = parse_period(m.group(0), fy_hint=None)
                if kind == "Q":
                    qs[qe] += 1
    if not qs:
        return None, None
    qe = qs.most_common(1)[0][0]
    return (qe.year + 1 if qe.month > 3 else qe.year), qe


# ---------------------------------------------------------------- metric label
METRIC = re.compile(r"\bnet\s+interest\s+margin|\bnim\b", re.I)
BAD_METRIC = re.compile(r"risk[\s-]*adjust|adjusted|\bcore\b|\breal\b|\bexcl|\bex-|dilut|\bimpact\b|spread|\bnii\b", re.I)
FORECAST = re.compile(r"estimate|guidance|expected|expects|outlook|target|project|forecast|\bby\s+(?:q[1-4]\s*)?fy\s*2?[89]\b", re.I)
VALUE = r"(\d{1,2}\.\d{1,2})"
LOW, HIGH = 1.0, 25.0  # MFIs and small-ticket lenders run NIMs of 15 to 25%
TERMS: tuple[str, ...] = ("Net Interest Margin", "NIM")

# One entry per metric: label rule, what disqualifies a label, sanity range in %, chart/card search terms.
_ADJ = r"risk[\s-]*adjust|adjusted|\bcore\b|\breal\b|\bexcl|\bex-|dilut|\bimpact\b|incremental|marginal|\bmclr\b|\beblr\b"
METRICS = {
    "nim": (r"\bnet\s+interest\s+margin|\bnim\b", _ADJ + r"|spread|\bnii\b", 1.0, 25.0, ("Net Interest Margin", "NIM")),
    "cof": (r"\bcost\s+of\s+funds\b|\bcof\b", _ADJ, 2.0, 12.0, ("Cost of Funds", "CoF")),
    "cod": (r"\bcost\s+of\s+deposits?\b|\bcod\b", _ADJ + r"|term\s+deposit|\bsaving|\bcasa\b", 2.0, 12.0, ("Cost of Deposits", "Cost of Deposit", "CoD")),
    "yield_adv": (
        r"\byield\s+on\s+(?:net\s+|gross\s+|average\s+)?(?:advances|loans)\b|\byoa\b",
        _ADJ + r"|investment",
        4.0,
        25.0,
        ("Yield on Advances", "Yield on Net Advances", "Yield on Loans", "YoA"),
    ),
    "yield_assets": (
        r"\byield\s+on\s+(?:average\s+)?(?:interest[\s-]+earning\s+)?assets\b",
        _ADJ + r"|investment",
        4.0,
        25.0,
        ("Yield on Assets", "Yield on average assets", "Yield on Advances and Assets"),
    ),
    "yield_funds": (r"\byield\s+on\s+funds\b", _ADJ, 4.0, 25.0, ("Yield on Funds",)),
}


def use_metric(name: str) -> None:
    """Point every layer at one metric (prototype: module-level settings, one metric at a time)."""
    global METRIC, BAD_METRIC, LOW, HIGH, TERMS
    pat, bad, LOW, HIGH, TERMS = METRICS[name]
    METRIC, BAD_METRIC = re.compile(pat, re.I), re.compile(bad, re.I)


def basis_of(text: str) -> str:
    t = text.lower()
    if re.search(r"\bportfolio\b|\bsegment\b", t):
        return "segment"  # 'Yield on Advances of EH portfolio': a segment's figure, not the company's
    q = re.search(r"\(([^)]*\b(?:basis|method|methodology)\b[^)]*)\)", t)
    if q:
        return q.group(1).strip()  # 'NIM (On Opening and Closing Average basis)': a method of its own
    for key, name in (("domestic", "domestic"), ("whole bank", "whole bank"), ("overall", "whole bank"), ("global", "global"), ("standalone", "standalone"), ("consolidated", "consolidated")):
        if key in t:
            return name
    return "unspecified"


def accept_metric(text: str) -> bool:
    return bool(METRIC.search(text)) and not BAD_METRIC.search(text)


def in_range(v: float) -> bool:
    return LOW <= v <= HIGH


# ---------------------------------------------------------------- sentence layer
def sentence_layer(page_text: str, page_no: int, page_q: date | None = None) -> list[dict]:
    out: list[dict] = []
    for line in page_text.splitlines():
        before = len(out)
        out += _sentence_line(line, page_no)
        if len(out) > before or not page_q:
            continue
        # No quarter in the sentence ('NIM 6.5%, up 35bps YoY', 'NIM had improved to 3.87%'): the value
        # follows the metric directly, its clause (up to '|' or ';') names no period, and the page title
        # names exactly one quarter: that quarter.
        for m in METRIC.finditer(line):
            if not accept_metric(line[max(0, m.start() - 22) : m.end() + 14]):
                continue
            clause = re.split(r"[|;]", line[m.start() :])[0]
            vm = re.match(r"^[^\d|;%]{0,25}?" + VALUE + r"\s*%", clause[len(m.group(0)) :])
            if not vm or not in_range(float(vm.group(1))):
                continue
            if parse_period(clause)[0] != "none" or re.search(r"\bvs\.?\b|\bv/s\b|\bfrom\b|\bagainst\b|compared", clause[: len(m.group(0)) + vm.end()], re.I):
                continue
            f = _find(page_q, float(vm.group(1)), "sentence(page quarter)", page_no, clause)
            f["flags"].append("quarter from page title")
            out.append(f)
            break
    return out


def page_quarter(page) -> date | None:
    """The one quarter named in the top fifth of the page (the slide title), else None."""
    words = page.get_text("words")
    top = " ".join(w[4] for w in words if w[1] < page.rect.height * 0.22)
    if NON_QUARTER.search(top):
        return None  # 'H1FY27', 'yearly' in the title: the slide is not about one quarter
    qs = {parse_period(m.group(0))[1] for pat in (FQ_B, FQ_A) for m in pat.finditer(top) if parse_period(m.group(0))[0] == "Q"}
    return next(iter(qs)) if len(qs) == 1 else None


def _sentence_line(line: str, page_no: int) -> list[dict]:
    out: list[dict] = []
    if True:
        if not METRIC.search(line):
            return out
        # a metric mention that is itself risk adjusted / core / impact is dropped as a whole
        mentions = [m for m in METRIC.finditer(line)]
        ok_mentions = [m for m in mentions if accept_metric(line[max(0, m.start() - 22) : m.end() + 14])]
        if not ok_mentions:
            return out
        first = ok_mentions[0].start()
        text = line[first:]
        # 'NIM up from 7.6% to 8.9% (Q2FY26 to Q2FY27)': each value takes its own quarter, in order
        ft = re.search(r"from\s+" + VALUE + r"\s*%\s+to\s+" + VALUE + r"\s*%\s*\(\s*([^()]+?)\s+to\s+([^()]+?)\s*\)", text, re.I)
        if ft:
            (k1, q1), (k2, q2) = parse_period(ft.group(3)), parse_period(ft.group(4))
            if k1 == k2 == "Q" and in_range(float(ft.group(1))) and in_range(float(ft.group(2))):
                return [_find(q1, float(ft.group(1)), "sentence", page_no, ft.group(0)), _find(q2, float(ft.group(2)), "sentence", page_no, ft.group(0))]
        values = [(m.start(), m.end(), float(m.group(1))) for m in re.finditer(VALUE + r"\s*%", text)]
        # "<value>% for/in/during <quarter>"
        for start, end, v in values:
            tail = text[end : end + 40]
            m = re.match(r"\s*(?:\([^)]*\)\s*)?(?:for|in|during|at|of)\s+(?:the\s+)?(?:quarter\s+)?(?P<q>[^,;.]{2,18})", tail, re.I)
            kind, qe = parse_period(m.group("q")) if m else ("none", None)
            around = text[max(0, start - 30) : end + 60]
            if kind == "Q" and in_range(v):
                out.append(_find(qe, v, "sentence", page_no, around))
        if out:
            return out
        # "<quarter> ... <value>%": quarter first, no other value between
        for qm in list(FQ_B.finditer(text)) + list(FQ_A.finditer(text)):
            kind, qe = parse_period(qm.group(0))
            if kind != "Q":
                continue
            after = text[qm.end() : qm.end() + 45]
            vm = re.search(VALUE + r"\s*%", after)
            if vm and in_range(float(vm.group(1))) and not re.search(r"\d\s*%", after[: vm.start()]):
                around = text[max(0, qm.start() - 20) : qm.end() + 60]
                out.append(_find(qe, float(vm.group(1)), "sentence", page_no, around))
        if out:
            return out
        # "In Q2, cost of funds was 7.31%": the quarter comes before the metric, with or without a year
        pre = line[max(0, first - 32) : first]
        pm = FQ_B.search(pre) or FQ_A.search(pre) or BARE_Q.search(pre)
        if pm:
            kind, qe = parse_period(pm.group(0))
            vm = re.search(VALUE + r"\s*%", text[:80])
            if kind == "Q" and vm and in_range(float(vm.group(1))) and not re.search(r"\d\s*%", text[: vm.start()]):
                out.append(_find(qe, float(vm.group(1)), "sentence", page_no, line[max(0, first - 32) : first + 90]))
    return out


def _find(qe, v, layer, page, ctx, basis=None):
    flags = []
    if FORECAST.search(ctx):
        flags.append("forecast-word")
    if re.search(r"\bexcl", ctx, re.I):
        flags.append("excl-note")
        basis = "excl. adjustment"  # an adjusted figure is never the reported NIM
    return {"quarter": qe, "value": v, "layer": layer, "page": page, "basis": basis or basis_of(ctx), "flags": flags}


# ---------------------------------------------------------------- table layer
def ffill(row: list[str]) -> list[str]:
    out, last = [], ""
    for c in row:
        last = c if c else last
        out.append(last)
    return out


ROW_IN_CELL = re.compile(r"^(?P<label>[A-Za-z][^\d]*?)\s+(?P<nums>(?:-?\d[\d,]*\.?\d*%?\s+)+-?\d[\d,]*\.?\d*%?)$")


def expand_merged(grid: list[list[str]]) -> list[list[str]]:
    """pdfplumber sometimes puts a whole column of rows into one cell (rows split by newlines, no ruling
    lines). Each line 'label n1 n2 n3' becomes its own row, numbers right-aligned to the grid's columns."""
    ncols = max(len(r) for r in grid)
    out: list[list[str]] = []
    for row in grid:
        row = row + [""] * (ncols - len(row))
        if not any("\n" in c for c in row):
            out.append([re.sub(r"\s+", " ", c).strip() for c in row])
            continue
        added = False
        for cell in row:
            for line in cell.split("\n"):
                m = ROW_IN_CELL.match(line.strip())
                if not m:
                    continue
                nums = m.group("nums").split()
                if len(nums) > ncols - 1:
                    continue
                new = [""] * ncols
                new[0] = m.group("label").strip()
                for k, n in enumerate(nums):
                    new[ncols - len(nums) + k] = n
                out.append(new)
                added = True
        if not added:  # an ordinary row whose cells wrap (e.g. a header 'Q2-\n2027'): keep it, flattened
            out.append([re.sub(r"\s+", " ", c).strip() for c in row])
    return out


def table_layer(grid: list[list[str]], page_no: int) -> list[dict]:
    out: list[dict] = []
    if not grid:
        return out
    grid = expand_merged(grid)
    for g in (grid, [list(c) for c in zip(*grid, strict=False)] if grid and len({len(r) for r in grid}) == 1 else None):
        if not g:
            continue
        out += _read_grid(g, page_no, transposed=g is not grid)
    return out


def _read_grid(g: list[list[str]], page_no: int, transposed: bool) -> list[dict]:
    ncols = max(len(r) for r in g)
    g = [r + [""] * (ncols - len(r)) for r in g]
    metric_rows = [i for i, r in enumerate(g) if any(accept_metric(c) for c in r[: max(3, ncols // 2)] if c and not re.fullmatch(r"[\d.,%\s-]+", c))]
    if not metric_rows:
        return []
    first_metric = min(metric_rows)
    header_rows = g[: max(1, min(first_metric, 4))]
    filled = [ffill(r) for r in header_rows]
    out: list[dict] = []
    for c in range(ncols):
        head = " ".join(filled[h][c] for h in range(len(filled)) if filled[h][c])
        kind, qe = parse_period(head)
        if kind != "Q":
            continue
        # a header like 'Q2 FY27 vs Q2 FY26' names two quarters: numbers in a prose cell map to them in order
        head_quarters = [p for p in (parse_period(part) for part in re.split(r"\bvs\.?\b|\bv/s\b|\bcompared\b|\bagainst\b", head, flags=re.I)) if p[0] == "Q"]
        for r in metric_rows:
            label = " ".join(x for x in g[r][: max(3, ncols // 2)] if x and not re.fullmatch(r"[\d.,%\s-]+", x))
            cell = g[r][c].replace("%", "").strip()
            if not re.fullmatch(VALUE, cell) and head_quarters:
                nums = [float(n) for n in re.findall(r"(\d{1,2}\.\d{1,2})\s*%", g[r][c])]
                if 0 < len(nums) <= len(head_quarters) and all(in_range(n) for n in nums):
                    for n, (_, hq) in zip(nums, head_quarters, strict=False):
                        out.append({"quarter": hq, "value": n, "layer": "table(prose cell)", "page": page_no, "basis": basis_of(label), "flags": []})
                continue
            if re.fullmatch(VALUE, cell) and in_range(float(cell)):
                flags = ["explicit-quarterly"] if re.search(r"quarterly|quarter\s+ended|\bqtr\b", head, re.I) else []
                out.append({"quarter": qe, "value": float(cell), "layer": "table" + ("(T)" if transposed else ""), "page": page_no, "basis": basis_of(label), "flags": flags})
    return out


def _colour_close(a, b, tol: float = 0.08) -> bool:
    return a is not None and b is not None and len(a) == len(b) and sum((x - y) ** 2 for x, y in zip(a, b, strict=False)) ** 0.5 < tol


def legend_series(page, words, region, quarters, box) -> dict[str, dict]:
    """Multi-series line chart: legend label -> {quarter_end: value}.
    1. Legend entries: a short coloured mark (line or marker) just left of a text label.
    2. Series lines: long stroked paths of the same colour across the chart.
    3. Each value label goes to the series whose line passes closest to it at that quarter.
    Empty when any step is unsure (a colour with no line, two labels for one point)."""
    x0, x1, y_top, axis_y = box
    drawings = page.get_drawings()
    span = max(q[1] for q in quarters) - min(q[1] for q in quarters)
    paths = []
    for d in drawings:
        r, col = d.get("rect"), d.get("color")
        if col is None or r is None or r.width < 0.6 * span or not (x0 <= (r.x0 + r.x1) / 2 <= x1) or r.y1 > axis_y + 5 or r.y0 < y_top:
            continue
        pts = [p for it in d["items"] for p in it[1:] if hasattr(p, "x")]
        if len(pts) >= 3:
            paths.append((col, pts))
    # legend labels: non-numeric, non-quarter words in the region, merged on one line
    lines: dict[int, list] = {}
    for w in region:
        if re.fullmatch(r"[\d.,%()]+", w[4]) or parse_period(w[4])[0] == "Q":
            continue
        lines.setdefault(round(w[1] / 3), []).append(w)
    labels = []
    for ws in lines.values():
        ws.sort(key=lambda w: w[0])
        cur = [ws[0]]
        for w in ws[1:]:
            if w[0] - cur[-1][2] < 8:
                cur.append(w)
            else:
                labels.append(cur)
                cur = [w]
        labels.append(cur)
    legend: dict[str, tuple] = {}
    for lab in labels:
        lx0, ly = lab[0][0], (lab[0][1] + lab[0][3]) / 2
        marks = [d for d in drawings if d.get("rect") is not None and d["rect"].width < 45 and abs((d["rect"].y0 + d["rect"].y1) / 2 - ly) < 6 and 0 <= lx0 - d["rect"].x1 < 45]
        if marks:
            m = min(marks, key=lambda d: lx0 - d["rect"].x1)
            colour = m.get("color") or m.get("fill")
            if colour is not None:
                legend[" ".join(w[4] for w in lab)] = colour
    series_paths = {}
    for label, colour in legend.items():
        match = [pts for col, pts in paths if _colour_close(col, colour)]
        if match:
            series_paths[label] = max(match, key=len)
    # one series is enough when it is the metric itself (a combined chart: NII bars plus a NIM line)
    if not series_paths or (len(series_paths) < 2 and not any(METRIC.search(lab) for lab in series_paths)):
        return {}

    def y_at(pts, x):
        return min(pts, key=lambda p: abs(p.x - x)).y

    out: dict[str, dict] = {label: {} for label in series_paths}
    for w in region:
        if not re.fullmatch(VALUE + "%?", w[4]) or w[3] >= axis_y or not in_range(float(w[4].rstrip("%"))):
            continue
        x, yc = (w[0] + w[2]) / 2, (w[1] + w[3]) / 2
        q = min(quarters, key=lambda q: abs(q[1] - x))
        if abs(q[1] - x) > 25:
            continue
        label = min(series_paths, key=lambda lab: abs(y_at(series_paths[lab], q[1]) - yc))
        if abs(y_at(series_paths[label], q[1]) - yc) > 30:
            continue
        if q[0] in out[label]:
            return {}  # two labels for one point: unsure, read nothing
        out[label][q[0]] = float(w[4].rstrip("%"))
    return {k: v for k, v in out.items() if v}


IGNORE_CUMULATIVE = False  # tests only: lets the legend reader run on a cumulative slide


def axis_is_not_quarterly(quarters) -> bool:
    """Every gap between consecutive axis labels is 5 months or more: a half-yearly or yearly axis. One
    3-month gap is enough to call it quarterly (Bandhan's axis keeps Q2FY26, Q1FY27, Q2FY27 and drops H1 labels)."""
    months = sorted({q[0].year * 12 + q[0].month for q in quarters})
    gaps = [b - a for a, b in zip(months, months[1:], strict=False)]
    return bool(gaps) and min(gaps) >= 5


def combo_layer(page, page_no: int) -> list[dict]:
    """Combined charts whose metric is named only in the legend (bars for one measure, a line for NIM):
    Bank of Maharashtra's 'NET Interest Income' bars with a 'NIM % (Domestic)' line and one '*NIM % (Global)' label.
    - the legend entry (marker + label, or an asterisk-marked label) names the series and its basis
    - the panel is the drawn frame around the legend; its quarters come from the axis labels under the bars
    - a line series is read by colour (legend_series); a text-only entry by the colour of its value labels"""
    out: list[dict] = []
    words = page.get_text("words")
    spans = [s for b in page.get_text("dict")["blocks"] if b.get("type") == 0 for ln in b["lines"] for s in ln["spans"]]
    drawings = page.get_drawings()
    done: set = set()
    for term in TERMS:
        for t in page.search_for(term):
            label_words, edge = [], t.x1
            for w in sorted((w for w in words if abs(w[1] - t.y0) < 4 and w[2] > t.x0 + 1), key=lambda w: w[0]):
                if w[0] - edge > 14:
                    break
                label_words.append(w)
                edge = w[2]
            label = " ".join(w[4] for w in label_words)
            marked = any(d.get("rect") is not None and d["rect"].width < 45 and abs((d["rect"].y0 + d["rect"].y1) / 2 - (t.y0 + t.y1) / 2) < 6 and 0 <= t.x0 - d["rect"].x1 < 45 for d in drawings)
            basis = basis_of(label)
            if BAD_METRIC.search(label) or not (marked or basis != "unspecified" or label.lstrip().startswith("*")):
                continue
            panel = enclosing_box(drawings, t, page.rect, max_frac=0.45)
            if panel is None or (panel.x0, panel.y0) in done and not label.lstrip().startswith("*"):
                continue
            # the panel's caption: '(Quarterly)' / '(Half-Yearly)' printed just above it
            caption = " ".join(w[4] for w in words if panel.y0 - 28 <= w[3] <= panel.y0 + 4 and panel.x0 - 10 <= w[0] <= panel.x1 + 10)
            if re.search(r"half|yearly|annual|9\s*m", caption, re.I) and not re.search(r"quarterly", caption, re.I):
                continue
            region = [w for w in words if panel.x0 <= (w[0] + w[2]) / 2 <= panel.x1 and panel.y0 <= w[1] <= panel.y1]
            lines: dict[int, list] = {}
            for w in region:
                lines.setdefault(round(w[1] / 3), []).append(w)
            quarters = []
            for ws in lines.values():
                ws.sort(key=lambda w: w[0])
                cur = [ws[0]]
                toks = []
                for w in ws[1:]:
                    if w[0] - cur[-1][2] < 10:
                        cur.append(w)
                    else:
                        toks.append(cur)
                        cur = [w]
                toks.append(cur)
                for tok in toks:
                    kind, qe = parse_period(" ".join(w[4] for w in tok))
                    if kind == "Q":
                        quarters.append((qe, (tok[0][0] + tok[-1][2]) / 2, tok[0][1]))
            by_line: dict = {}
            for q in quarters:
                by_line.setdefault(round(q[2] / 3), []).append(q)
            quarters = max(by_line.values(), key=lambda qs: len({q[0] for q in qs})) if by_line else []
            if len({q[0] for q in quarters}) < 2 or axis_is_not_quarterly(quarters):
                continue
            axis_y = min(q[2] for q in quarters)
            found: dict[str, float] = {}
            series_found: list[tuple[str, dict[str, float]]] = []  # (the series' own legend label, quarter -> value)
            if marked:
                series = legend_series(page, words, region, quarters, (panel.x0, panel.x1, panel.y0, axis_y))
                series_found = [(lab, {str(k): v for k, v in vals.items()}) for lab, vals in series.items() if METRIC.search(lab) and not BAD_METRIC.search(lab)]
            else:
                legend_colour = next((s["color"] for s in spans if abs(s["bbox"][1] - t.y0) < 4 and abs(s["bbox"][0] - t.x0) < 14), None)
                for s in spans:
                    sx0, sy0, sx1, sy1 = s["bbox"]
                    vm = re.fullmatch(VALUE + r"\*?", s["text"].strip())
                    if vm and s["color"] == legend_colour and panel.x0 <= sx0 <= panel.x1 and panel.y0 <= sy0 <= axis_y and in_range(float(vm.group(1))):
                        xc = (sx0 + sx1) / 2
                        q = min(quarters, key=lambda q: abs(q[1] - xc))
                        if abs(q[1] - xc) <= 25:
                            found[str(q[0])] = float(vm.group(1))
            if found:
                series_found.append((label, found))
            for lab, vals in series_found:
                b = basis_of(lab)  # each series carries its own basis ('NIM - Domestic' is not 'NIM - Overall')
                if b == "unspecified":
                    b = basis_of(label)  # the series label can be cut short ('NIM'): the whole legend entry says '(Domestic)'
                for qs, v in vals.items():
                    out.append(
                        {
                            "quarter": date.fromisoformat(qs),
                            "value": v,
                            "layer": "chart(combo)",
                            "page": page_no,
                            "basis": b,
                            "flags": ["metric named in the legend: " + lab[:40]],
                        }
                    )
            done.add((panel.x0, panel.y0))
    return out


# ---------------------------------------------------------------- chart layer (bars only)
CENTRED = False  # a title centred over its chart (IOB): the window is the title's centre +- 175, not its left edge + 330


def chart_layer(page, page_no: int) -> list[dict]:
    """Left-anchored window first (title at the chart's left edge). Only when that reads nothing on the
    page, retry with the window centred on the title, so a centred title no longer cuts off the first quarters."""
    global CENTRED
    CENTRED = False
    out = _chart_layer(page, page_no)
    CENTRED = True
    try:
        alt = _chart_layer(page, page_no)
    finally:
        CENTRED = False
    # keep the window that reads more quarters (a centred title cuts the left window short, not the reverse)
    return alt if len({f["quarter"] for f in alt}) > len({f["quarter"] for f in out}) else out


def _chart_layer(page, page_no: int) -> list[dict]:
    words = page.get_text("words")
    out = []
    for term in TERMS:
        for t in page.search_for(term):
            # the title is the run of adjacent words on this line (gaps under 15 pt), not a fixed window
            left_words: list = []
            edge = t.x0
            for w in sorted((w for w in words if abs(w[1] - t.y0) < 4 and w[2] <= t.x0 + 1), key=lambda w: -w[2]):
                if edge - w[2] > 15:
                    break
                left_words.insert(0, w)
                edge = w[0]
            line_left = " ".join(w[4] for w in left_words)
            title_x0 = edge
            line_right = " ".join(w[4] for w in words if abs(w[1] - t.y0) < 4 and t.x1 < w[0] < t.x1 + 140)
            # A title starts its line, or follows other metric names in a shared title ('Cost of Deposits, Cost of Funds, ...').
            shared_title = bool(re.fullmatch(r"(?:\s*(?:cost\s+of\s+\w+|yield\s+on\s+[\w\s]+?|net\s+interest\s+margin|nim)\s*[,&/]?\s*(?:and\b\s*)?)+", line_left, re.I))
            if BAD_METRIC.search(line_left + " " + term + " " + line_right) or (line_left.strip() and not re.search(r"^\W*$", line_left) and not shared_title):
                continue
            # A legend entry is not a title: it has a small marker (line or dot) just to its left.
            if any(
                d.get("rect") is not None and d["rect"].width < 45 and abs((d["rect"].y0 + d["rect"].y1) / 2 - (t.y0 + t.y1) / 2) < 6 and 0 <= t.x0 - d["rect"].x1 < 45 for d in page.get_drawings()
            ):
                continue
            if basis_of(line_left + " " + term + " " + line_right) == "segment":
                continue  # 'Yield on Advances of MARG portfolio': a segment chart
            col_x0, col_x1 = title_x0 - 30, title_x0 + 330  # a shared title: the chart starts where the title starts
            if CENTRED:
                col_x0, col_x1 = (t.x0 + t.x1) / 2 - 175, (t.x0 + t.x1) / 2 + 175
            # a title printed in a band (grey strip, coloured banner) spans the chart: the band gives its width
            band = next(
                (
                    d["rect"]
                    for d in page.get_drawings()
                    if d.get("rect") is not None
                    and d["rect"].x0 - 1 <= title_x0
                    and d["rect"].x1 + 1 >= t.x1
                    and d["rect"].y0 - 2 <= t.y0
                    and d["rect"].y1 + 2 >= t.y1
                    and d["rect"].width > (t.x1 - title_x0) + 40
                    and d["rect"].height < 4 * (t.y1 - t.y0)
                    and d["rect"].width < 0.7 * page.rect.width
                ),
                None,
            )
            if band is not None:
                col_x0, col_x1 = band.x0 - 5, band.x1 + 5
            # stop at the next chart's title on the same line (side-by-side charts must not mix)
            same_line = sorted((w for w in words if abs(w[1] - t.y0) < 4 and w[0] > t.x1), key=lambda w: w[0])
            prev_x1 = t.x1
            for w in same_line:
                if w[0] - prev_x1 > 30:
                    col_x1 = min(col_x1, w[0] - 10)
                    break
                prev_x1 = w[2]
            region = [w for w in words if col_x0 <= (w[0] + w[2]) / 2 <= col_x1 and t.y1 < w[1] < t.y1 + 260]
            # axis tokens: merge words on one line (gap < 10) and parse as quarter labels
            lines: dict[int, list] = {}
            for w in region:
                lines.setdefault(round(w[1] / 3), []).append(w)
            quarters = []
            for ws in lines.values():
                ws.sort(key=lambda w: w[0])
                tokens, cur = [], [ws[0]]
                for w in ws[1:]:
                    if w[0] - cur[-1][2] < 10:
                        cur.append(w)
                    else:
                        tokens.append(cur)
                        cur = [w]
                tokens.append(cur)
                for tok in tokens:
                    kind, qe = parse_period(" ".join(w[4] for w in tok))
                    if kind == "Q":
                        quarters.append((qe, (tok[0][0] + tok[-1][2]) / 2, tok[0][1]))
            # an axis is one line holding two or more different quarters ('(Q2 FY26)' repeated under cards is not)
            by_line: dict = {}
            for q in quarters:
                by_line.setdefault(round(q[2] / 3), []).append(q)
            quarters = max(by_line.values(), key=lambda qs: len({q[0] for q in qs})) if by_line else []
            if len({q[0] for q in quarters}) < 2:
                continue
            # The chart may be wider than the first guess: follow the axis line rightwards while the
            # labels keep their spacing (a bigger gap means the next chart has started).
            quarters.sort(key=lambda q: q[1])
            if axis_is_not_quarterly(quarters):
                continue  # labels 6 or 12 months apart: a half-yearly or yearly chart
            axis_line = sorted((w for w in words if abs(w[1] - quarters[0][2]) < 3 and w[0] >= quarters[0][1] - 40), key=lambda w: w[0])
            toks, cur = [], []
            for w in axis_line:
                if cur and w[0] - cur[-1][2] >= 10:
                    toks.append(cur)
                    cur = []
                cur.append(w)
            if cur:
                toks.append(cur)
            full = [(qe, (tk[0][0] + tk[-1][2]) / 2, tk[0][1]) for tk in toks for kind, qe in [parse_period(" ".join(w[4] for w in tk))] if kind == "Q"]
            steps = sorted(b[1] - a[1] for a, b in zip(quarters, quarters[1:], strict=False))
            step = steps[len(steps) // 2] if steps else 60
            keep = [q for q in full if q[1] <= quarters[0][1] + 1][-1:] or quarters[:1]
            for q in full:
                if q[1] > keep[-1][1] and q[1] - keep[-1][1] <= step * 1.5:
                    keep.append(q)
            if len(keep) > len(quarters):
                quarters = keep
                col_x1 = max(col_x1, keep[-1][1] + step * 0.6)
                region = [w for w in words if col_x0 <= (w[0] + w[2]) / 2 <= col_x1 and t.y1 < w[1] < t.y1 + 260]
            axis_y = min(q[2] for q in quarters)
            top_text = " ".join(w[4] for w in words if w[1] < page.rect.height * 0.25)
            if not IGNORE_CUMULATIVE and re.search(r"cumulative|\bytd\b|year\s+to\s+date|yearly|year[\s-]*wise|\bannual\b|\(\s*[369]\s*m\s*\)", top_text + " " + " ".join(w[4] for w in region), re.I):
                continue  # slide or chart says cumulative: not quarterly values
            candidate_bars = [
                d["rect"]
                for d in page.get_drawings()
                if d.get("rect")
                and d.get("fill")
                and col_x0 <= (d["rect"].x0 + d["rect"].x1) / 2 <= col_x1
                and d["rect"].height > 8
                and 8 <= d["rect"].width < 80
                and d["rect"].y1 <= axis_y + 2
                and d["rect"].y0 > t.y1
            ]
            # real bars sit over the quarter labels: legend squares and line markers do not
            bars = [b for b in candidate_bars if min(abs(q[1] - (b.x0 + b.x1) / 2) for q in quarters) < 20]
            covered = {min(range(len(quarters)), key=lambda i: abs(quarters[i][1] - (b.x0 + b.x1) / 2)) for b in bars}
            if len(covered) < len(quarters) - 1:
                # No bars: a line chart. Accept only a single series (exactly one value label per quarter, none extra);
                # two or more series in the region cannot be told apart without the legend.
                paired: dict = {}
                for w in region:
                    if re.fullmatch(VALUE + "%?", w[4]) and w[3] < axis_y and in_range(float(w[4].rstrip("%"))):
                        x = (w[0] + w[2]) / 2
                        q = min(quarters, key=lambda q: abs(q[1] - x))
                        if abs(q[1] - x) <= 25:
                            paired.setdefault(q[0], []).append(float(w[4].rstrip("%")))
                if len(paired) == len({q[0] for q in quarters}) and all(len(v) == 1 for v in paired.values()):
                    for qe, vs in paired.items():
                        out.append({"quarter": qe, "value": vs[0], "layer": "chart(line)", "page": page_no, "basis": "unspecified", "flags": ["single-series line chart"]})
                elif paired:  # several series: tell them apart with the legend (marker colour = line colour)
                    for label, series in legend_series(page, words, region, quarters, (col_x0, col_x1, t.y1, axis_y)).items():
                        b = basis_of(label)
                        for qe, v in series.items():
                            out.append(
                                {
                                    "quarter": qe,
                                    "value": v,
                                    "layer": "chart(legend)",
                                    "page": page_no,
                                    "basis": (b if b != "unspecified" else (label if not METRIC.fullmatch(re.sub(r"[^\w\s]", " ", label).strip()) else "unspecified")),
                                    "flags": [f"series '{label}'"],
                                }
                            )
                continue
            region_has_excl = bool(re.search(r"\bexcl", " ".join(w[4] for w in region), re.I))
            for w in region:
                if not re.fullmatch(VALUE + "%?", w[4]) or w[3] >= axis_y:
                    continue
                v, x = float(w[4].rstrip("%")), (w[0] + w[2]) / 2
                if not in_range(v):
                    continue
                q = min(quarters, key=lambda q: abs(q[1] - x))
                if abs(q[1] - x) > 25:
                    continue
                tops = [b.y0 for b in bars if b.x0 - 3 <= x <= b.x1 + 3]
                if not tops:
                    continue
                above = w[3] <= min(tops) + 2
                if not above and not region_has_excl:
                    # a small square tag around the value (IOB's markers) is a label box, not a bar: the value is plain
                    tag = any(b.x0 - 3 <= x <= b.x1 + 3 and b.y0 - 2 <= w[1] and w[3] <= b.y1 + 2 and b.width <= 40 and b.height <= 40 and w[0] >= b.x0 - 2 and w[2] <= b.x1 + 2 for b in bars)
                    if not tag:
                        continue  # a value inside a bar with no 'excl.' note on the chart: unexplained, dropped
                    above = True
                out.append(
                    {
                        "quarter": q[0],
                        "value": v,
                        "layer": "chart",
                        "page": page_no,
                        "basis": "unspecified" if above else "excl. adjustment",
                        "flags": [] if above else ["inside-bar, chart mentions excl."],
                    }
                )
    return out


# ---------------------------------------------------------------- position table (no ruling lines)
def phrase_boxes(words, gap: float = 8.0) -> list[tuple]:
    """Words joined into phrases: same line, gaps under `gap` pt. (x0, y0, x1, y1, text), like OCR boxes."""
    out: list[list] = []
    for w in sorted(words, key=lambda w: (round((w[1] + w[3]) / 2 / 3), w[0])):
        if out and abs((out[-1][1] + out[-1][3]) / 2 - (w[1] + w[3]) / 2) < 3 and 0 <= w[0] - out[-1][2] < gap:
            out[-1][2], out[-1][3], out[-1][4] = w[2], max(out[-1][3], w[3]), out[-1][4] + " " + w[4]
        else:
            out.append([w[0], w[1], w[2], w[3], w[4]])
    return [tuple(b) for b in out]


def rows_of(boxes):
    rows: list[list] = []
    for b in sorted(boxes, key=lambda b: (b[1] + b[3]) / 2):
        yc, h = (b[1] + b[3]) / 2, b[3] - b[1]
        if rows and abs(yc - rows[-1][0]) < 0.6 * max(h, rows[-1][1]):
            rows[-1][2].append(b)
        else:
            rows.append([yc, h, [b]])
    return [sorted(r[2], key=lambda b: b[0]) for r in rows]


DATA_TOKEN = re.compile(r"\d\.\d|%|\bRs\.?|\bCr\b|₹|\b(?!(?:19|20)\d{2}\b)\d{3,}|\d,\d|\bbps\b")  # values, amounts; a year is not data
NUMERIC_BOX = re.compile(r"^[\s(+-]*\d[\d,]*\.?\d*\s*(?:%|bps)?[\s)]*$")


def _split_words(b):
    text = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", b[4])
    text = re.sub(r"(?<=[\w')])(?=(?:FY\s?\d|Q[1-4]\b|Q[1-4]-|H[12]\b|H[12]-|HY[12]))", " ", text)
    words = text.split()
    if len(words) < 2:
        return [b]
    out, pos, width = [], 0, b[2] - b[0]
    for w in words:
        start = text.index(w, pos)
        pos = start + len(w)
        out.append((b[0] + width * start / len(text), b[1], b[0] + width * pos / len(text), b[3], w))
    return out


def column_header(boxes, b, centres=(), page_w=960.0, page_h=540.0) -> str:
    """Header of value b's column: walk up through the column's data cells, take the first band of
    non-data rows above them. Slide titles never count; a header over several value columns is split."""
    xc, bw = (b[0] + b[2]) / 2, max(b[2] - b[0], 1)
    words = []
    for h in boxes:
        if h[3] > b[1] + 1 or h[1] < 0.1 * page_h or (h[2] - h[0]) > 0.45 * page_w:
            continue
        spans = sum(1 for c in centres if h[0] - 6 <= c <= h[2] + 6)
        for w in _split_words(h) if spans >= 2 else [h]:
            if w[0] - 6 <= xc <= w[2] + 6 or min(w[2], b[2]) - max(w[0], b[0]) >= 0.25 * bw:
                words.append(w)
    picked: list = []
    last_top = None
    for row in sorted(rows_of(words), key=lambda r: -max(w[3] for w in r)):
        is_data = bool(DATA_TOKEN.search(" ".join(w[4] for w in row)))
        if not picked:
            if not is_data:
                picked, last_top = list(row), min(w[1] for w in row)
            continue
        if is_data or last_top - max(w[3] for w in row) > 35:
            break
        picked += row
        last_top = min(last_top, min(w[1] for w in row))
    return " ".join(w[4] for w in sorted(picked, key=lambda w: (w[1], w[0])))


def box_table(boxes, page_no: int, page_w: float, page_h: float, layer: str) -> list[dict]:
    """A table read by position (text words or OCR boxes): the metric's row, each value under its own header."""
    out = []
    for row in rows_of(boxes):
        labels = [b for b in row if not NUMERIC_BOX.match(b[4])]
        if not labels or not accept_metric(labels[0][4]):
            continue
        cells = [b for b in row if b is not labels[0] and b[0] > labels[0][0]]
        centres = [(c[0] + c[2]) / 2 for c in cells]
        for b in cells:
            head = column_header(boxes, b, centres, page_w, page_h)
            clean = re.sub(r"[¹²³⁰-⁹*#^\s]", "", b[4])
            vm = re.fullmatch(r"\(?(\d{1,2}\.\d{1,2})%?\)?", clean)
            if vm and in_range(float(vm.group(1))):
                kind, qe = parse_period(head)
                if kind == "Q":
                    flags = ["explicit-quarterly"] if re.search(r"quarterly|quarter\s+ended", head, re.I) else []
                    out.append({"quarter": qe, "value": float(vm.group(1)), "layer": layer, "page": page_no, "basis": basis_of(labels[0][4]), "flags": flags})
            elif "%" in b[4]:  # prose cell under 'Q2 FY27 vs Q2 FY26'
                hq = [p for p in (parse_period(s) for s in re.split(r"\bvs\.?\b|\bv/s\b|\bcompared\b|\bagainst\b", head, flags=re.I)) if p[0] == "Q"]
                nums = [float(n) for n in re.findall(r"(\d{1,2}\.\d{1,2})\s*%", b[4])]
                if hq and 0 < len(nums) <= len(hq) and all(in_range(n) for n in nums):
                    out += [{"quarter": q, "value": n, "layer": layer + "(prose)", "page": page_no, "basis": basis_of(labels[0][4]), "flags": []} for n, (_, q) in zip(nums, hq, strict=False)]
    return out


def enclosing_box(drawings, r, page_rect, max_frac: float = 0.3):
    """The smallest drawn box (card, cell, rounded rectangle) around rect r, or None. Page backgrounds
    and large panels (over max_frac of the page) are not cards."""
    best = None
    page_area = page_rect.width * page_rect.height
    for d in drawings:
        b = d.get("rect")
        if b is None or b.width < r.width + 4 or b.height < r.height + 4:
            continue
        if not (b.x0 - 1 <= r.x0 and b.y0 - 1 <= r.y0 and r.x1 <= b.x1 + 1 and r.y1 <= b.y1 + 1):
            continue
        if b.width * b.height > max_frac * page_area or b.height < 2 * r.height:
            continue  # page panels; a thin bar behind the label is not the card
        if best is None or b.width * b.height < best.width * best.height:
            best = b
    return best


# ---------------------------------------------------------------- card layer (KPI boxes)
def card_layer(page, page_no: int) -> list[dict]:
    """KPI cards: a 'NIM' label with its % value underneath. The value's quarter is the page title's quarter
    (exactly one on the page's top fifth); 'v/s X% in Q2FY26' under the value gives the comparator explicitly."""
    words = page.get_text("words")
    page_q = page_quarter(page)
    top = " ".join(w[4] for w in words if w[1] < page.rect.height * 0.22)
    slide_not_quarter = bool(NON_QUARTER.search(top))  # 'Key Financial Highlights – H1FY27', 'yearly trends'
    tokens = phrase_boxes(words, gap=6)  # '14.6' + '%' -> '14.6 %'
    drawings = page.get_drawings()
    out = []
    for term in TERMS:
        for t in page.search_for(term):
            ctx = " ".join(w[4] for w in words if abs(w[1] - t.y0) < 4 and t.x0 - 60 < w[0] < t.x1 + 80)
            if BAD_METRIC.search(ctx):
                continue
            cx = (t.x0 + t.x1) / 2
            box = enclosing_box(drawings, t, page.rect)
            first: Any = None
            v: float | None = None
            if box is not None:
                # The card's own box decides: only a value printed inside the label's box belongs to it
                # (CUB: 'NIM had improved to 3.87%' is in the box; 'Gross NPA 1.44%' is in the next one).
                inside = [w for w in tokens if box.contains(pymupdf.Point((w[0] + w[2]) / 2, (w[1] + w[3]) / 2))]
                # 1. the label's own phrase: 'NIM had improved to 3.87%'
                own = [w for w in inside if term.lower() in w[4].lower() and re.search(VALUE + r"\s*%", w[4][w[4].lower().find(term.lower()) + len(term) :])]
                pick: Any
                if own:
                    pick = own[0]
                    vm = re.search(VALUE + r"\s*%", pick[4][pick[4].lower().find(term.lower()) + len(term) :])
                else:
                    # 2. else the nearest value in the label's own column: a panel can hold several cards side by side
                    #    (Indostar: 'Yield on loan assets 17.1%' sits in the next card of the same panel)
                    col = [w for w in inside if abs((w[0] + w[2]) / 2 - cx) < 70 and re.fullmatch(r"\s*" + VALUE + r"\s*%\s*", w[4])]
                    pick = min(col, key=lambda w: min(abs(w[1] - t.y1), abs(t.y0 - w[3]))) if col else None
                    vm = re.search(VALUE + r"\s*%", pick[4]) if pick else None
                if vm:
                    first, v = pick, float(vm.group(1))
            if v is None and box is not None and box.height >= 3 * (t.y1 - t.y0):
                continue  # a real card with no value in it: never borrow the next card's number
            if v is None:  # no box, or a label strip with the value outside it (M&M's red 'NIM*' bar): nearest value
                pct = [w for w in tokens if re.fullmatch(r"\d{1,2}\.\d{1,2}\s*%", w[4]) and abs((w[0] + w[2]) / 2 - cx) < 80]
                below = [(w[1] - t.y1, w) for w in pct if t.y1 <= w[1] <= t.y1 + 90]
                above = [(t.y0 - w[3], w) for w in pct if t.y0 - 45 <= w[3] <= t.y0 + 1 and abs((w[0] + w[2]) / 2 - cx) < 60]
                if not below and not above:
                    continue
                first = min(below + above, key=lambda d: d[0])[1]
                v = float(re.sub(r"\s*%", "", first[4]))
            if not in_range(v):
                continue
            cap = " ".join(w[4] for w in sorted(words, key=lambda w: (round(w[1]), w[0])) if first[3] <= w[1] <= first[3] + 40 and abs((w[0] + w[2]) / 2 - cx) < 110)
            near = " ".join(w[4] for w in words if t.y1 <= w[1] <= first[3] + 120 and abs((w[0] + w[2]) / 2 - cx) < 140)
            if re.search(r"\bh[12]\b|\bhy\s*[12]\b|\b9m\b|\bfy\s*'?\d{2}\b(?!\s*q)|merger|since|\bas\s+(?:on|of|at)\b|cumulative|\bytd\b", near, re.I) and not re.search(r"\bq[1-4]\s*fy", near, re.I):
                continue  # the value carries its own non-quarter period label ('H1 FY27', 'At merger'): not this quarter
            card_basis = "excl. adjustment" if re.search(r"one[\s-]*off|x[\s-]*1\s*off|\bexcl", first[4], re.I) else "unspecified"  # 'NIM is 3.49% (x-1 Off)'
            if page_q:
                out.append({"quarter": page_q, "value": v, "layer": "card", "page": page_no, "basis": card_basis, "flags": ["quarter from page title"]})
            elif DECK_Q and not slide_not_quarter and re.search(r"\b(?:v/s|vs)\b", cap, re.I):
                # no quarter on the slide; the card compares with a named quarter, so the value is the deck's quarter
                out.append({"quarter": DECK_Q, "value": v, "layer": "card(deck quarter)", "page": page_no, "basis": "unspecified", "flags": ["quarter from deck cover"]})
            # comparators printed under the value, each with its own quarter:
            #   'v/s 7.0% in Q2FY26' | 'Q2FY26 7.6% | Q1FY27 8.8%' | '4.04%/4.21% (Q2FY26/Q1FY27)' | '15.4% (Q2 FY26)'
            pairs = []
            for cm in re.finditer(r"(\d{1,2}\.\d{1,2})\s*%\s*in\s+(\S+(?:\s\S+)?)", cap):
                pairs.append((cm.group(2), cm.group(1)))
            for cm in re.finditer(r"\b(Q[1-4]\s*FY\s*'?\d{2})\s*:?\s*(\d{1,2}\.\d{1,2})\s*%", cap, re.I):
                pairs.append((cm.group(1), cm.group(2)))
            for cm in re.finditer(r"(\d{1,2}\.\d{1,2})\s*%\s*/\s*(\d{1,2}\.\d{1,2})\s*%\s*\(\s*([^/()]+?)\s*/\s*([^/()]+?)\s*\)", cap):
                pairs += [(cm.group(3), cm.group(1)), (cm.group(4), cm.group(2))]
            for cm in re.finditer(r"(\d{1,2}\.\d{1,2})\s*%\s*\(\s*(Q[1-4]\s*FY\s*'?\d{2})\s*\)", cap, re.I):
                pairs.append((cm.group(2), cm.group(1)))
            for label, val in pairs:
                kind, qe = parse_period(label)
                if kind == "Q" and in_range(float(val)) and not (qe == page_q and abs(float(val) - v) > 0.001):
                    out.append({"quarter": qe, "value": float(val), "layer": "card(comparator)", "page": page_no, "basis": "unspecified", "flags": []})
    return out


# ---------------------------------------------------------------- run
def run(pdf_path: Path, self_symbol: str | None = None) -> list[dict]:
    """Every reading of the current metric (see use_metric) in one deck; `self_symbol` is the deck's own company.
    The deck's year context lives only for the run."""
    global CONTEXT_FY, DECK_Q
    try:
        return _run(pdf_path, self_symbol)
    finally:
        CONTEXT_FY, DECK_Q = None, None


def _run(pdf_path: Path, self_symbol: str | None) -> list[dict]:
    global CONTEXT_FY, DECK_Q
    found: list[dict] = []
    doc = pymupdf.open(pdf_path)
    CONTEXT_FY, DECK_Q = deck_context([doc[i].get_text() for i in range(min(len(doc), 5))])
    # entity tags for every page, from the section titles (read in order, so a page inherits its section)
    sections = ENTITY.page_sections([(doc[i].get_text("words"), doc[i].rect.height) for i in range(len(doc))], self_symbol)
    with pdfplumber.open(pdf_path) as plumb:
        for pno in range(len(doc)):  # every page: NIM can sit anywhere, even past page 60
            page = doc[pno]
            text = page.get_text()
            if not METRIC.search(text):
                continue
            page_found = sentence_layer(text, pno + 1, page_quarter(page))
            page_found += chart_layer(page, pno + 1)
            page_found += card_layer(page, pno + 1)
            page_found += combo_layer(page, pno + 1)
            page_found += box_table(phrase_boxes(page.get_text("words")), pno + 1, page.rect.width, page.rect.height, "table(position)")
            for tbl in plumb.pages[pno].extract_tables() or []:
                grid = [[(c or "").strip() for c in row] for row in tbl if row]  # keep newlines: merged rows are split later
                page_found += table_layer(grid, pno + 1)
            # the slide title's basis ('Snapshot Consolidated Q2FY27' / 'Snapshot Standalone Q2FY27') tags its values
            top = " ".join(w[4] for w in page.get_text("words") if w[1] < page.rect.height * 0.22).lower()
            title_basis = "consolidated" if "consolidated" in top and "standalone" not in top else "standalone" if "standalone" in top and "consolidated" not in top else None
            for f in page_found:
                if title_basis and f["basis"] == "unspecified":
                    f["basis"] = title_basis
            tag = sections[pno]
            for f in page_found:
                f["entity"] = tag["entity"]
                if tag["entity"] != "self":
                    f["basis"] = "entity:" + tag["entity"]  # a subsidiary's or segment's figure is never the company's own
                    f["flags"].append("section: " + tag["entity"])
                elif f["basis"] == "unspecified" and tag["basis"]:
                    f["basis"] = tag["basis"]
                    if tag.get("inferred_standalone"):
                        f["flags"].append("standalone inferred: the company-named section of a deck that also prints a consolidated one")
            # a footnote saying the page's figures are half-year ('Sep-26 are of H1FY27') voids its tables and cards
            foot = " ".join(w[4] for w in page.get_text("words") if w[1] > page.rect.height * 0.85)
            if re.search(r"\b(?:are|is)\s+(?:of|for)\s+(?:h[12]|9m|hy\s*[12])\s*'?\s*fy", foot, re.I):
                page_found = [f for f in page_found if f["layer"] == "sentence"]
            found += page_found
    # our coverage starts at FY23: older figures in a deck are real history, just outside what we show
    found = [f for f in found if f["quarter"] >= COVERAGE_FROM]
    return found
