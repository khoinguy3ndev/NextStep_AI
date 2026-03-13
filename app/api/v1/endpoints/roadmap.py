from fastapi import APIRouter

from app.schemas.roadmap import RoadmapGenerateRequest, RoadmapGenerateResponse
from app.services.roadmap_service import RoadmapService

router = APIRouter()


@router.post("/generate", response_model=RoadmapGenerateResponse)
def generate_roadmap(payload: RoadmapGenerateRequest) -> RoadmapGenerateResponse:
    return RoadmapService.generate(payload)
