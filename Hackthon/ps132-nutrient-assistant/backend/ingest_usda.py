"""Live USDA FoodData Central API ingestion & ICMR-NIN IFCT 2017 CSV importer.

Usage examples:
    python ingest_usda.py --foods "rolled oats" "cooked quinoa" "paneer"
    python ingest_usda.py --ifct-csv path/to/ifct2017.csv
"""

from __future__ import annotations

import argparse
import csv
import os
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

from rag_store import NutrientRAGStore, get_store
from seed_data import IFCT_SOURCE_NAME, IFCT_SOURCE_URL, USDA_SOURCE_NAME, usda_food_url

FDC_SEARCH_URL = "https://api.nal.usda.gov/fdc/v1/foods/search"

# USDA FDC nutrient numbers and nutrient IDs mapped to our SQLite schema
NUTRIENT_NUMBER_MAP: dict[str, str] = {
    "208": "energy_kcal",
    "1008": "energy_kcal",
    "203": "protein_g",
    "1003": "protein_g",
    "205": "carbs_g",
    "1005": "carbs_g",
    "291": "fiber_g",
    "1079": "fiber_g",
    "269": "sugar_g",
    "2000": "sugar_g",
    "204": "fat_g",
    "1004": "fat_g",
    "307": "sodium_mg",
    "1093": "sodium_mg",
    "306": "potassium_mg",
    "1092": "potassium_mg",
    "303": "iron_mg",
    "1089": "iron_mg",
    "301": "calcium_mg",
    "1087": "calcium_mg",
}


def _infer_state(description: str) -> str:
    lowered = description.lower()
    for word in ("cooked", "boiled", "steamed", "roasted", "baked", "grilled", "fried"):
        if word in lowered:
            return "cooked"
    return "raw"


