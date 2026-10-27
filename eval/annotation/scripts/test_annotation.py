"""Regression checks for metric denominators, blinding and access boundaries."""
import copy
import json
import tempfile
import unittest
from pathlib import Path

from calculate_agreement import calculate, render_report
from prepare_blind import CASE_IDS, FIELDS, prepare
from validate_annotations import effective_documents, validate_adjudication, validate_row


def annotation(id_, action="search", docs=None, **changes):
    row = {"id": id_, "action": action, "relevant_doc_ids": docs if docs is not None else ["doc_001"],
           "clarify_candidates": [], "filters": {}, "order_by": "relevance", "has_more": False}
    row.update(changes)
    return row


class AgreementTests(unittest.TestCase):
    def test_report_does_not_invent_annotation_method(self):
        a = {"x": annotation("x")}
        result = calculate(a, a)
        result.update(categories={"example": 1}, input_sha256={})
        report = render_report(result, a, a, [], {})
        self.assertIn("Способ разметки не указан", report)
        self.assertNotIn("LLM", report)
        self.assertNotIn("Человеческая проверка не проводилась", report)
        method = "Два человека независимо разметили выборку."
        self.assertIn(method, render_report(result, a, a, [], {}, method))

    def test_report_includes_shared_error_without_counting_a_disagreement(self):
        a = {"x": annotation("x", filters={"doc_type": "seminar"})}
        final = {"x": annotation("x")}
        result = calculate(a, a)
        result.update(categories={"example": 1}, input_sha256={})
        decision = {"id": "x", "annotation_a": a["x"], "annotation_b": a["x"],
                    "final": final["x"], "comment": "Removed an unsupported metadata filter"}
        report = render_report(result, a, a, [decision], final)
        self.assertEqual(result["disagreement_count"], 0)
        self.assertIn("Общие ошибки, исправленные после сравнения", report)
        self.assertIn(decision["comment"], report)
        self.assertIn("дополнительно исправлено совпавших записей: 1", report)

    def test_hand_calculated_metrics_and_disputes(self):
        a = {"a": annotation("a", docs=["d1", "d2"]),
             "b": annotation("b"), "c": annotation("c", "refuse", []),
             "d": annotation("d", "clarify", [], clarify_candidates=["d3"])}
        b = copy.deepcopy(a)
        b["a"]["relevant_doc_ids"] = ["d2", "d3"]
        b["b"] = annotation("b", "no_result", [])
        b["d"]["clarify_candidates"] = ["d4"]
        result = calculate(a, b)
        self.assertEqual(result["actions"]["fraction"], 3 / 4)
        self.assertEqual(result["actions"]["p_expected"], 1 / 4)
        self.assertAlmostEqual(result["actions"]["cohens_kappa"], 2 / 3)
        self.assertEqual(result["documents"]["exact_set_agreement"]["total"], 2)
        self.assertEqual(result["documents"]["exact_set_agreement"]["matched"], 0)
        self.assertAlmostEqual(result["documents"]["mean_jaccard"], 1 / 6)
        self.assertEqual(result["disputed_ids"], ["a", "b", "d"])
        self.assertEqual(result["actions"]["confusion_matrix"]["search"]["no_result"], 1)
        self.assertEqual(result["actions"]["disagreement_matrix"]["refuse"]["refuse"], 0)

    def test_joint_empty_answers_do_not_inflate_relevance(self):
        a = {str(i): annotation(str(i), action, []) for i, action in enumerate(("refuse", "no_result", "clarify"))}
        result = calculate(a, copy.deepcopy(a))
        self.assertIsNone(result["documents"]["mean_jaccard"])
        self.assertIsNone(result["documents"]["exact_set_agreement"]["fraction"])
        self.assertEqual(result["documents"]["applicable_ids"], [])

    def test_search_vs_clarify_is_included(self):
        result = calculate({"x": annotation("x")}, {"x": annotation("x", "clarify", [])})
        self.assertEqual(result["documents"]["mean_jaccard"], 0)
        self.assertEqual(result["documents"]["applicable_ids"], ["x"])

    def test_set_and_object_key_order_are_irrelevant(self):
        a = {"x": annotation("x", docs=["d1", "d2"], filters={"format": "pdf", "source_type": "file"})}
        b = {"x": annotation("x", docs=["d2", "d1"], filters={"source_type": "file", "format": "pdf"})}
        result = calculate(a, b)
        self.assertEqual(result["documents"]["mean_jaccard"], 1)
        self.assertEqual(result["disagreement_count"], 0)
        self.assertIsNone(result["actions"]["cohens_kappa"])

    def test_mismatched_or_empty_input_rejected(self):
        for a, b in (({}, {}), ({"a": annotation("a")}, {"b": annotation("b")})):
            with self.assertRaises(ValueError):
                calculate(a, b)


