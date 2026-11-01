"""Read the text of a published Word or PowerPoint file, safely (design: the publish step).

Only the package XML is read, through ooxml.py's limits and DTD-free parser. The file is never
opened in Office or LibreOffice, external relationships (linked images, remote templates) are never
followed, and a VBA project is noted, never parsed or run (rule 7). Text inside the marked areas for
rating, target price and guidance is kept apart, so it can always be masked before reuse (rule 8).
"""

import re
import zipfile
from dataclasses import dataclass, field

from lxml import etree

from analekh.reports.ooxml import PackageRefused, main_content_type, open_package, parse_xml, read_part
from analekh.templates.files import FILE_TYPES, PPT, WORD, suffix_of

ACCEPTED = {".docx", ".docm", ".pptx", ".pptm"}
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
P = "{http://schemas.openxmlformats.org/presentationml/2006/main}"
C = "{http://schemas.openxmlformats.org/drawingml/2006/chart}"
_SLIDE = re.compile(r"^ppt/slides/slide(\d+)\.xml$")
_CHART = re.compile(r"^(?:word|ppt)/charts/chart\d+\.xml$")


@dataclass
class PackageText:
    kind: str  # word, ppt
    extension: str
    has_macros: bool
    paragraphs: list[str] = field(default_factory=list)
    tables: list[list[list[str]]] = field(default_factory=list)
    chart_values: list[str] = field(default_factory=list)
    marked: dict[str, str] = field(default_factory=dict)  # rating, target, guidance


def _text(el: etree._Element, tag: str) -> str:
    return "".join(t.text or "" for t in el.iter(tag)).strip()


def _marked_kind(name: str | None) -> str | None:
    if name and name.startswith("analekh:"):
        kind = name.split(":", 1)[1]
        if kind in ("rating", "target", "guidance"):
            return kind
    return None


def _inside(el: etree._Element, tags: tuple[str, ...]) -> bool:
    return any(a.tag in tags for a in el.iterancestors())


def _word(z: zipfile.ZipFile, out: PackageText) -> None:
    root = parse_xml(read_part(z, "word/document.xml"))
    skip: set[etree._Element] = set()
    for sdt in root.iter(f"{W}sdt"):
        tag = sdt.find(f"{W}sdtPr/{W}tag")
        kind = _marked_kind(tag.get(f"{W}val") if tag is not None else None)
        if kind:
            content = sdt.find(f"{W}sdtContent")
            out.marked[kind] = _text(content if content is not None else sdt, f"{W}t")
            skip.update(sdt.iter(f"{W}p"))
    for tbl in root.iter(f"{W}tbl"):
        if not _inside(tbl, (f"{W}tbl",)):
            out.tables.append([[_text(tc, f"{W}t") for tc in tr.iter(f"{W}tc")] for tr in tbl.iter(f"{W}tr")])
    for p in root.iter(f"{W}p"):
        if p in skip or _inside(p, (f"{W}tbl",)):
            continue
        text = _text(p, f"{W}t")
        if text:
            out.paragraphs.append(text)


def _ppt(z: zipfile.ZipFile, out: PackageText) -> None:
    slides = sorted(((int(m.group(1)), n) for n in z.namelist() if (m := _SLIDE.match(n))), key=lambda x: x[0])
    for _, name in slides:
        root = parse_xml(read_part(z, name))
        for sp in root.iter(f"{P}sp"):
            cnv = sp.find(f"{P}nvSpPr/{P}cNvPr")
            kind = _marked_kind(cnv.get("name") if cnv is not None else None)
            text = "\n".join(t for para in sp.iter(f"{A}p") if (t := _text(para, f"{A}t")))
            if kind:
                out.marked[kind] = text
            elif text:
                out.paragraphs.append(text)
        for tbl in root.iter(f"{A}tbl"):
            out.tables.append([[_text(tc, f"{A}t") for tc in tr.iter(f"{A}tc")] for tr in tbl.iter(f"{A}tr")])


def _charts(z: zipfile.ZipFile, out: PackageText) -> None:
    for name in z.namelist():
        if _CHART.match(name):
            root = parse_xml(read_part(z, name))
            out.chart_values += [v.text.strip() for v in root.iter(f"{C}v") if v.text and v.text.strip()]


def read_package(data: bytes, filename: str | None) -> PackageText:
    suffix = suffix_of(filename)
    if suffix not in ACCEPTED:
        raise PackageRefused("Publish a .docx, .docm, .pptx or .pptm file.")
    ftype = FILE_TYPES[suffix]
    if main_content_type(data) != ftype.main_part:
        raise PackageRefused(f"The file's contents do not match its {suffix} name. Save it from Office as {suffix}.")
    with open_package(data) as z:
        has_macros = any(n.lower().endswith("vbaproject.bin") for n in z.namelist())
        out = PackageText(kind="word" if ftype.kind == WORD else "ppt", extension=suffix, has_macros=has_macros)
        if ftype.kind == WORD:
            _word(z, out)
        elif ftype.kind == PPT:
            _ppt(z, out)
        _charts(z, out)
    return out
