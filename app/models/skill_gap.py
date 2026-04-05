from sqlalchemy import Column, Float, ForeignKey, Integer, Text
from sqlalchemy.orm import relationship

from app.db.base_class import Base


class SkillGap(Base):
	__tablename__ = "skill_gaps"

	id = Column(Integer, primary_key=True, index=True)
	analysis_id = Column(Integer, ForeignKey("cv_analysis_results.analysis_id"), nullable=False, index=True)
	skill_id = Column(Integer, ForeignKey("skills.skill_id"), nullable=False, index=True)
	priority_score = Column(Float, nullable=False, default=0.0)
	gap_reason = Column(Text, nullable=True)

	analysis = relationship("CvAnalysisResult", back_populates="skill_gaps")
	skill = relationship("Skill", back_populates="skill_gaps")