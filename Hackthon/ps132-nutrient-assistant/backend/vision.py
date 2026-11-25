"""Vision AI Layer: MobileNetV2 local weights -> Gemini Vision -> CLIP Zero-Shot Food Recognizer.

Identifies virtually any food image and returns top-3 candidate food names
matching our SQLite food composition database with confidence scores so the
user can confirm, edit, or auto-compare immediately.
"""

from __future__ import annotations

import io
import json
import os
import re
from pathlib import Path
from typing import Any

os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("TRANSFORMERS_NO_ADVISORY_WARNINGS", "1")

from PIL import Image

from seed_data import SEED_FOODS

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent

DEFAULT_MODEL_PATHS = [
    BASE_DIR / "models" / "food_classifier.pth",
    PROJECT_ROOT / "models" / "food_classifier.pth",
]
DEFAULT_CLASS_PATHS = [
    BASE_DIR / "models" / "class_names.json",
    PROJECT_ROOT / "models" / "class_names.json",
]

CLIP_MODEL_ID = "openai/clip-vit-base-patch32"

_CACHED_MODEL: dict[str, Any] = {}
_CACHED_CLIP: dict[str, Any] = {}

# Visual descriptions paired with canonical food names in SEED_FOODS so CLIP
# accurately recognizes raw ingredients, Indian dishes, and global foods.
FOOD_VISUAL_PROMPTS: list[tuple[str, str]] = [
    ("Rolled oats", "dry rolled oats oatmeal cereal flakes"),
    ("Oatmeal, cooked with water", "cooked oatmeal porridge bowl"),
    ("Quinoa, cooked", "cooked quinoa grains in a bowl"),
    ("Quinoa, uncooked", "uncooked dry quinoa seeds"),
    ("Finger millet (Ragi)", "finger millet ragi grain or dark reddish brown ragi flour"),
    ("Green gram dal (Moong dal)", "dry yellow split moong dal lentils"),
    ("Mung beans, mature seeds, cooked, boiled", "cooked yellow moong dal lentil curry"),
    ("Paneer (Cottage cheese)", "white indian paneer cottage cheese cubes"),
    ("Brown rice, cooked", "cooked brown rice grains"),
    ("White rice, cooked", "steamed white basmati rice"),
    ("Boiled egg (Whole, hard-boiled)", "peeled or sliced hard boiled egg"),
    ("Omelette / Scrambled eggs", "cooked egg omelette or scrambled eggs"),
    ("Almonds", "whole brown almonds nuts"),
    ("Walnuts", "shelled walnut halves nuts"),
    ("Peanuts, raw", "roasted or raw peanuts groundnuts"),
    ("Peanut butter, smooth", "creamy peanut butter spread"),
    ("Spinach, raw", "fresh green raw spinach leaves"),
    ("Spinach, cooked", "cooked wilted green spinach palak"),
    ("Chickpeas (Garbanzo beans), cooked", "cooked chickpeas garbanzo beans chole"),
    ("Bengal gram whole (Chickpeas), raw", "dry whole brown chickpeas kala chana"),
    ("Lentils (Masoor dal), cooked", "cooked red lentils masoor dal soup"),
    ("Rajma (Red kidney beans), cooked", "cooked red kidney beans rajma curry"),
    ("Banana", "yellow ripe banana fruit"),
    ("Apple", "fresh whole or sliced red or green apple fruit"),
    ("Orange, raw", "fresh orange citrus fruit"),
    ("Mango, raw", "fresh yellow ripe mango fruit or mango slices"),
    ("Strawberries, raw", "fresh red strawberries fruit"),
    ("Avocado, raw", "fresh green sliced avocado fruit"),
    ("Broccoli, raw", "fresh green broccoli florets"),
    ("Tomatoes, raw", "fresh red tomatoes"),
    ("Carrots, raw", "fresh orange carrots"),
    ("Sweet potato, baked", "baked orange sweet potato"),
    ("Potato, boiled", "boiled or baked white potato"),
    ("Mixed vegetable salad", "fresh green vegetable salad bowl"),
    ("Greek yogurt, plain, nonfat", "thick white greek yogurt in a bowl"),
    ("Curd / Dahi (Whole milk yogurt)", "plain white curd dahi yogurt bowl"),
    ("Milk, whole", "glass of white milk"),
    ("Cheddar cheese", "yellow cheddar cheese slices or blocks"),
    ("Tofu, firm", "white firm tofu bean curd blocks"),
    ("Chicken breast, grilled", "grilled cooked chicken breast slices"),
    ("Salmon, cooked", "grilled or baked pink salmon fish fillet"),
    ("Whole wheat roti (Chapati)", "indian whole wheat chapati roti flatbread"),
    ("Paratha (Whole wheat, plain)", "pan fried layered indian paratha flatbread"),
    ("Idli (Steamed rice & lentil cake)", "white steamed south indian idli rice cakes"),
    ("Masala Dosa (Crisp rice & lentil crepe)", "crispy golden south indian masala dosa crepe"),
    ("Poha (Flattened rice, cooked)", "cooked yellow indian poha flattened rice breakfast"),
    ("Upma (Semolina, cooked)", "cooked south indian rava upma semolina"),
    ("Samosa (Fried potato pastry)", "crispy fried triangular indian samosa pastry"),
    ("Chicken Biryani", "spiced indian chicken biryani basmati rice dish"),
    ("Vegetable Pulao / Veg Biryani", "spiced indian vegetable pulao or veg biryani rice"),
    ("Whole wheat bread", "sliced whole wheat brown bread or toast"),
    ("White bread", "sliced white sandwich bread"),
    ("Pasta, cooked", "cooked spaghetti or penne pasta dish"),
    ("Pizza, cheese", "baked pizza slice or whole cheese pizza"),
    ("Burger (Hamburger)", "hamburger or cheeseburger with bun"),
    ("French fries", "crispy golden french fries"),
    ("Fried rice", "cooked fried rice dish in a plate or bowl"),
    ("Sushi", "japanese sushi rolls maki platter"),
    ("Sandwich", "grilled or layered bread sandwich"),
    ("Dark chocolate (70-85% cacao)", "pieces of dark chocolate bar"),
]


