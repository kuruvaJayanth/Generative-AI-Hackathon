"""Automated pipeline tests for PS 132: Food Nutrient Comparison Assistant.

Covers:
1. Portion-scaled comparison ("Compare 150g cooked quinoa vs 100g rolled oats")
2. Regional alias RAG lookup ("ragi vs moong dal" and "nachni")
3. Pre-retrieval clinical guardrail refusal ("I have diabetes, what should I eat for breakfast?")
4. Missing value ("N/A") handling, IFCT CSV ingestion, and /api/identify-image fallback
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image
import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import main as backend_main  # noqa: E402
from guardrail import check_clinical_guardrail  # noqa: E402
from ingest_usda import import_ifct_csv  # noqa: E402
from math_engine import compute_comparison  # noqa: E402
from rag_store import NutrientRAGStore  # noqa: E402


@pytest.fixture()
def isolated_store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> NutrientRAGStore:
    """Create a fresh SQLite + ChromaDB RAG store per test run."""
    store = NutrientRAGStore(
        db_path=tmp_path / "test_nutrients.db",
        chroma_dir=tmp_path / "test_chroma",
        auto_seed=True,
    )
    monkeypatch.setattr(backend_main, "get_store", lambda: store)
    return store


def test_portion_scaled_comparison_quinoa_vs_oats(isolated_store: NutrientRAGStore) -> None:
    client = TestClient(backend_main.app)
    resp = client.post(
        "/api/compare",
        json={"query": "Compare 150g cooked quinoa vs 100g rolled oats"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["guardrail"]["blocked"] is False

    comp = body["comparison"]
    food_a = comp["food_a"]
    food_b = comp["food_b"]

    assert food_a["food_id"] == "FDC-168917"
    assert food_a["state"] == "cooked"
    assert food_a["portion_g"] == 150.0
    assert food_a["source_url"].startswith("https://fdc.nal.usda.gov/")

    assert food_b["food_id"] == "FDC-173904"
    assert food_b["portion_g"] == 100.0
    assert food_b["source_url"].startswith("https://fdc.nal.usda.gov/")

    rows = {r["key"]: r for r in comp["rows"]}
    # Cooked quinoa per 100g: 120 kcal, 4.4g protein -> 150g = 180.0 kcal, 6.6g protein
    assert rows["energy_kcal"]["food_a_value"] == 180.0
    assert rows["energy_kcal"]["food_b_value"] == 379.0
    assert rows["energy_kcal"]["diff_a_minus_b"] == -199.0

    assert rows["protein_g"]["food_a_value"] == 6.6
    assert rows["protein_g"]["food_b_value"] == 13.15
    assert rows["protein_g"]["diff_a_minus_b"] == -6.55

    assert body["explanation"]["text"]
    assert "healthier" not in body["explanation"]["text"].lower()


def test_regional_alias_rag_lookup_ragi_vs_moong_dal(isolated_store: NutrientRAGStore) -> None:
    # Direct regional synonym check ("nachni" -> Finger millet (Ragi))
    nachni_rec = isolated_store.resolve_food("nachni")
    assert nachni_rec["food_id"] == "IFCT-A003"
    assert "Ragi" in nachni_rec["name"]

    client = TestClient(backend_main.app)
    resp = client.post("/api/compare", json={"query": "ragi vs moong dal"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"

    food_a = body["comparison"]["food_a"]
    food_b = body["comparison"]["food_b"]
    assert food_a["food_id"] == "IFCT-A003"
    assert food_b["food_id"] == "IFCT-B009"
    assert food_a["source_name"] == "ICMR-NIN IFCT 2017"
    assert food_a["source_url"] == "https://www.nin.res.in/ebooks/IFCT2017.pdf"
    assert food_b["source_url"] == "https://www.nin.res.in/ebooks/IFCT2017.pdf"

    rows = {r["key"]: r for r in body["comparison"]["rows"]}
    # Ragi calcium 364 mg vs Moong dal 43.1 mg per 100g
    assert rows["calcium_mg"]["food_a_value"] == 364.0
    assert rows["calcium_mg"]["food_b_value"] == 43.1
    assert rows["calcium_mg"]["diff_a_minus_b"] == 320.9


def test_clinical_guardrail_refusal(isolated_store: NutrientRAGStore) -> None:
    query = "I have diabetes, what should I eat for breakfast?"
    direct_guard = check_clinical_guardrail(query)
    assert direct_guard.blocked is True
    assert direct_guard.suggested_comparison

    client = TestClient(backend_main.app)
    resp = client.post("/api/compare", json={"query": query})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "blocked"
    assert body["guardrail"]["blocked"] is True
    assert "diabetes" in body["guardrail"]["matched_signals"]
    assert "medical" in body["guardrail"]["message"].lower()
    assert "comparison" not in body
    assert body["meta"]["layers_executed"] == ["input", "clinical_guardrail"]


def test_missing_values_marked_na_and_ifct_csv_import(
    isolated_store: NutrientRAGStore, tmp_path: Path
) -> None:
    food_x = {
        "food_id": "TEST-1",
        "name": "Test Food X",
        "aliases": "test x",
        "state": "raw",
        "source_name": "Test DB",
        "source_url": "https://example.org/1",
        "energy_kcal": 200.0,
        "protein_g": 10.0,
        "carbs_g": 30.0,
        "fiber_g": None,
        "fat_g": 4.0,
        "iron_mg": None,
        "calcium_mg": 50.0,
    }
    food_y = {
        "food_id": "TEST-2",
        "name": "Test Food Y",
        "aliases": "test y",
        "state": "raw",
        "source_name": "Test DB",
        "source_url": "https://example.org/2",
        "energy_kcal": 100.0,
        "protein_g": 5.0,
        "carbs_g": 15.0,
        "fiber_g": 3.0,
        "fat_g": 0.0,
        "iron_mg": 2.0,
        "calcium_mg": 25.0,
    }
    comp = compute_comparison(food_x, 100.0, food_y, 100.0)
    rows = {r["key"]: r for r in comp["rows"]}
    assert rows["fiber_g"]["food_a_display"] == "N/A"
    assert rows["fiber_g"]["diff_display"] == "N/A"
    assert rows["fat_g"]["pct_diff_display"] == "N/A"  # divide-by-zero guarded cleanly

    csv_file = tmp_path / "ifct_sample.csv"
    csv_file.write_text(
        "food_id,name,aliases,state,energy_kcal,protein_g,carbs_g,fiber_g,fat_g,iron_mg,calcium_mg\n"
        "IFCT-J001,Foxtail millet,kangni; navane,raw,331,12.3,60.9,8.0,4.3,2.8,31\n",
        encoding="utf-8",
    )
    records = import_ifct_csv(csv_file)
    assert len(records) == 1
    assert isolated_store.upsert_foods(records) == 1
    resolved = isolated_store.resolve_food("kangni")
    assert resolved["food_id"] == "IFCT-J001"


def test_identify_image_endpoint_returns_top3(isolated_store: NutrientRAGStore) -> None:
    img = Image.new("RGB", (64, 64), color=(50, 180, 60))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    buf.seek(0)

    client = TestClient(backend_main.app)
    resp = client.post(
        "/api/identify-image",
        files={"file": ("spinach_bowl.jpg", buf.getvalue(), "image/jpeg")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["predictions"]) == 3
    assert all("name" in p and "confidence" in p for p in data["predictions"])


def test_mixed_mode_structured_comparison_and_health(isolated_store: NutrientRAGStore) -> None:
    client = TestClient(backend_main.app)
    health_resp = client.get("/api/health")
    assert health_resp.status_code == 200
    assert health_resp.json()["food_count"] >= 10

    # Mixed mode: confirmed image label ("Spinach, raw") vs text ("paneer")
    resp = client.post(
        "/api/compare",
        json={
            "food_a": "Spinach, raw",
            "grams_a": 200.0,
            "food_b": "paneer",
            "grams_b": 100.0,
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["comparison"]["food_a"]["food_id"] == "FDC-168462"
    assert body["comparison"]["food_a"]["portion_g"] == 200.0
    assert body["comparison"]["food_b"]["food_id"] == "IFCT-L004"
    assert body["comparison"]["food_b"]["portion_g"] == 100.0

