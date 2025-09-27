"""
Configuration management for Opinator application
"""
import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://opinator:opinator@localhost:5432/opinator")

    # Google Places API
    GOOGLE_PLACES_API_KEY: str = os.getenv("GOOGLE_PLACES_API_KEY", "")

    # HuggingFace
    HF_TOKEN: str = os.getenv("HF_TOKEN", "")

    # HeadlessX
    HEADLESSX_URL: str = os.getenv("HEADLESSX_URL", "http://localhost:8080")
    HEADLESSX_API_KEY: str = os.getenv("HEADLESSX_API_KEY", "")

    # Application
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8001"))

    # Templates
    TEMPLATE_DIR: str = "app/web/templates"

settings = Settings()