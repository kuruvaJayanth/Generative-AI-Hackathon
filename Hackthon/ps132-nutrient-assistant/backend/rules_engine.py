"""Deterministic Nutrition Reference Rules Engine.

Evaluates portion-scaled food nutrients against pairwise differences and
CDC NHANES 2017-2018 cohort medians, sorts priority_nutrients to the top,
computes a transparent Nutrient Quality Score + Goal Alignment Verdict,
generates everyday culinary suggestions, and builds a full exportable report.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from guardrail import DISCLAIMER_TEXT
from math_engine import FOCUS_LENS_CONFIG, format_value


def _compute_derived_metrics(food_summary: dict[str, Any]) -> dict[str, float | None]:
    scaled = food_summary.get("scaled_nutrients", {})
    per_100g = food_summary.get("per_100g_record", {})
    protein = scaled.get("protein_g")
    energy = scaled.get("energy_kcal")
    protein_per_100kcal = (
        round((float(protein) / float(energy)) * 100.0, 2)
        if protein is not None and energy is not None and float(energy) > 0
        else None
    )
    kcal_per_100g = per_100g.get("energy_kcal")
    return {
        "protein_per_100kcal": protein_per_100kcal,
        "kcal_per_100g": round(float(kcal_per_100g), 1) if kcal_per_100g is not None else None,
    }


def _make_tag(
    label: str,
    category: str,
    metric_text: str,
    is_priority: bool,
) -> dict[str, Any]:
    return {
        "label": label,
        "category": category,
        "metric_text": metric_text,
        "is_priority": is_priority,
    }


def _score_food_profile(
    food_summary: dict[str, Any],
    metrics: dict[str, float | None],
    health_contexts: set[str],
    goal: str,
) -> tuple[int, list[str]]:
    """Compute a transparent 0-100 Nutrient Quality Score aligned to user context & goal.

    Scored strictly per-100g nutrient density + context modifiers (never clinical).
    """
    rec = food_summary.get("per_100g_record", {})
    protein = float(rec.get("protein_g") or 0.0)
    fiber = float(rec.get("fiber_g") or 0.0)
    sugar = rec.get("sugar_g")
    sodium = float(rec.get("sodium_mg") or 0.0)
    potassium = float(rec.get("potassium_mg") or 0.0)
    iron = float(rec.get("iron_mg") or 0.0)
    calcium = float(rec.get("calcium_mg") or 0.0)
    kcal_100 = float(rec.get("energy_kcal") or 100.0)
    p_per_100kcal = float(metrics.get("protein_per_100kcal") or 0.0)

    # Base nutrient density score (anchored around 50)
    score = 50.0
    strengths: list[str] = []

    # Protein contribution (up to +18)
    prot_pts = min(18.0, p_per_100kcal * 1.4 + protein * 0.35)
    score += prot_pts
    if p_per_100kcal >= 4.0 or protein >= 12.0:
        strengths.append(f"strong protein density ({p_per_100kcal} g / 100 kcal)")

    # Fiber contribution (up to +16)
    fiber_pts = min(16.0, fiber * 1.6)
    score += fiber_pts
    if fiber >= 5.0:
        strengths.append(f"high dietary fiber ({fiber} g / 100 g)")

    # Sugar moderation (up to +6 / -10)
    if sugar is not None:
        s_val = float(sugar)
        if s_val <= 3.0:
            score += 6.0
            strengths.append(f"low natural/total sugar ({s_val} g / 100 g)")
        elif s_val > 12.0:
            score -= min(10.0, (s_val - 12.0) * 0.8)

    # Sodium moderation (up to +8 / -16)
    if sodium <= 50.0:
        score += 8.0
        strengths.append(f"very low sodium ({sodium:g} mg / 100 g)")
    elif sodium <= 150.0:
        score += 3.0
    elif sodium > 250.0:
        score -= min(16.0, (sodium - 250.0) / 30.0)

    # Potassium & Micronutrient boost (up to +12)
    micro_pts = min(6.0, potassium / 120.0) + min(4.0, iron * 0.8) + min(4.0, calcium / 90.0)
    score += micro_pts
    if iron >= 3.0:
        strengths.append(f"notable iron ({iron} mg / 100 g)")
    if calcium >= 150.0:
        strengths.append(f"notable calcium ({calcium} mg / 100 g)")

    # Context & goal alignment adjustments
    if "fitness_gym" in health_contexts or goal == "higher_protein":
        score += min(10.0, p_per_100kcal * 0.9) - (3.0 if p_per_100kcal < 2.0 else 0.0)
    if "blood_sugar_awareness" in health_contexts or goal == "higher_fiber_lower_sugar":
        score += min(8.0, fiber * 0.7) - (min(8.0, float(sugar or 0.0) * 0.5))
    if "blood_pressure_awareness" in health_contexts or goal == "lower_sodium":
        score += (6.0 if sodium <= 40.0 else -min(10.0, sodium / 60.0)) + min(5.0, potassium / 150.0)
    if "micronutrient_focus" in health_contexts:
        score += min(8.0, iron * 1.1 + calcium / 80.0)
    if goal == "lower_calorie_density":
        score += 8.0 if kcal_100 <= 130.0 else (-min(8.0, (kcal_100 - 250.0) / 40.0) if kcal_100 > 250 else 0.0)

    clamped = max(15, min(98, int(round(score))))
    return clamped, strengths[:3]


def _build_model_assessment(
    food_a: dict[str, Any],
    food_b: dict[str, Any],
    metrics_a: dict[str, float | None],
    metrics_b: dict[str, float | None],
    rows_by_key: dict[str, dict[str, Any]],
    health_contexts: set[str],
    goal: str,
    goal_label: str,
) -> dict[str, Any]:
    score_a, strengths_a = _score_food_profile(food_a, metrics_a, health_contexts, goal)
    score_b, strengths_b = _score_food_profile(food_b, metrics_b, health_contexts, goal)

    diff_score = score_a - score_b
    if abs(diff_score) <= 3:
        recommended = "balanced_tie"
        verdict_badge = "Balanced Match"
        verdict_title = (
            f"Close Overall Fit: {food_a['name']} ({score_a}/100) vs {food_b['name']} ({score_b}/100)"
        )
    elif diff_score > 0:
        recommended = "food_a"
        verdict_badge = "Higher Nutrient Fit"
        verdict_title = (
            f"Model Prediction: {food_a['name']} ({score_a}/100) is a stronger fit than {food_b['name']} ({score_b}/100)"
        )
    else:
        recommended = "food_b"
        verdict_badge = "Higher Nutrient Fit"
        verdict_title = (
            f"Model Prediction: {food_b['name']} ({score_b}/100) is a stronger fit than {food_a['name']} ({score_a}/100)"
        )

    def _tier(score: int) -> str:
        if score >= 80:
            return "High Nutrient Density"
        if score >= 65:
            return "Good Everyday Balance"
        if score >= 50:
            return "Moderate Nutrient Density"
        return "Energy-Dense / Occasional Choice"

    energy = rows_by_key.get("energy_kcal", {})
    protein = rows_by_key.get("protein_g", {})
    fiber = rows_by_key.get("fiber_g", {})
    sodium = rows_by_key.get("sodium_mg", {})

    winner = food_a if recommended == "food_a" else (food_b if recommended == "food_b" else food_a)
    runner = food_b if winner is food_a else food_a
    winner_strengths = strengths_a if winner is food_a else strengths_b
    runner_strengths = strengths_b if winner is food_a else strengths_a

    strength_text = ", ".join(winner_strengths) if winner_strengths else "balanced macro profile"
    runner_text = (
        ", ".join(runner_strengths)
        if runner_strengths
        else f"{energy.get('food_b_display' if runner is food_b else 'food_a_display', '')} energy profile"
    )

    if recommended == "balanced_tie":
        verdict_summary = (
            f"For your {goal_label} lens, both foods score closely ({food_a['name']}: {score_a}/100; "
            f"{food_b['name']}: {score_b}/100). {food_a['name']} offers {strength_text}, while "
            f"{food_b['name']} contributes {runner_text}."
        )
    else:
        verdict_summary = (
            f"For your {goal_label} lens, {winner['name']} scores higher ({max(score_a, score_b)}/100 vs "
            f"{min(score_a, score_b)}/100) driven by {strength_text} "
            f"(Protein: {protein.get('food_a_display')} vs {protein.get('food_b_display')}; "
            f"Fiber: {fiber.get('food_a_display')} vs {fiber.get('food_b_display')}; "
            f"Sodium: {sodium.get('food_a_display')} vs {sodium.get('food_b_display')}). "
            f"Meanwhile, {runner['name']} provides {runner_text}."
        )

    return {
        "food_a_score": score_a,
        "food_b_score": score_b,
        "food_a_tier": _tier(score_a),
        "food_b_tier": _tier(score_b),
        "food_a_strengths": strengths_a,
        "food_b_strengths": strengths_b,
        "recommended_choice": recommended,
        "verdict_badge": verdict_badge,
        "verdict_title": verdict_title,
        "verdict_summary": verdict_summary,
    }


def _build_suggestions(
    food_a: dict[str, Any],
    food_b: dict[str, Any],
    rows_by_key: dict[str, dict[str, Any]],
    health_contexts: set[str],
    goal: str,
) -> list[str]:
    suggestions: list[str] = []
    prot = rows_by_key.get("protein_g", {})
    fib = rows_by_key.get("fiber_g", {})
    sod = rows_by_key.get("sodium_mg", {})
    kcal = rows_by_key.get("energy_kcal", {})
    iron = rows_by_key.get("iron_mg", {})

    pa = prot.get("food_a_value") or 0.0
    pb = prot.get("food_b_value") or 0.0
    if min(pa, pb) < 7.0:
        low_food = food_a if pa <= pb else food_b
        suggestions.append(
            f"Protein pairing: {low_food['portion_g']:g} g of {low_food['name']} provides "
            f"{min(pa, pb):g} g protein; pairing it with moong dal, Greek yogurt, tofu, or boiled eggs "
            "increases overall meal protein."
        )

    fa = fib.get("food_a_value") or 0.0
    fb = fib.get("food_b_value") or 0.0
    if min(fa, fb) < 3.0 or "blood_sugar_awareness" in health_contexts or goal == "higher_fiber_lower_sugar":
        low_fib_food = food_a if fa <= fb else food_b
        suggestions.append(
            f"Fiber balance: Adding vegetables (spinach, broccoli) or whole legumes alongside "
            f"{low_fib_food['name']} ({min(fa, fb):g} g fiber in this portion) boosts dietary fiber."
        )

    na = sod.get("food_a_value") or 0.0
    nb = sod.get("food_b_value") or 0.0
    if max(na, nb) >= 250.0 or "blood_pressure_awareness" in health_contexts or goal == "lower_sodium":
        high_na_food = food_a if na >= nb else food_b
        suggestions.append(
            f"Sodium mindfulness: {high_na_food['name']} contains {max(na, nb):g} mg sodium in the "
            "selected portion—pairing with potassium-rich fresh produce or using herbs/spices instead of "
            "extra table salt helps keep total meal sodium moderate."
        )

    ka = kcal.get("food_a_value") or 0.0
    kb = kcal.get("food_b_value") or 0.0
    if max(ka, kb) >= 320.0 or goal == "lower_calorie_density":
        dense_food = food_a if ka >= kb else food_b
        suggestions.append(
            f"Portion sizing: {dense_food['portion_g']:g} g of {dense_food['name']} supplies "
            f"{max(ka, kb):g} kcal; scaling down to a 30–50 g serving or balancing with lower-calorie "
            "water-rich vegetables keeps total meal energy moderate."
        )

    ia = iron.get("food_a_value") or 0.0
    ib = iron.get("food_b_value") or 0.0
    if max(ia, ib) >= 2.5 and len(suggestions) < 4:
        rich_iron_food = food_a if ia >= ib else food_b
        suggestions.append(
            f"Micronutrient synergy: Pair iron-containing {rich_iron_food['name']} "
            f"({max(ia, ib):g} mg iron) with a vitamin-C source such as lemon juice, orange, or tomatoes "
            "to enhance non-heme iron absorption."
        )

    if not suggestions:
        suggestions.append(
            f"Balanced variety: Combine {food_a['name']} and {food_b['name']} across meals with "
            "colorful vegetables to diversify macronutrients and minerals."
        )

    return suggestions[:4]


def _build_final_report(
    food_a: dict[str, Any],
    food_b: dict[str, Any],
    profile_summary: dict[str, Any],
    sorted_rows: list[dict[str, Any]],
    model_assessment: dict[str, Any],
    suggestions: list[str],
    nhanes_context: dict[str, Any] | None,
) -> dict[str, Any]:
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    table_lines = [
        "| Nutrient | Food A | Food B | Diff (A - B) | NHANES Observed Median |",
        "| --- | --- | --- | --- | --- |",
    ]
    for r in sorted_rows:
        pct_a = r.get("food_a_pct_nhanes_median")
        pct_b = r.get("food_b_pct_nhanes_median")
        nhanes_cell = (
            f"{r['nhanes_median_display']}/day (A: {pct_a}%, B: {pct_b}%)"
            if r.get("nhanes_median") is not None
            else "N/A"
        )
        prefix = "**[Priority]** " if r.get("is_focused") else ""
        table_lines.append(
            f"| {prefix}{r['label']} | {r['food_a_display']} | {r['food_b_display']} | "
            f"{r['diff_display']} | {nhanes_cell} |"
        )

    suggestion_lines = "\n".join(f"- {s}" for s in suggestions)
    nhanes_cohort = (
        f"{nhanes_context.get('age_group')} | Activity: {nhanes_context.get('activity_level')} | "
        f"BMI: {nhanes_context.get('bmi_range')}"
        if nhanes_context
        else "All Adults"
    )

    markdown = f"""# PS 132 Nutrient Comparison & Quality Report

