"""Generate minimal EPUB + PDF fixtures for the Windows smoke test.

Run: python3 tests/fixtures/windows-smoke/make_fixtures.py
Outputs kanzi-dummy.epub and kanzi-dummy.pdf next to this script.
Both contain the highlight sentences from 'My Clippings.txt' so
EPUB CFI and PDF text positioning can succeed.
"""
from __future__ import annotations

from pathlib import Path
import zipfile

HERE = Path(__file__).resolve().parent
EPUB_TEXT = "This is a test highlight long enough to import for EPUB."
PDF_TEXT = "This is a test highlight long enough to import for PDF."


def make_epub(path: Path) -> None:
    chapter = f"""<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml">
<head><title>Kanzi Dummy</title></head>
<body>
<h1>Kanzi Dummy EPUB</h1>
<p>Some intro text before the highlight.</p>
<p>{EPUB_TEXT}</p>
<p>Some trailing text after the highlight.</p>
</body>
</html>
"""
    container = """<?xml version="1.0" encoding="utf-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
<rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles>
</container>
"""
    opf = """<?xml version="1.0" encoding="utf-8"?>
<package version="3.0" unique-identifier="uid" xmlns="http://www.idpf.org/2007/opf">
<metadata xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:title>Kanzi Dummy EPUB</dc:title><dc:identifier id="uid">kanzi-dummy-epub</dc:identifier><dc:language>en</dc:language></metadata>
<manifest><item id="ch1" href="chapter1.xhtml" media-type="application/xhtml+xml"/></manifest>
<spine><itemref idref="ch1"/></spine>
</package>
"""
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        z.writestr("META-INF/container.xml", container, compress_type=zipfile.ZIP_DEFLATED)
        z.writestr("OEBPS/content.opf", opf, compress_type=zipfile.ZIP_DEFLATED)
        z.writestr("OEBPS/chapter1.xhtml", chapter, compress_type=zipfile.ZIP_DEFLATED)


def _pdf_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def make_pdf(path: Path) -> None:
    # Minimal one-page PDF with Helvetica text. pdftotext extracts it fine.
    content = (
        f"BT /F1 12 Tf 72 720 Td ({_pdf_escape('Kanzi Dummy PDF')}) Tj ET\n"
        f"BT /F1 12 Tf 72 700 Td ({_pdf_escape(PDF_TEXT)}) Tj ET\n"
    )
    objects: list[bytes] = []
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objects.append(b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>")
    objects.append(
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>"
    )
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    objects.append(f"<< /Length {len(content.encode('latin-1'))} >>\nstream\n{content}endstream".encode("latin-1"))

    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for i, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode("ascii") + body + b"\nendobj\n"
    xref_pos = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode("ascii")
    out += b"0000000000 65535 f \n"
    for off in offsets[1:]:
        out += f"{off:010d} 00000 n \n".encode("ascii")
    out += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_pos}\n%%EOF\n"
    ).encode("ascii")
    path.write_bytes(bytes(out))


def main() -> None:
    make_epub(HERE / "kanzi-dummy.epub")
    make_pdf(HERE / "kanzi-dummy.pdf")
    print("wrote kanzi-dummy.epub + kanzi-dummy.pdf")


if __name__ == "__main__":
    main()
