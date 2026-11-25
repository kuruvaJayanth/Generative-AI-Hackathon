"""Hybrid SQLite + ChromaDB RAG store for food nutrient retrieval & alias resolution."""

from __future__ import annotations

import os
import re
import sqlite3
import zlib
from pathlib import Path
from typing import Any

import chromadb
from chromadb.api.types import Documents, EmbeddingFunction, Embeddings
from chromadb.config import Settings
from chromadb.utils.embedding_functions import register_embedding_function
import numpy as np

from nhanes_benchmarks import ensure_nhanes_loaded
from seed_data import SEED_FOODS

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DATA_DIR = BASE_DIR / "data"
DEFAULT_DB_PATH = DEFAULT_DATA_DIR / "nutrients.db"
DEFAULT_CHROMA_DIR = DEFAULT_DATA_DIR / "chroma_db"

STATE_TOKENS = {"raw", "uncooked", "dry", "cooked", "boiled", "steamed", "roasted", "grilled"}


@register_embedding_function
class FoodNgramEmbeddingFunction(EmbeddingFunction[Documents]):
    """Deterministic, zero-network word + char n-gram embedding for ChromaDB."""

    def __init__(self, dim: int = 384) -> None:
        self.dim = dim

    def __call__(self, input: Documents) -> Embeddings:
        vectors: list[list[float]] = []
        for text in input:
            vec = np.zeros(self.dim, dtype=np.float32)
            cleaned = re.sub(r"[^a-z0-9\s]+", " ", (text or "").lower()).strip()
            words = cleaned.split()

            # Word unigrams and bigrams
            for w in words:
                idx = zlib.crc32(f"w:{w}".encode("utf-8")) % self.dim
                vec[idx] += 2.0
            for i in range(len(words) - 1):
                bg = f"{words[i]}_{words[i + 1]}"
                idx = zlib.crc32(f"b:{bg}".encode("utf-8")) % self.dim
                vec[idx] += 1.5

            # Character 3-grams and 4-grams for fuzzy/regional spelling tolerance
            padded = f" {cleaned} "
            for n in (3, 4):
                for i in range(max(0, len(padded) - n + 1)):
                    gram = padded[i : i + n]
                    if gram.strip():
                        idx = zlib.crc32(f"c{n}:{gram}".encode("utf-8")) % self.dim
                        vec[idx] += 0.6

            norm = float(np.linalg.norm(vec))
            if norm > 0:
                vec /= norm
            else:
                vec[0] = 1.0
            vectors.append(vec.tolist())
        return vectors

    @staticmethod
    def name() -> str:
        return "food_ngram_v1"

    def get_config(self) -> dict[str, Any]:
        return {"dim": self.dim}

    @staticmethod
    def build_from_config(config: dict[str, Any]) -> "FoodNgramEmbeddingFunction":
        return FoodNgramEmbeddingFunction(dim=int(config.get("dim", 384)))


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9\s]+", " ", text.lower())).strip()


def _tokenize(text: str) -> set[str]:
    return {t for t in _normalize_text(text).split() if t}


