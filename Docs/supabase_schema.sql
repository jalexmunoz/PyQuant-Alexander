-- Supabase Schema: raw_events table
-- Iron Vault - Immutable event storage
--
-- Purpose: Store all webhook events from TradingView
-- Design: Immutable append-only table (never update/delete)

-- ============================================================================
-- TABLE: raw_events
-- ============================================================================

CREATE TABLE IF NOT EXISTS raw_events (
    -- Primary key (auto-increment)
    id BIGSERIAL PRIMARY KEY,
    
    -- Raw payload storage (immutable full event data)
    payload JSONB NOT NULL,  -- Complete raw webhook payload as JSON
    
    -- Indexed fields for efficient queries
    ticker VARCHAR(20) NOT NULL,    -- e.g., "BTCUSDT", "ETHUSDT"
    source VARCHAR(50) NOT NULL DEFAULT 'tradingview',  -- Source of the event
    
    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()  -- When row was inserted (auto)
);

-- ============================================================================
-- INDEXES (for efficient queries)
-- ============================================================================

-- Index on ticker (for filtering by asset)
CREATE INDEX IF NOT EXISTS idx_raw_events_ticker ON raw_events(ticker);

-- Index on source (for filtering by source)
CREATE INDEX IF NOT EXISTS idx_raw_events_source ON raw_events(source);

-- Index on created_at (for date-based queries)
CREATE INDEX IF NOT EXISTS idx_raw_events_created_at ON raw_events(created_at);

-- Composite index for common queries (date + ticker)
CREATE INDEX IF NOT EXISTS idx_raw_events_date_ticker ON raw_events(
    DATE(created_at), ticker
);

-- GIN index on payload JSONB for efficient JSON queries
CREATE INDEX IF NOT EXISTS idx_raw_events_payload_gin ON raw_events USING GIN (payload);

-- ============================================================================
-- ROW LEVEL SECURITY (RLS)
-- ============================================================================

-- Enable RLS (optional, depends on your security needs)
-- ALTER TABLE raw_events ENABLE ROW LEVEL SECURITY;

-- Policy: Allow service role to insert (for webhook receiver)
-- CREATE POLICY "Service role can insert events" ON raw_events
--     FOR INSERT
--     TO service_role
--     WITH CHECK (true);

-- Policy: Allow authenticated users to read
-- CREATE POLICY "Authenticated users can read events" ON raw_events
--     FOR SELECT
--     TO authenticated
--     USING (true);

-- ============================================================================
-- COMMENTS (documentation)
-- ============================================================================

COMMENT ON TABLE raw_events IS 'Immutable storage for all webhook events from TradingView';
COMMENT ON COLUMN raw_events.payload IS 'Complete raw webhook payload stored as JSONB (immutable)';
COMMENT ON COLUMN raw_events.ticker IS 'Asset ticker extracted from payload for indexing (e.g., BTCUSDT)';
COMMENT ON COLUMN raw_events.source IS 'Source of the webhook event (e.g., tradingview)';
COMMENT ON COLUMN raw_events.created_at IS 'Database insertion timestamp (automatically set)';

