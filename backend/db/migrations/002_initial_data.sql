-- Insert initial admin user
-- Note: In production, this password should be changed immediately
INSERT INTO users (username, password_hash, role)
VALUES (
    'admin',
    -- This is a bcrypt hash of 'admin' with 12 rounds
    '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewKyA2LQY1DdCJ0K',
    'admin'
)
ON CONFLICT (username) DO NOTHING; 