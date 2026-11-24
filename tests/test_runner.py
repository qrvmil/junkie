import copy
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest

from eval.kt3.common import read_jsonl
from junkie.run import ROOT, run_once, run_scenario, search_rows, select_cases, safe_call, judge_rows


class FakeArchive:
    def __init__(self, docs=None):
        self.documents = dict(docs or {})
        self.preparation = {"test": True}

    def clone(self):
        return FakeArchive(self.documents)

    def without(self, doc_id):
        result = self.clone()
        result.documents.pop(doc_id, None)
        return result


class FakeService:
    calls = []

    def __init__(self, archive, variant, client=None, max_tool_calls=8, fault=None, ingestion_timeout_s=120):
        self.archive = archive
        self.termination_reason = "completed"
        self.max_tool_calls = max_tool_calls
        self.fault = fault

    def query(self, **kwargs):
        self.calls.append(copy.deepcopy(kwargs))
        return {"status": "ok", "action": "search", "result_doc_ids": ["doc_001"],
                "response": "Actual answer", "trace": {"complete": True, "calls": []},
                "llm_usage": {"complete": True, "calls": []}, "elapsed_ms": 10}

    def ingest(self, **kwargs):
        return {"status": "ok", "action": "reject", "reason": "unsupported_format",
                "llm_usage": {"complete": True, "calls": []}, "elapsed_ms": 10}


class RunnerTests(unittest.TestCase):
    def setUp(self):
        FakeService.calls = []

    def test_service_receives_no_gold_or_case_id(self):
        case = {"id": "E1", "query": "Find x", "expected": {"secret": "gold"},
                "expected_calls": ["oracle"], "gold_steps": {"oracle": 1}, "fixture_id": "base",
                "user_id": "u", "now": "2026-10-24T12:00:00+03:00", "timezone": "Europe/Moscow",
                "context": [{"role": "user", "content": "previous"}]}
        result = list(search_rows([case], {"base": FakeArchive()}, FakeService, "B0", None, ingestion_timeout_s=120))
        self.assertEqual(result[0]["id"], "E1")
        self.assertEqual(set(FakeService.calls[0]), {"query", "user_id", "now", "timezone", "context"})
        self.assertEqual(FakeService.calls[0]["query"], "Find x")

    def test_clean_controls_are_new_queries(self):
        case = {"id": "E1", "query": "typo", "clean_query": "clean", "variant_type": "typo",
                "user_id": "u", "now": "2026-10-24", "timezone": "UTC"}
        rows = list(search_rows([case], {"base": FakeArchive()}, FakeService, "B1", None, clean=True, ingestion_timeout_s=120))
        self.assertEqual(FakeService.calls[0]["query"], "clean")
        self.assertEqual(rows[0]["id"], "E1")

    def test_scenario_uses_actual_previous_answers_not_assertions(self):
        spec = {"id": "S", "max_steps": 3, "user_id": "u", "now": "2026-10-24", "timezone": "UTC",
                "turns": [{"user": "first", "assert": {"results_exact_set": ["gold-doc"]}},
                          {"user": "second", "assert": {"action": "refuse"}}]}
        result = run_scenario(spec, FakeArchive(), FakeService, "B1", None, ingestion_timeout_s=120)
        history = FakeService.calls[1]["context"]
        self.assertEqual(history, [{"role": "user", "content": "first"},
                                  {"role": "assistant", "content": "Actual answer", "result_doc_ids": ["doc_001"]}])
        self.assertEqual(result["steps"][1]["action"], "search")
        self.assertEqual(result["status"], "ok")  # execution finished, not a quality claim

    def test_missing_ingested_document_observed_after_setup(self):
        spec = {"id": "S", "max_steps": 3, "user_id": "u", "now": "2026-10-24", "timezone": "UTC",
                "turns": [{"input": {"path": "a.txt", "assigned_doc_id": "a"}, "assert": {}}]}
        archive = FakeArchive({"a": {"text": "a"}})
        result = run_scenario(spec, archive, FakeService, "B0", None, ingestion_timeout_s=120)
        self.assertEqual(result["initial_observations"]["absent_doc_ids"], ["a"])
        self.assertIn("a", archive.documents)

    def test_failures_remain_rows_and_do_not_expose_exception(self):
        def fail():
            raise RuntimeError("secret-token-do-not-log")
        result = safe_call(fail, id_="E1")
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["id"], "E1")
        self.assertNotIn("secret-token", str(result))
        self.assertEqual(result["llm_usage"], {"complete": True, "calls": []})

    def test_selection_fixed_and_validated(self):
        cases = [{"id": x} for x in ("E01", "E02", "E19", "E22")]
        self.assertEqual([x["id"] for x in select_cases(cases, limit=3)], ["E01", "E19", "E22"])
        for ids in ("E01,E01", "unknown"):
            with self.assertRaises(ValueError):
                select_cases(cases, case_ids=ids)

    def test_judge_budget_failure_keeps_task_and_no_call_cost(self):
        from junkie.openrouter import ModelError
        class ExhaustedClient:
            model = "test/model"
            calls = []
            def complete_json(self, *args, **kwargs):
                raise ModelError("cost_budget_exhausted")
        case = {"id": "E1", "query": "Show all", "expected": {"action": "search", "has_more": True}}
        output = {"id": "E1", "status": "ok", "action": "search", "result_doc_ids": [],
                  "response": "More matches exist"}
        rows = list(judge_rows([case], [output], [], {"fixtures": {"base": {}}}, ExhaustedClient()))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["status"], "error")
        self.assertEqual(rows[0]["error_code"], "cost_budget_exhausted")
        self.assertEqual(rows[0]["usage"], {"input_tokens": 0, "output_tokens": 0, "cost_usd": 0})
        self.assertEqual(len(rows[0]["output_sha256"]), 64)

    def test_partial_run_report_uses_selected_cohort(self):
        args = SimpleNamespace(eval_root=ROOT / "eval", limit=None, case_ids="E01,E19", skip_ingestion=True,
                               scenarios=False, variant="B0", model=None, budget_usd=1, max_calls=10,
                               ingestion_timeout_s=120, judge=False)
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "run"
            result = run_once(args, out, 1, None,
                              archive_factory=lambda root, docs, fixture: FakeArchive(), service_factory=FakeService)
            self.assertEqual(len(result["cases"]), 2)
            self.assertEqual(result["metrics"]["ActionAccuracy"]["eligible"], 2)
            self.assertEqual(len(read_jsonl(out / "search.jsonl")), 2)
            self.assertEqual(len(read_jsonl(out / "clean.jsonl")), 1)
            self.assertEqual(result["cost"]["search"]["cost_usd"], 0)
            self.assertGreaterEqual(result["run_elapsed_ms"], result["preparation"]["elapsed_ms"])
            self.assertTrue((out / "report.json").exists())
            self.assertEqual(result["not_run"], ["ingestion", "scenarios"])


if __name__ == "__main__":
    unittest.main()
