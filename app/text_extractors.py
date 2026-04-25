from __future__ import annotations
from typing import Tuple
import io
import os

def extract_text(filename: str, content: bytes) -> Tuple[str, str]:
    lower = filename.lower()
    if lower.endswith(".pdf"):
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(content))
        pages = [(p.extract_text() or "") for p in reader.pages]
        return "\n".join(pages), "pdf"
    if lower.endswith(".docx"):
        from docx import Document as DocxDocument
        doc = DocxDocument(io.BytesIO(content))
        return "\n".join([p.text for p in doc.paragraphs]), "docx"
    if lower.endswith(".txt") or lower.endswith(".md"):
        return content.decode("utf-8", errors="ignore"), "text"
    if lower.endswith(".csv"):
        # Use built-in csv to be lightweight
        text = content.decode("utf-8", errors="ignore")
        return text, "csv"
    raise ValueError(f"Unsupported file type: '{os.path.splitext(filename)[1]}'. Only PDF and DOCX are supported.")
