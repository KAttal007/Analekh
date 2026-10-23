"""Local PDF reading with PyMuPDF (design doc 9.1 step 1). Free and fast; no AI here."""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pymupdf

MIN_TEXT_CHARS = 40


@dataclass
class PageText:
    number: int  # 1-based, as cited to the analyst
    text: str
    ocr: bool = False

    @property
    def numeric_density(self) -> float:
        """Share of tokens that are numbers: a cheap table-likeness signal."""
        tokens = self.text.split()
        if not tokens:
            return 0.0
        numeric = sum(1 for t in tokens if re.fullmatch(r"\(?-?[\d,]+(\.\d+)?\)?%?", t))
        return numeric / len(tokens)


def read_pages(data: bytes, ocr: bool = True) -> list[PageText]:
    pages = []
    with pymupdf.open(stream=data, filetype="pdf") as doc:
        for i, page in enumerate(doc, start=1):
            text = page.get_text("text")
            if ocr and len(text.strip()) < MIN_TEXT_CHARS:
                ocr_text = _ocr(page)
                if ocr_text:
                    pages.append(PageText(i, ocr_text, ocr=True))
                    continue
            pages.append(PageText(i, text))
    return pages


def subset(data: bytes, page_numbers: list[int]) -> bytes:
    """A new PDF containing only the selected (1-based) pages, in the given order."""
    with pymupdf.open(stream=data, filetype="pdf") as src, pymupdf.open() as out:
        for n in page_numbers:
            out.insert_pdf(src, from_page=n - 1, to_page=n - 1)
        return out.tobytes()


OCR_DPI = 200
# Model routing, threads and logging for RapidOCR (see the file's header).
OCR_CONFIG = Path(__file__).with_name("rapidocr.yaml")
_engine: Any = None


def ocr_engine() -> Any:
    """The RapidOCR engine, built once per process from OCR_CONFIG. RapidOCR silently falls back
    to its own defaults when the file is missing, so a missing file is an error here."""
    global _engine
    if _engine is None:
        if not OCR_CONFIG.is_file():
            raise FileNotFoundError(OCR_CONFIG)
        from rapidocr import RapidOCR

        _engine = RapidOCR(config_path=str(OCR_CONFIG))
    return _engine


def _ocr(page: "pymupdf.Page") -> str:
    """RapidOCR fallback for scanned pages (ONNX models ship in the package; no system binary).
    Empty when OCR fails, so a bad scan never stops a document from being read."""
    try:
        result = ocr_engine()(page.get_pixmap(dpi=OCR_DPI).tobytes("png"))
        return "\n".join(result.txts or ())
    except Exception:  # noqa: BLE001 - OCR failed; the page is kept without text
        return ""
