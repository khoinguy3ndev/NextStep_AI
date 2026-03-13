from sqlalchemy import Column, Float, ForeignKey, Integer, Text
from sqlalchemy.orm import relationship

from app.db.base_class import Base


class JobSkill(Base):
    __tablename__ = "job_skills"

    job_skill_id = Column(Integer, primary_key=True, index=True)
    job_job_id = Column(Integer, ForeignKey("jobs.job_id"), nullable=False)
    skill_skill_id = Column(Integer, ForeignKey("skills.skill_id"), nullable=False)
    importance = Column(Float, nullable=True)
    evidence_snippet = Column(Text, nullable=True)

    job = relationship("Job", back_populates="job_skills")
    skill = relationship("Skill", back_populates="job_skills")