class ValidationTests(unittest.TestCase):
    def setUp(self):
        self.case = {"id": "x", "user_id": "user_a"}
        self.docs = {"doc_001": {"owner_id": "user_a", "searchable": True},
                     "private": {"owner_id": "user_b", "searchable": True},
                     "hidden": {"owner_id": "user_a", "searchable": False}}

    def test_acl_applies_to_results_and_clarification_candidates(self):
        for id_ in ("private", "hidden", "missing"):
            for row in (annotation("x", docs=[id_]), annotation("x", "clarify", [], clarify_candidates=[id_])):
                with self.assertRaises(ValueError):
                    validate_row(row, self.case, self.docs)

    def test_malformed_rows_rejected(self):
        variants = [annotation("x", docs=[]), annotation("x", "refuse"),
                    annotation("x", has_more=1), annotation("x", docs=["doc_001", "doc_001"]),
                    annotation("x", filters={"owner_id": "user_b"}), annotation("x", evidence="leak"),
                    annotation("x", filters={"uploaded_at": {"gte": "2026-10-20", "lt": "2026-10-19"}})]
        for row in variants:
            with self.assertRaises(ValueError):
                validate_row(row, self.case, self.docs)

    def test_complete_large_result_and_has_more(self):
        docs = {str(i): {"owner_id": "user_a", "searchable": True} for i in range(8)}
        row = annotation("x", docs=list(docs), has_more=True)
        validate_row(row, self.case, docs)
        row["has_more"] = False
        with self.assertRaises(ValueError):
            validate_row(row, self.case, docs)

    def test_fixture_override_and_addition(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ("base.txt", "override.txt", "private.txt"):
                (root / name).write_text(name)
            manifest = [{"doc_id": "d", "path": "base.txt", "uploaded_at": "2026-01-01"}]
            env = {"id": "e", "fixtures": {"f": {"additional_documents": [{"doc_id": "b", "path": "private.txt"}],
                     "document_overrides": {"d": {"path": "override.txt", "uploaded_at": "2026-02-01"}}}}}
            docs = effective_documents({"id": "x", "environment_id": "e", "fixture_id": "f"}, manifest, env, root)
            self.assertEqual(docs["d"]["path"], "override.txt")
            self.assertEqual(docs["d"]["uploaded_at"], "2026-02-01")
            self.assertIn("b", docs)
            self.assertEqual(manifest[0]["path"], "base.txt")

    def test_blinding_uses_allowlist_and_predeclared_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, output = Path(tmp) / "source.jsonl", Path(tmp) / "blind.jsonl"
            rows = [{"id": id_, "query": "query", "context": [], "expected": {"secret": True},
                     "evidence_hint": "secret", "future_gold_field": "secret"} for id_ in reversed(CASE_IDS)]
            source.write_text("".join(json.dumps(row) + "\n" for row in rows))
            blind = prepare(source, output)
            self.assertEqual([row["id"] for row in blind], CASE_IDS)
            self.assertTrue(all(set(row) <= set(FIELDS) for row in blind))
            self.assertNotIn("secret", output.read_text())

    def test_blind_export_cannot_overwrite_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "source.jsonl"
            path.write_text("original data")
            with self.assertRaises(ValueError):
                prepare(path, path)
            self.assertEqual(path.read_text(), "original data")

    def test_adjudication_requires_dispute_coverage_and_immutable_originals(self):
        a, b = {"x": annotation("x")}, {"x": annotation("x", "no_result", [])}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "adjudication.jsonl"
            row = {"id": "x", "annotation_a": a["x"], "annotation_b": b["x"], "final": a["x"], "comment": "Verified source"}
            path.write_text(json.dumps(row) + "\n")
            validate_adjudication(path, a, b, a)
            row["annotation_a"] = b["x"]
            path.write_text(json.dumps(row) + "\n")
            with self.assertRaises(ValueError):
                validate_adjudication(path, a, b, a)

    def test_agreed_case_correction_must_be_explicit(self):
        a = {"x": annotation("x", filters={"doc_type": "seminar"})}
        final = {"x": annotation("x")}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "adjudication.jsonl"
            path.write_text("")
            with self.assertRaises(ValueError):
                validate_adjudication(path, a, a, final)
            row = {"id": "x", "annotation_a": a["x"], "annotation_b": a["x"],
                   "final": final["x"], "comment": "Removed a filter missing from source metadata"}
            path.write_text(json.dumps(row) + "\n")
            validate_adjudication(path, a, a, final)
            row["final"] = a["x"]
            path.write_text(json.dumps(row) + "\n")
            with self.assertRaises(ValueError):
                validate_adjudication(path, a, a, a)


if __name__ == "__main__":
    unittest.main()
