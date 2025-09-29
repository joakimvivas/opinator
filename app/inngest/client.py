"""Inngest client configuration for Opinator"""

from inngest import Inngest
from ..core.config import settings

# Create Inngest client instance
inngest = Inngest(
    app_id="opinator",
    event_key=settings.INNGEST_EVENT_KEY,
    signing_key=settings.INNGEST_SIGNING_KEY,
    is_production=settings.DEBUG == False,
    # Dev server configuration
    inngest_api_base_url=settings.INNGEST_API_BASE_URL
)