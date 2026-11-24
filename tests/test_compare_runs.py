import unittest
from copy import deepcopy

from kt3.compare_runs import compare


class SameCohort(unittest.TestCase):
    def setUp(self):
        self.old = {
            "input_sha256": {"/runner/eval/queries/dev.jsonl":"a"},
            "run":{"git_commit":"a","config":{"search_case_ids":["X"], "fixture_version":"1",
                   "scenario_budgets":{}, "ingestion_timeout_s":120}},
            "cases":{"X":{"metrics":{"Hit":{"value":0}},"checks":{}}},
            "not_run":[], "checks":{}, "metrics":{"Hit":{"status":"ok","value":0}},
        }

    def test_case_gain_and_unscored_case_are_different(self):
        new = deepcopy(self.old)
        new["metrics"]["Hit"]["value"] = new["cases"]["X"]["metrics"]["Hit"]["value"] = 1
        row = compare(self.old,new)["metrics"]["Hit"]
        self.assertEqual((row["delta"],row["increased"]), (1,["X"]))
        new["metrics"]["Hit"] = {"status":"pending","value":None}
        new["cases"]["X"]["metrics"]["Hit"]["value"] = None
        row = compare(self.old,new)["metrics"]["Hit"]
        self.assertEqual((row["delta"],row["increased"],row["changed_availability"]), (None,[],["X"]))

    def test_reject_different_gold_or_case_selection(self):
        new = deepcopy(self.old)
        new["input_sha256"]["/runner/eval/queries/dev.jsonl"] = "b"
        with self.assertRaises(ValueError):
            compare(self.old,new)
        new = deepcopy(self.old)
        new["run"]["config"]["search_case_ids"] = ["Y"]
        with self.assertRaises(ValueError):
            compare(self.old,new)