def _find_local_weights() -> tuple[Path | None, Path | None]:
    model_path = next((p for p in DEFAULT_MODEL_PATHS if p.exists()), None)
    class_path = next((p for p in DEFAULT_CLASS_PATHS if p.exists()), None)
    return model_path, class_path


def _predict_with_mobilenet(
    image_bytes: bytes,
    model_path: Path,
    class_path: Path,
) -> list[dict[str, Any]]:
    import torch
    import torchvision.models as models
    import torchvision.transforms as transforms

    cache_key = f"{model_path}:{class_path}"
    if _CACHED_MODEL.get("key") != cache_key:
        with class_path.open("r", encoding="utf-8") as f:
            class_names = json.load(f)
        if not isinstance(class_names, list) or not class_names:
            raise ValueError("class_names.json must be a non-empty JSON list.")

        model = models.mobilenet_v2(weights=None)
        in_features = model.classifier[1].in_features
        model.classifier[1] = torch.nn.Linear(in_features, len(class_names))

        state_dict = torch.load(model_path, map_location="cpu", weights_only=True)
        if isinstance(state_dict, dict) and "state_dict" in state_dict:
            state_dict = state_dict["state_dict"]
        model.load_state_dict(state_dict)
        model.eval()

        _CACHED_MODEL["key"] = cache_key
        _CACHED_MODEL["model"] = model
        _CACHED_MODEL["class_names"] = class_names

    model = _CACHED_MODEL["model"]
    class_names = _CACHED_MODEL["class_names"]

    transform = transforms.Compose(
        [
            transforms.Resize(256),
            transforms.CenterCrop(224),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ]
    )

    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    tensor = transform(image).unsqueeze(0)

    with torch.no_grad():
        logits = model(tensor)
        probs = torch.softmax(logits, dim=1).squeeze(0)
        k = min(3, len(class_names))
        top_probs, top_indices = torch.topk(probs, k=k)

    return [
        {"name": str(class_names[idx]), "confidence": round(float(prob), 4)}
        for prob, idx in zip(top_probs.tolist(), top_indices.tolist())
    ]


