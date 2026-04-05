from __future__ import annotations

from datetime import date, timedelta
from typing import Dict, List

from app.schemas.roadmap import (
    RecommendedResource,
    RoadmapGenerateRequest,
    RoadmapGenerateResponse,
    RoadmapPhase,
    RoadmapSkillItem,
)


class RoadmapService:
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
            skill_items.append(
                RoadmapSkillItem(
                    skill_name=item.skill,
                    priority=RoadmapService._priority_from_importance(item.importance),
                    estimated_weeks=RoadmapService._weeks_from_importance(item.importance),
                    recommended_resources=skill_resource_map.get(key, []),
                )
            )

        for item in sorted(request.weak_skills, key=lambda value: value.gap, reverse=True):
            if any(existing.skill_name.lower() == item.skill.lower() for existing in skill_items):
                continue
            key = item.skill.strip().lower()
            skill_items.append(
                RoadmapSkillItem(
                    skill_name=item.skill,
                    priority=3,
                    estimated_weeks=RoadmapService._weeks_from_gap(item.gap),
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

