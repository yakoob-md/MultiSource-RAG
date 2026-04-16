"""
backend/ingestion/legal_loader.py

Production-grade Indian Legal Document Loader.
Handles IPC, CrPC, Constitution, and Supreme Court Judgments.

Pipeline:
  PDF → raw text → clean → extract structure → structured JSON → data/legal_processed/

Run:  python -m backend.ingestion.legal_loader
"""

from __future__ import annotations

import gc
import json
import logging
import re
import sys
import traceback
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import pdfplumber

# ── Logging ───────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ── Paths ─────────────────────────────────────────────────────────────────────

BASE_DIR        = Path(__file__).resolve().parent.parent.parent
DATA_DIR        = BASE_DIR / "data"
LEGAL_RAW_DIR   = DATA_DIR / "legal_raw"
LEGAL_PROC_DIR  = DATA_DIR / "legal_processed"
STATUTES_DIR    = LEGAL_RAW_DIR / "statutes"
JUDGMENTS_SC    = LEGAL_RAW_DIR / "judgments" / "sc" / "2024"

LEGAL_PROC_DIR.mkdir(parents=True, exist_ok=True)

# ── Dataclasses ───────────────────────────────────────────────────────────────

@dataclass
class StatuteSection:
    """
    One section of a statute (IPC/CrPC/Constitution).

    Example for IPC Section 302:
      section_id  = "302"
      title       = "Punishment for murder"
      text        = "Whoever commits murder shall be punished with death,
                     or imprisonment for life, and shall also be liable
                     to fine."
      sub_sections = ["(a) ...", "(b) ..."]
      explanations = ["Explanation.—A child in the mother's womb..."]
      exceptions   = ["Exception 1.—When culpable homicide is not murder..."]
      amendments   = ["Ins. by Act 26 of 1955", "Subs. by Act 2 of 1983"]
      part         = "XVI"      # Part of IPC
      chapter      = "Homicide" # Chapter heading
    """
    section_id    : str
    title         : str
    text          : str
    sub_sections  : list[str]         = field(default_factory=list)
    explanations  : list[str]         = field(default_factory=list)
    exceptions    : list[str]         = field(default_factory=list)
    amendments    : list[str]         = field(default_factory=list)
    part          : str               = ""
    chapter       : str               = ""
    article_id    : str               = ""   # For Constitution articles


@dataclass
class StatuteDocument:
    """Structured output for IPC, CrPC, Constitution."""
    source        : str
    doc_type      : str               # "statute" | "constitution"
    full_title    : str
    year          : str
    total_sections: int
    content       : list[StatuteSection]
    parts         : list[str]         = field(default_factory=list)
    chapters      : list[str]         = field(default_factory=list)


@dataclass
class JudgmentDocument:
    """Structured output for Supreme Court judgments."""
    source        : str
    doc_type      : str               = "judgment"
    metadata      : dict[str, Any]    = field(default_factory=dict)
    content       : str               = ""
    paragraphs    : list[dict]        = field(default_factory=list)
    cited_sections: list[str]         = field(default_factory=list)
    cited_cases   : list[str]         = field(default_factory=list)


# ══════════════════════════════════════════════════════════════════════════════
# 1.  PDF LOADING
# ══════════════════════════════════════════════════════════════════════════════

def load_pdf(pdf_path: Path) -> list[str]:
    """
    Extract text from a PDF, one string per page.
    Uses pdfplumber. Falls back page-by-page to handle corrupt pages gracefully.

    Returns list of page strings. Empty string for unreadable pages.
    """
    pages: list[str] = []

    try:
        with pdfplumber.open(str(pdf_path)) as pdf:
            for page_num, page in enumerate(pdf.pages, start=1):
                try:
                    text = page.extract_text(x_tolerance=2, y_tolerance=3) or ""
                    pages.append(text)
                except Exception as exc:
                    log.warning(f"  Page {page_num} unreadable in {pdf_path.name}: {exc}")
                    pages.append("")

        log.info(f"  Loaded {len(pages)} pages from {pdf_path.name}")
        return pages

    except Exception as exc:
        log.error(f"  Cannot open {pdf_path}: {exc}")
        return []


