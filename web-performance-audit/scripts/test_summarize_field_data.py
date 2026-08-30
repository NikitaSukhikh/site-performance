import json
import tempfile
import unittest
from pathlib import Path

import summarize_field_data as summary


class FieldSummaryTests(unittest.TestCase):
    def test_crux_record(self):
        data = {
            "record": {
                "key": {"origin": "https://example.com", "formFactor": "PHONE"},
                "collectionPeriod": {"firstDate": {"year": 2026}, "lastDate": {"year": 2026}},
                "metrics": {
                    "largest_contentful_paint": {
                        "percentiles": {"p75": 2500},
                        "histogram": [{"density": 0.8}, {"density": 0.15}, {"density": 0.05}],
                    }
                },
            }
        }
        out = summary.summarize_crux(Path("crux.json"), data)
        self.assertEqual(out["metrics"]["largest_contentful_paint"]["p75"], 2500)
        self.assertEqual(out["metrics"]["largest_contentful_paint"]["histogram_percent"], [80.0, 15.0, 5.0])

    def test_psi_missing_field_is_explicit(self):
        data = {
            "id": "https://example.com/",
            "lighthouseResult": {
                "categories": {"performance": {"score": 0.91}},
                "audits": {"total-blocking-time": {"numericValue": 123, "numericUnit": "millisecond"}},
            },
        }
        out = summary.summarize_psi(Path("psi.json"), data)
        self.assertFalse(out["field"]["loadingExperience"]["available"])
        self.assertEqual(out["lab"]["performance_score"], 91)
        self.assertEqual(out["lab"]["audits"]["total-blocking-time"]["numeric_value"], 123)

    def test_api_error_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "error.json"
            path.write_text(json.dumps({"error": {"message": "quota"}}), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "API error: quota"):
                summary.load_json(path)


if __name__ == "__main__":
    unittest.main()
