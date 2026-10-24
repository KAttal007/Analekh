"""Hidden tag (design doc 13.2): after the first link, the model ID and company symbol are written
into the workbook's custom document properties, so renames and moves keep working."""

import os
import uuid
import xml.etree.ElementTree as ET  # nosemgrep: DOCTYPE/ENTITY are refused before any parse
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from openpyxl import Workbook
from openpyxl.packaging.custom import StringProperty

MODEL_ID = "analekh_model_id"
SYMBOL = "analekh_symbol"


@dataclass(frozen=True)
class Tag:
    model_id: uuid.UUID
    symbol: str


def read_tag(wb: Workbook) -> Tag | None:
    props = {p.name: p.value for p in wb.custom_doc_props.props}
    if MODEL_ID not in props or SYMBOL not in props:
        return None
    try:
        return Tag(uuid.UUID(str(props[MODEL_ID])), str(props[SYMBOL]))
    except ValueError:
        return None


def write_tag(wb: Workbook, tag: Tag) -> None:
    for name in (MODEL_ID, SYMBOL):
        if name in wb.custom_doc_props.names:
            del wb.custom_doc_props[name]
    wb.custom_doc_props.append(StringProperty(name=MODEL_ID, value=str(tag.model_id)))
    wb.custom_doc_props.append(StringProperty(name=SYMBOL, value=tag.symbol))


class WorkbookLocked(Exception):
    """The file on disk cannot be replaced: another program (usually Excel) has it open."""


_CUSTOM = "docProps/custom.xml"
_CT = "[Content_Types].xml"
_RELS = "_rels/.rels"
_NS_PROPS = "http://schemas.openxmlformats.org/officeDocument/2006/custom-properties"
_NS_VT = "http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes"
_NS_CT = "http://schemas.openxmlformats.org/package/2006/content-types"
_NS_REL = "http://schemas.openxmlformats.org/package/2006/relationships"
_REL_TYPE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/custom-properties"
_CT_TYPE = "application/vnd.openxmlformats-officedocument.custom-properties+xml"
_FMTID = "{D5CDD505-2E9C-101B-9397-08002B2CF9AE}"


def _parse(data: bytes) -> ET.Element:
    # Package parts never carry a DTD; refusing one rules out entity-expansion tricks.
    head = data[:4096].upper()
    if b"<!DOCTYPE" in head or b"<!ENTITY" in head:
        raise ValueError("unexpected DTD in workbook part")
    return ET.fromstring(data)


def _dump(root: ET.Element) -> bytes:
    return ET.tostring(root, encoding="UTF-8", xml_declaration=True)


def _custom_part(existing: bytes | None, tag: Tag) -> bytes:
    ET.register_namespace("", _NS_PROPS)
    ET.register_namespace("vt", _NS_VT)
    root = _parse(existing) if existing else ET.Element(f"{{{_NS_PROPS}}}Properties")
    pids = [1]
    for prop in list(root):
        if prop.get("name") in (MODEL_ID, SYMBOL):
            root.remove(prop)
        else:
            pids.append(int(prop.get("pid", "1")))
    for offset, (name, value) in enumerate(((MODEL_ID, str(tag.model_id)), (SYMBOL, tag.symbol))):
        prop = ET.SubElement(
            root,
            f"{{{_NS_PROPS}}}property",
            {"fmtid": _FMTID, "pid": str(max(pids) + 1 + offset), "name": name},
        )
        ET.SubElement(prop, f"{{{_NS_VT}}}lpwstr").text = value
    return _dump(root)


def _content_types(data: bytes) -> bytes:
    ET.register_namespace("", _NS_CT)
    root = _parse(data)
    if not any(o.get("PartName") == "/" + _CUSTOM for o in root):
        ET.SubElement(
            root, f"{{{_NS_CT}}}Override", {"PartName": "/" + _CUSTOM, "ContentType": _CT_TYPE}
        )
    return _dump(root)


def _root_rels(data: bytes) -> bytes:
    ET.register_namespace("", _NS_REL)
    root = _parse(data)
    if not any(r.get("Type") == _REL_TYPE for r in root):
        used = {r.get("Id") for r in root}
        n = 1
        while f"rId{n}" in used:
            n += 1
        ET.SubElement(
            root,
            f"{{{_NS_REL}}}Relationship",
            {"Id": f"rId{n}", "Type": _REL_TYPE, "Target": _CUSTOM},
        )
    return _dump(root)


def write_tag_file(path: Path, tag: Tag) -> None:
    """Write the tag into the file by patching three small parts of the package.

    Everything else (sheets, styles, printer settings, images, VBA) is copied byte for byte, so
    linking never changes the analyst's model beyond the hidden tag. The new file is built
    beside the original and swapped in at the end: a failure leaves the original untouched, and
    a file Excel has open raises WorkbookLocked.
    """
    tmp = path.with_name(f".{path.stem}.analekh-tmp{path.suffix}")
    try:
        try:
            zin = zipfile.ZipFile(path)
        except PermissionError as exc:  # Excel holds the file and refuses even a read
            raise WorkbookLocked(str(path)) from exc
        with zin, zipfile.ZipFile(tmp, "w") as zout:
            names = set(zin.namelist())
            for item in zin.infolist():
                data = zin.read(item)
                if item.filename == _CUSTOM:
                    data = _custom_part(data, tag)
                elif item.filename == _CT:
                    data = _content_types(data)
                elif item.filename == _RELS:
                    data = _root_rels(data)
                zout.writestr(item, data, compress_type=item.compress_type)
            if _CUSTOM not in names:
                info = zipfile.ZipInfo(_CUSTOM, datetime.now().timetuple()[:6])
                zout.writestr(info, _custom_part(None, tag), compress_type=zipfile.ZIP_DEFLATED)
        try:
            os.replace(tmp, path)
        except PermissionError as exc:
            raise WorkbookLocked(str(path)) from exc
    finally:
        tmp.unlink(missing_ok=True)
