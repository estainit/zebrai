-- Create transcription_chunks table
CREATE TABLE IF NOT EXISTS transcription_chunks (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(100) NOT NULL,
    audio_chunk BYTEA NOT NULL,
    transcript TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create users table
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(20) NOT NULL CHECK (role IN ('admin', 'user')),
    conf JSONB DEFAULT '{"doTranscript": true}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create index on session_id for faster lookups
CREATE INDEX IF NOT EXISTS idx_transcription_chunks_session_id ON transcription_chunks(session_id);

-- Create index on username for faster lookups
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);

-- Insert initial users
INSERT INTO users (username, password_hash, role, conf) VALUES
('esta', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj4J/vYBxLri', 'admin', '{"doTranscript": true}'::jsonb),
('andy', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj4J/vYBxLri', 'admin', '{"doTranscript": false}'::jsonb)
ON CONFLICT (username) DO NOTHING; 