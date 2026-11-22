"""Локальный архив: извлечение текста, фильтры, B0 и BM25 без эталонных ответов."""
from collections import Counter
from copy import deepcopy
from datetime import date, datetime
import hashlib
import math
from pathlib import Path
import re
import time
import unicodedata

from eval.ingestion.source_text import units
from .rules import metadata_from_text, tokenize

SUPPORTED = {"txt", "md", "tex", "pdf", "docx", "pptx", "html"}
MAX_BYTES = 25 * 1024 * 1024
SOURCE_FIELDS = {"doc_id", "path", "owner_id", "uploaded_at", "source_type", "sha256"}
_TEXT_CACHE = {}
_FILENAME_TOKEN = re.compile(
    r'(?<![\w./-])(?:["«“](?P<quoted>[^"\n»”]+\.(?:pdf|docx|pptx|txt|md|tex|html))["»”]'
    r'|(?P<plain>[\w][\w.+-]*\.(?:pdf|docx|pptx|txt|md|tex|html)))(?!\w|\.\w)',
    re.IGNORECASE,
)


class ToolError(Exception):
    def __init__(self, code, read_doc_ids=None):
        super().__init__(code)
        self.code = self.error_code = code
        self.read_doc_ids = list(read_doc_ids or [])


def _source_path(root, value):
    if not isinstance(value, str) or not value:
        raise ValueError("Missing source path")
    path = (root / value).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError("Source is outside the archive")
    return path


def _text(path, expected_sha=None, use_cache=True):
    if path.stat().st_size > MAX_BYTES:
        raise ValueError("too_large")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if expected_sha and digest != expected_sha:
        raise ValueError("Source hash mismatch")
    key = (digest, path.suffix.casefold())
    if not use_cache or key not in _TEXT_CACHE:
        pieces = units(path)
        ordered = sorted(pieces, key=lambda name: (name.split(":")[0], int(name.split(":")[1])))
        value = "\n".join(pieces[name] for name in ordered)
        if not value.strip():
            raise ValueError("No extractable text")
        _TEXT_CACHE[key] = value
    return _TEXT_CACHE[key], digest


def _day(value):
    if isinstance(value, datetime):
        return value.date().isoformat()
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date().isoformat()


def _inside(value, bounds):
    if not isinstance(value, str):
        return False
    return (("gte" not in bounds or value >= bounds["gte"])
            and ("lt" not in bounds or value < bounds["lt"]))


def _matches(record, filters):
    for field, wanted in filters.items():
        if field in {"format", "source_type", "doc_type"}:
            if record.get(field) != wanted:
                return False
        elif field == "filename":
            filename = Path(record["path"]).name
            if wanted not in (filename, re.sub(r"^\d{3}_", "", filename)):
                return False
        elif field == "uploaded_at":
            if not _inside(record["uploaded_at"], wanted):
                return False
        elif field == "content_date":
            if not any(("event" not in wanted or event["kind"] == wanted["event"])
                       and _inside(event["date"], wanted) for event in record.get("content_events", [])):
                return False
        else:
            raise ToolError("invalid_arguments")
    return True


def _filename_key(value):
    return unicodedata.normalize("NFKC", re.sub(r"^\d{3}_", "", value)).casefold().replace("ё", "е")


def _edit_distance(left, right, maximum=2):
    """Bounded edit distance; an adjacent transposition counts as one typo."""
    if abs(len(left) - len(right)) > maximum:
        return maximum + 1
    previous = list(range(len(right) + 1))
    before_previous = None
    for i, char in enumerate(left, 1):
        current = [i] + [maximum + 1] * len(right)
        for j in range(max(1, i - maximum), min(len(right), i + maximum) + 1):
            current[j] = min(previous[j] + 1, current[j - 1] + 1,
                             previous[j - 1] + (char != right[j - 1]))
            if (before_previous is not None and j > 1
                    and char == right[j - 2] and left[i - 2] == right[j - 1]):
                current[j] = min(current[j], before_previous[j - 2] + 1)
        if min(current) > maximum:
            return maximum + 1
        before_previous, previous = previous, current
    return previous[-1]


def _filename_candidates(query, candidates):
    """None means no filename intent; [] means an unsafe/absent filename match."""
    names = {_filename_key(match.group("quoted") or match.group("plain"))
             for match in _FILENAME_TOKEN.finditer(query)}
    if not names:
        return None
    if len(names) != 1:
        return []
    wanted = names.pop()
    if len(wanted) > 128:
        return []
    wanted_path = Path(wanted)
    scored = {}
    for record in candidates:
        name = _filename_key(Path(record["path"]).name)
        candidate_path = Path(name)
        if len(name) > 128 or candidate_path.suffix != wanted_path.suffix:
            continue
        distance = _edit_distance(wanted_path.stem, candidate_path.stem)
        similarity = 1 - distance / max(len(wanted_path.stem), len(candidate_path.stem), 1)
        if distance > 2 or similarity < .8:
            continue
        scored.setdefault(name, {"similarity": similarity, "records": []})["records"].append(record)
    ranked = sorted(scored.values(), key=lambda item: item["similarity"], reverse=True)
    if not ranked:
        return []
    # Exact names are reliable; approximate matches need a clear margin.
    if (ranked[0]["similarity"] < 1 and len(ranked) > 1
            and ranked[0]["similarity"] - ranked[1]["similarity"] < .05):
        return []
    return ranked[0]["records"]


