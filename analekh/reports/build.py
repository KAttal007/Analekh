"""Build the approved draft into the file the analyst chose (owner's decision, 1 November 2026).

When the company's sector has an active Word or PowerPoint template, the approved draft is written
into it: the template's own pages, slides, styles and disclaimers stay, and in Word the content goes
where a paragraph reads exactly `{{analekh}}` (or after the template's content when there is none).
Without a template a plain default file is built. A macro template keeps its VBA part byte for byte
and gives a .docm or .pptm; the macros are never parsed or run (rule 7).

Rating, target price and guidance are left as marked blanks: a content control tagged
`analekh:<kind>` in Word, a shape named `analekh:<kind>` in PowerPoint. Citation markers are taken
out of the file; the sources stay in Analekh. Chart values become floats only here, at the Office
boundary (rule 4).
"""

import io
import re
from dataclasses import dataclass
from decimal import Decimal

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt
from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.enum.chart import XL_CHART_TYPE
from pptx.util import Inches
from pptx.util import Pt as PPt
from sqlalchemy import select
from sqlalchemy.orm import Session

from analekh.db.models import Company, ReportThread, ReportVersion, Template
from analekh.ingest.storage import ObjectStore
from analekh.reports.draft import Bullets, Chart, Draft, Heading, Paragraph, Placeholder, Table
from analekh.reports.ooxml import PackageRefused, main_content_type, set_main_content_type
from analekh.reports.store import load_draft
from analekh.reports.tag import ReportTag, write_report_tag
from analekh.templates.files import PPT, WORD, report_template_for, slug

MARKER = "{{analekh}}"
LABEL = {"rating": "Rating", "target": "Target price", "guidance": "Guidance"}
_CITE = re.compile(r"\s*\[(?:fact|kpi|filing|model|calc)\b[^\]]*\]")

_WP = "application/vnd.openxmlformats-officedocument.wordprocessingml"
_PR = "application/vnd.openxmlformats-officedocument.presentationml"
DOCX_MAIN = f"{_WP}.document.main+xml"
DOCM_MAIN = "application/vnd.ms-word.document.macroEnabled.main+xml"
WORD_MAINS = {DOCX_MAIN, DOCM_MAIN, f"{_WP}.template.main+xml", "application/vnd.ms-word.template.macroEnabled.main+xml"}
WORD_MACRO = {DOCM_MAIN, "application/vnd.ms-word.template.macroEnabled.main+xml"}
PPTX_MAIN = f"{_PR}.presentation.main+xml"
PPTM_MAIN = "application/vnd.ms-powerpoint.presentation.macroEnabled.main+xml"
PPT_MAINS = {PPTX_MAIN, PPTM_MAIN, f"{_PR}.template.main+xml", "application/vnd.ms-powerpoint.template.macroEnabled.main+xml"}
PPT_MACRO = {PPTM_MAIN, "application/vnd.ms-powerpoint.template.macroEnabled.main+xml"}

MIME = {
    ".docx": f"{_WP}.document",
    ".docm": "application/vnd.ms-word.document.macroEnabled.12",
    ".pptx": f"{_PR}.presentation",
    ".pptm": "application/vnd.ms-powerpoint.presentation.macroEnabled.12",
}


def clean(text: str) -> str:
    return _CITE.sub("", text).strip()


def _open(template: bytes | None, mains: set[str], macro_types: set[str], plain_main: str, what: str) -> tuple[io.BytesIO | None, bool]:
    if template is None:
        return None, False
    ct = main_content_type(template)
    if ct not in mains:
        raise PackageRefused(f"The {what} template is not a {what} file.")
    base = template if ct == plain_main else set_main_content_type(template, plain_main)
    return io.BytesIO(base), ct in macro_types


# --- Word -----------------------------------------------------------------------------------------


def _has_style(doc, name: str) -> bool:  # type: ignore[no-untyped-def]
    try:
        doc.styles[name]
    except KeyError:
        return False
    return True


