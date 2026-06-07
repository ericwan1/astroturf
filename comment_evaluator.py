"""Score generated comments against mined culture features."""

from __future__ import annotations

from typing import Any


def evaluate_comment(text: str, culture_features: dict[str, Any]) -> dict[str, Any]:
    profile = culture_features.get("median_poster_profile") or {}
    style = culture_features.get("comment_style") or {}
    length_stats = style.get("length_chars") or {}

    target_length = profile.get("target_length_chars") or 90
    p25 = length_stats.get("p25") or 40
    p75 = length_stats.get("p75") or 196
    length = len(text.strip())

    if p25 <= length <= p75:
        length_band = "in_band"
    elif length < p25:
        length_band = "too_short"
    else:
        length_band = "too_long"

    length_delta = abs(length - target_length)
    length_score = max(0.0, 1.0 - (length_delta / max(target_length, 1)))

    one_liner = length <= 100
    lowercase_start = bool(text[:1].islower()) if text else False

    checks = {
        "non_empty": bool(text.strip()),
        "length_in_band": length_band == "in_band",
        "one_liner": one_liner,
        "lowercase_start": lowercase_start,
    }
    passed = sum(1 for value in checks.values() if value)

    return {
        "length": length,
        "target_length": target_length,
        "length_band": length_band,
        "length_score": round(length_score, 3),
        "one_liner": one_liner,
        "lowercase_start": lowercase_start,
        "checks": checks,
        "checks_passed": passed,
        "checks_total": len(checks),
        "acceptable": checks["non_empty"] and length_band != "too_long",
    }
