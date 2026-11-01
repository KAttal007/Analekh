"""Building the approved draft into Word or PowerPoint, plain or on the sector template (Task 9)."""

import io
import zipfile

import pytest
from docx import Document
from pptx import Presentation

from analekh.reports.build import MARKER, build_docx, build_pptx
from analekh.reports.draft import parse_draft
from analekh.reports.ooxml import PackageRefused, main_content_type, rewrite
from analekh.reports.tag import ReportTag, read_report_tag, write_report_tag

WP = "application/vnd.openxmlformats-officedocument.wordprocessingml"
DOCM_MAIN = "application/vnd.ms-word.document.macroEnabled.main+xml"
DOTM_MAIN = "application/vnd.ms-word.template.macroEnabled.main+xml"
VBA_REL = "http://schemas.microsoft.com/office/2006/relationships/vbaProject"


def _draft(fmt: str = "word") -> object:
    return parse_draft(
        {
            "schema_version": 1,
            "format": fmt,
            "units": [
                {
                    "title": "Results highlights",
                    "blocks": [
                        {"type": "heading", "level": 1, "text": "Quarter"},
                        {"type": "paragraph", "text": "Net profit rose 12% [fact:123 filing:9 context:OneD]."},
                        {"type": "bullets", "items": ["NIM held [kpi:44]", "Costs flat"]},
                        {"type": "table", "header": ["Line", "Q2"], "rows": [["Revenue", "1,200"]]},
                        {"type": "chart", "chart_type": "bar", "title": "PAT", "labels": ["Q1", "Q2"], "series": [{"name": "PAT", "values": ["190.5", "210"], "sources": ["fact:1"]}]},
                    ],
                },
                {"title": "Rating, target price and guidance", "blocks": [{"type": "placeholder", "kind": k} for k in ("rating", "target", "guidance")]},
            ],
        }
    )


