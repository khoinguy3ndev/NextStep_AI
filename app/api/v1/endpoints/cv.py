from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import desc
from sqlalchemy.orm import Session
import re

from app.db.base_class import Base
from app.db.session import engine
from app.db.session import get_db
from app.models.cv_analysis_result import CvAnalysisResult
from app.models.cv_skill import CvSkill
from app.models.skill import Skill
from app.models.skill_gap import SkillGap
from app.schemas.analyzer import GapAnalysisRequest
from app.schemas.cv import AnalysisHistoryItem, AnalysisHistoryResponse, CvIngestRequest, CvIngestResponse
from app.schemas.roadmap import (
    MissingSkillInput,
    RoadmapGenerateRequest,
    WeakSkillInput,
)
from app.services.analysis_service import AnalysisService
from app.services.job_matching_service import JobMatchingService
from app.services.pdf_processor import CvIngestService
from app.services.roadmap_service import RoadmapService

router = APIRouter()


def _infer_cv_title(cv_text: str) -> str | None:
    if not cv_text:
        return None
    lines = [line.strip() for line in re.split(r"[\r\n]+", cv_text) if line.strip()]
    if lines:
        return lines[0][:120]

    fallback = cv_text.strip()
    return fallback[:120] if fallback else None


def _estimate_ats_score(cv_text: str) -> float:
    text = (cv_text or "").lower()
    score = 0.0
    if len(text) >= 300:
        score += 0.3
    if any(token in text for token in ["experience", "kinh nghiệm"]):
        score += 0.25
    if any(token in text for token in ["skills", "kỹ năng"]):
        score += 0.25
    if any(token in text for token in ["education", "học vấn"]):
        score += 0.2
    return min(1.0, score)


def _ensure_analysis_table() -> None:
    Base.metadata.create_all(
        bind=engine,
        tables=[
            CvAnalysisResult.__table__,
            CvSkill.__table__,
            SkillGap.__table__,
        ],
    )


def _build_skill_lookup(db: Session) -> tuple[dict[str, Skill], dict[str, Skill]]:
    skills = db.query(Skill).all()
    by_name: dict[str, Skill] = {}
    by_alias: dict[str, Skill] = {}

    for skill in skills:
        if not skill.name:
            continue
        name_key = skill.name.strip().lower()
        if name_key:
            by_name[name_key] = skill

        aliases = skill.aliases or []
        for alias in aliases:
            alias_key = str(alias or "").strip().lower()
            if alias_key and alias_key not in by_alias:
                by_alias[alias_key] = skill

    return by_name, by_alias


def _label_to_priority(label: str) -> float:
    normalized = (label or "").strip().lower()
    if normalized == "high":
        return 1.0
    if normalized == "medium":
        return 0.75
    return 0.5


