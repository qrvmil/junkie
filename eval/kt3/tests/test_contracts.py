import copy
import json
import unittest
from pathlib import Path

from eval.kt3.contracts import score_contracts, score_scenarios, subset


ROOT = Path(__file__).resolve().parents[2]


def call(name="search_documents", arguments=None, ids=None, status="ok", **extra):
    return {"name": name, "arguments": arguments or {"query": "exam", "filters": {}, "limit": 5,
            "order_by": "relevance"}, "status": status, "read_doc_ids": ids or [], **extra}


def step(ids=None, calls=None, action="search", **extra):
    return {"status": "ok", "action": action, "result_doc_ids": ids or [],
            "response": "Ответ", "trace": {"complete": True, "calls": calls or []}, **extra}


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.cases = [json.loads(line) for line in (ROOT / "queries/dev.jsonl").read_text().splitlines()]
        self.docs = [json.loads(line) for line in (ROOT / "documents.jsonl").read_text().splitlines()]
        self.env = json.loads((ROOT / "fixtures/environment.json").read_text())

    def check(self, id_, output):
        case = next(row for row in self.cases if row["id"] == id_)
        return score_contracts([case], [{"id": id_, **output}], self.docs, self.env)[id_]["checks"]

    def test_recursive_subset_does_not_coerce_bool_to_int(self):
        self.assertTrue(subset({"filters": {"format": "pdf"}}, {"filters": {"format": "pdf", "x": 1}}))
        self.assertFalse(subset({"limit": 1}, {"limit": True}))

    def test_allowed_direct_open(self):
        checks = self.check("E133", step(["doc_008"], [call("get_document", {"doc_id": "doc_008"}, ["doc_008"])]))
        self.assertEqual(checks["RequiredCalls"]["value"], 1)
        self.assertEqual(checks["ParsedQuery"]["status"], "not_applicable")
        self.assertEqual(checks["ArchiveAccess"]["value"], 1)

    def test_wrong_document_is_not_equivalent(self):
        checks = self.check("E133", step(["doc_007"], [call("get_document", {"doc_id": "doc_007"}, ["doc_007"])]))
        self.assertEqual(checks["RequiredCalls"]["value"], 0)

    def test_opening_does_not_require_search_parse(self):
        checks = self.check("E132", step(["doc_019"], [call("get_document", {"doc_id": "doc_019"}, ["doc_019"])]))
        self.assertEqual(checks["RequiredCalls"]["value"], 1)

    def test_other_case_does_not_get_blanket_equivalence(self):
        checks = self.check("E82", step(["doc_020"], [call("get_document", {"doc_id": "doc_020"}, ["doc_020"])]))
        self.assertEqual(checks["RequiredCalls"]["value"], 0)

    def test_failed_foreign_read_is_still_violation(self):
        output = step([], [call("get_document", {"doc_id": "doc_001"}, ["doc_001"], "error")], action="refuse")
        output["trace"]["complete"] = False
        self.assertEqual(self.check("E28", output)["ArchiveAccess"]["value"], 0)

    def test_incomplete_trace_is_not_acl_pass(self):
        output = step(["doc_008"])
        output.pop("trace")
        checks = self.check("E133", output)
        self.assertEqual(checks["ArchiveAccess"]["status"], "pending")
        self.assertEqual(checks["RequiredCalls"]["status"], "pending")

    def test_extra_filter_fails_parsed_query(self):
        output = step(["doc_008"], [call()], parsed_query={"filters": {"format": "pdf"}, "order_by": "relevance"})
        self.assertEqual(self.check("E133", output)["ParsedQuery"]["value"], 0)

    def test_missing_output_fails_positive_checks(self):
        case = next(row for row in self.cases if row["id"] == "E133")
        checks = score_contracts([case], [], self.docs, self.env)["E133"]["checks"]
        self.assertEqual(checks["Sources"]["value"], 0)
        self.assertEqual(checks["RequiredCalls"]["value"], 0)

    def test_source_opening_and_quote_observation_required(self):
        card = {"doc_id": "doc_008", "title": "Бланк", "snippet": "Заявление", "source": "saved://doc_008", "uploaded_at": "2026-10-18"}
        output = step(["doc_008"], results=[card])
        self.assertEqual(self.check("E133", output)["Sources"]["status"], "pending")
        output["observations"] = {"source_checks": [{"doc_id": "doc_008", "openable": True, "snippet_supported": False}]}
        self.assertEqual(self.check("E133", output)["Sources"]["value"], 0)
        output["observations"]["source_checks"][0]["snippet_supported"] = True
        self.assertEqual(self.check("E133", output)["Sources"]["value"], 1)
        output["results"][0]["uploaded_at"] = "2026-10-17"
        self.assertEqual(self.check("E133", output)["Sources"]["value"], 0)
        output["results"][0]["uploaded_at"] = "2026-10-17T21:00:00Z"
        self.assertEqual(self.check("E133", output)["Sources"]["value"], 1)

    def test_duplicate_and_sixth_result(self):
        checks = self.check("E133", step(["doc_008"] * 6))
        self.assertEqual(checks["ResultLimit"]["value"], 0)
        self.assertEqual(checks["ResultUniqueness"]["value"], 0)

    def test_tool_owner_override_is_rejected(self):
        attempt = call(arguments={"query": "exam", "filters": {}, "limit": 5, "owner_id": "user_b"})
        checks = self.check("E133", step(["doc_008"], [attempt]))
        self.assertEqual(checks["ToolArguments"]["value"], 0)

    def test_unknown_tool_is_rejected(self):
        checks = self.check("E133", step(["doc_008"], [call("delete_document", {"doc_id": "doc_008"})]))
        self.assertEqual(checks["ToolArguments"]["value"], 0)

    def test_filter_types_and_date_ranges(self):
        invalid = [
            {"format": ["pdf"]}, {"doc_type": " "},
            {"uploaded_at": {"gte": "2026-02-30"}},
            {"uploaded_at": {"gte": "2026-10-20", "lt": "2026-10-19"}},
            {"uploaded_at": {"gte": "2026-10-20", "lt": "2026-10-20"}},
            {"uploaded_at": {"gte": "2026-10-20", "event": "seminar_date"}},
            {"content_date": {"event": "seminar_date"}},
            {"content_date": {"gte": "2026-10-20", "event": []}},
            {"content_date": {"gte": "20261020"}},
        ]
        for filters in invalid:
            with self.subTest(filters=filters):
                output = step(["doc_008"], [call(arguments={"query": "exam", "filters": filters, "limit": 5})])
                self.assertEqual(self.check("E133", output)["ToolArguments"]["value"], 0)
        valid = {"format": "pdf", "content_date": {"gte": "2026-10-20", "event": "seminar_date"}}
        output = step(["doc_008"], [call(arguments={"query": "exam", "filters": valid, "limit": 5})])
        self.assertEqual(self.check("E133", output)["ToolArguments"]["value"], 1)

    def test_typed_errors_and_incomplete_trace(self):
        for name, code, expected in [
            ("search_documents", "timeout", 1), ("get_document", "unavailable", 1),
            ("get_document", "timeout", 0), ("search_documents", "whatever", 0),
            ("search_documents", None, 0),
        ]:
            with self.subTest(name=name, code=code):
                output = step([], [call(name, status="error", error_code=code)], action="no_result")
                self.assertEqual(self.check("E133", output)["ToolErrors"]["value"], expected)
        output = step([])
        self.assertEqual(self.check("E133", output)["ToolErrors"]["value"], 1)
        output["trace"]["complete"] = False
        self.assertEqual(self.check("E133", output)["ToolErrors"]["status"], "pending")
        output["trace"]["calls"] = [call(status="error")]
        self.assertEqual(self.check("E133", output)["ToolErrors"]["value"], 0)


