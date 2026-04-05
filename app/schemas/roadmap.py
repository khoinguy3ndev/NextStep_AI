from datetime import date
from typing import List, Optional

from pydantic import BaseModel, Field


class MissingSkillInput(BaseModel):
    skill: str
    importance: str
    reason: str


class WeakSkillInput(BaseModel):
    skill: str
    current_proficiency: float
    required_proficiency: float
    gap: float


class ResourceInput(BaseModel):
    skill_name: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    provider: Optional[str] = None
    url: Optional[str] = None
    duration_hours: Optional[int] = Field(default=None, ge=0)


class RoadmapGenerateRequest(BaseModel):
    goal_title: str = Field(..., min_length=3)
    timeframe_weeks: int = Field(0, ge=0)
    max_skills_per_phase: int = Field(4, ge=1, le=5)
    missing_skills: List[MissingSkillInput] = Field(default_factory=list)
    weak_skills: List[WeakSkillInput] = Field(default_factory=list)
    resources: List[ResourceInput] = Field(default_factory=list)


class RecommendedResource(BaseModel):
    title: str
    provider: Optional[str] = None
    url: Optional[str] = None
    duration_hours: Optional[int] = None


class RoadmapSkillItem(BaseModel):
    skill_name: str
    priority: int = Field(..., ge=1, le=5)
    estimated_weeks: int = Field(..., ge=1)
    recommended_resources: List[RecommendedResource] = Field(default_factory=list)


class RoadmapPhase(BaseModel):
    phase: int
    duration_weeks: int
    title: str
    skills: List[RoadmapSkillItem]


class RoadmapGenerateResponse(BaseModel):
    phases: List[RoadmapPhase]
    total_weeks: int
    estimated_completion: date
    difficulty_level: str
