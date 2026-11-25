"""Deterministic Python math engine for nutrient scaling, pairwise diffs, and NHANES benchmarks.

All arithmetic is executed deterministically in Python—never by an LLM.
Missing nutrient values (None) are preserved as None numerically and formatted
as "N/A" in display fields.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from nhanes_benchmarks import NHANES_SOURCE_NAME, NHANES_SOURCE_URL

NUTRIENT_SPECS: list[dict[str, str]] = [
    {"key": "energy_kcal", "label": "Energy", "unit": "kcal"},
    {"key": "protein_g", "label": "Protein", "unit": "g"},
    {"key": "carbs_g", "label": "Carbohydrates", "unit": "g"},
    {"key": "fiber_g", "label": "Dietary Fiber", "unit": "g"},
    {"key": "sugar_g", "label": "Total Sugars", "unit": "g"},
    {"key": "fat_g", "label": "Total Fat", "unit": "g"},
    {"key": "sodium_mg", "label": "Sodium", "unit": "mg"},
    {"key": "potassium_mg", "label": "Potassium", "unit": "mg"},
    {"key": "iron_mg", "label": "Iron", "unit": "mg"},
    {"key": "calcium_mg", "label": "Calcium", "unit": "mg"},
]

FOCUS_LENS_CONFIG: dict[str, dict[str, Any]] = {
    "balanced": {
        "label": "Balanced",
        "keys": ["energy_kcal", "protein_g", "carbs_g", "fiber_g", "fat_g"],
    },
    "protein_energy": {
        "label": "Protein & Energy",
        "keys": ["energy_kcal", "protein_g"],
    },
    "carb_fiber": {
        "label": "Carb & Fiber",
        "keys": ["carbs_g", "fiber_g", "sugar_g"],
    },
    "sodium_potassium": {
        "label": "Sodium & Potassium",
        "keys": ["sodium_mg", "potassium_mg"],
    },
    "iron_calcium": {
        "label": "Iron & Calcium",
        "keys": ["iron_mg", "calcium_mg"],
    },
}


@dataclass(frozen=True)
class ScaledFood:
    food: dict[str, Any]
    grams: float
    nutrients: dict[str, float | None]


def scale_value(per_100g: float | int | None, grams: float) -> float | None:
    """Scale a per-100g nutrient value to the requested gram portion."""
    if per_100g is None:
        return None
    if grams < 0:
        raise ValueError("Portion grams must be non-negative.")
    return round(float(per_100g) * (float(grams) / 100.0), 2)


def format_value(value: float | None, unit: str = "") -> str:
    """Format a nutrient number cleanly, returning 'N/A' when missing."""
    if value is None:
        return "N/A"
    formatted = f"{value:.2f}".rstrip("0").rstrip(".")
    return f"{formatted} {unit}".strip() if unit else formatted


def scale_food_record(food: dict[str, Any], grams: float = 100.0) -> ScaledFood:
    """Scale all tracked nutrients for a food record from per-100g to `grams`."""
    if grams <= 0:
        raise ValueError(f"Portion grams must be positive, got {grams}.")
    scaled: dict[str, float | None] = {}
    for spec in NUTRIENT_SPECS:
        key = spec["key"]
        scaled[key] = scale_value(food.get(key), grams)
    return ScaledFood(food=food, grams=round(float(grams), 2), nutrients=scaled)


def compute_pct_nhanes_median(
    food_nutrient_amount: float | None,
    cohort_median_daily_intake: float | None,
) -> float | None:
    """Compute % of NHANES observed median daily intake deterministically in Python."""
    if (
        food_nutrient_amount is None
        or cohort_median_daily_intake is None
        or cohort_median_daily_intake <= 0
    ):
        return None
    return round((float(food_nutrient_amount) / float(cohort_median_daily_intake)) * 100.0, 1)


def compute_comparison(
    food_a: dict[str, Any],
    grams_a: float,
    food_b: dict[str, Any],
    grams_b: float,
    nhanes_benchmark: dict[str, Any] | None = None,
    focus_lens: str = "balanced",
) -> dict[str, Any]:
    """Compute exact scaled nutrients, A - B differences, % deltas, and NHANES % benchmarks."""
    scaled_a = scale_food_record(food_a, grams_a)
    scaled_b = scale_food_record(food_b, grams_b)

    lens_key = focus_lens if focus_lens in FOCUS_LENS_CONFIG else "balanced"
    lens_info = FOCUS_LENS_CONFIG[lens_key]
    focus_keys: list[str] = lens_info["keys"]

    cohort_medians: dict[str, float | None] = (
        nhanes_benchmark.get("medians", {}) if nhanes_benchmark else {}
    )

    rows: list[dict[str, Any]] = []
    for spec in NUTRIENT_SPECS:
        key = spec["key"]
        unit = spec["unit"]
        val_a = scaled_a.nutrients[key]
        val_b = scaled_b.nutrients[key]

        if val_a is not None and val_b is not None:
            diff = round(val_a - val_b, 2)
            if val_b == 0:
                pct_diff = 0.0 if val_a == 0 else None
            else:
                pct_diff = round(((val_a - val_b) / val_b) * 100.0, 1)

            if val_a > val_b:
                higher_in = "A"
            elif val_b > val_a:
                higher_in = "B"
            else:
                higher_in = "equal"
        else:
            diff = None
            pct_diff = None
            higher_in = "N/A"

        median_val = cohort_medians.get(key)
        pct_nhanes_a = compute_pct_nhanes_median(val_a, median_val)
        pct_nhanes_b = compute_pct_nhanes_median(val_b, median_val)

        rows.append(
            {
                "key": key,
                "label": spec["label"],
                "unit": unit,
                "is_focused": key in focus_keys,
                "food_a_value": val_a,
                "food_a_display": format_value(val_a, unit),
                "food_b_value": val_b,
                "food_b_display": format_value(val_b, unit),
                "diff_a_minus_b": diff,
                "diff_display": (
                    f"{'+' if diff > 0 else ''}{format_value(diff, unit)}"
                    if diff is not None
                    else "N/A"
                ),
                "pct_diff_vs_b": pct_diff,
                "pct_diff_display": (
                    f"{'+' if pct_diff > 0 else ''}{pct_diff:.1f}%"
                    if pct_diff is not None
                    else "N/A"
                ),
                "higher_in": higher_in,
                "nhanes_median": median_val,
                "nhanes_median_display": format_value(median_val, unit),
                "food_a_pct_nhanes_median": pct_nhanes_a,
                "food_b_pct_nhanes_median": pct_nhanes_b,
                "pct_nhanes_median": {
                    "food_a": pct_nhanes_a,
                    "food_b": pct_nhanes_b,
                },
            }
        )

    def _serialize_food_summary(scaled: ScaledFood) -> dict[str, Any]:
        raw_aliases = scaled.food.get("aliases") or ""
        alias_list = [a.strip() for a in raw_aliases.split(",") if a.strip()]
        return {
            "food_id": scaled.food["food_id"],
            "name": scaled.food["name"],
            "state": scaled.food.get("state") or "raw",
            "aliases": alias_list,
            "portion_g": scaled.grams,
            "source_name": scaled.food["source_name"],
            "source_url": scaled.food["source_url"],
            "scaled_nutrients": scaled.nutrients,
            "per_100g_record": scaled.food,
        }

    nhanes_context: dict[str, Any] | None = None
    if nhanes_benchmark:
        nhanes_context = {
            "age_group": nhanes_benchmark.get("age_group", "all_adults"),
            "activity_level": nhanes_benchmark.get("activity_level", "all"),
            "bmi_range": nhanes_benchmark.get("bmi_range", "all"),
            "focus_lens": lens_key,
            "focus_lens_label": lens_info["label"],
            "focus_keys": focus_keys,
            "sample_size": nhanes_benchmark.get("sample_size"),
            "cohort_medians": cohort_medians,
            "survey_statistics": nhanes_benchmark.get("survey_statistics", {}),
            "data_origin": nhanes_benchmark.get("data_origin", "cached_fallback"),
            "source_name": nhanes_benchmark.get("source_name", NHANES_SOURCE_NAME),
            "source_url": nhanes_benchmark.get("source_url", NHANES_SOURCE_URL),
        }

    return {
        "food_a": _serialize_food_summary(scaled_a),
        "food_b": _serialize_food_summary(scaled_b),
        "rows": rows,
        "focus_lens": lens_key,
        "focus_lens_label": lens_info["label"],
        "nhanes_context": nhanes_context,
    }
