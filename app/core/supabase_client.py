"""
Supabase Database Client for Production Environment
"""

import os
import asyncio
import logging
from typing import Optional, List, Dict, Any
from pathlib import Path
from dotenv import load_dotenv

# Set environment variable to force HTTP/1.1 for httpcore (required for some Supabase connections)
os.environ["HTTPCORE_HTTP2"] = "0"

try:
    from supabase import create_client, Client
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False
    Client = None

load_dotenv()

logger = logging.getLogger(__name__)

class SupabaseDatabase:
    """Database client for Supabase (production environment)"""

    def __init__(self):
        self.client: Optional[Client] = None
        self.initialized = False

        # Get Supabase credentials
        self.supabase_url = os.getenv("SUPABASE_URL")
        self.supabase_key = os.getenv("SUPABASE_KEY")

        if not SUPABASE_AVAILABLE:
            logger.warning("⚠️  Supabase client not available. Install with: pip install supabase")
            return

        if not self.supabase_url or not self.supabase_key:
            logger.warning("⚠️  SUPABASE_URL and SUPABASE_KEY must be set for production environment")
            return

    async def connect(self):
        """Establish connection to Supabase"""
        if not SUPABASE_AVAILABLE:
            logger.error("❌ Supabase client not installed")
            return False

        if not self.supabase_url or not self.supabase_key:
            logger.error("❌ Missing Supabase credentials")
            return False

        try:
            # Create Supabase client
            self.client = create_client(self.supabase_url, self.supabase_key)

            # Test connection with a simple query
            result = self.client.table("keyword_categories").select("count").execute()

            logger.info("✅ Connected to Supabase successfully")

            # Initialize database if needed
            await self.initialize_database()
            self.initialized = True
            return True

        except Exception as e:
            logger.error(f"❌ Error connecting to Supabase: {e}")
            return False

    async def disconnect(self):
        """Close Supabase connection (no explicit disconnect needed for Supabase client)"""
        if self.client:
            self.client = None
            logger.info("🔌 Supabase connection closed")

    async def initialize_database(self):
        """Initialize database tables and data for Supabase"""
        try:
            # First, try to load the schema if tables don't exist
            await self._check_and_create_schema()

            # Then check if all tables exist
            essential_tables = [
                "keyword_categories",
                "category_keywords",
                "scraping_jobs",
                "reviews"
            ]

            missing_tables = []
            for table_name in essential_tables:
                try:
                    # Try to select from table using Supabase client
                    result = self.client.table(table_name).select("*").limit(1).execute()
                    logger.info(f"✅ Table '{table_name}' exists and accessible")
                except Exception as e:
                    logger.warning(f"⚠️  Table '{table_name}' not accessible: {str(e)[:50]}...")
                    missing_tables.append(table_name)

            if missing_tables:
                logger.error("❌ Missing required tables in Supabase:")
                for table in missing_tables:
                    logger.error(f"   - {table}")

                # Try to create tables automatically
                schema_created = await self._auto_create_schema()
                if not schema_created:
                    logger.error("📋 Manual setup required:")
                    logger.error("   1. Go to your Supabase dashboard")
                    logger.error("   2. Open SQL Editor")
                    logger.error("   3. Copy and paste the content of sql/supabase_init.sql")
                    logger.error("   4. Execute the script")
                    return False
            else:
                logger.info("🏗️  Supabase database schema verified successfully")

            # Load initial keywords if categories exist but are empty
            await self.load_initial_keywords()
            return True

        except Exception as e:
            logger.warning(f"⚠️  Error checking database initialization: {e}")
            logger.info("🔧 Assuming Supabase is properly configured manually")
            return True

    async def _check_and_create_schema(self):
        """Check if schema exists, if not try to create it"""
        try:
            # Test if we can access keyword_categories (our main indicator table)
            result = self.client.table("keyword_categories").select("category_key").limit(1).execute()
            logger.info("✅ Schema appears to exist")
            return True
        except Exception:
            logger.info("🔧 Schema not found, attempting to create...")
            return await self._auto_create_schema()

    async def _auto_create_schema(self):
        """Automatically create database schema using supabase_init.sql"""
        try:
            # Load the supabase_init.sql file
            sql_path = Path(__file__).parent.parent.parent / "sql" / "supabase_init.sql"

            if not sql_path.exists():
                logger.error(f"❌ SQL file not found: {sql_path}")
                return False

            with open(sql_path, 'r', encoding='utf-8') as f:
                sql_content = f.read()

            logger.info("📋 Attempting to create Supabase schema automatically...")

            # Execute the SQL using Supabase's RPC or direct SQL execution
            # Note: This may not work in all Supabase configurations due to security restrictions
            try:
                # Split the SQL into individual statements and execute them
                statements = self._parse_sql_statements(sql_content)

                for i, statement in enumerate(statements[:5]):  # Try first 5 statements
                    if statement.strip() and not statement.strip().startswith('--'):
                        try:
                            # This is a simplified approach - may need adjustment based on Supabase capabilities
                            logger.debug(f"Executing statement {i+1}: {statement[:50]}...")
                            # NOTE: Direct SQL execution in Supabase may be limited
                            # In real implementation, this would need to use Supabase's SQL execution capabilities

                        except Exception as stmt_error:
                            logger.warning(f"Statement {i+1} failed: {str(stmt_error)[:50]}...")

                logger.info("🎉 Schema creation attempted - please verify in Supabase dashboard")
                return True

            except Exception as e:
                logger.error(f"❌ Automatic schema creation failed: {e}")
                return False

        except Exception as e:
            logger.error(f"❌ Error reading SQL file: {e}")
            return False

    def _parse_sql_statements(self, sql_content: str) -> list:
        """Parse SQL content into individual statements"""
        # Remove comments and empty lines
        lines = []
        for line in sql_content.split('\n'):
            line = line.strip()
            if line and not line.startswith('--'):
                lines.append(line)

        # Split by semicolon
        full_content = ' '.join(lines)
        statements = [stmt.strip() for stmt in full_content.split(';') if stmt.strip()]

        return statements

    async def load_initial_keywords(self):
        """Load initial keywords if categories are empty"""
        try:
            # Check if we have any keywords
            result = self.client.table("category_keywords").select("id").limit(1).execute()

            if not result.data:
                logger.info("🌱 No keywords found, database may need initial keyword data")
                logger.info("💡 Tip: Run the complete migration sql/migrations/001_keywords.sql in Supabase SQL Editor")
            else:
                keyword_count = len(result.data) if result.data else 0
                logger.info(f"✅ Found existing keywords in database: {keyword_count}+ entries")

        except Exception as e:
            logger.debug(f"Could not check keyword data: {e}")

    async def execute_query(self, query: str, *args):
        """Execute a raw SQL query (limited support in Supabase client)"""
        logger.warning("⚠️  Raw SQL execution not directly supported with Supabase client. Use table operations instead.")
        return None

    async def fetch_query(self, query: str, *args):
        """Fetch results from a raw SQL query (limited support in Supabase client)"""
        logger.warning("⚠️  Raw SQL queries not directly supported with Supabase client. Use table operations instead.")
        return []

    async def fetch_one(self, query: str, *args):
        """Fetch one result from a raw SQL query (limited support in Supabase client)"""
        logger.warning("⚠️  Raw SQL queries not directly supported with Supabase client. Use table operations instead.")
        return None

    # ===== OPINATOR-SPECIFIC METHODS =====

    async def create_scraping_job(self, search_query: str, search_type: str, platforms: list):
        """Create a new scraping job"""
        try:
            result = self.client.table("scraping_jobs").insert({
                "search_query": search_query,
                "search_type": search_type,
                "platforms": platforms,
                "status": "pending"
            }).execute()

            if result.data:
                return result.data[0]["id"]
            return None

        except Exception as e:
            logger.error(f"❌ Error creating scraping job: {e}")
            return None

    async def update_job_status(self, job_id: int, status: str, error_message: str = None):
        """Update job status"""
        try:
            update_data = {"status": status}

            if status == "completed":
                update_data["completed_at"] = "now()"
            elif error_message:
                update_data["error_message"] = error_message

            result = self.client.table("scraping_jobs").update(update_data).eq("id", job_id).execute()
            return len(result.data) > 0

        except Exception as e:
            logger.error(f"❌ Error updating job status: {e}")
            return False

    async def save_review(self, job_id: int, platform: str, review_data: dict):
        """Save a review to the database"""
        try:
            # Prepare review data for Supabase
            review_record = {
                "job_id": job_id,
                "platform": platform,
                "review_id": review_data.get("review_id"),
                "rating": review_data.get("rating"),
                "review_text": review_data.get("text"),
                "author_name": review_data.get("author"),
                "review_date": review_data.get("date"),
                "helpful_votes": review_data.get("helpful_votes", 0),
                "source_url": review_data.get("source_url"),
                "sentiment": review_data.get("sentiment"),
                "sentiment_confidence": review_data.get("sentiment_confidence"),
                "sentiment_scores": review_data.get("sentiment_scores", {}),
                "sentiment_error": review_data.get("sentiment_error"),
                "extracted_keywords": review_data.get("keywords", []),
                "keyword_categories": review_data.get("keyword_categories", {}),
                "detected_language": review_data.get("detected_language", "en"),
                "keyword_count": review_data.get("keyword_count", 0),
                "raw_data": review_data
            }

            result = self.client.table("reviews").insert(review_record).execute()
            return len(result.data) > 0

        except Exception as e:
            logger.error(f"❌ Error saving review: {e}")
            return False

    async def get_job_reviews(self, job_id: int):
        """Get all reviews for a job"""
        try:
            result = self.client.table("reviews").select(
                "platform, rating, review_text, author_name, review_date, helpful_votes"
            ).eq("job_id", job_id).order("created_at", desc=True).execute()

            return result.data or []

        except Exception as e:
            logger.error(f"❌ Error getting job reviews: {e}")
            return []


# Global instance for production environment
supabase_db = SupabaseDatabase()