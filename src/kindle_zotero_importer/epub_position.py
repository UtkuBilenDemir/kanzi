from __future__ import annotations

from dataclasses import dataclass
from html import unescape
from html.parser import HTMLParser
import posixpath
import unicodedata
import zipfile
import xml.etree.ElementTree as ET
from typing import Any


CONTAINER_PATH = "META-INF/container.xml"


@dataclass(frozen=True)
class TextNode:
    spine_index: int
    cfi_parent_path: str
    text_step: str
    text: str
    start: int
    end: int


def add_epub_positions(plan: dict[str, Any]) -> dict[str, Any]:
    cache: dict[str, list[TextNode]] = {}
    positioned = []
    for item in plan["items"]:
        positioned.append(_position_item(item, cache))

    status_counts: dict[str, int] = {}
    for item in positioned:
        status_counts[item["status"]] = status_counts.get(item["status"], 0) + 1

    updated = dict(plan)
    updated["items"] = positioned
    updated["status_counts"] = status_counts
    return updated


def _position_item(
    item: dict[str, Any], cache: dict[str, list[TextNode]]
) -> dict[str, Any]:
    if item.get("status") != "ready-for-positioning":
        return item
    attachment = item.get("zotero", {}).get("attachment")
    if not attachment or attachment.get("content_type") != "application/epub+zip":
        return item
    if item["clipping"]["kind"] != "highlight" or not item["clipping"].get("text"):
        return _with_problem(item, "epub-position-skipped-non-highlight")

    path = attachment.get("resolved_path") or attachment.get("path")
    if not path:
        return _with_problem(item, "epub-position-missing-path")

    try:
        text_nodes = cache.setdefault(path, extract_epub_text_nodes(path))
        position = find_epub_cfi(text_nodes, item["clipping"]["text"])
    except Exception as error:  # noqa: BLE001 - preserve failure in plan, do not abort batch
        return _with_problem(item, f"epub-position-error:{error}")

    if not position:
        return _with_problem(item, "epub-text-not-found")

    updated = dict(item)
    annotation = dict(updated["annotation"])
    annotation["position"] = position["selector"]
    annotation["sortIndex"] = position["sortIndex"]
    updated["annotation"] = annotation
    updated["status"] = "positioned"
    if position.get("partial"):
        updated["problems"] = [*item.get("problems", []), "partial-text-match"]
    return updated


def extract_epub_text_nodes(path: str) -> list[TextNode]:
    with zipfile.ZipFile(path) as epub:
        opf_path = _opf_path(epub)
        spine_items = _spine_items(epub, opf_path)
        nodes: list[TextNode] = []
        cursor = 0
        for spine_index, item_path in enumerate(spine_items):
            try:
                xml = epub.read(item_path).decode("utf-8", errors="replace")
            except KeyError:
                continue
            for cfi_parent_path, text_step, text in _xhtml_text_nodes(xml):
                if not text.strip():
                    continue
                start = cursor
                cursor += len(text)
                nodes.append(
                    TextNode(
                        spine_index, cfi_parent_path, text_step, text, start, cursor
                    )
                )
                cursor += 1
        return nodes


