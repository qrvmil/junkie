#!/usr/bin/env python3
"""Build an offline viewer from blind inputs; never read queries or review answers."""

import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
from html.parser import HTMLParser
import xml.etree.ElementTree as ET
import zipfile


VIEWER = Path(__file__).resolve().parent
EVAL = VIEWER.parent.parent


class SavedHTMLText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.hidden += 1
        if tag in ("p", "div", "h1", "h2", "h3", "li", "section", "br", "tr"):
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.hidden = max(0, self.hidden - 1)

    def handle_data(self, value):
        if not self.hidden:
            self.parts.append(value)


def jsonl(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def extract(path, fmt):
    if fmt == "pdf":
        result = subprocess.run(
            ["pdftotext", "-layout", str(path), "-"],
            check=True, capture_output=True, text=True,
        )
        text = result.stdout
    elif fmt in ("docx", "pptx"):
        with zipfile.ZipFile(path) as archive:
            names = ["word/document.xml"] if fmt == "docx" else sorted(
                name for name in archive.namelist()
                if name.startswith("ppt/slides/slide") and name.endswith(".xml")
            )
            text = "\n".join(
                " ".join(element.text or "" for element in ET.fromstring(archive.read(name)).iter()
                         if element.tag.endswith("}t"))
                for name in names
            )
    else:
        text = path.read_text()
    if not text.strip():
        raise ValueError(f"No text extracted from {path.name}")
    if fmt == "html":
        parser = SavedHTMLText()
        parser.feed(text)
        text = re.sub(r"\n\s*\n+", "\n\n", "".join(parser.parts))
    return text


def build():
    if not shutil.which("pdftotext"):
        raise SystemExit("pdftotext must already be installed; no dependencies are installed by this script.")
    cases = jsonl(EVAL / "annotation/blind_cases.jsonl")
    annotations = jsonl(EVAL / "annotation/preannotation.jsonl")
    documents = jsonl(EVAL / "documents.jsonl")
    environment = json.loads((EVAL / "fixtures/environment.json").read_text())
    if [c["id"] for c in cases] != [a["id"] for a in annotations]:
        raise ValueError("Case coverage/order differs from preannotation")
    manifest_hash = hashlib.sha256((EVAL / "documents.jsonl").read_bytes()).hexdigest()
    if manifest_hash != environment["manifest_sha256"]:
        raise ValueError("Manifest checksum mismatch")
    assets, bundle = {}, []
    for case, annotation in zip(cases, annotations):
        if case["environment_id"] != environment["id"]:
            raise ValueError("Unknown environment")
        fixture = environment["fixtures"][case["fixture_id"]]
        effective = {d["doc_id"]: dict(d) for d in documents}
        for document in fixture.get("additional_documents", []):
            effective[document["doc_id"]] = dict(document)
        for doc_id, override in fixture.get("document_overrides", {}).items():
            effective[doc_id].update(override)
        available = []
        for document in effective.values():
            if document["owner_id"] != case["user_id"] or not document["searchable"]:
                continue
            digest = document["sha256"]
            if digest not in assets:
                path = EVAL / document["path"]
                if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
                    raise ValueError(f"Checksum mismatch: {document['doc_id']}")
                assets[digest] = {
                    "text": extract(path, document["format"]),
                    "url": "../../" + document["path"],
                    "filename": path.name,
                }
            available.append({**document, "asset": digest})
        allowed = {d["doc_id"] for d in available}
        if not set(annotation["relevant_doc_ids"] + annotation["clarify_candidates"]) <= allowed:
            raise ValueError(f"Inaccessible annotation document in {case['id']}")
        bundle.append({"case": case, "annotation": annotation, "documents": available})
    fingerprint = hashlib.sha256(
        json.dumps(bundle, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()[:16]
    output = {"fingerprint": fingerprint, "cases": bundle, "assets": assets}
    (VIEWER / "data.js").write_text(
        "window.REVIEW_DATA=" + json.dumps(output, ensure_ascii=False, separators=(",", ":")) + ";\n"
    )
    print(f"Built {len(bundle)} cases, {len(assets)} assets; dataset {fingerprint}")


if __name__ == "__main__":
    build()
