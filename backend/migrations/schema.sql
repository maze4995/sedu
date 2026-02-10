-- SEDU schema  –  PostgreSQL 15+
-- Internal PKs: uuid          (gen_random_uuid)
-- Public  IDs:  text prefix   (set_01J…, job_01J…, q_01J…, a_01J…)

CREATE EXTENSION IF NOT EXISTS "pgcrypto";          -- gen_random_uuid()

/* ------------------------------------------------------------------ */
/*  sets                                                               */
/* ------------------------------------------------------------------ */

CREATE TABLE sets (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    public_id       TEXT UNIQUE NOT NULL,             -- set_<ULID>

    status          TEXT NOT NULL DEFAULT 'created',  -- created | extracting | ready | error
    title           TEXT,
    file_name       TEXT,
    file_key        TEXT,                             -- object-storage key
    source_filename TEXT,
    source_mime     TEXT,
    source_size     BIGINT,

    question_count  INT  NOT NULL DEFAULT 0,

    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_sets_public_id ON sets (public_id);

/* ------------------------------------------------------------------ */
/*  extraction_jobs                                                    */
/* ------------------------------------------------------------------ */

CREATE TABLE extraction_jobs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    public_id       TEXT UNIQUE NOT NULL,             -- job_<ULID>

    set_id          UUID NOT NULL REFERENCES sets (id) ON DELETE CASCADE,

    status          TEXT NOT NULL DEFAULT 'queued',   -- queued | running | completed | failed
    stage           TEXT,                             -- e.g. upload | ocr | parse | review
    progress        REAL NOT NULL DEFAULT 0,          -- 0.0 – 1.0

    options         JSONB NOT NULL DEFAULT '{}',
    error_message   TEXT,

    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at    TIMESTAMPTZ
);

CREATE INDEX idx_extraction_jobs_public_id ON extraction_jobs (public_id);
CREATE INDEX idx_extraction_jobs_set_id    ON extraction_jobs (set_id, created_at DESC);

/* ------------------------------------------------------------------ */
/*  questions                                                          */
/* ------------------------------------------------------------------ */

CREATE TABLE questions (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    public_id           TEXT UNIQUE NOT NULL,         -- q_<ULID>

    set_id              UUID NOT NULL REFERENCES sets (id) ON DELETE CASCADE,

    order_index         INT  NOT NULL DEFAULT 0,
    number_label        TEXT,                         -- "1", "2-1", etc.

    original_image_key  TEXT,                         -- full page crop key
    cropped_image_key   TEXT,                         -- tight crop key
    ocr_text            TEXT,

    structure           JSONB NOT NULL DEFAULT '{}',  -- parsed stem / choices / answer
    metadata            JSONB NOT NULL DEFAULT '{}',  -- unit, difficulty, tags …

    confidence          REAL,
    review_status       TEXT NOT NULL DEFAULT 'pending', -- pending | approved | rejected

    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_questions_public_id  ON questions (public_id);
CREATE INDEX idx_questions_set_order  ON questions (set_id, order_index);

/* ------------------------------------------------------------------ */
/*  assets                                                             */
/* ------------------------------------------------------------------ */

CREATE TABLE assets (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    public_id       TEXT UNIQUE NOT NULL,             -- a_<ULID>

    question_id     UUID NOT NULL REFERENCES questions (id) ON DELETE CASCADE,

    type            TEXT NOT NULL,                    -- image | diagram | table | equation
    asset_key       TEXT NOT NULL,                    -- object-storage key
    bbox            JSONB,                            -- {x, y, w, h}

    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_assets_public_id ON assets (public_id);

/* ------------------------------------------------------------------ */
/*  question_revisions  (optional audit trail)                         */
/* ------------------------------------------------------------------ */

CREATE TABLE question_revisions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    question_id     UUID NOT NULL REFERENCES questions (id) ON DELETE CASCADE,

    revision_num    INT  NOT NULL,
    snapshot        JSONB NOT NULL,                   -- full question state at this revision
    changed_by      TEXT,

    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_question_revisions_qid ON question_revisions (question_id, revision_num);
