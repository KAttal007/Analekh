"""Template kinds and the checks on an uploaded template file.

Three kinds: the Excel financial model (read and written by our code), and the Word and PowerPoint
report templates (stored byte for byte; the report-writing model uses them, our code never parses or
writes them). Macros are never run (rule 7); a file is only listed and checked as a zip.
"""

import io
import re
import zipfile
from dataclasses import dataclass

from sqlalchemy import any_, literal, select
from sqlalchemy.orm import Session

from analekh.db.models import Template

EXCEL = "excel_model"
WORD = "word_report"
PPT = "ppt_report"
KINDS = (EXCEL, WORD, PPT)

_MAX_CONTENT_TYPES = 1024 * 1024  # [Content_Types].xml is tiny; never read more than this


@dataclass(frozen=True)
class FileType:
    kind: str
    mime: str
    main_part: str  # content type of the package's main part, as written in [Content_Types].xml
    macro_enabled: bool


_SS = "application/vnd.openxmlformats-officedocument.spreadsheetml"
_WP = "application/vnd.openxmlformats-officedocument.wordprocessingml"
_PR = "application/vnd.openxmlformats-officedocument.presentationml"

FILE_TYPES: dict[str, FileType] = {
    ".xlsx": FileType(EXCEL, f"{_SS}.sheet", f"{_SS}.sheet.main+xml", False),
    ".xlsm": FileType(EXCEL, "application/vnd.ms-excel.sheet.macroEnabled.12", "application/vnd.ms-excel.sheet.macroEnabled.main+xml", True),
    ".docx": FileType(WORD, f"{_WP}.document", f"{_WP}.document.main+xml", False),
    ".docm": FileType(WORD, "application/vnd.ms-word.document.macroEnabled.12", "application/vnd.ms-word.document.macroEnabled.main+xml", True),
    ".dotx": FileType(WORD, f"{_WP}.template", f"{_WP}.template.main+xml", False),
    ".dotm": FileType(WORD, "application/vnd.ms-word.template.macroEnabled.12", "application/vnd.ms-word.template.macroEnabled.main+xml", True),
    ".pptx": FileType(PPT, f"{_PR}.presentation", f"{_PR}.presentation.main+xml", False),
    ".pptm": FileType(PPT, "application/vnd.ms-powerpoint.presentation.macroEnabled.12", "application/vnd.ms-powerpoint.presentation.macroEnabled.main+xml", True),
    ".potx": FileType(PPT, f"{_PR}.template", f"{_PR}.template.main+xml", False),
    ".potm": FileType(PPT, "application/vnd.ms-powerpoint.template.macroEnabled.12", "application/vnd.ms-powerpoint.template.macroEnabled.main+xml", True),
}


class TemplateFileError(ValueError):
    pass


def extensions(kind: str) -> list[str]:
    return [e for e, t in FILE_TYPES.items() if t.kind == kind]


def suffix_of(filename: str | None) -> str:
    """The lower-case extension of an upload's file name (only ever compared with the allow-list)."""
    name = (filename or "").rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    return "." + name.rsplit(".", 1)[-1].lower() if "." in name else ""


def slug(name: str) -> str:
    """A template name made safe for use inside a storage key."""
    return re.sub(r"[^A-Za-z0-9_-]+", "-", name).strip("-")[:60] or "template"


def has_macro_project(data: bytes) -> bool:
    """True when the package carries a VBA project. Reads the zip listing only; nothing is run."""
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            return any(n.lower().endswith("vbaproject.bin") for n in z.namelist())
    except zipfile.BadZipFile:
        return False


def check_file(kind: str, filename: str | None, data: bytes) -> tuple[str, FileType]:
    """Refuse a file that is not what its name and the chosen kind say. Returns (suffix, type)."""
    if kind not in KINDS:
        raise TemplateFileError("unknown template kind")
    suffix = suffix_of(filename)
    ftype = FILE_TYPES.get(suffix)
    if ftype is None or ftype.kind != kind:
        raise TemplateFileError("upload " + ", ".join(extensions(kind)) + " for this kind of template")
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            info = z.getinfo("[Content_Types].xml")
            if info.file_size > _MAX_CONTENT_TYPES:
                raise TemplateFileError("not a valid Office file")
            content_types = z.read(info).decode("utf-8", "replace")
    except (zipfile.BadZipFile, KeyError) as exc:
        raise TemplateFileError("not a valid Office file") from exc
    if f'"{ftype.main_part}"' not in content_types:
        raise TemplateFileError(f"the file's contents do not match its {suffix} name; save it from Office as {suffix}")
    return suffix, ftype


def report_template_for(session: Session, kind: str, sector: str | None) -> Template | None:
    """The active Word or PowerPoint template for a sector: the newest one wins. One template
    serves flash note, note and initiation."""
    q = select(Template).where(Template.kind == kind, Template.status == "active")
    if sector:
        q = q.where(literal(sector) == any_(Template.sectors))
    return session.scalars(q.order_by(Template.id.desc())).first()
