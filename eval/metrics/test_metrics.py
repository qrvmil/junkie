"""Hand-calculated regressions for gold cohorts, failures, empty slices and ranking."""
import copy
import json
import unittest
from pathlib import Path

from score import score


def case(id_, action="search", docs=None):
    return {"id": id_, "expected": {"action": action,
            "relevant_doc_ids": docs if docs is not None else (["d1"] if action == "search" else [])}}


def prediction(id_, action="search", docs=None, status="ok"):
    return {"id": id_, "status": status, "action": action,
            "result_doc_ids": docs if docs is not None else (["d1"] if action == "search" else [])}


class MetricTests(unittest.TestCase):
    def test_hand_calculated_ranking_and_denominators(self):
        cases = [case("a", docs=["d1", "d2"]), case("b"), case("c", "no_result"), case("d", "clarify")]
        outputs = [prediction("a", docs=["wrong", "d2", "d2", "d1"]), prediction("b", "refuse"),
                   prediction("c", "no_result"), prediction("d", "clarify")]
        report = score(cases, outputs)
        expected = {"HitRate@5": (0.5, 2), "MRR@5": (0.25, 2), "Recall@5": (0.5, 2),
                    "Precision@5": (0.2, 2), "ActionAccuracy": (0.75, 4), "FalseRefusalRate": (0.5, 2)}
        for name, (value, n) in expected.items():
            self.assertAlmostEqual(report["metrics"][name]["value"], value)
            self.assertEqual(report["metrics"][name]["n"], n)

    def test_failure_and_missing_output_remain_in_denominator(self):
        cases = [case(str(i)) for i in range(5)]
        outputs = [prediction("0"), prediction("1", status="timeout"), prediction("2", status="error"),
                   prediction("3", action="Answer")]
        report = score(cases, outputs)
        self.assertEqual(report["metrics"]["HitRate@5"], {"value": 0.2, "sum": 1.0, "n": 5})
        self.assertEqual(report["metrics"]["ActionAccuracy"]["value"], 0.2)
        self.assertEqual(report["metrics"]["FalseRefusalRate"]["value"], 0)
        for outcome in ("error", "timeout", "invalid", "missing"):
            self.assertEqual(report["outcome_counts"][outcome], 1)

    def test_prediction_action_cannot_change_search_cohort(self):
        report = score([case("a"), case("b", "no_result")],
                       [prediction("a", "clarify"), prediction("b")])
        self.assertEqual(report["metrics"]["HitRate@5"]["n"], 1)
        self.assertEqual(report["metrics"]["HitRate@5"]["value"], 0)
        self.assertEqual(report["metrics"]["ActionAccuracy"]["value"], 0)

    def test_zero_applicable_cases_returns_null_not_success(self):
        report = score([case("a", "no_result")], [prediction("a", "no_result")])
        for name in ("HitRate@5", "MRR@5", "Recall@5", "Precision@5", "FalseRefusalRate"):
            self.assertEqual(report["metrics"][name], {"value": None, "sum": 0.0, "n": 0})
        self.assertIsNone(report["action_accuracy_by_gold_action"]["clarify"]["value"])
        self.assertEqual(report["action_accuracy_by_gold_action"]["no_result"]["value"], 1)

    def test_top_five_is_not_promoted_after_deduplication(self):
        report = score([case("a")], [prediction("a", docs=["wrong"] * 5 + ["d1"])])
        for name in ("HitRate@5", "MRR@5", "Recall@5", "Precision@5"):
            self.assertEqual(report["metrics"][name]["value"], 0)

    def test_recall_and_precision_have_their_documented_ceiling(self):
        report = score([case("a"), case("b", docs=[f"d{i}" for i in range(6)])],
                       [prediction("a"), prediction("b", docs=[f"d{i}" for i in range(5)])])
        self.assertEqual(report["metrics"]["HitRate@5"]["value"], 1)
        self.assertEqual(report["metrics"]["MRR@5"]["value"], 1)
        self.assertAlmostEqual(report["metrics"]["Recall@5"]["value"], (1 + 5 / 6) / 2)
        self.assertAlmostEqual(report["metrics"]["Precision@5"]["value"], (0.2 + 1) / 2)

    def test_malformed_response_is_failure_not_a_dropped_case(self):
        for output in [{"id": "a"}, prediction("a", docs="d1"), prediction("a", docs=[None]),
                       prediction("a", "no_result", docs=["d1"]), prediction("a", status="unknown")]:
            report = score([case("a")], [output])
            self.assertEqual(report["metrics"]["ActionAccuracy"]["n"], 1)
            self.assertEqual(report["outcome_counts"]["invalid"], 1)

    def test_duplicates_and_unknown_ids_fail_loudly(self):
        for cases, outputs in [([case("a"), case("a")], []), ([case("a")], [prediction("x")]),
                               ([case("a")], [prediction("a"), prediction("a")]), ([], [])]:
            with self.assertRaises(ValueError):
                score(cases, outputs)

    def test_empty_search_gold_is_an_error_not_excluded_case(self):
        with self.assertRaises(ValueError):
            score([case("a", docs=[])], [])

    def test_inputs_are_not_mutated(self):
        cases, outputs = [case("a")], [prediction("a", docs=["d1", "d1"])]
        before = copy.deepcopy((cases, outputs))
        score(cases, outputs)
        self.assertEqual((cases, outputs), before)

    def test_current_dataset_oracle_has_full_hit_rate_without_fake_benchmark(self):
        # Synthetic responses from gold test the formula, not search quality.
        path = Path(__file__).resolve().parents[1] / "queries/dev.jsonl"
        cases = [json.loads(s) for s in path.read_text(encoding="utf-8").splitlines()]
        outputs = [prediction(c["id"], c["expected"]["action"], c["expected"]["relevant_doc_ids"][:5]) for c in cases]
        report = score(cases, outputs)
        self.assertEqual(report["gold_action_counts"], {"search": 116, "clarify": 6, "no_result": 9, "refuse": 9})
        self.assertEqual(report["metrics"]["HitRate@5"], {"value": 1.0, "sum": 116.0, "n": 116})
        self.assertEqual(report["metrics"]["ActionAccuracy"], {"value": 1.0, "sum": 140.0, "n": 140})
        self.assertEqual(report["metrics"]["MRR@5"]["value"], 1)


if __name__ == "__main__":
    unittest.main()
