-- Georgian RAG - PostgreSQL Initialization Script

-- Create request logs table
CREATE TABLE IF NOT EXISTS request_logs (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    query TEXT NOT NULL,
    language VARCHAR(10),
    response TEXT,
    num_sources INTEGER,
    duration_total FLOAT,
    duration_search FLOAT,
    duration_llm FLOAT,
    status VARCHAR(20),
    error_message TEXT,
    error_type VARCHAR(100),
    cache_hit BOOLEAN DEFAULT FALSE,
    top_k INTEGER,
    model_used VARCHAR(50),
    total_tokens INTEGER
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_request_logs_timestamp ON request_logs(timestamp);
CREATE INDEX IF NOT EXISTS idx_request_logs_status ON request_logs(status);
CREATE INDEX IF NOT EXISTS idx_request_logs_language ON request_logs(language);
CREATE INDEX IF NOT EXISTS idx_request_logs_cache_hit ON request_logs(cache_hit);

-- Create cache metrics table
CREATE TABLE IF NOT EXISTS cache_metrics (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    cache_type VARCHAR(50),
    hit_rate FLOAT,
    total_requests INTEGER,
    cache_hits INTEGER,
    cache_misses INTEGER
);

CREATE INDEX IF NOT EXISTS idx_cache_metrics_timestamp ON cache_metrics(timestamp);

-- Create system metrics table
CREATE TABLE IF NOT EXISTS system_metrics (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    metric_name VARCHAR(100),
    metric_value FLOAT,
    metric_unit VARCHAR(20)
);

CREATE INDEX IF NOT EXISTS idx_system_metrics_timestamp ON system_metrics(timestamp);
CREATE INDEX IF NOT EXISTS idx_system_metrics_name ON system_metrics(metric_name);

-- Grant permissions
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO raguser;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO raguser;

-- Success message
DO $$
BEGIN
    RAISE NOTICE 'Georgian RAG Database initialized successfully!';
END $$;