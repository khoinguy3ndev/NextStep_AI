from sqlalchemy import ARRAY, Boolean, Column, Integer, String
from sqlalchemy.orm import relationship

from app.db.base_class import Base


class Skill(Base):
    __tablename__ = "skills"

    skill_id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, unique=True)
    category = Column(String(100), nullable=True)
    aliases = Column(ARRAY(String), nullable=False, default=list)
    is_active = Column(Boolean, nullable=False, default=True)

    job_skills = relationship("JobSkill", back_populates="skill")