def _predict_with_gemini(image_bytes: bytes, mime_type: str) -> list[dict[str, Any]]:
    from google import genai
    from google.genai import types

    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not configured.")

    model_name = os.getenv("GEMINI_VISION_MODEL", os.getenv("GEMINI_MODEL", "gemini-2.5-flash"))
    client = genai.Client(api_key=api_key)

    known_names = ", ".join(item["name"] for item in SEED_FOODS[:30])
    prompt = (
        "Identify the primary food in this image for nutrient database lookup. "
        "Return ONLY valid JSON with a top-level key 'predictions' containing exactly 3 objects, "
        "each with 'name' (concise food name; prefer matching names when applicable such as: "
        f"{known_names}) "
        "and 'confidence' (float between 0.0 and 1.0, descending)."
    )

    response = client.models.generate_content(
        model=model_name,
        contents=[
            types.Part.from_bytes(data=image_bytes, mime_type=mime_type or "image/jpeg"),
            prompt,
        ],
        config=types.GenerateContentConfig(
            temperature=0.1,
            response_mime_type="application/json",
        ),
    )

    raw_text = (response.text or "").strip()
    data = json.loads(raw_text)
    preds = data.get("predictions", [])
    cleaned: list[dict[str, Any]] = []
    for item in preds[:3]:
        name = str(item.get("name", "")).strip()
        if not name:
            continue
        conf = max(0.0, min(1.0, float(item.get("confidence", 0.5))))
        cleaned.append({"name": name, "confidence": round(conf, 4)})
    if not cleaned:
        raise ValueError("Gemini Vision returned empty predictions.")
    return cleaned


def _get_clip_resources():
    """Load and cache CLIP model, processor, and precomputed food text embeddings."""
    if _CACHED_CLIP.get("ready"):
        return (
            _CACHED_CLIP["model"],
            _CACHED_CLIP["processor"],
            _CACHED_CLIP["text_embeds"],
            _CACHED_CLIP["labels"],
        )

    import torch
    from transformers import CLIPModel, CLIPProcessor

    try:
        model = CLIPModel.from_pretrained(CLIP_MODEL_ID, local_files_only=True)
        processor = CLIPProcessor.from_pretrained(CLIP_MODEL_ID, local_files_only=True, use_fast=True)
    except Exception:
        model = CLIPModel.from_pretrained(CLIP_MODEL_ID)
        processor = CLIPProcessor.from_pretrained(CLIP_MODEL_ID, use_fast=True)

    model.eval()
    labels = [canonical for canonical, _ in FOOD_VISUAL_PROMPTS]
    prompts = [f"a close-up food photograph of {desc}" for _, desc in FOOD_VISUAL_PROMPTS]

    with torch.no_grad():
        text_inputs = processor(text=prompts, return_tensors="pt", padding=True, truncation=True)
        text_outputs = model.get_text_features(**text_inputs)
        text_embeds = text_outputs / text_outputs.norm(dim=-1, keepdim=True)

    _CACHED_CLIP["model"] = model
    _CACHED_CLIP["processor"] = processor
    _CACHED_CLIP["text_embeds"] = text_embeds
    _CACHED_CLIP["labels"] = labels
    _CACHED_CLIP["ready"] = True
    return model, processor, text_embeds, labels


def _predict_with_clip(image_bytes: bytes) -> list[dict[str, Any]]:
    import torch

    model, processor, text_embeds, labels = _get_clip_resources()
    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    img_inputs = processor(images=image, return_tensors="pt")

    with torch.no_grad():
        img_outputs = model.get_image_features(**img_inputs)
        img_embeds = img_outputs / img_outputs.norm(dim=-1, keepdim=True)
        logit_scale = model.logit_scale.exp().clamp(max=100.0)
        logits = (img_embeds @ text_embeds.T).squeeze(0) * logit_scale
        probs = torch.softmax(logits, dim=-1)
        top_probs, top_indices = torch.topk(probs, k=min(3, len(labels)))

    return [
        {"name": labels[idx], "confidence": round(float(prob), 4)}
        for prob, idx in zip(top_probs.tolist(), top_indices.tolist())
    ]