# ══════════════════════════════════════════════════════════════════════════════
# 2.  TEXT CLEANING
# ══════════════════════════════════════════════════════════════════════════════

# Patterns compiled once for performance
_RE_PAGE_NUMBER        = re.compile(r"^\s*(?:Page\s+)?\d+\s*$", re.MULTILINE)
_RE_DOT_FILLER         = re.compile(r"\.{3,}")
_RE_DASH_FILLER        = re.compile(r"-{4,}")
_RE_AMENDMENT_FOOTNOTE = re.compile(
    r"^\s*(?:Subs\.?|Ins\.?|Rep\.?|Omitted|Added|Substituted|Inserted|"
    r"Renumbered|Amended)\s+by\s+Act.*?(?:\n|$)",
    re.MULTILINE | re.IGNORECASE,
)
_RE_FOOTNOTE_MARKER    = re.compile(r"\[[\*†‡§¶\d]{1,3}\]")
_RE_BRACKET_REF        = re.compile(r"\[\d+\]")
_RE_MULTI_NEWLINE      = re.compile(r"\n{3,}")
_RE_MULTI_SPACE        = re.compile(r"[ \t]{2,}")
_RE_LEADING_SPACES     = re.compile(r"^[ \t]+", re.MULTILINE)

# These repeated headers/footers appear in official PDFs
_KNOWN_HEADERS = [
    r"THE\s+INDIAN\s+PENAL\s+CODE",
    r"THE\s+CODE\s+OF\s+CRIMINAL\s+PROCEDURE",
    r"THE\s+CONSTITUTION\s+OF\s+INDIA",
    r"MINISTRY\s+OF\s+LAW\s+AND\s+JUSTICE",
    r"LEGISLATIVE\s+DEPARTMENT",
    r"GOVERNMENT\s+OF\s+INDIA",
    r"w\.e\.f\.\s+\d{1,2}[-./]\d{1,2}[-./]\d{2,4}",
]
_RE_KNOWN_HEADERS = re.compile(
    "|".join(_KNOWN_HEADERS), re.IGNORECASE | re.MULTILINE
)


def clean_text(raw: str, preserve_structure: bool = True) -> str:
    """
    Robust cleaning pipeline for Indian legal PDFs.

    Order matters:
      1. Remove page numbers
      2. Remove dot/dash fillers
      3. Remove amendment footnotes (keep them for amendments list elsewhere)
      4. Remove bracket references
      5. Remove repeated headers
      6. Normalize whitespace
      7. Fix broken sentences (lines that continue mid-sentence)

    preserve_structure=True keeps double newlines that separate sections.
    """
    text = raw

    # 1. Page numbers on their own line
    text = _RE_PAGE_NUMBER.sub("", text)

    # 2. Dot fillers "........" and long dash fillers
    text = _RE_DOT_FILLER.sub(" ", text)
    text = _RE_DASH_FILLER.sub("—", text)

    # 3. Amendment footnotes (lines starting with "Subs. by Act …")
    #    We remove them from body text; legal_loader extracts them separately
    text = _RE_AMENDMENT_FOOTNOTE.sub("", text)

    # 4. Footnote markers [1], [*], [†]
    text = _RE_FOOTNOTE_MARKER.sub("", text)
    text = _RE_BRACKET_REF.sub("", text)

    # 5. Known repeated headers/footers
    text = _RE_KNOWN_HEADERS.sub("", text)

    # 6. Normalize whitespace
    text = _RE_LEADING_SPACES.sub("", text)
    text = _RE_MULTI_SPACE.sub(" ", text)

    # 7. Fix broken lines: if a line ends without sentence-ending punctuation
    #    and the next line starts lowercase → merge them
    if not preserve_structure:
        lines = text.split("\n")
        merged: list[str] = []
        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                merged.append("")
                continue
            if (
                merged
                and merged[-1]
                and not merged[-1].endswith((".", "—", ":", ";", ")", "]"))
                and line
                and line[0].islower()
            ):
                merged[-1] += " " + line
            else:
                merged.append(line)
        text = "\n".join(merged)

    # 8. Collapse excessive blank lines
    if preserve_structure:
        text = _RE_MULTI_NEWLINE.sub("\n\n", text)
    else:
        text = _RE_MULTI_NEWLINE.sub("\n", text)

    return text.strip()