def _persist_analysis_details(
    db: Session,
    analysis_id: int,
    extracted,
    gap_result,
) -> None:
    skill_by_name, skill_by_alias = _build_skill_lookup(db)

    cv_rows: list[CvSkill] = []
    for item in extracted.cv_skills:
        raw_name = (item.name or "").strip()
        if not raw_name:
            continue

        key = raw_name.lower()
        matched_skill = skill_by_name.get(key)
        confidence = 1.0

        if not matched_skill:
            matched_skill = skill_by_alias.get(key)
            confidence = 0.7 if matched_skill else 0.5

        if not matched_skill:
            continue

        cv_rows.append(
            CvSkill(
                analysis_id=analysis_id,
                skill_id=matched_skill.skill_id,
                confidence=confidence,
                source="regex",
            )
        )

    if cv_rows:
        db.add_all(cv_rows)

    gap_rows_by_skill: dict[int, SkillGap] = {}

    for item in gap_result.skillGap.missing:
        skill_name = (item.skill or "").strip().lower()
        matched_skill = skill_by_name.get(skill_name) or skill_by_alias.get(skill_name)
        if not matched_skill:
            continue

        priority = _label_to_priority(item.importance)
        gap_row = SkillGap(
            analysis_id=analysis_id,
            skill_id=matched_skill.skill_id,
            priority_score=priority,
            gap_reason=item.reason,
        )
        existing = gap_rows_by_skill.get(matched_skill.skill_id)
        if not existing or gap_row.priority_score > existing.priority_score:
            gap_rows_by_skill[matched_skill.skill_id] = gap_row

    for item in gap_result.skillGap.weak:
        skill_name = (item.skill or "").strip().lower()
        matched_skill = skill_by_name.get(skill_name) or skill_by_alias.get(skill_name)
        if not matched_skill:
            continue

        priority = max(0.4, min(1.0, float(item.gap)))
        reason = f"Current {item.current_proficiency:.2f}, required {item.required_proficiency:.2f}, gap {item.gap:.2f}"
        gap_row = SkillGap(
            analysis_id=analysis_id,
            skill_id=matched_skill.skill_id,
            priority_score=priority,
            gap_reason=reason,
        )

        existing = gap_rows_by_skill.get(matched_skill.skill_id)
        if not existing or gap_row.priority_score > existing.priority_score:
            gap_rows_by_skill[matched_skill.skill_id] = gap_row

    if gap_rows_by_skill:
        db.add_all(list(gap_rows_by_skill.values()))

    db.commit()


def _run_analysis(
    db: Session,
    cv_text: str,
    job_id: int | None,
    job_url: str | None,
    timeframe_weeks: int,
    max_skills_per_phase: int,
    cv_filename: str | None = None,
) -> CvIngestResponse:
    try:
        extracted = CvIngestService.extract_profile(db, cv_text)
        job = CvIngestService.find_job(db, job_id, job_url)
        job_context = CvIngestService.build_job_context(job)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to process CV: {exc}") from exc

    analysis_payload = GapAnalysisRequest(
        cv_skills=extracted.cv_skills,
        job_skills=job_context.job_skills,
        cv_years_experience=extracted.cv_years_experience,
        job_years_required=job_context.job_years_required,
        cv_level=extracted.cv_level,
        job_level=job_context.job_level,
        preferred_locations=extracted.preferred_locations,
        job_location=job_context.job_location,
        job_is_remote=job_context.job_is_remote,
        cv_certifications=extracted.cv_certifications,
        job_certifications=[],
        cv_title=_infer_cv_title(cv_text),
        job_title=job_context.title,
        ats_parse_score=_estimate_ats_score(cv_text),
    )

    match_result = JobMatchingService.calculate_job_match(analysis_payload)
    gap_result = AnalysisService.generate_gap_analysis(analysis_payload)

    roadmap_request = RoadmapGenerateRequest(
        goal_title=f"Match {job_context.title}",
        timeframe_weeks=timeframe_weeks,
        max_skills_per_phase=max_skills_per_phase,
        missing_skills=[
            MissingSkillInput(skill=item.skill, importance=item.importance, reason=item.reason)
            for item in gap_result.skillGap.missing
        ],
        weak_skills=[
            WeakSkillInput(
                skill=item.skill,
                current_proficiency=item.current_proficiency,
                required_proficiency=item.required_proficiency,
                gap=item.gap,
            )
            for item in gap_result.skillGap.weak
        ],
        resources=[],
    )
    roadmap_result = RoadmapService.generate(roadmap_request)

    _ensure_analysis_table()
    analysis_result = CvAnalysisResult(
        job_job_id=job_context.job_id,
        cv_filename=cv_filename,
        cv_text_excerpt=(cv_text[:1200] if cv_text else None),
        extracted_profile_json=extracted.model_dump(mode="json"),
        job_context_json=job_context.model_dump(mode="json"),
        job_match_json=match_result.model_dump(mode="json"),
        gap_analysis_json=gap_result.model_dump(mode="json"),
        roadmap_json=roadmap_result.model_dump(mode="json"),
    )
    db.add(analysis_result)
    db.commit()
    db.refresh(analysis_result)

    _persist_analysis_details(
        db=db,
        analysis_id=analysis_result.analysis_id,
        extracted=extracted,
        gap_result=gap_result,
    )

    return CvIngestResponse(
        analysis_result_id=analysis_result.analysis_id,
        extracted_profile=extracted,
        job_context=job_context,
        job_match=match_result,
        gap_analysis=gap_result,
        roadmap=roadmap_result,
    )


