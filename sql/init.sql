-- Inicialización de base de datos para Opinator
-- Este script se ejecuta automáticamente al crear el container de PostgreSQL

-- Crear tabla para almacenar trabajos de scraping
CREATE TABLE IF NOT EXISTS scraping_jobs (
    id SERIAL PRIMARY KEY,
    search_query VARCHAR(500) NOT NULL,
    search_type VARCHAR(20) NOT NULL CHECK (search_type IN ('keyword', 'url')),
    platforms TEXT[] NOT NULL,
    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'running', 'completed', 'failed')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    error_message TEXT,
    message TEXT,
    -- Summary statistics
    review_count INTEGER DEFAULT 0,
    positive_count INTEGER DEFAULT 0,
    negative_count INTEGER DEFAULT 0,
    neutral_count INTEGER DEFAULT 0,
    avg_rating DECIMAL(3,2),
    -- Keywords summary
    top_categories JSONB,
    total_keywords INTEGER DEFAULT 0
);

-- Crear tabla para almacenar reviews extraídas
CREATE TABLE IF NOT EXISTS reviews (
    id SERIAL PRIMARY KEY,
    job_id INTEGER REFERENCES scraping_jobs(id) ON DELETE CASCADE,
    platform VARCHAR(50) NOT NULL,
    review_id VARCHAR(200),
    rating DECIMAL(3,2),
    review_text TEXT,
    author_name VARCHAR(200),
    review_date DATE,
    helpful_votes INTEGER DEFAULT 0,
    source_url TEXT,
    scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    -- Sentiment analysis fields
    sentiment VARCHAR(20) CHECK (sentiment IN ('positive', 'negative', 'neutral')),
    sentiment_confidence DECIMAL(4,3),
    sentiment_scores JSONB,
    sentiment_error TEXT,
    -- Keywords analysis fields
    extracted_keywords JSONB,
    keyword_categories JSONB,
    detected_language VARCHAR(2),
    keyword_count INTEGER DEFAULT 0,
    -- Summary fields (BART)
    summary TEXT,
    has_summary BOOLEAN DEFAULT FALSE,
    -- Unique identifiers and metadata
    review_hash VARCHAR(32) UNIQUE,
    raw_data JSONB -- Almacenar datos originales completos
);