def extract_amendment_notes(raw: str) -> list[str]:
    """
    Pull out amendment footnotes before cleaning removes them.
    Returns list like ["Subs. by Act 26 of 1955, s. 2 (w.e.f. 1-1-1956)"]
    """
    return [
        m.group().strip()
        for m in _RE_AMENDMENT_FOOTNOTE.finditer(raw)
        if m.group().strip()
    ]


# ══════════════════════════════════════════════════════════════════════════════
# 3A.  STATUTE STRUCTURE EXTRACTION  (IPC / CrPC)
# ══════════════════════════════════════════════════════════════════════════════

# Section boundary: "302." or "302A." at start of line, followed by title
_RE_IPC_SECTION = re.compile(
    r"(?:^|\n)\s*"
    r"(?:Section\s+|Sec\.\s+|S\.\s+)?"
    r"(\d+[A-Z]{0,2})\s*[.—]\s*"
    r"([A-Z][^\n]{0,120}?)\s*[.—]\s*",
    re.MULTILINE,
)

# For bare act PDFs that just write "302. Punishment for murder—"
_RE_SECTION_BARE = re.compile(
    r"(?:^|\n)\s*(\d+[A-Z]{0,2})\.\s+([A-Z][^.\n]{3,100})[.—]",
    re.MULTILINE,
)

# Article for Constitution
_RE_ARTICLE = re.compile(
    r"(?:^|\n)\s*(?:Article|Art\.)\s+(\d+[A-Z]?)\s*[.—]\s*([^\n]{0,120})",
    re.MULTILINE,
)

# Part / Chapter headings
_RE_PART    = re.compile(r"(?:^|\n)\s*PART\s+([IVXLC\d]+)\s*[.—:]\s*([^\n]{0,80})", re.MULTILINE)
_RE_CHAPTER = re.compile(r"(?:^|\n)\s*CHAPTER\s+([IVXLC\d]+)\s*[.—:]\s*([^\n]{0,80})", re.MULTILINE)

# Sub-clauses, Explanations, Exceptions
_RE_EXPLANATION = re.compile(r"Explanation\s*[\d\w]*\s*[.—]\s*", re.IGNORECASE)
_RE_EXCEPTION   = re.compile(r"Exception\s*[\d\w]*\s*[.—]\s*", re.IGNORECASE)
_RE_PROVISO     = re.compile(r"Provided\s+that", re.IGNORECASE)


def _split_into_raw_sections(text: str, doc_type: str) -> list[tuple[str, str, str]]:
    """
    Split full document text into (section_id, section_header, section_body) tuples.
    Uses the best available regex for this doc type.

    Returns list of (id, title, body_text) tuples.
    """
    if doc_type == "constitution":
        pattern = _RE_ARTICLE
    else:
        # Try IPC section pattern first; if few matches fall back to bare
        pattern = _RE_IPC_SECTION
        matches = list(pattern.finditer(text))
        if len(matches) < 5:
            pattern = _RE_SECTION_BARE

    matches = list(pattern.finditer(text))
    if not matches:
        log.warning("    No sections found — treating whole doc as one block.")
        return [("1", "Full Text", text)]

    sections: list[tuple[str, str, str]] = []
    for i, match in enumerate(matches):
        sec_id    = match.group(1).strip()
        sec_title = match.group(2).strip().rstrip(".—-")
        start     = match.end()
        end       = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body      = text[start:end].strip()
        sections.append((sec_id, sec_title, body))

    return sections


