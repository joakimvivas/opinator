"""
Job Service - Database operations for scraping jobs
"""
import json
from typing import List, Dict, Optional
from ..core.database import db
import logging

logger = logging.getLogger(__name__)


class JobService:
    """Service for managing scraping jobs"""

    @staticmethod
    async def get_recent_jobs(limit: int = 10) -> List[Dict]:
        """Get recent scraping jobs with statistics"""
        try:
            # Use environment-specific implementation
            if hasattr(db, 'pool') and db.pool:
                # PostgreSQL local
                async with db.pool.acquire() as connection:
                    jobs = await connection.fetch(
                        """
                        SELECT *
                        FROM scraping_jobs
                        WHERE status = 'completed'
                        ORDER BY created_at DESC
                        LIMIT $1
                        """,
                        limit
                    )
            else:
                # Supabase production - use simplified query for now
                if db.active_db and hasattr(db.active_db, 'client'):
                    result = db.active_db.client.table("scraping_jobs").select(
                        "*, created_at, search_query, platforms, status, review_count, positive_count, negative_count, neutral_count, avg_rating"
                    ).eq("status", "completed").order("created_at", desc=True).limit(limit).execute()
                    jobs = result.data if result.data else []
                else:
                    jobs = []

            parsed_jobs = []
            for job in jobs:
                job_dict = dict(job)
                if job_dict.get('top_categories') and isinstance(job_dict['top_categories'], str):
                    try:
                        job_dict['top_categories'] = json.loads(job_dict['top_categories'])
                    except (json.JSONDecodeError, TypeError):
                        job_dict['top_categories'] = {}

                # Convert date strings to datetime objects for template compatibility (only for Supabase)
                if not (hasattr(db, 'pool') and db.pool):  # Supabase case
                    from datetime import datetime
                    for date_field in ['created_at', 'updated_at', 'completed_at']:
                        if job_dict.get(date_field) and isinstance(job_dict[date_field], str):
                            try:
                                # Parse ISO format datetime string
                                job_dict[date_field] = datetime.fromisoformat(job_dict[date_field].replace('Z', '+00:00'))
                            except (ValueError, TypeError):
                                job_dict[date_field] = None

                parsed_jobs.append(job_dict)

            return parsed_jobs

        except Exception as e:
            logger.error(f"❌ Error getting recent jobs: {str(e)}")
            return []

    @staticmethod
    async def get_dashboard_stats() -> Dict:
        """Get dashboard statistics"""
        try:
            # Use environment-specific implementation
            if hasattr(db, 'pool') and db.pool:
                # PostgreSQL local
                async with db.pool.acquire() as connection:
                    stats = await connection.fetchrow("""
                        SELECT
                            COUNT(DISTINCT j.id) as total_jobs,
                            COUNT(r.id) as total_reviews,
                            COUNT(CASE WHEN r.sentiment = 'positive' THEN 1 END) as positive_count,
                            COUNT(CASE WHEN r.sentiment = 'negative' THEN 1 END) as negative_count,
                            COUNT(CASE WHEN r.sentiment = 'neutral' THEN 1 END) as neutral_count,
                            COUNT(CASE WHEN r.has_summary = true THEN 1 END) as summaries_count
                        FROM scraping_jobs j
                        LEFT JOIN reviews r ON j.id = r.job_id
                        WHERE j.status = 'completed'
                    """)
            else:
                # Supabase production - simplified stats
                if db.active_db and hasattr(db.active_db, 'client'):
                    # Get basic stats from scraping_jobs table
                    jobs_result = db.active_db.client.table("scraping_jobs").select("id, review_count, positive_count, negative_count, neutral_count").eq("status", "completed").execute()
                    jobs_data = jobs_result.data if jobs_result.data else []

                    # Get summaries count from reviews table
                    summaries_result = db.active_db.client.table("reviews").select("id", count="exact").eq("has_summary", True).execute()
                    summaries_count = summaries_result.count if summaries_result.count is not None else 0

                    total_jobs = len(jobs_data)
                    total_reviews = sum(job.get('review_count', 0) for job in jobs_data)
                    positive_count = sum(job.get('positive_count', 0) for job in jobs_data)
                    negative_count = sum(job.get('negative_count', 0) for job in jobs_data)
                    neutral_count = sum(job.get('neutral_count', 0) for job in jobs_data)

                    stats = {
                        'total_jobs': total_jobs,
                        'total_reviews': total_reviews,
                        'positive_count': positive_count,
                        'negative_count': negative_count,
                        'neutral_count': neutral_count,
                        'summaries_count': summaries_count
                    }
                else:
                    stats = {'total_jobs': 0, 'total_reviews': 0, 'positive_count': 0, 'negative_count': 0, 'neutral_count': 0, 'summaries_count': 0}

            return {
                'total_jobs': stats['total_jobs'] or 0,
                'total_reviews': stats['total_reviews'] or 0,
                'total_summaries': stats['summaries_count'] or 0,
                'sentiment_distribution': {
                    'positive': stats['positive_count'] or 0,
                    'negative': stats['negative_count'] or 0,
                    'neutral': stats['neutral_count'] or 0
                }
            }
        except Exception as e:
            logger.error(f"❌ Error getting dashboard stats: {str(e)}")
            return {
                'total_jobs': 0,
                'total_reviews': 0,
                'total_summaries': 0,
                'sentiment_distribution': {
                    'positive': 0,
                    'negative': 0,
                    'neutral': 0
                }
            }

    @staticmethod
    async def get_job_details(job_id: int) -> Optional[Dict]:
        """Get detailed information about a specific job"""
        try:
            # Use environment-specific implementation
            if hasattr(db, 'pool') and db.pool:
                # PostgreSQL local
                async with db.pool.acquire() as connection:
                    job = await connection.fetchrow(
                        "SELECT * FROM scraping_jobs WHERE id = $1",
                        job_id
                    )
                    if not job:
                        return None

                    reviews = await connection.fetch(
                        "SELECT * FROM reviews WHERE job_id = $1 ORDER BY scraped_at",
                        job_id
                    )

                    # Process PostgreSQL data (dates are already datetime objects)
                    job_dict = dict(job)
                    parsed_reviews = []

                    for review in reviews:
                        try:
                            review_dict = dict(review)
                            # Parse JSON fields if they exist and are strings
                            for json_field in ['sentiment_scores', 'extracted_keywords', 'keyword_categories', 'raw_data']:
                                if review_dict.get(json_field) and isinstance(review_dict[json_field], str):
                                    try:
                                        review_dict[json_field] = json.loads(review_dict[json_field])
                                    except (json.JSONDecodeError, TypeError):
                                        review_dict[json_field] = {} if json_field in ['sentiment_scores', 'keyword_categories', 'raw_data'] else []

                            parsed_reviews.append(review_dict)

                        except Exception as e:
                            logger.error(f"❌ Error processing review: {str(e)}")
                            # Continue processing other reviews instead of failing completely
                            continue

                    return {
                        "job": job_dict,
                        "reviews": parsed_reviews
                    }

            else:
                # Supabase production
                if db.is_supabase():
                    client = db.get_supabase_client()

                    # Get job details
                    job_result = client.table("scraping_jobs").select("*").eq("id", job_id).execute()
                    if not job_result.data or len(job_result.data) == 0:
                        return None
                    job = job_result.data[0]

                    # Get reviews
                    reviews_result = client.table("reviews").select("*").eq("job_id", job_id).order("scraped_at").execute()
                    reviews = reviews_result.data if reviews_result.data else []

                    # Process Supabase data (convert date strings to datetime objects)
                    job_dict = dict(job)
                    from datetime import datetime

                    for date_field in ['created_at', 'updated_at', 'completed_at']:
                        if job_dict.get(date_field) and isinstance(job_dict[date_field], str):
                            try:
                                # Parse ISO format datetime string
                                job_dict[date_field] = datetime.fromisoformat(job_dict[date_field].replace('Z', '+00:00'))
                            except (ValueError, TypeError):
                                job_dict[date_field] = None

                    parsed_reviews = []
                    for review in reviews:
                        try:
                            review_dict = dict(review)
                            # Parse JSON fields if they exist and are strings
                            for json_field in ['sentiment_scores', 'extracted_keywords', 'keyword_categories', 'raw_data']:
                                if review_dict.get(json_field) and isinstance(review_dict[json_field], str):
                                    try:
                                        review_dict[json_field] = json.loads(review_dict[json_field])
                                    except (json.JSONDecodeError, TypeError):
                                        review_dict[json_field] = {} if json_field in ['sentiment_scores', 'keyword_categories', 'raw_data'] else []

                            # Convert dates for review objects (Supabase)
                            for date_field in ['scraped_at', 'review_date']:
                                if review_dict.get(date_field) and isinstance(review_dict[date_field], str):
                                    try:
                                        # Parse ISO format datetime string
                                        review_dict[date_field] = datetime.fromisoformat(review_dict[date_field].replace('Z', '+00:00'))
                                    except (ValueError, TypeError):
                                        review_dict[date_field] = None

                            parsed_reviews.append(review_dict)

                        except Exception as e:
                            logger.error(f"❌ Error processing review: {str(e)}")
                            # Continue processing other reviews instead of failing completely
                            continue

                    return {
                        "job": job_dict,
                        "reviews": parsed_reviews
                    }

                else:
                    return None

        except Exception as e:
            logger.error(f"❌ Error getting job {job_id} details: {str(e)}")
            import traceback
            traceback.print_exc()
            return None

    @staticmethod
    async def create_scraping_job(search_query: str, search_type: str, platforms: List[str]) -> int:
        """Create a new scraping job"""
        try:
            # Use environment-specific implementation
            if hasattr(db, 'pool') and db.pool:
                # PostgreSQL local
                async with db.pool.acquire() as connection:
                    job_id = await connection.fetchval(
                        """
                        INSERT INTO scraping_jobs (search_query, search_type, platforms, status, created_at, updated_at)
                        VALUES ($1, $2, $3, 'pending', NOW(), NOW())
                        RETURNING id
                        """,
                        search_query, search_type, platforms
                    )
                    logger.info(f"✅ Created scraping job {job_id}")
                    return job_id
            else:
                # Supabase production
                if db.is_supabase():
                    client = db.get_supabase_client()
                    result = client.table("scraping_jobs").insert({
                        "search_query": search_query,
                        "search_type": search_type,
                        "platforms": platforms,
                        "status": "pending",
                        "created_at": "now()",
                        "updated_at": "now()"
                    }).execute()

                    if result.data and len(result.data) > 0:
                        job_id = result.data[0]["id"]
                        logger.info(f"✅ Created scraping job {job_id}")
                        return job_id
                    else:
                        raise Exception("No job ID returned from Supabase")
                else:
                    raise Exception("No active database connection")

        except Exception as e:
            logger.error(f"❌ Error creating scraping job: {str(e)}")
            raise

    @staticmethod
    async def update_job_status(job_id: int, status: str, message: str = None):
        """Update job status"""
        try:
            # Use environment-specific implementation
            if hasattr(db, 'pool') and db.pool:
                # PostgreSQL local
                async with db.pool.acquire() as connection:
                    if message:
                        await connection.execute(
                            "UPDATE scraping_jobs SET status = $1, message = $2, updated_at = NOW() WHERE id = $3",
                            status, message, job_id
                        )
                    else:
                        await connection.execute(
                            "UPDATE scraping_jobs SET status = $1, updated_at = NOW() WHERE id = $2",
                            status, job_id
                        )
                    logger.info(f"✅ Updated job {job_id} status to {status}")
            else:
                # Supabase production
                if db.is_supabase():
                    client = db.get_supabase_client()
                    update_data = {
                        "status": status,
                        "updated_at": "now()"
                    }
                    if message:
                        update_data["message"] = message

                    client.table("scraping_jobs").update(update_data).eq("id", job_id).execute()
                    logger.info(f"✅ Updated job {job_id} status to {status}")

        except Exception as e:
            logger.error(f"❌ Error updating job status: {str(e)}")

    @staticmethod
    async def update_job_statistics(job_id: int, reviews: List[Dict]):
        """Update job statistics after processing reviews"""
        try:
            # Calculate statistics
            total_reviews = len(reviews)
            avg_rating = sum(r.get('rating', 0) for r in reviews) / total_reviews if total_reviews > 0 else 0

            sentiment_distribution = {'positive': 0, 'negative': 0, 'neutral': 0}
            category_counts = {}

            for review in reviews:
                sentiment = review.get('sentiment', 'neutral')
                if sentiment in sentiment_distribution:
                    sentiment_distribution[sentiment] += 1

                # Count keywords from categories
                categories = review.get('keyword_categories', {})
                if isinstance(categories, str):
                    try:
                        categories = json.loads(categories)
                    except (json.JSONDecodeError, TypeError):
                        categories = {}

                for category_key, category_data in categories.items():
                    if category_key not in category_counts:
                        category_counts[category_key] = {
                            'count': 0,
                            'name': category_data.get('category_name', category_key)
                        }
                    category_counts[category_key]['count'] += 1

            # Get top 5 categories
            top_categories = dict(sorted(category_counts.items(),
                                       key=lambda x: x[1]['count'],
                                       reverse=True)[:5])

            # Use environment-specific implementation
            if hasattr(db, 'pool') and db.pool:
                # PostgreSQL local
                async with db.pool.acquire() as connection:
                    await connection.execute(
                        """
                        UPDATE scraping_jobs
                        SET review_count = $1,
                            positive_count = $2,
                            negative_count = $3,
                            neutral_count = $4,
                            avg_rating = $5,
                            sentiment_distribution = $6,
                            top_categories = $7,
                            total_keywords = $8,
                            completed_at = NOW(),
                            updated_at = NOW()
                        WHERE id = $9
                        """,
                        total_reviews,
                        sentiment_distribution.get('positive', 0),
                        sentiment_distribution.get('negative', 0),
                        sentiment_distribution.get('neutral', 0),
                        round(avg_rating, 2),
                        json.dumps(sentiment_distribution),
                        json.dumps(top_categories),
                        sum(len(review.get('keywords', [])) for review in reviews),
                        job_id
                    )
            else:
                # Supabase production
                if db.is_supabase():
                    client = db.get_supabase_client()

                    # Calculate individual counts for Supabase schema
                    positive_count = sentiment_distribution.get('positive', 0)
                    negative_count = sentiment_distribution.get('negative', 0)
                    neutral_count = sentiment_distribution.get('neutral', 0)

                    # Count total keywords
                    total_keywords = sum(len(review.get('keywords', [])) for review in reviews)

                    client.table("scraping_jobs").update({
                        "review_count": total_reviews,
                        "positive_count": positive_count,
                        "negative_count": negative_count,
                        "neutral_count": neutral_count,
                        "avg_rating": round(avg_rating, 2),
                        "total_keywords": total_keywords,
                        "updated_at": "now()"
                    }).eq("id", job_id).execute()

            logger.info(f"✅ Updated job {job_id} statistics: {total_reviews} reviews")

        except Exception as e:
            logger.error(f"❌ Error updating job statistics: {str(e)}")
            import traceback
            traceback.print_exc()

    @staticmethod
    async def get_latest_job_status():
        """Get the status of the most recent job regardless of status"""
        try:
            # Use environment-specific implementation
            if hasattr(db, 'pool') and db.pool:
                # PostgreSQL local
                async with db.pool.acquire() as connection:
                    job = await connection.fetchrow(
                        """
                        SELECT id, status, created_at, completed_at
                        FROM scraping_jobs
                        ORDER BY created_at DESC
                        LIMIT 1
                        """
                    )
                    return dict(job) if job else None
            else:
                # Supabase production
                if db.is_supabase():
                    client = db.get_supabase_client()
                    result = client.table("scraping_jobs").select(
                        "id, status, created_at, completed_at"
                    ).order("created_at", desc=True).limit(1).execute()

                    if result.data and len(result.data) > 0:
                        job_data = result.data[0]
                        # Convert date strings to datetime objects for template compatibility
                        from datetime import datetime
                        for date_field in ['created_at', 'updated_at', 'completed_at']:
                            if job_data.get(date_field) and isinstance(job_data[date_field], str):
                                try:
                                    # Parse ISO format datetime string
                                    job_data[date_field] = datetime.fromisoformat(job_data[date_field].replace('Z', '+00:00'))
                                except (ValueError, TypeError):
                                    job_data[date_field] = None
                        return job_data
                    return None
                else:
                    return None

        except Exception as e:
            logger.error(f"❌ Error getting latest job status: {str(e)}")
            return None


# Global instance
job_service = JobService()