def _heading(doc, text: str, level: int) -> None:  # type: ignore[no-untyped-def]
    if _has_style(doc, f"Heading {level}"):
        doc.add_heading(text, level=level)
    else:
        doc.add_paragraph().add_run(text).bold = True


def _sdt(kind: str):  # type: ignore[no-untyped-def]
    sdt, pr, content = OxmlElement("w:sdt"), OxmlElement("w:sdtPr"), OxmlElement("w:sdtContent")
    alias, tag = OxmlElement("w:alias"), OxmlElement("w:tag")
    alias.set(qn("w:val"), LABEL[kind])
    tag.set(qn("w:val"), f"analekh:{kind}")
    pr.append(alias)
    pr.append(tag)
    p, r, t = OxmlElement("w:p"), OxmlElement("w:r"), OxmlElement("w:t")
    t.text = f"[{LABEL[kind]}: for the analyst]"
    r.append(t)
    p.append(r)
    content.append(p)
    sdt.append(pr)
    sdt.append(content)
    return sdt


def _table(doc, header: list[str], rows: list[list[str]]) -> None:  # type: ignore[no-untyped-def]
    width = max(1, len(header), *(len(r) for r in rows))
    table = doc.add_table(rows=1 + len(rows), cols=width)
    if _has_style(doc, "Table Grid"):
        table.style = "Table Grid"
    for i, row in enumerate([header, *rows]):
        for j, cell in enumerate(row):
            table.cell(i, j).text = clean(cell)


def build_docx(draft: Draft, template: bytes | None) -> bytes:
    source, macro = _open(template, WORD_MAINS, WORD_MACRO, DOCX_MAIN, "Word")
    doc = Document(source) if source else Document()
    body = doc.element.body
    existing = list(body)  # held so element identity stays stable below
    seen = {id(e) for e in existing}
    marker = next((p for p in doc.paragraphs if p.text.strip() == MARKER), None)
    bullet_style = "List Bullet" if _has_style(doc, "List Bullet") else None
    for unit in draft.units:
        _heading(doc, clean(unit.title), 1)
        for b in unit.blocks:
            if isinstance(b, Heading):
                _heading(doc, clean(b.text), min(b.level + 1, 4))
            elif isinstance(b, Paragraph):
                doc.add_paragraph(clean(b.text))
            elif isinstance(b, Bullets):
                for item in b.items:
                    doc.add_paragraph(clean(item), style=bullet_style) if bullet_style else doc.add_paragraph("• " + clean(item))
            elif isinstance(b, Table):
                _table(doc, b.header, b.rows)
            elif isinstance(b, Chart):
                run = doc.add_paragraph().add_run(clean(b.title))
                run.bold, run.font.size = True, Pt(10)
                _table(doc, ["", *b.labels], [[s.name, *s.values] for s in b.series])
            elif isinstance(b, Placeholder):
                anchor = doc.add_paragraph()
                anchor._p.addprevious(_sdt(b.kind))
                anchor._p.getparent().remove(anchor._p)
    if marker is not None:
        added = [e for e in body if id(e) not in seen and e.tag != qn("w:sectPr")]
        for e in added:
            marker._p.addprevious(e)
        marker._p.getparent().remove(marker._p)
    out = io.BytesIO()
    doc.save(out)
    data = out.getvalue()
    return set_main_content_type(data, DOCM_MAIN) if macro else data


# --- PowerPoint -----------------------------------------------------------------------------------


def _layout(prs):  # type: ignore[no-untyped-def]
    by_name = {layout.name: layout for layout in prs.slide_layouts}
    for name in ("Title Only", "Title and Content"):
        if name in by_name:
            return by_name[name]
    return prs.slide_layouts[len(prs.slide_layouts) - 1]


def _box(slide, left, top, width, height, text: str, *, name: str | None = None, size: int = 14):  # type: ignore[no-untyped-def]
    shape = slide.shapes.add_textbox(left, top, width, height)
    if name:
        shape.name = name
    tf = shape.text_frame
    tf.word_wrap = True
    for i, line in enumerate(text.split("\n")):
        para = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        para.text = line
        para.font.size = PPt(size)
    return shape


