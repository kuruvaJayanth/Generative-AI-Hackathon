"""Entity parser and strictly grounded tailored food insights generator.

- Extracts Food A / Food B names, gram portions, and optional state from free text.
- Generates a Tailored Food Insights payload containing:
  1. profile_context_summary (1 sentence restating selected non-clinical context)
  2. bullet_points (3-4 objective bullets grounded in verified Python comparison
     numbers and % of CDC NHANES 2017-2018 observed survey medians)
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

from math_engine import format_value

SYSTEM_PROMPT = """You are a factual food nutrient comparison assistant.
You receive ONLY a verified `rules_analysis` JSON payload computed deterministically in Python from official food composition databases (USDA FDC / ICMR-NIN IFCT 2017) and CDC NHANES 2017-2018 observational population survey medians.

OUTPUT FORMAT (STRICT JSON):
Return ONLY valid JSON with two keys:
- "profile_context_summary": Exactly 1 concise sentence restating the user's non-clinical profile context (e.g., "Analyzed for Age 25, BMI 23.5 (Normal), Active / Gym & Fitness, focusing on Fitness / Gym (Goal: Higher Protein Focus).").
- "bullet_points": An array of 3 to 4 concise, objective plain-English bullet strings explaining how the compared foods differ on the user's priority_nutrients.

