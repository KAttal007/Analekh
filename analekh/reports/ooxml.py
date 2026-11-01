"""Office packages (.docx, .docm, .pptx, ...) read and rewritten safely, in memory.

Used for templates and for files analysts publish. Nothing is extracted to disk, nothing is opened
in Office or LibreOffice, and no macro is parsed or run (rule 7). Limits come from settings: number of
entries, expanded size, expansion ratio and size of any one part read (a zip bomb is refused before
it expands). XML is parsed without DTDs, entities or network access; a part that declares a DTD is
refused (fail closed, rule 11).
"""

import io
import re
import zipfile

from lxml import etree

from analekh.config import get_settings

CONTENT_TYPES = "[Content_Types].xml"
OLE_MAGIC = b"\xd0\xcf\x11\xe0"  # an encrypted (password-protected) Office file, or the old binary format
_PARSER = etree.XMLParser(resolve_entities=False, no_network=True, load_dtd=False, dtd_validation=False, huge_tree=False, remove_comments=True)
_DTD = re.compile(rb"<!(?:DOCTYPE|ENTITY)", re.IGNORECASE)


class PackageRefused(ValueError):
    """The file cannot be used. The message is safe to show: it never repeats file content."""


def open_package(data: bytes) -> zipfile.ZipFile:
    if data[:4] == OLE_MAGIC:
        raise PackageRefused("This file is password-protected or in an old Office format. Save it without a password as a current Office file.")
    try:
        z = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        raise PackageRefused("This is not a valid Office file.") from None
    cfg = get_settings()
    infos = z.infolist()
    if len(infos) > cfg.publish_max_entries:
        raise PackageRefused("This file has too many parts.")
    if sum(i.file_size for i in infos) > cfg.publish_max_expanded_bytes:
        raise PackageRefused("This file is too large once expanded.")
    for i in infos:
        if i.compress_size and i.file_size / i.compress_size > cfg.publish_max_ratio:
            raise PackageRefused("This file expands too far to be safe.")
        if i.flag_bits & 0x1:
            raise PackageRefused("This file is encrypted.")
    if CONTENT_TYPES not in z.namelist():
        raise PackageRefused("This is not a valid Office file.")
    return z


def read_part(z: zipfile.ZipFile, name: str) -> bytes:
    info = z.getinfo(name)
    if info.file_size > get_settings().publish_max_part_bytes:
        raise PackageRefused("A part of this file is too large.")
    return z.read(info)


def parse_xml(data: bytes) -> etree._Element:
    if _DTD.search(data):
        raise PackageRefused("This file contains a document type declaration, which is not allowed.")
    try:
        root = etree.fromstring(data, _PARSER)
    except etree.XMLSyntaxError:
        raise PackageRefused("A part of this file is not valid XML.") from None
    # The byte search above misses a DTD in a UTF-16 part; the parser does not (security review,
    # 2 November 2026). Entities are never expanded either way; this keeps the refusal promise.
    info = root.getroottree().docinfo
    if info.doctype or info.internalDTD is not None or any(isinstance(n, etree._Entity) for n in root.iter()):
        raise PackageRefused("This file contains a document type declaration, which is not allowed.")
    return root


_NS_CT = "{http://schemas.openxmlformats.org/package/2006/content-types}"


def main_content_type(data: bytes) -> str:
    """Content type of the package's main part (/word/document.xml or /ppt/presentation.xml)."""
    with open_package(data) as z:
        root = parse_xml(read_part(z, CONTENT_TYPES))
    for o in root.iter(f"{_NS_CT}Override"):
        if o.get("PartName") in ("/word/document.xml", "/ppt/presentation.xml"):
            return o.get("ContentType") or ""
    raise PackageRefused("This is not a Word or PowerPoint file.")


def set_main_content_type(data: bytes, content_type: str) -> bytes:
    with open_package(data) as z:
        root = parse_xml(read_part(z, CONTENT_TYPES))
    for o in root.iter(f"{_NS_CT}Override"):
        if o.get("PartName") in ("/word/document.xml", "/ppt/presentation.xml"):
            o.set("ContentType", content_type)
    return rewrite(data, {CONTENT_TYPES: etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)}, {})


def rewrite(data: bytes, replace: dict[str, bytes], add: dict[str, bytes]) -> bytes:
    """A copy of the package with some parts replaced and some added; every other part byte for byte."""
    out = io.BytesIO()
    with open_package(data) as zin, zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            body = replace.get(item.filename)
            zout.writestr(item, body if body is not None else zin.read(item), compress_type=zipfile.ZIP_DEFLATED)
        existing = set(zin.namelist())
        for name, body in add.items():
            if name not in existing:
                zout.writestr(name, body)
    return out.getvalue()
