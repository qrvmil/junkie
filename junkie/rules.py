"""Фиксированные правила B0/B1. Не используют историю и разметку eval."""
from datetime import date, datetime, timedelta
from pathlib import Path
import re
import unicodedata
from zoneinfo import ZoneInfo


STOP = set("и в во на с со по из к ко а но или для от до не мне мой моя мои это тот та те все весь найти найди покажи где какой какая какие сохраненные сохранённые файл файлы документ документы пожалуйста the a an of in on for to and or my me find show saved file files document documents please".split())
SUFFIXES = ("иями", "ами", "ого", "ему", "ому", "ими", "ыми", "иях", "ах", "ях", "ов", "ев", "ей", "ая", "яя", "ое", "ее", "ые", "ие", "ый", "ий", "ой", "ам", "ям", "ом", "ем", "а", "я", "ы", "и", "у", "ю", "е")
MONTHS = {name: number for number, name in enumerate(
    ("январ", "феврал", "март", "апрел", "ма", "июн", "июл", "август", "сентябр", "октябр", "ноябр", "декабр"), 1)}
TYPE_WORDS = {
    "exam": ("экзамен", "exam", "midterm", "test"),
    "seminar": ("семинар", "seminar"),
    "lecture": ("лекци", "lecture"),
    "contract": ("договор", "contract", "agreement"),
    "recipe": ("рецепт", "recipe"),
    "presentation": ("презентаци", "presentation", "slides"),
    "instruction": ("инструкци", "instruction", "manual", "guide", "howto"),
}
TOPICS = {
    "Математика": ("математ", "math", "теорем", "theorem", "уравнен", "equation", "probability", "вероятност", "статист", "statistics"),
    "Машинное обучение": ("machine learning", "машинн", "neural", "нейрон", "diffusion", "диффуз", "наивн", "bayes", "pca"),
    "Программирование": ("python", "javascript", "c++", "api", "программ", "function", "код", "code"),
    "Сети": ("vpn", "headscale", "tailscale", "network", "ssh", "сетев"),
    "Робототехника": ("robot", "робот", "piper", "lerobot", "teleop"),
    "Кулинария": ("рецепт", "ингредиент", "recipe", "выпек", "мука", "яблок", "ингредиент"),
    "Документы": ("заявлен", "договор", "contract", "приказ", "signature", "подпис"),
}
TAG_CONCEPTS = {
    "математика": ("математ", "math"), "теория вероятностей": ("вероятност", "probability"),
    "статистика": ("статист", "statistics"), "дифференциальные уравнения": ("дифференциальн", "differential equation"),
    "машинное обучение": ("машинн", "machine learning"), "нейросети": ("нейрон", "neural"),
    "диффузионные модели": ("диффуз", "diffusion"), "байесовский классификатор": ("bayes", "наивный байес"),
    "Python": ("python",), "API": ("api",), "документация": ("документаци", "manual", "documentation"),
    "VPN": ("vpn",), "Headscale": ("headscale",), "Tailscale": ("tailscale",), "SSH": ("ssh",),
    "робототехника": ("робот", "robot"), "телеуправление": ("teleop", "телеуправ"),
    "рецепт": ("рецепт", "recipe"), "выпечка": ("выпеч", "выпек", "baking"),
    "яблоки": ("яблок", "apple"), "заявление": ("заявлен", "application form"),
    "договор": ("договор", "contract"), "экзамен": ("экзамен", "exam", "midterm"),
    "семинар": ("семинар", "seminar"), "лекция": ("лекци", "lecture"),
}


def normalize(text):
    return unicodedata.normalize("NFKC", str(text)).casefold().replace("ё", "е")


def tokenize(text):
    text = re.sub(r"([a-z])([A-Z])", r"\1 \2", str(text))
    result = []
    for word in re.findall(r"[a-zа-я0-9]+", normalize(text)):
        if word in STOP:
            continue
        if re.fullmatch("[а-я]+", word) and len(word) > 4:
            for suffix in SUFFIXES:
                if word.endswith(suffix) and len(word) - len(suffix) >= 4:
                    word = word[:-len(suffix)]
                    break
        elif len(word) > 4 and word.endswith("s"):
            word = word[:-1]
        result.append(word)
    return result


def _doc_type(text):
    text = normalize(text)
    for kind, words in TYPE_WORDS.items():
        if any(re.search(r"(?<!\w)" + re.escape(word), text) for word in words):
            return kind
    return None


def _dates(text, default_year):
    """Return dates with their source spans; invalid dates are ignored."""
    patterns = [r"(?P<year>20\d{2})[-./](?P<month>\d{1,2})[-./](?P<day>\d{1,2})",
                r"(?P<day>\d{1,2})[./](?P<month>\d{1,2})[./](?P<year>20\d{2})",
                r"(?P<day>\d{1,2})\s+(?P<word>январ\w*|феврал\w*|март\w*|апрел\w*|ма[йяе]|июн\w*|июл\w*|август\w*|сентябр\w*|октябр\w*|ноябр\w*|декабр\w*)(?:\s+(?P<year>20\d{2}))?"]
    for pattern in patterns:
        for match in re.finditer(pattern, normalize(text)):
            groups = match.groupdict()
            month = groups.get("month")
            if month is None:
                month = next(v for k, v in MONTHS.items() if groups["word"].startswith(k))
            try:
                found = date(int(groups.get("year") or default_year), int(month), int(groups["day"]))
            except ValueError:
                continue
            yield found, match.span()