STRICT RULES:
1. Cite ONLY exact numbers, units, percentages, food names, and source names explicitly present in the provided JSON. NEVER invent or recalculate numbers.
2. When referencing NHANES percentages, cite the exact Python-computed % of NHANES 2017-2018 observed median figures and explicitly note they are observational survey medians (NOT personal clinical targets or dietary prescriptions).
3. NEVER diagnose a disease, prescribe personal daily gram or calorie limits for a medical condition, tell a user to start/stop medication, or recommend a clinical diet.
4. NEVER use subjective claims ("healthier", "better for you", "superfood", "should eat", "diabetic-friendly"). Always use objective, educational phrasing (e.g., "Food A provides 16.7 g more protein per 100 g than Food B")."""

STATE_WORDS = {"cooked", "boiled", "steamed", "raw", "uncooked", "dry", "roasted", "grilled"}

BANNED_PHRASES = (
    "healthier",
    "unhealthy",
    "superfood",
    "treat ",
    "cure ",
    "prevent ",
    "diagnos",
    "prescrib",
    "you should eat",
    "you must eat",
    "stop taking",
    "medication",
    "diabetes",
    "hypertension",
    "pcos",
)


def _extract_portion_and_state(fragment: str) -> dict[str, Any]:
    cleaned = fragment.strip(" ,.;:!?")
    cleaned = re.sub(
        r"^(?:compare|comparison\s+of|nutrients?\s+(?:in|of)|between|a|an|the)\s+",
        "",
        cleaned,
        flags=re.IGNORECASE,
    ).strip()

    grams = 100.0
    weight_match = re.search(
        r"\b(\d+(?:\.\d+)?)\s*(?:grams?|gms?|g)\b",
        cleaned,
        flags=re.IGNORECASE,
    )
    if weight_match:
        grams = float(weight_match.group(1))
        cleaned = (cleaned[: weight_match.start()] + " " + cleaned[weight_match.end() :]).strip()
    else:
        kg_match = re.search(r"\b(\d+(?:\.\d+)?)\s*(?:kg|kilograms?)\b", cleaned, flags=re.IGNORECASE)
        if kg_match:
            grams = float(kg_match.group(1)) * 1000.0
            cleaned = (cleaned[: kg_match.start()] + " " + cleaned[kg_match.end() :]).strip()

    cleaned = re.sub(r"^\s*of\s+", "", cleaned, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)

    preferred_state: str | None = None
    tokens = re.findall(r"[a-zA-Z]+", cleaned.lower())
    for tok in tokens:
        if tok in {"cooked", "boiled", "steamed", "roasted", "grilled"}:
            preferred_state = "cooked"
            break
        if tok in {"raw", "uncooked", "dry"}:
            preferred_state = "raw"
            break

    return {
        "query": cleaned or fragment.strip(),
        "grams": round(grams, 2) if grams > 0 else 100.0,
        "preferred_state": preferred_state,
    }


def _parse_deterministically(raw_query: str) -> dict[str, Any] | None:
    text = raw_query.strip()
    if not text:
        return None

    stripped = re.sub(
        r"^(?:please\s+)?(?:compare|show\s+(?:me\s+)?(?:the\s+)?comparison\s+(?:of|between)|what\s+is\s+the\s+difference\s+between|nutrients?\s+in)\s+",
        "",
        text,
        flags=re.IGNORECASE,
    ).strip()

    split_patterns = [
        r"\s+(?:vs\.?|versus|v/s)\s+",
        r"\s+compared\s+(?:to|with)\s+",
        r"\s+against\s+",
    ]
    parts: list[str] | None = None
    for pat in split_patterns:
        candidate = re.split(pat, stripped, maxsplit=1, flags=re.IGNORECASE)
        if len(candidate) == 2 and candidate[0].strip() and candidate[1].strip():
            parts = candidate
            break

    if parts is None and re.search(r"^(?:compare|between)\b", text, flags=re.IGNORECASE):
        candidate = re.split(r"\s+(?:and|with|to)\s+", stripped, maxsplit=1, flags=re.IGNORECASE)
        if len(candidate) == 2 and candidate[0].strip() and candidate[1].strip():
            parts = candidate

    if parts is None:
        return None

    left = _extract_portion_and_state(parts[0])
    right = _extract_portion_and_state(parts[1])
    return {"food_a": left, "food_b": right, "parser": "deterministic"}


def parse_comparison_query(raw_query: str) -> dict[str, Any]:
    """Parse free-text query into two structured food items + gram portions."""
    parsed = _parse_deterministically(raw_query)
    if parsed is not None:
        return parsed

    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if api_key:
        try:
            from google import genai
            from google.genai import types

            model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
            client = genai.Client(api_key=api_key)
            prompt = (
                "Extract the two foods and their portion weights in grams from this comparison request. "
                "Default grams to 100 if omitted. Return ONLY JSON with keys: "
                "food_a_name, food_a_grams, food_a_state (raw/cooked/null), "
                "food_b_name, food_b_grams, food_b_state (raw/cooked/null).\n"
                f"Query: {raw_query}"
            )
            resp = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.0,
                    response_mime_type="application/json",
                ),
            )
            data = json.loads((resp.text or "").strip())
            if data.get("food_a_name") and data.get("food_b_name"):
                return {
                    "food_a": {
                        "query": str(data["food_a_name"]).strip(),
                        "grams": float(data.get("food_a_grams") or 100.0),
                        "preferred_state": data.get("food_a_state") or None,
                    },
                    "food_b": {
                        "query": str(data["food_b_name"]).strip(),
                        "grams": float(data.get("food_b_grams") or 100.0),
                        "preferred_state": data.get("food_b_state") or None,
                    },
                    "parser": "gemini",
                }
        except Exception:
            pass

    raise ValueError(
        "Could not identify two foods to compare. Try a format like "
        "'Compare 150g cooked quinoa vs 100g rolled oats' or 'ragi vs moong dal'."
    )


def _deterministic_tailored_explanation(
    comparison: dict[str, Any],
    rules_analysis: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Generate a deterministic 1-sentence profile summary + 3-4 objective bullets."""
    fa = comparison["food_a"]
    fb = comparison["food_b"]
    rows = rules_analysis["comparison_rows"] if rules_analysis else comparison["rows"]
    rows_by_key = {row["key"]: row for row in rows}
    nhanes = comparison.get("nhanes_context") or {}

    if rules_analysis and rules_analysis.get("profile_summary"):
        ps = rules_analysis["profile_summary"]
        contexts_str = ", ".join(ps.get("health_context_labels", ["General Wellness"]))
        profile_summary_sentence = (
            f"Analyzed for Age {ps['age']} (NHANES {ps['age_group']}), "
            f"BMI {ps['bmi']} ({ps['bmi_category']}), {ps['activity_label']}, "
            f"focusing on {contexts_str} (Goal: {ps['goal_label']})."
        )
    else:
        profile_summary_sentence = (
            f"Objective nutrient comparison for {fa['portion_g']:g} g of {fa['name']} "
            f"versus {fb['portion_g']:g} g of {fb['name']}."
        )

    bullets: list[str] = []

    # Bullet 1 & 2: Top priority nutrients from rules_analysis
    priority_rows = [r for r in rows if r.get("is_focused") or r.get("is_priority")]
    if not priority_rows:
        priority_rows = [rows_by_key["energy_kcal"], rows_by_key["protein_g"]]

    for row in priority_rows[:2]:
        pct_a = row.get("food_a_pct_nhanes_median")
        pct_b = row.get("food_b_pct_nhanes_median")
        nhanes_part = ""
        if row.get("nhanes_median") is not None and pct_a is not None and pct_b is not None:
            nhanes_part = (
                f" — representing {pct_a}% and {pct_b}% of the CDC NHANES 2017–2018 "
                f"observational cohort median ({row['nhanes_median_display']}/day, "
                f"observational survey median only)"
            )
        bullets.append(
            f"{row['label']}: {fa['portion_g']:g} g of {fa['name']} provides "
            f"{row['food_a_display']} compared with {row['food_b_display']} in "
            f"{fb['portion_g']:g} g of {fb['name']} (difference A − B: {row['diff_display']})"
            f"{nhanes_part}."
        )

    # Bullet 3: Derived density / secondary macro comparison
    if rules_analysis and rules_analysis.get("derived_metrics"):
        dm = rules_analysis["derived_metrics"]
        p100_a = dm["food_a"].get("protein_per_100kcal")
        p100_b = dm["food_b"].get("protein_per_100kcal")
        energy = rows_by_key["energy_kcal"]
        fiber = rows_by_key["fiber_g"]
        if p100_a is not None and p100_b is not None:
            bullets.append(
                f"Energy & Protein Density: {fa['name']} supplies {energy['food_a_display']} "
                f"({p100_a} g protein per 100 kcal) and {fiber['food_a_display']} fiber, while "
                f"{fb['name']} supplies {energy['food_b_display']} ({p100_b} g protein per 100 kcal) "
                f"and {fiber['food_b_display']} fiber."
            )
    if len(bullets) < 3:
        carbs = rows_by_key["carbs_g"]
        fat = rows_by_key["fat_g"]
        bullets.append(
            f"Macronutrient Balance: {fa['name']} provides {carbs['food_a_display']} carbohydrates "
            f"and {fat['food_a_display']} fat, versus {carbs['food_b_display']} carbohydrates and "
            f"{fat['food_b_display']} fat in {fb['name']}."
        )

    # Bullet 4: Sources & deterministic reference tag summary
    sources = list(dict.fromkeys([fa["source_name"], fb["source_name"]]))
    if nhanes:
        sources.append(nhanes.get("source_name", "CDC NHANES 2017–2018"))
    source_str = (
        f"{', '.join(sources[:-1])} and {sources[-1]}"
        if len(sources) > 1
        else sources[0]
    )
    bullets.append(
        f"Data Grounding: All scaled nutrient quantities and survey benchmarks are computed "
        f"deterministically from {source_str} records for educational comparison only."
    )

    full_text = profile_summary_sentence + "\n" + "\n".join(f"• {b}" for b in bullets)
    return {
        "text": full_text,
        "profile_context_summary": profile_summary_sentence,
        "bullet_points": bullets,
        "provider": "deterministic_grounded",
    }


