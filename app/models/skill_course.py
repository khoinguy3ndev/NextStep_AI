from sqlalchemy import Column, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.db.base_class import Base


class SkillCourse(Base):
	__tablename__ = "skill_courses"

	id = Column(Integer, primary_key=True, index=True)
	skill_id = Column(Integer, ForeignKey("skills.skill_id"), nullable=False, index=True)
	platform = Column(String(50), nullable=True)
	title = Column(String(255), nullable=False)
	url = Column(Text, nullable=True)
	duration = Column(String(50), nullable=True)
	level = Column(String(20), nullable=True)

	skill = relationship("Skill", back_populates="skill_courses")