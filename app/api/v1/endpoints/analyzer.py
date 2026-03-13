from fastapi import APIRouter

from app.schemas.analyzer import (
    GapAnalysisRequest,
    GapAnalysisResponse,
    JobMatchRequest,
    JobMatchResponse,
)
from app.services.analysis_service import AnalysisService
from app.services.job_matching_service import JobMatchingService

router = APIRouter()


@router.post("/job-match", response_model=JobMatchResponse)
def calculate_job_match(payload: JobMatchRequest) -> JobMatchResponse:
    return JobMatchingService.calculate_job_match(payload)


@router.post("/gap-analysis", response_model=GapAnalysisResponse)
def calculate_gap_analysis(payload: GapAnalysisRequest) -> GapAnalysisResponse:
    return AnalysisService.generate_gap_analysis(payload)
