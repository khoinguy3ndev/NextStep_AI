from typing import List, Optional

from pydantic import BaseModel, Field


class CvSkillInput(BaseModel):
    name: str = Field(..., min_length=1)
    proficiency: float = Field(0.7, ge=0, le=1)
    years_of_experience: float = Field(0, ge=0)


class JobSkillInput(BaseModel):
    name: str = Field(..., min_length=1)
    importance: float = Field(..., gt=0)
    required_proficiency: float = Field(0.8, ge=0, le=1)


class SalaryRange(BaseModel):
    min: float = Field(..., ge=0)
    max: float = Field(..., ge=0)


class JobMatchRequest(BaseModel):
    cv_skills: List[CvSkillInput] = Field(default_factory=list)
    job_skills: List[JobSkillInput] = Field(default_factory=list)

    cv_years_experience: float = Field(0, ge=0)
    job_years_required: float = Field(0, ge=0)

    cv_level: str = Field("junior")
    job_level: str = Field("junior")

    desired_salary: Optional[SalaryRange] = None
    job_salary: Optional[SalaryRange] = None

    preferred_locations: List[str] = Field(default_factory=list)
    job_location: Optional[str] = None
    job_is_remote: bool = False


class ScoreBreakdown(BaseModel):
    skillMatch: int
    experienceMatch: int
    levelMatch: int
    salaryMatch: int
    locationMatch: int


class JobMatchResponse(BaseModel):
    score: int
    scoreBreakdownJson: ScoreBreakdown
    missingSkills: List[str]
    matchedSkills: List[str]


class GapAnalysisRequest(JobMatchRequest):
    cv_certifications: List[str] = Field(default_factory=list)
    job_certifications: List[str] = Field(default_factory=list)


class MissingSkillGap(BaseModel):
    skill: str
    importance: str
    reason: str


class WeakSkillGap(BaseModel):
    skill: str
    current_proficiency: float
    required_proficiency: float
    gap: float


class ExperienceGap(BaseModel):
    required_years: float
    current_years: float
    gap_weeks: int


class LevelGap(BaseModel):
    cv_level: str
    job_level: str
    gap_levels: int


class CertificationGap(BaseModel):
    required: List[str]
    have: List[str]
    missing: List[str]


class SkillGap(BaseModel):
    missing: List[MissingSkillGap]
    weak: List[WeakSkillGap]


class GapAnalysisResponse(BaseModel):
    skillGap: SkillGap
    experienceGap: ExperienceGap
    levelGap: LevelGap
    certificationGap: CertificationGap
    recommendedSkills: List[str]
