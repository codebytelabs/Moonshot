-- Autonomous Trading Bot Database Schema

-- Market data table
CREATE TABLE IF NOT EXISTS market_data (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    open DECIMAL NOT NULL,
    high DECIMAL NOT NULL,
    low DECIMAL NOT NULL,
    close DECIMAL NOT NULL,
    volume DECIMAL NOT NULL,
    UNIQUE(symbol, timeframe, timestamp)
);

CREATE INDEX IF NOT EXISTS idx_market_data_symbol_tf ON market_data(symbol, timeframe, timestamp DESC);

-- Watcher signals
CREATE TABLE IF NOT EXISTS watcher_signals (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    cycle_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    score DECIMAL NOT NULL,
    features JSONB NOT NULL,
    last_price DECIMAL NOT NULL,
    volume_24h DECIMAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_watcher_cycle ON watcher_signals(cycle_id);

-- Analyzer signals
CREATE TABLE IF NOT EXISTS analyzer_signals (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    cycle_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    ta_score DECIMAL NOT NULL,
    ml_probability DECIMAL NOT NULL,
    setup_type TEXT NOT NULL,
    pattern TEXT NOT NULL,
    mtf_alignment JSONB NOT NULL,
    entry_zone JSONB NOT NULL,
    stop_zone JSONB NOT NULL,
    target_zones JSONB NOT NULL
);

-- Context analysis
CREATE TABLE IF NOT EXISTS context_analysis (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    cycle_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    catalysts JSONB NOT NULL,
    sentiment TEXT NOT NULL,
    driver_type TEXT NOT NULL,
    sustainability_hours INTEGER NOT NULL,
    risks JSONB NOT NULL,
    narrative_strength DECIMAL NOT NULL,
    confidence DECIMAL NOT NULL
);

-- Decisions
CREATE TABLE IF NOT EXISTS decisions (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    cycle_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    prior DECIMAL NOT NULL,
    posterior DECIMAL NOT NULL,
    threshold DECIMAL NOT NULL,
    should_enter BOOLEAN NOT NULL,
    size_multiplier DECIMAL NOT NULL,
    conviction TEXT NOT NULL
);

-- Positions
CREATE TABLE IF NOT EXISTS positions (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    symbol TEXT NOT NULL,
    entry_price DECIMAL NOT NULL,
    entry_time TIMESTAMPTZ NOT NULL,
    quantity DECIMAL NOT NULL,
    stop_price DECIMAL NOT NULL,
    trailing_stop DECIMAL,
    setup_type TEXT NOT NULL,
    posterior DECIMAL NOT NULL,
    status TEXT NOT NULL,
    exit_price DECIMAL,
    exit_time TIMESTAMPTZ,
    pnl DECIMAL,
    pnl_pct DECIMAL,
    r_multiple DECIMAL,
    exit_reason TEXT,
    adds INTEGER DEFAULT 0,
    tier1_exited BOOLEAN DEFAULT FALSE,
    tier2_exited BOOLEAN DEFAULT FALSE,
    cycle_id TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_positions_symbol ON positions(symbol);
CREATE INDEX IF NOT EXISTS idx_positions_status ON positions(status);

-- Trades
CREATE TABLE IF NOT EXISTS trades (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    position_id BIGINT REFERENCES positions(id),
    symbol TEXT NOT NULL,
    action TEXT NOT NULL,
    price DECIMAL NOT NULL,
    quantity DECIMAL NOT NULL,
    notional DECIMAL NOT NULL,
    pnl DECIMAL,
    r_multiple DECIMAL,
    reason TEXT,
    mode TEXT NOT NULL
);

-- Performance metrics
CREATE TABLE IF NOT EXISTS performance_metrics (
    id BIGSERIAL PRIMARY KEY,
    date DATE NOT NULL UNIQUE,
    account_equity DECIMAL NOT NULL,
    daily_pnl DECIMAL NOT NULL,
    daily_pnl_pct DECIMAL NOT NULL,
    trades_count INTEGER NOT NULL,
    wins_count INTEGER NOT NULL,
    losses_count INTEGER NOT NULL,
    win_rate DECIMAL NOT NULL,
    avg_r_multiple DECIMAL NOT NULL,
    max_drawdown_pct DECIMAL NOT NULL
);

-- BigBrother events
CREATE TABLE IF NOT EXISTS bigbrother_events (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    event_type TEXT NOT NULL,
    severity TEXT NOT NULL,
    data JSONB NOT NULL,
    user_notified BOOLEAN DEFAULT FALSE
);

-- User interactions
CREATE TABLE IF NOT EXISTS user_interactions (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    user_message TEXT NOT NULL,
    bot_response TEXT NOT NULL,
    context JSONB
);