def _parse_section_body(body: str, raw_page_text: str) -> dict:
    """
    Given the raw body of one section, extract:
      - main_text (before any Explanation/Exception)
      - sub_sections
      - explanations
      - exceptions
      - amendments (from original raw text before cleaning)
    """
    amendments   = extract_amendment_notes(raw_page_text)

    # Split off Explanations
    explanation_parts: list[str] = []
    if _RE_EXPLANATION.search(body):
        parts = _RE_EXPLANATION.split(body, maxsplit=4)
        body  = parts[0]
        explanation_parts = [p.strip() for p in parts[1:] if p.strip()]

    # Split off Exceptions
    exception_parts: list[str] = []
    if _RE_EXCEPTION.search(body):
        parts = _RE_EXCEPTION.split(body, maxsplit=4)
        body  = parts[0]
        exception_parts = [p.strip() for p in parts[1:] if p.strip()]

    # Detect sub-clauses like (a), (b), (i), (ii)
    sub_clause_re = re.compile(r"\n\s*\([a-z]{1,2}\)\s+|\n\s*\([ivx]+\)\s+", re.IGNORECASE)
    sub_parts     = sub_clause_re.split(body)
    main_text     = sub_parts[0].strip()
    sub_sections  = [s.strip() for s in sub_parts[1:] if s.strip()]

    return {
        "main_text"   : main_text,
        "sub_sections": sub_sections,
        "explanations": explanation_parts,
        "exceptions"  : exception_parts,
        "amendments"  : amendments,
    }


def extract_parts_and_chapters(text: str) -> dict[str, list[str]]:
    """Extract Part and Chapter headings for navigation metadata."""
    parts    = [f"PART {m.group(1)}: {m.group(2).strip()}" for m in _RE_PART.finditer(text)]
    chapters = [f"CHAPTER {m.group(1)}: {m.group(2).strip()}" for m in _RE_CHAPTER.finditer(text)]
    return {"parts": parts, "chapters": chapters}


def _infer_part_chapter(section_id: str, part_chapter_map: list[tuple]) -> tuple[str, str]:
    """
    Given sorted list of (start_section_int, part, chapter) tuples,
    find which Part/Chapter this section_id falls under.
    """
    try:
        sid_int = int(re.match(r"\d+", section_id).group())
    except (AttributeError, ValueError):
        return "", ""

    current_part, current_chapter = "", ""
    for (boundary, part, chapter) in part_chapter_map:
        if sid_int >= boundary:
            current_part    = part
            current_chapter = chapter
        else:
            break
    return current_part, current_chapter


# ══════════════════════════════════════════════════════════════════════════════
# 3B.  JUDGMENT STRUCTURE EXTRACTION
# ══════════════════════════════════════════════════════════════════════════════

# Typical SC judgment first page patterns
_RE_COURT_NAME  = re.compile(
    r"(IN\s+THE\s+SUPREME\s+COURT\s+OF\s+INDIA"
    r"|IN\s+THE\s+HIGH\s+COURT\s+OF\s+[A-Z\s]+"
    r"|IN\s+THE\s+COURT\s+OF\s+[A-Z\s]+)",
    re.IGNORECASE,
)
_RE_CASE_TITLE  = re.compile(
    r"([A-Z][A-Za-z\s,\.]+)\s+[Vv](?:s?\.?|ersus)\s+([A-Z][A-Za-z\s,\.&]+)",
)
_RE_DATE        = re.compile(
    r"\b(\d{1,2}(?:st|nd|rd|th)?\s+(?:January|February|March|April|May|June|"
    r"July|August|September|October|November|December)\s+\d{4}"
    r"|\d{1,2}[-/]\d{1,2}[-/]\d{2,4})\b",
    re.IGNORECASE,
)
_RE_BENCH       = re.compile(
    r"(?:BENCH|CORAM|BEFORE)[:\s]+([^\n]{10,200})", re.IGNORECASE
)
_RE_PARA_NUM    = re.compile(r"^\s*(\d+)\.\s+", re.MULTILINE)
_RE_IPC_REF     = re.compile(
    r"\b(?:Section|Sec\.|S\.)\s*(\d+[A-Z]?)\s*(?:of\s+(?:the\s+)?IPC|I\.P\.C\.?)?",
    re.IGNORECASE,
)
_RE_CASE_CITE   = re.compile(
    r"\((\d{4})\)\s+\d+\s+SCC\s+\d+"          # (2019) 5 SCC 1
    r"|\bAIR\s+\d{4}\s+SC\s+\d+"              # AIR 1994 SC 1349
    r"|\d{4}\s+SCC\s+\(Cri\)\s+\d+"           # 2021 SCC (Cri) 123
    r"|\(\d{4}\)\s+\d+\s+SCR\s+\d+",          # (2020) 3 SCR 200
    re.IGNORECASE,
)
_RE_WRIT        = re.compile(
    r"\b(Civil\s+Appeal|Criminal\s+Appeal|Writ\s+Petition|SLP|"
    r"Special\s+Leave\s+Petition|Review\s+Petition)\s+"
    r"(?:No\.?|Number)?\s*(\d+[-/]?\d*)\s+of\s+(\d{4})",
    re.IGNORECASE,
)


