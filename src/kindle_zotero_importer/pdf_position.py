from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
import re
import shutil
import subprocess
import tempfile
import unicodedata
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any


_TOOL_PATHS = {
    "pdftotext": (str(Path.home() / "bin" / "pdftotext"), "/opt/homebrew/bin/pdftotext"),
    "pdftohtml": (str(Path.home() / "bin" / "pdftohtml"), "/opt/homebrew/bin/pdftohtml"),
    "pdfinfo": (str(Path.home() / "bin" / "pdfinfo"), "/opt/homebrew/bin/pdfinfo"),
    "qpdf": (str(Path.home() / "bin" / "qpdf"), "/opt/homebrew/bin/qpdf"),
}


def _tool(name: str) -> str:
    resolved = shutil.which(name)
    if resolved:
        return resolved
    for candidate in _TOOL_PATHS.get(name, ()):
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return name


def _missing_required_tools() -> list[str]:
    missing = []
    for name in ("pdftotext", "pdftohtml", "pdfinfo"):
        path = _tool(name)
        if path == name and shutil.which(name) is None:
            missing.append(name)
    return missing


@dataclass(frozen=True)
class PDFWord:
    text: str
    left: float
    top: float
    width: float
    height: float
    start: int
    end: int


@dataclass(frozen=True)
class PDFPageXML:
    index: int
    width: float
    height: float
    words: list[PDFWord]


def add_pdf_positions(plan: dict[str, Any]) -> dict[str, Any]:
    text_cache: dict[str, list[str]] = {}
    xml_cache: dict[tuple[str, int], PDFPageXML] = {}
    size_cache: dict[tuple[str, int], tuple[float, float]] = {}
    decrypted_cache: dict[str, str] = {}
    positioned = []
    missing_tools = _missing_required_tools()
    with tempfile.TemporaryDirectory(prefix="kindle-zotero-pdf-") as temp_dir:
        for item in plan["items"]:
            attachment = (item.get("zotero") or {}).get("attachment") or {}
            if (
                missing_tools
                and item.get("status") == "ready-for-positioning"
                and attachment.get("content_type") == "application/pdf"
            ):
                positioned.append(
                    _with_problem(item, f"pdf-tools-missing:{','.join(missing_tools)}")
                )
            else:
                positioned.append(
                    _position_item(
                        item,
                        text_cache,
                        xml_cache,
                        size_cache,
                        decrypted_cache,
                        temp_dir,
                    )
                )

    status_counts: dict[str, int] = {}
    for item in positioned:
        status_counts[item["status"]] = status_counts.get(item["status"], 0) + 1

    updated = dict(plan)
    updated["items"] = positioned
    updated["status_counts"] = status_counts
    return updated


def _position_item(
    item: dict[str, Any],
    text_cache: dict[str, list[str]],
    xml_cache: dict[tuple[str, int], PDFPageXML],
    size_cache: dict[tuple[str, int], tuple[float, float]],
    decrypted_cache: dict[str, str],
    temp_dir: str,
) -> dict[str, Any]:
    if item.get("status") != "ready-for-positioning":
        return item
    attachment = item.get("zotero", {}).get("attachment")
    if not attachment or attachment.get("content_type") != "application/pdf":
        return item
    if item["clipping"]["kind"] != "highlight" or not item["clipping"].get("text"):
        return _with_problem(item, "pdf-position-skipped-non-highlight")

    path = attachment.get("resolved_path") or attachment.get("path")
    if not path or path.startswith("attachments:"):
        return _with_problem(item, "pdf-position-missing-path")

    try:
        text_pages, extraction_path = _text_pages_for_path(
            path, text_cache, decrypted_cache, temp_dir
        )
        page_index = find_pdf_text_page(
            text_pages, item["clipping"]["text"], item["clipping"].get("page")
        )
        if page_index is None:
            failed = _with_problem(item, "pdf-text-not-found")
            hint = _page_hint_text(text_pages, item["clipping"].get("page"))
            if hint:
                failed = dict(failed)
                failed["page_hint"] = hint
            return failed
        page_xml = xml_cache.setdefault(
            (extraction_path, page_index),
            extract_pdf_page_xml(extraction_path, page_index),
        )
        position = find_pdf_rects(
            extraction_path, page_xml, item["clipping"]["text"], size_cache
        )
    except Exception as error:  # noqa: BLE001 - preserve failure in plan, do not abort batch
        return _with_problem(item, f"pdf-position-error:{error}")

    if not position:
        return _with_problem(item, "pdf-rects-not-found")

    updated = dict(item)
    annotation = dict(updated["annotation"])
    annotation["position"] = {
        "pageIndex": position["pageIndex"],
        "rects": position["rects"],
    }
    annotation["pageLabel"] = item["clipping"].get("page") or str(
        position["pageIndex"] + 1
    )
    annotation["sortIndex"] = position.get("sortIndex")
    updated["annotation"] = annotation
    updated["status"] = "positioned"
    if position.get("partial"):
        updated["problems"] = [*item.get("problems", []), "partial-text-match"]
    return updated


