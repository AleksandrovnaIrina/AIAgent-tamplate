-- LumysAgent HR Database Schema

-- Chat sessions (Claude conversation continuity)
CREATE TABLE IF NOT EXISTS chat_sessions (
    chat_id     BIGINT PRIMARY KEY,
    claude_session_id TEXT,
    updated_at  TIMESTAMP DEFAULT NOW()
);

-- Long-term memory (used by mcp-memory)
CREATE TABLE IF NOT EXISTS memories (
    id          SERIAL PRIMARY KEY,
    text        TEXT NOT NULL,
    tags        TEXT[] DEFAULT '{}',
    created_at  TIMESTAMP DEFAULT NOW(),
    text_search TSVECTOR GENERATED ALWAYS AS (to_tsvector('simple', text)) STORED
);
CREATE INDEX IF NOT EXISTS memories_fts_idx ON memories USING GIN (text_search);

-- Vacancies / job descriptions
CREATE TABLE IF NOT EXISTS vacancies (
    id           SERIAL PRIMARY KEY,
    title        TEXT NOT NULL,
    company      TEXT,
    stack        TEXT[] DEFAULT '{}',
    seniority    TEXT,
    requirements TEXT,
    status       TEXT DEFAULT 'active',  -- active, paused, closed
    created_at   TIMESTAMP DEFAULT NOW()
);

-- Candidates pipeline
CREATE TABLE IF NOT EXISTS candidates (
    id          SERIAL PRIMARY KEY,
    name        TEXT NOT NULL,
    profile_url TEXT,
    source      TEXT,     -- linkedin, djinni, dou, referral, telegram
    status      TEXT DEFAULT 'new',  -- new, contacted, screening, interview, offer, rejected
    vacancy_id  INTEGER REFERENCES vacancies(id) ON DELETE SET NULL,
    notes       TEXT,
    created_at  TIMESTAMP DEFAULT NOW(),
    updated_at  TIMESTAMP DEFAULT NOW()
);

-- Outreach log
CREATE TABLE IF NOT EXISTS outreach (
    id             SERIAL PRIMARY KEY,
    candidate_id   INTEGER REFERENCES candidates(id) ON DELETE CASCADE,
    channel        TEXT,   -- linkedin, email, telegram
    content        TEXT,
    sent_at        TIMESTAMP,
    response       TEXT,
    responded_at   TIMESTAMP
);

-- Reminders
CREATE TABLE IF NOT EXISTS reminders (
    id          SERIAL PRIMARY KEY,
    chat_id     TEXT NOT NULL,
    message     TEXT NOT NULL,
    remind_at   TIMESTAMP NOT NULL,
    sent        BOOLEAN DEFAULT FALSE,
    created_at  TIMESTAMP DEFAULT NOW()
);

-- Auto-scout results
CREATE TABLE IF NOT EXISTS scout_results (
    id              SERIAL PRIMARY KEY,
    source          TEXT NOT NULL,  -- djinni, dou, linkedin_xray
    profile_url     TEXT UNIQUE,
    candidate_data  JSONB,
    vacancy_match   TEXT,
    reviewed        BOOLEAN DEFAULT FALSE,
    fetched_at      TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS scout_results_source_idx ON scout_results (source, fetched_at DESC);
