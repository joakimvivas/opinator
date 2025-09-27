-- Migration 003: Add BART summarization fields to reviews table
-- This migration adds summary capabilities for long reviews

DO $$
BEGIN
    -- Add summary fields if they don't exist
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'reviews' AND column_name = 'summary') THEN
        ALTER TABLE reviews ADD COLUMN summary TEXT;
        RAISE NOTICE 'Added summary column to reviews table';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'reviews' AND column_name = 'has_summary') THEN
        ALTER TABLE reviews ADD COLUMN has_summary BOOLEAN DEFAULT FALSE;
        RAISE NOTICE 'Added has_summary column to reviews table';
    END IF;

    RAISE NOTICE 'Migration 003 completed: BART summarization fields added';
END $$;