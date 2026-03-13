from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    # Thông tin App
    APP_NAME: str = "AI Job Matching Server"
    DEBUG: bool = True
    
    # Database
    DATABASE_URL: str
    
    # AI API (Gemini)
    GEMINI_API_KEY: str

    # Các biến bảo mật từ Backend bạn của bạn gửi
    JWT_ACCESS_SECRET: str
    JWT_ACCESS_EXPIRES_IN: str

    # Tự động đọc từ file .env
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

# Khởi tạo object dùng chung toàn server
settings = Settings()