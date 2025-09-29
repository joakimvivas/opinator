"""Inngest functions for background processing"""

from .client import inngest
from ..services import job_service
from ..services.scraping_service import scraping_service
from ..services.sentiment_analyzer import sentiment_analyzer
from ..services.keyword_analyzer import keyword_analyzer
from ..services.summarizer import review_summarizer
import logging

logger = logging.getLogger(__name__)

@inngest.create_function(
    fn_id="process-scraping-job",
    trigger=inngest.trigger.event(event="scraping/job.created")
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
        await job_service.update_job_status(job_id, "scraping")
        logger.info(f"📡 Scraping reviews for job {job_id}")

        if search_type == "keyword":
            reviews = await scraping_service.scrape_by_keyword(search_query, platforms)
        else:
            reviews = await scraping_service.scrape_by_url(search_query, platforms)

        logger.info(f"📊 Scraped {len(reviews)} reviews for job {job_id}")
        return reviews

    raw_reviews = await step.run("scrape-reviews", scrape_step)

    # Step 2: Sentiment analysis (heavy AI processing)
    async def sentiment_step():
        await job_service.update_job_status(job_id, "analyzing_sentiment")
        logger.info(f"🤖 Analyzing sentiment for {len(raw_reviews)} reviews")

        analyzed = await sentiment_analyzer.analyze_reviews_batch(raw_reviews)
        logger.info(f"✅ Sentiment analysis completed for job {job_id}")
        return analyzed

    sentiment_reviews = await step.run("analyze-sentiment", sentiment_step)

    # Step 3: Keyword analysis
    async def keyword_step():
        await job_service.update_job_status(job_id, "analyzing_keywords")
        logger.info(f"🔍 Analyzing keywords for {len(sentiment_reviews)} reviews")

        analyzed = await keyword_analyzer.analyze_reviews_batch(sentiment_reviews)
        logger.info(f"✅ Keyword analysis completed for job {job_id}")
        return analyzed

    keyword_reviews = await step.run("analyze-keywords", keyword_step)

    # Step 4: Generate summaries (very heavy AI processing)
    async def summary_step():
        await job_service.update_job_status(job_id, "generating_summaries")
        logger.info(f"📝 Generating summaries for {len(keyword_reviews)} reviews")

        summarized = review_summarizer.summarize_reviews_batch(keyword_reviews)
        logger.info(f"✅ Summary generation completed for job {job_id}")
        return summarized

    final_reviews = await step.run("generate-summaries", summary_step)

    # Step 5: Save results and complete job
    async def save_step():
        await job_service.update_job_status(job_id, "saving_results")
        logger.info(f"💾 Saving results for job {job_id}")

        # Generate summaries
        sentiment_summary = sentiment_analyzer.get_sentiment_summary(final_reviews)
        keyword_summary = await keyword_analyzer.get_category_summary_for_job(final_reviews)

        # Save to database
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
@inngest.create_function(
    fn_id="hello-world",
    trigger=inngest.trigger.event(event="test/hello")
)
async def hello_world(ctx, step):
    """Simple test function to verify Inngest is working"""

    message = ctx.event.data.get("message", "Hello from Inngest!")

    async def hello_step():
        logger.info(f"👋 {message}")
        return {"message": message, "status": "success"}

    result = await step.run("say-hello", hello_step)
    return result