**Generated:** {timestamp}
**Compared Foods:** {food_a['portion_g']:g} g {food_a['name']} ({food_a['state']}) vs {food_b['portion_g']:g} g {food_b['name']} ({food_b['state']})
**Active User Profile:** {profile_summary['summary_line']}
**CDC NHANES 2017–2018 Cohort:** {nhanes_cohort}

## 1. Model Prediction & Nutrient Quality Assessment
- **Verdict:** {model_assessment['verdict_title']}
- **{food_a['name']} Score:** {model_assessment['food_a_score']}/100 ({model_assessment['food_a_tier']})
- **{food_b['name']} Score:** {model_assessment['food_b_score']}/100 ({model_assessment['food_b_tier']})
- **Summary:** {model_assessment['verdict_summary']}

## 2. Deterministic Nutrient Comparison Table
{chr(10).join(table_lines)}

## 3. Practical Everyday Suggestions
{suggestion_lines}

## 4. Official Sources & Non-Clinical Disclaimer
- **Food A ({food_a['food_id']}):** {food_a['source_name']} — {food_a['source_url']}
- **Food B ({food_b['food_id']}):** {food_b['source_name']} — {food_b['source_url']}
- **Population Survey Benchmarks:** CDC NHANES 2017–2018 — https://wwwn.cdc.gov/nchs/nhanes/continuousnhanes/overview.aspx?BeginYear=2017

