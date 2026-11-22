"""Время и фактическая стоимость. Неизвестная стоимость не равна нулю."""
import math
from collections import Counter

from eval.metrics.score import outcome
from .common import index_rows


def number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0


def percentile(values, q):
    if not values:
        return None
    values = sorted(values)
    position = (len(values) - 1) * q
    left = math.floor(position)
    right = math.ceil(position)
    return values[left] + (values[right] - values[left]) * (position - left)


def latency(cases, outputs, successful_actions):
    outputs = index_rows(outputs, "outputs")
    durations, states, missing_timing, invalid_success = [], Counter(), [], []
    for case in cases:
        row = outputs.get(case["id"], {})
        status = row.get("status", "missing")
        if not isinstance(status, str):
            status = "invalid"
        states[status] += 1
        valid = outcome(row)[0] in successful_actions
        if successful_actions == {"ingest"}:
            observations = row.get("observations")
            valid = (row.get("action") == "ingest" and isinstance(observations, dict)
                     and all(observations.get(k) is True for k in ("source_saved", "source_openable", "searchable"))
                     and isinstance(row.get("extracted_text"), str) and bool(row["extracted_text"].strip()))
        if status == "ok" and not valid:
            invalid_success.append(case["id"])
        if status == "ok" and valid:
            duration = row.get("elapsed_ms")
            if number(duration):
                durations.append(duration)
            else:
                missing_timing.append(case["id"])
    return {
        "population": "completed responses; failures counted separately",
        "unit": "ms", "quantile_method": "linear interpolation (type 7)",
        "status": "pending" if missing_timing else "ok" if durations else "not_applicable",
        "p50": None if missing_timing else percentile(durations, .5),
        "p95": None if missing_timing else percentile(durations, .95),
        "measured": len(durations), "outcomes": dict(states), "missing_timing": missing_timing,
        "invalid_success": invalid_success,
    }


def cost(outputs):
    known_cost, tokens_in, tokens_out = [], 0, 0
    unknown, unknown_tokens, models = [], [], Counter()
    for row in outputs:
        id_ = row["id"]
        usage = row.get("llm_usage")
        if not isinstance(usage, dict) or not isinstance(usage.get("calls"), list):
            unknown.append(id_)
            continue
        if usage.get("complete") is not True:
            unknown.append(id_)
        for i, call in enumerate(usage["calls"]):
            if not isinstance(call, dict):
                unknown.append(f"{id_}:{i}")
                unknown_tokens.append(f"{id_}:{i}")
                continue
            model = call.get("model")
            if isinstance(model, str):
                models[model] += 1
            price = call.get("cost_usd")
            if number(price):
                known_cost.append(price)
            else:
                unknown.append(f"{id_}:{i}")
            incoming, outgoing = call.get("input_tokens"), call.get("output_tokens")
            if all(isinstance(v, int) and not isinstance(v, bool) and v >= 0 for v in (incoming, outgoing)):
                tokens_in += incoming
                tokens_out += outgoing
            else:
                unknown_tokens.append(f"{id_}:{i}")
    total = math.fsum(known_cost)
    return {"status": "pending" if unknown else "ok", "cost_usd": None if unknown else total,
            "known_cost_usd": total, "unknown_cost": unknown,
            "known_input_tokens": tokens_in, "known_output_tokens": tokens_out,
            "unknown_tokens": unknown_tokens, "calls_by_model": dict(models)}