def metadata_from_text(text, filename, uploaded_at):
    filename = Path(filename).name
    flat = " ".join(text.split())
    normalized = normalize(filename + " " + text)
    topic_scores = {name: sum(normalized.count(word) for word in words) for name, words in TOPICS.items()}
    topic = max(topic_scores, key=topic_scores.get)
    if not topic_scores[topic]:
        topic = "Прочее"
    tag_scores = {name: sum(normalized.count(word) for word in words) for name, words in TAG_CONCEPTS.items()}
    tags = [name for name in sorted(tag_scores, key=lambda name: (-tag_scores[name], name)) if tag_scores[name]][:7]
    result = {"title": filename, "topic": topic, "description": flat[:350],
              "tags": tags, "uploaded_at": uploaded_at, "content_events": []}
    kind = _doc_type(filename + " " + text[:1000])
    if kind:
        result["doc_type"] = kind
    # Event dates require an explicit year in source; upload year is not evidence.
    source = filename + "\n" + text
    seen = set()
    for found, (start, end) in _dates(source, 1):
        if found.year == 1:
            continue
        around = normalize(source[max(0, start - 100):end + 100])
        event_kind = ("seminar_date" if "семинар" in around or "seminar" in around else
                      "exam_date" if "экзамен" in around or "exam" in around else "document_date")
        event = (event_kind, found.isoformat())
        if event not in seen:
            result["content_events"].append({"kind": event_kind, "date": found.isoformat()})
            seen.add(event)
    return result


def parse_query(query, now, timezone):
    original = str(query)
    text = normalize(original)
    current = datetime.fromisoformat(str(now).replace("Z", "+00:00"))
    if current.tzinfo is not None:
        current = current.astimezone(ZoneInfo(timezone))
    today, filters, order = current.date(), {}, "relevance"
    filename = re.search(r'[^\s"<>]+\.(?:pdf|docx|pptx|txt|md|tex|html)\b', original, re.I)
    if filename:
        filters["filename"] = filename.group(0).strip("'«»")
        return {"query": filename.group(0), "filters": filters, "order_by": order}
    format_match = re.search(r"\b(pdf|docx|pptx|txt|md|tex|html)\b", text)
    if format_match:
        filters["format"] = format_match.group(1)
        text = text[:format_match.start()] + text[format_match.end():]
    if re.search(r"ссылк|\burls?\b|\blinks?\b", text):
        filters["source_type"] = "url"
        text = re.sub(r"ссылк\w*|\burls?\b|\blinks?\b", " ", text)
    if re.search(r"последн|новейш|самые новые|свеж|newest|latest|recent", text):
        order = "uploaded_at_desc"
        text = re.sub(r"последн\w*|новейш\w*|самые новые|свеж\w*|newest|latest|recent", " ", text)
    elif re.search(r"старейш|самые старые|oldest|по возрастанию", text):
        order = "uploaded_at_asc"
        text = re.sub(r"старейш\w*|самые старые|oldest|по возрастанию", " ", text)
    uploaded = bool(re.search(r"добавл|загруз|сохран|uploaded|added|saved", text))
    event = "seminar_date" if re.search(r"семинар|seminar", text) else "exam_date" if re.search(r"экзамен|exam", text) else None
    bounds = None
    dates = list(_dates(text, today.year))
    if dates and (uploaded or event):
        first, span = dates[0]
        bounds = {"gte": first.isoformat(), "lt": (first + timedelta(days=1)).isoformat()}
        text = text[:span[0]] + text[span[1]:]
    elif uploaded and re.search(r"вчера|yesterday", text):
        bounds = {"gte": (today - timedelta(days=1)).isoformat(), "lt": today.isoformat()}
        text = re.sub(r"вчера|yesterday", " ", text)
    elif uploaded and re.search(r"сегодня|today", text):
        bounds = {"gte": today.isoformat(), "lt": (today + timedelta(days=1)).isoformat()}
        text = re.sub(r"сегодня|today", " ", text)
    if bounds:
        if uploaded:
            filters["uploaded_at"] = bounds
        else:
            filters["content_date"] = {**bounds, "event": event}
        text = re.sub(r"добавл\w*|загруз\w*|сохран\w*|uploaded|added|saved", " ", text)
    text = re.sub(r"\b(?:только|лишь|only)\b", " ", text)
    # Archive tokenizes once; returning stems here would stem Russian words twice.
    terms = [word for word in re.findall(r"[a-zа-я0-9]+", text) if word not in STOP]
    return {"query": " ".join(terms), "filters": filters, "order_by": order}
