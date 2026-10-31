"""Template kinds: file checks, macro flag, report-template storage, disable and enable."""

import io
import zipfile

import pytest

from analekh.templates.files import (
    EXCEL,
    FILE_TYPES,
    PPT,
    WORD,
    TemplateFileError,
    check_file,
    has_macro_project,
    suffix_of,
)


def package(suffix: str, macros: bool = False, content_type: str | None = None) -> bytes:
    main = content_type or FILE_TYPES[suffix].main_part
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("[Content_Types].xml", f'<Types><Override PartName="/x" ContentType="{main}"/></Types>')
        if macros:
            z.writestr("word/vbaProject.bin", b"\x00vba")
    return buf.getvalue()


@pytest.mark.parametrize("suffix", sorted(FILE_TYPES))
def test_every_accepted_extension_passes_for_its_kind(suffix: str) -> None:
    ftype = FILE_TYPES[suffix]
    assert check_file(ftype.kind, f"My Template{suffix.upper()}", package(suffix))[0] == suffix


@pytest.mark.parametrize(
    ("kind", "name"),
    [(EXCEL, "a.docx"), (WORD, "a.xlsx"), (PPT, "a.docm"), (WORD, "a.exe"), (WORD, "noext"), (EXCEL, None)],
)
def test_wrong_extension_for_kind_is_refused(kind: str, name: str | None) -> None:
    with pytest.raises(TemplateFileError):
        check_file(kind, name, package(".docx"))


def test_renamed_file_is_refused() -> None:
    # a .docx renamed to .dotm: the main part says document, not macro-enabled template
    with pytest.raises(TemplateFileError):
        check_file(WORD, "a.dotm", package(".docx"))
    with pytest.raises(TemplateFileError):
        check_file(WORD, "a.docx", b"not a zip at all")
    with pytest.raises(TemplateFileError):
        check_file("nonsense", "a.docx", package(".docx"))


def test_macro_flag_reads_the_zip_listing() -> None:
    assert has_macro_project(package(".dotm", macros=True))
    assert not has_macro_project(package(".docx"))
    assert not has_macro_project(b"junk")


def test_path_in_filename_does_not_matter() -> None:
    assert suffix_of(r"C:\x\y\Initiation.DOTM") == ".dotm"
    assert suffix_of("../../etc/passwd") == ""
