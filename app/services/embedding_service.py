from __future__ import annotations

import hashlib
import random
from datetime import datetime, timezone
from typing import Optional

from google import genai
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.job import Job


class EmbeddingService:
    DEFAULT_MODEL = "gemini-embedding-001"
    EMBEDDING_API_VERSION = "v1beta"
    EMBEDDING_DIMENSION = 1536

    @classmethod
    def _ensure_embedding_table(cls, db: Session) -> None:
        db.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        db.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS entity_embeddings (
                    embedding_id BIGSERIAL PRIMARY KEY,
                    entity_type VARCHAR(32) NOT NULL,
                    entity_id BIGINT NOT NULL,
                    embedding VECTOR(1536) NOT NULL,
                    embedding_model VARCHAR(100) NOT NULL,
                    embedding_dimension INTEGER NOT NULL DEFAULT 1536,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    UNIQUE(entity_type, entity_id, embedding_model)
                )
                """
            )
        )
        db.commit()

    @classmethod
    def _fallback_embedding(cls, text_input: str) -> list[float]:
        seed_int = int(hashlib.sha256(text_input.encode("utf-8")).hexdigest(), 16)
        rng = random.Random(seed_int)
        return [round(rng.uniform(-1, 1), 6) for _ in range(cls.EMBEDDING_DIMENSION)]

    @classmethod
    def embed_text(cls, text_input: str, model: Optional[str] = None) -> list[float]:
        if not text_input or not text_input.strip():
            return cls._fallback_embedding("empty")

        selected_model = model or cls.DEFAULT_MODEL
        try:
            client = genai.Client(
                api_key=settings.GEMINI_API_KEY,
                http_options={"api_version": cls.EMBEDDING_API_VERSION},
            )
            response = client.models.embed_content(
                model=selected_model,
                contents=text_input,
                config={"output_dimensionality": cls.EMBEDDING_DIMENSION},
            )

            values = response.embeddings[0].values if response and response.embeddings else None
            if not values:
                return cls._fallback_embedding(text_input)

            vector = [float(v) for v in values]
            if len(vector) > cls.EMBEDDING_DIMENSION:
                return vector[: cls.EMBEDDING_DIMENSION]
            if len(vector) < cls.EMBEDDING_DIMENSION:
                return vector + [0.0] * (cls.EMBEDDING_DIMENSION - len(vector))
            return vector
        except Exception:
            return cls._fallback_embedding(text_input)

    @classmethod
    def _build_job_text(cls, job: Job) -> str:
        skill_names = ", ".join(
            sorted(
                {
                    item.skill.name
                    for item in (job.job_skills or [])
                    if item.skill and item.skill.name
                }
            )
        )
        parts = [
            job.title or "",
            job.company.name if job.company else "",
            job.location or "",
            skill_names,
            job.description_clean or "",
            job.description_raw or "",
        ]
        return "\n".join(part.strip() for part in parts if part and part.strip())

    @classmethod
    def sync_job_embeddings(
        cls,
        db: Session,
        limit: int = 20,
        only_missing: bool = True,
        model: Optional[str] = None,
    ) -> dict:
        cls._ensure_embedding_table(db)

        selected_model = model or cls.DEFAULT_MODEL
        jobs = db.query(Job).order_by(Job.scraped_at.desc()).limit(max(limit, 1)).all()

        processed = 0
        skipped = 0
        failed = 0

        for job in jobs:
            try:
                if only_missing:
                    exists = db.execute(
                        text(
                            """
                            SELECT 1
                            FROM entity_embeddings
                            WHERE entity_type = 'job'
                              AND entity_id = :entity_id
                              AND embedding_model = :embedding_model
                            LIMIT 1
                            """
                        ),
                        {"entity_id": job.job_id, "embedding_model": selected_model},
                    ).scalar()
                    if exists:
                        skipped += 1
                        continue

                source_text = cls._build_job_text(job)
                embedding_values = cls.embed_text(source_text, selected_model)
                embedding_literal = "[" + ",".join(str(v) for v in embedding_values) + "]"

                db.execute(
                    text(
                        """
                        INSERT INTO entity_embeddings (
                            entity_type,
                            entity_id,
                            embedding,
                            embedding_model,
                            embedding_dimension,
                            created_at
                        ) VALUES (
                            'job',
                            :entity_id,
                            CAST(:embedding AS vector),
                            :embedding_model,
                            :embedding_dimension,
                            :created_at
                        )
                        ON CONFLICT (entity_type, entity_id, embedding_model)
                        DO UPDATE SET
                            embedding = EXCLUDED.embedding,
                            embedding_dimension = EXCLUDED.embedding_dimension,
                            created_at = EXCLUDED.created_at
                        """
                    ),
                    {
                        "entity_id": job.job_id,
                        "embedding": embedding_literal,
                        "embedding_model": selected_model,
                        "embedding_dimension": cls.EMBEDDING_DIMENSION,
                        "created_at": datetime.now(timezone.utc),
                    },
                )
                processed += 1
            except Exception:
                db.rollback()
                failed += 1
                continue

        db.commit()
        return {
            "total_jobs": len(jobs),
            "processed": processed,
            "skipped": skipped,
            "failed": failed,
            "model": selected_model,
            "dimension": cls.EMBEDDING_DIMENSION,
        }
