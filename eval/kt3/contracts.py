"""Contract checks and checks for actual multi-turn runs.

Scenario outputs: {id, status, termination_reason, steps: [ordinary output]}.
Each step is one user turn and has a complete tool trace. ``max_steps`` counts
tool calls (including errors); it does not count user turns or model tokens.
The scenario runner must use its own previous replies, never a gold history.
"""
from datetime import date, datetime
from zoneinfo import ZoneInfo

from eval.metrics.score import outcome

from .common import cell, index_rows, na, pending
from .search import effective_documents


DIRECT_OPEN = {"E132": (0, "doc_019"), "E133": (1, "doc_008")}


def subset(expected, actual):
    """Dictionary subsets are recursive; scalar/list values match exactly."""
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(
            key in actual and subset(value, actual[key]) for key, value in expected.items())
    return type(expected) is type(actual) and expected == actual


def calls_from(output):
    trace = output.get("trace")
    if not isinstance(trace, dict) or not isinstance(trace.get("calls"), list):
        return [], False
    calls = trace["calls"]
    valid = all(isinstance(call, dict) and isinstance(call.get("name"), str)
                and isinstance(call.get("arguments"), dict)
                and call.get("status") in ("ok", "error")
                and isinstance(call.get("read_doc_ids"), list)
                and all(isinstance(doc, str) for doc in call["read_doc_ids"])
                for call in calls)
    return [call for call in calls if isinstance(call, dict)], trace.get("complete") is True and valid


def call_matches(required, actual):
    return (isinstance(actual.get("arguments"), dict)
            and actual.get("name") == required["tool"]
            and actual.get("status") == "ok"
            and subset(required.get("arguments_subset", {}), actual.get("arguments"))
            and (not required.get("query_nonempty") or (
                isinstance(actual.get("arguments", {}).get("query"), str)
                and bool(actual["arguments"]["query"].strip()))))


def valid_filters(filters):
    if not isinstance(filters, dict):
        return False
    scalar_fields = {"format", "source_type", "doc_type", "filename"}
    if not set(filters).issubset(scalar_fields | {"uploaded_at", "content_date"}):
        return False
    for field, value in filters.items():
        if field in scalar_fields:
            if not isinstance(value, str) or not value.strip():
                return False
            continue
        allowed = {"gte", "lt", "event"} if field == "content_date" else {"gte", "lt"}
        if (not isinstance(value, dict) or not set(value).issubset(allowed)
                or not {"gte", "lt"}.intersection(value)):
            return False
        if "event" in value and (not isinstance(value["event"], str) or not value["event"].strip()):
            return False
        for key in ("gte", "lt"):
            if key in value:
                bound = value[key]
                try:
                    if not isinstance(bound, str) or date.fromisoformat(bound).isoformat() != bound:
                        return False
                except ValueError:
                    return False
        if "gte" in value and "lt" in value and value["gte"] >= value["lt"]:
            return False
    return True


def tool_arguments(calls, complete):
    for call in calls:
        name, args = call.get("name"), call.get("arguments")
        if not isinstance(args, dict):
            return cell(0, "Tool arguments must be an object")
        if name == "get_document":
            valid = (set(args) == {"doc_id"} and isinstance(args.get("doc_id"), str)
                     and bool(args["doc_id"].strip()))
        elif name == "search_documents":
            valid = (set(args).issubset({"query", "filters", "order_by", "limit"})
                     and isinstance(args.get("query"), str) and valid_filters(args.get("filters"))
                     and type(args.get("limit")) is int and 1 <= args["limit"] <= 5
                     and ("order_by" not in args or isinstance(args["order_by"], str)))
        else:
            valid = False
        if not valid:
            return cell(0, "Unknown tool, invalid arguments, or caller-supplied owner")
    return cell(1) if complete else pending("Complete tool trace is required")