def extract_judgment_metadata(first_two_pages: str) -> dict[str, Any]:
    """
    Extract structured metadata from the first 1-2 pages of a judgment.

    Returns dict with: case_name, petitioner, respondent, court, date,
    bench, writ_details, citation
    """
    meta: dict[str, Any] = {
        "case_name"   : "",
        "petitioner"  : "",
        "respondent"  : "",
        "court"       : "",
        "date"        : "",
        "bench"       : "",
        "writ_details": "",
        "citation"    : "",
        "year"        : "",
    }

    # Court name
    court_m = _RE_COURT_NAME.search(first_two_pages)
    if court_m:
        meta["court"] = court_m.group(1).strip()

    # Case title (Party vs Party)
    case_m = _RE_CASE_TITLE.search(first_two_pages)
    if case_m:
        meta["petitioner"] = case_m.group(1).strip()
        meta["respondent"] = case_m.group(2).strip()
        meta["case_name"]  = f"{meta['petitioner']} v. {meta['respondent']}"

    # Date
    date_matches = _RE_DATE.findall(first_two_pages)
    if date_matches:
        meta["date"] = date_matches[0]
        year_m = re.search(r"\d{4}", meta["date"])
        if year_m:
            meta["year"] = year_m.group()

    # Bench
    bench_m = _RE_BENCH.search(first_two_pages)
    if bench_m:
        meta["bench"] = bench_m.group(1).strip()

    # Writ / SLP details
    writ_m = _RE_WRIT.search(first_two_pages)
    if writ_m:
        meta["writ_details"] = writ_m.group(0).strip()

    # Citation (SCC/AIR etc.)
    cite_matches = _RE_CASE_CITE.findall(first_two_pages)
    if cite_matches:
        meta["citation"] = cite_matches[0] if isinstance(cite_matches[0], str) else cite_matches[0][0]

    return meta


def extract_cited_references(full_text: str) -> dict[str, list[str]]:
    """
    Extract all IPC sections and case citations mentioned in the judgment.
    Useful for building a citation graph later.
    """
    ipc_refs  = list({m.group(1) for m in _RE_IPC_REF.finditer(full_text)})
    case_refs = list({m.group(0) for m in _RE_CASE_CITE.finditer(full_text)})
    return {
        "cited_ipc_sections": sorted(ipc_refs, key=lambda x: int(re.match(r"\d+", x).group())),
        "cited_cases"        : case_refs[:50],  # cap at 50
    }


def split_judgment_into_paragraphs(text: str) -> list[dict]:
    """
    Split judgment body into numbered paragraphs.
    Judgments use para numbers like:
      "1. The brief facts of the case..."
      "2. The learned counsel for the appellant..."

    Returns list of {"para_num": int, "text": str}
    """
    para_matches = list(_RE_PARA_NUM.finditer(text))
    if not para_matches:
        # No numbered paragraphs — chunk by double newlines
        blocks = [b.strip() for b in re.split(r"\n{2,}", text) if b.strip()]
        return [{"para_num": i + 1, "text": b} for i, b in enumerate(blocks)]

    paragraphs: list[dict] = []
    for i, match in enumerate(para_matches):
        para_num = int(match.group(1))
        start    = match.end()
        end      = para_matches[i + 1].start() if i + 1 < len(para_matches) else len(text)
        para_text = text[start:end].strip()
        if para_text:
            paragraphs.append({"para_num": para_num, "text": para_text})

    return paragraphs