def build_pptx(draft: Draft, template: bytes | None) -> bytes:
    source, macro = _open(template, PPT_MAINS, PPT_MACRO, PPTX_MAIN, "PowerPoint")
    prs = Presentation(source) if source else Presentation()
    layout = _layout(prs)
    margin = Inches(0.5)
    width = prs.slide_width - 2 * margin
    for unit in draft.units:
        slide = prs.slides.add_slide(layout)
        if slide.shapes.title is not None:
            slide.shapes.title.text = clean(unit.title)
        else:
            _box(slide, margin, Inches(0.3), width, Inches(0.8), clean(unit.title), size=28)
        y: int = Inches(1.4)
        for b in unit.blocks:
            if isinstance(b, Heading | Paragraph):
                h = Inches(0.5)
                _box(slide, margin, y, width, h, clean(b.text), size=16 if isinstance(b, Heading) else 14)
            elif isinstance(b, Bullets):
                h = Inches(0.35 * max(len(b.items), 1))
                _box(slide, margin, y, width, h, "\n".join("• " + clean(i) for i in b.items))
            elif isinstance(b, Table):
                cols = max(1, len(b.header), *(len(r) for r in b.rows))
                h = Inches(0.35 * (len(b.rows) + 1))
                table = slide.shapes.add_table(len(b.rows) + 1, cols, margin, y, width, h).table
                for i, row in enumerate([b.header, *b.rows]):
                    for j, cell in enumerate(row):
                        table.cell(i, j).text = clean(cell)
            elif isinstance(b, Chart):
                data = CategoryChartData()
                data.categories = [clean(x) for x in b.labels]
                for s in b.series:
                    data.add_series(clean(s.name), [float(Decimal(v)) for v in s.values])
                kind = XL_CHART_TYPE.COLUMN_CLUSTERED if b.chart_type == "bar" else XL_CHART_TYPE.LINE_MARKERS
                h = Inches(3)
                chart = slide.shapes.add_chart(kind, margin, y, width, h, data).chart
                chart.has_title = True
                chart.chart_title.text_frame.text = clean(b.title)
            elif isinstance(b, Placeholder):
                h = Inches(0.5)
                _box(slide, margin, y, width, h, f"[{LABEL[b.kind]}: for the analyst]", name=f"analekh:{b.kind}")
            else:
                continue
            y += h + Inches(0.15)
    out = io.BytesIO()
    prs.save(out)
    data_out = out.getvalue()
    return set_main_content_type(data_out, PPTM_MAIN) if macro else data_out


# --- the thread's file ----------------------------------------------------------------------------


@dataclass(frozen=True)
class BuiltFile:
    data: bytes
    filename: str
    mime: str
    template_id: int | None


def approved_version(db: Session, thread: ReportThread) -> ReportVersion:
    row = db.scalars(select(ReportVersion).where(ReportVersion.thread_id == thread.id, ReportVersion.trigger == "approved").order_by(ReportVersion.version_no.desc())).first()
    if row is None:
        raise LookupError("the thread has no approved version")
    return row


def build_file(db: Session, store: ObjectStore, thread: ReportThread) -> BuiltFile:
    """The approved draft as the thread's file, on the sector's template when one is active."""
    version = approved_version(db, thread)
    draft = load_draft(db, store, thread, version.version_no)
    company = db.get(Company, thread.company_id)
    assert company is not None
    word = thread.format == "word"
    template: Template | None = report_template_for(db, WORD if word else PPT, company.sector)
    raw = store.get(template.storage_key) if template else None
    data = build_docx(draft, raw) if word else build_pptx(draft, raw)
    macro = main_content_type(data) in (WORD_MACRO | PPT_MACRO)
    ext = (".docm" if macro else ".docx") if word else (".pptm" if macro else ".pptx")
    data = write_report_tag(data, ReportTag(thread.id, version.version_no))
    when = thread.quarter_end.isoformat() if thread.quarter_end else "latest"
    name = f"{slug(company.nse_symbol)}-{thread.report_type}-{when}{ext}"
    return BuiltFile(data, name, MIME[ext], template.id if template else None)
