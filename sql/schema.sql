-- Tables for the live demo in Supabase Postgres. Safe to run more than once.
-- Loaded by: python -m src.export_demo

-- Pre-scored test-period transactions (Oct-Dec 2020). No names, street addresses,
-- dates of birth, or card numbers.
CREATE TABLE IF NOT EXISTS transactions_demo (
    transaction_id    CHAR(32) PRIMARY KEY,
    transaction_time  TIMESTAMP NOT NULL,
    merchant          TEXT NOT NULL,
    category          TEXT NOT NULL,
    amount            NUMERIC(10, 2) NOT NULL,
    city              TEXT NOT NULL,
    state             CHAR(2) NOT NULL,
    fraud_probability DOUBLE PRECISION NOT NULL CHECK (fraud_probability BETWEEN 0 AND 1),
    action            TEXT NOT NULL CHECK (action IN ('approve', 'review', 'block')),
    cost_approve      DOUBLE PRECISION NOT NULL,  -- expected cost of each action, in dollars
    cost_review       DOUBLE PRECISION NOT NULL,
    cost_block        DOUBLE PRECISION NOT NULL,
    loss_prevented    DOUBLE PRECISION NOT NULL,  -- expected dollars a review saves over the next-best action
    reason_1          TEXT NOT NULL,
    reason_2          TEXT NOT NULL,
    reason_3          TEXT NOT NULL,
    is_fraud          BOOLEAN NOT NULL            -- true label, shown only after an analyst decides
);

-- The queue page asks for one day at a time.
CREATE INDEX IF NOT EXISTS transactions_demo_day ON transactions_demo ((transaction_time::date));

-- Analyst decisions made in the web app.
CREATE TABLE IF NOT EXISTS reviews (
    id             BIGSERIAL PRIMARY KEY,
    transaction_id CHAR(32) NOT NULL REFERENCES transactions_demo (transaction_id),
    decision       TEXT NOT NULL CHECK (decision IN ('fraud', 'legitimate')),
    note           TEXT CHECK (char_length(note) <= 500),
    reviewed_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Supabase also exposes tables in the public schema through its own web API.
-- Row level security with no policies switches that path off; our API connects
-- with the database password from DATABASE_URL, which isn't affected.
ALTER TABLE transactions_demo ENABLE ROW LEVEL SECURITY;
ALTER TABLE reviews ENABLE ROW LEVEL SECURITY;
