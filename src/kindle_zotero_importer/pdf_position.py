from __future__ import annotations

from dataclasses import dataclass
import re
import subprocess
import xml.etree.ElementTree as ET
from typing import Any


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
    positioned = []
    for item in plan["items"]:
        positioned.append(_position_item(item, text_cache, xml_cache, size_cache))

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
        text_pages = text_cache.setdefault(path, extract_pdf_text_pages(path))
        page_index = find_pdf_text_page(
            text_pages, item["clipping"]["text"], item["clipping"].get("page")
        )
        if page_index is None:
            return _with_problem(item, "pdf-text-not-found")
        page_xml = xml_cache.setdefault(
            (path, page_index), extract_pdf_page_xml(path, page_index)
        )
        position = find_pdf_rects(path, page_xml, item["clipping"]["text"], size_cache)
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
    return updated


def extract_pdf_text_pages(path: str) -> list[str]:
    result = subprocess.run(
        ["pdftotext", "-enc", "UTF-8", path, "-"],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.split("\f")


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
    return None


def extract_pdf_page_xml(path: str, page_index: int) -> PDFPageXML:
    page_number = page_index + 1
    result = subprocess.run(
        [
            "pdftohtml",
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
    if start < 0:
        return None
    end = start + len(normalized_quote)
    raw_start = text_map[start]
    raw_end = text_map[end - 1] + 1
    matched_words = [
        word for word in page.words if word.end >= raw_start and word.start <= raw_end
    ]
    if not matched_words:
        return None
    pdf_width, pdf_height = size_cache.setdefault(
        (path, page.index),
        _pdf_page_size(path, page.index + 1, page.width, page.height),
    )
    rects = _word_rects(matched_words, page, pdf_width, pdf_height)
    return {
        "pageIndex": page.index,
        "rects": rects,
        "sortIndex": f"{page.index:05d}|{int(rects[0][1]):06d}|{int(rects[0][0]):05d}",
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
        ["pdfinfo", "-f", str(page_number), "-l", str(page_number), path],
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


def _with_problem(item: dict[str, Any], problem: str) -> dict[str, Any]:
    updated = dict(item)
    updated["status"] = problem
    updated["problems"] = [*item.get("problems", []), problem]
    return updated
