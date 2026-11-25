"""Deterministic user profile processing: BMI calculation, NHANES cohort mapping, and priority nutrients."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from nhanes_benchmarks import DEFAULT_DB_PATH, get_nhanes_benchmark

ACTIVITY_LABELS: dict[str, str] = {
    "low": "Low / Sedentary",
    "sedentary": "Low / Sedentary",
    "moderate_low": "Moderate / Low",
    "moderate": "Moderate",
    "active": "Active / Gym & Fitness",
}

HEALTH_CONTEXT_LABELS: dict[str, str] = {
    "general_wellness": "General Wellness",
    "blood_sugar_awareness": "Blood Sugar Awareness",
    "blood_pressure_awareness": "Blood Pressure Awareness",
    "fitness_gym": "Fitness / Gym",
    "micronutrient_focus": "Micronutrient Focus",
}

GOAL_LABELS: dict[str, str] = {
    "balanced": "Balanced Nutrient Comparison",
    "higher_protein": "Higher Protein Focus",
    "higher_fiber_lower_sugar": "Higher Fiber / Lower Sugar Focus",
    "lower_sodium": "Lower Sodium Focus",
    "lower_calorie_density": "Lower Calorie Density",
}

HEALTH_CONTEXT_NUTRIENTS: dict[str, list[str]] = {
    "general_wellness": [],
    "blood_sugar_awareness": ["carbs_g", "fiber_g", "sugar_g"],
    "blood_pressure_awareness": ["sodium_mg", "potassium_mg"],
    "fitness_gym": ["protein_g", "energy_kcal"],
    "micronutrient_focus": ["iron_mg", "calcium_mg"],
}

GOAL_NUTRIENTS: dict[str, list[str]] = {
    "balanced": [],
    "higher_protein": ["protein_g", "energy_kcal"],
    "higher_fiber_lower_sugar": ["fiber_g", "sugar_g", "carbs_g"],
    "lower_sodium": ["sodium_mg", "potassium_mg"],
    "lower_calorie_density": ["energy_kcal", "fat_g", "fiber_g"],
}

DEFAULT_PRIORITY_NUTRIENTS: list[str] = [
    "energy_kcal",
    "protein_g",
    "carbs_g",
    "fiber_g",
    "fat_g",
]


def calculate_bmi(weight_kg: float, height_cm: float) -> tuple[float, str, str]:
    """Compute BMI deterministically and map to standard category and NHANES BMI bucket."""
    if weight_kg <= 0 or height_cm <= 0:
        raise ValueError("Height (cm) and Weight (kg) must be positive values.")
    height_m = float(height_cm) / 100.0
    bmi = round(float(weight_kg) / (height_m ** 2), 1)
    if bmi < 18.5:
        return bmi, "Underweight", "<18.5"
    if bmi < 25.0:
        return bmi, "Normal", "18.5-24.9"
    if bmi < 30.0:
        return bmi, "Overweight", "25.0-29.9"
    return bmi, "Obese", "30+"


def map_age_to_nhanes_group(age: int | float) -> str:
    """Map numeric age (years) to CDC NHANES adult bracket."""
    a = float(age)
    if a <= 39:
        return "18-39"
    if a <= 59:
        return "40-59"
    return "60+"


def map_activity_to_nhanes_bucket(activity_level: str) -> str:
    """Map UI activity selection to CDC NHANES PAQ_J cohort bucket."""
    normalized = (activity_level or "all").strip().lower()
    if normalized in {"active", "fitness", "active_gym", "high"}:
        return "active"
    if normalized in {"low", "sedentary", "moderate", "moderate_low"}:
        return "moderate_low"
    return "all"


def build_priority_nutrients(
    health_contexts: list[str] | None = None,
    goal: str = "balanced",
) -> list[str]:
    """Build deterministic ordered list of priority nutrient keys from contexts and goal."""
    ordered: list[str] = []

    def _add_keys(keys: list[str]) -> None:
        for k in keys:
            if k not in ordered:
                ordered.append(k)

    goal_key = (goal or "balanced").strip().lower()
    _add_keys(GOAL_NUTRIENTS.get(goal_key, []))

    for ctx in health_contexts or []:
        ctx_key = (ctx or "").strip().lower()
        _add_keys(HEALTH_CONTEXT_NUTRIENTS.get(ctx_key, []))

    if not ordered:
        _add_keys(DEFAULT_PRIORITY_NUTRIENTS)

    return ordered


def infer_focus_lens(
    health_contexts: list[str] | None = None,
    goal: str = "balanced",
) -> str:
    """Map profile goal/contexts to legacy focus_lens identifier for chart/API parity."""
    goal_key = (goal or "balanced").strip().lower()
    contexts = [c.strip().lower() for c in (health_contexts or [])]

    if goal_key == "higher_protein" or "fitness_gym" in contexts:
        return "protein_energy"
    if goal_key == "higher_fiber_lower_sugar" or "blood_sugar_awareness" in contexts:
        return "carb_fiber"
    if goal_key == "lower_sodium" or "blood_pressure_awareness" in contexts:
        return "sodium_potassium"
    if "micronutrient_focus" in contexts:
        return "iron_calcium"
    return "balanced"


def process_user_profile(
    user_profile: dict[str, Any],
    db_path: str | Path = DEFAULT_DB_PATH,
    explicit_age_group: str | None = None,
    explicit_activity_bucket: str | None = None,
    explicit_bmi_range: str | None = None,
    explicit_focus_lens: str | None = None,
) -> dict[str, Any]:
    """Process user profile into BMI, NHANES cohort lookup, and priority nutrients."""
    age = int(round(float(user_profile.get("age", 25))))
    height_cm = float(user_profile.get("height_cm", 170.0))
    weight_kg = float(user_profile.get("weight_kg", 68.0))
    activity_raw = str(user_profile.get("activity_level", "active")).strip().lower()
    raw_contexts = user_profile.get("health_contexts") or ["general_wellness"]
    health_contexts = [str(c).strip().lower() for c in raw_contexts if str(c).strip()]
    if not health_contexts:
        health_contexts = ["general_wellness"]
    goal = str(user_profile.get("goal", "balanced")).strip().lower()

    bmi, bmi_category, inferred_bmi_range = calculate_bmi(weight_kg, height_cm)
    age_group = explicit_age_group or map_age_to_nhanes_group(age)
    nhanes_activity = explicit_activity_bucket or map_activity_to_nhanes_bucket(activity_raw)
    bmi_range = explicit_bmi_range or inferred_bmi_range

    nhanes_benchmark = get_nhanes_benchmark(
        age_group=age_group,
        activity_level=nhanes_activity,
        bmi_range=bmi_range,
        db_path=db_path,
    )

    priority_nutrients = build_priority_nutrients(health_contexts=health_contexts, goal=goal)
    if explicit_focus_lens and explicit_focus_lens != "balanced" and not user_profile.get("_from_user_profile", True):
        # Preserve exact focus_lens behavior when legacy context_filter is passed alone
        focus_lens = explicit_focus_lens
    else:
        focus_lens = explicit_focus_lens or infer_focus_lens(health_contexts=health_contexts, goal=goal)

    activity_label = ACTIVITY_LABELS.get(activity_raw, "Moderate / Low")
    context_labels = [
        HEALTH_CONTEXT_LABELS.get(c, c.replace("_", " ").title())
        for c in health_contexts
    ]
    goal_label = GOAL_LABELS.get(goal, "Balanced Nutrient Comparison")

    profile_summary = {
        "age": age,
        "age_group": age_group,
        "height_cm": round(height_cm, 1),
        "weight_kg": round(weight_kg, 1),
        "bmi": bmi,
        "bmi_category": bmi_category,
        "bmi_range": bmi_range,
        "activity_level": activity_raw,
        "activity_label": activity_label,
        "nhanes_activity_bucket": nhanes_activity,
        "health_contexts": health_contexts,
        "health_context_labels": context_labels,
        "goal": goal,
        "goal_label": goal_label,
        "summary_line": (
            f"Age {age} ({age_group}), BMI {bmi} ({bmi_category}), "
            f"{activity_label}, Focus: {', '.join(context_labels)}, "
            f"Goal: {goal_label}"
        ),
    }

    return {
        "profile_summary": profile_summary,
        "priority_nutrients": priority_nutrients,
        "focus_lens": focus_lens,
        "nhanes_benchmark": nhanes_benchmark,
    }