def tool_errors(calls, complete):
    allowed = {"search_documents": ("timeout", "unavailable", "invalid_arguments"),
               "get_document": ("not_found_or_forbidden", "unavailable")}
    for call in calls:
        if call.get("status") == "error":
            name = call.get("name")
            if not isinstance(name, str) or call.get("error_code") not in allowed.get(name, ()):
                return cell(0, "Missing or undeclared tool error code")
    return cell(1) if complete else pending("Complete tool trace is required")


def direct_open_allowed(case, output, calls, documents):
    if case["id"] not in DIRECT_OPEN:
        return False
    position, doc_id = DIRECT_OPEN[case["id"]]
    previous = next((turn.get("result_doc_ids", []) for turn in reversed(case.get("context", []))
                     if turn.get("role") == "assistant"), [])
    return (len(previous) > position and previous[position] == doc_id
            and case["expected"].get("relevant_doc_ids") == [doc_id]
            and documents.get(doc_id, {}).get("owner_id") == case["user_id"]
            and output.get("result_doc_ids") == [doc_id]
            and any(call_matches({"tool": "get_document", "arguments_subset": {"doc_id": doc_id}}, call)
                    and doc_id in call.get("read_doc_ids", []) for call in calls))


def access_check(case, output, calls, complete, documents):
    reads = list(output.get("result_doc_ids", [])) if isinstance(output.get("result_doc_ids"), list) else []
    for call in calls:
        if isinstance(call.get("read_doc_ids"), list):
            reads.extend(call["read_doc_ids"])
    bad = [doc for doc in reads if not isinstance(doc, str)
           or documents.get(doc, {}).get("owner_id") != case["user_id"]]
    if bad:
        return cell(0, "Unknown or foreign document accessed/returned")
    if not complete:
        return pending("Complete tool trace is required for ACL")
    return cell(1)


def valid_date(value):
    if not isinstance(value, str):
        return False
    try:
        if len(value) == 10:
            date.fromisoformat(value)
        else:
            datetime.fromisoformat(value.replace("Z", "+00:00"))
        return True
    except ValueError:
        return False


def source_check(output, ids, documents, timezone):
    if not ids:
        return na("No returned sources")
    results = output.get("results")
    if results is None:
        return pending("Result cards are missing")
    if (not isinstance(results, list) or any(not isinstance(item, dict) for item in results)
            or [item.get("doc_id") for item in results] != ids):
        return cell(0, "Result cards do not match returned IDs/order")
    if any(any(not isinstance(row.get(field), str) or not row[field].strip()
               for field in ("title", "snippet", "source"))
           or not valid_date(row.get("uploaded_at")) for row in results):
        return cell(0, "A result card lacks a required field")
    for row in results:
        value = row["uploaded_at"]
        if len(value) == 10:
            local_date = value
        else:
            timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if timestamp.tzinfo is None:
                return cell(0, "Result timestamps must include a timezone")
            local_date = timestamp.astimezone(ZoneInfo(timezone)).date().isoformat()
        if local_date != documents.get(row["doc_id"], {}).get("uploaded_at"):
            return cell(0, "Result date differs from fixture upload date")
    observations = output.get("observations")
    checks = observations.get("source_checks") if isinstance(observations, dict) else None
    if not isinstance(checks, list):
        return pending("Runner did not check source opening/snippets")
    observed = {}
    for check in checks:
        if not isinstance(check, dict) or not isinstance(check.get("doc_id"), str):
            return pending("Invalid source observation")
        if check["doc_id"] in observed:
            return pending("Duplicate source observations")
        observed[check["doc_id"]] = check
    unknown = False
    for doc in ids:
        observation = observed.get(doc, {})
        for field in ("openable", "snippet_supported"):
            if observation.get(field) is False:
                return cell(0, "Source could not be opened or snippet is not supported")
            if observation.get(field) is not True:
                unknown = True
    return pending("Incomplete source observations") if unknown else cell(1)


