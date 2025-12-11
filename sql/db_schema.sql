CREATE TABLE IF NOT EXISTS products (
    id SERIAL PRIMARY KEY,
    url TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    brand TEXT,
    category TEXT,
    image_url TEXT,
    price NUMERIC(12,2),
    currency VARCHAR(10),
    page INT,
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_change_at TIMESTAMPTZ,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    data_hash TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS files (
    id SERIAL PRIMARY KEY,
    url TEXT NOT NULL UNIQUE,
    filename TEXT NOT NULL,
    local_path TEXT NOT NULL,
    mime_type TEXT,
    hash TEXT NOT NULL,
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_change_at TIMESTAMPTZ,
    is_active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS events (
    id SERIAL PRIMARY KEY,
    entity_type VARCHAR(20) NOT NULL,   -- 'product' o 'file'
    entity_id INT,
    event_type VARCHAR(40) NOT NULL,    -- 'created', 'updated', 'deleted', 'file_changed', etc.
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
