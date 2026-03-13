from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.embedding_service import EmbeddingService

router = APIRouter()


class SyncEmbeddingRequest(BaseModel):
    limit: int = Field(default=20, ge=1, le=200)
    only_missing: bool = True
    model: str | None = None


@router.post("/jobs/sync")
def sync_job_embeddings(payload: SyncEmbeddingRequest, db: Session = Depends(get_db)):
    result = EmbeddingService.sync_job_embeddings(
        db=db,
        limit=payload.limit,
        only_missing=payload.only_missing,
        model=payload.model,
    )
    return {"status": "success", "result": result}
