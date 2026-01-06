from __future__ import annotations
from typing import Tuple
from pypdf import PdfReader
from docx import Document as DocxDocument
import pandas as pd
import io

def extract_text(filename: str, content: bytes) -> Tuple[str, str]:
    lower = filename.lower()
    if lower.endswith(".pdf"):
        reader = PdfReader(io.BytesIO(content))
        pages = [(p.extract_text() or "") for p in reader.pages]
        return "\n".join(pages), "pdf"
    if lower.endswith(".docx"):
        doc = DocxDocument(io.BytesIO(content))
        return "\n".join([p.text for p in doc.paragraphs]), "docx"
    if lower.endswith(".txt") or lower.endswith(".md"):
        return content.decode("utf-8", errors="ignore"), "text"
    if lower.endswith(".csv"):
        df = pd.read_csv(io.BytesIO(content))
        return df.to_csv(index=False), "csv"
    return content.decode("utf-8", errors="ignore"), "unknown"
