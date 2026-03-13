from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Set

from app.schemas.analyzer import JobMatchRequest, JobMatchResponse, ScoreBreakdown


LEVEL_MAP: Dict[str, int] = {
    "intern": 0,
    "junior": 1,
    "mid": 2,
    "senior": 3,
    "lead": 4,
}


@dataclass
class MatchComponents:
    skill: float
    experience: float
    level: float
    salary: float
    location: float


class JobMatchingService:
    @staticmethod
    def _normalize_importance(raw_importance: float) -> float:
        if raw_importance <= 1:
            return raw_importance
        return min(raw_importance / 5.0, 1.0)

    @staticmethod
    def _normalize_skill_name(value: str) -> str:
        return value.strip().lower()

    @staticmethod
    def calculate_skill_match(payload: JobMatchRequest) -> float:
        if not payload.job_skills:
            return 0.0

        cv_skill_map = {
            JobMatchingService._normalize_skill_name(skill.name): skill.proficiency
            for skill in payload.cv_skills
        }

        weighted_sum = 0.0
        weight_total = 0.0

        for required in payload.job_skills:
            skill_key = JobMatchingService._normalize_skill_name(required.name)
            weight = JobMatchingService._normalize_importance(required.importance)
            proficiency = cv_skill_map.get(skill_key, 0.0)

            weighted_sum += weight * proficiency
            weight_total += weight

        if weight_total == 0:
            return 0.0

        return weighted_sum / weight_total

    @staticmethod
    def calculate_experience_match(payload: JobMatchRequest) -> float:
        if payload.job_years_required <= 0:
            return 1.0
        return min(1.0, payload.cv_years_experience / payload.job_years_required)

    @staticmethod
    def calculate_level_match(payload: JobMatchRequest) -> float:
        cv_level = LEVEL_MAP.get(payload.cv_level.strip().lower(), 1)
        job_level = LEVEL_MAP.get(payload.job_level.strip().lower(), 1)
        level_diff = abs(cv_level - job_level)

        if level_diff == 0:
            return 1.0
        if level_diff == 1:
            return 0.6
        return 0.0

    @staticmethod
    def calculate_salary_match(payload: JobMatchRequest) -> float:
        if not payload.desired_salary or not payload.job_salary:
            return 0.0

        desired_min = payload.desired_salary.min
        desired_max = payload.desired_salary.max
        job_min = payload.job_salary.min
        job_max = payload.job_salary.max

        desired_range = desired_max - desired_min
        if desired_range <= 0:
            return 0.0

        overlap = max(0.0, min(desired_max, job_max) - max(desired_min, job_min))
        return overlap / desired_range

    @staticmethod
    def calculate_location_match(payload: JobMatchRequest) -> float:
        if payload.job_is_remote:
            return 0.8

        if not payload.job_location or not payload.preferred_locations:
            return 0.0

        job_location = payload.job_location.strip().lower()
        preferred_locations = {location.strip().lower() for location in payload.preferred_locations}

        return 1.0 if job_location in preferred_locations else 0.0

    @staticmethod
    def _matched_missing_skills(payload: JobMatchRequest) -> tuple[List[str], List[str]]:
        cv_skill_keys: Set[str] = {
            JobMatchingService._normalize_skill_name(skill.name)
            for skill in payload.cv_skills
        }
        job_skill_keys: Set[str] = {
            JobMatchingService._normalize_skill_name(skill.name)
            for skill in payload.job_skills
        }

        matched = sorted(job_skill_keys.intersection(cv_skill_keys))
        missing = sorted(job_skill_keys.difference(cv_skill_keys))
        return matched, missing

    @staticmethod
    def calculate_job_match(payload: JobMatchRequest) -> JobMatchResponse:
        components = MatchComponents(
            skill=JobMatchingService.calculate_skill_match(payload),
            experience=JobMatchingService.calculate_experience_match(payload),
            level=JobMatchingService.calculate_level_match(payload),
            salary=JobMatchingService.calculate_salary_match(payload),
            location=JobMatchingService.calculate_location_match(payload),
        )

        score = (
            0.55 * components.skill
            + 0.15 * components.experience
            + 0.10 * components.level
            + 0.10 * components.salary
            + 0.10 * components.location
        )

        matched_skills, missing_skills = JobMatchingService._matched_missing_skills(payload)

        return JobMatchResponse(
            score=round(score * 100),
            scoreBreakdownJson=ScoreBreakdown(
                skillMatch=round(components.skill * 100),
                experienceMatch=round(components.experience * 100),
                levelMatch=round(components.level * 100),
                salaryMatch=round(components.salary * 100),
                locationMatch=round(components.location * 100),
            ),
            missingSkills=missing_skills,
            matchedSkills=matched_skills,
        )