def _all_text(data: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        return z.read("word/document.xml").decode()


# --- tag ------------------------------------------------------------------------------------------


def test_tag_round_trips_and_a_missing_tag_reads_as_none():
    plain = build_docx(_draft(), None)
    assert read_report_tag(plain) is None
    tagged = write_report_tag(plain, ReportTag(thread_id=7, version_no=3))
    assert read_report_tag(tagged) == ReportTag(7, 3)
    assert read_report_tag(write_report_tag(tagged, ReportTag(8, 1))) == ReportTag(8, 1)  # replaced, not doubled
    Document(io.BytesIO(tagged))  # still opens


def test_a_tag_part_with_a_dtd_is_refused():
    plain = build_docx(_draft(), None)
    evil = b'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY e SYSTEM "file:///etc/passwd">]><Properties>&e;</Properties>'
    with zipfile.ZipFile(io.BytesIO(plain)) as z:
        names = z.namelist()
    data = rewrite(plain, {}, {"docProps/custom.xml": evil}) if "docProps/custom.xml" not in names else rewrite(plain, {"docProps/custom.xml": evil}, {})
    with pytest.raises(PackageRefused):
        read_report_tag(data)


# --- Word -----------------------------------------------------------------------------------------


def test_default_word_file_has_sections_marked_blanks_and_no_citation_markers():
    data = build_docx(_draft(), None)
    doc = Document(io.BytesIO(data))
    texts = [p.text for p in doc.paragraphs]
    assert "Results highlights" in texts
    assert any(t.startswith("Net profit rose 12%") for t in texts)
    assert not any("[fact:" in t or "[kpi:" in t for t in texts)
    xml = _all_text(data)
    for kind in ("rating", "target", "guidance"):
        assert f'w:val="analekh:{kind}"' in xml
    assert len(doc.tables) == 2  # the table and the chart's data table
    assert "vbaProject" not in str(zipfile.ZipFile(io.BytesIO(data)).namelist())


def _word_template(*paragraphs: str) -> bytes:
    doc = Document()
    for p in paragraphs:
        doc.add_paragraph(p)
    out = io.BytesIO()
    doc.save(out)
    return out.getvalue()


def test_content_goes_at_the_marker_and_the_template_is_kept():
    data = build_docx(_draft(), _word_template("Cover page", MARKER, "House disclaimer"))
    texts = [p.text for p in Document(io.BytesIO(data)).paragraphs if p.text]
    assert texts[0] == "Cover page" and texts[-1] == "House disclaimer"
    assert MARKER not in texts and "Results highlights" in texts


def test_without_a_marker_content_goes_after_the_template():
    data = build_docx(_draft(), _word_template("Cover page"))
    texts = [p.text for p in Document(io.BytesIO(data)).paragraphs if p.text]
    assert texts[0] == "Cover page" and "Results highlights" in texts[1:]


def test_a_dotx_template_gives_a_docx_document():
    tmpl = _word_template("Cover")
    dotx = rewrite(tmpl, {"[Content_Types].xml": main_swap(tmpl, f"{WP}.document.main+xml", f"{WP}.template.main+xml")}, {})
    assert main_content_type(dotx) == f"{WP}.template.main+xml"
    out = build_docx(_draft(), dotx)
    assert main_content_type(out) == f"{WP}.document.main+xml"


def _with_macros(tmpl: bytes, main: str) -> bytes:
    with zipfile.ZipFile(io.BytesIO(tmpl)) as z:
        ct = z.read("[Content_Types].xml").decode()
        rels = z.read("word/_rels/document.xml.rels").decode()
    ct = ct.replace(f"{WP}.document.main+xml", main).replace("</Types>", '<Default Extension="bin" ContentType="application/vnd.ms-office.vbaProject"/></Types>')
    rels = rels.replace("</Relationships>", f'<Relationship Id="rIdVba" Type="{VBA_REL}" Target="vbaProject.bin"/></Relationships>')
    return rewrite(tmpl, {"[Content_Types].xml": ct.encode(), "word/_rels/document.xml.rels": rels.encode()}, {"word/vbaProject.bin": b"VBA-BYTES-UNTOUCHED"})


def test_a_macro_template_keeps_its_macros_byte_for_byte_and_gives_a_docm():
    for main in (DOCM_MAIN, DOTM_MAIN):
        out = build_docx(_draft(), _with_macros(_word_template("Cover"), main))
        assert main_content_type(out) == DOCM_MAIN
        with zipfile.ZipFile(io.BytesIO(out)) as z:
            assert z.read("word/vbaProject.bin") == b"VBA-BYTES-UNTOUCHED"


def test_a_broken_template_is_refused_not_silently_replaced():
    with pytest.raises(PackageRefused):
        build_docx(_draft(), b"not a zip at all")


# --- PowerPoint -----------------------------------------------------------------------------------


def test_default_presentation_has_a_slide_per_unit_native_chart_and_named_blanks():
    data = build_pptx(_draft("ppt"), None)
    prs = Presentation(io.BytesIO(data))
    assert len(prs.slides) == 2
    shapes = list(prs.slides[0].shapes)
    assert prs.slides[0].shapes.title.text == "Results highlights"
    assert any(s.has_chart for s in shapes)
    assert any(s.has_table for s in shapes)
    names = {s.name for s in prs.slides[1].shapes}
    assert {"analekh:rating", "analekh:target", "analekh:guidance"} <= names
    all_text = " ".join(s.text_frame.text for sl in prs.slides for s in sl.shapes if s.has_text_frame)
    assert "[fact:" not in all_text


def test_a_presentation_template_keeps_its_own_slides():
    prs = Presentation()
    prs.slides.add_slide(prs.slide_layouts[0]).shapes.title.text = "House cover"
    out = io.BytesIO()
    prs.save(out)
    built = Presentation(io.BytesIO(build_pptx(_draft("ppt"), out.getvalue())))
    assert len(built.slides) == 3 and built.slides[0].shapes.title.text == "House cover"


def main_swap(data: bytes, old: str, new: str) -> bytes:
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        return z.read("[Content_Types].xml").replace(old.encode(), new.encode())