def find_epub_cfi(text_nodes: list[TextNode], quote: str) -> dict[str, Any] | None:
    haystack = " ".join(node.text for node in text_nodes)
    normalized_haystack, haystack_map = _normalize_with_map(haystack)
    normalized_quote, _ = _normalize_with_map(quote)
    if not normalized_quote:
        return None

    match_start = normalized_haystack.find(normalized_quote)
    raw_start: int | None = None
    raw_end: int | None = None
    partial = False
    if match_start >= 0:
        match_end = match_start + len(normalized_quote)
        raw_start = haystack_map[match_start]
        raw_end = haystack_map[match_end - 1] + 1
    else:
        stripped_quote, _ = _strip_with_map(normalized_quote)
        if stripped_quote and len(stripped_quote) >= 20:
            stripped_haystack, stripped_map = _strip_with_map(normalized_haystack)
            strip_start = stripped_haystack.find(stripped_quote)
            strip_len = len(stripped_quote)
            if strip_start < 0:
                hit = _partial_stripped_range(stripped_haystack, stripped_quote)
                if hit is not None:
                    strip_start, strip_end = hit
                    strip_len = strip_end - strip_start
                    partial = True
            if strip_start >= 0:
                # stripped_map points into normalized_haystack;
                # convert via haystack_map back to raw haystack offsets.
                norm_start = stripped_map[strip_start]
                norm_end = stripped_map[strip_start + strip_len - 1]
                raw_start = haystack_map[norm_start]
                raw_end = haystack_map[norm_end] + 1
            else:
                span = _shingle_span(normalized_haystack, _quote_words(normalized_quote))
                if span is not None:
                    raw_start = haystack_map[span[0]]
                    raw_end = haystack_map[span[1] - 1] + 1
                    partial = True
        else:
            partial = False
    if raw_start is None or raw_end is None:
        return None

    # Account for the spaces inserted between text nodes in haystack construction.
    adjusted_nodes = _nodes_for_joined_text(text_nodes)
    start_node, start_offset = _node_at(adjusted_nodes, raw_start)
    end_node, end_offset = _node_at(adjusted_nodes, raw_end)
    if not start_node or not end_node:
        return None

    if start_node.spine_index != end_node.spine_index:
        return None

    spine_step = 2 * (start_node.spine_index + 1)
    if start_node.cfi_parent_path == end_node.cfi_parent_path:
        value = (
            f"epubcfi(/6/{spine_step}!{start_node.cfi_parent_path},"
            f"/{start_node.text_step}:{start_offset},/{end_node.text_step}:{end_offset})"
        )
    else:
        value = (
            f"epubcfi(/6/{spine_step}!"
            f"{start_node.cfi_parent_path}/{start_node.text_step}:{start_offset},"
            f"{end_node.cfi_parent_path}/{end_node.text_step}:{end_offset})"
        )
    return {
        "selector": {
            "type": "FragmentSelector",
            "conformsTo": "http://www.idpf.org/epub/linking/cfi/epub-cfi.html",
            "value": value,
        },
        "sortIndex": f"{spine_step:05d}|{raw_start:08d}",
        "partial": partial,
    }


def _opf_path(epub: zipfile.ZipFile) -> str:
    root = ET.fromstring(epub.read(CONTAINER_PATH))
    rootfile = root.find(".//{*}rootfile")
    if rootfile is None:
        raise ValueError("EPUB container has no rootfile")
    return rootfile.attrib["full-path"]


def _spine_items(epub: zipfile.ZipFile, opf_path: str) -> list[str]:
    root = ET.fromstring(epub.read(opf_path))
    manifest = {
        item.attrib["id"]: item.attrib["href"]
        for item in root.findall(".//{*}manifest/{*}item")
    }
    base = posixpath.dirname(opf_path)
    paths = []
    for itemref in root.findall(".//{*}spine/{*}itemref"):
        href = manifest.get(itemref.attrib.get("idref", ""))
        if href:
            paths.append(posixpath.normpath(posixpath.join(base, href)))
    return paths


def _xhtml_text_nodes(xml: str) -> list[tuple[str, str, str]]:
    parser = _CFIHTMLParser()
    parser.feed(xml)
    return parser.nodes


class _CFIHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[dict[str, Any]] = []
        self.nodes: list[tuple[str, str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        tag = tag.lower()
        if not self.stack:
            path: list[str] = [] if tag == "html" else ["2"]
        else:
            parent = self.stack[-1]
            parent["element_count"] += 1
            path = [*parent["path"], str(2 * parent["element_count"])]
        self.stack.append(
            {"tag": tag, "path": path, "element_count": 0, "text_count": 0}
        )

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index]["tag"] == tag:
                del self.stack[index:]
                return

    def handle_data(self, data: str) -> None:
        if not self.stack or not data.strip():
            return
        current = self.stack[-1]
        current["text_count"] += 1
        text_step = str(2 * current["text_count"] - 1)
        self.nodes.append(
            ("/" + "/".join(current["path"]), text_step, _clean_text(data))
        )


def _clean_text(text: str) -> str:
    return unescape(text).replace("\xa0", " ")


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


def _quote_words(normalized: str) -> list[str]:
    words: list[str] = []
    for token in normalized.split():
        cleaned = "".join(char for char in token if char.isalnum())
        if cleaned:
            words.append(cleaned)
    return words


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


def _nodes_for_joined_text(text_nodes: list[TextNode]) -> list[TextNode]:
    nodes = []
    cursor = 0
    for node in text_nodes:
        start = cursor
        end = start + len(node.text)
        nodes.append(
            TextNode(
                node.spine_index,
                node.cfi_parent_path,
                node.text_step,
                node.text,
                start,
                end,
            )
        )
        cursor = end + 1
    return nodes


def _node_at(nodes: list[TextNode], offset: int) -> tuple[TextNode | None, int]:
    for node in nodes:
        if node.start <= offset <= node.end:
            return node, max(0, min(offset - node.start, len(node.text)))
    return None, 0


def _with_problem(item: dict[str, Any], problem: str) -> dict[str, Any]:
    updated = dict(item)
    updated["status"] = problem
    updated["problems"] = [*item.get("problems", []), problem]
    return updated
