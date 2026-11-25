"""Automated tests for Context Filter & NHANES 2017-2018 Population Benchmarks."""

from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient
import pandas as pd
import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import main as backend_main  # noqa: E402
from guardrail import check_clinical_guardrail  # noqa: E402
from nhanes_benchmarks import (  # noqa: E402
    NHANES_SOURCE_URL,
    get_nhanes_benchmark,
    process_nhanes_dataframes,
    save_benchmarks_to_sqlite,
)
from rag_store import NutrientRAGStore  # noqa: E402


@pytest.fixture()
def isolated_store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> NutrientRAGStore:
    store = NutrientRAGStore(
        db_path=tmp_path / "nhanes_test.db",
        chroma_dir=tmp_path / "nhanes_chroma",
        auto_seed=True,
    )
    monkeypatch.setattr(backend_main, "get_store", lambda: store)
    return store


def test_merge_mock_nhanes_xpt_dataframes_filters_adults_and_reliable_recalls(
    tmp_path: Path,
) -> None:
    # SEQN 101, 102: 18-39 active (reliable)
    # SEQN 103: age 15 (child -> MUST be filtered out)
    # SEQN 104: age 35, DR1DRSTZ == 2 (unreliable -> MUST be filtered out)
    # SEQN 105, 106, 107: 40-59 moderate_low (reliable)
    demo_df = pd.DataFrame(
        {
            "SEQN": [101, 102, 103, 104, 105, 106, 107],
            "RIDAGEYR": [25, 32, 15, 35, 45, 52, 58],
        }
    )
    bmx_df = pd.DataFrame(
        {
            "SEQN": [101, 102, 103, 104, 105, 106, 107],
            "BMXBMI": [22.5, 24.0, 19.0, 26.0, 27.5, 29.0, 31.0],
        }
    )
    paq_df = pd.DataFrame(
        {
            "SEQN": [101, 102, 103, 104, 105, 106, 107],
            "PAQ605": [1, 2, 1, 1, 2, 2, 2],  # vigorous work
            "PAQ650": [2, 1, 2, 2, 2, 2, 2],  # vigorous recreational
            "PAQ620": [2, 2, 2, 2, 1, 2, 2],
            "PAQ665": [2, 2, 2, 2, 2, 1, 2],
        }
    )
    dr1tot_df = pd.DataFrame(
        {
            "SEQN": [101, 102, 103, 104, 105, 106, 107],
            "DR1DRSTZ": [1, 1, 1, 2, 1, 1, 1],
            "DR1TKCAL": [2200.0, 2400.0, 9999.0, 8888.0, 1800.0, 1900.0, 2000.0],
            "DR1TPROT": [80.0, 100.0, 300.0, 400.0, 60.0, 70.0, 80.0],
            "DR1TCARB": [260.0, 280.0, 500.0, 500.0, 200.0, 220.0, 240.0],
            "DR1TFIBE": [18.0, 22.0, 50.0, 50.0, 12.0, 14.0, 16.0],
            "DR1TSUGR": [80.0, 90.0, 200.0, 200.0, 70.0, 75.0, 85.0],
            "DR1TTFAT": [70.0, 80.0, 200.0, 200.0, 65.0, 70.0, 75.0],
            "DR1TSODI": [3000.0, 3400.0, 9000.0, 9000.0, 2900.0, 3100.0, 3300.0],
            "DR1TIRON": [14.0, 16.0, 50.0, 50.0, 11.0, 12.0, 13.0],
            "DR1TCALC": [900.0, 1100.0, 2000.0, 2000.0, 750.0, 800.0, 850.0],
        }
    )
    diq_df = pd.DataFrame(
        {
            "SEQN": [101, 102, 103, 104, 105, 106, 107],
            "DIQ010": [2, 2, 2, 1, 1, 2, 2],
        }
    )
    bpx_df = pd.DataFrame(
        {
            "SEQN": [101, 102, 103, 104, 105, 106, 107],
            "BPXSY1": [112.0, 116.0, 100.0, 140.0, 126.0, 130.0, 134.0],
            "BPXDI1": [70.0, 72.0, 60.0, 90.0, 78.0, 80.0, 82.0],
        }
    )

    payload = process_nhanes_dataframes(
        demo_df=demo_df,
        bmx_df=bmx_df,
        paq_df=paq_df,
        dr1tot_df=dr1tot_df,
        diq_df=diq_df,
        bpx_df=bpx_df,
    )
    assert payload["data_origin"] == "nhanes_xpt"
    assert payload["source_url"] == NHANES_SOURCE_URL

    db_file = tmp_path / "xpt_benchmarks.db"
    saved_count = save_benchmarks_to_sqlite(payload, db_path=db_file)
    assert saved_count > 0

    young_active = get_nhanes_benchmark(
        age_group="18-39",
        activity_level="active",
        bmi_range="all",
        db_path=db_file,
    )
    # Only SEQN 101 & 102 pass RIDAGEYR>=18 and DR1DRSTZ==1
    assert young_active["sample_size"] == 2
    assert young_active["medians"]["energy_kcal"] == 2300.0
    assert young_active["medians"]["protein_g"] == 90.0
    assert young_active["medians"]["fiber_g"] == 20.0
    assert young_active["medians"]["sodium_mg"] == 3200.0

    mid_mod = get_nhanes_benchmark(
        age_group="40-59",
        activity_level="moderate_low",
        bmi_range="all",
        db_path=db_file,
    )
    assert mid_mod["sample_size"] == 3
    assert mid_mod["medians"]["protein_g"] == 70.0
    assert mid_mod["medians"]["fiber_g"] == 14.0
    assert mid_mod["survey_statistics"]["median_systolic_bp_mmhg"] == 130.0
    assert mid_mod["survey_statistics"]["pct_self_reported_diabetes"] == 33.3


