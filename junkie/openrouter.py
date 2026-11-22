"""OpenRouter JSON client with an explicit call and dollar budget."""
import json
import math
import os
import time
import urllib.error
import urllib.request


class ModelError(Exception):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


class OpenRouterClient:
    def __init__(self, model, budget_usd, max_calls, api_key=None,
                 input_price=.30, output_price=2.50, timeout=60):
        if (not isinstance(model, str) or not model.strip() or type(max_calls) is not int or max_calls < 1
                or any(type(x) not in (float, int) or not math.isfinite(x) or x <= 0
                       for x in (budget_usd, input_price, output_price, timeout))):
            raise ValueError("Model, positive budget/rates/timeout and max_calls are required")
        self.model = model
        # This model requires reasoning; pin its documented minimum, not "disabled".
        self.reasoning_effort = "minimal" if model in {
            "google/gemini-3.5-flash-lite", "google/gemini-3.5-flash-lite-20260721"} else None
        self.budget_usd = budget_usd
        self.max_calls = max_calls
        self.input_price, self.output_price = input_price, output_price
        self.timeout = timeout
        self.api_key = api_key if api_key is not None else os.environ.get("OPENROUTER_API_KEY", "")
        self.calls = []
        self.accounted_spend_usd = 0.0

    def complete_json(self, messages, max_tokens=1200, purpose="query"):
        if not self.api_key:
            raise ModelError("missing_api_key")
        if type(max_tokens) is not int or max_tokens < 1:
            raise ValueError("max_tokens must be positive")
        if not isinstance(messages, list) or not messages:
            raise ValueError("messages must be nonempty")
        if len(self.calls) >= self.max_calls:
            raise ModelError("model_call_budget_exhausted")
        # UTF-8 bytes plus framing is a conservative token estimate for text requests.
        estimated_input = len(json.dumps(messages, ensure_ascii=False).encode("utf-8")) + 1024
        reserve = (estimated_input * self.input_price + max_tokens * self.output_price) / 1e6
        if self.accounted_spend_usd + reserve > self.budget_usd:
            raise ModelError("cost_budget_exhausted")
        self.accounted_spend_usd += reserve
        call = {"model": self.model, "purpose": purpose, "status": "error",
                "input_tokens": None, "output_tokens": None, "cost_usd": None,
                "reserved_cost_usd": reserve, "reasoning_effort": self.reasoning_effort}
        self.calls.append(call)
        started = time.perf_counter()
        body = {"model": self.model, "temperature": 0, "max_tokens": max_tokens,
                "response_format": {"type": "json_object"}, "messages": messages,
                "provider": {"max_price": {"prompt": self.input_price,
                                            "completion": self.output_price, "request": 0},
                             "allow_fallbacks": False}}
        if self.reasoning_effort:
            body["reasoning"] = {"effort": self.reasoning_effort}
        request = urllib.request.Request("https://openrouter.ai/api/v1/chat/completions",
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            method="POST")
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                payload = json.load(response)
            usage = payload.get("usage") or {}
            for source, target in (("prompt_tokens", "input_tokens"), ("completion_tokens", "output_tokens")):
                value = usage.get(source)
                if type(value) is int and value >= 0:
                    call[target] = value
            details = usage.get("completion_tokens_details")
            reasoning_tokens = details.get("reasoning_tokens") if isinstance(details, dict) else None
            if type(reasoning_tokens) is int and reasoning_tokens >= 0:
                # Already included in completion_tokens: do not add it again.
                call["reasoning_tokens"] = reasoning_tokens
            price = usage.get("cost")
            if type(price) in (int, float) and math.isfinite(price) and price >= 0:
                call["cost_usd"] = price
                self.accounted_spend_usd += price - reserve
            call["generation_id"] = payload.get("id")
            call["actual_model"] = payload.get("model")
            choice = payload["choices"][0]
            call["finish_reason"] = choice.get("finish_reason")
            content = choice["message"]["content"]
            value = json.loads(content)
            if not isinstance(value, dict):
                raise ValueError("JSON object required")
            call["status"] = "ok"
            return value
        except urllib.error.HTTPError as exc:
            code = f"http_{exc.code}"
            call["error_code"] = code
            try:
                error = json.loads(exc.read(8192)).get("error", {})
                detail = error.get("message") if isinstance(error, dict) else None
                if isinstance(detail, str):
                    call["error_message"] = detail.replace(self.api_key, "[redacted]")[:500]
            except (ValueError, OSError, AttributeError):
                pass
            raise ModelError(code) from None
        except (urllib.error.URLError, TimeoutError, OSError):
            call["error_code"] = "model_unavailable"
            raise ModelError("model_unavailable") from None
        except (ValueError, TypeError, KeyError, IndexError, AttributeError):
            call["error_code"] = "invalid_model_response"
            raise ModelError("invalid_model_response") from None
        finally:
            call["duration_ms"] = (time.perf_counter() - started) * 1000
