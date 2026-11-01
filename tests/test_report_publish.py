"""Publishing the final file: safe reading and the publish step (Task 10, design: publish routes)."""

import io
import zipfile
from datetime import date

import pytest

from analekh.config import get_settings
from analekh.db.models import Company, PublishedFile
from analekh.reports.build import build_docx, build_pptx
from analekh.reports.draft import parse_draft
from analekh.reports.office_read import read_package
from analekh.reports.ooxml import PackageRefused, rewrite
from analekh.reports.publish import PublishRefused, publish
from analekh.reports.store import save_version
from analekh.reports.tag import ReportTag, write_report_tag
from analekh.reports.threads import create_thread

WP = "application/vnd.openxmlformats-officedocument.wordprocessingml"
VBA_REL = "http://schemas.microsoft.com/office/2006/relationships/vbaProject"


def _draft(fmt="word"):
    return parse_draft(
        {
            "schema_version": 1,
            "format": fmt,
            "units": [
                {
                    "title": "Results highlights",
                    "blocks": [
                        {"type": "paragraph", "text": "Net profit rose 12% [fact:1]."},
                        {"type": "table", "header": ["Line", "Q2"], "rows": [["Revenue", "1,200"]]},
                        {"type": "chart", "chart_type": "bar", "title": "PAT", "labels": ["Q1", "Q2"], "series": [{"name": "PAT", "values": ["190.5", "210"], "sources": ["fact:1"]}]},
                    ],
                },
                {"title": "Rating, target price and guidance", "blocks": [{"type": "placeholder", "kind": k} for k in ("rating", "target", "guidance")]},
            ],
        }
    )


def _replace_part(data: bytes, name: str, fn) -> bytes:
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        body = z.read(name)
    return rewrite(data, {name: fn(body)}, {})


# --- reading --------------------------------------------------------------------------------------


def test_word_text_tables_and_marked_areas_are_read_apart():
    data = build_docx(_draft(), None)
    data = _replace_part(data, "word/document.xml", lambda b: b.replace(b"[Rating: for the analyst]", b"Buy"))
    text = read_package(data, "final.docx")
    assert text.kind == "word" and not text.has_macros
    assert "Net profit rose 12%." in text.paragraphs
    assert ["Revenue", "1,200"] in text.tables[0]
    assert text.marked["rating"] == "Buy"
    assert not any("Buy" in p for p in text.paragraphs)


def test_powerpoint_text_named_shapes_and_chart_values_are_read():
    text = read_package(build_pptx(_draft("ppt"), None), "final.pptx")
    assert text.kind == "ppt"
    assert any("Net profit rose 12%." in p for p in text.paragraphs)
    assert text.marked["target"].startswith("[Target price")
    assert "190.5" in text.chart_values and "210.0" in text.chart_values  # PowerPoint writes floats


def test_a_password_protected_file_is_refused():
    with pytest.raises(PackageRefused, match="password"):
        read_package(b"\xd0\xcf\x11\xe0" + b"\x00" * 100, "final.docx")


def test_a_file_renamed_to_docx_is_refused():
    with pytest.raises(PackageRefused):
        read_package(build_pptx(_draft("ppt"), None), "final.docx")


def test_an_unknown_extension_is_refused():
    with pytest.raises(PackageRefused):
        read_package(build_docx(_draft(), None), "final.exe")


def test_too_many_parts_or_too_large_expanded_is_refused(monkeypatch):
    data = build_docx(_draft(), None)
    monkeypatch.setattr(get_settings(), "publish_max_entries", 3)
    with pytest.raises(PackageRefused):
        read_package(data, "final.docx")
    monkeypatch.setattr(get_settings(), "publish_max_entries", 5000)
    monkeypatch.setattr(get_settings(), "publish_max_expanded_bytes", 1000)
    with pytest.raises(PackageRefused):
        read_package(data, "final.docx")


def test_a_zip_bomb_part_is_refused_before_it_expands():
    data = build_docx(_draft(), None)
    out = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(data)) as zin, zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            zout.writestr(item.filename, zin.read(item))
        zout.writestr("word/media/bomb.bin", b"0" * 20_000_000)
    with pytest.raises(PackageRefused, match="expands"):
        read_package(out.getvalue(), "final.docx")


def test_a_dtd_or_external_entity_is_refused():
    data = build_docx(_draft(), None)
    evil = _replace_part(data, "word/document.xml", lambda b: b.replace(b"?>", b'?><!DOCTYPE w [<!ENTITY e SYSTEM "file:///etc/passwd">]>', 1))
    with pytest.raises(PackageRefused):
        read_package(evil, "final.docx")