# ══════════════════════════════════════════════════════════════════════════════
# 4.  PROCESS STATUTE  (IPC / CrPC / Constitution)
# ══════════════════════════════════════════════════════════════════════════════

def process_statute(pdf_path: Path) -> StatuteDocument | None:
    """
    Full pipeline for IPC, CrPC, Constitution PDFs.

    Returns structured StatuteDocument or None on failure.
    """
    stem     = pdf_path.stem.lower()
    doc_type = "constitution" if "constitution" in stem else "statute"

    log.info(f"Processing statute: {pdf_path.name}")
    pages = load_pdf(pdf_path)
    if not pages:
        return None

    # ── Assemble full raw text (needed for amendment extraction before cleaning)
    raw_full = "\n".join(pages)

    # ── Extract Part / Chapter map from RAW text (structure survives cleaning)
    pc_data = extract_parts_and_chapters(raw_full)

    # ── Clean
    cleaned_pages = [clean_text(p, preserve_structure=True) for p in pages]
    clean_full    = "\n".join(cleaned_pages)

    # ── Split into sections
    raw_sections = _split_into_raw_sections(clean_full, doc_type)
    log.info(f"    Found {len(raw_sections)} sections/articles")

    # ── Build Part/Chapter lookup: list of (section_int, part, chapter)
    # (simplified: assign based on known IPC part boundaries)
    ipc_part_boundaries = _build_ipc_part_map() if "ipc" in stem else []

    # ── Parse each section
    statute_sections: list[StatuteSection] = []
    for (sec_id, sec_title, sec_body) in raw_sections:
        parsed = _parse_section_body(sec_body, raw_full)
        part, chapter = _infer_part_chapter(sec_id, ipc_part_boundaries)

        s = StatuteSection(
            section_id   = sec_id,
            title        = sec_title,
            text         = parsed["main_text"],
            sub_sections = parsed["sub_sections"],
            explanations = parsed["explanations"],
            exceptions   = parsed["exceptions"],
            amendments   = parsed["amendments"],
            part         = part,
            chapter      = chapter,
            article_id   = sec_id if doc_type == "constitution" else "",
        )
        statute_sections.append(s)

    # ── Infer full title from filename
    title_map = {
        "ipc"         : "The Indian Penal Code, 1860",
        "crpc"        : "The Code of Criminal Procedure, 1973",
        "constitution": "The Constitution of India",
    }
    full_title = next((v for k, v in title_map.items() if k in stem), pdf_path.stem)
    year_m     = re.search(r"_(\d{4})", stem)
    year       = year_m.group(1) if year_m else ""

    return StatuteDocument(
        source        = pdf_path.stem,
        doc_type      = doc_type,
        full_title    = full_title,
        year          = year,
        total_sections= len(statute_sections),
        content       = statute_sections,
        parts         = pc_data["parts"],
        chapters      = pc_data["chapters"],
    )


