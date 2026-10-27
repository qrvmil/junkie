"""Evidence integrity, dates, tag rubrics and extraction-score failure regressions."""
import copy
import tempfile
import unittest
from pathlib import Path

from score_extraction import score
from source_text import contains_quote, locate, normalize, units
from validate_gold import ROOT, load_rows, validate, validate_row


class IngestionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.gold = {r["id"]: r for r in load_rows(ROOT / "ingestion/gold.jsonl")}
        cls.cases = {r["id"]: r for r in load_rows(ROOT / "queries/ingestion.jsonl")}

    def test_all_seven_sources_and_rubrics_are_verified(self):
        self.assertEqual(validate(), (7, 33))

    def test_sha_mismatch_and_wrong_locator_rejected(self):
        for field in ("hash", "locator", "quote", "duplicate", "evidence"):
            row = copy.deepcopy(self.gold["I01"])
            if field == "hash": row["source"]["sha256"] = "0" * 64
            elif field == "locator": row["fragments"][0]["locator"] = "line:999"
            elif field == "quote": row["fragments"][0]["quote"] = "Invented source statement"
            elif field == "duplicate": row["fragments"].append(copy.deepcopy(row["fragments"][0]))
            else: row["metadata"]["title"]["evidence"] = ["UNKNOWN"]
            with self.subTest(field=field), self.assertRaises(ValueError):
                validate_row(row, self.cases["I01"], ROOT)

    def test_source_internal_date_cannot_become_ingestion_date(self):
        row = copy.deepcopy(self.gold["I03"])
        row["metadata"]["uploaded_at"]["expected_local_date"] = "2026-09-03"
        with self.assertRaisesRegex(ValueError, "fixed request clock"):
            validate_row(row, self.cases["I03"], ROOT)

    def test_fake_human_review_and_synonym_padding_rejected(self):
        row = copy.deepcopy(self.gold["I01"])
        row["human_review_status"] = "completed"
        with self.assertRaises(ValueError):
            validate_row(row, self.cases["I01"], ROOT)
        row = copy.deepcopy(self.gold["I01"])
        row["tags"]["examples"] = ["шарлотка", "charlotte", "яблоки"]
        with self.assertRaisesRegex(ValueError, "tag examples"):
            validate_row(row, self.cases["I01"], ROOT)

    def test_normalization_preserves_numbers_and_word_boundaries(self):
        self.assertTrue(contains_quote("ИНГРЕДИЕНТЫ\nна\t8 порций", "Ингредиенты на 8 порций"))
        self.assertTrue(contains_quote("преобразо-\nвания", "преобразования"))
        self.assertFalse(contains_quote("Ингредиенты на 18 порций", "Ингредиенты на 8 порций"))
        self.assertFalse(contains_quote("неЗАЯВЛЕНИЕ", "ЗАЯВЛЕНИЕ"))
        self.assertNotEqual(normalize("190°C"), normalize("90°C"))

    def test_html_ignores_script_style_and_head_but_decodes_visible_entities(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "page.html"
            path.write_text('<html><head><title>hidden</title><script>attack</script></head>\n'
                            '<body><style>secret</style><p>audio &amp; <span>capture</span></p></body></html>', encoding="utf-8")
            extracted = "\n".join(units(path).values())
            self.assertTrue(contains_quote(extracted, "audio & capture"))
            for word in ("hidden", "attack", "secret"):
                self.assertNotIn(word, extracted)

    def test_document_and_slide_locators_are_1_based(self):
        docx = units(ROOT / self.gold["I03"]["source"]["path"])
        pptx = units(ROOT / self.gold["I04"]["source"]["path"])
        self.assertTrue(contains_quote(locate(docx, "paragraph:19"), "Прошу изменить мои учетные данные"))
        self.assertTrue(contains_quote(locate(pptx, "slide:10"), "Use logarithms instead."))
        with self.assertRaises(ValueError):
            locate(docx, "paragraph:0")

    def test_reference_readback_checks_score_not_product_quality(self):
        outputs = [{"id": row["id"], "status": "ok",
                    "extracted_text": "\n".join(units(ROOT / row["source"]["path"]).values())}
                   for row in self.gold.values()]
        report = score(list(self.gold.values()), outputs)
        self.assertEqual((report["value"], report["n"]), (1, 7))

    def test_macro_mean_does_not_favor_long_documents(self):
        gold = [{"id": "a", "fragments": [{"id": "f1", "quote": "one"}]},
                {"id": "b", "fragments": [{"id": "f1", "quote": "two"}, {"id": "f2", "quote": "three"}]}]
        outputs = [{"id": "a", "status": "ok", "extracted_text": "one one"},
                   {"id": "b", "status": "ok", "extracted_text": "two"}]
        self.assertEqual(score(gold, outputs)["value"], 0.75)

    def test_missing_and_failed_extraction_stay_in_denominator(self):
        outputs = [{"id": "I01", "status": "error", "extracted_text": self.gold["I01"]["fragments"][0]["quote"]},
                   {"id": "I02", "status": "ok", "extracted_text": None}]
        report = score(list(self.gold.values()), outputs)
        self.assertEqual((report["value"], report["n"]), (0, 7))
        self.assertEqual(report["cases"][1]["status"], "invalid")

    def test_unknown_or_duplicate_outputs_are_not_silently_ignored(self):
        for outputs in [[{"id": "unknown"}], [{"id": "I01"}, {"id": "I01"}]]:
            with self.assertRaises(ValueError):
                score(list(self.gold.values()), outputs)


if __name__ == "__main__":
    unittest.main()
