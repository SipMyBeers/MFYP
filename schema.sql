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
