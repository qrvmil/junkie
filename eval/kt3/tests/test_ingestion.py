import copy
import unittest

from eval.kt3.common import output_hash
from eval.kt3.ingestion import manual_review_template, score_ingestion


class IngestionMetricsTests(unittest.TestCase):
    def setUp(self):
        self.case = {"id": "I01", "category": "ingestion", "expected": {"action": "ingest"},
                     "now": "2026-10-24T12:00:00+03:00", "timezone": "Europe/Moscow"}
        self.gold = {"id": "I01", "source": {"path": "recipe.txt"},
                     "fragments": [{"id": "a", "quote": "eight portions"}, {"id": "b", "quote": "190 degrees"}],
                     "metadata": {field: {"must_convey": ["recipe"], "must_not_claim": ["cinnamon"]}
                                  for field in ("title", "description", "topic")},
                     "tags": {"accepted_concepts": [], "rejected_examples": []}}
        self.output = {"id": "I01", "status": "ok", "action": "ingest",
                       "observations": {"source_saved": True, "source_openable": True, "searchable": True},
                       "extracted_text": "Eight portions, 190 degrees.", "elapsed_ms": 1000,
                       "metadata": {"title": "Recipe", "description": "Eight portions", "topic": "Cooking",
                                    "tags": ["apples", "recipe", "baking"], "uploaded_at": "2026-10-24"}}

    def review(self, output=None):
        output = output or self.output
        return {"id": "I01", "kind": "metadata", "output_sha256": output_hash(output),
                "status": "ok", "reviewer": "reviewer-a",
                "fields": {field: {"passed": True, "reason": "Confirmed by source"}
                           for field in ("title", "description", "topic")},
                "tags": [{"tag_index": i, "supported": True, "concept_id": str(i), "reason": "Source evidence"}
                         for i in range(len(output["metadata"]["tags"]))]}

    def score(self, outputs=None, reviews=None, timeout=60):
        return score_ingestion([self.case], [self.output] if outputs is None else outputs,
                               [self.gold], [] if reviews is None else reviews, timeout)["I01"]

    def test_complete_observations_and_review(self):
        result = self.score(reviews=[self.review()])
        self.assertTrue(all(item["status"] == "ok" and item["value"] == 1 for item in result["metrics"].values()))

    def test_missing_review_does_not_become_bad_quality(self):
        metrics = self.score()["metrics"]
        self.assertEqual(metrics["IngestionSuccessRate"]["value"], 1)
        self.assertEqual(metrics["MetadataCorrectness/Title"]["status"], "pending")
        self.assertEqual(metrics["MetadataCompleteness/mean"]["status"], "pending")
        self.assertEqual(metrics["TagRelevance"]["status"], "pending")

    def test_missing_outputs_and_errors_get_zero(self):
        for outputs in ([], [{"id": "I01", "status": "timeout"}], [{"id": "I01", "status": "error"}]):
            with self.subTest(outputs=outputs):
                self.assertTrue(all(item["value"] == 0 for item in self.score(outputs)["metrics"].values()))

    def test_wrong_action_cannot_pass_ingestion(self):
        self.output["action"] = "reject"
        self.assertTrue(all(item["value"] == 0 for item in self.score()["metrics"].values()))

    def test_missing_runner_observation_is_pending(self):
        del self.output["observations"]["searchable"]
        self.assertEqual(self.score()["metrics"]["IngestionSuccessRate"]["status"], "pending")
        self.output["observations"]["source_saved"] = False
        self.assertEqual(self.score()["metrics"]["IngestionSuccessRate"]["value"], 0)

    def test_timeout_is_separate_from_latency_slo(self):
        self.output["elapsed_ms"] = 50000
        self.assertEqual(self.score(timeout=60)["metrics"]["IngestionSuccessRate"]["value"], 1)
        self.assertEqual(self.score(timeout=45)["metrics"]["IngestionSuccessRate"]["value"], 0)
        for timeout in (None, False, 0, -1, float("inf"), float("nan")):
            with self.subTest(timeout=timeout), self.assertRaises(ValueError):
                self.score(timeout=timeout)

    def test_missing_duration_is_pending(self):
        del self.output["elapsed_ms"]
        self.assertEqual(self.score()["metrics"]["IngestionSuccessRate"]["status"], "pending")

    def test_added_date_uses_case_timezone(self):
        self.output["metadata"]["uploaded_at"] = "2026-10-23T21:00:00Z"
        self.assertEqual(self.score()["metrics"]["MetadataCorrectness/AddedDate"]["value"], 1)
        self.output["metadata"]["uploaded_at"] = "2026-10-23T20:59:59Z"
        self.assertEqual(self.score()["metrics"]["MetadataCorrectness/AddedDate"]["value"], 0)

    def test_invalid_date_and_naive_timestamp_fail(self):
        for value in ("2026-10-24T12:00:00", "2026-02-30", "20261024", None):
            self.output["metadata"]["uploaded_at"] = value
            with self.subTest(value=value):
                self.assertEqual(self.score()["metrics"]["MetadataCorrectness/AddedDate"]["value"], 0)

    def test_missing_field_forces_fullpass_zero_even_with_pending_tags(self):
        del self.output["metadata"]["title"]
        metrics = self.score()["metrics"]
        self.assertEqual(metrics["MetadataCorrectness/Title"]["value"], 0)
        self.assertEqual(metrics["MetadataCompleteness/FullPassRate"]["value"], 0)
        self.assertEqual(metrics["MetadataCompleteness/mean"]["status"], "pending")

    def test_synonyms_do_not_inflate_distinct_concepts(self):
        review = self.review()
        review["tags"][1]["concept_id"] = review["tags"][0]["concept_id"]
        metrics = self.score(reviews=[review])["metrics"]
        self.assertEqual(metrics["MetadataCompleteness/mean"]["value"], 0.8)
        self.assertEqual(metrics["MetadataCompleteness/FullPassRate"]["value"], 0)
        self.assertEqual(metrics["TagRelevance"]["value"], 1)

    def test_unsupported_tag_affects_relevance_not_presence(self):
        review = self.review()
        review["tags"][0]["supported"] = False
        metrics = self.score(reviews=[review])["metrics"]
        self.assertEqual(metrics["MetadataCompleteness/mean"]["value"], 1)
        self.assertAlmostEqual(metrics["TagRelevance"]["value"], 2 / 3)

    def test_empty_tags_need_no_manual_review(self):
        self.output["metadata"]["tags"] = []
        metrics = self.score()["metrics"]
        self.assertEqual(metrics["TagRelevance"]["value"], 0)
        self.assertEqual(metrics["MetadataCompleteness/mean"]["value"], 0.8)

    def test_partial_tag_review_stays_pending(self):
        review = self.review()
        review["tags"].pop()
        self.assertEqual(self.score(reviews=[review])["metrics"]["TagRelevance"]["status"], "pending")

    def test_duplicate_tag_indices_rejected(self):
        review = self.review()
        review["tags"][1]["tag_index"] = 0
        with self.assertRaises(ValueError):
            self.score(reviews=[review])

    def test_stale_review_rejected(self):
        review = self.review()
        self.output["metadata"]["title"] = "New answer"
        with self.assertRaises(ValueError):
            self.score(reviews=[review])

    def test_review_requires_reviewer_and_typed_decisions(self):
        for invalid in ("reviewer", "supported"):
            review = self.review()
            if invalid == "reviewer":
                review["reviewer"] = ""
            else:
                review["tags"][0]["supported"] = "false"
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                self.score(reviews=[review])

    def test_extraction_uses_anchors_not_repeated_occurrences(self):
        self.output["extracted_text"] = "EIGHT portions eight portions"
        self.assertEqual(self.score()["metrics"]["ExtractionCoverage"]["value"], 0.5)

    def test_manual_template_is_pending_and_bound_to_output(self):
        rows = manual_review_template([self.case], [self.output], [self.gold])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["output_sha256"], output_hash(self.output))
        self.assertEqual(rows[0]["status"], "pending")
        self.assertIsNone(rows[0]["fields"]["title"]["passed"])
        self.assertIsNone(rows[0]["tags"][0]["supported"])
        self.assertEqual(self.gold.get("human_review_status"), None)

    def test_invalid_gate_needs_complete_instrumentation(self):
        case = {"id": "I08", "category": "invalid_format",
                "expected": {"action": "reject", "reason": "unsupported_format", "model_calls": 0}}
        output = {"id": "I08", "status": "ok", "action": "reject", "reason": "unsupported_format"}
        def value():
            return score_ingestion([case], [output], [], [], 60)["I08"]["metrics"]["InvalidInput/Format"]
        self.assertEqual(value()["status"], "pending")
        output["llm_usage"] = {"complete": False, "calls": []}
        self.assertEqual(value()["status"], "pending")
        output["llm_usage"]["complete"] = True
        self.assertEqual(value()["value"], 1)
        output["llm_usage"]["calls"] = [{"model": "test"}]
        self.assertEqual(value()["value"], 0)
        output["llm_usage"]["complete"] = False
        self.assertEqual(value()["value"], 0)
        del output["llm_usage"]
        output["reason"] = "unavailable"
        self.assertEqual(value()["value"], 0)

    def test_corrupted_case_does_not_require_zero_model_calls(self):
        case = {"id": "I10", "category": "corrupted", "expected": {"action": "reject", "reason": "corrupted"}}
        output = {"id": "I10", "status": "ok", "action": "reject", "reason": "corrupted"}
        result = score_ingestion([case], [output], [], [], 60)
        self.assertEqual(result["I10"]["metrics"]["InvalidInput/Corrupted"]["value"], 1)

    def test_unknown_and_duplicate_outputs_rejected(self):
        for rows in ([{"id": "unknown"}], [self.output, copy.deepcopy(self.output)]):
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                self.score(rows)


if __name__ == "__main__":
    unittest.main()