class NutrientRAGStore:
    """Manages SQLite structured food records and ChromaDB semantic/alias index."""

    def __init__(
        self,
        db_path: str | Path | None = None,
        chroma_dir: str | Path | None = None,
        auto_seed: bool = True,
    ) -> None:
        self.db_path = Path(db_path or os.getenv("SQLITE_DB_PATH") or DEFAULT_DB_PATH)
        self.chroma_dir = Path(chroma_dir or os.getenv("CHROMA_PERSIST_DIR") or DEFAULT_CHROMA_DIR)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.chroma_dir.mkdir(parents=True, exist_ok=True)

        self._init_sqlite()
        self._ef = FoodNgramEmbeddingFunction()
        self._chroma_client = chromadb.PersistentClient(
            path=str(self.chroma_dir),
            settings=Settings(anonymized_telemetry=False),
        )
        self._collection = self._chroma_client.get_or_create_collection(
            name="food_nutrients_index",
            embedding_function=self._ef,
            metadata={"hnsw:space": "cosine"},
        )

        if auto_seed:
            self.ensure_seeded()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_sqlite(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS foods (
                    food_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    aliases TEXT NOT NULL DEFAULT '',
                    state TEXT NOT NULL DEFAULT 'raw',
                    source_name TEXT NOT NULL,
                    source_url TEXT NOT NULL,
                    energy_kcal REAL,
                    protein_g REAL,
                    carbs_g REAL,
                    fiber_g REAL,
                    sugar_g REAL,
                    fat_g REAL,
                    sodium_mg REAL,
                    potassium_mg REAL,
                    iron_mg REAL,
                    calcium_mg REAL
                )
                """
            )
            existing_cols = {
                row["name"]
                for row in conn.execute("PRAGMA table_info(foods)").fetchall()
            }
            for col in ("sugar_g", "sodium_mg", "potassium_mg"):
                if col not in existing_cols:
                    conn.execute(f"ALTER TABLE foods ADD COLUMN {col} REAL")
            conn.commit()

    def ensure_seeded(self) -> None:
        """Seed sample foods if SQLite is empty, upgrade missing columns/rows, and load NHANES."""
        existing_ids = {r["food_id"] for r in self.list_foods()}
        seed_ids = {r["food_id"] for r in SEED_FOODS}
        if not existing_ids or not seed_ids.issubset(existing_ids):
            self.upsert_foods(SEED_FOODS)
        else:
            sample = self.get_food_by_id("FDC-173904")
            if sample and sample.get("sodium_mg") is None:
                self.upsert_foods(SEED_FOODS)
            elif self._collection.count() == 0:
                self._sync_all_to_chroma()
        ensure_nhanes_loaded(db_path=self.db_path)

    def count_foods(self) -> int:
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) AS cnt FROM foods").fetchone()
            return int(row["cnt"]) if row else 0

    def list_foods(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM foods ORDER BY name ASC").fetchall()
            return [dict(r) for r in rows]

    def get_food_by_id(self, food_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM foods WHERE food_id = ?", (food_id,)).fetchone()
            return dict(row) if row else None

    def upsert_foods(self, records: list[dict[str, Any]]) -> int:
        if not records:
            return 0

        with self._connect() as conn:
            for rec in records:
                conn.execute(
                    """
                    INSERT INTO foods (
                        food_id, name, aliases, state, source_name, source_url,
                        energy_kcal, protein_g, carbs_g, fiber_g, sugar_g, fat_g,
                        sodium_mg, potassium_mg, iron_mg, calcium_mg
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(food_id) DO UPDATE SET
                        name = excluded.name,
                        aliases = excluded.aliases,
                        state = excluded.state,
                        source_name = excluded.source_name,
                        source_url = excluded.source_url,
                        energy_kcal = excluded.energy_kcal,
                        protein_g = excluded.protein_g,
                        carbs_g = excluded.carbs_g,
                        fiber_g = excluded.fiber_g,
                        sugar_g = excluded.sugar_g,
                        fat_g = excluded.fat_g,
                        sodium_mg = excluded.sodium_mg,
                        potassium_mg = excluded.potassium_mg,
                        iron_mg = excluded.iron_mg,
                        calcium_mg = excluded.calcium_mg
                    """,
                    (
                        rec["food_id"],
                        rec["name"],
                        rec.get("aliases", ""),
                        rec.get("state", "raw"),
                        rec["source_name"],
                        rec["source_url"],
                        rec.get("energy_kcal"),
                        rec.get("protein_g"),
                        rec.get("carbs_g"),
                        rec.get("fiber_g"),
                        rec.get("sugar_g"),
                        rec.get("fat_g"),
                        rec.get("sodium_mg"),
                        rec.get("potassium_mg"),
                        rec.get("iron_mg"),
                        rec.get("calcium_mg"),
                    ),
                )
            conn.commit()

        ids = [r["food_id"] for r in records]
        docs = [
            f"{r['name']} | {r.get('aliases', '')} | {r.get('state', 'raw')}"
            for r in records
        ]
        metas = [
            {
                "food_id": r["food_id"],
                "name": r["name"],
                "state": r.get("state", "raw"),
            }
            for r in records
        ]
        self._collection.upsert(ids=ids, documents=docs, metadatas=metas)
        return len(records)

    def _sync_all_to_chroma(self) -> None:
        all_rows = self.list_foods()
        if not all_rows:
            return
        ids = [r["food_id"] for r in all_rows]
        docs = [
            f"{r['name']} | {r.get('aliases', '')} | {r.get('state', 'raw')}"
            for r in all_rows
        ]
        metas = [
            {
                "food_id": r["food_id"],
                "name": r["name"],
                "state": r.get("state", "raw"),
            }
            for r in all_rows
        ]
        self._collection.upsert(ids=ids, documents=docs, metadatas=metas)

    def resolve_food(
        self,
        query: str,
        preferred_state: str | None = None,
    ) -> dict[str, Any]:
        """Resolve a food name or regional alias to an exact SQLite record via hybrid RAG."""
        cleaned_query = (query or "").strip()
        if not cleaned_query:
            raise LookupError("Empty food query provided.")

        norm_q = _normalize_text(cleaned_query)
        q_tokens = _tokenize(cleaned_query)
        core_q_tokens = q_tokens - STATE_TOKENS
        if not core_q_tokens:
            core_q_tokens = q_tokens

        # Infer preferred state from query tokens if caller did not specify
        if preferred_state is None:
            if q_tokens & {"cooked", "boiled", "steamed", "roasted", "grilled"}:
                preferred_state = "cooked"
            elif q_tokens & {"raw", "uncooked", "dry"}:
                preferred_state = "raw"

        # 1. ChromaDB vector search
        total_indexed = self._collection.count()
        chroma_scores: dict[str, float] = {}
        if total_indexed > 0:
            n_results = min(8, total_indexed)
            chroma_res = self._collection.query(
                query_texts=[cleaned_query],
                n_results=n_results,
            )
            res_ids = (chroma_res.get("ids") or [[]])[0]
            res_dists = (chroma_res.get("distances") or [[]])[0]
            for fid, dist in zip(res_ids, res_dists):
                chroma_scores[fid] = max(0.0, 1.0 - float(dist))

        # 2. Hybrid scoring over SQLite records (exact alias + token match + ChromaDB vector score)
        all_foods = self.list_foods()
        if not all_foods:
            raise LookupError("Food nutrient database is empty.")

        best_record: dict[str, Any] | None = None
        best_score = -1.0
        best_method = "chromadb_rag"

        for rec in all_foods:
            fid = rec["food_id"]
            rec_name_norm = _normalize_text(rec["name"])
            alias_list = [
                _normalize_text(a)
                for a in re.split(r"[,;|]+", rec.get("aliases") or "")
                if _normalize_text(a)
            ]
            rec_tokens = _tokenize(f"{rec['name']} {rec.get('aliases', '')}")
            core_rec_tokens = rec_tokens - STATE_TOKENS

            lexical_score = 0.0
            method = "chromadb_rag"

            if norm_q == rec_name_norm or norm_q in alias_list:
                lexical_score += 1.2
                method = "exact_alias_rag"
            else:
                q_without_state = _normalize_text(" ".join(t for t in norm_q.split() if t not in STATE_TOKENS))
                if q_without_state and (
                    q_without_state == rec_name_norm or q_without_state in alias_list
                ):
                    lexical_score += 1.05
                    method = "alias_state_rag"

            if core_q_tokens and core_rec_tokens:
                overlap = len(core_q_tokens & core_rec_tokens)
                recall = overlap / len(core_q_tokens)
                lexical_score += 0.65 * recall
                if overlap > 0 and method == "chromadb_rag":
                    method = "hybrid_rag"

            state_bonus = 0.0
            rec_state = (rec.get("state") or "raw").lower()
            if preferred_state:
                if rec_state == preferred_state.lower():
                    state_bonus = 0.4
                else:
                    state_bonus = -0.15
            else:
                # Default preference for raw/base staples unless item is inherently prepared (e.g., boiled egg)
                if rec_state == "raw":
                    state_bonus = 0.05

            vec_sim = chroma_scores.get(fid, 0.0)
            total_score = lexical_score + 0.65 * vec_sim + state_bonus

            if total_score > best_score:
                best_score = total_score
                best_record = rec
                best_method = method

        if best_record is None or best_score < 0.32:
            raise LookupError(
                f"No matching food found in database for '{query}'. "
                "Try standard names or ingest additional items via ingest_usda.py."
            )

        enriched = dict(best_record)
        enriched["_match_method"] = best_method
        enriched["_similarity_score"] = round(float(best_score), 4)
        return enriched


_DEFAULT_STORE: NutrientRAGStore | None = None


def get_store() -> NutrientRAGStore:
    global _DEFAULT_STORE
    if _DEFAULT_STORE is None:
        _DEFAULT_STORE = NutrientRAGStore()
    return _DEFAULT_STORE
