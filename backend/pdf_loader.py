"""
PDF / Text Loader — extracts text from PDF or plain-text files.

Priority chain for PDFs:
  1. pdfplumber  (best layout-aware extraction)
  2. pypdf       (fallback for PDFs pdfplumber can't open)
  3. OCR via pdf2image + pytesseract  (last resort for scanned/image PDFs)
"""

import os
from pathlib import Path


class PDFLoader:

    def load_pdf(self, file_path: str) -> str:
        """
        Extract text from a file.

        • .txt / .md / .tex → read directly as UTF-8 (no PDF parsing at all)
        • everything else   → try pdfplumber → pypdf → OCR
        """
        path = Path(file_path)

        # ── Plain-text / LaTeX short-circuit ─────────────────────────────
        if path.suffix.lower() in (".txt", ".md", ".rst", ".tex"):
            text = path.read_text(encoding="utf-8", errors="replace").strip()
            if not text:
                raise ValueError(f"File is empty: {file_path}")
            return text

        # ── Attempt 1: pdfplumber ─────────────────────────────────────────
        text = self._try_pdfplumber(str(path))

        # ── Attempt 2: pypdf ─────────────────────────────────────────────
        if len(text.strip()) < 80:
            text = self._try_pypdf(str(path))

        # ── Attempt 3: OCR (optional deps) ───────────────────────────────
        if len(text.strip()) < 80:
            text = self._try_ocr(str(path))

        text = text.strip()
        if not text:
            raise ValueError(f"No text could be extracted from: {file_path}")
        return text

    # ── Internal helpers ──────────────────────────────────────────────────

    def _try_pdfplumber(self, path: str) -> str:
        try:
            import pdfplumber
            out = ""
            with pdfplumber.open(path) as pdf:
                for page in pdf.pages:
                    t = page.extract_text()
                    if t:
                        out += t + "\n"
            return out
        except Exception as e:
            print(f"[pdf_loader] pdfplumber failed on '{path}': {e}")
            return ""

    def _try_pypdf(self, path: str) -> str:
        try:
            from pypdf import PdfReader
            reader = PdfReader(path)
            out = ""
            for page in reader.pages:
                t = page.extract_text()
                if t:
                    out += t + "\n"
            return out
        except ImportError:
            pass  # pypdf not installed — skip silently
        except Exception as e:
            print(f"[pdf_loader] pypdf failed on '{path}': {e}")
        return ""

    def _try_ocr(self, path: str) -> str:
        print(f"[pdf_loader] Attempting OCR fallback for '{path}'")
        try:
            from pdf2image import convert_from_path
            import pytesseract

            poppler = os.getenv("POPPLER_PATH")
            images = convert_from_path(path, poppler_path=poppler)
            return "\n".join(pytesseract.image_to_string(img) for img in images)
        except ImportError:
            print("[pdf_loader] OCR deps not installed (pdf2image / pytesseract) — skipping.")
        except Exception as e:
            print(f"[pdf_loader] OCR failed: {e}")
        return ""
