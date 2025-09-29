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
from .inngest.client import inngest as inngest_client
from .inngest import functions  # Import to register functions

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

# Setup Inngest endpoint for background processing
import inngest.fast_api
from .inngest.functions import process_scraping_job, hello_world
from .core.config import settings

# Serve Inngest functions at /api/inngest
# serve_origin tells the Inngest dev server where to find THIS app for auto-discovery
# Since Inngest runs in Docker, use host.docker.internal or the local network IP
# In dev mode, manually add the app URL in the Inngest UI at:
# http://localhost:8288 -> Apps -> Add App -> http://host.docker.internal:8001/api/inngest
# If that doesn't work, try: http://192.168.1.164:8001/api/inngest
serve_origin = f"http://host.docker.internal:{settings.PORT}" if settings.DEBUG else None

inngest.fast_api.serve(
    app,
    inngest_client,
    [process_scraping_job, hello_world],
    serve_origin=serve_origin,
    serve_path="/api/inngest"
)

# All scraping logic and configuration has been moved to services/scraping_service.py
