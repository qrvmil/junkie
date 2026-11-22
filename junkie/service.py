"""Common execution interface for rules, BM25 and the LLM query planner."""
from copy import deepcopy
from contextlib import contextmanager
from datetime import date
import hashlib
import json
import math
from pathlib import Path
import signal
import time

from .archive import ToolError
from .openrouter import ModelError
from .rules import parse_query


PROMPTS = Path(__file__).with_name("prompts")
QUERY_PROMPT = (PROMPTS / "query.txt").read_text(encoding="utf-8")
METADATA_PROMPT = (PROMPTS / "metadata.txt").read_text(encoding="utf-8")


CHOOSE_PROMPT = (PROMPTS / "choose.txt").read_text(encoding="utf-8")


class StepBudget(Exception):
    pass


class DeadlineExceeded(BaseException):
    # Parser libraries catch Exception for malformed files; a deadline must escape.
    code = "timeout"

    def __init__(self, read_doc_ids=None):
        self.read_doc_ids = list(read_doc_ids or [])


@contextmanager
def deadline(seconds, archive=None):
    """Bound local work on the Linux main thread used by the CLI/CI runner."""
    previous_handler = signal.getsignal(signal.SIGALRM)
    previous_timer = signal.setitimer(signal.ITIMER_REAL, 0)
    started = time.perf_counter()

    def expired(signum, frame):
        raise DeadlineExceeded(getattr(archive, "last_read_doc_ids", []))

    signal.signal(signal.SIGALRM, expired)
    duration = min(seconds, previous_timer[0]) if previous_timer[0] else seconds
    try:
        signal.setitimer(signal.ITIMER_REAL, duration)
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)
        if previous_timer[0]:
            remaining = max(.000001, previous_timer[0] - (time.perf_counter() - started))
            signal.setitimer(signal.ITIMER_REAL, remaining, previous_timer[1])


def valid_filters(filters):
    if not isinstance(filters, dict):
        return False
    simple = {"format", "source_type", "doc_type", "filename"}
    if set(filters) - simple - {"uploaded_at", "content_date"}:
        return False
    for name, value in filters.items():
        if name in simple:
            if not isinstance(value, str) or not value.strip():
                return False
        else:
            allowed = {"gte", "lt", "event"} if name == "content_date" else {"gte", "lt"}
            if not isinstance(value, dict) or set(value) - allowed or not ({"gte", "lt"} & set(value)):
                return False
            if "event" in value and (not isinstance(value["event"], str) or not value["event"].strip()):
                return False
            for bound in ("gte", "lt"):
                if bound in value:
                    try:
                        if date.fromisoformat(value[bound]).isoformat() != value[bound]:
                            return False
                    except (ValueError, TypeError):
                        return False
            if "gte" in value and "lt" in value and value["gte"] >= value["lt"]:
                return False
    return True


