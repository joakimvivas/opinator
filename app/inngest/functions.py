"""Inngest functions for background processing"""

import inngest
from .client import inngest as inngest_client
from ..services.job_service import job_service
from ..services.scraping_service import scraping_service
from ..services.sentiment_analyzer import sentiment_analyzer
from ..services.keyword_analyzer import keyword_analyzer
from ..services.summarizer import review_summarizer
import logging

logger = logging.getLogger(__name__)

# List of hotels to monitor (can be moved to database later)
MONITORED_HOTELS = [
    {"name": "W Barcelona", "platforms": ["google"]},
    {"name": "Hotel Arts Barcelona", "platforms": ["google"]},
    # Add more hotels as needed
]

@inngest_client.create_function(
    fn_id="process-scraping-job",
    trigger=inngest.TriggerEvent(event="scraping/job.created")
)
async def process_scraping_job(ctx, step):
    """Process a scraping job in the background with multiple steps"""

    # Get job data from the event
    job_id = ctx.event.data.get("job_id")
    search_query = ctx.event.data.get("search_query")
    platforms = ctx.event.data.get("platforms", [])
    search_type = ctx.event.data.get("search_type", "keyword")

    logger.info(f"🚀 Starting background processing for job {job_id}: {search_query}")

    # Step 1: Initial scraping
    async def scrape_step():
        await job_service.update_job_status(job_id, "running")
        logger.info(f"📡 Scraping reviews for job {job_id}")

        all_reviews = []
        if search_type == "keyword":
            # Iterate over each platform
            for platform in platforms:
                logger.info(f"🔍 Scraping {platform} for: {search_query}")

                # Use Google Places API if available for google platform
                if platform == "google":
                    from ..core.config import settings
                    if settings.GOOGLE_PLACES_API_KEY:
                        logger.info(f"🔗 Using Google Places API for: {search_query}")
                        result = await scraping_service.get_google_reviews_via_api(search_query)
                    else:
                        logger.warning("⚠️ Google Places API key not configured, skipping Google")
                        continue
                else:
                    result = await scraping_service.scrape_by_keyword(search_query, platform)

                if isinstance(result, dict) and 'reviews' in result:
                    all_reviews.extend(result['reviews'])
                elif isinstance(result, list):
                    all_reviews.extend(result)
        else:
            # For URL scraping, determine platform from URL
            for platform in platforms:
                result = await scraping_service.scrape_by_url(search_query, platform)
                if isinstance(result, dict) and 'reviews' in result:
                    all_reviews.extend(result['reviews'])
                elif isinstance(result, list):
                    all_reviews.extend(result)

        logger.info(f"📊 Scraped {len(all_reviews)} reviews for job {job_id}")
        return all_reviews

    raw_reviews = await step.run("scrape-reviews", scrape_step)

    # Step 2: Sentiment analysis (heavy AI processing)
    async def sentiment_step():
        logger.info(f"🤖 Analyzing sentiment for {len(raw_reviews)} reviews")

        analyzed = await sentiment_analyzer.analyze_reviews_batch(raw_reviews)
        logger.info(f"✅ Sentiment analysis completed for job {job_id}")
        return analyzed

    sentiment_reviews = await step.run("analyze-sentiment", sentiment_step)

    # Step 3: Keyword analysis
    async def keyword_step():
        logger.info(f"🔍 Analyzing keywords for {len(sentiment_reviews)} reviews")

        analyzed = await keyword_analyzer.analyze_reviews_batch(sentiment_reviews)
        logger.info(f"✅ Keyword analysis completed for job {job_id}")
        return analyzed

    keyword_reviews = await step.run("analyze-keywords", keyword_step)

    # Step 4: Generate summaries (very heavy AI processing)
    async def summary_step():
        logger.info(f"📝 Generating summaries for {len(keyword_reviews)} reviews")

        summarized = review_summarizer.summarize_reviews_batch(keyword_reviews)
        logger.info(f"✅ Summary generation completed for job {job_id}")
        return summarized

    final_reviews = await step.run("generate-summaries", summary_step)

    # Step 5: Save results and complete job
    async def save_step():
        logger.info(f"💾 Saving results for job {job_id}")

        # Generate review IDs and hashes before saving
        import hashlib
        for review in final_reviews:
            # Generate unique hash based on review text
            review_text = review.get('text', '')
            review_hash = hashlib.md5(review_text.encode()).hexdigest()[:16]
            platform = review.get('platform', platforms[0] if platforms else 'unknown')

            # Add hash and ID to review data
            review['review_hash'] = review_hash
            review['review_id'] = f"{platform}_{review_hash}"

        # Save individual reviews to database
        from ..core.database import db
        saved_count = 0
        skipped_count = 0

        for review in final_reviews:
            try:
                # Check if review already exists by hash
                from ..core.database import db as database
                if database.is_supabase():
                    client = database.get_supabase_client()
                    existing = client.table("reviews").select("id").eq("review_hash", review['review_hash']).limit(1).execute()

                    if existing.data and len(existing.data) > 0:
                        logger.info(f"⏭️ Skipping duplicate review: {review['review_id']}")
                        skipped_count += 1
                        continue

                # Save to database
                await db.save_review(
                    job_id=job_id,
                    platform=review.get('platform', platforms[0] if platforms else 'unknown'),
                    review_data=review
                )

                # Index to vector database
                from ..services.vector_service import vector_service
                try:
                    await vector_service.add_review(
                        review_id=review['review_id'],
                        review_text=review.get('text', ''),
                        metadata={
                            "job_id": job_id,
                            "platform": review.get('platform'),
                            "rating": review.get('rating'),
                            "sentiment": review.get('sentiment'),
                            "sentiment_confidence": review.get('sentiment_confidence'),
                            "author": review.get('author'),
                            "date": review.get('date'),
                            "helpful_votes": review.get('helpful_votes', 0),
                            "source_url": review.get('source_url'),
                            "keywords": review.get('keywords', []),
                            "keyword_categories": review.get('keyword_categories', {}),
                            "detected_language": review.get('detected_language', 'en'),
                            "keyword_count": review.get('keyword_count', 0),
                            "summary": review.get('summary'),
                            "has_summary": bool(review.get('summary'))
                        }
                    )
                    logger.info(f"🔮 Indexed review to vector DB: {review['review_id']}")
                except Exception as vector_error:
                    logger.warning(f"⚠️ Failed to index review to vector DB: {vector_error}")

                saved_count += 1
            except Exception as e:
                logger.error(f"❌ Error saving review: {str(e)}")
                continue

        logger.info(f"✅ Saved {saved_count} new reviews, skipped {skipped_count} duplicates")

        # Generate summaries
        sentiment_summary = sentiment_analyzer.get_sentiment_summary(final_reviews)
        keyword_summary = await keyword_analyzer.get_category_summary_for_job(final_reviews)

        # Update job statistics
        await job_service.update_job_statistics(job_id, final_reviews)

        # Mark as completed
        await job_service.update_job_status(job_id, "completed")
        logger.info(f"🎉 Job {job_id} completed successfully with {len(final_reviews)} reviews")

        return {
            "job_id": job_id,
            "review_count": len(final_reviews),
            "sentiment_summary": sentiment_summary,
            "keyword_summary": keyword_summary
        }

    result = await step.run("save-results", save_step)

    return result

# Simple test function
@inngest_client.create_function(
    fn_id="hello-world",
    trigger=inngest.TriggerEvent(event="test/hello")
)
async def hello_world(ctx, step):
    """Simple test function to verify Inngest is working"""

    message = ctx.event.data.get("message", "Hello from Inngest!")

    async def hello_step():
        logger.info(f"👋 {message}")
        return {"message": message, "status": "success"}

    result = await step.run("say-hello", hello_step)
    return result