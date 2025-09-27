-- Keyword Analysis Database Schema (Complete Migration)
-- This script drops and recreates keyword-related tables and data
-- UPDATED: Now includes all tested and working keywords across all categories
-- Version: Complete as of 2025-09-24
-- IMPORTANT: This migration should only run once, protected by existence checks

-- Only proceed if keyword_categories doesn't exist (first time migration)
DO $$
BEGIN
    -- Check if this migration has already been applied
    IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'keyword_categories') THEN
        -- Drop existing keyword tables (in correct order due to foreign keys)
        DROP TABLE IF EXISTS category_keywords CASCADE;
        DROP TABLE IF EXISTS keyword_categories CASCADE;

        -- Remove keyword-related columns from existing tables (only if they exist)
        IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'reviews' AND column_name = 'extracted_keywords') THEN
            ALTER TABLE reviews DROP COLUMN extracted_keywords;
        END IF;
        IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'reviews' AND column_name = 'keyword_categories') THEN
            ALTER TABLE reviews DROP COLUMN keyword_categories;
        END IF;
        IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'reviews' AND column_name = 'detected_language') THEN
            ALTER TABLE reviews DROP COLUMN detected_language;
        END IF;
        IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'reviews' AND column_name = 'keyword_count') THEN
            ALTER TABLE reviews DROP COLUMN keyword_count;
        END IF;

        IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'scraping_jobs' AND column_name = 'top_categories') THEN
            ALTER TABLE scraping_jobs DROP COLUMN top_categories;
        END IF;
        IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'scraping_jobs' AND column_name = 'total_keywords') THEN
            ALTER TABLE scraping_jobs DROP COLUMN total_keywords;
        END IF;
    ELSE
        -- Migration already applied, skip destructive operations
        RAISE NOTICE 'Keyword migration already applied, skipping destructive operations';
        RETURN;
    END IF;

    -- Continue with table creation if this is the first run
    IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'keyword_categories') THEN
        -- Categories table (main categories) - Using category_key as PK
        CREATE TABLE keyword_categories (
    category_key VARCHAR(50) PRIMARY KEY,     -- e.g., 'parking', 'pets', 'cleanliness'
    category_en VARCHAR(100) NOT NULL,        -- English display name
    category_es VARCHAR(100),                 -- Spanish display name
    category_fr VARCHAR(100),                 -- French display name
    description TEXT,                         -- Description of the category
    icon VARCHAR(50),                         -- FontAwesome icon class
    color VARCHAR(7) DEFAULT '#6B7280',      -- Hex color for visualization
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Keywords table (multilingual keywords for each category)
CREATE TABLE category_keywords (
    id SERIAL PRIMARY KEY,
    category_key VARCHAR(50) REFERENCES keyword_categories(category_key) ON DELETE CASCADE,
    keyword VARCHAR(100) NOT NULL,
    language VARCHAR(2) NOT NULL,             -- 'en', 'es', 'fr'
    weight DECIMAL(3,2) DEFAULT 1.0,         -- Weight/importance of this keyword (0.1 to 1.0)
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(category_key, keyword, language)
);

-- Add keywords columns to reviews table
ALTER TABLE reviews ADD COLUMN extracted_keywords JSONB;
ALTER TABLE reviews ADD COLUMN keyword_categories JSONB;
ALTER TABLE reviews ADD COLUMN detected_language VARCHAR(2);
ALTER TABLE reviews ADD COLUMN keyword_count INTEGER DEFAULT 0;

-- Add keywords summary to scraping_jobs table
ALTER TABLE scraping_jobs ADD COLUMN top_categories JSONB;
ALTER TABLE scraping_jobs ADD COLUMN total_keywords INTEGER DEFAULT 0;

-- Indexes for performance
CREATE INDEX idx_category_keywords_category ON category_keywords(category_key);
CREATE INDEX idx_category_keywords_language ON category_keywords(language);
CREATE INDEX idx_reviews_language ON reviews(detected_language);
CREATE INDEX idx_reviews_keywords ON reviews USING GIN(extracted_keywords);
CREATE INDEX idx_reviews_categories ON reviews USING GIN(keyword_categories);

-- Insert initial categories
INSERT INTO keyword_categories (category_key, category_en, category_es, category_fr, icon, color) VALUES
('parking', 'Parking', 'Estacionamiento', 'Parking', 'fas fa-car', '#3B82F6'),
('pets', 'Pets', 'Mascotas', 'Animaux', 'fas fa-dog', '#10B981'),
('reception_services', 'Reception & Services', 'Recepción y Servicios', 'Réception et Services', 'fas fa-concierge-bell', '#8B5CF6'),
('location', 'Location', 'Ubicación', 'Emplacement', 'fas fa-map-marker-alt', '#EF4444'),
('cleanliness', 'Cleanliness', 'Limpieza', 'Propreté', 'fas fa-broom', '#06B6D4'),
('facilities', 'Facilities', 'Instalaciones', 'Installations', 'fas fa-swimming-pool', '#F59E0B'),
('food_drink', 'Food & Drink', 'Comida y Bebida', 'Nourriture et Boisson', 'fas fa-utensils', '#EC4899'),
('internet', 'Internet/WiFi', 'Internet/WiFi', 'Internet/WiFi', 'fas fa-wifi', '#6366F1'),
('price', 'Price', 'Precio', 'Prix', 'fas fa-euro-sign', '#84CC16'),
('beach_nature', 'Beach & Nature', 'Playa y Naturaleza', 'Plage et Nature', 'fas fa-umbrella-beach', '#14B8A6'),
('security', 'Security', 'Seguridad', 'Sécurité', 'fas fa-shield-alt', '#F97316'),
('entertainment', 'Entertainment', 'Entretenimiento', 'Divertissement', 'fas fa-gamepad', '#A855F7');

-- Insert keywords (all languages in one statement)
INSERT INTO category_keywords (category_key, keyword, language, weight) VALUES
-- Spanish keywords
('parking', 'parking', 'es', 1.0),
('parking', 'estacionamiento', 'es', 1.0),
('parking', 'aparcamiento', 'es', 1.0),
('parking', 'coche', 'es', 0.8),
('pets', 'perro', 'es', 1.0),
('pets', 'mascota', 'es', 1.0),
('pets', 'animal', 'es', 0.9),
('reception_services', 'recepcion', 'es', 1.0),
('reception_services', 'servicio', 'es', 1.0),
('reception_services', 'personal', 'es', 0.8),
('location', 'ubicacion', 'es', 1.0),
('location', 'lugar', 'es', 0.8),
('location', 'cerca', 'es', 0.9),
('cleanliness', 'limpio', 'es', 1.0),
('cleanliness', 'sucio', 'es', 1.0),
('cleanliness', 'baño', 'es', 0.8),
('internet', 'internet', 'es', 1.0),
('internet', 'wifi', 'es', 1.0),
('price', 'precio', 'es', 1.0),
('price', 'barato', 'es', 0.9),
('price', 'caro', 'es', 0.9),
('beach_nature', 'playa', 'es', 1.0),
('beach_nature', 'mar', 'es', 0.9),

-- English keywords
('parking', 'parking', 'en', 1.0),
('parking', 'car', 'en', 0.8),
('pets', 'dog', 'en', 1.0),
('pets', 'pet', 'en', 1.0),
('pets', 'animal', 'en', 0.9),
('reception_services', 'reception', 'en', 1.0),
('reception_services', 'service', 'en', 1.0),
('reception_services', 'staff', 'en', 0.9),
('location', 'location', 'en', 1.0),
('location', 'near', 'en', 0.9),
('cleanliness', 'clean', 'en', 1.0),
('cleanliness', 'dirty', 'en', 1.0),
('cleanliness', 'bathroom', 'en', 0.8),
('internet', 'internet', 'en', 1.0),
('internet', 'wifi', 'en', 1.0),
('price', 'price', 'en', 1.0),
('price', 'cheap', 'en', 0.9),
('beach_nature', 'beach', 'en', 1.0),

-- French keywords
('parking', 'parking', 'fr', 1.0),
('pets', 'chien', 'fr', 1.0),
('cleanliness', 'propre', 'fr', 1.0),
('internet', 'wifi', 'fr', 1.0),
('beach_nature', 'plage', 'fr', 1.0),

-- ===== ADDITIONAL KEYWORDS ADDED =====

-- FACILITIES keywords (Spanish)
('facilities', 'bbq', 'es', 1.0),
('facilities', 'secadora', 'es', 1.0),
('facilities', 'lavadora', 'es', 1.0),
('facilities', 'sanitarios accesibles', 'es', 1.0),
('facilities', 'piscina interior', 'es', 1.0),

-- FACILITIES keywords (English)
('facilities', 'bbq', 'en', 1.0),
('facilities', 'dryer', 'en', 1.0),
('facilities', 'washing machine', 'en', 1.0),
('facilities', 'accessible toilets', 'en', 1.0),
('facilities', 'indoor pool', 'en', 1.0),

-- FOOD_DRINK keywords (Spanish)
('food_drink', 'bar', 'es', 1.0),
('food_drink', 'comida llevar', 'es', 1.0),
('food_drink', 'comida rápida', 'es', 1.0),

-- FOOD_DRINK keywords (English)
('food_drink', 'bar', 'en', 1.0),
('food_drink', 'takeaway', 'en', 1.0),
('food_drink', 'fast food', 'en', 1.0),

-- ENTERTAINMENT keywords (Spanish)
('entertainment', 'excursiones', 'es', 1.0),
('entertainment', 'sala juegos', 'es', 1.0),
('entertainment', 'sala televisión', 'es', 1.0),
('entertainment', 'espectáculos', 'es', 1.0),
('entertainment', 'tenis', 'es', 1.0),
('entertainment', 'padel', 'es', 1.0),

-- ENTERTAINMENT keywords (English)
('entertainment', 'excursions', 'en', 1.0),
('entertainment', 'game room', 'en', 1.0),
('entertainment', 'tv room', 'en', 1.0),
('entertainment', 'shows', 'en', 1.0),
('entertainment', 'tennis', 'en', 1.0),
('entertainment', 'padel', 'en', 1.0),

-- SECURITY keywords (Spanish)
('security', 'seguridad', 'es', 1.0),
('security', 'vigilancia', 'es', 1.0),
('security', 'caja fuerte', 'es', 1.0),
('security', 'seguro', 'es', 1.0),

-- SECURITY keywords (English)
('security', 'security', 'en', 1.0),
('security', 'surveillance', 'en', 1.0),
('security', 'safe', 'en', 1.0),
('security', 'secure', 'en', 1.0),

-- PETS additional keywords (Spanish)
('pets', 'perros permitidos', 'es', 1.0),

-- PETS additional keywords (English)
('pets', 'dogs allowed', 'en', 1.0),

-- PETS additional keywords (French)
('pets', 'chiens autorisés', 'fr', 1.0),

-- PARKING additional keywords (Spanish)
('parking', 'aparcamiento parcela', 'es', 1.0),

-- PARKING additional keywords (English)
('parking', 'on-site parking', 'en', 1.0),

-- PARKING additional keywords (French)
('parking', 'parking sur place', 'fr', 1.0),

-- RECEPTION_SERVICES additional keywords (Spanish)
('reception_services', 'periódicos', 'es', 1.0),
('reception_services', 'minimercado', 'es', 1.0),

-- RECEPTION_SERVICES additional keywords (English)
('reception_services', 'newspapers', 'en', 1.0),
('reception_services', 'mini market', 'en', 1.0);

-- Note: Basic internet keywords already exist above, no duplicates needed

-- ===== END ADDITIONAL KEYWORDS =====
-- Total categories: 12
-- Total keywords: ~65+ in multiple languages
-- This migration now includes all keywords that have been tested and working
-- Last updated: 2025-09-24

    END IF; -- End of table creation check
END $$; -- End of migration protection