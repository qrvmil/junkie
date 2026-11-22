import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from junkie.archive import Archive, MAX_BYTES, ToolError, build_archive
from junkie.rules import metadata_from_text, parse_query


class ArchiveTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)

    def source(self, id_, text, owner="a", path=None, **extra):
        path = path or id_ + ".txt"
        file = self.root / path
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(text)
        return {"doc_id": id_, "path": path, "owner_id": owner, "source_type": "file",
                "uploaded_at": "2026-10-24", "sha256": hashlib.sha256(file.read_bytes()).hexdigest(), **extra}

    def test_bm25_length_normalization_changes_overlap_order(self):
        rows = [self.source("short", "needle compact"), self.source("long", "needle " * 5 + "padding " * 100)]
        archive = build_archive(self.root, rows)
        baseline = archive.search("needle", {}, "relevance", 5, "a", ranking="overlap")
        bm25 = archive.search("needle", {}, "relevance", 5, "a", ranking="bm25")
        self.assertEqual(baseline["results"][0]["doc_id"], "long")
        self.assertEqual(bm25["results"][0]["doc_id"], "short")

    def test_foreign_documents_never_ranked_or_read(self):
        own = self.source("own", "needle", path="a/apple.txt")
        foreign = self.source("foreign", "needle secret", owner="b", path="b/apple.txt")
        archive = build_archive(self.root, [own, foreign])
        found = archive.search("needle", {}, "relevance", 5, "a")
        self.assertEqual(found["read_doc_ids"], ["own"])
        self.assertEqual([d["doc_id"] for d in found["results"]], ["own"])
        with self.assertRaises(ToolError) as denied:
            archive.get_document("foreign", "a")
        self.assertEqual(denied.exception.code, "not_found_or_forbidden")
        self.assertEqual(denied.exception.read_doc_ids, [])

    def test_gold_semantic_metadata_not_used(self):
        row = self.source("document", "Unrelated plain text", doc_type="invented-gold-type",
                          content_events=[{"kind": "exam_date", "date": "2030-01-01"}], searchable=False)
        archive = build_archive(self.root, [row])
        stored = archive.documents["document"]
        self.assertNotEqual(stored.get("doc_type"), "invented-gold-type")
        self.assertEqual(stored["content_events"], [])
        self.assertTrue(stored["searchable"])

    def test_fixture_dates_and_additional_owners(self):
        row = self.source("own", "apple")
        extra = self.source("other", "apple", owner="b")
        archive = build_archive(self.root, [row], {"document_overrides": {"own": {"uploaded_at": "2026-11-01"}},
                                                  "additional_documents": [extra]})
        result = archive.search("", {"uploaded_at": {"gte": "2026-11-01", "lt": "2026-11-02"}}, "relevance", 5, "a")
        self.assertEqual(result["results"][0]["uploaded_at"], "2026-11-01")
        self.assertEqual(row["uploaded_at"], "2026-10-24")

    def test_snippet_is_exact_source_substring(self):
        source = "Начало. " * 80 + "needle, exact punctuation!\nNext paragraph."
        archive = build_archive(self.root, [self.source("doc", source)])
        card = archive.search("needle", {}, "relevance", 5, "a")["results"][0]
        self.assertIn(card["snippet"], source)
        self.assertIn("needle", card["snippet"])

    def test_inventory_snippet_skips_leading_whitespace(self):
        source = "\n " * 400 + "Actual source content."
        archive = build_archive(self.root, [self.source("doc", source)])
        snippet = archive.search("", {}, "relevance", 5, "a")["results"][0]["snippet"]
        self.assertEqual(snippet, "Actual source content.")
        self.assertIn(snippet, source)

    def test_source_resolver_opens_actual_source_and_enforces_owner(self):
        archive = build_archive(self.root, [self.source("doc", "content")])
        self.assertEqual(archive.resolve_source("saved://doc", "a"), self.root / "doc.txt")
        for source, user, code in [("https://doc", "a", "invalid_arguments"),
                                   ("saved://doc/extra", "a", "invalid_arguments"),
                                   ("saved://missing", "a", "not_found_or_forbidden"),
                                   ("saved://doc", "b", "not_found_or_forbidden")]:
            with patch("pathlib.Path.open") as opener:
                with self.assertRaises(ToolError) as result:
                    archive.resolve_source(source, user)
                opener.assert_not_called()
            self.assertEqual(result.exception.code, code)
        (self.root / "doc.txt").unlink()
        with self.assertRaises(ToolError) as result:
            archive.resolve_source("saved://doc", "a")
        self.assertEqual(result.exception.code, "unavailable")

    def test_interrupted_search_records_only_documents_inspected_so_far(self):
        archive = build_archive(self.root, [self.source("one", "content"), self.source("two", "content")])
        with patch("junkie.archive._matches", side_effect=TimeoutError):
            with self.assertRaises(TimeoutError):
                archive.search("content", {}, "relevance", 5, "a")
        self.assertEqual(archive.last_read_doc_ids, ["one"])
        with self.assertRaises(ToolError):
            archive.get_document("one", "foreign")
        self.assertEqual(archive.last_read_doc_ids, [])

    def test_overflow_and_empty_query_inventory(self):
        archive = build_archive(self.root, [self.source(str(i), "contents") for i in range(6)])
        result = archive.search("", {}, "relevance", 5, "a")
        self.assertEqual(len(result["results"]), 5)
        self.assertTrue(result["has_more"])

    def test_reject_invalid_input_before_parser(self):
        archive = Archive(self.root)
        for value, reason in [({"path": "image.png"}, "unsupported_format"),
                              ({"generator": "repeat_byte", "size_bytes": MAX_BYTES + 1}, "too_large")]:
            with patch("junkie.archive._text") as parser:
                result = archive.ingest(value, "a", "2026-10-24")
            parser.assert_not_called()
            self.assertEqual(result["reason"], reason)
            self.assertEqual(result["llm_usage"]["calls"], [])

    def test_corrupted_input_is_controlled_failure(self):
        (self.root / "broken.docx").write_bytes(b"not a zip")
        result = Archive(self.root).ingest({"path": "broken.docx"}, "a", "2026-10-24")
        self.assertEqual(result["action"], "reject")
        self.assertEqual(result["reason"], "corrupted")

    def test_ingestion_then_search_then_open(self):
        self.source("doc", "needle contents")
        archive = Archive(self.root)
        result = archive.ingest({"path": "doc.txt"}, "a", "2026-10-24", doc_id="added")
        self.assertEqual(result["action"], "ingest")
        self.assertTrue(all(result["observations"].values()))
        self.assertEqual(archive.search("needle", {}, "relevance", 5, "a")["results"][0]["doc_id"], "added")
        self.assertEqual(archive.get_document("added", "a")["text"], "needle contents")
        self.assertNotIn("added", archive.without("added").documents)
        self.assertIn("added", archive.documents)

    def test_ingestion_parses_even_when_archive_extraction_is_cached(self):
        row = self.source("doc", "fresh extraction")
        archive = build_archive(self.root, [row])
        with patch("junkie.archive.units", return_value={"line:1": "parsed again"}) as parser:
            result = archive.ingest({"path": "doc.txt"}, "a", "2026-10-24")
        parser.assert_called_once_with(self.root / "doc.txt")
        self.assertEqual(result["extracted_text"], "parsed again")

    def test_source_hash_mismatch_is_not_silent(self):
        row = self.source("doc", "old")
        (self.root / "doc.txt").write_text("new")
        archive = build_archive(self.root, [row])
        self.assertFalse(archive.documents["doc"]["searchable"])
        self.assertEqual(len(archive.preparation["errors"]), 1)

    def test_invalid_filters_and_limit_are_typed_errors(self):
        archive = build_archive(self.root, [self.source("doc", "data")])
        for filters in ({"owner_id": "b"}, {"format": []}, {"uploaded_at": {"gte": "nonsense"}},
                        {"uploaded_at": {"gte": "2026-11-01", "lt": "2026-10-01"}}):
            with self.assertRaises(ToolError) as result:
                archive.search("data", filters, "relevance", 5, "a")
            self.assertEqual(result.exception.code, "invalid_arguments")
        with self.assertRaises(ToolError):
            archive.search("data", {}, "relevance", 6, "a")

    def test_rules_inventory_and_explicit_date(self):
        parsed = parse_query("Покажи только PDF", "2026-10-24T12:00:00+03:00", "Europe/Moscow")
        self.assertEqual(parsed["filters"], {"format": "pdf"})
        self.assertEqual(parsed["query"], "")
        parsed = parse_query("добавленные вчера файлы", "2026-10-24T12:00:00+03:00", "Europe/Moscow")
        self.assertEqual(parsed["filters"]["uploaded_at"], {"gte": "2026-10-23", "lt": "2026-10-24"})
        metadata = metadata_from_text("Семинар 25 апреля 2026 года", "notes.txt", "2026-10-24")
        self.assertIn({"kind": "seminar_date", "date": "2026-04-25"}, metadata["content_events"])


if __name__ == "__main__":
    unittest.main()
