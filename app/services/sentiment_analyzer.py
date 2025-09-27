"""
Sentiment Analysis Module using HuggingFace Transformers
"""

import asyncio
from transformers import pipeline, AutoTokenizer, AutoModelForSequenceClassification
import logging
from typing import List, Dict, Optional
import re
import warnings

# Suppress specific transformers warnings
warnings.filterwarnings("ignore", message=".*return_all_scores.*", category=UserWarning)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SentimentAnalyzer:
    def __init__(self, model_name: str = "finiteautomata/bertweet-base-sentiment-analysis"):
        """Initialize sentiment analyzer with specified model"""
        self.model_name = model_name
        self.analyzer = None
        self.initialized = False

    async def initialize(self):
        """Initialize the model asynchronously"""
        if self.initialized:
            return

        try:
            logger.info("🤖 Loading sentiment analysis model...")

            # Load model and tokenizer
            tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            model = AutoModelForSequenceClassification.from_pretrained(self.model_name)

            # Create pipeline
            self.analyzer = pipeline(
                "sentiment-analysis",
                model=model,
                tokenizer=tokenizer,
                return_all_scores=True
            )

            self.initialized = True
            logger.info("✅ Sentiment analysis model loaded successfully")

        except Exception as e:
            logger.error(f"❌ Failed to load sentiment model: {str(e)}")
            self.analyzer = None
            self.initialized = False

    def preprocess_text(self, text: str) -> str:
        """Clean and preprocess text for sentiment analysis"""
        if not text:
            return ""

        # Remove extra whitespace and normalize
        text = re.sub(r'\s+', ' ', text.strip())

        # Limit text length (BERT models have token limits)
        max_length = 512
        if len(text) > max_length:
            text = text[:max_length] + "..."

        return text

    async def analyze_sentiment(self, text: str) -> Dict[str, any]:
        """Analyze sentiment of a single text"""
        if not self.initialized or not self.analyzer:
            await self.initialize()

        if not self.analyzer:
            return {
                "sentiment": None,
                "confidence": 0.0,
                "scores": {},
                "error": "Model not available"
            }

        try:
            # Preprocess text
            clean_text = self.preprocess_text(text)

            if not clean_text:
                return {
                    "sentiment": None,  # No sentiment for empty text
                    "confidence": 0.0,
                    "scores": {},
                    "error": "Empty text"
                }

            # Run sentiment analysis
            results = self.analyzer(clean_text)

            # Process results
            scores = {}
            max_score = 0
            predicted_sentiment = "neutral"

            for result in results[0]:  # results[0] contains all scores
                label = result['label'].lower()
                score = result['score']
                scores[label] = score

                if score > max_score:
                    max_score = score
                    predicted_sentiment = label

            # Map model labels to our standard labels
            sentiment_mapping = {
                'pos': 'positive',
                'positive': 'positive',
                'neg': 'negative',
                'negative': 'negative',
                'neu': 'neutral',
                'neutral': 'neutral'
            }

            final_sentiment = sentiment_mapping.get(predicted_sentiment, 'neutral')

            return {
                "sentiment": final_sentiment,
                "confidence": max_score,
                "scores": scores,
                "text_length": len(clean_text),
                "analysis_method": "text"
            }

        except Exception as e:
            logger.error(f"❌ Sentiment analysis failed: {str(e)}")
            return {
                "sentiment": "neutral",
                "confidence": 0.0,
                "scores": {},
                "error": str(e)
            }

    def analyze_sentiment_from_rating(self, rating: float) -> Dict[str, any]:
        """Analyze sentiment based on star rating
        0-2 stars = negative, 3 stars = neutral, 4-5 stars = positive
        """
        if rating is None:
            return {
                "sentiment": None,
                "confidence": 0.0,
                "scores": {},
                "analysis_method": "none",
                "error": "No rating available"
            }

        try:
            rating = float(rating)

            # Determine sentiment based on rating
            if rating <= 2.0:
                sentiment = "negative"
                confidence = 0.8 + (2.0 - rating) * 0.1  # Higher confidence for lower ratings
            elif rating == 3.0:
                sentiment = "neutral"
                confidence = 0.7  # Moderate confidence for neutral ratings
            else:  # rating >= 4.0
                sentiment = "positive"
                confidence = 0.7 + (rating - 4.0) * 0.2  # Higher confidence for higher ratings

            # Create scores distribution based on rating
            scores = {
                "positive": confidence if sentiment == "positive" else (1.0 - confidence) / 2,
                "neutral": confidence if sentiment == "neutral" else (1.0 - confidence) / 2,
                "negative": confidence if sentiment == "negative" else (1.0 - confidence) / 2
            }

            return {
                "sentiment": sentiment,
                "confidence": confidence,
                "scores": scores,
                "analysis_method": "rating",
                "rating_value": rating
            }

        except Exception as e:
            logger.error(f"❌ Rating-based sentiment analysis failed: {str(e)}")
            return {
                "sentiment": "neutral",
                "confidence": 0.0,
                "scores": {},
                "analysis_method": "rating",
                "error": str(e)
            }

    async def analyze_reviews_batch(self, reviews: List[Dict]) -> List[Dict]:
        """Analyze sentiment for a batch of reviews"""
        if not reviews:
            return []

        analyzed_reviews = []

        for review in reviews:
            review_text = review.get('text', '').strip()
            rating = review.get('rating')

            enhanced_review = review.copy()

            # Priority: Text analysis first, then rating-based analysis
            if review_text:
                # Analyze sentiment from text (most accurate)
                sentiment_result = await self.analyze_sentiment(review_text)
                enhanced_review.update({
                    "sentiment": sentiment_result["sentiment"],
                    "sentiment_confidence": sentiment_result["confidence"],
                    "sentiment_scores": sentiment_result.get("scores", {}),
                    "sentiment_error": sentiment_result.get("error"),
                    "sentiment_method": "text"
                })
            elif rating is not None:
                # Fallback to rating-based sentiment analysis
                sentiment_result = self.analyze_sentiment_from_rating(rating)
                enhanced_review.update({
                    "sentiment": sentiment_result["sentiment"],
                    "sentiment_confidence": sentiment_result["confidence"],
                    "sentiment_scores": sentiment_result.get("scores", {}),
                    "sentiment_error": sentiment_result.get("error"),
                    "sentiment_method": "rating"
                })
            else:
                # No text or rating available
                enhanced_review.update({
                    "sentiment": None,
                    "sentiment_confidence": None,
                    "sentiment_scores": {},
                    "sentiment_error": "No text or rating to analyze",
                    "sentiment_method": "none"
                })

            analyzed_reviews.append(enhanced_review)

        return analyzed_reviews

    def get_sentiment_summary(self, reviews: List[Dict]) -> Dict:
        """Generate sentiment summary statistics"""
        if not reviews:
            return {
                "total_reviews": 0,
                "analyzed_reviews": 0,
                "positive": 0,
                "negative": 0,
                "neutral": 0,
                "no_text": 0,
                "average_confidence": 0.0,
                "sentiment_distribution": {}
            }

        # Only count reviews that have sentiment analysis (not None)
        analyzed_reviews = [r for r in reviews if r.get('sentiment') is not None]
        no_text_reviews = [r for r in reviews if r.get('sentiment') is None]

        sentiments = [r.get('sentiment') for r in analyzed_reviews]
        confidences = [r.get('sentiment_confidence', 0.0) for r in analyzed_reviews if r.get('sentiment_confidence')]

        positive_count = sentiments.count('positive')
        negative_count = sentiments.count('negative')
        neutral_count = sentiments.count('neutral')
        analyzed_total = len(analyzed_reviews)
        total_reviews = len(reviews)

        return {
            "total_reviews": total_reviews,
            "analyzed_reviews": analyzed_total,
            "positive": positive_count,
            "negative": negative_count,
            "neutral": neutral_count,
            "no_text": len(no_text_reviews),
            "positive_percentage": round((positive_count / analyzed_total) * 100, 1) if analyzed_total > 0 else 0,
            "negative_percentage": round((negative_count / analyzed_total) * 100, 1) if analyzed_total > 0 else 0,
            "neutral_percentage": round((neutral_count / analyzed_total) * 100, 1) if analyzed_total > 0 else 0,
            "average_confidence": round(sum(confidences) / len(confidences), 2) if confidences else 0.0,
            "sentiment_distribution": {
                "positive": positive_count,
                "negative": negative_count,
                "neutral": neutral_count
            }
        }

# Global instance
sentiment_analyzer = SentimentAnalyzer()