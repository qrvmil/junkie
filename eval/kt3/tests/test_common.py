import unittest

from eval.kt3.common import aggregate_cases, cell, na, output_hash, pending, review_for, summarize
from eval.kt3.telemetry import cost, latency


class CommonTests(unittest.TestCase):
    def test_pending_does_not_improve_mean(self):
        result = summarize([cell(1), pending("judge unavailable"), na("no filter")])
        self.assertIsNone(result["value"])
        self.assertEqual(result["eligible"], 2)
        self.assertEqual(summarize([cell(1), cell(0)])["value"], .5)

    def test_review_cannot_be_reused_after_answer_changes(self):
        output = {"id": "E1", "response": "a"}
        review = {"id": "E1", "kind": "messages", "status": "ok", "output_sha256": output_hash(output)}
        self.assertEqual(review_for([review], output, "messages"), review)
        with self.assertRaisesRegex(ValueError, "stale"):
            review_for([review], {**output, "response": "b"}, "messages")

    def test_timeout_not_fast_success(self):
        cases = [{"id": "a"}, {"id": "b"}, {"id": "c"}]
        result = latency(cases, [{"id": "a", "status": "ok", "action": "search", "result_doc_ids": [], "elapsed_ms": 100},
                                 {"id": "b", "status": "timeout", "elapsed_ms": 1}], {"search"})
        self.assertEqual(result["p95"], 100)
        self.assertEqual(result["outcomes"], {"ok": 1, "timeout": 1, "missing": 1})

    def test_unknown_price_not_zero(self):
        self.assertIsNone(cost([{"id": "a"}])["cost_usd"])
        self.assertEqual(cost([{"id": "a", "llm_usage": {"complete": True, "calls": []}}])["cost_usd"], 0)
        self.assertIsNone(cost([{"id": "a", "llm_usage": {"complete": True, "calls": [
            {"model": "x", "input_tokens": 10, "output_tokens": 2}]}}])["cost_usd"])

    def test_partial_cost_preserves_known_spend(self):
        result = cost([{"id": "a", "llm_usage": {"complete": False, "calls": [{"cost_usd": .5}]}}])
        self.assertEqual(result["known_cost_usd"], .5)
        self.assertIsNone(result["cost_usd"])

    def test_invalid_success_excluded_from_latency(self):
        result = latency([{"id": "a"}], [{"id": "a", "status": "ok", "action": "search",
                         "result_doc_ids": "wrong", "elapsed_ms": 1}], {"search"})
        self.assertIsNone(result["p95"])
        self.assertEqual(result["invalid_success"], ["a"])


if __name__ == "__main__":
    unittest.main()
