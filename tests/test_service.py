import io
import json
from pathlib import Path
import signal
import tempfile
import time
import unittest
from unittest.mock import patch

from junkie.archive import build_archive
from junkie.openrouter import ModelError, OpenRouterClient
from junkie.service import Service


class FakeClient:
    def __init__(self, answers):
        self.answers = iter(answers)
        self.calls = []
        self.messages = []

    def complete_json(self, messages, max_tokens=1200, purpose="query"):
        self.calls.append({"model": "test", "input_tokens": 1, "output_tokens": 1, "cost_usd": .001})
        self.messages.append(messages)
        answer = next(self.answers)
        if isinstance(answer, Exception):
            raise answer
        return answer


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "apple.txt").write_text("Apple pie recipe with cinnamon and flour.")
        (self.root / "private.txt").write_text("SECRET_PRIVATE_CONTENT")
        self.archive = build_archive(self.root, [
            {"doc_id": "a", "path": "apple.txt", "owner_id": "u", "uploaded_at": "2026-10-24", "source_type": "file"},
            {"doc_id": "b", "path": "private.txt", "owner_id": "other", "uploaded_at": "2026-10-24", "source_type": "file"}])

    def query(self, service, query="apple", **kwargs):
        return service.query(query, "u", "2026-10-24T12:00:00+03:00", "Europe/Moscow", **kwargs)

    def test_baseline_never_calls_model_and_ignores_history(self):
        service = Service(self.archive, "B1", FakeClient([]))
        output = self.query(service, context=[{"role": "assistant", "content": "irrelevant", "result_doc_ids": ["b"]}])
        self.assertEqual(output["status"], "ok")
        self.assertEqual(output["result_doc_ids"], ["a"])
        self.assertEqual(output["llm_usage"]["calls"], [])
        self.assertNotIn("b", output["trace"]["calls"][0]["read_doc_ids"])

    def test_direct_open_and_ownership(self):
        client = FakeClient([{"action": "get_document", "doc_id": "a"},
                             {"action": "get_document", "doc_id": "b"}])
        service = Service(self.archive, "Junkie", client)
        good = self.query(service, "открой первый", context=[{"role": "assistant", "result_doc_ids": ["a"], "content": "нашёл"}])
        self.assertEqual(good["result_doc_ids"], ["a"])
        self.assertTrue(good["observations"]["source_checks"][0]["snippet_supported"])
        bad = self.query(service, "открой b")
        self.assertEqual(bad["action"], "refuse")
        self.assertEqual(bad["trace"]["calls"], [])
        self.assertNotIn("SECRET_PRIVATE_CONTENT", json.dumps(bad))

    def test_source_observation_checks_the_actual_source(self):
        service = Service(self.archive, "B0")
        card = self.archive.get_document("a", "u")["result"]
        self.assertTrue(service._observations([card], "u")["source_checks"][0]["openable"])
        card["source"] = "saved://b"
        self.assertFalse(service._observations([card], "u")["source_checks"][0]["openable"])

    def test_ordered_midway_fault_is_retried(self):
        service = Service(self.archive, "Junkie", FakeClient([
            {"action": "search", "query": "apple", "filters": {}, "open_first": True}]),
            fault={"tool": "get_document", "occurrence": 1, "error_code": "unavailable"})
        result = self.query(service)
        self.assertEqual(result["result_doc_ids"], ["a"])
        self.assertEqual([(c["name"], c["status"]) for c in result["trace"]["calls"]],
                         [("search_documents", "ok"), ("get_document", "error"), ("get_document", "ok")])

    def test_persistent_fault_stops_at_budget(self):
        service = Service(self.archive, "B0", max_tool_calls=3,
                          fault={"tool": "search_documents", "persistent": True, "error_code": "unavailable"})
        output = self.query(service)
        self.assertEqual(output["reason"], "step_budget_exhausted")
        self.assertEqual(service.termination_reason, "budget_exhausted")
        self.assertEqual(len(output["trace"]["calls"]), 3)
        self.assertEqual(self.query(service)["trace"]["calls"], [])

    def test_midway_fault_requires_successful_search(self):
        service = Service(self.archive, "Junkie", FakeClient([
            {"action": "get_document", "doc_id": "a"},
            {"action": "search", "query": "apple", "filters": {}, "open_first": True}]),
            fault={"tool": "get_document", "occurrence": 1, "error_code": "unavailable",
                   "after_successful_tool": "search_documents"})
        direct = self.query(service, context=[{"role":"assistant","result_doc_ids":["a"]}])
        self.assertEqual([c["status"] for c in direct["trace"]["calls"]], ["ok"])
        searched = self.query(service)
        self.assertEqual([(c["name"], c["status"]) for c in searched["trace"]["calls"]],
                         [("search_documents", "ok"), ("get_document", "error"), ("get_document", "ok")])

    def test_invalid_filter_not_executed(self):
        service = Service(self.archive, "Junkie", FakeClient([
            {"action": "search", "query": "x", "filters": {"owner_id": "other"}}]))
        output = self.query(service)
        self.assertEqual(output["status"], "error")
        self.assertEqual(output["trace"]["model_steps"][0]["invalid_field"], "filters.owner_id")
        self.assertEqual(output["trace"]["calls"], [])

    def test_ambiguous_open_only_uses_allowed_candidates(self):
        (self.root / "apple-v2.txt").write_text("apple revised recipe")
        self.archive.ingest({"path":"apple-v2.txt"}, "u", "2026-10-24", doc_id="v2")
        plan = {"action":"search","query":"apple","filters":{},"open_first":True}
        for answer, status in [({"action":"clarify","question":"Какая версия рецепта нужна?"}, "ok"),
                               ({"action":"open","doc_id":"b"}, "error")]:
            client = FakeClient([plan, answer])
            result = self.query(Service(self.archive, "Junkie", client), "открой рецепт")
            self.assertEqual(result["status"], status)
            self.assertEqual([c["name"] for c in result["trace"]["calls"]], ["search_documents"])
            self.assertEqual(result["result_doc_ids"], [])
            self.assertNotIn("private.txt", client.messages[1][1]["content"])
            if status == "ok":
                self.assertEqual(result["action"], "clarify")

    def test_filename_retry_is_visible_in_trace(self):
        (self.root / "pineapple.txt").write_text("tropical fruit")
        self.archive.ingest({"path":"pineapple.txt"}, "u", "2026-10-24", doc_id="fruit")
        client = FakeClient([{"action":"search","query":"","filters":{"filename":"pineaple.txt"}}])
        result = self.query(Service(self.archive, "Junkie", client), "найди pineaple.txt")
        self.assertEqual(result["result_doc_ids"], ["fruit"])
        self.assertTrue(result["trace"]["calls"][1]["filename_fallback"])

    def test_invalid_ingestion_gated_before_model(self):
        client = FakeClient([])
        service = Service(self.archive, "Junkie", client)
        output = service.ingest({"generator": "repeat_byte", "byte": "x", "size_bytes": 26214401,
                                 "filename": "large.txt"}, "u", "2026-10-24T12:00:00+03:00")
        self.assertEqual(output["action"], "reject")
        self.assertEqual(output["reason"], "too_large")
        self.assertEqual(client.calls, [])

    def test_search_timeout_retries_and_restores_signal(self):
        service = Service(self.archive, "B0", tool_timeout_s=.01)
        old_handler = signal.getsignal(signal.SIGALRM)
        with patch.object(self.archive, "search", side_effect=lambda **kwargs: time.sleep(.05)):
            result = self.query(service)
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error_code"], "timeout")
        self.assertEqual([c["error_code"] for c in result["trace"]["calls"]], ["timeout"] * 3)
        self.assertEqual(signal.getsignal(signal.SIGALRM), old_handler)
        self.assertEqual(signal.getitimer(signal.ITIMER_REAL), (0, 0))

    def test_ingestion_timeout_escapes_parser_exception_handler(self):
        service = Service(self.archive, "Junkie", FakeClient([]), ingestion_timeout_s=.01)
        with patch.object(self.archive, "_add", side_effect=lambda *args, **kwargs: time.sleep(.05)):
            result = service.ingest({"path": "apple.txt"}, "u", "2026-10-24T12:00:00+03:00", "new")
        self.assertEqual(result["status"], "timeout")
        self.assertEqual(result["error_code"], "timeout")
        self.assertEqual(result["llm_usage"]["calls"], [])

    def test_get_timeout_keeps_declared_tool_error_code(self):
        service = Service(self.archive, "Junkie", FakeClient([
            {"action": "get_document", "doc_id": "a"}]), tool_timeout_s=.01)
        with patch.object(self.archive, "get_document", side_effect=lambda *args: time.sleep(.05)):
            result = self.query(service, context=[{"role":"assistant","result_doc_ids":["a"]}])
        self.assertEqual(result["error_code"], "unavailable")
        self.assertTrue(all(c["error_code"] == "unavailable" and c["failure_reason"] == "timeout"
                            for c in result["trace"]["calls"]))

    def test_ingestion_deadline_includes_metadata_generation(self):
        client = FakeClient([])
        service = Service(self.archive, "Junkie", client, ingestion_timeout_s=.01)
        with patch.object(client, "complete_json", side_effect=lambda *args, **kwargs: time.sleep(.05)):
            result = service.ingest({"path": "apple.txt"}, "u", "2026-10-24T12:00:00+03:00", "new")
        self.assertEqual(result["status"], "timeout")
        self.assertTrue(result["observations"]["source_saved"])

    def test_metadata_stored_and_usage_recorded(self):
        client = FakeClient([{"title": "Apple pie", "topic": "Cooking", "description": "Recipe",
                              "tags": ["apple", "pie", "cinnamon"]}])
        service = Service(self.archive, "Junkie", client)
        output = service.ingest({"path": "apple.txt", "source_type": "file"}, "u", "2026-10-24T12:00:00+03:00", "new")
        self.assertEqual(output["metadata"]["title"], "Apple pie")
        self.assertEqual(self.archive.documents["new"]["metadata"]["title"], "Apple pie")
        self.assertEqual(len(output["llm_usage"]["calls"]), 1)
        self.assertNotIn("SECRET_PRIVATE_CONTENT", json.dumps(client.messages))

    def test_model_failure_not_fabricated_success(self):
        output = self.query(Service(self.archive, "Junkie", FakeClient([ModelError("model_unavailable")])))
        self.assertEqual(output["status"], "error")
        self.assertEqual(output["result_doc_ids"], [])
        self.assertEqual(len(output["llm_usage"]["calls"]), 1)


