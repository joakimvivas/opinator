-- Migration: Add missing columns to scraping_jobs table
-- Date: 2024-12-20

-- Add updated_at column if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'scraping_jobs' AND column_name = 'updated_at'
    ) THEN
        ALTER TABLE scraping_jobs ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;

        -- Update existing records to have updated_at = created_at
        UPDATE scraping_jobs SET updated_at = created_at WHERE updated_at IS NULL;

        RAISE NOTICE 'Added updated_at column to scraping_jobs';
    END IF;
END $$;

-- Add message column if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'scraping_jobs' AND column_name = 'message'
    ) THEN
        ALTER TABLE scraping_jobs ADD COLUMN message TEXT;
        RAISE NOTICE 'Added message column to scraping_jobs';
    END IF;
END $$;

-- Add total_reviews column if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'scraping_jobs' AND column_name = 'total_reviews'
    ) THEN
        ALTER TABLE scraping_jobs ADD COLUMN total_reviews INTEGER DEFAULT 0;
        RAISE NOTICE 'Added total_reviews column to scraping_jobs';
    END IF;
END $$;

-- Add sentiment_distribution column if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'scraping_jobs' AND column_name = 'sentiment_distribution'
    ) THEN
        ALTER TABLE scraping_jobs ADD COLUMN sentiment_distribution JSONB;
        RAISE NOTICE 'Added sentiment_distribution column to scraping_jobs';
    END IF;
END $$;

DO $$
BEGIN
    RAISE NOTICE 'Migration 002_add_missing_columns.sql completed';
END $$;