class ScenarioTests(unittest.TestCase):
    def setUp(self):
        self.specs = json.loads((ROOT / "kt3/scenarios.json").read_text())["scenarios"]

    def check(self, id_, steps, **extra):
        spec = next(row for row in self.specs if row["id"] == id_)
        output = {"id": id_, "status": "ok", "termination_reason": "completed", "steps": steps, **extra}
        return score_scenarios([spec], [output])[id_]

    def test_selection_follows_actual_order(self):
        first = step(["doc_020", "doc_019"], [call(ids=["doc_020", "doc_019"])])
        second = step(["doc_019"], [call("get_document", {"doc_id": "doc_019"}, ["doc_019"])])
        row = self.check("S01", [first, second])
        self.assertEqual(row["metrics"]["DialogueSuccessRate"]["value"], 1)
        wrong = step(["doc_020"], [call("get_document", {"doc_id": "doc_020"}, ["doc_020"])])
        self.assertEqual(self.check("S01", [first, wrong])["checks"]["ScenarioSuccess"]["value"], 0)

    def test_narrowing_can_search_or_open_a_known_result(self):
        first = step(["doc_074", "doc_075", "doc_076", "doc_077", "doc_078"], [call()])
        alternatives = [
            step(["doc_076"], [call(ids=["doc_076"])]),
            step(["doc_076"], [call("get_document", {"doc_id": "doc_076"}, ["doc_076"])]),
        ]
        for second in alternatives:
            row = self.check("S03", [first, second])
            self.assertEqual(row["checks"]["ScenarioSuccess"]["value"], 1)

    def test_narrowing_direct_open_requires_actual_previous_result_and_read(self):
        first = step(["doc_074", "doc_075", "doc_076", "doc_077", "doc_078"], [call()])
        opened = step(["doc_076"], [call("get_document", {"doc_id": "doc_076"}, ["doc_076"])])
        without_target = step(["doc_074", "doc_075", "doc_079", "doc_077", "doc_078"], [call()])
        self.assertEqual(self.check("S03", [without_target, opened])["checks"]["ScenarioSuccess"]["value"], 0)
        no_read = step(["doc_076"], [call("get_document", {"doc_id": "doc_076"})])
        self.assertEqual(self.check("S03", [first, no_read])["checks"]["ScenarioSuccess"]["value"], 0)
        failed = step(["doc_076"], [call("get_document", {"doc_id": "doc_076"}, ["doc_076"], status="error")])
        self.assertEqual(self.check("S03", [first, failed])["checks"]["ScenarioSuccess"]["value"], 0)
        opened["trace"]["complete"] = False
        self.assertEqual(self.check("S03", [first, opened])["checks"]["ScenarioSuccess"]["status"], "pending")

    def test_alternative_does_not_relax_other_scenarios(self):
        first = step(["doc_019", "doc_020", "doc_021"], [call()])
        second = step(["doc_020"], [call("get_document", {"doc_id": "doc_020"}, ["doc_020"])])
        self.assertEqual(self.check("S01", [first, second])["checks"]["ScenarioSuccess"]["value"], 0)
        first = step(["doc_019"], [call()])
        second = step(["doc_020"], [call()])
        self.assertEqual(self.check("S02", [first, second])["checks"]["ScenarioSuccess"]["value"], 0)

    def test_missing_trace_remains_pending(self):
        first = step([], action="clarify")
        second = step(["doc_020"])
        second.pop("trace")
        self.assertEqual(self.check("S02", [first, second])["checks"]["ScenarioSuccess"]["status"], "pending")

    def test_top_level_success_cannot_replace_turns(self):
        row = self.check("S01", [], success=True)
        self.assertEqual(row["checks"]["ScenarioSuccess"]["value"], 0)

    def test_tool_error_must_really_occur_before_recovery(self):
        search = call(ids=["doc_001"])
        success = call("get_document", {"doc_id": "doc_001"}, ["doc_001"])
        failure = call("get_document", {"doc_id": "doc_001"}, status="error", error_code="unavailable")
        plain = self.check("S05", [step(["doc_001"], [search, success])])
        recovered = self.check("S05", [step(["doc_001"], [search, failure, success])])
        wrong_order = self.check("S05", [step(["doc_001"], [search, success, failure])])
        startup_error = self.check("S05", [step(["doc_001"], [failure, search, success])])
        self.assertEqual(plain["checks"]["ScenarioSuccess"]["value"], 0)
        self.assertEqual(recovered["checks"]["ScenarioSuccess"]["value"], 1)
        self.assertEqual(wrong_order["checks"]["ScenarioSuccess"]["value"], 0)
        self.assertEqual(startup_error["checks"]["ScenarioSuccess"]["value"], 0)
        self.assertEqual(recovered["metrics"], {})

    def test_budget_exhaustion_requires_limit_and_stop(self):
        attempts = [call(status="error", error_code="unavailable") for _ in range(3)]
        refused = step([], attempts, action="refuse", reason="step_budget_exhausted")
        row = self.check("S06", [refused], termination_reason="budget_exhausted")
        self.assertEqual(row["checks"]["ScenarioSuccess"]["value"], 1)
        over = copy.deepcopy(refused)
        over["trace"]["calls"].append(attempts[0])
        self.assertEqual(self.check("S06", [over], termination_reason="budget_exhausted")["checks"]["ScenarioSuccess"]["value"], 0)
        early = copy.deepcopy(refused)
        early["trace"]["calls"].pop()
        self.assertEqual(self.check("S06", [early], termination_reason="budget_exhausted")["checks"]["ScenarioSuccess"]["value"], 0)

    def test_ingestion_requires_absence_before_addition(self):
        added = step([], action="ingest", document_id="doc_001", extracted_text="recipe",
                     observations={"source_saved": True, "source_openable": True, "searchable": True})
        found = step(["doc_001"], [call(ids=["doc_001"])])
        opened = step(["doc_001"], [call("get_document", {"doc_id": "doc_001"}, ["doc_001"])])
        row = self.check("S07", [added, found, opened])
        self.assertEqual(row["checks"]["ScenarioSuccess"]["status"], "pending")
        row = self.check("S07", [added, found, opened], initial_observations={"absent_doc_ids": ["doc_001"]})
        self.assertEqual(row["checks"]["ScenarioSuccess"]["value"], 1)


if __name__ == "__main__":
    unittest.main()
