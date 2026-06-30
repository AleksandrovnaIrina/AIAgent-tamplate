-- LumysAgent — Unified HR Schema (Argus + Scout + Sirius merged)

-- ── Shared memory (all agents) ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS memories (
    id          BIGSERIAL PRIMARY KEY,
    text        TEXT NOT NULL,
    tags        TEXT[] NOT NULL DEFAULT '{}',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    text_search TSVECTOR GENERATED ALWAYS AS (to_tsvector('simple', text)) STORED
);
CREATE INDEX IF NOT EXISTS memories_fts_idx     ON memories USING GIN (text_search);
CREATE INDEX IF NOT EXISTS memories_tags_idx    ON memories USING GIN (tags);
CREATE INDEX IF NOT EXISTS memories_created_idx ON memories (created_at DESC);

-- ── Chat sessions (orchestrator tracks last agent per chat) ──────────────────
CREATE TABLE IF NOT EXISTS chat_sessions (
    chat_id            BIGINT PRIMARY KEY,
    claude_session_id  TEXT,
    last_agent         TEXT DEFAULT 'lumys',
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── Bot settings (key-value config) ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS bot_settings (
    key    TEXT PRIMARY KEY,
    value  TEXT NOT NULL
);

-- ── Instagram competitor monitoring (Argus) ──────────────────────────────────
CREATE TABLE IF NOT EXISTS scout_state (
    competitor_handle TEXT PRIMARY KEY,
    last_post_id      TEXT,
    last_seen_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS scout_posts (
    post_id             TEXT PRIMARY KEY,
    competitor_handle   TEXT NOT NULL,
    post_url            TEXT,
    caption             TEXT,
    transcript          TEXT,
    original_transcript TEXT,
    transcript_ua       TEXT,
    hook                TEXT,
    likes             INTEGER,
    comments          INTEGER,
    views             INTEGER,
    engagement_rate   REAL,
    duration_seconds  REAL,
    video_url         TEXT,
    posted_at         TIMESTAMPTZ,
    raw               JSONB,
    fetched_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    sent_in_digest_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS scout_posts_handle_idx ON scout_posts (competitor_handle, posted_at DESC);
CREATE INDEX IF NOT EXISTS scout_posts_unsent_idx ON scout_posts (competitor_handle) WHERE sent_in_digest_at IS NULL;

-- ── HR pipeline (Scout) ───────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS vacancies (
    id           SERIAL PRIMARY KEY,
    title        TEXT NOT NULL,
    company      TEXT,
    stack        TEXT[] DEFAULT '{}',
    seniority    TEXT,
    requirements TEXT,
    status       TEXT DEFAULT 'active',
    created_at   TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS candidates (
    id          SERIAL PRIMARY KEY,
    name        TEXT NOT NULL,
    profile_url TEXT UNIQUE,
    source      TEXT,
    status      TEXT DEFAULT 'new',
    vacancy_id  INTEGER REFERENCES vacancies(id) ON DELETE SET NULL,
    notes       TEXT,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS outreach (
    id           SERIAL PRIMARY KEY,
    candidate_id INTEGER REFERENCES candidates(id) ON DELETE CASCADE,
    channel      TEXT,
    content      TEXT,
    sent_at      TIMESTAMPTZ,
    response     TEXT,
    responded_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS reminders (
    id         SERIAL PRIMARY KEY,
    chat_id    TEXT NOT NULL,
    message    TEXT NOT NULL,
    remind_at  TIMESTAMPTZ NOT NULL,
    sent       BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS hr_scout_results (
    id             SERIAL PRIMARY KEY,
    source         TEXT NOT NULL,
    profile_url    TEXT UNIQUE,
    candidate_data JSONB,
    vacancy_match  TEXT,
    reviewed       BOOLEAN DEFAULT FALSE,
    fetched_at     TIMESTAMPTZ DEFAULT NOW()
);
