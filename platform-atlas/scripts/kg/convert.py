"""Convert source documents to Markdown.

Research notes are Markdown; vendor material you add by hand (Word, PowerPoint, Excel, HTML, CSV, PDF)
is converted too. Office files are zip packages of XML and are read with the standard library; HTML and
CSV likewise. PDFs need the optional `pypdf` package. Conversion is text-faithful: no summarizing.
"""
from __future__ import annotations

import csv
import io
import re
import zipfile
from html.parser import HTMLParser
from pathlib import Path
from xml.etree import ElementTree as ET

SUPPORTED = (".md", ".markdown", ".txt", ".vtt", ".csv", ".html", ".htm", ".docx", ".pptx", ".xlsx", ".pdf")
MAX_SOURCE_BYTES = 50 * 1024 * 1024
MAX_SHEET_ROWS = 500
MAX_SHEET_COLS = 40

_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
_P = "{http://schemas.openxmlformats.org/presentationml/2006/main}"
_S = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
_PKG_REL = "{http://schemas.openxmlformats.org/package/2006/relationships}"


class ConversionError(RuntimeError):
    pass


def _cell(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").replace("|", "\\|").strip()


def _table(rows: list[list[str]]) -> str:
    rows = [r for r in rows if any(c.strip() for c in r)]
    if not rows:
        return ""
    width = max(len(r) for r in rows)
    rows = [r + [""] * (width - len(r)) for r in rows]
    lines = ["| " + " | ".join(_cell(c) for c in rows[0]) + " |", "|" + "---|" * width]
    lines += ["| " + " | ".join(_cell(c) for c in r) + " |" for r in rows[1:]]
    return "\n".join(lines)


def _read_xml(z: zipfile.ZipFile, name: str) -> ET.Element | None:
    try:
        return ET.fromstring(z.read(name))
    except KeyError:
        return None


def _docx(path: Path) -> str:
    with zipfile.ZipFile(path) as z:
        root = _read_xml(z, "word/document.xml")
    if root is None:
        raise ConversionError("word/document.xml not found; not a Word document")
    body = root.find(f"{_W}body")
    out: list[str] = []

    def para_text(p: ET.Element) -> str:
        parts = []
        for node in p.iter():
            if node.tag == f"{_W}t":
                parts.append(node.text or "")
            elif node.tag in (f"{_W}tab",):
                parts.append("\t")
            elif node.tag in (f"{_W}br", f"{_W}cr"):
                parts.append("\n")
        return "".join(parts).strip()

    def blocks(container: ET.Element):
        """Block-level paragraphs and tables, including those inside content controls and custom XML."""
        for child in list(container):
            if child.tag in (f"{_W}p", f"{_W}tbl"):
                yield child
            elif child.tag == f"{_W}sdt":
                content = child.find(f"{_W}sdtContent")
                if content is not None:
                    yield from blocks(content)
            elif child.tag == f"{_W}customXml":
                yield from blocks(child)

    for child in blocks(body) if body is not None else []:
        if child.tag == f"{_W}p":
            text = para_text(child)
            if not text:
                continue
            style = child.find(f"{_W}pPr/{_W}pStyle")
            style_val = (style.get(f"{_W}val") if style is not None else "") or ""
            heading = re.match(r"(?i)heading\s*([1-6])$", style_val) or re.match(r"(?i)title$", style_val)
            if heading:
                level = int(heading.group(1)) if heading.groups() else 1
                out.append("#" * level + " " + text)
            elif child.find(f"{_W}pPr/{_W}numPr") is not None:
                out.append("- " + text)
            else:
                out.append(text)
        elif child.tag == f"{_W}tbl":
            rows = []
            for tr in child.findall(f"{_W}tr"):
                rows.append([" ".join(para_text(p) for p in tc.findall(f"{_W}p")) for tc in tr.findall(f"{_W}tc")])
            table = _table(rows)
            if table:
                out.append(table)
    return "\n\n".join(out)


def _slide_number(name: str) -> int:
    m = re.search(r"(\d+)\.xml$", name)
    return int(m.group(1)) if m else 0


def _rel_targets(z: zipfile.ZipFile, part: str) -> dict[str, tuple[str, str]]:
    """Map relationship id -> (type suffix, resolved part name) for one package part."""
    folder, name = part.rsplit("/", 1)
    rels = _read_xml(z, f"{folder}/_rels/{name}.rels")
    out = {}
    for r in rels.findall(f"{_PKG_REL}Relationship") if rels is not None else []:
        target = r.get("Target", "")
        if r.get("TargetMode") == "External":
            continue
        parts = (target.lstrip("/").split("/") if target.startswith("/") else (folder + "/" + target).split("/"))
        resolved: list[str] = []
        for p in parts:
            if p == "..":
                if resolved:
                    resolved.pop()
            elif p and p != ".":
                resolved.append(p)
        out[r.get("Id")] = (r.get("Type", "").rsplit("/", 1)[-1], "/".join(resolved))
    return out


def _slide_order(z: zipfile.ZipFile) -> list[str]:
    """Slides in presentation order (presentation.xml sldIdLst), falling back to file numbering."""
    pres = _read_xml(z, "ppt/presentation.xml")
    rels = _rel_targets(z, "ppt/presentation.xml")
    ordered = []
    if pres is not None:
        for sld in pres.iter(f"{_P}sldId"):
            target = rels.get(sld.get(f"{_R}id"), ("", ""))[1]
            if target in z.namelist():
                ordered.append(target)
    if ordered:
        return ordered
    return sorted((n for n in z.namelist() if re.match(r"ppt/slides/slide\d+\.xml$", n)), key=_slide_number)


def _pptx(path: Path) -> str:
    out: list[str] = []
    with zipfile.ZipFile(path) as z:
        slides = _slide_order(z)
        if not slides:
            raise ConversionError("no slides found; not a PowerPoint deck")
        for number, name in enumerate(slides, start=1):
            root = ET.fromstring(z.read(name))
            title, lines = "", []
            for sp in root.iter(f"{_P}sp"):
                ph = sp.find(f".//{_P}nvPr/{_P}ph")
                paras = []
                for p in sp.iter(f"{_A}p"):
                    text = "".join(t.text or "" for t in p.iter(f"{_A}t")).strip()
                    if text:
                        paras.append(text)
                if not paras:
                    continue
                if ph is not None and ph.get("type") in ("title", "ctrTitle") and not title:
                    title = " ".join(paras)
                else:
                    lines += ["- " + t for t in paras]
            for tbl in root.iter(f"{_A}tbl"):
                rows = [["".join(t.text or "" for t in tc.iter(f"{_A}t")) for tc in tr.findall(f"{_A}tc")]
                        for tr in tbl.findall(f"{_A}tr")]
                table = _table(rows)
                if table:
                    lines.append(table)
            notes_part = next((t for kind, t in _rel_targets(z, name).values() if kind == "notesSlide"), None)
            notes_root = _read_xml(z, notes_part) if notes_part else None
            notes = []
            if notes_root is not None:
                for sp in notes_root.iter(f"{_P}sp"):
                    ph = sp.find(f".//{_P}nvPr/{_P}ph")
                    if ph is not None and ph.get("type") == "body":
                        notes += ["".join(t.text or "" for t in p.iter(f"{_A}t")).strip() for p in sp.iter(f"{_A}p")]
            section = [f"## Slide {number}" + (f": {title}" if title else "")] + lines
            notes = [n for n in notes if n]
            if notes:
                section.append("Speaker notes:\n" + "\n".join(notes))
            out.append("\n\n".join(section))
    return "\n\n".join(out)


def _col_index(ref: str) -> int:
    letters = re.match(r"[A-Z]+", ref or "A")
    n = 0
    for ch in letters.group(0) if letters else "A":
        n = n * 26 + (ord(ch) - 64)
    return n - 1


def _xlsx(path: Path) -> str:
    out: list[str] = []
    with zipfile.ZipFile(path) as z:
        shared: list[str] = []
        sst = _read_xml(z, "xl/sharedStrings.xml")
        if sst is not None:
            for si in sst.findall(f"{_S}si"):
                shared.append("".join(t.text or "" for t in si.iter(f"{_S}t")))
        wb = _read_xml(z, "xl/workbook.xml")
        rels = _read_xml(z, "xl/_rels/workbook.xml.rels")
        if wb is None or rels is None:
            raise ConversionError("workbook parts not found; not an Excel workbook")
        targets = {r.get("Id"): r.get("Target") for r in rels.findall(f"{_PKG_REL}Relationship")}
        for sheet in wb.iter(f"{_S}sheet"):
            target = targets.get(sheet.get(f"{_R}id"), "")
            part = "xl/" + target.lstrip("/").removeprefix("xl/")
            root = _read_xml(z, part)
            if root is None:
                continue
            rows, truncated = [], False
            for i, row in enumerate(root.iter(f"{_S}row")):
                if i >= MAX_SHEET_ROWS:
                    truncated = True
                    break
                cells: dict[int, str] = {}
                for c in row.findall(f"{_S}c"):
                    col = _col_index(c.get("r", ""))
                    if col >= MAX_SHEET_COLS:
                        truncated = True
                        continue
                    kind, v = c.get("t"), c.find(f"{_S}v")
                    if kind == "s" and v is not None and (v.text or "").isdigit() and int(v.text) < len(shared):
                        cells[col] = shared[int(v.text)]
                    elif kind == "inlineStr":
                        cells[col] = "".join(t.text or "" for t in c.iter(f"{_S}t"))
                    elif v is not None:
                        cells[col] = v.text or ""
                if cells:
                    rows.append([cells.get(j, "") for j in range(max(cells) + 1)])
            section = [f"## Sheet: {sheet.get('name')}"]
            table = _table(rows)
            section.append(table or "(empty sheet)")
            if truncated:
                section.append(f"(truncated to {MAX_SHEET_ROWS} rows and {MAX_SHEET_COLS} columns)")
            out.append("\n\n".join(section))
    return "\n\n".join(out)


class _HtmlToMarkdown(HTMLParser):
    _SKIP = {"script", "style", "noscript", "nav", "footer", "header", "svg", "form", "head"}
    _BLOCK = {"p", "div", "section", "article", "br", "tr", "table", "ul", "ol", "blockquote", "pre"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in self._SKIP:
            self.skip += 1
        elif self.skip:
            return
        elif re.fullmatch(r"h[1-6]", tag):
            self.out.append("\n\n" + "#" * int(tag[1]) + " ")
        elif tag == "li":
            self.out.append("\n- ")
        elif tag in ("td", "th"):
            self.out.append(" | ")
        elif tag in self._BLOCK:
            self.out.append("\n\n")

    def handle_endtag(self, tag):
        if tag in self._SKIP and self.skip:
            self.skip -= 1
        elif not self.skip and (tag in self._BLOCK or re.fullmatch(r"h[1-6]", tag)):
            self.out.append("\n\n")

    def handle_data(self, data):
        if not self.skip:
            self.out.append(re.sub(r"\s+", " ", data))


def _html(text: str) -> str:
    parser = _HtmlToMarkdown()
    parser.feed(text)
    parser.close()
    return "".join(parser.out)


def _pdf(path: Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise ConversionError("pypdf is not installed; run `python -m pip install pypdf` to read PDFs") from exc
    try:
        reader = PdfReader(str(path))
        if reader.is_encrypted:
            raise ConversionError("PDF is password protected")
        pages = []
        for i, page in enumerate(reader.pages, start=1):
            text = (page.extract_text() or "").strip()
            pages.append(f"## Page {i}\n\n{text or '(no extractable text; the page may be a scanned image)'}")
    except ConversionError:
        raise
    except Exception as exc:
        raise ConversionError(f"PDF could not be read: {exc}") from exc
    return "\n\n".join(pages)


def _normalize(md: str) -> str:
    md = md.replace("\r\n", "\n").replace("\r", "\n").lstrip("﻿")
    md = re.sub(r"[ \t]+\n", "\n", md)
    md = re.sub(r"\n{3,}", "\n\n", md)
    return md.strip() + "\n"


_CORE_DATE = re.compile(r"<dcterms:(modified|created)[^>]*>\s*(\d{4}-\d{2}-\d{2})")


def document_date(path: Path) -> str | None:
    """The date a document records about itself (Office core properties or PDF metadata), if any."""
    suffix = path.suffix.lower()
    try:
        if suffix in (".docx", ".pptx", ".xlsx"):
            with zipfile.ZipFile(path) as z:
                core = z.read("docProps/core.xml").decode("utf-8", errors="replace")
            found = dict((kind, day) for kind, day in _CORE_DATE.findall(core))
            return found.get("modified") or found.get("created")
        if suffix == ".pdf":
            from pypdf import PdfReader
            meta = PdfReader(str(path)).metadata
            when = meta and (meta.modification_date or meta.creation_date)
            return when.date().isoformat() if when else None
    except Exception:
        return None
    return None


def convert(path: Path) -> str:
    """Return the Markdown text of a supported source file."""
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED:
        raise ConversionError(f"unsupported file type {suffix!r}; supported: {', '.join(SUPPORTED)}")
    size = path.stat().st_size
    if size > MAX_SOURCE_BYTES:
        raise ConversionError(f"file is {size // (1024 * 1024)} MB; the limit is {MAX_SOURCE_BYTES // (1024 * 1024)} MB")
    if suffix in (".docx", ".pptx", ".xlsx"):
        with path.open("rb") as fh:
            if fh.read(8) == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
                raise ConversionError(
                    f"{path.name} is encrypted (a sensitivity label or password). Open it and save an "
                    "unprotected copy or a PDF if policy allows, then add that instead."
                )
    try:
        if suffix in (".md", ".markdown", ".txt", ".vtt"):
            return _normalize(path.read_text(encoding="utf-8-sig", errors="replace"))
        if suffix == ".csv":
            text = path.read_text(encoding="utf-8-sig", errors="replace")
            rows = list(csv.reader(io.StringIO(text)))[:MAX_SHEET_ROWS]
            return _normalize(_table([r[:MAX_SHEET_COLS] for r in rows]))
        if suffix in (".html", ".htm"):
            return _normalize(_html(path.read_text(encoding="utf-8-sig", errors="replace")))
        if suffix == ".docx":
            return _normalize(_docx(path))
        if suffix == ".pptx":
            return _normalize(_pptx(path))
        if suffix == ".xlsx":
            return _normalize(_xlsx(path))
        return _normalize(_pdf(path))
    except (zipfile.BadZipFile, ET.ParseError) as exc:
        raise ConversionError(f"{path.name} is damaged or not a valid {suffix} file: {exc}") from exc
