-- Add sentiment analysis columns to existing reviews table
ALTER TABLE reviews ADD COLUMN IF NOT EXISTS sentiment VARCHAR(20) CHECK (sentiment IN ('positive', 'negative', 'neutral'));
ALTER TABLE reviews ADD COLUMN IF NOT EXISTS sentiment_confidence DECIMAL(4,3);
ALTER TABLE reviews ADD COLUMN IF NOT EXISTS sentiment_scores JSONB;
ALTER TABLE reviews ADD COLUMN IF NOT EXISTS sentiment_error TEXT;
ALTER TABLE reviews ADD COLUMN IF NOT EXISTS review_hash VARCHAR(32) UNIQUE;
ALTER TABLE reviews ADD COLUMN IF NOT EXISTS review_id VARCHAR(255);
ALTER TABLE reviews ADD COLUMN IF NOT EXISTS review_date DATE;

-- Add sentiment summary columns to scraping_jobs table
ALTER TABLE scraping_jobs ADD COLUMN IF NOT EXISTS review_count INTEGER DEFAULT 0;
ALTER TABLE scraping_jobs ADD COLUMN IF NOT EXISTS positive_count INTEGER DEFAULT 0;
ALTER TABLE scraping_jobs ADD COLUMN IF NOT EXISTS negative_count INTEGER DEFAULT 0;
ALTER TABLE scraping_jobs ADD COLUMN IF NOT EXISTS neutral_count INTEGER DEFAULT 0;
ALTER TABLE scraping_jobs ADD COLUMN IF NOT EXISTS avg_rating DECIMAL(3,2);

-- Add keywords columns to reviews table
ALTER TABLE reviews ADD COLUMN IF NOT EXISTS extracted_keywords JSONB;
ALTER TABLE reviews ADD COLUMN IF NOT EXISTS keyword_categories JSONB;
ALTER TABLE reviews ADD COLUMN IF NOT EXISTS detected_language VARCHAR(2);
ALTER TABLE reviews ADD COLUMN IF NOT EXISTS keyword_count INTEGER DEFAULT 0;

-- Add keywords summary to scraping_jobs table
ALTER TABLE scraping_jobs ADD COLUMN IF NOT EXISTS top_categories JSONB;
ALTER TABLE scraping_jobs ADD COLUMN IF NOT EXISTS total_keywords INTEGER DEFAULT 0;

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_reviews_hash ON reviews(review_hash);
CREATE INDEX IF NOT EXISTS idx_reviews_language ON reviews(detected_language);
CREATE INDEX IF NOT EXISTS idx_reviews_keywords ON reviews USING GIN(extracted_keywords);
CREATE INDEX IF NOT EXISTS idx_reviews_categories ON reviews USING GIN(keyword_categories);