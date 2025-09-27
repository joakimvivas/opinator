from fastapi import FastAPI
from fastapi.templating import Jinja2Templates
from contextlib import asynccontextmanager
from dotenv import load_dotenv
import logging

# Load environment variables
load_dotenv()

# Configure logging to reduce noise
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("transformers.tokenization_utils_base").setLevel(logging.ERROR)
logging.getLogger("transformers.pipelines.text_classification").setLevel(logging.ERROR)

# Import modules from new structure
from .core.database import init_database, close_database
from .services.sentiment_analyzer import sentiment_analyzer
from .api.routes import setup_routes

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("🚀 Starting Opinator...")
    await init_database()

    # Initialize sentiment analyzer
    print("🤖 Initializing sentiment analysis...")
    await sentiment_analyzer.initialize()

    yield
    # Shutdown
    print("🛑 Shutting down Opinator...")
    await close_database()

app = FastAPI(
    title="Opinator - Review Scraper",
    version="1.0.0",
    lifespan=lifespan
)

templates = Jinja2Templates(directory="app/web/templates")

# Setup all routes
setup_routes(app)

# All scraping logic and configuration has been moved to services/scraping_service.py
