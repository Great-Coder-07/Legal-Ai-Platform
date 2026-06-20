import io
import re
import shutil
from pathlib import Path
try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None

try:
    import pdfplumber
except ImportError:
    pdfplumber = None

try:
    import docx
except ImportError:
    docx = None

# ─── Optional OCR (only needed for scanned PDFs) ───────────────────────────

try:
    import pytesseract
except ImportError:
    pytesseract = None
tesseract_path = shutil.which("tesseract") or r"C:\Program Files\Tesseract-OCR\tesseract.exe"
if pytesseract is not None:
    pytesseract.pytesseract.tesseract_cmd = tesseract_path

try:
    from PIL import Image
    OCR_AVAILABLE = bool(
        pytesseract is not None
        and fitz is not None
        and (shutil.which("tesseract") or Path(tesseract_path).exists())
    )
except ImportError:
    OCR_AVAILABLE = False


# ─── PDF extraction ────────────────────────────────────────────────────────

def extract_text_from_pdf(file_bytes: bytes) -> tuple[str, list[str]]:
    """
    Multi-strategy PDF text extraction with structure preservation.
    Returns a tuple of (master_text_string, list_of_individual_page_strings).
    """
    # Strategy 1: Fast PyMuPDF Page-by-Page Reading
    pages_text = _extract_pages_with_pymupdf(file_bytes)
    text = "\n\n".join(pages_text)

    # Strategy 2: If text is too thin, fallback to detailed layout extraction
    if len(text.strip()) < 100:
        text = _extract_with_pdfplumber(file_bytes)
        # Split string by our double-newlines marker to reconstruct an estimated page array
        pages_text = [p.strip() for p in text.split("\n\n") if p.strip()]

    # Strategy 3: Final fallback - OCR page-by-page via Tesseract Computer Vision
    if len(text.strip()) < 100:
        text = _extract_with_ocr(file_bytes)
        pages_text = [p.strip() for p in text.split("\n\n") if p.strip()]

    return text, pages_text


def _extract_with_pymupdf(file_bytes: bytes) -> str:
    """
    Extract text using PyMuPDF in natural reading order.
    Much better for legal documents than block-based extraction.
    """
    return "\n\n".join(_extract_pages_with_pymupdf(file_bytes))


def _extract_pages_with_pymupdf(file_bytes: bytes) -> list[str]:
    pages_text = []
    if fitz is None:
        return ""
    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        for page in doc:
            text = page.get_text("text")  # 🔥 KEY FIX
            if text.strip():
                pages_text.append(text.strip())
    except Exception as e:
        print(f"[parsers] PyMuPDF failed: {e}")

    return pages_text


def _extract_with_pdfplumber(file_bytes: bytes) -> str:
    """
    Accurate extraction for complex layouts using pdfplumber.
    Falls back gracefully if a page fails.
    """
    pages_text = []
    if pdfplumber is None:
        return ""
    try:
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for page in pdf.pages:
                extracted = page.extract_text(x_tolerance=3, y_tolerance=3)
                if extracted:
                    pages_text.append(extracted.strip())
    except Exception as e:
        print(f"[parsers] pdfplumber failed: {e}")
    return "\n\n".join(pages_text)


def _extract_with_ocr(file_bytes: bytes) -> str:
    """
    OCR fallback for scanned / image-only PDFs using pytesseract.
    Renders each page as a high-resolution image before OCR.
    Requires: pip install pytesseract pillow
    """
    if not OCR_AVAILABLE:
        print("[parsers] OCR unavailable — install pytesseract and Pillow.")
        return ""

    pages_text = []
    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        for page in doc:
            # Render at 2x resolution for better OCR accuracy
            mat = fitz.Matrix(2.0, 2.0)
            pix = page.get_pixmap(matrix=mat)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            ocr_text = pytesseract.image_to_string(img, config="--psm 6")
            if ocr_text.strip():
                pages_text.append(ocr_text.strip())
    except Exception as e:
        print(f"[parsers] OCR failed: {e}")
    return "\n\n".join(pages_text)


# ─── DOCX extraction ───────────────────────────────────────────────────────

def extract_text_from_docx(file_bytes: bytes) -> str:
    """
    Extract text from Word documents, preserving paragraph structure.
    Skips empty paragraphs to avoid blank-line noise.
    """
    if docx is None:
        raise ValueError("DOCX support is unavailable because python-docx is not installed.")
    doc = docx.Document(io.BytesIO(file_bytes))
    paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    return "\n\n".join(paragraphs)


# ─── Text cleaning ─────────────────────────────────────────────────────────

def clean_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # 🔥 CRITICAL: join broken sentences
    text = re.sub(r"\n(?=[a-z])", " ", text)

    # 🔥 fix broken uppercase headings
    text = re.sub(r"([A-Z])\n([A-Z])", r"\1 \2", text)

    # preserve paragraph breaks
    text = re.sub(r"\n{3,}", "\n\n", text)

    # spacing cleanup
    text = re.sub(r"[^\S\n]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)

    # remove page artifacts
    text = re.sub(r"(?i)(page\s+\d+\s+of\s+\d+|\-\s*\d+\s*\-)", "", text)

    return text.strip()


# ─── Main entry point ──────────────────────────────────────────────────────

def parse_document_with_pages(filename: str, file_bytes: bytes) -> tuple[str, list[str]]:
    """
    Route the uploaded file to the correct extractor, then clean the result.
    Returns a structured string with paragraph breaks intact alongside an array of pages.
    """
    ext = filename.rsplit(".", 1)[-1].lower()
    cleaned_pages = []
    raw_text = ""

    if ext == "pdf":
        # Capture both the compiled text string and the layout engine's page array list
        raw_text, raw_pages = extract_text_from_pdf(file_bytes)
        
        for page in raw_pages:
          cleaned_page = clean_text(page)
          if cleaned_page:
              cleaned_pages.append(cleaned_page)
              
    elif ext in ("doc", "docx"):
        raw_text = extract_text_from_docx(file_bytes)
        # Treat docx paragraphs as pseudo-page layout frames to ensure chunking works smoothly
        cleaned_pages = [clean_text(p) for p in raw_text.split("\n\n") if clean_text(p)]
        
    elif ext == "txt":
        raw_text = file_bytes.decode("utf-8", errors="replace")
        cleaned_pages = [clean_text(p) for p in raw_text.split("\n\n") if clean_text(p)]
        
    else:
        raise ValueError(f"Unsupported file format: .{ext}")

    cleaned = clean_text(raw_text)

    if not cleaned:
        raise ValueError(
            "No text could be extracted from this document. "
            "It may be a scanned image PDF without OCR support."
        )

    return cleaned, cleaned_pages


def parse_document(filename: str, file_bytes: bytes) -> str:
    text, _pages = parse_document_with_pages(filename, file_bytes)
    return text
