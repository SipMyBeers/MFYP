CREATE TABLE entities (
    entity_id UUID PRIMARY KEY,
    name TEXT NOT NULL,
    metadata JSONB, -- Stores specific 'Ditto' traits
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE ingestion_log (
    id SERIAL PRIMARY KEY,
    entity_id UUID REFERENCES entities(entity_id),
    url TEXT NOT NULL,
    content TEXT, -- Scraped body text
    processed_status TEXT DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
, platform TEXT DEFAULT 'Unknown', timestamp DATETIME, description TEXT, comments TEXT);
CREATE TABLE embeddings (
    embedding_id SERIAL PRIMARY KEY,
    entity_id UUID REFERENCES entities(entity_id),
    source_id INT REFERENCES ingestion_log(id),
    embedding_vector TEXT NOT NULL, -- Storage for RAG
    content_snippet TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE entity_links (source_id TEXT, target_id TEXT, relationship TEXT);
CREATE TABLE missions (id INTEGER PRIMARY KEY, goal TEXT, status TEXT, priority INTEGER);

-- BrowserOS tables
CREATE TABLE IF NOT EXISTS browser_tabs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    gorm_id TEXT NOT NULL,
    gorm_name TEXT NOT NULL,
    tab_url TEXT NOT NULL,
    platform TEXT NOT NULL,
    domain TEXT NOT NULL,
    status TEXT DEFAULT 'idle',
    last_active TEXT,
    UNIQUE(gorm_id, domain)
);

CREATE TABLE IF NOT EXISTS visit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    gorm_id TEXT NOT NULL,
    gorm_name TEXT NOT NULL,
    url TEXT NOT NULL,
    domain TEXT NOT NULL,
    platform TEXT NOT NULL,
    content_snippet TEXT,
    visited_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS domain_frequency (
    gorm_id TEXT NOT NULL,
    domain TEXT NOT NULL,
    visit_count INTEGER DEFAULT 1,
    last_visited TEXT DEFAULT (datetime('now')),
    source_requested INTEGER DEFAULT 0,
    PRIMARY KEY (gorm_id, domain)
);
