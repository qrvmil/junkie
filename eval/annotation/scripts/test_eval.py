"""Regression tests for primary gold, filter boundaries, provenance and tool expectations."""
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from prepare_blind import ROOT, load_jsonl
from validate_annotations import effective_documents, validate_filters
from validate_eval import matches_filters, validate_case, validate_dataset


class FilterTests(unittest.TestCase):
    def test_half_open_dates_preserve_inclusive_calendar_end(self):
        f = {"uploaded_at": {"gte": "2026-10-15", "lt": "2026-10-19"}}
        for value, expected in [("2026-10-14", False), ("2026-10-15", True),
                                ("2026-10-18", True), ("2026-10-19", False)]:
            self.assertEqual(matches_filters({"uploaded_at": value}, f), expected)

    def test_one_sided_ranges_have_no_invented_bound(self):
        for f in [{"uploaded_at": {"gte": "2026-10-18"}},
                  {"uploaded_at": {"lt": "2026-10-17"}}]:
            validate_filters(f, "x")
        self.assertFalse(matches_filters({"uploaded_at": "2026-10-17"}, {"uploaded_at": {"gte": "2026-10-18"}}))
        self.assertTrue(matches_filters({"uploaded_at": "2030-01-01"}, {"uploaded_at": {"gte": "2026-10-18"}}))
        self.assertTrue(matches_filters({"uploaded_at": "2000-01-01"}, {"uploaded_at": {"lt": "2026-10-17"}}))

    def test_legacy_and_malformed_filters_rejected(self):
        for f in [{"uploaded_at": "2026-10-15"}, {"uploaded_at_to": "2026-10-15"},
                  {"content_event": "exam_date"}, {"uploaded_at": {}},
                  {"content_date": {"event": "exam_date"}},
                  {"uploaded_at": {"gte": "2026-02-30"}},
                  {"uploaded_at": {"lt": "2026-1-1"}},
                  {"uploaded_at": {"gte": "2026-10-15", "lt": "2026-10-15"}}]:
            with self.subTest(filters=f), self.assertRaises(ValueError):
                validate_filters(f, "x")

    def test_event_kind_and_date_must_match_same_event(self):
        doc = {"uploaded_at": "2026-10-15", "content_events": [
            {"kind": "exam_date", "date": "2025-01-01"},
            {"kind": "upload", "date": "2026-10-15"}]}
        f = {"content_date": {"gte": "2026-10-15", "lt": "2026-10-16", "event": "exam_date"}}
        self.assertFalse(matches_filters(doc, f))
        doc["content_events"].append({"kind": "exam_date", "date": "2026-10-15"})
        self.assertTrue(matches_filters(doc, f))
        self.assertFalse(matches_filters({"uploaded_at": "2026-10-15"}, f))

    def test_filename_allows_only_exact_or_numbered_original(self):
        doc = {"path": "corpus/011_ml1-exam-2025-var1.pdf"}
        self.assertTrue(matches_filters(doc, {"filename": "ml1-exam-2025-var1.pdf"}))
        self.assertTrue(matches_filters(doc, {"filename": "011_ml1-exam-2025-var1.pdf"}))
        self.assertFalse(matches_filters(doc, {"filename": "exam-2025-var1.pdf"}))


class EvalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = {x["id"]: x for x in load_jsonl(ROOT / "queries/dev.jsonl")}
        cls.manifest = [json.loads(s) for s in (ROOT / "documents.jsonl").read_text(encoding="utf-8").splitlines()]
        cls.env = json.loads((ROOT / "fixtures/environment.json").read_text(encoding="utf-8"))

    def docs(self, case):
        return effective_documents(case, self.manifest, self.env, ROOT)

    def test_complete_repository_and_adjudication_are_consistent(self):
        self.assertEqual(validate_dataset(), (140, 30))

    def test_step_and_call_drift_cannot_pass(self):
        for target in ["steps", "call", "limit", "text", "checks"]:
            case = copy.deepcopy(self.cases["E06"])
            if target == "steps": case["gold_steps"]["filters"] = {}
            elif target == "call": case["expected_calls"][0]["arguments_subset"]["filters"] = {}
            elif target == "limit": case["expected_calls"][0]["arguments_subset"]["limit"] = True
            elif target == "text": case["expected_calls"][0]["query_contains"] = "other.pdf"
            else: case["checks"].append("clarification")
            with self.subTest(target=target), self.assertRaises(ValueError):
                validate_case(case, self.docs(case))

    def test_synchronized_but_impossible_date_filter_rejected(self):
        case = copy.deepcopy(self.cases["E82"])
        f = {"content_date": {"gte": "2026-01-01", "lt": "2027-01-01"}}
        case["expected"]["filters"] = f
        case["gold_steps"]["filters"] = f
        case["expected_calls"][0]["arguments_subset"]["filters"] = f
        with self.assertRaisesRegex(ValueError, "cannot satisfy"):
            validate_case(case, self.docs(case))

    def test_private_results_and_stale_overflow_rejected(self):
        for field, value in [("relevant_doc_ids", ["doc_001"]), ("has_more", True)]:
            case = copy.deepcopy(self.cases["E93"])
            case["expected"][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                validate_case(case, self.docs(case))

    def test_expanded_gold_and_injection_checks_are_preserved(self):
        self.assertEqual(self.cases["E46"]["expected"]["relevant_doc_ids"], ["doc_057", "doc_058", "doc_059"])
        case = self.cases["E87"]
        self.assertEqual(case["expected"]["relevant_doc_ids"], ["doc_049", "doc_050"])
        self.assertEqual(case["expected"]["forbidden_output_strings"], ["CANARY_PRIVATE_B_2026"])
        self.assertIn("injection", case["checks"])
        self.assertEqual(case["fixture_id"], "injection_document")

    def test_fixture_dates_are_applied_before_filter_check(self):
        case = self.cases["E92"]
        validate_case(case, self.docs(case))
        with self.assertRaisesRegex(ValueError, "cannot satisfy"):
            validate_case(case, {d["doc_id"]: d for d in self.manifest})

    def test_primary_gold_drift_is_detected_even_when_steps_still_agree(self):
        # A real regression: dropping one relevant ID does not invalidate any tool call.
        import shutil
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ("queries", "annotation", "fixtures"):
                shutil.copytree(ROOT / name, root / name)
            shutil.copyfile(ROOT / "documents.jsonl", root / "documents.jsonl")
            # Path-existence checks need corpus entries, not their contents for this test.
            for doc in self.manifest:
                p = root / doc["path"]
                p.parent.mkdir(parents=True, exist_ok=True)
                p.touch()
            cases = copy.deepcopy(list(self.cases.values()))
            next(c for c in cases if c["id"] == "E46")["expected"]["relevant_doc_ids"] = ["doc_059"]
            (root / "queries/dev.jsonl").write_text("".join(json.dumps(c) + "\n" for c in cases), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "E46: dev expected differs"):
                validate_dataset(root)

    def test_original_annotations_and_agreement_numbers_unchanged(self):
        stored = json.loads((ROOT / "annotation/agreement.json").read_text(encoding="utf-8"))
        for key, filename in [("annotator_a", "preannotation.jsonl"), ("annotator_b", "preannotation_2.jsonl")]:
            self.assertEqual(hashlib.sha256((ROOT / "annotation" / filename).read_bytes()).hexdigest(), stored["input_sha256"][key])


if __name__ == "__main__":
    unittest.main()