class ClientTests(unittest.TestCase):
    def test_gemini_reasoning_included_in_output_usage(self):
        client = OpenRouterClient("google/gemini-3.5-flash-lite", 1, 2, api_key="secret")
        response = {"usage": {"prompt_tokens": 10, "completion_tokens": 120,
                              "completion_tokens_details": {"reasoning_tokens": 100}, "cost": .000303},
                    "choices": [{"finish_reason": "stop", "message": {"content": '{"ok":true}'}}]}
        with patch("urllib.request.urlopen", return_value=io.StringIO(json.dumps(response))) as network:
            client.complete_json([{"role": "user", "content": "hello"}], max_tokens=900)
        body = json.loads(network.call_args.args[0].data)
        self.assertEqual(body["reasoning"], {"effort": "minimal"})
        self.assertEqual(body["max_tokens"], 900)
        self.assertFalse(body["provider"]["allow_fallbacks"])
        self.assertEqual(client.calls[0]["output_tokens"], 120)
        self.assertEqual(client.calls[0]["reasoning_tokens"], 100)
        self.assertEqual(client.calls[0]["finish_reason"], "stop")
        self.assertAlmostEqual(client.accounted_spend_usd, .000303)

    def test_budget_checked_before_network(self):
        client = OpenRouterClient("test", budget_usd=.00001, max_calls=2, api_key="secret")
        with patch("urllib.request.urlopen") as network, self.assertRaisesRegex(ModelError, "cost_budget"):
            client.complete_json([{"role": "user", "content": "hello"}])
        network.assert_not_called()
        self.assertEqual(client.calls, [])

    def test_malformed_json_preserves_cost_and_no_secret_in_ledger(self):
        client = OpenRouterClient("test", 1, 2, api_key="do-not-log")
        response = {"id": "gen1", "model": "test", "usage": {"prompt_tokens": 10, "completion_tokens": 5, "cost": .001},
                    "choices": [{"message": {"content": "not json"}}]}
        with patch("urllib.request.urlopen", return_value=io.StringIO(json.dumps(response))), self.assertRaises(ModelError):
            client.complete_json([{"role": "user", "content": "hello"}])
        self.assertEqual(client.calls[0]["cost_usd"], .001)
        self.assertAlmostEqual(client.accounted_spend_usd, .001)
        self.assertNotIn("do-not-log", json.dumps(client.calls))

    def test_unknown_bill_keeps_reservation(self):
        client = OpenRouterClient("test", 1, 1, api_key="secret")
        response = {"choices": [{"message": {"content": '{"ok":true}'}}]}
        with patch("urllib.request.urlopen", return_value=io.StringIO(json.dumps(response))) as network:
            self.assertEqual(client.complete_json([{"role": "user", "content": "hello"}]), {"ok": True})
        body = json.loads(network.call_args.args[0].data)
        self.assertEqual(body["provider"]["max_price"]["completion"], 2.50)
        self.assertIsNone(client.calls[0]["cost_usd"])
        self.assertGreater(client.accounted_spend_usd, 0)
        with self.assertRaisesRegex(ModelError, "model_call_budget"):
            client.complete_json([{"role": "user", "content": "again"}])


if __name__ == "__main__":
    unittest.main()