def _build_ipc_part_map() -> list[tuple]:
    """
    IPC is divided into 23 chapters. This maps section ranges to chapters.
    Source: IPC Chapter headings (official text).
    Returns sorted list of (start_section_int, part_label, chapter_label).
    """
    return sorted([
        (1,   "", "Chapter I: Introduction"),
        (40,  "", "Chapter II: General Explanations"),
        (53,  "", "Chapter III: Punishments"),
        (75,  "", "Chapter IV: General Exceptions"),
        (107, "", "Chapter V: Abetment"),
        (120, "", "Chapter VA: Criminal Conspiracy"),
        (121, "", "Chapter VI: Offences Against the State"),
        (141, "", "Chapter VIII: Offences Against Public Tranquillity"),
        (161, "", "Chapter IX: Offences by or relating to Public Servants"),
        (191, "", "Chapter XI: False Evidence"),
        (221, "", "Chapter XII: Offences relating to Coin and Stamps"),
        (255, "", "Chapter XIII: Offences relating to Weights and Measures"),
        (268, "", "Chapter XIV: Offences affecting Public Health"),
        (279, "", "Chapter XV: Offences relating to Religion"),
        (291, "", "Chapter XVI: Offences affecting Human Body"),
        (378, "", "Chapter XVII: Offences against Property"),
        (425, "", "Chapter XVIII: Offences relating to Documents"),
        (489, "", "Chapter XIX: Criminal Breach of Contracts"),
        (493, "", "Chapter XX: Offences relating to Marriage"),
        (499, "", "Chapter XXI: Defamation"),
        (503, "", "Chapter XXII: Criminal Intimidation"),
        (510, "", "Chapter XXIII: Attempts"),
    ])


# ══════════════════════════════════════════════════════════════════════════════
# 5.  PROCESS JUDGMENT
# ══════════════════════════════════════════════════════════════════════════════

def process_judgment(pdf_path: Path) -> JudgmentDocument | None:
    """
    Full pipeline for Supreme Court judgment PDFs.

    Returns structured JudgmentDocument or None on failure.
    """
    log.info(f"Processing judgment: {pdf_path.name}")
    pages = load_pdf(pdf_path)
    if not pages:
        return None

    raw_full = "\n".join(pages)

    # ── Extract metadata from first 2 pages before cleaning
    first_pages_raw = "\n".join(pages[:2])
    metadata        = extract_judgment_metadata(first_pages_raw)

    # ── Clean all pages
    cleaned_pages = [clean_text(p, preserve_structure=False) for p in pages]
    clean_full    = "\n".join(cleaned_pages)

    # ── Extract cited references from cleaned text
    refs = extract_cited_references(clean_full)

    # ── Split into paragraphs
    paragraphs = split_judgment_into_paragraphs(clean_full)
    log.info(f"    Metadata: {metadata.get('case_name','(no title)')} | "
             f"{len(paragraphs)} paragraphs | "
             f"{len(refs['cited_ipc_sections'])} IPC refs")

    # ── Build source name: prefer case title, fall back to filename
    if metadata.get("case_name"):
        words  = re.sub(r"[^A-Za-z0-9\s]", "", metadata["case_name"]).split()
        source = "_".join(words[:6]).lower()
    else:
        source = pdf_path.stem

    return JudgmentDocument(
        source        = source,
        doc_type      = "judgment",
        metadata      = metadata,
        content       = clean_full,
        paragraphs    = paragraphs,
        cited_sections= refs["cited_ipc_sections"],
        cited_cases   = refs["cited_cases"],
    )


# ══════════════════════════════════════════════════════════════════════════════
# 6.  OUTPUT  — Serialise to JSON
# ══════════════════════════════════════════════════════════════════════════════

def save_statute_json(doc: StatuteDocument, out_dir: Path) -> Path:
    """Serialise StatuteDocument → JSON, return output path."""
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{doc.source}.json"

    # Convert dataclasses to dicts
    data = {
        "source"        : doc.source,
        "doc_type"      : doc.doc_type,
        "full_title"    : doc.full_title,
        "year"          : doc.year,
        "total_sections": doc.total_sections,
        "parts"         : doc.parts,
        "chapters"      : doc.chapters,
        "content"       : [asdict(s) for s in doc.content],
    }

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    log.info(f"    Saved → {out_path.name}  ({out_path.stat().st_size // 1024}KB)")
    return out_path


