from __future__ import annotations

from datetime import date, timedelta
import math
from typing import Dict, List

from app.schemas.roadmap import (
    RecommendedResource,
    RoadmapGenerateRequest,
    RoadmapGenerateResponse,
    RoadmapPhase,
    RoadmapSkillItem,
)


class RoadmapService:
    HOURS_PER_WEEK = 8

    @staticmethod
    def _priority_from_importance(importance: str) -> int:
        if importance == "high":
            return 5
        if importance == "medium":
            return 3
        return 2

    @staticmethod
    def _weeks_from_importance(importance: str) -> int:
        if importance == "high":
            return 4
        if importance == "medium":
            return 3
        return 2

    @staticmethod
    def _weeks_from_gap(gap_value: float) -> int:
        if gap_value >= 0.5:
            return 4
        if gap_value >= 0.3:
            return 3
        return 2

    @staticmethod
    def _estimated_hours_and_weeks(
        baseline_hours: int | None,
        importance: str,
        gap_value: float,
        transfer_bonus: float,
        fallback_weeks: int,
    ) -> tuple[int | None, int]:
        if baseline_hours is None or baseline_hours <= 0:
            return None, max(1, fallback_weeks)

        normalized_gap = max(0.0, min(gap_value, 1.0))
        normalized_transfer = max(0.0, min(transfer_bonus, 0.6))

        importance_factor = 1.15 if importance == "high" else 1.0 if importance == "medium" else 0.9
        gap_factor = 1.0 + (0.7 * normalized_gap)
        transfer_factor = 1.0 - normalized_transfer

        adjusted_hours = max(6, round(float(baseline_hours) * importance_factor * gap_factor * transfer_factor))
        weeks = max(1, math.ceil(adjusted_hours / RoadmapService.HOURS_PER_WEEK))
        return adjusted_hours, weeks

    @staticmethod
    def _resource_map(request: RoadmapGenerateRequest) -> Dict[str, List[RecommendedResource]]:
        skill_resource_map: Dict[str, List[RecommendedResource]] = {}
        for resource in request.resources:
            key = resource.skill_name.strip().lower()
            if key not in skill_resource_map:
                skill_resource_map[key] = []
            skill_resource_map[key].append(
                RecommendedResource(
                    title=resource.title,
                    provider=resource.provider,
                    url=resource.url,
                    duration_hours=resource.duration_hours,
                )
            )
        return skill_resource_map

    @staticmethod
    def generate(request: RoadmapGenerateRequest) -> RoadmapGenerateResponse:
        skill_resource_map = RoadmapService._resource_map(request)
        skill_items: List[RoadmapSkillItem] = []

        for item in request.missing_skills:
            key = item.skill.strip().lower()
            default_weeks = RoadmapService._weeks_from_importance(item.importance)
            adjusted_hours, estimated_weeks = RoadmapService._estimated_hours_and_weeks(
                baseline_hours=item.baseline_hours,
                importance=item.importance,
                gap_value=1.0,
                transfer_bonus=item.transfer_bonus,
                fallback_weeks=default_weeks,
            )
            skill_items.append(
                RoadmapSkillItem(
                    skill_name=item.skill,
                    priority=RoadmapService._priority_from_importance(item.importance),
                    estimated_weeks=estimated_weeks,
                    baseline_hours=item.baseline_hours,
                    transfer_bonus=item.transfer_bonus,
                    adjusted_hours=adjusted_hours,
                    recommended_resources=skill_resource_map.get(key, []),
                )
            )

        for item in sorted(request.weak_skills, key=lambda value: value.gap, reverse=True):
            if any(existing.skill_name.lower() == item.skill.lower() for existing in skill_items):
                continue
            key = item.skill.strip().lower()
            default_weeks = RoadmapService._weeks_from_gap(item.gap)
            adjusted_hours, estimated_weeks = RoadmapService._estimated_hours_and_weeks(
                baseline_hours=item.baseline_hours,
                importance="medium",
                gap_value=item.gap,
                transfer_bonus=item.transfer_bonus,
                fallback_weeks=default_weeks,
            )
            skill_items.append(
                RoadmapSkillItem(
                    skill_name=item.skill,
                    priority=3,
                    estimated_weeks=estimated_weeks,
                    baseline_hours=item.baseline_hours,
                    transfer_bonus=item.transfer_bonus,
                    adjusted_hours=adjusted_hours,
                    recommended_resources=skill_resource_map.get(key, []),
                )
            )

        skill_items.sort(key=lambda value: (value.priority, value.estimated_weeks), reverse=True)

        phases: List[RoadmapPhase] = []
        if not skill_items:
            completion = date.today() + timedelta(weeks=1)
            return RoadmapGenerateResponse(
                phases=[],
                total_weeks=0,
                estimated_completion=completion,
                difficulty_level="LOW",
            )

        total_weeks = 0
        phase_index = 1
        for start in range(0, len(skill_items), request.max_skills_per_phase):
            phase_skills = skill_items[start : start + request.max_skills_per_phase]
            phase_duration = sum(item.estimated_weeks for item in phase_skills)
            total_weeks += phase_duration
            phases.append(
                RoadmapPhase(
                    phase=phase_index,
                    duration_weeks=phase_duration,
                    title=f"Phase {phase_index}",
                    skills=phase_skills,
                )
            )
            phase_index += 1

        if request.timeframe_weeks > 0:
            total_weeks = min(total_weeks, request.timeframe_weeks)
        completion = date.today() + timedelta(weeks=total_weeks)

        if total_weeks <= 12:
            difficulty = "LOW"
        elif total_weeks <= 26:
            difficulty = "MEDIUM"
        else:
            difficulty = "HIGH"

        return RoadmapGenerateResponse(
            phases=phases,
            total_weeks=total_weeks,
            estimated_completion=completion,
            difficulty_level=difficulty,
        )

