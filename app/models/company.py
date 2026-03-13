from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship

from app.db.base_class import Base


class Company(Base):
    __tablename__ = "companies"

    company_id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, unique=True)
    website = Column(String(500), nullable=True)
    industry = Column(String(255), nullable=True)
    size = Column(String(100), nullable=True)
    location = Column(String(255), nullable=True)
    logo_url = Column(String(1000), nullable=True)

    jobs = relationship("Job", back_populates="company")
