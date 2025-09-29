"""Inngest client configuration for Opinator"""

from inngest import Inngest
from ..core.config import settings

# Create Inngest client instance
# Dev mode: no keys needed, just app_id and is_production=False
inngest = Inngest(
    app_id="opinator",
    is_production=settings.DEBUG == False
)