"""Automated tests for full User Profile, BMI calculator, and Nutrition Reference Rules Engine."""

from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import main as backend_main  # noqa: E402
from profile_processor import calculate_bmi, process_user_profile  # noqa: E402
from rag_store import NutrientRAGStore  # noqa: E402


@pytest.fixture()
def isolated_store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> NutrientRAGStore:
    store = NutrientRAGStore(
        db_path=tmp_path / "profile_rules_test.db",
        chroma_dir=tmp_path / "profile_rules_chroma",
        auto_seed=True,
    )
    monkeypatch.setattr(backend_main, "get_store", lambda: store)
    return store


def test_profile_processor_bmi_and_cohort_selection(
    isolated_store: NutrientRAGStore,
) -> None:
    bmi, category, bmi_range = calculate_bmi(weight_kg=70.0, height_cm=175.0)
    assert bmi == 22.9
    assert category == "Normal"
    assert bmi_range == "18.5-24.9"

    res = process_user_profile(
        {
            "age": 25,
            "height_cm": 170,
            "weight_kg": 68,
            "activity_level": "active",
            "health_contexts": ["fitness_gym", "blood_sugar_awareness"],
            "goal": "higher_protein",
        },
        db_path=isolated_store.db_path,
    )

    summary = res["profile_summary"]
    assert summary["bmi"] == 23.5
    assert summary["bmi_category"] == "Normal"
    assert summary["age_group"] == "18-39"
    assert summary["nhanes_activity_bucket"] == "active"

    # Priority nutrients ordered: higher_protein/fitness_gym first, then blood_sugar_awareness
    assert res["priority_nutrients"] == [
        "protein_g",
        "energy_kcal",
        "carbs_g",
        "fiber_g",
        "sugar_g",
    ]
    assert res["nhanes_benchmark"]["age_group"] == "18-39"
    assert res["nhanes_benchmark"]["activity_level"] == "active"
    assert res["nhanes_benchmark"]["bmi_range"] == "18.5-24.9"


def test_compare_with_full_user_profile_returns_rules_analysis_and_tags(
    isolated_store: NutrientRAGStore,
) -> None:
    client = TestClient(backend_main.app)
    resp = client.post(
        "/api/compare",
        json={
            "query": "Compare 150g cooked quinoa vs 100g rolled oats",
            "user_profile": {
                "age": 25,
                "height_cm": 170,
                "weight_kg": 68,
                "activity_level": "active",
                "health_contexts": ["fitness_gym", "blood_sugar_awareness"],
                "goal": "higher_protein",
            },
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"

    rules = body["rules_analysis"]
    assert rules["profile_summary"]["bmi"] == 23.5
    assert rules["profile_summary"]["bmi_category"] == "Normal"
    assert len(rules["food_tags"]["food_a"]) >= 1
    assert len(rules["food_tags"]["food_b"]) >= 1

    # Priority nutrients appear at the top of comparison_rows
    top_keys = [r["key"] for r in rules["comparison_rows"][:5]]
    assert top_keys == ["protein_g", "energy_kcal", "carbs_g", "fiber_g", "sugar_g"]
    assert rules["comparison_rows"][0]["is_focused"] is True
    assert rules["comparison_rows"][-1]["is_focused"] is False

    # Protein-per-100 kcal derived deterministically
    assert rules["derived_metrics"]["food_a"]["protein_per_100kcal"] == 3.67
    assert rules["derived_metrics"]["food_b"]["protein_per_100kcal"] == 3.47

    # NHANES % medians present
    prot_row = rules["comparison_rows"][0]
    assert prot_row["food_a_pct_nhanes_median"] is not None
    assert prot_row["food_b_pct_nhanes_median"] is not None

    # Tailored insights structure & non-clinical phrasing
    expl = body["explanation"]
    assert "Age 25" in expl["profile_context_summary"]
    assert "BMI 23.5 (Normal)" in expl["profile_context_summary"]
    assert len(expl["bullet_points"]) >= 3
    assert "not personal clinical targets" in expl["text"].lower() or "observational" in expl["text"].lower()

    # Model assessment, practical suggestions & final report
    assessment = rules["model_assessment"]
    assert 0 < assessment["food_a_score"] <= 100
    assert 0 < assessment["food_b_score"] <= 100
    assert assessment["recommended_choice"] in {"food_a", "food_b", "balanced_tie"}
    assert assessment["verdict_title"]
    assert len(rules["suggestions"]) >= 1
    assert "Nutrient Comparison & Quality Report" in rules["final_report"]["markdown"]
    assert "USDA FoodData Central" in rules["final_report"]["markdown"]


def test_blood_sugar_and_blood_pressure_contexts_remain_objective_and_non_clinical(
    isolated_store: NutrientRAGStore,
) -> None:
    client = TestClient(backend_main.app)

    # 1. Blood Sugar Awareness context
    bs_resp = client.post(
        "/api/compare",
        json={
            "query": "100g ragi vs 100g moong dal",
            "user_profile": {
                "age": 48,
                "height_cm": 168,
                "weight_kg": 76,
                "activity_level": "moderate",
                "health_contexts": ["blood_sugar_awareness"],
                "goal": "higher_fiber_lower_sugar",
            },
        },
    )
    assert bs_resp.status_code == 200
    bs_body = bs_resp.json()
    assert bs_body["status"] == "ok"
    assert bs_body["guardrail"]["blocked"] is False
    assert bs_body["guardrail"]["disclaimer"]

    bs_top3 = [r["key"] for r in bs_body["comparison"]["rows"][:3]]
    assert bs_top3 == ["fiber_g", "sugar_g", "carbs_g"]
    assert "diabetes" not in bs_body["explanation"]["text"].lower()
    assert "should eat" not in bs_body["explanation"]["text"].lower()

    # 2. Blood Pressure Awareness context
    bp_resp = client.post(
        "/api/compare",
        json={
            "query": "100g spinach vs 100g boiled egg",
            "user_profile": {
                "age": 62,
                "height_cm": 170,
                "weight_kg": 80,
                "activity_level": "low",
                "health_contexts": ["blood_pressure_awareness"],
                "goal": "lower_sodium",
            },
        },
    )
    assert bp_resp.status_code == 200
    bp_body = bp_resp.json()
    assert bp_body["status"] == "ok"
    assert bp_body["guardrail"]["blocked"] is False
    assert bp_body["guardrail"]["disclaimer"]

    bp_top2 = [r["key"] for r in bp_body["comparison"]["rows"][:2]]
    assert bp_top2 == ["sodium_mg", "potassium_mg"]
    spinach_tag_labels = [t["label"] for t in bp_body["rules_analysis"]["food_tags"]["food_a"]]
    assert "Lower Sodium" in spinach_tag_labels
    assert "Higher Potassium" in spinach_tag_labels
    assert "hypertension" not in bp_body["explanation"]["text"].lower()
