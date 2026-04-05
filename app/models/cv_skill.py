from sqlalchemy import Column, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.db.base_class import Base


class CvSkill(Base):
	__tablename__ = "cv_skills"

	id = Column(Integer, primary_key=True, index=True)
	analysis_id = Column(Integer, ForeignKey("cv_analysis_results.analysis_id"), nullable=False, index=True)
	skill_id = Column(Integer, ForeignKey("skills.skill_id"), nullable=False, index=True)
	confidence = Column(Float, nullable=False, default=0.5)
	source = Column(String(20), nullable=False, default="regex")

	analysis = relationship("CvAnalysisResult", back_populates="cv_skills")
	skill = relationship("Skill", back_populates="cv_skills")