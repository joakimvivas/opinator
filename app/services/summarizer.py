"""
Review Summarization Service using BART
"""
import logging
from typing import Optional
from transformers import pipeline

logger = logging.getLogger(__name__)

class ReviewSummarizer:
    def __init__(self):
        """Initialize BART summarizer"""
        self.summarizer = None
        self.min_review_length = 150  # Only summarize reviews longer than this
        self.max_length = 100
        self.min_length = 30

    def _load_model(self):
        """Load BART summarization model"""
        try:
            logger.info("🤖 Loading BART summarization model...")
            self.summarizer = pipeline("summarization", model="facebook/bart-large-cnn")
            logger.info("✅ BART summarization model loaded successfully")
        except Exception as e:
            logger.error(f"❌ Error loading BART model: {str(e)}")
            self.summarizer = None

    def should_summarize(self, text: str) -> bool:
        """Check if review is long enough to benefit from summarization"""
        return len(text.strip()) > self.min_review_length

    def summarize_review(self, review_text: str) -> Optional[str]:
        """Generate summary for a single review"""
        try:
            # Load model on first use
            if self.summarizer is None:
                self._load_model()

            if self.summarizer is None:
                return None

            # Only summarize if review is long enough
            if not self.should_summarize(review_text):
                return None

            # Clean and prepare text
            text = review_text.strip()
            if len(text) < self.min_length:
                return None

            # Generate summary
            result = self.summarizer(
                text,
                max_length=self.max_length,
                min_length=self.min_length,
                do_sample=False,
                truncation=True
            )

            if result and len(result) > 0:
                summary = result[0]['summary_text']
                logger.info(f"📝 Generated summary for review ({len(text)} → {len(summary)} chars)")
                return summary

        except Exception as e:
            logger.warning(f"❌ Summarization failed: {str(e)}")

        return None

    def summarize_reviews_batch(self, reviews: list) -> list:
        """Add summaries to a batch of reviews"""
        enhanced_reviews = []

        for review in reviews:
            review_copy = review.copy()
            review_text = review.get('review_text', review.get('text', ''))

            # Generate summary if review is long enough
            if self.should_summarize(review_text):
                summary = self.summarize_review(review_text)
                review_copy['summary'] = summary
                review_copy['has_summary'] = summary is not None
            else:
                review_copy['summary'] = None
                review_copy['has_summary'] = False

            enhanced_reviews.append(review_copy)

        return enhanced_reviews

# Global instance
review_summarizer = ReviewSummarizer()