def save_judgment_json(doc: JudgmentDocument, out_dir: Path) -> Path:
    """Serialise JudgmentDocument → JSON, return output path."""
    out_dir.mkdir(parents=True, exist_ok=True)
    safe_name = re.sub(r"[^\w\-]", "_", doc.source)[:80]
    out_path  = out_dir / f"{safe_name}.json"

    data = {
        "source"        : doc.source,
        "doc_type"      : doc.doc_type,
        "metadata"      : doc.metadata,
        "cited_sections": doc.cited_sections,
        "cited_cases"   : doc.cited_cases,
        "total_paras"   : len(doc.paragraphs),
        "paragraphs"    : doc.paragraphs,
        "content"       : doc.content,         # full text as fallback
    }

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    log.info(f"    Saved → {out_path.name}  ({out_path.stat().st_size // 1024}KB)")
    return out_path


# ══════════════════════════════════════════════════════════════════════════════
# 7.  MAIN ORCHESTRATOR
# ══════════════════════════════════════════════════════════════════════════════

def run_pipeline() -> dict[str, Any]:
    """
    Process all documents in:
      data/legal_raw/statutes/
      data/legal_raw/judgments/sc/2024/

    Saves JSON to data/legal_processed/
    Returns summary dict.
    """
    stats = {
        "statutes_ok"  : 0,
        "statutes_fail": 0,
        "judgments_ok" : 0,
        "judgments_fail": 0,
        "errors"       : [],
    }

    statute_out  = LEGAL_PROC_DIR / "statutes"
    judgment_out = LEGAL_PROC_DIR / "judgments" / "sc" / "2024"

    # ── Process statutes
    statute_pdfs = sorted(STATUTES_DIR.glob("*.pdf"))
    log.info(f"═══ Found {len(statute_pdfs)} statute PDFs ═══")
    for pdf_path in statute_pdfs:
        try:
            doc = process_statute(pdf_path)
            if doc:
                save_statute_json(doc, statute_out)
                stats["statutes_ok"] += 1
            else:
                stats["statutes_fail"] += 1
        except Exception as exc:
            stats["statutes_fail"] += 1
            err = f"{pdf_path.name}: {exc}"
            stats["errors"].append(err)
            log.error(f"  FAILED {err}")
            traceback.print_exc()
        finally:
            gc.collect()

    # ── Process SC judgments 2024
    judgment_pdfs = sorted(JUDGMENTS_SC.glob("*.pdf"))
    log.info(f"═══ Found {len(judgment_pdfs)} judgment PDFs ═══")
    for pdf_path in judgment_pdfs:
        try:
            doc = process_judgment(pdf_path)
            if doc:
                save_judgment_json(doc, judgment_out)
                stats["judgments_ok"] += 1
            else:
                stats["judgments_fail"] += 1
        except Exception as exc:
            stats["judgments_fail"] += 1
            err = f"{pdf_path.name}: {exc}"
            stats["errors"].append(err)
            log.error(f"  FAILED {err}")
            traceback.print_exc()
        finally:
            gc.collect()

    # ── Summary
    log.info(
        f"\n{'═'*60}\n"
        f"  Statutes : {stats['statutes_ok']} OK  /  {stats['statutes_fail']} FAILED\n"
        f"  Judgments: {stats['judgments_ok']} OK  /  {stats['judgments_fail']} FAILED\n"
        f"  Errors   : {len(stats['errors'])}\n"
        f"{'═'*60}"
    )
    if stats["errors"]:
        for e in stats["errors"]:
            log.error(f"  ✗ {e}")

    return stats


# ══════════════════════════════════════════════════════════════════════════════
# 8.  ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    log.info("Indian Legal Document Loader — starting pipeline")
    log.info(f"  Input  : {LEGAL_RAW_DIR}")
    log.info(f"  Output : {LEGAL_PROC_DIR}")

    if not STATUTES_DIR.exists() and not JUDGMENTS_SC.exists():
        log.error("Neither statutes/ nor judgments/sc/2024/ found under data/legal_raw/")
        log.error("Expected structure:")
        log.error("  data/legal_raw/statutes/ipc_1860.pdf")
        log.error("  data/legal_raw/judgments/sc/2024/case_name.pdf")
        sys.exit(1)

    result = run_pipeline()
    sys.exit(0 if result["statutes_fail"] + result["judgments_fail"] == 0 else 1)