-- Crear tabla para configuración de plataformas
CREATE TABLE IF NOT EXISTS platform_configs (
    id SERIAL PRIMARY KEY,
    platform VARCHAR(50) UNIQUE NOT NULL,
    selectors JSONB NOT NULL, -- CSS selectors para extraer datos
    search_url_template VARCHAR(500),
    is_active BOOLEAN DEFAULT true,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Insertar configuraciones iniciales de plataformas
INSERT INTO platform_configs (platform, selectors, search_url_template) VALUES
('tripadvisor', '{
    "reviews": "[data-test-target=\"review-card\"]",
    "rating": "[data-test-target=\"review-rating\"]",
    "text": "[data-test-target=\"review-text\"]",
    "author": "[data-test-target=\"review-username\"]",
    "date": "[data-test-target=\"review-date\"]"
}', 'https://www.tripadvisor.es/Search?q={keyword}'),

('google', '{
    "reviews": "[data-review-id]",
    "rating": "[aria-label*=\"stars\"]",
    "text": "[data-expandable-section]",
    "author": "[aria-label*=\"review\"] [dir=\"ltr\"]",
    "date": "[aria-label*=\"ago\"]"
}', 'https://www.google.com/search?q={keyword}+reviews'),

('booking', '{
    "reviews": "[data-testid=\"review-card\"]",
    "rating": "[data-testid=\"review-score\"]",
    "text": "[data-testid=\"review-positive-text\"]",
    "author": "[data-testid=\"review-username\"]",
    "date": "[data-testid=\"review-date\"]"
}', 'https://www.booking.com/searchresults.html?ss={keyword}')

ON CONFLICT (platform) DO UPDATE SET
    selectors = EXCLUDED.selectors,
    search_url_template = EXCLUDED.search_url_template,
    updated_at = CURRENT_TIMESTAMP;

-- Crear tablas para análisis de keywords multiidioma
CREATE TABLE IF NOT EXISTS keyword_categories (
    category_key VARCHAR(50) PRIMARY KEY,
    category_en VARCHAR(100) NOT NULL,
    category_es VARCHAR(100),
    category_fr VARCHAR(100),
    description TEXT,
    icon VARCHAR(50),
    color VARCHAR(7) DEFAULT '#6B7280',
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS category_keywords (
    id SERIAL PRIMARY KEY,
    category_key VARCHAR(50) REFERENCES keyword_categories(category_key) ON DELETE CASCADE,
    keyword VARCHAR(100) NOT NULL,
    language VARCHAR(2) NOT NULL,
    weight DECIMAL(3,2) DEFAULT 1.0,
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(category_key, keyword, language)
);

-- Crear índices para mejorar rendimiento
CREATE INDEX IF NOT EXISTS idx_reviews_job_id ON reviews(job_id);
CREATE INDEX IF NOT EXISTS idx_reviews_platform ON reviews(platform);
CREATE INDEX IF NOT EXISTS idx_reviews_scraped_at ON reviews(scraped_at);
CREATE INDEX IF NOT EXISTS idx_reviews_hash ON reviews(review_hash);
CREATE INDEX IF NOT EXISTS idx_reviews_language ON reviews(detected_language);
CREATE INDEX IF NOT EXISTS idx_reviews_keywords ON reviews USING GIN(extracted_keywords);
CREATE INDEX IF NOT EXISTS idx_reviews_categories ON reviews USING GIN(keyword_categories);
CREATE INDEX IF NOT EXISTS idx_scraping_jobs_status ON scraping_jobs(status);
CREATE INDEX IF NOT EXISTS idx_scraping_jobs_created_at ON scraping_jobs(created_at);
CREATE INDEX IF NOT EXISTS idx_category_keywords_category ON category_keywords(category_key);
CREATE INDEX IF NOT EXISTS idx_category_keywords_language ON category_keywords(language);

-- Insertar categorías iniciales
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
('entertainment', 'Entertainment', 'Entretenimiento', 'Divertissement', 'fas fa-gamepad', '#A855F7')
ON CONFLICT (category_key) DO NOTHING;

-- Insertar keywords (todos los idiomas)
INSERT INTO category_keywords (category_key, keyword, language, weight) VALUES
-- Spanish keywords
('parking', 'parking', 'es', 1.0),
('parking', 'estacionamiento', 'es', 1.0),
('parking', 'coche', 'es', 0.8),
('pets', 'perro', 'es', 1.0),
('pets', 'mascota', 'es', 1.0),
('pets', 'animal', 'es', 0.9),
('reception_services', 'recepcion', 'es', 1.0),
('reception_services', 'servicio', 'es', 1.0),
('location', 'ubicacion', 'es', 1.0),
('location', 'cerca', 'es', 0.9),
('cleanliness', 'limpio', 'es', 1.0),
('cleanliness', 'sucio', 'es', 1.0),
('cleanliness', 'baño', 'es', 0.8),
('internet', 'internet', 'es', 1.0),
('internet', 'wifi', 'es', 1.0),
('price', 'precio', 'es', 1.0),
('price', 'barato', 'es', 0.9),
('beach_nature', 'playa', 'es', 1.0),

-- English keywords
('parking', 'parking', 'en', 1.0),
('parking', 'car', 'en', 0.8),
('pets', 'dog', 'en', 1.0),
('pets', 'pet', 'en', 1.0),
('cleanliness', 'clean', 'en', 1.0),
('cleanliness', 'dirty', 'en', 1.0),
('location', 'location', 'en', 1.0),
('internet', 'wifi', 'en', 1.0),
('price', 'price', 'en', 1.0),
('beach_nature', 'beach', 'en', 1.0),

-- French keywords
('parking', 'parking', 'fr', 1.0),
('pets', 'chien', 'fr', 1.0),
('cleanliness', 'propre', 'fr', 1.0),
('internet', 'wifi', 'fr', 1.0),
('beach_nature', 'plage', 'fr', 1.0),

-- ===== ADDITIONAL KEYWORDS (from updated migration) =====

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
('reception_services', 'mini market', 'en', 1.0)

ON CONFLICT (category_key, keyword, language) DO NOTHING;

-- Database initialization completed successfully
-- Note: Optional cleanup function removed to avoid SQL parsing issues
-- If needed, create cleanup functions manually via database admin tools

-- Final status check
SELECT 'Opinator database initialized with keywords!' as initialization_status;