def score_contracts(cases, outputs, documents, environment):
    cases, outputs = index_rows(cases, "cases"), index_rows(outputs, "outputs")
    if outputs.keys() - cases.keys():
        raise ValueError("Unknown output case IDs")
    rows = {}
    for id_, case in cases.items():
        output = outputs.get(id_, {})
        action, ids = outcome(output or None)
        known_action = action in {"search", "clarify", "no_result", "refuse"}
        docs = effective_documents(documents, environment, case.get("fixture_id", "base"))
        calls, complete = calls_from(output)
        checks = {"ArchiveAccess": access_check(case, output, calls, complete, docs),
                  "ToolArguments": tool_arguments(calls, complete),
                  "ToolErrors": tool_errors(calls, complete)}
        if not known_action:
            checks.update({name: cell(0, "No valid response") for name in (
                "ResultLimit", "ResultUniqueness", "Sources", "ParsedQuery", "RequiredCalls")})
        else:
            checks["ResultLimit"] = cell(int(len(ids) <= 5))
            checks["ResultUniqueness"] = cell(int(len(ids) == len(set(ids))))
            checks["Sources"] = source_check(output, ids, docs, case.get("timezone", "UTC"))
            required = case.get("expected_calls", [])
            parsed = output.get("parsed_query")
            gold = case.get("gold_steps", {})
            alternate = direct_open_allowed(case, output, calls, docs)
            if not required:
                checks["ParsedQuery"] = na("No required search parse")
            elif alternate:
                checks["ParsedQuery"] = na("Direct opening of an unambiguous previous result")
            elif not isinstance(parsed, dict):
                checks["ParsedQuery"] = pending("Parsed query was not recorded")
            else:
                checks["ParsedQuery"] = cell(int(
                    parsed.get("filters") == gold.get("filters", {})
                    and parsed.get("order_by") == gold.get("order_by", "relevance")))
            if not complete:
                checks["RequiredCalls"] = pending("Complete tool trace is required")
            else:
                matched = alternate or all(any(call_matches(r, call) for call in calls) for r in required)
                checks["RequiredCalls"] = cell(int(matched),
                    "Allowed direct opening" if alternate else "")
        rows[id_] = {"metrics": {}, "checks": checks}
    return rows


def _combine(checks):
    if any(check["status"] == "ok" and check["value"] == 0 for check in checks.values()):
        return cell(0)
    if any(check["status"] == "pending" for check in checks.values()):
        return pending("Scenario trace is incomplete")
    return cell(1)


