"""
FastAPI routes for Opinator application
"""
from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from typing import List
import asyncio

from ..services.sentiment_analyzer import sentiment_analyzer
from ..services.keyword_analyzer import keyword_analyzer
from ..services.job_service import job_service
from ..services.admin_service import admin_service
from ..services.scraping_service import scraping_service
from ..services.vector_service import vector_service
from ..inngest.client import inngest
import inngest as inngest_module

# Templates configuration
templates = Jinja2Templates(directory="app/web/templates")

def setup_routes(app: FastAPI):
    """Setup all application routes"""

    @app.get("/", response_class=HTMLResponse)
    async def dashboard(request: Request, job_started: bool = False):
        """Main dashboard page"""
        try:
            recent_jobs = await job_service.get_recent_jobs(10)
            stats = await job_service.get_dashboard_stats()

            # Get latest job status if a job was just started
            latest_job = None
            if job_started:
                latest_job = await job_service.get_latest_job_status()

            return templates.TemplateResponse("dashboard.html", {
                "request": request,
                "jobs": recent_jobs,
                "stats": stats,
                "job_started": job_started,
                "latest_job": latest_job
            })
        except Exception as e:
            print(f"❌ Error loading dashboard: {str(e)}")
            return templates.TemplateResponse("dashboard.html", {
                "request": request,
                "recent_jobs": [],
                "stats": {
                    'total_jobs': 0,
                    'total_reviews': 0,
                    'sentiment_distribution': {'positive': 0, 'negative': 0, 'neutral': 0}
                },
                "error": "Error loading dashboard"
            })

    @app.get("/search", response_class=HTMLResponse)
    async def search_page(request: Request):
        """Search form page"""
        return templates.TemplateResponse("search.html", {"request": request})

    @app.get("/history", response_class=HTMLResponse)
    async def history_page(request: Request):
        """History page showing all completed jobs"""
        try:
            jobs = await job_service.get_recent_jobs(50)  # Get more jobs for history
            return templates.TemplateResponse("history.html", {
                "request": request,
                "jobs": jobs
            })
        except Exception as e:
            print(f"❌ Error loading history: {str(e)}")
            return templates.TemplateResponse("history.html", {
                "request": request,
                "jobs": [],
                "error": "Error loading job history"
            })

    @app.get("/job/{job_id}", response_class=HTMLResponse)
    async def job_details(request: Request, job_id: int):
        """Show detailed results for a specific job"""
        job_data = await job_service.get_job_details(job_id)
        if not job_data:
            return templates.TemplateResponse("error.html", {
                "request": request,
                "error": "Job not found"
            })
        return templates.TemplateResponse("job_detail.html", {
            "request": request,
            "job": job_data["job"],
            "reviews": job_data["reviews"]
        })

    @app.post("/scrape")
    async def start_scraping(
        request: Request,
        search_type: str = Form(...),
        search_query: str = Form(...),
        platforms: list = Form(default=[])
    ):
        """Start a new scraping job"""
        try:
            # Create new job
            job_id = await job_service.create_scraping_job(search_query, search_type, platforms)

            # Dispatch Inngest event for background processing
            event = inngest_module.Event(
                name="scraping/job.created",
                data={
                    "job_id": job_id,
                    "search_query": search_query,
                    "search_type": search_type,
                    "platforms": platforms
                }
            )
            await inngest.send(event)

            # Redirect to home with job started notification
            return RedirectResponse(url="/?job_started=true", status_code=302)

        except Exception as e:
            print(f"❌ Error starting scraping job: {str(e)}")
            return templates.TemplateResponse("search.html", {
                "request": request,
                "error": f"Error starting scraping: {str(e)}"
            })

    @app.get("/api/latest-job-status")
    async def get_latest_job_status():
        """Get the status of the most recent job"""
        try:
            latest_job = await job_service.get_latest_job_status()

            if latest_job:
                return JSONResponse({
                    "status": latest_job.get('status'),
                    "job_id": latest_job.get('id'),
                    "created_at": latest_job.get('created_at').isoformat() if latest_job.get('created_at') else None
                })
            else:
                return JSONResponse({
                    "status": "no_jobs",
                    "job_id": None
                })

        except Exception as e:
            return JSONResponse({
                "status": "error",
                "error": str(e)
            }, status_code=500)

    # === ADMIN API ROUTES ===

    @app.post("/admin/api/categories/{category_key}/keywords")
    async def add_keyword_to_category(
        category_key: str,
        keyword: str = Form(...),
        language: str = Form(...),
        weight: float = Form(default=1.0)
    ):
        """Add a keyword to a category"""
        try:
            success = await admin_service.add_keyword(category_key, keyword, language, weight)

            if success:
                return JSONResponse({"success": True, "message": f"Keyword '{keyword}' added successfully"})
            else:
                return JSONResponse({"success": False, "message": "Failed to add keyword"}, status_code=400)

        except Exception as e:
            return JSONResponse({"success": False, "message": str(e)}, status_code=500)

    @app.post("/admin/api/categories/{category_key}/keywords/bulk")
    async def add_keywords_bulk(
        category_key: str,
        keywords: str = Form(...),
        language: str = Form(...),
        weight: float = Form(default=1.0)
    ):
        """Bulk add keywords to a category"""
        try:
            # Parse keywords (split by comma or newline)
            keyword_list = [k.strip().lower() for k in keywords.replace('\n', ',').split(',') if k.strip()]

            success_count = 0
            failed_keywords = []

            for keyword in keyword_list:
                success = await admin_service.add_keyword(category_key, keyword, language, weight)
                if success:
                    success_count += 1
                else:
                    failed_keywords.append(keyword)

            if success_count > 0:
                message = f"Added {success_count} keywords successfully"
                if failed_keywords:
                    message += f". Failed to add: {', '.join(failed_keywords)}"

                return JSONResponse({"success": True, "message": message, "added": success_count})
            else:
                return JSONResponse({"success": False, "message": "No keywords were added"}, status_code=400)

        except Exception as e:
            return JSONResponse({"success": False, "message": str(e)}, status_code=500)

    @app.delete("/admin/api/categories/{category_key}/keywords/{keyword}/{language}")
    async def delete_keyword(category_key: str, keyword: str, language: str):
        """Delete a keyword from a category"""
        try:
            success = await admin_service.delete_keyword(category_key, keyword, language)

            if success:
                return JSONResponse({"success": True, "message": f"Keyword '{keyword}' deleted successfully"})
            else:
                return JSONResponse({"success": False, "message": "Failed to delete keyword"}, status_code=400)

        except Exception as e:
            return JSONResponse({"success": False, "message": str(e)}, status_code=500)

    @app.put("/admin/api/categories/{category_key}/keywords/{old_keyword}/{old_language}")
    async def update_keyword(
        category_key: str,
        old_keyword: str,
        old_language: str,
        keyword: str = Form(...),
        language: str = Form(...),
        weight: float = Form(...)
    ):
        """Update a keyword (keyword, language, or weight can be changed)"""
        try:
            # If keyword or language changed, we need to delete old and create new
            if keyword.lower().strip() != old_keyword or language != old_language:
                # Delete old keyword
                await admin_service.delete_keyword(category_key, old_keyword, old_language)
                # Add new keyword
                success = await admin_service.add_keyword(category_key, keyword, language, weight)
            else:
                # Only weight changed, use direct update
                success = await admin_service.update_keyword(category_key, keyword, language, weight)

            if success:
                return JSONResponse({"success": True, "message": f"Keyword updated successfully"})
            else:
                return JSONResponse({"success": False, "message": "Failed to update keyword"}, status_code=400)

        except Exception as e:
            return JSONResponse({"success": False, "message": str(e)}, status_code=500)

    # === ADMIN ROUTES ===

    @app.get("/admin", response_class=HTMLResponse)
    async def admin_dashboard(request: Request):
        """Admin dashboard for managing keywords and categories"""
        return templates.TemplateResponse("admin/dashboard.html", {
            "request": request
        })

    @app.get("/admin/categories", response_class=HTMLResponse)
    async def admin_categories(request: Request):
        """Manage keyword categories"""
        try:
            categories = await admin_service.get_all_categories()
            return templates.TemplateResponse("admin/categories.html", {
                "request": request,
                "categories": categories
            })
        except Exception as e:
            return templates.TemplateResponse("error.html", {
                "request": request,
                "error": f"Error loading categories: {str(e)}"
            })

    @app.get("/admin/keywords", response_class=HTMLResponse)
    async def admin_keywords(request: Request, category_key: str = None):
        """Manage keywords for categories"""
        try:
            categories = await admin_service.get_all_categories()
            keywords = []
            if category_key:
                keywords = await admin_service.get_keywords_by_category(category_key)

            return templates.TemplateResponse("admin/keywords.html", {
                "request": request,
                "categories": categories,
                "selected_category": category_key,
                "keywords": keywords
            })
        except Exception as e:
            return templates.TemplateResponse("error.html", {
                "request": request,
                "error": f"Error loading keywords: {str(e)}"
            })

    # === RAG / KNOWLEDGE BASE ROUTES ===

    @app.get("/chat", response_class=HTMLResponse)
    async def chat_page(request: Request):
        """Simple chat interface to query knowledge base"""
        try:
            stats = await vector_service.get_collection_stats()
            return templates.TemplateResponse("chat.html", {
                "request": request,
                "stats": stats
            })
        except Exception as e:
            return templates.TemplateResponse("chat.html", {
                "request": request,
                "stats": {},
                "error": f"Error loading chat: {str(e)}"
            })

    @app.post("/api/chat/query")
    async def chat_query(request: Request):
        """Query the knowledge base using semantic search"""
        try:
            body = await request.json()
            query = body.get("query", "").strip()
            threshold = body.get("threshold", 0.25)  # Default 25% similarity

            if not query:
                return JSONResponse({
                    "success": False,
                    "message": "Query cannot be empty"
                }, status_code=400)

            # Search in reviews with threshold
            reviews = await vector_service.search_reviews(
                query,
                limit=10,  # Increased limit since we're filtering by score
                score_threshold=threshold
            )

            # Search in knowledge base
            knowledge = await vector_service.search_knowledge(query, limit=3)

            return JSONResponse({
                "success": True,
                "query": query,
                "results": {
                    "reviews": reviews,
                    "knowledge": knowledge
                }
            })

        except Exception as e:
            return JSONResponse({
                "success": False,
                "message": str(e)
            }, status_code=500)

    @app.post("/api/knowledge/add")
    async def add_knowledge(
        title: str = Form(...),
        text: str = Form(...),
        category: str = Form(default="general")
    ):
        """Add a knowledge base document"""
        try:
            import hashlib
            doc_id = hashlib.md5(f"{title}{text}".encode()).hexdigest()[:16]

            success = await vector_service.add_knowledge(
                doc_id=doc_id,
                text=text,
                metadata={
                    "title": title,
                    "category": category,
                    "source": "manual"
                }
            )

            if success:
                return JSONResponse({
                    "success": True,
                    "message": "Knowledge document added successfully",
                    "doc_id": doc_id
                })
            else:
                return JSONResponse({
                    "success": False,
                    "message": "Failed to add knowledge document"
                }, status_code=400)

        except Exception as e:
            return JSONResponse({
                "success": False,
                "message": str(e)
            }, status_code=500)

    @app.get("/api/vector/stats")
    async def get_vector_stats():
        """Get vector database statistics"""
        try:
            stats = await vector_service.get_collection_stats()
            return JSONResponse({
                "success": True,
                "stats": stats
            })
        except Exception as e:
            return JSONResponse({
                "success": False,
                "message": str(e)
            }, status_code=500)

    @app.post("/api/vector/index-reviews")
    async def index_existing_reviews():
        """Index all existing reviews from Supabase to Qdrant"""
        try:
            from ..core.database import db

            # Get all reviews from database
            if db.is_supabase():
                client = db.get_supabase_client()
                result = client.table("reviews").select("*").execute()
                reviews = result.data
            else:
                # PostgreSQL query
                query = """
                    SELECT id, job_id, platform, review_id, review_text,
                           author_name, review_date, rating, sentiment,
                           extracted_keywords, summary
                    FROM reviews
                    ORDER BY created_at DESC
                """
                reviews = await db.fetch_query(query)

            if not reviews:
                return JSONResponse({
                    "success": False,
                    "message": "No reviews found in database"
                })

            # Index each review
            indexed_count = 0
            skipped_count = 0
            error_count = 0

            for review in reviews:
                try:
                    review_text = review.get("review_text", "")
                    review_id = review.get("review_id", "")

                    if not review_text or not review_id:
                        skipped_count += 1
                        continue

                    # Add to vector database
                    success = await vector_service.add_review(
                        review_id=review_id,
                        review_text=review_text,
                        metadata={
                            "job_id": review.get("job_id"),
                            "platform": review.get("platform"),
                            "rating": review.get("rating"),
                            "sentiment": review.get("sentiment"),
                            "sentiment_confidence": review.get("sentiment_confidence"),
                            "author": review.get("author_name"),
                            "date": str(review.get("review_date")) if review.get("review_date") else None,
                            "helpful_votes": review.get("helpful_votes", 0),
                            "source_url": review.get("source_url"),
                            "keywords": review.get("extracted_keywords", []),
                            "keyword_categories": review.get("keyword_categories", {}),
                            "detected_language": review.get("detected_language", "en"),
                            "keyword_count": review.get("keyword_count", 0),
                            "summary": review.get("summary"),
                            "has_summary": review.get("has_summary", False)
                        }
                    )

                    if success:
                        indexed_count += 1
                    else:
                        error_count += 1

                except Exception as e:
                    error_count += 1
                    continue

            return JSONResponse({
                "success": True,
                "message": f"Indexing completed",
                "stats": {
                    "total": len(reviews),
                    "indexed": indexed_count,
                    "skipped": skipped_count,
                    "errors": error_count
                }
            })

        except Exception as e:
            return JSONResponse({
                "success": False,
                "message": str(e)
            }, status_code=500)