def generate_explanation(
    comparison: dict[str, Any],
    rules_analysis: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Generate strictly grounded Tailored Food Insights from verified Python JSON."""
    payload = {
        "food_a": {
            "food_id": comparison["food_a"]["food_id"],
            "name": comparison["food_a"]["name"],
            "state": comparison["food_a"]["state"],
            "portion_g": comparison["food_a"]["portion_g"],
            "source_name": comparison["food_a"]["source_name"],
            "source_url": comparison["food_a"]["source_url"],
        },
        "food_b": {
            "food_id": comparison["food_b"]["food_id"],
            "name": comparison["food_b"]["name"],
            "state": comparison["food_b"]["state"],
            "portion_g": comparison["food_b"]["portion_g"],
            "source_name": comparison["food_b"]["source_name"],
            "source_url": comparison["food_b"]["source_url"],
        },
        "rules_analysis": rules_analysis,
        "nutrient_comparison": [
            {
                "nutrient": row["label"],
                "unit": row["unit"],
                "priority": row.get("is_focused", False),
                "food_a_value": row["food_a_display"],
                "food_b_value": row["food_b_display"],
                "diff_a_minus_b": row["diff_display"],
                "pct_diff_vs_b": row["pct_diff_display"],
                "nhanes_observed_median": row.get("nhanes_median_display"),
                "food_a_pct_nhanes_median": row.get("food_a_pct_nhanes_median"),
                "food_b_pct_nhanes_median": row.get("food_b_pct_nhanes_median"),
            }
            for row in (rules_analysis["comparison_rows"] if rules_analysis else comparison["rows"])
        ],
    }

    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if api_key:
        try:
            from google import genai
            from google.genai import types

            model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
            client = genai.Client(api_key=api_key)
            resp = client.models.generate_content(
                model=model_name,
                contents=(
                    "Generate a strictly non-clinical Tailored Food Insights JSON summary from this verified rules_analysis payload:\n"
                    + json.dumps(payload, indent=2)
                ),
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    temperature=0.1,
                    response_mime_type="application/json",
                ),
            )
            parsed = json.loads((resp.text or "").strip())
            summary = str(parsed.get("profile_context_summary", "")).strip()
            bullets = [str(b).strip() for b in parsed.get("bullet_points", []) if str(b).strip()]
            combined = f"{summary}\n" + "\n".join(f"• {b}" for b in bullets)
            lowered = combined.lower()
            if (
                summary
                and len(bullets) >= 2
                and not any(banned in lowered for banned in BANNED_PHRASES)
            ):
                return {
                    "text": combined,
                    "profile_context_summary": summary,
                    "bullet_points": bullets[:4],
                    "provider": f"gemini:{model_name}",
                }
        except Exception:
            pass

    return _deterministic_tailored_explanation(comparison, rules_analysis=rules_analysis)
