-- =========================================================
--  VoiceHub database (PostgreSQL)
--  6 tables: clients, voice_actors, projects, auditions,
--            contracts, reviews
-- =========================================================

-- People who post voice-over projects
CREATE TABLE IF NOT EXISTS clients (
    client_id      SERIAL PRIMARY KEY,
    full_name      VARCHAR(100) NOT NULL,
    email          VARCHAR(150) NOT NULL UNIQUE,
    password_hash  TEXT         NOT NULL,
    company_name   VARCHAR(120),
    client_type    VARCHAR(20)  NOT NULL CHECK (client_type IN ('Individual', 'Company')),
    industry       VARCHAR(30)  NOT NULL CHECK (industry IN ('Advertising', 'Animation', 'Gaming',
                                     'YouTube', 'E-learning', 'Radio', 'Other')),
    phone          VARCHAR(20),
    city           VARCHAR(60),
    created_at     TIMESTAMP    NOT NULL DEFAULT NOW()
);

-- Voice actors who send auditions
CREATE TABLE IF NOT EXISTS voice_actors (
    actor_id          SERIAL PRIMARY KEY,
    full_name         VARCHAR(100) NOT NULL,
    email             VARCHAR(150) NOT NULL UNIQUE,
    password_hash     TEXT         NOT NULL,
    gender            VARCHAR(10)  NOT NULL CHECK (gender IN ('Male', 'Female', 'Other')),
    voice_age_range   VARCHAR(20)  NOT NULL CHECK (voice_age_range IN ('Child', 'Young adult', 'Adult', 'Senior')),
    voice_style       VARCHAR(60),
    languages         VARCHAR(120) NOT NULL,
    experience_years  INTEGER      NOT NULL DEFAULT 0 CHECK (experience_years >= 0),
    rate_pkr          INTEGER      NOT NULL CHECK (rate_pkr >= 0),
    city              VARCHAR(60),
    is_available      BOOLEAN      NOT NULL DEFAULT TRUE,
    bio               TEXT,
    rating            NUMERIC(2,1) NOT NULL DEFAULT 0,      -- average of reviews, updated by the app
    created_at        TIMESTAMP    NOT NULL DEFAULT NOW()
);

-- Casting calls posted by clients
CREATE TABLE IF NOT EXISTS projects (
    project_id         SERIAL PRIMARY KEY,
    client_id          INTEGER      NOT NULL REFERENCES clients(client_id) ON DELETE CASCADE,
    title              VARCHAR(150) NOT NULL,
    category           VARCHAR(30)  NOT NULL CHECK (category IN ('Commercial', 'Animation', 'Video game',
                                         'Audiobook', 'YouTube', 'E-learning', 'Documentary', 'Other')),
    script             TEXT         NOT NULL,
    language_required  VARCHAR(40)  NOT NULL,
    gender_preference  VARCHAR(10)  NOT NULL DEFAULT 'Any' CHECK (gender_preference IN ('Any', 'Male', 'Female')),
    budget_pkr         INTEGER      NOT NULL CHECK (budget_pkr > 0),
    deadline           DATE         NOT NULL,
    status             VARCHAR(20)  NOT NULL DEFAULT 'Open' CHECK (status IN ('Open', 'Hired', 'Completed')),
    created_at         TIMESTAMP    NOT NULL DEFAULT NOW()
);

-- Audio auditions sent by voice actors for a project
CREATE TABLE IF NOT EXISTS auditions (
    audition_id   SERIAL PRIMARY KEY,
    project_id    INTEGER      NOT NULL REFERENCES projects(project_id) ON DELETE CASCADE,
    actor_id      INTEGER      NOT NULL REFERENCES voice_actors(actor_id) ON DELETE CASCADE,
    audio_file    VARCHAR(200) NOT NULL,
    note          TEXT,
    status        VARCHAR(20)  NOT NULL DEFAULT 'Submitted' CHECK (status IN ('Submitted', 'Hired', 'Not selected')),
    submitted_at  TIMESTAMP    NOT NULL DEFAULT NOW(),
    UNIQUE (project_id, actor_id)                           -- one audition per actor per project
);

-- Created when a client hires an actor; tracks payment
CREATE TABLE IF NOT EXISTS contracts (
    contract_id     SERIAL PRIMARY KEY,
    project_id      INTEGER     NOT NULL UNIQUE REFERENCES projects(project_id) ON DELETE CASCADE,
    audition_id     INTEGER     NOT NULL REFERENCES auditions(audition_id) ON DELETE CASCADE,
    client_id       INTEGER     NOT NULL REFERENCES clients(client_id) ON DELETE CASCADE,
    actor_id        INTEGER     NOT NULL REFERENCES voice_actors(actor_id) ON DELETE CASCADE,
    amount_pkr      INTEGER     NOT NULL CHECK (amount_pkr > 0),
    payment_status  VARCHAR(10) NOT NULL DEFAULT 'Pending' CHECK (payment_status IN ('Pending', 'Paid')),
    created_at      TIMESTAMP   NOT NULL DEFAULT NOW(),
    paid_at         TIMESTAMP
);

-- Client's review of the actor after payment
CREATE TABLE IF NOT EXISTS reviews (
    review_id    SERIAL PRIMARY KEY,
    contract_id  INTEGER   NOT NULL UNIQUE REFERENCES contracts(contract_id) ON DELETE CASCADE,
    client_id    INTEGER   NOT NULL REFERENCES clients(client_id) ON DELETE CASCADE,
    actor_id     INTEGER   NOT NULL REFERENCES voice_actors(actor_id) ON DELETE CASCADE,
    rating       INTEGER   NOT NULL CHECK (rating BETWEEN 1 AND 5),
    comment      TEXT,
    created_at   TIMESTAMP NOT NULL DEFAULT NOW()
);