@router.post("/ingest", response_model=CvIngestResponse)
def ingest_cv(payload: CvIngestRequest, db: Session = Depends(get_db)) -> CvIngestResponse:
    return _run_analysis(
        db=db,
        cv_text=payload.cv_text,
        job_id=payload.job_id,
        job_url=payload.job_url,
        timeframe_weeks=payload.timeframe_weeks,
        max_skills_per_phase=payload.max_skills_per_phase,
        cv_filename=None,
    )


@router.post("/ingest-file", response_model=CvIngestResponse)
async def ingest_cv_file(
    cv_file: UploadFile = File(...),
    job_id: int | None = Form(default=None),
    job_url: str | None = Form(default=None),
    timeframe_weeks: int = Form(default=0),
    max_skills_per_phase: int = Form(default=4),
    db: Session = Depends(get_db),
) -> CvIngestResponse:
    if not job_id and not job_url:
        raise HTTPException(status_code=400, detail="Either job_id or job_url is required")

    if timeframe_weeks < 0:
        raise HTTPException(status_code=400, detail="timeframe_weeks must be >= 0 (0 means unlimited)")

    if max_skills_per_phase < 1 or max_skills_per_phase > 5:
        raise HTTPException(status_code=400, detail="max_skills_per_phase must be between 1 and 5")

    try:
        file_bytes = await cv_file.read()
        cv_text = CvIngestService.extract_text_from_file(cv_file.filename or "", cv_file.content_type, file_bytes)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to read CV file: {exc}") from exc

    return _run_analysis(
        db=db,
        cv_text=cv_text,
        job_id=job_id,
        job_url=job_url,
        timeframe_weeks=timeframe_weeks,
        max_skills_per_phase=max_skills_per_phase,
        cv_filename=cv_file.filename,
    )


@router.get("/analysis-results", response_model=AnalysisHistoryResponse)
def list_analysis_results(limit: int = 20, db: Session = Depends(get_db)) -> AnalysisHistoryResponse:
    _ensure_analysis_table()
    normalized_limit = max(1, min(limit, 100))
    rows = (
        db.query(CvAnalysisResult)
        .order_by(desc(CvAnalysisResult.created_at), desc(CvAnalysisResult.analysis_id))
        .limit(normalized_limit)
        .all()
    )

    items = [
        AnalysisHistoryItem(
            analysis_id=row.analysis_id,
            job_id=row.job_job_id,
            job_title=row.job.title if row.job else "Unknown job",
            cv_filename=row.cv_filename,
            created_at=row.created_at,
            job_match_score=(row.job_match_json or {}).get("score"),
            roadmap_total_weeks=(row.roadmap_json or {}).get("total_weeks"),
        )
        for row in rows
    ]
    return AnalysisHistoryResponse(total=len(items), items=items)


@router.get("/analysis-results/{analysis_id}", response_model=CvIngestResponse)
def get_analysis_result(analysis_id: int, db: Session = Depends(get_db)) -> CvIngestResponse:
    _ensure_analysis_table()
    row = db.query(CvAnalysisResult).filter(CvAnalysisResult.analysis_id == analysis_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Analysis result not found")

    if not row.job:
        raise HTTPException(status_code=404, detail="Related job not found")

    return CvIngestResponse(
        analysis_result_id=row.analysis_id,
        extracted_profile=row.extracted_profile_json,
        job_context=row.job_context_json,
        job_match=row.job_match_json,
        gap_analysis=row.gap_analysis_json,
        roadmap=row.roadmap_json,
    )