"""Pre-retrieval clinical and medical advice guardrail.

Classifies whether an incoming query requests personalized medical, clinical,
or therapeutic dietary advice. When triggered, blocks retrieval/generation and
returns a polite boundary response, a structured suggested_lens, and an
objective comparison suggestion.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

DISCLAIMER_TEXT = (
    "Comparison data is based on USDA FDC, ICMR-NIN IFCT 2017, and CDC NHANES "
    "2017–2018 observational survey medians. Not personalized clinical or medical "
    "dietary advice."
)

LENS_LABELS: dict[str, str] = {
    "balanced": "Balanced",
    "protein_energy": "Protein & Energy",
    "carb_fiber": "Carb & Fiber",
    "sodium_potassium": "Sodium & Potassium",
    "iron_calcium": "Iron & Calcium",
}

# Medical conditions, clinical metrics, and therapeutic terms
CLINICAL_CONDITION_PATTERNS: list[str] = [
    r"\bdiabet(?:es|ic|ics)\b",
    r"\bprediabet(?:es|ic)\b",
    r"\bgestational\b",
    r"\bpcos\b",
    r"\bpcod\b",
    r"\bhypertension\b",
    r"\b(?:high|low)?\s*blood\s+pressure\b",
    r"\bbp\b",
    r"\bbmi\b",
    r"\bbody\s+mass\s+index\b",
    r"\bpatient\b",
    r"\bpregnan(?:t|cy)\b",
    r"\bbreastfeeding\b",
    r"\blactating\b",
    r"\banemi(?:a|c)\b",
    r"\bthyroid\b",
    r"\bhypothyroid(?:ism)?\b",
    r"\bhyperthyroid(?:ism)?\b",
    r"\bkidney\s+disease\b",
    r"\brenal\b",
    r"\bckd\b",
    r"\bliver\s+disease\b",
    r"\bfatty\s+liver\b",
    r"\bheart\s+disease\b",
    r"\bcardiac\b",
    r"\bcholesterol\b",
    r"\btriglycerides\b",
    r"\bgout\b",
    r"\buric\s+acid\b",
    r"\bceliac\b",
    r"\bibs\b",
    r"\bgastritis\b",
    r"\bulcer\b",
    r"\bcancer\b",
    r"\bobesity\b",
    r"\binsulin\s+resistance\b",
    r"\bblood\s+sugar\b",
    r"\bglucose\s+spike\b",
    r"\ba1c\b",
    r"\bhba1c\b",
    r"\bdeficiency\b",
]

# Therapeutic / personalized prescription intent patterns
CLINICAL_INTENT_PATTERNS: list[str] = [
    r"\bwhat\s+should\s+i\s+eat\b",
    r"\bwhat\s+can\s+i\s+eat\b",
    r"\bshould\s+i\s+eat\b",
    r"\bcan\s+i\s+eat\b",
    r"\bhow\s+much\s+[a-z\s]+\s+(?:can|should|may)\s+i\s+(?:eat|consume|take|have)\b",
    r"\bfor\s+my\s+condition\b",
    r"\bmy\s+(?:doctor|physician|condition|illness|disease|diagnosis|symptoms?|bmi)\b",
    r"\b(?:dosage|dose|limit|restriction)\b",
    r"\bsupplement\s+plan\b",
    r"\b(?:meal|diet)\s+plan\b",
    r"\btherapeutic\s+diet\b",
    r"\bmedical\s+(?:advice|diet|nutrition)\b",
    r"\b(?:cure|treat|heal|manage|reverse|prevent|control)\s+(?:my\s+)?[a-z]+\b",
    r"\bprescribe\b",
    r"\bmedication\b",
    r"\bwhich\s+(?:food\s+)?is\s+(?:healthier|better|safer)\s+for\s+(?:me|my|patients?)\b",
    r"\bis\s+it\s+safe\s+for\s+(?:me|my|someone\s+with)\b",
]

# Known food keywords for generating relevant objective fallback suggestions
KNOWN_FOOD_HINTS: list[tuple[str, str]] = [
    ("quinoa", "150g cooked quinoa"),
    ("oats", "100g rolled oats"),
    ("ragi", "100g finger millet (ragi)"),
    ("nachni", "100g finger millet (ragi)"),
    ("moong", "100g moong dal"),
    ("paneer", "100g paneer"),
    ("brown rice", "150g cooked brown rice"),
    ("rice", "150g cooked white rice"),
    ("egg", "100g boiled egg"),
    ("almond", "30g almonds"),
    ("spinach", "100g raw spinach"),
    ("palak", "100g raw spinach"),
    ("chickpea", "100g cooked chickpeas"),
    ("chana", "100g cooked chickpeas"),
    ("banana", "100g banana"),
    ("apple", "100g apple"),
    ("roti", "100g whole wheat roti"),
]


@dataclass(frozen=True)
class GuardrailResult:
    blocked: bool
    reason_category: str | None
    matched_signals: list[str]
    message: str
    suggested_comparison: str | None
    suggested_lens: str | None = None
    suggested_lens_label: str | None = None
    disclaimer: str = DISCLAIMER_TEXT


def _infer_suggested_lens(query: str) -> tuple[str, str]:
    lowered = query.lower()
    if re.search(
        r"\b(?:bp|blood\s+pressure|hypertension|sodium|salt|potassium|cardiac|heart\s+disease|renal|kidney|ckd)\b",
        lowered,
    ):
        return "sodium_potassium", LENS_LABELS["sodium_potassium"]
    if re.search(
        r"\b(?:diabet(?:es|ic|ics)|prediabet(?:es|ic)|blood\s+sugar|glucose|a1c|hba1c|insulin|pcos|pcod|carb|sugar|fiber)\b",
        lowered,
    ):
        return "carb_fiber", LENS_LABELS["carb_fiber"]
    if re.search(
        r"\b(?:anemi(?:a|c)|iron|calcium|pregnan(?:t|cy)|lactating|breastfeeding|bone|deficiency)\b",
        lowered,
    ):
        return "iron_calcium", LENS_LABELS["iron_calcium"]
    if re.search(
        r"\b(?:protein|energy|calorie|kcal|bmi|obesity|weight)\b",
        lowered,
    ):
        return "protein_energy", LENS_LABELS["protein_energy"]
    return "balanced", LENS_LABELS["balanced"]


def _suggest_objective_comparison(query: str, suggested_lens: str) -> str:
    lowered = query.lower()
    found: list[str] = []
    for keyword, label in KNOWN_FOOD_HINTS:
        if keyword in lowered and label not in found:
            found.append(label)
        if len(found) == 2:
            break

    if len(found) == 2:
        return f"Compare {found[0]} vs {found[1]}"
    if len(found) == 1:
        other = "100g rolled oats" if "oats" not in found[0] else "150g cooked quinoa"
        return f"Compare {found[0]} vs {other}"

    if suggested_lens == "sodium_potassium":
        return "Compare 100g spinach vs 100g boiled egg"
    if suggested_lens == "iron_calcium":
        return "Compare 100g finger millet (ragi) vs 100g paneer"
    return "Compare 150g cooked quinoa vs 100g rolled oats"


def check_clinical_guardrail(query: str | None) -> GuardrailResult:
    """Inspect user query before retrieval and block clinical/medical advice requests."""
    text = (query or "").strip()
    if not text:
        return GuardrailResult(
            blocked=False,
            reason_category=None,
            matched_signals=[],
            message="",
            suggested_comparison=None,
        )

    lowered = text.lower()
    matched_conditions: list[str] = []
    matched_intents: list[str] = []

    for pattern in CLINICAL_CONDITION_PATTERNS:
        m = re.search(pattern, lowered)
        if m:
            matched_conditions.append(m.group(0))

    for pattern in CLINICAL_INTENT_PATTERNS:
        m = re.search(pattern, lowered)
        if m:
            matched_intents.append(m.group(0))

    if matched_conditions or matched_intents:
        category = (
            "clinical_condition_and_advice"
            if (matched_conditions and matched_intents)
            else ("clinical_condition" if matched_conditions else "personalized_dietary_advice")
        )
        suggested_lens, suggested_lens_label = _infer_suggested_lens(text)
        suggestion = _suggest_objective_comparison(text, suggested_lens)
        signals = list(dict.fromkeys(matched_conditions + matched_intents))
        message = (
            "I cannot provide personalized medical, clinical, or therapeutic dietary advice "
            "(such as disease-specific meal plans, blood pressure/diabetes limits, or personal intake dosages). "
            "This assistant only performs factual, per-portion nutrient comparisons alongside "
            "observational population survey medians. Please consult a qualified physician or "
            "registered dietitian for clinical guidance. "
            f'If you would like an objective {suggested_lens_label} nutrient comparison, try: "{suggestion}".'
        )
        return GuardrailResult(
            blocked=True,
            reason_category=category,
            matched_signals=signals,
            message=message,
            suggested_comparison=suggestion,
            suggested_lens=suggested_lens,
            suggested_lens_label=suggested_lens_label,
        )

    return GuardrailResult(
        blocked=False,
        reason_category=None,
        matched_signals=[],
        message="",
        suggested_comparison=None,
    )