def _heuristic_offline_fallback(image_bytes: bytes, filename: str | None) -> list[dict[str, Any]]:
    """Last-resort offline fallback if local CLIP, custom weights, and Gemini are unavailable."""
    fname = (filename or "").lower()
    tokens = set(re.findall(r"[a-z]+", fname))

    matched: list[dict[str, Any]] = []
    for item in SEED_FOODS:
        haystack = f"{item['name']} {item.get('aliases', '')}".lower()
        hay_tokens = set(re.findall(r"[a-z]+", haystack))
        overlap = tokens.intersection(hay_tokens) - {"jpg", "jpeg", "png", "webp", "image", "food", "img"}
        if overlap:
            matched.append({"name": item["name"], "confidence": 0.78})
        if len(matched) >= 3:
            break

    if matched:
        defaults = ["Quinoa, cooked", "Rolled oats", "Finger millet (Ragi)"]
        existing = {m["name"] for m in matched}
        conf = 0.14
        for d in defaults:
            if len(matched) >= 3:
                break
            if d not in existing:
                matched.append({"name": d, "confidence": conf})
                conf = max(0.05, round(conf - 0.06, 2))
        return matched[:3]

    image = Image.open(io.BytesIO(image_bytes)).convert("RGB").resize((32, 32))
    pixels = list(image.getdata())
    r_avg = sum(p[0] for p in pixels) / len(pixels)
    g_avg = sum(p[1] for p in pixels) / len(pixels)
    b_avg = sum(p[2] for p in pixels) / len(pixels)

    if g_avg > r_avg + 10 and g_avg > b_avg + 10:
        return [
            {"name": "Spinach, raw", "confidence": 0.62},
            {"name": "Broccoli, raw", "confidence": 0.24},
            {"name": "Green gram dal (Moong dal)", "confidence": 0.14},
        ]
    return [
        {"name": "Quinoa, cooked", "confidence": 0.52},
        {"name": "Rolled oats", "confidence": 0.28},
        {"name": "Chickpeas (Garbanzo beans), cooked", "confidence": 0.20},
    ]


def identify_food_image(
    image_bytes: bytes,
    filename: str | None = None,
    mime_type: str = "image/jpeg",
) -> dict[str, Any]:
    """Identify top-3 food candidates from image bytes using MobileNetV2 -> Gemini -> CLIP -> fallback."""
    if not image_bytes:
        raise ValueError("Uploaded image is empty.")

    try:
        img = Image.open(io.BytesIO(image_bytes))
        img.verify()
    except Exception as exc:
        raise ValueError(f"Invalid image file: {exc}") from exc

    model_path, class_path = _find_local_weights()
    if model_path and class_path:
        try:
            preds = _predict_with_mobilenet(image_bytes, model_path, class_path)
            return {
                "provider": "mobilenet_v2_local",
                "predictions": preds,
                "note": "Predicted locally using PyTorch MobileNetV2 weights.",
            }
        except Exception as exc:
            local_err = str(exc)
    else:
        local_err = "Custom MobileNetV2 weights not found."

    if os.getenv("GEMINI_API_KEY", "").strip():
        try:
            preds = _predict_with_gemini(image_bytes, mime_type)
            return {
                "provider": "gemini_vision",
                "predictions": preds,
                "note": "Predicted using Gemini Vision (gemini-2.5-flash).",
            }
        except Exception as exc:
            gemini_err = str(exc)
    else:
        gemini_err = "GEMINI_API_KEY not set."

    try:
        preds = _predict_with_clip(image_bytes)
        return {
            "provider": "clip_zero_shot_local",
            "predictions": preds,
            "note": (
                f"Identified locally via CLIP Vision ({len(FOOD_VISUAL_PROMPTS)} food categories). "
                "You can pick any top-3 match or edit the food name before comparing."
            ),
        }
    except Exception as exc:
        clip_err = str(exc)

    preds = _heuristic_offline_fallback(image_bytes, filename)
    return {
        "provider": "offline_fallback",
        "predictions": preds,
        "note": (
            f"Offline preview mode ({local_err} {gemini_err} {clip_err}). "
            "Please confirm or edit the predicted food name before comparing."
        ),
    }
