-- Influence Connect schema for Supabase PostgreSQL
-- Run in Supabase Dashboard → SQL Editor (optional; Flask also creates tables via db.create_all())

CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(120) NOT NULL UNIQUE,
    username VARCHAR(80) UNIQUE,
    mobile VARCHAR(20) UNIQUE,
    password_hash VARCHAR(256) NOT NULL,
    role VARCHAR(20) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_users_email ON users (email);
CREATE INDEX IF NOT EXISTS ix_users_username ON users (username);
CREATE INDEX IF NOT EXISTS ix_users_mobile ON users (mobile);

CREATE TABLE IF NOT EXISTS categories (
    id SERIAL PRIMARY KEY,
    name VARCHAR(80) NOT NULL UNIQUE,
    slug VARCHAR(80) NOT NULL UNIQUE,
    icon VARCHAR(10) NOT NULL,
    color VARCHAR(20) NOT NULL DEFAULT '#6366f1'
);

CREATE TABLE IF NOT EXISTS brand_profiles (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    company_name VARCHAR(120) NOT NULL,
    industry VARCHAR(80),
    website VARCHAR(200),
    description TEXT,
    contact_email VARCHAR(120)
);

CREATE TABLE IF NOT EXISTS influencer_profiles (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    full_name VARCHAR(120) NOT NULL,
    category_id INTEGER NOT NULL REFERENCES categories(id),
    instagram_handle VARCHAR(80) NOT NULL,
    instagram_url VARCHAR(200),
    followers VARCHAR(30) DEFAULT '—',
    monthly_reach VARCHAR(30) DEFAULT '—',
    reel_pricing DOUBLE PRECISION NOT NULL DEFAULT 0,
    story_pricing DOUBLE PRECISION NOT NULL DEFAULT 0,
    post_pricing DOUBLE PRECISION NOT NULL DEFAULT 0,
    bio TEXT
);