def extract_pdf_text_pages(path: str) -> list[str]:
    result = subprocess.run(
        [_tool("pdftotext"), "-enc", "UTF-8", path, "-"],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.split("\f")


def _text_pages_for_path(
    path: str,
    text_cache: dict[str, list[str]],
    decrypted_cache: dict[str, str],
    temp_dir: str,
) -> tuple[list[str], str]:
    if path in text_cache:
        return text_cache[path], decrypted_cache.get(path, path)

    try:
        text_cache[path] = extract_pdf_text_pages(path)
        return text_cache[path], path
    except subprocess.CalledProcessError as error:
        if not _is_pdf_permission_error(error):
            raise

    decrypted_path = _decrypted_pdf_path(path, decrypted_cache, temp_dir)
    text_cache[path] = extract_pdf_text_pages(decrypted_path)
    return text_cache[path], decrypted_path


def _decrypted_pdf_path(
    path: str, decrypted_cache: dict[str, str], temp_dir: str
) -> str:
    cached = decrypted_cache.get(path)
    if cached:
        return cached

    digest = hashlib.sha256(path.encode("utf-8")).hexdigest()[:16]
    base_name = os.path.splitext(os.path.basename(path))[0] or "document"
    output_path = os.path.join(temp_dir, f"{base_name}.{digest}.decrypted.pdf")
    subprocess.run(
        [_tool("qpdf"), "--decrypt", path, output_path],
        check=True,
        capture_output=True,
        text=True,
    )
    decrypted_cache[path] = output_path
    return output_path


def _is_pdf_permission_error(error: subprocess.CalledProcessError) -> bool:
    output = "\n".join(part for part in (error.stdout, error.stderr) if part)
    return "Permission Error" in output and "Copying of text" in output


def find_pdf_text_page(
    pages: list[str], quote: str, kindle_page: str | None = None
) -> int | None:
    normalized_quote, _ = _normalize_with_map(quote)
    if not normalized_quote:
        return None
    page_order = list(range(len(pages)))
    if kindle_page and kindle_page.isdigit():
        index = int(kindle_page) - 1
        if 0 <= index < len(pages):
            page_order.remove(index)
            page_order.insert(0, index)
    for index in page_order:
        normalized_page, _ = _normalize_with_map(pages[index])
        if normalized_quote in normalized_page:
            return index
    # Fallback: alphanumeric-only search tolerates PDF extraction artifacts
    # such as "o f" for "of", hyphenation, and punctuation differences.
    stripped_quote, _ = _strip_with_map(quote)
    if stripped_quote and len(stripped_quote) >= 20:
        for index in page_order:
            stripped_page, _ = _strip_with_map(pages[index])
            if stripped_quote in stripped_page:
                return index
        # Partial fallback: long highlights may span pages or contain a
        # divergent middle (edition differences). Anchor to either half so
        # Zotero-style word search behaviour is approximated.
        for index in page_order:
            stripped_page, _ = _strip_with_map(pages[index])
            if _partial_stripped_hit(stripped_page, stripped_quote):
                return index
        # Shingle fallback: scattered OCR substitutions (e.g. Kindle
        # "yadsınaraz" vs PDF "yadsınamaz") break every long substring but
        # leave most 6-word runs intact. Rank pages by shingle hits.
        quote_words = _quote_words(normalized_quote)
        if len(quote_words) >= 6:
            required = 2 if len(quote_words) >= 12 else 1
            best_index: int | None = None
            best_hits = 0
            for index in page_order:
                normalized_page, _ = _normalize_with_map(pages[index])
                hits = _shingle_hits(normalized_page, quote_words)
                if hits > best_hits:
                    best_hits = hits
                    best_index = index
            if best_index is not None and best_hits >= required:
                return best_index
    return None


def extract_pdf_page_xml(path: str, page_index: int) -> PDFPageXML:
    page_number = page_index + 1
    result = subprocess.run(
        [
            _tool("pdftohtml"),
            "-f",
            str(page_number),
            "-l",
            str(page_number),
            "-xml",
            "-stdout",
            path,
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    root = ET.fromstring(result.stdout)
    page_el = root.find("page")
    if page_el is None:
        raise ValueError(f"no XML page for PDF page {page_number}")
    cursor = 0
    words: list[PDFWord] = []
    for text_el in page_el.findall("text"):
        text = "".join(text_el.itertext()).strip()
        if not text:
            continue
        for word in text.split():
            start = cursor
            end = start + len(word)
            words.append(
                PDFWord(
                    text=word,
                    left=float(text_el.attrib["left"]),
                    top=float(text_el.attrib["top"]),
                    width=float(text_el.attrib["width"]),
                    height=float(text_el.attrib["height"]),
                    start=start,
                    end=end,
                )
            )
            cursor = end + 1
    return PDFPageXML(
        index=page_index,
        width=float(page_el.attrib["width"]),
        height=float(page_el.attrib["height"]),
        words=words,
    )


def find_pdf_rects(
    path: str,
    page: PDFPageXML,
    quote: str,
    size_cache: dict[tuple[str, int], tuple[float, float]],
) -> dict[str, Any] | None:
    normalized_quote, _ = _normalize_with_map(quote)
    text = " ".join(word.text for word in page.words)
    normalized_text, text_map = _normalize_with_map(text)
    start = normalized_text.find(normalized_quote)
    raw_start: int | None = None
    raw_end: int | None = None
    partial = False
    if start >= 0:
        end = start + len(normalized_quote)
        raw_start = text_map[start]
        raw_end = text_map[end - 1] + 1
    else:
        stripped_quote, _ = _strip_with_map(quote)
        if stripped_quote and len(stripped_quote) >= 20:
            stripped_text, stripped_map = _strip_with_map(text)
            strip_start = stripped_text.find(stripped_quote)
            if strip_start >= 0:
                strip_end = strip_start + len(stripped_quote)
                raw_start = stripped_map[strip_start]
                raw_end = stripped_map[strip_end - 1] + 1
            else:
                hit = _partial_stripped_range(stripped_text, stripped_quote)
                if hit is not None:
                    strip_start, strip_end = hit
                    raw_start = stripped_map[strip_start]
                    raw_end = stripped_map[strip_end - 1] + 1
                    partial = True
                else:
                    span = _shingle_span(normalized_text, _quote_words(normalized_quote))
                    if span is not None:
                        raw_start = text_map[span[0]]
                        raw_end = text_map[span[1] - 1] + 1
                        partial = True
    if raw_start is None or raw_end is None:
        return None
    matched_words = [
        word for word in page.words if word.end >= raw_start and word.start <= raw_end
    ]
    if not matched_words:
        return None
    size_key = (path, page.index)
    if size_key not in size_cache:
        size_cache[size_key] = _pdf_page_size(path, page.index + 1, page.width, page.height)
    pdf_width, pdf_height = size_cache[size_key]
    rects = _word_rects(matched_words, page, pdf_width, pdf_height)
    return {
        "pageIndex": page.index,
        "rects": rects,
        "sortIndex": f"{page.index:05d}|{int(rects[0][1]):06d}|{int(rects[0][0]):05d}",
        "partial": partial,
    }


def _word_rects(
    words: list[PDFWord], page: PDFPageXML, pdf_width: float, pdf_height: float
) -> list[list[float]]:
    lines: dict[int, list[PDFWord]] = {}
    for word in words:
        lines.setdefault(round(word.top), []).append(word)
    scale_x = pdf_width / page.width
    scale_y = pdf_height / page.height
    rects = []
    for top in sorted(lines):
        line_words = lines[top]
        left = min(word.left for word in line_words)
        right = max(word.left + word.width for word in line_words)
        line_top = min(word.top for word in line_words)
        line_bottom = max(word.top + word.height for word in line_words)
        rects.append(
            [
                round(left * scale_x, 3),
                round(pdf_height - line_bottom * scale_y, 3),
                round(right * scale_x, 3),
                round(pdf_height - line_top * scale_y, 3),
            ]
        )
    return rects


def _pdf_page_size(
    path: str, page_number: int, fallback_width: float, fallback_height: float
) -> tuple[float, float]:
    result = subprocess.run(
        [_tool("pdfinfo"), "-f", str(page_number), "-l", str(page_number), path],
        check=True,
        capture_output=True,
        text=True,
    )
    match = re.search(
        rf"Page\s+{page_number}\s+size:\s+([0-9.]+)\s+x\s+([0-9.]+)\s+pts",
        result.stdout,
    )
    if not match:
        match = re.search(
            r"Page size:\s+([0-9.]+)\s+x\s+([0-9.]+)\s+pts", result.stdout
        )
    if not match:
        return fallback_width, fallback_height
    return float(match.group(1)), float(match.group(2))


def _normalize_with_map(text: str) -> tuple[str, list[int]]:
    text = unicodedata.normalize("NFKC", text)
    text = (
        text.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
        .replace("–", "-").replace("—", "-").replace("\xa0", " ").replace("\xad", "")
    )
    normalized = []
    mapping = []
    last_was_space = False
    for index, char in enumerate(text):
        if char.isspace():
            if not last_was_space and normalized:
                normalized.append(" ")
                mapping.append(index)
                last_was_space = True
            continue
        normalized.append(char.casefold())
        mapping.append(index)
        last_was_space = False
    if normalized and normalized[-1] == " ":
        normalized.pop()
        mapping.pop()
    return "".join(normalized), mapping


def _strip_with_map(text: str) -> tuple[str, list[int]]:
    """Alphanumeric-only folding with index mapping.

    Removes spaces and punctuation so PDF artifacts like "o f" for "of",
    hyphenated line breaks, and curly-quote/dash variants still match.
    Mapping points back into the input string for rect recovery.
    """
    text = unicodedata.normalize("NFKC", text).casefold()
    stripped: list[str] = []
    mapping: list[int] = []
    for index, char in enumerate(text):
        if char.isalnum():
            stripped.append(char)
            mapping.append(index)
    return "".join(stripped), mapping


def _partial_stripped_range(
    haystack: str, quote: str, min_len: int = 30
) -> tuple[int, int] | None:
    """Best half-quote hit for long highlights spanning pages/editions."""
    if len(quote) < min_len * 2:
        return None
    mid = len(quote) // 2
    for part in (quote[:mid], quote[mid:]):
        if len(part) < min_len:
            continue
        start = haystack.find(part)
        if start >= 0:
            return start, start + len(part)
    return None


def _partial_stripped_hit(haystack: str, quote: str, min_len: int = 30) -> bool:
    return _partial_stripped_range(haystack, quote, min_len) is not None


def _quote_words(normalized: str, width: int = 6) -> list[str]:
    del width
    words: list[str] = []
    for token in normalized.split():
        cleaned = "".join(char for char in token if char.isalnum())
        if cleaned:
            words.append(cleaned)
    return words


def _shingle_hits(normalized_page: str, quote_words: list[str], width: int = 6) -> int:
    hits = 0
    seen: set[tuple[str, ...]] = set()
    for start in range(len(quote_words) - width + 1):
        shingle = tuple(quote_words[start : start + width])
        if shingle in seen:
            continue
        seen.add(shingle)
        if " ".join(shingle) in normalized_page:
            hits += 1
    return hits


def _shingle_span(
    normalized_text: str, quote_words: list[str], width: int = 6
) -> tuple[int, int] | None:
    first: int | None = None
    last: int | None = None
    for start in range(len(quote_words) - width + 1):
        needle = " ".join(quote_words[start : start + width])
        at = normalized_text.find(needle)
        if at >= 0:
            end = at + len(needle)
            first = at if first is None else min(first, at)
            last = end if last is None else max(last, end)
    if first is None or last is None:
        return None
    return first, last


def _page_hint_text(
    pages: list[str], kindle_page: str | None, radius: int = 1, limit: int = 1200
) -> dict[str, Any] | None:
    """Snippet of the PDF pages around the Kindle page hint.

    Lets the user eyeball which part a `pdf-text-not-found` highlight
    belongs to and place it manually. Truncated to keep artifacts small.
    """
    if not kindle_page or not kindle_page.isdigit():
        return None
    center = int(kindle_page) - 1
    if center < 0 or center >= len(pages):
        return None
    parts = []
    for index in range(max(0, center - radius), min(len(pages), center + radius + 1)):
        snippet = " ".join(pages[index].split())
        if snippet:
            parts.append(f"[PDF p.{index + 1}] {snippet[:limit]}")
    if not parts:
        return None
    return {
        "kindle_page": kindle_page,
        "pdf_pages": list(
            range(max(1, center - radius + 1), min(len(pages), center + radius + 1) + 1)
        ),
        "text": "\n\n".join(parts)[: limit * 2 + 64],
    }


def _with_problem(item: dict[str, Any], problem: str) -> dict[str, Any]:
    updated = dict(item)
    updated["status"] = problem
    updated["problems"] = [*item.get("problems", []), problem]
    return updated
