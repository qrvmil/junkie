"""Проверка секрета и тарифа без вызова генерации."""
import json
import os
from pathlib import Path
import urllib.request
import urllib.error


def get(path, key):
    request = urllib.request.Request("https://openrouter.ai/api/v1/" + path,
        headers={"Authorization": "Bearer " + key, "Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def main():
    out = Path("runs/connection")
    out.mkdir(parents=True, exist_ok=True)
    key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    report = {"authenticated": False, "generation_calls": 0}
    try:
        if not key:
            raise ValueError("OPENROUTER_API_KEY secret is missing")
        data = get("key", key)["data"]
        report["authenticated"] = True
        report["key_limit_usd"] = data.get("limit")
        report["key_limit_remaining_usd"] = data.get("limit_remaining")
        models = get("models", key)["data"]
        wanted = "google/gemini-3.5-flash-lite"
        model = next((m for m in models if m["id"] == wanted), None)
        report["model"] = wanted
        report["model_available"] = model is not None
        if model:
            report["pricing"] = model.get("pricing")
            report["supported_parameters"] = model.get("supported_parameters")
    except urllib.error.HTTPError as exc:
        report["error"] = f"OpenRouter HTTP {exc.code}"
    except (OSError, ValueError, KeyError) as exc:
        report["error"] = str(exc) if isinstance(exc, ValueError) else type(exc).__name__
    (out / "connection.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))
    if not report["authenticated"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
