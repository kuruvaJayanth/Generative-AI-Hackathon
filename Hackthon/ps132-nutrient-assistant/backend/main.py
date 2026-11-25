"""FastAPI entrypoint for PS 132: Food Nutrient Comparison Assistant."""

from __future__ import annotations

import os
import threading
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Literal

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from guardrail import DISCLAIMER_TEXT, check_clinical_guardrail
from ingest_usda import fetch_usda_foods
from llm_service import (
    _extract_portion_and_state,
    generate_explanation,
    parse_comparison_query,
)
from math_engine import FOCUS_LENS_CONFIG, compute_comparison
from nhanes_benchmarks import (
    NHANES_SOURCE_NAME,
    NHANES_SOURCE_URL,
    ensure_nhanes_loaded,
    get_nhanes_benchmark,
)
from profile_processor import process_user_profile
from rag_store import get_store
from rules_engine import run_rules_engine
from vision import _get_clip_resources, identify_food_image

load_dotenv()


def _warmup_clip_bg() -> None:
    try:
        _get_clip_resources()
    except Exception:
        pass


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    get_store()
    if not os.getenv("PYTEST_CURRENT_TEST"):
        threading.Thread(target=_warmup_clip_bg, daemon=True).start()
    yield


app = FastAPI(
    title="PS 132: Food Nutrient Comparison Assistant",
    description=(
        "5-step food nutrient comparison API combining Vision AI, "
        "User Profile Processing (BMI + NHANES Cohort), SQLite + ChromaDB RAG, "
        "Nutrition Reference Rules Engine, and strictly grounded non-clinical insights."
    ),
    version="1.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class UserProfileInput(BaseModel):
    age: int = Field(default=25, ge=18, le=90)
    height_cm: float = Field(default=170.0, gt=50, le=260)
    weight_kg: float = Field(default=68.0, gt=20, le=350)
    activity_level: Literal["low", "sedentary", "moderate", "moderate_low", "active"] = "active"
    health_contexts: list[str] = Field(default_factory=lambda: ["general_wellness"])
    goal: Literal[
        "balanced",
        "higher_protein",
        "higher_fiber_lower_sugar",
        "lower_sodium",
        "lower_calorie_density",
    ] = "balanced"


class ContextFilter(BaseModel):
    age_group: Literal["all_adults", "18-39", "40-59", "60+"] = "all_adults"
    activity_level: Literal["all", "active", "moderate_low"] = "all"
    focus_lens: Literal[
        "balanced",
        "protein_energy",
        "carb_fiber",
        "sodium_potassium",
        "iron_calcium",
    ] = "balanced"
    bmi_range: Literal["all", "<18.5", "18.5-24.9", "25.0-29.9", "30+"] = "all"


class CompareRequest(BaseModel):
    query: str | None = Field(
        default=None,
        description='Free-text comparison query, e.g. "Compare 150g cooked quinoa vs 100g rolled oats".',
    )
    food_a: str | None = Field(default=None, description="Explicit Food A name (text or confirmed from image).")
    grams_a: float = Field(default=100.0, gt=0, description="Portion weight in grams for Food A.")
    state_a: str | None = Field(default=None, description="Optional state preference (raw/cooked) for Food A.")
    food_b: str | None = Field(default=None, description="Explicit Food B name (text or confirmed from image).")
    grams_b: float = Field(default=100.0, gt=0, description="Portion weight in grams for Food B.")
    state_b: str | None = Field(default=None, description="Optional state preference (raw/cooked) for Food B.")
    user_profile: UserProfileInput | None = Field(
        default=None,
        description="Full user profile for BMI calculation, NHANES cohort mapping, and rules prioritization.",
    )
    context_filter: ContextFilter | None = Field(
        default=None,
        description="Optional legacy age/activity lens filter.",
    )


def _profile_from_legacy_filter(ctx: ContextFilter) -> dict[str, Any]:
    age_map = {"all_adults": 35, "18-39": 25, "40-59": 48, "60+": 65}
    lens_to_ctx = {
        "balanced": "general_wellness",
        "protein_energy": "fitness_gym",
        "carb_fiber": "blood_sugar_awareness",
        "sodium_potassium": "blood_pressure_awareness",
        "iron_calcium": "micronutrient_focus",
    }
    lens_to_goal = {
        "balanced": "balanced",
        "protein_energy": "higher_protein",
        "carb_fiber": "higher_fiber_lower_sugar",
        "sodium_potassium": "lower_sodium",
        "iron_calcium": "balanced",
    }
    return {
        "age": age_map.get(ctx.age_group, 30),
        "height_cm": 170.0,
        "weight_kg": 68.0,
        "activity_level": ctx.activity_level,
        "health_contexts": [lens_to_ctx.get(ctx.focus_lens, "general_wellness")],
        "goal": lens_to_goal.get(ctx.focus_lens, "balanced"),
        "_from_user_profile": False,
    }


@app.get("/api/health")
def health() -> dict[str, Any]:
    store = get_store()
    nhanes = get_nhanes_benchmark(db_path=store.db_path)
    return {
        "status": "ok",
        "food_count": store.count_foods(),
        "nhanes_data_origin": nhanes.get("data_origin"),
        "gemini_configured": bool(os.getenv("GEMINI_API_KEY", "").strip()),
        "usda_configured": bool(os.getenv("USDA_FDC_API_KEY", "").strip()),
        "disclaimer": DISCLAIMER_TEXT,
    }


@app.get("/api/foods")
def list_foods() -> dict[str, Any]:
    store = get_store()
    return {"foods": store.list_foods()}


@app.get("/api/nhanes/benchmarks")
def get_nhanes_benchmarks(
    age_group: Literal["all_adults", "18-39", "40-59", "60+"] = "all_adults",
    activity_level: Literal["all", "active", "moderate_low"] = "all",
    bmi_range: Literal["all", "<18.5", "18.5-24.9", "25.0-29.9", "30+"] = "all",
) -> dict[str, Any]:
    store = get_store()
    ensure_nhanes_loaded(db_path=store.db_path)
    active = get_nhanes_benchmark(
        age_group=age_group,
        activity_level=activity_level,
        bmi_range=bmi_range,
        db_path=store.db_path,
    )
    cohorts = [
        get_nhanes_benchmark(
            age_group=ag,
            activity_level=activity_level,
            bmi_range="all",
            db_path=store.db_path,
        )
        for ag in ("all_adults", "18-39", "40-59", "60+")
    ]
    return {
        "source_name": NHANES_SOURCE_NAME,
        "source_url": NHANES_SOURCE_URL,
        "active_benchmark": active,
        "age_cohort_summary": cohorts,
        "focus_lenses": {k: v["label"] for k, v in FOCUS_LENS_CONFIG.items()},
        "disclaimer": DISCLAIMER_TEXT,
    }


@app.post("/api/identify-image")
async def identify_image(file: UploadFile = File(...)) -> dict[str, Any]:
    image_bytes = await file.read()
    try:
        result = identify_food_image(
            image_bytes=image_bytes,
            filename=file.filename,
            mime_type=file.content_type or "image/jpeg",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return result


@app.post("/api/compare")
def compare_foods(req: CompareRequest) -> dict[str, Any]:
    # 1. Pre-Retrieval Clinical Guardrail (inspects food text query only, never UI profile chips)
    guardrail_text = " ".join(
        part for part in [req.query, req.food_a, req.food_b] if part and part.strip()
    )
    if not guardrail_text:
        raise HTTPException(
            status_code=400,
            detail="Provide either a free-text `query` or both `food_a` and `food_b`.",
        )

    guard = check_clinical_guardrail(guardrail_text)
    guardrail_payload = {
        "blocked": guard.blocked,
        "reason_category": guard.reason_category,
        "matched_signals": guard.matched_signals,
        "message": guard.message,
        "suggested_comparison": guard.suggested_comparison,
        "suggested_lens": guard.suggested_lens,
        "suggested_lens_label": guard.suggested_lens_label,
        "disclaimer": guard.disclaimer,
    }
    if guard.blocked:
        return {
            "status": "blocked",
            "guardrail": guardrail_payload,
            "meta": {
                "parser": "pre_retrieval_guardrail",
                "layers_executed": ["input", "clinical_guardrail"],
            },
        }

    # 2. Entity Extraction
    if req.food_a and req.food_b:
        parsed_a = _extract_portion_and_state(req.food_a)
        parsed_b = _extract_portion_and_state(req.food_b)
        food_a_query = parsed_a["query"]
        food_b_query = parsed_b["query"]
        grams_a = req.grams_a if req.grams_a != 100.0 else parsed_a["grams"]
        grams_b = req.grams_b if req.grams_b != 100.0 else parsed_b["grams"]
        state_a = req.state_a or parsed_a["preferred_state"]
        state_b = req.state_b or parsed_b["preferred_state"]
        parser_used = "structured_slots"
    elif req.query:
        try:
            parsed = parse_comparison_query(req.query)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        food_a_query = parsed["food_a"]["query"]
        grams_a = parsed["food_a"]["grams"]
        state_a = parsed["food_a"]["preferred_state"]
        food_b_query = parsed["food_b"]["query"]
        grams_b = parsed["food_b"]["grams"]
        state_b = parsed["food_b"]["preferred_state"]
        parser_used = parsed.get("parser", "deterministic")
    else:
        raise HTTPException(
            status_code=400,
            detail="Please provide both Food A and Food B or a free-text comparison query.",
        )

    # 3. Profile Processing (BMI + NHANES Cohort + Priority Nutrients) & RAG Retrieval
    store = get_store()

    def _resolve_with_usda_fallback(food_query: str, state_pref: str | None) -> dict[str, Any]:
        try:
            return store.resolve_food(food_query, preferred_state=state_pref)
        except LookupError as original_exc:
            # Optional live lookup from USDA FoodData Central when local DB has no match
            try:
                live_records = fetch_usda_foods([food_query], page_size=1, timeout=6)
            except Exception:
                live_records = []
            if live_records:
                store.upsert_foods(live_records)
                return store.resolve_food(food_query, preferred_state=state_pref)
            raise original_exc

    try:
        rec_a = _resolve_with_usda_fallback(food_a_query, state_a)
        rec_b = _resolve_with_usda_fallback(food_b_query, state_b)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    if req.user_profile is not None:
        profile_res = process_user_profile(
            req.user_profile.model_dump(),
            db_path=store.db_path,
        )
    elif req.context_filter is not None:
        ctx = req.context_filter
        profile_res = process_user_profile(
            _profile_from_legacy_filter(ctx),
            db_path=store.db_path,
            explicit_age_group=ctx.age_group,
            explicit_activity_bucket=ctx.activity_level,
            explicit_bmi_range=ctx.bmi_range,
            explicit_focus_lens=ctx.focus_lens,
        )
    else:
        profile_res = process_user_profile(
            UserProfileInput().model_dump(),
            db_path=store.db_path,
        )

    match_a_method = rec_a.pop("_match_method", "rag")
    match_a_score = rec_a.pop("_similarity_score", None)
    match_b_method = rec_b.pop("_match_method", "rag")
    match_b_score = rec_b.pop("_similarity_score", None)

    # 4. Deterministic Python Math Engine + Nutrition Reference Rules Engine
    comparison = compute_comparison(
        food_a=rec_a,
        grams_a=grams_a,
        food_b=rec_b,
        grams_b=grams_b,
        nhanes_benchmark=profile_res["nhanes_benchmark"],
        focus_lens=profile_res["focus_lens"],
    )
    rules_analysis = run_rules_engine(comparison, profile_res)
    comparison["rows"] = rules_analysis["comparison_rows"]
    comparison["food_a"]["match_method"] = match_a_method
    comparison["food_a"]["similarity_score"] = match_a_score
    comparison["food_b"]["match_method"] = match_b_method
    comparison["food_b"]["similarity_score"] = match_b_score

    # 5. Strictly Grounded Tailored Food Insights
    explanation = generate_explanation(comparison, rules_analysis=rules_analysis)

    return {
        "status": "ok",
        "guardrail": guardrail_payload,
        "comparison": comparison,
        "rules_analysis": rules_analysis,
        "explanation": explanation,
        "meta": {
            "parser": parser_used,
            "user_profile": profile_res["profile_summary"],
            "layers_executed": [
                "user_profile_input",
                "clinical_guardrail",
                "profile_processing_bmi_nhanes",
                "rag_sqlite_chromadb",
                "python_math_and_rules_engine",
                "grounded_tailored_insights",
            ],
        },
    }
