"""
Vector Database Service for Qdrant Integration
Handles embeddings generation and vector storage/retrieval
"""

import logging
from typing import List, Dict, Any, Optional
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue
import hashlib

logger = logging.getLogger(__name__)

class VectorService:
    """Service for managing embeddings and vector search with Qdrant"""

    def __init__(self, qdrant_url: str = "http://localhost:6333"):
        self.qdrant_url = qdrant_url
        self.client: Optional[QdrantClient] = None
        self.embedding_model_384: Optional[SentenceTransformer] = None
        self.embedding_model_512: Optional[SentenceTransformer] = None
        self.model_name_384 = "all-MiniLM-L6-v2"  # Fast, 384 dimensions
        self.model_name_512 = "sentence-transformers/clip-ViT-B-32-multilingual-v1"  # 512 dimensions

        # Collection names
        self.REVIEWS_COLLECTION = "reviews"
        self.KNOWLEDGE_COLLECTION = "hotel_knowledge"

    async def initialize(self):
        """Initialize Qdrant client and embedding model"""
        try:
            # Initialize Qdrant client
            self.client = QdrantClient(url=self.qdrant_url)
            logger.info(f"✅ Connected to Qdrant at {self.qdrant_url}")

            # Test connection
            collections = self.client.get_collections()
            logger.info(f"📊 Qdrant collections: {[c.name for c in collections.collections]}")

            # Initialize 384-dim embedding model (for reviews and knowledge)
            logger.info(f"🤖 Loading embedding model (384d): {self.model_name_384}")
            self.embedding_model_384 = SentenceTransformer(self.model_name_384)
            logger.info(f"✅ Embedding model loaded (384 dimensions)")

            # Create collections if they don't exist
            await self._create_collections()

            return True

        except Exception as e:
            logger.error(f"❌ Error initializing Vector Service: {e}")
            return False

    async def _create_collections(self):
        """Create Qdrant collections if they don't exist"""
        try:
            existing_collections = [c.name for c in self.client.get_collections().collections]

            # Create reviews collection
            if self.REVIEWS_COLLECTION not in existing_collections:
                self.client.create_collection(
                    collection_name=self.REVIEWS_COLLECTION,
                    vectors_config=VectorParams(
                        size=384,  # Using 384-dim model
                        distance=Distance.COSINE
                    )
                )
                logger.info(f"✅ Created collection: {self.REVIEWS_COLLECTION}")
            else:
                logger.info(f"📊 Collection already exists: {self.REVIEWS_COLLECTION}")

            # Create knowledge base collection
            if self.KNOWLEDGE_COLLECTION not in existing_collections:
                self.client.create_collection(
                    collection_name=self.KNOWLEDGE_COLLECTION,
                    vectors_config=VectorParams(
                        size=384,  # Using 384-dim model
                        distance=Distance.COSINE
                    )
                )
                logger.info(f"✅ Created collection: {self.KNOWLEDGE_COLLECTION}")
            else:
                logger.info(f"📊 Collection already exists: {self.KNOWLEDGE_COLLECTION}")

        except Exception as e:
            logger.error(f"❌ Error creating collections: {e}")

    def generate_embedding(self, text: str, dimension: int = 384) -> List[float]:
        """Generate embedding vector from text"""
        try:
            if dimension == 384:
                if not self.embedding_model_384:
                    raise Exception("384-dim embedding model not initialized")
                embedding = self.embedding_model_384.encode(text)
            elif dimension == 512:
                # Lazy load 512-dim model
                if not self.embedding_model_512:
                    logger.info(f"🤖 Loading 512-dim model: {self.model_name_512}")
                    self.embedding_model_512 = SentenceTransformer(self.model_name_512)
                    logger.info(f"✅ 512-dim model loaded")
                embedding = self.embedding_model_512.encode(text)
            else:
                raise Exception(f"Unsupported dimension: {dimension}")

            return embedding.tolist()

        except Exception as e:
            logger.error(f"❌ Error generating embedding: {e}")
            return []

    async def add_review(self, review_id: str, review_text: str, metadata: Dict[str, Any]) -> bool:
        """Add a review to the vector database"""
        try:
            # Generate embedding
            embedding = self.generate_embedding(review_text)

            if not embedding:
                return False

            # Create point ID from review_id
            point_id = abs(hash(review_id)) % (10 ** 10)  # Convert to positive integer

            # Upsert to Qdrant
            self.client.upsert(
                collection_name=self.REVIEWS_COLLECTION,
                points=[
                    PointStruct(
                        id=point_id,
                        vector=embedding,
                        payload={
                            "review_id": review_id,
                            "text": review_text,
                            "job_id": metadata.get("job_id"),
                            "platform": metadata.get("platform"),
                            "rating": metadata.get("rating"),
                            "sentiment": metadata.get("sentiment"),
                            "sentiment_confidence": metadata.get("sentiment_confidence"),
                            "author": metadata.get("author"),
                            "date": metadata.get("date"),
                            "helpful_votes": metadata.get("helpful_votes", 0),
                            "source_url": metadata.get("source_url"),
                            "keywords": metadata.get("keywords", []),
                            "keyword_categories": metadata.get("keyword_categories", {}),
                            "detected_language": metadata.get("detected_language", "en"),
                            "keyword_count": metadata.get("keyword_count", 0),
                            "summary": metadata.get("summary"),
                            "has_summary": metadata.get("has_summary", False)
                        }
                    )
                ]
            )

            logger.info(f"✅ Added review to vector DB: {review_id}")
            return True

        except Exception as e:
            logger.error(f"❌ Error adding review to vector DB: {e}")
            return False

    async def search_reviews(self, query: str, limit: int = 5, filter_params: Optional[Dict] = None, score_threshold: float = 0.5) -> List[Dict]:
        """Search for similar reviews using semantic search

        Args:
            query: Search query text
            limit: Maximum number of results
            filter_params: Optional filters (sentiment, platform, job_id)
            score_threshold: Minimum similarity score (0.0-1.0), default 0.5 (50%)
        """
        try:
            # Generate query embedding
            query_embedding = self.generate_embedding(query)

            if not query_embedding:
                return []

            # Build filter if provided
            query_filter = None
            if filter_params:
                conditions = []
                if "sentiment" in filter_params:
                    conditions.append(
                        FieldCondition(
                            key="sentiment",
                            match=MatchValue(value=filter_params["sentiment"])
                        )
                    )
                if "platform" in filter_params:
                    conditions.append(
                        FieldCondition(
                            key="platform",
                            match=MatchValue(value=filter_params["platform"])
                        )
                    )
                if "job_id" in filter_params:
                    conditions.append(
                        FieldCondition(
                            key="job_id",
                            match=MatchValue(value=filter_params["job_id"])
                        )
                    )
                if conditions:
                    query_filter = Filter(must=conditions)

            # Search Qdrant (search without threshold first to see all scores)
            search_results = self.client.search(
                collection_name=self.REVIEWS_COLLECTION,
                query_vector=query_embedding,
                query_filter=query_filter,
                limit=limit,
                with_payload=True
            )

            # Log all scores for debugging
            if search_results:
                scores = [hit.score for hit in search_results]
                logger.info(f"📊 Search scores (before threshold): {scores}")

            # Format results and apply threshold manually
            results = []
            for hit in search_results:
                # Apply threshold filter
                if hit.score < score_threshold:
                    continue

                results.append({
                    "score": hit.score,
                    "review_id": hit.payload.get("review_id"),
                    "text": hit.payload.get("text"),
                    "job_id": hit.payload.get("job_id"),
                    "platform": hit.payload.get("platform"),
                    "rating": hit.payload.get("rating"),
                    "sentiment": hit.payload.get("sentiment"),
                    "sentiment_confidence": hit.payload.get("sentiment_confidence"),
                    "author": hit.payload.get("author"),
                    "date": hit.payload.get("date"),
                    "helpful_votes": hit.payload.get("helpful_votes", 0),
                    "source_url": hit.payload.get("source_url"),
                    "keywords": hit.payload.get("keywords", []),
                    "keyword_categories": hit.payload.get("keyword_categories", {}),
                    "detected_language": hit.payload.get("detected_language", "en"),
                    "keyword_count": hit.payload.get("keyword_count", 0),
                    "summary": hit.payload.get("summary"),
                    "has_summary": hit.payload.get("has_summary", False)
                })

            logger.info(f"🔍 Found {len(results)} similar reviews for query: {query[:50]}...")
            return results

        except Exception as e:
            logger.error(f"❌ Error searching reviews: {e}")
            return []

    async def add_knowledge(self, doc_id: str, text: str, metadata: Dict[str, Any]) -> bool:
        """Add a knowledge base document (hotel policy, FAQ, etc.)"""
        try:
            # Generate embedding
            embedding = self.generate_embedding(text)

            if not embedding:
                return False

            # Create point ID
            point_id = abs(hash(doc_id)) % (10 ** 10)

            # Upsert to Qdrant
            self.client.upsert(
                collection_name=self.KNOWLEDGE_COLLECTION,
                points=[
                    PointStruct(
                        id=point_id,
                        vector=embedding,
                        payload={
                            "doc_id": doc_id,
                            "text": text,
                            "category": metadata.get("category", "general"),
                            "source": metadata.get("source", "manual"),
                            "title": metadata.get("title", "")
                        }
                    )
                ]
            )

            logger.info(f"✅ Added knowledge document: {doc_id}")
            return True

        except Exception as e:
            logger.error(f"❌ Error adding knowledge document: {e}")
            return False

    async def search_knowledge(self, query: str, limit: int = 3) -> List[Dict]:
        """Search knowledge base for relevant documents"""
        try:
            # Generate query embedding
            query_embedding = self.generate_embedding(query)

            if not query_embedding:
                return []

            # Search Qdrant
            search_results = self.client.search(
                collection_name=self.KNOWLEDGE_COLLECTION,
                query_vector=query_embedding,
                limit=limit,
                with_payload=True
            )

            # Format results
            results = []
            for hit in search_results:
                results.append({
                    "score": hit.score,
                    "doc_id": hit.payload.get("doc_id"),
                    "text": hit.payload.get("text"),
                    "category": hit.payload.get("category"),
                    "title": hit.payload.get("title")
                })

            logger.info(f"📚 Found {len(results)} knowledge documents for query: {query[:50]}...")
            return results

        except Exception as e:
            logger.error(f"❌ Error searching knowledge base: {e}")
            return []


    async def get_collection_stats(self) -> Dict[str, Any]:
        """Get statistics about collections using REST API to avoid Pydantic validation issues"""
        try:
            import httpx

            stats = {}

            # Reviews collection stats - use REST API directly
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(f"{self.qdrant_url}/collections/{self.REVIEWS_COLLECTION}")
                    if response.status_code == 200:
                        data = response.json()
                        count = data.get("result", {}).get("points_count", 0)
                        stats["reviews"] = {
                            "count": count,
                            "vectors_count": count
                        }
                        logger.info(f"📊 Reviews collection: {count} points")
                    else:
                        stats["reviews"] = {"count": 0, "vectors_count": 0}
            except Exception as e:
                logger.error(f"❌ Error getting reviews stats: {e}")
                stats["reviews"] = {"count": 0, "vectors_count": 0}

            # Knowledge collection stats - use REST API directly
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(f"{self.qdrant_url}/collections/{self.KNOWLEDGE_COLLECTION}")
                    if response.status_code == 200:
                        data = response.json()
                        count = data.get("result", {}).get("points_count", 0)
                        stats["knowledge"] = {
                            "count": count,
                            "vectors_count": count
                        }
                        logger.info(f"📊 Knowledge collection: {count} points")
                    else:
                        stats["knowledge"] = {"count": 0, "vectors_count": 0}
            except Exception as e:
                logger.error(f"❌ Error getting knowledge stats: {e}")
                stats["knowledge"] = {"count": 0, "vectors_count": 0}

            return stats

        except Exception as e:
            logger.error(f"❌ Error getting collection stats: {e}")
            return {"reviews": {"count": 0, "vectors_count": 0}, "knowledge": {"count": 0, "vectors_count": 0}}


# Global instance
vector_service = VectorService()