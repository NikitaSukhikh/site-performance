#!/usr/bin/env python3
"""Summarize captured CrUX or PageSpeed Insights JSON without hiding missing data."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


PSI_METRIC_NAMES = {
    "LARGEST_CONTENTFUL_PAINT_MS": "LCP",
    "FIRST_CONTENTFUL_PAINT_MS": "FCP",
    "CUMULATIVE_LAYOUT_SHIFT_SCORE": "CLS",
    "INTERACTION_TO_NEXT_PAINT": "INP",
    "EXPERIMENTAL_TIME_TO_FIRST_BYTE": "TTFB",
}


def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"{path}: cannot read valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected a JSON object")
    if "error" in data:
        error = data["error"]
        message = error.get("message") if isinstance(error, dict) else str(error)
        raise ValueError(f"{path}: API error: {message}")
    return data


def proportions(items: Any, key: str) -> list[float]:
    if not isinstance(items, list):
        return []
    values: list[float] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        value = item.get(key)
        if isinstance(value, (int, float)):
            values.append(round(float(value) * 100, 1))
    return values


def summarize_psi(path: Path, data: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {
        "file": str(path),
        "kind": "psi",
        "final_url": data.get("id"),
        "field": {},
        "lab": {},
    }

    for scope in ("loadingExperience", "originLoadingExperience"):
        experience = data.get(scope)
        if not isinstance(experience, dict) or not isinstance(experience.get("metrics"), dict):
            result["field"][scope] = {"available": False}
            continue
        metrics: dict[str, Any] = {}
        for raw_name, metric in experience["metrics"].items():
            if not isinstance(metric, dict):
                continue
            metrics[PSI_METRIC_NAMES.get(raw_name, raw_name)] = {
                "p75": metric.get("percentile"),
                "category": metric.get("category"),
                "distribution_percent": proportions(metric.get("distributions"), "proportion"),
            }
        result["field"][scope] = {
            "available": True,
            "overall_category": experience.get("overall_category"),
            "metrics": metrics,
        }

    lighthouse = data.get("lighthouseResult")
    if isinstance(lighthouse, dict):
        categories = lighthouse.get("categories")
        performance = categories.get("performance") if isinstance(categories, dict) else None
        score = performance.get("score") if isinstance(performance, dict) else None
        audits = lighthouse.get("audits")
        selected: dict[str, Any] = {}
        if isinstance(audits, dict):
            for audit_id in (
                "server-response-time",
                "first-contentful-paint",
                "largest-contentful-paint",
                "total-blocking-time",
                "cumulative-layout-shift",
                "speed-index",
            ):
                audit = audits.get(audit_id)
                if isinstance(audit, dict):
                    selected[audit_id] = {
                        "numeric_value": audit.get("numericValue"),
                        "numeric_unit": audit.get("numericUnit"),
                        "display_value": audit.get("displayValue"),
                        "score": audit.get("score"),
                    }
        result["lab"] = {
            "available": True,
            "performance_score": round(score * 100) if isinstance(score, (int, float)) else None,
            "audits": selected,
        }
    else:
        result["lab"] = {"available": False}
    return result


def summarize_crux(path: Path, data: dict[str, Any]) -> dict[str, Any]:
    record = data.get("record")
    if not isinstance(record, dict):
        raise ValueError(f"{path}: missing CrUX record")

    metrics_out: dict[str, Any] = {}
    metrics = record.get("metrics")
    if isinstance(metrics, dict):
        for name, metric in metrics.items():
            if not isinstance(metric, dict):
                continue
            percentiles = metric.get("percentiles")
            metrics_out[name] = {
                "p75": percentiles.get("p75") if isinstance(percentiles, dict) else None,
                "histogram_percent": proportions(metric.get("histogram"), "density"),
            }

    return {
        "file": str(path),
        "kind": "crux",
        "key": record.get("key"),
        "collection_period": record.get("collectionPeriod"),
        "metrics": metrics_out,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kind", choices=("psi", "crux"))
    parser.add_argument("files", nargs="+", type=Path)
    args = parser.parse_args()

    output: list[dict[str, Any]] = []
    try:
        for path in args.files:
            data = load_json(path)
            output.append(summarize_psi(path, data) if args.kind == "psi" else summarize_crux(path, data))
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    print(json.dumps(output, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