def _parse_float(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if text in {"", "-", "NA", "N/A", "null", "None", "tr", "Tr"}:
        return None
    try:
        return round(float(text), 2)
    except ValueError:
        return None


def parse_usda_food_item(item: dict[str, Any], extra_aliases: str = "") -> dict[str, Any]:
    """Convert a single USDA FoodData Central search result item to our SQLite schema."""
    fdc_id = str(item.get("fdcId", "")).strip()
    description = str(item.get("description", "")).strip()
    if not fdc_id or not description:
        raise ValueError("USDA item missing fdcId or description.")

    nutrients: dict[str, float | None] = {
        "energy_kcal": None,
        "protein_g": None,
        "carbs_g": None,
        "fiber_g": None,
        "sugar_g": None,
        "fat_g": None,
        "sodium_mg": None,
        "potassium_mg": None,
        "iron_mg": None,
        "calcium_mg": None,
    }

    for n in item.get("foodNutrients", []):
        num = str(n.get("nutrientNumber") or n.get("nutrientId") or "").strip()
        unit = str(n.get("unitName") or "").strip().lower()
        target_col = NUTRIENT_NUMBER_MAP.get(num)
        if not target_col:
            continue
        # Ensure energy is kcal rather than kJ
        if target_col == "energy_kcal" and unit and unit != "kcal":
            continue
        val = _parse_float(n.get("value"))
        if val is not None and nutrients[target_col] is None:
            nutrients[target_col] = val

    common_names = str(item.get("commonNames") or "").strip()
    alias_parts = [p for p in [common_names, extra_aliases] if p]

    return {
        "food_id": f"FDC-{fdc_id}",
        "name": description,
        "aliases": ", ".join(alias_parts),
        "state": _infer_state(description),
        "source_name": USDA_SOURCE_NAME,
        "source_url": usda_food_url(fdc_id),
        **nutrients,
    }


def fetch_usda_foods(
    queries: list[str],
    api_key: str | None = None,
    page_size: int = 3,
    timeout: int = 20,
) -> list[dict[str, Any]]:
    """Query the live USDA FoodData Central API and return normalized food records."""
    key = (api_key or os.getenv("USDA_FDC_API_KEY") or "DEMO_KEY").strip()
    records: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    for query in queries:
        resp = requests.get(
            FDC_SEARCH_URL,
            params={
                "api_key": key,
                "query": query,
                "pageSize": page_size,
                "dataType": "Foundation,SR Legacy",
            },
            timeout=timeout,
        )
        resp.raise_for_status()
        payload = resp.json()
        for item in payload.get("foods", []):
            rec = parse_usda_food_item(item, extra_aliases=query.lower())
            if rec["food_id"] not in seen_ids:
                seen_ids.add(rec["food_id"])
                records.append(rec)

    return records


def import_ifct_csv(csv_path: str | Path) -> list[dict[str, Any]]:
    """Parse an ICMR-NIN IFCT 2017 CSV export into normalized SQLite/Chroma records."""
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"IFCT CSV file not found: {path}")

    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for idx, raw_row in enumerate(reader, start=1):
            row = {k.strip().lower(): (v.strip() if v is not None else "") for k, v in raw_row.items() if k}
            food_id = (
                row.get("food_id")
                or row.get("code")
                or row.get("ifct_code")
                or f"IFCT-CSV-{idx:04d}"
            )
            name = row.get("name") or row.get("food_name") or row.get("food")
            if not name:
                continue

            aliases = row.get("aliases") or row.get("synonyms") or row.get("regional_names") or ""
            state = (row.get("state") or _infer_state(name)).lower()

            records.append(
                {
                    "food_id": food_id,
                    "name": name,
                    "aliases": aliases,
                    "state": state,
                    "source_name": row.get("source_name") or IFCT_SOURCE_NAME,
                    "source_url": row.get("source_url") or IFCT_SOURCE_URL,
                    "energy_kcal": _parse_float(row.get("energy_kcal") or row.get("energy")),
                    "protein_g": _parse_float(row.get("protein_g") or row.get("protein")),
                    "carbs_g": _parse_float(
                        row.get("carbs_g") or row.get("carbohydrates") or row.get("carbs")
                    ),
                    "fiber_g": _parse_float(
                        row.get("fiber_g") or row.get("dietary_fiber") or row.get("fiber")
                    ),
                    "sugar_g": _parse_float(row.get("sugar_g") or row.get("sugars") or row.get("sugar")),
                    "fat_g": _parse_float(row.get("fat_g") or row.get("fat")),
                    "sodium_mg": _parse_float(row.get("sodium_mg") or row.get("sodium")),
                    "potassium_mg": _parse_float(row.get("potassium_mg") or row.get("potassium")),
                    "iron_mg": _parse_float(row.get("iron_mg") or row.get("iron")),
                    "calcium_mg": _parse_float(row.get("calcium_mg") or row.get("calcium")),
                }
            )

    return records


def ingest_into_store(
    records: list[dict[str, Any]],
    store: NutrientRAGStore | None = None,
) -> int:
    target_store = store or get_store()
    return target_store.upsert_foods(records)


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(
        description="Ingest food composition data from USDA FoodData Central or IFCT 2017 CSV."
    )
    parser.add_argument(
        "--foods",
        nargs="+",
        default=[],
        help="Food search terms to fetch from USDA FoodData Central API.",
    )
    parser.add_argument(
        "--page-size",
        type=int,
        default=3,
        help="Max USDA search results per query (default: 3).",
    )
    parser.add_argument(
        "--ifct-csv",
        type=str,
        default="",
        help="Path to an ICMR-NIN IFCT 2017 CSV file to import.",
    )
    args = parser.parse_args()

    total_ingested = 0
    if args.foods:
        usda_records = fetch_usda_foods(args.foods, page_size=args.page_size)
        count = ingest_into_store(usda_records)
        total_ingested += count
        print(f"Ingested {count} USDA FoodData Central records.")

    if args.ifct_csv:
        ifct_records = import_ifct_csv(args.ifct_csv)
        count = ingest_into_store(ifct_records)
        total_ingested += count
        print(f"Ingested {count} ICMR-NIN IFCT 2017 CSV records.")

    if not args.foods and not args.ifct_csv:
        parser.print_help()
    else:
        print(f"Total upserted records: {total_ingested}")


if __name__ == "__main__":
    main()
