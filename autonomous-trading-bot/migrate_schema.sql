-- Moonshot Trading Bot — Schema Migration
-- Run this in Supabase SQL Editor to fix missing columns
-- This drops existing tables and recreates them with the correct schema

-- Drop existing tables (order matters due to potential FK references)
DROP TABLE IF EXISTS user_interactions CASCADE;
DROP TABLE IF EXISTS bigbrother_events CASCADE;
DROP TABLE IF EXISTS performance_metrics CASCADE;
DROP TABLE IF EXISTS trades CASCADE;
DROP TABLE IF EXISTS positions CASCADE;
DROP TABLE IF EXISTS decisions CASCADE;
DROP TABLE IF EXISTS context_analysis CASCADE;
DROP TABLE IF EXISTS analyzer_signals CASCADE;
DROP TABLE IF EXISTS watcher_signals CASCADE;

-- Recreate all tables with correct schema
-- Watcher signals
CREATE TABLE watcher_signals (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    symbol TEXT NOT NULL,
    exchange TEXT DEFAULT 'gateio',
    score DOUBLE PRECISION,
    features JSONB DEFAULT '{}'
);

-- Analyzer signals
CREATE TABLE analyzer_signals (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    symbol TEXT NOT NULL,
    exchange TEXT DEFAULT 'gateio',
    setup_type TEXT,
    ta_score DOUBLE PRECISION,
    features JSONB DEFAULT '{}',
    entry_zone JSONB DEFAULT '{}'
);

-- Context analysis (Perplexity enrichment)
CREATE TABLE context_analysis (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    symbol TEXT NOT NULL,
    sentiment TEXT,
    confidence DOUBLE PRECISION,
    catalysts JSONB DEFAULT '[]',
    risks JSONB DEFAULT '[]',
    driver_type TEXT,
    narrative_strength DOUBLE PRECISION
);

-- Bayesian decisions
CREATE TABLE decisions (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    symbol TEXT NOT NULL,
    posterior DOUBLE PRECISION,
    action TEXT,
    setup_type TEXT,
    mode TEXT,
    reasoning JSONB DEFAULT '{}'
);

-- Positions
CREATE TABLE positions (
    id TEXT PRIMARY KEY,
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    symbol TEXT NOT NULL,
    exchange TEXT DEFAULT 'gateio',
    side TEXT DEFAULT 'long',
    status TEXT DEFAULT 'open',
    entry_price DOUBLE PRECISION,
    current_price DOUBLE PRECISION,
    quantity DOUBLE PRECISION,
    notional_usd DOUBLE PRECISION,
    unrealized_pnl DOUBLE PRECISION DEFAULT 0,
    stop_loss DOUBLE PRECISION,
    take_profit DOUBLE PRECISION
);

-- Trades
CREATE TABLE trades (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    position_id TEXT,
    symbol TEXT NOT NULL,
    exchange TEXT DEFAULT 'gateio',
    side TEXT,
    price DOUBLE PRECISION,
    quantity DOUBLE PRECISION,
    notional_usd DOUBLE PRECISION,
    trade_type TEXT,
    pnl DOUBLE PRECISION,
    r_multiple DOUBLE PRECISION
);

-- Performance metrics
CREATE TABLE performance_metrics (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    metric_type TEXT NOT NULL,
    value DOUBLE PRECISION,
    metadata JSONB DEFAULT '{}'
);

-- BigBrother events
CREATE TABLE bigbrother_events (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    event_type TEXT NOT NULL,
    severity TEXT,
    message TEXT,
    details JSONB DEFAULT '{}'
);

-- User interactions (chat)
CREATE TABLE user_interactions (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    interaction_type TEXT,
    content TEXT,
    response TEXT
);

-- Indexes for common queries
CREATE INDEX idx_watcher_signals_created ON watcher_signals(created_at DESC);
CREATE INDEX idx_analyzer_signals_created ON analyzer_signals(created_at DESC);
CREATE INDEX idx_decisions_created ON decisions(created_at DESC);
CREATE INDEX idx_trades_created ON trades(created_at DESC);
CREATE INDEX idx_positions_status ON positions(status);
CREATE INDEX idx_bigbrother_events_created ON bigbrother_events(created_at DESC);

-- Enable Row Level Security (optional but recommended)
ALTER TABLE watcher_signals ENABLE ROW LEVEL SECURITY;
ALTER TABLE analyzer_signals ENABLE ROW LEVEL SECURITY;
ALTER TABLE context_analysis ENABLE ROW LEVEL SECURITY;
ALTER TABLE decisions ENABLE ROW LEVEL SECURITY;
ALTER TABLE positions ENABLE ROW LEVEL SECURITY;
ALTER TABLE trades ENABLE ROW LEVEL SECURITY;
ALTER TABLE performance_metrics ENABLE ROW LEVEL SECURITY;
ALTER TABLE bigbrother_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_interactions ENABLE ROW LEVEL SECURITY;

-- Create policies for anon key access (allow all operations for service role)
CREATE POLICY "Allow all for anon" ON watcher_signals FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow all for anon" ON analyzer_signals FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow all for anon" ON context_analysis FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow all for anon" ON decisions FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow all for anon" ON positions FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow all for anon" ON trades FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow all for anon" ON performance_metrics FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow all for anon" ON bigbrother_events FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow all for anon" ON user_interactions FOR ALL USING (true) WITH CHECK (true);
