"""Read saved corpus text for evidence checks; no network or document instructions run."""
import re
import unicodedata
import xml.etree.ElementTree as ET
from collections import defaultdict
from html.parser import HTMLParser
from pathlib import Path
from zipfile import ZipFile


def normalize(text):
    text = unicodedata.normalize("NFKC", text).replace("\u00ad", "")
    text = re.sub(r"(?<=\w)[-\u2010]\s*\n\s*(?=\w)", "", text)
    text = text.translate(str.maketrans({"–": "-", "—": "-", "−": "-"}))
    return " ".join(text.casefold().split())


def contains_quote(text, quote):
    quote = normalize(quote)
    if not quote:
        return False
    start = r"(?<!\w)" if quote[0].isalnum() else ""
    end = r"(?!\w)" if quote[-1].isalnum() else ""
    return re.search(start + re.escape(quote) + end, normalize(text)) is not None


class VisibleHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.hidden = 0
        self.lines = defaultdict(list)

    def handle_starttag(self, tag, attrs):
        if tag in {"head", "script", "style"}:
            self.hidden += 1
        if not self.hidden and tag in {"p", "div", "li", "br", "h1", "h2", "tr"}:
            self.lines[self.getpos()[0]].append(" ")

    def handle_endtag(self, tag):
        if tag in {"head", "script", "style"}:
            self.hidden = max(0, self.hidden - 1)
        if not self.hidden and tag in {"p", "div", "li", "h1", "h2", "td"}:
            self.lines[self.getpos()[0]].append(" ")

    def handle_data(self, data):
        if not self.hidden:
            for offset, chunk in enumerate(data.splitlines(keepends=True)):
                self.lines[self.getpos()[0] + offset].append(chunk)


def units(path):
    path = Path(path)
    extension = path.suffix.lower()
    if extension == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise ValueError("PDF evidence checks need pypdf; install eval/ingestion/requirements.txt") from exc
        return {f"page:{i}": page.extract_text() or "" for i, page in enumerate(PdfReader(path).pages, 1)}
    if extension == ".docx":
        ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
        with ZipFile(path) as archive:
            tree = ET.fromstring(archive.read("word/document.xml"))
        return {f"paragraph:{i}": "".join(node.text or "" for node in p.iter(ns + "t"))
                for i, p in enumerate(tree.iter(ns + "p"), 1)}
    if extension == ".pptx":
        ns = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
        result = {}
        with ZipFile(path) as archive:
            for name in archive.namelist():
                match = re.fullmatch(r"ppt/slides/slide(\d+)\.xml", name)
                if match:
                    tree = ET.fromstring(archive.read(name))
                    result[f"slide:{match[1]}"] = "\n".join(
                        "".join(node.text or "" for node in p.iter(ns + "t")) for p in tree.iter(ns + "p"))
        return result
    if extension not in {".txt", ".md", ".tex", ".html"}:
        raise ValueError(f"Unsupported evidence format: {extension}")
    text = path.read_text(encoding="utf-8")
    if extension == ".html":
        parser = VisibleHTML()
        parser.feed(text)
        return {f"line:{i}": "".join(parser.lines[i]) for i in range(1, len(text.splitlines()) + 1)}
    return {f"line:{i}": line for i, line in enumerate(text.splitlines(), 1)}


def locate(source_units, locator):
    match = re.fullmatch(r"(line|page|paragraph|slide):([1-9]\d*)(?:-([1-9]\d*))?", locator)
    if not match:
        raise ValueError(f"Invalid locator: {locator}")
    kind, first, last = match.groups()
    first, last = int(first), int(last or first)
    if first > last:
        raise ValueError(f"Reversed locator: {locator}")
    try:
        return "\n".join(source_units[f"{kind}:{i}"] for i in range(first, last + 1))
    except KeyError as exc:
        raise ValueError(f"Missing source location: {locator}") from exc