class Archive:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.documents = {}
        self.last_read_doc_ids = []
        self.preparation = {"errors": [], "elapsed_ms": 0, "documents": 0, "searchable": 0}

    def clone(self):
        result = Archive(self.root)
        # Text is immutable; mutable per-document metadata must not cross sessions.
        result.documents = {key: {**value, "metadata": deepcopy(value.get("metadata", {})),
                                  "content_events": deepcopy(value.get("content_events", []))}
                            for key, value in self.documents.items()}
        result.preparation = deepcopy(self.preparation)
        return result

    def without(self, doc_id):
        result = self.clone()
        result.documents.pop(doc_id, None)
        return result

    def _add(self, source, use_cache=True):
        source = {key: value for key, value in source.items() if key in SOURCE_FIELDS}
        doc_id = source.get("doc_id")
        if not isinstance(doc_id, str) or not doc_id or not isinstance(source.get("owner_id"), str):
            raise ValueError("Document needs an ID and owner")
        path = _source_path(self.root, source.get("path"))
        fmt = path.suffix.casefold().lstrip(".")
        record = {**source, "format": fmt, "text": "", "searchable": False,
                  "source_type": source.get("source_type", "file"),
                  "uploaded_at": _day(source["uploaded_at"])}
        self.documents[doc_id] = record
        if fmt not in SUPPORTED:
            raise ValueError("unsupported_format")
        text, digest = _text(path, source.get("sha256"), use_cache=use_cache)
        metadata = metadata_from_text(text, path.name, record["uploaded_at"])
        record.update(metadata)
        record.update(text=text, sha256=digest, searchable=True, metadata=metadata)
        record["terms"] = Counter(tokenize(path.name + " " + text))
        record["length"] = sum(record["terms"].values())
        return record

    def _card(self, record, query=""):
        text = record["text"]
        folded = text.casefold()
        positions = [folded.find(word.casefold()) for word in tokenize(query)]
        positions = [position for position in positions if position >= 0]
        start = max(0, min(positions) - 60) if positions else 0
        while start < len(text) and text[start].isspace():
            start += 1
        return {"doc_id": record["doc_id"],
                "title": record.get("metadata", {}).get("title") or Path(record["path"]).name,
                "snippet": text[start:start + 280], "source": "saved://" + record["doc_id"],
                "uploaded_at": record["uploaded_at"]}

    def search(self, query, filters, order_by, limit, user_id, ranking="bm25", fuzzy_filename=False):
        self.last_read_doc_ids = []
        if (not isinstance(query, str) or not isinstance(filters, dict) or type(limit) is not int
                or not 1 <= limit <= 5 or ranking not in {"bm25", "overlap"} or type(fuzzy_filename) is not bool
                or order_by not in {"relevance", "uploaded_at_asc", "uploaded_at_desc"}):
            raise ToolError("invalid_arguments")
        allowed = {"format", "source_type", "doc_type", "filename", "uploaded_at", "content_date"}
        if set(filters) - allowed:
            raise ToolError("invalid_arguments")
        for name, value in filters.items():
            if name in {"uploaded_at", "content_date"}:
                valid_keys = {"gte", "lt", "event"} if name == "content_date" else {"gte", "lt"}
                if (not isinstance(value, dict) or not any(k in value for k in ("gte", "lt"))
                        or set(value) - valid_keys):
                    raise ToolError("invalid_arguments")
                if any(not isinstance(v, str) or not v for v in value.values()):
                    raise ToolError("invalid_arguments")
                try:
                    for bound in ("gte", "lt"):
                        if bound in value:
                            if len(value[bound]) != 10:
                                raise ValueError("Invalid date")
                            date.fromisoformat(value[bound])
                except ValueError as exc:
                    raise ToolError("invalid_arguments") from exc
                if "gte" in value and "lt" in value and value["gte"] >= value["lt"]:
                    raise ToolError("invalid_arguments")
            elif not isinstance(value, str):
                raise ToolError("invalid_arguments")
        # Owner filtering precedes access to text, term counts, or snippets.
        owned = [record for record in self.documents.values()
                 if record.get("owner_id") == user_id and record.get("searchable")]
        candidates = []
        for record in owned:
            self.last_read_doc_ids.append(record["doc_id"])
            if _matches(record, filters):
                candidates.append(record)
        filename_candidates = (_filename_candidates(query, candidates)
                               if fuzzy_filename and "filename" not in filters else None)
        if filename_candidates is not None:
            candidates = filename_candidates
        query_terms = set(tokenize(query))
        avgdl = sum(record["length"] for record in owned) / len(owned) if owned else 1
        frequencies = {term: sum(term in record["terms"] for record in owned) for term in query_terms}
        scored = []
        for record in candidates:
            if filename_candidates is not None or not query_terms:
                score = 1
            elif ranking == "overlap":
                score = sum(record["terms"][term] for term in query_terms)
            else:
                score = 0.0
                for term in query_terms:
                    frequency = record["terms"][term]
                    if frequency:
                        idf = math.log(1 + (len(owned) - frequencies[term] + .5) / (frequencies[term] + .5))
                        score += idf * frequency * 2.2 / (frequency + 1.2 * (.25 + .75 * record["length"] / (avgdl or 1)))
            if score > 0:
                scored.append((score, record))
        scored.sort(key=lambda item: (-item[0], item[1]["doc_id"]))
        if order_by != "relevance":
            scored.sort(key=lambda item: item[1]["uploaded_at"], reverse=order_by.endswith("desc"))
        return {"results": [self._card(record, query) for _, record in scored[:limit]],
                "has_more": len(scored) > limit, "read_doc_ids": list(self.last_read_doc_ids)}

    def get_document(self, doc_id, user_id):
        self.last_read_doc_ids = []
        if not isinstance(doc_id, str) or not doc_id:
            raise ToolError("not_found_or_forbidden")
        record = self.documents.get(doc_id)
        if record is None or record.get("owner_id") != user_id:
            raise ToolError("not_found_or_forbidden")
        if not record.get("searchable"):
            raise ToolError("unavailable")
        self.last_read_doc_ids.append(doc_id)
        return {"result": self._card(record), "text": record["text"], "read_doc_ids": [doc_id]}

    def resolve_source(self, source, user_id):
        """Resolve an internal source and verify that its bytes can be opened."""
        if not isinstance(source, str) or not re.fullmatch(r"saved://[^/\s?#]+", source):
            raise ToolError("invalid_arguments")
        doc_id = source.removeprefix("saved://")
        record = self.documents.get(doc_id)
        if record is None or record.get("owner_id") != user_id:
            raise ToolError("not_found_or_forbidden")
        try:
            path = _source_path(self.root, record.get("path"))
            with path.open("rb") as stream:
                stream.read(1)
            return path
        except (OSError, ValueError):
            raise ToolError("unavailable", read_doc_ids=[doc_id]) from None

    def ingest(self, input, user_id, now, doc_id=None):
        started = time.perf_counter()
        def finish(row):
            row.update(elapsed_ms=(time.perf_counter() - started) * 1000,
                       llm_usage={"complete": True, "calls": []})
            return row
        def reject(reason):
            return finish({"status": "ok", "action": "reject", "reason": reason,
                           "observations": {"source_saved": False, "source_openable": False, "searchable": False}})
        if input.get("generator") == "repeat_byte":
            if type(input.get("size_bytes")) is int and input["size_bytes"] > MAX_BYTES:
                return reject("too_large")
            return reject("unsupported_format")
        try:
            path = _source_path(self.root, input.get("path"))
        except ValueError:
            return reject("unsupported_format")
        if path.suffix.casefold().lstrip(".") not in SUPPORTED:
            return reject("unsupported_format")
        try:
            if path.stat().st_size > MAX_BYTES:
                return reject("too_large")
            new_id = doc_id or "new_" + hashlib.sha256((user_id + "\0" + str(path)).encode()).hexdigest()[:16]
            if new_id in self.documents and self.documents[new_id]["owner_id"] != user_id:
                return reject("not_found_or_forbidden")
            record = self._add({"doc_id": new_id, "path": str(path.relative_to(self.root)), "owner_id": user_id,
                                "uploaded_at": _day(now), "source_type": input.get("source_type", "file")},
                               use_cache=False)
        except Exception:
            # Parser exceptions are controlled; their text may contain source data.
            return reject("corrupted")
        return finish({"status": "ok", "action": "ingest", "document_id": new_id,
                       "extracted_text": record["text"], "metadata": deepcopy(record["metadata"]),
                       "observations": {"source_saved": new_id in self.documents,
                                        "source_openable": path.is_file(), "searchable": record["searchable"]}})


def build_archive(root, documents, fixture=None):
    started = time.perf_counter()
    archive = Archive(root)
    sources = {doc["doc_id"]: {k: v for k, v in doc.items() if k in SOURCE_FIELDS} for doc in documents}
    if len(sources) != len(documents):
        raise ValueError("Duplicate document IDs")
    fixture = fixture or {}
    for doc in fixture.get("additional_documents", []):
        if doc["doc_id"] in sources:
            raise ValueError("Duplicate fixture document ID")
        sources[doc["doc_id"]] = {k: v for k, v in doc.items() if k in SOURCE_FIELDS}
    for doc_id, updates in fixture.get("document_overrides", {}).items():
        if doc_id not in sources:
            raise ValueError("Unknown fixture document ID")
        sources[doc_id].update({k: v for k, v in updates.items() if k in SOURCE_FIELDS})
    for source in sources.values():
        try:
            archive._add(source)
        except Exception as exc:
            archive.preparation["errors"].append({"doc_id": source["doc_id"], "error": type(exc).__name__})
    archive.preparation.update(elapsed_ms=(time.perf_counter() - started) * 1000,
                               documents=len(archive.documents),
                               searchable=sum(bool(d.get("searchable")) for d in archive.documents.values()))
    return archive
