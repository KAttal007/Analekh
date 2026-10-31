"""Entity tagging for deck pages: which company, and which basis, does each page's figures belong to?

A group deck holds several companies (Bajaj Finance and its subsidiary Bajaj Housing Finance) and two bases
(consolidated, standalone). Each page's title names them. A page's tag is the section it sits in:
  - the title line is read ('Lead financial indicators for Q2 FY27 - consolidated (1/4)',
    'Executive summary - BHFL', 'Executive summary - Bajaj Finance')
  - a name is matched to our own companies table (full name or initials), so 'BHFL' becomes BAJAJHFL
  - a page without such a title inherits the section it follows
Tag = (entity, basis, named): entity is 'self' (the deck's company) or a symbol or 'other:<name>';
basis is 'consolidated' | 'standalone' | None; named is True when the page's own title named the entity.
"""

import re

NAMES: dict[str, str] = {}  # symbol -> company name, from our own companies table (set_names)
_DASH = re.compile(r"\s[–—-]\s|–|—")
_PERIOD = re.compile(r"\b(?:q[1-4]\s*fy\s*'?\d{2,4}|[1-4]q\s*fy\s*'?\d{2,4}|h[12]\s*fy\s*'?\d{2,4}|fy\s*'?\d{2,4})\b", re.I)
_PAGE_OF = re.compile(r"\(\s*\d+\s*/\s*\d+\s*\)")
_LEAD = re.compile(r"executive\s+summary|financial\s+summary|lead\s+financial\s+indicators|snapshot|subsidiary|business\s+overview|company\s+overview", re.I)
_DROP = re.compile(r"\b(limited|ltd|the|inc|plc)\b", re.I)
_SUBSIDIARY = re.compile(r"subsidiar|\bassociates?\b|joint\s+venture|regional\s+rural|\brrbs?\b|sponsored\s+by", re.I)
_STATEMENT = re.compile(r"profit\s*(?:and|&)?\s*loss|income\s+statement|balance\s+sheet|statement\s+of", re.I)
_MONTH = re.compile(r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\b", re.I)
_GENERIC = re.compile(
    r"(?:key\s+|financial\s+|business\s+|operational\s+|performance\s+|asset\s+quality\s+|balance\s+sheet\s+|profit\s+loss\s+)*"
    r"(?:overview|highlights?|performance|metrics|ratios?|update|profile|presentation|statements?|profit loss statement|balance sheet|trends?|outlook|strategy|snapshot|results?)?(?:\s+(?:for|of))?",
    re.I,
)


def norm(s: str) -> str:
    s = re.sub(r"[^a-z0-9 ]+", " ", _DROP.sub(" ", s.lower()))
    return re.sub(r"\s+", " ", s).strip()


def initials(name: str) -> str:
    return "".join(w[0] for w in re.findall(r"[A-Za-z]+", name)).upper()


_BY_NAME: dict[str, str] = {}
_BY_INITIALS: dict[str, list[str]] = {}


def set_names(names: dict[str, str]) -> None:
    """Load the symbol -> name table the tagger matches section titles against."""
    NAMES.clear()
    NAMES.update(names)
    _BY_NAME.clear()
    _BY_INITIALS.clear()
    for sym, name in NAMES.items():
        if name:
            _BY_NAME.setdefault(norm(name), sym)
            _BY_INITIALS.setdefault(initials(name), []).append(sym)


def title_line(words, page_height: float) -> str:
    """The first line of text on the page (the slide title)."""
    top = sorted((w for w in words if w[1] < page_height * 0.2 and w[4].strip()), key=lambda w: (w[1], w[0]))
    if not top:
        return ""
    y0 = top[0][1]
    return " ".join(w[4] for w in sorted((w for w in top if abs(w[1] - y0) < 5), key=lambda w: w[0]))


def parse_title(title: str, self_sym: str | None) -> tuple[str | None, str | None]:
    """(entity, basis) read from one title line; either may be None (not stated)."""
    t = _PAGE_OF.sub(" ", title)
    low = t.lower()
    basis = "consolidated" if "consolidated" in low and "standalone" not in low else "standalone" if "standalone" in low and "consolidated" not in low else None
    entity = None
    # the group's own figures: 'SBI group financials - Q1FY27' is the consolidated company, not a subsidiary
    if re.search(r"\bgroup\b", low) and re.search(r"financials?|results?|summary|snapshot", low) and not _SUBSIDIARY.search(low.replace("group", "")):
        return "self", basis or "consolidated"
    # pages about subsidiaries, associates or sponsored banks are never the company's own figures
    if _SUBSIDIARY.search(low):
        return "other:" + re.sub(r"\s+", " ", t).strip()[:60], None
    parts = [p.strip() for p in _DASH.split(t) if p.strip()]
    seg = _PERIOD.sub(" ", parts[-1]).strip() if len(parts) > 1 else ""
    seg_clean = re.sub(r"\b(consolidated|standalone|financials|results|summary|overview)\b", " ", seg, flags=re.I)
    seg_clean = re.sub(r"\s+", " ", seg_clean).strip()
    if seg_clean and (_GENERIC.fullmatch(norm(seg_clean)) or re.search(r"\d", seg_clean) or _MONTH.search(seg_clean) or len(seg_clean.split()) > 6):
        seg_clean = ""  # 'September 2026', 'Q2 FY27 Performance', 'Overview': a period or a topic, not a company
    if seg_clean and (_LEAD.search(t) or norm(seg_clean) in _BY_NAME or seg_clean.upper().replace(" ", "") in _BY_INITIALS):
        entity = _resolve(seg_clean, self_sym)
    elif seg_clean and _STATEMENT.search(parts[0]):
        entity = "other:" + seg_clean[:60]  # 'Profit and Loss Statement - Vehicle Finance (Managed)': one business's statement
    elif not seg_clean and basis:
        entity = "self"  # 'Financial summary - Consolidated', 'Snapshot Standalone Q2FY27': the company itself
    elif basis and _LEAD.search(t):
        entity = "self"
    return entity, basis


def _resolve(name: str, self_sym: str | None) -> str | None:
    n = norm(name)
    if not n or len(n) < 2:
        return None
    key = name.upper().replace(" ", "")
    if self_sym and self_sym in NAMES:
        full = norm(NAMES[self_sym])
        if n == full or full.startswith(n) and len(n.split()) >= 2 or key == initials(NAMES[self_sym]):
            return "self"
    if n in _BY_NAME:
        return "self" if _BY_NAME[n] == self_sym else _BY_NAME[n]
    cands = _BY_INITIALS.get(key, [])
    if self_sym in NAMES and NAMES[self_sym]:  # an acronym is trusted only for a company of the same group ('BHFL' in Bajaj Finance's deck)
        brand = norm(NAMES[self_sym]).split()[:1]
        cands = [c for c in cands if norm(NAMES[c]).split()[:1] == brand]
    if len(cands) == 1 and len(key) >= 3:
        return "self" if cands[0] == self_sym else cands[0]
    # a company named with more words than its table entry ('Bajaj Finance Limited (BFL)') still starts with it
    for full, sym in _BY_NAME.items():
        if len(full.split()) >= 2 and (n == full or n.startswith(full + " ")):
            return "self" if sym == self_sym else sym
    return "other:" + name.strip()


def page_sections(pages_words: list[tuple[list, float]], self_sym: str | None) -> list[dict]:
    """One tag per page, in order. pages_words: [(words, page_height), ...]."""
    out, cur_entity, cur_basis = [], "self", None
    named_any_consolidated = False
    for words, height in pages_words:
        ent, basis = parse_title(title_line(words, height), self_sym)
        named = ent is not None
        if ent is not None:
            cur_entity, cur_basis = ent, basis
        elif basis is not None:
            cur_basis = basis
        # an untitled page never inherits another entity: a subsidiary's section ends with its own pages
        # (ICICI p45 'Yield, cost and margin' sat under 'Key subsidiaries' and is the bank's own figure)
        entity_here = cur_entity if named or not cur_entity.startswith("other:") else "self"
        out.append({"entity": entity_here, "basis": cur_basis, "named": named, "inherited": not named})
        named_any_consolidated |= cur_entity == "self" and cur_basis == "consolidated"
    if named_any_consolidated:
        # a deck that prints a consolidated section AND names the company on its own elsewhere:
        # the company-named, basis-less section is the standalone one (Bajaj: 'Executive summary - Bajaj Finance')
        for tag in out:
            if tag["entity"] == "self" and tag["basis"] is None and tag["named"]:
                tag["basis"] = "standalone"
                tag["inferred_standalone"] = True
    return out
