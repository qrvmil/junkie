import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from eval.kt3.common import read_jsonl, output_hash
from eval.kt3.evaluate import evaluate, main
from eval.kt3.judge import build_tasks, PROMPT_PATH
from eval.kt3.judge import judge_task
from eval.kt3.ingestion import manual_review_template
from eval.metrics.score import score as score_kt2

ROOT = Path(__file__).resolve().parents[2]


class EvaluateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = read_jsonl(ROOT / "queries/dev.jsonl")
        cls.docs = read_jsonl(ROOT / "documents.jsonl")
        cls.environment = json.loads((ROOT / "fixtures/environment.json").read_text())

    def test_real_gold_old_metrics_match(self):
        # A small synthetic mix, not a measured system or baseline.
        predictions = [{"id": "E01", "status": "ok", "action": "search", "result_doc_ids": ["doc_001", "doc_001"]},
                       {"id": "E02", "status": "timeout"},
                       {"id": "E03", "status": "ok", "action": "refuse", "result_doc_ids": []}]
        old = score_kt2(self.cases, predictions)
        new = evaluate(self.cases, predictions, self.docs, self.environment)
        for name, metric in old["metrics"].items():
            self.assertEqual(new["metrics"][name]["value"], metric["value"], name)
            self.assertEqual(new["metrics"][name]["eligible"], metric["n"], name)
        self.assertEqual(new["by_gold_action"]["search"]["metrics"]["ActionAccuracy"]["eligible"], 116)
        self.assertIsNone(new["cost"]["search"]["cost_usd"])

    def test_all_missing_does_not_report_zero_cost(self):
        new = evaluate(self.cases, [], self.docs, self.environment)
        self.assertEqual(new["metrics"]["HitRate@5"]["value"], 0)
        self.assertIsNone(new["cost"]["search"]["cost_usd"])
        self.assertEqual(new["metrics"]["TypoHitRateDrop"]["status"], "pending")

    def test_changed_judge_input_rejected(self):
        import hashlib
        case = next(c for c in self.cases if c["id"] == "E22")
        output = {"id": "E22", "status": "ok", "action": "clarify", "result_doc_ids": [], "response": "Какой PDF?"}
        task = build_tasks([case], [output], self.docs, self.environment)[0]
        review = {**task, "status": "ok", "checks": {"clarification_useful": {"passed": True, "reason": "Asks title"}},
                  "prompt_sha256": hashlib.sha256(PROMPT_PATH.read_bytes()).hexdigest()}
        evaluate([case], [output], self.docs, self.environment, reviews=[review])
        with self.assertRaisesRegex(ValueError, "judge input"):
            evaluate([{**case, "query": "different"}], [output], self.docs, self.environment, reviews=[review])

    def test_judge_and_manual_reviews_complete_report(self):
        case = next(c for c in self.cases if c["id"] == "E89")
        output = {"id": "E89", "status": "ok", "action": "search",
                  "result_doc_ids": case["expected"]["relevant_doc_ids"][:5],
                  "response": "Есть ещё результаты. Уточните тему."}
        task = build_tasks([case], [output], self.docs, self.environment)[0]
        fake = {"choices": [{"message": {"content": json.dumps({"checks": {
            "mentions_more": {"passed": True, "reason": "Says more"},
            "suggests_narrowing": {"passed": True, "reason": "Asks topic"}}})}}]}
        with patch("eval.kt3.judge.request_judgment", return_value=fake):
            judged = judge_task(task, PROMPT_PATH.read_text(), "unit-test", "unused")
        ing_case = read_jsonl(ROOT / "queries/ingestion.jsonl")[0]
        gold = read_jsonl(ROOT / "ingestion/gold.jsonl")[0]
        ing_output = {"id": "I01", "status": "ok", "action": "ingest", "elapsed_ms": 100,
                      "extracted_text": "\n".join(f["quote"] for f in gold["fragments"]),
                      "observations": {"source_saved": True, "source_openable": True, "searchable": True},
                      "metadata": {"title": "Test", "description": "Test", "topic": "Test",
                                   "tags": ["a", "b", "c"], "uploaded_at": "2026-10-24"}}
        manual = manual_review_template([ing_case], [ing_output], [gold])[0]
        manual.update(status="ok", reviewer="unit-test")
        for field in manual["fields"].values():
            field.update(passed=True, reason="Synthetic test")
        for i, tag in enumerate(manual["tags"]):
            tag.update(supported=True, concept_id=str(i), reason="Synthetic test")
        result = evaluate([case], [output], self.docs, self.environment,
                          ingestion_cases=[ing_case], ingestion_outputs=[ing_output], ingestion_gold=[gold],
                          ingestion_timeout_s=120, reviews=[judged, manual])
        for name in ("OverflowHandling", "MetadataCompleteness/mean", "ExtractionCoverage", "TagRelevance"):
            self.assertEqual(result["metrics"][name]["value"], 1, name)
        self.assertIsNone(result["cost"]["judge"]["cost_usd"])

    def test_cli_search_ingestion_scenarios_without_paid_calls(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            run = {"run_id": "unit-test", "variant": "B0", "git_commit": "test-fixture",
                   "model": None, "temperature": None, "seed": None, "prompts": []}
            (p / "run.json").write_text(json.dumps(run))
            (p / "empty.jsonl").write_text("")
            args = ["evaluate", "--run", str(p / "run.json"), "--predictions", str(p / "empty.jsonl"),
                    "--ingestion-outputs", str(p / "empty.jsonl"), "--ingestion-timeout-s", "120",
                    "--scenario-outputs", str(p / "empty.jsonl"), "--output", str(p / "report.json")]
            with patch("sys.argv", args), contextlib.redirect_stdout(io.StringIO()):
                main()
            report = json.loads((p / "report.json").read_text())
            self.assertEqual(len(report["cases"]), 157)
            self.assertEqual(report["metrics"]["IngestionSuccessRate"]["value"], 0)
            self.assertEqual(report["metrics"]["DialogueSuccessRate"]["value"], 0)
            self.assertIsNone(report["cost"]["ingestion"]["cost_usd"])
            self.assertIn(str(ROOT / "ingestion/gold.jsonl"), report["input_sha256"])


if __name__ == "__main__":
    unittest.main()
