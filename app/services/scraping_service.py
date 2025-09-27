"""
Scraping Service - Handles web scraping operations
"""
import asyncio
import httpx
import os
import json
import hashlib
import logging
from datetime import datetime
from typing import List, Dict, Optional
from bs4 import BeautifulSoup
import re

from ..core.database import db
from .sentiment_analyzer import sentiment_analyzer
from .keyword_analyzer import keyword_analyzer
from .summarizer import review_summarizer
from .job_service import job_service

logger = logging.getLogger(__name__)

# Configuration from environment variables
HEADLESSX_URL = os.getenv("HEADLESSX_URL", "http://localhost:3001")
MAX_REVIEWS_PER_PLATFORM = int(os.getenv("MAX_REVIEWS_PER_PLATFORM", "25"))
AUTH_TOKEN = os.getenv("AUTH_TOKEN", "")
GOOGLE_PLACES_API_KEY = os.getenv("GOOGLE_PLACES_API_KEY", "")


class ScrapingService:
    """Service for web scraping operations"""

    @staticmethod
    async def process_scraping_job(job_id: int, search_query: str, search_type: str, platforms: List[str]):
        """Process a scraping job in the background"""
        try:
            logger.info(f"🚀 Starting scraping job {job_id}: {search_query} on {platforms}")

            # Update job status to running
            await job_service.update_job_status(job_id, 'running')

            results = []

            # If URL mode, detect platform automatically
            if search_type == "url":
                detected_platform = ScrapingService.detect_platform_from_url(search_query)
                if detected_platform != "unknown":
                    platforms = [detected_platform]
                else:
                    results.append({
                        "platform": "unknown",
                        "data": {"error": "Could not detect platform from URL", "reviews": []},
                        "status": "error"
                    })
                    await job_service.update_job_status(job_id, 'failed', 'Could not detect platform from URL')
                    return

            # Ensure we have platforms to process
            if not platforms:
                error_msg = "No platforms selected"
                results.append({
                    "platform": "none",
                    "data": {"error": error_msg, "reviews": []},
                    "status": "error"
                })
                await job_service.update_job_status(job_id, 'failed', error_msg)
                return

            # Process each platform
            for platform in platforms:
                try:
                    logger.info(f"🔍 Processing platform: {platform}")

                    if search_type == "keyword":
                        # For keyword searches, use official APIs when available
                        if platform == "google" and GOOGLE_PLACES_API_KEY:
                            logger.info(f"🔗 Using Google Places API for keyword search: {search_query}")
                            review_data = await ScrapingService.get_google_reviews_via_api(search_query)
                        else:
                            # For other platforms in keyword mode, try to scrape search results
                            logger.info(f"🔍 Using HeadlessX for keyword search: {platform}")
                            review_data = await ScrapingService.scrape_by_keyword(search_query, platform)
                    else:
                        # For direct URLs, always use web scraping
                        logger.info(f"🌐 Using HeadlessX for direct URL scraping: {platform}")
                        review_data = await ScrapingService.scrape_url(search_query, platform)

                    results.append({
                        "platform": platform,
                        "data": review_data,
                        "status": "success"
                    })

                except Exception as e:
                    logger.error(f"❌ Error processing {platform}: {str(e)}")
                    results.append({
                        "platform": platform,
                        "data": None,
                        "status": "error",
                        "error": str(e)
                    })

            # Save results to database
            await ScrapingService.save_scraping_results(job_id, results)

            # Update job statistics
            all_reviews = []
            for result in results:
                if result.get('status') == 'success' and result.get('data'):
                    all_reviews.extend(result.get('data', {}).get('reviews', []))

            await job_service.update_job_statistics(job_id, all_reviews)

            # Mark job as completed
            await job_service.update_job_status(job_id, 'completed')

            logger.info(f"✅ Completed scraping job {job_id} with {len(all_reviews)} total reviews")

        except Exception as e:
            logger.error(f"❌ Error in scraping job {job_id}: {str(e)}")
            await job_service.update_job_status(job_id, 'failed', str(e))

    @staticmethod
    def detect_platform_from_url(url: str) -> str:
        """Detect platform from URL"""
        url_lower = url.lower()
        if "tripadvisor" in url_lower:
            return "tripadvisor"
        elif "google.com" in url_lower and "reviews" in url_lower:
            return "google"
        elif "booking.com" in url_lower:
            return "booking"
        else:
            return "unknown"

    @staticmethod
    async def scrape_url(url: str, platform: str):
        """Scrape a specific URL using HeadlessX"""
        try:
            async with httpx.AsyncClient(timeout=25.0) as client:
                headers = {"Content-Type": "application/json"}

                # HeadlessX API payload structure
                payload = {
                    "url": url,
                    "timeout": 12000,
                    "returnPartialOnTimeout": True
                }

                # Add token as query parameter
                api_url = f"{HEADLESSX_URL}/api/html"
                if AUTH_TOKEN:
                    api_url += f"?token={AUTH_TOKEN}"

                logger.info(f"🔄 Sending request to HeadlessX: {api_url}")

                response = await client.post(api_url, json=payload, headers=headers)

                if response.status_code != 200:
                    return {
                        "error": f"HeadlessX returned status {response.status_code}",
                        "details": response.text,
                        "reviews": []
                    }

                if not response.text.strip():
                    return {
                        "error": "Empty response from HeadlessX",
                        "reviews": []
                    }

                try:
                    data = response.json()
                    html_content = data.get('html', '')

                    # Parse HTML to extract reviews
                    reviews = ScrapingService.parse_reviews_from_html(html_content, platform)

                    return {
                        "title": data.get('title', ''),
                        "url": data.get('url', ''),
                        "reviews": reviews,
                        "total_reviews": len(reviews),
                        "success": True
                    }
                except Exception as json_error:
                    return {
                        "error": f"Invalid JSON response: {str(json_error)}",
                        "raw_response": response.text,
                        "reviews": []
                    }

        except httpx.TimeoutException:
            return {
                "error": "Request to HeadlessX timed out",
                "reviews": []
            }
        except Exception as e:
            return {
                "error": f"Request failed: {str(e)}",
                "reviews": []
            }

    @staticmethod
    async def scrape_by_keyword(keyword: str, platform: str):
        """Search and scrape by keyword"""
        search_url = ScrapingService.build_search_url(keyword, platform)
        return await ScrapingService.scrape_url(search_url, platform)

    @staticmethod
    def build_search_url(keyword: str, platform: str) -> str:
        """Build search URLs for each platform"""
        search_urls = {
            "tripadvisor": f"https://www.tripadvisor.es/Search?q={keyword}",
            "google": f"https://www.google.com/search?q={keyword}+reviews",
            "booking": f"https://www.booking.com/searchresults.html?ss={keyword}"
        }
        return search_urls.get(platform, "")

    @staticmethod
    def parse_reviews_from_html(html_content: str, platform: str) -> list:
        """Parse reviews from HTML content based on platform"""
        if not html_content:
            return []

        soup = BeautifulSoup(html_content, 'html.parser')
        reviews = []

        try:
            if platform == "tripadvisor":
                reviews = ScrapingService.parse_tripadvisor_reviews(soup)
            elif platform == "google":
                reviews = ScrapingService.parse_google_reviews(soup)
            elif platform == "booking":
                reviews = ScrapingService.parse_booking_reviews(soup)
        except Exception as e:
            logger.error(f"❌ Error parsing {platform} reviews: {str(e)}")
            return []

        logger.info(f"✅ Extracted {len(reviews)} reviews from {platform}")
        return reviews

    @staticmethod
    def parse_tripadvisor_reviews(soup: BeautifulSoup) -> list:
        """Parse TripAdvisor reviews"""
        reviews = []

        # Try multiple selectors for TripAdvisor reviews
        review_selectors = [
            "[data-test-target='review-card']",
            ".review-container",
            ".reviewSelector",
            "[data-reviewid]"
        ]

        review_elements = []
        for selector in review_selectors:
            review_elements = soup.select(selector)
            if review_elements:
                break

        for element in review_elements[:MAX_REVIEWS_PER_PLATFORM]:
            try:
                # Extract review data
                rating_elem = element.select_one("[data-test-target='review-rating'] span, .ui_bubble_rating, [class*='bubble_']")
                text_elem = element.select_one("[data-test-target='review-text'], .partial_entry, .review-text")
                author_elem = element.select_one("[data-test-target='review-username'], .username, .profile-name")
                date_elem = element.select_one("[data-test-target='review-date'], .ratingDate, .review-date")

                # Extract rating from class or aria-label
                rating = None
                if rating_elem:
                    class_attr = rating_elem.get('class', [])
                    for cls in class_attr:
                        if 'bubble_' in cls:
                            rating_match = re.search(r'bubble_(\d+)', cls)
                            if rating_match:
                                rating = int(rating_match.group(1)) / 10
                                break

                review = {
                    "rating": rating,
                    "text": text_elem.get_text(strip=True) if text_elem else "",
                    "author": author_elem.get_text(strip=True) if author_elem else "Anonymous user",
                    "date": date_elem.get_text(strip=True) if date_elem else "",
                    "platform": "tripadvisor"
                }

                if review["text"]:  # Only add reviews with text content
                    reviews.append(review)

            except Exception as e:
                logger.error(f"❌ Error parsing TripAdvisor review element: {str(e)}")
                continue

        return reviews

    @staticmethod
    def parse_google_reviews(soup: BeautifulSoup) -> list:
        """Parse Google Reviews"""
        reviews = []

        # Google reviews selectors
        review_selectors = [
            "[data-review-id]",
            ".review-item",
            "[jscontroller*='review']"
        ]

        review_elements = []
        for selector in review_selectors:
            review_elements = soup.select(selector)
            if review_elements:
                break

        for element in review_elements[:MAX_REVIEWS_PER_PLATFORM]:
            try:
                rating_elem = element.select_one("[aria-label*='stars'], [aria-label*='estrellas']")
                text_elem = element.select_one("[data-expandable-section], .review-text, [jsname]")
                author_elem = element.select_one(".review-author-name, [dir='ltr']")
                date_elem = element.select_one("[aria-label*='ago'], [aria-label*='hace']")

                # Extract rating from aria-label
                rating = None
                if rating_elem:
                    aria_label = rating_elem.get('aria-label', '')
                    rating_match = re.search(r'(\d+)', aria_label)
                    if rating_match:
                        rating = int(rating_match.group(1))

                review = {
                    "rating": rating,
                    "text": text_elem.get_text(strip=True) if text_elem else "",
                    "author": author_elem.get_text(strip=True) if author_elem else "Anonymous user",
                    "date": date_elem.get_text(strip=True) if date_elem else "",
                    "platform": "google"
                }

                if review["text"]:  # Only add reviews with text content
                    reviews.append(review)

            except Exception as e:
                logger.error(f"❌ Error parsing Google review element: {str(e)}")
                continue

        return reviews

    @staticmethod
    def parse_booking_reviews(soup: BeautifulSoup) -> list:
        """Parse Booking.com reviews"""
        reviews = []

        # Booking.com selectors
        review_selectors = [
            "[data-testid='review-card']",
            ".review_item",
            ".review-container"
        ]

        review_elements = []
        for selector in review_selectors:
            review_elements = soup.select(selector)
            if review_elements:
                break

        for element in review_elements[:MAX_REVIEWS_PER_PLATFORM]:
            try:
                rating_elem = element.select_one("[data-testid='review-score'], .review-score-badge")
                text_elem = element.select_one("[data-testid='review-positive-text'], .review-text")
                author_elem = element.select_one("[data-testid='review-username'], .reviewer-name")
                date_elem = element.select_one("[data-testid='review-date'], .review-date")

                # Extract rating
                rating = None
                if rating_elem:
                    rating_text = rating_elem.get_text(strip=True)
                    rating_match = re.search(r'(\d+\.?\d*)', rating_text)
                    if rating_match:
                        rating = float(rating_match.group(1))

                review = {
                    "rating": rating,
                    "text": text_elem.get_text(strip=True) if text_elem else "",
                    "author": author_elem.get_text(strip=True) if author_elem else "Anonymous user",
                    "date": date_elem.get_text(strip=True) if date_elem else "",
                    "platform": "booking"
                }

                if review["text"]:  # Only add reviews with text content
                    reviews.append(review)

            except Exception as e:
                logger.error(f"❌ Error parsing Booking review element: {str(e)}")
                continue

        return reviews

    @staticmethod
    async def get_google_reviews_via_api(query: str) -> dict:
        """Get Google reviews using Google Places API"""
        if not GOOGLE_PLACES_API_KEY:
            return {
                "error": "Google Places API key not configured",
                "reviews": []
            }

        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                # Step 1: Search for places using the query
                search_url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
                search_params = {
                    "query": query,
                    "key": GOOGLE_PLACES_API_KEY,
                    "fields": "place_id,name,rating,user_ratings_total"
                }

                logger.info(f"🔍 Searching Google Places for: {query}")
                search_response = await client.get(search_url, params=search_params)

                if search_response.status_code != 200:
                    return {
                        "error": f"Google Places API search failed: {search_response.status_code}",
                        "reviews": []
                    }

                search_data = search_response.json()

                if search_data.get("status") != "OK" or not search_data.get("results"):
                    return {
                        "error": f"No places found for query: {query}",
                        "reviews": []
                    }

                # Get the first result
                place = search_data["results"][0]
                place_id = place.get("place_id")
                place_name = place.get("name")

                logger.info(f"📍 Found place: {place_name} (ID: {place_id})")

                # Step 2: Get place details including reviews
                details_url = "https://maps.googleapis.com/maps/api/place/details/json"
                details_params = {
                    "place_id": place_id,
                    "fields": "name,rating,user_ratings_total,reviews,url",
                    "key": GOOGLE_PLACES_API_KEY,
                    "reviews_sort": "newest"
                }

                details_response = await client.get(details_url, params=details_params)

                if details_response.status_code != 200:
                    return {
                        "error": f"Google Places API details failed: {details_response.status_code}",
                        "reviews": []
                    }

                details_data = details_response.json()

                if details_data.get("status") != "OK":
                    return {
                        "error": f"Failed to get place details: {details_data.get('status')}",
                        "reviews": []
                    }

                place_details = details_data.get("result", {})
                raw_reviews = place_details.get("reviews", [])

                logger.info(f"📊 Google API returned {len(raw_reviews)} reviews (API limit: max 5)")

                # Step 3: Format reviews for our application
                formatted_reviews = []
                for i, review in enumerate(raw_reviews):
                    review_text = review.get("text", "").strip()
                    formatted_review = {
                        "rating": review.get("rating"),
                        "text": review_text,
                        "author": review.get("author_name", "Anonymous user"),
                        "date": ScrapingService.format_google_review_date(review.get("time")),
                        "platform": "google"
                    }

                    # Include reviews with text OR rating
                    if review_text or review.get("rating"):
                        formatted_reviews.append(formatted_review)

                # Analyze sentiment for all reviews
                logger.info(f"🤖 Analyzing sentiment for {len(formatted_reviews)} reviews...")
                analyzed_reviews = await sentiment_analyzer.analyze_reviews_batch(formatted_reviews)

                # Analyze keywords for all reviews
                logger.info(f"🔍 Analyzing keywords for {len(analyzed_reviews)} reviews...")
                keyword_analyzed_reviews = await keyword_analyzer.analyze_reviews_batch(analyzed_reviews)

                # Generate summaries for long reviews
                logger.info(f"📝 Generating summaries for {len(keyword_analyzed_reviews)} reviews...")
                final_reviews = review_summarizer.summarize_reviews_batch(keyword_analyzed_reviews)

                # Generate sentiment summary
                sentiment_summary = sentiment_analyzer.get_sentiment_summary(final_reviews)

                # Generate keyword summary
                keyword_summary = await keyword_analyzer.get_category_summary_for_job(final_reviews)

                return {
                    "title": place_details.get("name", "Google Place"),
                    "url": place_details.get("url", ""),
                    "reviews": final_reviews,
                    "total_reviews": len(final_reviews),
                    "overall_rating": place_details.get("rating"),
                    "total_ratings": place_details.get("user_ratings_total"),
                    "sentiment_summary": sentiment_summary,
                    "keyword_summary": keyword_summary,
                    "success": True,
                    "api_source": "Google Places API"
                }

        except Exception as e:
            logger.error(f"❌ Error getting Google reviews via API: {str(e)}")
            return {
                "error": f"Google Places API error: {str(e)}",
                "reviews": []
            }

    @staticmethod
    def format_google_review_date(timestamp):
        """Format Google review timestamp to readable date"""
        if not timestamp:
            return ""

        try:
            dt = datetime.fromtimestamp(timestamp)
            return dt.strftime("%B %Y")
        except:
            return ""

    @staticmethod
    def parse_review_date(date_str: str):
        """Parse review date string to date object"""
        if not date_str:
            return datetime.now().date()

        try:
            # Try to parse different date formats
            if 'September 2025' in str(date_str):
                return datetime(2025, 9, 1).date()
            elif 'months ago' in str(date_str) or 'month ago' in str(date_str):
                return datetime.now().date()
            elif 'years ago' in str(date_str) or 'year ago' in str(date_str):
                return datetime.now().date()
            else:
                return datetime.now().date()
        except:
            return datetime.now().date()

    @staticmethod
    async def save_scraping_results(job_id: int, results: list):
        """Save scraping results to database"""
        try:
            # Use environment-specific implementation
            if hasattr(db, 'pool') and db.pool:
                # PostgreSQL local
                async with db.pool.acquire() as connection:
                    for result in results:
                        platform = result.get('platform')
                        data = result.get('data', {})

                        if data and result.get('status') == 'success':
                            reviews = data.get('reviews', [])

                            # Analyze sentiment and keywords for all reviews if not already done
                            if reviews and not reviews[0].get('sentiment'):
                                logger.info(f"🤖 Analyzing sentiment for {len(reviews)} {platform} reviews...")
                                reviews = await sentiment_analyzer.analyze_reviews_batch(reviews)

                            if reviews and not reviews[0].get('keywords'):
                                logger.info(f"🔍 Analyzing keywords for {len(reviews)} {platform} reviews...")
                                reviews = await keyword_analyzer.analyze_reviews_batch(reviews)

                            # Generate summaries for long reviews if not already done
                            if reviews and not reviews[0].get('has_summary'):
                                logger.info(f"📝 Generating summaries for {len(reviews)} {platform} reviews...")
                                reviews = review_summarizer.summarize_reviews_batch(reviews)

                            for review in reviews:
                                # Generate unique review ID and hash
                                review_content = f"{review.get('author', '')}-{review.get('text', '')}-{review.get('rating', '')}-{platform}"
                                review_hash = hashlib.md5(review_content.encode()).hexdigest()

                                # Generate clean, unique review_id using platform prefix + hash
                                review_id = f"{platform}_{review_hash[:16]}"

                                # Parse review date
                                review_date = None
                                date_str = review.get('date')
                                if date_str:
                                    try:
                                        # Try to parse different date formats
                                        if 'September 2025' in str(date_str):
                                            review_date = datetime(2025, 9, 1).date()
                                        else:
                                            review_date = datetime.now().date()
                                    except:
                                        review_date = datetime.now().date()
                                else:
                                    review_date = datetime.now().date()

                                # Check if review already exists
                                existing = await connection.fetchrow(
                                    "SELECT id FROM reviews WHERE review_hash = $1",
                                    review_hash
                                )

                                if not existing:
                                    await connection.execute(
                                        """
                                        INSERT INTO reviews (
                                            job_id, platform, rating, review_text, author_name,
                                            sentiment, sentiment_confidence, sentiment_scores, sentiment_error,
                                            extracted_keywords, keyword_categories, detected_language, keyword_count,
                                            summary, has_summary,
                                            source_url, raw_data, review_hash, review_id, review_date
                                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20)
                                        """,
                                        job_id,
                                        platform,
                                        review.get('rating'),
                                        review.get('text'),
                                        review.get('author'),
                                    review.get('sentiment'),
                                    review.get('sentiment_confidence'),
                                    json.dumps(review.get('sentiment_scores', {})),
                                    review.get('sentiment_error'),
                                    json.dumps(review.get('keywords', [])),
                                    json.dumps(review.get('keyword_categories', {})),
                                    review.get('detected_language', 'en')[:2] if review.get('detected_language') else 'en',
                                    review.get('keyword_count', 0),
                                    review.get('summary'),
                                    review.get('has_summary', False),
                                    data.get('url'),
                                    json.dumps(review),
                                    review_hash,
                                    review_id,
                                    review_date
                                )
            else:
                # Supabase production
                if db.is_supabase():
                    client = db.get_supabase_client()

                    for result in results:
                        platform = result.get('platform')
                        data = result.get('data', {})

                        if data and result.get('status') == 'success':
                            reviews = data.get('reviews', [])

                            # Process reviews like in PostgreSQL
                            if reviews and not reviews[0].get('sentiment'):
                                logger.info(f"🤖 Analyzing sentiment for {len(reviews)} {platform} reviews...")
                                reviews = await sentiment_analyzer.analyze_reviews_batch(reviews)

                            if reviews and not reviews[0].get('keywords'):
                                logger.info(f"🔍 Analyzing keywords for {len(reviews)} {platform} reviews...")
                                reviews = await keyword_analyzer.analyze_reviews_batch(reviews)

                            # Generate summaries for long reviews
                            if reviews and not reviews[0].get('has_summary'):
                                logger.info(f"📝 Generating summaries for {len(reviews)} {platform} reviews...")
                                reviews = review_summarizer.summarize_reviews_batch(reviews)

                            # Save each review
                            for review in reviews:
                                if not review.get('text'):
                                    continue

                                review_hash = hashlib.md5(review.get('text', '').encode()).hexdigest()[:16]
                                review_id = f"{platform}_{review_hash}"
                                review_date = ScrapingService.parse_review_date(review.get('date', ''))

                                # Check if review exists (simplified for Supabase)
                                existing = client.table("reviews").select("id").eq("review_hash", review_hash).limit(1).execute()

                                if not existing.data:
                                    # Insert new review
                                    client.table("reviews").insert({
                                        "job_id": job_id,
                                        "platform": platform,
                                        "rating": review.get('rating'),
                                        "review_text": review.get('text'),
                                        "author_name": review.get('author'),
                                        "sentiment": review.get('sentiment'),
                                        "sentiment_confidence": review.get('sentiment_confidence'),
                                        "sentiment_scores": review.get('sentiment_scores', {}),
                                        "sentiment_error": review.get('sentiment_error'),
                                        "extracted_keywords": review.get('keywords', []),
                                        "keyword_categories": review.get('keyword_categories', {}),
                                        "detected_language": review.get('detected_language', 'en')[:2] if review.get('detected_language') else 'en',
                                        "keyword_count": review.get('keyword_count', 0),
                                        "summary": review.get('summary'),
                                        "has_summary": review.get('has_summary', False),
                                        "source_url": data.get('url'),
                                        "raw_data": review,
                                        "review_hash": review_hash,
                                        "review_id": review_id,
                                        "review_date": review_date.isoformat() if review_date else None
                                    }).execute()

            logger.info(f"💾 Saved results for job {job_id}")

        except Exception as e:
            logger.error(f"❌ Error saving results for job {job_id}: {str(e)}")


# Global instance
scraping_service = ScrapingService()