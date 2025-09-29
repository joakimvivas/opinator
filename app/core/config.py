"""
Configuration management for Opinator application
"""
import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    # Database - Using Supabase for all environments
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
    SUPABASE_KEY: str = os.getenv("SUPABASE_KEY", "")
    SUPABASE_DB_PASSWORD: str = os.getenv("SUPABASE_DB_PASSWORD", "")

    @property
    def DATABASE_URL(self) -> str:
        if self.SUPABASE_URL and self.SUPABASE_DB_PASSWORD:
            # Extract project ID from Supabase URL
            project_id = self.SUPABASE_URL.replace("https://", "").replace(".supabase.co", "")
            return f"postgresql://postgres:{self.SUPABASE_DB_PASSWORD}@db.{project_id}.supabase.co:5432/postgres"
        return "postgresql://opinator:opinator@localhost:5432/opinator"

    # Google Places API
    GOOGLE_PLACES_API_KEY: str = os.getenv("GOOGLE_PLACES_API_KEY", "")

    # HuggingFace
    HF_TOKEN: str = os.getenv("HF_TOKEN", "")

    # HeadlessX
    HEADLESSX_URL: str = os.getenv("HEADLESSX_URL", "http://localhost:8080")
    AUTH_TOKEN: str = os.getenv("AUTH_TOKEN", "")

    # Inngest
    INNGEST_EVENT_KEY: str = os.getenv("INNGEST_EVENT_KEY", "abcd1234567890abcdef1234567890ab")
    INNGEST_SIGNING_KEY: str = os.getenv("INNGEST_SIGNING_KEY", "fedcba0987654321fedcba0987654321")
    INNGEST_API_BASE_URL: str = os.getenv("INNGEST_API_BASE_URL", "http://localhost:8289")
    INNGEST_DEV_SERVER_URL: str = os.getenv("INNGEST_DEV_SERVER_URL", "http://localhost:8288")

    # Application
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8001"))

    # Templates
    TEMPLATE_DIR: str = "app/web/templates"

settings = Settings()