def score_scenarios(specs, outputs):
    """Score runner-produced turns against specs; never accept a success flag."""
    if isinstance(specs, dict):
        specs = specs["scenarios"]
    specs, outputs = index_rows(specs, "scenarios"), index_rows(outputs, "scenario outputs")
    if outputs.keys() - specs.keys():
        raise ValueError("Unknown scenario IDs")
    rows = {}
    for id_, spec in specs.items():
        output = outputs.get(id_, {})
        steps = output.get("steps", [])
        checks = {}
        valid_steps = isinstance(steps, list) and all(isinstance(step, dict) for step in steps)
        if not valid_steps:
            steps = []
        checks["Turns"] = cell(int(valid_steps and len(steps) == len(spec["turns"])))
        checks["RunStatus"] = cell(int(output.get("status") == "ok"))
        checks["Termination"] = cell(int(output.get("termination_reason") in spec["termination_reasons"]))
        if spec.get("initial_assert"):
            initial = output.get("initial_observations")
            checks["InitialState"] = (cell(int(subset(spec["initial_assert"], initial)))
                                      if isinstance(initial, dict) else pending("Initial state was not checked"))
        all_calls, complete = [], True
        for number, turn in enumerate(spec["turns"]):
            if number >= len(steps):
                checks[f"Turn{number + 1}"] = cell(0, "Missing turn")
                complete = False
                continue
            step = steps[number]
            calls, observed = calls_from(step)
            complete = complete and observed
            all_calls.extend(calls)
            expected = turn["assert"]
            ids = step.get("result_doc_ids", [])
            valid_ids = isinstance(ids, list) and all(isinstance(doc, str) for doc in ids)
            good = step.get("status") == "ok" and step.get("action") == expected["action"] and valid_ids
            if valid_ids:
                good = good and len(ids) == len(set(ids)) and len(ids) <= 5
                if "results_exact_set" in expected:
                    good = good and set(ids) == set(expected["results_exact_set"])
                if "results_allowed" in expected:
                    good = good and set(ids).issubset(expected["results_allowed"])
                if "result_count" in expected:
                    good = good and len(ids) == expected["result_count"]
            if "selected_from_turn" in expected:
                source = expected["selected_from_turn"]
                prior_ids = steps[source["turn"] - 1].get("result_doc_ids", []) if source["turn"] <= number else []
                position = source["position"] - 1
                wanted = prior_ids[position] if isinstance(prior_ids, list) and len(prior_ids) > position else None
                good = good and wanted is not None and ids == [wanted]
                if observed:
                    good = good and any(call_matches({"tool": "get_document", "arguments_subset": {"doc_id": wanted}}, c)
                                        and wanted in c.get("read_doc_ids", []) for c in calls)
            if expected.get("response_nonempty"):
                good = good and isinstance(step.get("response"), str) and bool(step["response"].strip())
            if expected.get("text_extracted"):
                good = good and isinstance(step.get("extracted_text"), str) and bool(step["extracted_text"].strip())
            if "fields" in expected:
                good = good and subset(expected["fields"], step)
            if "required_call" in expected and observed:
                good = good and any(call_matches(expected["required_call"], c) for c in calls)
            for field in expected.get("observations_true", []):
                observations = step.get("observations")
                observed_value = observations.get(field) if isinstance(observations, dict) else None
                if observed_value is False:
                    good = False
                elif observed_value is not True:
                    checks[f"Turn{number + 1}/{field}"] = pending("Missing runner observation")
            checks[f"Turn{number + 1}"] = cell(int(good))
        # All turns count, including unexpected extra turns.
        for step in steps[len(spec["turns"]):]:
            calls, observed = calls_from(step)
            all_calls.extend(calls)
            complete = complete and observed
        limit = spec["max_steps"]
        checks["StepBudget"] = cell(0, "Tool-call budget exceeded") if len(all_calls) > limit else (
            cell(1) if complete else pending("Complete tool traces are required"))
        checks["Trace"] = cell(1) if complete else pending("Incomplete tool trace")
        if spec.get("fault"):
            fault = spec["fault"]
            failures = [i for i, call in enumerate(all_calls) if call.get("name") == fault["tool"]
                        and call.get("status") == "error" and call.get("error_code") == fault["error_code"]]
            recovered = any(
                any(call.get("name") == fault.get("after_successful_tool") and call.get("status") == "ok"
                    for call in all_calls[:i])
                and any(call.get("name") == fault["tool"] and call.get("status") == "ok"
                        and call.get("arguments") == all_calls[i].get("arguments")
                        for call in all_calls[i + 1:]) for i in failures)
            checks["ToolErrorRecovery"] = (cell(int(bool(failures) and recovered)) if complete
                                           else pending("Need ordered error and recovery calls"))
        if spec.get("exhaust_budget"):
            fault = spec["persistent_fault"]
            checks["BudgetExhaustion"] = (cell(int(len(all_calls) == limit
                and output.get("termination_reason") == "budget_exhausted"
                and all(call.get("status") == "error" and call.get("name") == fault["tool"]
                        and call.get("error_code") == fault["error_code"] for call in all_calls))) if complete
                else pending("Need all calls up to exhaustion"))
        success = _combine(checks)
        checks["ScenarioSuccess"] = success
        metrics = {"DialogueSuccessRate": success} if spec.get("dialogue") else {}
        rows[id_] = {"metrics": metrics, "checks": checks}
    return rows
