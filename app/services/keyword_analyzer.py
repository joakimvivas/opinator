"""
Keyword Analysis Module using database-driven categorization
"""

import logging
from typing import List, Dict, Optional, Set
import re
import json

# Import database module
from ..core.database import db

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class KeywordAnalyzer:
    def __init__(self):
        """Initialize keyword analyzer with database-driven categories"""
        self.categories_cache = {}  # Cache for categories and keywords

    async def load_categories_from_db(self) -> Dict:
        """Load keyword categories and keywords from database"""
        try:
            # Use environment-specific implementation
            if hasattr(db, 'pool') and db.pool:
                # PostgreSQL local
                    async with db.pool.acquire() as connection:
                        # Load categories with their multilingual names
                        categories_query = """
                            SELECT category_key, category_en, category_es, category_fr,
                                   icon, color, description
                            FROM keyword_categories
                            WHERE active = TRUE
                            ORDER BY category_key
                        """
                        categories = await connection.fetch(categories_query)

                        # Load all keywords for active categories
                        keywords_query = """
                            SELECT ck.category_key, ck.keyword, ck.language, ck.weight
                            FROM category_keywords ck
                            JOIN keyword_categories kc ON ck.category_key = kc.category_key
                            WHERE ck.active = TRUE AND kc.active = TRUE
                            ORDER BY ck.category_key, ck.language, ck.weight DESC
                        """
                        keywords = await connection.fetch(keywords_query)
            else:
                # Supabase production
                if db.is_supabase():
                    client = db.get_supabase_client()

                    # Load categories
                    categories_result = client.table("keyword_categories").select(
                        "category_key, category_en, category_es, category_fr, icon, color, description"
                    ).eq("active", True).order("category_key").execute()
                    categories = categories_result.data if categories_result.data else []

                    # Load keywords with join simulation
                    keywords_result = client.table("category_keywords").select(
                        "category_key, keyword, language, weight"
                    ).eq("active", True).execute()
                    keywords = keywords_result.data if keywords_result.data else []
                else:
                    categories = []
                    keywords = []

            # Organize data structure
            categories_data = {}

            # First, create category structure
            for category in categories:
                categories_data[category['category_key']] = {
                    'names': {
                        'en': category['category_en'],
                        'es': category['category_es'],
                        'fr': category['category_fr']
                    },
                    'icon': category['icon'],
                    'color': category['color'],
                    'description': category['description'],
                    'keywords': {
                        'es': [],
                        'en': [],
                        'fr': []
                    }
                }

            # Then, populate keywords
            for keyword in keywords:
                category_key = keyword['category_key']
                if category_key in categories_data:
                    lang = keyword['language']
                    categories_data[category_key]['keywords'][lang].append({
                        'keyword': keyword['keyword'],
                        'weight': float(keyword['weight'])
                    })

            self.categories_cache = categories_data
            logger.info(f"✅ Loaded {len(categories_data)} categories from database")
            return categories_data

        except Exception as e:
            logger.error(f"❌ Error loading categories from database: {str(e)}")
            return {}


    def _extract_keywords_from_text(self, text: str) -> List[str]:
        """Extract keywords from text using basic NLP"""
        if not text:
            return []

        # Clean and normalize text
        text = text.lower()
        text = re.sub(r'[^\w\s]', ' ', text)
        words = text.split()

        # Remove common stop words (multilingual)
        stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by',
            'el', 'la', 'un', 'una', 'y', 'o', 'pero', 'en', 'de', 'con', 'por', 'para', 'es', 'son',
            'le', 'la', 'un', 'une', 'et', 'ou', 'mais', 'dans', 'sur', 'à', 'de', 'avec', 'par', 'pour',
            'was', 'were', 'is', 'are', 'have', 'has', 'had', 'will', 'would', 'could', 'should'
        }

        # Get meaningful words (length > 3, not stop words)
        keywords = [word for word in words
                   if len(word) > 3 and word not in stop_words and word.isalpha()]

        # Return unique keywords
        return list(dict.fromkeys(keywords))

    async def categorize_keywords(self, keywords: List[str], text: str = "", language: str = "auto") -> Dict[str, any]:
        """Categorize keywords using database-driven categories"""

        # Load categories if not cached
        if not self.categories_cache:
            await self.load_categories_from_db()

        if not self.categories_cache:
            return {}

        # Auto-detect language if needed
        if language == "auto":
            language = self._detect_language(text + " " + " ".join(keywords))

        # Default to English if detection fails
        if language not in ['es', 'en', 'fr']:
            language = 'en'

        # Prepare text for matching
        all_text = (text + " " + " ".join(keywords)).lower()
        categories_found = {}

        # Check each category
        for category_key, category_data in self.categories_cache.items():
            category_keywords = category_data['keywords'].get(language, [])
            found_keywords = []
            total_weight = 0

            # Check if any keywords from this category appear in the text
            for keyword_data in category_keywords:
                keyword = keyword_data['keyword'].lower()
                weight = keyword_data['weight']

                if keyword in all_text:
                    found_keywords.append({
                        'keyword': keyword,
                        'weight': weight
                    })
                    total_weight += weight

            # If we found keywords for this category, add it
            if found_keywords:
                categories_found[category_key] = {
                    'category_name': category_data['names'][language] or category_data['names']['en'],
                    'icon': category_data['icon'],
                    'color': category_data['color'],
                    'keywords_found': found_keywords,
                    'total_weight': round(total_weight, 2),
                    'confidence': min(total_weight / len(found_keywords), 1.0) if found_keywords else 0
                }

        # Sort by total weight (most relevant first)
        sorted_categories = dict(sorted(categories_found.items(),
                                      key=lambda x: x[1]['total_weight'],
                                      reverse=True))

        return sorted_categories

    def _extract_keywords_from_text(self, text: str, language: str = 'en') -> List[str]:
        """Extract keywords by direct matching against our database keywords"""
        if not self.categories_cache:
            return []

        found_keywords = []
        text_lower = text.lower()

        # Search through all categories and keywords
        for category_key, category_data in self.categories_cache.items():
            for keyword_data in category_data['keywords'].get(language, []):
                keyword = keyword_data['keyword'].lower()
                if keyword in text_lower:
                    found_keywords.append(keyword_data['keyword'])  # Keep original case

        return list(set(found_keywords))  # Remove duplicates

    def _detect_language(self, text: str) -> str:
        """Simple language detection based on common words"""
        if not text:
            return 'en'  # Default to English

        text_lower = text.lower()

        # Spanish indicators
        spanish_words = ['el', 'la', 'de', 'que', 'y', 'es', 'en', 'un', 'una', 'con', 'muy', 'bien', 'está', 'camping']
        spanish_count = sum(1 for word in spanish_words if word in text_lower)

        # French indicators
        french_words = ['le', 'de', 'et', 'à', 'un', 'une', 'dans', 'pour', 'avec', 'très', 'bien', 'est', 'camping']
        french_count = sum(1 for word in french_words if word in text_lower)

        # English indicators
        english_words = ['the', 'and', 'of', 'to', 'a', 'in', 'is', 'it', 'you', 'that', 'he', 'was', 'for', 'camping']
        english_count = sum(1 for word in english_words if word in text_lower)

        # Return language with highest count
        counts = {'es': spanish_count, 'fr': french_count, 'en': english_count}
        detected = max(counts, key=counts.get)

        # If no clear winner, default to English
        return detected if counts[detected] > 0 else 'en'

    async def analyze_review_keywords(self, review: Dict) -> Dict:
        """Complete keyword analysis for a review"""
        review_text = review.get('review_text', review.get('text', '')).strip()

        if not review_text:
            return {
                'keywords': [],
                'categories': {},
                'language': 'en',  # Default to English
                'keyword_count': 0,
                'categories_found': []
            }

        try:
            # Detect language first
            language = self._detect_language(review_text)

            # Extract keywords using direct database matching
            keywords = self._extract_keywords_from_text(review_text, language)

            # Categorize keywords using database
            categories = await self.categorize_keywords(keywords, review_text, language)

            return {
                'keywords': keywords,
                'categories': categories,
                'language': language,
                'keyword_count': len(keywords),
                'categories_found': list(categories.keys()),
                'top_category': list(categories.keys())[0] if categories else None
            }

        except Exception as e:
            logger.error(f"❌ Keyword analysis failed: {str(e)}")
            return {
                'keywords': [],
                'categories': {},
                'language': 'en',  # Default to English
                'keyword_count': 0,
                'categories_found': [],
                'error': str(e)
            }

    async def analyze_reviews_batch(self, reviews: List[Dict]) -> List[Dict]:
        """Analyze keywords for a batch of reviews"""
        analyzed_reviews = []

        # Load categories once for the batch
        if not self.categories_cache:
            await self.load_categories_from_db()

        for review in reviews:
            keyword_analysis = await self.analyze_review_keywords(review)

            enhanced_review = review.copy()
            enhanced_review.update({
                'keywords': keyword_analysis['keywords'],
                'keyword_categories': keyword_analysis['categories'],
                'detected_language': keyword_analysis['language'],
                'keyword_count': keyword_analysis['keyword_count']
            })

            analyzed_reviews.append(enhanced_review)

        return analyzed_reviews

    async def get_category_summary_for_job(self, job_reviews: List[Dict]) -> Dict:
        """Generate category summary for a job's reviews"""
        try:
            if not job_reviews:
                return {}

            category_counts = {}
            total_reviews_with_categories = 0

            for review in job_reviews:
                categories = review.get('keyword_categories', {})
                if categories:
                    total_reviews_with_categories += 1
                    for category_key, category_data in categories.items():
                        if category_key not in category_counts:
                            category_counts[category_key] = {
                                'count': 0,
                                'total_weight': 0,
                                'category_name': category_data.get('category_name', category_key),
                                'icon': category_data.get('icon', ''),
                                'color': category_data.get('color', '#6B7280')
                            }
                        category_counts[category_key]['count'] += 1
                        category_counts[category_key]['total_weight'] += category_data.get('total_weight', 0)

            # Calculate percentages and sort by frequency
            for category_key in category_counts:
                category_counts[category_key]['percentage'] = round(
                    (category_counts[category_key]['count'] / total_reviews_with_categories) * 100, 1
                ) if total_reviews_with_categories > 0 else 0

            # Sort by count (most frequent first)
            sorted_categories = dict(sorted(category_counts.items(),
                                          key=lambda x: x[1]['count'],
                                          reverse=True))

            return {
                'categories': sorted_categories,
                'total_reviews_analyzed': total_reviews_with_categories,
                'top_categories': list(sorted_categories.keys())[:5]
            }

        except Exception as e:
            logger.error(f"❌ Error generating category summary: {str(e)}")
            return {}

# Global instance
keyword_analyzer = KeywordAnalyzer()