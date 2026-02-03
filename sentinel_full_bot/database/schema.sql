CREATE TABLE IF NOT EXISTS users (
    id BIGINT PRIMARY KEY,
    power INT DEFAULT 0,
    trust INT DEFAULT 50,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS mod_logs (
    id SERIAL PRIMARY KEY,
    mod_id BIGINT,
    action TEXT,
    target_id BIGINT,
    created_at TIMESTAMP DEFAULT NOW()
);
