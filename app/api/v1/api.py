from fastapi import APIRouter
# Import biến 'router' từ file crawler.py trong thư mục endpoints
from app.api.v1.endpoints import crawler
from app.api.v1.endpoints import analyzer
from app.api.v1.endpoints import roadmap
from app.api.v1.endpoints import embeddings
from app.api.v1.endpoints import cv

api_router = APIRouter()

# Kết nối router của crawler vào api_router với đường dẫn /jobs
api_router.include_router(crawler.router, prefix="/jobs", tags=["Jobs"])
api_router.include_router(analyzer.router, prefix="/analyzer", tags=["Analyzer"])
api_router.include_router(roadmap.router, prefix="/roadmap", tags=["Roadmap"])
api_router.include_router(embeddings.router, prefix="/embeddings", tags=["Embeddings"])
api_router.include_router(cv.router, prefix="/cv", tags=["CV"])