class Service:
    def __init__(self, archive, variant, client=None, max_tool_calls=8, max_model_calls=4, fault=None,
                 tool_timeout_s=10, ingestion_timeout_s=120):
        if variant not in {"B0", "B1", "Junkie"}:
            raise ValueError("variant must be B0, B1 or Junkie")
        if type(max_tool_calls) is not int or max_tool_calls < 1 or type(max_model_calls) is not int or max_model_calls < 1:
            raise ValueError("Positive tool/model limits required")
        if any(type(value) not in (int, float) or not math.isfinite(value) or value <= 0
               for value in (tool_timeout_s, ingestion_timeout_s)):
            raise ValueError("Positive finite tool/ingestion timeouts required")
        self.archive, self.variant, self.client = archive, variant, client
        self.max_tool_calls, self.max_model_calls = max_tool_calls, max_model_calls
        self.tool_timeout_s, self.ingestion_timeout_s = tool_timeout_s, ingestion_timeout_s
        self.fault = fault or {}
        self.tool_calls = []
        self.model_calls = 0
        self.termination_reason = "completed"
        self._fault_occurrences = 0
        self.model_steps = []

    def _model(self, messages, max_tokens, purpose):
        if self.client is None:
            raise ModelError("missing_model_client")
        if self.model_calls >= self.max_model_calls:
            raise ModelError("model_call_budget_exhausted")
        self.model_calls += 1
        if purpose not in {"query", "choose"}:
            return self.client.complete_json(messages, max_tokens=max_tokens, purpose=purpose)
        step = {"purpose": purpose, "prompt_sha256": hashlib.sha256(messages[0]["content"].encode()).hexdigest(),
                "input": json.loads(messages[-1]["content"])}
        self.model_steps.append(step)
        try:
            step["output"] = self.client.complete_json(messages, max_tokens=max_tokens, purpose=purpose)
            return step["output"]
        except ModelError as exc:
            step["error"] = exc.code
            raise

    def _invalid(self, field):
        self.model_steps[-1]["invalid_field"] = field
        raise ModelError("invalid_query_plan")

    def _fault_code(self, name):
        if self.fault.get("tool") != name:
            return None
        prerequisite = self.fault.get("after_successful_tool")
        if prerequisite and not any(call["name"] == prerequisite and call["status"] == "ok"
                                    for call in self.tool_calls):
            return None
        self._fault_occurrences += 1
        if self.fault.get("persistent") or self._fault_occurrences == self.fault.get("occurrence", 1):
            return self.fault.get("error_code", "unavailable")
        return None

    def _call(self, name, arguments, user_id, *, fuzzy_filename=False):
        for attempt in range(3):
            if len(self.tool_calls) >= self.max_tool_calls:
                raise StepBudget()
            started = time.perf_counter()
            call = {"name": name, "arguments": deepcopy(arguments), "status": "error", "read_doc_ids": []}
            if fuzzy_filename:
                call["filename_fallback"] = True
            self.tool_calls.append(call)
            try:
                injected = self._fault_code(name)
                if injected:
                    raise ToolError(injected)
                with deadline(self.tool_timeout_s, self.archive):
                    if name == "search_documents":
                        result = self.archive.search(**arguments, user_id=user_id,
                                                     fuzzy_filename=fuzzy_filename, ranking="overlap" if self.variant == "B0" else "bm25")
                    elif name == "get_document":
                        result = self.archive.get_document(arguments["doc_id"], user_id)
                    else:
                        raise ToolError("invalid_arguments")
                call["read_doc_ids"] = list(result.get("read_doc_ids", []))
                call["status"] = "ok"
                return result
            except (ToolError, DeadlineExceeded) as exc:
                call["read_doc_ids"] = list(exc.read_doc_ids)
                code = "unavailable" if name == "get_document" and exc.code == "timeout" else exc.code
                call["error_code"] = code
                if code != exc.code:
                    call["failure_reason"] = exc.code
                if code not in {"timeout", "unavailable"}:
                    raise
                if len(self.tool_calls) >= self.max_tool_calls:
                    raise StepBudget() from None
                if attempt == 2:
                    raise ToolError(code, exc.read_doc_ids) from None
            finally:
                call["duration_ms"] = (time.perf_counter() - started) * 1000

    def _plan(self, query, now, timezone, context):
        if self.variant != "Junkie":
            return {"action": "search", **parse_query(query, now, timezone)}, False
        selected = []
        remaining = 16000
        for turn in reversed((context or [])[-6:]):
            if not isinstance(turn, dict) or turn.get("role") not in {"user", "assistant"}:
                continue
            content = str(turn.get("content", ""))
            row = {"role": turn["role"], "content": content[:min(4000, remaining)]}
            ids = turn.get("result_doc_ids")
            if isinstance(ids, list):
                row["result_doc_ids"] = [d for d in ids[:5] if isinstance(d, str)]
            selected.append(row)
            remaining -= len(row["content"])
            if remaining <= 0:
                break
        selected.reverse()
        payload = {"query": query[:8000], "now": now, "timezone": timezone, "context": selected}
        truncated = len(query) > 8000 or len(selected) < len(context or []) or any(
            len(str(t.get("content", ""))) > 4000 for t in (context or []) if isinstance(t, dict))
        value = self._model([{"role": "system", "content": QUERY_PROMPT},
                             {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}], 900, "query")
        action = value.get("action")
        if action not in ("search", "clarify", "refuse", "get_document"):
            self._invalid("action")
        if action == "search":
            if not isinstance(value.get("query"), str):
                self._invalid("query")
            filters = value.get("filters", {})
            if not valid_filters(filters):
                bad = next((key for key in filters if not valid_filters({key: filters[key]})), None) if isinstance(filters, dict) else None
                self._invalid("filters." + bad if bad else "filters")
            if value.get("order_by", "relevance") not in ("relevance", "uploaded_at_asc", "uploaded_at_desc"):
                self._invalid("order_by")
            if "open_first" in value and type(value["open_first"]) is not bool:
                self._invalid("open_first")
        if action == "get_document":
            if not isinstance(value.get("doc_id"), str) or not value["doc_id"].strip():
                self._invalid("doc_id")
            if not any(value["doc_id"] in turn.get("result_doc_ids", [])
                       for turn in selected if turn["role"] == "assistant"):
                self.model_steps[-1]["invalid_field"] = "doc_id:not_in_history"
                return {"action": "refuse"}, truncated
        if action == "clarify" and (not isinstance(value.get("question"), str) or not value["question"].strip()):
            self._invalid("question")
        return value, truncated

    def _observations(self, cards, user_id):
        observations = []
        for card in cards:
            document = self.archive.documents.get(card["doc_id"], {})
            permitted = document.get("owner_id") == user_id
            openable = False
            if permitted and card.get("source") == "saved://" + card["doc_id"]:
                try:
                    with deadline(self.tool_timeout_s):
                        self.archive.resolve_source(card["source"], user_id)
                    openable = True
                except (ToolError, DeadlineExceeded, OSError):
                    pass
            observations.append({"doc_id": card["doc_id"], "openable": openable,
                                 "snippet_supported": permitted and isinstance(card.get("snippet"), str)
                                 and bool(card["snippet"]) and card["snippet"] in document.get("text", "")})
        return {"source_checks": observations}

    def _finish(self, result, started, tool_start, model_start):
        result["trace"] = {"complete": True, "calls": deepcopy(self.tool_calls[tool_start:])}
        if self.model_steps:
            result["trace"]["model_steps"] = deepcopy(self.model_steps)
        result["llm_usage"] = {"complete": True,
                               "calls": deepcopy(self.client.calls[model_start:]) if self.client else []}
        result["elapsed_ms"] = (time.perf_counter() - started) * 1000
        return result

    def query(self, query, user_id, now, timezone, context=None):
        self.model_steps = []
        started, tool_start = time.perf_counter(), len(self.tool_calls)
        model_start = len(self.client.calls) if self.client else 0
        self.termination_reason = "completed"
        result = {"status": "ok", "action": "search", "result_doc_ids": [], "results": []}
        try:
            plan, truncated = self._plan(query, now, timezone, context)
            result["context_truncated"] = truncated
            if plan["action"] == "refuse":
                result.update(action="refuse", response="Могу искать только в вашем архиве.")
            elif plan["action"] == "clarify":
                result.update(action="clarify", response=plan["question"])
            else:
                has_more = False
                if plan["action"] == "get_document":
                    opened = self._call("get_document", {"doc_id": plan["doc_id"]}, user_id)
                    cards = [opened["result"]]
                else:
                    arguments = {"query": plan["query"], "filters": plan.get("filters", {}),
                                 "order_by": plan.get("order_by", "relevance"), "limit": 5}
                    result["parsed_query"] = {"filters": arguments["filters"], "order_by": arguments["order_by"]}
                    found = self._call("search_documents", arguments, user_id)
                    cards, has_more = found["results"], found["has_more"]
                    if self.variant == "Junkie" and not cards and arguments["filters"].get("filename"):
                        retry = deepcopy(arguments)
                        filename = retry["filters"].pop("filename")
                        if Path(filename).suffix.lower() in {".pdf", ".docx", ".pptx", ".txt", ".md", ".html", ".tex"} and not any(c in filename for c in '/"\n'):
                            retry["query"] = '"' + filename + '"'
                            found = self._call("search_documents", retry, user_id, fuzzy_filename=True)
                            cards, has_more = found["results"], found["has_more"]
                    if plan.get("open_first") and cards:
                        chosen_id = cards[0]["doc_id"]
                        if self.variant == "Junkie" and len(cards) > 1:
                            choices = [{"doc_id": c["doc_id"], "title": c["title"][:180],
                                        "filename": Path(self.archive.documents[c["doc_id"]]["path"]).name}
                                       for c in cards]
                            decision = self._model([{"role":"system","content":CHOOSE_PROMPT},
                                {"role":"user","content":json.dumps({"query":query[:8000], "search_terms":arguments["query"],
                                 "candidates":choices}, ensure_ascii=False)}], 300, "choose")
                            if decision.get("action") == "clarify" and isinstance(decision.get("question"), str) and decision["question"].strip():
                                result.update(action="clarify", response=decision["question"])
                                return self._finish(result, started, tool_start, model_start)
                            if decision.get("action") == "no_result":
                                result.update(action="no_result", response="Подходящий документ не найден.")
                                return self._finish(result, started, tool_start, model_start)
                            chosen_id = decision.get("doc_id")
                            if decision.get("action") != "open" or chosen_id not in [c["doc_id"] for c in cards]:
                                self._invalid("choose.action_or_doc_id")
                        opened = self._call("get_document", {"doc_id": chosen_id}, user_id)
                        cards, has_more = [opened["result"]], False
                result.update(result_doc_ids=[c["doc_id"] for c in cards], results=cards,
                              has_more=has_more, observations=self._observations(cards, user_id))
                if cards:
                    response = "Найдено: " + "; ".join(card["title"] for card in cards) + "."
                    if has_more:
                        response += " Есть и другие совпадения. Уточните тему, формат или дату, чтобы сузить поиск."
                    result["response"] = response
                else:
                    result.update(action="no_result", response="Подходящих материалов не найдено. Попробуйте уточнить запрос.")
        except StepBudget:
            self.termination_reason = "budget_exhausted"
            result.update(action="refuse", reason="step_budget_exhausted",
                          response="Достигнут лимит шагов. Поиск остановлен.")
        except (ToolError, DeadlineExceeded) as exc:
            if exc.code == "not_found_or_forbidden":
                result.update(action="refuse", reason=exc.code, response="Документ недоступен в вашем архиве.")
            else:
                self.termination_reason = "tool_error"
                result.update(status="error", error_code=exc.code, response="Инструмент временно недоступен.")
        except ModelError as exc:
            self.termination_reason = "model_error"
            result.update(status="error", error_code=exc.code, response="Не удалось обработать запрос.")
        return self._finish(result, started, tool_start, model_start)

    def ingest(self, input, user_id, now, doc_id=None):
        self.model_steps = []
        started, tool_start = time.perf_counter(), len(self.tool_calls)
        model_start = len(self.client.calls) if self.client else 0
        self.termination_reason = "completed"
        result = {"status": "error", "action": "ingest"}
        try:
            with deadline(self.ingestion_timeout_s):
                result = self.archive.ingest(input, user_id, now, doc_id=doc_id)
                if result.get("action") == "ingest" and result.get("status") == "ok" and self.variant == "Junkie":
                    text = result["extracted_text"]
                    value = self._model([{"role": "system", "content": METADATA_PROMPT},
                                         {"role": "user", "content": json.dumps({"filename": input.get("path", ""),
                                              "document_text": text[:40000]}, ensure_ascii=False)}], 1200, "metadata")
                    if (any(not isinstance(value.get(k), str) or not value[k].strip() for k in ("title", "topic", "description"))
                            or not isinstance(value.get("tags"), list)
                            or any(not isinstance(t, str) or not t.strip() for t in value["tags"])):
                        raise ModelError("invalid_metadata")
                    value = {k: value[k] for k in ("title", "topic", "description", "tags")}
                    value["uploaded_at"] = result["metadata"]["uploaded_at"]
                    result["metadata"] = value
                    self.archive.documents[result["document_id"]]["metadata"] = deepcopy(value)
                    result["metadata_context_truncated"] = len(text) > 40000
        except (ToolError, DeadlineExceeded) as exc:
            result.update(status="timeout" if exc.code == "timeout" else "error", error_code=exc.code)
            self.termination_reason = "tool_error"
            if self.client and len(self.client.calls) > model_start:
                call = self.client.calls[-1]
                if call.get("status") == "error":
                    call.setdefault("error_code", exc.code)
        except ModelError as exc:
            result.update(status="error", error_code=exc.code)
            self.termination_reason = "model_error"
        return self._finish(result, started, tool_start, model_start)