def _docm(data: bytes) -> bytes:
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        ct = z.read("[Content_Types].xml").decode()
        rels = z.read("word/_rels/document.xml.rels").decode()
    ct = ct.replace(f"{WP}.document.main+xml", "application/vnd.ms-word.document.macroEnabled.main+xml")
    rels = rels.replace("</Relationships>", f'<Relationship Id="rIdVba" Type="{VBA_REL}" Target="vbaProject.bin"/></Relationships>')
    return rewrite(data, {"[Content_Types].xml": ct.encode(), "word/_rels/document.xml.rels": rels.encode()}, {"word/vbaProject.bin": b"<!DOCTYPE not parsed> garbage"})


def test_a_docm_is_accepted_and_its_macros_are_only_noted():
    text = read_package(_docm(build_docx(_draft(), None)), "final.docm")
    assert text.has_macros and "Net profit rose 12%." in text.paragraphs


# --- the publish step -----------------------------------------------------------------------------


@pytest.fixture
def approved(db, store, analyst):
    co = Company(nse_symbol="PUBCO", name="Pub Co Limited", isin="INE000P01011")
    db.add(co)
    db.flush()
    thread = create_thread(db, analyst.id, co.id, "quarterly", "word", "standalone", date(2026, 9, 30))
    save_version(db, store, thread, _draft(), "first_draft", 0, None)
    save_version(db, store, thread, _draft(), "approved", 1, analyst.id)
    thread.status = "approved"
    db.flush()
    return thread


def _final(thread, version=2) -> bytes:
    return write_report_tag(build_docx(_draft(), None), ReportTag(thread.id, version))


def test_a_tagged_final_file_publishes_and_is_kept_byte_for_byte(db, store, analyst, approved):
    data = _final(approved)
    row = publish(db, store, analyst.id, data, "final.docx", "upload", thread_id=approved.id)
    db.refresh(approved)
    assert approved.status == "published" and approved.published_at is not None
    assert store.get(row.storage_key) == data
    assert row.has_macros is False and row.route == "upload" and row.text_key


def test_the_add_in_route_finds_the_thread_from_the_tag(db, store, analyst, approved):
    row = publish(db, store, analyst.id, _final(approved), "final.docx", "addin")
    assert row.thread_id == approved.id


def test_no_tag_needs_the_analysts_confirmation(db, store, analyst, approved):
    untagged = build_docx(_draft(), None)
    with pytest.raises(PublishRefused) as err:
        publish(db, store, analyst.id, untagged, "final.docx", "upload", thread_id=approved.id)
    assert err.value.code == "no_tag"
    with pytest.raises(PublishRefused):
        publish(db, store, analyst.id, untagged, "final.docx", "addin")  # nothing to pick on the add-in route
    publish(db, store, analyst.id, untagged, "final.docx", "upload", thread_id=approved.id, confirmed=True)


def test_someone_elses_tag_is_refused_without_saying_whose(db, store, analyst2, approved):
    with pytest.raises(PublishRefused) as err:
        publish(db, store, analyst2.id, _final(approved), "final.docx", "addin")
    assert err.value.code == "tag_mismatch"


def test_a_tag_for_another_thread_is_refused_on_this_threads_page(db, store, analyst, approved):
    with pytest.raises(PublishRefused) as err:
        publish(db, store, analyst.id, write_report_tag(build_docx(_draft(), None), ReportTag(approved.id + 999, 1)), "final.docx", "upload", thread_id=approved.id)
    assert err.value.code == "tag_mismatch"


def test_a_thread_still_in_drafting_cannot_publish(db, store, analyst, approved):
    approved.status = "drafting"
    db.flush()
    with pytest.raises(PublishRefused) as err:
        publish(db, store, analyst.id, _final(approved), "final.docx", "upload", thread_id=approved.id)
    assert err.value.code == "not_approved"


def test_a_presentation_for_a_word_report_is_refused(db, store, analyst, approved):
    deck = write_report_tag(build_pptx(_draft("ppt"), None), ReportTag(approved.id, 2))
    with pytest.raises(PublishRefused) as err:
        publish(db, store, analyst.id, deck, "final.pptx", "upload", thread_id=approved.id)
    assert err.value.code == "wrong_format"


def test_publishing_again_keeps_both_files(db, store, analyst, approved):
    publish(db, store, analyst.id, _final(approved), "final.docx", "upload", thread_id=approved.id)
    publish(db, store, analyst.id, _docm(_final(approved)), "final-v2.docm", "upload", thread_id=approved.id)
    rows = db.query(PublishedFile).filter_by(thread_id=approved.id).order_by(PublishedFile.id).all()
    assert [r.extension for r in rows] == [".docx", ".docm"] and rows[1].has_macros


def test_a_dtd_in_a_utf16_part_is_refused_too():
    from analekh.reports.ooxml import parse_xml

    doc = '<?xml version="1.0" encoding="UTF-16"?><!DOCTYPE r [<!ENTITY e SYSTEM "file:///etc/passwd">]><r>&e;</r>'
    with pytest.raises(PackageRefused):
        parse_xml(doc.encode("utf-16"))
    assert parse_xml('<?xml version="1.0" encoding="UTF-16"?><r>fine</r>'.encode("utf-16")).text == "fine"
