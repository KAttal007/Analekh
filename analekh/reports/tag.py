"""The report tag: which thread and version a Word or PowerPoint file was built from.

Kept in the file's custom document properties (hidden from the reader, kept by Word and PowerPoint on
save), the way workbooks are tagged (workbook/tags.py). When the analyst publishes the final file,
the tag finds its thread. A tag only points; the publish step still checks that the thread is the
signed-in user's own.
"""

from dataclasses import dataclass

from lxml import etree

from analekh.reports.ooxml import CONTENT_TYPES, open_package, parse_xml, read_part, rewrite

CUSTOM = "docProps/custom.xml"
RELS = "_rels/.rels"
PROP_THREAD = "AnalekhReportThread"
PROP_VERSION = "AnalekhReportVersion"
_NS_PROPS = "http://schemas.openxmlformats.org/officeDocument/2006/custom-properties"
_NS_VT = "http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes"
_NS_CT = "http://schemas.openxmlformats.org/package/2006/content-types"
_NS_REL = "http://schemas.openxmlformats.org/package/2006/relationships"
_REL_TYPE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/custom-properties"
_CT_TYPE = "application/vnd.openxmlformats-officedocument.custom-properties+xml"
_FMTID = "{D5CDD505-2E9C-101B-9397-08002B2CF9AE}"
_OURS = (PROP_THREAD, PROP_VERSION)


@dataclass(frozen=True)
class ReportTag:
    thread_id: int
    version_no: int


def _xml(root: etree._Element) -> bytes:
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)


def write_report_tag(data: bytes, tag: ReportTag) -> bytes:
    with open_package(data) as z:
        names = set(z.namelist())
        custom = parse_xml(read_part(z, CUSTOM)) if CUSTOM in names else etree.Element(f"{{{_NS_PROPS}}}Properties", nsmap={None: _NS_PROPS, "vt": _NS_VT})
        types = parse_xml(read_part(z, CONTENT_TYPES))
        rels = parse_xml(read_part(z, RELS))
    pids = [1]
    for prop in list(custom):
        if prop.get("name") in _OURS:
            custom.remove(prop)
        else:
            pids.append(int(prop.get("pid", "1")) if (prop.get("pid") or "").isdigit() else 1)
    for offset, (name, value) in enumerate(((PROP_THREAD, tag.thread_id), (PROP_VERSION, tag.version_no))):
        prop = etree.SubElement(custom, f"{{{_NS_PROPS}}}property", fmtid=_FMTID, pid=str(max(pids) + 1 + offset), name=name)
        etree.SubElement(prop, f"{{{_NS_VT}}}lpwstr").text = str(value)
    if not any(o.get("PartName") == "/" + CUSTOM for o in types):
        etree.SubElement(types, f"{{{_NS_CT}}}Override", PartName="/" + CUSTOM, ContentType=_CT_TYPE)
    if not any(r.get("Type") == _REL_TYPE for r in rels):
        used = {r.get("Id") for r in rels}
        n = 1
        while f"rId{n}" in used:
            n += 1
        etree.SubElement(rels, f"{{{_NS_REL}}}Relationship", Id=f"rId{n}", Type=_REL_TYPE, Target=CUSTOM)
    replace = {CONTENT_TYPES: _xml(types), RELS: _xml(rels)}
    if CUSTOM in names:
        return rewrite(data, {**replace, CUSTOM: _xml(custom)}, {})
    return rewrite(data, replace, {CUSTOM: _xml(custom)})


def read_report_tag(data: bytes) -> ReportTag | None:
    """The tag, or None when the file has none or it is malformed. Raises PackageRefused for unsafe files."""
    with open_package(data) as z:
        if CUSTOM not in z.namelist():
            return None
        custom = parse_xml(read_part(z, CUSTOM))
    values: dict[str, str] = {}
    for prop in custom:
        name = prop.get("name")
        if name in _OURS:
            values[name] = "".join(prop.itertext()).strip()
    try:
        return ReportTag(int(values[PROP_THREAD]), int(values[PROP_VERSION]))
    except (KeyError, ValueError):
        return None
