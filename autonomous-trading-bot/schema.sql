-- Moonshot Trading Bot — Supabase Schema
-- Run this in Supabase SQL Editor to create all required tables

-- Watcher signals
CREATE TABLE IF NOT EXISTS watcher_signals (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    symbol TEXT NOT NULL,
    exchange TEXT DEFAULT 'gateio',
    score DOUBLE PRECISION,
    features JSONB DEFAULT '{}'
);

-- Analyzer signals
CREATE TABLE IF NOT EXISTS analyzer_signals (
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
CREATE TABLE IF NOT EXISTS context_analysis (
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
CREATE TABLE IF NOT EXISTS decisions (
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
CREATE TABLE IF NOT EXISTS positions (
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
CREATE TABLE IF NOT EXISTS trades (
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
CREATE TABLE IF NOT EXISTS performance_metrics (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    metric_type TEXT NOT NULL,
    value DOUBLE PRECISION,
    metadata JSONB DEFAULT '{}'
);

-- BigBrother events
CREATE TABLE IF NOT EXISTS bigbrother_events (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    event_type TEXT NOT NULL,
    severity TEXT,
    message TEXT,
    details JSONB DEFAULT '{}'
);

-- User interactions (chat)
CREATE TABLE IF NOT EXISTS user_interactions (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    interaction_type TEXT,
    content TEXT,
    response TEXT
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_watcher_signals_created ON watcher_signals(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_analyzer_signals_created ON analyzer_signals(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_decisions_created ON decisions(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_trades_created ON trades(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_positions_status ON positions(status);
CREATE INDEX IF NOT EXISTS idx_bigbrother_events_created ON bigbrother_events(created_at DESC);