def test_compare_with_context_filter_returns_pct_nhanes_median(
    isolated_store: NutrientRAGStore,
) -> None:
    client = TestClient(backend_main.app)
    resp = client.post(
        "/api/compare",
        json={
            "query": "Compare 150g cooked quinoa vs 100g rolled oats",
            "context_filter": {
                "age_group": "18-39",
                "activity_level": "active",
                "focus_lens": "protein_energy",
            },
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"

    comp = body["comparison"]
    assert comp["focus_lens"] == "protein_energy"
    assert comp["nhanes_context"]["age_group"] == "18-39"
    assert comp["nhanes_context"]["activity_level"] == "active"
    assert comp["nhanes_context"]["source_url"] == NHANES_SOURCE_URL

    rows = {r["key"]: r for r in comp["rows"]}
    assert rows["energy_kcal"]["is_focused"] is True
    assert rows["protein_g"]["is_focused"] is True
    assert rows["sodium_mg"]["is_focused"] is False

    # Verify deterministic Python math for pct_nhanes_median
    prot_row = rows["protein_g"]
    expected_pct_a = round((prot_row["food_a_value"] / prot_row["nhanes_median"]) * 100.0, 1)
    expected_pct_b = round((prot_row["food_b_value"] / prot_row["nhanes_median"]) * 100.0, 1)
    assert prot_row["food_a_pct_nhanes_median"] == expected_pct_a
    assert prot_row["food_b_pct_nhanes_median"] == expected_pct_b
    assert prot_row["pct_nhanes_median"]["food_a"] == expected_pct_a
    assert prot_row["pct_nhanes_median"]["food_b"] == expected_pct_b

    # Verify explanation objectively frames NHANES as observational survey medians
    explanation_text = body["explanation"]["text"].lower()
    assert "nhanes" in explanation_text
    assert "observational" in explanation_text
    assert "healthier" not in explanation_text


def test_clinical_guardrail_bp_bmi_returns_suggested_lens_sodium_potassium(
    isolated_store: NutrientRAGStore,
) -> None:
    bp_query = "I am a BP patient with BMI 29, how much sodium can I eat?"
    guard = check_clinical_guardrail(bp_query)
    assert guard.blocked is True
    assert guard.suggested_lens == "sodium_potassium"

    client = TestClient(backend_main.app)
    resp = client.post(
        "/api/compare",
        json={
            "query": bp_query,
            "context_filter": {
                "age_group": "40-59",
                "activity_level": "moderate_low",
                "focus_lens": "balanced",
            },
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "blocked"
    assert body["guardrail"]["blocked"] is True
    assert body["guardrail"]["suggested_lens"] == "sodium_potassium"
    assert body["guardrail"]["suggested_lens_label"] == "Sodium & Potassium"
    assert "comparison" not in body

    # Diabetes + BMI query redirects to carb_fiber lens
    dm_resp = client.post(
        "/api/compare",
        json={"query": "I have diabetes, my BMI is 28, what should I eat?"},
    )
    assert dm_resp.status_code == 200
    dm_body = dm_resp.json()
    assert dm_body["status"] == "blocked"
    assert dm_body["guardrail"]["suggested_lens"] == "carb_fiber"


def test_nhanes_benchmarks_endpoint(isolated_store: NutrientRAGStore) -> None:
    client = TestClient(backend_main.app)
    resp = client.get("/api/nhanes/benchmarks?age_group=18-39&activity_level=active")
    assert resp.status_code == 200
    data = resp.json()
    assert data["source_url"] == NHANES_SOURCE_URL
    assert data["active_benchmark"]["age_group"] == "18-39"
    assert data["active_benchmark"]["activity_level"] == "active"
    assert len(data["age_cohort_summary"]) == 4
    assert "survey_statistics" in data["active_benchmark"]