> {DISCLAIMER_TEXT}
"""
    return {
        "title": f"{food_a['name']} vs {food_b['name']} — Nutrient Report",
        "generated_at": timestamp,
        "markdown": markdown.strip(),
    }


def run_rules_engine(
    comparison: dict[str, Any],
    profile_result: dict[str, Any],
) -> dict[str, Any]:
    """Apply deterministic nutrition reference rules over verified comparison data."""
    profile_summary = profile_result["profile_summary"]
    priority_nutrients: list[str] = list(profile_result["priority_nutrients"])
    health_contexts: set[str] = set(profile_summary.get("health_contexts", []))
    goal: str = profile_summary.get("goal", "balanced")
    goal_label: str = profile_summary.get("goal_label", "Balanced Nutrient Comparison")

    rows = [dict(r) for r in comparison["rows"]]
    priority_rank = {key: idx for idx, key in enumerate(priority_nutrients)}

    for row in rows:
        row["is_priority"] = row["key"] in priority_rank
        row["is_focused"] = row["key"] in priority_rank

    sorted_rows = sorted(
        rows,
        key=lambda r: (0, priority_rank[r["key"]]) if r["key"] in priority_rank else (1, 0),
    )

    rows_by_key = {r["key"]: r for r in sorted_rows}
    food_a = comparison["food_a"]
    food_b = comparison["food_b"]
    metrics_a = _compute_derived_metrics(food_a)
    metrics_b = _compute_derived_metrics(food_b)

    tags_a: list[dict[str, Any]] = []
    tags_b: list[dict[str, Any]] = []

    is_fitness = "fitness_gym" in health_contexts or goal == "higher_protein"
    prot = rows_by_key.get("protein_g")
    if prot and prot["food_a_value"] is not None and prot["food_b_value"] is not None:
        pa, pb = prot["food_a_value"], prot["food_b_value"]
        if pa > pb:
            tags_a.append(
                _make_tag(
                    "Higher Protein",
                    "protein_energy",
                    f"+{format_value(round(pa - pb, 2), 'g')} ({prot['food_a_display']})",
                    is_fitness,
                )
            )
        elif pb > pa:
            tags_b.append(
                _make_tag(
                    "Higher Protein",
                    "protein_energy",
                    f"+{format_value(round(pb - pa, 2), 'g')} ({prot['food_b_display']})",
                    is_fitness,
                )
            )

    p100_a = metrics_a["protein_per_100kcal"]
    p100_b = metrics_b["protein_per_100kcal"]
    if p100_a is not None and p100_b is not None:
        if p100_a > p100_b:
            tags_a.append(
                _make_tag(
                    "Higher Protein / 100 kcal",
                    "protein_energy",
                    f"{p100_a} g per 100 kcal",
                    is_fitness,
                )
            )
        elif p100_b > p100_a:
            tags_b.append(
                _make_tag(
                    "Higher Protein / 100 kcal",
                    "protein_energy",
                    f"{p100_b} g per 100 kcal",
                    is_fitness,
                )
            )

    is_sugar_ctx = (
        "blood_sugar_awareness" in health_contexts or goal == "higher_fiber_lower_sugar"
    )
    fib = rows_by_key.get("fiber_g")
    if fib and fib["food_a_value"] is not None and fib["food_b_value"] is not None:
        fa, fb = fib["food_a_value"], fib["food_b_value"]
        if fa > fb:
            tags_a.append(
                _make_tag(
                    "Higher Dietary Fiber",
                    "carb_fiber",
                    f"{fib['food_a_display']} ({fib['food_a_pct_nhanes_median']}% NHANES)",
                    is_sugar_ctx,
                )
            )
        elif fb > fa:
            tags_b.append(
                _make_tag(
                    "Higher Dietary Fiber",
                    "carb_fiber",
                    f"{fib['food_b_display']} ({fib['food_b_pct_nhanes_median']}% NHANES)",
                    is_sugar_ctx,
                )
            )

    sug = rows_by_key.get("sugar_g")
    if sug and sug["food_a_value"] is not None and sug["food_b_value"] is not None:
        sa, sb = sug["food_a_value"], sug["food_b_value"]
        if sa < sb:
            tags_a.append(
                _make_tag("Lower Sugar", "carb_fiber", sug["food_a_display"], is_sugar_ctx)
            )
        elif sb < sa:
            tags_b.append(
                _make_tag("Lower Sugar", "carb_fiber", sug["food_b_display"], is_sugar_ctx)
            )

    is_bp_ctx = "blood_pressure_awareness" in health_contexts or goal == "lower_sodium"
    sod = rows_by_key.get("sodium_mg")
    if sod and sod["food_a_value"] is not None and sod["food_b_value"] is not None:
        na, nb = sod["food_a_value"], sod["food_b_value"]
        if na < nb:
            tags_a.append(
                _make_tag("Lower Sodium", "sodium_potassium", sod["food_a_display"], is_bp_ctx)
            )
        elif nb < na:
            tags_b.append(
                _make_tag("Lower Sodium", "sodium_potassium", sod["food_b_display"], is_bp_ctx)
            )

    pot = rows_by_key.get("potassium_mg")
    if pot and pot["food_a_value"] is not None and pot["food_b_value"] is not None:
        ka, kb = pot["food_a_value"], pot["food_b_value"]
        if ka > kb:
            tags_a.append(
                _make_tag(
                    "Higher Potassium", "sodium_potassium", pot["food_a_display"], is_bp_ctx
                )
            )
        elif kb > ka:
            tags_b.append(
                _make_tag(
                    "Higher Potassium", "sodium_potassium", pot["food_b_display"], is_bp_ctx
                )
            )

    is_micro_ctx = "micronutrient_focus" in health_contexts
    iron = rows_by_key.get("iron_mg")
    if iron and iron["food_a_value"] is not None and iron["food_b_value"] is not None:
        ia, ib = iron["food_a_value"], iron["food_b_value"]
        if ia > ib:
            label = (
                "Rich in Iron"
                if (iron["food_a_pct_nhanes_median"] or 0) >= 20
                else "Higher Iron"
            )
            tags_a.append(
                _make_tag(label, "iron_calcium", iron["food_a_display"], is_micro_ctx)
            )
        elif ib > ia:
            label = (
                "Rich in Iron"
                if (iron["food_b_pct_nhanes_median"] or 0) >= 20
                else "Higher Iron"
            )
            tags_b.append(
                _make_tag(label, "iron_calcium", iron["food_b_display"], is_micro_ctx)
            )

    calc = rows_by_key.get("calcium_mg")
    if calc and calc["food_a_value"] is not None and calc["food_b_value"] is not None:
        ca, cb = calc["food_a_value"], calc["food_b_value"]
        if ca > cb:
            label = (
                "Rich in Calcium"
                if (calc["food_a_pct_nhanes_median"] or 0) >= 20
                else "Higher Calcium"
            )
            tags_a.append(
                _make_tag(label, "iron_calcium", calc["food_a_display"], is_micro_ctx)
            )
        elif cb > ca:
            label = (
                "Rich in Calcium"
                if (calc["food_b_pct_nhanes_median"] or 0) >= 20
                else "Higher Calcium"
            )
            tags_b.append(
                _make_tag(label, "iron_calcium", calc["food_b_display"], is_micro_ctx)
            )

    is_cal_goal = goal == "lower_calorie_density"
    ka_100 = metrics_a["kcal_per_100g"]
    kb_100 = metrics_b["kcal_per_100g"]
    if ka_100 is not None and kb_100 is not None:
        if ka_100 < kb_100:
            tags_a.append(
                _make_tag(
                    "Lower Calorie Density",
                    "energy",
                    f"{ka_100} kcal / 100g",
                    is_cal_goal,
                )
            )
        elif kb_100 < ka_100:
            tags_b.append(
                _make_tag(
                    "Lower Calorie Density",
                    "energy",
                    f"{kb_100} kcal / 100g",
                    is_cal_goal,
                )
            )

    tags_a.sort(key=lambda t: (0 if t["is_priority"] else 1))
    tags_b.sort(key=lambda t: (0 if t["is_priority"] else 1))

    focus_lens = profile_result.get("focus_lens", "balanced")
    focus_lens_label = FOCUS_LENS_CONFIG.get(focus_lens, FOCUS_LENS_CONFIG["balanced"])["label"]

    model_assessment = _build_model_assessment(
        food_a=food_a,
        food_b=food_b,
        metrics_a=metrics_a,
        metrics_b=metrics_b,
        rows_by_key=rows_by_key,
        health_contexts=health_contexts,
        goal=goal,
        goal_label=goal_label,
    )
    suggestions = _build_suggestions(
        food_a=food_a,
        food_b=food_b,
        rows_by_key=rows_by_key,
        health_contexts=health_contexts,
        goal=goal,
    )
    final_report = _build_final_report(
        food_a=food_a,
        food_b=food_b,
        profile_summary=profile_summary,
        sorted_rows=sorted_rows,
        model_assessment=model_assessment,
        suggestions=suggestions,
        nhanes_context=comparison.get("nhanes_context"),
    )

    return {
        "profile_summary": profile_summary,
        "priority_nutrients": [
            {
                "key": rows_by_key[k]["key"],
                "label": rows_by_key[k]["label"],
                "unit": rows_by_key[k]["unit"],
            }
            for k in priority_nutrients
            if k in rows_by_key
        ],
        "focus_lens": focus_lens,
        "focus_lens_label": focus_lens_label,
        "derived_metrics": {
            "food_a": metrics_a,
            "food_b": metrics_b,
        },
        "food_tags": {
            "food_a": tags_a[:4],
            "food_b": tags_b[:4],
        },
        "model_assessment": model_assessment,
        "suggestions": suggestions,
        "final_report": final_report,
        "comparison_rows": sorted_rows,
        "nhanes_benchmarks": comparison.get("nhanes_context"),
    }
