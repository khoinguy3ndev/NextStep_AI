from dotenv import load_dotenv
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))

from fastapi import FastAPI
from app.api.v1.api import api_router
from app.core.config import settings

app = FastAPI(title=settings.APP_NAME)
app.include_router(api_router, prefix="/api/v1")
